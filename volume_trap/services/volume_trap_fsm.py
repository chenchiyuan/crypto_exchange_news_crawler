"""
巨量诱多/弃盘检测状态机（Volume Trap Finite State Machine）

实现三阶段状态机逻辑：Discovery → Confirmation → Validation

Related:
    - PRD: docs/iterations/002-volume-trap-detection/prd.md (第二部分-功能模块拆解)
    - Architecture: docs/iterations/002-volume-trap-detection/architecture.md (状态机管理层)
    - Task: TASK-002-021
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from backtest.models import KLine
from monitor.models import FuturesContract, SpotContract
from volume_trap.detectors.amplitude_detector import AmplitudeDetector
from volume_trap.detectors.atr_compression_detector import ATRCompressionDetector
from volume_trap.detectors.key_level_breach_detector import KeyLevelBreachDetector
from volume_trap.detectors.moving_average_cross_detector import MovingAverageCrossDetector
from volume_trap.detectors.obv_divergence_analyzer import OBVDivergenceAnalyzer
from volume_trap.detectors.price_efficiency_analyzer import PriceEfficiencyAnalyzer
from volume_trap.detectors.rvol_calculator import RVOLCalculator
from volume_trap.detectors.volume_retention_analyzer import VolumeRetentionAnalyzer
from volume_trap.evaluators.condition_evaluator import ConditionEvaluator
from volume_trap.exceptions import DataInsufficientError, InvalidDataError
from volume_trap.models import VolumeTrapIndicators, VolumeTrapMonitor, VolumeTrapStateTransition

logger = logging.getLogger(__name__)


class VolumeTrapStateMachine:
    """巨量诱多/弃盘检测状态机。

    实现三阶段状态机逻辑，协调8个检测器和1个评估器完成弃盘检测。

    三阶段流转：
        - Discovery（发现）: 全量扫描 → 创建Monitor记录（status=pending）
        - Confirmation（确认）: pending → suspected_abandonment
        - Validation（验证）: suspected_abandonment → confirmed_abandonment

    设计模式：
        - 依赖注入：所有检测器通过构造函数注入
        - 事务管理：使用Django transaction.atomic确保原子性
        - 状态追踪：创建StateTransition日志记录状态流转
        - 快照存储：状态变更时创建Indicators快照

    Attributes:
        rvol_calculator (RVOLCalculator): RVOL计算器
        amplitude_detector (AmplitudeDetector): 振幅检测器
        volume_retention_analyzer (VolumeRetentionAnalyzer): 成交量留存分析器
        key_level_breach_detector (KeyLevelBreachDetector): 关键位跌破检测器
        price_efficiency_analyzer (PriceEfficiencyAnalyzer): 价差效率分析器
        ma_cross_detector (MovingAverageCrossDetector): 均线交叉检测器
        obv_divergence_analyzer (OBVDivergenceAnalyzer): OBV背离分析器
        atr_compression_detector (ATRCompressionDetector): ATR压缩检测器
        condition_evaluator (ConditionEvaluator): 条件评估器

    Examples:
        >>> # 初始化状态机（注入所有检测器）
        >>> fsm = VolumeTrapStateMachine()
        >>> # 执行三阶段扫描
        >>> result = fsm.scan(interval='4h')
        >>> print(f"发现: {result['discovery']}, 确认: {result['confirmation']}, 验证: {result['validation']}")

    Related:
        - PRD: 第二部分-功能模块拆解
        - Architecture: 状态机管理层 - VolumeTrapStateMachine
        - Task: TASK-002-021
    """

    def __init__(self):
        """初始化状态机，注入所有检测器和评估器。

        使用默认配置初始化8个检测器和1个评估器。

        Examples:
            >>> fsm = VolumeTrapStateMachine()
            >>> fsm.rvol_calculator is not None
            True
        """
        # 初始化检测器（使用默认配置）
        self.rvol_calculator = RVOLCalculator()
        self.amplitude_detector = AmplitudeDetector()
        self.volume_retention_analyzer = VolumeRetentionAnalyzer()
        self.key_level_breach_detector = KeyLevelBreachDetector()
        self.price_efficiency_analyzer = PriceEfficiencyAnalyzer()
        self.ma_cross_detector = MovingAverageCrossDetector()
        self.obv_divergence_analyzer = OBVDivergenceAnalyzer()
        self.atr_compression_detector = ATRCompressionDetector()

        # 初始化评估器
        self.condition_evaluator = ConditionEvaluator()

    def _get_monitor_symbol(self, monitor: VolumeTrapMonitor) -> str:
        """获取监控记录的符号。

        Args:
            monitor: 监控记录

        Returns:
            str: 符号

        Raises:
            ValueError: 当monitor既没有futures_contract也没有spot_contract时
        """
        if monitor.market_type == "futures":
            if not monitor.futures_contract:
                raise ValueError(f"Futures monitor missing futures_contract: {monitor.id}")
            return monitor.futures_contract.symbol
        elif monitor.market_type == "spot":
            if not monitor.spot_contract:
                raise ValueError(f"Spot monitor missing spot_contract: {monitor.id}")
            return monitor.spot_contract.symbol
        else:
            raise ValueError(f"Invalid market_type: {monitor.market_type}")

    def scan(self, interval: str = "4h", market_type: str = "futures") -> Dict:
        """执行三阶段扫描。

        依次执行Discovery、Confirmation、Validation三个阶段的扫描。

        业务逻辑：
            1. Discovery: 扫描所有active合约/现货，发现异常放量 → 创建Monitor记录
            2. Confirmation: 扫描pending记录，确认弃盘特征 → 更新为suspected
            3. Validation: 扫描suspected记录，验证趋势反转 → 更新为confirmed

        Args:
            interval: K线周期（'1h'/'4h'/'1d'），默认'4h'
            market_type: 市场类型（'spot'现货或'futures'合约），默认'futures'

        Returns:
            Dict: 扫描结果统计，包含以下键：
                - discovery (int): 发现阶段新增监控数量
                - confirmation (int): 确认阶段状态转换数量
                - validation (int): 验证阶段状态转换数量
                - errors (List[str]): 错误日志列表

        Raises:
            ValueError: 当interval不在['1h','4h','1d']中时

        Side Effects:
            - 创建/更新VolumeTrapMonitor记录
            - 创建VolumeTrapStateTransition日志
            - 创建VolumeTrapIndicators快照
            - 数据库写入操作使用transaction.atomic确保原子性

        Examples:
            >>> fsm = VolumeTrapStateMachine()
            >>> result = fsm.scan(interval='4h')
            >>> print(f"新增监控: {result['discovery']}")

        Context:
            - PRD Requirement: 三阶段状态机流转
            - Architecture: 状态机管理层 - scan方法
            - Task: TASK-002-021

        Performance:
            - 执行时间取决于合约数量和K线数据量
            - 建议在定时任务中异步执行
        """
        # === Guard Clause: 验证interval参数 ===
        valid_intervals = ["1h", "4h", "1d"]
        if interval not in valid_intervals:
            raise ValueError(f"interval参数错误: 预期{valid_intervals}, 实际值='{interval}'")

        result = {"discovery": 0, "confirmation": 0, "validation": 0, "errors": []}

        logger.info(f"=== 开始执行三阶段扫描 (interval={interval}) ===")

        # === 阶段1: Discovery（发现阶段）===
        try:
            discovery_count = self._scan_discovery(interval, market_type)
            result["discovery"] = discovery_count
            logger.info(f"阶段1完成: 新增监控{discovery_count}个")
        except Exception as e:
            error_msg = f"Discovery阶段异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result["errors"].append(error_msg)

        # === 阶段2: Confirmation（确认阶段）===
        try:
            confirmation_count = self._scan_confirmation(interval, market_type)
            result["confirmation"] = confirmation_count
            logger.info(f"阶段2完成: 状态转换{confirmation_count}个")
        except Exception as e:
            error_msg = f"Confirmation阶段异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result["errors"].append(error_msg)

        # === 阶段3: Validation（验证阶段）===
        try:
            validation_count = self._scan_validation(interval, market_type)
            result["validation"] = validation_count
            logger.info(f"阶段3完成: 状态转换{validation_count}个")
        except Exception as e:
            error_msg = f"Validation阶段异常: {str(e)}"
            logger.error(error_msg, exc_info=True)
            result["errors"].append(error_msg)

        logger.info(f"=== 三阶段扫描完成 ===")
        logger.info(
            f"结果: 发现{result['discovery']}, "
            f"确认{result['confirmation']}, "
            f"验证{result['validation']}, "
            f"错误{len(result['errors'])}"
        )

        return result

    def scan_historical(
        self,
        interval: str,
        market_type: str = "futures",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        batch_size: int = 1000,
    ) -> Dict:
        """执行历史数据扫描。

        批量扫描多个交易对的历史数据，发现异常事件并创建监控记录。

        Args:
            interval: K线周期（'1h'/'4h'/'1d'）
            market_type: 市场类型（'spot'现货或'futures'合约），默认'futures'
            start_date: 开始日期，'all'或不指定表示扫描全部历史，默认'all'
            end_date: 结束日期，可选
            batch_size: 批处理大小，默认1000

        Returns:
            Dict: 扫描结果统计，包含以下键：
                - total_contracts (int): 总交易对数量
                - processed (int): 已处理数量
                - found_events (int): 发现的异常事件数量
                - events (List[VolumeTrapMonitor]): 异常事件列表

        Side Effects:
            - 创建VolumeTrapMonitor记录
            - 创建VolumeTrapStateTransition日志
            - 创建VolumeTrapIndicators快照

        Context:
            - TASK-005-002: 实现历史数据批量扫描逻辑
            - Architecture: Discovery历史扫描优化

        Examples:
            >>> fsm = VolumeTrapStateMachine()
            >>> result = fsm.scan_historical(
            ...     interval='4h',
            ...     market_type='futures',
            ...     start_date='2025-11-01',
            ...     end_date='2025-11-30',
            ...     batch_size=500
            ... )
            >>> print(f"发现{result['found_events']}个异常事件")
        """
        # === Guard Clause: 验证参数 ===
        valid_intervals = ["1h", "4h", "1d"]
        if interval not in valid_intervals:
            raise ValueError(f"interval参数错误: 预期{valid_intervals}, 实际值='{interval}'")

        valid_market_types = ["spot", "futures"]
        if market_type not in valid_market_types:
            raise ValueError(
                f"market_type参数错误: 预期{valid_market_types}, 实际值='{market_type}'"
            )

        if batch_size <= 0:
            raise ValueError(f"batch_size参数错误: 预期>0, 实际值={batch_size}")

        # === 默认值处理 ===
        if not start_date:
            start_date = "all"

        # === 获取交易对列表 ===
        if market_type == "futures":
            contracts_query = FuturesContract.objects.filter(
                status="active", contract_type="perpetual"
            )
            logger.info(f"Discovery: 扫描{len(contracts_query)}个合约...")
        elif market_type == "spot":
            contracts_query = SpotContract.objects.filter(status="active")
            logger.info(f"Discovery: 扫描{len(contracts_query)}个现货交易对...")
        else:
            raise ValueError(f"无效的market_type: {market_type}")

        # 转换为列表以便分批处理
        contracts_list = list(contracts_query)

        # 过滤掉没有K线数据的交易对
        valid_contracts = []
        for contract in contracts_list:
            # 检查是否有对应interval和market_type的K线数据
            has_klines = KLine.objects.filter(
                symbol=contract.symbol, interval=interval, market_type=market_type
            ).exists()
            if has_klines:
                valid_contracts.append(contract)

        contracts = valid_contracts
        total_contracts = len(contracts)
        processed = 0
        found_events = []

        logger.info(
            f"开始历史扫描 (interval={interval}, market_type={market_type}, "
            f"start={start_date}, end={end_date}, batch_size={batch_size})"
        )

        # === 分批处理 ===
        for i in range(0, total_contracts, batch_size):
            batch = contracts[i : i + batch_size]

            for contract in batch:
                symbol = contract.symbol

                try:
                    # 检测是否触发Discovery条件
                    triggered, indicators = self._check_discovery_condition(
                        symbol=symbol, interval=interval, start_date=start_date, end_date=end_date
                    )

                    if triggered:
                        # 创建监控记录（使用transaction确保原子性）
                        with transaction.atomic():
                            monitor = self._create_monitor_record(
                                contract=contract,
                                market_type=market_type,
                                interval=interval,
                                indicators=indicators,
                            )
                            found_events.append(monitor)
                            logger.info(
                                f"历史扫描触发: {symbol} ({interval}) at {indicators['trigger_time']}"
                            )

                except Exception as e:
                    # 单个交易对失败，记录日志并继续
                    logger.error(f"扫描{symbol}失败: {str(e)}")
                    continue

            processed += len(batch)
            progress = (processed / total_contracts) * 100 if total_contracts > 0 else 100
            logger.info(f"扫描进度: {progress:.1f}% ({processed}/{total_contracts})")

        logger.info(
            f"历史扫描完成: 总计{total_contracts}, 已处理{processed}, "
            f"发现{len(found_events)}个异常事件"
        )

        return {
            "total_contracts": total_contracts,
            "processed": processed,
            "found_events": len(found_events),
            "events": found_events,
        }

    def _scan_discovery(self, interval: str, market_type: str) -> int:
        """Discovery阶段扫描：检测异常放量，创建Monitor记录。

        扫描所有active合约/现货，检测RVOL和振幅是否同时触发，触发时创建Monitor记录。

        业务逻辑：
            1. 获取所有active的合约或现货（根据market_type）
            2. 对每个合约/现货调用RVOL计算器和振幅检测器
            3. 使用条件评估器判断是否满足Discovery条件
            4. 满足条件时创建Monitor记录（status=pending, phase_1_passed=True）
            5. 创建StateTransition日志和Indicators快照

        Args:
            interval: K线周期
            market_type: 市场类型（'spot'现货或'futures'合约）

        Returns:
            int: 新增监控记录数量

        Side Effects:
            - 创建VolumeTrapMonitor记录
            - 创建VolumeTrapStateTransition日志
            - 创建VolumeTrapIndicators快照
        """
        count = 0

        # 根据market_type获取对应的交易对
        if market_type == "futures":
            contracts = FuturesContract.objects.filter(status="active", contract_type="perpetual")
            logger.info(f"Discovery: 扫描{len(contracts)}个合约...")
        elif market_type == "spot":
            contracts = SpotContract.objects.filter(status="active")
            logger.info(f"Discovery: 扫描{len(contracts)}个现货交易对...")
        else:
            raise ValueError(f"无效的market_type: {market_type}, 期望值为'spot'或'futures'")

        for contract in contracts:
            try:
                # 检测是否触发Discovery条件
                triggered, indicators = self._check_discovery_condition(contract.symbol, interval)

                if triggered:
                    # 创建Monitor记录（使用transaction确保原子性）
                    with transaction.atomic():
                        self._create_monitor_record(
                            contract=contract,
                            market_type=market_type,
                            interval=interval,
                            indicators=indicators,
                        )
                        count += 1
                        logger.info(f"Discovery触发: {contract.symbol} ({interval})")

            except DataInsufficientError as e:
                # 数据不足，跳过该合约/现货
                logger.debug(f"跳过{contract.symbol}: 数据不足 ({e})")
                continue
            except Exception as e:
                logger.warning(f"Discovery检测失败: {contract.symbol} - {str(e)}")
                continue

        return count

    def _scan_confirmation(self, interval: str, market_type: str) -> int:
        """Confirmation阶段扫描：确认弃盘特征，更新状态为suspected。

        扫描所有pending状态的监控记录，检测成交量留存、关键位跌破、PE异常。

        业务逻辑：
            1. 获取所有status=pending且market_type匹配的监控记录
            2. 对每个记录调用成交量留存、关键位跌破、PE异常检测器
            3. 使用条件评估器判断是否满足Confirmation条件
            4. 满足条件时更新状态为suspected_abandonment，phase_2_passed=True
            5. 创建StateTransition日志和Indicators快照

        Args:
            interval: K线周期
            market_type: 市场类型（'spot'现货或'futures'合约）

        Returns:
            int: 状态转换数量

        Side Effects:
            - 更新VolumeTrapMonitor记录状态
            - 创建VolumeTrapStateTransition日志
            - 创建VolumeTrapIndicators快照
        """
        count = 0

        # 获取所有pending状态的监控记录（根据market_type筛选）
        monitors = VolumeTrapMonitor.objects.filter(
            status="pending", interval=interval, market_type=market_type
        )

        logger.info(f"Confirmation: 扫描{len(monitors)}个pending记录...")

        for monitor in monitors:
            try:
                # 检测是否触发Confirmation条件
                triggered, indicators = self._check_confirmation_condition(monitor)

                if triggered:
                    # 更新状态（使用transaction确保原子性）
                    with transaction.atomic():
                        self._update_monitor_status(
                            monitor=monitor,
                            new_status="suspected_abandonment",
                            phase=2,
                            indicators=indicators,
                        )
                        count += 1
                        symbol = self._get_monitor_symbol(monitor)
                        logger.info(f"Confirmation触发: {symbol}")

            except DataInsufficientError as e:
                symbol = self._get_monitor_symbol(monitor)
                logger.debug(f"跳过{symbol}: 数据不足 ({e})")
                continue
            except Exception as e:
                symbol = self._get_monitor_symbol(monitor)
                logger.warning(f"Confirmation检测失败: {symbol} - {str(e)}")
                continue

        return count

    def _scan_validation(self, interval: str, market_type: str) -> int:
        """Validation阶段扫描：验证趋势反转，更新状态为confirmed。

        扫描所有suspected状态的监控记录，检测MA死叉、OBV单边下滑、ATR压缩。

        业务逻辑：
            1. 获取所有status=suspected_abandonment且market_type匹配的监控记录
            2. 对每个记录调用MA交叉、OBV背离、ATR压缩检测器
            3. 使用条件评估器判断是否满足Validation条件
            4. 满足条件时更新状态为confirmed_abandonment，phase_3_passed=True
            5. 创建StateTransition日志和Indicators快照

        Args:
            interval: K线周期
            market_type: 市场类型（'spot'现货或'futures'合约）

        Returns:
            int: 状态转换数量

        Side Effects:
            - 更新VolumeTrapMonitor记录状态
            - 创建VolumeTrapStateTransition日志
            - 创建VolumeTrapIndicators快照
        """
        count = 0

        # 获取所有suspected状态的监控记录（根据market_type筛选）
        monitors = VolumeTrapMonitor.objects.filter(
            status="suspected_abandonment", interval=interval, market_type=market_type
        )

        logger.info(f"Validation: 扫描{len(monitors)}个suspected记录...")

        for monitor in monitors:
            try:
                # 检测是否触发Validation条件
                triggered, indicators = self._check_validation_condition(monitor)

                if triggered:
                    # 更新状态（使用transaction确保原子性）
                    with transaction.atomic():
                        self._update_monitor_status(
                            monitor=monitor,
                            new_status="confirmed_abandonment",
                            phase=3,
                            indicators=indicators,
                        )
                        count += 1
                        symbol = self._get_monitor_symbol(monitor)
                        logger.info(f"Validation触发: {symbol}")

            except DataInsufficientError as e:
                symbol = self._get_monitor_symbol(monitor)
                logger.debug(f"跳过{symbol}: 数据不足 ({e})")
                continue
            except Exception as e:
                symbol = self._get_monitor_symbol(monitor)
                logger.warning(f"Validation检测失败: {symbol} - {str(e)}")
                continue

        return count

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """解析日期字符串为datetime对象。

        Args:
            date_str: 日期字符串，'all'或ISO 8601格式'YYYY-MM-DD'

        Returns:
            Optional[datetime]: 解析后的datetime对象，'all'返回None

        Raises:
            ValueError: 当日期格式无效时

        Examples:
            >>> self._parse_date('all')
            None
            >>> self._parse_date('2025-11-01')
            datetime.datetime(2025, 11, 1, 0, 0, tzinfo=datetime.timezone.utc)
        """
        if date_str is None or date_str == "all":
            return None

        try:
            return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError as e:
            raise ValueError(f"日期格式错误: 应为YYYY-MM-DD，实际值='{date_str}'") from e

    def _check_discovery_condition(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> tuple:
        """检测Discovery条件：RVOL触发 AND 振幅触发。

        支持历史数据扫描，当指定start_date和end_date时，遍历指定日期范围内的所有K线。

        Args:
            symbol: 交易对符号
            interval: K线周期
            start_date: 开始日期，'all'或不指定表示扫描最新数据
            end_date: 结束日期，可选

        Returns:
            tuple: (是否触发, 指标字典)

        Raises:
            DataInsufficientError: K线数据不足

        Context:
            - TASK-005-001: 修改VolumeTrapStateMachine._check_discovery_condition
            - PRD: Discovery阶段历史扫描优化
        """
        # === 默认行为：不指定日期时只检查最新数据 ===
        if not start_date and not end_date:
            # 调用RVOL计算器
            rvol_result = self.rvol_calculator.calculate(symbol, interval)
            if rvol_result is None:
                return False, {}

            # 调用振幅检测器
            amplitude_result = self.amplitude_detector.calculate(symbol, interval)
            if amplitude_result is None:
                return False, {}

            # 组合检测结果
            detector_results = {
                "rvol_triggered": rvol_result["triggered"],
                "amplitude_triggered": amplitude_result["triggered"],
            }

            # 使用条件评估器判断
            triggered = self.condition_evaluator.evaluate_discovery_condition(detector_results)

            # 构建指标字典
            # 注意：从 amplitude_result 获取 trigger_time，确保时间字段正确
            trigger_time = amplitude_result.get("current_kline_open_time")
            if not trigger_time:
                raise ValueError(
                    f"无法获取触发时间: amplitude_result中缺少current_kline_open_time字段, "
                    f"symbol={symbol}, interval={interval}"
                )

            indicators = {
                "rvol_ratio": rvol_result["rvol_ratio"],
                "amplitude_ratio": amplitude_result["amplitude_ratio"],
                "upper_shadow_ratio": amplitude_result["upper_shadow_ratio"],
                "trigger_volume": rvol_result["current_volume"],
                "trigger_price": amplitude_result["current_close"],
                "trigger_kline_high": amplitude_result["current_high"],
                "trigger_kline_low": amplitude_result["current_low"],
                "trigger_time": trigger_time,
            }

            return triggered, indicators

        # === 历史扫描：遍历指定日期范围内的所有K线 ===
        # 解析日期参数
        start_datetime = self._parse_date(start_date) if start_date else None
        end_datetime = self._parse_date(end_date) if end_date else None

        # 构建查询条件
        query_params = {"symbol": symbol, "interval": interval}

        # 添加日期范围过滤
        if start_datetime:
            query_params["open_time__gte"] = start_datetime
        if end_datetime:
            query_params["open_time__lte"] = end_datetime

        # 批量查询历史K线
        klines = KLine.objects.filter(**query_params).order_by("open_time")

        # 遍历检查每个K线（按时间正序）
        for kline in klines:
            try:
                # 计算当前K线对应的历史数据
                # 需要获取当前K线之前的lookback_period根K线

                # 获取当前K线之前的数据（用于RVOL计算）
                rvol_required = self.rvol_calculator.lookback_period + 1
                historical_klines = KLine.objects.filter(
                    symbol=symbol, interval=interval, open_time__lte=kline.open_time
                ).order_by("-open_time")[:rvol_required]

                historical_list = list(historical_klines)

                # 检查数据是否足够
                if len(historical_list) < rvol_required:
                    continue

                # 转换为pandas DataFrame进行向量化计算
                import pandas as pd

                volumes = pd.Series([float(k.volume) for k in reversed(historical_list)])
                ma_volume = volumes.iloc[: self.rvol_calculator.lookback_period].mean()
                current_volume = float(kline.volume)
                rvol_ratio = current_volume / ma_volume if ma_volume > 0 else 0
                rvol_triggered = rvol_ratio >= self.rvol_calculator.threshold

                # 计算振幅
                amplitude = (
                    (float(kline.high_price) - float(kline.low_price))
                    / float(kline.low_price)
                    * 100
                )

                # 获取历史振幅（当前K线之前30根）
                amp_required = self.amplitude_detector.lookback_period
                amp_klines = KLine.objects.filter(
                    symbol=symbol, interval=interval, open_time__lt=kline.open_time
                ).order_by("-open_time")[:amp_required]

                amp_list = list(amp_klines)
                if len(amp_list) < amp_required:
                    continue

                # 计算历史振幅均值
                historical_amplitudes = [
                    (float(k.high_price) - float(k.low_price)) / float(k.low_price) * 100
                    for k in reversed(amp_list)
                ]
                avg_amplitude = sum(historical_amplitudes) / len(historical_amplitudes)
                amplitude_ratio = amplitude / avg_amplitude if avg_amplitude > 0 else 0

                # 计算上影线比例
                upper_shadow = float(kline.high_price) - float(kline.close_price)
                shadow_range = float(kline.high_price) - float(kline.low_price)
                upper_shadow_ratio = (upper_shadow / shadow_range * 100) if shadow_range > 0 else 0

                amplitude_triggered = (
                    amplitude_ratio >= self.amplitude_detector.amplitude_threshold
                    and upper_shadow_ratio >= self.amplitude_detector.upper_shadow_threshold * 100
                )

                # 组合检测结果
                detector_results = {
                    "rvol_triggered": rvol_triggered,
                    "amplitude_triggered": amplitude_triggered,
                }

                # 使用条件评估器判断
                triggered = self.condition_evaluator.evaluate_discovery_condition(detector_results)

                if triggered:
                    # 返回第一个触发的事件
                    indicators = {
                        "trigger_time": kline.open_time,
                        "trigger_price": kline.close_price,
                        "trigger_volume": kline.volume,
                        "rvol_ratio": rvol_ratio,
                        "amplitude_ratio": amplitude_ratio,
                        "upper_shadow_ratio": upper_shadow_ratio,
                        "trigger_kline_high": kline.high_price,
                        "trigger_kline_low": kline.low_price,
                    }
                    return True, indicators

            except Exception as e:
                # 单个K线检查失败，记录日志并继续
                logger.debug(f"检查K线失败: {symbol} at {kline.open_time} - {str(e)}")
                continue

        # 遍历完所有K线都没有触发
        return False, {}

    def _check_confirmation_condition(self, monitor: VolumeTrapMonitor) -> tuple:
        """检测Confirmation条件：成交量留存 AND 关键位跌破 AND PE异常。

        Args:
            monitor: 监控记录

        Returns:
            tuple: (是否触发, 指标字典)

        Raises:
            DataInsufficientError: K线数据不足
        """
        symbol = self._get_monitor_symbol(monitor)
        interval = monitor.interval

        # 获取触发后的K线数据（用于成交量留存分析）
        post_klines = KLine.objects.filter(
            symbol=symbol, interval=interval, open_time__gt=monitor.trigger_time
        ).order_by("open_time")[:5]

        # 调用成交量留存分析器
        retention_result = self.volume_retention_analyzer.analyze(
            trigger_volume=monitor.trigger_volume, post_klines=list(post_klines)
        )
        if retention_result is None:
            return False, {}

        # 获取当前K线（用于关键位跌破和PE检测）
        current_kline = post_klines.last() if post_klines.exists() else None
        if current_kline is None:
            return False, {}

        # 调用关键位跌破检测器
        breach_result = self.key_level_breach_detector.detect(
            trigger_high=monitor.trigger_kline_high,
            trigger_low=monitor.trigger_kline_low,
            current_close=current_kline.close_price,
        )

        # 调用PE分析器（需要最近5根和历史30根K线）
        recent_klines = list(post_klines)
        historical_klines = KLine.objects.filter(
            symbol=symbol, interval=interval, open_time__lte=monitor.trigger_time
        ).order_by("-open_time")[:30]

        if len(historical_klines) < 30:
            return False, {}

        pe_result = self.price_efficiency_analyzer.analyze(
            recent_klines=recent_klines, historical_klines=list(historical_klines)
        )
        if pe_result is None:
            return False, {}

        # 组合检测结果
        detector_results = {
            "volume_retention_triggered": retention_result["triggered"],
            "key_level_breached": breach_result["triggered"],
            "pe_triggered": pe_result["triggered"],
        }

        # 使用条件评估器判断
        triggered = self.condition_evaluator.evaluate_confirmation_condition(detector_results)

        # 构建指标字典
        indicators = {
            "volume_retention_ratio": retention_result["retention_ratio"],
            "key_level_breach": breach_result["triggered"],
            "price_efficiency": pe_result["current_pe"],
            "kline_close_price": current_kline.close_price,
        }

        return triggered, indicators

    def _check_validation_condition(self, monitor: VolumeTrapMonitor) -> tuple:
        """检测Validation条件：MA死叉 AND OBV单边下滑 AND ATR压缩。

        Args:
            monitor: 监控记录

        Returns:
            tuple: (是否触发, 指标字典)

        Raises:
            DataInsufficientError: K线数据不足
        """
        symbol = self._get_monitor_symbol(monitor)
        interval = monitor.interval

        # 获取最近26根K线（MA计算需要）
        klines = KLine.objects.filter(symbol=symbol, interval=interval).order_by("-open_time")[:30]

        if len(klines) < 30:
            raise DataInsufficientError(
                required=30, actual=len(klines), symbol=symbol, interval=interval
            )

        klines_list = list(reversed(list(klines)))  # 转为时间正序

        # 调用MA交叉检测器
        ma_result = self.ma_cross_detector.detect(klines=klines_list)

        # 调用OBV背离分析器
        obv_result = self.obv_divergence_analyzer.analyze(klines=klines_list[:10])  # 使用最近10根

        # 调用ATR压缩检测器
        atr_result = self.atr_compression_detector.detect(klines=klines_list)

        # 组合检测结果
        detector_results = {
            "ma_death_cross": ma_result["death_cross"],
            "obv_single_side_decline": obv_result["single_side_decline"],
            "atr_compressed": atr_result["is_compressed"],
        }

        # 使用条件评估器判断
        triggered = self.condition_evaluator.evaluate_validation_condition(detector_results)

        # 构建指标字典
        indicators = {
            "ma7": ma_result["ma7"],
            "ma25": ma_result["ma25"],
            "ma25_slope": ma_result["ma25_slope"],
            "obv_divergence": obv_result.get("divergence_detected", False),
            "atr": atr_result["atr_current"],
            "atr_compression": atr_result["is_compressed"],
            "kline_close_price": klines_list[-1].close_price,
        }

        return triggered, indicators

    def _create_monitor_record(
        self, contract, market_type: str, interval: str, indicators: Dict
    ) -> VolumeTrapMonitor:
        """创建Monitor记录。

        Args:
            contract: 合约或现货交易对
            market_type: 市场类型（'spot'现货或'futures'合约）
            interval: K线周期
            indicators: 指标字典

        Returns:
            VolumeTrapMonitor: 创建的监控记录
        """
        # 使用K线的触发时间，而不是当前时间
        trigger_time = indicators.get("trigger_time", timezone.now())

        # 根据market_type设置对应的外键
        if market_type == "futures":
            monitor = VolumeTrapMonitor.objects.create(
                futures_contract=contract,
                spot_contract=None,
                market_type="futures",
                interval=interval,
                trigger_time=trigger_time,
                trigger_price=indicators["trigger_price"],
                trigger_volume=indicators["trigger_volume"],
                trigger_kline_high=indicators["trigger_kline_high"],
                trigger_kline_low=indicators["trigger_kline_low"],
                status="pending",
                phase_1_passed=True,
            )
        elif market_type == "spot":
            monitor = VolumeTrapMonitor.objects.create(
                futures_contract=None,
                spot_contract=contract,
                market_type="spot",
                interval=interval,
                trigger_time=trigger_time,
                trigger_price=indicators["trigger_price"],
                trigger_volume=indicators["trigger_volume"],
                trigger_kline_high=indicators["trigger_kline_high"],
                trigger_kline_low=indicators["trigger_kline_low"],
                status="pending",
                phase_1_passed=True,
            )
        else:
            raise ValueError(f"无效的market_type: {market_type}")

        # 创建StateTransition日志
        VolumeTrapStateTransition.objects.create(
            monitor=monitor,
            from_status="",
            to_status="pending",
            trigger_condition={
                "rvol_ratio": float(indicators["rvol_ratio"]),
                "amplitude_ratio": float(indicators["amplitude_ratio"]),
                "upper_shadow_ratio": float(indicators["upper_shadow_ratio"]),
                "phase": 1,
            },
            transition_time=timezone.now(),
        )

        # 创建Indicators快照
        VolumeTrapIndicators.objects.create(
            monitor=monitor,
            snapshot_time=timezone.now(),
            kline_close_price=indicators["trigger_price"],
            rvol_ratio=indicators["rvol_ratio"],
            amplitude_ratio=indicators["amplitude_ratio"],
            upper_shadow_ratio=indicators["upper_shadow_ratio"],
        )

        return monitor

    def _update_monitor_status(
        self, monitor: VolumeTrapMonitor, new_status: str, phase: int, indicators: Dict
    ):
        """更新Monitor记录状态。

        Args:
            monitor: 监控记录
            new_status: 新状态
            phase: 阶段编号（2/3）
            indicators: 指标字典
        """
        # 记录原状态
        old_status = monitor.status

        # 更新Monitor状态
        monitor.status = new_status
        if phase == 2:
            monitor.phase_2_passed = True
        elif phase == 3:
            monitor.phase_3_passed = True
        monitor.save()

        # 创建StateTransition日志
        trigger_condition = {"phase": phase}
        for key, value in indicators.items():
            if key != "kline_close_price":
                trigger_condition[key] = float(value) if isinstance(value, Decimal) else value

        VolumeTrapStateTransition.objects.create(
            monitor=monitor,
            from_status=old_status,
            to_status=new_status,
            trigger_condition=trigger_condition,
            transition_time=timezone.now(),
        )

        # 创建Indicators快照
        snapshot_data = {
            "monitor": monitor,
            "snapshot_time": timezone.now(),
            "kline_close_price": indicators.get("kline_close_price", Decimal("0")),
        }

        # 根据阶段添加对应指标
        if phase == 2:
            snapshot_data.update(
                {
                    "volume_retention_ratio": indicators.get("volume_retention_ratio"),
                    "key_level_breach": indicators.get("key_level_breach"),
                    "price_efficiency": indicators.get("price_efficiency"),
                }
            )
        elif phase == 3:
            snapshot_data.update(
                {
                    "ma7": indicators.get("ma7"),
                    "ma25": indicators.get("ma25"),
                    "ma25_slope": indicators.get("ma25_slope"),
                    "obv_divergence": indicators.get("obv_divergence"),
                    "atr": indicators.get("atr"),
                    "atr_compression": indicators.get("atr_compression"),
                }
            )

        VolumeTrapIndicators.objects.create(**snapshot_data)
