"""
信号转换器

本模块实现信号转换器SignalConverter，负责将应用层信号（List[Dict]）转换为
vectorbt回测引擎所需的格式（pd.Series）。

核心功能：
- 信号格式转换：List[Dict] → pd.Series（布尔序列）
- 时间对齐：精确匹配策略（Exact Match），严格验证数据一致性
- 信号验证：确保所有信号时间戳都在K线数据范围内

设计决策：
采用精确匹配策略（architecture.md 决策点二），而非最近邻匹配：
- 优点：最安全，不会出现时间对齐错误；强制数据一致性；O(1)哈希查找性能
- 缺点：对数据质量要求极高；K线缺失时会立即失败
- 理由：问题暴露优于问题隐藏，数据缺失应立即修复而非被容错机制掩盖

迭代编号: 013 (策略适配层)
创建日期: 2026-01-06
关联任务: TASK-013-006
关联需求: FP-013-006 (prd.md)
关联架构: architecture.md#4.3 核心组件模块 + 决策点二
"""

from typing import Dict, List, Tuple
import pandas as pd


class SignalConverter:
    """
    信号转换器（静态方法）

    职责：
    - 将应用层信号列表转换为vectorbt格式的pd.Series
    - 处理时间对齐（毫秒时间戳 → pd.Timestamp）
    - 验证信号有效性（时间戳必须在K线范围内）

    Example:
        >>> klines = pd.DataFrame({'open': [2300, 2310], 'close': [2310, 2320]},
        ...     index=pd.DatetimeIndex(['2026-01-06 00:00', '2026-01-06 04:00'], tz='UTC'))
        >>> buy_signals = [{'timestamp': 1736164800000, 'price': 2300}]
        >>> entries, exits = SignalConverter.to_vectorbt_signals(buy_signals, [], klines)
        >>> print(entries.sum())  # 1 (一个买入信号)
    """

    @staticmethod
    def to_vectorbt_signals(
        buy_signals: List[Dict],
        sell_signals: List[Dict],
        klines: pd.DataFrame
    ) -> Tuple[pd.Series, pd.Series]:
        """
        转换为vectorbt信号（精确匹配策略）

        采用精确匹配策略：对每个信号时间戳，在K线DataFrame中查找完全匹配的index。
        如果找不到精确匹配，立即抛出异常（Fail-Fast原则）。

        Args:
            buy_signals (List[Dict]): 买入信号列表
                每个信号格式：{'timestamp': int, 'price': Decimal/float, ...}
                timestamp为毫秒时间戳
            sell_signals (List[Dict]): 卖出信号列表
                每个信号格式：{'timestamp': int, 'price': Decimal/float, ...}
            klines (pd.DataFrame): K线DataFrame
                index必须为pd.DatetimeIndex（带时区信息，如UTC）

        Returns:
            Tuple[pd.Series, pd.Series]: (entries, exits)
                - entries: 买入信号序列（布尔值，True表示买入）
                - exits: 卖出信号序列（布尔值，True表示卖出）
                两个序列的index与klines.index完全一致

        Raises:
            ValueError: 当信号时间戳在K线数据中不存在时抛出
                错误信息包含：
                - 不存在的时间戳值
                - 可用时间范围（klines的首尾时间）
                - 修复建议（检查数据完整性、运行update_klines命令）
            TypeError: 当klines.index不是pd.DatetimeIndex时抛出

        Example:
            >>> # 正常情况
            >>> klines = pd.DataFrame({
            ...     'open': [2300, 2310, 2320],
            ...     'close': [2310, 2320, 2330]
            ... }, index=pd.DatetimeIndex([
            ...     '2026-01-06 00:00:00',
            ...     '2026-01-06 04:00:00',
            ...     '2026-01-06 08:00:00'
            ... ], tz='UTC'))
            >>> buy_signals = [{
            ...     'timestamp': int(pd.Timestamp('2026-01-06 04:00:00', tz='UTC').timestamp() * 1000),
            ...     'price': 2310
            ... }]
            >>> entries, exits = SignalConverter.to_vectorbt_signals(buy_signals, [], klines)
            >>> print(entries.tolist())  # [False, True, False]

            >>> # 异常情况：时间戳不存在
            >>> bad_signals = [{'timestamp': 9999999999999, 'price': 2310}]
            >>> SignalConverter.to_vectorbt_signals(bad_signals, [], klines)
            Traceback (most recent call last):
                ...
            ValueError: 买入信号时间 ... 在K线数据中不存在。请检查...
        """
        # Guard Clause: 验证klines.index类型
        if not isinstance(klines.index, pd.DatetimeIndex):
            raise TypeError(
                f"klines.index必须为pd.DatetimeIndex类型，当前为: {type(klines.index).__name__}。"
                f"请确保K线数据的index已转换为DatetimeIndex格式。"
            )

        kline_index = klines.index

        # 初始化信号序列（全False）
        entries = pd.Series(False, index=kline_index, dtype=bool)
        exits = pd.Series(False, index=kline_index, dtype=bool)

        # 转换买入信号（精确匹配）
        for signal in buy_signals:
            # 将毫秒时间戳转换为pd.Timestamp（UTC时区）
            signal_time = pd.Timestamp(signal['timestamp'], unit='ms', tz='UTC')

            # Guard Clause: 精确匹配检查（Fail-Fast）
            if signal_time not in kline_index:
                raise ValueError(
                    f"买入信号时间 {signal_time} 在K线数据中不存在。\\n"
                    f"请检查：\\n"
                    f"  1) K线数据是否完整（运行 update_klines 命令）\\n"
                    f"  2) 信号时间戳是否正确\\n"
                    f"可用时间范围: {kline_index[0]} ~ {kline_index[-1]}\\n"
                    f"信号时间戳（毫秒）: {signal['timestamp']}"
                )

            # 精确匹配成功，设置买入信号
            entries.loc[signal_time] = True

        # 转换卖出信号（精确匹配）
        for signal in sell_signals:
            signal_time = pd.Timestamp(signal['timestamp'], unit='ms', tz='UTC')

            # Guard Clause: 精确匹配检查（Fail-Fast）
            if signal_time not in kline_index:
                raise ValueError(
                    f"卖出信号时间 {signal_time} 在K线数据中不存在。\\n"
                    f"请检查：\\n"
                    f"  1) K线数据是否完整（运行 update_klines 命令）\\n"
                    f"  2) 信号时间戳是否正确\\n"
                    f"可用时间范围: {kline_index[0]} ~ {kline_index[-1]}\\n"
                    f"信号时间戳（毫秒）: {signal['timestamp']}"
                )

            # 精确匹配成功，设置卖出信号
            exits.loc[signal_time] = True

        return entries, exits
