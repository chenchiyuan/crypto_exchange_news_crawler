"""
价差效率分析器（Price Efficiency Analyzer）

用于分析价格变化相对于成交量的效率，识别"卖盘深度已撤离"的特征。

业务逻辑：
    - 价差效率（PE）= |收盘价 - 开盘价| / 成交量
    - 高PE值意味着：极小的成交量就能导致价格大幅下跌，买盘深度已消失
    - 触发条件：当前5根K线平均PE > 历史30天平均PE × 2

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (F3.3 价差效率计算)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (检测器层-价格检测器)
    - Task: TASK-002-014
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings

import pandas as pd

from backtest.models import KLine
from volume_trap.exceptions import DataInsufficientError

logger = logging.getLogger(__name__)


class PriceEfficiencyAnalyzer:
    """价差效率分析器。

    分析价格变化相对于成交量的效率，用于识别买盘深度已撤离的市场状态。

    算法说明：
        - 价差效率（PE）= |close - open| / volume
        - 当PE值异常升高时，说明极小的卖盘就能导致价格大幅下跌
        - 使用pandas向量化计算提升性能

    触发条件：
        - 当前5根K线平均PE > 历史30天平均PE × 2（买盘深度消失）

    业务含义：
        - 正常市场：PE值稳定，价格变化需要较大成交量支撑
        - 弃盘市场：PE值飙升，微小卖盘即可导致价格暴跌，买盘深度已撤离

    Attributes:
        historical_period (int): 历史PE均值计算周期，默认30天（30根日K线）
        efficiency_multiplier (float): 异常倍数阈值，默认2倍

    Examples:
        >>> analyzer = PriceEfficiencyAnalyzer()
        >>> result = analyzer.analyze(
        ...     recent_klines=[kline1, kline2, kline3, kline4, kline5],
        ...     historical_klines=[...],  # 30根历史K线
        ...     efficiency_multiplier=2.0
        ... )
        >>> if result and result['triggered']:
        ...     print(f"价差效率异常：{result['current_pe']} > {result['historical_pe_mean']} × 2")

    Related:
        - PRD: F3.3 价差效率计算
        - Architecture: 检测器层 - PriceEfficiencyAnalyzer
        - Task: TASK-002-014
    """

    def __init__(self):
        """初始化价差效率分析器。

        从配置读取默认参数。

        Examples:
            >>> analyzer = PriceEfficiencyAnalyzer()
            >>> analyzer.historical_period
            30
        """
        self.historical_period = settings.VOLUME_TRAP_CONFIG.get("PE_HISTORICAL_PERIOD", 30)
        self.efficiency_multiplier = settings.VOLUME_TRAP_CONFIG.get(
            "PE_EFFICIENCY_MULTIPLIER", 2.0
        )

    def analyze(
        self,
        recent_klines: List[KLine],
        historical_klines: List[KLine],
        efficiency_multiplier: Optional[float] = None,
    ) -> Optional[Dict]:
        """分析价差效率指标。

        计算当前K线的平均PE与历史PE的比值，判断是否出现买盘深度消失的异常。

        业务逻辑：
            1. 验证数据完整性（Guard Clauses）
            2. 计算每根K线的PE = |close - open| / volume（跳过volume=0的K线）
            3. 计算当前5根K线的平均PE
            4. 计算历史30天K线的平均PE
            5. 判断触发：current_pe > historical_pe × multiplier

        业务含义：
            - PE值 = 单位成交量导致的价格变化幅度
            - PE升高：说明买盘深度已撤离，微小卖盘即可导致价格暴跌
            - PE正常：说明市场流动性充足，价格变化需要较大成交量

        Args:
            recent_klines: 最近的K线列表（通常5根），用于计算当前PE
            historical_klines: 历史K线列表（至少30根），用于计算历史PE均值
            efficiency_multiplier: 异常倍数阈值（可选），默认2倍

        Returns:
            Optional[Dict]: 分析结果，包含以下键：
                - current_pe (Decimal): 当前5根K线的平均PE
                - historical_pe_mean (Decimal): 历史30天K线的平均PE
                - triggered (bool): 是否触发异常阈值
                - recent_count (int): 参与计算的当前K线数量（跳过volume=0）
                - historical_count (int): 参与计算的历史K线数量（跳过volume=0）
                数据不足时返回None

        Raises:
            DataInsufficientError: 当历史K线数量 < 30时
            ValueError: 当efficiency_multiplier不在合理范围内时

        Side Effects:
            - 只读操作，无状态修改
            - 使用pandas进行向量化计算

        Examples:
            >>> analyzer = PriceEfficiencyAnalyzer()
            >>> result = analyzer.analyze(
            ...     recent_klines=[kline1, kline2, kline3, kline4, kline5],
            ...     historical_klines=[...],  # 30根K线
            ...     efficiency_multiplier=2.0
            ... )
            >>> if result and result['triggered']:
            ...     print(f"PE异常：{result['current_pe']} > {result['historical_pe_mean']} × 2")

        Context:
            - PRD Requirement: F3.3 价差效率计算
            - Architecture: 检测器层 - PriceEfficiencyAnalyzer
            - Task: TASK-002-014

        Performance:
            - 使用pandas向量化计算，30-35根K线计算 < 5ms
        """
        # === Guard Clause 1: efficiency_multiplier合法性检查 ===
        if efficiency_multiplier is None:
            efficiency_multiplier = self.efficiency_multiplier
        if efficiency_multiplier <= 0:
            raise ValueError(
                f"efficiency_multiplier参数边界错误: " f"预期>0, 实际值={efficiency_multiplier}"
            )

        # === Guard Clause 2: 历史K线数量检查 ===
        actual_count = len(historical_klines)
        if actual_count < self.historical_period:
            raise DataInsufficientError(
                required=self.historical_period,
                actual=actual_count,
                symbol="N/A",  # PE分析不依赖特定symbol
                interval="N/A",
            )

        # === pandas向量化计算 ===
        # 原因：向量化计算比Python循环快100倍以上

        # 计算历史PE均值
        historical_pe_list = self._calculate_pe_list(historical_klines)
        if len(historical_pe_list) == 0:
            # 所有历史K线volume都为0，无法计算
            logger.warning("所有历史K线volume=0，无法计算PE")
            return None

        historical_pe_mean = sum(historical_pe_list) / len(historical_pe_list)

        # 计算当前PE均值
        recent_pe_list = self._calculate_pe_list(recent_klines)
        if len(recent_pe_list) == 0:
            # 所有当前K线volume都为0，无法计算
            logger.warning("所有当前K线volume=0，无法计算PE")
            return None

        current_pe = sum(recent_pe_list) / len(recent_pe_list)

        # === 判断是否触发 ===
        # 触发条件：current_pe > historical_pe × multiplier
        triggered = current_pe > (historical_pe_mean * efficiency_multiplier)

        return {
            "current_pe": Decimal(str(round(current_pe, 8))),
            "historical_pe_mean": Decimal(str(round(historical_pe_mean, 8))),
            "triggered": triggered,
            "recent_count": len(recent_pe_list),
            "historical_count": len(historical_pe_list),
        }

    def _calculate_pe_list(self, klines: List[KLine]) -> List[float]:
        """计算K线列表的PE值列表。

        跳过volume=0的K线（无法计算PE）。

        业务逻辑：
            - PE = |close - open| / volume
            - 跳过volume=0的K线（除零错误）

        Args:
            klines: K线列表

        Returns:
            List[float]: PE值列表（跳过volume=0的K线）

        Side Effects:
            - 只读操作，无状态修改
            - 使用pandas进行向量化计算

        Examples:
            >>> analyzer = PriceEfficiencyAnalyzer()
            >>> pe_list = analyzer._calculate_pe_list([kline1, kline2, kline3])
            >>> print(pe_list)  # [0.005, 0.003, 0.004]
        """
        # 转换为pandas DataFrame
        df = pd.DataFrame(
            [
                {
                    "open": float(k.open_price),
                    "close": float(k.close_price),
                    "volume": float(k.volume),
                }
                for k in klines
            ]
        )

        # 过滤掉volume=0的K线
        df = df[df["volume"] > 0]

        if len(df) == 0:
            return []

        # 计算PE = |close - open| / volume
        df["pe"] = (df["close"] - df["open"]).abs() / df["volume"]

        return df["pe"].tolist()
