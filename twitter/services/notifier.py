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

# 默认推送配置（复用 monitor 应用的 AlertPushService 配置）
# 与 monitor 应用保持一致的 token 和 channel


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
            token: 推送服务 token（默认使用环境变量 ALERT_PUSH_TOKEN，未配置则使用默认token）
            channel: 推送渠道（默认使用环境变量 ALERT_PUSH_CHANNEL，未配置则使用默认channel "symbal_rate"）
            cost_alert_threshold: 成本告警阈值（默认使用 settings.COST_ALERT_THRESHOLD）

        Note:
            默认配置与 monitor 应用保持一致：
            token="6020867bc6334c609d4f348c22f90f14", channel="symbal_rate"
            通知功能始终启用，无需额外配置。
        """
        # 从环境变量或 settings 获取配置，如果没有则使用默认 token 和 channel
        # 使用与 monitor 应用一致的默认配置：token="6020867bc6334c609d4f348c22f90f14", channel="symbal_rate"
        self.token = token or getattr(settings, 'ALERT_PUSH_TOKEN', "6020867bc6334c609d4f348c22f90f14")
        self.channel = channel or getattr(settings, 'ALERT_PUSH_CHANNEL', "symbal_rate")
        self.cost_alert_threshold = cost_alert_threshold or getattr(
            settings, 'COST_ALERT_THRESHOLD', Decimal('5.00')
        )

        # 检查是否使用了默认配置
        using_default = (self.token == "6020867bc6334c609d4f348c22f90f14" and
                        self.channel == "symbal_rate" and
                        not token and
                        not channel and
                        not getattr(settings, 'ALERT_PUSH_TOKEN', None) and
                        not getattr(settings, 'ALERT_PUSH_CHANNEL', None))

        # 初始化推送服务（始终启用，除非显式传递 None）
        if self.token is not None:
            self.alert_service = AlertPushService(token=self.token, channel=self.channel)
            if using_default:
                logger.info("✅ 通知功能已启用（使用默认配置，与 monitor 应用保持一致）")
            else:
                logger.info("✅ 通知功能已启用（使用自定义配置）")
        else:
            self.alert_service = None
            logger.warning("⚠️ 通知功能已禁用")

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

        # 根据结果结构判断分析类型
        # 检查新格式：consensus_statistics 字段
        if 'consensus_statistics' in result:
            # 专业投研分析格式（新格式）
            return self._format_pro_investment_content(task, result)
        # 检查旧格式：以emoji开头的键名
        elif any(key.startswith('0️⃣') for key in result.keys()):
            # 专业投研分析格式（旧格式，兼容处理）
            return self._format_pro_investment_content_old(task, result)
        elif 'sentiment' in result:
            # 市场情绪分析格式
            return self._format_sentiment_content(task, result)
        else:
            # 通用分析格式
            return self._format_general_content(task, result)

    def _format_pro_investment_content_old(self, task: TwitterAnalysisResult, result: dict) -> str:
        """格式化专业投研分析内容（旧格式兼容）"""
        lines = [
            f"任务 ID: {task.task_id}",
            f"Twitter List: {task.twitter_list.name}",
            f"推文数量: {task.tweet_count} 条",
            f"",
            f"🎯 专业投研分析结果：",
            f"",
        ]

        # 0️⃣ 多空一致性统计
        consensus = result.get('0️⃣ 多空一致性统计', {})
        if consensus:
            lines.append("📊 0️⃣ 多空一致性统计：")
            # 支持字典格式（老版本）和列表格式（新版本）
            if isinstance(consensus, list):
                # 列表格式：每个元素包含资产信息
                for item in consensus:
                    if isinstance(item, dict):
                        asset = item.get('资产', 'N/A')
                        reason = item.get('主流看法 & 核心理由', 'N/A')
                        lines.append(f"  • {asset}: {reason}")
            elif isinstance(consensus, dict):
                # 字典格式：键是资产名，值是详情
                for asset, data in consensus.items():
                    if isinstance(data, dict):
                        lines.append(f"  • {asset}: {data.get('主流看法 & 核心理由', 'N/A')}")
            lines.append("")

        # 1️⃣ 观点提炼
        viewpoints = result.get('1️⃣ 观点提炼', [])
        if viewpoints:
            lines.append("💡 1️⃣ 关键观点：")
            for view in viewpoints[:3]:  # 只显示前3个
                if isinstance(view, dict):
                    # 支持中英文键名
                    kol = view.get('KOL') or view.get('kol', 'N/A')
                    asset = view.get('资产') or view.get('asset', 'N/A')
                    direction = view.get('观点方向') or view.get('view_direction', 'N/A')
                    credibility = view.get('可信度(高/中/低)') or view.get('credibility', 'N/A')
                    lines.append(f"  • @{kol} [{asset}]: {direction} (可信度: {credibility})")
            lines.append("")

        # 3️⃣ 即时信号流
        signals = result.get('3️⃣ 即时信号流', [])
        if signals:
            lines.append("⚡ 3️⃣ 即时信号流：")
            for signal in signals[:3]:  # 只显示前3个
                if isinstance(signal, dict):
                    # 支持中英文键名
                    time = signal.get('时间') or signal.get('time', 'N/A')
                    user = signal.get('用户') or signal.get('user', 'N/A')
                    direction = signal.get('方向') or signal.get('direction', 'N/A')
                    asset = signal.get('资产') or signal.get('asset', 'N/A')
                    confidence = signal.get('置信度') or signal.get('confidence', 'N/A')
                    lines.append(f"  • {time} — @{user}: {direction} {asset} (置信度: {confidence})")
            lines.append("")

        # 4️⃣ 综合研判
        ca = result.get('4️⃣ 综合研判 & 交易计划', {})
        if ca and isinstance(ca, dict):
            lines.append(f"🌡️ 4️⃣ 综合研判已生成")

        # 成本和时间
        lines.extend([
            f"",
            f"💰 成本统计：",
            f"  • 实际成本: ${task.cost_amount:.4f}",
            f"  • 处理时长: {task.processing_time:.2f} 秒",
            f"",
            f"完成时间: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ])

        return "\n".join(lines)

    def _format_pro_investment_content(self, task: TwitterAnalysisResult, result: dict) -> str:
        """格式化专业投研分析内容"""
        lines = [
            f"任务 ID: {task.task_id}",
            f"Twitter List: {task.twitter_list.name}",
            f"推文数量: {task.tweet_count} 条",
            f"",
            f"🎯 专业投研分析结果：",
            f"",
        ]

        # 0️⃣ 多空一致性统计
        consensus = result.get('consensus_statistics', [])
        if consensus:
            lines.append("📊 0️⃣ 多空一致性统计：")
            for stat in consensus[:3]:  # 只显示前3个
                lines.append(f"  • {stat.get('asset', 'N/A')}: {stat.get('main_view', 'N/A')} ({stat.get('core_reason', 'N/A')[:50]}...)")
            lines.append("")

        # 1️⃣ 观点提炼
        viewpoints = result.get('viewpoints', [])
        if viewpoints:
            lines.append("💡 1️⃣ 关键观点：")
            for view in viewpoints[:3]:  # 只显示前3个
                lines.append(f"  • @{view.get('kol', 'N/A')} [{view.get('asset', 'N/A')}]: {view.get('view_direction', 'N/A')} "
                           f"(可信度: {view.get('credibility', 'N/A')})")
            lines.append("")

        # 3️⃣ 即时信号流
        signals = result.get('signals', [])
        if signals:
            lines.append("⚡ 3️⃣ 即时信号流：")
            for signal in signals[:3]:  # 只显示前3个
                lines.append(f"  • {signal.get('time', 'N/A')} — @{signal.get('user', 'N/A')}: "
                           f"{signal.get('direction', 'N/A')} {signal.get('asset', 'N/A')} "
                           f"(置信度: {signal.get('confidence', 'N/A')})")
            lines.append("")

        # 4️⃣ 综合研判
        ca = result.get('comprehensive_analysis', {})
        if ca and 'market_thermometer' in ca:
            mt = ca['market_thermometer']
            lines.append(f"🌡️ 4️⃣ 市场情绪: {mt.get('overall_sentiment', 'N/A')}")

        # 成本和时间
        lines.extend([
            f"",
            f"💰 成本统计：",
            f"  • 实际成本: ${task.cost_amount:.4f}",
            f"  • 处理时长: {task.processing_time:.2f} 秒",
            f"",
            f"完成时间: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ])

        return "\n".join(lines)

    def _format_sentiment_content(self, task: TwitterAnalysisResult, result: dict) -> str:
        """格式化市场情绪分析内容"""
        sentiment = result.get('sentiment', {})
        lines = [
            f"任务 ID: {task.task_id}",
            f"Twitter List: {task.twitter_list.name}",
            f"推文数量: {task.tweet_count} 条",
            f"",
            f"📈 市场情绪分析结果：",
            f"",
            f"整体情绪：",
            f"  • 多头: {sentiment.get('bullish', 0)} 条 ({sentiment.get('bullish_percentage', 0):.1f}%)",
            f"  • 空头: {sentiment.get('bearish', 0)} 条 ({sentiment.get('bearish_percentage', 0):.1f}%)",
            f"  • 中性: {sentiment.get('neutral', 0)} 条 ({sentiment.get('neutral_percentage', 0):.1f}%)",
            f"",
            f"💰 成本统计：",
            f"  • 实际成本: ${task.cost_amount:.4f}",
            f"  • 处理时长: {task.processing_time:.2f} 秒",
            f"",
            f"完成时间: {task.updated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        return "\n".join(lines)

    def _format_general_content(self, task: TwitterAnalysisResult, result: dict) -> str:
        """格式化通用分析内容"""
        sentiment = result.get('sentiment', {})
        key_topics = result.get('key_topics', [])
        important_tweets = result.get('important_tweets', [])

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

        if important_tweets:
            lines.append(f"重要推文: {len(important_tweets)} 条")
            lines.append("")

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

        直接使用 AlertPushService（与 monitor 应用保持一致的推送服务）

        Args:
            title: 推送标题
            content: 推送内容

        Returns:
            bool: 是否发送成功
        """
        import requests

        try:
            payload = {
                "token": self.token,
                "title": title,
                "content": content,
                "channel": self.channel
            }

            response = requests.post(
                self.alert_service.api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            response_data = response.json()

            if response_data.get('errcode') == 0:
                logger.info(f"✅ 推送成功: {title[:50]}...")
                return True
            else:
                error_msg = response_data.get('msg', '未知错误')
                logger.warning(f"❌ 推送失败: {error_msg} (errcode: {response_data.get('errcode')})")

                # 提供配置指导
                if error_msg == '找不到数据':
                    logger.warning("💡 解决方案: 访问 https://huicheng.powerby.com.cn/api/simple/alert/ 配置接收渠道")
                    logger.warning("💡 或设置自定义环境变量:")
                    logger.warning("   export ALERT_PUSH_TOKEN='your_token'")
                    logger.warning("   export ALERT_PUSH_CHANNEL='your_channel'")

                return False

        except requests.exceptions.Timeout:
            logger.error(f"❌ 推送超时")
            return False

        except Exception as e:
            logger.error(f"❌ 推送异常: {e}")
            return False
