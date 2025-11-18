import requests
import time
import json
import logging
import os
from decimal import Decimal
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from .rate_limiter import rate_limiter_manager
from .retry_manager import retry, RetryStrategy


logger = logging.getLogger(__name__)


class DeepSeekAPIError(Exception):
    """DeepSeek API调用异常"""
    def __init__(self, message: str, status_code: int = None, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class DeepSeekQuotaExceededError(DeepSeekAPIError):
    """DeepSeek配额超限异常"""
    def __init__(self, message: str, reset_time: int = None):
        self.reset_time = reset_time
        super().__init__(message, 429)


class DeepSeekTimeoutError(DeepSeekAPIError):
    """DeepSeek超时异常"""
    def __init__(self, message: str):
        super().__init__(message, 408)


class DeepSeekValidationError(ValueError):
    """DeepSeek参数验证异常"""
    pass


@dataclass
class DeepSeekResponse:
    """DeepSeek API响应数据"""
    content: str
    model: str
    tokens_used: int
    completion_tokens: int
    prompt_tokens: int
    cost_estimate: Decimal
    processing_time_ms: int
    request_id: str
    created_at: datetime


# DeepSeek API重试装饰器
def deepseek_api_retry(max_attempts: int = 3):
    """DeepSeek API调用重试装饰器"""
    return retry(
        max_attempts=max_attempts,
        base_delay=1.0,
        max_delay=30.0,
        strategy=RetryStrategy.JITTERED_EXPONENTIAL,
        multiplier=2.0,
        retryable_exceptions=(
            DeepSeekAPIError, DeepSeekQuotaExceededError, DeepSeekTimeoutError,
            ConnectionError, TimeoutError
        ),
        non_retryable_exceptions=(ValueError, TypeError),
        retry_condition=lambda e: not (hasattr(e, 'status_code') and e.status_code is not None and 400 <= e.status_code < 500)
    )


class DeepSeekSDK:
    """DeepSeek AI SDK封装"""

    # 定价表（每1K tokens）
    PRICING = {
        "deepseek-chat": {
            "input": Decimal("0.00014"),   # $0.14/1M tokens
            "output": Decimal("0.00028")   # $0.28/1M tokens
        }
    }

    def __init__(self, api_key: str = None, base_url: str = None,
                 model: str = None, timeout: int = 600, max_retries: int = 3):
        """
        初始化DeepSeek SDK

        Args:
            api_key: API密钥
            base_url: API基础URL
            model: 使用的模型名称
            timeout: 请求超时时间（秒）
            max_retries: 最大重试次数
        """
        self.api_key = api_key or getattr(settings, 'DEEPSEEK_API_KEY', None)
        self.base_url = base_url or getattr(settings, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com')
        self.model = model or getattr(settings, 'DEEPSEEK_MODEL', 'deepseek-chat')
        self.timeout = timeout
        self.max_retries = max_retries

        if not self.api_key:
            raise DeepSeekValidationError("DeepSeek API key is required")

        self.session = requests.Session()

        # 根据base_url判断使用哪种认证方式
        # 万界数据代理使用 apiKey header（自定义认证）
        # 官方DeepSeek API使用 Authorization: Bearer（标准认证）
        if 'wanjiedata.com' in self.base_url:
            # 万界数据代理认证方式
            self.session.headers.update({
                'apiKey': self.api_key,
                'Content-Type': 'application/json',
                'User-Agent': 'CryptoExchangeNewsCrawler-DeepSeek/1.0'
            })
            logger.debug("Using wanjiedata.com authentication (apiKey header)")
        else:
            # 官方DeepSeek认证方式
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'User-Agent': 'CryptoExchangeNewsCrawler-DeepSeek/1.0'
            })
            logger.debug("Using official DeepSeek authentication (Authorization header)")

    def chat_completion(self, messages: List[Dict[str, str]],
                       temperature: float = 0.3, max_tokens: int = 8000) -> DeepSeekResponse:
        """
        发送聊天完成请求

        Args:
            messages: 消息列表，格式：[{"role": "user|assistant|system", "content": "..."}]
            temperature: 温度参数（0-2），越低越确定
            max_tokens: 最大生成token数

        Returns:
            DeepSeekResponse: API响应数据
        """
        start_time = time.time()

        # 验证参数
        self._validate_messages(messages)
        self._validate_parameters(temperature, max_tokens)

        # 构建请求体
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        # 发送请求
        response = self._make_request('/chat/completions', payload)
        processing_time = int((time.time() - start_time) * 1000)

        # 解析响应
        return self._parse_response(response, processing_time)

    def analyze_content(self, content: str, prompt_template: str,
                       context: Dict[str, Any] = None, task_id: str = None) -> DeepSeekResponse:
        """
        分析文本内容

        Args:
            content: 要分析的文本内容
            prompt_template: 提示词模板
            context: 额外的上下文信息
            task_id: 任务ID，用于文件命名

        Returns:
            DeepSeekResponse: 分析结果
        """
        # 处理提示词模板
        if context:
            try:
                formatted_prompt = prompt_template.format(**context)
            except KeyError as e:
                raise DeepSeekValidationError(f"Prompt template missing key: {e}")
        else:
            formatted_prompt = prompt_template

        # 构建消息
        messages = [
            {"role": "system", "content": "你是一个专业的文本分析助手，请按照用户的要求仔细分析给定的内容。"},
            {"role": "user", "content": f"{formatted_prompt}\n\n分析内容：\n{content}"}
        ]

        # 保存发送给DeepSeek的文本到data目录
        self._save_deepseek_input(messages, content, formatted_prompt, task_id)

        logger.info(f"开始分析内容，长度: {len(content)} 字符")
        return self.chat_completion(messages)

    def estimate_cost(self, prompt_tokens: int, completion_tokens: int = None) -> Decimal:
        """
        估算API调用成本

        Args:
            prompt_tokens: 输入token数
            completion_tokens: 输出token数（如果为None，则估算）

        Returns:
            Decimal: 估算成本（美元）
        """
        if completion_tokens is None:
            # 估算输出token数（通常是输入的20%-50%）
            completion_tokens = int(prompt_tokens * 0.3)

        pricing = self.PRICING.get(self.model, self.PRICING["deepseek-chat"])

        # 使用Decimal进行精确计算，避免float和Decimal混合运算
        prompt_tokens_decimal = Decimal(str(prompt_tokens))
        completion_tokens_decimal = Decimal(str(completion_tokens))

        input_cost = (prompt_tokens_decimal / Decimal("1000")) * pricing["input"]
        output_cost = (completion_tokens_decimal / Decimal("1000")) * pricing["output"]

        total_cost = input_cost + output_cost
        logger.debug(f"成本估算: 输入{prompt_tokens}tokens=${input_cost:.6f}, "
                    f"输出{completion_tokens}tokens=${output_cost:.6f}, "
                    f"总计=${total_cost:.6f}")

        return total_cost

    def count_tokens(self, text: str) -> int:
        """
        估算文本的token数量

        Args:
            text: 要计算的文本

        Returns:
            int: 估算的token数
        """
        # 简单估算：中文约1个字符=1token，英文约4个字符=1token
        chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
        other_chars = len(text) - chinese_chars

        tokens = chinese_chars + (other_chars // 4)
        return max(tokens, 1)

    def validate_prompt_template(self, template: str,
                                required_vars: List[str] = None) -> bool:
        """
        验证提示词模板格式

        Args:
            template: 提示词模板
            required_vars: 必需的变量列表

        Returns:
            bool: 是否有效
        """
        if not template or not isinstance(template, str):
            return False

        if len(template.strip()) < 10:  # 模板太短
            return False

        # 检查是否包含必需变量
        if required_vars:
            for var in required_vars:
                if f"{{{var}}}" not in template:
                    logger.warning(f"Prompt template missing required variable: {var}")
                    return False

        # 检查模板变量语法
        try:
            import re
            vars_in_template = re.findall(r'\{(\w+)\}', template)
            test_data = {var: "test" for var in vars_in_template}
            template.format(**test_data)
        except (KeyError, ValueError) as e:
            logger.warning(f"Prompt template format error: {e}")
            return False

        return True

    @deepseek_api_retry(max_attempts=3)
    def _make_request(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """发送HTTP请求"""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        # 使用限流器控制API调用频率
        if not rate_limiter_manager.wait_and_acquire('deepseek_api', timeout=30):
            raise DeepSeekAPIError("DeepSeek API rate limit exceeded, timeout waiting for quota")

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.timeout
            )

            # 记录详细的响应信息用于调试
            logger.debug(f"DeepSeek API Response: status={response.status_code}, "
                        f"content_length={len(response.content) if response.content else 0}")

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise DeepSeekQuotaExceededError(
                    "API quota exceeded",
                    retry_after
                )
            elif response.status_code == 408:
                raise DeepSeekTimeoutError("Request timeout")
            else:
                # 改进错误处理：先尝试解析JSON，失败则记录原始响应
                try:
                    error_data = response.json() if response.content else {}
                    error_msg = error_data.get('error', {}).get('message', f"HTTP {response.status_code}")
                    error_code = error_data.get('error', {}).get('code')
                except (ValueError, requests.exceptions.JSONDecodeError) as json_err:
                    # JSON解析失败，记录原始响应内容
                    response_text = response.text[:500] if response.text else "(empty)"
                    logger.error(f"Failed to parse error response as JSON. "
                               f"Status: {response.status_code}, "
                               f"Content-Type: {response.headers.get('Content-Type', 'unknown')}, "
                               f"Response preview: {response_text}")
                    error_msg = f"HTTP {response.status_code}: {response_text}"
                    error_code = None

                raise DeepSeekAPIError(error_msg, response.status_code, error_code)

        except requests.RequestException as e:
            if "timeout" in str(e).lower():
                raise DeepSeekTimeoutError(f"Network timeout: {e}")
            else:
                raise DeepSeekAPIError(f"Request failed: {e}")

    def _parse_response(self, response_data: Dict[str, Any],
                       processing_time_ms: int) -> DeepSeekResponse:
        """解析API响应"""
        try:
            choice = response_data["choices"][0]
            usage = response_data["usage"]

            content = choice["message"]["content"]
            model = response_data["model"]

            prompt_tokens = usage["prompt_tokens"]
            completion_tokens = usage["completion_tokens"]
            total_tokens = usage["total_tokens"]

            # 计算实际成本
            cost = self.estimate_cost(prompt_tokens, completion_tokens)

            return DeepSeekResponse(
                content=content,
                model=model,
                tokens_used=total_tokens,
                completion_tokens=completion_tokens,
                prompt_tokens=prompt_tokens,
                cost_estimate=cost,
                processing_time_ms=processing_time_ms,
                request_id=response_data.get("id", ""),
                created_at=datetime.now()
            )

        except (KeyError, TypeError, IndexError) as e:
            logger.error(f"Failed to parse DeepSeek response: {e}")
            logger.error(f"Response data: {response_data}")
            raise DeepSeekAPIError(f"Invalid response format: {e}")

    def _validate_messages(self, messages: List[Dict[str, str]]):
        """验证消息格式"""
        if not messages or not isinstance(messages, list):
            raise DeepSeekValidationError("Messages must be a non-empty list")

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise DeepSeekValidationError(f"Message {i} must be a dictionary")

            if "role" not in msg or "content" not in msg:
                raise DeepSeekValidationError(f"Message {i} must have 'role' and 'content' fields")

            if msg["role"] not in ["user", "assistant", "system"]:
                raise DeepSeekValidationError(f"Message {i} role must be 'user', 'assistant', or 'system'")

            if not isinstance(msg["content"], str) or not msg["content"].strip():
                raise DeepSeekValidationError(f"Message {i} content must be a non-empty string")

    def _validate_parameters(self, temperature: float, max_tokens: int):
        """验证参数"""
        if temperature is None:
            raise DeepSeekValidationError("Temperature cannot be None")
        if max_tokens is None:
            raise DeepSeekValidationError("Max tokens cannot be None")

        if not 0 <= temperature <= 2:
            raise DeepSeekValidationError("Temperature must be between 0 and 2")

        if not 1 <= max_tokens <= 8192:
            raise DeepSeekValidationError("Max tokens must be between 1 and 8192")

    def _save_deepseek_input(self, messages: List[Dict[str, str]], content: str,
                            formatted_prompt: str, task_id: str = None):
        """
        保存发送给DeepSeek的输入文本到data目录

        Args:
            messages: 发送给DeepSeek的消息列表
            content: 原始内容
            formatted_prompt: 格式化后的提示词
            task_id: 任务ID
        """
        try:
            # 确保data目录存在
            data_dir = "data"
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)

            # 生成文件名
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if task_id:
                filename = f"deepseek_input_{timestamp}_{task_id[:8]}.json"
            else:
                filename = f"deepseek_input_{timestamp}.json"

            filepath = os.path.join(data_dir, filename)

            # 构建保存的数据
            save_data = {
                "timestamp": timestamp,
                "task_id": task_id,
                "model": self.model,
                "formatted_prompt": formatted_prompt,
                "content_length": len(content),
                "content": content,
                "messages": messages,
                "metadata": {
                    "content_char_count": len(content),
                    "estimated_tokens": self.count_tokens(content + formatted_prompt),
                    "api_endpoint": f"{self.base_url}/chat/completions"
                }
            }

            # 保存到JSON文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)

            logger.debug(f"DeepSeek输入已保存到: {filepath}")

        except Exception as e:
            # 记录错误但不影响主流程
            logger.warning(f"保存DeepSeek输入文件失败: {e}")

    def close(self):
        """关闭会话"""
        if hasattr(self, 'session'):
            self.session.close()
