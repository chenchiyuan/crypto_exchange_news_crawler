"""
关键位跌破检测器（Key Level Breach Detector）

用于检测价格是否跌破触发K线的关键支撑位，确认弃盘特征。

业务逻辑：
    - 中轴 = (触发K线high + 触发K线low) / 2
    - 关键位 = min(中轴, 触发K线low)
    - 跌破判断：当前收盘价 < 关键位
    - 跌破幅度 = (关键位 - 当前收盘价) / 关键位 × 100

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (F3.2 关键位跌破检测)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (检测器层-价格检测器)
    - Task: TASK-002-013
"""

import logging
from decimal import Decimal
from typing import Dict, Optional

from volume_trap.exceptions import InvalidDataError

logger = logging.getLogger(__name__)


class KeyLevelBreachDetector:
    """关键位跌破检测器。

    检测价格是否跌破触发K线的关键支撑位，用于确认弃盘特征。

    算法说明：
        - 中轴（Midpoint）= (触发K线最高价 + 触发K线最低价) / 2
        - 关键位（Key Level）= min(中轴, 触发K线最低价)
        - 跌破幅度 = (关键位 - 当前收盘价) / 关键位 × 100 (单位：%)

    触发条件：
        - 当前收盘价 < 关键位（确认跌破支撑）

    业务含义：
        - 关键位取min值：确保即使中轴下移，也不会低于触发K线的最低点
        - 跌破关键位：意味着价格已经失守触发K线的支撑位，进入弱势区域

    Attributes:
        无状态，无需初始化参数

    Examples:
        >>> detector = KeyLevelBreachDetector()
        >>> result = detector.detect(
        ...     trigger_high=Decimal('51000.00'),
        ...     trigger_low=Decimal('49000.00'),
        ...     current_close=Decimal('48500.00')
        ... )
        >>> if result['triggered']:
        ...     print(f"跌破关键位：{result['breach_percentage']}%")

    Related:
        - PRD: F3.2 关键位跌破检测
        - Architecture: 检测器层 - KeyLevelBreachDetector
        - Task: TASK-002-013
    """

    def detect(self, trigger_high: Decimal, trigger_low: Decimal, current_close: Decimal) -> Dict:
        """检测价格是否跌破关键支撑位。

        计算触发K线的关键支撑位，判断当前收盘价是否跌破该位置。

        业务逻辑：
            1. 验证价格数据合法性（Guard Clauses）
            2. 计算中轴 = (trigger_high + trigger_low) / 2
            3. 计算关键位 = min(中轴, trigger_low)
            4. 判断跌破：current_close < key_level
            5. 计算跌破幅度 = (key_level - current_close) / key_level × 100

        业务含义：
            - 中轴代表触发K线的中间价位
            - 关键位取min值：确保支撑位不低于触发K线的最低点
            - 跌破幅度：量化价格跌破的严重程度

        Args:
            trigger_high: 触发K线的最高价，必须 > 0 且 >= trigger_low
            trigger_low: 触发K线的最低价，必须 > 0
            current_close: 当前K线的收盘价，必须 > 0

        Returns:
            Dict: 检测结果，包含以下键：
                - midpoint (Decimal): 触发K线中轴价格
                - key_level (Decimal): 关键支撑位
                - breach_percentage (Decimal): 跌破幅度（%），未跌破时为0
                - triggered (bool): 是否跌破关键位

        Raises:
            InvalidDataError: 当价格数据不合法时：
                - trigger_high < trigger_low（数据异常）
                - 任何价格字段 <= 0

        Side Effects:
            - 纯计算函数，无状态修改
            - 无数据库操作

        Examples:
            >>> detector = KeyLevelBreachDetector()
            >>> # 场景1：跌破关键位
            >>> result = detector.detect(
            ...     trigger_high=Decimal('51000.00'),
            ...     trigger_low=Decimal('49000.00'),
            ...     current_close=Decimal('48500.00')  # 低于49000
            ... )
            >>> print(result['triggered'])  # True
            >>> print(result['breach_percentage'])  # 约1.02%

            >>> # 场景2：未跌破关键位
            >>> result = detector.detect(
            ...     trigger_high=Decimal('51000.00'),
            ...     trigger_low=Decimal('49000.00'),
            ...     current_close=Decimal('50000.00')  # 高于49000
            ... )
            >>> print(result['triggered'])  # False

        Context:
            - PRD Requirement: F3.2 关键位跌破检测
            - Architecture: 检测器层 - KeyLevelBreachDetector
            - Task: TASK-002-013

        Performance:
            - 纯计算逻辑，执行时间 < 0.1ms
        """
        # === Guard Clause 1: 价格字段正数检查 ===
        if trigger_high <= 0:
            raise InvalidDataError(
                field="trigger_high", value=float(trigger_high), context="触发K线最高价必须>0"
            )

        if trigger_low <= 0:
            raise InvalidDataError(
                field="trigger_low", value=float(trigger_low), context="触发K线最低价必须>0"
            )

        if current_close <= 0:
            raise InvalidDataError(
                field="current_close", value=float(current_close), context="当前收盘价必须>0"
            )

        # === Guard Clause 2: 价格数据合理性检查 ===
        if trigger_high < trigger_low:
            raise InvalidDataError(
                field="trigger_high",
                value=float(trigger_high),
                context=f"数据异常：trigger_high ({trigger_high}) < trigger_low ({trigger_low})",
            )

        # === 计算关键位 ===
        # 中轴 = (high + low) / 2
        midpoint = (trigger_high + trigger_low) / 2

        # 关键位 = min(中轴, 最低价)
        # 原因：确保关键位不低于触发K线的最低点，作为最后的支撑位
        key_level = min(midpoint, trigger_low)

        # === 判断是否跌破 ===
        triggered = current_close < key_level

        # === 计算跌破幅度 ===
        if triggered:
            # 跌破幅度 = (关键位 - 当前价) / 关键位 × 100
            breach_percentage = (key_level - current_close) / key_level * 100
        else:
            # 未跌破时幅度为0
            breach_percentage = Decimal("0.00")

        return {
            "midpoint": Decimal(str(round(midpoint, 8))),  # 保留8位小数，支持小价格币种
            "key_level": Decimal(str(round(key_level, 8))),
            "breach_percentage": Decimal(str(round(breach_percentage, 2))),
            "triggered": triggered,
        }
