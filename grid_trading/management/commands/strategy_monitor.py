"""
策略监控命令
Strategy Monitor Command

功能:
1. 显示所有策略的实时状态
2. 显示风险汇总信息
3. 显示订单统计
"""
import logging
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Sum, Q

from grid_trading.models import GridStrategy, GridZone
from grid_trading.services.risk_manager import get_risk_manager

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '策略监控 - 显示所有策略状态和风险指标'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            help='筛选指定交易对'
        )
        parser.add_argument(
            '--active-only',
            action='store_true',
            help='只显示active策略'
        )

    def handle(self, *args, **options):
        symbol_filter = options.get('symbol')
        active_only = options['active_only']

        risk_manager = get_risk_manager()

        self.stdout.write("=" * 100)
        self.stdout.write(self.style.SUCCESS("策略监控仪表板"))
        self.stdout.write(f"时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.stdout.write("=" * 100)

        # 1. 显示GridZone状态
        self._display_grid_zones(symbol_filter)

        # 2. 显示策略状态
        self._display_strategies(symbol_filter, active_only, risk_manager)

        # 3. 显示风险汇总
        if symbol_filter:
            self._display_risk_summary(symbol_filter, risk_manager)

        self.stdout.write("=" * 100)

    def _display_grid_zones(self, symbol_filter):
        """显示GridZone状态"""
        self.stdout.write("\n" + "-" * 100)
        self.stdout.write(self.style.MIGRATE_HEADING("📊 GridZone 区间状态"))
        self.stdout.write("-" * 100)

        queryset = GridZone.objects.filter(is_active=True, expires_at__gt=timezone.now())

        if symbol_filter:
            queryset = queryset.filter(symbol=symbol_filter)

        zones = queryset.order_by('symbol', 'zone_type', 'price_low')

        if not zones.exists():
            self.stdout.write("  (无活跃区间)")
            return

        for zone in zones:
            zone_type_icon = "🔻" if zone.zone_type == 'support' else "🔺"
            self.stdout.write(
                f"  {zone_type_icon} {zone.symbol} {zone.get_zone_type_display()}: "
                f"${zone.price_low:.2f} - ${zone.price_high:.2f} "
                f"(置信度:{zone.confidence}分, "
                f"过期:{zone.expires_at.strftime('%H:%M')})"
            )

    def _display_strategies(self, symbol_filter, active_only, risk_manager):
        """显示策略状态"""
        self.stdout.write("\n" + "-" * 100)
        self.stdout.write(self.style.MIGRATE_HEADING("🤖 策略状态"))
        self.stdout.write("-" * 100)

        queryset = GridStrategy.objects.all()

        if symbol_filter:
            queryset = queryset.filter(symbol=symbol_filter)

        if active_only:
            queryset = queryset.filter(status='active')

        strategies = queryset.order_by('-started_at')

        if not strategies.exists():
            self.stdout.write("  (无策略)")
            return

        for strategy in strategies:
            # 获取风险指标
            metrics = risk_manager.get_strategy_risk_metrics(strategy)

            # 状态图标
            status_icons = {
                'idle': '⚪',
                'active': '🟢',
                'stopped': '🔴',
                'error': '🟡',
            }
            status_icon = status_icons.get(strategy.status, '⚪')

            # 策略类型图标
            type_icon = '📈' if strategy.strategy_type == 'long' else '📉'

            # 盈亏颜色
            pnl = float(strategy.current_pnl)
            if pnl > 0:
                pnl_str = self.style.SUCCESS(f"+${pnl:.2f}")
            elif pnl < 0:
                pnl_str = self.style.ERROR(f"${pnl:.2f}")
            else:
                pnl_str = f"${pnl:.2f}"

            self.stdout.write(
                f"\n  {status_icon} {type_icon} Strategy #{strategy.id} - {strategy.symbol} "
                f"[{strategy.get_status_display()}]"
            )

            if strategy.entry_price:
                self.stdout.write(
                    f"     入场价: ${float(strategy.entry_price):.2f}  |  "
                    f"当前盈亏: {pnl_str}  |  "
                    f"盈亏率: {metrics['pnl_pct']:+.2f}%"
                )

            self.stdout.write(
                f"     仓位价值: ${metrics['position_value']:.2f}  |  "
                f"订单: {metrics['pending_orders']}/{metrics['total_orders']} pending  |  "
                f"成交率: {metrics['fill_rate']:.1f}%"
            )

            if strategy.started_at:
                runtime = timezone.now() - strategy.started_at
                hours = runtime.total_seconds() / 3600
                self.stdout.write(
                    f"     运行时间: {hours:.1f}小时  |  "
                    f"止损线: {metrics['stop_loss_pct']:.0f}%"
                )

    def _display_risk_summary(self, symbol, risk_manager):
        """显示风险汇总"""
        self.stdout.write("\n" + "-" * 100)
        self.stdout.write(self.style.MIGRATE_HEADING("⚠️  风险汇总"))
        self.stdout.write("-" * 100)

        summary = risk_manager.get_symbol_risk_summary(symbol)

        self.stdout.write(f"  交易对: {summary['symbol']}")
        self.stdout.write(f"  活跃策略数: {summary['active_strategies']}")
        self.stdout.write(f"  总仓位价值: ${summary['total_position_value']:.2f}")

        total_pnl = summary['total_pnl']
        if total_pnl > 0:
            pnl_str = self.style.SUCCESS(f"+${total_pnl:.2f}")
        elif total_pnl < 0:
            pnl_str = self.style.ERROR(f"${total_pnl:.2f}")
        else:
            pnl_str = f"${total_pnl:.2f}"

        self.stdout.write(f"  总盈亏: {pnl_str}  ({summary['total_pnl_pct']:+.2f}%)")
