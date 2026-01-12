# PRD: DDPS多市场多周期支持

## 文档信息

| 属性 | 值 |
|------|-----|
| 迭代编号 | 024 |
| 版本 | 1.0 |
| 状态 | 需求定义中 |
| 创建日期 | 2026-01-09 |
| 关联迭代 | 009(DDPS-Z), 023(DDPS监控) |

## 1. 背景与目标

### 1.1 背景

当前DDPS策略系统存在以下限制：
- **时间周期限制**：默认仅支持4h周期，硬编码在多处
- **市场类型限制**：仅支持加密货币的现货/合约，不支持A股、美股等传统市场

用户需要将DDPS策略应用到：
- 不同时间周期：1min, 5min, 15min, 1h, 4h, 1d 等
- 不同市场类型：A股、美股、港股、加密货币等

### 1.2 核心价值

**一句话描述**：升级DDPS服务层，实现对任意K线周期和任意市场类型的通用支持。

### 1.3 目标用户

- 量化交易者：需要在不同市场和周期测试DDPS策略
- 技术分析师：需要跨市场应用DDPS分析方法

## 2. 现状分析

### 2.1 当前架构

```
┌─────────────────────────────────────────────────────────────┐
│                     数据层 (KLine Model)                      │
│  - market_type: spot | futures (仅加密货币)                   │
│  - interval: 支持任意周期（数据模型层面已通用）                  │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│                     服务层 (DDPSMonitorService)               │
│  - interval: 默认'4h'，可配置                                 │
│  - market_type: 默认'futures'，可配置                         │
│  - 数据获取: 仅支持Binance API                                │
└─────────────────────────────────────────────────────────────┘
                              ↑
┌─────────────────────────────────────────────────────────────┐
│                     计算层 (Calculators)                      │
│  - EMACalculator: 周期无关 ✓                                 │
│  - EWMACalculator: 周期无关 ✓                                │
│  - BetaCycleCalculator: 需要interval_hours参数               │
│  - InertiaCalculator: 周期无关 ✓                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 硬编码点分析

| 位置 | 硬编码内容 | 影响 |
|------|-----------|------|
| settings.DDPS_MONITOR_CONFIG | interval='4h', market_type='futures' | 默认配置 |
| DDPSMonitorService.__init__ | interval='4h', market_type='futures' | 服务默认值 |
| BetaCycleCalculator.calculate | interval_hours=4.0 | 周期计算 |
| 前端模板 | data-interval="4h" | UI显示 |

### 2.3 扩展性分析

| 组件 | 扩展难度 | 说明 |
|------|----------|------|
| KLine模型 | 低 | market_type已支持choices扩展 |
| 计算器 | 低 | 大部分与周期无关 |
| 数据获取 | 中 | 需要抽象数据源接口 |
| API接口 | 低 | 已支持interval/market_type参数 |

## 3. 需求范围

### 3.1 核心需求（P0 - MVP）

| ID | 功能 | 描述 | 优先级 |
|----|------|------|--------|
| REQ-001 | 市场类型扩展 | 扩展market_type支持：crypto_spot, crypto_futures, us_stock, a_stock, hk_stock | P0 |
| REQ-002 | 周期标准化 | 定义标准周期枚举：1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w | P0 |
| REQ-003 | 数据源抽象 | 抽象KLineDataSource接口，支持不同市场的数据获取 | P0 |
| REQ-004 | 周期自适应计算 | BetaCycleCalculator等周期相关计算器自动适配interval | P0 |
| REQ-005 | 配置扩展 | DDPS_MONITOR_CONFIG支持多市场多周期配置 | P0 |

### 3.2 延迟需求（P1）

| ID | 功能 | 描述 |
|----|------|------|
| REQ-P1-001 | 美股数据源 | 实现USStockDataSource（如Yahoo Finance） |
| REQ-P1-002 | A股数据源 | 实现AStockDataSource（如Tushare） |
| REQ-P1-003 | 交易日历 | 不同市场的交易时间和节假日处理 |

## 4. 功能详情

### 4.1 市场类型扩展（REQ-001）

**市场类型定义**：

```python
class MarketType:
    CRYPTO_SPOT = 'crypto_spot'      # 加密货币现货
    CRYPTO_FUTURES = 'crypto_futures' # 加密货币合约
    US_STOCK = 'us_stock'            # 美股
    A_STOCK = 'a_stock'              # A股
    HK_STOCK = 'hk_stock'            # 港股

    CHOICES = [
        (CRYPTO_SPOT, '加密货币现货'),
        (CRYPTO_FUTURES, '加密货币合约'),
        (US_STOCK, '美股'),
        (A_STOCK, 'A股'),
        (HK_STOCK, '港股'),
    ]
