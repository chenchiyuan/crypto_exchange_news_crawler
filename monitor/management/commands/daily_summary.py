"""
每日新币汇总脚本
Usage: python manage.py daily_summary [--hours 24] [--start-time "YYYY-MM-DD HH:MM"]
可通过 cron 定时执行:
0 9 * * * cd /path/to/project && python manage.py daily_summary

默认统计过去24小时的新币上线，兼容监控脚本的24小时窗口逻辑
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from monitor.models import Listing, Exchange, NotificationRecord
from monitor.services.notifier import AlertPushService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '每日新币汇总推送（自动统计当日所有新币上线）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='统计时间窗口(小时，默认24)'
        )
        parser.add_argument(
            '--start-time',
            type=str,
            help='指定开始时间，格式: YYYY-MM-DD HH:MM (默认: 过去N小时)'
        )
        parser.add_argument(
            '--exchanges',
            type=str,
            default='binance,bybit,hyperliquid',
            help='要统计的交易所(默认: binance,bybit,hyperliquid)'
        )
        parser.add_argument(
            '--skip-notification',
            action='store_true',
            help='跳过推送，只生成汇总报告'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        start_time_param = options['start_time']
        exchange_codes = [code.strip() for code in options['exchanges'].split(',')]
        skip_notification = options['skip_notification']

        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('📊 每日新币汇总报告'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f"时间窗口: {hours} 小时")
        self.stdout.write(f"交易所: {', '.join(exchange_codes)}")
        if skip_notification:
            self.stdout.write(f"🔕 推送: 已跳过")
        else:
            self.stdout.write(f"📢 推送: 慧诚告警推送")
        self.stdout.write('')

        # ========== 统计新币 ==========
        self.stdout.write(self.style.SUCCESS('\n🔍 统计新币上线...'))
        self.stdout.write('-'*70)

        # 计算时间范围
        now = timezone.now()
        if start_time_param:
            # 指定了开始时间
            try:
                start_time = datetime.strptime(start_time_param, '%Y-%m-%d %H:%M')
                start_time = timezone.make_aware(start_time)
                end_time = now
                self.stdout.write(f"📅 开始时间: {start_time.strftime('%Y-%m-%d %H:%M')}")
                self.stdout.write(f"📅 结束时间: {end_time.strftime('%Y-%m-%d %H:%M')}")
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"❌ 时间格式错误: {start_time_param} (应使用 YYYY-MM-DD HH:MM)")
                )
                return
        else:
            # 默认过去N小时
            end_time = now
            start_time = now - timedelta(hours=hours)
            self.stdout.write(f"📅 开始时间: {start_time.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"📅 结束时间: {end_time.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write(f"⏰ 统计过去 {hours} 小时")

        # 查询新币
        listings = Listing.objects.filter(
            identified_at__range=[start_time, end_time],
            announcement__exchange__code__in=exchange_codes,
            status=Listing.CONFIRMED
        ).select_related('announcement__exchange').order_by('announcement__exchange__name', 'coin_symbol')

        # 统计信息
        total_count = listings.count()
        by_exchange = {}
        by_type = {'spot': 0, 'futures': 0, 'both': 0}

        for listing in listings:
            exchange_code = listing.announcement.exchange.code
            if exchange_code not in by_exchange:
                by_exchange[exchange_code] = []
            by_exchange[exchange_code].append(listing)

            by_type[listing.listing_type] += 1

        self.stdout.write(f"总计新币: {total_count} 个")
        self.stdout.write(f"  - 现货: {by_type['spot']} 个")
        self.stdout.write(f"  - 合约: {by_type['futures']} 个")
        self.stdout.write(f"  - 现货+合约: {by_type['both']} 个")
        self.stdout.write(f"交易所分布: {', '.join([f'{k}({len(v)})' for k, v in by_exchange.items()])}")
        self.stdout.write('')

        # ========== 生成汇总报告 ==========
        self.stdout.write(self.style.SUCCESS('\n📝 生成汇总报告...'))
        self.stdout.write('-'*70)

        if total_count == 0:
            # 空结果报告
            title = f"📊 新币汇总 - 过去{hours}小时 (无新币)"
            content = self._generate_empty_report(start_time, end_time, hours, exchange_codes)
            self.stdout.write("无新币上线")
        else:
            # 有新币报告
            title = f"📊 新币汇总 - 过去{hours}小时 (共 {total_count} 个)"
            content = self._generate_detailed_report(start_time, end_time, hours, listings, by_exchange, by_type)
            self.stdout.write(f"已发现 {total_count} 个新币")

        # ========== 发送推送 ==========
        if skip_notification:
            self.stdout.write(self.style.WARNING('\n🔕 跳过推送'))
            self.stdout.write('')
            self.stdout.write('标题预览:')
            self.stdout.write(f"  {title}")
            self.stdout.write('')
            self.stdout.write('内容预览:')
            for line in content.split('\n'):
                self.stdout.write(f"  {line}")
        else:
            self.stdout.write(self.style.SUCCESS('\n📢 发送推送...'))
            self.stdout.write('-'*70)

            push_service = AlertPushService()

            # 直接发送汇总推送（不关联具体 Listing）
            success = self._send_summary_push(push_service, title, content)

            if success:
                self.stdout.write(self.style.SUCCESS('\n✅ 推送成功！'))
            else:
                self.stdout.write(self.style.ERROR('\n❌ 推送失败'))
                self.stdout.write('请检查日志获取详细错误信息')

        # ========== 显示报告 ==========
        self.stdout.write(self.style.SUCCESS('\n' + '='*70))
        self.stdout.write(self.style.SUCCESS('📋 汇总报告'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write('')
        self.stdout.write(title)
        self.stdout.write('')
        self.stdout.write(content)
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))

    def _generate_empty_report(self, start_time, end_time, hours: int, exchange_codes: list) -> str:
        """生成空结果报告"""
        lines = [
            f"统计时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}",
            f"时间窗口: {hours} 小时",
            f"监控交易所: {', '.join(exchange_codes)}",
            "",
            f"😴 过去{hours}小时未发现新币上线",
            "",
            "可能原因:",
            "• 市场休息日，无新币公告",
            "• 新币公告较少，未达识别阈值",
            "• 交易所暂无新币上线计划",
            "",
            f"统计时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        return '\n'.join(lines)

    def _generate_detailed_report(self, start_time, end_time, hours: int, listings, by_exchange: dict, by_type: dict) -> str:
        """生成详细报告"""
        lines = [
            f"统计时间范围: {start_time.strftime('%Y-%m-%d %H:%M')} ~ {end_time.strftime('%Y-%m-%d %H:%M')}",
            f"时间窗口: {hours} 小时",
            f"统计时间: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "📊 总体统计:",
            f"  总计: {len(listings)} 个新币",
            f"  现货: {by_type['spot']} 个",
            f"  合约: {by_type['futures']} 个",
            f"  现货+合约: {by_type['both']} 个",
            "",
            "🏢 按交易所分布:",
        ]

        for exchange_code, exchange_listings in by_exchange.items():
            exchange_name = exchange_listings[0].announcement.exchange.name
            lines.append(f"  {exchange_name} ({exchange_code}): {len(exchange_listings)} 个")

        lines.append("")
        lines.append("💎 详细清单:")
        lines.append("")

        for exchange_code, exchange_listings in by_exchange.items():
            exchange_name = exchange_listings[0].announcement.exchange.name
            lines.append(f"【{exchange_name}】")

            for listing in exchange_listings:
                type_display = listing.get_listing_type_display()
                confidence_pct = int(listing.confidence * 100)
                announced_at = listing.announcement.announced_at.strftime('%m-%d %H:%M')

                lines.append(
                    f"  • {listing.coin_symbol} ({type_display}) "
                    f"- 置信度 {confidence_pct}% - 公告时间 {announced_at}"
                )

            lines.append("")

        lines.append("💡 提示:")
        lines.append("• 置信度 ≥ 50% 的新币才会被推送")
        lines.append("• 点击公告链接查看详细信息")
        lines.append("• 建议结合技术分析和基本面做决策")

        return '\n'.join(lines)

    def _send_summary_push(self, push_service: AlertPushService, title: str, content: str) -> bool:
        """
        发送汇总推送（不依赖具体 Listing）

        Args:
            push_service: AlertPushService 实例
            title: 推送标题
            content: 推送内容

        Returns:
            True=发送成功, False=发送失败
        """
        try:
            import requests

            # 构建请求payload
            payload = {
                "token": push_service.token,
                "title": title,
                "content": content,
                "channel": push_service.channel
            }

            # 发送请求
            response = requests.post(
                push_service.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            # 解析响应
            response_data = response.json()

            if response_data.get('errcode') == 0:
                logger.info(f"每日汇总推送成功: {title[:50]}...")
                return True
            else:
                error_msg = f"API返回错误: {response_data.get('msg', '未知错误')}"
                logger.warning(f"每日汇总推送失败: {error_msg}")
                return False

        except Exception as e:
            error_msg = f"推送异常: {str(e)}"
            logger.error(f"每日汇总推送异常: {error_msg}", exc_info=True)
            return False