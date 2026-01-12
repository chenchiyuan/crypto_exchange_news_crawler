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
from ddps_z.datasources import CSVFetcher
from strategy_adapter import DDPSZStrategy, StrategyAdapter
from strategy_adapter.core.unified_order_manager import UnifiedOrderManager
from strategy_adapter.core.metrics_calculator import MetricsCalculator
from strategy_adapter.core.equity_curve_builder import EquityCurveBuilder
from strategy_adapter.models import Order, OrderStatus, OrderSide

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

    def _load_klines_from_csv(
        self,
        csv_path: str,
        interval: str,
        timestamp_unit: str,
        start_date=None,
        end_date=None
    ) -> pd.DataFrame:
        """
        从CSV文件加载K线数据

        Args:
            csv_path: CSV文件路径
            interval: K线周期（1s, 1m等）
            timestamp_unit: 时间戳单位（microseconds/milliseconds/seconds）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            pd.DataFrame: 包含OHLCV的DataFrame，index为时间

        Related:
            - TASK-025-013: 集成CSV数据源到run_strategy_backtest
        """
        # 转换日期为毫秒时间戳
        start_ms = None
        end_ms = None
        if start_date:
            start_ms = int(start_date.timestamp() * 1000)
        if end_date:
            end_ms = int(end_date.timestamp() * 1000)

        # 创建CSVFetcher并加载数据
        fetcher = CSVFetcher(
            csv_path=csv_path,
            interval=interval,
            timestamp_unit=timestamp_unit
        )

        # 使用CSVFetcher获取数据（返回List[StandardKLine]）
        klines = fetcher.fetch(
            symbol='',  # CSV数据不需要symbol
            interval=interval,
            limit=0,  # 0表示不限制
            start_time=start_ms,
            end_time=end_ms
        )

        if not klines:
            raise ValueError(f"CSV文件中没有找到K线数据: {csv_path}")

        # 转换为DataFrame
        data = []
        for kline in klines:
            data.append({
                'open_time': pd.Timestamp(kline.timestamp, unit='ms', tz='UTC'),
                'open': float(kline.open),
                'high': float(kline.high),
                'low': float(kline.low),
                'close': float(kline.close),
                'volume': float(kline.volume)
            })

        df = pd.DataFrame(data)
        df = df.set_index('open_time')

        return df

    def _calculate_indicators(self, klines_df: pd.DataFrame, symbol: str, interval: str, market_type: str, verbose=False) -> dict:
        """
        计算DDPS-Z策略所需的技术指标（直接基于传入的K线数据）

        🔧 Bug-021修复：避免向前看偏差
        - 原问题：调用DDPSService.calculate_series()会重新从数据库查询最新的N根K线
          导致使用了未来数据计算历史时刻的指标（Look-Ahead Bias）
        - 修复方案：直接使用传入的klines_df计算所有指标，确保每根K线的指标只使用该K线之前的历史数据

        修复说明（Bug-015）:
        本方法之前使用简化版指标计算，导致买入信号触发率极低（2/2190）。
        现修改为完全复用各计算器的完整计算逻辑，确保与DDPS-Z详情页100%一致。

        Args:
            klines_df: K线数据DataFrame
            symbol: 交易对符号
            interval: K线周期
            market_type: 市场类型
            verbose: 是否显示详细信息

        Returns:
            dict: 包含ema25, p5, p95, beta, inertia_mid, cycle_phase的指标字典
        """
        from ddps_z.calculators.adx_calculator import ADXCalculator
        from ddps_z.calculators.inertia_calculator import InertiaCalculator

        # 初始化计算器
        adx_calc = ADXCalculator(period=14)
        inertia_calc = InertiaCalculator(base_period=5)

        if verbose:
            self.stdout.write('  直接基于传入K线计算指标（避免向前看偏差）:')

        try:
            # 🔧 Bug-021修复：直接基于传入的K线数据计算指标，避免向前看偏差
            # 原问题：调用DDPSService.calculate_series()会重新从数据库查询最新的N根K线
            # 导致使用了未来数据计算历史时刻的指标

            from ddps_z.calculators.ema_calculator import EMACalculator
            from ddps_z.calculators.ewma_calculator import EWMACalculator

            # 初始化计算器
            ema_calc = EMACalculator(period=25)
            ema7_calc = EMACalculator(period=7)
            ema99_calc = EMACalculator(period=99)
            ewma_calc = EWMACalculator(window_n=50)

            # 提取价格序列（从传入的klines_df）
            prices = klines_df['close'].values
            timestamps_ms = np.array([int(ts.timestamp() * 1000) for ts in klines_df.index])

            # Step 1: 计算EMA序列（EMA7, EMA25, EMA99）
            ema_array = ema_calc.calculate_ema_series(prices)
            ema7_array = ema7_calc.calculate_ema_series(prices)
            ema99_array = ema99_calc.calculate_ema_series(prices)

            if verbose:
                self.stdout.write('    ✓ EMA7/EMA25/EMA99序列计算完成')

            # Step 2: 计算偏离率序列和EWMA标准差
            deviation = ema_calc.calculate_deviation_series(prices)
            ewma_mean, ewma_std_series = ewma_calc.calculate_ewma_stats(deviation)

            if verbose:
                self.stdout.write('    ✓ EWMA标准差序列计算完成')

            # Step 3: 计算P5和P95价格序列（静态阈值）
            z_p5 = -1.645
            z_p95 = +1.645
            p5_array = ema_array * (1 + z_p5 * ewma_std_series)
            p95_array = ema_array * (1 + z_p95 * ewma_std_series)

            if verbose:
                self.stdout.write('    ✓ P5价格序列计算完成')
                self.stdout.write('    ✓ P95价格序列计算完成')

            # Step 4: 计算ADX序列（用于惯性计算）
            high = klines_df['high'].values
            low = klines_df['low'].values
            close = klines_df['close'].values

            adx_result = adx_calc.calculate(high, low, close)
            adx_series = adx_result['adx']

            if verbose:
                self.stdout.write('    ✓ ADX序列计算完成')

            # Step 5: 使用InertiaCalculator计算惯性扇面和β序列
            fan_result = inertia_calc.calculate_historical_fan_series(
                timestamps=timestamps_ms,
                ema_series=ema_array,
                sigma_series=ewma_std_series,
                adx_series=adx_series
            )

            # 提取惯性指标
            beta_array = fan_result['beta']
            inertia_mid_array = fan_result['mid']
            inertia_upper_array = fan_result['upper']  # 🆕 Bug-022: 添加惯性扇面上界
            inertia_lower_array = fan_result['lower']  # 扇面下界（备用）

            if verbose:
                self.stdout.write('    ✓ β斜率序列计算完成')
                self.stdout.write('    ✓ 惯性中值序列计算完成')
                self.stdout.write('    ✓ 惯性扇面上界计算完成')  # 🆕 Bug-022

            # Step 6: 计算β宏观周期状态 (cycle_phase)
            from ddps_z.calculators.beta_cycle_calculator import BetaCycleCalculator

            cycle_calc = BetaCycleCalculator()
            beta_list_for_cycle = [
                b if not np.isnan(b) else None
                for b in beta_array
            ]
            prices_list = prices.tolist()

            cycle_phases, current_cycle_info = cycle_calc.calculate(
                beta_list=beta_list_for_cycle,
                timestamps=timestamps_ms.tolist(),
                prices=prices_list,
                interval_hours=4.0  # 4小时K线
            )

            if verbose:
                self.stdout.write('    ✓ β宏观周期状态计算完成')
                self.stdout.write(f'      当前周期: {current_cycle_info.get("phase_label", "未知")}')

            # Step 7: 转换为pandas Series（确保index对齐）
            indicators = {
                'ema7': pd.Series(ema7_array, index=klines_df.index),
                'ema25': pd.Series(ema_array, index=klines_df.index),
                'ema99': pd.Series(ema99_array, index=klines_df.index),
                'p5': pd.Series(p5_array, index=klines_df.index),
                'p95': pd.Series(p95_array, index=klines_df.index),
                'beta': pd.Series(beta_array, index=klines_df.index),
                'inertia_mid': pd.Series(inertia_mid_array, index=klines_df.index),
                'inertia_upper': pd.Series(inertia_upper_array, index=klines_df.index),  # 🆕 Bug-022
                'inertia_lower': pd.Series(inertia_lower_array, index=klines_df.index),  # 备用
                'cycle_phase': pd.Series(cycle_phases, index=klines_df.index),
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
                self.stdout.write(f'    - 惯性upper: {np.nanmean(inertia_upper_array):.2f} (均值)')  # 🆕 Bug-022
                # cycle_phase统计
                from collections import Counter
                phase_counts = Counter(cycle_phases)
                bull_strong_count = phase_counts.get('bull_strong', 0)
                self.stdout.write(f'    - cycle_phase: 强势上涨 {bull_strong_count}/{len(cycle_phases)} 根K线')

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

        # === 步骤10: 输出交易成本 ===
        self.stdout.write('')
        self.stdout.write('【交易成本】')

        # 总交易量
        total_volume = stats.get('total_volume', Decimal("0"))
        self.stdout.write(f'  总交易量: {float(total_volume):.2f} USDT')

        # 总手续费
        total_commission = float(stats['total_commission'])
        self.stdout.write(f'  总手续费: {total_commission:.2f} USDT')

        # === 步骤11: verbose模式额外信息 ===
        if verbose:
            self.stdout.write('')
            self.stdout.write('【详细统计】')
            self.stdout.write(f'  盈利订单: {stats["win_orders"]}')
            self.stdout.write(f'  亏损订单: {stats["lose_orders"]}')

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

    def _save_multi_strategy_result(
        self,
        result: dict,
        project_config: 'ProjectConfig',
        klines_df: pd.DataFrame
    ) -> int:
        """
        保存多策略回测结果到数据库

        Purpose:
            将多策略组合回测结果持久化存储，支持策略组合名称和多个策略的订单。

        Args:
            result (dict): adapt_for_backtest() 返回的结果，包含：
                - orders: 订单列表（Order 对象，包含config_strategy_id）
                - statistics: 统计信息
                - strategy_statistics: 按策略分组的统计信息
            project_config (ProjectConfig): 项目配置对象
            klines_df (pd.DataFrame): K线数据（用于计算权益曲线和时间范围）

        Returns:
            int: 保存的 BacktestResult 记录 ID

        Context:
            关联任务：TASK-017-016
            关联需求：多策略回测结果保存
        """
        from django.db import transaction
        from strategy_adapter.models.db_models import BacktestResult, BacktestOrder

        orders = result['orders']
        backtest_config = project_config.backtest_config
        capital_config = project_config.capital_management

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
            initial_cash=backtest_config.initial_cash
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
        # 使用配置中的risk_free_rate，默认为3.0%
        risk_free_rate = getattr(backtest_config, 'risk_free_rate', Decimal("3.0"))
        rfr_decimal = Decimal(str(risk_free_rate)) / Decimal("100")

        calculator = MetricsCalculator(risk_free_rate=rfr_decimal)
        metrics = calculator.calculate_all_metrics(
            orders=orders,
            equity_curve=equity_curve,
            initial_cash=backtest_config.initial_cash,
            days=days
        )

        # 转换为可序列化的字典格式
        metrics_data = {
            k: str(v) if isinstance(v, Decimal) else v
            for k, v in metrics.items()
        }

        # === 步骤4: 生成策略名称（多策略组合） ===
        # 格式：项目名称（策略1+策略2+策略3）
        enabled_strategies = [s for s in project_config.strategies if s.enabled]
        strategy_names = '+'.join([s.name for s in enabled_strategies])
        combined_strategy_name = f"{project_config.project_name}（{strategy_names}）"

        # === 步骤5: 使用事务保存数据 ===
        with transaction.atomic():
            # 创建 BacktestResult 记录
            backtest_result = BacktestResult.objects.create(
                strategy_name=combined_strategy_name,
                symbol=backtest_config.symbol,
                interval=backtest_config.interval,
                market_type=backtest_config.market_type,
                start_date=start_time.date(),
                end_date=end_time.date(),
                initial_cash=backtest_config.initial_cash,
                position_size=capital_config.position_size,
                commission_rate=backtest_config.commission_rate,
                risk_free_rate=risk_free_rate,
                equity_curve=equity_curve_data,
                metrics=metrics_data
            )

            # 批量创建 BacktestOrder 记录（带config_strategy_id）
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
                    direction=order.direction,
                    config_strategy_id=order.config_strategy_id  # 多策略标识
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
            🔧 Bug-027修改：命令行参数优先级 > 配置文件参数

        Args:
            config_path: 配置文件路径
            options: CLI选项（verbose, save_to_db, 以及可覆盖配置文件的参数）

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

            # === Bug-027: 命令行参数覆盖配置文件 ===
            cli_overrides = []

            # 覆盖symbol（位置参数或配置文件）
            if options.get('symbol'):
                original_symbol = backtest_config.symbol
                backtest_config.symbol = options['symbol'].upper()
                if original_symbol != backtest_config.symbol:
                    cli_overrides.append(f'symbol: {original_symbol} -> {backtest_config.symbol}')

            # 覆盖interval
            if options.get('interval') and options['interval'] != '4h':  # 非默认值才覆盖
                original_interval = backtest_config.interval
                backtest_config.interval = options['interval']
                if original_interval != backtest_config.interval:
                    cli_overrides.append(f'interval: {original_interval} -> {backtest_config.interval}')

            # 覆盖market_type
            if options.get('market_type') and options['market_type'] != 'futures':  # 非默认值才覆盖
                original_market_type = backtest_config.market_type
                backtest_config.market_type = options['market_type']
                if original_market_type != backtest_config.market_type:
                    cli_overrides.append(f'market_type: {original_market_type} -> {backtest_config.market_type}')

            # 覆盖start_date
            if options.get('start_date'):
                original_start = backtest_config.start_date
                backtest_config.start_date = options['start_date']
                if original_start != backtest_config.start_date:
                    cli_overrides.append(f'start_date: {original_start} -> {backtest_config.start_date}')

            # 覆盖end_date
            if options.get('end_date'):
                original_end = backtest_config.end_date
                backtest_config.end_date = options['end_date']
                if original_end != backtest_config.end_date:
                    cli_overrides.append(f'end_date: {original_end} -> {backtest_config.end_date}')

            # 覆盖initial_cash
            if options.get('initial_cash') and options['initial_cash'] != 10000.0:  # 非默认值才覆盖
                original_cash = float(backtest_config.initial_cash)
                backtest_config.initial_cash = Decimal(str(options['initial_cash']))
                if original_cash != float(backtest_config.initial_cash):
                    cli_overrides.append(f'initial_cash: {original_cash} -> {float(backtest_config.initial_cash)}')

            # 覆盖position_size
            if options.get('position_size') and options['position_size'] != 100.0:  # 非默认值才覆盖
                original_position = float(capital_config.position_size)
                capital_config.position_size = Decimal(str(options['position_size']))
                if original_position != float(capital_config.position_size):
                    cli_overrides.append(f'position_size: {original_position} -> {float(capital_config.position_size)}')

            # 覆盖commission_rate
            if options.get('commission_rate') and options['commission_rate'] != 0.001:  # 非默认值才覆盖
                original_commission = float(backtest_config.commission_rate)
                backtest_config.commission_rate = Decimal(str(options['commission_rate']))
                if original_commission != float(backtest_config.commission_rate):
                    cli_overrides.append(f'commission_rate: {original_commission} -> {float(backtest_config.commission_rate)}')

            # 输出覆盖信息
            if cli_overrides:
                self.stdout.write(self.style.WARNING('  命令行参数覆盖:'))
                for override in cli_overrides:
                    self.stdout.write(self.style.WARNING(f'    - {override}'))

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

            # 根据数据源类型选择加载方式
            data_source = project_config.data_source
            if data_source and data_source.type == 'csv_local':
                # 从CSV文件加载
                self.stdout.write(f'  数据源: CSV文件 ({data_source.csv_path})')
                klines_df = self._load_klines_from_csv(
                    csv_path=data_source.csv_path,
                    interval=data_source.interval,
                    timestamp_unit=data_source.timestamp_unit,
                    start_date=start_date,
                    end_date=end_date
                )
            else:
                # 从数据库加载
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
            limit_order_strategies = []  # 策略11的特殊处理
            empirical_cdf_strategies = []  # 滚动经验CDF策略 (迭代034)

            for strategy_config in enabled_strategies:
                # 创建策略实例，传入position_size（来自capital_management）
                strategy = StrategyFactory.create(
                    strategy_config,
                    position_size=capital_config.position_size
                )

                # 检测是否为策略11/12/13/14（限价挂单类策略）
                from strategy_adapter.strategies import LimitOrderStrategy, DoublingPositionStrategy, SplitTakeProfitStrategy, OptimizedEntryStrategy, EmpiricalCDFStrategy, Strategy16LimitEntry, Strategy17BullWarningEntry
                if isinstance(strategy, EmpiricalCDFStrategy):
                    # 滚动经验CDF策略 (迭代034)
                    empirical_cdf_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(滚动经验CDF策略)'
                    ))
                elif hasattr(strategy, 'STRATEGY_ID') and strategy.STRATEGY_ID == 'empirical_cdf_v01':
                    # Empirical CDF V01 策略 (迭代035)
                    empirical_cdf_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(Empirical CDF V01 - EMA状态止盈)'
                    ))
                elif isinstance(strategy, Strategy16LimitEntry):
                    # 策略16: P5限价挂单入场 (Bug-Fix) - 使用限价挂单回测
                    limit_order_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(P5限价挂单入场)'
                    ))
                elif isinstance(strategy, Strategy17BullWarningEntry):
                    # 策略17: 上涨预警入场 (迭代038) - 使用限价挂单回测
                    limit_order_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(上涨预警入场)'
                    ))
                elif isinstance(strategy, LimitOrderStrategy):
                    limit_order_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(限价挂单策略)'
                    ))
                elif isinstance(strategy, SplitTakeProfitStrategy):
                    limit_order_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(分批止盈策略)'
                    ))
                elif isinstance(strategy, OptimizedEntryStrategy):
                    limit_order_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(优化买入策略)'
                    ))
                elif isinstance(strategy, DoublingPositionStrategy):
                    limit_order_strategies.append((strategy_config.id, strategy))
                    self.stdout.write(self.style.SUCCESS(
                        f'  ✓ {strategy_config.id}: {strategy_config.name} '
                        f'(倍增仓位限价挂单策略)'
                    ))
                else:
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

            # === Step 5: 执行回测 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[5/6] 执行回测...'))

            # 如果有滚动经验CDF策略，使用专门的回测流程 (迭代034)
            if empirical_cdf_strategies and not strategies and not limit_order_strategies:
                strategy_id, cdf_strategy = empirical_cdf_strategies[0]

                # 滚动经验CDF策略使用自带的run_backtest方法
                result = cdf_strategy.run_backtest(
                    klines_df=klines_df,
                    initial_capital=backtest_config.initial_cash
                )
                self.stdout.write(self.style.SUCCESS('✓ 滚动经验CDF策略回测完成'))

                # 转换结果格式以兼容现有显示逻辑
                result = self._convert_empirical_cdf_result(
                    result, strategy_id, backtest_config.initial_cash,
                    symbol=backtest_config.symbol
                )

            # 如果只有策略11/12/13/14，使用专门的限价挂单回测
            elif limit_order_strategies and not strategies:
                # 纯限价挂单策略回测（策略11/12/13/14）
                strategy_id, limit_strategy = limit_order_strategies[0]

                # 根据策略类型选择回测方法
                from strategy_adapter.strategies import LimitOrderStrategy, DoublingPositionStrategy, SplitTakeProfitStrategy, OptimizedEntryStrategy
                if isinstance(limit_strategy, Strategy16LimitEntry):
                    # 策略16: P5限价挂单入场 - 使用run_backtest
                    result = limit_strategy.run_backtest(
                        klines_df=klines_df,
                        initial_capital=backtest_config.initial_cash
                    )
                    self.stdout.write(self.style.SUCCESS('✓ P5限价挂单回测完成'))
                elif isinstance(limit_strategy, Strategy17BullWarningEntry):
                    # 策略17: 上涨预警入场 (迭代038) - 使用run_backtest
                    result = limit_strategy.run_backtest(
                        klines_df=klines_df,
                        initial_capital=backtest_config.initial_cash
                    )
                    self.stdout.write(self.style.SUCCESS('✓ 上涨预警入场回测完成'))
                elif isinstance(limit_strategy, SplitTakeProfitStrategy):
                    # 策略15: 分批止盈优化策略 - 使用run_optimized_backtest
                    if hasattr(limit_strategy, 'STRATEGY_ID') and limit_strategy.STRATEGY_ID == 'strategy_15':
                        result = limit_strategy.run_optimized_backtest(
                            klines_df=klines_df,
                            indicators=indicators,
                            initial_capital=backtest_config.initial_cash
                        )
                        self.stdout.write(self.style.SUCCESS('✓ 分批止盈优化回测完成'))
                    else:
                        # 策略13: 分批止盈回测 - 使用run_split_backtest
                        result = limit_strategy.run_split_backtest(
                            klines_df=klines_df,
                            indicators=indicators,
                            initial_capital=backtest_config.initial_cash
                        )
                        self.stdout.write(self.style.SUCCESS('✓ 分批止盈回测完成'))
                elif isinstance(limit_strategy, OptimizedEntryStrategy):
                    # 策略14: 优化买入回测
                    result = limit_strategy.run_optimized_backtest(
                        klines_df=klines_df,
                        indicators=indicators,
                        initial_capital=backtest_config.initial_cash
                    )
                    self.stdout.write(self.style.SUCCESS('✓ 优化买入回测完成'))
                elif isinstance(limit_strategy, DoublingPositionStrategy):
                    # 策略12: 倍增仓位回测
                    result = limit_strategy.run_doubling_backtest(
                        klines_df=klines_df,
                        indicators=indicators,
                        initial_capital=backtest_config.initial_cash
                    )
                    self.stdout.write(self.style.SUCCESS('✓ 倍增仓位回测完成'))
                else:
                    # 策略11: 标准限价挂单回测
                    result = limit_strategy.run_limit_order_backtest(
                        klines_df=klines_df,
                        indicators=indicators,
                        initial_capital=backtest_config.initial_cash
                    )
                    self.stdout.write(self.style.SUCCESS('✓ 限价挂单回测完成'))

                # 转换结果格式以兼容现有显示逻辑
                result = self._convert_limit_order_result(
                    result, strategy_id, backtest_config.initial_cash,
                    symbol=backtest_config.symbol
                )

            elif strategies:
                # 标准多策略回测
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
            else:
                raise CommandError('没有可执行的策略')

            # === Step 6: 输出结果 ===
            self.stdout.write(self.style.MIGRATE_LABEL('[6/6] 回测结果'))
            self._display_multi_strategy_results(
                result, project_config, klines_df, verbose
            )

            # 保存到数据库（可选）
            if save_to_db:
                self.stdout.write(self.style.MIGRATE_LABEL('\n[7/7] 保存到数据库...'))
                record_id = self._save_multi_strategy_result(
                    result=result,
                    project_config=project_config,
                    klines_df=klines_df
                )
                self.stdout.write(self.style.SUCCESS(
                    f'✓ 保存成功！回测记录ID: {record_id}'
                ))
                self.stdout.write(
                    f'   查看地址: http://127.0.0.1:8000/strategy-adapter/backtest/{record_id}/'
                )

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

        # 持仓统计（如果有持仓）
        if stats["open_orders"] > 0:
            holding_cost = stats.get('holding_cost', 0)
            holding_value = stats.get('holding_value', 0)
            holding_unrealized_pnl = stats.get('holding_unrealized_pnl', 0)
            if holding_cost > 0:
                self.stdout.write(f'    - 持仓买入成本: {holding_cost:.2f} USDT')
                self.stdout.write(f'    - 当前持仓价值: {holding_value:.2f} USDT')
                pnl_style = self.style.SUCCESS if holding_unrealized_pnl >= 0 else self.style.ERROR
                self.stdout.write(pnl_style(f'    - 持仓浮盈浮亏: {holding_unrealized_pnl:+.2f} USDT'))

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

        # === 资金统计 ===
        available_capital = stats.get('available_capital', 0)
        frozen_capital = stats.get('frozen_capital', 0)
        holding_value = stats.get('holding_value', 0)
        total_equity = stats.get('total_equity', 0)
        if available_capital > 0 or total_equity > 0:
            self.stdout.write('')
            self.stdout.write('【资金统计】')
            self.stdout.write(f'  可用现金: {available_capital:.2f} USDT')
            self.stdout.write(f'  挂单冻结: {frozen_capital:.2f} USDT')
            self.stdout.write(f'  持仓市值: {holding_value:.2f} USDT')
            self.stdout.write(f'  总资产: {total_equity:.2f} USDT')

        # === 交易成本 ===
        self.stdout.write('')
        self.stdout.write('【交易成本】')
        total_volume = stats.get('total_volume', Decimal('0'))
        total_commission = stats.get('total_commission', Decimal('0'))
        self.stdout.write(f'  总交易量: {float(total_volume):.2f} USDT')
        self.stdout.write(f'  总手续费: {float(total_commission):.2f} USDT')

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
                # 兼容Order对象和dict格式
                if hasattr(order, 'profit_loss'):
                    pnl = order.profit_loss
                    order_id = order.id
                    strategy_id = order.config_strategy_id
                    status = order.status.value
                else:
                    pnl = order.get('profit_loss')
                    order_id = order.get('order_id', order.get('buy_order_id', 'N/A'))
                    strategy_id = order.get('config_strategy_id', 'strategy_11')
                    status = order.get('status', 'closed')

                pnl_str = f'{pnl:+.2f}' if pnl else 'N/A'
                self.stdout.write(
                    f'  {order_id}: {strategy_id} | '
                    f'{status} | PnL: {pnl_str}'
                )
            if len(orders) > 10:
                self.stdout.write(f'  ... 共{len(orders)}个订单')

    def _convert_limit_order_result(
        self,
        limit_result: dict,
        strategy_id: str,
        initial_cash: Decimal,
        symbol: str = 'ETHUSDT'
    ) -> dict:
        """
        转换LimitOrderStrategy回测结果为统一格式

        Purpose:
            将LimitOrderStrategy.run_limit_order_backtest()返回的结果
            转换为_display_multi_strategy_results()期望的格式。

        Args:
            limit_result: LimitOrderStrategy回测结果
            strategy_id: 策略配置ID（如 'strategy_11'）
            initial_cash: 初始资金
            symbol: 交易对符号

        Returns:
            dict: 统一格式的回测结果
                {
                    'orders': list[Order],
                    'statistics': dict,
                    'strategy_statistics': dict
                }

        Context:
            关联任务：TASK-027-008
            关联��求：FP-027-018（集成到回测命令）
        """
        # 提取结果数据
        completed_orders = limit_result.get('orders', [])
        total_trades = limit_result.get('total_trades', 0)
        winning_trades = limit_result.get('winning_trades', 0)
        losing_trades = limit_result.get('losing_trades', 0)
        total_profit_loss = limit_result.get('total_profit_loss', 0)
        win_rate = limit_result.get('win_rate', 0)
        return_rate = limit_result.get('return_rate', 0)
        remaining_holdings = limit_result.get('remaining_holdings', 0)

        # 将字典转换为 Order 对象
        order_objects = []
        for order_dict in completed_orders:
            buy_price = Decimal(str(order_dict.get('buy_price', 0)))
            quantity = Decimal(str(order_dict.get('quantity', 0)))
            position_value = buy_price * quantity

            order_obj = Order(
                id=order_dict.get('buy_order_id', f'order_{order_dict.get("buy_timestamp", 0)}'),
                symbol=symbol,
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_timestamp=order_dict.get('buy_timestamp', 0),
                open_price=buy_price,
                quantity=quantity,
                position_value=position_value,
                close_timestamp=order_dict.get('sell_timestamp'),
                close_price=Decimal(str(order_dict.get('sell_price', 0))) if order_dict.get('sell_price') else None,
                close_reason='limit_order_exit',
                strategy_name='LimitOrderStrategy',
                strategy_id='11',
                config_strategy_id=strategy_id,
                entry_reason='limit_order_buy',
                profit_loss=Decimal(str(order_dict.get('profit_loss', 0))) if order_dict.get('profit_loss') is not None else None,
                # profit_rate 已经是百分比形式（如5表示5%），无需再乘以100
                profit_loss_rate=Decimal(str(order_dict.get('profit_rate', 0))) if order_dict.get('profit_rate') is not None else None,
                direction='long',
            )
            order_objects.append(order_obj)

        # 计算交易量和手续费
        # 买入金额 = sum(buy_price * quantity)
        # 卖出金额 = sum(sell_price * quantity) for completed orders
        total_buy_volume = Decimal('0')
        total_sell_volume = Decimal('0')
        total_commission = Decimal('0')

        # 默认手续费率（与项目配置一致）
        commission_rate = Decimal('0.001')  # 0.1%

        for order_dict in completed_orders:
            buy_price = Decimal(str(order_dict.get('buy_price', 0)))
            sell_price = Decimal(str(order_dict.get('sell_price', 0))) if order_dict.get('sell_price') else Decimal('0')
            quantity = Decimal(str(order_dict.get('quantity', 0)))

            buy_value = buy_price * quantity
            sell_value = sell_price * quantity

            total_buy_volume += buy_value
            total_sell_volume += sell_value

            # 计算手续费（买入和卖出各一次）
            total_commission += buy_value * commission_rate
            if sell_price > 0:
                total_commission += sell_value * commission_rate

        total_volume = total_buy_volume + total_sell_volume

        # 提取持仓统计（策略12新增）
        holding_cost = limit_result.get('holding_cost', 0)
        holding_value = limit_result.get('holding_value', 0)
        holding_unrealized_pnl = limit_result.get('holding_unrealized_pnl', 0)
        holding_losing_count = limit_result.get('holding_losing_count', 0)
        last_close_price = limit_result.get('last_close_price', 0)

        # 提取资金统计
        available_capital = limit_result.get('available_capital', 0)
        frozen_capital = limit_result.get('frozen_capital', 0)
        total_equity = limit_result.get('total_equity', 0)

        # 构建统一的statistics格式
        statistics = {
            'total_orders': total_trades + remaining_holdings,
            'closed_orders': total_trades,
            'open_orders': remaining_holdings,
            'win_orders': winning_trades,
            'lose_orders': losing_trades,
            'net_profit': float(total_profit_loss),
            'win_rate': float(win_rate),
            'return_rate': float(return_rate),
            'total_commission': total_commission,
            'total_volume': total_volume,
            # 新增：持仓统计
            'holding_cost': holding_cost,
            'holding_value': holding_value,
            'holding_unrealized_pnl': holding_unrealized_pnl,
            'holding_losing_count': holding_losing_count,
            'last_close_price': last_close_price,
            # 新增：资金统计
            'available_capital': available_capital,
            'frozen_capital': frozen_capital,
            'total_equity': total_equity,
        }

        # 构建strategy_statistics（单策略）
        strategy_statistics = {
            strategy_id: {
                'total_orders': total_trades + remaining_holdings,
                'closed_orders': total_trades,
                'open_orders': remaining_holdings,
                'win_orders': winning_trades,
                'lose_orders': losing_trades,
                'net_profit': float(total_profit_loss),
                'win_rate': float(win_rate),
                'return_rate': float(return_rate),
            }
        }

        return {
            'orders': order_objects,
            'statistics': statistics,
            'strategy_statistics': strategy_statistics,
        }

    def _convert_empirical_cdf_result(
        self,
        cdf_result: dict,
        strategy_id: str,
        initial_cash: Decimal,
        symbol: str = 'ETHUSDT'
    ) -> dict:
        """
        转换EmpiricalCDFStrategy回测结果为统一格式

        Purpose:
            将EmpiricalCDFStrategy.run_backtest()返回的结果
            转换为_display_multi_strategy_results()期望的格式。

        Args:
            cdf_result: EmpiricalCDFStrategy回测结果
            strategy_id: 策略配置ID（如 'strategy_empirical_cdf'）
            initial_cash: 初始资金
            symbol: 交易对符号

        Returns:
            dict: 统一格式的回测结果

        Context:
            关联任务：Bug-Fix (迭代034集成)
        """
        # 提取结果数据
        completed_orders = cdf_result.get('orders', [])
        total_trades = cdf_result.get('total_trades', 0)
        winning_trades = cdf_result.get('winning_trades', 0)
        losing_trades = cdf_result.get('losing_trades', 0)
        total_profit_loss = cdf_result.get('total_profit_loss', 0)
        win_rate = cdf_result.get('win_rate', 0)
        return_rate = cdf_result.get('return_rate', 0)
        remaining_holdings = cdf_result.get('remaining_holdings', 0)
        final_capital = cdf_result.get('final_capital', float(initial_cash))
        statistics = cdf_result.get('statistics', {})

        # 将字典转换为 Order 对象
        order_objects = []
        for order_dict in completed_orders:
            buy_price = Decimal(str(order_dict.get('buy_price', 0)))
            sell_price = Decimal(str(order_dict.get('sell_price', 0))) if order_dict.get('sell_price') else None
            quantity = Decimal(str(order_dict.get('quantity', 0)))
            position_value = buy_price * quantity

            order_obj = Order(
                id=order_dict.get('buy_order_id', f'order_{order_dict.get("entry_timestamp", 0)}'),
                symbol=symbol,
                side=OrderSide.BUY,
                status=OrderStatus.CLOSED,
                open_timestamp=order_dict.get('entry_timestamp', 0),
                open_price=buy_price,
                quantity=quantity,
                position_value=position_value,
                close_timestamp=order_dict.get('exit_timestamp'),
                close_price=sell_price,
                close_reason=order_dict.get('exit_reason', 'UNKNOWN'),
                strategy_name='EmpiricalCDFStrategy',
                strategy_id='empirical_cdf',
                config_strategy_id=strategy_id,
                entry_reason='prob_entry',
                profit_loss=Decimal(str(order_dict.get('profit_loss', 0))) if order_dict.get('profit_loss') is not None else None,
                profit_loss_rate=Decimal(str(order_dict.get('profit_rate', 0))) if order_dict.get('profit_rate') is not None else None,
                direction='long',
            )
            order_objects.append(order_obj)

        # 计算交易量和手续费
        total_buy_volume = Decimal('0')
        total_sell_volume = Decimal('0')
        total_commission = Decimal('0')
        commission_rate = Decimal('0.001')

        for order_dict in completed_orders:
            buy_price = Decimal(str(order_dict.get('buy_price', 0)))
            sell_price = Decimal(str(order_dict.get('sell_price', 0))) if order_dict.get('sell_price') else Decimal('0')
            quantity = Decimal(str(order_dict.get('quantity', 0)))

            buy_value = buy_price * quantity
            sell_value = sell_price * quantity

            total_buy_volume += buy_value
            total_sell_volume += sell_value
            total_commission += buy_value * commission_rate
            if sell_price > 0:
                total_commission += sell_value * commission_rate

        total_volume = total_buy_volume + total_sell_volume

        # 构建统一的statistics格式
        unified_statistics = {
            'total_orders': total_trades + remaining_holdings,
            'closed_orders': total_trades,
            'open_orders': remaining_holdings,
            'win_orders': winning_trades,
            'lose_orders': losing_trades,
            'net_profit': float(total_profit_loss),
            'win_rate': float(win_rate),
            'return_rate': float(return_rate),
            'total_commission': total_commission,
            'total_volume': total_volume,
            'available_capital': statistics.get('available_capital', float(final_capital)),
            'frozen_capital': statistics.get('frozen_capital', 0),
            'holding_value': 0,
            'total_equity': statistics.get('total_capital', float(final_capital)),
        }

        # 构建strategy_statistics（单策略）
        strategy_statistics = {
            strategy_id: {
                'total_orders': total_trades + remaining_holdings,
                'closed_orders': total_trades,
                'open_orders': remaining_holdings,
                'win_orders': winning_trades,
                'lose_orders': losing_trades,
                'net_profit': float(total_profit_loss),
                'win_rate': float(win_rate),
                'return_rate': float(return_rate),
            }
        }

        return {
            'orders': order_objects,
            'statistics': unified_statistics,
            'strategy_statistics': strategy_statistics,
        }
