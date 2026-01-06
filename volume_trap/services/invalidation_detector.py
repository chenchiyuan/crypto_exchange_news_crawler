"""
失效检测器（Invalidation Detector）

检测价格收复场景，将监控记录标记为invalidated状态。

业务逻辑：
    - 价格收复定义：current_close > P_trigger
    - 失效含义：价格收复说明"弃盘"判断失败，市场重新获得支撑
    - 状态更新：pending/suspected/confirmed → invalidated

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第三部分-5.1 价格收复检测)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (状态机管理层-失效检测)
    - Task: TASK-002-022
"""

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from backtest.models import KLine
from volume_trap.models import VolumeTrapMonitor, VolumeTrapStateTransition

logger = logging.getLogger(__name__)


class InvalidationDetector:
    """失效检测器。

    检测价格收复场景，自动将监控记录标记为invalidated状态。

    业务逻辑：
        - 扫描所有非invalidated状态的监控记录
        - 获取最新收盘价，与触发价格P_trigger对比
        - 如果current_close > P_trigger，则判定为价格收复
        - 更新状态为invalidated，并记录StateTransition日志

    业务含义：
        - 价格收复：市场重新获得支撑，弃盘判断失效
        - 失效标记：帮助用户快速识别无效监控，避免误导决策
        - 监控池清理：失效记录可被定期清理，节省存储空间

    设计原则：
        - 无状态：每次调用check_all()都重新扫描
        - 容错机制：单个合约失败不影响其他合约
        - 事务管理：使用Django transaction.atomic确保原子性
        - 详细日志：记录检测过程和失效原因

    Examples:
        >>> # 初始化检测器
        >>> detector = InvalidationDetector()
        >>> # 检测所有4h周期的失效记录
        >>> result = detector.check_all(interval='4h')
        >>> print(f"失效记录数: {result['invalidated_count']}")

    Related:
        - PRD: 第三部分-5.1 价格收复检测
        - Architecture: 状态机管理层 - InvalidationDetector
        - Task: TASK-002-022
    """

    def check_all(self, interval: str = "4h", market_type: str = "futures") -> Dict:
        """检测所有非invalidated记录的价格收复情况。

        扫描所有非invalidated状态的监控记录，检测价格是否收复到触发价格之上。

        业务逻辑：
            1. 获取所有status != 'invalidated'且market_type匹配的监控记录（按interval筛选）
            2. 对每个记录获取最新K线的收盘价
            3. 判断：current_close > P_trigger
            4. 如果收复，更新状态为invalidated，创建StateTransition日志
            5. 统计失效记录数量

        Args:
            interval: K线周期（'1h'/'4h'/'1d'），默认'4h'
            market_type: 市场类型（'spot'现货或'futures'合约），默认'futures'

        Returns:
            Dict: 检测结果统计，包含以下键：
                - checked_count (int): 检测的监控记录数量
                - invalidated_count (int): 失效记录数量
                - errors (List[str]): 错误日志列表

        Raises:
            ValueError: 当interval不在['1h','4h','1d']中时

        Side Effects:
            - 更新VolumeTrapMonitor记录的status字段
            - 创建VolumeTrapStateTransition日志
            - 数据库写入操作使用transaction.atomic确保原子性

        Examples:
            >>> detector = InvalidationDetector()
            >>> # 检测4h周期
            >>> result = detector.check_all(interval='4h')
            >>> print(f"检测{result['checked_count']}条，失效{result['invalidated_count']}条")

            >>> # 检测1h周期
            >>> result = detector.check_all(interval='1h')

        Context:
            - PRD Requirement: 价格收复检测
            - Architecture: 失效检测器 - check_all方法
            - Task: TASK-002-022

        Performance:
            - 执行时间取决于监控记录数量
            - 建议在定时任务中异步执行
        """
        # === Guard Clause: 验证interval参数 ===
        valid_intervals = ["1h", "4h", "1d"]
        if interval not in valid_intervals:
            raise ValueError(f"interval参数错误: 预期{valid_intervals}, 实际值='{interval}'")

        result = {"checked_count": 0, "invalidated_count": 0, "errors": []}

        logger.info(f"=== 开始失效检测 (interval={interval}, market_type={market_type}) ===")

        # === 获取所有非invalidated状态的监控记录（根据market_type筛选） ===
        monitors = VolumeTrapMonitor.objects.filter(
            interval=interval, market_type=market_type
        ).exclude(status="invalidated")

        result["checked_count"] = len(monitors)
        logger.info(f"失效检测: 扫描{len(monitors)}个监控记录...")

        for monitor in monitors:
            try:
                # === 检测价格收复 ===
                is_recovered = self._check_price_recovery(monitor)

                if is_recovered:
                    # === 更新状态为invalidated（使用transaction确保原子性）===
                    with transaction.atomic():
                        self._update_to_invalidated(monitor)
                        result["invalidated_count"] += 1
                        # 获取交易对符号（支持现货和合约）
                        contract = (
                            monitor.futures_contract
                            if monitor.futures_contract
                            else monitor.spot_contract
                        )
                        symbol = contract.symbol if contract else "Unknown"
                        logger.info(f"失效检测触发: {symbol} (价格收复)")

            except Exception as e:
                # 获取交易对符号（支持现货和合约）
                contract = (
                    monitor.futures_contract if monitor.futures_contract else monitor.spot_contract
                )
                symbol = contract.symbol if contract else "Unknown"
                error_msg = f"失效检测失败: {symbol} - {str(e)}"
                logger.error(error_msg, exc_info=True)
                result["errors"].append(error_msg)
                continue

        logger.info(f"=== 失效检测完成 ===")
        logger.info(
            f"结果: 检测{result['checked_count']}, "
            f"失效{result['invalidated_count']}, "
            f"错误{len(result['errors'])}"
        )

        return result

    def _check_price_recovery(self, monitor: VolumeTrapMonitor) -> bool:
        """检测价格是否收复到触发价格之上。

        Args:
            monitor: 监控记录

        Returns:
            bool: 是否收复（True=收复，False=未收复）

        Raises:
            ValueError: 当P_trigger=0时

        Side Effects:
            - 只读操作，无状态修改
        """
        # === Guard Clause: 检查P_trigger是否为0 ===
        if monitor.trigger_price == Decimal("0"):
            error_msg = f"跳过{monitor.futures_contract.symbol}: P_trigger=0（数据异常）"
            logger.error(error_msg)
            raise ValueError(f"P_trigger不能为0 (monitor_id={monitor.id})")

        # === 获取最新K线的收盘价 ===
        symbol = monitor.futures_contract.symbol
        interval = monitor.interval

        latest_kline = (
            KLine.objects.filter(symbol=symbol, interval=interval).order_by("-open_time").first()
        )

        if latest_kline is None:
            logger.warning(f"跳过{symbol}: 无最新K线数据")
            return False

        # === 判断价格收复：current_close > P_trigger ===
        current_close = latest_kline.close_price
        is_recovered = current_close > monitor.trigger_price

        if is_recovered:
            logger.debug(
                f"{symbol}: 价格收复检测触发 "
                f"(current_close={current_close}, P_trigger={monitor.trigger_price})"
            )

        return is_recovered

    def _update_to_invalidated(self, monitor: VolumeTrapMonitor):
        """更新Monitor记录状态为invalidated。

        Args:
            monitor: 监控记录

        Side Effects:
            - 更新Monitor的status字段
            - 创建StateTransition日志
        """
        # 记录原状态
        old_status = monitor.status

        # 更新Monitor状态
        monitor.status = "invalidated"
        monitor.save()

        # 创建StateTransition日志
        VolumeTrapStateTransition.objects.create(
            monitor=monitor,
            from_status=old_status,
            to_status="invalidated",
            trigger_condition={
                "reason": "price_recovery",
                "current_close": float(self._get_current_close(monitor)),
                "trigger_price": float(monitor.trigger_price),
            },
            transition_time=timezone.now(),
        )

        logger.info(f"失效更新: {monitor.futures_contract.symbol} " f"({old_status} → invalidated)")

    def _get_current_close(self, monitor: VolumeTrapMonitor) -> Decimal:
        """获取当前最新收盘价。

        Args:
            monitor: 监控记录

        Returns:
            Decimal: 最新收盘价
        """
        latest_kline = (
            KLine.objects.filter(symbol=monitor.futures_contract.symbol, interval=monitor.interval)
            .order_by("-open_time")
            .first()
        )

        if latest_kline:
            return latest_kline.close_price
        else:
            return Decimal("0")
