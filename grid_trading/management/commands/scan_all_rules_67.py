"""
扫描币安所有USDT永续合约的规则6和7触发情况
用于验证规则6和7的指标正确性
"""
from django.core.management.base import BaseCommand
from grid_trading.services.rule_engine import PriceRuleEngine
from grid_trading.services.kline_cache import KlineCache
from grid_trading.services.binance_futures_client import BinanceFuturesClient
from decimal import Decimal
import logging

# 禁用详细日志
logging.disable(logging.INFO)


class Command(BaseCommand):
    help = '扫描币安所有USDT永续合约的规则6和7触发情况'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=0,
            help='限制检测的合约数量（默认0=检测全部）'
        )

    def handle(self, *args, **options):
        limit = options['limit']

        self.stdout.write('=' * 80)
        self.stdout.write('规则6和7全市场扫描 - 币安USDT永续合约')
        self.stdout.write('=' * 80)
        self.stdout.write('')

        # 初始化
        client = BinanceFuturesClient()
        cache = KlineCache(api_client=client)
        engine = PriceRuleEngine()

        # 从本地数据库获取所有有K线数据的合约
        self.stdout.write('正在从本地数据库获取合约列表...')
        try:
            from grid_trading.models import KlineData
            usdt_symbols = sorted(list(set(KlineData.objects.values_list('symbol', flat=True))))
            self.stdout.write(f'从本地数据库获取到 {len(usdt_symbols)} 个合约')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'获取本地合约列表失败: {str(e)}'))
            return

        total_count = len(usdt_symbols)
        if limit > 0:
            usdt_symbols = usdt_symbols[:limit]
            self.stdout.write(f'检测合约总数: {len(usdt_symbols)} (限制前: {total_count})')
        else:
            self.stdout.write(f'检测合约总数: {total_count}')

        self.stdout.write('')

        # 收集触发的合约
        rule_6_triggers = []
        rule_7_triggers = []
        success_count = 0
        failed_count = 0

        # 遍历检测
        for idx, symbol in enumerate(usdt_symbols, 1):
            self.stdout.write(f'[{idx}/{len(usdt_symbols)}] 检测 {symbol}...', ending=' ')
            self.stdout.flush()

            try:
                # 获取当前价格
                ticker = client.get_ticker(symbol)
                if not ticker or 'price' not in ticker:
                    self.stdout.write('❌ 无法获取价格')
                    failed_count += 1
                    continue

                current_price = Decimal(ticker['price'])

                # 获取K线数据（优先使用本地数据库）
                klines_15m = cache.get_klines(symbol, interval='15m', limit=100, use_cache=True)
                klines_1h = cache.get_klines(symbol, interval='1h', limit=50, use_cache=True)
                klines_4h = cache.get_klines(symbol, interval='4h', limit=42, use_cache=True)

                if not klines_15m or len(klines_15m) < 50:
                    self.stdout.write('⚠️ K线数据不足')
                    failed_count += 1
                    continue

                # 调用规则引擎检测
                results = engine.check_all_rules_batch(
                    symbol=symbol,
                    current_price=current_price,
                    klines_4h=klines_4h or [],
                    klines_15m=klines_15m,
                    klines_1h=klines_1h or []
                )

                # 筛选规则6和7的触发
                rule_6_result = None
                rule_7_result = None

                for result in results:
                    if result['rule_id'] == 6:
                        rule_6_result = result
                    elif result['rule_id'] == 7:
                        rule_7_result = result

                if rule_6_result:
                    self.stdout.write('🟢 触发规则6', ending=' ')
                    rule_6_triggers.append({
                        'symbol': symbol,
                        'price': current_price,
                        'vpa_signal': rule_6_result['extra_info'].get('vpa_signal'),
                        'tech_signal': rule_6_result['extra_info'].get('tech_signal'),
                        'timeframe': rule_6_result['extra_info'].get('timeframe'),
                        'rsi_value': rule_6_result['extra_info'].get('rsi_value')
                    })

                if rule_7_result:
                    self.stdout.write('🔴 触发规则7', ending=' ')
                    rule_7_triggers.append({
                        'symbol': symbol,
                        'price': current_price,
                        'vpa_signal': rule_7_result['extra_info'].get('vpa_signal'),
                        'tech_signal': rule_7_result['extra_info'].get('tech_signal'),
                        'timeframe': rule_7_result['extra_info'].get('timeframe'),
                        'rsi_value': rule_7_result['extra_info'].get('rsi_value'),
                        'rsi_slope': rule_7_result['extra_info'].get('rsi_slope')
                    })

                if not rule_6_result and not rule_7_result:
                    self.stdout.write('✓ 无触发')
                else:
                    self.stdout.write('')

                success_count += 1

            except Exception as e:
                self.stdout.write(f'❌ 检测失败: {str(e)[:50]}')
                failed_count += 1
                continue

        self.stdout.write('')
        self.stdout.write('=' * 80)
        self.stdout.write('检测结果汇总')
        self.stdout.write('=' * 80)
        self.stdout.write('')
        self.stdout.write(f'成功检测: {success_count} 个合约')
        self.stdout.write(f'失败/跳过: {failed_count} 个合约')
        self.stdout.write('')

        # 显示规则6触发结果
        self.stdout.write(f'🟢 规则6 (止盈信号) 触发数量: {len(rule_6_triggers)}')
        self.stdout.write('-' * 80)
        if rule_6_triggers:
            for trigger in rule_6_triggers:
                self.stdout.write(f"  {trigger['symbol']:12s} ${float(trigger['price']):>10,.4f}")
                self.stdout.write(f"    VPA: {trigger['vpa_signal']:10s} | 技术: {trigger['tech_signal']}")
                rsi_str = f"{trigger['rsi_value']:.1f}" if trigger['rsi_value'] else 'N/A'
                self.stdout.write(f"    周期: {trigger['timeframe']:10s} | RSI: {rsi_str}")
                self.stdout.write('')
        else:
            self.stdout.write('  暂无合约触发规则6')
            self.stdout.write('')

        # 显示规则7触发结果
        self.stdout.write(f'🔴 规则7 (止损信号) 触发数量: {len(rule_7_triggers)}')
        self.stdout.write('-' * 80)
        if rule_7_triggers:
            for trigger in rule_7_triggers:
                self.stdout.write(f"  {trigger['symbol']:12s} ${float(trigger['price']):>10,.4f}")
                self.stdout.write(f"    VPA: {trigger['vpa_signal']:10s} | 技术: {trigger['tech_signal']}")
                rsi_str = f"{trigger['rsi_value']:.1f}" if trigger['rsi_value'] else 'N/A'
                slope_str = f" | 斜率: {trigger['rsi_slope']:.2f}" if trigger['rsi_slope'] else ""
                self.stdout.write(f"    周期: {trigger['timeframe']:10s} | RSI: {rsi_str}{slope_str}")
                self.stdout.write('')
        else:
            self.stdout.write('  暂无合约触发规则7')
            self.stdout.write('')

        self.stdout.write('=' * 80)
        self.stdout.write(f'总结: 检测 {success_count} 个合约，规则6触发 {len(rule_6_triggers)} 个，规则7触发 {len(rule_7_triggers)} 个')
        self.stdout.write('=' * 80)
