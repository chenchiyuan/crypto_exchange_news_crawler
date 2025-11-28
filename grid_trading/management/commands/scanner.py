"""
网格交易Scanner命令 - 识别支撑/压力区间
Grid Trading Scanner Command - Identify Support/Resistance Zones

功能:
1. 调用VP-Squeeze分析器识别S1/S2/R1/R2
2. 写入GridZone表
3. 设置4小时过期时间
"""
import logging
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from grid_trading.models import GridZone
from grid_trading.services.config_loader import load_config
from vp_squeeze.services.multi_timeframe_analyzer import analyze_multi_timeframe
from vp_squeeze.services.four_peaks_analyzer import analyze_four_peaks
from vp_squeeze.exceptions import VPSqueezeError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '扫描支撑/压力区间 - 基于VP-Squeeze分析'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对，如: btc 或 BTCUSDT'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细日志'
        )

    def handle(self, *args, **options):
        symbol_input = options['symbol']
        verbose = options['verbose']

        # 配置日志
        if verbose:
            logging.getLogger('grid_trading').setLevel(logging.INFO)
            logging.getLogger('vp_squeeze').setLevel(logging.INFO)

        try:
            # 1. 加载配置
            config = load_config(symbol_input)
            symbol_full = config['symbol']  # BTCUSDT
            scanner_interval_hours = config.get('scanner_interval_hours', 4)

            self.stdout.write(f"[Scanner] 开始扫描 {symbol_full}...")

            # 2. 执行VP-Squeeze多周期分析
            timeframes = ['15m', '1h', '4h']
            analyses, _ = analyze_multi_timeframe(
                symbol=symbol_input,
                timeframes=timeframes,
                limit=100,
                verbose=verbose
            )

            # 3. 执行4峰值分析
            result = analyze_four_peaks(
                analyses=analyses,
                symbol=symbol_full,
                verbose=verbose
            )

            # 4. 计算过期时间
            expires_at = timezone.now() + timedelta(hours=scanner_interval_hours)

            # 5. 停用旧的区间（相同symbol）
            old_zones_count = GridZone.objects.filter(
                symbol=symbol_full,
                is_active=True
            ).update(is_active=False)

            if old_zones_count > 0:
                self.stdout.write(f"[Scanner] 停用旧区间: {old_zones_count}条")

            # 6. 创建4个新区间
            zones_created = []

            # S2 - 支撑位2 (大箱体下界)
            s2_zone = GridZone.objects.create(
                symbol=symbol_full,
                zone_type='support',
                price_low=result.support2.price * 0.998,  # 扩展0.2%作为区间
                price_high=result.support2.price * 1.002,
                confidence=result.support2.confidence,
                expires_at=expires_at,
                is_active=True
            )
            zones_created.append(('S2', s2_zone))

            # S1 - 支撑位1 (小箱体下界)
            s1_zone = GridZone.objects.create(
                symbol=symbol_full,
                zone_type='support',
                price_low=result.support1.price * 0.998,
                price_high=result.support1.price * 1.002,
                confidence=result.support1.confidence,
                expires_at=expires_at,
                is_active=True
            )
            zones_created.append(('S1', s1_zone))

            # R1 - 压力位1 (小箱体上界)
            r1_zone = GridZone.objects.create(
                symbol=symbol_full,
                zone_type='resistance',
                price_low=result.resistance1.price * 0.998,
                price_high=result.resistance1.price * 1.002,
                confidence=result.resistance1.confidence,
                expires_at=expires_at,
                is_active=True
            )
            zones_created.append(('R1', r1_zone))

            # R2 - 压力位2 (大箱体上界)
            r2_zone = GridZone.objects.create(
                symbol=symbol_full,
                zone_type='resistance',
                price_low=result.resistance2.price * 0.998,
                price_high=result.resistance2.price * 1.002,
                confidence=result.resistance2.confidence,
                expires_at=expires_at,
                is_active=True
            )
            zones_created.append(('R2', r2_zone))

            # 7. 输出结果
            self.stdout.write(self.style.SUCCESS(f"\n✅ Scanner完成 - {symbol_full}"))
            self.stdout.write(f"当前价格: ${result.current_price:.2f}")
            self.stdout.write(f"过期时间: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
            self.stdout.write("\n识别的S/R区间:")

            for label, zone in zones_created:
                zone_type_display = '🔻支撑' if zone.zone_type == 'support' else '🔺压力'
                self.stdout.write(
                    f"  {zone_type_display} {label}: "
                    f"${zone.price_low:.2f} - ${zone.price_high:.2f} "
                    f"(置信度: {zone.confidence}分)"
                )

            self.stdout.write(f"\n总计创建: {len(zones_created)}个区间")

        except VPSqueezeError as e:
            raise CommandError(f"VP-Squeeze分析失败: {e}")
        except ValueError as e:
            raise CommandError(f"配置错误: {e}")
        except Exception as e:
            logger.exception("Scanner执行异常")
            raise CommandError(f"Scanner失败: {e}")
