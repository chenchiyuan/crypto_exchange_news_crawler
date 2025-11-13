import time
import logging
import random
import functools
from typing import Callable, Type, Tuple, Optional, Any, List
from dataclasses import dataclass
from enum import Enum
import threading


logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """重试策略枚举"""
    FIXED_DELAY = "fixed_delay"          # 固定延迟
    EXPONENTIAL_BACKOFF = "exponential"  # 指数退避
    LINEAR_BACKOFF = "linear"           # 线性退避
    JITTERED_EXPONENTIAL = "jittered"   # 带抖动的指数退避


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3                           # 最大重试次数
    base_delay: float = 1.0                        # 基础延迟时间（秒）
    max_delay: float = 60.0                        # 最大延迟时间（秒）
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    multiplier: float = 2.0                        # 延迟倍数（用于指数/线性退避）
    jitter_range: Tuple[float, float] = (0.8, 1.2) # 抖动范围
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    non_retryable_exceptions: Tuple[Type[Exception], ...] = ()
    retry_condition: Optional[Callable[[Exception], bool]] = None

    def __post_init__(self):
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.base_delay < 0:
            raise ValueError("base_delay must be non-negative")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")


class RetryState:
    """重试状态跟踪"""

    def __init__(self, config: RetryConfig):
        self.config = config
        self.attempt_count = 0
        self.total_elapsed_time = 0.0
        self.last_exception: Optional[Exception] = None
        self.start_time = time.time()
        self.attempt_history: List[dict] = []

    def record_attempt(self, exception: Optional[Exception] = None,
                      execution_time: float = 0.0):
        """记录重试尝试"""
        self.attempt_count += 1
        self.last_exception = exception

        attempt_info = {
            'attempt': self.attempt_count,
            'timestamp': time.time(),
            'execution_time': execution_time,
            'exception': str(exception) if exception else None,
            'exception_type': type(exception).__name__ if exception else None
        }
        self.attempt_history.append(attempt_info)

    def should_retry(self, exception: Exception) -> bool:
        """判断是否应该重试"""
        # 检查是否超过最大重试次数
        if self.attempt_count >= self.config.max_attempts:
            return False

        # 检查非重试异常
        if isinstance(exception, self.config.non_retryable_exceptions):
            return False

        # 检查重试异常
        if not isinstance(exception, self.config.retryable_exceptions):
            return False

        # 自定义重试条件
        if self.config.retry_condition and not self.config.retry_condition(exception):
            return False

        return True

    def calculate_delay(self) -> float:
        """计算下次重试的延迟时间"""
        if self.config.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.config.base_delay

        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.base_delay * (self.config.multiplier ** (self.attempt_count - 1))

        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.base_delay + (self.config.multiplier * (self.attempt_count - 1))

        elif self.config.strategy == RetryStrategy.JITTERED_EXPONENTIAL:
            base_delay = self.config.base_delay * (self.config.multiplier ** (self.attempt_count - 1))
            jitter_min, jitter_max = self.config.jitter_range
            jitter = random.uniform(jitter_min, jitter_max)
            delay = base_delay * jitter

        else:
            delay = self.config.base_delay

        # 限制在最大延迟时间内
        return min(delay, self.config.max_delay)

    def get_summary(self) -> dict:
        """获取重试统计摘要"""
        return {
            'total_attempts': self.attempt_count,
            'total_elapsed_time': time.time() - self.start_time,
            'last_exception': str(self.last_exception) if self.last_exception else None,
            'success': self.last_exception is None,
            'attempt_history': self.attempt_history
        }


