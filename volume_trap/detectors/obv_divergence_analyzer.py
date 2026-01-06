"""
OBV背离分析器（OBV Divergence Analyzer）

用于分析OBV（On-Balance Volume）指标与价格的背离关系，识别"无底背离"特征。

业务逻辑：
    - 计算OBV序列：OBV[i] = OBV[i-1] + volume[i] × sign(close[i] - close[i-1])
    - 检测底背离：价格创新低时，OBV未创新低（买盘积聚信号）
    - 判断单边下滑：连续N根K线（默认5）无底背离（确认弃盘）

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (F4.2 OBV持续性分析)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (检测器层-趋势检测器)
    - Task: TASK-002-016
"""

import logging
from decimal import Decimal
from typing import Dict, List

from django.conf import settings

import pandas as pd

from backtest.models import KLine
from volume_trap.exceptions import DataInsufficientError

logger = logging.getLogger(__name__)


class OBVDivergenceAnalyzer:
    """OBV背离分析器。

    分析OBV与价格的背离关系，用于识别买盘积聚或彻底弃盘的市场状态。

    算法说明：
        - OBV[i] = OBV[i-1] + volume[i] × sign(close[i] - close[i-1])
        - sign(x) = 1 if x > 0, -1 if x < 0, 0 if x == 0
        - 底背离（Bottom Divergence）：价格创新低，OBV未创新低
        - 单边下滑（Single-Side Decline）：连续N根K线无底背离

    触发条件：
        - 单边下滑 = 连续N根K线（默认5）无底背离

    业务含义：
        - 正常下跌：价格下跌时出现底背离（OBV回升），说明买盘在积聚
        - 弃盘下跌：价格下跌时无底背离（OBV同步下滑），说明买盘彻底撤离

    Attributes:
        lookback_period (int): OBV计算回溯周期，默认30根K线
        divergence_window (int): 底背离检测窗口，默认5根K线

    Examples:
        >>> analyzer = OBVDivergenceAnalyzer(lookback_period=30, divergence_window=5)
        >>> result = analyzer.analyze(klines=[...])  # 最近30根K线
        >>> if result['single_side_decline']:
        ...     print(f"确认弃盘：连续{result['consecutive_no_divergence']}根K线无底背离")

    Related:
        - PRD: F4.2 OBV持续性分析
        - Architecture: 检测器层 - OBVDivergenceAnalyzer
        - Task: TASK-002-016
    """

    def __init__(self, lookback_period: int = 30, divergence_window: int = 5):
        """初始化OBV背离分析器。

        Args:
            lookback_period: OBV计算回溯周期（默认30根K线）
            divergence_window: 底背离检测窗口（默认5根K线）

        Examples:
            >>> analyzer = OBVDivergenceAnalyzer()
            >>> analyzer.lookback_period
            30
            >>> analyzer.divergence_window
            5
        """
        self.lookback_period = lookback_period
        self.divergence_window = divergence_window

    def analyze(self, klines: List[KLine]) -> Dict:
        """分析OBV背离特征。

        计算OBV序列，检测底背离信号，判断是否进入单边下滑模式。

        业务逻辑：
            1. 验证数据完整性（Guard Clauses）
            2. 计算OBV序列（使用pandas向量化）
            3. 检测底背离：在最近N根K线中，价格新低时OBV未新低
            4. 判断单边下滑：连续N根K线无底背离

        业务含义：
            - OBV上升：买盘积聚（正能量潮）
            - OBV下滑：卖盘主导（负能量潮）
            - 底背离：价格新低时OBV回升，暗示买盘介入
            - 单边下滑：无底背离，确认买盘彻底撤离

        Args:
            klines: K线列表，需要至少lookback_period根（默认30根）

        Returns:
            Dict: 分析结果，包含以下键：
                - obv_series (List[Decimal]): OBV序列（与klines等长）
                - obv_current (Decimal): 当前OBV值（最后一个）
                - divergence_detected (bool): 是否检测到底背离
                - single_side_decline (bool): 是否为单边下滑（无底背离）
                - consecutive_no_divergence (int): 连续无底背离的K线数量

        Raises:
            DataInsufficientError: 当K线数量 < lookback_period时

        Side Effects:
            - 只读操作，无状态修改
            - 使用pandas进行向量化计算

        Examples:
            >>> analyzer = OBVDivergenceAnalyzer(lookback_period=30, divergence_window=5)
            >>> result = analyzer.analyze(klines=[...])  # 30根K线
            >>> if result['single_side_decline']:
            ...     print(f"单边下滑：连续{result['consecutive_no_divergence']}根无底背离")
            ...     print(f"当前OBV：{result['obv_current']}")

        Context:
            - PRD Requirement: F4.2 OBV持续性分析
            - Architecture: 检测器层 - OBVDivergenceAnalyzer
            - Task: TASK-002-016

        Performance:
            - 使用pandas向量化计算，30根K线计算 < 5ms
        """
        # === Guard Clause 1: K线数量检查 ===
        # 需要至少 lookback_period 根K线才能计算OBV序列
        actual_count = len(klines)
        if actual_count < self.lookback_period:
            raise DataInsufficientError(
                required=self.lookback_period,
                actual=actual_count,
                symbol="N/A",  # OBV分析不依赖特定symbol
                interval="N/A",
            )

        # === pandas向量化计算 ===
        # 原因：向量化计算比Python循环快100倍以上

        # 提取价格和成交量序列
        df = pd.DataFrame(
            [{"close": float(k.close_price), "volume": float(k.volume)} for k in klines]
        )

        # === 计算OBV序列 ===
        # OBV[i] = OBV[i-1] + volume[i] × sign(close[i] - close[i-1])
        # sign(x) = 1 if x > 0, -1 if x < 0, 0 if x == 0

        # 计算价格变化：close[i] - close[i-1]
        df["price_change"] = df["close"].diff()  # 第一个值为NaN

        # 计算sign(price_change)
        # 使用pandas的符号函数：返回1（上涨）、-1（下跌）、0（平盘）
        df["sign"] = df["price_change"].apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))

        # 计算每根K线的OBV增量：volume × sign
        df["obv_delta"] = df["volume"] * df["sign"]

        # 累加计算OBV序列（第一根K线的OBV=0）
        df["obv"] = df["obv_delta"].cumsum()

        # === 检测底背离 ===
        # 底背离定义：在最近N根K线中，价格创新低，但OBV未创新低
        # 检测窗口：最后 divergence_window 根K线

        # 获取最近N根K线的数据
        recent_window = min(self.divergence_window, len(df))
        recent_df = df.iloc[-recent_window:]

        # 检测底背离：
        # 条件1：价格创新低（当前价格 <= 窗口内最低价）
        # 条件2：OBV未创新低（当前OBV > 窗口内最低OBV）
        price_min = recent_df["close"].min()
        obv_min = recent_df["obv"].min()

        current_price = df["close"].iloc[-1]
        current_obv = df["obv"].iloc[-1]

        # 底背离触发条件
        divergence_detected = (current_price <= price_min) and (current_obv > obv_min)

        # === 判断单边下滑 ===
        # 单边下滑定义：连续N根K线无底背离
        # 需要逐根检查最近N根K线，看是否出现底背离

        consecutive_no_divergence = 0
        for i in range(len(df) - 1, max(len(df) - self.divergence_window - 1, -1), -1):
            # 对每根K线，检查从开始到该K线为止的窗口内是否有底背离
            window_start = max(0, i - self.divergence_window + 1)
            window_df = df.iloc[window_start : i + 1]

            price_min_window = window_df["close"].min()
            obv_min_window = window_df["obv"].min()

            current_price_i = df["close"].iloc[i]
            current_obv_i = df["obv"].iloc[i]

            # 检查是否有底背离
            has_divergence = (current_price_i <= price_min_window) and (
                current_obv_i > obv_min_window
            )

            if has_divergence:
                # 遇到底背离，停止计数
                break
            else:
                # 无底背离，计数+1
                consecutive_no_divergence += 1

        # 单边下滑触发条件：连续N根K线无底背离
        single_side_decline = consecutive_no_divergence >= self.divergence_window

        # 将OBV序列转换为Decimal列表
        obv_series = [Decimal(str(round(obv, 8))) for obv in df["obv"].tolist()]

        return {
            "obv_series": obv_series,
            "obv_current": obv_series[-1],
            "divergence_detected": divergence_detected,
            "single_side_decline": single_side_decline,
            "consecutive_no_divergence": consecutive_no_divergence,
        }
