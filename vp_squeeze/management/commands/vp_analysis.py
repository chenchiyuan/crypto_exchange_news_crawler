"""VP-Squeeze分析Django管理命令"""
import logging
import sys
from django.core.management.base import BaseCommand, CommandError

from vp_squeeze.constants import (
    SYMBOL_MAP,
    SYMBOL_GROUPS,
    VALID_INTERVALS,
    DEFAULT_KLINES,
    MIN_KLINES,
    MAX_KLINES,
)
from vp_squeeze.exceptions import (
    VPSqueezeError,
    InvalidSymbolError,
    InvalidIntervalError,
    InsufficientDataError,
    BinanceAPIError,
)
from vp_squeeze.services.vp_squeeze_analyzer import analyze, save_result
from vp_squeeze.services.output_formatter import (
    format_text_output,
    format_json_output,
    format_batch_text_output,
    format_batch_json_output,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'VP-Squeeze算法技术分析 - 计算支撑位和压力位'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            help=f'交易对（逗号分隔多个），支持: {", ".join(SYMBOL_MAP.keys())}'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            help=f'时间周期，支持: {", ".join(VALID_INTERVALS)}'
        )
        parser.add_argument(
            '--limit', '-l',
            type=int,
            default=DEFAULT_KLINES,
            help=f'K线数量 (默认: {DEFAULT_KLINES}, 范围: {MIN_KLINES}-{MAX_KLINES})'
        )
        parser.add_argument(
            '--group', '-g',
            type=str,
            choices=list(SYMBOL_GROUPS.keys()),
            help=f'预设组合，支持: {", ".join(SYMBOL_GROUPS.keys())}'
        )
        parser.add_argument(
            '--json', '-j',
            action='store_true',
            help='以JSON格式输出'
        )
        parser.add_argument(
            '--save',
            action='store_true',
            help='保存结果到数据库'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='显示详细日志'
        )

    def handle(self, *args, **options):
        symbol = options.get('symbol')
        interval = options['interval']
        limit = options['limit']
        group = options.get('group')
        output_json = options['json']
        save_to_db = options['save']
        verbose = options['verbose']

        # 配置日志
        if verbose:
            logging.getLogger('vp_squeeze').setLevel(logging.INFO)
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
            logging.getLogger('vp_squeeze').addHandler(handler)

        # 确定要分析的交易对列表
        symbols = self._get_symbols(symbol, group)

        if not symbols:
            raise CommandError('请指定 --symbol 或 --group 参数')

        # 执行分析
        results = []
        errors = []

        for sym in symbols:
            try:
                if verbose:
                    self.stderr.write(f"分析 {sym}...")

                result = analyze(sym, interval, limit, verbose=verbose)
                results.append(result)

                if save_to_db:
                    save_result(result)

            except InvalidSymbolError as e:
                errors.append(f"{sym}: {e}")
            except InvalidIntervalError as e:
                errors.append(f"{sym}: {e}")
            except InsufficientDataError as e:
                errors.append(f"{sym}: {e}")
            except BinanceAPIError as e:
                errors.append(f"{sym}: API错误 - {e}")
            except VPSqueezeError as e:
                errors.append(f"{sym}: {e}")

        # 输出结果
        if results:
            if len(results) == 1:
                # 单个结果
                if output_json:
                    self.stdout.write(format_json_output(results[0]))
                else:
                    self.stdout.write(format_text_output(results[0]))
            else:
                # 批量结果
                if output_json:
                    self.stdout.write(format_batch_json_output(results))
                else:
                    self.stdout.write(format_batch_text_output(results))

        # 输出错误
        if errors:
            self.stderr.write(self.style.ERROR("\n分析失败的交易对:"))
            for err in errors:
                self.stderr.write(self.style.ERROR(f"  • {err}"))

        # 汇总
        if len(symbols) > 1:
            success_count = len(results)
            fail_count = len(errors)
            self.stderr.write(f"\n完成: {success_count} 成功, {fail_count} 失败")

    def _get_symbols(self, symbol: str, group: str) -> list:
        """获取要分析的交易对列表"""
        symbols = []

        if group:
            symbols.extend(SYMBOL_GROUPS.get(group, []))

        if symbol:
            # 支持逗号分隔的多个symbol
            for s in symbol.split(','):
                s = s.strip()
                if s and s not in symbols:
                    symbols.append(s)

        return symbols
