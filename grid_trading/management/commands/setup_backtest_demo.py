"""
setup_backtest_demo Django Management Command

用途: 创建MONUSDT回测示例配置和数据
"""

from django.core.management.base import BaseCommand, CommandError
from decimal import Decimal
from datetime import datetime, timedelta
import csv
import os
import random

from grid_trading.models import GridConfig


class Command(BaseCommand):
    """
    创建回测示例配置和数据

    示例:
        python manage.py setup_backtest_demo
        python manage.py setup_backtest_demo --days 7
    """

    help = "创建MONUSDT回测示例配置和模拟K线数据"

    def add_arguments(self, parser):
        """添加命令行参数"""
        parser.add_argument(
            "--days",
            type=int,
            default=3,
            help="生成K线数据的天数（默认3天）",
        )
        
        parser.add_argument(
            "--output-dir",
            type=str,
            default="backtest_data",
            help="输出目录（默认backtest_data）",
        )

    def handle(self, *args, **options):
        """命令主逻辑"""
        try:
            self.stdout.write(
                self.style.SUCCESS("=== 创建MONUSDT回测示例 ===")
            )
            
            # 1. 创建网格配置
            config = self.create_grid_config()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ 创建网格配置: {config.name} (ID: {config.id})"
                )
            )
            self.stdout.write(f"  交易对: {config.symbol}")
            self.stdout.write(f"  价格区间: {config.lower_price} - {config.upper_price}")
            self.stdout.write(f"  网格层数: {config.grid_levels}")
            self.stdout.write("")
            
            # 2. 生成模拟K线数据
            output_dir = options['output_dir']
            os.makedirs(output_dir, exist_ok=True)
            
            csv_path = os.path.join(output_dir, "MONUSDT_1m.csv")
            days = options['days']
            
            kline_count = self.generate_kline_csv(
                csv_path,
                days=days,
                base_price=Decimal('0.03'),
                price_range=(Decimal('0.01'), Decimal('0.05'))
            )
            
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ 生成K线数据: {csv_path}"
                )
            )
            self.stdout.write(f"  K线数量: {kline_count}")
            self.stdout.write(f"  时间跨度: {days}天")
            self.stdout.write("")
            
            # 3. 输出使用说明
            self.stdout.write(
                self.style.WARNING("【使用说明】")
            )
            self.stdout.write("运行回测命令：")
            self.stdout.write(
                f"  python manage.py backtest_grid --config-id {config.id} "
                f"--csv {csv_path}"
            )
            self.stdout.write("")
            self.stdout.write("查看更多选项：")
            self.stdout.write("  python manage.py backtest_grid --help")
            
        except Exception as e:
            raise CommandError(f"创建失败: {str(e)}")

    def create_grid_config(self) -> GridConfig:
        """创建MONUSDT网格配置"""
        # 检查是否已存在
        existing = GridConfig.objects.filter(name='MONUSDT_backtest_demo').first()
        if existing:
            self.stdout.write(
                self.style.WARNING(
                    f"配置 'MONUSDT_backtest_demo' 已存在 (ID: {existing.id})，将复用"
                )
            )
            return existing
        
        config = GridConfig.objects.create(
            name='MONUSDT_backtest_demo',
            exchange='binance',
            symbol='MONUSDT',
            grid_mode='SHORT',
            upper_price=Decimal('0.05'),
            lower_price=Decimal('0.01'),
            grid_levels=100,
            trade_amount=Decimal('100'),  # 每次交易100个MON
            max_position_size=Decimal('5000'),  # 最大持仓5000个MON
            price_tick=Decimal('0.00001'),  # 价格精度
            qty_step=Decimal('1'),  # 数量精度
            is_active=True
        )
        
        return config
    
    def generate_kline_csv(
        self,
        csv_path: str,
        days: int,
        base_price: Decimal,
        price_range: tuple
    ) -> int:
        """
        生成模拟K线数据CSV
        
        Args:
            csv_path: CSV文件路径
            days: 天数
            base_price: 基准价格
            price_range: 价格范围 (min, max)
            
        Returns:
            生成的K线数量
        """
        # 计算K线数量（1分钟周期）
        kline_count = days * 24 * 60
        
        # 生成K线
        klines = []
        current_time = datetime.now() - timedelta(days=days)
        current_price = base_price
        
        for i in range(kline_count):
            # 模拟价格波动（随机游走）
            # 价格变化 = 当前价格 * 随机百分比（-0.5% to +0.5%）
            price_change_pct = Decimal(str(random.uniform(-0.005, 0.005)))
            price_change = current_price * price_change_pct
            current_price = current_price + price_change
            
            # 限制在价格范围内
            if current_price < price_range[0]:
                current_price = price_range[0]
            elif current_price > price_range[1]:
                current_price = price_range[1]
            
            # 生成OHLC
            open_price = current_price
            
            # 模拟高低价（±0.2%）
            high_offset = Decimal(str(random.uniform(0, 0.002)))
            low_offset = Decimal(str(random.uniform(0, 0.002)))
            
            high = open_price * (Decimal('1') + high_offset)
            low = open_price * (Decimal('1') - low_offset)
            
            # 收盘价在high和low之间
            close_ratio = Decimal(str(random.uniform(0, 1)))
            close = low + (high - low) * close_ratio
            
            # 成交量（随机）
            volume = Decimal(str(random.uniform(10000, 50000)))
            
            # 更新当前价格为收盘价
            current_price = close
            
            # 添加K线
            klines.append({
                'timestamp': int(current_time.timestamp() * 1000),
                'open': f"{open_price:.6f}",
                'high': f"{high:.6f}",
                'low': f"{low:.6f}",
                'close': f"{close:.6f}",
                'volume': f"{volume:.2f}"
            })
            
            # 下一分钟
            current_time += timedelta(minutes=1)
        
        # 写入CSV
        with open(csv_path, 'w', newline='') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            writer.writeheader()
            writer.writerows(klines)
        
        return len(klines)
