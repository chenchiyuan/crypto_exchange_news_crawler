"""
价格触发检测脚本
Price Alert Check Script

每次执行检查所有启用的监控合约，调用规则引擎判定是否触发告警
Feature: 001-price-alert-monitor
Task: T011, T026-T032
"""
import sys
import logging
from decimal import Decimal
from typing import List, Dict
from django.core.management.base import BaseCommand
from django.utils import timezone
from grid_trading.django_models import (
    MonitoredContract,
    PriceAlertRule,
    AlertTriggerLog,
    SystemConfig
)
from grid_trading.services.script_lock import acquire_lock, release_lock
from grid_trading.services.rule_engine import PriceRuleEngine
from grid_trading.services.kline_cache import KlineCache
from grid_trading.services.binance_futures_client import BinanceFuturesClient

logger = logging.getLogger("grid_trading")


class Command(BaseCommand):
    help = '检测价格触发规则并发送告警'

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-lock',
            action='store_true',
            help='跳过脚本锁检查(仅用于测试)'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            help='指定检测的合约(逗号分隔)，如: BTCUSDT,ETHUSDT'
        )
        parser.add_argument(
            '--retry-failed',
            action='store_true',
            help='重试最近1小时内失败的推送'
        )

    def handle(self, *args, **options):
        """
        主执行函数

        工作流程:
        1. 获取脚本锁
        2. (可选)重试失败的推送
        3. 查询启用的监控合约
        4. 批量检测价格触发规则
        5. 输出执行统计并释放锁
        """
        lock_name = 'price_alert_check'
        skip_lock = options.get('skip_lock', False)

        # Step 1: 获取脚本锁
        if not skip_lock:
            if not acquire_lock(lock_name, timeout_minutes=5):
                self.stdout.write(
                    self.style.ERROR('✗ 脚本已在运行，跳过本次执行')
                )
                sys.exit(1)

        try:
            start_time = timezone.now()
            self.stdout.write(
                self.style.SUCCESS(
                    f'[{start_time.strftime("%Y-%m-%d %H:%M:%S")}] '
                    f'开始价格触发检测...'
                )
            )

            # 初始化规则引擎
            engine = PriceRuleEngine()

            # Step 2: (可选)重试失败的推送
            if options.get('retry_failed'):
                self.stdout.write('\n重试失败的推送...')
                retried_count = engine.retry_failed_pushes(hours=1)
                self.stdout.write(
                    self.style.SUCCESS(f'✓ 成功重试 {retried_count} 条失败推送\n')
                )

            # Step 3: 查询监控合约
            if options.get('symbols'):
                symbols = options['symbols'].split(',')
                contracts = MonitoredContract.objects.filter(
                    symbol__in=symbols,
                    status='enabled'
                )
            else:
                contracts = MonitoredContract.objects.filter(status='enabled')

            contracts_count = contracts.count()

            self.stdout.write(
                self.style.SUCCESS(f'获取到 {contracts_count} 个启用的监控合约')
            )

            if contracts_count == 0:
                self.stdout.write(
                    self.style.WARNING('⚠️ 没有启用的监控合约，退出执行')
                )
                return

            # 检查启用的规则数量
            enabled_rules_count = PriceAlertRule.objects.filter(enabled=True).count()
            self.stdout.write(
                self.style.SUCCESS(f'启用规则数量: {enabled_rules_count}\n')
            )

            if enabled_rules_count == 0:
                self.stdout.write(
                    self.style.WARNING('⚠️ 没有启用的规则，退出执行')
                )
                return

            # Step 4: 批量检测价格触发规则
            stats = self._check_all_contracts(contracts, engine)

            # Step 5: 输出执行统计
            elapsed_seconds = (timezone.now() - start_time).total_seconds()

            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ 价格检测完成，耗时 {elapsed_seconds:.1f} 秒'
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f'统计: 检测 {stats["total_contracts"]} 个合约，'
                    f'触发 {stats["total_triggered"]} 次规则，'
                    f'推送 {stats["total_pushed"]} 条告警'
                )
            )

            if stats['failed_contracts']:
                self.stdout.write(
                    self.style.WARNING(
                        f'\n⚠️ {len(stats["failed_contracts"])} 个合约检测失败:'
                    )
                )
                for symbol in stats['failed_contracts'][:5]:  # 只显示前5个
                    self.stdout.write(f'  - {symbol}')

        except Exception as e:
            logger.error(f"价格检测异常: {e}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f'✗ 价格检测失败: {e}')
            )
            sys.exit(1)

        finally:
            # 释放脚本锁
            if not skip_lock:
                release_lock(lock_name)

    def _check_all_contracts(
        self,
        contracts,
        engine: PriceRuleEngine
    ) -> Dict:
        """
        检测所有合约的价格触发规则

        Args:
            contracts: 监控合约查询集
            engine: 规则引擎实例

        Returns:
            dict: 执行统计信息
        """
        # 初始化币安客户端和K线缓存
        try:
            client = BinanceFuturesClient()
            cache = KlineCache(api_client=client)
        except Exception as e:
            logger.error(f"初始化币安客户端失败: {e}")
            raise

        stats = {
            'total_contracts': contracts.count(),
            'total_triggered': 0,
            'total_pushed': 0,
            'failed_contracts': []
        }

        # 收集所有触发的告警（用于批量推送）
        batch_alerts = {}

        # 遍历每个合约
        for idx, contract in enumerate(contracts, 1):
            symbol = contract.symbol
            self.stdout.write(
                f'\n[{idx}/{contracts.count()}] 检测 {symbol}...'
            )

            try:
                # 获取当前价格
                current_price = self._get_current_price(client, symbol)

                if current_price is None:
                    self.stdout.write(
                        self.style.ERROR(f'  ✗ 无法获取当前价格')
                    )
                    stats['failed_contracts'].append(symbol)
                    continue

                self.stdout.write(
                    f'  当前价格: ${float(current_price):,.2f}'
                )

                # 获取4h K线数据(7天=42根)
                klines_4h = cache.get_klines(
                    symbol=symbol,
                    interval='4h',
                    limit=42,
                    use_cache=True
                )

                if not klines_4h or len(klines_4h) < 3:
                    self.stdout.write(
                        self.style.WARNING(
                            f'  ⚠️ K线数据不足(需要至少3根，实际{len(klines_4h) if klines_4h else 0}根)'
                        )
                    )
                    stats['failed_contracts'].append(symbol)
                    continue

                self.stdout.write(
                    f'  K线数据: {len(klines_4h)} 根(4h)'
                )

                # 调用规则引擎检测所有规则（批量模式，不立即推送）
                triggered_rules = engine.check_all_rules_batch(
                    symbol=symbol,
                    current_price=current_price,
                    klines_4h=klines_4h
                )

                # 如果有触发，计算波动率并收集到batch_alerts
                if triggered_rules:
                    # 计算波动率（基于100根15m K线振幅累计）
                    volatility = self._calculate_volatility(symbol, cache)

                    # 为每个触发的规则添加波动率信息
                    for rule in triggered_rules:
                        rule['volatility'] = volatility

                    batch_alerts[symbol] = triggered_rules
                    stats['total_triggered'] += len(triggered_rules)

                    self.stdout.write(
                        self.style.WARNING(
                            f'  🔔 触发 {len(triggered_rules)} 个规则:'
                        )
                    )

                    for result in triggered_rules:
                        self.stdout.write(
                            f'    - 规则{result["rule_id"]}: {result["rule_name"]}'
                        )
                else:
                    self.stdout.write('  ✓ 未触发任何规则')

            except Exception as e:
                logger.error(
                    f"检测 {symbol} 失败: {e}",
                    exc_info=True
                )
                stats['failed_contracts'].append(symbol)
                self.stdout.write(
                    self.style.ERROR(f'  ✗ 检测失败: {e}')
                )

        # 检测完所有合约后，批量推送
        if batch_alerts:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n📤 准备批量推送 {len(batch_alerts)} 个合约的告警...'
                )
            )

            # 防重复过滤：检查每个触发是否在防重复时间窗口内
            from datetime import timedelta
            suppress_minutes = int(SystemConfig.get_value('duplicate_suppress_minutes', 60))
            threshold_time = timezone.now() - timedelta(minutes=suppress_minutes)

            filtered_alerts = {}
            skipped_alerts = {}

            for symbol, triggers in batch_alerts.items():
                valid_triggers = []
                skipped_triggers = []

                for trigger in triggers:
                    rule_id = trigger['rule_id']

                    # 查询最近一次推送时间
                    last_push = AlertTriggerLog.objects.filter(
                        symbol=symbol,
                        rule_id=rule_id,
                        pushed=True,
                        pushed_at__gte=threshold_time
                    ).order_by('-pushed_at').first()

                    if last_push:
                        # 计算距上次推送的时间
                        elapsed_minutes = (
                            timezone.now() - last_push.pushed_at
                        ).total_seconds() / 60

                        skip_reason = f'防重复(上次推送于 {elapsed_minutes:.1f} 分钟前)'

                        # 记录跳过的触发
                        skipped_triggers.append({
                            'trigger': trigger,
                            'skip_reason': skip_reason
                        })

                        self.stdout.write(
                            self.style.WARNING(
                                f'  ⊘ {symbol} 规则{rule_id} 跳过推送 ({skip_reason})'
                            )
                        )
                    else:
                        valid_triggers.append(trigger)

                # 保存有效和跳过的触发
                if valid_triggers:
                    filtered_alerts[symbol] = valid_triggers
                if skipped_triggers:
                    skipped_alerts[symbol] = skipped_triggers

            # 记录跳过的触发到数据库
            for symbol, skipped in skipped_alerts.items():
                for item in skipped:
                    trigger = item['trigger']
                    AlertTriggerLog.objects.create(
                        symbol=symbol,
                        rule_id=trigger['rule_id'],
                        current_price=trigger['current_price'],
                        pushed=False,
                        skip_reason=item['skip_reason'],
                        extra_info=trigger['extra_info']
                    )

            # 如果没有有效触发，直接返回
            if not filtered_alerts:
                self.stdout.write(
                    self.style.WARNING('⊘ 所有触发都在防重复时间窗口内，跳过推送')
                )
                return stats

            # 显示实际推送的触发数
            total_valid_triggers = sum(len(t) for t in filtered_alerts.values())
            total_skipped_triggers = sum(len(s) for s in skipped_alerts.values())

            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ 过滤完成: {total_valid_triggers}个有效触发, {total_skipped_triggers}个跳过'
                )
            )

            # 转换数据格式为PriceAlertNotifier.send_batch_alert所需格式
            formatted_alerts = {}
            for symbol, triggers in filtered_alerts.items():
                formatted_alerts[symbol] = [
                    {
                        'rule_id': t['rule_id'],
                        'rule_name': t['rule_name'],
                        'price': t['current_price'],
                        'extra_info': t['extra_info'],
                        'volatility': t.get('volatility', 0)  # 添加波动率字段
                    }
                    for t in triggers
                ]

            # 发送批量推送
            from grid_trading.services.alert_notifier import PriceAlertNotifier
            notifier = PriceAlertNotifier()

            try:
                success = notifier.send_batch_alert(formatted_alerts)

                if success:
                    stats['total_pushed'] = total_valid_triggers
                    self.stdout.write(
                        self.style.SUCCESS('✓ 批量推送成功')
                    )

                    # 记录所有触发到数据库（只记录实际推送的）
                    for symbol, triggers in filtered_alerts.items():
                        for trigger in triggers:
                            AlertTriggerLog.objects.create(
                                symbol=symbol,
                                rule_id=trigger['rule_id'],
                                current_price=trigger['current_price'],
                                pushed=True,
                                pushed_at=timezone.now(),
                                skip_reason='',
                                extra_info=trigger['extra_info']
                            )
                else:
                    self.stdout.write(
                        self.style.ERROR('✗ 批量推送失败')
                    )

                    # 记录失败到数据库
                    for symbol, triggers in filtered_alerts.items():
                        for trigger in triggers:
                            AlertTriggerLog.objects.create(
                                symbol=symbol,
                                rule_id=trigger['rule_id'],
                                current_price=trigger['current_price'],
                                pushed=False,
                                skip_reason='批量推送失败',
                                extra_info=trigger['extra_info']
                            )
            except Exception as e:
                logger.error(f"批量推送异常: {e}", exc_info=True)
                self.stdout.write(
                    self.style.ERROR(f'✗ 批量推送异常: {e}')
                )

                # 记录异常到数据库
                for symbol, triggers in filtered_alerts.items():
                    for trigger in triggers:
                        AlertTriggerLog.objects.create(
                            symbol=symbol,
                            rule_id=trigger['rule_id'],
                            current_price=trigger['current_price'],
                            pushed=False,
                            skip_reason=f'推送异常: {str(e)}',
                            extra_info=trigger['extra_info']
                        )
        else:
            self.stdout.write(
                self.style.SUCCESS('\n✓ 无触发告警，跳过推送')
            )

        return stats

    def _get_current_price(
        self,
        client: BinanceFuturesClient,
        symbol: str
    ) -> Decimal:
        """
        获取合约当前价格

        Args:
            client: 币安客户端
            symbol: 合约代码

        Returns:
            Decimal: 当前价格，失败返回None
        """
        try:
            ticker = client.get_ticker(symbol)
            if ticker:
                # API返回的字段是 'price' 而非 'lastPrice'
                if 'price' in ticker:
                    return Decimal(ticker['price'])
                elif 'lastPrice' in ticker:
                    return Decimal(ticker['lastPrice'])
                else:
                    logger.error(f"获取 {symbol} 价格失败: ticker数据格式错误 - {ticker}")
                    return None
            else:
                logger.error(f"获取 {symbol} 价格失败: ticker为空")
                return None
        except Exception as e:
            logger.error(f"获取 {symbol} 价格异常: {e}")
            return None

    def _get_volatility_from_db(self, symbol: str) -> float:
        """
        从数据库中获取最新的15分钟振幅累计（优先使用）

        Args:
            symbol: 合约代码

        Returns:
            float: 振幅累计百分比，如果没有数据返回0.0
        """
        try:
            from grid_trading.models import ScreeningRecord, ScreeningResultModel
            from datetime import timedelta

            # 查找最近3天内的筛选记录中的该合约数据
            three_days_ago = timezone.now() - timedelta(days=3)
            result = ScreeningResultModel.objects.filter(
                symbol=symbol,
                record__created_at__gte=three_days_ago
            ).select_related('record').order_by('-record__created_at').first()

            if result:
                logger.info(f"✓ 从数据库获取 {symbol} 波动率: {result.amplitude_sum_15m}")
                return result.amplitude_sum_15m

            logger.warning(f"⚠️ 数据库中无 {symbol} 最近数据，将实时计算")
            return 0.0
        except Exception as e:
            logger.error(f"从数据库获取波动率失败: {e}")
            return 0.0

    def _calculate_volatility(self, symbol: str, cache) -> float:
        """
        计算15分钟K线振幅累计和（与筛选系统一致）

        公式:
            Amplitude_i = (High_i - Low_i) / Close_i × 100  (百分比)
            Amplitude_Sum = Σ Amplitude_i (最近100根15m K线)

        Args:
            symbol: 合约代码
            cache: K线缓存对象

        Returns:
            float: 振幅累计百分比
        """
        try:
            # 优先从数据库获取
            volatility = self._get_volatility_from_db(symbol)
            if volatility > 0:
                return volatility

            # 如果数据库没有，实时计算
            logger.info(f"实时计算 {symbol} 波动率...")
            klines_15m = cache.get_klines(
                symbol=symbol,
                interval='15m',
                limit=100,
                use_cache=True
            )

            if not klines_15m or len(klines_15m) < 100:
                return 0.0

            # 计算每根K线的振幅百分比并累加
            amplitude_sum = sum(
                (float(k["high"]) - float(k["low"])) / float(k["close"]) * 100.0
                for k in klines_15m[-100:]
            )

            return round(amplitude_sum, 2)
        except Exception as e:
            logger.error(f"计算振幅累计失败: {e}")
            return 0.0
