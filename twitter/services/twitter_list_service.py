import logging
from datetime import datetime, timezone
from typing import List, Dict, Iterator, Optional
from django.conf import settings
from django.db import transaction

from twitter.models import TwitterList, Tweet
from twitter.sdk.twitter_sdk import TwitterSDK, ValidationError as TwitterValidationError
from twitter.sdk.rate_limiter import initialize_default_limiters


logger = logging.getLogger(__name__)


class TwitterListService:
    """
    Twitter List 推文获取服务

    提供从 Twitter List 获取推文并存储到数据库的核心功能。
    """

    def __init__(self, twitter_list: TwitterList):
        """
        初始化服务

        Args:
            twitter_list: TwitterList 模型实例
        """
        self.twitter_list = twitter_list
        self.twitter_sdk = TwitterSDK()

        # 确保限流器已初始化
        initialize_default_limiters()

        logger.info(f"Initialized TwitterListService for list {twitter_list.list_id}")

    def get_tweets_in_range(self, start_time: datetime, end_time: datetime,
                           batch_size: int = 500) -> Iterator[List[Tweet]]:
        """
        获取指定时间范围内的推文（生成器）

        Args:
            start_time: 开始时间（timezone-aware）
            end_time: 结束时间（timezone-aware）
            batch_size: 每批获取的推文数量（50-1000）

        Yields:
            List[Tweet]: 推文对象列表（每批）

        Raises:
            TwitterValidationError: 参数验证失败
            TwitterAPIError: API 调用失败
        """
        # 确保时间带有时区信息
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)

        logger.info(f"Fetching tweets for list {self.twitter_list.list_id} "
                   f"from {start_time} to {end_time}, batch_size={batch_size}")

        total_fetched = 0
        batch_count = 0

        try:
            # 使用 Twitter SDK 获取推文（生成器模式）
            for tweet_batch_data in self.twitter_sdk.get_list_tweets(
                self.twitter_list.list_id,
                start_time,
                end_time,
                batch_size
            ):
                batch_count += 1
                batch_size_actual = len(tweet_batch_data)
                total_fetched += batch_size_actual

                logger.debug(f"Processing batch {batch_count}: {batch_size_actual} tweets")

                # 转换为 Tweet 对象
                tweet_objects = self._convert_to_tweet_objects(tweet_batch_data)

                if tweet_objects:
                    yield tweet_objects

            logger.info(f"Completed fetching tweets for list {self.twitter_list.list_id}: "
                       f"{total_fetched} tweets in {batch_count} batches")

        except TwitterValidationError as e:
            logger.error(f"Validation error fetching tweets: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching tweets: {e}")
            raise

    def save_tweets_to_db(self, tweets: List[Tweet]) -> Dict[str, int]:
        """
        批量保存推文到数据库（带去重）

        Args:
            tweets: Tweet 对象列表

        Returns:
            Dict[str, int]: 统计信息 {
                'total': 总数,
                'created': 新创建数,
                'duplicates': 重复数
            }
        """
        if not tweets:
            return {'total': 0, 'created': 0, 'duplicates': 0}

        total = len(tweets)
        logger.debug(f"Saving {total} tweets to database")

        try:
            with transaction.atomic():
                # 使用 bulk_create 批量插入，ignore_conflicts=True 自动忽略重复
                Tweet.objects.bulk_create(tweets, ignore_conflicts=True)

                # 查询实际创建的数量
                tweet_ids = [tweet.tweet_id for tweet in tweets]
                created_count = Tweet.objects.filter(tweet_id__in=tweet_ids).count()
                duplicates = total - created_count

                logger.info(f"Saved tweets: {created_count} created, {duplicates} duplicates")

                return {
                    'total': total,
                    'created': created_count,
                    'duplicates': duplicates
                }

        except Exception as e:
            logger.error(f"Error saving tweets to database: {e}")
            raise

    def collect_and_save_tweets(self, start_time: datetime, end_time: datetime,
                                batch_size: int = 500, dry_run: bool = False) -> Dict[str, any]:
        """
        获取并保存推文（完整流程）

        Args:
            start_time: 开始时间（timezone-aware）
            end_time: 结束时间（timezone-aware）
            batch_size: 批次大小（50-1000）
            dry_run: 是否试运行（不保存到数据库）

        Returns:
            Dict: 执行摘要 {
                'total_fetched': 总获取数,
                'total_saved': 总保存数,
                'total_duplicates': 总重复数,
                'batches_processed': 处理批次数,
                'dry_run': 是否试运行
            }
        """
        logger.info(f"Starting collection for list {self.twitter_list.list_id}, dry_run={dry_run}")

        total_fetched = 0
        total_saved = 0
        total_duplicates = 0
        batches_processed = 0

        try:
            for tweet_batch in self.get_tweets_in_range(start_time, end_time, batch_size):
                batches_processed += 1
                batch_size_actual = len(tweet_batch)
                total_fetched += batch_size_actual

                if not dry_run:
                    # 保存到数据库
                    save_result = self.save_tweets_to_db(tweet_batch)
                    total_saved += save_result['created']
                    total_duplicates += save_result['duplicates']
                else:
                    # 试运行模式：只统计，不保存
                    logger.debug(f"Dry-run: Would save {batch_size_actual} tweets")

            summary = {
                'total_fetched': total_fetched,
                'total_saved': total_saved if not dry_run else 0,
                'total_duplicates': total_duplicates if not dry_run else 0,
                'batches_processed': batches_processed,
                'dry_run': dry_run,
                'list_id': self.twitter_list.list_id,
                'list_name': self.twitter_list.name
            }

            logger.info(f"Collection completed: {summary}")
            return summary

        except Exception as e:
            logger.error(f"Error during collection: {e}")
            raise

    def _convert_to_tweet_objects(self, tweet_data_list: List[Dict]) -> List[Tweet]:
        """
        将 API 返回的推文数据转换为 Tweet 模型对象

        Args:
            tweet_data_list: 推文数据字典列表

        Returns:
            List[Tweet]: Tweet 对象列表
        """
        tweet_objects = []

        for tweet_data in tweet_data_list:
            try:
                # 解析推文发布时间
                tweet_created_at = self._parse_tweet_timestamp(tweet_data.get('tweet_created_at'))

                if not tweet_created_at:
                    logger.warning(f"Skipping tweet {tweet_data.get('tweet_id')}: invalid timestamp")
                    continue

                # 创建 Tweet 对象
                tweet = Tweet(
                    tweet_id=tweet_data.get('tweet_id', ''),
                    twitter_list=self.twitter_list,
                    user_id=tweet_data.get('user_id', ''),
                    screen_name=tweet_data.get('screen_name', 'unknown'),
                    user_name=tweet_data.get('user_name', ''),
                    content=tweet_data.get('content', ''),
                    tweet_created_at=tweet_created_at,
                    retweet_count=tweet_data.get('retweet_count', 0),
                    favorite_count=tweet_data.get('favorite_count', 0),
                    reply_count=tweet_data.get('reply_count', 0)
                )

                tweet_objects.append(tweet)

            except Exception as e:
                logger.warning(f"Error converting tweet data: {e}, data: {tweet_data}")
                continue

        return tweet_objects

    def _parse_tweet_timestamp(self, created_at_str: str) -> Optional[datetime]:
        """
        解析推文时间戳字符串

        Args:
            created_at_str: Twitter 时间格式字符串 (e.g., "Wed Oct 05 20:31:00 +0000 2022")

        Returns:
            datetime: 时区感知的 datetime 对象，解析失败返回 None
        """
        if not created_at_str:
            return None

        try:
            # Twitter 时间格式: "Wed Oct 05 20:31:00 +0000 2022"
            parsed_time = datetime.strptime(created_at_str, "%a %b %d %H:%M:%S %z %Y")
            return parsed_time
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse tweet timestamp '{created_at_str}': {e}")
            return None

    def get_statistics(self) -> Dict[str, any]:
        """
        获取当前 List 的统计信息

        Returns:
            Dict: 统计数据 {
                'total_tweets': 总推文数,
                'unique_users': 唯一用户数,
                'latest_tweet_time': 最新推文时间,
                'oldest_tweet_time': 最早推文时间
            }
        """
        tweets_queryset = Tweet.objects.filter(twitter_list=self.twitter_list)

        total_tweets = tweets_queryset.count()
        unique_users = tweets_queryset.values('user_id').distinct().count()

        latest_tweet = tweets_queryset.order_by('-tweet_created_at').first()
        oldest_tweet = tweets_queryset.order_by('tweet_created_at').first()

        return {
            'total_tweets': total_tweets,
            'unique_users': unique_users,
            'latest_tweet_time': latest_tweet.tweet_created_at if latest_tweet else None,
            'oldest_tweet_time': oldest_tweet.tweet_created_at if oldest_tweet else None,
            'list_id': self.twitter_list.list_id,
            'list_name': self.twitter_list.name
        }

    def close(self):
        """关闭 SDK 会话"""
        if hasattr(self, 'twitter_sdk'):
            self.twitter_sdk.close()
