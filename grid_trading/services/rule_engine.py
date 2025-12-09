"""
价格触发规则引擎
Price Alert Rule Engine

实现5种价格触发规则的判定逻辑和防重复推送机制
Feature: 001-price-alert-monitor
Tasks: T018-T025, T028-T030
"""
import logging
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
        klines_4h: List[Dict]
    ) -> List[Dict]:
        """
        检查所有启用的规则（批量模式，不立即推送）

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
                    'current_price': Decimal
                }

        Example:
            engine = PriceRuleEngine()
            results = engine.check_all_rules_batch('BTCUSDT', price, klines)
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
        parameters: Dict
    ) -> Tuple[bool, Dict]:
        """
        检查单个规则

        Args:
            rule_id: 规则ID (1-5)
            symbol: 合约代码
            current_price: 当前价格
            klines_4h: 4h K线数据
            parameters: 规则参数

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
