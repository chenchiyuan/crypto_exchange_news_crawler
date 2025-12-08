"""
模拟交易所
Simulated Exchange for Backtesting

提供订单撮合、成交模拟功能
"""
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class SimulatedOrder:
    """模拟订单"""
    
    def __init__(
        self,
        order_id: str,
        symbol: str,
        side: str,
        price: Decimal,
        quantity: Decimal,
        client_order_id: str = None
    ):
        self.order_id = order_id
        self.symbol = symbol
        self.side = side  # BUY/SELL
        self.price = price
        self.quantity = quantity
        self.filled_quantity = Decimal('0')
        self.status = 'NEW'  # NEW, FILLED, CANCELED
        self.client_order_id = client_order_id
        self.created_at = datetime.now()
        self.filled_at = None


class SimulatedExchange:
    """模拟交易所"""
    
    def __init__(self, enable_slippage: bool = False, slippage_pct: Decimal = Decimal('0.001')):
        """
        初始化模拟交易所
        
        Args:
            enable_slippage: 是否启用滑点
            slippage_pct: 滑点百分比（默认0.1%）
        """
        self.orders: Dict[str, SimulatedOrder] = {}
        self.order_counter = 0
        self.enable_slippage = enable_slippage
        self.slippage_pct = slippage_pct
        
        # 统计信息
        self.total_trades = 0
        self.total_buy_volume = Decimal('0')
        self.total_sell_volume = Decimal('0')
    
    def create_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: float,
        client_order_id: str = None
    ) -> Dict:
        """
        创建订单
        
        Args:
            symbol: 交易对
            side: BUY/SELL
            order_type: LIMIT
            quantity: 数量
            price: 价格
            client_order_id: 客户端订单ID
            
        Returns:
            订单响应
        """
        self.order_counter += 1
        order_id = f"backtest_{self.order_counter}"
        
        order = SimulatedOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            price=Decimal(str(price)),
            quantity=Decimal(str(quantity)),
            client_order_id=client_order_id
        )
        
        self.orders[order_id] = order
        
        logger.debug(
            f"创建订单: {order_id}, {side} {quantity} @ {price}"
        )
        
        return {
            'orderId': order_id,
            'status': 'NEW',
            'symbol': symbol,
            'side': side,
            'price': price,
            'origQty': quantity,
            'clientOrderId': client_order_id
        }
    
    def cancel_order(self, symbol: str, order_id: str) -> Dict:
        """
        撤销订单
        
        Args:
            symbol: 交易对
            order_id: 订单ID
            
        Returns:
            撤销响应
        """
        if order_id in self.orders:
            order = self.orders[order_id]
            if order.status == 'NEW':
                order.status = 'CANCELED'
                logger.debug(f"撤销订单: {order_id}")
                
                return {
                    'orderId': order_id,
                    'status': 'CANCELED'
                }
        
        raise Exception(f"订单不存在或无法撤销: {order_id}")
    
    def match_orders(
        self,
        kline_open: Decimal,
        kline_high: Decimal,
        kline_low: Decimal,
        kline_close: Decimal
    ) -> List[Tuple[str, str, Decimal]]:
        """
        撮合订单（模拟K线期间的成交）
        
        Args:
            kline_open: 开盘价
            kline_high: 最高价
            kline_low: 最低价
            kline_close: 收盘价
            
        Returns:
            成交订单列表 [(order_id, side, fill_price), ...]
        """
        filled_orders = []
        
        for order_id, order in self.orders.items():
            if order.status != 'NEW':
                continue
            
            filled = False
            fill_price = order.price
            
            # 买单：价格触及订单价格或更低时成交
            if order.side == 'BUY':
                if kline_low <= order.price:
                    filled = True
                    # 如果开盘价就低于买单价格，按开盘价成交
                    if kline_open <= order.price:
                        fill_price = kline_open
                    else:
                        # 否则按订单价格成交
                        fill_price = order.price
                    
                    # 应用滑点（买单价格上浮）
                    if self.enable_slippage:
                        fill_price = fill_price * (Decimal('1') + self.slippage_pct)
            
            # 卖单：价格触及订单价格或更高时成交
            elif order.side == 'SELL':
                if kline_high >= order.price:
                    filled = True
                    # 如果开盘价就高于卖单价格，按开盘价成交
                    if kline_open >= order.price:
                        fill_price = kline_open
                    else:
                        # 否则按订单价格成交
                        fill_price = order.price
                    
                    # 应用滑点（卖单价格下浮）
                    if self.enable_slippage:
                        fill_price = fill_price * (Decimal('1') - self.slippage_pct)
            
            if filled:
                order.status = 'FILLED'
                order.filled_quantity = order.quantity
                order.filled_at = datetime.now()
                
                # 更新统计
                self.total_trades += 1
                if order.side == 'BUY':
                    self.total_buy_volume += order.quantity
                else:
                    self.total_sell_volume += order.quantity
                
                filled_orders.append((order_id, order.side, fill_price))
                
                logger.debug(
                    f"订单成交: {order_id}, {order.side} "
                    f"{order.quantity} @ {fill_price}"
                )
        
        return filled_orders
    
    def get_active_orders(self, symbol: str) -> List[SimulatedOrder]:
        """获取活跃订单"""
        return [
            order for order in self.orders.values()
            if order.symbol == symbol and order.status == 'NEW'
        ]
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            'total_trades': self.total_trades,
            'total_buy_volume': float(self.total_buy_volume),
            'total_sell_volume': float(self.total_sell_volume),
            'total_orders': len(self.orders)
        }
