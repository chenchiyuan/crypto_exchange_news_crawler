"""
条件评估器（Condition Evaluator）

用于组合多个检测器结果，评估三阶段检测条件是否满足。

业务逻辑：
    - Discovery（发现）: RVOL触发 AND 振幅触发
    - Confirmation（确认）: 成交量留存触发 AND 关键位跌破触发 AND PE触发
    - Validation（验证）: MA死叉触发 AND OBV单边下滑 AND ATR压缩触发

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第二部分-功能模块拆解)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (检测器层-条件评估器)
    - Task: TASK-002-020
"""

import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ConditionEvaluator:
    """条件评估器。

    组合多个检测器的结果，评估三阶段检测条件是否满足。

    业务逻辑：
        - Discovery（发现阶段）：RVOL触发 AND 振幅触发
        - Confirmation（确认阶段）：成交量留存 AND 关键位跌破 AND PE异常
        - Validation（验证阶段）：MA死叉 AND OBV单边下滑 AND ATR压缩

    设计原则：
        - 纯逻辑组合，无状态
        - 输入为dict（检测器结果）
        - 输出为boolean
        - 缺少required key时抛出KeyError
        - 检测器返回None时返回False（无法评估）

    Examples:
        >>> evaluator = ConditionEvaluator()
        >>> discovery_result = evaluator.evaluate_discovery_condition({
        ...     'rvol_triggered': True,
        ...     'amplitude_triggered': True
        ... })
        >>> print(discovery_result)  # True

    Related:
        - PRD: 第二部分-功能模块拆解
        - Architecture: 检测器层 - ConditionEvaluator
        - Task: TASK-002-020
    """

    def evaluate_discovery_condition(self, results: Dict) -> bool:
        """评估发现阶段条件。

        组合RVOL和振幅检测器的结果，判断是否满足发现条件。

        业务逻辑：
            - RVOL触发：成交量 >= 历史均值 × 8倍（异常放量）
            - 振幅触发：振幅 >= 历史均值 × 3倍 AND 上影线 >= 50%（脉冲特征）
            - 组合条件：RVOL触发 AND 振幅触发（双重确认）

        业务含义：
            - RVOL触发：异常资金涌入，市场关注度突然升高
            - 振幅触发：剧烈波动且收盘价回落，疑似诱多
            - 组合触发：高概率为"拉高出货"的脉冲特征

        Args:
            results: 检测器结果字典，必须包含以下键：
                - rvol_triggered (bool): RVOL是否触发
                - amplitude_triggered (bool): 振幅是否触发

        Returns:
            bool: 是否满足发现条件（True=满足，False=不满足）

        Raises:
            KeyError: 当results缺少required key时

        Side Effects:
            - 只读操作，无状态修改
            - 如果results为None或检测器结果为None，返回False

        Examples:
            >>> evaluator = ConditionEvaluator()
            >>> # 场景1：双重确认，满足条件
            >>> result = evaluator.evaluate_discovery_condition({
            ...     'rvol_triggered': True,
            ...     'amplitude_triggered': True
            ... })
            >>> print(result)  # True

            >>> # 场景2：RVOL触发但振幅未触发，不满足条件
            >>> result = evaluator.evaluate_discovery_condition({
            ...     'rvol_triggered': True,
            ...     'amplitude_triggered': False
            ... })
            >>> print(result)  # False

        Context:
            - PRD Requirement: 发现阶段条件
            - Architecture: 条件评估器 - evaluate_discovery_condition
            - Task: TASK-002-020

        Performance:
            - 纯逻辑组合，执行时间 < 0.01ms
        """
        # === Guard Clause: 检查results是否为None ===
        if results is None:
            logger.warning("Discovery条件评估：results为None，返回False")
            return False

        # === 获取检测器结果（会抛出KeyError如果key不存在）===
        rvol_triggered = results["rvol_triggered"]
        amplitude_triggered = results["amplitude_triggered"]

        # === Guard Clause: 检查检测器结果是否为None ===
        if rvol_triggered is None or amplitude_triggered is None:
            logger.warning(
                f"Discovery条件评估：检测器结果包含None，返回False "
                f"(rvol={rvol_triggered}, amplitude={amplitude_triggered})"
            )
            return False

        # === 组合逻辑：RVOL触发 AND 振幅触发 ===
        # 业务规则来源：PRD-发现阶段-双重确认机制
        return rvol_triggered and amplitude_triggered

    def evaluate_confirmation_condition(self, results: Dict) -> bool:
        """评估确认阶段条件。

        组合成交量留存、关键位跌破、PE异常的结果，判断是否满足确认条件。

        业务逻辑：
            - 成交量留存触发：平均成交量 < 触发成交量 × 15%（弃盘特征）
            - 关键位跌破触发：当前收盘价 < 关键位（支撑失守）
            - PE异常触发：当前PE > 历史PE × 2（买盘深度消失）
            - 组合条件：三者同时触发（三重确认）

        业务含义：
            - 成交量留存低：资金快速撤离，无后续买盘
            - 关键位跌破：价格失守支撑，进入弱势区域
            - PE异常：微小卖盘即可导致价格暴跌，市场流动性枯竭
            - 组合触发：确认"弃盘"特征，非正常洗盘

        Args:
            results: 检测器结果字典，必须包含以下键：
                - volume_retention_triggered (bool): 成交量留存是否触发
                - key_level_breached (bool): 关键位是否跌破
                - pe_triggered (bool): PE是否触发

        Returns:
            bool: 是否满足确认条件（True=满足，False=不满足）

        Raises:
            KeyError: 当results缺少required key时

        Side Effects:
            - 只读操作，无状态修改
            - 如果results为None或检测器结果为None，返回False

        Examples:
            >>> evaluator = ConditionEvaluator()
            >>> # 场景1：三重确认，满足条件
            >>> result = evaluator.evaluate_confirmation_condition({
            ...     'volume_retention_triggered': True,
            ...     'key_level_breached': True,
            ...     'pe_triggered': True
            ... })
            >>> print(result)  # True

            >>> # 场景2：成交量留存触发但其他未触发，不满足条件
            >>> result = evaluator.evaluate_confirmation_condition({
            ...     'volume_retention_triggered': True,
            ...     'key_level_breached': False,
            ...     'pe_triggered': False
            ... })
            >>> print(result)  # False

        Context:
            - PRD Requirement: 确认阶段条件
            - Architecture: 条件评估器 - evaluate_confirmation_condition
            - Task: TASK-002-020

        Performance:
            - 纯逻辑组合，执行时间 < 0.01ms
        """
        # === Guard Clause: 检查results是否为None ===
        if results is None:
            logger.warning("Confirmation条件评估：results为None，返回False")
            return False

        # === 获取检测器结果（会抛出KeyError如果key不存在）===
        volume_retention_triggered = results["volume_retention_triggered"]
        key_level_breached = results["key_level_breached"]
        pe_triggered = results["pe_triggered"]

        # === Guard Clause: 检查检测器结果是否为None ===
        if volume_retention_triggered is None or key_level_breached is None or pe_triggered is None:
            logger.warning(
                f"Confirmation条件评估：检测器结果包含None，返回False "
                f"(volume_retention={volume_retention_triggered}, "
                f"key_level={key_level_breached}, pe={pe_triggered})"
            )
            return False

        # === 组合逻辑：成交量留存 AND 关键位跌破 AND PE异常 ===
        # 业务规则来源：PRD-确认阶段-三重确认机制
        return volume_retention_triggered and key_level_breached and pe_triggered

    def evaluate_validation_condition(self, results: Dict) -> bool:
        """评估验证阶段条件。

        组合MA死叉、OBV单边下滑、ATR压缩的结果，判断是否满足验证条件。

        业务逻辑：
            - MA死叉触发：MA(7) < MA(25) AND MA25斜率 < 0（趋势反转）
            - OBV单边下滑触发：连续5根K线无底背离（持续流出）
            - ATR压缩触发：连续5根K线ATR递减 AND ATR < 历史均值 × 0.5（波动率收缩）
            - 组合条件：三者同时触发（三重确认）

        业务含义：
            - MA死叉：短期和长期趋势均转弱，市场情绪转空
            - OBV单边下滑：资金持续流出，无抄底资金介入
            - ATR压缩：波动率收缩，市场关注度持续下降
            - 组合触发：确认"已弃盘"，进入长期沉寂

        Args:
            results: 检测器结果字典，必须包含以下键：
                - ma_death_cross (bool): MA是否死叉
                - obv_single_side_decline (bool): OBV是否单边下滑
                - atr_compressed (bool): ATR是否压缩

        Returns:
            bool: 是否满足验证条件（True=满足，False=不满足）

        Raises:
            KeyError: 当results缺少required key时

        Side Effects:
            - 只读操作，无状态修改
            - 如果results为None或检测器结果为None，返回False

        Examples:
            >>> evaluator = ConditionEvaluator()
            >>> # 场景1：三重确认，满足条件
            >>> result = evaluator.evaluate_validation_condition({
            ...     'ma_death_cross': True,
            ...     'obv_single_side_decline': True,
            ...     'atr_compressed': True
            ... })
            >>> print(result)  # True

            >>> # 场景2：MA死叉但其他未触发，不满足条件
            >>> result = evaluator.evaluate_validation_condition({
            ...     'ma_death_cross': True,
            ...     'obv_single_side_decline': False,
            ...     'atr_compressed': False
            ... })
            >>> print(result)  # False

        Context:
            - PRD Requirement: 验证阶段条件
            - Architecture: 条件评估器 - evaluate_validation_condition
            - Task: TASK-002-020

        Performance:
            - 纯逻辑组合，执行时间 < 0.01ms
        """
        # === Guard Clause: 检查results是否为None ===
        if results is None:
            logger.warning("Validation条件评估：results为None，返回False")
            return False

        # === 获取检测器结果（会抛出KeyError如果key不存在）===
        ma_death_cross = results["ma_death_cross"]
        obv_single_side_decline = results["obv_single_side_decline"]
        atr_compressed = results["atr_compressed"]

        # === Guard Clause: 检查检测器结果是否为None ===
        if ma_death_cross is None or obv_single_side_decline is None or atr_compressed is None:
            logger.warning(
                f"Validation条件评估：检测器结果包含None，返回False "
                f"(ma={ma_death_cross}, "
                f"obv={obv_single_side_decline}, atr={atr_compressed})"
            )
            return False

        # === 组合逻辑：MA死叉 AND OBV单边下滑 AND ATR压缩 ===
        # 业务规则来源：PRD-验证阶段-三重确认机制
        return ma_death_cross and obv_single_side_decline and atr_compressed
