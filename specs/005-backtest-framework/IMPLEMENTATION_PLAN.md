# Implementation Plan: 回测框架与历史数据系统

**Branch**: `005-backtest-framework`
**Date**: 2025-11-28
**Spec**: [solution-proposal.md](./solution-proposal.md)
**Status**: Approved ✅

---

## Summary

基于vectorbt实现专业的网格策略回测系统，支持历史K线数据持久化、多币种多周期扩展、回测结果分析。

**核心特性**:
- ✅ 支持多币种（BTC/ETH/SOL等）
- ✅ 支持多时间周期（1h/4h/1d）
- ✅ 使用vectorbt专业回测框架
- ✅ 历史数据持久化（PostgreSQL）
- ✅ 回测结果可视化和报告
- ✅ 参数优化支持

**测试数据**: 币安ETH 4小时真实数据（6个月）

---

## Technical Context

**Language/Version**: Python 3.8+
**Primary Dependencies**:
- Django 4.2.8
- vectorbt 0.26+ (新增)
- pandas 2.0+ (新增)
- numpy 1.24+ (新增)
- matplotlib 3.7+ (新增，可视化)

**Storage**: PostgreSQL 14+ (生产) / SQLite (开发)
**Testing**: pytest
**Target Platform**: Linux server / macOS
**Project Type**: Django应用（新增backtest模块）

**Performance Goals**:
- 数据获取: 6个月数据 < 30秒
- 数据查询: 单次查询 < 100ms
- 回测执行: 6个月数据回测 < 10秒
- 数据库写入: 1000条K线 < 1秒

**Constraints**:
- 币安API限制：1200请求/分钟
- 初期测试使用ETH 4h数据
- 架构必须支持多币种多周期扩展

**Scale/Scope**:
- 单币种6个月4h数据：约1080条K线
- 数据库存储：单币种单周期 < 10MB
- 支持3-5个币种并发回测

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 核心原则验证

| 原则 | 验证 | 说明 |
|------|------|------|
| **简单至上** | ✅ PASS | 复用Django框架，使用成熟的vectorbt库 |
| **借鉴现有代码** | ✅ PASS | 复用binance_kline_service、KLineData DTO |
| **小步提交** | ✅ PASS | 4个阶段，每阶段独立可测试 |
| **务实主义** | ✅ PASS | 使用vectorbt而非自己实现回测引擎 |
| **模块化与状态隔离** | ✅ PASS | backtest独立应用，不影响grid_trading |
| **参数可追溯** | ✅ PASS | BacktestResult表记录所有参数和结果 |

### 量化系统特定验证

| 要求 | 状态 | 说明 |
|------|------|------|
| **回测优先** | ✅ PASS | 本期核心目标就是实现回测 |
| **风险控制第一** | ✅ PASS | 回测考虑滑点、手续费、止损 |
| **渐进式部署** | ✅ PASS | 先回测验证 → 再应用到Paper Trading → 最后实盘 |
| **数据质量** | ✅ PASS | 实现数据验证和缺口检测 |

---

## Project Structure

### Documentation (this feature)

```text
specs/005-backtest-framework/
├── IMPLEMENTATION_PLAN.md       # This file
├── solution-proposal.md         # Approved solution
└── (将在各阶段生成)
    ├── data-schema.md           # Phase 0 output
    ├── backtest-guide.md        # Phase 3 output
    └── optimization-report.md   # Phase 4 output
```

### Source Code (repository root)

```text
backtest/                        # 🆕 新增Django应用
├── __init__.py
├── models.py                    # 2个核心模型
│   ├── KLine                   # K线历史数据
│   └── BacktestResult          # 回测结果
├── management/
│   └── commands/
│       ├── fetch_klines.py     # 数据获取命令
│       ├── update_klines.py    # 数据更新命令
│       ├── run_backtest.py     # 回测执行命令
│       └── optimize_params.py  # 参数优化命令
├── services/
│   ├── data_fetcher.py         # 数据获取服务
│   ├── data_validator.py       # 数据验证服务
│   ├── backtest_engine.py      # vectorbt回测引擎
│   ├── grid_strategy_vbt.py    # 网格策略（vectorbt格式）
│   └── result_analyzer.py      # 结果分析服务
├── admin.py                     # Django Admin界面
├── migrations/                  # 数据库迁移
└── tests/                       # 单元测试
    ├── test_data_fetcher.py
    ├── test_data_validator.py
    ├── test_backtest_engine.py
    └── test_grid_strategy.py

config/
└── backtest.yaml               # 🆕 回测配置

vp_squeeze/                      # ✅ 复用现有模块
├── services/
│   └── binance_kline_service.py
└── dto.py

tests/
└── backtest/                    # 🆕 新增测试
    ├── test_kline_model.py
    ├── test_fetch_command.py
    ├── test_backtest_command.py
    └── test_integration.py
```

