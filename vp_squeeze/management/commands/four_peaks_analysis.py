"""4峰值箱体分析命令"""
import logging
import sys
import json
from django.core.management.base import BaseCommand, CommandError

from vp_squeeze.constants import SYMBOL_MAP
from vp_squeeze.exceptions import VPSqueezeError
from vp_squeeze.services.multi_timeframe_analyzer import analyze_multi_timeframe
from vp_squeeze.services.four_peaks_analyzer import analyze_four_peaks
from vp_squeeze.services.indicators.utils import format_price

logger = logging.getLogger(__name__)


def format_text_output(result) -> str:
    """格式化文本输出"""
    score_bar = "█" * (result.overall_score // 10) + "░" * (10 - result.overall_score // 10)

    lines = [
        "═" * 85,
        f"4峰值箱体通道分析: {result.symbol}",
        "═" * 85,
        "",
        "─" * 85,
        "📊 综合评分",
        "─" * 85,
        f"   总分: {result.overall_score}分 [{score_bar}]",
        f"   ├─ 成交量质量: {result.volume_quality}分",
        f"   └─ MA对齐度:   {result.ma_alignment}分",
        "",
        "─" * 85,
        "📍 4个关键点位（成交量峰值 + MA调整）",
        "─" * 85,
    ]

    # 压力位2
    r2 = result.resistance2
    lines.extend([
        f"",
        f"   🔺 压力位2 (大箱体上界): ${format_price(r2.price)}",
        f"      ├─ 原始峰值: ${format_price(r2.original_peak)}",
        f"      ├─ 成交量强度: {r2.volume_strength}分",
        f"      ├─ MA调整: {'是' if r2.ma_adjusted else '否'}{' → ' + r2.ma_type if r2.ma_type else ''}",
        f"      └─ 置信度: {r2.confidence}分",
        "",
    ])

    # 压力位1
    r1 = result.resistance1
    lines.extend([
        f"   🔸 压力位1 (小箱体上界): ${format_price(r1.price)}",
        f"      ├─ 原始峰值: ${format_price(r1.original_peak)}",
        f"      ├─ 成交量强度: {r1.volume_strength}分",
        f"      ├─ MA调整: {'是' if r1.ma_adjusted else '否'}{' → ' + r1.ma_type if r1.ma_type else ''}",
        f"      └─ 置信度: {r1.confidence}分",
        "",
    ])

    # 当前价格
    lines.append(f"   ⚪ 当前价格: ${format_price(result.current_price)} [{result.position_in_box}]")
    lines.append("")

    # 支撑位1
    s1 = result.support1
    lines.extend([
        f"   🔹 支撑位1 (小箱体下界): ${format_price(s1.price)}",
        f"      ├─ 原始峰值: ${format_price(s1.original_peak)}",
        f"      ├─ 成交量强度: {s1.volume_strength}分",
        f"      ├─ MA调整: {'是' if s1.ma_adjusted else '否'}{' → ' + s1.ma_type if s1.ma_type else ''}",
        f"      └─ 置信度: {s1.confidence}分",
        "",
    ])

    # 支撑位2
    s2 = result.support2
    lines.extend([
        f"   🔻 支撑位2 (大箱体下界): ${format_price(s2.price)}",
        f"      ├─ 原始峰值: ${format_price(s2.original_peak)}",
        f"      ├─ 成交量强度: {s2.volume_strength}分",
        f"      ├─ MA调整: {'是' if s2.ma_adjusted else '否'}{' → ' + s2.ma_type if s2.ma_type else ''}",
        f"      └─ 置信度: {s2.confidence}分",
        "",
    ])

    # 箱体定义
    lines.extend([
        "─" * 85,
        "📦 箱体定义",
        "─" * 85,
        f"   小箱体（精确入场）:",
        f"      支撑: ${format_price(result.small_box['support'])}",
        f"      压力: ${format_price(result.small_box['resistance'])}",
        f"      中点: ${format_price(result.small_box['midpoint'])}",
        f"      宽度: {result.small_box['width_pct']:.2f}%",
        "",
        f"   大箱体（趋势级别）:",
        f"      支撑: ${format_price(result.large_box['support'])}",
        f"      压力: ${format_price(result.large_box['resistance'])}",
        f"      中点: ${format_price(result.large_box['midpoint'])}",
        f"      宽度: {result.large_box['width_pct']:.2f}%",
        "",
    ])

    lines.append("═" * 85)

    return "\n".join(lines)


def format_json_output(result) -> str:
    """格式化JSON输出"""
    data = {
        "symbol": result.symbol,
        "current_price": result.current_price,
        "position": result.position_in_box,
        "key_levels": {
            "support2": {
                "price": result.support2.price,
                "original_peak": result.support2.original_peak,
                "volume_strength": result.support2.volume_strength,
                "ma_adjusted": result.support2.ma_adjusted,
                "ma_type": result.support2.ma_type,
                "confidence": result.support2.confidence
            },
            "support1": {
                "price": result.support1.price,
                "original_peak": result.support1.original_peak,
                "volume_strength": result.support1.volume_strength,
                "ma_adjusted": result.support1.ma_adjusted,
                "ma_type": result.support1.ma_type,
                "confidence": result.support1.confidence
            },
            "resistance1": {
                "price": result.resistance1.price,
                "original_peak": result.resistance1.original_peak,
                "volume_strength": result.resistance1.volume_strength,
                "ma_adjusted": result.resistance1.ma_adjusted,
                "ma_type": result.resistance1.ma_type,
                "confidence": result.resistance1.confidence
            },
            "resistance2": {
                "price": result.resistance2.price,
                "original_peak": result.resistance2.original_peak,
                "volume_strength": result.resistance2.volume_strength,
                "ma_adjusted": result.resistance2.ma_adjusted,
                "ma_type": result.resistance2.ma_type,
                "confidence": result.resistance2.confidence
            }
        },
        "boxes": {
            "small": result.small_box,
            "large": result.large_box
        },
        "scores": {
            "overall": result.overall_score,
            "volume_quality": result.volume_quality,
            "ma_alignment": result.ma_alignment
        }
    }

    return json.dumps(data, indent=2, ensure_ascii=False)


class Command(BaseCommand):
    help = '4峰值箱体通道分析 - 成交量峰值 + MA均线调整'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help=f'交易对，支持: {", ".join(SYMBOL_MAP.keys())}'
        )
        parser.add_argument(
            '--timeframes', '-t',
            type=str,
            default='15m,1h,4h',
            help='时间周期（逗号分隔），默认: 15m,1h,4h'
        )
        parser.add_argument(
            '--limit', '-l',
            type=int,
            default=100,
            help='K线数量，默认100'
        )
        parser.add_argument(
            '--json', '-j',
            action='store_true',
            help='以JSON格式输出'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细日志'
        )

    def handle(self, *args, **options):
        symbol = options['symbol']
        timeframes_str = options['timeframes']
        limit = options['limit']
        output_json = options['json']
        verbose = options['verbose']

        # 配置日志
        if verbose:
            logging.getLogger('vp_squeeze').setLevel(logging.INFO)
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            logging.getLogger('vp_squeeze').addHandler(handler)

        # 解析时间周期
        timeframes = [tf.strip() for tf in timeframes_str.split(',')]

        try:
            # 1. 多周期分析
            if verbose:
                self.stderr.write(f"分析 {symbol} [{', '.join(timeframes)}]...")

            analyses, _ = analyze_multi_timeframe(
                symbol=symbol,
                timeframes=timeframes,
                limit=limit,
                verbose=verbose
            )

            # 2. 4峰值分析
            result = analyze_four_peaks(
                analyses=analyses,
                symbol=symbol,
                verbose=verbose
            )

            # 3. 输出结果
            if output_json:
                self.stdout.write(format_json_output(result))
            else:
                self.stdout.write(format_text_output(result))

        except VPSqueezeError as e:
            raise CommandError(f"分析失败: {e}")
        except Exception as e:
            if verbose:
                import traceback
                traceback.print_exc()
            raise CommandError(f"未知错误: {e}")
