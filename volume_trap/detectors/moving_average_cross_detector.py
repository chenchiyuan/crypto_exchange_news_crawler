"""
均线交叉检测器（Moving Average Cross Detector）

用于检测MA(7)死叉MA(25)，识别长期趋势反转进入弱势区域的特征。

业务逻辑：
    - 计算MA(7)和MA(25)
    - 计算MA(25)斜率：(MA25_current - MA25_prev) / MA25_prev
    - 死叉判断：MA(7) < MA(25) AND MA25_slope < 0

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (F4.1 均线系统计算)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (检测器层-趋势检测器)
    - Task: TASK-002-015
"""

import logging
from decimal import Decimal
from typing import Dict, List

from django.conf import settings

import pandas as pd

from backtest.models import KLine
from volume_trap.exceptions import DataInsufficientError, InvalidDataError

logger = logging.getLogger(__name__)


class MovingAverageCrossDetector:
    """均线交叉检测器。

    检测MA(7)死叉MA(25)，用于识别长期趋势反转进入弱势区域的市场状态。

    算法说明：
        - MA(N) = avg(close_price, N)
        - MA25_slope = (MA25_current - MA25_prev) / MA25_prev
        - 死叉（Death Cross）= MA(7) < MA(25) AND MA25_slope < 0
        - 使用pandas向量化计算提升性能

    触发条件：
        - MA(7) < MA(25)：短期均线跌破长期均线
        - MA(25)斜率 < 0：长期均线本身也在下行

    业务含义：
        - 正常市场：MA(7) >= MA(25)，短期趋势强于长期趋势
        - 弱势市场：MA(7) < MA(25) AND MA25_slope < 0，趋势反转，进入下跌通道

    Attributes:
        short_period (int): 短期均线周期，默认7
        long_period (int): 长期均线周期，默认25

    Examples:
        >>> detector = MovingAverageCrossDetector()
        >>> result = detector.detect(klines=[...])  # 最近25根K线
        >>> if result['death_cross']:
        ...     print(f"死叉：MA(7)={result['ma7']} < MA(25)={result['ma25']}, "
        ...           f"MA25斜率={result['ma25_slope']}")

    Related:
        - PRD: F4.1 均线系统计算
        - Architecture: 检测器层 - MovingAverageCrossDetector
        - Task: TASK-002-015
    """

    def __init__(self, short_period: int = 7, long_period: int = 25):
        """初始化均线交叉检测器。

        Args:
            short_period: 短期均线周期（默认7）
            long_period: 长期均线周期（默认25）

        Examples:
            >>> detector = MovingAverageCrossDetector()
            >>> detector.short_period
            7
            >>> detector.long_period
            25
        """
        self.short_period = short_period
        self.long_period = long_period

    def detect(self, klines: List[KLine]) -> Dict:
        """检测均线死叉信号。

        计算MA(7)和MA(25)，判断是否发生死叉（短期均线下穿长期均线且长期均线斜率为负）。

        业务逻辑：
            1. 验证数据完整性（Guard Clauses）
            2. 计算MA(7)和MA(25)（使用pandas向量化）
            3. 计算MA(25)斜率
            4. 判断死叉：MA(7) < MA(25) AND MA25_slope < 0

        业务含义：
            - MA(7)：短期价格趋势
            - MA(25)：长期价格趋势
            - MA25_slope < 0：长期趋势本身也在恶化
            - 死叉：确认趋势反转，进入弱势区域

        Args:
            klines: K线列表，需要至少26根（long_period + 1，用于计算MA25斜率）

        Returns:
            Dict: 检测结果，包含以下键：
                - ma7 (Decimal): 当前MA(7)值
                - ma25 (Decimal): 当前MA(25)值
                - ma25_slope (Decimal): MA(25)斜率（%）
                - death_cross (bool): 是否发生死叉

        Raises:
            DataInsufficientError: 当K线数量 < long_period时
            InvalidDataError: 当MA25_prev=0时（除零错误）

        Side Effects:
            - 只读操作，无状态修改
            - 使用pandas进行向量化计算

        Examples:
            >>> detector = MovingAverageCrossDetector()
            >>> result = detector.detect(klines=[...])  # 25根K线
            >>> if result['death_cross']:
            ...     print(f"死叉确认：MA7={result['ma7']} < MA25={result['ma25']}")
            ...     print(f"MA25斜率：{result['ma25_slope']}%（下行趋势）")

        Context:
            - PRD Requirement: F4.1 均线系统计算
            - Architecture: 检测器层 - MovingAverageCrossDetector
            - Task: TASK-002-015

        Performance:
            - 使用pandas向量化计算，25根K线计算 < 5ms
        """
        # === Guard Clause 1: K线数量检查 ===
        # 需要至少 long_period + 1 根K线才能计算MA25的斜率
        # 原因：MA(25)需要25根K线，计算斜率需要MA25_prev，所以需要26根
        required_count = self.long_period + 1
        actual_count = len(klines)
        if actual_count < required_count:
            raise DataInsufficientError(
                required=required_count,
                actual=actual_count,
                symbol="N/A",  # MA分析不依赖特定symbol
                interval="N/A",
            )

        # === pandas向量化计算 ===
        # 原因：向量化计算比Python循环快100倍以上

        # 提取收盘价序列
        df = pd.DataFrame([{"close": float(k.close_price)} for k in klines])

        # 计算MA(7)和MA(25)
        df["ma7"] = df["close"].rolling(window=self.short_period).mean()
        df["ma25"] = df["close"].rolling(window=self.long_period).mean()

        # 获取当前MA值（最后一行）
        ma7_current = df["ma7"].iloc[-1]
        ma25_current = df["ma25"].iloc[-1]

        # 获取前一根K线的MA(25)，用于计算斜率
        ma25_prev = df["ma25"].iloc[-2]

        # === Guard Clause 2: MA25_prev=0或NaN检查（除零错误）===
        # 注意：pandas的rolling()在窗口不足时会返回NaN
        if pd.isna(ma25_prev):
            raise InvalidDataError(
                field="ma25_prev",
                value=float("nan"),
                context="MA25前值为NaN，数据不足（至少需要26根K线才能计算斜率）",
            )
        if ma25_prev == 0:
            raise InvalidDataError(
                field="ma25_prev", value=0.0, context="MA25前值为0，无法计算斜率（除零错误）"
            )

        # === 计算MA(25)斜率 ===
        # 斜率 = (MA25_current - MA25_prev) / MA25_prev × 100（单位：%）
        ma25_slope = ((ma25_current - ma25_prev) / ma25_prev) * 100

        # === 判断死叉 ===
        # 死叉条件：
        # 1. MA(7) < MA(25)：短期均线跌破长期均线
        # 2. MA25_slope < 0：长期均线本身也在下行
        death_cross = (ma7_current < ma25_current) and (ma25_slope < 0)

        return {
            "ma7": Decimal(str(round(ma7_current, 8))),
            "ma25": Decimal(str(round(ma25_current, 8))),
            "ma25_slope": Decimal(str(round(ma25_slope, 2))),  # 保留2位小数，单位：%
            "death_cross": death_cross,
        }
