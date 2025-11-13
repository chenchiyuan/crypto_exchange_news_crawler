import time
import logging
from decimal import Decimal
from typing import Dict, Optional, List, Tuple
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from django.db import transaction

from twitter.models import TwitterList, Tweet, TwitterAnalysisResult
from twitter.sdk.deepseek_sdk import DeepSeekSDK, DeepSeekAPIError
from twitter.services.ai_analysis_service import AIAnalysisService
from twitter.services.notifier import TwitterNotificationService


logger = logging.getLogger(__name__)


class CostLimitExceededError(Exception):
    """成本超限异常"""
    def __init__(self, estimated_cost: Decimal, max_cost: Decimal):
        self.estimated_cost = estimated_cost
        self.max_cost = max_cost
        message = f"预估成本 ${estimated_cost:.4f} 超过上限 ${max_cost:.4f}"
        super().__init__(message)


class TwitterAnalysisOrchestrator:
    """
    Twitter 分析编排器

    负责编排完整的分析流程：
    1. 创建分析任务
    2. 获取推文数据
    3. 估算成本并检查上限
    4. 执行 AI 分析
    5. 保存结果并更新任务状态
    """

    def __init__(self, deepseek_sdk: DeepSeekSDK = None,
                 ai_service: AIAnalysisService = None,
                 notifier: TwitterNotificationService = None):
        """
        初始化编排器

        Args:
            deepseek_sdk: DeepSeekSDK 实例（可选）
            ai_service: AIAnalysisService 实例（可选）
            notifier: TwitterNotificationService 实例（可选）
        """
        self.sdk = deepseek_sdk or DeepSeekSDK()
        self.ai_service = ai_service or AIAnalysisService(deepseek_sdk=self.sdk)
        self.notifier = notifier or TwitterNotificationService()

    def create_analysis_task(self,
                            twitter_list: TwitterList,
                            start_time: datetime,
                            end_time: datetime,
                            prompt_template: str) -> TwitterAnalysisResult:
        """
        创建分析任务记录

        Args:
            twitter_list: Twitter List 对象
            start_time: 分析起始时间
            end_time: 分析结束时间
            prompt_template: Prompt 模板内容

        Returns:
            TwitterAnalysisResult: 创建的任务对象
        """
        task = TwitterAnalysisResult.objects.create(
            twitter_list=twitter_list,
            start_time=start_time,
            end_time=end_time,
            prompt_template=prompt_template,
            status=TwitterAnalysisResult.STATUS_PENDING
        )

        logger.info(f"[Task {task.task_id}] 创建分析任务: List={twitter_list.name}, "
                   f"时间范围={start_time} ~ {end_time}")

        return task

    def get_tweets_for_analysis(self,
                                twitter_list: TwitterList,
                                start_time: datetime,
                                end_time: datetime) -> List[Tweet]:
        """
        获取待分析的推文

        Args:
            twitter_list: Twitter List 对象
            start_time: 起始时间
            end_time: 结束时间

        Returns:
            List[Tweet]: 推文列表

        Raises:
            ValueError: 没有找到推文
        """
        tweets = list(Tweet.get_tweets_in_range(twitter_list, start_time, end_time))

        if not tweets:
            raise ValueError(f"在时间范围 {start_time} ~ {end_time} 内没有找到推文")

        logger.info(f"获取到 {len(tweets)} 条待分析推文")
        return tweets

    def estimate_cost_and_validate(self,
                                   tweets: List[Tweet],
                                   prompt_template: str,
                                   max_cost: Decimal) -> Tuple[int, Decimal]:
        """
        估算成本并验证是否超限

        Args:
            tweets: 推文列表
            prompt_template: Prompt 模板
            max_cost: 最大允许成本

        Returns:
            Tuple[int, Decimal]: (token 数, 预估成本)

        Raises:
            CostLimitExceededError: 成本超限
        """
        estimated_tokens, estimated_cost = self.ai_service.estimate_analysis_cost(
            tweets=tweets,
            prompt_template=prompt_template
        )

        if estimated_cost > max_cost:
            logger.warning(f"成本超限: 预估 ${estimated_cost:.4f} > 上限 ${max_cost:.4f}")
            raise CostLimitExceededError(estimated_cost, max_cost)

        logger.info(f"成本检查通过: 预估 ${estimated_cost:.4f} ≤ 上限 ${max_cost:.4f}")
        return estimated_tokens, estimated_cost

    def execute_analysis(self,
                        task: TwitterAnalysisResult,
                        tweets: List[Tweet],
                        batch_mode: bool = None,
                        batch_size: int = 100) -> Dict:
        """
        执行 AI 分析

        Args:
            task: 任务对象
            tweets: 推文列表
            batch_mode: 批次模式（None=自动）
            batch_size: 批次大小

        Returns:
            Dict: 分析结果字典

        Raises:
            DeepSeekAPIError: API 调用失败
        """
        # 标记任务为运行中
        task.mark_as_running()

        # 记录开始时间
        start_time = time.time()

        try:
            # 执行分析
            analysis_result = self.ai_service.analyze_tweets(
                tweets=tweets,
                prompt_template=task.prompt_template,
                batch_mode=batch_mode,
                batch_size=batch_size,
                task_id=str(task.task_id)
            )

            # 计算实际处理时长
            processing_time = time.time() - start_time

            # 提取成本信息
            metadata = analysis_result.get('analysis_metadata', {})
            actual_cost = Decimal(str(metadata.get('actual_cost', 0)))

            logger.info(f"[Task {task.task_id}] 分析完成: "
                       f"成本=${actual_cost:.4f}, 耗时={processing_time:.2f}s")

            return analysis_result

        except Exception as e:
            # 记录处理时长
            processing_time = time.time() - start_time
            logger.error(f"[Task {task.task_id}] 分析失败: {str(e)}, 耗时={processing_time:.2f}s")
            raise

    def run_analysis(self,
                    twitter_list: TwitterList,
                    start_time: datetime,
                    end_time: datetime,
                    prompt_template: str = None,
                    max_cost: Decimal = None,
                    batch_mode: bool = None,
                    batch_size: int = 100,
                    dry_run: bool = False) -> TwitterAnalysisResult:
        """
        运行完整的分析流程

        Args:
            twitter_list: Twitter List 对象
            start_time: 分析起始时间
            end_time: 分析结束时间
            prompt_template: Prompt 模板内容（可选）
            max_cost: 最大允许成本（可选，默认使用配置）
            batch_mode: 批次模式（None=自动）
            batch_size: 批次大小
            dry_run: 是否为演练模式（仅估算，不执行）

        Returns:
            TwitterAnalysisResult: 任务对象

        Raises:
            ValueError: 参数验证失败或没有推文
            CostLimitExceededError: 成本超限
            DeepSeekAPIError: AI API 调用失败
        """
        # 1. 加载 prompt 模板
        if prompt_template is None:
            prompt_template = self.ai_service.load_prompt_template()

        # 2. 设置成本上限
        if max_cost is None:
            max_cost = getattr(settings, 'MAX_COST_PER_ANALYSIS', Decimal('10.00'))

        # 3. 创建任务记录
        task = self.create_analysis_task(
            twitter_list=twitter_list,
            start_time=start_time,
            end_time=end_time,
            prompt_template=prompt_template
        )

        try:
            # 4. 获取推文
            tweets = self.get_tweets_for_analysis(twitter_list, start_time, end_time)
            task.tweet_count = len(tweets)
            task.save(update_fields=['tweet_count'])

            # 5. 估算成本并验证
            estimated_tokens, estimated_cost = self.estimate_cost_and_validate(
                tweets=tweets,
                prompt_template=prompt_template,
                max_cost=max_cost
            )

            logger.info(f"[Task {task.task_id}] 成本估算: {estimated_tokens} tokens, "
                       f"约 ${estimated_cost:.4f}")

            # 6. 如果是 dry-run，直接返回
            if dry_run:
                logger.info(f"[Task {task.task_id}] Dry-run 模式，跳过实际分析")
                task.status = TwitterAnalysisResult.STATUS_CANCELLED
                task.save(update_fields=['status'])
                return task

            # 7. 执行分析
            start_time_exec = time.time()
            analysis_result = self.execute_analysis(
                task=task,
                tweets=tweets,
                batch_mode=batch_mode,
                batch_size=batch_size
            )
            processing_time = time.time() - start_time_exec

            # 8. 提取成本信息
            metadata = analysis_result.get('analysis_metadata', {})
            actual_cost = Decimal(str(metadata.get('actual_cost', 0)))

            # 9. 保存结果并标记为完成
            task.mark_as_completed(
                analysis_result=analysis_result,
                cost_amount=actual_cost,
                processing_time=processing_time
            )

            logger.info(f"[Task {task.task_id}] 分析任务完成: "
                       f"推文数={len(tweets)}, 成本=${actual_cost:.4f}, "
                       f"耗时={processing_time:.2f}s")

            # 10. 发送完成通知
            try:
                self.notifier.send_completion_notification(task)
            except Exception as e:
                logger.error(f"[Task {task.task_id}] 发送完成通知失败: {e}")

            # 11. 检查成本告警
            try:
                self.notifier.send_cost_alert(task)
            except Exception as e:
                logger.error(f"[Task {task.task_id}] 发送成本告警失败: {e}")

            return task

        except CostLimitExceededError as e:
            # 成本超限
            error_message = str(e)
            task.mark_as_failed(error_message)
            logger.error(f"[Task {task.task_id}] 成本超限: {error_message}")

            # 发送失败通知
            try:
                self.notifier.send_failure_notification(task)
            except Exception as notify_error:
                logger.error(f"[Task {task.task_id}] 发送失败通知失败: {notify_error}")

            raise

        except ValueError as e:
            # 参数验证失败或没有推文
            error_message = str(e)
            task.mark_as_failed(error_message)
            logger.error(f"[Task {task.task_id}] 参数错误: {error_message}")

            # 发送失败通知
            try:
                self.notifier.send_failure_notification(task)
            except Exception as notify_error:
                logger.error(f"[Task {task.task_id}] 发送失败通知失败: {notify_error}")

            raise

        except DeepSeekAPIError as e:
            # AI API 调用失败
            error_message = f"DeepSeek API 错误: {str(e)}"
            task.mark_as_failed(error_message)
            logger.error(f"[Task {task.task_id}] API 调用失败: {error_message}")

            # 发送失败通知
            try:
                self.notifier.send_failure_notification(task)
            except Exception as notify_error:
                logger.error(f"[Task {task.task_id}] 发送失败通知失败: {notify_error}")

            raise

        except Exception as e:
            # 其他未知错误
            error_message = f"未知错误: {str(e)}"
            task.mark_as_failed(error_message)
            logger.exception(f"[Task {task.task_id}] 分析失败")

            # 发送失败通知
            try:
                self.notifier.send_failure_notification(task)
            except Exception as notify_error:
                logger.error(f"[Task {task.task_id}] 发送失败通知失败: {notify_error}")

            raise

    def cancel_task(self, task: TwitterAnalysisResult) -> bool:
        """
        取消分析任务

        Args:
            task: 任务对象

        Returns:
            bool: 是否成功取消
        """
        if not task.can_be_cancelled():
            logger.warning(f"[Task {task.task_id}] 任务状态为 {task.status}，无法取消")
            return False

        task.mark_as_cancelled()
        logger.info(f"[Task {task.task_id}] 任务已取消")
        return True

    def get_task_status(self, task_id: str) -> Optional[TwitterAnalysisResult]:
        """
        查询任务状态

        Args:
            task_id: 任务 ID

        Returns:
            Optional[TwitterAnalysisResult]: 任务对象，如果不存在则返回 None
        """
        try:
            return TwitterAnalysisResult.objects.get(task_id=task_id)
        except TwitterAnalysisResult.DoesNotExist:
            logger.warning(f"任务 {task_id} 不存在")
            return None