**Structure Decision**: 创建独立的backtest Django应用，包含数据持久化和回测逻辑。复用现有binance_kline_service获取数据，避免重复开发。

---

## Phase 0: 项目初始化

**目标**: 搭建backtest应用基础结构，定义数据模型

**状态**: ⏳ 未开始

**验收标准**:
- [ ] 创建`backtest` Django应用
- [ ] 定义KLine和BacktestResult模型
- [ ] 数据库迁移就绪（2个模型表创建成功）
- [ ] 配置文件加载逻辑验证通过
- [ ] 安装vectorbt等依赖

**任务清单**:

### Task 0.1: 创建Django应用

```bash
# 创建应用
python manage.py startapp backtest

# 注册到settings.py
INSTALLED_APPS = [
    ...
    'backtest',
]
```

### Task 0.2: 定义数据模型

**KLine模型**:

```python
# backtest/models.py
from django.db import models
from decimal import Decimal

class KLine(models.Model):
    """K线历史数据"""

    # 基本信息
    symbol = models.CharField(
        '交易对', max_length=20, db_index=True,
        help_text='如: BTCUSDT, ETHUSDT'
    )
    interval = models.CharField(
        '时间周期', max_length=10, db_index=True,
        help_text='如: 1h, 4h, 1d'
    )

    # 时间
    open_time = models.DateTimeField('开盘时间', db_index=True)
    close_time = models.DateTimeField('收盘时间')

    # OHLCV数据
    open_price = models.DecimalField('开盘价', max_digits=20, decimal_places=8)
    high_price = models.DecimalField('最高价', max_digits=20, decimal_places=8)
    low_price = models.DecimalField('最低价', max_digits=20, decimal_places=8)
    close_price = models.DecimalField('收盘价', max_digits=20, decimal_places=8)
    volume = models.DecimalField('成交量', max_digits=30, decimal_places=8)

    # 其他数据
    quote_volume = models.DecimalField(
        '成交额', max_digits=30, decimal_places=8,
        help_text='Quote asset volume'
    )
    trade_count = models.IntegerField('成交笔数', default=0)
    taker_buy_volume = models.DecimalField(
        '主动买入量', max_digits=30, decimal_places=8, default=0
    )
    taker_buy_quote_volume = models.DecimalField(
        '主动买入额', max_digits=30, decimal_places=8, default=0
    )

    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = 'K线数据'
        verbose_name_plural = 'K线数据列表'
        db_table = 'backtest_kline'
        unique_together = [['symbol', 'interval', 'open_time']]  # 防止重复
        indexes = [
            models.Index(fields=['symbol', 'interval', 'open_time']),
            models.Index(fields=['symbol', 'interval', '-open_time']),  # 倒序查询
            models.Index(fields=['open_time']),
        ]
        ordering = ['symbol', 'interval', 'open_time']

    def __str__(self):
        return f"{self.symbol} {self.interval} {self.open_time.strftime('%Y-%m-%d %H:%M')}"
```

**BacktestResult模型**:

```python
class BacktestResult(models.Model):
    """回测结果记录"""

    # 基本信息
    name = models.CharField('回测名称', max_length=100)
    symbol = models.CharField('交易对', max_length=20, db_index=True)
    interval = models.CharField('时间周期', max_length=10)

    # 时间范围
    start_date = models.DateTimeField('开始日期')
    end_date = models.DateTimeField('结束日期')

    # 策略参数（JSON格式）
    strategy_params = models.JSONField(
        '策略参数',
        help_text='包含: grid_step_pct, grid_levels, order_size, stop_loss等'
    )

    # 回测结果指标
    initial_cash = models.DecimalField('初始资金', max_digits=20, decimal_places=2, default=10000)
    final_value = models.DecimalField('最终价值', max_digits=20, decimal_places=2)
    total_return = models.DecimalField('总收益率', max_digits=10, decimal_places=4)

    sharpe_ratio = models.DecimalField(
        '夏普比率', max_digits=10, decimal_places=4, null=True, blank=True
    )
    max_drawdown = models.DecimalField('最大回撤', max_digits=10, decimal_places=4)
    win_rate = models.DecimalField('胜率', max_digits=5, decimal_places=2)

    total_trades = models.IntegerField('总交易次数', default=0)
    profitable_trades = models.IntegerField('盈利交易次数', default=0)
    losing_trades = models.IntegerField('亏损交易次数', default=0)

    # 详细数据（JSON格式）
    equity_curve = models.JSONField(
        '权益曲线', null=True, blank=True,
        help_text='时间序列的账户价值'
    )
    trades_detail = models.JSONField(
        '交易明细', null=True, blank=True,
        help_text='每笔交易的详细信息'
    )
    daily_returns = models.JSONField(
        '每日收益', null=True, blank=True
    )

    # 元数据
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    notes = models.TextField('备注', blank=True)

    class Meta:
        verbose_name = '回测结果'
        verbose_name_plural = '回测结果列表'
        db_table = 'backtest_result'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['symbol', 'interval', '-created_at']),
            models.Index(fields=['-total_return']),  # 按收益率排序
        ]

    def __str__(self):
        return f"{self.name} - {self.symbol} ({self.total_return:.2%})"
```

