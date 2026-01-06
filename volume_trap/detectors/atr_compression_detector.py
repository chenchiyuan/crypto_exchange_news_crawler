"""
ATR压缩检测器（ATR Compression Detector）

用于检测平均真实波幅（ATR）的压缩，识别市场波动率持续收缩的特征。

业务逻辑：
    - 计算TR（True Range）：TR = max(high-low, abs(high-close_prev), abs(low-close_prev))
    - 计算ATR(14)：使用14周期的EMA平滑TR
    - 检测连续递减：最近5根K线的ATR持续下降
    - 判断压缩：连续递减 AND 当前ATR < 历史均值 × 0.5

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (F4.3 ATR波动率压缩检测)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (检测器层-趋势检测器)
    - Task: TASK-002-017
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings

import pandas as pd

from backtest.models import KLine
from volume_trap.exceptions import DataInsufficientError

logger = logging.getLogger(__name__)


class ATRCompressionDetector:
    """ATR压缩检测器。

    检测平均真实波幅（ATR）的压缩，用于识别市场波动率持续收缩的状态。

    算法说明：
        - TR（True Range）= max(high - low, abs(high - close_prev), abs(low - close_prev))
        - ATR(14) = EMA(TR, 14)，使用指数移动平均平滑TR序列
        - 连续递减：最近5根K线的ATR单调递减
        - 压缩判断：连续递减 AND 当前ATR < 历史30根K线ATR均值 × 0.5

    触发条件：
        - is_decreasing: 最近5根K线ATR连续递减
        - is_compressed: is_decreasing AND atr_current < atr_baseline × 0.5

    业务含义：
        - ATR压缩：市场波动率持续收缩，进入低波动区域
        - 组合弃盘特征：低波动率意味着市场关注度下降，缺乏新资金入场
        - 历史意义：压缩后往往伴随暴力突破或进一步沉寂

    Attributes:
        atr_period (int): ATR计算周期，默认14
        baseline_period (int): 基线计算周期，默认30
        decreasing_window (int): 连续递减检测窗口，默认5
        compression_threshold (float): 压缩阈值倍数，默认0.5

    Examples:
        >>> detector = ATRCompressionDetector()
        >>> result = detector.detect(klines=[...])  # 最近30根K线
        >>> if result['is_compressed']:
        ...     print(f"ATR压缩：{result['atr_current']} < {result['atr_baseline']} × 0.5")
        ...     print(f"连续递减：{result['is_decreasing']}")

    Related:
        - PRD: F4.3 ATR波动率压缩检测
        - Architecture: 检测器层 - ATRCompressionDetector
        - Task: TASK-002-017
    """

    def __init__(self):
        """初始化ATR压缩检测器。

        从配置读取默认参数。

        Examples:
            >>> detector = ATRCompressionDetector()
            >>> detector.atr_period
            14
            >>> detector.compression_threshold
            0.5
        """
        self.atr_period = settings.VOLUME_TRAP_CONFIG.get("ATR_PERIOD", 14)
        self.baseline_period = settings.VOLUME_TRAP_CONFIG.get("ATR_BASELINE_PERIOD", 30)
        self.decreasing_window = settings.VOLUME_TRAP_CONFIG.get("ATR_DECREASING_WINDOW", 5)
        self.compression_threshold = settings.VOLUME_TRAP_CONFIG.get(
            "ATR_COMPRESSION_THRESHOLD", 0.5
        )

    def detect(self, klines: List[KLine], compression_threshold: Optional[float] = None) -> Dict:
        """检测ATR压缩信号。

        计算ATR序列，判断是否出现连续递减和压缩（ATR < 历史均值 × 0.5）。

        业务逻辑：
            1. 验证数据完整性（Guard Clauses）
            2. 计算TR序列：TR = max(high-low, abs(high-close_prev), abs(low-close_prev))
            3. 计算ATR(14)：使用EMA平滑TR
            4. 计算历史ATR均值（基线）
            5. 检测连续递减：最近5根K线ATR单调递减
            6. 判断压缩：连续递减 AND atr_current < atr_baseline × 0.5

        业务含义：
            - TR（True Range）：当前K线的真实波动幅度，考虑跳空因素
            - ATR：平滑后的真实波幅，反映市场波动率水平
            - 连续递减：波动率持续下降，市场活跃度降低
            - 压缩：波动率已降至历史均值的一半以下，极度冷清

        Args:
            klines: K线列表，至少需要baseline_period根（默认30根）
            compression_threshold: 压缩阈值（可选），默认0.5

        Returns:
            Dict: 检测结果，包含以下键：
                - atr_current (Decimal): 当前ATR值
                - atr_baseline (Decimal): 历史ATR均值（基线）
                - is_decreasing (bool): 是否连续递减（最近5根）
                - is_compressed (bool): 是否压缩（连续递减 AND ATR < 基线 × 0.5）

        Raises:
            DataInsufficientError: 当K线数量 < baseline_period时

        Side Effects:
            - 只读操作，无状态修改
            - 使用pandas进行向量化计算

        Examples:
            >>> detector = ATRCompressionDetector()
            >>> result = detector.detect(klines=[...])  # 30根K线
            >>> if result['is_compressed']:
            ...     print(f"ATR压缩：{result['atr_current']} < {result['atr_baseline']} × 0.5")
            >>> if result['is_decreasing']:
            ...     print("最近5根K线ATR连续递减")

        Context:
            - PRD Requirement: F4.3 ATR波动率压缩检测
            - Architecture: 检测器层 - ATRCompressionDetector
            - Task: TASK-002-017

        Performance:
            - 使用pandas向量化计算，30根K线计算 < 5ms
        """
        # === Guard Clause 1: 参数默认值处理 ===
        if compression_threshold is None:
            compression_threshold = self.compression_threshold

        # === Guard Clause 2: K线数量检查 ===
        # 需要至少baseline_period根K线才能计算历史ATR均值
        actual_count = len(klines)
        if actual_count < self.baseline_period:
            raise DataInsufficientError(
                required=self.baseline_period,
                actual=actual_count,
                symbol="N/A",  # ATR分析不依赖特定symbol
                interval="N/A",
            )

        # === pandas向量化计算 ===
        # 原因：向量化计算比Python循环快100倍以上

        # 转换为pandas DataFrame
        df = pd.DataFrame(
            [
                {
                    "high": float(k.high_price),
                    "low": float(k.low_price),
                    "close": float(k.close_price),
                }
                for k in klines
            ]
        )

        # === 计算TR（True Range）===
        # TR = max(high - low, abs(high - close_prev), abs(low - close_prev))
        # 注意：第一根K线没有close_prev，所以TR = high - low

        # 方法1：当前high - low
        method1 = df["high"] - df["low"]

        # 方法2：abs(high - close_prev)
        # 使用shift(1)获取前一根K线的close
        df["close_prev"] = df["close"].shift(1)
        method2 = (df["high"] - df["close_prev"]).abs()

        # 方法3：abs(low - close_prev)
        method3 = (df["low"] - df["close_prev"]).abs()

        # TR = max(method1, method2, method3)
        # 对于第一根K线（close_prev=NaN），只使用method1
        df["tr"] = pd.concat([method1, method2, method3], axis=1).max(axis=1)

        # === 计算ATR(14) - 使用EMA平滑 ===
        # ATR(14) = EMA(TR, 14)
        # pandas的ewm()方法使用span参数控制平滑度，span=14对应EMA周期14
        df["atr"] = df["tr"].ewm(span=self.atr_period, adjust=False).mean()

        # === 获取当前ATR值 ===
        atr_current = df["atr"].iloc[-1]

        # === 计算历史ATR均值（基线）===
        # 使用所有K线的ATR均值作为基线
        atr_baseline = df["atr"].mean()

        # === 检测连续递减 ===
        # 判断最近decreasing_window根K线的ATR是否单调递减
        recent_atr = df["atr"].iloc[-self.decreasing_window :].tolist()
        is_decreasing = all(recent_atr[i] > recent_atr[i + 1] for i in range(len(recent_atr) - 1))

        # === 判断压缩 ===
        # 压缩条件：连续递减 AND 当前ATR < 历史均值 × threshold
        is_compressed = is_decreasing and (atr_current < atr_baseline * compression_threshold)

        return {
            "atr_current": Decimal(str(round(atr_current, 8))),
            "atr_baseline": Decimal(str(round(atr_baseline, 8))),
            "is_decreasing": is_decreasing,
            "is_compressed": is_compressed,
        }
