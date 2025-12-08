"""
交易所适配器类型定义
Exchange Adapter Type Definitions
"""
from typing import TypedDict, Literal, Optional, Union
from decimal import Decimal


# 订单方向
OrderSide = Literal["BUY", "SELL"]

# 订单类型
OrderType = Literal[
    "LIMIT",
    "MARKET",
    "STOP",
    "STOP_MARKET",
    "TAKE_PROFIT",
    "TAKE_PROFIT_MARKET",
    "TRAILING_STOP_MARKET"
]

# 持仓方向
PositionSide = Literal["BOTH", "LONG", "SHORT"]

# 时效类型
TimeInForce = Literal["GTC", "IOC", "FOK", "GTX"]

# 订单状态
OrderStatus = Literal[
    "NEW",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCELED",
    "REJECTED",
    "EXPIRED"
]


class CreateOrderParams(TypedDict, total=False):
    """创建订单参数"""
    symbol: str  # 必填
    side: OrderSide  # 必填
    type: OrderType  # 必填
    quantity: float
    price: float
    stop_price: float
    activation_price: float
    callback_rate: float
    time_in_force: TimeInForce
    reduce_only: bool
    close_position: bool
    client_order_id: str


class ExchangeOrder(TypedDict, total=False):
    """交易所订单"""
    order_id: str  # 必填
    client_order_id: Optional[str]
    symbol: str  # 必填
    side: OrderSide  # 必填
    type: OrderType  # 必填
    status: OrderStatus  # 必填
    quantity: str
    price: str
    executed_qty: str
    avg_price: str
    time_in_force: TimeInForce
    reduce_only: bool
    close_position: bool
    create_time: int
    update_time: int


class AccountPosition(TypedDict, total=False):
    """账户持仓"""
    symbol: str  # 必填
    position_amt: str  # 必填
    entry_price: str
    unrealized_profit: str
    position_side: PositionSide
    update_time: int
    leverage: str
    liquidation_price: str
    mark_price: str


class AccountSnapshot(TypedDict, total=False):
    """账户快照"""
    total_balance: str
    available_balance: str
    total_unrealized_profit: str
    total_margin_balance: str
    total_position_initial_margin: str
    total_open_order_initial_margin: str
    positions: list[AccountPosition]
    update_time: int


class DepthLevel(TypedDict):
    """深度档位"""
    price: str
    quantity: str


class OrderBookDepth(TypedDict):
    """订单簿深度"""
    symbol: str
    bids: list[DepthLevel]  # 买单 (价格从高到低)
    asks: list[DepthLevel]  # 卖单 (价格从低到高)
    timestamp: int


class Ticker(TypedDict):
    """行情ticker"""
    symbol: str
    last_price: str
    bid_price: str
    ask_price: str
    volume_24h: str
    price_change_24h: str
    price_change_percent_24h: str
    high_24h: str
    low_24h: str
    timestamp: int


class Kline(TypedDict):
    """K线数据"""
    symbol: str
    interval: str
    open_time: int
    close_time: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    quote_volume: str


class ExchangePrecision(TypedDict, total=False):
    """交易所精度信息"""
    price_tick: Decimal  # 价格最小变动
    qty_step: Decimal  # 数量最小变动
    price_decimals: int  # 价格小数位
    size_decimals: int  # 数量小数位
    min_notional: Decimal  # 最小名义价值
    min_qty: Decimal  # 最小数量
