import time
import logging
import threading
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum


logger = logging.getLogger(__name__)


class RateLimitStrategy(Enum):
    """限流策略枚举"""
    TOKEN_BUCKET = "token_bucket"      # 令牌桶算法
    SLIDING_WINDOW = "sliding_window"  # 滑动窗口算法
    FIXED_WINDOW = "fixed_window"      # 固定窗口算法


@dataclass
class RateLimitConfig:
    """限流配置"""
    name: str                          # 限流器名称
    max_requests: int                  # 最大请求数
    time_window: int                   # 时间窗口（秒）
    strategy: RateLimitStrategy        # 限流策略
    burst_size: Optional[int] = None   # 突发大小（用于令牌桶）
    block_on_limit: bool = True        # 达到限制时是否阻塞

    def __post_init__(self):
        if self.burst_size is None:
            self.burst_size = self.max_requests


class RateLimiter:
    """通用限流器"""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.lock = threading.RLock()

        # 根据策略初始化状态
        if config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            self.tokens = config.burst_size
            self.last_refill = time.time()
        elif config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            self.requests = deque()
        elif config.strategy == RateLimitStrategy.FIXED_WINDOW:
            self.window_start = time.time()
            self.window_requests = 0

        logger.info(f"Initialized rate limiter '{config.name}' with strategy {config.strategy.value}")

    def acquire(self, tokens: int = 1) -> bool:
        """
        尝试获取令牌

        Args:
            tokens: 需要的令牌数量

        Returns:
            bool: 是否成功获取令牌
        """
        with self.lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                return self._acquire_token_bucket(tokens)
            elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                return self._acquire_sliding_window(tokens)
            elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                return self._acquire_fixed_window(tokens)

        return False

    def wait_and_acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        """
        等待并获取令牌

        Args:
            tokens: 需要的令牌数量
            timeout: 超时时间（秒），None表示无限等待

        Returns:
            bool: 是否成功获取令牌
        """
        start_time = time.time()

        while True:
            if self.acquire(tokens):
                return True

            # 检查超时
            if timeout and (time.time() - start_time) >= timeout:
                logger.warning(f"Rate limiter '{self.config.name}' timeout after {timeout}s")
                return False

            # 计算等待时间
            wait_time = self._calculate_wait_time()
            if wait_time > 0:
                time.sleep(min(wait_time, 1.0))  # 最多等待1秒再检查
            else:
                time.sleep(0.1)  # 短暂等待后重试

    def get_current_limit_info(self) -> Dict[str, Any]:
        """获取当前限流状态信息"""
        with self.lock:
            if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
                self._refill_tokens()
                return {
                    "available_tokens": self.tokens,
                    "max_tokens": self.config.burst_size,
                    "refill_rate": self.config.max_requests / self.config.time_window
                }
            elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
                self._cleanup_old_requests()
                return {
                    "current_requests": len(self.requests),
                    "max_requests": self.config.max_requests,
                    "time_window": self.config.time_window
                }
            elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
                current_time = time.time()
                if current_time - self.window_start >= self.config.time_window:
                    self.window_start = current_time
                    self.window_requests = 0

                return {
                    "current_requests": self.window_requests,
                    "max_requests": self.config.max_requests,
                    "window_remaining": self.config.time_window - (current_time - self.window_start)
                }

        return {}

    def _acquire_token_bucket(self, tokens: int) -> bool:
        """令牌桶算法实现"""
        self._refill_tokens()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _acquire_sliding_window(self, tokens: int) -> bool:
        """滑动窗口算法实现"""
        self._cleanup_old_requests()

        if len(self.requests) + tokens <= self.config.max_requests:
            for _ in range(tokens):
                self.requests.append(time.time())
            return True
        return False

    def _acquire_fixed_window(self, tokens: int) -> bool:
        """固定窗口算法实现"""
        current_time = time.time()

        # 检查是否需要重置窗口
        if current_time - self.window_start >= self.config.time_window:
            self.window_start = current_time
            self.window_requests = 0

        if self.window_requests + tokens <= self.config.max_requests:
            self.window_requests += tokens
            return True
        return False

    def _refill_tokens(self):
        """重新填充令牌（令牌桶算法）"""
        current_time = time.time()
        time_passed = current_time - self.last_refill

        # 计算应该添加的令牌数
        tokens_to_add = int(time_passed * self.config.max_requests / self.config.time_window)

        if tokens_to_add > 0:
            self.tokens = min(self.config.burst_size, self.tokens + tokens_to_add)
            self.last_refill = current_time

    def _cleanup_old_requests(self):
        """清理过期请求（滑动窗口算法）"""
        current_time = time.time()
        cutoff_time = current_time - self.config.time_window

        while self.requests and self.requests[0] < cutoff_time:
            self.requests.popleft()

    def _calculate_wait_time(self) -> float:
        """计算需要等待的时间"""
        if self.config.strategy == RateLimitStrategy.TOKEN_BUCKET:
            # 令牌桶：计算下一个令牌生成时间
            return self.config.time_window / self.config.max_requests
        elif self.config.strategy == RateLimitStrategy.SLIDING_WINDOW:
            # 滑动窗口：计算最老请求的过期时间
            if self.requests:
                oldest_request = self.requests[0]
                return max(0, oldest_request + self.config.time_window - time.time())
        elif self.config.strategy == RateLimitStrategy.FIXED_WINDOW:
            # 固定窗口：计算窗口重置时间
            return max(0, self.window_start + self.config.time_window - time.time())

        return 1.0  # 默认等待1秒


