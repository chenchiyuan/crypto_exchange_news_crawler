# PRD: CSV数据源K线获取服务

**迭代编号**: 025
**版本**: 1.0
**创建日期**: 2026-01-09
**状态**: 需求定义完成

---

## 1. 背景与目标

### 1.1 背景

当前项目的K线数据获取依赖Binance API实时获取，但存在以下限制：
1. **API限制**: Binance API最小支持1分钟K线，无法获取1秒级数据
2. **历史数据**: 部分历史数据无法通过API补全
3. **回测需求**: 高频策略回测需要秒级K线数据支持

用户已有本地CSV格式的历史K线数据（币安官方数据导出格式），包含：
- ETHUSDT-1s-2025-12.csv（268万行，1秒级K线）
- ETHUSDT-1m-2025-12.csv（4.5万行，1分钟K线）

### 1.2 目标

实现CSV数据源K线获取服务，使系统能够：
1. 解析本地CSV格式的K线数据
2. 支持1秒级（1s）和1分钟（1m）周期的回测
3. 与现有`KLineFetcher`架构无缝集成
4. 支持DDPS分析和策略回测

### 1.3 非目标

- ❌ 不实现CSV数据的实时监控功能
- ❌ 不替代Binance API作为主要数据源
- ❌ 不支持CSV数据写入/导出
- ❌ 不实现增量加载优化（MVP采用全量加载）

---

## 2. 用户故事

### US-01: 作为量化研究员
**我想要** 使用本地1秒K线数据进行高频策略回测
**以便于** 评估策略在高频场景下的表现

**验收标准**:
- 可以通过配置指定CSV文件路径
- 支持指定时间范围筛选数据
- 返回标准`StandardKLine`格式数据

### US-02: 作为回测系统
**我想要** 无缝切换API数据源和CSV数据源
**以便于** 对比不同数据源的回测结果

**验收标准**:
- CSVFetcher实现`KLineFetcher`接口
- 可通过`FetcherFactory`注册和获取
- 与现有回测流程兼容

### US-03: 作为用户
**我想要** CSV数据回测结果能保存到数据库并在Web界面查看
**以便于** 分析回测表现、对比不同策略和参数组合

**验收标准**:
- 支持`--save-to-db`参数保存回测结果到数据库
- 回测结果存储到`BacktestResult`表
- 订单详情存储到`BacktestOrder`表
- 可在`/backtest/results/`页面查看完整回测结果
- 支持查看权益曲线、量化指标和订单列表

---

## 3. 功能需求

### 3.1 核心功能

#### F-01: CSV文件解析器
- 解析币安标准12列K线CSV格式
- 支持无表头CSV文件
- 列映射：timestamp, open, high, low, close, volume（其他列忽略）

#### F-02: CSVFetcher数据获取器
- ��现`KLineFetcher`抽象接口
- 支持`fetch()`方法按时间范围获取数据
- 支持`supports_interval()`检查周期支持

#### F-03: 工厂注册集成
- 注册新的market_type: `csv_local`
- 通过`FetcherFactory.create('csv_local')`创建实例
- 支持配置参数传递（文件路径、周期）

#### F-04: 时间范围过滤
- 支持`start_time`、`end_time`参数
- 按时间戳毫秒级精度过滤
- 返回时间正序排列的K线列表

#### F-05: 回测结果持久化
- 与现有`--save-to-db`参数兼容
- 回测结果存储到`BacktestResult`模型
- 订单详情存储到`BacktestOrder`模型
- 支持权益曲线和量化指标的完整存储

#### F-06: Web界面查看
- 复用现有`/backtest/results/`页面
- 支持查看CSV数据源回测的完整结果
- 显示回测配置、权益曲线、量化指标
- 显示订单列表（买入/卖出时间、价格、盈亏）

### 3.2 数据格式

**输入CSV格式（币安标准）**:
```
timestamp,open,high,low,close,volume,close_time,quote_volume,trades,taker_buy_volume,taker_buy_quote_volume,ignore
1764547200000000,2991.25,2991.25,2991.25,2991.25,0.0621,1764547200999999,185.76,4,0.0,0.0,0
```

**注意**: CSV中timestamp为微秒（1s数据），需转换为毫秒

