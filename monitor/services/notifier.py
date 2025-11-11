"""
Webhook通知服务
发送新币上线通知到用户提供的Webhook URL
"""
import requests
import logging
from datetime import datetime
from typing import Dict, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """Webhook通知器"""

    def __init__(self, webhook_url: str, max_retries: int = 3, retry_delay: int = 60):
        """
        初始化Webhook通知器

        Args:
            webhook_url: 用户提供的Webhook URL
            max_retries: 最大重试次数,默认3次
            retry_delay: 重试延迟(秒),默认60秒
        """
        self.webhook_url = webhook_url
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def format_message(self, listing) -> Dict:
        """
        格式化通知消息

        Args:
            listing: Listing模型实例

        Returns:
            Webhook payload字典
        """
        exchange = listing.get_exchange()
        announcement = listing.announcement

        return {
            'event': 'new_listing',
            'timestamp': timezone.now().isoformat(),
            'data': {
                'coin_symbol': listing.coin_symbol,
                'coin_name': listing.coin_name or '',
                'listing_type': listing.listing_type,
                'exchange': {
                    'code': exchange.code if exchange else '',
                    'name': exchange.name if exchange else '',
                },
                'confidence': listing.confidence,
                'status': listing.status,
                'announcement': {
                    'title': announcement.title,
                    'url': announcement.url,
                    'announced_at': announcement.announced_at.isoformat(),
                },
                'identified_at': listing.identified_at.isoformat(),
            }
        }

    def send_notification(self, listing, create_record: bool = True) -> bool:
        """
        发送Webhook通知

        Args:
            listing: Listing模型实例
            create_record: 是否创建通知记录,默认True

        Returns:
            True=发送成功, False=发送失败
        """
        from monitor.models import NotificationRecord

        # 格式化消息
        payload = self.format_message(listing)

        # 创建通知记录
        notification_record = None
        if create_record:
            notification_record = NotificationRecord.objects.create(
                listing=listing,
                channel=NotificationRecord.WEBHOOK,
                status=NotificationRecord.PENDING,
                retry_count=0
            )

        # 发送请求
        success = False
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.webhook_url,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                if response.status_code in [200, 201, 204]:
                    logger.info(f"Webhook通知发送成功: {listing.coin_symbol} "
                              f"(尝试 {attempt + 1}/{self.max_retries})")

                    # 更新通知记录
                    if notification_record:
                        notification_record.status = NotificationRecord.SUCCESS
                        notification_record.sent_at = timezone.now()
                        notification_record.retry_count = attempt
                        notification_record.save()

                    success = True
                    break
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.warning(f"Webhook响应异常: {error_msg}")

                    if notification_record:
                        notification_record.retry_count = attempt + 1
                        notification_record.error_message = error_msg
                        notification_record.save()

            except requests.exceptions.Timeout:
                error_msg = "请求超时(30秒)"
                logger.warning(f"Webhook发送超时 (尝试 {attempt + 1}/{self.max_retries})")

                if notification_record:
                    notification_record.retry_count = attempt + 1
                    notification_record.error_message = error_msg
                    notification_record.save()

            except requests.exceptions.RequestException as e:
                error_msg = f"请求异常: {str(e)}"
                logger.warning(f"Webhook发送失败: {error_msg} "
                             f"(尝试 {attempt + 1}/{self.max_retries})")

                if notification_record:
                    notification_record.retry_count = attempt + 1
                    notification_record.error_message = error_msg
                    notification_record.save()

            except Exception as e:
                error_msg = f"未知错误: {str(e)}"
                logger.error(f"Webhook发送异常: {error_msg}", exc_info=True)

                if notification_record:
                    notification_record.retry_count = attempt + 1
                    notification_record.error_message = error_msg
                    notification_record.save()

            # 如果不是最后一次尝试,等待后重试
            if attempt < self.max_retries - 1:
                import time
                time.sleep(self.retry_delay)

        # 如果所有重试都失败
        if not success and notification_record:
            notification_record.status = NotificationRecord.FAILED
            notification_record.save()
            logger.error(f"Webhook通知最终失败: {listing.coin_symbol} "
                        f"(重试 {self.max_retries} 次)")

        return success

    def send_batch_notifications(self, listings: list) -> Dict[str, int]:
        """
        批量发送通知

        Args:
            listings: Listing实例列表

        Returns:
            统计信息 {'success': 成功数, 'failed': 失败数}
        """
        stats = {'success': 0, 'failed': 0}

        for listing in listings:
            if self.send_notification(listing):
                stats['success'] += 1
            else:
                stats['failed'] += 1

        logger.info(f"批量通知完成: 成功 {stats['success']}, "
                   f"失败 {stats['failed']}")
        return stats

    def test_webhook(self) -> bool:
        """
        测试Webhook连接

        Returns:
            True=连接正常, False=连接失败
        """
        test_payload = {
            'event': 'test',
            'timestamp': timezone.now().isoformat(),
            'message': 'Webhook连接测试'
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=test_payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code in [200, 201, 204]:
                logger.info(f"Webhook连接测试成功: {self.webhook_url}")
                return True
            else:
                logger.warning(f"Webhook测试失败: HTTP {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Webhook测试异常: {str(e)}")
            return False


class AlertPushService:
    """
    慧诚告警推送服务
    用于发送新币上线告警到慧诚推送平台
    """

    def __init__(self, token: str = "6020867bc6334c609d4f348c22f90f14", channel: str = "symbal_rate"):
        """
        初始化告警推送服务

        Args:
            token: 认证令牌，默认使用配置的token
            channel: 推送渠道，默认"symbal_rate"
        """
        self.api_url = "https://huicheng.powerby.com.cn/api/simple/alert/"
        self.token = token
        self.channel = channel

    def format_title(self, listing) -> str:
        """
        格式化推送标题

        Args:
            listing: Listing模型实例

        Returns:
            推送标题字符串
        """
        exchange = listing.get_exchange()
        listing_type_display = listing.get_listing_type_display()

        return f"🚀 {exchange.name} 新币上线 - {listing.coin_symbol} ({listing_type_display})"

    def format_content(self, listing) -> str:
        """
        格式化推送内容

        Args:
            listing: Listing模型实例

        Returns:
            推送内容字符串（支持多行）
        """
        exchange = listing.get_exchange()
        announcement = listing.announcement
        listing_type_display = listing.get_listing_type_display()

        # 格式化时间
        announced_at_str = announcement.announced_at.strftime('%Y-%m-%d %H:%M')

        # 构建内容
        lines = [
            f"币种: {listing.coin_symbol}",
            f"名称: {listing.coin_name or '未知'}" if listing.coin_name else None,
            f"类型: {listing_type_display}",
            f"交易所: {exchange.name} ({exchange.code})",
            f"置信度: {listing.confidence:.0%}",
            f"",
            f"公告标题: {announcement.title}",
            f"发布时间: {announced_at_str}",
            f"",
            f"公告链接: {announcement.url}",
        ]

        # 过滤掉 None 值
        content = "\n".join(line for line in lines if line is not None)
        return content

    def send_notification(self, listing, create_record: bool = True) -> bool:
        """
        发送告警推送

        Args:
            listing: Listing模型实例
            create_record: 是否创建通知记录，默认True

        Returns:
            True=发送成功, False=发送失败
        """
        from monitor.models import NotificationRecord

        # 格式化标题和内容
        title = self.format_title(listing)
        content = self.format_content(listing)

        # 构建请求payload
        payload = {
            "token": self.token,
            "title": title,
            "content": content,
            "channel": self.channel
        }

        # 创建通知记录
        notification_record = None
        if create_record:
            notification_record = NotificationRecord.objects.create(
                listing=listing,
                channel=NotificationRecord.WEBHOOK,  # 复用WEBHOOK类型
                status=NotificationRecord.PENDING,
                retry_count=0
            )

        # 发送请求
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            # 解析响应
            response_data = response.json()

            if response_data.get('errcode') == 0:
                logger.info(f"告警推送成功: {listing.coin_symbol}")

                # 更新通知记录
                if notification_record:
                    notification_record.status = NotificationRecord.SUCCESS
                    notification_record.sent_at = timezone.now()
                    notification_record.save()

                return True
            else:
                error_msg = f"API返回错误: {response_data.get('msg', '未知错误')}"
                logger.warning(f"告警推送失败: {error_msg}")

                if notification_record:
                    notification_record.status = NotificationRecord.FAILED
                    notification_record.error_message = error_msg
                    notification_record.save()

                return False

        except requests.exceptions.Timeout:
            error_msg = "请求超时(30秒)"
            logger.warning(f"告警推送超时: {listing.coin_symbol}")

            if notification_record:
                notification_record.status = NotificationRecord.FAILED
                notification_record.error_message = error_msg
                notification_record.save()

            return False

        except requests.exceptions.RequestException as e:
            error_msg = f"请求异常: {str(e)}"
            logger.warning(f"告警推送失败: {error_msg}")

            if notification_record:
                notification_record.status = NotificationRecord.FAILED
                notification_record.error_message = error_msg
                notification_record.save()

            return False

        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"告警推送异常: {error_msg}", exc_info=True)

            if notification_record:
                notification_record.status = NotificationRecord.FAILED
                notification_record.error_message = error_msg
                notification_record.save()

            return False

    def send_batch_notifications(self, listings: list) -> Dict[str, int]:
        """
        批量发送告警推送

        Args:
            listings: Listing实例列表

        Returns:
            统计信息 {'success': 成功数, 'failed': 失败数}
        """
        stats = {'success': 0, 'failed': 0}

        for listing in listings:
            if self.send_notification(listing):
                stats['success'] += 1
            else:
                stats['failed'] += 1

        logger.info(f"批量告警推送完成: 成功 {stats['success']}, "
                   f"失败 {stats['failed']}")
        return stats

    def test_push(self) -> bool:
        """
        测试推送服务连接

        Returns:
            True=连接正常, False=连接失败
        """
        test_payload = {
            "token": self.token,
            "title": "🧪 推送服务测试",
            "content": "这是一条测试消息\n用于验证推送服务是否正常工作",
            "channel": self.channel
        }

        try:
            response = requests.post(
                self.api_url,
                json=test_payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            response_data = response.json()

            if response_data.get('errcode') == 0:
                logger.info(f"推送服务测试成功")
                return True
            else:
                logger.warning(f"推送服务测试失败: {response_data.get('msg')}")
                return False

        except Exception as e:
            logger.error(f"推送服务测试异常: {str(e)}")
            return False

    def format_title_futures(self, contract) -> str:
        """
        格式化futures合约推送标题

        Args:
            contract: FuturesContract模型实例

        Returns:
            推送标题字符串
        """
        return f"📈 {contract.exchange.name} 永续合约上线 - {contract.symbol}"

    def format_content_futures(self, contract) -> str:
        """
        格式化futures合约推送内容

        Args:
            contract: FuturesContract模型实例

        Returns:
            推送内容字符串（支持多行）
        """
        # 格式化时间
        first_seen_str = contract.first_seen.strftime('%Y-%m-%d %H:%M:%S')
        last_updated_str = contract.last_updated.strftime('%Y-%m-%d %H:%M:%S')

        # 构建内容
        lines = [
            f"合约代码: {contract.symbol}",
            f"交易类型: {contract.get_contract_type_display()}",
            f"交易所: {contract.exchange.name} ({contract.exchange.code})",
            f"当前价格: ${contract.current_price}",
            f"",
            f"状态: {contract.get_status_display()}",
            f"首次发现: {first_seen_str}",
            f"最后更新: {last_updated_str}",
        ]

        # 过滤掉 None 值
        content = "\n".join(line for line in lines if line is not None)
        return content

    def send_notification_futures(self, contract, create_record: bool = False) -> bool:
        """
        发送futures合约告警推送

        Args:
            contract: FuturesContract模型实例
            create_record: 是否创建通知记录，默认False（由调用方创建）

        Returns:
            True=发送成功, False=发送失败
        """
        # 格式化标题和内容
        title = self.format_title_futures(contract)
        content = self.format_content_futures(contract)

        # 构建请求payload
        payload = {
            "token": self.token,
            "title": title,
            "content": content,
            "channel": self.channel
        }

        # 发送请求
        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            # 解析响应
            response_data = response.json()

            if response_data.get('errcode') == 0:
                logger.info(f"合约告警推送成功: {contract.symbol}")
                return True
            else:
                error_msg = f"API返回错误: {response_data.get('msg', '未知错误')}"
                logger.warning(f"合约告警推送失败: {error_msg}")
                return False

        except requests.exceptions.Timeout:
            error_msg = "请求超时(30秒)"
            logger.warning(f"合约告警推送超时: {contract.symbol}")
            return False

        except requests.exceptions.RequestException as e:
            error_msg = f"请求异常: {str(e)}"
            logger.warning(f"合约告警推送失败: {error_msg}")
            return False

        except Exception as e:
            error_msg = f"未知错误: {str(e)}"
            logger.error(f"合约告警推送异常: {error_msg}", exc_info=True)
            return False


def get_webhook_url_from_env() -> Optional[str]:
    """
    从环境变量获取Webhook URL

    Returns:
        Webhook URL字符串,未配置返回None
    """
    import os
    webhook_url = os.getenv('WEBHOOK_URL', '').strip()

    if not webhook_url:
        logger.warning("未配置WEBHOOK_URL环境变量")
        return None

    return webhook_url
