"""
详细分析合约的规则6和7检测状态
显示每个合约距离触发的差距
"""
from django.core.management.base import BaseCommand
from grid_trading.django_models import MonitoredContract
from grid_trading.services.rule_engine import PriceRuleEngine
from grid_trading.services.kline_cache import KlineCache
from grid_trading.services.binance_futures_client import BinanceFuturesClient
from decimal import Decimal
import logging

# 禁用详细日志
logging.disable(logging.INFO)


class Command(BaseCommand):
    help = '详细分析合约的规则6和7检测状态'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol',
            type=str,
            help='指定分析的合约（可选，默认分析前5个）'
        )

    def handle(self, *args, **options):
        self.stdout.write('=' * 80)
        self.stdout.write('规则6和7详细技术分析')
        self.stdout.write('=' * 80)
        self.stdout.write('')

        # 初始化
        client = BinanceFuturesClient()
        cache = KlineCache(api_client=client)
        engine = PriceRuleEngine()

        # 获取合约
        if options.get('symbol'):
            contracts = MonitoredContract.objects.filter(
                symbol=options['symbol'],
                status='enabled'
            )
        else:
            contracts = MonitoredContract.objects.filter(status='enabled').order_by('symbol')[:5]

        for contract in contracts:
            symbol = contract.symbol
            self.stdout.write('')
            self.stdout.write('=' * 80)
            self.stdout.write(f'分析合约: {symbol}')
            self.stdout.write('=' * 80)

            try:
                # 获取当前价格
                ticker = client.get_ticker(symbol)
                if not ticker or 'price' not in ticker:
                    self.stdout.write('❌ 无法获取价格')
                    continue

                current_price = Decimal(ticker['price'])
                self.stdout.write(f'当前价格: ${float(current_price):,.4f}')
                self.stdout.write('')

                # 获取K线数据
                klines_15m = cache.get_klines(symbol, interval='15m', limit=100, use_cache=False)
                klines_1h = cache.get_klines(symbol, interval='1h', limit=50, use_cache=False)

                if not klines_15m or len(klines_15m) < 50:
                    self.stdout.write('⚠️ K线数据不足，跳过分析')
                    continue

                self.stdout.write(f'K线数据: 15m={len(klines_15m)}根, 1h={len(klines_1h) if klines_1h else 0}根')
                self.stdout.write('')

                # 分析规则6 (15m周期)
                self.stdout.write('【规则6分析 - 止盈信号监控 (15m周期)】')
                self.stdout.write('-' * 80)
                self._analyze_rule_6(engine, klines_15m, symbol)

                self.stdout.write('')

                # 分析规则7 (15m周期)
                self.stdout.write('【规则7分析 - 止损信号监控 (15m周期)】')
                self.stdout.write('-' * 80)
                self._analyze_rule_7(engine, klines_15m, symbol)

            except Exception as e:
                self.stdout.write(f'❌ 分析失败: {str(e)}')
                import traceback
                self.stdout.write(traceback.format_exc())
                continue

        self.stdout.write('')
        self.stdout.write('=' * 80)
        self.stdout.write('分析完成')
        self.stdout.write('=' * 80)

    def _analyze_rule_6(self, engine, klines, symbol):
        """分析规则6的各项条件"""
        params = {
            'crash_threshold': 0.02,
            'vol_multi_spike': 2.5,
            'vol_multi_sustain': 0.8,
            'body_shrink_ratio': 0.25,
            'lower_shadow_ratio': 2.0,
            'close_position_ratio': 0.6,
            'rsi_period': 14,
            'rsi_oversold': 20,
            'bb_period': 20,
            'bb_std': 2.0
        }

        # 检测急刹车
        stopping_volume = engine._detect_stopping_volume(klines, params)
        self.stdout.write(f'  VPA模式1 - 急刹车: {"✓ 触发" if stopping_volume else "✗ 未触发"}')
        if not stopping_volume and len(klines) >= 2:
            # 分析原因
            prev_kline = klines[-2]
            curr_kline = klines[-1]
            prev_drop = (float(prev_kline['open']) - float(prev_kline['close'])) / float(prev_kline['open'])
            vol_ratio = float(curr_kline['volume']) / float(prev_kline['volume'])
            prev_body = abs(float(prev_kline['close']) - float(prev_kline['open']))
            curr_body = abs(float(curr_kline['close']) - float(curr_kline['open']))
            body_ratio = curr_body / prev_body if prev_body > 0 else 0

            self.stdout.write(f'    - 前序跌幅: {prev_drop:.2%} (需要≥2%)')
            self.stdout.write(f'    - 成交量维持: {vol_ratio:.2f}x (需要≥0.8x)')
            self.stdout.write(f'    - 实体压缩: {body_ratio:.2%} (需要<25%)')

        # 检测金针探底
        golden_needle = engine._detect_golden_needle(klines, params)
        self.stdout.write(f'  VPA模式2 - 金针探底: {"✓ 触发" if golden_needle else "✗ 未触发"}')
        if not golden_needle and len(klines) >= 50:
            curr_kline = klines[-1]
            vol_ma50 = engine._calculate_ma(klines, period=50, field='volume')
            if vol_ma50:
                vol_ratio = float(curr_kline['volume']) / vol_ma50
                body = abs(float(curr_kline['close']) - float(curr_kline['open']))
                lower_shadow = min(float(curr_kline['open']), float(curr_kline['close'])) - float(curr_kline['low'])
                shadow_ratio = lower_shadow / body if body > 0 else 0
                price_range = float(curr_kline['high']) - float(curr_kline['low'])
                close_position = (float(curr_kline['close']) - float(curr_kline['low'])) / price_range if price_range > 0 else 0

                self.stdout.write(f'    - 放量倍数: {vol_ratio:.2f}x (需要>2.5x)')
                self.stdout.write(f'    - 下影线/实体: {shadow_ratio:.2f}x (需要>2.0x)')
                self.stdout.write(f'    - 收盘位置: {close_position:.2%} (需要>60%)')

        # 检测RSI超卖
        rsi_oversold, rsi_value, reason = engine._check_rsi_oversold(klines, params)
        self.stdout.write(f'  技术确认1 - RSI超卖: {"✓ 触发" if rsi_oversold else "✗ 未触发"}')
        if rsi_value is not None:
            self.stdout.write(f'    - RSI值: {rsi_value:.1f} (需要<20)')

        # 检测布林带回升
        bb_reversion = engine._check_bb_reversion(klines, params)
        self.stdout.write(f'  技术确认2 - 布林带回升: {"✓ 触发" if bb_reversion else "✗ 未触发"}')
        if not bb_reversion and len(klines) >= 20:
            ma, upper, lower = engine._calculate_bollinger_bands(klines, period=20, std_dev=2.0)
            if ma and lower:
                curr_low = float(klines[-1]['low'])
                curr_close = float(klines[-1]['close'])
                self.stdout.write(f'    - 最低价: ${curr_low:.4f}, BB下轨: ${lower:.4f}')
                self.stdout.write(f'    - 收盘价: ${curr_close:.4f}, BB下轨: ${lower:.4f}')
                self.stdout.write(f'    - 需要: Low < BB_Lower AND Close > BB_Lower')

        # 判断是否会触发
        vpa_ok = stopping_volume or golden_needle
        tech_ok = rsi_oversold or bb_reversion
        self.stdout.write('')
        if vpa_ok and tech_ok:
            self.stdout.write('  ✅ 规则6会触发!')
        else:
            self.stdout.write(f'  ❌ 规则6不会触发 (VPA={vpa_ok}, 技术确认={tech_ok})')

    def _analyze_rule_7(self, engine, klines, symbol):
        """分析规则7的各项条件"""
        params = {
            'surge_threshold': 0.02,
            'vol_multiplier': 1.5,
            'upper_shadow_ratio': 0.1,
            'rsi_period': 14,
            'rsi_threshold': 60,
            'rsi_slope_threshold': 2.0,
            'bb_period': 20,
            'bb_std': 2.0
        }

        # 检测攻城锤
        battering_ram = engine._detect_battering_ram(klines, params)
        self.stdout.write(f'  VPA模式1 - 攻城锤: {"✓ 触发" if battering_ram else "✗ 未触发"}')
        if not battering_ram and len(klines) >= 50:
            curr_kline = klines[-1]
            surge_pct = (float(curr_kline['close']) - float(curr_kline['open'])) / float(curr_kline['open'])
            vol_ma50 = engine._calculate_ma(klines, period=50, field='volume')
            if vol_ma50:
                vol_ratio = float(curr_kline['volume']) / vol_ma50
                body = float(curr_kline['close']) - float(curr_kline['open'])
                upper_shadow = float(curr_kline['high']) - float(curr_kline['close'])
                shadow_ratio = upper_shadow / body if body > 0 else 0

                self.stdout.write(f'    - 涨幅: {surge_pct:.2%} (需要≥2%)')
                self.stdout.write(f'    - 放量倍数: {vol_ratio:.2f}x (需要≥1.5x)')
                self.stdout.write(f'    - 上影线/实体: {shadow_ratio:.2%} (需要<10%)')

        # 检测阳包阴
        bullish_engulfing = engine._detect_bullish_engulfing(klines, params)
        self.stdout.write(f'  VPA模式2 - 阳包阴: {"✓ 触发" if bullish_engulfing else "✗ 未触发"}')
        if not bullish_engulfing and len(klines) >= 20:
            prev_kline = klines[-2]
            curr_kline = klines[-1]
            prev_is_bearish = float(prev_kline['open']) > float(prev_kline['close'])
            curr_is_bullish = float(curr_kline['close']) > float(curr_kline['open'])
            engulfing = float(curr_kline['open']) < float(prev_kline['close']) and float(curr_kline['close']) > float(prev_kline['open'])
            vol_increase = float(curr_kline['volume']) > float(prev_kline['volume'])

            self.stdout.write(f'    - 前阴线: {"✓" if prev_is_bearish else "✗"}')
            self.stdout.write(f'    - 当前阳线: {"✓" if curr_is_bullish else "✗"}')
            self.stdout.write(f'    - 完全吞没: {"✓" if engulfing else "✗"}')
            self.stdout.write(f'    - 成交量增加: {"✓" if vol_increase else "✗"}')

        # 检测RSI超买加速
        rsi_acc, rsi_value, rsi_slope = engine._check_rsi_acceleration(klines, params)
        self.stdout.write(f'  技术确认1 - RSI超买加速: {"✓ 触发" if rsi_acc else "✗ 未触发"}')
        if rsi_value is not None:
            self.stdout.write(f'    - RSI值: {rsi_value:.1f} (需要>60)')
        if rsi_slope is not None:
            self.stdout.write(f'    - RSI斜率: {rsi_slope:.2f} (需要>2.0)')

        # 检测布林带突破扩张
        bb_breakout = engine._check_bb_breakout(klines, params)
        self.stdout.write(f'  技术确认2 - 布林带突破扩张: {"✓ 触发" if bb_breakout else "✗ 未触发"}')
        if not bb_breakout and len(klines) >= 21:
            ma, upper, lower = engine._calculate_bollinger_bands(klines, period=20, std_dev=2.0)
            if ma and upper:
                curr_close = float(klines[-1]['close'])
                bandwidth_curr = (upper - lower) / ma if ma > 0 else 0
                self.stdout.write(f'    - 收盘价: ${curr_close:.4f}, BB上轨: ${upper:.4f}')
                self.stdout.write(f'    - 带宽: {bandwidth_curr:.4f}')
                self.stdout.write(f'    - 需要: Close > BB_Upper AND 带宽扩张')

        # 判断是否会触发
        vpa_ok = battering_ram or bullish_engulfing
        tech_ok = rsi_acc or bb_breakout
        self.stdout.write('')
        if vpa_ok and tech_ok:
            self.stdout.write('  ✅ 规则7会触发!')
        else:
            self.stdout.write(f'  ❌ 规则7不会触发 (VPA={vpa_ok}, 技术确认={tech_ok})')
