"""两层箱体通道分析命令"""
import logging
import sys
from django.core.management.base import BaseCommand, CommandError

from vp_squeeze.constants import SYMBOL_MAP
from vp_squeeze.exceptions import VPSqueezeError
from vp_squeeze.services.dual_box_analyzer import analyze_dual_box
from vp_squeeze.services.dual_box_formatter import (
    format_dual_box_text,
    format_dual_box_json
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '两层箱体通道分析 - 基于多周期成交量共振'

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
            # 执行分析
            if verbose:
                self.stderr.write(f"分析 {symbol} [{', '.join(timeframes)}]...")

            result = analyze_dual_box(
                symbol=symbol,
                timeframes=timeframes,
                limit=limit,
                verbose=verbose
            )

            # 输出结果
            if output_json:
                self.stdout.write(format_dual_box_json(result))
            else:
                self.stdout.write(format_dual_box_text(result))

        except VPSqueezeError as e:
            raise CommandError(f"分析失败: {e}")
        except Exception as e:
            if verbose:
                import traceback
                traceback.print_exc()
            raise CommandError(f"未知错误: {e}")