### Task 0.3: 安装依赖

创建或更新`requirements.txt`:

```text
# 现有依赖
Django==4.2.8
psycopg2-binary==2.9.9
pytest==9.0.0
pytest-django==4.11.1

# 新增依赖（Phase 0）
vectorbt==0.26.2
pandas==2.1.4
numpy==1.26.2
matplotlib==3.8.2
scikit-learn==1.3.2  # 用于参数优化
```

```bash
pip install -r requirements.txt
```

### Task 0.4: 创建配置文件

**config/backtest.yaml**:

```yaml
# 回测系统配置

# 默认回测参数
default:
  initial_cash: 10000          # 初始资金（USDT）
  commission: 0.001            # 手续费率（0.1%）
  slippage: 0.0005            # 滑点（0.05%）

# 数据获取配置
data_fetch:
  max_retries: 3               # 最大重试次数
  retry_delay: 1.0            # 重试延迟（秒）
  batch_size: 1000            # 批量大小（币安API限制）

# 支持的交易对
symbols:
  - BTCUSDT
  - ETHUSDT
  - SOLUSDT
  - BNBUSDT

# 支持的时间周期
intervals:
  - 1h
  - 4h
  - 1d

# ETH 4h 测试配置（用于开发测试）
eth_4h_test:
  symbol: ETHUSDT
  interval: 4h
  days: 180                    # 6个月
  initial_cash: 10000

# 网格策略默认参数范围（用于优化）
grid_strategy:
  grid_step_pct:
    min: 0.005                 # 0.5%
    max: 0.02                  # 2%
    default: 0.01              # 1%

  grid_levels:
    min: 5
    max: 20
    default: 10

  order_size_usdt:
    min: 50
    max: 500
    default: 100

  stop_loss_pct:
    min: 0.05                  # 5%
    max: 0.20                  # 20%
    default: 0.10              # 10%
```

### Task 0.5: 运行迁移

```bash
# 创建迁移文件
python manage.py makemigrations backtest

# 应用迁移
python manage.py migrate

# 验证表创建
python manage.py dbshell
# sqlite> .tables
# 应该看到 backtest_kline 和 backtest_result
```

**测试**:

```bash
# 验证模型可以创建
python manage.py shell
>>> from backtest.models import KLine, BacktestResult
>>> from django.utils import timezone
>>> from decimal import Decimal

# 创建测试K线
>>> kline = KLine.objects.create(
...     symbol='ETHUSDT',
...     interval='4h',
...     open_time=timezone.now(),
...     close_time=timezone.now(),
...     open_price=Decimal('2000.00'),
...     high_price=Decimal('2050.00'),
...     low_price=Decimal('1990.00'),
...     close_price=Decimal('2020.00'),
...     volume=Decimal('1000.0'),
...     quote_volume=Decimal('2000000.0'),
...     trade_count=5000,
...     taker_buy_volume=Decimal('500.0'),
...     taker_buy_quote_volume=Decimal('1000000.0')
... )
>>> print(kline)
>>> KLine.objects.count()
1
```

**关键文件**:
- `backtest/__init__.py`
- `backtest/models.py`
- `backtest/migrations/0001_initial.py`
- `config/backtest.yaml`
- `requirements.txt`

---

## Phase 1: 数据获取与持久化

**目标**: 实现币安历史K线数据获取、验证、存储

**状态**: ⏳ 未开始

**验收标准**:
- [ ] 数据获取命令可执行：`python manage.py fetch_klines --symbol ETHUSDT --interval 4h --days 180`
- [ ] 6个月ETH 4h数据成功存入数据库（约1080条）
- [ ] 数据验证正常（无缺口、无异常值）
- [ ] 支持增量更新
- [ ] 支持多币种多周期

**任务清单**:

### Task 1.1: 实现数据获取服务

**backtest/services/data_fetcher.py**:

