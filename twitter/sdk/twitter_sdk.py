import requests
import time
import logging
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Iterator
from django.conf import settings

from .rate_limiter import rate_limiter_manager
from .retry_manager import retry, RetryStrategy


logger = logging.getLogger(__name__)


class TwitterAPIError(Exception):
    def __init__(self, message: str, status_code: int = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(ValueError):
    pass


class RateLimitError(TwitterAPIError):
    def __init__(self, message: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message, 429)


class ListNotFoundError(TwitterAPIError):
    def __init__(self, list_id: str):
        super().__init__(f"Twitter List not found: {list_id}", 404)


class ListAccessDeniedError(TwitterAPIError):
    def __init__(self, list_id: str):
        super().__init__(f"Access denied to Twitter List: {list_id}", 403)


class TwitterAPIQuotaExceededError(TwitterAPIError):
    def __init__(self, message: str, reset_time: int = None):
        self.reset_time = reset_time
        super().__init__(message, 429)


# API重试装饰器（Twitter专用）
def twitter_api_retry(max_attempts: int = 3):
    """Twitter API调用重试装饰器"""
    return retry(
        max_attempts=max_attempts,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategy.JITTERED_EXPONENTIAL,
        multiplier=2.0,
        retryable_exceptions=(
            TwitterAPIError, RateLimitError,
            ConnectionError, TimeoutError
        ),
        non_retryable_exceptions=(ValueError, TypeError),
        retry_condition=lambda e: not (hasattr(e, 'status_code') and e.status_code is not None and 400 <= e.status_code < 500)
    )


class TwitterSDK:
    def __init__(self, api_key: str = None, base_url: str = None, timeout: int = 30,
                 retry_count: int = 3, retry_delay: float = 1.0):
        self.api_key = api_key or settings.TWITTER_API_KEY
        self.base_url = base_url or settings.TWITTER_API_BASE_URL
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay

        if not self.api_key:
            raise ValueError("Twitter API key is required")

        self.session = requests.Session()
        self.session.headers.update({
            'apikey': self.api_key,
            'User-Agent': 'CryptoExchangeNewsC rawler/1.0'
        })

    @twitter_api_retry(max_attempts=3)
    def _make_request(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # 使用限流器控制API调用频率
        if not rate_limiter_manager.wait_and_acquire('twitter_api', timeout=30):
            raise TwitterAPIError("Twitter API rate limit exceeded, timeout waiting for quota")

        try:
            logger.debug(f"Making request to {url}")

            response = self.session.get(url, params=params, timeout=self.timeout)

            if response.status_code == 200:
                try:
                    data = response.json()
                    return data
                except ValueError as e:
                    raise TwitterAPIError(f"Invalid JSON response: {e}")

            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise RateLimitError(
                    f"Rate limit exceeded, retry after {retry_after} seconds",
                    retry_after
                )
            elif response.status_code == 404:
                raise TwitterAPIError("Resource not found", 404)
            elif response.status_code == 403:
                raise TwitterAPIError("Access forbidden", 403)
            else:
                response.raise_for_status()

        except requests.RequestException as e:
            raise TwitterAPIError(f"Request failed: {e}")

        raise TwitterAPIError("Unexpected error in request")

    def get_list_tweets(self, list_id: str, start_time: datetime, end_time: datetime,
                       batch_size: int = 200) -> Iterator[List[Dict[str, Any]]]:
        """
        Get tweets from a Twitter List within a specified time range

        Args:
            list_id: Twitter List ID
            start_time: Start time for tweet filtering (timezone-aware)
            end_time: End time for tweet filtering (timezone-aware)
            batch_size: Number of tweets per batch (50-1000, default 200)

        Yields:
            List[Dict[str, Any]]: Batches of tweet data

        Raises:
            ListNotFoundError: If the list doesn't exist
            ListAccessDeniedError: If access to the list is denied
            TwitterAPIQuotaExceededError: If API quota is exceeded
            ValidationError: If parameters are invalid
            TimeoutError: If API call times out
        """

        # 参数验证
        self._validate_list_tweets_params(list_id, start_time, end_time, batch_size)

        # 转换时间格式
        start_timestamp = int(start_time.timestamp())
        end_timestamp = int(end_time.timestamp())

        try:
            cursor = None
            processed_tweets = set()  # 用于去重
            total_fetched = 0
            page_count = 0

            while True:
                page_count += 1

                try:
                    # 获取一批推文数据
                    actual_count = min(batch_size, 1000)  # API限制最大1000
                    batch_data = self._fetch_list_tweets_batch(
                        list_id, cursor, actual_count
                    )

                    tweets = batch_data.get('tweets', [])
                    cursor = batch_data.get('next_cursor')

                    if not tweets:
                        logger.info(f"No more tweets found for list {list_id}")
                        break

                    # 过滤和去重推文
                    filtered_tweets = []
                    should_stop = False
                    has_tweet_before_start_time = False

                    for tweet in tweets:
                        normalized_tweet = self._normalize_tweet_data(tweet)
                        tweet_id = normalized_tweet.get('tweet_id')
                        tweet_time = self._parse_tweet_timestamp(normalized_tweet.get('tweet_created_at'))

                        # 检查是否有推文早于开始时间
                        if tweet_time and tweet_time < start_timestamp:
                            has_tweet_before_start_time = True

                        # 过滤时间范围内的推文
                        if tweet_id not in processed_tweets and tweet_time:
                            if start_timestamp <= tweet_time <= end_timestamp:
                                processed_tweets.add(tweet_id)
                                filtered_tweets.append(normalized_tweet)

                    # 判断是否需要停止分页
                    if has_tweet_before_start_time:
                        should_stop = True
                        logger.info(f"Found tweet older than start_time, stopping pagination for list {list_id}")

                    if filtered_tweets:
                        # 按时间倒序排列
                        filtered_tweets.sort(
                            key=lambda x: self._parse_tweet_timestamp(x.get('tweet_created_at', '')),
                            reverse=True
                        )
                        total_fetched += len(filtered_tweets)
                        logger.debug(f"Yielding {len(filtered_tweets)} tweets for list {list_id}")
                        yield filtered_tweets

                    # 检查提前停止条件
                    if should_stop:
                        logger.info(f"Stopping pagination early for list {list_id}, total processed: {total_fetched}")
                        break

                    # 检查是否还有更多数据
                    if not cursor:
                        logger.info(f"Reached end of list {list_id}, total processed: {total_fetched}")
                        break

                    # 避免过于频繁的API调用
                    time.sleep(0.1)

                except TwitterAPIQuotaExceededError as e:
                    logger.warning(f"API quota exceeded for list {list_id}, attempting retry")
                    self._handle_quota_exceeded(e)
                    continue
                except TimeoutError:
                    logger.warning(f"Timeout fetching tweets for list {list_id}, retrying once")
                    try:
                        batch_data = self._fetch_list_tweets_batch(
                            list_id, cursor, min(batch_size, 500)
                        )
                    except Exception as retry_error:
                        logger.error(f"Retry failed for list {list_id}: {retry_error}")
                        raise TimeoutError(f"API call timeout for list {list_id}")

        except ListNotFoundError:
            raise
        except ListAccessDeniedError:
            raise
        except TwitterAPIQuotaExceededError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching tweets for list {list_id}: {e}")
            raise TwitterAPIError(f"Failed to fetch list tweets: {e}")

    def _validate_list_tweets_params(self, list_id: str, start_time: datetime,
                                   end_time: datetime, batch_size: int):
        """验证get_list_tweets参数"""
        # 验证list_id
        if not list_id or not isinstance(list_id, str):
            raise ValidationError("list_id must be a non-empty string")

        list_id = list_id.strip()
        if not list_id or len(list_id) > 50:
            raise ValidationError("list_id length must be between 1-50 characters")

        if not list_id.isdigit():
            raise ValidationError("list_id must contain only digits")

        # 验证时间参数
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            raise ValidationError("start_time and end_time must be datetime objects")

        if start_time.tzinfo is None or end_time.tzinfo is None:
            raise ValidationError("start_time and end_time must be timezone-aware")

        if start_time >= end_time:
            raise ValidationError("start_time must be earlier than end_time")

        # 检查时间范围限制（7天）
        time_diff = end_time - start_time
        if time_diff.days > 7:
            raise ValidationError("Time range cannot exceed 7 days")

        # 验证batch_size
        if not isinstance(batch_size, int) or batch_size < 50 or batch_size > 1000:
            raise ValidationError("batch_size must be an integer between 50-1000")

    def _fetch_list_tweets_batch(self, list_id: str, cursor: str = None,
                               count: int = 500) -> Dict[str, Any]:
        """获取List推文的单个批次"""

        try:
            variables = {
                "listId": list_id,
                "count": count,
                "includePromotedContent": False,
                "withQuickPromoteEligibilityTweetFields": True,
                "withVoice": True,
                "withV2Timeline": True
            }

            if cursor:
                variables["cursor"] = cursor

            params = {'variables': json.dumps(variables)}
            response_data = self._make_request('/graphql/ListLatestTweetsTimeline', params)

            tweets = []
            next_cursor = None

            instructions = response_data.get('data', {}).get('list', {}).get('tweets_timeline', {}).get('timeline', {}).get('instructions', [])

            for instruction in instructions:
                if instruction.get('type') == 'TimelineAddEntries':
                    for entry in instruction.get('entries', []):
                        entry_id = entry.get('entryId', '')

                        # 处理推文数据
                        if entry_id.startswith('tweet-'):
                            tweet_result = entry.get('content', {}).get('itemContent', {}).get('tweet_results', {}).get('result', {})
                            if tweet_result.get('__typename') == 'Tweet':
                                tweets.append(tweet_result)

                        # 处理分页游标
                        elif entry_id.startswith('cursor-bottom-'):
                            cursor_content = entry.get('content', {})
                            if cursor_content.get('cursorType') == 'Bottom':
                                next_cursor = cursor_content.get('value')

            return {
                'tweets': tweets,
                'next_cursor': next_cursor
            }

        except TwitterAPIError:
            raise
        except Exception as e:
            logger.error(f"Error fetching list tweets batch: {e}")
            raise TwitterAPIError(f"Failed to fetch list tweets batch: {e}")

    def _normalize_tweet_data(self, tweet_result: Dict[str, Any]) -> Dict[str, Any]:
        """标准化推文数据格式"""
        legacy = tweet_result.get('legacy', {})
        user_result = tweet_result.get('core', {}).get('user_results', {}).get('result', {})

        return {
            'tweet_id': legacy.get('id_str', ''),
            'content': legacy.get('full_text', ''),
            'tweet_created_at': legacy.get('created_at', ''),
            'retweet_count': legacy.get('retweet_count', 0),
            'favorite_count': legacy.get('favorite_count', 0),
            'reply_count': legacy.get('reply_count', 0),
            'quote_count': legacy.get('quote_count', 0),
            'user_id': user_result.get('rest_id', ''),
            'screen_name': user_result.get('legacy', {}).get('screen_name', ''),
            'user_name': user_result.get('legacy', {}).get('name', ''),
            'user_verified': user_result.get('legacy', {}).get('verified', False)
        }

    def _parse_tweet_timestamp(self, created_at: str) -> Optional[int]:
        """解析推文时间戳"""
        if not created_at:
            return None

        try:
            # Twitter时间格式: "Wed Oct 05 20:31:00 +0000 2022"
            import datetime as dt
            parsed_time = dt.datetime.strptime(created_at, "%a %b %d %H:%M:%S %z %Y")
            return int(parsed_time.timestamp())
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to parse tweet timestamp '{created_at}': {e}")
            return None

    def _handle_quota_exceeded(self, error: TwitterAPIQuotaExceededError):
        """处理API配额超限"""
        retry_count = 3
        base_wait = 60  # 基础等待时间60秒

        for attempt in range(retry_count):
            wait_time = base_wait * (2 ** attempt)  # 指数退避
            logger.warning(f"API quota exceeded, waiting {wait_time}s (attempt {attempt + 1}/{retry_count})")
            time.sleep(wait_time)

            try:
                # 简单的健康检查
                self._make_request('/1.1/help/configuration.json')
                logger.info("API quota appears to be restored")
                return
            except TwitterAPIError:
                if attempt == retry_count - 1:
                    raise error
                continue

        raise error

    def close(self):
        if hasattr(self, 'session'):
            self.session.close()