class RateLimiterManager:
    """限流器管理器"""

    def __init__(self):
        self.limiters: Dict[str, RateLimiter] = {}
        self.lock = threading.RLock()

    def register_limiter(self, config: RateLimitConfig) -> RateLimiter:
        """注册限流器"""
        with self.lock:
            limiter = RateLimiter(config)
            self.limiters[config.name] = limiter
            logger.info(f"Registered rate limiter: {config.name}")
            return limiter

    def get_limiter(self, name: str) -> Optional[RateLimiter]:
        """获取限流器"""
        return self.limiters.get(name)

    def acquire(self, limiter_name: str, tokens: int = 1) -> bool:
        """从指定限流器获取令牌"""
        limiter = self.get_limiter(limiter_name)
        if limiter:
            return limiter.acquire(tokens)
        return True  # 如果限流器不存在，允许通过

    def wait_and_acquire(self, limiter_name: str, tokens: int = 1,
                        timeout: Optional[float] = None) -> bool:
        """从指定限流器等待并获取令牌"""
        limiter = self.get_limiter(limiter_name)
        if limiter:
            return limiter.wait_and_acquire(tokens, timeout)
        return True

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有限流器状态"""
        status = {}
        for name, limiter in self.limiters.items():
            status[name] = limiter.get_current_limit_info()
        return status


# 全局限流器管理器实例
rate_limiter_manager = RateLimiterManager()


def rate_limit(limiter_name: str, tokens: int = 1, timeout: Optional[float] = None):
    """
    限流装饰器

    Args:
        limiter_name: 限流器名称
        tokens: 需要的令牌数
        timeout: 超时时间
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            # 尝试获取令牌
            if not rate_limiter_manager.wait_and_acquire(limiter_name, tokens, timeout):
                raise Exception(f"Rate limit exceeded for {limiter_name}")

            # 执行原函数
            return func(*args, **kwargs)

        return wrapper
    return decorator


# 预定义的限流配置（根据 Django settings 配置）
def get_twitter_rate_limit_config():
    """获取 Twitter API 限流配置"""
    from django.conf import settings

    return RateLimitConfig(
        name='twitter_api',
        max_requests=getattr(settings, 'TWITTER_RATE_LIMIT_PER_MINUTE', 50),
        time_window=60,  # 1分钟
        strategy=RateLimitStrategy.SLIDING_WINDOW,
        block_on_limit=True
    )


def get_deepseek_rate_limit_config():
    """获取 DeepSeek API 限流配置"""
    return RateLimitConfig(
        name='deepseek_api',
        max_requests=50,          # DeepSeek API 限制：50请求/分钟
        time_window=60,           # 1分钟
        strategy=RateLimitStrategy.TOKEN_BUCKET,
        burst_size=10,            # 允许突发10个请求
        block_on_limit=True
    )


def initialize_default_limiters():
    """初始化默认限流器"""
    rate_limiter_manager.register_limiter(get_twitter_rate_limit_config())
    rate_limiter_manager.register_limiter(get_deepseek_rate_limit_config())
    logger.info("Default rate limiters initialized")


# 在模块加载时初始化默认限流器
# 注意：由于 Django 的加载顺序，这里不立即初始化，而是在首次使用时初始化
