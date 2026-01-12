"""
批量回测管理命令

按月批量执行策略回测，生成月度报告汇总。

功能特性:
    - 自动扫描指定目录下的CSV数据文件
    - 为每个月份生成临时配置并执行回测
    - 汇总所有月份的回测结果
    - 输出CSV格式的月度报告

使用示例:
    # 批量回测eth1m目录下的所有月份数据
    python manage.py batch_backtest --data-dir data/eth1m

    # 指定策略配置模板
    python manage.py batch_backtest --data-dir data/eth1m --template strategy_adapter/configs/strategy11_limit_order.json

    # 指定输出报告路径
    python manage.py batch_backtest --data-dir data/eth1m --output reports/monthly_report.csv

关联迭代: 027 (策略11-限价挂单买卖机制)
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '批量执行策略回测，按月生成报告'
    requires_system_checks = []  # 跳过系统检查，避免vectorbt模块缺失导致的问题

    def add_arguments(self, parser):
        parser.add_argument(
            '--data-dir',
            type=str,
            required=True,
            help='包含CSV数据文件的目录路径'
        )
        parser.add_argument(
            '--template',
            type=str,
            default='strategy_adapter/configs/strategy11_limit_order.json',
            help='策略配置模板文件路径（默认: strategy11_limit_order.json）'
        )
        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='输出报告文件路径（默认: 输出到终端）'
        )
        parser.add_argument(
            '--pattern',
            type=str,
            default=None,
            help='CSV文件名匹配模式（可选，默认扫描目录下所有.csv文件）'
        )

    def handle(self, *args, **options):
        data_dir = options['data_dir']
        template_path = options['template']
        output_path = options['output']
        pattern = options['pattern']

        # 验证目录存在
        if not os.path.isdir(data_dir):
            raise CommandError(f"目录不存在: {data_dir}")

        # 加载模板配置
        if not os.path.isfile(template_path):
            raise CommandError(f"模板配置文件不存在: {template_path}")

        with open(template_path, 'r', encoding='utf-8') as f:
            template_config = json.load(f)

        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*60}\n"
            f"批量回测系统\n"
            f"{'='*60}\n"
        ))
        self.stdout.write(f"数据目录: {data_dir}")
        self.stdout.write(f"配置模板: {template_path}")

        # 扫描CSV文件（pattern为可选参数）
        csv_files = self._scan_csv_files(data_dir, pattern)
        if not csv_files:
            raise CommandError(f"目录下未找到CSV文件: {data_dir}")

        self.stdout.write(f"发现 {len(csv_files)} 个数据文件\n")

        # 执行批量回测
        results = []
        for idx, (month, csv_path) in enumerate(sorted(csv_files.items()), 1):
            self.stdout.write(self.style.HTTP_INFO(
                f"\n[{idx}/{len(csv_files)}] 回测 {month}..."
            ))
            try:
                result = self._run_backtest(month, csv_path, template_config)
                results.append(result)
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ 完成: 订单={result['total_orders']}, "
                    f"胜率={result['win_rate']:.2f}%, "
                    f"收益率={result['return_rate']:.2f}%"
                ))
            except Exception as e:
                logger.exception(f"回测 {month} 失败")
                self.stdout.write(self.style.ERROR(f"  ✗ 失败: {e}"))
                results.append({
                    'month': month,
                    'status': 'failed',
                    'error': str(e)
                })

        # 生成报告
        self._generate_report(results, output_path)

    def _scan_csv_files(self, data_dir: str, pattern: str = None) -> dict:
        """
        扫描目录下的CSV文件

        Args:
            data_dir: 数据目录路径
            pattern: 可选的正则匹配模式，如果不指定则扫描所有.csv文件

        Returns:
            dict: {标识符: 文件路径} 的字典，按标识符排序
        """
        csv_files = {}

        for filename in os.listdir(data_dir):
            if not filename.endswith('.csv'):
                continue

            filepath = os.path.join(data_dir, filename)

            # 如果指定了pattern，使用正则匹配
            if pattern:
                regex = re.compile(pattern)
                match = regex.match(filename)
                if match:
                    identifier = match.group(1) if match.groups() else filename
                    csv_files[identifier] = filepath
            else:
                # 智能提取标识符：尝试从文件名提取YYYY-MM格式
                identifier = self._extract_identifier(filename)
                csv_files[identifier] = filepath

        return csv_files

    def _extract_identifier(self, filename: str) -> str:
        """
        从文件名智能提取标识符

        支持的格式：
        - ETHUSDT-1m-2025-01.csv -> 2025-01
        - BTCUSDT-4h-2024-12.csv -> 2024-12
        - 2025-01-data.csv -> 2025-01
        - data_202501.csv -> 2025-01
        - 其他格式 -> 使用文件名（不含扩展名）

        Args:
            filename: 文件名

        Returns:
            str: 提取的标识符
        """
        # 尝试匹配 YYYY-MM 格式
        match = re.search(r'(\d{4}-\d{2})', filename)
        if match:
            return match.group(1)

        # 尝试匹配 YYYYMM 格式
        match = re.search(r'(\d{4})(\d{2})', filename)
        if match:
            return f"{match.group(1)}-{match.group(2)}"

        # 无法提取，返回文件名（不含扩展名）
        return os.path.splitext(filename)[0]

    def _run_backtest(self, month: str, csv_path: str, template_config: dict) -> dict:
        """执行单月回测"""
        # 复制模板配置并修改CSV路径
        config = json.loads(json.dumps(template_config))  # 深拷贝
        config['project_name'] = f"策略11-限价挂单回测-{month}"
        config['data_source']['csv_path'] = csv_path

        # 创建临时配置文件
        with tempfile.NamedTemporaryFile(
            mode='w',
            suffix='.json',
            delete=False,
            encoding='utf-8'
        ) as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
            temp_config_path = f.name

        try:
            # 调用回测命令并捕获输出
            from io import StringIO
            from django.core.management import call_command

            out = StringIO()
            call_command('run_strategy_backtest', config=temp_config_path, stdout=out)
            output = out.getvalue()

            # 解析回测结果
            result = self._parse_backtest_output(output, month)
            return result

        finally:
            # 清理临时文件
            if os.path.exists(temp_config_path):
                os.unlink(temp_config_path)

    def _parse_backtest_output(self, output: str, month: str) -> dict:
        """解析回测输出"""
        result = {
            'month': month,
            'status': 'success',
            'total_orders': 0,
            'closed_orders': 0,
            'holding_orders': 0,
            'net_profit': 0.0,
            'win_rate': 0.0,
            'return_rate': 0.0,
            'total_volume': 0.0,
            'total_commission': 0.0,
            # 新增：资金统计
            'available_capital': 0.0,
            'frozen_capital': 0.0,
            'holding_value': 0.0,
            'total_equity': 0.0,
            'holding_unrealized_pnl': 0.0,
        }

        # 解析总订单数
        match = re.search(r'总订单数:\s*(\d+)', output)
        if match:
            result['total_orders'] = int(match.group(1))

        # 解析已平仓
        match = re.search(r'已平仓:\s*(\d+)', output)
        if match:
            result['closed_orders'] = int(match.group(1))

        # 解析持仓中
        match = re.search(r'持仓中:\s*(\d+)', output)
        if match:
            result['holding_orders'] = int(match.group(1))

        # 解析净利润（支持+/-符号）
        match = re.search(r'净利润:\s*([+-]?[\d.]+)\s*USDT', output)
        if match:
            result['net_profit'] = float(match.group(1))

        # 解析胜率
        match = re.search(r'胜率:\s*([\d.]+)%', output)
        if match:
            result['win_rate'] = float(match.group(1))

        # 解析收益率（支持+/-符号）
        match = re.search(r'收益率:\s*([+-]?[\d.]+)%', output)
        if match:
            result['return_rate'] = float(match.group(1))

        # 解析总交易量
        match = re.search(r'总交易量:\s*([\d.]+)\s*USDT', output)
        if match:
            result['total_volume'] = float(match.group(1))

        # 解析总手续费
        match = re.search(r'总手续费:\s*([\d.]+)\s*USDT', output)
        if match:
            result['total_commission'] = float(match.group(1))

        # 新增：解析资金统计
        match = re.search(r'可用现金:\s*([\d.]+)\s*USDT', output)
        if match:
            result['available_capital'] = float(match.group(1))

        match = re.search(r'挂单冻结:\s*([\d.]+)\s*USDT', output)
        if match:
            result['frozen_capital'] = float(match.group(1))

        match = re.search(r'持仓市值:\s*([\d.]+)\s*USDT', output)
        if match:
            result['holding_value'] = float(match.group(1))

        match = re.search(r'总资产:\s*([\d.]+)\s*USDT', output)
        if match:
            result['total_equity'] = float(match.group(1))

        match = re.search(r'持仓浮盈浮亏:\s*([+-]?[\d.]+)\s*USDT', output)
        if match:
            result['holding_unrealized_pnl'] = float(match.group(1))

        return result

    def _generate_report(self, results: list, output_path: str = None):
        """生成汇总报告"""
        self.stdout.write(self.style.SUCCESS(
            f"\n{'='*160}\n"
            f"月度回测报告汇总\n"
            f"{'='*160}\n"
        ))

        # 表头（使用固定宽度，避免中文对齐问题）
        header = (
            f"{'Month':<10} {'Orders':>8} {'Closed':>8} {'WinRate%':>10} "
            f"{'NetProfit':>12} {'Return%':>10} {'Volume':>14} {'Commission':>12} {'Available':>12} {'Equity':>12} {'Status':<8}"
        )
        separator = "-" * 160

        self.stdout.write(header)
        self.stdout.write(separator)

        # 统计汇总
        total_orders = 0
        total_closed = 0
        total_profit = 0.0
        total_volume = 0.0
        total_commission = 0.0
        success_count = 0
        win_rates = []

        for r in results:
            if r.get('status') == 'success':
                line = (
                    f"{r['month']:<10} "
                    f"{r['total_orders']:>8} "
                    f"{r['closed_orders']:>8} "
                    f"{r['win_rate']:>10.2f} "
                    f"{r['net_profit']:>12.2f} "
                    f"{r['return_rate']:>10.2f} "
                    f"{r['total_volume']:>14.2f} "
                    f"{r['total_commission']:>12.2f} "
                    f"{r['available_capital']:>12.2f} "
                    f"{r['total_equity']:>12.2f} "
                    f"{'OK':<8}"
                )
                total_orders += r['total_orders']
                total_closed += r['closed_orders']
                total_profit += r['net_profit']
                total_volume += r['total_volume']
                total_commission += r['total_commission']
                win_rates.append(r['win_rate'])
                success_count += 1
            else:
                line = (
                    f"{r['month']:<10} "
                    f"{'-':>8} "
                    f"{'-':>8} "
                    f"{'-':>10} "
                    f"{'-':>12} "
                    f"{'-':>10} "
                    f"{'-':>14} "
                    f"{'-':>12} "
                    f"{'-':>12} "
                    f"{'-':>12} "
                    f"{'FAIL':<8}"
                )
            self.stdout.write(line)

        self.stdout.write(separator)

        # 汇总行
        avg_win_rate = sum(win_rates) / len(win_rates) if win_rates else 0
        avg_return = total_profit / 10000 * 100 if total_orders > 0 else 0  # 基于10000初始资金
        summary = (
            f"{'TOTAL':<10} "
            f"{total_orders:>8} "
            f"{total_closed:>8} "
            f"{avg_win_rate:>10.2f} "
            f"{total_profit:>12.2f} "
            f"{avg_return:>10.2f} "
            f"{total_volume:>14.2f} "
            f"{total_commission:>12.2f} "
            f"{'-':>12} "
            f"{'-':>12} "
            f"{f'{success_count}/{len(results)}':<8}"
        )
        self.stdout.write(self.style.WARNING(summary))

        # 输出到CSV文件
        if output_path:
            self._save_csv_report(results, output_path, total_orders, total_profit, avg_win_rate, total_volume, total_commission)
            self.stdout.write(self.style.SUCCESS(f"\n报告已保存到: {output_path}"))

    def _save_csv_report(self, results: list, output_path: str, total_orders: int, total_profit: float, avg_win_rate: float, total_volume: float, total_commission: float):
        """保存CSV格式报告"""
        # 确保目录存在
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入表头
            f.write("月份,订单数,已平仓,持仓中,胜率%,净利润,收益率%,可用现金,挂单冻结,持仓市值,总资产,持仓浮盈浮亏,交易量,手续费,状态\n")

            # 写入每月数据
            for r in results:
                if r.get('status') == 'success':
                    f.write(
                        f"{r['month']},"
                        f"{r['total_orders']},"
                        f"{r['closed_orders']},"
                        f"{r['holding_orders']},"
                        f"{r['win_rate']:.2f},"
                        f"{r['net_profit']:.2f},"
                        f"{r['return_rate']:.2f},"
                        f"{r['available_capital']:.2f},"
                        f"{r.get('frozen_capital', 0):.2f},"
                        f"{r['holding_value']:.2f},"
                        f"{r['total_equity']:.2f},"
                        f"{r['holding_unrealized_pnl']:.2f},"
                        f"{r['total_volume']:.2f},"
                        f"{r['total_commission']:.2f},"
                        f"成功\n"
                    )
                else:
                    f.write(f"{r['month']},-,-,-,-,-,-,-,-,-,-,-,-,-,失败\n")

            # 写入汇总行
            f.write(f"\n汇总,{total_orders},-,-,{avg_win_rate:.2f},{total_profit:.2f},-,-,-,-,-,-,{total_volume:.2f},{total_commission:.2f},-\n")
