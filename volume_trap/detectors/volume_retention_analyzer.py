"""
成交量留存分析器（Volume Retention Analyzer）

用于检测巨量K线后的资金留存情况，区分"洗盘"还是"彻底弃盘"。

业务逻辑：
    - 留存率 = 触发后3-5根K线的平均成交量 / 触发时成交量 × 100
    - 触发条件：留存率 < 15%（代表买盘极度匮乏）
    - 低留存率意味着：资金已撤离，市场进入流动性荒漠

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (F3.1 成交量留存率监控)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (检测器层-成交量检测器)
    - Task: TASK-002-012
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings

import pandas as pd

from backtest.models import KLine
from volume_trap.exceptions import DataInsufficientError, InvalidDataError

logger = logging.getLogger(__name__)


class VolumeRetentionAnalyzer:
    """成交量留存分析器。

    分析巨量K线后的成交量衰减情况，识别"资金洗盘"与"彻底弃盘"的区别。

    算法说明：
        - 留存率 = 平均成交量(后续3-5根K线) / 触发时成交量 × 100 (单位：%)
        - 使用pandas向量化计算提升性能

    触发条件：
        - 留存率 < 15% （买盘极度匮乏）

    Attributes:
        retention_threshold (float): 留存率触发阈值，默认15%

    Examples:
        >>> analyzer = VolumeRetentionAnalyzer()
        >>> result = analyzer.analyze(
        ...     trigger_volume=Decimal('8000.00'),
        ...     post_klines=[kline1, kline2, kline3, kline4, kline5],
        ...     retention_threshold=15.0
        ... )
        >>> if result and result['triggered']:
        ...     print(f"成交量急剧衰减：留存率={result['retention_ratio']}%")

    Related:
        - PRD: F3.1 成交量留存率监控
        - Architecture: 检测器层 - VolumeRetentionAnalyzer
        - Task: TASK-002-012
    """

    def __init__(self):
        """初始化成交量留存分析器。

        从配置读取默认阈值。

        Examples:
            >>> analyzer = VolumeRetentionAnalyzer()
            >>> analyzer.retention_threshold
            15.0
        """
        self.retention_threshold = settings.VOLUME_TRAP_CONFIG.get("VOLUME_RETENTION_THRESHOLD", 15)

    def analyze(
        self,
        trigger_volume: Decimal,
        post_klines: List[KLine],
        retention_threshold: Optional[float] = None,
    ) -> Optional[Dict]:
        """分析成交量留存情况。

        计算触发后K线的平均成交量与触发时成交量的比值，判断是否出现资金撤离。

        业务逻辑：
            1. 验证trigger_volume > 0（Guard Clause）
            2. 验证后续K线数量 >= 3根（Guard Clause）
            3. 计算后续3-5根K线的平均成交量
            4. 计算留存率 = avg(V_post) / V_trigger × 100
            5. 判断触发：留存率 < 15%（买盘极度匮乏）

        业务含义：
            - 留存率 < 15%：资金彻底撤离，进入弃盘状态
            - 留存率 >= 15%：可能是洗盘或正常回调

        Args:
            trigger_volume: 触发时的成交量（V_trigger），必须 > 0
            post_klines: 触发后的K线列表（3-5根），按时间升序排列
            retention_threshold: 留存率触发阈值（可选），默认使用配置值

        Returns:
            Optional[Dict]: 分析结果，包含以下键：
                - avg_volume_post (Decimal): 后续K线平均成交量
                - retention_ratio (Decimal): 留存率（%）
                - triggered (bool): 是否触发阈值（留存率 < threshold）
                - post_kline_count (int): 实际参与计算的K线数量
                数据不足时返回None

        Raises:
            InvalidDataError: 当trigger_volume <= 0时
            DataInsufficientError: 当后续K线数量 < 3时
            ValueError: 当retention_threshold不在合理范围内时

        Side Effects:
            - 只读操作，无状态修改
            - 使用pandas进行向量化计算

        Examples:
            >>> analyzer = VolumeRetentionAnalyzer()
            >>> result = analyzer.analyze(
            ...     trigger_volume=Decimal('8000.00'),
            ...     post_klines=[kline1, kline2, kline3],
            ...     retention_threshold=15.0
            ... )
            >>> if result and result['triggered']:
            ...     print(f"留存率: {result['retention_ratio']}% < 15%")

        Context:
            - PRD Requirement: F3.1 成交量留存率监控
            - Architecture: 检测器层 - VolumeRetentionAnalyzer
            - Task: TASK-002-012

        Performance:
            - 使用pandas向量化计算，3-5根K线计算 < 1ms
        """
        # === Guard Clause 1: trigger_volume合法性检查 ===
        if trigger_volume <= 0:
            raise InvalidDataError(
                field="trigger_volume",
                value=float(trigger_volume),
                context="触发成交量必须>0，无法计算留存率",
            )

        # === Guard Clause 2: retention_threshold合法性检查 ===
        if retention_threshold is None:
            retention_threshold = self.retention_threshold
        if not (0 < retention_threshold <= 100):
            raise ValueError(
                f"retention_threshold参数边界错误: "
                f"预期范围=(0, 100], 实际值={retention_threshold}"
            )

        # === Guard Clause 3: 后续K线数量检查 ===
        actual_count = len(post_klines)
        if actual_count < 3:
            raise DataInsufficientError(
                required=3,
                actual=actual_count,
                symbol="N/A",  # 留存率分析不依赖特定symbol
                interval="N/A",
            )

        # === pandas向量化计算 ===
        # 原因：向量化计算比Python循环快100倍以上
        # 取前5根K线（如果有）
        klines_to_analyze = post_klines[:5]
        volumes = pd.Series([float(k.volume) for k in klines_to_analyze])

        # 计算平均成交量
        avg_volume_post = volumes.mean()

        # 计算留存率（%）
        # retention_ratio = avg(V_post) / V_trigger × 100
        trigger_volume_float = float(trigger_volume)
        retention_ratio = (avg_volume_post / trigger_volume_float) * 100

        # 判断是否触发
        # 触发条件：留存率 < threshold（买盘极度匮乏）
        triggered = retention_ratio < retention_threshold

        return {
            "avg_volume_post": Decimal(str(round(avg_volume_post, 2))),
            "retention_ratio": Decimal(str(round(retention_ratio, 2))),
            "triggered": triggered,
            "post_kline_count": len(klines_to_analyze),
        }
