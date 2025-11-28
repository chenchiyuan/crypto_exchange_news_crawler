"""
风险管理服务
Risk Manager Service

功能:
1. 仓位限制检查
2. 多策略并发控制
3. 止损触发检查
4. 风险指标监控
"""
import logging
from decimal import Decimal
from typing import Dict, List, Optional
from django.db.models import Sum, Q

from grid_trading.models import GridStrategy, GridOrder

logger = logging.getLogger(__name__)


class RiskManager:
    """风险管理器"""

    def __init__(self):
        """初始化风险管理器"""
        pass

    def check_max_position_limit(
        self,
        symbol: str,
        new_position_value: float,
        max_position_usdt: float
    ) -> bool:
        """
        检查是否超过最大仓位限制

        Args:
            symbol: 交易对
            new_position_value: 新增仓位价值(USDT)
            max_position_usdt: 最大允许仓位(USDT)

        Returns:
            bool: True=允许, False=拒绝
        """
        # 计算当前总仓位
        current_position = self.calculate_total_position_value(symbol)

        # 预估新总仓位
        projected_position = current_position + new_position_value

        if projected_position > max_position_usdt:
            logger.warning(
                f"仓位限制触发: symbol={symbol}, "
                f"current={current_position:.2f}, "
                f"projected={projected_position:.2f}, "
                f"limit={max_position_usdt:.2f}"
            )
            return False

        logger.info(
            f"仓位检查通过: symbol={symbol}, "
            f"projected={projected_position:.2f}/{max_position_usdt:.2f}"
        )
        return True

    def calculate_total_position_value(self, symbol: str) -> float:
        """
        计算指定交易对的总仓位价值

        Args:
            symbol: 交易对

        Returns:
            float: 总仓位价值(USDT)
        """
        # 查询所有active策略
        active_strategies = GridStrategy.objects.filter(
            symbol=symbol,
            status='active'
        )

        total_value = 0.0

        for strategy in active_strategies:
            # 计算策略的仓位价值
            position_value = strategy.calculate_total_position_value()
            total_value += position_value

        logger.debug(
            f"总仓位计算: symbol={symbol}, "
            f"strategies={active_strategies.count()}, "
            f"total_value={total_value:.2f}"
        )

        return total_value

    def check_concurrent_strategy_limit(
        self,
        symbol: str,
        max_concurrent: int = 3
    ) -> bool:
        """
        检查并发策略数量限制

        Args:
            symbol: 交易对
            max_concurrent: 最大并发策略数

        Returns:
            bool: True=允许, False=拒绝
        """
        active_count = GridStrategy.objects.filter(
            symbol=symbol,
            status='active'
        ).count()

        if active_count >= max_concurrent:
            logger.warning(
                f"并发策略限制触发: symbol={symbol}, "
                f"active={active_count}, limit={max_concurrent}"
            )
            return False

        logger.info(
            f"并发检查通过: symbol={symbol}, "
            f"active={active_count}/{max_concurrent}"
        )
        return True

    def check_stop_loss(
        self,
        strategy: GridStrategy,
        current_price: float
    ) -> bool:
        """
        检查是否触发止损

        Args:
            strategy: 策略实例
            current_price: 当前价格

        Returns:
            bool: True=触发止损, False=正常
        """
        if not strategy.entry_price or strategy.status != 'active':
            return False

        entry_price = float(strategy.entry_price)
        stop_loss_pct = float(strategy.stop_loss_pct)

        # 计算止损价格
        if strategy.strategy_type == 'long':
            # 做多: 价格下跌超过止损百分比
            stop_loss_price = entry_price * (1 - stop_loss_pct)
            triggered = current_price <= stop_loss_price

            if triggered:
                logger.warning(
                    f"止损触发(做多): strategy_id={strategy.id}, "
                    f"entry=${entry_price:.2f}, "
                    f"current=${current_price:.2f}, "
                    f"stop_loss=${stop_loss_price:.2f}, "
                    f"loss_pct={(entry_price-current_price)/entry_price*100:.2f}%"
                )

            return triggered

        elif strategy.strategy_type == 'short':
            # 做空: 价格上涨超过止损百分比
            stop_loss_price = entry_price * (1 + stop_loss_pct)
            triggered = current_price >= stop_loss_price

            if triggered:
                logger.warning(
                    f"止损触发(做空): strategy_id={strategy.id}, "
                    f"entry=${entry_price:.2f}, "
                    f"current=${current_price:.2f}, "
                    f"stop_loss=${stop_loss_price:.2f}, "
                    f"loss_pct={(current_price-entry_price)/entry_price*100:.2f}%"
                )

            return triggered

        return False

    def get_strategy_risk_metrics(self, strategy: GridStrategy) -> Dict:
        """
        获取策略风险指标

        Args:
            strategy: 策略实例

        Returns:
            Dict: 风险指标字典
        """
        # 统计订单
        total_orders = strategy.gridorder_set.count()
        pending_orders = strategy.gridorder_set.filter(status='pending').count()
        filled_orders = strategy.gridorder_set.filter(status='filled').count()

        # 计算已用仓位
        position_value = strategy.calculate_total_position_value()

        # 计算浮动盈亏百分比
        pnl_pct = 0.0
        if strategy.entry_price and position_value > 0:
            pnl_pct = float(strategy.current_pnl) / position_value * 100

        metrics = {
            'strategy_id': strategy.id,
            'symbol': strategy.symbol,
            'status': strategy.status,
            'entry_price': float(strategy.entry_price) if strategy.entry_price else None,
            'current_pnl': float(strategy.current_pnl),
            'pnl_pct': pnl_pct,
            'position_value': position_value,
            'total_orders': total_orders,
            'pending_orders': pending_orders,
            'filled_orders': filled_orders,
            'fill_rate': filled_orders / total_orders * 100 if total_orders > 0 else 0,
            'stop_loss_pct': float(strategy.stop_loss_pct) * 100,
        }

        return metrics

    def get_symbol_risk_summary(self, symbol: str) -> Dict:
        """
        获取交易对风险汇总

        Args:
            symbol: 交易对

        Returns:
            Dict: 风险汇总字典
        """
        active_strategies = GridStrategy.objects.filter(
            symbol=symbol,
            status='active'
        )

        total_position_value = 0.0
        total_pnl = Decimal('0.00')

        for strategy in active_strategies:
            total_position_value += strategy.calculate_total_position_value()
            total_pnl += strategy.current_pnl

        summary = {
            'symbol': symbol,
            'active_strategies': active_strategies.count(),
            'total_position_value': total_position_value,
            'total_pnl': float(total_pnl),
            'total_pnl_pct': (
                float(total_pnl) / total_position_value * 100
                if total_position_value > 0 else 0
            ),
        }

        return summary

    def validate_new_strategy(
        self,
        symbol: str,
        estimated_position_value: float,
        max_position_usdt: float,
        max_concurrent: int = 3
    ) -> tuple[bool, Optional[str]]:
        """
        验证是否可以创建新策略

        Args:
            symbol: 交易对
            estimated_position_value: 预估仓位价值
            max_position_usdt: 最大仓位限制
            max_concurrent: 最大并发策略数

        Returns:
            (bool, str): (是否允许, 拒绝原因)
        """
        # 检查并发策略数量
        if not self.check_concurrent_strategy_limit(symbol, max_concurrent):
            return False, f"并发策略数量已达上限({max_concurrent})"

        # 检查仓位限制
        if not self.check_max_position_limit(symbol, estimated_position_value, max_position_usdt):
            current_position = self.calculate_total_position_value(symbol)
            return False, (
                f"仓位超限: 当前${current_position:.2f} + "
                f"新增${estimated_position_value:.2f} > "
                f"限制${max_position_usdt:.2f}"
            )

        return True, None


# 全局单例
_risk_manager = None


def get_risk_manager() -> RiskManager:
    """
    获取风险管理器单例

    Returns:
        RiskManager: 风险管理器实例
    """
    global _risk_manager
    if _risk_manager is None:
        _risk_manager = RiskManager()
    return _risk_manager
