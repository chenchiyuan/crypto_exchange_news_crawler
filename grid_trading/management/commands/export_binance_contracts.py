"""导出币安USDT永续合约列表到data目录

用途:
    导出币安的USDT永续合约列表，保存为JSON文件供后续LLM匹配使用

使用方法:
    python manage.py export_binance_contracts
"""
import json
import logging
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from grid_trading.services.mapping_service import MappingService


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '导出币安USDT永续合约列表到data/binance_contracts.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='data/binance_contracts.json',
            help='输出文件路径（默认: data/binance_contracts.json）'
        )

    def handle(self, *args, **options):
        output_path = options['output']

        # 确保data目录存在
        data_dir = os.path.dirname(output_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            self.stdout.write(self.style.SUCCESS(f'✓ 创建目录: {data_dir}'))

        self.stdout.write('=' * 60)
        self.stdout.write('导出币安USDT永续合约列表')
        self.stdout.write('=' * 60)

        try:
            # 初始化映射服务
            service = MappingService()

            # 获取币安合约列表
            self.stdout.write(f'\n正在获取币安USDT永续合约列表...')
            contracts = service.get_binance_usdt_perpetuals()

            if not contracts:
                self.stdout.write(self.style.ERROR('✗ 获取失败，返回空列表'))
                return

            self.stdout.write(self.style.SUCCESS(f'✓ 成功获取 {len(contracts)} 个合约'))

            # 保存到JSON文件
            self.stdout.write(f'\n保存到文件: {output_path}')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(contracts, f, ensure_ascii=False, indent=2)

            # 统计信息
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('✓ 导出完成'))
            self.stdout.write('=' * 60)

            # 显示前5个示例
            self.stdout.write('\n前5个合约示例:')
            for i, contract in enumerate(contracts[:5], 1):
                self.stdout.write(
                    f'  {i}. {contract["symbol"]:12s} '
                    f'(base: {contract["base_asset"]:6s}, '
                    f'quote: {contract["quote_asset"]}, '
                    f'status: {contract["status"]})'
                )

            # 文件大小
            file_size = os.path.getsize(output_path)
            self.stdout.write(f'\n文件大小: {file_size / 1024:.2f} KB')
            self.stdout.write(f'总合约数: {len(contracts)}')
            self.stdout.write(f'输出路径: {os.path.abspath(output_path)}')

            # 字段说明
            self.stdout.write('\n字段说明:')
            self.stdout.write('  - symbol: 合约symbol (如BTCUSDT)')
            self.stdout.write('  - base_asset: 基础资产 (如BTC)')
            self.stdout.write('  - quote_asset: 计价资产 (固定为USDT)')
            self.stdout.write('  - status: 合约状态 (TRADING)')

            # 按base_asset首字母统计
            self.stdout.write('\n按首字母统计:')
            letter_counts = {}
            for contract in contracts:
                first_letter = contract['base_asset'][0].upper()
                letter_counts[first_letter] = letter_counts.get(first_letter, 0) + 1

            for letter in sorted(letter_counts.keys()):
                count = letter_counts[letter]
                self.stdout.write(f'  {letter}: {count:3d} 个合约')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ 导出失败: {str(e)}'))
            logger.exception('Failed to export Binance contracts')
            raise
