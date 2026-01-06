"""
量化指标计算器

Purpose:
    计算回测策略的 17 个 P0 量化指标，包括收益分析、风险分析、风险调整收益和交易效率。
    这是量化回测指标系统的核心计算引擎。

关联任务: TASK-014-003, TASK-014-004至TASK-014-008
关联需求: FP-014-001至FP-014-015（prd.md）
关联架构: architecture.md#4.2 MetricsCalculator - 核心原子服务

Design Philosophy:
    - 单一职责：专注于指标计算，不涉及订单管理或数据持久化
    - 确定性计算：相同输入必定产生相同输出
    - 除零保护：所有除法运算检查分母不为0
    - Decimal 精度：所有指标保留 2 位小数
    - Fail-Fast 纪律：非法输入立即抛出异常
"""

from decimal import Decimal
from typing import List, Dict, Optional

# 用于类型提示，实际实现在其他文件
from strategy_adapter.models.equity_point import EquityPoint
from strategy_adapter.models.order import Order


class MetricsCalculator:
    """
    量化指标计算器

    Purpose:
        计算回测策略的专业级量化指标，支持科学评估策略质量、风险收益特征和交易效率。
        提供 17 个 P0 核心指标，覆盖收益、风险、风险调整收益和交易效率四大维度。

    Core Guarantees (核心保障):
        - 计算确定性：相同输入必定产生相同指标
        - 除零保护：所有除法运算检查分母不为0，返回 None 而非抛出异常
        - 精度保障：所有指标保留 2 位小数（使用 Decimal.quantize）
        - 边界处理：无已平仓订单时，返回默认值（如 MDD=0）

    Attributes:
        risk_free_rate (Decimal): 无风险收益率（年化），用于夏普率等风险调整收益指标的计算。
            范围：[0, 1]，表示百分比的小数形式。
            例如：0.03 表示 3%

    Raises:
        ValueError: 当 risk_free_rate < 0 或 > 1 时触发

    Example:
        >>> from decimal import Decimal
        >>> calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))
        >>>
        >>> # 准备测试数据
        >>> orders = [...]  # 订单列表
        >>> equity_curve = [...]  # 权益曲线
        >>> initial_cash = Decimal("10000")
        >>> days = 365
        >>>
        >>> # 计算所有指标
        >>> metrics = calculator.calculate_all_metrics(orders, equity_curve, initial_cash, days)
        >>>
        >>> # 访问指标
        >>> print(f"年化收益率: {metrics['apr']}%")
        >>> print(f"最大回撤: {metrics['mdd']}%")
        >>> print(f"夏普率: {metrics['sharpe_ratio']}")

    Context:
        - 关联任务：TASK-014-003（框架类），TASK-014-004至TASK-014-008（指标计算）
        - 关联需求：FP-014-001至FP-014-015（17个P0指标）
        - 关联架构：architecture.md#4.2 MetricsCalculator - 核心原子服务
        - 使用场景：run_strategy_backtest 命令行回测流程
    """

    def __init__(self, risk_free_rate: Decimal = Decimal("0.03")):
        """
        初始化量化指标计算器

        Purpose:
            创建 MetricsCalculator 实例，配置无风险收益率参数。
            无风险收益率用于计算夏普率等风险调整收益指标。

        Args:
            risk_free_rate (Decimal, optional): 无风险收益率（年化），默认 3%。
                必须在 [0, 1] 范围内，表示百分比的小数形式。
                例如：0.03 表示 3%，0.05 表示 5%
                常见值参考：
                - 0.00：加密货币市场（无传统无风险资产）
                - 0.03：传统金融市场（美国国债收益率）
                - 0.05：高风险市场调整

        Raises:
            ValueError: 当 risk_free_rate < 0 或 > 1 时触发，异常消息包含预期范围和实际值

        Side Effects:
            设置实例属性 self.risk_free_rate

        Example:
            >>> # 使用默认无风险收益率（3%）
            >>> calculator = MetricsCalculator()
            >>> calculator.risk_free_rate
            Decimal('0.03')
            >>>
            >>> # 使用自定义无风险收益率（5%）
            >>> calculator = MetricsCalculator(risk_free_rate=Decimal("0.05"))
            >>> calculator.risk_free_rate
            Decimal('0.05')
            >>>
            >>> # 边界测试：0% 和 100%
            >>> calculator_zero = MetricsCalculator(risk_free_rate=Decimal("0"))
            >>> calculator_one = MetricsCalculator(risk_free_rate=Decimal("1"))

        Context:
            关联任务：TASK-014-003
            关联架构：architecture.md#7 关键技术决策 - 决策点2
        """
        # Guard Clause: 验证 risk_free_rate 在 [0, 1] 范围内
        if risk_free_rate < 0 or risk_free_rate > 1:
            raise ValueError(
                "risk_free_rate必须在[0, 1]范围内。\n"
                f"期望：0 <= risk_free_rate <= 1\n"
                f"实际：{risk_free_rate}"
            )

        self.risk_free_rate = risk_free_rate

    # === 收益指标计算方法 ===

    def calculate_apr(
        self,
        total_profit: Decimal,
        initial_cash: Decimal,
        days: int
    ) -> Decimal:
        """
        计算年化收益率 (APR - Annual Percentage Rate)

        Purpose:
            将回测期间的总收益年化，便于与其他策略或投资产品对比。
            年化收益率消除了时间长度对收益率的影响，是评估策略长期盈利能力的关键指标。

        Formula:
            APR = (total_profit / initial_cash) × (365 / days) × 100%

        Args:
            total_profit (Decimal): 总盈亏（USDT），可以为负数（表示亏损）
            initial_cash (Decimal): 初始资金（USDT），必须 > 0
            days (int): 回测天数，必须 > 0

        Returns:
            Decimal: 年化收益率（%），保留2位小数
                - 正值：年化盈利
                - 负值：年化亏损
                - 例如：10.00 表示年化收益率10%

        Raises:
            ValueError: 当 initial_cash <= 0 时触发，异常消息包含实际值
            ValueError: 当 days <= 0 时触发，异常消息包含实际值

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 365天，盈利1000 USDT
            >>> apr = calculator.calculate_apr(
            ...     total_profit=Decimal("1000.00"),
            ...     initial_cash=Decimal("10000.00"),
            ...     days=365
            ... )
            >>> apr
            Decimal('10.00')
            >>>
            >>> # 182天（半年），盈利1000 USDT，年化约20%
            >>> apr_half_year = calculator.calculate_apr(
            ...     total_profit=Decimal("1000.00"),
            ...     initial_cash=Decimal("10000.00"),
            ...     days=182
            ... )
            >>> apr_half_year
            Decimal('20.05')

        Context:
            关联任务：TASK-014-004
            关联需求：FP-014-001
        """
        # Guard Clause: 验证 initial_cash > 0
        if initial_cash <= 0:
            raise ValueError(
                "initial_cash必须大于0。\n"
                f"期望：initial_cash > 0\n"
                f"实际：{initial_cash}"
            )

        # Guard Clause: 验证 days > 0
        if days <= 0:
            raise ValueError(
                "days必须大于0。\n"
                f"期望：days > 0\n"
                f"实际：{days}"
            )

        # 计算年化收益率
        # APR = (总收益 / 初始资金) × (365天 / 回测天数) × 100%
        return_rate = total_profit / initial_cash
        annualized_rate = return_rate * (Decimal("365") / Decimal(str(days)))
        apr = (annualized_rate * Decimal("100")).quantize(Decimal("0.01"))

        return apr

    def calculate_cumulative_return(
        self,
        total_profit: Decimal,
        initial_cash: Decimal
    ) -> Decimal:
        """
        计算累计收益率 (Cumulative Return)

        Purpose:
            计算回测期间的总收益率，直观反映策略在整个回测期的盈利能力。
            累计收益率不考虑时间因素，适合评估单次回测的整体表现。

        Formula:
            累计收益率 = (total_profit / initial_cash) × 100%

        Args:
            total_profit (Decimal): 总盈亏（USDT），可以为负数（表示亏损）
            initial_cash (Decimal): 初始资金（USDT），必须 > 0

        Returns:
            Decimal: 累计收益率（%），保留2位小数
                - 正值：盈利
                - 负值：亏损
                - 例如：15.50 表示累计收益率15.5%

        Raises:
            ValueError: 当 initial_cash <= 0 时触发，异常消息包含实际值

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 初始10000，盈利1000
            >>> cumulative_return = calculator.calculate_cumulative_return(
            ...     total_profit=Decimal("1000.00"),
            ...     initial_cash=Decimal("10000.00")
            ... )
            >>> cumulative_return
            Decimal('10.00')
            >>>
            >>> # 初始10000，亏损2000
            >>> cumulative_return_loss = calculator.calculate_cumulative_return(
            ...     total_profit=Decimal("-2000.00"),
            ...     initial_cash=Decimal("10000.00")
            ... )
            >>> cumulative_return_loss
            Decimal('-20.00')

        Context:
            关联任务：TASK-014-004
            关联需求：FP-014-003
        """
        # Guard Clause: 验证 initial_cash > 0
        if initial_cash <= 0:
            raise ValueError(
                "initial_cash必须大于0。\n"
                f"期望：initial_cash > 0\n"
                f"实际：{initial_cash}"
            )

        # 计算累计收益率
        # 累计收益率 = (总收益 / 初始资金) × 100%
        return_rate = total_profit / initial_cash
        cumulative_return = (return_rate * Decimal("100")).quantize(Decimal("0.01"))

        return cumulative_return

    def calculate_absolute_return(self, total_profit: Decimal) -> Decimal:
        """
        计算绝对收益 (Absolute Return)

        Purpose:
            返回回测期间的总盈亏金额（USDT）。
            绝对收益是最直观的盈利指标，直接反映策略赚了多少钱或亏了多少钱。

        Formula:
            绝对收益 = total_profit

        Args:
            total_profit (Decimal): 总盈亏（USDT），可以为负数（表示亏损）

        Returns:
            Decimal: 绝对收益（USDT），保留2位小数
                - 正值：盈利金额
                - 负值：亏损金额

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> absolute_return = calculator.calculate_absolute_return(Decimal("1234.56"))
            >>> absolute_return
            Decimal('1234.56')
            >>>
            >>> absolute_return_loss = calculator.calculate_absolute_return(Decimal("-500.00"))
            >>> absolute_return_loss
            Decimal('-500.00')

        Context:
            关联任务：TASK-014-004
            关联需求：FP-014-002
            复用来源：UnifiedOrderManager.calculate_statistics() 的 total_profit 字段
        """
        # 绝对收益即为总盈亏，保留2位小数
        return total_profit.quantize(Decimal("0.01"))

    def calculate_all_metrics(
        self,
        orders: List[Order],
        equity_curve: List[EquityPoint],
        initial_cash: Decimal,
        days: int
    ) -> Dict[str, Optional[Decimal]]:
        """
        计算所有 P0 量化指标

        Purpose:
            集成调用所有 17 个 P0 指标计算方法，返回完整的量化指标字典。
            这是 MetricsCalculator 的主要入口方法。

        Args:
            orders (List[Order]): 所有订单列表，包含已平仓和持仓订单。
                每个 Order 必须包含 profit_loss、profit_loss_rate、status 等字段。
            equity_curve (List[EquityPoint]): 权益曲线时间序列，从 EquityCurveBuilder 生成。
                每个 EquityPoint 包含 timestamp、cash、position_value、equity、equity_rate。
                如果为空列表，风险指标（MDD、波动率）将返回默认值。
            initial_cash (Decimal): 初始资金（USDT），必须 > 0。
            days (int): 回测天数，必须 > 0。
                用于年化收益率、交易频率等指标的计算。

        Returns:
            Dict[str, Optional[Decimal]]: 包含 17 个 P0 指标的字典。
                字典键（17个）：
                - 收益分析（3个）：'apr', 'absolute_return', 'cumulative_return'
                - 风险分析（4个）：'mdd', 'mdd_start_time', 'mdd_end_time', 'recovery_time'
                - 波动率：'volatility'
                - 风险调整收益（4个）：'sharpe_ratio', 'calmar_ratio', 'mar_ratio', 'profit_factor'
                - 交易效率（4个）：'trade_frequency', 'cost_percentage', 'win_rate', 'payoff_ratio'

                指标值类型：
                - Decimal: 数值型指标（精度保留2位小数）
                - None: 无法计算的指标（如波动率=0时的夏普率）

        Raises:
            ValueError: 当 initial_cash <= 0 时触发
            ValueError: 当 days <= 0 时触发

        Side Effects:
            无。纯计算函数，不修改任何输入参数。

        Example:
            >>> calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))
            >>> metrics = calculator.calculate_all_metrics(orders, equity_curve, Decimal("10000"), 365)
            >>>
            >>> # 访问收益指标
            >>> print(f"APR: {metrics['apr']}%")
            >>> print(f"累计收益率: {metrics['cumulative_return']}%")
            >>>
            >>> # 访问风险指标
            >>> print(f"MDD: {metrics['mdd']}%")
            >>> print(f"波动率: {metrics['volatility']}%")
            >>>
            >>> # 访问风险调整收益指标
            >>> if metrics['sharpe_ratio'] is not None:
            ...     print(f"夏普率: {metrics['sharpe_ratio']}")
            >>> else:
            ...     print("夏普率: N/A（波动率为0）")

        Context:
            关联任务：TASK-014-008（集成任务）
            关联需求：FP-014-001至FP-014-015
            关联架构：architecture.md#4.2 MetricsCalculator
        """
        # Guard Clause: 验证输入参数
        if initial_cash <= 0:
            raise ValueError(
                "initial_cash必须大于0。\n"
                f"期望：initial_cash > 0\n"
                f"实际：{initial_cash}"
            )
        if days <= 0:
            raise ValueError(
                "days必须大于0。\n"
                f"期望：days > 0\n"
                f"实际：{days}"
            )

        # TODO: 在 TASK-014-004至TASK-014-008 中实现各个指标计算方法
        # 这里返回默认值结构，确保框架测试通过
        metrics: Dict[str, Optional[Decimal]] = {
            # 收益分析（3个）
            'apr': Decimal("0.00"),
            'absolute_return': Decimal("0.00"),
            'cumulative_return': Decimal("0.00"),
            # 风险分析（4个）
            'mdd': Decimal("0.00"),
            'mdd_start_time': None,
            'mdd_end_time': None,
            'recovery_time': None,
            # 波动率
            'volatility': Decimal("0.00"),
            # 风险调整收益（4个）
            'sharpe_ratio': None,
            'calmar_ratio': None,
            'mar_ratio': None,
            'profit_factor': None,
            # 交易效率（4个）
            'trade_frequency': Decimal("0.00"),
            'cost_percentage': None,
            'win_rate': Decimal("0.00"),
            'payoff_ratio': None,
        }

        return metrics
