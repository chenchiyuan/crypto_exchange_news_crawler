"""
批量回测管理命令
Run Batch Backtest Command

支持批量回测多个交易对，输出CSV结果文件。

功能特性:
    - 支持指定单个/多个交易对或ALL模式
    - 使用策略16配置文件执行回测
    - 输出CSV结果（UTF-8 BOM编码，Excel兼容）
    - 实时显示进度和关键指标

使用示例:
    # 单个交易对回测
    python manage.py run_batch_backtest \
        --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
        --symbols ETHUSDT

    # 多个交易对回测
    python manage.py run_batch_backtest \
        --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
        --symbols ETHUSDT,BTCUSDT,SOLUSDT

    # 回测所有活跃交易对
    python manage.py run_batch_backtest \
        --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
        --symbols ALL \
        --auto-fetch

Related:
    - PRD: docs/iterations/040-batch-backtest-evaluation/prd.md
    - Architecture: docs/iterations/040-batch-backtest-evaluation/architecture.md
    - Tasks: docs/iterations/040-batch-backtest-evaluation/tasks.md
"""

import csv
import logging
import time
from datetime import datetime
from decimal import Decimal
from typing import Dict, List

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger(__name__)

# CSV表头定义
CSV_HEADERS = [
    'symbol',           # 交易对
    'total_orders',     # 总订单数
    'closed_orders',    # 已平仓
    'open_positions',   # 持仓中
    'available_capital',# 可用现金
    'frozen_capital',   # 挂单冻结
    'holding_cost',     # 持仓成本
    'holding_value',    # 持仓市值
    'total_equity',     # 账户总值
    'total_volume',     # 总交易量
    'total_commission', # 总手续费
    'win_rate',         # 胜率
    'net_profit',       # 净利润
    'return_rate',      # 收益率
    'static_apr',       # 静态APR
    'weighted_apy',     # 综合APY
    'backtest_days',    # 回测天数
    'start_date',       # 开始日期
    'end_date',         # 结束日期
]


