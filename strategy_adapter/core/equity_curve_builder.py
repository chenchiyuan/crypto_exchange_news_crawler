"""
权益曲线重建工具类

Purpose:
    从订单历史和K线数据重建回测过程中的账户净值时间序列（权益曲线）。
    权益曲线是计算最大回撤(MDD)、波动率、夏普率等核心风险指标的基础数据。

关联任务: TASK-014-002
关联需求: FP-014-004（prd.md）
关联架构: architecture.md#4.1 EquityCurveBuilder - 核心原子服务

Design Philosophy:
    - 确定性计算：相同输入必定产生相同的权益曲线
    - Fail-Fast纪律：非法输入立即抛出异常
    - Decimal精度：所有金额计算使用Decimal类型
    - 静态方法设计：无状态工具类，便于独立调用
"""

from decimal import Decimal
from typing import List
import pandas as pd

from strategy_adapter.models.equity_point import EquityPoint
from strategy_adapter.models.order import Order, OrderStatus


class EquityCurveBuilder:
    """
    权益曲线重建工具类

    Purpose:
        从订单历史和K线数据重建回测过程中的账户净值时间序列。
        采用静态方法设计，提供无状态的工具函数，支持权益曲线的确定性重建。

    Core Algorithm:
        1. 遍历每根K线的时间点
        2. 计算该时间点的可用资金（cash）
        3. 计算该时间点的持仓市值（position_value）
        4. 计算账户净值（equity = cash + position_value）
        5. 计算净值变化率（equity_rate）

    Context:
        - 关联任务：TASK-014-002（迭代014开发计划）
        - 关联需求：FP-014-004 权益曲线重建（prd.md）
        - 关联架构：architecture.md#4.1 EquityCurveBuilder - 核心原子服务
        - 使用场景：run_strategy_backtest 命令行回测流程，MetricsCalculator依赖
    """

    @staticmethod
    def build_from_orders(
        orders: List[Order],
        klines: pd.DataFrame,
        initial_cash: Decimal
    ) -> List[EquityPoint]:
        """
        从订单列表和K线数据重建权益曲线

        Purpose:
            根据回测过程中的订单历史和K线数据，重建每个时间点的账户净值状态。
            返回的权益曲线时间序列可用于计算MDD、波动率等核心风险指标。

        Algorithm:
            对于每根K线的时间点t：
            1. 计算可用资金 cash(t)：
               - 初始资金
               - 减去所有在t时刻及之前买入的订单的本金和手续费
               - 加上所有在t时刻及之前卖出的订单的回款
            2. 计算持仓市值 position_value(t)：
               - 所有在t时刻持仓的订单，按K线close价格计算市值
            3. 计算账户净值 equity(t) = cash(t) + position_value(t)
            4. 计算净值变化率 equity_rate(t) = (equity(t) - initial_cash) / initial_cash × 100%

        Args:
            orders (List[Order]): 订单列表，包含已平仓和持仓订单。
                每个Order必须包含buy_timestamp、sell_timestamp、buy_price等字段。
            klines (pd.DataFrame): K线数据，必须包含以下列：
                - 'open_time' (int): K线开盘时间戳（毫秒）
                - 'close' (float): K线收盘价
            initial_cash (Decimal): 初始资金（USDT），必须 > 0。

        Returns:
            List[EquityPoint]: 权益曲线时间序列，长度等于K线数量。
                每个EquityPoint包含timestamp、cash、position_value、equity、equity_rate字段。
                权益曲线按时间戳升序排列。

        Raises:
            ValueError: 当 initial_cash <= 0 时触发，异常消息包含实际值。
            ValueError: 当 klines 为空 DataFrame 时触发。
            ValueError: 当 klines 缺少必需列时触发，异常消息包含缺失的列名。

        Side Effects:
            无。纯计算函数，不修改任何输入参数。

        Example:
            >>> from decimal import Decimal
            >>> import pandas as pd
            >>> from strategy_adapter.models.order import Order
            >>> from strategy_adapter.models.enums import OrderStatus, OrderSide
            >>>
            >>> # 准备K线数据
            >>> klines = pd.DataFrame({
            ...     'open_time': [1640995200000, 1641081600000],
            ...     'close': [47500.0, 48000.0]
            ... })
            >>>
            >>> # 准备订单
            >>> order = Order(
            ...     id="TEST-001",
            ...     symbol="BTCUSDT",
            ...     side=OrderSide.BUY,
            ...     status=OrderStatus.CLOSED,
            ...     open_price=Decimal("47000.00"),
            ...     open_timestamp=1640995200000,
            ...     close_price=Decimal("48000.00"),
            ...     close_timestamp=1641081600000,
            ...     quantity=Decimal("0.2"),
            ...     position_value=Decimal("9400.00"),
            ...     open_commission=Decimal("9.40"),
            ...     close_commission=Decimal("9.40"),
            ...     profit_loss=Decimal("181.20")
            ... )
            >>>
            >>> # 重建权益曲线
            >>> equity_curve = EquityCurveBuilder.build_from_orders(
            ...     orders=[order],
            ...     klines=klines,
            ...     initial_cash=Decimal("10000.00")
            ... )
            >>>
            >>> # 验证结果
            >>> len(equity_curve)
            2
            >>> equity_curve[0].equity  # 第一个点：买入后
            Decimal('10000.00')
            >>> equity_curve[1].equity  # 第二个点：卖出后
            Decimal('10181.20')

        Context:
            关联任务：TASK-014-002
            关联架构：architecture.md#4.1 EquityCurveBuilder
        """
        # === Guard Clauses: 输入参数验证 ===

        # Guard Clause 1: 验证 initial_cash > 0
        if initial_cash <= 0:
            raise ValueError(
                "initial_cash必须大于0。\n"
                f"期望：initial_cash > 0\n"
                f"实际：{initial_cash}"
            )

        # Guard Clause 2: 验证 klines 非空
        if klines.empty:
            raise ValueError(
                "klines不能为空。\n"
                f"期望：klines包含至少1行数据\n"
                f"实际：klines行数为0"
            )

        # Guard Clause 3: 验证 klines 包含必需列
        required_columns = ['open_time', 'close']
        missing_columns = [col for col in required_columns if col not in klines.columns]
        if missing_columns:
            raise ValueError(
                "klines缺少必需列。\n"
                f"期望列：{required_columns}\n"
                f"缺失列：{missing_columns}\n"
                f"实际列：{list(klines.columns)}"
            )

        # === 步骤1: 初始化权益曲线列表 ===
        equity_curve: List[EquityPoint] = []

        # === 步骤2: 遍历每根K线，计算该时间点的账户净值 ===
        for _, kline in klines.iterrows():
            timestamp = int(kline['open_time'])
            close_price = Decimal(str(kline['close']))

            # === 步骤3: 计算可用资金（cash） ===
            # 🆕 Bug-019修复：区分做多和做空订单的资金流
            # 修复前：做多做空使用相同逻辑，导致做空资金流错误
            # 修复后：根据direction字段区分处理
            cash = initial_cash

            for order in orders:
                # 🆕 区分做多和做空的资金流
                if order.direction == 'long':
                    # 做多：开仓时扣除本金
                    if order.open_timestamp <= timestamp:
                        cash -= order.position_value
                        cash -= order.open_commission

                    # 做多：平仓时加上卖出回款
                    if order.status == OrderStatus.CLOSED and order.close_timestamp <= timestamp:
                        sell_revenue = order.close_price * order.quantity
                        cash += sell_revenue
                        cash -= order.close_commission

                elif order.direction == 'short':
                    # 🆕 做空：开仓时获得卖出回款（做空是先卖后买）
                    if order.open_timestamp <= timestamp:
                        sell_revenue = order.open_price * order.quantity
                        cash += sell_revenue
                        cash -= order.open_commission

                    # 🆕 做空：平仓时扣除买入成本（平仓时需要买回币归还）
                    if order.status == OrderStatus.CLOSED and order.close_timestamp <= timestamp:
                        buy_cost = order.close_price * order.quantity
                        cash -= buy_cost
                        cash -= order.close_commission

            # === 步骤4: 计算持仓市值（position_value） ===
            # 🆕 Bug-019修复：做空持仓为负债（负值）
            position_value = Decimal("0")

            for order in orders:
                # 在当前时间点持仓的订单
                is_bought = order.open_timestamp <= timestamp
                is_not_sold = (order.status == OrderStatus.FILLED) or \
                              (order.status == OrderStatus.CLOSED and order.close_timestamp > timestamp)

                if is_bought and is_not_sold:
                    if order.direction == 'long':
                        # 做多持仓：资产（正值）
                        position_value += close_price * order.quantity
                    elif order.direction == 'short':
                        # 🆕 做空持仓：负债（负值）
                        # 做空持仓需要归还币，当前价格越高，负债越大
                        position_value -= close_price * order.quantity

            # === 步骤5: 计算账户净值（equity） ===
            equity = cash + position_value

            # === 步骤6: 计算净值变化率（equity_rate） ===
            equity_rate = ((equity - initial_cash) / initial_cash * Decimal("100")).quantize(Decimal("0.01"))

            # === 步骤7: 创建EquityPoint并添加到权益曲线 ===
            equity_point = EquityPoint(
                timestamp=timestamp,
                cash=cash.quantize(Decimal("0.01")),
                position_value=position_value.quantize(Decimal("0.01")),
                equity=equity.quantize(Decimal("0.01")),
                equity_rate=equity_rate
            )
            equity_curve.append(equity_point)

        # === 步骤8: 返回权益曲线 ===
        return equity_curve
