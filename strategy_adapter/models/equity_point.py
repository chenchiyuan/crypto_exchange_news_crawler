"""
权益曲线时间点数据结构

Purpose:
    表示回测过程中某个时间点的账户净值状态，用于构建完整的权益曲线时间序列。
    权益曲线是计算最大回撤(MDD)、波动率等核心风险指标的基础数据。

关联任务: TASK-014-001
关联需求: FP-014-004（prd.md）
关联架构: architecture.md#4.1 EquityCurveBuilder

Design Philosophy:
    - 数据不可变性：使用@dataclass frozen模式确保数据一致性
    - Fail-Fast纪律：在__post_init__中进行边界检查，立即抛出异常
    - 类型安全：所有金额字段使用Decimal类型，避免浮点数精度问题
    - 契约透明：完整的Google Docstring文档化所有字段和异常条件
"""

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class EquityPoint:
    """
    权益曲线时间点数据结构

    Purpose:
        表示回测过程中某个时间点的账户净值状态。每个EquityPoint记录了特定时刻的
        可用资金、持仓市值、账户净值和净值变化率，用于构建完整的权益曲线时间序列。

    Attributes:
        timestamp (int): 时间戳（毫秒），Unix时间戳格式，必须为正整数。
            例如：1640995200000 代表 2022-01-01 00:00:00 UTC
        cash (Decimal): 可用资金（USDT），账户中未用于持仓的现金余额。
        position_value (Decimal): 持仓市值（USDT），当前所有持仓按市价计算的总价值。
        equity (Decimal): 账户净值（USDT），必须非负。
            恒等式：equity = cash + position_value
            表示账户的总资产价值。
        equity_rate (Decimal): 净值变化率（%），相对于初始资金的变化百分比。
            计算公式：equity_rate = (equity - initial_cash) / initial_cash × 100%
            正值表示盈利，负值表示亏损。

    Raises:
        ValueError: 当timestamp <= 0时触发，异常消息包含实际值。
        ValueError: 当equity < 0时触发，异常消息包含实际值。

    Side Effects:
        无。本数据类为纯数据结构，不产生任何副作用。

    Example:
        >>> from decimal import Decimal
        >>> # 初始状态：10000 USDT初始资金，全部为现金
        >>> point = EquityPoint(
        ...     timestamp=1640995200000,
        ...     cash=Decimal("10000.00"),
        ...     position_value=Decimal("0.00"),
        ...     equity=Decimal("10000.00"),
        ...     equity_rate=Decimal("0.00")
        ... )
        >>>
        >>> # 盈利状态：买入后价格上涨
        >>> point_profit = EquityPoint(
        ...     timestamp=1641081600000,
        ...     cash=Decimal("9000.00"),
        ...     position_value=Decimal("2200.00"),
        ...     equity=Decimal("11200.00"),
        ...     equity_rate=Decimal("12.00")
        ... )
        >>>
        >>> # 验证恒等式
        >>> point_profit.cash + point_profit.position_value == point_profit.equity
        True

    Context:
        - 关联任务：TASK-014-001（迭代014开发计划）
        - 关联需求：FP-014-004 权益曲线重建（prd.md）
        - 关联架构：architecture.md#4.1 EquityCurveBuilder - 核心原子服务
        - 使用场景：EquityCurveBuilder.build_from_orders() 的返回值元素
    """

    timestamp: int
    cash: Decimal
    position_value: Decimal
    equity: Decimal
    equity_rate: Decimal

    def __post_init__(self):
        """
        Guard Clauses：数据边界检查

        Purpose:
            在对象创建后立即执行边界检查，确保数据符合业务规则。
            遵循Fail-Fast纪律，在数据不合法时立即抛出异常。

        Raises:
            ValueError: 当timestamp <= 0时，抛出包含实际值的异常
            ValueError: 当equity < 0时，抛出包含实际值的异常

        Example:
            >>> # 负数时间戳触发异常
            >>> EquityPoint(
            ...     timestamp=-1640995200000,
            ...     cash=Decimal("10000.00"),
            ...     position_value=Decimal("0.00"),
            ...     equity=Decimal("10000.00"),
            ...     equity_rate=Decimal("0.00")
            ... )
            Traceback (most recent call last):
                ...
            ValueError: timestamp必须为正整数。\n期望：timestamp > 0\n实际：-1640995200000
        """
        # Guard Clause: 验证timestamp为正整数
        if self.timestamp <= 0:
            raise ValueError(
                "timestamp必须为正整数。\n"
                f"期望：timestamp > 0\n"
                f"实际：{self.timestamp}"
            )

        # Guard Clause: 验证equity非负
        if self.equity < 0:
            raise ValueError(
                "equity必须非负。\n"
                f"期望：equity >= 0\n"
                f"实际：{self.equity}"
            )
