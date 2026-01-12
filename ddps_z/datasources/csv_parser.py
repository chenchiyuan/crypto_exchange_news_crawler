"""
CSV文件解析器

解析币安标准12列K线CSV格式，转换为StandardKLine列表。

Related:
    - Architecture: docs/iterations/025-csv-datasource/architecture.md
    - TASK: TASK-025-001, TASK-025-002
"""

import logging
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

from ddps_z.models import StandardKLine

logger = logging.getLogger(__name__)


class CSVParser:
    """
    CSV文件解析器

    负责解析币安标准12列K线CSV格式，转换为StandardKLine列表。

    CSV格式（无表头）:
    [0] open_time (微秒/毫秒，取决于timestamp_unit配置)
    [1] open
    [2] high
    [3] low
    [4] close
    [5] volume
    [6] close_time
    [7] quote_volume
    [8] trades
    [9] taker_buy_volume
    [10] taker_buy_quote_volume
    [11] ignore

    Attributes:
        timestamp_unit: 时间戳单位 ('microseconds', 'milliseconds', 'seconds')

    Example:
        >>> parser = CSVParser(timestamp_unit='microseconds')
        >>> klines = parser.parse('/path/to/ETHUSDT-1s-2025-12.csv')
        >>> len(klines)
        2680000
    """

    COLUMN_MAPPING = {
        'timestamp': 0,
        'open': 1,
        'high': 2,
        'low': 3,
        'close': 4,
        'volume': 5
    }

    def __init__(self, timestamp_unit: str = 'microseconds'):
        """
        初始化解析器

        Args:
            timestamp_unit: 时间戳单位
                - 'microseconds': 微秒，需除以1000转毫秒
                - 'milliseconds': 毫秒，无需转换
                - 'seconds': 秒，需乘以1000转毫秒
        """
        self.timestamp_unit = timestamp_unit
        self._divisor = self._get_divisor()

    def _get_divisor(self) -> float:
        """获取时间戳转换除数"""
        divisors = {
            'microseconds': 1000.0,    # 微秒 → 毫秒
            'milliseconds': 1.0,       # 毫秒 → 毫秒
            'seconds': 0.001           # 秒 → 毫秒 (实际是乘法)
        }
        return divisors.get(self.timestamp_unit, 1000.0)

    def parse(self, csv_path: str) -> List[StandardKLine]:
        """
        解析CSV文件，返回StandardKLine列表

        使用numpy向量化操作优化性能。

        Args:
            csv_path: CSV文件绝对路径

        Returns:
            List[StandardKLine]: 时间正序排列的K线列表

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 解析失败
        """
        # 1. 验证文件存在
        path = Path(csv_path)
        if not path.exists():
            raise FileNotFoundError(f"CSV文件不存在: {csv_path}")

        logger.info(f"开始解析CSV文件: {csv_path}")

        # 2. 读取CSV（无表头，只读取需要的列）
        usecols = [0, 1, 2, 3, 4, 5]
        df = pd.read_csv(csv_path, header=None, usecols=usecols)

        logger.info(f"CSV文件读取完成，共 {len(df)} 行")

        # 3. 向量化转换时间戳
        if self.timestamp_unit == 'seconds':
            # 秒转毫秒需要乘法
            timestamps = (df[0].values * 1000).astype(np.int64)
        else:
            # 微秒/毫秒转毫秒需要除法
            timestamps = (df[0].values // self._divisor).astype(np.int64)

        # 4. 提取OHLCV数据
        opens = df[1].values.astype(np.float64)
        highs = df[2].values.astype(np.float64)
        lows = df[3].values.astype(np.float64)
        closes = df[4].values.astype(np.float64)
        volumes = df[5].values.astype(np.float64)

        # 5. 批量创建StandardKLine（使用列表推导优化）
        klines = [
            StandardKLine(
                timestamp=int(timestamps[i]),
                open=float(opens[i]),
                high=float(highs[i]),
                low=float(lows[i]),
                close=float(closes[i]),
                volume=float(volumes[i])
            )
            for i in range(len(df))
        ]

        logger.info(f"CSV解析完成，生成 {len(klines)} 根K线")

        return klines
