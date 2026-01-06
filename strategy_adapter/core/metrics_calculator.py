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
from strategy_adapter.models.order import Order, OrderStatus


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

    # === 风险指标计算方法 ===

    def calculate_mdd(
        self,
        equity_curve: List[EquityPoint]
    ) -> Dict[str, Optional[Decimal]]:
        """
        计算最大回撤 (MDD - Maximum Drawdown) 及相关指标

        Purpose:
            计算回测期间的最大回撤幅度、回撤时间区间和恢复时间。
            最大回撤是衡量策略风险的核心指标，反映策略在最坏情况下的损失程度。

        Algorithm:
            1. 遍历权益曲线，维护历史最高净值（peak）
            2. 对每个时间点，计算当前回撤 = (当前净值 - peak) / peak
            3. 记录最大回撤及其发生的时间区间
            4. 检测是否已恢复到峰值（recovery_time）

        Args:
            equity_curve (List[EquityPoint]): 权益曲线时间序列，从 EquityCurveBuilder 生成。
                - 空列表：返回默认值（优雅降级）
                - 单点：MDD=0
                - 多点：正常计算

        Returns:
            Dict[str, Optional[Decimal]]: 包含4个字段的字典
                - 'mdd' (Decimal): 最大回撤（%），保留2位小数
                    - 负值：表示回撤幅度（如-10.00表示10%回撤）
                    - 0.00：无回撤
                - 'mdd_start_time' (int|None): 回撤开始时间戳（峰值时间），毫秒
                - 'mdd_end_time' (int|None): 回撤结束时间戳（谷底时间），毫秒
                - 'recovery_time' (int|None): 恢复时间戳（回到峰值的时间），毫秒
                    - None：未恢复或无回撤

        Side Effects:
            无。纯计算函数，不修改任何输入参数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 构建权益曲线：10000 → 11000 → 9000 → 10500
            >>> equity_curve = [
            ...     EquityPoint(timestamp=1, cash=Decimal("10000"), position_value=Decimal("0"), equity=Decimal("10000"), equity_rate=Decimal("0")),
            ...     EquityPoint(timestamp=2, cash=Decimal("11000"), position_value=Decimal("0"), equity=Decimal("11000"), equity_rate=Decimal("10")),
            ...     EquityPoint(timestamp=3, cash=Decimal("9000"), position_value=Decimal("0"), equity=Decimal("9000"), equity_rate=Decimal("-10")),
            ...     EquityPoint(timestamp=4, cash=Decimal("10500"), position_value=Decimal("0"), equity=Decimal("10500"), equity_rate=Decimal("5")),
            ... ]
            >>> mdd_result = calculator.calculate_mdd(equity_curve)
            >>> mdd_result['mdd']
            Decimal('-18.18')  # (9000-11000)/11000
            >>> mdd_result['mdd_start_time']
            2
            >>> mdd_result['mdd_end_time']
            3
            >>> mdd_result['recovery_time']
            None  # 未恢复到11000

        Context:
            关联任务：TASK-014-005
            关联需求：FP-014-005, FP-014-006
        """
        # === Guard Clause: 空权益曲线，优雅降级 ===
        if not equity_curve:
            return {
                'mdd': Decimal("0.00"),
                'mdd_start_time': None,
                'mdd_end_time': None,
                'recovery_time': None,
            }

        # === Guard Clause: 单点权益曲线，无法计算回撤 ===
        if len(equity_curve) == 1:
            return {
                'mdd': Decimal("0.00"),
                'mdd_start_time': None,
                'mdd_end_time': None,
                'recovery_time': None,
            }

        # === 步骤1: 初始化变量 ===
        peak_equity = equity_curve[0].equity  # 历史最高净值
        peak_timestamp = equity_curve[0].timestamp  # 峰值时间戳

        max_drawdown = Decimal("0")  # 最大回撤幅度（负值）
        mdd_start_time = None  # 最大回撤开始时间（峰值）
        mdd_end_time = None  # 最大回撤结束时间（谷底）
        recovery_time = None  # 恢复时间

        current_peak_equity = equity_curve[0].equity
        current_peak_timestamp = equity_curve[0].timestamp

        # === 步骤2: 遍历权益曲线，计算最大回撤 ===
        for point in equity_curve[1:]:
            # 更新历史最高净值
            if point.equity > current_peak_equity:
                current_peak_equity = point.equity
                current_peak_timestamp = point.timestamp

            # 计算当前回撤
            if current_peak_equity > 0:
                current_drawdown = ((point.equity - current_peak_equity) / current_peak_equity * Decimal("100")).quantize(Decimal("0.01"))

                # 更新最大回撤
                if current_drawdown < max_drawdown:
                    max_drawdown = current_drawdown
                    mdd_start_time = current_peak_timestamp
                    mdd_end_time = point.timestamp

        # === 步骤3: 检测恢复时间 ===
        if mdd_start_time is not None and mdd_end_time is not None:
            # 找到谷底对应的峰值净值
            peak_value = None
            for point in equity_curve:
                if point.timestamp == mdd_start_time:
                    peak_value = point.equity
                    break

            # 从谷底之后查找是否恢复到峰值
            found_trough = False
            for point in equity_curve:
                if point.timestamp == mdd_end_time:
                    found_trough = True
                    continue

                if found_trough and peak_value is not None:
                    if point.equity >= peak_value:
                        recovery_time = point.timestamp
                        break

        # === 步骤4: 返回结果 ===
        return {
            'mdd': max_drawdown,
            'mdd_start_time': mdd_start_time,
            'mdd_end_time': mdd_end_time,
            'recovery_time': recovery_time,
        }

    def calculate_volatility(self, equity_curve: List[EquityPoint]) -> Decimal:
        """
        计算年化波动率 (Annualized Volatility)

        Purpose:
            计算回测期间的收益率波动率，反映策略收益的稳定性。
            波动率越低，策略收益越稳定；波动率越高，策略风险越大。

        Formula:
            年化波动率 = std(daily_returns) × sqrt(252)

            其中：
            - daily_returns: 每日收益率序列 = (equity[i] - equity[i-1]) / equity[i-1]
            - std: 标准差
            - 252: 一年的交易日数（加密货币市场全年无休，实际为365）

        Args:
            equity_curve (List[EquityPoint]): 权益曲线时间序列
                - 空列表：返回 0.00%（优雅降级）
                - 长度 < 2：返回 0.00%（无法计算收益率）
                - 长度 >= 2：正常计算

        Returns:
            Decimal: 年化波动率（%），保留2位小数
                - 0.00：无波动或数据不足
                - 正值：波动率（如15.50表示15.5%年化波动率）

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 构建权益曲线：10000 → 11000 (+10%) → 10500 (-4.55%)
            >>> equity_curve = [
            ...     EquityPoint(timestamp=1, cash=Decimal("10000"), position_value=Decimal("0"), equity=Decimal("10000"), equity_rate=Decimal("0")),
            ...     EquityPoint(timestamp=2, cash=Decimal("11000"), position_value=Decimal("0"), equity=Decimal("11000"), equity_rate=Decimal("10")),
            ...     EquityPoint(timestamp=3, cash=Decimal("10500"), position_value=Decimal("0"), equity=Decimal("10500"), equity_rate=Decimal("5")),
            ... ]
            >>> volatility = calculator.calculate_volatility(equity_curve)
            >>> volatility > Decimal("0.00")
            True

        Context:
            关联任务：TASK-014-005
            关联需求：FP-014-007
        """
        # === Guard Clause: 空权益曲线或单点，优雅降级 ===
        if not equity_curve or len(equity_curve) < 2:
            return Decimal("0.00")

        # === 步骤1: 计算每日收益率序列 ===
        daily_returns = []
        for i in range(1, len(equity_curve)):
            prev_equity = equity_curve[i - 1].equity
            curr_equity = equity_curve[i].equity

            # 除零保护
            if prev_equity > 0:
                daily_return = (curr_equity - prev_equity) / prev_equity
                daily_returns.append(daily_return)

        # === Guard Clause: 收益率序列为空或只有一个点，无法计算标准差 ===
        if len(daily_returns) < 2:
            return Decimal("0.00")

        # === 步骤2: 计算收益率标准差 ===
        # 计算平均收益率
        mean_return = sum(daily_returns) / Decimal(str(len(daily_returns)))

        # 计算方差
        variance = sum((r - mean_return) ** 2 for r in daily_returns) / Decimal(str(len(daily_returns) - 1))

        # 计算标准差
        import math
        std_dev = Decimal(str(math.sqrt(float(variance))))

        # === 步骤3: 年化波动率 ===
        # 使用252个交易日（传统金融市场标准）
        annualized_volatility = (std_dev * Decimal(str(math.sqrt(252))) * Decimal("100")).quantize(Decimal("0.01"))

        return annualized_volatility

    # === 风险调整收益指标计算方法 ===

    def calculate_sharpe_ratio(self, apr: Decimal, volatility: Decimal) -> Optional[Decimal]:
        """
        计算夏普率 (Sharpe Ratio)

        Purpose:
            衡量策略的风险调整后收益，反映每单位风险所获得的超额收益。
            夏普率越高，说明策略在承担相同风险的情况下获得更高的收益。

        Formula:
            Sharpe Ratio = (APR - risk_free_rate) / Volatility

            其中：
            - APR: 年化收益率（%）
            - risk_free_rate: 无风险收益率（初始化时设置）
            - Volatility: 年化波动率（%）

        Args:
            apr (Decimal): 年化收益率（%），可以为负数
            volatility (Decimal): 年化波动率（%），必须 >= 0

        Returns:
            Decimal|None: 夏普率，保留2位小数
                - 正值：策略超额收益高于风险
                - 负值：策略收益低于无风险收益率
                - None：波动率=0（除零保护，优雅降级）

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator(risk_free_rate=Decimal("0.03"))
            >>> # APR=12%, 波动率=15%, risk_free_rate=3%
            >>> sharpe = calculator.calculate_sharpe_ratio(Decimal("12.00"), Decimal("15.00"))
            >>> sharpe
            Decimal('0.60')  # (12-3) / 15
            >>>
            >>> # 波动率=0，除零保护
            >>> sharpe_zero = calculator.calculate_sharpe_ratio(Decimal("12.00"), Decimal("0.00"))
            >>> sharpe_zero is None
            True

        Context:
            关联任务：TASK-014-006
            关联需求：FP-014-008
        """
        # === Guard Clause: 除零保护 - 波动率为0时返回None ===
        if volatility == 0:
            return None

        # 计算超额收益
        risk_free_rate_percent = self.risk_free_rate * Decimal("100")
        excess_return = apr - risk_free_rate_percent

        # 计算夏普率
        sharpe_ratio = (excess_return / volatility).quantize(Decimal("0.01"))

        return sharpe_ratio

    def calculate_calmar_ratio(self, apr: Decimal, mdd: Decimal) -> Optional[Decimal]:
        """
        计算卡玛比率 (Calmar Ratio)

        Purpose:
            衡量策略的年化收益与最大回撤的比率，反映策略在承担回撤风险下的收益能力。
            卡玛比率越高，说明策略在控制回撤的情况下获得更高的收益。

        Formula:
            Calmar Ratio = APR / abs(MDD)

            其中：
            - APR: 年化收益率（%）
            - MDD: 最大回撤（%），通常为负值

        Args:
            apr (Decimal): 年化收益率（%），可以为负数
            mdd (Decimal): 最大回撤（%），通常为负值（如-10.00表示10%回撤）

        Returns:
            Decimal|None: 卡玛比率，保留2位小数
                - 正值：策略在控制回撤下获得正收益
                - 负值：策略收益为负
                - None：MDD=0（除零保护，优雅降级）

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # APR=12%, MDD=-10%
            >>> calmar = calculator.calculate_calmar_ratio(Decimal("12.00"), Decimal("-10.00"))
            >>> calmar
            Decimal('1.20')  # 12 / 10
            >>>
            >>> # MDD=0，除零保护
            >>> calmar_zero = calculator.calculate_calmar_ratio(Decimal("12.00"), Decimal("0.00"))
            >>> calmar_zero is None
            True

        Context:
            关联任务：TASK-014-006
            关联需求：FP-014-009
        """
        # === Guard Clause: 除零保护 - MDD为0时返回None ===
        if mdd == 0:
            return None

        # 计算卡玛比率（使用MDD的绝对值）
        calmar_ratio = (apr / abs(mdd)).quantize(Decimal("0.01"))

        return calmar_ratio

    def calculate_mar_ratio(self, cumulative_return: Decimal, mdd: Decimal) -> Optional[Decimal]:
        """
        计算MAR比率 (MAR Ratio)

        Purpose:
            衡量策略的累计收益与最大回撤的比率，类似卡玛比率但使用累计收益率。
            MAR比率越高，说明策略在相同回撤下获得更高的累计收益。

        Formula:
            MAR Ratio = 累计收益率 / abs(MDD)

            其中：
            - 累计收益率: 回测期间的总收益率（%）
            - MDD: 最大回撤（%），通常为负值

        Args:
            cumulative_return (Decimal): 累计收益率（%），可以为负数
            mdd (Decimal): 最大回撤（%），通常为负值

        Returns:
            Decimal|None: MAR比率，保留2位小数
                - 正值：策略获得正收益
                - 负值：策略收益为负
                - None：MDD=0（除零保护，优雅降级）

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 累计收益率=20%, MDD=-15%
            >>> mar = calculator.calculate_mar_ratio(Decimal("20.00"), Decimal("-15.00"))
            >>> mar
            Decimal('1.33')  # 20 / 15
            >>>
            >>> # MDD=0，除零保护
            >>> mar_zero = calculator.calculate_mar_ratio(Decimal("20.00"), Decimal("0.00"))
            >>> mar_zero is None
            True

        Context:
            关联任务：TASK-014-006
            关联需求：FP-014-010
        """
        # === Guard Clause: 除零保护 - MDD为0时返回None ===
        if mdd == 0:
            return None

        # 计算MAR比率（使用MDD的绝对值）
        mar_ratio = (cumulative_return / abs(mdd)).quantize(Decimal("0.01"))

        return mar_ratio

    def calculate_profit_factor(self, orders: List[Order]) -> Optional[Decimal]:
        """
        计算盈利因子 (Profit Factor)

        Purpose:
            衡量策略的盈利能力与亏损控制，反映所有盈利订单与亏损订单的比率。
            盈利因子越高，说明策略的盈利能力远超亏损。

        Formula:
            Profit Factor = sum(盈利订单) / abs(sum(亏损订单))

            其中：
            - sum(盈利订单): 所有profit_loss > 0的订单的总盈利
            - sum(亏损订单): 所有profit_loss < 0的订单的总亏损

        Args:
            orders (List[Order]): 订单列表，每个Order必须包含profit_loss字段

        Returns:
            Decimal|None: 盈利因子，保留2位小数
                - > 1.00：盈利大于亏损
                - = 1.00：盈亏平衡
                - < 1.00：亏损大于盈利
                - None：无亏损订单或订单列表为空（除零保护，优雅降级）

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 2笔盈利订单，1笔亏损订单
            >>> orders = [
            ...     Order(..., profit_loss=Decimal("1000.00")),
            ...     Order(..., profit_loss=Decimal("500.00")),
            ...     Order(..., profit_loss=Decimal("-300.00")),
            ... ]
            >>> profit_factor = calculator.calculate_profit_factor(orders)
            >>> profit_factor
            Decimal('5.00')  # (1000+500) / 300
            >>>
            >>> # 无亏损订单，除零保护
            >>> orders_no_loss = [Order(..., profit_loss=Decimal("1000.00"))]
            >>> pf_none = calculator.calculate_profit_factor(orders_no_loss)
            >>> pf_none is None
            True

        Context:
            关联任务：TASK-014-006
            关联需求：FP-014-011
        """
        # === Guard Clause: 空订单列表，优雅降级 ===
        if not orders:
            return None

        # === 步骤1: 计算总盈利和总亏损 ===
        total_profit = Decimal("0")
        total_loss = Decimal("0")

        for order in orders:
            # 只统计已平仓订单（有profit_loss字段）
            if order.status == OrderStatus.CLOSED and order.profit_loss is not None:
                if order.profit_loss > 0:
                    total_profit += order.profit_loss
                elif order.profit_loss < 0:
                    total_loss += order.profit_loss

        # === Guard Clause: 除零保护 - 无亏损订单时返回None ===
        if total_loss == 0:
            return None

        # === 步骤2: 计算盈利因子 ===
        profit_factor = (total_profit / abs(total_loss)).quantize(Decimal("0.01"))

        return profit_factor

    # === 交易效率指标计算方法 ===

    def calculate_trade_frequency(self, total_orders: int, days: int) -> Decimal:
        """
        计算交易频率 (Trade Frequency)

        Purpose:
            计算策略的交易频率，反映策略的交易活跃度。
            交易频率用于评估策略的换手率和交易成本影响。

        Formula:
            交易频率 = total_orders / days（次/天）

        Args:
            total_orders (int): 总交易订单数，包含所有已平仓订单
            days (int): 回测天数，必须 > 0

        Returns:
            Decimal: 交易频率（次/天），保留2位小数
                - 例如：0.33 表示平均每天交易0.33次
                - 10.00 表示平均每天交易10次（高频交易）

        Raises:
            ValueError: 当 days <= 0 时触发，异常消息包含预期范围和实际值

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 365天120笔交易
            >>> frequency = calculator.calculate_trade_frequency(120, 365)
            >>> frequency
            Decimal('0.33')
            >>>
            >>> # 30天300笔交易（高频交易）
            >>> frequency_high = calculator.calculate_trade_frequency(300, 30)
            >>> frequency_high
            Decimal('10.00')

        Context:
            关联任务：TASK-014-007
            关联需求：FP-014-012
        """
        # Guard Clause: 验证 days > 0
        if days <= 0:
            raise ValueError(
                "days必须大于0。\n"
                f"期望：days > 0\n"
                f"实际：{days}"
            )

        # 计算交易频率
        # 交易频率 = 总订单数 / 回测天数
        frequency = (Decimal(str(total_orders)) / Decimal(str(days))).quantize(Decimal("0.01"))

        return frequency

    def calculate_cost_percentage(
        self,
        total_commission: Decimal,
        total_profit: Decimal
    ) -> Optional[Decimal]:
        """
        计算成本占比 (Cost Percentage)

        Purpose:
            计算交易手续费占总收益的比例，反映交易成本对收益的侵蚀程度。
            成本占比越低，说明策略的交易成本控制越好。

        Formula:
            Cost % = (total_commission / total_profit) × 100%

        Args:
            total_commission (Decimal): 总手续费（USDT），包含开仓和平仓手续费
            total_profit (Decimal): 总盈亏（USDT），可以为负数

        Returns:
            Decimal|None: 成本占比（%），保留2位小数
                - 正值：手续费占收益的比例（如2.00表示手续费占收益的2%）
                - None：total_profit=0时返回（除零保护，优雅降级）

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 收益1000，手续费20
            >>> cost_pct = calculator.calculate_cost_percentage(
            ...     Decimal("20.00"),
            ...     Decimal("1000.00")
            ... )
            >>> cost_pct
            Decimal('2.00')
            >>>
            >>> # 收益为0，除零保护
            >>> cost_pct_zero = calculator.calculate_cost_percentage(
            ...     Decimal("20.00"),
            ...     Decimal("0.00")
            ... )
            >>> cost_pct_zero is None
            True

        Context:
            关联任务：TASK-014-007
            关联需求：FP-014-013
        """
        # === Guard Clause: 除零保护 - total_profit为0时返回None ===
        if total_profit == 0:
            return None

        # 计算成本占比
        # Cost % = (总手续费 / 总收益) × 100%
        cost_percentage = ((total_commission / total_profit) * Decimal("100")).quantize(Decimal("0.01"))

        return cost_percentage

    def calculate_payoff_ratio(self, orders: List[Order]) -> Optional[Decimal]:
        """
        计算盈亏比 (Payoff Ratio)

        Purpose:
            计算平均盈利订单与平均亏损订单的比率，反映策略的盈亏平衡能力。
            盈亏比越高，说明策略在盈利时赚得更多，亏损时损失更少。

        Formula:
            Payoff Ratio = avg(盈利订单) / abs(avg(亏损订单))

            其中：
            - avg(盈利订单): 所有 profit_loss > 0 的订单的平均盈利
            - avg(亏损订单): 所有 profit_loss < 0 的订单的平均亏损

        Args:
            orders (List[Order]): 订单列表，每个Order必须包含profit_loss字段

        Returns:
            Decimal|None: 盈亏比，保留2位小数
                - > 1.00：平均盈利大于平均亏损
                - = 1.00：平均盈亏相等
                - < 1.00：平均亏损大于平均盈利
                - None：无亏损订单或订单列表为空（除零保护，优雅降级）

        Side Effects:
            无。纯计算函数。

        Example:
            >>> calculator = MetricsCalculator()
            >>> # 2笔盈利订单（平均100），2笔亏损订单（平均-50）
            >>> orders = [
            ...     Order(..., profit_loss=Decimal("100.00")),
            ...     Order(..., profit_loss=Decimal("100.00")),
            ...     Order(..., profit_loss=Decimal("-50.00")),
            ...     Order(..., profit_loss=Decimal("-50.00")),
            ... ]
            >>> payoff_ratio = calculator.calculate_payoff_ratio(orders)
            >>> payoff_ratio
            Decimal('2.00')  # 100 / 50
            >>>
            >>> # 无亏损订单，除零保护
            >>> orders_no_loss = [Order(..., profit_loss=Decimal("100.00"))]
            >>> payoff_none = calculator.calculate_payoff_ratio(orders_no_loss)
            >>> payoff_none is None
            True

        Context:
            关联任务：TASK-014-007
            关联需求：FP-014-015
        """
        # === Guard Clause: 空订单列表，优雅降级 ===
        if not orders:
            return None

        # === 步骤1: 计算盈利和亏损订单 ===
        winning_profits = []
        losing_losses = []

        for order in orders:
            # 只统计已平仓订单（有profit_loss字段）
            if order.status == OrderStatus.CLOSED and order.profit_loss is not None:
                if order.profit_loss > 0:
                    winning_profits.append(order.profit_loss)
                elif order.profit_loss < 0:
                    losing_losses.append(order.profit_loss)

        # === Guard Clause: 除零保护 - 无亏损订单时返回None ===
        if not losing_losses:
            return None

        # === 步骤2: 计算平均盈利和平均亏损 ===
        avg_winning_profit = sum(winning_profits) / Decimal(str(len(winning_profits))) if winning_profits else Decimal("0")
        avg_losing_loss = sum(losing_losses) / Decimal(str(len(losing_losses)))

        # === 步骤3: 计算盈亏比 ===
        payoff_ratio = (avg_winning_profit / abs(avg_losing_loss)).quantize(Decimal("0.01"))

        return payoff_ratio

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

        # === 步骤1: 计算基础统计数据 ===
        # 筛选已平仓订单
        closed_orders = [o for o in orders if o.status == OrderStatus.CLOSED]

        # 计算总盈亏（total_profit）
        total_profit = sum(o.profit_loss for o in closed_orders if o.profit_loss) if closed_orders else Decimal("0")

        # 计算总手续费（total_commission）
        total_commission = sum(
            (o.open_commission or Decimal("0")) + (o.close_commission or Decimal("0"))
            for o in closed_orders
        )

        # 计算胜率（win_rate）
        if closed_orders:
            win_orders = [o for o in closed_orders if o.profit_loss and o.profit_loss > 0]
            win_rate = (Decimal(str(len(win_orders))) / Decimal(str(len(closed_orders))) * Decimal("100")).quantize(Decimal("0.01"))
        else:
            win_rate = Decimal("0.00")

        # 计算总订单数（total_orders）
        total_orders = len(closed_orders)

        # === 步骤2: 调用收益指标计算方法 ===
        apr = self.calculate_apr(total_profit, initial_cash, days)
        absolute_return = self.calculate_absolute_return(total_profit)
        cumulative_return = self.calculate_cumulative_return(total_profit, initial_cash)

        # === 步骤3: 调用风险指标计算方法 ===
        mdd_result = self.calculate_mdd(equity_curve)
        volatility = self.calculate_volatility(equity_curve)

        # === 步骤4: 调用风险调整收益指标计算方法 ===
        sharpe_ratio = self.calculate_sharpe_ratio(apr, volatility)
        calmar_ratio = self.calculate_calmar_ratio(apr, mdd_result['mdd'])
        mar_ratio = self.calculate_mar_ratio(cumulative_return, mdd_result['mdd'])
        profit_factor = self.calculate_profit_factor(orders)

        # === 步骤5: 调用交易效率指标计算方法 ===
        trade_frequency = self.calculate_trade_frequency(total_orders, days)
        cost_percentage = self.calculate_cost_percentage(total_commission, total_profit)
        payoff_ratio = self.calculate_payoff_ratio(orders)

        # === 步骤6: 组装返回字典 ===
        metrics: Dict[str, Optional[Decimal]] = {
            # 收益分析（3个）
            'apr': apr,
            'absolute_return': absolute_return,
            'cumulative_return': cumulative_return,
            # 风险分析（4个）
            'mdd': mdd_result['mdd'],
            'mdd_start_time': mdd_result['mdd_start_time'],
            'mdd_end_time': mdd_result['mdd_end_time'],
            'recovery_time': mdd_result['recovery_time'],
            # 波动率
            'volatility': volatility,
            # 风险调整收益（4个）
            'sharpe_ratio': sharpe_ratio,
            'calmar_ratio': calmar_ratio,
            'mar_ratio': mar_ratio,
            'profit_factor': profit_factor,
            # 交易效率（4个）
            'trade_frequency': trade_frequency,
            'cost_percentage': cost_percentage,
            'win_rate': win_rate,
            'payoff_ratio': payoff_ratio,
        }

        return metrics