```python
"""
数据获取服务
Data Fetcher Service
"""
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from django.utils import timezone

from vp_squeeze.services.binance_kline_service import fetch_klines
from vp_squeeze.dto import KLineData
from backtest.models import KLine

logger = logging.getLogger(__name__)


class DataFetcher:
    """历史数据获取器"""

    def __init__(self, symbol: str, interval: str):
        """
        初始化

        Args:
            symbol: 交易对，如'ETHUSDT'
            interval: 时间周期，如'4h'
        """
        self.symbol = symbol.upper()
        self.interval = interval

    def fetch_historical_data(
        self,
        days: int = 180,
        batch_size: int = 1000
    ) -> int:
        """
        获取历史数据并存储到数据库

        Args:
            days: 获取天数
            batch_size: 批量大小

        Returns:
            int: 新增数据条数
        """
        logger.info(
            f"开始获取历史数据: {self.symbol} {self.interval}, "
            f"天数={days}"
        )

        # 计算需要的K线数量
        # 4h周期：每天6根K线
        # 1h周期：每天24根K线
        # 1d周期：每天1根K线
        interval_map = {
            '1h': 24,
            '4h': 6,
            '1d': 1,
        }
        bars_per_day = interval_map.get(self.interval, 6)
        limit = min(days * bars_per_day, batch_size)

        # 从币安获取数据
        kline_data_list = fetch_klines(
            symbol=self.symbol,
            interval=self.interval,
            limit=limit
        )

        logger.info(f"从币安获取{len(kline_data_list)}条K线数据")

        # 转换并保存
        saved_count = self._save_klines(kline_data_list)

        logger.info(f"数据获取完成: 新增{saved_count}条")
        return saved_count

    def _save_klines(self, kline_data_list: List[KLineData]) -> int:
        """
        保存K线数据到数据库

        Args:
            kline_data_list: KLineData列表

        Returns:
            int: 新增数据条数
        """
        new_klines = []

        for kline_data in kline_data_list:
            # 检查是否已存在（防止重复）
            exists = KLine.objects.filter(
                symbol=self.symbol,
                interval=self.interval,
                open_time=kline_data.open_time
            ).exists()

            if not exists:
                new_klines.append(KLine(
                    symbol=self.symbol,
                    interval=self.interval,
                    open_time=kline_data.open_time,
                    close_time=kline_data.close_time,
                    open_price=kline_data.open,
                    high_price=kline_data.high,
                    low_price=kline_data.low,
                    close_price=kline_data.close,
                    volume=kline_data.volume,
                    quote_volume=kline_data.quote_volume,
                    trade_count=kline_data.trade_count,
                    taker_buy_volume=kline_data.taker_buy_volume,
                    taker_buy_quote_volume=kline_data.taker_buy_quote_volume
                ))

        # 批量创建
        if new_klines:
            KLine.objects.bulk_create(new_klines, batch_size=500)
            logger.info(f"批量创建{len(new_klines)}条K线记录")

        return len(new_klines)

    def update_latest_data(self, limit: int = 100) -> int:
        """
        增量更新最新数据

        Args:
            limit: 获取最新N条

        Returns:
            int: 新增数据条数
        """
        logger.info(f"增量更新数据: {self.symbol} {self.interval}")

        # 获取最新数据
        kline_data_list = fetch_klines(
            symbol=self.symbol,
            interval=self.interval,
            limit=limit
        )

        # 保存
        saved_count = self._save_klines(kline_data_list)

        logger.info(f"增量更新完成: 新增{saved_count}条")
        return saved_count
```

### Task 1.2: 实现数据验证服务

**backtest/services/data_validator.py**:

