"""
多交易对共享资金池回测命令
Run Multi-Symbol Backtest Command

执行策略20回测，支持多交易对共享资金池。

功能特性:
    - 支持指定多个交易对
    - 共享资金池，全局持仓限制
    - 输出每个交易对的独立统计和全局统计

使用示例:
    # 默认4个交易对回测
    python manage.py run_multi_symbol_backtest

    # 指定交易对
    python manage.py run_multi_symbol_backtest --symbols ETHUSDT,BTCUSDT,SOLUSDT

    # 指定日期范围和初始资金
    python manage.py run_multi_symbol_backtest \
        --symbols ETHUSDT,BTCUSDT \
        --start-date 2025-01-01 \
        --end-date 2025-12-31 \
        --initial-cash 50000

Related:
    - PRD: docs/iterations/045-multi-symbol-strategy/prd.md
    - Architecture: docs/iterations/045-multi-symbol-strategy/architecture.md
    - Tasks: docs/iterations/045-multi-symbol-strategy/tasks.md

迭代编号: 045 (策略20-多交易对共享资金池)
创建日期: 2026-01-14
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from backtest.models import KLine

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '执行多交易对共享资金池回测（策略20）'
    requires_system_checks = []

    # 默认交易对
    DEFAULT_SYMBOLS = ['ETHUSDT', 'BTCUSDT', 'HYPEUSDT', 'BNBUSDT']

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbols',
            type=str,
            default=','.join(self.DEFAULT_SYMBOLS),
            help=f'交易对列表（逗号分隔），默认: {",".join(self.DEFAULT_SYMBOLS)}'
        )
        parser.add_argument(
            '--start-date',
            type=str,
            help='开始日期 (格式: YYYY-MM-DD)'
        )
        parser.add_argument(
            '--end-date',
            type=str,
            help='结束日期 (格式: YYYY-MM-DD)'
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
            '--max-positions',
            type=int,
            default=10,
            help='全局最大持仓数（默认: 10）'
        )
        parser.add_argument(
            '--discount',
            type=float,
            default=0.001,
            help='买入折扣率（默认: 0.001，即千一）'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细信息'
        )
        parser.add_argument(
            '--auto-fetch',
            action='store_true',
            help='自动从API获取缺失的K线数据'
        )

    def handle(self, *args, **options):
        from strategy_adapter.strategies import Strategy20MultiSymbol

        symbols_str = options['symbols']
        interval = options['interval']
        market_type = options['market_type']
        initial_cash = Decimal(str(options['initial_cash']))
        max_positions = options['max_positions']
        discount = Decimal(str(options['discount']))
        verbose = options['verbose']
        auto_fetch = options.get('auto_fetch', False)

        # 解析交易对列表
        symbols = [s.strip().upper() for s in symbols_str.split(',') if s.strip()]
        if not symbols:
            raise CommandError('必须指定至少一个交易对')

        # 解析日期
        start_date = None
        end_date = None
        if options.get('start_date'):
            start_date = datetime.strptime(options['start_date'], '%Y-%m-%d')
            start_date = timezone.make_aware(start_date)
        if options.get('end_date'):
            end_date = datetime.strptime(options['end_date'], '%Y-%m-%d')
            end_date = timezone.make_aware(end_date)

        # 解析interval_hours
        interval_hours = self._parse_interval_hours(interval)

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n=== 多交易对共享资金池回测 (策略20) ===\n'
        ))

        # === Step 1: 加载K线数据 ===
        self.stdout.write(self.style.MIGRATE_LABEL('[1/3] 加载K线数据...'))
        klines_dict: Dict[str, pd.DataFrame] = {}

        for symbol in symbols:
            self.stdout.write(f'  加载 {symbol}...')
            try:
                klines_df = self._load_klines(
                    symbol=symbol,
                    interval=interval,
                    market_type=market_type,
                    start_date=start_date,
                    end_date=end_date,
                    auto_fetch=auto_fetch
                )
                if klines_df is not None and len(klines_df) > 0:
                    klines_dict[symbol] = klines_df
                    self.stdout.write(self.style.SUCCESS(
                        f'    ✓ {len(klines_df)}根K线'
                    ))
                else:
                    self.stdout.write(self.style.WARNING(
                        f'    ⚠ 无数据，跳过'
                    ))
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f'    ⚠ 加载失败: {e}'
                ))

        if not klines_dict:
            raise CommandError('没有加载到任何K线数据')

        self.stdout.write(self.style.SUCCESS(
            f'✓ 共加载 {len(klines_dict)} 个交易对数据'
        ))
        self.stdout.write('')

        # === Step 2: 执行回测 ===
        self.stdout.write(self.style.MIGRATE_LABEL('[2/3] 执行回测...'))
        self.stdout.write(f'  初始资金: {initial_cash} USDT')
        self.stdout.write(f'  最大持仓: {max_positions}')
        self.stdout.write(f'  买入折扣: {discount * 100:.2f}%')
        self.stdout.write('')

        strategy = Strategy20MultiSymbol(
            symbols=list(klines_dict.keys()),
            discount=discount,
            max_positions=max_positions,
            interval_hours=interval_hours
        )

        result = strategy.run_backtest(
            klines_dict=klines_dict,
            initial_capital=initial_cash
        )

        self.stdout.write(self.style.SUCCESS('✓ 回测完成'))
        self.stdout.write('')

        # === Step 3: 输出结果 ===
        self.stdout.write(self.style.MIGRATE_LABEL('[3/3] 回测结果'))
        self._print_results(result, verbose)

    def _parse_interval_hours(self, interval: str) -> float:
        """解析K线周期为小时数"""
        interval = interval.lower()
        if interval.endswith('h'):
            return float(interval[:-1])
        elif interval.endswith('d'):
            return float(interval[:-1]) * 24
        elif interval.endswith('m'):
            return float(interval[:-1]) / 60
        else:
            return 4.0  # 默认4小时

    def _load_klines(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
        auto_fetch: bool = False
    ) -> Optional[pd.DataFrame]:
        """从数据库加载K线数据"""
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
        klines = list(queryset.values(
            'open_time', 'open_price', 'high_price', 'low_price', 'close_price', 'volume'
        ))

        if not klines:
            if auto_fetch:
                return self._fetch_and_save_klines(
                    symbol, interval, market_type, start_date, end_date
                )
            return None

        df = pd.DataFrame(klines)
        df['open_time'] = pd.to_datetime(df['open_time'])
        df.set_index('open_time', inplace=True)

        # 转换数值类型并重命名字段
        df = df.rename(columns={
            'open_price': 'open',
            'high_price': 'high',
            'low_price': 'low',
            'close_price': 'close'
        })
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)

        return df

    def _fetch_and_save_klines(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> Optional[pd.DataFrame]:
        """从API获取K线数据并保存"""
        try:
            from ddps_z.datasources import BinanceFetcher
            fetcher = BinanceFetcher()

            # 获取数据
            klines_df = fetcher.fetch_klines(
                symbol=symbol,
                interval=interval,
                start_time=int(start_date.timestamp() * 1000) if start_date else None,
                end_time=int(end_date.timestamp() * 1000) if end_date else None,
                limit=1000
            )

            if klines_df is None or len(klines_df) == 0:
                return None

            # 保存到数据库
            for idx, row in klines_df.iterrows():
                KLine.objects.update_or_create(
                    symbol=symbol,
                    interval=interval,
                    market_type=market_type,
                    open_time=idx,
                    defaults={
                        'open': Decimal(str(row['open'])),
                        'high': Decimal(str(row['high'])),
                        'low': Decimal(str(row['low'])),
                        'close': Decimal(str(row['close'])),
                        'volume': Decimal(str(row['volume'])),
                    }
                )

            return klines_df

        except Exception as e:
            logger.warning(f'获取K线数据失败: {e}')
            return None

    def _print_results(self, result: Dict, verbose: bool):
        """输出回测结果"""
        global_stats = result.get('global', {})
        by_symbol = result.get('by_symbol', {})

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('【全局统计】'))
        self.stdout.write(f'  初始资金: {global_stats.get("initial_capital", 0):.2f} USDT')
        self.stdout.write(f'  最终权益: {global_stats.get("final_capital", 0):.2f} USDT')
        self.stdout.write(f'  净利润: {global_stats.get("total_return", 0):.2f} USDT')
        self.stdout.write(f'  收益率: {global_stats.get("total_return_rate", 0):.2f}%')
        self.stdout.write(f'  总订单数: {global_stats.get("total_orders", 0)}')
        self.stdout.write(f'  盈利订单: {global_stats.get("winning_orders", 0)}')
        self.stdout.write(f'  胜率: {global_stats.get("win_rate", 0):.2f}%')
        self.stdout.write(f'  当前持仓: {global_stats.get("open_positions", 0)}')
        self.stdout.write(f'  最大回撤: {global_stats.get("max_drawdown", 0):.2f}%')
        self.stdout.write(f'  年化收益率: {global_stats.get("apr", 0):.2f}%')
        self.stdout.write(f'  回测天数: {global_stats.get("trading_days", 0)}')
        self.stdout.write('')

        self.stdout.write(self.style.MIGRATE_HEADING('【各交易对统计】'))
        for symbol, stats in by_symbol.items():
            self.stdout.write(self.style.MIGRATE_LABEL(f'\n  {symbol}:'))
            self.stdout.write(f'    订单数: {stats.get("orders", 0)}')
            self.stdout.write(f'    盈利订单: {stats.get("winning_orders", 0)}')
            self.stdout.write(f'    胜率: {stats.get("win_rate", 0):.2f}%')
            self.stdout.write(f'    净利润: {stats.get("profit_loss", 0):.2f} USDT')
            self.stdout.write(f'    当前持仓: {stats.get("current_holdings", 0)}')

        if verbose:
            orders = result.get('orders', [])
            if orders:
                self.stdout.write('')
                self.stdout.write(self.style.MIGRATE_HEADING('【订单明细】'))
                for order in orders[-20:]:  # 只显示最后20笔
                    self.stdout.write(
                        f'  {order.get("symbol")} | '
                        f'{order.get("side")} | '
                        f'价格: {order.get("price", 0):.4f} | '
                        f'数量: {order.get("quantity", 0):.6f} | '
                        f'损益: {order.get("profit_loss", 0):.2f}'
                    )
