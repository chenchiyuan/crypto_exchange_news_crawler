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
    - 支持多策略组合回测（TASK-017）

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

    # 多策略组合回测（使用配置文件）
    python manage.py run_strategy_backtest --config path/to/project.json

Related:
    - PRD: docs/iterations/013-strategy-adapter-layer/prd.md
    - Architecture: docs/iterations/013-strategy-adapter-layer/architecture.md
    - Tasks: docs/iterations/013-strategy-adapter-layer/tasks.md
    - TASK-014-010: CLI参数扩展（--risk-free-rate）
    - TASK-017-015: 多策略配置文件支持
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
        # 位置参数（使用--config时可选）
        parser.add_argument(
            'symbol',
            type=str,
            nargs='?',  # 使用--config时可选
            default=None,
            help='交易对，如BTCUSDT、ETHUSDT（使用--config时可从配置读取）'
        )

        # 多策略配置文件（TASK-017）
        parser.add_argument(
            '--config',
            type=str,
            help='多策略配置文件路径（JSON格式）。使用此参数时，从配置文件读取所有参数。'
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
            '--strategies',
            type=str,
            default='1,2',
            help='策略组合，逗号分隔（默认: 1,2）。'
                 '1=EMA斜率做多, 2=惯性下跌做多, '
                 '3=EMA斜率做空, 4=惯性上涨做空。'
                 '示例: --strategies 1,2,3,4'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细信息'
        )
        parser.add_argument(
            '--save-to-db',
            action='store_true',
            help='将回测结果保存到数据库。保存后可在Web界面查看和分析历史回测记录。'
        )

    def handle(self, *args, **options):
        from django.core.management.base import CommandError
        from strategy_adapter.core.strategy_selector import StrategySelector

        # === TASK-017: 检查是否使用配置文件模式 ===
        config_path = options.get('config')
        if config_path:
            return self._handle_multi_strategy(config_path, options)

        # === 单策略模式（向后兼容）===
        symbol = options['symbol']
        if not symbol:
            raise CommandError('必须提供交易对参数（如 ETHUSDT）或使用 --config 参数')
        symbol = symbol.upper()

        interval = options['interval']
        market_type = options['market_type']
        initial_cash = options['initial_cash']
        position_size = options['position_size']
        commission_rate = options['commission_rate']
        risk_free_rate = options['risk_free_rate']
        strategy_name = options['strategy']
        strategies_str = options['strategies']
        verbose = options['verbose']
        save_to_db = options['save_to_db']

        # === 解析策略组合 ===
        try:
            enabled_strategies = StrategySelector.parse(strategies_str)
        except ValueError as e:
            raise CommandError(str(e))

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
            strategy = self._create_strategy(strategy_name, position_size, enabled_strategies)
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

            # Step 6: 保存到数据库（可选）
            if save_to_db:
                self.stdout.write(self.style.MIGRATE_LABEL('\n[6/6] 保存到数据库...'))
                record_id = self._save_backtest_result(
                    result=result,
                    klines_df=klines_df,
                    options={
                        'strategy_name': strategy_name,
                        'symbol': symbol,
                        'interval': interval,
                        'market_type': market_type,
                        'initial_cash': initial_cash,
                        'position_size': position_size,
                        'commission_rate': commission_rate,
                        'risk_free_rate': risk_free_rate,
                    }
                )
                self.stdout.write(self.style.SUCCESS(
                    f'✓ 保存成功: ID={record_id}'
                ))

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

            # 计算P95价格序列（静态阈值上界）
            # 公式: p95_price = EMA × (1 + z_p95 × ewma_std)
            # 其中 z_p95 = +1.645 对应正态分布95%分位
            z_p95 = +1.645
            p95_array = ema_array * (1 + z_p95 * ewma_std_series)

            if verbose:
                self.stdout.write('    ✓ EMA25序列计算完成')
                self.stdout.write('    ✓ EWMA标准差序列提取完成')
                self.stdout.write('    ✓ P5价格序列计算完成')
                self.stdout.write('    ✓ P95价格序列计算完成')

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
                'p95': pd.Series(p95_array, index=klines_df.index),
                'beta': pd.Series(beta_array, index=klines_df.index),
                'inertia_mid': pd.Series(inertia_mid_array, index=klines_df.index),
            }

            if verbose:
                self.stdout.write('    ✓ 指标序列对齐完成')
                self.stdout.write('')
                self.stdout.write('  【指标统计】')
                self.stdout.write(f'    - EMA25: {np.nanmean(ema_array):.2f} (均值)')
                self.stdout.write(f'    - P5: {np.nanmean(p5_array):.2f} (下界)')
                self.stdout.write(f'    - P95: {np.nanmean(p95_array):.2f} (上界)')
                self.stdout.write(f'    - β斜率: {np.nanmean(beta_array):.4f} (均值)')
                self.stdout.write(f'    - 惯性mid: {np.nanmean(inertia_mid_array):.2f} (均值)')

            return indicators

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ 指标计算失败: {e}'))
            logger.exception(f"指标计算失败: {e}")
            raise

    def _create_strategy(self, strategy_name: str, position_size: float, enabled_strategies: list):
        """
        创建策略实例

        Args:
            strategy_name (str): 策略名称
            position_size (float): 单笔买入金额（USDT）
            enabled_strategies (list): 启用的策略ID列表（1-4）

        Returns:
            IStrategy: 策略实例
        """
        if strategy_name == 'ddps-z':
            return DDPSZStrategy(
                position_size=Decimal(str(position_size)),
                enabled_strategies=enabled_strategies
            )
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

        # 多空分类统计
        long_orders = [o for o in orders if o.direction == 'long']
        short_orders = [o for o in orders if o.direction == 'short']
        long_closed = [o for o in long_orders if o.status.value == 'closed']
        short_closed = [o for o in short_orders if o.status.value == 'closed']

        if long_orders or short_orders:
            self.stdout.write('')
            self.stdout.write(f'  做多订单: {len(long_orders)} (持仓{len(long_orders) - len(long_closed)}, 已平仓{len(long_closed)})')
            self.stdout.write(f'  做空订单: {len(short_orders)} (持仓{len(short_orders) - len(short_closed)}, 已平仓{len(short_closed)})')

            # 获取最新价格（用于计算未实现盈亏）
            latest_price = Decimal(str(klines_df['close'].iloc[-1])) if not klines_df.empty else None

            # 做多胜率和盈亏统计
            if long_closed or (len(long_orders) > len(long_closed)):
                if long_closed:
                    long_win = [o for o in long_closed if o.profit_loss and o.profit_loss > 0]
                    long_win_rate = len(long_win) / len(long_closed) * 100
                    # 已平仓订单的实现盈亏
                    long_realized_pnl = sum(o.profit_loss for o in long_closed if o.profit_loss)
                else:
                    long_win_rate = 0
                    long_realized_pnl = Decimal("0")

                # 🆕 Bug-018扩展修复：计算持仓订单的未实现盈亏
                long_open_orders = [o for o in long_orders if o.status.value == 'filled']
                long_unrealized_pnl = Decimal("0")
                if long_open_orders and latest_price:
                    for order in long_open_orders:
                        # 做多未实现盈亏 = (当前价格 - 开仓价格) × 数量 - 已付手续费
                        mtm_pnl = (latest_price - order.open_price) * order.quantity - order.open_commission
                        long_unrealized_pnl += mtm_pnl

                long_total_pnl = long_realized_pnl + long_unrealized_pnl

                if long_closed:
                    long_style = self.style.SUCCESS if long_win_rate >= 50 else self.style.WARNING
                    if long_open_orders:
                        self.stdout.write(long_style(
                            f'    做多胜率: {long_win_rate:.2f}% ({len(long_win)}/{len(long_closed)}), '
                            f'总盈亏: {long_total_pnl:+.2f} USDT (已实现{long_realized_pnl:+.2f}, 未实现{long_unrealized_pnl:+.2f})'
                        ))
                    else:
                        self.stdout.write(long_style(
                            f'    做多胜率: {long_win_rate:.2f}% ({len(long_win)}/{len(long_closed)}), '
                            f'总盈亏: {long_total_pnl:+.2f} USDT'
                        ))
                elif long_open_orders:
                    # 仅有持仓订单，无已平仓订单
                    self.stdout.write(
                        f'    做多持仓未实现盈亏: {long_unrealized_pnl:+.2f} USDT'
                    )

            # 做空胜率和盈亏统计
            if short_closed or (len(short_orders) > len(short_closed)):
                if short_closed:
                    short_win = [o for o in short_closed if o.profit_loss and o.profit_loss > 0]
                    short_win_rate = len(short_win) / len(short_closed) * 100
                    short_realized_pnl = sum(o.profit_loss for o in short_closed if o.profit_loss)
                else:
                    short_win_rate = 0
                    short_realized_pnl = Decimal("0")

                # 🆕 Bug-018扩展修复：计算持仓订单的未实现盈亏
                short_open_orders = [o for o in short_orders if o.status.value == 'filled']
                short_unrealized_pnl = Decimal("0")
                if short_open_orders and latest_price:
                    for order in short_open_orders:
                        # 做空未实现盈亏 = (开仓价格 - 当前价格) × 数量 - 已付手续费
                        mtm_pnl = (order.open_price - latest_price) * order.quantity - order.open_commission
                        short_unrealized_pnl += mtm_pnl

                short_total_pnl = short_realized_pnl + short_unrealized_pnl

                if short_closed:
                    short_style = self.style.SUCCESS if short_win_rate >= 50 else self.style.WARNING
                    if short_open_orders:
                        self.stdout.write(short_style(
                            f'    做空胜率: {short_win_rate:.2f}% ({len(short_win)}/{len(short_closed)}), '
                            f'总盈亏: {short_total_pnl:+.2f} USDT (已实现{short_realized_pnl:+.2f}, 未实现{short_unrealized_pnl:+.2f})'
                        ))
                    else:
                        self.stdout.write(short_style(
                            f'    做空胜率: {short_win_rate:.2f}% ({len(short_win)}/{len(short_closed)}), '
                            f'总盈亏: {short_total_pnl:+.2f} USDT'
                        ))
                elif short_open_orders:
                    # 仅有持仓订单，无已平仓订单
                    self.stdout.write(
                        f'    做空持仓未实现盈亏: {short_unrealized_pnl:+.2f} USDT'
                    )

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

    def _save_backtest_result(
        self,
        result: dict,
        klines_df: pd.DataFrame,
        options: dict
    ) -> int:
        """
        将回测结果保存到数据库

        Purpose:
            将回测结果持久化存储到数据库，包括回测配置、权益曲线、
            量化指标和订单详情。使用事务确保数据一致性。

        Args:
            result (dict): adapt_for_backtest() 返回的结果，包含：
                - orders: 订单列表（Order 对象）
                - statistics: 统计信息
            klines_df (pd.DataFrame): K线数据（用于计算权益曲线和时间范围）
            options (dict): CLI参数字典，包含：
                - strategy_name: 策略名称
                - symbol: 交易对
                - interval: K线周期
                - market_type: 市场类型
                - initial_cash: 初始资金
                - position_size: 单笔金额
                - commission_rate: 手续费率
                - risk_free_rate: 无风险收益率

        Returns:
            int: 保存的 BacktestResult 记录 ID

        Side Effects:
            - 在数据库中创建 BacktestResult 记录
            - 批量创建 BacktestOrder 记录（关联到 BacktestResult）

        Context:
            关联任务：TASK-014-014
            关联需求：FP-014-018, FP-014-019
        """
        from django.db import transaction
        from strategy_adapter.models.db_models import BacktestResult, BacktestOrder

        orders = result['orders']

        # === 步骤1: 计算回测时间范围 ===
        start_time = klines_df.index[0]
        end_time = klines_df.index[-1]
        days = max((end_time - start_time).days, 1)

        # === 步骤2: 构建权益曲线 ===
        klines_for_builder = pd.DataFrame({
            'open_time': [int(ts.timestamp() * 1000) for ts in klines_df.index],
            'close': klines_df['close'].values
        })

        equity_curve = EquityCurveBuilder.build_from_orders(
            orders=orders,
            klines=klines_for_builder,
            initial_cash=Decimal(str(options['initial_cash']))
        )

        # 转换为可序列化的列表格式
        equity_curve_data = [
            {
                'timestamp': point.timestamp,
                'cash': str(point.cash),
                'position_value': str(point.position_value),
                'equity': str(point.equity),
                'equity_rate': str(point.equity_rate)
            }
            for point in equity_curve
        ]

        # === 步骤3: 计算量化指标 ===
        rfr_decimal = Decimal(str(options['risk_free_rate'])) / Decimal("100")
        calculator = MetricsCalculator(risk_free_rate=rfr_decimal)
        metrics = calculator.calculate_all_metrics(
            orders=orders,
            equity_curve=equity_curve,
            initial_cash=Decimal(str(options['initial_cash'])),
            days=days
        )

        # 转换为可序列化的字典格式
        metrics_data = {
            k: str(v) if isinstance(v, Decimal) else v
            for k, v in metrics.items()
        }

        # === 步骤4: 使用事务保存数据 ===
        with transaction.atomic():
            # 创建 BacktestResult 记录
            backtest_result = BacktestResult.objects.create(
                strategy_name=options['strategy_name'].upper(),
                symbol=options['symbol'],
                interval=options['interval'],
                market_type=options['market_type'],
                start_date=start_time.date(),
                end_date=end_time.date(),
                initial_cash=Decimal(str(options['initial_cash'])),
                position_size=Decimal(str(options['position_size'])),
                commission_rate=Decimal(str(options['commission_rate'])),
                risk_free_rate=Decimal(str(options['risk_free_rate'])),
                equity_curve=equity_curve_data,
                metrics=metrics_data
            )

            # 批量创建 BacktestOrder 记录
            order_objects = [
                BacktestOrder(
                    backtest_result=backtest_result,
                    order_id=order.id,
                    status=order.status.value,
                    buy_price=order.open_price,
                    buy_timestamp=order.open_timestamp,
                    sell_price=order.close_price,
                    sell_timestamp=order.close_timestamp,
                    quantity=order.quantity,
                    position_value=order.position_value,
                    commission=order.open_commission + order.close_commission,
                    profit_loss=order.profit_loss,
                    profit_loss_rate=order.profit_loss_rate,
                    holding_periods=order.holding_periods,
                    direction=order.direction  # 添加direction字段
                )
                for order in orders
            ]
            BacktestOrder.objects.bulk_create(order_objects)

        return backtest_result.id

    # === TASK-017: 多策略回测支持 ===

    def _handle_multi_strategy(self, config_path: str, options: dict):
        """
        处理多策略回测（使用配置文件）

        Purpose:
            从JSON配置文件加载多策略回测项目，执行组合回测。

        Args:
            config_path: 配置文件路径
            options: CLI选项（verbose, save_to_db）

        Context:
            关联任务：TASK-017-015
            关联功能点：FP-017-018
        """
        from strategy_adapter.core import (
            ProjectLoader, ProjectLoaderError,
            StrategyFactory, SharedCapitalManager,
            MultiStrategyAdapter, UnifiedOrderManager
        )
        from strategy_adapter.exits import (
            ExitConditionCombiner, create_exit_condition
        )

        verbose = options.get('verbose', False)
        save_to_db = options.get('save_to_db', False)

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 多策略组合回测系统 ===\n'))

        try:
            # === Step 1: 加载配置文件 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[1/6] 加载配置文件...'))
            loader = ProjectLoader()
            project_config = loader.load(config_path)
            self.stdout.write(self.style.SUCCESS(
                f'✓ 加载成功: {project_config.project_name}'
            ))
            if verbose:
                self.stdout.write(f'  描述: {project_config.description}')
                self.stdout.write(f'  版本: {project_config.version}')

            # 提取配置
            backtest_config = project_config.backtest_config
            capital_config = project_config.capital_management
            enabled_strategies = project_config.get_enabled_strategies()

            self.stdout.write(f'  交易对: {backtest_config.symbol}')
            self.stdout.write(f'  周期: {backtest_config.interval}')
            self.stdout.write(f'  市场: {backtest_config.market_type}')
            self.stdout.write(f'  初始资金: {backtest_config.initial_cash} USDT')
            self.stdout.write(f'  单笔仓位: {capital_config.position_size} USDT')
            self.stdout.write(f'  最大持仓: {capital_config.max_positions}')
            self.stdout.write(f'  启用策略: {len(enabled_strategies)}个')
            self.stdout.write('')

            # === Step 2: 加载K线数据 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[2/6] 加载K线数据...'))

            # 解析日期
            start_date = None
            end_date = None
            if backtest_config.start_date:
                start_date = datetime.strptime(backtest_config.start_date, '%Y-%m-%d')
                start_date = timezone.make_aware(start_date)
            if backtest_config.end_date:
                end_date = datetime.strptime(backtest_config.end_date, '%Y-%m-%d')
                end_date = timezone.make_aware(end_date)

            klines_df = self._load_klines(
                backtest_config.symbol,
                backtest_config.interval,
                backtest_config.market_type,
                start_date, end_date
            )
            self.stdout.write(self.style.SUCCESS(
                f'✓ 加载成功: {len(klines_df)}根K线'
            ))

            # === Step 3: 计算技术指标 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[3/6] 计算技术指标...'))
            indicators = self._calculate_indicators(
                klines_df,
                backtest_config.symbol,
                backtest_config.interval,
                backtest_config.market_type,
                verbose=verbose
            )
            self.stdout.write(self.style.SUCCESS(
                f'✓ 计算完成: {len(indicators)}个指标'
            ))

            # === Step 4: 创建策略实例和卖出条件 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[4/6] 初始化策略...'))

            strategies = []  # [(config_strategy_id, strategy_instance), ...]
            exit_combiners = {}  # {config_strategy_id: combiner}

            for strategy_config in enabled_strategies:
                # 创建策略实例
                strategy = StrategyFactory.create(strategy_config)
                strategies.append((strategy_config.id, strategy))

                # 创建卖出条件组合器
                combiner = ExitConditionCombiner()
                for exit_config in strategy_config.exits:
                    condition = create_exit_condition(exit_config)
                    combiner.add_condition(condition)
                exit_combiners[strategy_config.id] = combiner

                self.stdout.write(self.style.SUCCESS(
                    f'  ✓ {strategy_config.id}: {strategy_config.name} '
                    f'({len(strategy_config.exits)}个卖出条件)'
                ))

            # === Step 5: 执行多策略回测 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[5/6] 执行回测...'))

            # 初始化资金管理器
            capital_manager = SharedCapitalManager(
                initial_cash=backtest_config.initial_cash,
                max_positions=capital_config.max_positions,
                position_size=capital_config.position_size
            )

            # 初始化订单管理器
            order_manager = UnifiedOrderManager(
                commission_rate=backtest_config.commission_rate
            )

            # 创建多策略适配器
            adapter = MultiStrategyAdapter(
                strategies=strategies,
                exit_combiners=exit_combiners,
                capital_manager=capital_manager,
                order_manager=order_manager,
                commission_rate=backtest_config.commission_rate
            )

            # 执行回测
            result = adapter.adapt_for_backtest(
                klines=klines_df,
                indicators=indicators,
                initial_cash=backtest_config.initial_cash,
                symbol=backtest_config.symbol
            )
            self.stdout.write(self.style.SUCCESS('✓ 回测完成'))

            # === Step 6: 输出结果 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[6/6] 回测结果'))
            self._display_multi_strategy_results(
                result, project_config, klines_df, verbose
            )

            # 保存到数据库（可选）
            if save_to_db:
                self.stdout.write(self.style.MIGRATE_LABEL('\n[7/7] 保存到数据库...'))
                # TODO: 实现多策略结果保存
                self.stdout.write(self.style.WARNING(
                    '⚠ 多策略结果保存功能尚未实现'
                ))

            self.stdout.write(self.style.SUCCESS('\n✅ 多策略回测执行成功\n'))

        except ProjectLoaderError as e:
            raise CommandError(f'配置文件加载失败: {e}')
        except Exception as e:
            logger.exception(f"多策略回测失败: {e}")
            raise CommandError(f'回测失败: {str(e)}')

    def _display_multi_strategy_results(
        self,
        result: dict,
        project_config: 'ProjectConfig',
        klines_df: pd.DataFrame,
        verbose: bool = False
    ):
        """
        展示多策略回测结果

        Args:
            result: 回测结果
            project_config: 项目配置
            klines_df: K线数据
            verbose: 是否显示详细信息
        """
        stats = result['statistics']
        strategy_stats = result['strategy_statistics']
        orders = result['orders']

        # 计算时间范围
        start_time = klines_df.index[0]
        end_time = klines_df.index[-1]
        days = max((end_time - start_time).days, 1)

        # === 基本信息 ===
        self.stdout.write('')
        self.stdout.write('【基本信息】')
        self.stdout.write(f'  项目: {project_config.project_name}')
        self.stdout.write(f'  数据周期: {len(klines_df)}根K线')
        self.stdout.write(f'  时间范围: {start_time.strftime("%Y-%m-%d")} ~ {end_time.strftime("%Y-%m-%d")} ({days}天)')
        self.stdout.write(f'  初始资金: {project_config.backtest_config.initial_cash} USDT')

        # === 整体统计 ===
        self.stdout.write('')
        self.stdout.write('【整体统计】')
        self.stdout.write(f'  总订单数: {stats["total_orders"]}')
        self.stdout.write(f'  已平仓: {stats["closed_orders"]}')
        self.stdout.write(f'  持仓中: {stats["open_orders"]}')

        # 盈亏统计
        net_profit = stats['net_profit']
        profit_style = self.style.SUCCESS if net_profit >= 0 else self.style.ERROR
        self.stdout.write(profit_style(f'  净利润: {net_profit:+.2f} USDT'))

        # 胜率
        win_rate = stats['win_rate']
        wr_style = self.style.SUCCESS if win_rate >= 50 else self.style.WARNING
        self.stdout.write(wr_style(f'  胜率: {win_rate:.2f}%'))

        # 收益率
        return_rate = stats['return_rate']
        ret_style = self.style.SUCCESS if return_rate >= 0 else self.style.ERROR
        self.stdout.write(ret_style(f'  收益率: {return_rate:+.2f}%'))

        # === 按策略分组统计 ===
        self.stdout.write('')
        self.stdout.write('【策略分组统计】')
        for strategy_id, s_stats in strategy_stats.items():
            # 获取策略配置
            strategy_config = project_config.get_strategy_by_id(strategy_id)
            strategy_name = strategy_config.name if strategy_config else strategy_id

            s_win_rate = s_stats['win_rate']
            s_net_profit = s_stats['net_profit']

            profit_style = self.style.SUCCESS if s_net_profit >= 0 else self.style.ERROR
            wr_style = self.style.SUCCESS if s_win_rate >= 50 else self.style.WARNING

            self.stdout.write(f'  [{strategy_id}] {strategy_name}')
            self.stdout.write(f'    订单: {s_stats["total_orders"]} (已平仓{s_stats["closed_orders"]})')
            self.stdout.write(wr_style(f'    胜率: {s_win_rate:.2f}%'))
            self.stdout.write(profit_style(f'    净利润: {s_net_profit:+.2f} USDT'))
            self.stdout.write('')

        # === 详细模式：显示订单列表 ===
        if verbose and orders:
            self.stdout.write('【最近订单】')
            for order in orders[-10:]:  # 只显示最后10个订单
                pnl_str = f'{order.profit_loss:+.2f}' if order.profit_loss else 'N/A'
                self.stdout.write(
                    f'  {order.id}: {order.config_strategy_id} | '
                    f'{order.status.value} | PnL: {pnl_str}'
                )
            if len(orders) > 10:
                self.stdout.write(f'  ... 共{len(orders)}个订单')
