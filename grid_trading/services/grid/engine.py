"""
网格引擎核心模块
Grid Engine Core Module

负责网格层级计算、初始化和恢复
"""
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, TYPE_CHECKING
import logging
import time

from grid_trading.models import GridConfig, GridLevel, GridLevelSide, GridLevelStatus, TradeLog

if TYPE_CHECKING:
    from grid_trading.services.exchange import ExchangeAdapter

logger = logging.getLogger(__name__)


class GridEngine:
    """网格引擎"""

    def __init__(
        self,
        config: GridConfig,
        exchange_adapter: Optional['ExchangeAdapter'] = None
    ):
        """
        初始化网格引擎

        Args:
            config: 网格配置对象
            exchange_adapter: 交易所适配器（可选，回测时可为None）
        """
        self.config = config
        self.grid_levels: List[GridLevel] = []
        self.exchange_adapter = exchange_adapter
        self.strategy = None  # 网格策略实例
        self.order_sync_manager = None  # 订单同步管理器
        self.running = False
        self.last_persist_time = 0  # 上次持久化时间戳

        # 记录适配器信息
        if exchange_adapter:
            logger.info(
                f"GridEngine初始化: 使用 {exchange_adapter.id} 交易所适配器"
            )
        else:
            logger.info("GridEngine初始化: 回测模式（无交易所适配器）")
    
    def calculate_grid_levels(self) -> List[Dict]:
        """
        计算网格层级数组
        
        Returns:
            网格层级数据列表，每个元素包含 {level_index, price, side}
        """
        upper = Decimal(str(self.config.upper_price))
        lower = Decimal(str(self.config.lower_price))
        levels = self.config.grid_levels
        
        if levels <= 1:
            raise ValueError("网格层数必须大于1")
        
        # 计算网格间距
        spacing = (upper - lower) / Decimal(levels - 1)
        
        # 计算中心价格
        center_price = (upper + lower) / Decimal('2')
        
        # 生成网格层级
        grid_data = []
        
        for i in range(levels):
            # 计算价格
            price = lower + spacing * Decimal(i)
            
            # 计算层级索引 (中心为0，下方为负，上方为正)
            center_index = (levels - 1) / 2
            level_index = i - int(center_index)
            
            # 根据网格模式确定订单方向
            side = self._determine_side(price, center_price, level_index)
            
            grid_data.append({
                'level_index': level_index,
                'price': price,
                'side': side
            })
        
        logger.info(f"计算完成: {levels}层网格, 间距={spacing}, 中心价={center_price}")
        return grid_data
    
    def _determine_side(self, price: Decimal, center_price: Decimal, level_index: int) -> str:
        """
        根据网格模式确定订单方向

        Args:
            price: 网格价格
            center_price: 中心价格
            level_index: 层级索引

        Returns:
            订单方向 (BUY/SELL)
        """
        mode = self.config.grid_mode.upper()

        if mode == 'SHORT':
            # 做空网格: 上方卖单开仓，下方买单平仓
            return GridLevelSide.SELL if price >= center_price else GridLevelSide.BUY
        elif mode == 'LONG':
            # 做多网格: 下方买单开仓，上方卖单平仓
            return GridLevelSide.BUY if price <= center_price else GridLevelSide.SELL
        elif mode == 'NEUTRAL':
            # 中性网格: 上方卖单，下方买单
            return GridLevelSide.SELL if price >= center_price else GridLevelSide.BUY
        else:
            raise ValueError(f"不支持的网格模式: {self.config.grid_mode}")
    
    def initialize_grid(self, current_price: Decimal = None) -> List[GridLevel]:
        """
        首次启动初始化网格
        
        Args:
            current_price: 当前市场价格（用于计算中心价）
            
        Returns:
            创建的GridLevel对象列表
        """
        # 检查是否已存在网格层级
        existing_levels = GridLevel.objects.filter(config=self.config).count()
        if existing_levels > 0:
            logger.warning(f"配置 {self.config.name} 已存在 {existing_levels} 个网格层级，将清空重建")
            GridLevel.objects.filter(config=self.config).delete()
        
        # 计算网格层级数据
        grid_data = self.calculate_grid_levels()
        
        # 批量创建GridLevel对象
        levels_to_create = []
        for data in grid_data:
            level = GridLevel(
                config=self.config,
                level_index=data['level_index'],
                price=data['price'],
                side=data['side'],
                status=GridLevelStatus.IDLE
            )
            levels_to_create.append(level)
        
        # 批量保存
        created_levels = GridLevel.objects.bulk_create(levels_to_create)
        self.grid_levels = list(created_levels)
        
        logger.info(f"初始化完成: 创建了 {len(created_levels)} 个网格层级")
        return created_levels
    
    def recover_from_existing_positions(self) -> Tuple[List[GridLevel], List[str]]:
        """
        从现有持仓恢复网格状态
        
        用于策略重启时，根据数据库中的订单和持仓状态恢复网格
        
        Returns:
            (已加载的GridLevel列表, 孤立订单ID列表)
        """
        # 加载现有的网格层级
        existing_levels = GridLevel.objects.filter(config=self.config).order_by('level_index')
        
        if not existing_levels.exists():
            logger.warning(f"配置 {self.config.name} 没有现有网格层级，将执行初始化")
            return self.initialize_grid(), []
        
        self.grid_levels = list(existing_levels)
        
        # 识别孤立订单（有订单ID但状态异常的层级）
        orphan_orders = []
        for level in self.grid_levels:
            # 检查状态一致性
            if level.status == GridLevelStatus.ENTRY_WORKING and not level.entry_order_id:
                logger.warning(f"层级 {level.level_index} 状态为entry_working但无订单ID，重置为idle")
                level.status = GridLevelStatus.IDLE
                level.save()
            
            if level.status == GridLevelStatus.EXIT_WORKING and not level.exit_order_id:
                logger.warning(f"层级 {level.level_index} 状态为exit_working但无订单ID，重置为position_open")
                level.status = GridLevelStatus.POSITION_OPEN
                level.save()
            
            # 收集可能的孤立订单
            if level.entry_order_id and level.status == GridLevelStatus.IDLE:
                orphan_orders.append(level.entry_order_id)
            if level.exit_order_id and level.status not in [GridLevelStatus.EXIT_WORKING, GridLevelStatus.POSITION_OPEN]:
                orphan_orders.append(level.exit_order_id)
        
        logger.info(f"恢复完成: 加载了 {len(self.grid_levels)} 个网格层级，发现 {len(orphan_orders)} 个孤立订单")
        return self.grid_levels, orphan_orders
    
    def get_grid_summary(self) -> Dict:
        """
        获取网格摘要信息

        Returns:
            网格统计摘要
        """
        # 总是从数据库重新加载以获取最新状态
        self.grid_levels = list(GridLevel.objects.filter(config=self.config))

        total = len(self.grid_levels)
        idle = sum(1 for level in self.grid_levels if level.status == GridLevelStatus.IDLE)
        entry_working = sum(1 for level in self.grid_levels if level.status == GridLevelStatus.ENTRY_WORKING)
        position_open = sum(1 for level in self.grid_levels if level.status == GridLevelStatus.POSITION_OPEN)
        exit_working = sum(1 for level in self.grid_levels if level.status == GridLevelStatus.EXIT_WORKING)

        return {
            'config_name': self.config.name,
            'total_levels': total,
            'idle': idle,
            'entry_working': entry_working,
            'position_open': position_open,
            'exit_working': exit_working,
            'grid_spacing': self.config.grid_spacing,
            'grid_spacing_pct': self.config.grid_spacing_pct
        }

    def start(self, current_price: Optional[Decimal] = None) -> None:
        """
        启动网格引擎

        Args:
            current_price: 当前市场价格（可选）
        """
        logger.info(f"启动网格引擎: {self.config.name}")

        # 初始化策略
        from grid_trading.services.grid.short_grid import ShortGridStrategy
        from grid_trading.services.grid.order_sync import OrderSyncManager

        mode = self.config.grid_mode.upper()
        if mode == 'SHORT':
            self.strategy = ShortGridStrategy(self.config)
        else:
            raise ValueError(f"暂不支持的网格模式: {mode}")

        # 初始化订单同步管理器
        self.order_sync_manager = OrderSyncManager(self.config)

        # 尝试从现有持仓恢复，如果没有则初始化
        levels, orphans = self.recover_from_existing_positions()

        if orphans:
            TradeLog.log_warn(
                self.config,
                f"发现 {len(orphans)} 个孤立订单，建议手动检查"
            )
            logger.warning(f"发现 {len(orphans)} 个孤立订单，建议手动检查")

        # 加载网格层级到策略
        self.strategy.load_grid_levels()

        # 标记为运行中
        self.running = True
        self.last_persist_time = int(time.time())

        # 记录启动事件
        TradeLog.log_info(
            self.config,
            f"网格引擎启动成功: 加载了 {len(levels)} 个层级"
        )
        logger.info(f"网格引擎启动成功: 加载了 {len(levels)} 个层级")

    def stop(self) -> None:
        """停止网格引擎"""
        # 记录停止事件
        TradeLog.log_info(self.config, f"停止网格引擎: {self.config.name}")
        logger.info(f"停止网格引擎: {self.config.name}")
        self.running = False

        # 持久化最终状态
        self.persist_grid_levels()

        logger.info("网格引擎已停止")

    def tick(self, current_price: Optional[Decimal] = None) -> Dict:
        """
        执行一次同步循环

        Args:
            current_price: 当前市场价格（可选）

        Returns:
            同步结果统计
        """
        if not self.running:
            raise RuntimeError("引擎未启动，请先调用start()")

        # 重新加载网格层级以获取最新状态
        self.strategy.load_grid_levels()

        # 1. 检查持仓限制
        current_position = self.strategy.get_current_position()
        position_ok = self.strategy.check_position_limit(current_position)

        # 2. 计算理想订单
        ideal_orders = self.strategy.calculate_ideal_orders(current_price)

        # 3. 根据持仓限制过滤订单
        allowed_orders, filtered_orders = self.strategy.filter_orders_by_position_limit(
            ideal_orders,
            current_position
        )

        # 4. 同步订单
        created_orders, cancelled_orders = self.order_sync_manager.sync_orders(
            allowed_orders,
            self.exchange_adapter
        )

        # 5. 定期持久化（每10秒）
        current_time = int(time.time())
        if current_time - self.last_persist_time >= 10:
            self.persist_grid_levels()
            self.last_persist_time = current_time

        # 返回统计信息
        return {
            'current_position': current_position,
            'position_ok': position_ok,
            'ideal_orders_count': len(ideal_orders),
            'allowed_orders_count': len(allowed_orders),
            'filtered_orders_count': len(filtered_orders),
            'created_orders_count': len(created_orders),
            'cancelled_orders_count': len(cancelled_orders)
        }

    def persist_grid_levels(self) -> int:
        """
        持久化网格层级状态到数据库

        Returns:
            更新的层级数量
        """
        if not self.grid_levels:
            self.grid_levels = list(GridLevel.objects.filter(config=self.config))

        # 批量更新（Django会自动处理）
        updated_count = 0
        for level in self.grid_levels:
            # 刷新以确保最新状态
            level.refresh_from_db()
            updated_count += 1

        logger.debug(f"持久化了 {updated_count} 个网格层级状态")
        return updated_count

    def on_order_filled(self, order_id: str, intent: str) -> None:
        """
        处理订单成交事件

        Args:
            order_id: 订单ID
            intent: 订单意图 (ENTRY/EXIT)
        """
        from grid_trading.models import OrderIntent

        # 查找OrderIntent
        try:
            order_intent = OrderIntent.objects.get(order_id=order_id)
        except OrderIntent.DoesNotExist:
            logger.warning(f"未找到订单意图: {order_id}")
            return

        # 获取对应的GridLevel
        try:
            level = GridLevel.objects.get(
                config=self.config,
                level_index=order_intent.level_index
            )
        except GridLevel.DoesNotExist:
            logger.error(f"未找到网格层级: level_index={order_intent.level_index}")
            return

        # 调用策略处理成交
        updated_level = self.strategy.on_order_filled(level, intent)

        # 更新OrderIntent状态
        order_intent.mark_filled()

        logger.info(
            f"订单成交处理完成: order_id={order_id}, "
            f"level={level.level_index}, intent={intent}"
        )