**输出StandardKLine**:
```python
StandardKLine(
    timestamp=1764547200000,  # 毫秒
    open=2991.25,
    high=2991.25,
    low=2991.25,
    close=2991.25,
    volume=0.0621
)
```

### 3.3 配置方式

通过回测配置JSON文件指定CSV数据源：

```json
{
  "project_name": "csv_backtest",
  "data_source": {
    "type": "csv_local",
    "csv_path": "/path/to/ETHUSDT-1s-2025-12.csv",
    "interval": "1s"
  },
  "symbol": "ETHUSDT",
  "date_range": {
    "start": "2025-12-01",
    "end": "2025-12-31"
  }
}
```

---

## 4. 技术约束

### 4.1 性能要求
- **加载策略**: 全量加载到内存（用户选择）
- **数据量**: 支持单文件最大300万行（约1个月1s数据）
- **解析时间**: 全量加载<30秒

### 4.2 兼容性要求
- 继承`KLineFetcher`抽象基类
- 返回`List[StandardKLine]`标准格式
- 支持现有回测命令`run_strategy_backtest`

### 4.3 文件格式要求
- 支持UTF-8编码CSV
- 支持无表头或有表头格式
- 支持标准币安数据导出格式

---

## 5. 接口设计

### 5.1 CSVFetcher类

```python
class CSVFetcher(KLineFetcher):
    """CSV文件K线数据获取器"""

    def __init__(
        self,
        csv_path: str,
        interval: str = '1s',
        market_type: str = 'csv_local'
    ):
        """
        Args:
            csv_path: CSV文件绝对路径
            interval: K线周期（1s/1m）
            market_type: 市场类型标识
        """
        pass

    @property
    def market_type(self) -> str:
        """返回 'csv_local'"""
        pass

    def fetch(
        self,
        symbol: str,
        interval: str,
        limit: int = 500,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[StandardKLine]:
        """从CSV加载K线数据"""
        pass

    def supports_interval(self, interval: str) -> bool:
        """支持 1s, 1m 周期"""
        pass
```

### 5.2 FetcherFactory扩展

```python
# 注册CSV Fetcher
FetcherFactory.register('csv_local', CSVFetcher)

# 使用示例
fetcher = FetcherFactory.create(
    'csv_local',
    csv_path='/path/to/data.csv',
    interval='1s'
)
```

---

## 6. 验收标准

### 6.1 功能验收
- [ ] 成功解析1s K线CSV文件
- [ ] 成功解析1m K线CSV文件
- [ ] 时间戳正确转换（微秒→毫秒）
- [ ] 支持时间范围过滤
- [ ] 与FetcherFactory集成成功

### 6.2 性能验收
- [ ] 268万行1s数据加载<30秒
- [ ] 内存占用合理（<2GB）

### 6.3 兼容性验收
- [ ] 回测命令可使用CSV数据源
- [ ] DDPS计算可使用CSV数据
- [ ] 现有策略适配器无需修改

### 6.4 回测结果持久化验收
- [ ] `--save-to-db`参数正常工作
- [ ] BacktestResult记录创建成功
- [ ] BacktestOrder记录创建成功
- [ ] 权益曲线数据完整
- [ ] 量化指标（17个P0指标）计算正确

### 6.5 Web界面验收
- [ ] `/backtest/results/`页面正常显示CSV回测结果
- [ ] 回测详情页显示完整信息
- [ ] 订单列表显示买入/卖出时间和价格
- [ ] 盈亏统计正确

---

## 7. 里程碑

| 阶段 | 内容 | 状态 |
|------|------|------|
| P1 | 需求定义+澄清 | ✅ 完成 |
| P4 | 架构设计 | 待开始 |
| P5 | 开发规划 | 待开始 |
| P6 | 开发实现 | 待开始 |
| P7 | 代码审查 | 待开始 |

---

## 8. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 大文件内存溢出 | 高 | 监控内存使用，提供文件大小限制 |
| 时间戳格式不一致 | 中 | 自动检测并转换时间戳单位 |
| CSV格式变体 | 低 | 支持有/无表头两种格式 |

---

## 9. 相关文档

- 架构文档: `docs/iterations/024-ddps-multi-market-support/architecture.md`
- 数据源基类: `ddps_z/datasources/base.py`
- 工厂类: `ddps_z/datasources/fetcher_factory.py`
