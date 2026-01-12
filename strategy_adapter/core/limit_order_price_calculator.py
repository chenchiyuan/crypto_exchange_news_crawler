"""
限价挂单价格计算器

本模块实现限价挂单的价格计算逻辑：
- 买入挂单价格：根据mid与P5的关系确定基础价格，然后统一应用折扣
  - mid < P5: 首笔 = (P5+mid)/2 × (1 - first_order_discount)
  - mid >= P5: 首笔 = P5 × (1 - first_order_discount)
- 卖出挂单价格：取min(买入价×1.05, EMA25)

迭代编号: 027 (策略11-限价挂单买卖机制)
创建日期: 2026-01-10
关联任务: TASK-027-003
关联需求: FP-027-007, FP-027-008, FP-027-012 (function-points.md)
关联架构: architecture.md#5.3 LimitOrderPriceCalculator
"""

from decimal import Decimal
from typing import List


class LimitOrderPriceCalculator:
    """
    限价挂单价格计算器

    负责计算买入挂单和卖出挂单的价格：
    - 买入：根据mid与P5关系确定基础价格，统一应用折扣后按interval递减
    - 卖出：取5%止盈价格和EMA25的较低值

    Attributes:
        order_count (int): 挂单数量，默认10笔
        order_interval (float): 挂单间隔比例，默认0.005（0.5%）
        first_order_discount (float): 首笔挂单折扣，默认0.01（1%）

    Example:
        >>> calculator = LimitOrderPriceCalculator(order_count=10, order_interval=0.005)
        >>> # mid < P5: 首笔 = (P5+mid)/2 × (1 - discount)
        >>> prices = calculator.calculate_buy_prices(Decimal("3100"), Decimal("3000"))
        >>> prices[0]  # (3100+3000)/2 × 0.99 = 3019.5
        >>> # mid >= P5: 首笔 = P5 × (1 - discount)
        >>> prices = calculator.calculate_buy_prices(Decimal("3100"), Decimal("3200"))
        >>> prices[0]  # 3100 × 0.99 = 3069
    """

    def __init__(
        self,
        order_count: int = 10,
        order_interval: float = 0.005,
        first_order_discount: float = 0.01
    ):
        """
        初始化价格计算器

        Args:
            order_count: 挂单数量，默认10笔
            order_interval: 挂单间隔比例，默认0.005（0.5%）
            first_order_discount: 首笔挂单折扣，默认0.01（1%）

        Raises:
            ValueError: 如果order_count < 1或order_interval < 0
        """
        if order_count < 1:
            raise ValueError(f"order_count must be >= 1, got {order_count}")
        if order_interval < 0:
            raise ValueError(f"order_interval must be >= 0, got {order_interval}")

        self.order_count = order_count
        self.order_interval = Decimal(str(order_interval))
        self.first_order_discount = Decimal(str(first_order_discount))

    def calculate_buy_prices(self, p5: Decimal, mid: Decimal, close: Decimal = None) -> List[Decimal]:
        """
        计算买入挂单价格列表

        价格计算规则：
        - 首笔价格：
          - mid < P5: min(close, (P5 + mid) / 2) × (1 - first_order_discount)
          - mid >= P5: min(close, P5) × (1 - first_order_discount)
        - 第N笔：首笔 × (1 - (N-1) × interval)

        Args:
            p5: DDPS概率分布的5%分位数价格
            mid: DDPS扇形的中间价格
            close: 当前K线收盘价，用于限制挂单价格上限（可选）

        Returns:
            List[Decimal]: 买入挂单价格列表，长度为order_count

        Example:
            >>> calculator = LimitOrderPriceCalculator(order_count=3, order_interval=0.01)
            >>> # mid < P5: 首笔 = min(close, (P5+mid)/2) × (1 - discount)
            >>> prices = calculator.calculate_buy_prices(Decimal("100"), Decimal("90"), Decimal("92"))
            >>> prices[0]  # 91.08 = min(92, 95) × 0.99 = 92 × 0.99
            >>> # mid >= P5: 首笔 = min(close, P5) × (1 - discount)
            >>> prices = calculator.calculate_buy_prices(Decimal("100"), Decimal("110"), Decimal("98"))
            >>> prices[0]  # 97.02 = min(98, 100) × 0.99 = 98 × 0.99
        """
        # 计算基础价格：根据mid与P5的关系，并应用close上限约束
        if mid < p5:
            # mid < P5: 使用 (P5 + mid) / 2
            base_price = (p5 + mid) / Decimal("2")
        else:
            # mid >= P5: 使用 P5
            base_price = p5

        # 应用close上限约束，防止挂单价格偏高
        if close is not None:
            base_price = min(base_price, close)

        # 统一应用首笔折扣
        first_price = base_price * (Decimal("1") - self.first_order_discount)

        prices = []
        for i in range(self.order_count):
            # 第i笔价格 = 首笔价格 × (1 - i × interval)
            discount_factor = Decimal("1") - (Decimal(i) * self.order_interval)
            price = first_price * discount_factor
            prices.append(price)

        return prices

    def calculate_sell_price(
        self,
        buy_price: Decimal,
        ema25: Decimal,
        take_profit_rate: float = 0.05,
        commission_rate: float = 0.001,
        min_profit_rate: float = 0.02
    ) -> Decimal:
        """
        计算卖出挂单价格

        价格计算规则：
        1. 正常情况：卖出价格 = min(止盈价格, EMA25)
        2. 防亏损：如果正常卖出价格 < 买入价（会亏损），则：
           卖出价格 = min(EMA25×(1+min_profit_rate), 买入价×(1+commission_rate))

        Args:
            buy_price: 买入成交价格
            ema25: 当前K线的EMA25值
            take_profit_rate: 止盈比例，默认0.05（5%）
            commission_rate: 手续费率，默认0.001（0.1%）
            min_profit_rate: 保底收益率，默认0.02（2%），用于防亏损时计算EMA加成

        Returns:
            Decimal: 卖出挂单价格

        Example:
            >>> calculator = LimitOrderPriceCalculator()
            >>> # 正常情况：5%止盈价(3360)低于EMA25(3400)，返回3360
            >>> calculator.calculate_sell_price(Decimal("3200"), Decimal("3400"), 0.05)
            Decimal('3360')
            >>> # 防亏损：EMA25(3100)低于买入价(3200)，启用保底逻辑
            >>> # min(3100×1.02, 3200×1.001) = min(3162, 3203.2) = 3162
            >>> calculator.calculate_sell_price(Decimal("3200"), Decimal("3100"), 0.05)
            Decimal('3162')
        """
        # 计算止盈价格
        take_profit_price = buy_price * (Decimal("1") + Decimal(str(take_profit_rate)))

        # 正常卖出价格 = min(止盈价格, EMA25)
        normal_sell_price = min(take_profit_price, ema25)

        # 防亏损检查：如果正常卖出价格 < 买入价，启用保底逻辑
        if normal_sell_price < buy_price:
            # EMA保底价 = EMA25 × (1 + min_profit_rate)
            ema_floor_price = ema25 * (Decimal("1") + Decimal(str(min_profit_rate)))
            # 手续费保底价 = 买入价 × (1 + commission_rate)
            commission_floor_price = buy_price * (Decimal("1") + Decimal(str(commission_rate)))
            # 取两者较低值
            return min(ema_floor_price, commission_floor_price)

        return normal_sell_price

    def get_first_buy_price(self, p5: Decimal, mid: Decimal, close: Decimal = None) -> Decimal:
        """
        获取首笔买入挂单价格

        便捷方法，用于单独获取首笔价格而不计算全部价格列表。

        Args:
            p5: DDPS概率分布的5%分位数价格
            mid: DDPS扇形的中间价格
            close: 当前K线收盘价，用于限制挂单价格上限（可选）

        Returns:
            Decimal: 首笔买入挂单价格
                - mid < P5: min(close, (P5 + mid) / 2) × (1 - first_order_discount)
                - mid >= P5: min(close, P5) × (1 - first_order_discount)
        """
        # 计算基础价格
        if mid < p5:
            base_price = (p5 + mid) / Decimal("2")
        else:
            base_price = p5

        # 应用close上限约束
        if close is not None:
            base_price = min(base_price, close)

        # 统一应用折扣
        return base_price * (Decimal("1") - self.first_order_discount)
