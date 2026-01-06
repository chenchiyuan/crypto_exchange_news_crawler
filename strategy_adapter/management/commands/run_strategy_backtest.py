"""
策略回测管理命令
Run Strategy Backtest Command

执行策略回测，支持DDPS-Z等策略的历史数据验证。

功能特性:
    - 支持指定交易对和日期范围
    - 自动计算所需技术指标
    - 使用策略适配层执行回测
    - 输出详细的回测统计信息
    - 支持自定义无风险收益率（用于夏普率等风险调整指标）

使用示例:
    # 回测单个交易对（全部历史数据）
    python manage.py run_strategy_backtest ETHUSDT

    # 指定日期范围
    python manage.py run_strategy_backtest BTCUSDT --start-date 2025-01-01 --end-date 2025-12-31

    # 指定周期和市场类型
    python manage.py run_strategy_backtest ETHUSDT --interval 4h --market-type futures

    # 指定初始资金
    python manage.py run_strategy_backtest ETHUSDT --initial-cash 50000

    # 指定无风险收益率（用于风险调整指标）
    python manage.py run_strategy_backtest ETHUSDT --risk-free-rate 5.0

Related:
    - PRD: docs/iterations/013-strategy-adapter-layer/prd.md
    - Architecture: docs/iterations/013-strategy-adapter-layer/architecture.md
    - Tasks: docs/iterations/013-strategy-adapter-layer/tasks.md
    - TASK-014-010: CLI参数扩展（--risk-free-rate）
"""

