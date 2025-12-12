"""下载CoinGecko完整代币列表到data目录

用途:
    下载CoinGecko的完整代币列表，保存为JSON文件供后续LLM匹配使用

使用方法:
    python manage.py download_coingecko_data
"""
import json
import logging
import os
from django.core.management.base import BaseCommand
from django.conf import settings

from grid_trading.services.coingecko_client import CoingeckoClient


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '下载CoinGecko完整代币列表到data/coingecko_coins.json'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='data/coingecko_coins.json',
            help='输出文件路径（默认: data/coingecko_coins.json）'
        )
        parser.add_argument(
            '--include-platform',
            action='store_true',
            help='是否包含平台信息（链上合约地址）'
        )

    def handle(self, *args, **options):
        output_path = options['output']
        include_platform = options['include_platform']

        # 确保data目录存在
        data_dir = os.path.dirname(output_path)
        if data_dir and not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            self.stdout.write(self.style.SUCCESS(f'✓ 创建目录: {data_dir}'))

        self.stdout.write('=' * 60)
        self.stdout.write('下载CoinGecko代币列表')
        self.stdout.write('=' * 60)

        try:
            # 初始化CoinGecko客户端
            client = CoingeckoClient()

            # 下载代币列表
            self.stdout.write(f'\n正在下载CoinGecko代币列表...')
            coins_list = client.fetch_coins_list(include_platform=include_platform)

            if not coins_list:
                self.stdout.write(self.style.ERROR('✗ 下载失败，返回空列表'))
                return

            self.stdout.write(self.style.SUCCESS(f'✓ 成功下载 {len(coins_list)} 个代币'))

            # 保存到JSON文件
            self.stdout.write(f'\n保存到文件: {output_path}')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(coins_list, f, ensure_ascii=False, indent=2)

            # 统计信息
            self.stdout.write('\n' + '=' * 60)
            self.stdout.write(self.style.SUCCESS('✓ 下载完成'))
            self.stdout.write('=' * 60)

            # 显示前5个示例
            self.stdout.write('\n前5个代币示例:')
            for i, coin in enumerate(coins_list[:5], 1):
                self.stdout.write(f'  {i}. {coin["symbol"].upper():8s} → {coin["id"]:20s} ({coin["name"]})')

            # 文件大小
            file_size = os.path.getsize(output_path)
            self.stdout.write(f'\n文件大小: {file_size / 1024 / 1024:.2f} MB')
            self.stdout.write(f'总代币数: {len(coins_list)}')
            self.stdout.write(f'输出路径: {os.path.abspath(output_path)}')

            # 字段说明
            self.stdout.write('\n字段说明:')
            self.stdout.write('  - id: CoinGecko ID (用于API查询)')
            self.stdout.write('  - symbol: 代币symbol (如btc, eth)')
            self.stdout.write('  - name: 代币全称 (如Bitcoin, Ethereum)')
            if include_platform:
                self.stdout.write('  - platforms: 各链上的合约地址')

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n✗ 下载失败: {str(e)}'))
            logger.exception('Failed to download CoinGecko data')
            raise