```python
"""
数据验证服务
Data Validator Service
"""
import logging
from datetime import timedelta
from typing import List, Tuple
from django.db.models import QuerySet

from backtest.models import KLine

logger = logging.getLogger(__name__)


class DataValidator:
    """数据验证器"""

    def validate_klines(
        self,
        symbol: str,
        interval: str
    ) -> Tuple[bool, List[str]]:
        """
        验证K线数据质量

        Args:
            symbol: 交易对
            interval: 时间周期

        Returns:
            (is_valid, errors): (是否有效, 错误列表)
        """
        errors = []

        # 获取数据
        klines = KLine.objects.filter(
            symbol=symbol,
            interval=interval
        ).order_by('open_time')

        if not klines.exists():
            errors.append(f"没有找到数据: {symbol} {interval}")
            return False, errors

        logger.info(f"开始验证数据: {symbol} {interval}, 共{klines.count()}条")

        # 1. 检查价格合理性
        price_errors = self._check_price_validity(klines)
        errors.extend(price_errors)

        # 2. 检查时间连续性
        gap_errors = self._check_time_gaps(klines, interval)
        errors.extend(gap_errors)

        # 3. 检查成交量异常
        volume_errors = self._check_volume_anomalies(klines)
        errors.extend(volume_errors)

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(f"数据验证通过: {symbol} {interval}")
        else:
            logger.warning(f"数据验证失败: {symbol} {interval}, 错误数={len(errors)}")

        return is_valid, errors

    def _check_price_validity(self, klines: QuerySet) -> List[str]:
        """检查价格合理性"""
        errors = []

        for kline in klines:
            # high >= low
            if kline.high_price < kline.low_price:
                errors.append(
                    f"{kline.open_time}: high({kline.high_price}) < low({kline.low_price})"
                )

            # high >= open, close
            if (kline.high_price < kline.open_price or
                kline.high_price < kline.close_price):
                errors.append(
                    f"{kline.open_time}: high价格异常"
                )

            # low <= open, close
            if (kline.low_price > kline.open_price or
                kline.low_price > kline.close_price):
                errors.append(
                    f"{kline.open_time}: low价格异常"
                )

        return errors

    def _check_time_gaps(
        self,
        klines: QuerySet,
        interval: str
    ) -> List[str]:
        """检查时间缺口"""
        errors = []

        # 计算时间间隔
        interval_map = {
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1),
        }
        expected_delta = interval_map.get(interval)

        if not expected_delta:
            return errors

        klines_list = list(klines)

        for i in range(1, len(klines_list)):
            prev_kline = klines_list[i-1]
            curr_kline = klines_list[i]

            actual_delta = curr_kline.open_time - prev_kline.open_time

            # 允许5分钟误差
            if abs(actual_delta - expected_delta) > timedelta(minutes=5):
                errors.append(
                    f"时间缺口: {prev_kline.open_time} -> {curr_kline.open_time}, "
                    f"间隔={actual_delta}"
                )

        return errors

    def _check_volume_anomalies(self, klines: QuerySet) -> List[str]:
        """检查成交量异常"""
        errors = []

        for kline in klines:
            # 成交量不能为负
            if kline.volume < 0:
                errors.append(f"{kline.open_time}: 成交量为负({kline.volume})")

            # quote_volume应该大致等于 (open+close)/2 * volume
            # 这里只做基本检查
            if kline.quote_volume < 0:
                errors.append(f"{kline.open_time}: 成交额为负({kline.quote_volume})")

        return errors
```

### Task 1.3: 实现数据获取命令

**backtest/management/commands/fetch_klines.py**:

```python
"""
数据获取管理命令
Fetch KLines Command
"""
import logging
from django.core.management.base import BaseCommand

from backtest.services.data_fetcher import DataFetcher
from backtest.services.data_validator import DataValidator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '从币安获取历史K线数据并存储到数据库'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对，如: ETHUSDT, BTCUSDT'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            help='时间周期，如: 1h, 4h, 1d'
        )
        parser.add_argument(
            '--days', '-d',
            type=int,
            default=180,
            help='获取天数，默认180天（6个月）'
        )
        parser.add_argument(
            '--validate',
            action='store_true',
            help='获取后验证数据'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        days = options['days']
        validate = options['validate']

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS(f"数据获取: {symbol} {interval}"))
        self.stdout.write(f"时间范围: {days}天")
        self.stdout.write(f"{'='*80}\n")

        try:
            # 1. 获取数据
            fetcher = DataFetcher(symbol, interval)
            saved_count = fetcher.fetch_historical_data(days=days)

            self.stdout.write(
                self.style.SUCCESS(f"✓ 数据获取成功: 新增{saved_count}条K线")
            )

            # 2. 验证数据（可选）
            if validate:
                self.stdout.write("\n验证数据...")
                validator = DataValidator()
                is_valid, errors = validator.validate_klines(symbol, interval)

                if is_valid:
                    self.stdout.write(self.style.SUCCESS("✓ 数据验证通过"))
                else:
                    self.stdout.write(
                        self.style.WARNING(f"⚠ 数据验证发现{len(errors)}个问题:")
                    )
                    for error in errors[:10]:  # 只显示前10个
                        self.stdout.write(f"  - {error}")

            self.stdout.write(f"\n{'='*80}")
            self.stdout.write(self.style.SUCCESS("数据获取完成"))
            self.stdout.write(f"{'='*80}\n")

        except Exception as e:
            logger.exception("数据获取失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
```

### Task 1.4: 实现数据更新命令

**backtest/management/commands/update_klines.py**:

```python
"""
数据更新管理命令
Update KLines Command
"""
import logging
from django.core.management.base import BaseCommand

from backtest.services.data_fetcher import DataFetcher

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '增量更新K线数据'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            help='时间周期'
        )
        parser.add_argument(
            '--limit', '-l',
            type=int,
            default=100,
            help='获取最新N条，默认100'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        limit = options['limit']

        self.stdout.write(f"更新数据: {symbol} {interval}...")

        try:
            fetcher = DataFetcher(symbol, interval)
            saved_count = fetcher.update_latest_data(limit=limit)

            self.stdout.write(
                self.style.SUCCESS(f"✓ 更新完成: 新增{saved_count}条")
            )

        except Exception as e:
            logger.exception("数据更新失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
```

**测试**:

```bash
# 1. 获取ETH 4h数据（6个月）
python manage.py fetch_klines --symbol ETHUSDT --interval 4h --days 180 --validate

# 2. 验证数据库
python manage.py shell
>>> from backtest.models import KLine
>>> KLine.objects.filter(symbol='ETHUSDT', interval='4h').count()
# 应该约1080条

# 3. 测试增量更新
python manage.py update_klines --symbol ETHUSDT --interval 4h --limit 10

# 4. 测试多币种
python manage.py fetch_klines --symbol BTCUSDT --interval 4h --days 180
python manage.py fetch_klines --symbol SOLUSDT --interval 1h --days 30
```

**关键文件**:
- `backtest/services/data_fetcher.py`
- `backtest/services/data_validator.py`
- `backtest/management/commands/fetch_klines.py`
- `backtest/management/commands/update_klines.py`
- `tests/backtest/test_data_fetcher.py`

---

## Phase 2: vectorbt回测引擎集成

**目标**: 集成vectorbt，实现基础回测框架

**状态**: ⏳ 未开始

**验收标准**:
- [ ] vectorbt成功集成
- [ ] 可以从数据库读取K线数据转换为DataFrame
- [ ] 实现简单的买入持有策略回测
- [ ] 回测结果可以保存到BacktestResult表
- [ ] 回测指标计算正确（收益率、夏普比率、最大回撤）

**任务清单**:

### Task 2.1: 实现回测引擎基类

**backtest/services/backtest_engine.py**:

```python
"""
回测引擎
Backtest Engine using vectorbt
"""
import logging
import pandas as pd
import numpy as np
import vectorbt as vbt
from datetime import datetime
from typing import Dict, Any, Optional
from decimal import Decimal

from django.utils import timezone
from backtest.models import KLine, BacktestResult

logger = logging.getLogger(__name__)


class BacktestEngine:
    """vectorbt回测引擎"""

    def __init__(
        self,
        symbol: str,
        interval: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        initial_cash: float = 10000.0,
        commission: float = 0.001,  # 0.1%
        slippage: float = 0.0005    # 0.05%
    ):
        """
        初始化回测引擎

        Args:
            symbol: 交易对
            interval: 时间周期
            start_date: 开始日期
            end_date: 结束日期
            initial_cash: 初始资金
            commission: 手续费率
            slippage: 滑点
        """
        self.symbol = symbol
        self.interval = interval
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.commission = commission
        self.slippage = slippage

        # 加载数据
        self.df = self._load_data()

        logger.info(
            f"回测引擎初始化: {symbol} {interval}, "
            f"数据量={len(self.df)}, "
            f"时间范围={self.df.index[0]} ~ {self.df.index[-1]}"
        )

    def _load_data(self) -> pd.DataFrame:
        """从数据库加载K线数据"""
        queryset = KLine.objects.filter(
            symbol=self.symbol,
            interval=self.interval
        )

        if self.start_date:
            queryset = queryset.filter(open_time__gte=self.start_date)
        if self.end_date:
            queryset = queryset.filter(open_time__lte=self.end_date)

        queryset = queryset.order_by('open_time')

        if not queryset.exists():
            raise ValueError(f"没有找到数据: {self.symbol} {self.interval}")

        # 转换为DataFrame
        data = list(queryset.values(
            'open_time', 'open_price', 'high_price',
            'low_price', 'close_price', 'volume'
        ))

        df = pd.DataFrame(data)

        # 重命名列
        df = df.rename(columns={
            'open_price': 'Open',
            'high_price': 'High',
            'low_price': 'Low',
            'close_price': 'Close',
            'volume': 'Volume'
        })

        # 转换为float（从Decimal）
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = df[col].astype(float)

        # 设置索引
        df['open_time'] = pd.to_datetime(df['open_time'])
        df = df.set_index('open_time')

        return df

    def run_backtest(
        self,
        entries: pd.Series,
        exits: pd.Series,
        strategy_name: str = "Custom Strategy",
        strategy_params: Optional[Dict[str, Any]] = None
    ) -> BacktestResult:
        """
        运行回测

        Args:
            entries: 买入信号（True/False）
            exits: 卖出信号（True/False）
            strategy_name: 策略名称
            strategy_params: 策略参数

        Returns:
            BacktestResult: 回测结果对象
        """
        logger.info(f"开始回测: {strategy_name}")

        # 创建Portfolio
        portfolio = vbt.Portfolio.from_signals(
            close=self.df['Close'],
            entries=entries,
            exits=exits,
            init_cash=self.initial_cash,
            fees=self.commission,
            slippage=self.slippage,
            freq=self.interval
        )

        # 计算指标
        total_return = portfolio.total_return()
        sharpe_ratio = portfolio.sharpe_ratio()
        max_drawdown = portfolio.max_drawdown()

        # 交易统计
        trades = portfolio.trades.records_readable
        total_trades = len(trades)
        profitable_trades = len(trades[trades['PnL'] > 0])
        losing_trades = len(trades[trades['PnL'] < 0])
        win_rate = profitable_trades / total_trades * 100 if total_trades > 0 else 0

        # 权益曲线
        equity_curve = portfolio.value().to_dict()
        equity_curve = {str(k): float(v) for k, v in equity_curve.items()}

        # 交易明细
        trades_detail = trades.to_dict('records') if not trades.empty else []

        # 每日收益
        daily_returns = portfolio.returns().to_dict()
        daily_returns = {str(k): float(v) for k, v in daily_returns.items()}

        # 创建回测结果
        result = BacktestResult.objects.create(
            name=strategy_name,
            symbol=self.symbol,
            interval=self.interval,
            start_date=self.df.index[0],
            end_date=self.df.index[-1],
            strategy_params=strategy_params or {},
            initial_cash=Decimal(str(self.initial_cash)),
            final_value=Decimal(str(portfolio.final_value())),
            total_return=Decimal(str(total_return)),
            sharpe_ratio=Decimal(str(sharpe_ratio)) if not pd.isna(sharpe_ratio) else None,
            max_drawdown=Decimal(str(abs(max_drawdown))),
            win_rate=Decimal(str(win_rate)),
            total_trades=total_trades,
            profitable_trades=profitable_trades,
            losing_trades=losing_trades,
            equity_curve=equity_curve,
            trades_detail=trades_detail,
            daily_returns=daily_returns
        )

        logger.info(
            f"回测完成: {strategy_name}, "
            f"收益率={total_return:.2%}, "
            f"夏普比率={sharpe_ratio:.2f}, "
            f"最大回撤={max_drawdown:.2%}"
        )

        return result
```

### Task 2.2: 实现简单买入持有策略（测试用）

**backtest/services/buy_hold_strategy.py**:

```python
"""
买入持有策略（用于测试）
Buy and Hold Strategy
"""
import pandas as pd
from backtest.services.backtest_engine import BacktestEngine


class BuyHoldStrategy:
    """买入持有策略"""

    def __init__(self, engine: BacktestEngine):
        self.engine = engine

    def generate_signals(self) -> tuple[pd.Series, pd.Series]:
        """
        生成买入持有信号

        Returns:
            (entries, exits): 买入信号和卖出信号
        """
        df = self.engine.df

        # 第一天买入
        entries = pd.Series(False, index=df.index)
        entries.iloc[0] = True

        # 最后一天卖出
        exits = pd.Series(False, index=df.index)
        exits.iloc[-1] = True

        return entries, exits

    def run(self) -> 'BacktestResult':
        """运行回测"""
        entries, exits = self.generate_signals()

        result = self.engine.run_backtest(
            entries=entries,
            exits=exits,
            strategy_name=f"Buy & Hold - {self.engine.symbol}",
            strategy_params={
                'strategy_type': 'buy_and_hold'
            }
        )

        return result
```

### Task 2.3: 实现回测命令

**backtest/management/commands/run_backtest.py**:

