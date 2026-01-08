"""
DDPS价格监控主命令
DDPS Price Monitor Main Command

整合K线数据更新、指标计算、信号检测和消息推送的主控命令。

功能特性:
    - --full: 完整流程（更新数据 + 计算 + 推送）
    - --skip-update: 跳过数据更新，仅计算和推送
    - --no-push: 跳过推送，仅更新和计算
    - --symbols: 指定交易对列表
    - --dry-run: 试运行，显示结果但不推送

使用示例:
    # 完整流程
    python manage.py ddps_monitor --full

    # 跳过数据更新
    python manage.py ddps_monitor --skip-update

    # 仅更新和计算，不推送
    python manage.py ddps_monitor --full --no-push

    # 试运行
    python manage.py ddps_monitor --full --dry-run

    # 指定交易对
    python manage.py ddps_monitor --full --symbols ETHUSDT,BTCUSDT

Related:
    - PRD: docs/iterations/023-ddps-price-monitor/prd.md
    - Task: TASK-023-010~011
"""

import logging
import requests
from datetime import datetime
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from ddps_z.services import DDPSMonitorService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'DDPS价格监控服务：更新数据、计算指标、检测信号并推送'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='执行完整流程：更新数据 + 计算指标 + 推送信号'
        )
        parser.add_argument(
            '--skip-update',
            action='store_true',
            help='跳过K线数据更新，仅执行计算和推送'
        )
        parser.add_argument(
            '--no-push',
            action='store_true',
            help='跳过消息推送，仅执行更新和计算'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='试运行模式：显示结果但不实际推送'
        )
        parser.add_argument(
            '--symbols',
            type=str,
            required=False,
            help='交易对列表，逗号分隔（如ETHUSDT,BTCUSDT）'
        )
        parser.add_argument(
            '--interval',
            type=str,
            default=None,
            choices=['1h', '4h', '1d'],
            help='K线周期，默认使用配置'
        )

    def handle(self, *args, **options):
        """执行主流程"""
        start_time = datetime.now()

        self.stdout.write(
            self.style.MIGRATE_HEADING('\n=== DDPS价格监控服务 ===\n')
        )
        self.stdout.write(f'开始时间: {start_time.strftime("%Y-%m-%d %H:%M:%S")}')

        # 获取配置
        config = getattr(settings, 'DDPS_MONITOR_CONFIG', {})

        # 解析参数
        skip_update = options.get('skip_update', False)
        no_push = options.get('no_push', False)
        dry_run = options.get('dry_run', False)
        full_mode = options.get('full', False)

        # 解析交易对
        symbols_str = options.get('symbols')
        if symbols_str:
            symbols = [s.strip().upper() for s in symbols_str.split(',')]
        else:
            symbols = config.get('default_symbols', [])

        if not symbols:
            self.stdout.write(
                self.style.ERROR('错误：未配置交易对列表')
            )
            return

        interval = options.get('interval') or config.get('interval', '4h')

        self.stdout.write(f'交易对: {", ".join(symbols)}')
        self.stdout.write(f'周期: {interval}')
        self.stdout.write(f'模式: {"完整" if full_mode else "部分"}')
        if skip_update:
            self.stdout.write(self.style.WARNING('  - 跳过数据更新'))
        if no_push:
            self.stdout.write(self.style.WARNING('  - 跳过消息推送'))
        if dry_run:
            self.stdout.write(self.style.WARNING('  - 试运行模式'))
        self.stdout.write('')

        # 步骤1: 更新K线数据
        if not skip_update:
            self._step_update_klines(symbols, interval, config)
        else:
            self.stdout.write(self.style.WARNING('[跳过] K线数据更新\n'))

        # 步骤2: 计算指标和检测信号
        result = self._step_calculate_signals(symbols, interval, config)

        if result is None:
            self.stdout.write(
                self.style.ERROR('计算失败，终止流程')
            )
            return

        # 步骤3: 推送消息
        if not no_push and not dry_run:
            self._step_push_notification(result, config)
        elif dry_run:
            self._show_dry_run_result(result)
        else:
            self.stdout.write(self.style.WARNING('[跳过] 消息推送\n'))

        # 完成统计
        elapsed = (datetime.now() - start_time).total_seconds()
        self.stdout.write(
            self.style.SUCCESS(f'\n✓ 监控完成，耗时: {elapsed:.1f}秒')
        )

    def _step_update_klines(self, symbols: list, interval: str, config: dict):
        """步骤1: 更新K线数据"""
        self.stdout.write(
            self.style.MIGRATE_HEADING('[步骤1] 更新K线数据')
        )

        from django.core.management import call_command
        from io import StringIO

        # 捕获输出
        out = StringIO()

        try:
            call_command(
                'update_ddps_klines',
                symbols=','.join(symbols),
                interval=interval,
                stdout=out
            )
            self.stdout.write(self.style.SUCCESS('  ✓ K线数据更新完成'))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ✗ K线数据更新失败: {e}')
            )
            logger.error(f'K线数据更新失败: {e}', exc_info=True)

        self.stdout.write('')

    def _step_calculate_signals(self, symbols: list, interval: str, config: dict):
        """步骤2: 计算指标和检测信号"""
        self.stdout.write(
            self.style.MIGRATE_HEADING('[步骤2] 计算指标和检测信号')
        )

        try:
            # 创建监控服务
            service = DDPSMonitorService(
                symbols=symbols,
                interval=interval,
                market_type=config.get('market_type', 'futures')
            )

            # 执行计算
            result = service.calculate_all()

            # 显示统计
            self.stdout.write(f'  交易对数量: {len(symbols)}')
            self.stdout.write(f'  买入信号: {len(result.buy_signals)} 个')
            self.stdout.write(f'  卖出信号: {len(result.exit_signals)} 个')

            # 显示周期分布
            warnings = result.cycle_warnings
            self.stdout.write(f'  周期分布:')
            if warnings.bull_strong:
                self.stdout.write(
                    self.style.SUCCESS(f'    上涨强势: {", ".join(warnings.bull_strong)}')
                )
            if warnings.bull_warning:
                self.stdout.write(f'    上涨预警: {", ".join(warnings.bull_warning)}')
            if warnings.consolidation:
                self.stdout.write(f'    震荡期: {", ".join(warnings.consolidation)}')
            if warnings.bear_warning:
                self.stdout.write(
                    self.style.WARNING(f'    下跌预警: {", ".join(warnings.bear_warning)}')
                )
            if warnings.bear_strong:
                self.stdout.write(
                    self.style.ERROR(f'    下跌强势: {", ".join(warnings.bear_strong)}')
                )

            self.stdout.write(self.style.SUCCESS('  ✓ 指标计算完成'))
            self.stdout.write('')

            return result

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ✗ 指标计算失败: {e}')
            )
            logger.error(f'指标计算失败: {e}', exc_info=True)
            return None

    def _step_push_notification(self, result, config: dict):
        """步骤3: 推送消息"""
        self.stdout.write(
            self.style.MIGRATE_HEADING('[步骤3] 推送消息')
        )

        try:
            # 创建监控服务实例以获取格式化消息
            service = DDPSMonitorService(
                symbols=config.get('default_symbols', []),
                interval=config.get('interval', '4h'),
                market_type=config.get('market_type', 'futures')
            )

            # 格式化消息
            title, content = service.format_push_message(result)

            # 发送推送
            success = self._send_push(
                title=title,
                content=content,
                channel=config.get('push_channel', 'price_ddps'),
                token=config.get('push_token', '6020867bc6334c609d4f348c22f90f14')
            )

            if success:
                self.stdout.write(self.style.SUCCESS('  ✓ 消息推送成功'))
            else:
                self.stdout.write(self.style.ERROR('  ✗ 消息推送失败'))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'  ✗ 推送失败: {e}')
            )
            logger.error(f'消息推送失败: {e}', exc_info=True)

        self.stdout.write('')

    def _send_push(
        self,
        title: str,
        content: str,
        channel: str,
        token: str
    ) -> bool:
        """
        发送推送消息到慧诚平台

        Args:
            title: 消息标题
            content: 消息内容
            channel: 推送渠道
            token: 认证令牌

        Returns:
            bool: 是否成功
        """
        api_url = "https://huicheng.powerby.com.cn/api/simple/alert/"

        payload = {
            "token": token,
            "title": title,
            "content": content,
            "channel": channel
        }

        try:
            response = requests.post(
                api_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )

            response_data = response.json()

            if response_data.get('errcode') == 0:
                logger.info(f'DDPS监控推送成功: {title}')
                return True
            else:
                error_msg = response_data.get('msg', '未知错误')
                logger.warning(f'DDPS监控推送失败: {error_msg}')
                return False

        except requests.exceptions.Timeout:
            logger.warning('DDPS监控推送超时')
            return False
        except requests.exceptions.RequestException as e:
            logger.warning(f'DDPS监控推送请求异常: {e}')
            return False
        except Exception as e:
            logger.error(f'DDPS监控推送异常: {e}', exc_info=True)
            return False

    def _show_dry_run_result(self, result):
        """显示试运行结果"""
        self.stdout.write(
            self.style.MIGRATE_HEADING('[试运行] 推送预览')
        )

        try:
            service = DDPSMonitorService(
                symbols=[],
                interval='4h',
                market_type='futures'
            )

            title, content = service.format_push_message(result)

            self.stdout.write('')
            self.stdout.write(self.style.WARNING('--- 推送标题 ---'))
            self.stdout.write(title)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('--- 推送内容 ---'))
            self.stdout.write(content)
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('--- 预览结束 ---'))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'格式化预览失败: {e}')
            )

        self.stdout.write('')
