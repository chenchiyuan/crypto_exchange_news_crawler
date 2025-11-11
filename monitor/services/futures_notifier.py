"""
新合约通知服务
用于检测新上线合约并通过慧诚告警推送发送通知
"""
import logging
from typing import List, Dict
from datetime import datetime, timedelta

from django.utils import timezone
from django.db.models import Q

from monitor.models import FuturesContract, FuturesListingNotification
from monitor.services.notifier import AlertPushService

logger = logging.getLogger(__name__)


class FuturesNotifierService:
    """新合约通知服务"""

    def __init__(self):
        """初始化通知服务"""
        self.alert_service = AlertPushService()
        self.notifications_sent = 0
        self.notifications_failed = 0

    def detect_new_listings(self, current_contracts: List[FuturesContract]) -> List[FuturesContract]:
        """
        检测新上线的合约

        新合约的判断条件：
        1. first_seen == last_updated (即首次创建)
        2. 初始部署已完成（避免历史数据触发通知）

        Args:
            current_contracts: 当前获取的合约列表

        Returns:
            新合约列表
        """
        if not current_contracts:
            return []

        # 检查初始部署是否完成
        if not self._is_initial_deployment_completed():
            logger.info("初始部署阶段，跳过新合约通知")
            return []

        # 获取所有活跃合约的ID集合
        contract_ids = {c.id for c in current_contracts}

        # 查找可能是新合约的记录
        # first_seen 字段与 last_updated 相同，表示是刚刚创建
        new_contracts = FuturesContract.objects.filter(
            id__in=contract_ids,
            status=FuturesContract.ACTIVE,
            # 过滤出first_seen和last_updated在5分钟内的记录
            # 这样可以捕获最近创建但还没有被重复获取过的合约
            first_seen__gte=timezone.now() - timedelta(minutes=5)
        ).order_by('first_seen')

        if new_contracts.exists():
            logger.info(f"检测到 {new_contracts.count()} 个新合约")

        return list(new_contracts)

    def send_new_listing_notifications(self, new_contracts: List[FuturesContract]) -> Dict[str, int]:
        """
        发送新合约上线通知

        Args:
            new_contracts: 新合约列表

        Returns:
            发送统计信息 {'success': 成功数, 'failed': 失败数}
        """
        if not new_contracts:
            logger.info("没有新合约需要发送通知")
            return {'success': 0, 'failed': 0}

        self.notifications_sent = 0
        self.notifications_failed = 0

        # 逐个发送通知
        for contract in new_contracts:
            # 检查是否已经发送过通知（避免重复通知）
            existing_notification = FuturesListingNotification.objects.filter(
                futures_contract=contract,
                status=FuturesListingNotification.SUCCESS
            ).first()

            if existing_notification:
                logger.debug(f"合约 {contract.symbol} 已经发送过通知，跳过")
                continue

            # 发送通知
            success = self._send_notification(contract)

            if success:
                self.notifications_sent += 1
            else:
                self.notifications_failed += 1

        # 记录结果
        logger.info(f"新合约通知发送完成: 成功 {self.notifications_sent}, "
                   f"失败 {self.notifications_failed}")

        return {
            'success': self.notifications_sent,
            'failed': self.notifications_failed
        }

    def _send_notification(self, contract: FuturesContract) -> bool:
        """
        发送单个合约的通知

        Args:
            contract: 合约实例

        Returns:
            True=发送成功, False=发送失败
        """
        try:
            # 创建通知记录
            notification = FuturesListingNotification.objects.create(
                futures_contract=contract,
                channel=FuturesListingNotification.WEBHOOK,
                status=FuturesListingNotification.PENDING
            )

            # 发送通知
            success = self.alert_service.send_notification_futures(contract)

            # 更新通知记录
            if success:
                notification.status = FuturesListingNotification.SUCCESS
                notification.sent_at = timezone.now()
                notification.save()
                logger.info(f"✅ 新合约通知发送成功: {contract.exchange.name} - {contract.symbol}")
            else:
                notification.status = FuturesListingNotification.FAILED
                notification.save()
                logger.error(f"❌ 新合约通知发送失败: {contract.exchange.name} - {contract.symbol}")

            return success

        except Exception as e:
            logger.error(f"发送合约通知异常: {contract.symbol} - {str(e)}", exc_info=True)
            return False

    def _is_initial_deployment_completed(self) -> bool:
        """
        检查初始部署是否完成

        Returns:
            是否完成
        """
        import os
        from config.futures_config import INITIAL_DEPLOYMENT_FLAG

        return os.path.exists(INITIAL_DEPLOYMENT_FLAG)

    def get_notification_stats(self) -> Dict[str, int]:
        """
        获取通知统计信息

        Returns:
            统计信息字典
        """
        return {
            'sent': self.notifications_sent,
            'failed': self.notifications_failed,
        }
