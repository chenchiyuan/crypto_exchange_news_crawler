"""
做空网格策略
Short Grid Strategy

实现做空网格的核心逻辑：上方卖单开仓，下方买单平仓
"""
from decimal import Decimal
from typing import List, Dict, Tuple
import logging

from grid_trading.models import (
    GridConfig, GridLevel, GridLevelSide, GridLevelStatus,
    OrderIntent, OrderIntentType, OrderSide, TradeLog
)

logger = logging.getLogger(__name__)


class ShortGridStrategy:
    """做空网格策略"""
    
    def __init__(self, config: GridConfig):
        """
        初始化做空网格策略
        
        Args:
            config: 网格配置对象
        """
        if config.grid_mode.upper() != 'SHORT':
            raise ValueError(f"配置的网格模式不是SHORT: {config.grid_mode}")
        
        self.config = config
        self.grid_levels: List[GridLevel] = []
    
    def load_grid_levels(self):
        """加载网格层级"""
        self.grid_levels = list(
            GridLevel.objects.filter(config=self.config).order_by('level_index')
        )
        logger.info(f"加载了 {len(self.grid_levels)} 个网格层级")
    
    def calculate_ideal_orders(self, current_price: Decimal = None) -> List[Dict]:
        """
        计算理想挂单
        
        做空网格策略：
        - 上方：卖单开仓（ENTRY/SELL）
        - 下方：买单平仓（EXIT/BUY）
        
        Args:
            current_price: 当前市场价格（用于判断哪些层级需要挂单）
            
        Returns:
            理想订单列表，每个元素包含 {level, intent, side, price, amount}
        """
        if not self.grid_levels:
            self.load_grid_levels()
        
        ideal_orders = []
        
        for level in self.grid_levels:
            order = self._calculate_level_order(level, current_price)
            if order:
                ideal_orders.append(order)
        
        logger.info(f"计算完成：需要 {len(ideal_orders)} 个理想订单")
        return ideal_orders
    
    def _calculate_level_order(self, level: GridLevel, current_price: Decimal = None) -> Dict | None:
        """
        计算单个层级的理想订单

        Args:
            level: 网格层级
            current_price: 当前市场价格

        Returns:
            订单信息字典，如果不需要挂单则返回None
        """
        price = Decimal(str(level.price))

        # idle状态：需要挂开仓单
        if level.status == GridLevelStatus.IDLE:
            if level.side == GridLevelSide.SELL:
                # 上方卖单开仓
                return {
                    'level': level,
                    'level_index': level.level_index,
                    'intent': OrderIntentType.ENTRY,
                    'side': OrderSide.SELL,
                    'price': price,
                    'amount': Decimal(str(self.config.trade_amount))
                }
            # 下方买单暂时不挂（等待上方开仓后才挂平仓单）
            return None

        # entry_working状态：订单已挂，保留在理想订单中
        elif level.status == GridLevelStatus.ENTRY_WORKING:
            if level.side == GridLevelSide.SELL:
                return {
                    'level': level,
                    'level_index': level.level_index,
                    'intent': OrderIntentType.ENTRY,
                    'side': OrderSide.SELL,
                    'price': price,
                    'amount': Decimal(str(self.config.trade_amount))
                }
            return None

        # position_open状态：需要挂平仓单
        elif level.status == GridLevelStatus.POSITION_OPEN:
            if level.side == GridLevelSide.SELL:
                # 卖单开仓后，在下方挂买单平仓
                # 平仓价格 = 开仓价格 - 网格间距
                exit_price = price - self.config.grid_spacing

                # 确保不低于价格下界
                lower_bound = Decimal(str(self.config.lower_price))
                if exit_price < lower_bound:
                    exit_price = lower_bound

                return {
                    'level': level,
                    'level_index': level.level_index,
                    'intent': OrderIntentType.EXIT,
                    'side': OrderSide.BUY,
                    'price': exit_price,
                    'amount': Decimal(str(self.config.trade_amount))
                }

        # exit_working状态：订单已挂，保留在理想订单中
        elif level.status == GridLevelStatus.EXIT_WORKING:
            if level.side == GridLevelSide.SELL:
                exit_price = price - self.config.grid_spacing
                lower_bound = Decimal(str(self.config.lower_price))
                if exit_price < lower_bound:
                    exit_price = lower_bound

                return {
                    'level': level,
                    'level_index': level.level_index,
                    'intent': OrderIntentType.EXIT,
                    'side': OrderSide.BUY,
                    'price': exit_price,
                    'amount': Decimal(str(self.config.trade_amount))
                }

        # 其他状态不挂单
        return None
    
    def check_position_limit(self, current_position: Decimal) -> bool:
        """
        检查持仓限制
        
        做空网格：净空头持仓（负值）不能超过max_position_size
        
        Args:
            current_position: 当前持仓数量（负数表示空头）
            
        Returns:
            是否在限制范围内
        """
        max_position = Decimal(str(self.config.max_position_size))
        
        # 做空持仓是负数，取绝对值比较
        abs_position = abs(current_position)
        
        if abs_position > max_position:
            logger.warning(
                f"持仓超限: 当前={abs_position}, 最大={max_position}"
            )
            return False
        
        return True
    
    def filter_orders_by_position_limit(
        self,
        ideal_orders: List[Dict],
        current_position: Decimal
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        根据持仓限制过滤订单

        达到持仓上限时，拒绝新的开仓单（ENTRY/SELL），只允许平仓单（EXIT/BUY）

        Args:
            ideal_orders: 理想订单列表
            current_position: 当前持仓（负数表示空头）

        Returns:
            (允许的订单列表, 被过滤的订单列表)
        """
        max_position = Decimal(str(self.config.max_position_size))
        cumulative_position = abs(current_position)

        allowed_orders = []
        filtered_orders = []

        for order in ideal_orders:
            # 平仓单始终允许
            if order['intent'] == OrderIntentType.EXIT:
                allowed_orders.append(order)
                continue

            # 检查开仓单是否会超限
            if order['intent'] == OrderIntentType.ENTRY:
                new_position = cumulative_position + order['amount']

                if new_position > max_position:
                    logger.info(
                        f"过滤开仓单: level={order['level_index']}, "
                        f"会导致持仓={new_position} > 上限={max_position}"
                    )
                    filtered_orders.append(order)
                else:
                    allowed_orders.append(order)
                    # 更新累积持仓
                    cumulative_position = new_position

        logger.info(
            f"持仓过滤完成: 允许={len(allowed_orders)}, 过滤={len(filtered_orders)}"
        )
        return allowed_orders, filtered_orders
    
    def on_order_filled(self, level: GridLevel, intent: str) -> GridLevel:
        """
        订单成交回调，更新层级状态
        
        状态转换：
        - ENTRY成交: entry_working → position_open
        - EXIT成交: exit_working → idle
        
        Args:
            level: 网格层级
            intent: 订单意图 (ENTRY/EXIT)
            
        Returns:
            更新后的GridLevel对象
        """
        if intent == OrderIntentType.ENTRY:
            # 开仓单成交
            if level.status == GridLevelStatus.ENTRY_WORKING:
                level.transition_to_position_open()
                # 记录成交事件
                TradeLog.log_fill(
                    self.config,
                    f"网格开仓成交: 层级={level.level_index}, 价格={level.price}",
                    order_id=None,  # 由调用者传入
                    level_index=level.level_index
                )
                logger.info(
                    f"开仓成交: level={level.level_index}, "
                    f"价格={level.price}, 状态→position_open"
                )
            else:
                logger.warning(
                    f"状态异常: 开仓成交但状态不是entry_working, "
                    f"level={level.level_index}, status={level.status}"
                )
        
        elif intent == OrderIntentType.EXIT:
            # 平仓单成交
            if level.status == GridLevelStatus.EXIT_WORKING:
                level.transition_to_idle()
                # 记录成交事件
                TradeLog.log_fill(
                    self.config,
                    f"网格平仓成交: 层级={level.level_index}, 价格={level.price}, 该层级已完成一轮交易",
                    order_id=None,  # 由调用者传入
                    level_index=level.level_index
                )
                logger.info(
                    f"平仓成交: level={level.level_index}, "
                    f"状态→idle, 该层级已完成一轮交易"
                )
            else:
                logger.warning(
                    f"状态异常: 平仓成交但状态不是exit_working, "
                    f"level={level.level_index}, status={level.status}"
                )
        
        return level
    
    def get_current_position(self) -> Decimal:
        """
        计算当前总持仓
        
        做空网格：position_open状态的层级数量 × trade_amount（负数）
        
        Returns:
            当前持仓（负数表示空头）
        """
        if not self.grid_levels:
            self.load_grid_levels()
        
        position_count = sum(
            1 for level in self.grid_levels 
            if level.status in [GridLevelStatus.POSITION_OPEN, GridLevelStatus.EXIT_WORKING]
        )
        
        trade_amount = Decimal(str(self.config.trade_amount))
        # 做空持仓是负数
        current_position = -trade_amount * Decimal(position_count)
        
        logger.debug(
            f"当前持仓: {position_count}个层级 × {trade_amount} = {current_position}"
        )
        return current_position
