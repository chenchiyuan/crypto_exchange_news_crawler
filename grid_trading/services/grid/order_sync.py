"""
订单同步管理器
Order Synchronization Manager

负责对比理想订单与实际订单，实现幂等性挂单
"""
from decimal import Decimal
from typing import List, Dict, Tuple
import hashlib
import logging
import time
import random

from grid_trading.models import (
    GridConfig, GridLevel, OrderIntent, OrderIntentType, OrderSide, TradeLog
)

logger = logging.getLogger(__name__)


class OrderSyncManager:
    """订单同步管理器"""

    def __init__(self, config: GridConfig):
        """
        初始化订单同步管理器

        Args:
            config: 网格配置对象
        """
        self.config = config

    def generate_client_order_id(
        self,
        intent: str,
        side: str,
        level_index: int
    ) -> str:
        """
        生成client_order_id

        格式: {config_name}_{intent}_{side}_{level}_{timestamp}_{random}
        例如: test_btc_short_ENTRY_SELL_5_1701234567890_a3f2

        Args:
            intent: 订单意图 (ENTRY/EXIT)
            side: 订单方向 (BUY/SELL)
            level_index: 层级索引

        Returns:
            唯一的client_order_id
        """
        # 使用时间戳（毫秒）+ 4位随机数确保唯一性
        timestamp = int(time.time() * 1000)
        random_suffix = ''.join(random.choices('0123456789abcdef', k=4))

        # 组装client_order_id
        client_order_id = f"{self.config.name}_{intent}_{side}_{level_index}_{timestamp}_{random_suffix}"

        return client_order_id

    def sync_orders(
        self,
        ideal_orders: List[Dict],
        exchange_adapter
    ) -> Tuple[List[str], List[str]]:
        """
        同步订单：对比理想订单vs实际订单

        Args:
            ideal_orders: 理想订单列表，每个元素包含 {level, intent, side, price, amount}
            exchange_adapter: 交易所适配器（用于创建/撤销订单）

        Returns:
            (新创建的订单ID列表, 已撤销的订单ID列表)
        """
        # 加载当前数据库中的订单意图（活跃状态）
        from grid_trading.models import OrderStatus
        existing_intents = OrderIntent.objects.filter(
            config=self.config,
            status__in=[OrderStatus.NEW, OrderStatus.PARTIALLY_FILLED]
        )

        # 构建现有订单的四元组集合 (intent, side, price, level_index)
        existing_tuples = {}
        for intent_obj in existing_intents:
            # 规范化价格为8位小数
            normalized_price = Decimal(str(intent_obj.price)).quantize(Decimal('0.00000001'))
            key = (
                str(intent_obj.intent),  # 转为字符串确保一致性
                str(intent_obj.side),
                normalized_price,
                intent_obj.level_index
            )
            existing_tuples[key] = intent_obj

        # 构建理想订单的四元组集合
        ideal_tuples = {}
        for order in ideal_orders:
            # 规范化价格为8位小数
            normalized_price = Decimal(str(order['price'])).quantize(Decimal('0.00000001'))
            key = (
                str(order['intent']),  # 转为字符串确保一致性
                str(order['side']),
                normalized_price,
                order['level_index']
            )
            ideal_tuples[key] = order

        # 找出需要撤销的订单（存在于existing但不在ideal中）
        to_cancel = set(existing_tuples.keys()) - set(ideal_tuples.keys())

        # 找出需要创建的订单（存在于ideal但不在existing中）
        to_create = set(ideal_tuples.keys()) - set(existing_tuples.keys())

        # 执行撤销
        cancelled_order_ids = self.cancel_excess_orders(
            to_cancel,
            existing_tuples,
            exchange_adapter
        )

        # 执行创建
        created_order_ids = self.create_missing_orders(
            to_create,
            ideal_tuples,
            exchange_adapter
        )

        logger.info(
            f"订单同步完成: 创建={len(created_order_ids)}, 撤销={len(cancelled_order_ids)}"
        )

        return created_order_ids, cancelled_order_ids

    def cancel_excess_orders(
        self,
        to_cancel: set,
        existing_tuples: Dict,
        exchange_adapter
    ) -> List[str]:
        """
        撤销多余的订单

        Args:
            to_cancel: 需要撤销的订单四元组集合
            existing_tuples: 现有订单字典
            exchange_adapter: 交易所适配器

        Returns:
            已撤销的订单ID列表
        """
        from grid_trading.models import OrderStatus
        cancelled_order_ids = []

        for key in to_cancel:
            intent_obj = existing_tuples[key]

            # 获取对应的GridLevel
            level = GridLevel.objects.get(
                config=self.config,
                level_index=intent_obj.level_index
            )

            # 检查GridLevel是否被冷却
            if level.is_blocked():
                logger.info(
                    f"层级 {level.level_index} 处于冷却期，跳过撤单"
                )
                continue

            try:
                # 调用交易所API撤销订单
                if exchange_adapter and intent_obj.order_id:
                    exchange_adapter.cancel_order(
                        symbol=self.config.symbol,
                        order_id=intent_obj.order_id
                    )

                # 更新OrderIntent状态
                intent_obj.mark_canceled()

                # 更新GridLevel状态
                if intent_obj.intent == OrderIntentType.ENTRY:
                    level.cancel_entry_order()
                elif intent_obj.intent == OrderIntentType.EXIT:
                    level.cancel_exit_order()

                cancelled_order_ids.append(intent_obj.order_id)

                # 记录事件
                TradeLog.log_order(
                    self.config,
                    f"撤销订单: {intent_obj.client_order_id}, 层级={level.level_index}",
                    order_id=intent_obj.order_id,
                    level_index=level.level_index
                )

                logger.info(
                    f"撤销订单成功: {intent_obj.client_order_id}, "
                    f"层级={level.level_index}"
                )

            except Exception as e:
                logger.error(
                    f"撤销订单失败: {intent_obj.client_order_id}, "
                    f"错误={str(e)}"
                )
                # 记录错误事件
                TradeLog.log_error(
                    self.config,
                    f"撤销订单失败: {intent_obj.client_order_id}, 错误={str(e)}",
                    order_id=intent_obj.order_id,
                    level_index=level.level_index
                )
                # 设置冷却期（5秒）
                level.set_blocked(duration_ms=5000)

        return cancelled_order_ids

    def create_missing_orders(
        self,
        to_create: set,
        ideal_tuples: Dict,
        exchange_adapter
    ) -> List[str]:
        """
        创建缺失的订单

        Args:
            to_create: 需要创建的订单四元组集合
            ideal_tuples: 理想订单字典
            exchange_adapter: 交易所适配器

        Returns:
            新创建的订单ID列表
        """
        from grid_trading.models import OrderStatus
        created_order_ids = []

        for key in to_create:
            order = ideal_tuples[key]
            level = order['level']

            # 检查GridLevel是否被冷却
            if level.is_blocked():
                logger.info(
                    f"层级 {level.level_index} 处于冷却期，跳过创建订单"
                )
                continue

            # 检查是否可以挂单
            if order['intent'] == OrderIntentType.ENTRY and not level.can_place_entry_order():
                logger.warning(
                    f"层级 {level.level_index} 状态={level.status}，blocked={level.is_blocked()}，不能挂开仓单"
                )
                continue

            if order['intent'] == OrderIntentType.EXIT and not level.can_place_exit_order():
                logger.warning(
                    f"层级 {level.level_index} 状态={level.status}，blocked={level.is_blocked()}，不能挂平仓单"
                )
                continue

            # 生成client_order_id
            client_order_id = self.generate_client_order_id(
                intent=order['intent'],
                side=order['side'],
                level_index=level.level_index
            )

            try:
                # 调用交易所API创建订单
                if exchange_adapter:
                    response = exchange_adapter.create_order(
                        symbol=self.config.symbol,
                        side=order['side'],
                        order_type='LIMIT',
                        quantity=float(order['amount']),
                        price=float(order['price']),
                        client_order_id=client_order_id
                    )
                    exchange_order_id = response.get('orderId') or response.get('order_id')
                else:
                    # 测试模式：生成模拟订单ID
                    exchange_order_id = f"test_{client_order_id}"

                # 创建OrderIntent记录
                intent_obj = OrderIntent.objects.create(
                    config=self.config,
                    level_index=level.level_index,
                    intent=order['intent'],
                    side=order['side'],
                    price=order['price'],
                    amount=order['amount'],
                    client_order_id=client_order_id,
                    order_id=exchange_order_id,
                    status=OrderStatus.NEW
                )

                # 更新GridLevel状态
                if order['intent'] == OrderIntentType.ENTRY:
                    level.transition_to_entry_working(
                        entry_order_id=exchange_order_id,
                        entry_client_id=client_order_id
                    )
                elif order['intent'] == OrderIntentType.EXIT:
                    level.transition_to_exit_working(
                        exit_order_id=exchange_order_id,
                        exit_client_id=client_order_id
                    )

                created_order_ids.append(exchange_order_id)

                # 记录事件
                intent_label = "开仓" if order['intent'] == OrderIntentType.ENTRY else "平仓"
                TradeLog.log_order(
                    self.config,
                    f"挂{intent_label}单: {client_order_id}, 层级={level.level_index}, "
                    f"价格={order['price']}, 数量={order['amount']}",
                    order_id=exchange_order_id,
                    level_index=level.level_index
                )

                logger.info(
                    f"创建订单成功: {client_order_id}, "
                    f"层级={level.level_index}, 价格={order['price']}, "
                    f"数量={order['amount']}"
                )

            except Exception as e:
                logger.error(
                    f"创建订单失败: 层级={level.level_index}, "
                    f"错误={str(e)}"
                )
                # 记录错误事件
                TradeLog.log_error(
                    self.config,
                    f"挂单失败: 层级={level.level_index}, 价格={order['price']}, 错误={str(e)}",
                    level_index=level.level_index
                )
                # 设置冷却期（5秒）
                level.set_blocked(duration_ms=5000)

        return created_order_ids
