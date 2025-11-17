import json
import logging
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pathlib import Path

from django.conf import settings
from twitter.sdk.deepseek_sdk import DeepSeekSDK, DeepSeekAPIError, DeepSeekResponse
from twitter.models import Tweet


logger = logging.getLogger(__name__)


class AIAnalysisService:
    """
    AI 分析服务

    负责调用 DeepSeek AI API 分析推文内容，支持批次和一次性分析模式。
    """

    # 默认批次大小
    DEFAULT_BATCH_SIZE = 100

    # 默认 prompt 模板路径
    DEFAULT_PROMPT_TEMPLATE = 'twitter/templates/prompts/crypto_analysis.txt'

    def __init__(self, deepseek_sdk: DeepSeekSDK = None):
        """
        初始化 AI 分析服务

        Args:
            deepseek_sdk: DeepSeekSDK 实例，如果为 None 则自动创建
        """
        self.sdk = deepseek_sdk or DeepSeekSDK()

    def load_prompt_template(self, template_path: str = None) -> str:
        """
        加载 prompt 模板

        Args:
            template_path: 模板文件路径，如果为 None 则使用默认模板

        Returns:
            str: 模板内容

        Raises:
            FileNotFoundError: 模板文件不存在
        """
        if template_path is None:
            template_path = self.DEFAULT_PROMPT_TEMPLATE

        # 转换为绝对路径
        if not Path(template_path).is_absolute():
            template_path = Path(settings.BASE_DIR) / template_path

        if not Path(template_path).exists():
            raise FileNotFoundError(f"Prompt template not found: {template_path}")

        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()

    def format_tweets_for_analysis(self, tweets: List[Tweet]) -> str:
        """
        格式化推文列表为分析文本

        Args:
            tweets: 推文对象列表

        Returns:
            str: 格式化后的文本
        """
        formatted_lines = []

        for i, tweet in enumerate(tweets, 1):
            formatted_lines.append(
                f"{i}. [@{tweet.screen_name}] ({tweet.tweet_created_at.strftime('%Y-%m-%d %H:%M')})\n"
                f"   内容: {tweet.content}\n"
                f"   互动: 👍{tweet.favorite_count} 🔄{tweet.retweet_count} 💬{tweet.reply_count}\n"
                f"   Tweet ID: {tweet.tweet_id}\n"
            )

        return "\n".join(formatted_lines)

    def estimate_analysis_cost(self, tweets: List[Tweet],
                              prompt_template: str = None) -> Tuple[int, Decimal]:
        """
        估算分析成本

        Args:
            tweets: 要分析的推文列表
            prompt_template: Prompt 模板内容（可选）

        Returns:
            Tuple[int, Decimal]: (预估 token 数, 预估成本)
        """
        # 加载 prompt 模板
        if prompt_template is None:
            prompt_template = self.load_prompt_template()

        # 格式化推文内容
        tweets_text = self.format_tweets_for_analysis(tweets)

        # 计算总文本长度
        full_text = prompt_template + "\n\n" + tweets_text

        # 估算 token 数
        estimated_tokens = self.sdk.count_tokens(full_text)

        # 估算成本（包含输入和预估输出）
        estimated_cost = self.sdk.estimate_cost(estimated_tokens)

        logger.info(f"成本估算: {len(tweets)} 条推文, "
                   f"约 {estimated_tokens} tokens, "
                   f"预估成本 ${estimated_cost:.4f}")

        return estimated_tokens, estimated_cost

    def analyze_tweets_once(self, tweets: List[Tweet],
                           prompt_template: str,
                           task_id: str = None,
                           save_prompt: bool = False) -> Dict:
        """
        一次性分析推文（适用于少量推文 <100 条）

        Args:
            tweets: 推文列表
            prompt_template: Prompt 模板内容
            task_id: 任务 ID（用于日志记录）
            save_prompt: 是否保存推送给AI前的原始内容（用于调试）

        Returns:
            Dict: 分析结果字典

        Raises:
            DeepSeekAPIError: API 调用失败
            ValueError: 解析结果失败
        """
        logger.info(f"[Task {task_id}] 开始一次性分析 {len(tweets)} 条推文")

        # 格式化推文内容
        tweets_text = self.format_tweets_for_analysis(tweets)

        # 调用 AI API
        response = self.sdk.analyze_content(
            content=tweets_text,
            prompt_template=prompt_template,
            task_id=task_id
        )

        # 保存原始prompt（如果启用）
        if save_prompt:
            self._save_prompt_for_debug(
                task_id=task_id,
                prompt_template=prompt_template,
                tweets_text=tweets_text,
                final_prompt=response.content if hasattr(response, 'content') else str(response)
            )

        # 解析 JSON 结果
        analysis_result = self._parse_ai_response(response.content)

        # 添加元数据
        analysis_result['analysis_metadata'] = {
            'total_tweets': len(tweets),
            'analysis_timestamp': datetime.now().isoformat(),
            'time_range': f"{tweets[0].tweet_created_at.isoformat()} ~ {tweets[-1].tweet_created_at.isoformat()}" if tweets else "N/A",
            'tokens_used': response.tokens_used,
            'actual_cost': float(response.cost_estimate),
            'processing_time_ms': response.processing_time_ms,
            'model': response.model
        }

        logger.info(f"[Task {task_id}] 分析完成, 成本: ${response.cost_estimate:.4f}, "
                   f"耗时: {response.processing_time_ms}ms")

        return analysis_result

    def analyze_tweets_batch(self, tweets: List[Tweet],
                            prompt_template: str,
                            batch_size: int = DEFAULT_BATCH_SIZE,
                            task_id: str = None,
                            save_prompt: bool = False) -> Dict:
        """
        分批分析推文（适用于大量推文 ≥100 条）

        Args:
            tweets: 推文列表
            prompt_template: Prompt 模板内容
            batch_size: 每批推文数量
            task_id: 任务 ID（用于日志记录）
            save_prompt: 是否保存推送给AI前的原始内容（用于调试）

        Returns:
            Dict: 合并后的分析结果字典

        Raises:
            DeepSeekAPIError: API 调用失败
            ValueError: 解析结果失败
        """
        logger.info(f"[Task {task_id}] 开始分批分析 {len(tweets)} 条推文, "
                   f"批次大小: {batch_size}")

        batch_results = []
        total_cost = Decimal('0.0000')
        total_tokens = 0
        total_time_ms = 0

        # 保存调试信息（仅第一批）
        if save_prompt:
            first_batch_tweets = tweets[:batch_size]
            tweets_text = self.format_tweets_for_analysis(first_batch_tweets)
            self._save_prompt_for_debug(
                task_id=f"{task_id}_batch_1",
                prompt_template=prompt_template,
                tweets_text=tweets_text,
                final_prompt="[批次模式: 多个批次合并结果]"
            )

        # 分批处理
        for i in range(0, len(tweets), batch_size):
            batch = tweets[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(tweets) + batch_size - 1) // batch_size

            logger.info(f"[Task {task_id}] 处理批次 {batch_num}/{total_batches} "
                       f"({len(batch)} 条推文)")

            # 分析单个批次
            batch_result = self.analyze_tweets_once(
                tweets=batch,
                prompt_template=prompt_template,
                task_id=f"{task_id}_batch{batch_num}"
            )

            batch_results.append(batch_result)

            # 累计统计
            metadata = batch_result.get('analysis_metadata', {})
            total_cost += Decimal(str(metadata.get('actual_cost', 0)))
            total_tokens += metadata.get('tokens_used', 0)
            total_time_ms += metadata.get('processing_time_ms', 0)

        # 合并批次结果
        merged_result = self._merge_batch_results(batch_results)

        # 更新合并后的元数据
        merged_result['analysis_metadata'] = {
            'total_tweets': len(tweets),
            'analysis_timestamp': datetime.now().isoformat(),
            'time_range': f"{tweets[0].tweet_created_at.isoformat()} ~ {tweets[-1].tweet_created_at.isoformat()}" if tweets else "N/A",
            'tokens_used': total_tokens,
            'actual_cost': float(total_cost),
            'processing_time_ms': total_time_ms,
            'batch_count': len(batch_results),
            'batch_size': batch_size,
            'model': self.sdk.model
        }

        logger.info(f"[Task {task_id}] 批次分析完成, 总成本: ${total_cost:.4f}, "
                   f"总耗时: {total_time_ms}ms, 批次数: {len(batch_results)}")

        return merged_result

    def analyze_tweets(self, tweets: List[Tweet],
                      prompt_template: str = None,
                      batch_mode: bool = None,
                      batch_size: int = DEFAULT_BATCH_SIZE,
                      task_id: str = None,
                      save_prompt: bool = False) -> Dict:
        """
        分析推文（自动选择批次或一次性模式）

        Args:
            tweets: 推文列表
            prompt_template: Prompt 模板内容（可选，默认使用预设模板）
            batch_mode: 是否使用批次模式（None=自动判断，True=强制批次，False=强制一次性）
            batch_size: 批次大小（仅批次模式有效）
            task_id: 任务 ID
            save_prompt: 是否保存推送给AI前的原始内容（用于调试）

        Returns:
            Dict: 分析结果字典
        """
        if not tweets:
            raise ValueError("推文列表不能为空")

        # 加载 prompt 模板
        if prompt_template is None:
            prompt_template = self.load_prompt_template()

        # 自动判断模式
        if batch_mode is None:
            batch_mode = len(tweets) >= self.DEFAULT_BATCH_SIZE

        # 执行分析
        if batch_mode:
            return self.analyze_tweets_batch(
                tweets=tweets,
                prompt_template=prompt_template,
                batch_size=batch_size,
                task_id=task_id,
                save_prompt=save_prompt
            )
        else:
            return self.analyze_tweets_once(
                tweets=tweets,
                prompt_template=prompt_template,
                task_id=task_id,
                save_prompt=save_prompt
            )

    def _parse_ai_response(self, response_text: str) -> Dict:
        """
        解析 AI 返回的 JSON 结果

        Args:
            response_text: AI 返回的文本

        Returns:
            Dict: 解析后的结果字典

        Raises:
            ValueError: JSON 解析失败
        """
        # 尝试提取 JSON 部分（AI 可能返回额外的文本）
        try:
            # 直接解析
            return json.loads(response_text)
        except json.JSONDecodeError:
            # 尝试提取 {} 之间的内容
            import re
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.error(f"无法解析 AI 响应为 JSON: {response_text[:200]}")
            raise ValueError(f"AI 返回的结果不是有效的 JSON 格式")

    def _merge_batch_results(self, batch_results: List[Dict]) -> Dict:
        """
        合并多个批次的分析结果

        Args:
            batch_results: 批次结果列表

        Returns:
            Dict: 合并后的结果
        """
        if not batch_results:
            return {}

        if len(batch_results) == 1:
            return batch_results[0]

        # 合并情绪统计
        total_bullish = sum(r.get('sentiment', {}).get('bullish', 0) for r in batch_results)
        total_bearish = sum(r.get('sentiment', {}).get('bearish', 0) for r in batch_results)
        total_neutral = sum(r.get('sentiment', {}).get('neutral', 0) for r in batch_results)
        total_tweets = total_bullish + total_bearish + total_neutral

        merged_sentiment = {
            'bullish': total_bullish,
            'bearish': total_bearish,
            'neutral': total_neutral,
            'bullish_percentage': round(total_bullish / total_tweets * 100, 2) if total_tweets > 0 else 0,
            'bearish_percentage': round(total_bearish / total_tweets * 100, 2) if total_tweets > 0 else 0,
            'neutral_percentage': round(total_neutral / total_tweets * 100, 2) if total_tweets > 0 else 0,
        }

        # 合并关键话题（去重并重新统计）
        topic_counts = {}
        for result in batch_results:
            for topic in result.get('key_topics', []):
                topic_name = topic['topic']
                if topic_name in topic_counts:
                    topic_counts[topic_name]['count'] += topic['count']
                else:
                    topic_counts[topic_name] = {
                        'topic': topic_name,
                        'count': topic['count'],
                        'sentiment': topic.get('sentiment', 'neutral')
                    }

        merged_topics = sorted(topic_counts.values(), key=lambda x: x['count'], reverse=True)[:10]

        # 合并重要推文（按互动量排序，取前 10）
        all_important_tweets = []
        for result in batch_results:
            all_important_tweets.extend(result.get('important_tweets', []))

        merged_important_tweets = sorted(
            all_important_tweets,
            key=lambda x: x.get('engagement', 0),
            reverse=True
        )[:10]

        # 合并市场总结（拼接所有批次的总结）
        market_summaries = [r.get('market_summary', '') for r in batch_results if r.get('market_summary')]
        merged_summary = ' '.join(market_summaries) if market_summaries else "多批次分析完成"

        return {
            'sentiment': merged_sentiment,
            'key_topics': merged_topics,
            'important_tweets': merged_important_tweets,
            'market_summary': merged_summary,
            'analysis_metadata': {}  # 会在调用方更新
        }

    def _save_prompt_for_debug(self, task_id: str, prompt_template: str,
                               tweets_text: str, final_prompt: str):
        """
        保存推送给AI前的原始内容（用于调试）

        Args:
            task_id: 任务ID
            prompt_template: 提示词模板
            tweets_text: 格式化后的推文内容
            final_prompt: 最终发送给AI的完整prompt
        """
        try:
            import os
            from pathlib import Path

            # 创建debug目录
            debug_dir = Path(settings.BASE_DIR) / 'debug_prompts'
            debug_dir.mkdir(exist_ok=True)

            # 生成文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"prompt_{task_id}_{timestamp}.txt"
            filepath = debug_dir / filename

            # 构建保存内容
            content = []
            content.append("=" * 80)
            content.append(f"AI 调试信息 - Task: {task_id}")
            content.append(f"保存时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            content.append("=" * 80)
            content.append("")

            content.append("【1. 提示词模板】")
            content.append("-" * 80)
            content.append(prompt_template)
            content.append("")

            content.append("【2. 推文原文内容】")
            content.append("-" * 80)
            content.append(tweets_text)
            content.append("")

            content.append("【3. 最终发送给AI的完整Prompt】")
            content.append("-" * 80)
            content.append(final_prompt)
            content.append("")

            content.append("=" * 80)
            content.append("调试信息结束")
            content.append("=" * 80)

            # 写入文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))

            logger.info(f"[Task {task_id}] ✅ 调试信息已保存到: {filepath}")

        except Exception as e:
            logger.error(f"[Task {task_id}] ❌ 保存调试信息失败: {e}", exc_info=True)