class Command(BaseCommand):
    help = '批量回测多个交易对，输出CSV结果文件'

    def add_arguments(self, parser):
        parser.add_argument(
            '--config',
            type=str,
            required=True,
            help='策略配置文件路径（JSON格式）'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            default='ALL',
            help='交易对列表（逗号分隔）或ALL（默认: ALL）'
        )
        parser.add_argument(
            '--output',
            type=str,
            help='CSV输出路径（可选，默认: data/backtest_{timestamp}.csv）'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='开始日期 (格式: YYYY-MM-DD)，覆盖配置文件设置'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='结束日期 (格式: YYYY-MM-DD)，覆盖配置文件设置'
        )
        parser.add_argument(
            '--auto-fetch',
            action='store_true',
            help='自动从API获取缺失的K线数据'
        )

    def handle(self, *args, **options):
        config_path = options['config']
        symbols_arg = options['symbols']
        output_path = options.get('output')
        start_date = options.get('start_date')
        end_date = options.get('end_date')
        auto_fetch = options.get('auto_fetch', False)

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== 批量回测系统 ===\n'))

        # 1. 加载配置文件
        self.stdout.write(self.style.MIGRATE_LABEL('[1/4] 加载配置文件...'))
        try:
            project_config = self._load_config(config_path)
            self.stdout.write(self.style.SUCCESS(
                f'✓ 加载成功: {project_config.project_name}'
            ))
        except Exception as e:
            raise CommandError(f'配置文件加载失败: {e}')

        # 2. 获取交易对列表
        self.stdout.write(self.style.MIGRATE_LABEL('[2/4] 解析交易对列表...'))
        try:
            symbols = self._get_symbols(symbols_arg)
            self.stdout.write(self.style.SUCCESS(
                f'✓ 解析成功: {len(symbols)}个交易对'
            ))
        except Exception as e:
            raise CommandError(f'交易对解析失败: {e}')

        # 3. 循环回测
        self.stdout.write(self.style.MIGRATE_LABEL('[3/4] 执行批量回测...'))
        self.stdout.write('')
        results = []
        success_count = 0
        fail_count = 0

        for i, symbol in enumerate(symbols, 1):
            start_time = time.time()
            try:
                result = self._run_single_backtest(
                    symbol, project_config, auto_fetch,
                    start_date_override=start_date,
                    end_date_override=end_date
                )
                result['symbol'] = symbol
                results.append(result)
                success_count += 1
                elapsed = time.time() - start_time
                self._display_progress(i, len(symbols), symbol, result, elapsed, success=True)
            except Exception as e:
                fail_count += 1
                elapsed = time.time() - start_time
                error_result = self._create_error_result(symbol)
                results.append(error_result)
                self._display_progress(i, len(symbols), symbol, error_result, elapsed, success=False, error=str(e))
                logger.warning(f'回测失败 [{symbol}]: {e}')

        self.stdout.write('')

        # 4. 写入CSV
        self.stdout.write(self.style.MIGRATE_LABEL('[4/4] 保存CSV结果...'))
        if not output_path:
            output_path = self._default_output_path()

        try:
            self._write_csv(results, output_path)
            self.stdout.write(self.style.SUCCESS(
                f'✓ 保存成功: {output_path}'
            ))
        except Exception as e:
            raise CommandError(f'CSV写入失败: {e}')

        # 汇总
        self.stdout.write('')
        self.stdout.write('=' * 50)
        self.stdout.write(self.style.SUCCESS(
            f'批量回测完成: {success_count}/{len(symbols)} 成功'
        ))
        if fail_count > 0:
            self.stdout.write(self.style.WARNING(
                f'失败: {fail_count}个'
            ))
        self.stdout.write(f'结果保存至: {output_path}')
        self.stdout.write('')

    def _load_config(self, config_path: str):
        """加载策略配置文件"""
        from strategy_adapter.core import ProjectLoader
        loader = ProjectLoader()
        return loader.load(config_path)

    def _get_symbols(self, symbols_arg: str) -> List[str]:
        """
        获取交易对列表

        Args:
            symbols_arg: 命令行参数（逗号分隔或ALL）

        Returns:
            交易对列表
        """
        if symbols_arg.upper() == 'ALL':
            from monitor.models import FuturesContract
            symbols = list(FuturesContract.objects.filter(
                status='active'
            ).values_list('symbol', flat=True))
            if not symbols:
                raise ValueError('数据库中没有活跃的交易对')
            return sorted(set(symbols))
        else:
            symbols = [s.strip().upper() for s in symbols_arg.split(',')]
            symbols = list(set(symbols))  # 去重
            if not symbols:
                raise ValueError('交易对列表为空')
            return sorted(symbols)

    def _run_single_backtest(
        self,
        symbol: str,
        project_config,
        auto_fetch: bool,
        start_date_override: str = None,
        end_date_override: str = None
    ) -> Dict:
        """
        执行单个交易对回测

        Args:
            symbol: 交易对
            project_config: 项目配置
            auto_fetch: 是否自动拉取K线
            start_date_override: 覆盖配置文件的开始日期
            end_date_override: 覆盖配置文件的结束日期

        Returns:
            回测结果字典
        """
        from strategy_adapter.core import StrategyFactory
        from backtest.models import KLine

        backtest_config = project_config.backtest_config
        capital_config = project_config.capital_management
        enabled_strategies = project_config.get_enabled_strategies()

        if not enabled_strategies:
            raise ValueError('没有启用的策略')

        strategy_config = enabled_strategies[0]

        # 使用命令行覆盖日期或配置文件日期
        effective_start_date = start_date_override or backtest_config.start_date
        effective_end_date = end_date_override or backtest_config.end_date

        # 加载K线数据
        klines_df = self._load_klines(
            symbol=symbol,
            interval=backtest_config.interval,
            market_type=backtest_config.market_type,
            start_date=effective_start_date,
            end_date=effective_end_date,
            auto_fetch=auto_fetch
        )

        if klines_df.empty or len(klines_df) < 100:
            raise ValueError(f'K线数据不足: {len(klines_df)}根')

        # 创建策略实例
        strategy = StrategyFactory.create(
            strategy_config,
            position_size=capital_config.position_size
        )

        # 执行回测
        result = strategy.run_backtest(
            klines_df=klines_df,
            initial_capital=backtest_config.initial_cash
        )

        return result

    def _load_klines(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_date: str = None,
        end_date: str = None,
        auto_fetch: bool = False
    ):
        """加载K线数据"""
        import pandas as pd
        from backtest.models import KLine

        # 构建查询条件
        queryset = KLine.objects.filter(
            symbol=symbol,
            interval=interval,
            market_type=market_type
        ).order_by('open_time')

        # 日期过滤
        if start_date:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            start_dt = timezone.make_aware(start_dt)
            queryset = queryset.filter(open_time__gte=start_dt)

        if end_date:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d')
            end_dt = timezone.make_aware(end_dt)
            queryset = queryset.filter(open_time__lte=end_dt)

        # 自动拉取K线
        if auto_fetch and queryset.count() < 100:
            self._fetch_klines(symbol, interval, market_type)
            # 重新查询
            queryset = KLine.objects.filter(
                symbol=symbol,
                interval=interval,
                market_type=market_type
            ).order_by('open_time')
            if start_date:
                queryset = queryset.filter(open_time__gte=start_dt)
            if end_date:
                queryset = queryset.filter(open_time__lte=end_dt)

        # 转换为DataFrame
        klines = list(queryset.values(
            'open_time', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
        ))

        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(klines)
        df['open_time'] = pd.to_datetime(df['open_time'])
        df.set_index('open_time', inplace=True)

        # 重命名列以匹配策略期望的格式
        df.rename(columns={
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'close_price': 'close'
        }, inplace=True)

        # 转换为float类型
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df

    def _fetch_klines(self, symbol: str, interval: str, market_type: str):
        """从API拉取K线数据"""
        try:
            from ddps_z.datasources import CSVFetcher
            fetcher = CSVFetcher()
            fetcher.fetch_and_store(
                symbol=symbol,
                interval=interval,
                market_type=market_type,
                limit=1500
            )
        except Exception as e:
            logger.warning(f'K线拉取失败 [{symbol}]: {e}')

    def _create_error_result(self, symbol: str) -> Dict:
        """创建错误结果"""
        return {
            'symbol': symbol,
            'total_orders': 0,
            'closed_orders': 0,
            'open_positions': 0,
            'available_capital': 0,
            'frozen_capital': 0,
            'holding_cost': 0,
            'holding_value': 0,
            'total_equity': 0,
            'total_volume': 0,
            'total_commission': 0,
            'win_rate': 0,
            'net_profit': 0,
            'return_rate': 0,
            'static_apr': 0,
            'weighted_apy': 0,
            'backtest_days': 0,
            'start_date': '',
            'end_date': '',
        }

    def _display_progress(
        self,
        current: int,
        total: int,
        symbol: str,
        result: Dict,
        elapsed: float,
        success: bool = True,
        error: str = None
    ):
        """显示进度"""
        prefix = f'[{current}/{total}]'
        if success:
            # 兼容不同策略返回的字段名
            total_orders = result.get('total_orders', result.get('total_trades', 0))
            win_rate = result.get('win_rate', 0)
            static_apr = result.get('static_apr', 0)
            apr_sign = '+' if static_apr >= 0 else ''
            self.stdout.write(
                f'{prefix} {symbol} ... {elapsed:.1f}s | '
                f'订单:{total_orders} '
                f'胜率:{win_rate:.2f}% '
                f'APR:{apr_sign}{static_apr:.2f}%'
            )
        else:
            self.stdout.write(self.style.ERROR(
                f'{prefix} {symbol} ... {elapsed:.1f}s | 失败: {error[:50] if error else "未知错误"}'
            ))

    def _default_output_path(self) -> str:
        """生成默认输出路径"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'data/backtest_{timestamp}.csv'

    def _write_csv(self, results: List[Dict], output_path: str):
        """
        写入CSV文件

        Args:
            results: 回测结果列表
            output_path: 输出路径
        """
        import os

        # 确保目录存在
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # 写入CSV（UTF-8 BOM编码）
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=CSV_HEADERS,
                extrasaction='ignore'
            )
            writer.writeheader()
            for result in results:
                writer.writerow(self._format_row(result))

    def _format_row(self, result: Dict) -> Dict:
        """格式化CSV行数据"""
        formatted = {}

        # 字段映射：兼容不同策略返回的字段名
        field_mappings = {
            'total_orders': ['total_orders', 'total_trades'],
            'closed_orders': ['closed_orders', 'total_trades'],
            'open_positions': ['open_positions', 'remaining_holdings'],
            'net_profit': ['net_profit', 'total_profit_loss'],
        }

        for key in CSV_HEADERS:
            # 检查是否有字段映射
            if key in field_mappings:
                value = None
                for field_name in field_mappings[key]:
                    if field_name in result:
                        value = result[field_name]
                        break
                if value is None:
                    value = ''
            else:
                value = result.get(key, '')

            # 数值类型保留2位小数
            if isinstance(value, (float, Decimal)):
                formatted[key] = round(float(value), 2)
            else:
                formatted[key] = value
        return formatted