class RetryManager:
    """重试管理器"""

    def __init__(self):
        self.active_retries: dict = {}
        self.retry_stats: dict = {}
        self.lock = threading.RLock()

    def execute_with_retry(self, func: Callable, config: RetryConfig,
                          *args, **kwargs) -> Any:
        """
        使用重试机制执行函数

        Args:
            func: 要执行的函数
            config: 重试配置
            *args, **kwargs: 函数参数

        Returns:
            函数执行结果

        Raises:
            最后一次尝试的异常
        """
        retry_id = f"{func.__name__}_{id(threading.current_thread())}"
        state = RetryState(config)

        with self.lock:
            self.active_retries[retry_id] = state

        try:
            while True:
                execution_start = time.time()

                try:
                    # 执行函数
                    result = func(*args, **kwargs)

                    # 成功执行，记录并返回结果
                    execution_time = time.time() - execution_start
                    state.record_attempt(execution_time=execution_time)

                    logger.info(f"Function {func.__name__} succeeded on attempt {state.attempt_count}")
                    return result

                except Exception as e:
                    execution_time = time.time() - execution_start
                    state.record_attempt(e, execution_time)

                    logger.warning(
                        f"Function {func.__name__} failed on attempt {state.attempt_count}: {e}"
                    )

                    # 判断是否应该重试
                    if not state.should_retry(e):
                        logger.error(
                            f"Function {func.__name__} exhausted retries after {state.attempt_count} attempts"
                        )
                        raise e

                    # 计算延迟时间并等待
                    delay = state.calculate_delay()
                    logger.info(f"Retrying {func.__name__} in {delay:.2f} seconds...")
                    time.sleep(delay)

        finally:
            # 清理活跃重试记录
            with self.lock:
                self.active_retries.pop(retry_id, None)
                # 记录统计信息
                func_name = func.__name__
                if func_name not in self.retry_stats:
                    self.retry_stats[func_name] = {'total_calls': 0, 'total_retries': 0, 'success_rate': 0.0}

                stats = self.retry_stats[func_name]
                stats['total_calls'] += 1
                stats['total_retries'] += state.attempt_count - 1
                stats['success_rate'] = (stats['total_calls'] -
                                       sum(1 for s in self.retry_stats[func_name].get('failures', []))) / stats['total_calls']

    def get_active_retries(self) -> dict:
        """获取当前活跃的重试操作"""
        with self.lock:
            return {retry_id: state.get_summary() for retry_id, state in self.active_retries.items()}

    def get_retry_statistics(self) -> dict:
        """获取重试统计信息"""
        with self.lock:
            return self.retry_stats.copy()

    def clear_statistics(self):
        """清空统计信息"""
        with self.lock:
            self.retry_stats.clear()


# 全局重试管理器实例
retry_manager = RetryManager()


def retry(max_attempts: int = 3,
          base_delay: float = 1.0,
          max_delay: float = 60.0,
          strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
          multiplier: float = 2.0,
          jitter_range: Tuple[float, float] = (0.8, 1.2),
          retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
          non_retryable_exceptions: Tuple[Type[Exception], ...] = (),
          retry_condition: Optional[Callable[[Exception], bool]] = None):
    """
    重试装饰器

    Args:
        max_attempts: 最大重试次数
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        strategy: 重试策略
        multiplier: 延迟倍数
        jitter_range: 抖动范围
        retryable_exceptions: 可重试的异常类型
        non_retryable_exceptions: 不可重试的异常类型
        retry_condition: 自定义重试条件函数
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        max_delay=max_delay,
        strategy=strategy,
        multiplier=multiplier,
        jitter_range=jitter_range,
        retryable_exceptions=retryable_exceptions,
        non_retryable_exceptions=non_retryable_exceptions,
        retry_condition=retry_condition
    )

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return retry_manager.execute_with_retry(func, config, *args, **kwargs)

        # 添加重试配置信息到函数
        wrapper.retry_config = config
        return wrapper

    return decorator


# 预定义的重试配置（稍后在创建 Twitter 和 DeepSeek SDK 后添加具体的异常类）
def network_retry(max_attempts: int = 3):
    """网络操作重试装饰器"""
    import requests

    return retry(
        max_attempts=max_attempts,
        base_delay=2.0,
        max_delay=30.0,
        strategy=RetryStrategy.JITTERED_EXPONENTIAL,
        multiplier=2.0,
        retryable_exceptions=(
            requests.RequestException,
            ConnectionError,
            TimeoutError,
            OSError
        ),
        non_retryable_exceptions=(
            requests.exceptions.InvalidURL,
            requests.exceptions.MissingSchema
        )
    )


def database_retry(max_attempts: int = 2):
    """数据库操作重试装饰器"""
    from django.db import OperationalError, IntegrityError

    return retry(
        max_attempts=max_attempts,
        base_delay=0.5,
        max_delay=5.0,
        strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
        multiplier=2.0,
        retryable_exceptions=(OperationalError,),
        non_retryable_exceptions=(IntegrityError, ValueError)
    )