import logging
from datetime import datetime
from decimal import Decimal

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from backtest.models import KLine
from ddps_z.calculators import EMACalculator
from strategy_adapter import DDPSZStrategy, StrategyAdapter
from strategy_adapter.core.unified_order_manager import UnifiedOrderManager
from strategy_adapter.core.metrics_calculator import MetricsCalculator
from strategy_adapter.core.equity_curve_builder import EquityCurveBuilder

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '执行策略回测（默认使用DDPS-Z策略）'
    requires_system_checks = []  # 跳过系统检查，避免vectorbt模块缺失导致的问题

    def add_arguments(self, parser):
        # 必填参数
        parser.add_argument(
            'symbol',
            type=str,
            help='交易对，如BTCUSDT、ETHUSDT'
        )

        # 可选参数
        parser.add_argument(
            '--start-date',
            type=str,
            help='开始日期 (格式: YYYY-MM-DD)，默认为最早数据'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='结束日期 (格式: YYYY-MM-DD)，默认为最新数据'
        )
        parser.add_argument(
            '--interval',
            type=str,
            default='4h',
            help='K线周期（默认: 4h）'
        )
        parser.add_argument(
            '--market-type',
            type=str,
            default='futures',
            choices=['futures', 'spot'],
            help='市场类型（默认: futures）'
        )
        parser.add_argument(
            '--initial-cash',
            type=float,
            default=10000.0,
            help='初始资金（默认: 10000 USDT）'
        )
        parser.add_argument(
            '--position-size',
            type=float,
            default=100.0,
            help='单笔买入金额（默认: 100 USDT）'
        )
        parser.add_argument(
            '--commission-rate',
            type=float,
            default=0.001,
            help='手续费率（默认: 0.001，即千一）'
        )
        parser.add_argument(
            '--risk-free-rate',
            type=float,
            default=3.0,
            help='无风险收益率（年化，百分比）（默认: 3.0%）。'
                 '用于计算夏普率等风险调整收益指标。'
                 '常见值：0.0（加密货币市场）、3.0（美国国债）、5.0（高风险市场）'
        )
        parser.add_argument(
            '--strategy',
            type=str,
            default='ddps-z',
            choices=['ddps-z'],
            help='策略类型（当前仅支持: ddps-z）'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细信息'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        market_type = options['market_type']
        initial_cash = options['initial_cash']
        position_size = options['position_size']
        commission_rate = options['commission_rate']
        risk_free_rate = options['risk_free_rate']
        strategy_name = options['strategy']
        verbose = options['verbose']

        # === Guard Clause: 验证risk_free_rate范围 ===
        if risk_free_rate < 0 or risk_free_rate > 100:
            self.stdout.write(self.style.WARNING(
                f'警告: risk-free-rate={risk_free_rate}% 超出合理范围 [0, 100]，'
                f'建议使用常见值：0.0（加密货币）、3.0（美国国债）、5.0（高风险市场）'
            ))

        # 解析日期
        start_date = None
        end_date = None
        if options['start_date']:
            try:
                start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
                start_date = timezone.make_aware(start_date)
            except ValueError:
                raise CommandError(f'日期格式错误: {options["start_date"]}，请使用 YYYY-MM-DD')

        if options['end_date']:
            try:
                end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
                end_date = timezone.make_aware(end_date)
            except ValueError:
                raise CommandError(f'日期格式错误: {options["end_date"]}，请使用 YYYY-MM-DD')

        # 输出回测配置
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 策略回测系统 ===\n'))
        self.stdout.write(f'策略: {strategy_name.upper()}')
        self.stdout.write(f'交易对: {symbol}')
        self.stdout.write(f'周期: {interval}')
        self.stdout.write(f'市场: {market_type}')
        self.stdout.write(f'初始资金: {initial_cash:.2f} USDT')
        self.stdout.write(f'单笔资金: {position_size:.2f} USDT')
        self.stdout.write(f'手续费率: {commission_rate:.4f} ({commission_rate*100:.2f}%)')
        self.stdout.write(f'无风险收益率: {risk_free_rate:.2f}%')
        if start_date:
            self.stdout.write(f'开始日期: {start_date.strftime("%Y-%m-%d")}')
        if end_date:
            self.stdout.write(f'结束日期: {end_date.strftime("%Y-%m-%d")}')
        self.stdout.write('')

        try:
            # Step 1: 加载K线数据
            self.stdout.write(self.style.MIGRATE_LABEL('[1/5] 加载K线数据...'))
            klines_df = self._load_klines(symbol, interval, market_type, start_date, end_date)
            self.stdout.write(self.style.SUCCESS(
                f'✓ 加载成功: {len(klines_df)}根K线'
            ))
            if verbose:
                self.stdout.write(f'  时间范围: {klines_df.index[0]} ~ {klines_df.index[-1]}')

            # Step 2: 计算技术指标
            self.stdout.write(self.style.MIGRATE_LABEL('[2/5] 计算技术指标...'))
            indicators = self._calculate_indicators(klines_df, symbol, interval, market_type, verbose=verbose)
            self.stdout.write(self.style.SUCCESS(
                f'✓ 计算完成: {len(indicators)}个指标'
            ))
            if verbose:
                for name in indicators.keys():
                    self.stdout.write(f'  - {name}')

            # Step 3: 创建策略实例
            self.stdout.write(self.style.MIGRATE_LABEL('[3/5] 初始化策略...'))
            strategy = self._create_strategy(strategy_name, position_size)
            self.stdout.write(self.style.SUCCESS(
                f'✓ 策略创建: {strategy.get_strategy_name()} v{strategy.get_strategy_version()}'
            ))

            # Step 4: 执行回测
            self.stdout.write(self.style.MIGRATE_LABEL('[4/5] 执行回测...'))
            # 创建UnifiedOrderManager并传入手续费率
            order_manager = UnifiedOrderManager(commission_rate=Decimal(str(commission_rate)))
            adapter = StrategyAdapter(strategy, order_manager=order_manager)
            result = adapter.adapt_for_backtest(klines_df, indicators)
            self.stdout.write(self.style.SUCCESS('✓ 回测完成'))

            # Step 5: 输出结果
            self.stdout.write(self.style.MIGRATE_LABEL('[5/5] 回测结果'))
            self._display_results(result, initial_cash, klines_df, risk_free_rate, verbose)

            self.stdout.write(self.style.SUCCESS('\n✅ 回测执行成功\n'))

        except Exception as e:
            logger.exception(f"回测失败: {e}")
            raise CommandError(f'回测失败: {str(e)}')

    def _load_klines(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_date=None,
        end_date=None
    ) -> pd.DataFrame:
        """
        从数据库加载K线数据

        Returns:
            pd.DataFrame: 包含OHLCV的DataFrame，index为时间
        """
        queryset = KLine.objects.filter(
            symbol=symbol,
            interval=interval,
            market_type=market_type
        )

        if start_date:
            queryset = queryset.filter(open_time__gte=start_date)
        if end_date:
            queryset = queryset.filter(open_time__lte=end_date)

        queryset = queryset.order_by('open_time')

        if not queryset.exists():
            raise ValueError(
                f"没有找到K线数据: {symbol} {interval} {market_type}\n"
                f"请先运行: python manage.py update_klines --symbol {symbol} --interval {interval} --market-type {market_type}"
            )

        # 转换为DataFrame
        data = list(queryset.values(
            'open_time', 'open_price', 'high_price',
            'low_price', 'close_price', 'volume'
        ))

        df = pd.DataFrame(data)

        # 重命名列
        df = df.rename(columns={
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'close_price': 'close',
            'volume': 'volume'
        })

        # 转换为float
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        # 设置索引
        df = df.set_index('open_time')

        return df

    def _calculate_indicators(self, klines_df: pd.DataFrame, symbol: str, interval: str, market_type: str, verbose=False) -> dict:
        """
        计算DDPS-Z策略所需的技术指标（复用DDPSService完整逻辑）

        修复说明（Bug-015）:
        本方法之前使用简化版指标计算，导致买入信号触发率极低（2/2190）。
        现修改为完全复用DDPSService和InertiaCalculator的完整计算逻辑，
        确保与DDPS-Z详情页100%一致。

        Args:
            klines_df: K线数据DataFrame
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            verbose: 是否显示详细信息

        Returns:
            dict: 包含ema25, p5, beta, inertia_mid的指标字典
        """
        from ddps_z.services.ddps_service import DDPSService
        from ddps_z.calculators.adx_calculator import ADXCalculator
        from ddps_z.calculators.inertia_calculator import InertiaCalculator

        # 初始化服务
        ddps_service = DDPSService()
        adx_calc = ADXCalculator(period=14)
        inertia_calc = InertiaCalculator(base_period=5)

        if verbose:
            self.stdout.write('  复用DDPSService完整计算逻辑:')

        try:
            # Step 1: 使用DDPSService计算完整的DDPS序列
            series_result = ddps_service.calculate_series(
                symbol=symbol,
                interval=interval,
                market_type=market_type,
                limit=len(klines_df)
            )

            if not series_result['success']:
                raise ValueError(f"DDPSService计算失败: {series_result['error']}")

            series = series_result['series']

            # 提取基础指标
            ema_array = np.array([
                v if v is not None else np.nan
                for v in series['ema']
            ])

            # Step 2: 提取ewma_std序列（用于P5和惯性计算）
            ewma_std_series = np.array([
                v if v is not None else np.nan
                for v in series.get('ewma_std', [np.nan] * len(ema_array))
            ])

            # 计算P5价格序列（静态阈值下界）
            # 公式: p5_price = EMA × (1 + z_p5 × ewma_std)
            # 其中 z_p5 = -1.645 对应正态分布5%分位
            z_p5 = -1.645
            p5_array = ema_array * (1 + z_p5 * ewma_std_series)

            if verbose:
                self.stdout.write('    ✓ EMA25序列计算完成')
                self.stdout.write('    ✓ EWMA标准差序列提取完成')
                self.stdout.write('    ✓ P5价格序列计算完成')

            # Step 3: 计算ADX序列（用于惯性计算）
            high = klines_df['high'].values
            low = klines_df['low'].values
            close = klines_df['close'].values

            adx_result = adx_calc.calculate(high, low, close)
            adx_series = adx_result['adx']

            if verbose:
                self.stdout.write('    ✓ ADX序列计算完成')

            # Step 4: 使用InertiaCalculator计算惯性扇面
            timestamps = np.array(series['timestamps'])

            fan_result = inertia_calc.calculate_historical_fan_series(
                timestamps=timestamps,
                ema_series=ema_array,
                sigma_series=ewma_std_series,
                adx_series=adx_series
            )

            # 提取惯性指标
            beta_array = fan_result['beta']
            inertia_mid_array = fan_result['mid']

            if verbose:
                self.stdout.write('    ✓ β斜率序列计算完成')
                self.stdout.write('    ✓ 惯性中值序列计算完成')

            # Step 5: 转换为pandas Series（确保index对齐）
            indicators = {
                'ema25': pd.Series(ema_array, index=klines_df.index),
                'p5': pd.Series(p5_array, index=klines_df.index),
                'beta': pd.Series(beta_array, index=klines_df.index),
                'inertia_mid': pd.Series(inertia_mid_array, index=klines_df.index),
            }

            if verbose:
                self.stdout.write('    ✓ 指标序列对齐完成')
                self.stdout.write('')
                self.stdout.write('  【指标统计】')
                self.stdout.write(f'    - EMA25: {np.nanmean(ema_array):.2f} (均值)')
                self.stdout.write(f'    - P5: {p5_array[0]:.2f} (分位值)')
                self.stdout.write(f'    - β斜率: {np.nanmean(beta_array):.4f} (均值)')
                self.stdout.write(f'    - 惯性mid: {np.nanmean(inertia_mid_array):.2f} (均值)')

            return indicators

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ 指标计算失败: {e}'))
            logger.exception(f"指标计算失败: {e}")
            raise

    def _create_strategy(self, strategy_name: str, position_size: float):
        """
        创建策略实例

        Args:
            strategy_name (str): 策略名称
            position_size (float): 单笔买入金额（USDT）

        Returns:
            IStrategy: 策略实例
        """
        if strategy_name == 'ddps-z':
            return DDPSZStrategy(position_size=Decimal(str(position_size)))
        else:
            raise ValueError(f'不支持的策略: {strategy_name}')

    def _display_results(
        self,
        result: dict,
        initial_cash: float,
        klines_df: pd.DataFrame,
        risk_free_rate: float = 3.0,
        verbose: bool = False
    ):
        """
        展示回测结果（分层报告输出）

        Purpose:
            以分层结构展示回测结果，支持默认模式和详细模式。
            默认模式输出15个P0核心指标，详细模式输出所有可用指标。

        Args:
            result (dict): adapt_for_backtest()返回的结果
            initial_cash (float): 初始资金
            klines_df (pd.DataFrame): K线数据（用于计算时间范围和权益曲线）
            risk_free_rate (float): 无风险收益率（百分比），默认3.0%
            verbose (bool): 是否显示详细信息，默认False

        Report Structure (分层报告结构):
            - 【基本信息】：数据周期、时间范围、初始资金
            - 【订单统计】：总订单数、持仓中、已平仓
            - 【收益分析】：APR、绝对收益、累计收益率
            - 【风险分析】：MDD、波动率、恢复时间（verbose模式）
            - 【风险调整收益】：夏普率、卡玛比率、MAR比率、盈利因子
            - 【交易效率】：交易频率、成本占比、胜率、盈亏比

        Context:
            关联任务：TASK-014-011
            关联需求：FP-014-016
        """
        stats = result['statistics']
        orders = result['orders']

        # === 步骤1: 计算回测天数 ===
        start_time = klines_df.index[0]
        end_time = klines_df.index[-1]
        days = max((end_time - start_time).days, 1)

        # === 步骤2: 构建权益曲线 ===
        # 准备K线数据（用于EquityCurveBuilder）
        klines_for_builder = pd.DataFrame({
            'open_time': [int(ts.timestamp() * 1000) for ts in klines_df.index],
            'close': klines_df['close'].values
        })

        equity_curve = EquityCurveBuilder.build_from_orders(
            orders=orders,
            klines=klines_for_builder,
            initial_cash=Decimal(str(initial_cash))
        )

        # === 步骤3: 计算所有量化指标 ===
        # 将百分比形式的risk_free_rate转换为小数形式
        rfr_decimal = Decimal(str(risk_free_rate)) / Decimal("100")
        calculator = MetricsCalculator(risk_free_rate=rfr_decimal)
        metrics = calculator.calculate_all_metrics(
            orders=orders,
            equity_curve=equity_curve,
            initial_cash=Decimal(str(initial_cash)),
            days=days
        )

        # === 辅助函数：格式化指标值 ===
        def fmt(value, suffix: str = "", positive_prefix: str = "") -> str:
            """格式化指标值，None显示为N/A"""
            if value is None:
                return "N/A"
            if isinstance(value, Decimal):
                value = float(value)
            if positive_prefix and value > 0:
                return f"{positive_prefix}{value:.2f}{suffix}"
            return f"{value:.2f}{suffix}"

        def fmt_pnl(value, suffix: str = ""):
            """格式化盈亏值，带颜色"""
            if value is None:
                return self.stdout.write("  N/A")
            v = float(value) if isinstance(value, Decimal) else value
            text = f"{v:+.2f}{suffix}" if v != 0 else f"{v:.2f}{suffix}"
            style = self.style.SUCCESS if v >= 0 else self.style.ERROR
            return style(text)

        # === 步骤4: 输出基本信息 ===
        self.stdout.write('')
        self.stdout.write('【基本信息】')
        self.stdout.write(f'  数据周期: {len(klines_df)}根K线')
        self.stdout.write(f'  时间范围: {start_time.strftime("%Y-%m-%d")} ~ {end_time.strftime("%Y-%m-%d")} ({days}天)')
        self.stdout.write(f'  初始资金: {initial_cash:.2f} USDT')

        # === 步骤5: 输出订单统计 ===
        self.stdout.write('')
        self.stdout.write('【订单统计】')
        self.stdout.write(f'  总订单数: {stats["total_orders"]}')
        self.stdout.write(f'  持仓中: {stats["open_orders"]}')
        self.stdout.write(f'  已平仓: {stats["closed_orders"]}')

        # === 步骤6: 输出收益分析 ===
        self.stdout.write('')
        self.stdout.write('【收益分析】')

        # APR
        apr_val = metrics['apr']
        apr_style = self.style.SUCCESS if apr_val and apr_val >= 0 else self.style.ERROR
        self.stdout.write(apr_style(f'  年化收益率(APR): {fmt(apr_val, "%")}'))

        # 绝对收益
        abs_ret = metrics['absolute_return']
        abs_style = self.style.SUCCESS if abs_ret and abs_ret >= 0 else self.style.ERROR
        self.stdout.write(abs_style(f'  绝对收益: {fmt(abs_ret, " USDT", "+")}'))

        # 累计收益率
        cum_ret = metrics['cumulative_return']
        cum_style = self.style.SUCCESS if cum_ret and cum_ret >= 0 else self.style.ERROR
        self.stdout.write(cum_style(f'  累计收益率: {fmt(cum_ret, "%")}'))

        # === 步骤7: 输出风险分析 ===
        self.stdout.write('')
        self.stdout.write('【风险分析】')

        # MDD
        mdd_val = metrics['mdd']
        mdd_style = self.style.ERROR if mdd_val and mdd_val < Decimal("-10") else self.style.WARNING
        if mdd_val == Decimal("0"):
            mdd_style = self.style.SUCCESS
        self.stdout.write(mdd_style(f'  最大回撤(MDD): {fmt(mdd_val, "%")}'))

        # 波动率
        vol_val = metrics['volatility']
        self.stdout.write(f'  年化波动率: {fmt(vol_val, "%")}')

        # verbose模式：显示回撤时间区间和恢复时间
        if verbose:
            if metrics['mdd_start_time'] and metrics['mdd_end_time']:
                self.stdout.write(f'  回撤开始: {metrics["mdd_start_time"]}')
                self.stdout.write(f'  回撤结束: {metrics["mdd_end_time"]}')
            if metrics['recovery_time']:
                self.stdout.write(f'  恢复时间: {metrics["recovery_time"]}')
            else:
                self.stdout.write(self.style.WARNING('  恢复状态: 未恢复'))

        # === 步骤8: 输出风险调整收益 ===
        self.stdout.write('')
        self.stdout.write('【风险调整收益】')

        # 夏普率
        sharpe = metrics['sharpe_ratio']
        if sharpe is not None:
            sharpe_style = self.style.SUCCESS if sharpe >= Decimal("1") else \
                           (self.style.WARNING if sharpe >= Decimal("0.5") else self.style.ERROR)
            self.stdout.write(sharpe_style(f'  夏普率: {fmt(sharpe)}'))
        else:
            self.stdout.write('  夏普率: N/A（波动率为0）')

        # 卡玛比率
        calmar = metrics['calmar_ratio']
        if calmar is not None:
            calmar_style = self.style.SUCCESS if calmar >= Decimal("1") else self.style.WARNING
            self.stdout.write(calmar_style(f'  卡玛比率: {fmt(calmar)}'))
        else:
            self.stdout.write('  卡玛比率: N/A（无回撤）')

        # MAR比率
        mar = metrics['mar_ratio']
        if mar is not None:
            mar_style = self.style.SUCCESS if mar >= Decimal("1") else self.style.WARNING
            self.stdout.write(mar_style(f'  MAR比率: {fmt(mar)}'))
        else:
            self.stdout.write('  MAR比率: N/A（无回撤）')

        # 盈利因子
        pf = metrics['profit_factor']
        if pf is not None:
            pf_style = self.style.SUCCESS if pf >= Decimal("1.5") else \
                       (self.style.WARNING if pf >= Decimal("1") else self.style.ERROR)
            self.stdout.write(pf_style(f'  盈利因子: {fmt(pf)}'))
        else:
            self.stdout.write('  盈利因子: N/A（无亏损订单）')

        # === 步骤9: 输出交易效率 ===
        self.stdout.write('')
        self.stdout.write('【交易效率】')

        # 交易频率
        freq = metrics['trade_frequency']
        self.stdout.write(f'  交易频率: {fmt(freq, " 次/天")}')

        # 成本占比
        cost_pct = metrics['cost_percentage']
        if cost_pct is not None:
            cost_style = self.style.SUCCESS if cost_pct <= Decimal("5") else self.style.WARNING
            self.stdout.write(cost_style(f'  成本占比: {fmt(cost_pct, "%")}'))
        else:
            self.stdout.write('  成本占比: N/A（无盈利）')

        # 胜率
        win_rate = metrics['win_rate']
        wr_style = self.style.SUCCESS if win_rate >= Decimal("50") else self.style.WARNING
        self.stdout.write(wr_style(f'  胜率: {fmt(win_rate, "%")}'))

        # 盈亏比
        payoff = metrics['payoff_ratio']
        if payoff is not None:
            payoff_style = self.style.SUCCESS if payoff >= Decimal("1.5") else \
                           (self.style.WARNING if payoff >= Decimal("1") else self.style.ERROR)
            self.stdout.write(payoff_style(f'  盈亏比: {fmt(payoff)}'))
        else:
            self.stdout.write('  盈亏比: N/A（无亏损订单）')

        # === 步骤10: verbose模式额外信息 ===
        if verbose:
            self.stdout.write('')
            self.stdout.write('【详细统计】')
            self.stdout.write(f'  盈利订单: {stats["win_orders"]}')
            self.stdout.write(f'  亏损订单: {stats["lose_orders"]}')

            total_commission = float(stats['total_commission'])
            self.stdout.write(f'  总手续费: {total_commission:.2f} USDT')

            # 极值订单
            if stats['closed_orders'] > 0:
                closed_orders = [o for o in orders if o.status.value == 'closed']
                max_profit_order = max(closed_orders, key=lambda o: o.profit_loss or 0)
                max_loss_order = min(closed_orders, key=lambda o: o.profit_loss or 0)

                max_profit = float(max_profit_order.profit_loss)
                max_profit_rate = float(max_profit_order.profit_loss_rate)
                max_loss = float(max_loss_order.profit_loss)
                max_loss_rate = float(max_loss_order.profit_loss_rate)

                self.stdout.write(self.style.SUCCESS(
                    f'  最佳订单: +{max_profit:.2f} USDT ({max_profit_rate:+.2f}%)'
                ))
                self.stdout.write(self.style.ERROR(
                    f'  最差订单: {max_loss:.2f} USDT ({max_loss_rate:+.2f}%)'
                ))

            # 持仓时长
            if stats['closed_orders'] > 0:
                closed_orders = [o for o in orders if o.status.value == 'closed']
                if closed_orders and closed_orders[0].holding_periods is not None:
                    avg_holding = sum(o.holding_periods for o in closed_orders if o.holding_periods) / len(closed_orders)
                    self.stdout.write(f'  平均持仓: {avg_holding:.1f}根K线')

        self.stdout.write('')