```python
"""
回测执行命令
Run Backtest Command
"""
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from backtest.services.backtest_engine import BacktestEngine
from backtest.services.buy_hold_strategy import BuyHoldStrategy

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '运行回测'

    def add_arguments(self, parser):
        parser.add_argument(
            '--symbol', '-s',
            type=str,
            required=True,
            help='交易对'
        )
        parser.add_argument(
            '--interval', '-i',
            type=str,
            required=True,
            help='时间周期'
        )
        parser.add_argument(
            '--strategy',
            type=str,
            default='buy_hold',
            choices=['buy_hold', 'grid'],
            help='策略类型'
        )
        parser.add_argument(
            '--days',
            type=int,
            help='回测天数（从最新数据往前）'
        )
        parser.add_argument(
            '--initial-cash',
            type=float,
            default=10000.0,
            help='初始资金，默认10000 USDT'
        )

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        interval = options['interval']
        strategy_type = options['strategy']
        days = options.get('days')
        initial_cash = options['initial_cash']

        self.stdout.write(f"\n{'='*80}")
        self.stdout.write(self.style.SUCCESS(f"回测: {symbol} {interval}"))
        self.stdout.write(f"策略: {strategy_type}")
        self.stdout.write(f"初始资金: ${initial_cash}")
        self.stdout.write(f"{'='*80}\n")

        try:
            # 计算时间范围
            end_date = None
            start_date = None
            if days:
                end_date = timezone.now()
                start_date = end_date - timedelta(days=days)

            # 创建回测引擎
            engine = BacktestEngine(
                symbol=symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash
            )

            # 运行策略
            if strategy_type == 'buy_hold':
                strategy = BuyHoldStrategy(engine)
                result = strategy.run()
            else:
                raise ValueError(f"不支持的策略类型: {strategy_type}")

            # 显示结果
            self.stdout.write("\n" + "="*80)
            self.stdout.write(self.style.SUCCESS("回测结果"))
            self.stdout.write("="*80)
            self.stdout.write(f"回测ID: {result.id}")
            self.stdout.write(f"时间范围: {result.start_date} ~ {result.end_date}")
            self.stdout.write(f"初始资金: ${float(result.initial_cash):.2f}")
            self.stdout.write(f"最终价值: ${float(result.final_value):.2f}")

            total_return_pct = float(result.total_return) * 100
            if total_return_pct > 0:
                self.stdout.write(
                    self.style.SUCCESS(f"总收益率: +{total_return_pct:.2f}%")
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"总收益率: {total_return_pct:.2f}%")
                )

            if result.sharpe_ratio:
                self.stdout.write(f"夏普比率: {float(result.sharpe_ratio):.2f}")
            self.stdout.write(f"最大回撤: {float(result.max_drawdown):.2f}%")
            self.stdout.write(f"总交易次数: {result.total_trades}")
            self.stdout.write(f"胜率: {float(result.win_rate):.2f}%")
            self.stdout.write("="*80 + "\n")

        except Exception as e:
            logger.exception("回测失败")
            self.stderr.write(self.style.ERROR(f"✗ 错误: {e}"))
```

**测试**:

```bash
# 1. 运行买入持有策略回测（ETH 4h, 6个月）
python manage.py run_backtest --symbol ETHUSDT --interval 4h --strategy buy_hold

# 2. 查看回测结果
python manage.py shell
>>> from backtest.models import BacktestResult
>>> result = BacktestResult.objects.latest('created_at')
>>> print(f"收益率: {result.total_return:.2%}")
>>> print(f"夏普比率: {result.sharpe_ratio}")
```

**关键文件**:
- `backtest/services/backtest_engine.py`
- `backtest/services/buy_hold_strategy.py`
- `backtest/management/commands/run_backtest.py`
- `tests/backtest/test_backtest_engine.py`

---

## Phase 3: 网格策略回测实现

**目标**: 实现网格交易策略的vectorbt回测版本

**状态**: ⏳ 未开始

**验收标准**:
- [ ] 网格策略信号生成正确
- [ ] 回测结果与预期一致
- [ ] 支持参数化（网格步长、层数、止损）
- [ ] 多参数组合回测功能
- [ ] 回测报告生成

**实现细节**: (由于篇幅限制，Phase 3和4将在确认后继续编写)

---

## Phase 4: 结果分析与参数优化

**目标**: 回测结果可视化、参数优化

**状态**: ⏳ 未开始

**验收标准**:
- [ ] 权益曲线可视化
- [ ] 参数优化网格搜索
- [ ] 回测报告生成
- [ ] 最优参数推荐

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (初始化)
  ↓
Phase 1 (数据获取) ← 独立，可并行测试
  ↓
Phase 2 (vectorbt集成) ← 依赖Phase 1数据
  ↓
Phase 3 (网格策略) ← 依赖Phase 2引擎
  ↓
Phase 4 (优化分析) ← 依赖Phase 3回测结果
```

---

## Risk Mitigation

### 技术风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| **vectorbt版本兼容** | 中 | 中 | 使用稳定版本0.26.2，充分测试 |
| **数据量过大** | 低 | 低 | 6个月数据量适中，可控 |
| **回测性能差** | 低 | 中 | vectorbt基于NumPy，性能优异 |

---

**计划创建时间**: 2025-11-28
**预计完成时间**: 2025-12-12（2周）
**当前状态**: Phase 0 准备中
