"""
Twitter 分析通知服务

用于发送 Twitter 分析任务完成/失败/成本告警通知
复用 monitor 应用的 AlertPushService
"""
import logging
from decimal import Decimal
from typing import Optional
from django.conf import settings

from monitor.services.notifier import AlertPushService
from twitter.models import TwitterAnalysisResult


logger = logging.getLogger(__name__)


class TwitterNotificationService:
    """
    Twitter 分析通知服务

    负责发送分析任务的各类通知：
    - 分析完成通知（包含结果摘要）
    - 分析失败通知（包含错误信息）
    - 成本告警通知（成本超过阈值时）
    """

    def __init__(self,
                 token: str = None,
                 channel: str = None,
                 cost_alert_threshold: Decimal = None):
        """
        初始化通知服务

        Args:
            token: 推送服务 token（默认使用环境变量 ALERT_PUSH_TOKEN）
            channel: 推送渠道（默认使用环境变量 ALERT_PUSH_CHANNEL 或 "twitter_analysis"）
            cost_alert_threshold: 成本告警阈值（默认使用 settings.COST_ALERT_THRESHOLD）
        """
        # 从环境变量或 settings 获取配置
        self.token = token or getattr(settings, 'ALERT_PUSH_TOKEN', None)
        self.channel = channel or getattr(settings, 'ALERT_PUSH_CHANNEL', 'twitter_analysis')
        self.cost_alert_threshold = cost_alert_threshold or getattr(
            settings, 'COST_ALERT_THRESHOLD', Decimal('5.00')
        )

        # 初始化推送服务（如果有 token）
        if self.token:
            self.alert_service = AlertPushService(token=self.token, channel=self.channel)
        else:
            self.alert_service = None
            logger.warning("未配置 ALERT_PUSH_TOKEN，通知功能将被禁用")

    def is_enabled(self) -> bool:
        """
        检查通知服务是否启用

        Returns:
            bool: 是否启用
        """
        return self.alert_service is not None

    def format_completion_title(self, task: TwitterAnalysisResult) -> str:
        """
        格式化完成通知标题

        Args:
            task: 任务对象

        Returns:
            str: 标题字符串
        """
        return f"✅ Twitter 分析完成 - {task.twitter_list.name}"

    def format_completion_content(self, task: TwitterAnalysisResult) -> str:
        """
        格式化完成通知内容

        Args:
            task: 任务对象

        Returns:
            str: 内容字符串（多行）
        """
        result = task.analysis_result or {}
        sentiment = result.get('sentiment', {})
        key_topics = result.get('key_topics', [])
        important_tweets = result.get('important_tweets', [])

        # 构建内容
        lines = [
            f"任务 ID: {task.task_id}",
            f"Twitter List: {task.twitter_list.name}",
            f"推文数量: {task.tweet_count} 条",
            f"",
            f"📊 分析结果：",
            f"",
            f"市场情绪：",
            f"  • 多头: {sentiment.get('bullish', 0)} 条 ({sentiment.get('bullish_percentage', 0):.1f}%)",
            f"  • 空头: {sentiment.get('bearish', 0)} 条 ({sentiment.get('bearish_percentage', 0):.1f}%)",
            f"  • 中性: {sentiment.get('neutral', 0)} 条 ({sentiment.get('neutral_percentage', 0):.1f}%)",
            f"",
        ]

        # 关键话题（最多 5 个）
        if key_topics:
            lines.append("关键话题：")
            for i, topic in enumerate(key_topics[:5], 1):
                sentiment_icon = {
                    'bullish': '📈',
                    'bearish': '📉',
                    'neutral': '➖'
                }.get(topic.get('sentiment', 'neutral'), '➖')
                lines.append(f"  {i}. {topic['topic']} ({topic['count']} 次) {sentiment_icon}")
            lines.append("")

        # 重要推文数量
        if important_tweets:
            lines.append(f"重要推文: {len(important_tweets)} 条")
            lines.append("")

        # 成本和时间
        lines.extend([
            f"💰 成本统计：",
            f"  • 实际成本: ${task.cost_amount:.4f}",
            f"  • 处理时长: {task.processing_time:.2f} 秒",
            f"",
            f"完成时间: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ])

        return "\n".join(lines)

    def format_failure_title(self, task: TwitterAnalysisResult) -> str:
        """
        格式化失败通知标题

        Args:
            task: 任务对象

        Returns:
            str: 标题字符串
        """
        return f"❌ Twitter 分析失败 - {task.twitter_list.name}"

    def format_failure_content(self, task: TwitterAnalysisResult) -> str:
        """
        格式化失败通知内容

        Args:
            task: 任务对象

        Returns:
            str: 内容字符串（多行）
        """
        lines = [
            f"任务 ID: {task.task_id}",
            f"Twitter List: {task.twitter_list.name}",
            f"推文数量: {task.tweet_count} 条",
            f"",
            f"⚠️ 错误信息：",
            f"{task.error_message}",
            f"",
            f"处理时长: {task.processing_time:.2f} 秒",
            f"失败时间: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]

        return "\n".join(lines)

    def format_cost_alert_title(self, task: TwitterAnalysisResult) -> str:
        """
        格式化成本告警标题

        Args:
            task: 任务对象

        Returns:
            str: 标题字符串
        """
        return f"⚠️ Twitter 分析成本告警 - {task.twitter_list.name}"

    def format_cost_alert_content(self, task: TwitterAnalysisResult) -> str:
        """
        格式化成本告警内容

        Args:
            task: 任务对象

        Returns:
            str: 内容字符串（多行）
        """
        lines = [
            f"任务 ID: {task.task_id}",
            f"Twitter List: {task.twitter_list.name}",
            f"推文数量: {task.tweet_count} 条",
            f"",
            f"💰 成本告警：",
            f"  • 实际成本: ${task.cost_amount:.4f}",
            f"  • 告警阈值: ${self.cost_alert_threshold:.2f}",
            f"  • 超出比例: {(task.cost_amount / self.cost_alert_threshold - 1) * 100:.1f}%",
            f"",
            f"处理时长: {task.processing_time:.2f} 秒",
            f"完成时间: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"",
            f"⚠️ 提示: 建议检查分析参数，避免成本过高",
        ]

        return "\n".join(lines)

    def send_completion_notification(self, task: TwitterAnalysisResult) -> bool:
        """
        发送完成通知

        Args:
            task: 任务对象

        Returns:
            bool: 是否发送成功
        """
        if not self.is_enabled():
            logger.info(f"[Task {task.task_id}] 通知服务未启用，跳过完成通知")
            return False

        logger.info(f"[Task {task.task_id}] 发送完成通知")

        title = self.format_completion_title(task)
        content = self.format_completion_content(task)

        try:
            success = self._send_push(title, content)
            if success:
                logger.info(f"[Task {task.task_id}] 完成通知发送成功")
            else:
                logger.warning(f"[Task {task.task_id}] 完成通知发送失败")
            return success

        except Exception as e:
            logger.error(f"[Task {task.task_id}] 完成通知发送异常: {e}", exc_info=True)
            return False

    def send_failure_notification(self, task: TwitterAnalysisResult) -> bool:
        """
        发送失败通知

        Args:
            task: 任务对象

        Returns:
            bool: 是否发送成功
        """
        if not self.is_enabled():
            logger.info(f"[Task {task.task_id}] 通知服务未启用，跳过失败通知")
            return False

        logger.info(f"[Task {task.task_id}] 发送失败通知")

        title = self.format_failure_title(task)
        content = self.format_failure_content(task)

        try:
            success = self._send_push(title, content)
            if success:
                logger.info(f"[Task {task.task_id}] 失败通知发送成功")
            else:
                logger.warning(f"[Task {task.task_id}] 失败通知发送失败")
            return success

        except Exception as e:
            logger.error(f"[Task {task.task_id}] 失败通知发送异常: {e}", exc_info=True)
            return False

    def send_cost_alert(self, task: TwitterAnalysisResult) -> bool:
        """
        发送成本告警通知

        Args:
            task: 任务对象

        Returns:
            bool: 是否发送成功
        """
        if not self.is_enabled():
            logger.info(f"[Task {task.task_id}] 通知服务未启用，跳过成本告警")
            return False

        # 检查是否需要发送告警
        if task.cost_amount <= self.cost_alert_threshold:
            logger.debug(f"[Task {task.task_id}] 成本 ${task.cost_amount:.4f} "
                        f"未超过阈值 ${self.cost_alert_threshold:.2f}，跳过告警")
            return True  # 不需要发送，返回 True

        logger.warning(f"[Task {task.task_id}] 成本 ${task.cost_amount:.4f} "
                      f"超过阈值 ${self.cost_alert_threshold:.2f}，发送告警")

        title = self.format_cost_alert_title(task)
        content = self.format_cost_alert_content(task)

        try:
            success = self._send_push(title, content)
            if success:
                logger.info(f"[Task {task.task_id}] 成本告警发送成功")
            else:
                logger.warning(f"[Task {task.task_id}] 成本告警发送失败")
            return success

        except Exception as e:
            logger.error(f"[Task {task.task_id}] 成本告警发送异常: {e}", exc_info=True)
            return False

    def _send_push(self, title: str, content: str) -> bool:
        """
        发送推送消息（内部方法）

        Args:
            title: 推送标题
            content: 推送内容

        Returns:
            bool: 是否发送成功
        """
        import requests

        payload = {
            "token": self.token,
            "title": title,
            "content": content,
            "channel": self.channel
        }

        try:
            response = requests.post(
                self.alert_service.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            response_data = response.json()

            if response_data.get('errcode') == 0:
                logger.info(f"推送成功: {title[:50]}...")
                return True
            else:
                error_msg = response_data.get('msg', '未知错误')
                logger.warning(f"推送失败: {error_msg}")
                return False

        except requests.exceptions.Timeout:
            logger.error(f"推送超时")
            return False

        except Exception as e:
            logger.error(f"推送异常: {e}")
            return False