```

**向后兼容**：
- `spot` → `crypto_spot`
- `futures` → `crypto_futures`

### 4.2 周期标准化（REQ-002）

**周期枚举定义**：

```python
class Interval:
    M1 = '1m'    # 1分钟
    M5 = '5m'    # 5分钟
    M15 = '15m'  # 15分钟
    M30 = '30m'  # 30分钟
    H1 = '1h'    # 1小时
    H4 = '4h'    # 4小时
    D1 = '1d'    # 1天
    W1 = '1w'    # 1周

    @staticmethod
    def to_hours(interval: str) -> float:
        """将interval转换为小时数"""
        mapping = {
            '1m': 1/60, '5m': 5/60, '15m': 0.25, '30m': 0.5,
            '1h': 1, '4h': 4, '1d': 24, '1w': 168
        }
        return mapping.get(interval, 4)  # 默认4小时
```

### 4.3 数据源抽象（REQ-003）

**接口设计**：

```python
from abc import ABC, abstractmethod

class KLineDataSource(ABC):
    """K线数据源抽象接口"""

    @abstractmethod
    def fetch_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 500
    ) -> List[dict]:
        """获取K线数据"""
        pass

    @abstractmethod
    def get_supported_intervals(self) -> List[str]:
        """获取支持的周期列表"""
        pass

    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """标准化交易对格式"""
        pass


class BinanceDataSource(KLineDataSource):
    """Binance数据源（加密货币）"""
    pass


class YahooFinanceDataSource(KLineDataSource):
    """Yahoo Finance数据源（美股）"""
    pass
```

### 4.4 周期自适应计算（REQ-004）

**BetaCycleCalculator改造**：

```python
class BetaCycleCalculator:
    def calculate(
        self,
        beta_list: List[float],
        timestamps: List[int],
        prices: List[float],
        interval: str = '4h'  # 改为接受interval字符串
    ) -> Tuple[List[str], dict]:
        # 自动转换为小时数
        interval_hours = Interval.to_hours(interval)
        # ... 其余逻辑不变
```

### 4.5 配置扩展（REQ-005）

**新配置结构**：

```python
DDPS_MONITOR_CONFIG = {
    # 默认配置
    'default_market': 'crypto_futures',
    'default_interval': '4h',

    # 市场配置
    'markets': {
        'crypto_futures': {
            'data_source': 'binance',
            'symbols': ['ETHUSDT', 'BTCUSDT', 'BNBUSDT'],
            'intervals': ['1h', '4h', '1d'],
        },
        'us_stock': {
            'data_source': 'yahoo',
            'symbols': ['AAPL', 'GOOGL', 'MSFT'],
            'intervals': ['1d'],
        },
    },

    # 推送配置
    'push_channel': 'price_ddps',
    'push_token': '...',
}
```

## 5. 技术约束

### 5.1 向后兼容

| 约束 | 说明 |
|------|------|
| API兼容 | 现有API接口保持不变，新增参数为可选 |
| 数据兼容 | 现有KLine数据自动映射到新market_type |
| 配置兼容 | 旧配置格式继续支持 |

### 5.2 性能要求

| 指标 | 目标 |
|------|------|
| 周期转换 | < 1ms |
| 数据源切换 | 无额外开销 |
| 计算性能 | 与现有一致 |

## 6. 验收标准

### 6.1 功能验收

- [ ] 支持配置多种market_type
- [ ] 支持配置任意interval
- [ ] BetaCycleCalculator正确处理不同周期
- [ ] 数据源接口可扩展
- [ ] 向后兼容现有功能

### 6.2 集成验收

- [ ] 现有DDPS监控命令正常工作
- [ ] 现有Web界面正常显示
- [ ] 推送功能正常

## 7. 里程碑

| 阶段 | 内容 | 预期产出 |
|------|------|----------|
| M1 | 定义标准类型和接口 | MarketType, Interval, KLineDataSource |
| M2 | 改造核心服务 | DDPSMonitorService支持多周期 |
| M3 | 扩展配置系统 | 新配置格式支持 |
| M4 | 验证和测试 | 端到端测试通过 |
