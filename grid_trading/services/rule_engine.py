"""
价格触发规则引擎
Price Alert Rule Engine

实现5种价格触发规则的判定逻辑和防重复推送机制
Feature: 001-price-alert-monitor
Tasks: T018-T025, T028-T030
"""
import logging
import numpy as np
from datetime import timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from grid_trading.django_models import (
    PriceAlertRule,
    AlertTriggerLog,
    SystemConfig
)
from grid_trading.services.rule_utils import (
    calculate_ma,
    calculate_price_distribution,
    get_7d_high_low,
    check_price_in_range
)
from grid_trading.services.alert_notifier import PriceAlertNotifier

logger = logging.getLogger("grid_trading")


class PriceRuleEngine:
    """
    价格触发规则引擎

    负责检测5种价格触发规则，并处理触发事件(防重复、推送通知、记录日志)
    """

    def __init__(self):
        """初始化规则引擎"""
        self.notifier = PriceAlertNotifier()

    def check_all_rules(
        self,
        symbol: str,
        current_price: Decimal,
        klines_4h: List[Dict]
    ) -> List[Dict]:
        """
        检查所有启用的规则

        Args:
            symbol: 合约代码
            current_price: 当前价格
            klines_4h: 4h K线数据列表(至少7天=42根)

        Returns:
            List[Dict]: 触发的规则列表，每个元素包含:
                {
                    'rule_id': int,
                    'rule_name': str,
                    'triggered': bool,
                    'extra_info': dict,
                    'pushed': bool,
                    'skip_reason': str
                }

        Example:
            engine = PriceRuleEngine()
            klines = get_klines('BTCUSDT', '4h', limit=42)
            current_price = Decimal('45000.50')
            results = engine.check_all_rules('BTCUSDT', current_price, klines)

            for result in results:
                if result['triggered']:
                    print(f"触发规则: {result['rule_name']}")
        """
        # 查询所有启用的规则
        enabled_rules = PriceAlertRule.objects.filter(enabled=True)

        results = []

        for rule in enabled_rules:
            rule_id = rule.rule_id
            rule_name = rule.name

            # 调用对应的规则检测方法
            triggered, extra_info = self._check_rule(
                rule_id,
                symbol,
                current_price,
                klines_4h,
                rule.parameters
            )

            result = {
                'rule_id': rule_id,
                'rule_name': rule_name,
                'triggered': triggered,
                'extra_info': extra_info,
                'pushed': False,
                'skip_reason': ''
            }

            if triggered:
                # 处理触发事件
                pushed, skip_reason = self.process_trigger(
                    symbol,
                    rule_id,
                    current_price,
                    extra_info
                )
                result['pushed'] = pushed
                result['skip_reason'] = skip_reason

            results.append(result)

        return results

    def check_all_rules_batch(
        self,
        symbol: str,
        current_price: Decimal,
        klines_4h: List[Dict],
        klines_15m: Optional[List[Dict]] = None,
        klines_1h: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """
        检查所有启用的规则（批量模式，不立即推送）

        Args:
            symbol: 合约代码
            current_price: 当前价格
            klines_4h: 4h K线数据列表(至少7天=42根)
            klines_15m: 15m K线数据列表(可选，用于规则6/7)
            klines_1h: 1h K线数据列表(可选，用于规则6/7)

        Returns:
            List[Dict]: 触发的规则列表，每个元素包含:
                {
                    'rule_id': int,
                    'rule_name': str,
                    'triggered': bool,
                    'extra_info': dict,
                    'current_price': Decimal
                }

        Example:
            engine = PriceRuleEngine()
            # 规则1-5（仅需4h K线）
            results = engine.check_all_rules_batch('BTCUSDT', price, klines_4h)
            # 规则6/7（需要15m和1h K线）
            results = engine.check_all_rules_batch(
                'BTCUSDT', price, klines_4h, klines_15m, klines_1h
            )
        """
        # 查询所有启用的规则
        enabled_rules = PriceAlertRule.objects.filter(enabled=True)

        results = []

        for rule in enabled_rules:
            rule_id = rule.rule_id
            rule_name = rule.name

            # 调用对应的规则检测方法
            triggered, extra_info = self._check_rule(
                rule_id,
                symbol,
                current_price,
                klines_4h,
                rule.parameters,
                klines_15m=klines_15m,
                klines_1h=klines_1h
            )

            if triggered:
                result = {
                    'rule_id': rule_id,
                    'rule_name': rule_name,
                    'triggered': True,
                    'extra_info': extra_info,
                    'current_price': current_price
                }
                results.append(result)

        return results

    def _check_rule(
        self,
        rule_id: int,
        symbol: str,
        current_price: Decimal,
        klines_4h: List[Dict],
        parameters: Dict,
        klines_15m: Optional[List[Dict]] = None,
        klines_1h: Optional[List[Dict]] = None
    ) -> Tuple[bool, Dict]:
        """
        检查单个规则

        Args:
            rule_id: 规则ID (1-7)
            symbol: 合约代码
            current_price: 当前价格
            klines_4h: 4h K线数据
            parameters: 规则参数
            klines_15m: 15m K线数据（可选，用于规则6/7）
            klines_1h: 1h K线数据（可选，用于规则6/7）

        Returns:
            (triggered, extra_info): 是否触发和额外信息
        """
        if rule_id == 1:
            return self.check_rule_1_7d_high(current_price, klines_4h)
        elif rule_id == 2:
            return self.check_rule_2_7d_low(current_price, klines_4h)
        elif rule_id == 3:
            return self.check_rule_3_ma20_touch(
                current_price,
                klines_4h,
                parameters
            )
        elif rule_id == 4:
            return self.check_rule_4_ma99_touch(
                current_price,
                klines_4h,
                parameters
            )
        elif rule_id == 5:
            return self.check_rule_5_price_distribution(
                current_price,
                klines_4h,
                parameters
            )
        elif rule_id == 6:
            # 规则6: 止盈信号监控
            result = self._check_rule_6_take_profit(
                symbol,
                klines_15m or [],
                klines_1h or [],
                current_price,
                parameters
            )
            if result:
                return (True, result)
            else:
                return (False, {})
        elif rule_id == 7:
            # 规则7: 止损信号监控
            result = self._check_rule_7_stop_loss(
                symbol,
                klines_15m or [],
                klines_1h or [],
                current_price,
                parameters
            )
            if result:
                return (True, result)
            else:
                return (False, {})
        else:
            logger.error(f"未知规则ID: {rule_id}")
            return (False, {})

    # ========== 规则1: 7天价格新高 ==========
    def check_rule_1_7d_high(
        self,
        current_price: Decimal,
        klines_4h: List[Dict]
    ) -> Tuple[bool, Dict]:
        """
        规则1: 检测价格是否创7天新高

        Args:
            current_price: 当前价格
            klines_4h: 4h K线数据(至少7天=42根)

        Returns:
            (triggered, extra_info)
        """
        if not klines_4h or len(klines_4h) < 3:
            logger.warning("K线数据不足，跳过7天新高检测")
            return (False, {'degraded': True, 'reason': '数据不足'})

        # 获取7天内最高价和最低价
        high_7d, low_7d = get_7d_high_low(klines_4h)

        if high_7d is None:
            return (False, {'degraded': True, 'reason': '计算失败'})

        # 判断是否创新高
        price_float = float(current_price)
        triggered = price_float > high_7d

        extra_info = {
            'high_7d': high_7d,
            'low_7d': low_7d,
            'actual_days': len(klines_4h) / 6,  # 4h K线: 6根/天
            'degraded': len(klines_4h) < 42
        }

        return (triggered, extra_info)

    # ========== 规则2: 7天价格新低 ==========
    def check_rule_2_7d_low(
        self,
        current_price: Decimal,
        klines_4h: List[Dict]
    ) -> Tuple[bool, Dict]:
        """
        规则2: 检测价格是否创7天新低

        Args:
            current_price: 当前价格
            klines_4h: 4h K线数据

        Returns:
            (triggered, extra_info)
        """
        if not klines_4h or len(klines_4h) < 3:
            logger.warning("K线数据不足，跳过7天新低检测")
            return (False, {'degraded': True, 'reason': '数据不足'})

        # 获取7天内最高价和最低价
        high_7d, low_7d = get_7d_high_low(klines_4h)

        if low_7d is None:
            return (False, {'degraded': True, 'reason': '计算失败'})

        # 判断是否创新低
        price_float = float(current_price)
        triggered = price_float < low_7d

        extra_info = {
            'high_7d': high_7d,
            'low_7d': low_7d,
            'actual_days': len(klines_4h) / 6,
            'degraded': len(klines_4h) < 42
        }

        return (triggered, extra_info)

    # ========== 规则3: 价格触及MA20 ==========
    def check_rule_3_ma20_touch(
        self,
        current_price: Decimal,
        klines_4h: List[Dict],
        parameters: Dict
    ) -> Tuple[bool, Dict]:
        """
        规则3: 检测价格是否触及MA20

        Args:
            current_price: 当前价格
            klines_4h: 4h K线数据(至少20根)
            parameters: 规则参数，包含ma_threshold(默认0.5%)

        Returns:
            (triggered, extra_info)
        """
        if not klines_4h or len(klines_4h) < 20:
            logger.warning("K线数据不足20根，跳过MA20检测")
            return (False, {'reason': '数据不足，需要至少20根K线'})

        # 计算MA20
        ma20 = calculate_ma(klines_4h, period=20)

        if ma20 is None:
            return (False, {'reason': 'MA20计算失败'})

        # 获取阈值参数
        threshold_pct = parameters.get('ma_threshold', 0.5)

        # 检查价格是否在MA20的±threshold_pct范围内
        triggered = check_price_in_range(
            current_price,
            Decimal(str(ma20)),
            threshold_pct
        )

        extra_info = {
            'ma20': ma20,
            'threshold_pct': threshold_pct,
            'distance_pct': abs(float(current_price) - ma20) / ma20 * 100
        }

        return (triggered, extra_info)

    # ========== 规则4: 价格触及MA99 ==========
    def check_rule_4_ma99_touch(
        self,
        current_price: Decimal,
        klines_4h: List[Dict],
        parameters: Dict
    ) -> Tuple[bool, Dict]:
        """
        规则4: 检测价格是否触及MA99

        Args:
            current_price: 当前价格
            klines_4h: 4h K线数据(至少99根)
            parameters: 规则参数，包含ma_threshold(默认0.5%)

        Returns:
            (triggered, extra_info)
        """
        if not klines_4h or len(klines_4h) < 99:
            logger.warning("K线数据不足99根，跳过MA99检测")
            return (False, {'reason': '数据不足，需要至少99根K线'})

        # 计算MA99
        ma99 = calculate_ma(klines_4h, period=99)

        if ma99 is None:
            return (False, {'reason': 'MA99计算失败'})

        # 获取阈值参数
        threshold_pct = parameters.get('ma_threshold', 0.5)

        # 检查价格是否在MA99的±threshold_pct范围内
        triggered = check_price_in_range(
            current_price,
            Decimal(str(ma99)),
            threshold_pct
        )

        extra_info = {
            'ma99': ma99,
            'threshold_pct': threshold_pct,
            'distance_pct': abs(float(current_price) - ma99) / ma99 * 100
        }

        return (triggered, extra_info)

    # ========== 规则5: 价格达到分布区间90%极值 ==========
    def check_rule_5_price_distribution(
        self,
        current_price: Decimal,
        klines_4h: List[Dict],
        parameters: Dict
    ) -> Tuple[bool, Dict]:
        """
        规则5: 检测价格是否达到价格分布区间90%极值

        Args:
            current_price: 当前价格
            klines_4h: 4h K线数据(至少7天=42根)
            parameters: 规则参数，包含percentile(默认90)

        Returns:
            (triggered, extra_info)
        """
        if not klines_4h or len(klines_4h) < 10:
            logger.warning("K线数据不足，跳过价格分布检测")
            return (False, {'reason': '数据不足'})

        # 获取分位数参数
        percentile = parameters.get('percentile', 90)

        # 计算价格分布区间
        lower_bound, upper_bound = calculate_price_distribution(
            klines_4h,
            percentile
        )

        if lower_bound is None or upper_bound is None:
            return (False, {'reason': '价格分布计算失败'})

        # 判断价格是否超过上限或低于下限
        price_float = float(current_price)
        triggered = price_float > upper_bound or price_float < lower_bound

        # 判断是高位还是低位
        position = 'high' if price_float > upper_bound else 'low' if price_float < lower_bound else 'middle'

        extra_info = {
            'percentile': percentile,
            'percentile_lower': lower_bound,
            'percentile_upper': upper_bound,
            'position': position
        }

        return (triggered, extra_info)

    # ========== 规则6: 4h高低点10%变化 ==========
    def check_rule_6_4h_change(
        self,
        current_price: Decimal,
        klines_4h: List[Dict]
    ) -> Tuple[bool, Dict]:
        """
        规则6: 检测价格相对过去4h高低点的10%变化

        Args:
            current_price: 当前价格
            klines_4h: 4h K线数据

        Returns:
            (triggered, extra_info)

        逻辑:
            - 如果当前价格 >= 过去4h最高价 * 1.10: 触发（相对高点上涨10%）
            - 如果当前价格 <= 过去4h最低价 * 0.90: 触发（相对低点下跌10%）
        """
        if not klines_4h or len(klines_4h) < 2:
            logger.warning("K线数据不足，跳过4h变化检测")
            return (False, {'degraded': True, 'reason': '数据不足'})

        # 获取最近一根4h K线（过去4小时）
        last_kline = klines_4h[-1]
        high_4h = float(last_kline.get('high', 0))
        low_4h = float(last_kline.get('low', 0))

        if high_4h == 0 or low_4h == 0:
            logger.warning("K线数据异常，高低价为0")
            return (False, {'degraded': True, 'reason': 'K线数据异常'})

        price_float = float(current_price)

        # 判断是否触发
        up_threshold = high_4h * 1.10  # 高点上涨10%
        down_threshold = low_4h * 0.90  # 低点下跌10%

        triggered_up = price_float >= up_threshold
        triggered_down = price_float <= down_threshold
        triggered = triggered_up or triggered_down

        extra_info = {
            'high_4h': high_4h,
            'low_4h': low_4h,
            'up_threshold': up_threshold,
            'down_threshold': down_threshold,
            'direction': 'up' if triggered_up else 'down' if triggered_down else 'none',
            'change_pct': ((price_float - high_4h) / high_4h * 100) if triggered_up else ((price_float - low_4h) / low_4h * 100) if triggered_down else 0
        }

        return (triggered, extra_info)

    # ========== 防重复推送检查 ==========
    def should_push_alert(self, symbol: str, rule_id: int) -> Tuple[bool, str]:
        """
        检查是否应该推送告警(防重复)

        Args:
            symbol: 合约代码
            rule_id: 规则ID

        Returns:
            (should_push, skip_reason): 是否应该推送和跳过原因
        """
        # 从SystemConfig读取防重复间隔
        suppress_minutes = int(
            SystemConfig.get_value('duplicate_suppress_minutes', 60)
        )

        # 查询最近一次推送时间
        threshold_time = timezone.now() - timedelta(minutes=suppress_minutes)

        last_push = AlertTriggerLog.objects.filter(
            symbol=symbol,
            rule_id=rule_id,
            pushed=True,
            pushed_at__gte=threshold_time
        ).order_by('-pushed_at').first()

        if last_push is None:
            return (True, '')

        # 计算距上次推送的时间
        elapsed_minutes = (
            timezone.now() - last_push.pushed_at
        ).total_seconds() / 60

        skip_reason = f'防重复(上次推送于 {elapsed_minutes:.1f} 分钟前)'

        return (False, skip_reason)

    # ========== 处理触发事件 ==========
    def process_trigger(
        self,
        symbol: str,
        rule_id: int,
        current_price: Decimal,
        extra_info: Dict
    ) -> Tuple[bool, str]:
        """
        处理触发事件

        Args:
            symbol: 合约代码
            rule_id: 规则ID
            current_price: 当前价格
            extra_info: 额外信息

        Returns:
            (pushed, skip_reason): 是否已推送和跳过原因

        工作流程:
        1. 检查防重复
        2. 如果应该推送，调用通知服务
        3. 记录触发日志
        """
        # Step 1: 检查防重复
        should_push, skip_reason = self.should_push_alert(symbol, rule_id)

        if not should_push:
            # 记录触发但跳过推送
            AlertTriggerLog.objects.create(
                symbol=symbol,
                rule_id=rule_id,
                current_price=current_price,
                pushed=False,
                skip_reason=skip_reason,
                extra_info=extra_info
            )
            return (False, skip_reason)

        # Step 2: 发送推送
        try:
            success = self.notifier.send_price_alert(
                symbol=symbol,
                rule_id=rule_id,
                current_price=current_price,
                extra_info=extra_info
            )

            if success:
                # 推送成功，记录日志
                AlertTriggerLog.objects.create(
                    symbol=symbol,
                    rule_id=rule_id,
                    current_price=current_price,
                    pushed=True,
                    pushed_at=timezone.now(),
                    skip_reason='',
                    extra_info=extra_info
                )
                return (True, '')
            else:
                # 推送失败
                AlertTriggerLog.objects.create(
                    symbol=symbol,
                    rule_id=rule_id,
                    current_price=current_price,
                    pushed=False,
                    skip_reason='推送失败',
                    extra_info=extra_info
                )
                return (False, '推送失败')

        except Exception as e:
            logger.error(f"处理触发事件异常: {e}", exc_info=True)
            AlertTriggerLog.objects.create(
                symbol=symbol,
                rule_id=rule_id,
                current_price=current_price,
                pushed=False,
                skip_reason=f'推送异常: {str(e)}',
                extra_info=extra_info
            )
            return (False, f'推送异常: {str(e)}')

    # ========== 补偿重试失败的推送 ==========
    def retry_failed_pushes(self, hours: int = 1) -> int:
        """
        重试最近N小时内失败的推送

        Args:
            hours: 重试最近N小时的失败记录，默认1小时

        Returns:
            int: 成功重试的数量

        Example:
            engine = PriceRuleEngine()
            retried = engine.retry_failed_pushes(hours=2)
            print(f"成功重试 {retried} 条失败推送")
        """
        threshold_time = timezone.now() - timedelta(hours=hours)

        # 查询失败的推送
        failed_logs = AlertTriggerLog.objects.filter(
            pushed=False,
            skip_reason='推送失败',
            triggered_at__gte=threshold_time
        )

        success_count = 0

        for log in failed_logs:
            # 再次检查防重复
            should_push, _ = self.should_push_alert(log.symbol, log.rule_id)

            if should_push:
                try:
                    success = self.notifier.send_price_alert(
                        symbol=log.symbol,
                        rule_id=log.rule_id,
                        current_price=log.current_price,
                        extra_info=log.extra_info
                    )

                    if success:
                        log.pushed = True
                        log.pushed_at = timezone.now()
                        log.skip_reason = ''
                        log.save()
                        success_count += 1
                        logger.info(
                            f"✓ 补偿推送成功: {log.symbol} 规则{log.rule_id}"
                        )

                except Exception as e:
                    logger.error(f"补偿推送失败: {e}")

        return success_count

    # ========== 技术指标计算方法 (Feature: 001-006-short-grid) ==========

    def _calculate_bollinger_bands(
        self,
        klines: List[Dict],
        period: int = 20,
        std_dev: float = 2.0
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """
        计算布林带 (Bollinger Bands)

        Args:
            klines: K线数据列表
            period: 移动平均周期，默认20
            std_dev: 标准差倍数，默认2.0

        Returns:
            Tuple[Optional[float], Optional[float], Optional[float]]:
                (BB_Middle, BB_Upper, BB_Lower)
                如果数据不足返回 (None, None, None)

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            ma, upper, lower = engine._calculate_bollinger_bands(klines_15m)
            if ma is not None:
                print(f"BB中轨: {ma}, 上轨: {upper}, 下轨: {lower}")
        """
        if len(klines) < period:
            logger.debug(
                f"K线数据不足以计算布林带: 需要{period}根，实际{len(klines)}根"
            )
            return None, None, None

        try:
            # 提取收盘价
            closes = np.array([float(k.get('close', 0)) for k in klines])

            # 计算移动平均 (中轨)
            ma = np.mean(closes[-period:])

            # 计算标准差 (使用ddof=1确保样本标准差)
            std = np.std(closes[-period:], ddof=1)

            # 计算上下轨
            upper = ma + std_dev * std
            lower = ma - std_dev * std

            return float(ma), float(upper), float(lower)

        except Exception as e:
            logger.error(f"计算布林带失败: {e}")
            return None, None, None

    def _calculate_ma(
        self,
        klines: List[Dict],
        period: int,
        field: str = 'close'
    ) -> Optional[float]:
        """
        计算简单移动平均 (Simple Moving Average)

        Args:
            klines: K线数据列表
            period: 移动平均周期
            field: 计算字段，默认'close'，可选'volume'

        Returns:
            Optional[float]: MA值，如果数据不足返回None

        Example:
            # 计算价格MA20
            ma20 = engine._calculate_ma(klines, period=20, field='close')

            # 计算成交量MA50
            vol_ma50 = engine._calculate_ma(klines, period=50, field='volume')
        """
        if len(klines) < period:
            logger.debug(
                f"K线数据不足以计算MA{period}: 需要{period}根，实际{len(klines)}根"
            )
            return None

        try:
            # 提取指定字段的值
            values = np.array([float(k.get(field, 0)) for k in klines])

            # 计算移动平均
            ma = np.mean(values[-period:])

            return float(ma)

        except Exception as e:
            logger.error(f"计算MA{period}失败: {e}")
            return None

    def _calculate_rsi_slope(
        self,
        klines: List[Dict],
        period: int = 14,
        lookback: int = 3
    ) -> Optional[float]:
        """
        计算RSI加速度（斜率）

        用于检测RSI的变化速度，正值表示加速上升，负值表示减速下降

        Args:
            klines: K线数据列表
            period: RSI周期，默认14
            lookback: 回溯根数用于计算斜率，默认3

        Returns:
            Optional[float]: RSI斜率 = (RSI_t - RSI_t-lookback) / lookback
                如果数据不足返回None

        Example:
            # 检测RSI超买加速
            rsi_slope = engine._calculate_rsi_slope(klines, period=14, lookback=3)
            if rsi_slope is not None and rsi_slope > 2.0:
                print(f"RSI加速上升，斜率: {rsi_slope}")
        """
        # 需要足够的数据计算RSI和斜率
        min_required = period + lookback + 1
        if len(klines) < min_required:
            logger.debug(
                f"K线数据不足以计算RSI斜率: 需要{min_required}根，实际{len(klines)}根"
            )
            return None

        try:
            # 提取收盘价
            closes = np.array([float(k.get('close', 0)) for k in klines])

            # 计算价格变化
            deltas = np.diff(closes)

            # 分离涨跌
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            # 计算最近period根的平均涨跌幅
            avg_gain = np.mean(gains[-period:])
            avg_loss = np.mean(losses[-period:])

            # 计算当前RSI (t时刻)
            if avg_loss == 0:
                rsi_current = 100.0
            else:
                rs_current = avg_gain / avg_loss
                rsi_current = 100 - 100 / (1 + rs_current)

            # 计算t-lookback时刻的RSI
            avg_gain_prev = np.mean(gains[-(period + lookback):-lookback])
            avg_loss_prev = np.mean(losses[-(period + lookback):-lookback])

            if avg_loss_prev == 0:
                rsi_prev = 100.0
            else:
                rs_prev = avg_gain_prev / avg_loss_prev
                rsi_prev = 100 - 100 / (1 + rs_prev)

            # 计算斜率
            slope = (rsi_current - rsi_prev) / lookback

            return float(slope)

        except Exception as e:
            logger.error(f"计算RSI斜率失败: {e}")
            return None

    # ========== VPA模式检测方法 (Feature: 001-006-short-grid) ==========

    def _detect_stopping_volume(
        self,
        klines: List[Dict],
        params: Dict
    ) -> bool:
        """
        检测急刹车模式 (Stopping Volume)

        规则6的VPA信号之一：检测前序暴跌后，成交量维持但实体压缩的情况
        这是恐慌抛售后主力接盘的标志

        Args:
            klines: K线数据列表（至少需要2根）
            params: 规则6的参数配置
                - crash_threshold: 前序暴跌阈值（默认0.02，即2%）
                - vol_multi_sustain: 成交量维持比率（默认0.8，即80%）
                - body_shrink_ratio: 实体压缩比率（默认0.25，即25%）

        Returns:
            bool: 是否检测到急刹车模式

        检测条件（三个条件必须同时满足）:
            1. 前序暴跌: (open_t-1 - close_t-1) / open_t-1 >= crash_threshold
            2. 成交量维持: vol_t >= vol_t-1 × vol_multi_sustain
            3. 实体压缩: |close_t - open_t| < |close_t-1 - open_t-1| × body_shrink_ratio

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            params = {'crash_threshold': 0.02, 'vol_multi_sustain': 0.8, 'body_shrink_ratio': 0.25}
            if engine._detect_stopping_volume(klines_15m, params):
                print("检测到急刹车模式")
        """
        if len(klines) < 2:
            logger.debug("K线数据不足以检测急刹车模式: 需要至少2根K线")
            return False

        try:
            # 提取参数
            crash_threshold = params.get('crash_threshold', 0.02)
            vol_multi_sustain = params.get('vol_multi_sustain', 0.8)
            body_shrink_ratio = params.get('body_shrink_ratio', 0.25)

            # 获取最近两根K线
            prev_kline = klines[-2]
            curr_kline = klines[-1]

            # 提取价格和成交量数据
            prev_open = float(prev_kline.get('open', 0))
            prev_close = float(prev_kline.get('close', 0))
            prev_volume = float(prev_kline.get('volume', 0))

            curr_open = float(curr_kline.get('open', 0))
            curr_close = float(curr_kline.get('close', 0))
            curr_volume = float(curr_kline.get('volume', 0))

            # 验证数据有效性
            if prev_open == 0 or prev_volume == 0:
                logger.debug("前一根K线数据无效")
                return False

            # 条件1: 前序暴跌检测
            prev_drop = (prev_open - prev_close) / prev_open
            crash_detected = prev_drop >= crash_threshold

            if not crash_detected:
                logger.debug(
                    f"未检测到前序暴跌: 前跌幅={prev_drop:.4f}, 阈值={crash_threshold}"
                )
                return False

            # 条件2: 成交量维持检测
            vol_threshold = prev_volume * vol_multi_sustain
            vol_sustained = curr_volume >= vol_threshold

            if not vol_sustained:
                logger.debug(
                    f"成交量未维持: 当前={curr_volume:.2f}, 阈值={vol_threshold:.2f}"
                )
                return False

            # 条件3: 实体压缩检测
            prev_body = abs(prev_close - prev_open)
            curr_body = abs(curr_close - curr_open)
            body_threshold = prev_body * body_shrink_ratio
            body_compressed = curr_body < body_threshold

            if not body_compressed:
                logger.debug(
                    f"实体未压缩: 当前={curr_body:.2f}, 阈值={body_threshold:.2f}"
                )
                return False

            # 所有条件满足
            logger.info(
                f"✓ 检测到急刹车模式: 前跌幅={prev_drop:.2%}, "
                f"成交量比={curr_volume/prev_volume:.2f}, "
                f"实体压缩={curr_body/prev_body:.2%}"
            )
            return True

        except Exception as e:
            logger.error(f"检测急刹车模式失败: {e}")
            return False

    def _detect_golden_needle(
        self,
        klines: List[Dict],
        params: Dict
    ) -> bool:
        """
        检测金针探底模式 (Golden Needle Bottom)

        规则6的VPA信号之一：检测放量暴跌后出现长下影线且收盘强势的K线
        这是市场底部出现的强烈反转信号

        Args:
            klines: K线数据列表（至少需要50根以计算MA50）
            params: 规则6的参数配置
                - vol_multi_spike: 放量倍数阈值（默认2.5，即成交量 > MA50×2.5）
                - lower_shadow_ratio: 下影线倍数阈值（默认2.0，即下影线 > 实体×2.0）
                - close_position_ratio: 收盘位置阈值（默认0.6，即收盘价位于K线60%以上位置）

        Returns:
            bool: 是否检测到金针探底模式

        检测条件（三个条件必须同时满足）:
            1. 放量暴跌: volume > MA50(volume) × vol_multi_spike
            2. 长下影线: lower_shadow > body × lower_shadow_ratio
            3. 收盘强势: (close - low) / (high - low) > close_position_ratio

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            params = {'vol_multi_spike': 2.5, 'lower_shadow_ratio': 2.0, 'close_position_ratio': 0.6}
            if engine._detect_golden_needle(klines_15m, params):
                print("检测到金针探底模式")
        """
        # 需要至少50根K线以计算MA50
        if len(klines) < 50:
            logger.debug("K线数据不足以检测金针探底模式: 需要至少50根K线")
            return False

        try:
            # 提取参数
            vol_multi_spike = params.get('vol_multi_spike', 2.5)
            lower_shadow_ratio = params.get('lower_shadow_ratio', 2.0)
            close_position_ratio = params.get('close_position_ratio', 0.6)

            # 获取最后一根K线
            curr_kline = klines[-1]

            # 提取当前K线的价格和成交量数据
            curr_open = float(curr_kline.get('open', 0))
            curr_close = float(curr_kline.get('close', 0))
            curr_high = float(curr_kline.get('high', 0))
            curr_low = float(curr_kline.get('low', 0))
            curr_volume = float(curr_kline.get('volume', 0))

            # 验证数据有效性
            if curr_high == curr_low or curr_volume == 0:
                logger.debug("当前K线数据无效")
                return False

            # 条件1: 放量检测 - 计算成交量MA50
            vol_ma50 = self._calculate_ma(klines, period=50, field='volume')
            if vol_ma50 is None:
                logger.debug("无法计算成交量MA50")
                return False

            vol_threshold = vol_ma50 * vol_multi_spike
            volume_spike = curr_volume > vol_threshold

            if not volume_spike:
                logger.debug(
                    f"未检测到放量: 当前={curr_volume:.2f}, 阈值={vol_threshold:.2f}"
                )
                return False

            # 条件2: 长下影线检测
            body = abs(curr_close - curr_open)
            lower_shadow = min(curr_open, curr_close) - curr_low
            shadow_threshold = body * lower_shadow_ratio
            long_lower_shadow = lower_shadow > shadow_threshold

            if not long_lower_shadow:
                logger.debug(
                    f"下影线不够长: 下影线={lower_shadow:.2f}, 阈值={shadow_threshold:.2f}"
                )
                return False

            # 条件3: 收盘强势检测（收盘价位于K线上半部分）
            price_range = curr_high - curr_low
            if price_range == 0:
                logger.debug("价格区间为0，无法计算收盘位置")
                return False

            close_position = (curr_close - curr_low) / price_range
            strong_close = close_position > close_position_ratio

            if not strong_close:
                logger.debug(
                    f"收盘位置不够强势: 位置={close_position:.2%}, 阈值={close_position_ratio:.2%}"
                )
                return False

            # 所有条件满足
            logger.info(
                f"✓ 检测到金针探底模式: 放量={curr_volume/vol_ma50:.2f}x, "
                f"下影线={lower_shadow/body:.2f}x实体, 收盘位置={close_position:.2%}"
            )
            return True

        except Exception as e:
            logger.error(f"检测金针探底模式失败: {e}")
            return False

    def _check_rsi_oversold(
        self,
        klines: List[Dict],
        params: Dict
    ) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        检测RSI超卖信号

        规则6的技术指标确认之一：检测RSI是否处于超卖区域或出现底背离

        Args:
            klines: K线数据列表（至少需要period+1根）
            params: 规则6的参数配置
                - rsi_period: RSI计算周期（默认14）
                - rsi_oversold: RSI超卖阈值（默认20）

        Returns:
            Tuple[bool, Optional[float], Optional[str]]:
                - bool: 是否检测到RSI超卖
                - Optional[float]: RSI值
                - Optional[str]: 触发原因（'RSI超卖' 或 'RSI底背离'）

        检测条件（满足任一即可）:
            1. RSI单纯超卖: RSI < rsi_oversold (默认20)
            2. RSI底背离: 价格创新低但RSI未创新低（暂不实现，返回None）

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            params = {'rsi_period': 14, 'rsi_oversold': 20}
            oversold, rsi_value, reason = engine._check_rsi_oversold(klines_15m, params)
            if oversold:
                print(f"检测到{reason}, RSI={rsi_value}")
        """
        # 提取参数
        rsi_period = params.get('rsi_period', 14)
        rsi_oversold = params.get('rsi_oversold', 20)

        # 需要足够的数据计算RSI
        min_required = rsi_period + 1
        if len(klines) < min_required:
            logger.debug(
                f"K线数据不足以计算RSI: 需要{min_required}根，实际{len(klines)}根"
            )
            return (False, None, None)

        try:
            # 提取收盘价
            closes = np.array([float(k.get('close', 0)) for k in klines])

            # 计算价格变化
            deltas = np.diff(closes)

            # 分离涨跌
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            # 计算最近period根的平均涨跌幅
            avg_gain = np.mean(gains[-rsi_period:])
            avg_loss = np.mean(losses[-rsi_period:])

            # 计算RSI
            if avg_loss == 0:
                rsi_value = 100.0
            else:
                rs = avg_gain / avg_loss
                rsi_value = 100 - 100 / (1 + rs)

            # 检查是否超卖
            if rsi_value < rsi_oversold:
                logger.info(f"✓ 检测到RSI超卖: RSI={rsi_value:.2f} < {rsi_oversold}")
                return (True, float(rsi_value), 'RSI超卖')

            # TODO: RSI底背离检测（需要识别多个波谷，暂不实现）
            # 底背离定义：价格创新低但RSI未创新低
            # 实现需要：
            # 1. 识别最近两个价格低点
            # 2. 对应时刻的RSI值对比
            # 3. 判断价格低点2 < 价格低点1 但 RSI2 > RSI1

            logger.debug(f"未检测到RSI超卖: RSI={rsi_value:.2f} >= {rsi_oversold}")
            return (False, float(rsi_value), None)

        except Exception as e:
            logger.error(f"检测RSI超卖失败: {e}")
            return (False, None, None)

    def _check_bb_reversion(
        self,
        klines: List[Dict],
        params: Dict
    ) -> bool:
        """
        检测布林带触底回升

        规则6的技术指标确认之一：检测价格击穿布林带下轨后收回的反转信号

        Args:
            klines: K线数据列表（至少需要20根以计算布林带）
            params: 规则6的参数配置
                - bb_period: 布林带周期（默认20）
                - bb_std: 布林带标准差倍数（默认2.0）

        Returns:
            bool: 是否检测到布林带触底回升

        检测条件（两个条件必须同时满足）:
            1. 最低价击穿下轨: Low < BB_Lower
            2. 收盘价收回下轨: Close > BB_Lower

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            params = {'bb_period': 20, 'bb_std': 2.0}
            if engine._check_bb_reversion(klines_15m, params):
                print("检测到布林带触底回升")
        """
        # 提取参数
        bb_period = params.get('bb_period', 20)
        bb_std = params.get('bb_std', 2.0)

        # 需要足够的数据计算布林带
        if len(klines) < bb_period:
            logger.debug(
                f"K线数据不足以计算布林带: 需要{bb_period}根，实际{len(klines)}根"
            )
            return False

        try:
            # 计算布林带
            ma, upper, lower = self._calculate_bollinger_bands(
                klines,
                period=bb_period,
                std_dev=bb_std
            )

            if ma is None or lower is None:
                logger.debug("布林带计算失败")
                return False

            # 获取最后一根K线
            curr_kline = klines[-1]
            curr_low = float(curr_kline.get('low', 0))
            curr_close = float(curr_kline.get('close', 0))

            # 条件1: 最低价击穿下轨
            low_break = curr_low < lower

            if not low_break:
                logger.debug(
                    f"最低价未击穿下轨: low={curr_low:.2f}, BB_Lower={lower:.2f}"
                )
                return False

            # 条件2: 收盘价收回下轨
            close_above = curr_close > lower

            if not close_above:
                logger.debug(
                    f"收盘价未收回下轨: close={curr_close:.2f}, BB_Lower={lower:.2f}"
                )
                return False

            # 所有条件满足
            logger.info(
                f"✓ 检测到布林带触底回升: low={curr_low:.2f} < BB_Lower={lower:.2f} < close={curr_close:.2f}"
            )
            return True

        except Exception as e:
            logger.error(f"检测布林带触底回升失败: {e}")
            return False

    # ========== 规则7: VPA模式检测方法 ==========

    def _detect_battering_ram(
        self,
        klines: List[Dict],
        params: Dict
    ) -> bool:
        """
        检测攻城锤模式 (Battering Ram)

        规则7的VPA信号之一：检测大阳线+放量+光头阳的强势上涨信号
        这是多头主力强力进攻的标志

        Args:
            klines: K线数据列表（至少需要50根以计算MA50）
            params: 规则7的参数配置
                - surge_threshold: 涨幅阈值（默认0.02，即2%）
                - vol_multiplier: 放量倍数（默认1.5，即成交量 >= MA50×1.5）
                - upper_shadow_ratio: 上影线比率（默认0.1，即上影线 < 实体×0.1）

        Returns:
            bool: 是否检测到攻城锤模式

        检测条件（三个条件必须同时满足）:
            1. 大阳线涨幅: (close - open) / open >= surge_threshold
            2. 放量: volume >= MA50(volume) × vol_multiplier
            3. 光头阳: upper_shadow < body × upper_shadow_ratio

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            params = {'surge_threshold': 0.02, 'vol_multiplier': 1.5, 'upper_shadow_ratio': 0.1}
            if engine._detect_battering_ram(klines_15m, params):
                print("检测到攻城锤模式")
        """
        # 需要至少50根K线以计算MA50
        if len(klines) < 50:
            logger.debug("K线数据不足以检测攻城锤模式: 需要至少50根K线")
            return False

        try:
            # 提取参数
            surge_threshold = params.get('surge_threshold', 0.02)
            vol_multiplier = params.get('vol_multiplier', 1.5)
            upper_shadow_ratio = params.get('upper_shadow_ratio', 0.1)

            # 获取最后一根K线
            curr_kline = klines[-1]

            # 提取当前K线的价格和成交量数据
            curr_open = float(curr_kline.get('open', 0))
            curr_close = float(curr_kline.get('close', 0))
            curr_high = float(curr_kline.get('high', 0))
            curr_low = float(curr_kline.get('low', 0))
            curr_volume = float(curr_kline.get('volume', 0))

            # 验证数据有效性
            if curr_open == 0 or curr_volume == 0:
                logger.debug("当前K线数据无效")
                return False

            # 条件1: 大阳线涨幅检测
            surge_pct = (curr_close - curr_open) / curr_open
            big_bullish = surge_pct >= surge_threshold

            if not big_bullish:
                logger.debug(
                    f"涨幅不足: 涨幅={surge_pct:.4f}, 阈值={surge_threshold}"
                )
                return False

            # 条件2: 放量检测 - 计算成交量MA50
            vol_ma50 = self._calculate_ma(klines, period=50, field='volume')
            if vol_ma50 is None:
                logger.debug("无法计算成交量MA50")
                return False

            vol_threshold = vol_ma50 * vol_multiplier
            volume_surge = curr_volume >= vol_threshold

            if not volume_surge:
                logger.debug(
                    f"未检测到放量: 当前={curr_volume:.2f}, 阈值={vol_threshold:.2f}"
                )
                return False

            # 条件3: 光头阳检测（上影线很短）
            body = curr_close - curr_open  # 阳线，close > open
            upper_shadow = curr_high - curr_close
            shadow_threshold = body * upper_shadow_ratio
            bald_bullish = upper_shadow < shadow_threshold

            if not bald_bullish:
                logger.debug(
                    f"上影线过长: 上影线={upper_shadow:.2f}, 阈值={shadow_threshold:.2f}"
                )
                return False

            # 所有条件满足
            logger.info(
                f"✓ 检测到攻城锤模式: 涨幅={surge_pct:.2%}, "
                f"放量={curr_volume/vol_ma50:.2f}x, 上影线={upper_shadow/body:.2%}实体"
            )
            return True

        except Exception as e:
            logger.error(f"检测攻城锤模式失败: {e}")
            return False

    def _detect_bullish_engulfing(
        self,
        klines: List[Dict],
        params: Dict
    ) -> bool:
        """
        检测阳包阴模式 (Bullish Engulfing)

        规则7的VPA信号之一：检测强势反转模式（当前阳线完全吞没前阴线）
        这是多头主力强势夺回控制权的标志

        Args:
            klines: K线数据列表（至少需要20根以计算MA20）
            params: 规则7的参数配置（无特定参数，但需要足够数据计算MA20）

        Returns:
            bool: 是否检测到阳包阴模式

        检测条件（四个条件必须同时满足）:
            1. 前一根是阴线: open_t-1 > close_t-1
            2. 当前阳线完全吞没前阴线: open_t < close_t-1 AND close_t > open_t-1
            3. 成交量增量: volume_t > volume_t-1
            4. 价格位置确认: close_t > MA20（确保在上升趋势中）

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            if engine._detect_bullish_engulfing(klines_15m, {}):
                print("检测到阳包阴模式")
        """
        # 需要至少20根K线以计算MA20
        if len(klines) < 20:
            logger.debug("K线数据不足以检测阳包阴模式: 需要至少20根K线")
            return False

        try:
            # 获取最近两根K线
            prev_kline = klines[-2]
            curr_kline = klines[-1]

            # 提取价格和成交量数据
            prev_open = float(prev_kline.get('open', 0))
            prev_close = float(prev_kline.get('close', 0))
            prev_volume = float(prev_kline.get('volume', 0))

            curr_open = float(curr_kline.get('open', 0))
            curr_close = float(curr_kline.get('close', 0))
            curr_high = float(curr_kline.get('high', 0))
            curr_low = float(curr_kline.get('low', 0))
            curr_volume = float(curr_kline.get('volume', 0))

            # 验证数据有效性
            if prev_open == 0 or prev_volume == 0 or curr_open == 0:
                logger.debug("K线数据无效")
                return False

            # 条件1: 前一根是阴线
            prev_is_bearish = prev_open > prev_close

            if not prev_is_bearish:
                logger.debug(
                    f"前一根不是阴线: open={prev_open:.2f}, close={prev_close:.2f}"
                )
                return False

            # 条件2: 当前阳线完全吞没前阴线
            # 开盘价低于前阴线收盘价，收盘价高于前阴线开盘价
            curr_is_bullish = curr_close > curr_open
            engulfing = curr_open < prev_close and curr_close > prev_open

            if not (curr_is_bullish and engulfing):
                logger.debug(
                    f"未完全吞没: curr_open={curr_open:.2f} < prev_close={prev_close:.2f}? "
                    f"curr_close={curr_close:.2f} > prev_open={prev_open:.2f}?"
                )
                return False

            # 条件3: 成交量增量
            volume_increase = curr_volume > prev_volume

            if not volume_increase:
                logger.debug(
                    f"成交量未增加: curr_vol={curr_volume:.2f} <= prev_vol={prev_volume:.2f}"
                )
                return False

            # 条件4: 价格位置确认（收盘价高于MA20）
            ma20 = self._calculate_ma(klines, period=20, field='close')

            if ma20 is None:
                logger.debug("无法计算MA20")
                return False

            above_ma20 = curr_close > ma20

            if not above_ma20:
                logger.debug(
                    f"收盘价未高于MA20: close={curr_close:.2f} <= MA20={ma20:.2f}"
                )
                return False

            # 所有条件满足
            volume_ratio = curr_volume / prev_volume if prev_volume > 0 else 0
            logger.info(
                f"✓ 检测到阳包阴模式: "
                f"前阴线[{prev_open:.2f}→{prev_close:.2f}], "
                f"当前阳线[{curr_open:.2f}→{curr_close:.2f}], "
                f"成交量增={volume_ratio:.2f}x, "
                f"收盘>{ma20:.2f}(MA20)"
            )
            return True

        except Exception as e:
            logger.error(f"检测阳包阴模式失败: {e}")
            return False

    def _check_bb_breakout(
        self,
        klines: List[Dict],
        params: Dict
    ) -> bool:
        """
        检测布林带突破扩张

        规则7的技术指标确认之一：检测价格突破布林带上轨且带宽扩张的强势信号

        Args:
            klines: K线数据列表（至少需要21根以计算两个时间点的布林带）
            params: 规则7的参数配置
                - bb_period: 布林带周期（默认20）
                - bb_std: 布林带标准差倍数（默认2.0）

        Returns:
            bool: 是否检测到布林带突破扩张

        检测条件（两个条件必须同时满足）:
            1. 收盘价突破上轨: Close > BB_Upper
            2. 带宽扩张: BandWidth_t > BandWidth_t-1
               （BandWidth = (BB_Upper - BB_Lower) / BB_Middle）

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            params = {'bb_period': 20, 'bb_std': 2.0}
            if engine._check_bb_breakout(klines_15m, params):
                print("检测到布林带突破扩张")
        """
        # 提取参数
        bb_period = params.get('bb_period', 20)
        bb_std = params.get('bb_std', 2.0)

        # 需要至少period+1根K线以计算当前和前一时刻的布林带
        min_required = bb_period + 1
        if len(klines) < min_required:
            logger.debug(
                f"K线数据不足以计算布林带突破: 需要{min_required}根，实际{len(klines)}根"
            )
            return False

        try:
            # 计算当前时刻的布林带（使用最新的period根K线）
            ma_curr, upper_curr, lower_curr = self._calculate_bollinger_bands(
                klines,
                period=bb_period,
                std_dev=bb_std
            )

            if ma_curr is None or upper_curr is None or lower_curr is None:
                logger.debug("当前布林带计算失败")
                return False

            # 计算前一时刻的布林带（排除最后一根K线）
            ma_prev, upper_prev, lower_prev = self._calculate_bollinger_bands(
                klines[:-1],
                period=bb_period,
                std_dev=bb_std
            )

            if ma_prev is None or upper_prev is None or lower_prev is None:
                logger.debug("前一时刻布林带计算失败")
                return False

            # 获取当前收盘价
            curr_close = float(klines[-1].get('close', 0))

            if curr_close == 0:
                logger.debug("当前K线数据无效")
                return False

            # 条件1: 收盘价突破上轨
            breakout = curr_close > upper_curr

            if not breakout:
                logger.debug(
                    f"收盘价未突破上轨: close={curr_close:.2f} <= upper={upper_curr:.2f}"
                )
                return False

            # 条件2: 带宽扩张
            # BandWidth = (Upper - Lower) / Middle
            bandwidth_curr = (upper_curr - lower_curr) / ma_curr if ma_curr != 0 else 0
            bandwidth_prev = (upper_prev - lower_prev) / ma_prev if ma_prev != 0 else 0

            expansion = bandwidth_curr > bandwidth_prev

            if not expansion:
                logger.debug(
                    f"带宽未扩张: 当前={bandwidth_curr:.4f} <= 前一={bandwidth_prev:.4f}"
                )
                return False

            # 所有条件满足
            bandwidth_change_pct = ((bandwidth_curr - bandwidth_prev) / bandwidth_prev * 100
                                    if bandwidth_prev > 0 else 0)
            logger.info(
                f"✓ 检测到布林带突破扩张: "
                f"close={curr_close:.2f} > upper={upper_curr:.2f}, "
                f"带宽从{bandwidth_prev:.4f}扩张到{bandwidth_curr:.4f} (+{bandwidth_change_pct:.2f}%)"
            )
            return True

        except Exception as e:
            logger.error(f"检测布林带突破扩张失败: {e}")
            return False

    def _check_rsi_acceleration(
        self,
        klines: List[Dict],
        params: Dict
    ) -> Tuple[bool, Optional[float], Optional[float]]:
        """
        检测RSI超买加速

        规则7的技术指标确认之一：检测RSI处于超买区域且加速上升

        Args:
            klines: K线数据列表（至少需要period+lookback+1根）
            params: 规则7的参数配置
                - rsi_period: RSI计算周期（默认14）
                - rsi_threshold: RSI超买阈值（默认60）
                - rsi_slope_threshold: RSI斜率阈值（默认2.0）

        Returns:
            Tuple[bool, Optional[float], Optional[float]]:
                - bool: 是否检测到RSI超买加速
                - Optional[float]: RSI值
                - Optional[float]: RSI斜率

        检测条件（两个条件必须同时满足）:
            1. RSI超买: RSI > rsi_threshold (默认60)
            2. RSI加速: (RSI_t - RSI_t-3) / 3 > rsi_slope_threshold (默认2.0)

        Example:
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            params = {'rsi_period': 14, 'rsi_threshold': 60, 'rsi_slope_threshold': 2.0}
            accelerated, rsi_value, rsi_slope = engine._check_rsi_acceleration(klines_15m, params)
            if accelerated:
                print(f"检测到RSI超买加速, RSI={rsi_value}, 斜率={rsi_slope}")
        """
        # 提取参数
        rsi_period = params.get('rsi_period', 14)
        rsi_threshold = params.get('rsi_threshold', 60)
        rsi_slope_threshold = params.get('rsi_slope_threshold', 2.0)

        # 需要足够的数据计算RSI和斜率（period + lookback=3）
        min_required = rsi_period + 4  # +1 for diff, +3 for slope
        if len(klines) < min_required:
            logger.debug(
                f"K线数据不足以计算RSI斜率: 需要{min_required}根，实际{len(klines)}根"
            )
            return (False, None, None)

        try:
            # 提取收盘价
            closes = np.array([float(k.get('close', 0)) for k in klines])

            # 计算价格变化
            deltas = np.diff(closes)

            # 分离涨跌
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            # 计算当前RSI
            avg_gain = np.mean(gains[-rsi_period:])
            avg_loss = np.mean(losses[-rsi_period:])

            if avg_loss == 0:
                rsi_current = 100.0
            else:
                rs_current = avg_gain / avg_loss
                rsi_current = 100 - 100 / (1 + rs_current)

            # 条件1: 检查是否超买
            if rsi_current <= rsi_threshold:
                logger.debug(f"RSI未超买: RSI={rsi_current:.2f} <= {rsi_threshold}")
                return (False, float(rsi_current), None)

            # 条件2: 计算RSI斜率（加速度）
            rsi_slope = self._calculate_rsi_slope(klines, period=rsi_period, lookback=3)

            if rsi_slope is None:
                logger.debug("RSI斜率计算失败")
                return (False, float(rsi_current), None)

            if rsi_slope <= rsi_slope_threshold:
                logger.debug(
                    f"RSI斜率不足: 斜率={rsi_slope:.2f} <= {rsi_slope_threshold}"
                )
                return (False, float(rsi_current), float(rsi_slope))

            # 所有条件满足
            logger.info(
                f"✓ 检测到RSI超买加速: RSI={rsi_current:.2f} > {rsi_threshold}, "
                f"斜率={rsi_slope:.2f} > {rsi_slope_threshold}"
            )
            return (True, float(rsi_current), float(rsi_slope))

        except Exception as e:
            logger.error(f"检测RSI超买加速失败: {e}")
            return (False, None, None)

    # ========== 规则6: 止盈信号监控主方法 ==========
    def _check_rule_6_take_profit(
        self,
        symbol: str,
        klines_15m: List[Dict],
        klines_1h: List[Dict],
        current_price: Decimal,
        params: Dict
    ) -> Optional[Dict]:
        """
        规则6止盈信号监控主方法

        检测"动能衰竭"信号：通过VPA识别恐慌抛售后的接盘信号，
        结合技术指标确认超卖状态，提示做多止盈时机

        Args:
            symbol: 合约代码
            klines_15m: 15分钟K线数据列表
            klines_1h: 1小时K线数据列表
            current_price: 当前价格
            params: 规则6的参数配置

        Returns:
            Optional[Dict]: 触发信息字典，格式：
                {
                    'rule_id': 6,
                    'signal_type': 'take_profit',
                    'vpa_signal': '急刹车' | '金针探底',
                    'tech_signal': 'RSI超卖' | '布林带回升',
                    'timeframe': '15m' | '1h' | '15m+1h',
                    'rsi_value': float,
                    'volume_ratio': float
                }
                如果未触发返回None

        检测逻辑:
            1. VPA信号检测（OR关系）:
               - 急刹车模式: _detect_stopping_volume()
               - 金针探底模式: TODO (Phase 4)
            2. 技术指标确认（OR关系）:
               - RSI超卖: _check_rsi_oversold()
               - 布林带回升: TODO (Phase 4)
            3. 综合决策: VPA AND 技术指标
            4. 多周期独立触发: 15m和1h周期分别检测，任一触发即可

        Example:
            engine = PriceRuleEngine()
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            klines_1h = get_klines('BTCUSDT', '1h', limit=30)
            params = {...}  # 规则6的参数
            result = engine._check_rule_6_take_profit(
                'BTCUSDT', klines_15m, klines_1h, Decimal('45000'), params
            )
            if result:
                print(f"触发止盈信号: {result}")
        """
        triggered_timeframes = []
        vpa_signal = None
        tech_signal = None
        rsi_value = None
        volume_ratio = None

        # 检测15m周期
        if klines_15m and len(klines_15m) >= 50:
            logger.debug(f"[规则6] {symbol} - 检测15m周期")

            # Step 1: VPA信号检测（急刹车 OR 金针探底）
            stopping_volume = self._detect_stopping_volume(klines_15m, params)
            golden_needle = self._detect_golden_needle(klines_15m, params)

            vpa_detected_15m = stopping_volume or golden_needle

            if vpa_detected_15m:
                # 记录VPA信号类型
                if stopping_volume:
                    vpa_signal = '急刹车'
                elif golden_needle:
                    vpa_signal = '金针探底'

                # Step 2: 技术指标确认（RSI超卖 OR 布林带回升）
                rsi_oversold, rsi_val, rsi_reason = self._check_rsi_oversold(
                    klines_15m, params
                )
                bb_reversion = self._check_bb_reversion(klines_15m, params)

                tech_confirmed_15m = rsi_oversold or bb_reversion

                if tech_confirmed_15m:
                    # 记录技术信号类型
                    if rsi_oversold:
                        tech_signal = rsi_reason  # 'RSI超卖' 或 'RSI底背离'
                        rsi_value = rsi_val
                    elif bb_reversion:
                        tech_signal = '布林带回升'

                    # 计算成交量比率
                    if len(klines_15m) >= 2:
                        curr_vol = float(klines_15m[-1].get('volume', 0))
                        prev_vol = float(klines_15m[-2].get('volume', 0))
                        if prev_vol > 0:
                            volume_ratio = curr_vol / prev_vol

                    triggered_timeframes.append('15m')
                    logger.info(
                        f"[规则6] {symbol} - 15m周期触发: {vpa_signal}+{tech_signal}"
                    )

        # 检测1h周期
        if klines_1h and len(klines_1h) >= 50:
            logger.debug(f"[规则6] {symbol} - 检测1h周期")

            # Step 1: VPA信号检测
            stopping_volume = self._detect_stopping_volume(klines_1h, params)
            golden_needle = self._detect_golden_needle(klines_1h, params)

            vpa_detected_1h = stopping_volume or golden_needle

            if vpa_detected_1h:
                # 如果15m周期未触发，需要记录VPA信号类型
                if not vpa_signal:
                    if stopping_volume:
                        vpa_signal = '急刹车'
                    elif golden_needle:
                        vpa_signal = '金针探底'

                # Step 2: 技术指标确认
                rsi_oversold, rsi_val, rsi_reason = self._check_rsi_oversold(
                    klines_1h, params
                )
                bb_reversion = self._check_bb_reversion(klines_1h, params)

                tech_confirmed_1h = rsi_oversold or bb_reversion

                if tech_confirmed_1h:
                    # 如果15m周期未触发，需要记录技术信号类型
                    if not tech_signal:
                        if rsi_oversold:
                            tech_signal = rsi_reason
                            rsi_value = rsi_val
                        elif bb_reversion:
                            tech_signal = '布林带回升'

                    # 计算成交量比率（如果15m未计算）
                    if volume_ratio is None and len(klines_1h) >= 2:
                        curr_vol = float(klines_1h[-1].get('volume', 0))
                        prev_vol = float(klines_1h[-2].get('volume', 0))
                        if prev_vol > 0:
                            volume_ratio = curr_vol / prev_vol

                    triggered_timeframes.append('1h')
                    logger.info(
                        f"[规则6] {symbol} - 1h周期触发: {vpa_signal}+{tech_signal}"
                    )

        # 判断是否触发
        if not triggered_timeframes:
            logger.debug(f"[规则6] {symbol} - 未触发")
            return None

        # 构造触发结果
        timeframe_str = '+'.join(triggered_timeframes)
        result = {
            'rule_id': 6,
            'signal_type': 'take_profit',
            'vpa_signal': vpa_signal,
            'tech_signal': tech_signal,
            'timeframe': timeframe_str,
            'rsi_value': rsi_value,
            'volume_ratio': volume_ratio
        }

        logger.info(
            f"[规则6] {symbol} - 触发止盈信号: "
            f"{vpa_signal}+{tech_signal} [{timeframe_str}]"
        )
        return result

    # ========== 规则7: 止损信号监控主方法 ==========
    def _check_rule_7_stop_loss(
        self,
        symbol: str,
        klines_15m: List[Dict],
        klines_1h: List[Dict],
        current_price: Decimal,
        params: Dict
    ) -> Optional[Dict]:
        """
        规则7止损信号监控主方法

        检测"动能爆发"信号：通过VPA识别多头主力进攻信号，
        结合技术指标确认超买加速状态，提示做空止损时机

        Args:
            symbol: 合约代码
            klines_15m: 15分钟K线数据列表
            klines_1h: 1小时K线数据列表
            current_price: 当前价格
            params: 规则7的参数配置

        Returns:
            Optional[Dict]: 触发信息字典，格式：
                {
                    'rule_id': 7,
                    'signal_type': 'stop_loss',
                    'vpa_signal': '攻城锤' | '阳包阴',
                    'tech_signal': 'RSI超买加速' | '布林带突破扩张',
                    'timeframe': '15m' | '1h' | '15m+1h',
                    'rsi_value': float,
                    'rsi_slope': float,
                    'volume_ratio': float
                }
                如果未触发返回None

        检测逻辑:
            1. VPA信号检测（OR关系）:
               - 攻城锤模式: _detect_battering_ram()
               - 阳包阴模式: TODO (Phase 6)
            2. 技术指标确认（OR关系）:
               - RSI超买加速: _check_rsi_acceleration()
               - 布林带突破扩张: TODO (Phase 6)
            3. 综合决策: VPA AND 技术指标
            4. 多周期独立触发: 15m和1h周期分别检测，任一触发即可

        Example:
            engine = PriceRuleEngine()
            klines_15m = get_klines('BTCUSDT', '15m', limit=100)
            klines_1h = get_klines('BTCUSDT', '1h', limit=30)
            params = {...}  # 规则7的参数
            result = engine._check_rule_7_stop_loss(
                'BTCUSDT', klines_15m, klines_1h, Decimal('98000'), params
            )
            if result:
                print(f"触发止损信号: {result}")
        """
        triggered_timeframes = []
        vpa_signal = None
        tech_signal = None
        rsi_value = None
        rsi_slope = None
        volume_ratio = None

        # 检测15m周期
        if klines_15m and len(klines_15m) >= 50:
            logger.debug(f"[规则7] {symbol} - 检测15m周期")

            # Step 1: VPA信号检测（攻城锤 OR 阳包阴）
            battering_ram = self._detect_battering_ram(klines_15m, params)
            bullish_engulfing = self._detect_bullish_engulfing(klines_15m, params)

            vpa_detected_15m = battering_ram or bullish_engulfing

            if vpa_detected_15m:
                # 记录VPA信号类型
                if battering_ram:
                    vpa_signal = '攻城锤'
                elif bullish_engulfing:
                    vpa_signal = '阳包阴'

                # Step 2: 技术指标确认（RSI超买加速 OR 布林带突破扩张）
                rsi_accelerated, rsi_val, rsi_sl = self._check_rsi_acceleration(
                    klines_15m, params
                )
                bb_breakout = self._check_bb_breakout(klines_15m, params)

                tech_confirmed_15m = rsi_accelerated or bb_breakout

                if tech_confirmed_15m:
                    # 记录技术信号类型
                    if rsi_accelerated:
                        tech_signal = 'RSI超买加速'
                        rsi_value = rsi_val
                        rsi_slope = rsi_sl
                    elif bb_breakout:
                        tech_signal = '布林带突破扩张'

                    # 计算成交量比率
                    if len(klines_15m) >= 2:
                        curr_vol = float(klines_15m[-1].get('volume', 0))
                        prev_vol = float(klines_15m[-2].get('volume', 0))
                        if prev_vol > 0:
                            volume_ratio = curr_vol / prev_vol

                    triggered_timeframes.append('15m')
                    logger.info(
                        f"[规则7] {symbol} - 15m周期触发: {vpa_signal}+{tech_signal}"
                    )

        # 检测1h周期
        if klines_1h and len(klines_1h) >= 50:
            logger.debug(f"[规则7] {symbol} - 检测1h周期")

            # Step 1: VPA信号检测
            battering_ram = self._detect_battering_ram(klines_1h, params)
            bullish_engulfing = self._detect_bullish_engulfing(klines_1h, params)

            vpa_detected_1h = battering_ram or bullish_engulfing

            if vpa_detected_1h:
                # 如果15m周期未触发，需要记录VPA信号类型
                if not vpa_signal:
                    if battering_ram:
                        vpa_signal = '攻城锤'
                    elif bullish_engulfing:
                        vpa_signal = '阳包阴'

                # Step 2: 技术指标确认
                rsi_accelerated, rsi_val, rsi_sl = self._check_rsi_acceleration(
                    klines_1h, params
                )
                bb_breakout = self._check_bb_breakout(klines_1h, params)

                tech_confirmed_1h = rsi_accelerated or bb_breakout

                if tech_confirmed_1h:
                    # 如果15m周期未触发，需要记录技术信号类型
                    if not tech_signal:
                        if rsi_accelerated:
                            tech_signal = 'RSI超买加速'
                            rsi_value = rsi_val
                            rsi_slope = rsi_sl
                        elif bb_breakout:
                            tech_signal = '布林带突破扩张'

                    # 计算成交量比率（如果15m未计算）
                    if volume_ratio is None and len(klines_1h) >= 2:
                        curr_vol = float(klines_1h[-1].get('volume', 0))
                        prev_vol = float(klines_1h[-2].get('volume', 0))
                        if prev_vol > 0:
                            volume_ratio = curr_vol / prev_vol

                    triggered_timeframes.append('1h')
                    logger.info(
                        f"[规则7] {symbol} - 1h周期触发: {vpa_signal}+{tech_signal}"
                    )

        # 判断是否触发
        if not triggered_timeframes:
            logger.debug(f"[规则7] {symbol} - 未触发")
            return None

        # 构造触发结果
        timeframe_str = '+'.join(triggered_timeframes)
        result = {
            'rule_id': 7,
            'signal_type': 'stop_loss',
            'vpa_signal': vpa_signal,
            'tech_signal': tech_signal,
            'timeframe': timeframe_str,
            'rsi_value': rsi_value,
            'rsi_slope': rsi_slope,
            'volume_ratio': volume_ratio
        }

        logger.info(
            f"[规则7] {symbol} - 触发止损信号: "
            f"{vpa_signal}+{tech_signal} [{timeframe_str}]"
        )
        return result
