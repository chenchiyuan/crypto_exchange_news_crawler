# 验收清单: DDPS多市场多周期支持

## 文档信息

| 属性 | 值 |
|------|-----|
| 迭代编号 | 024 |
| 版本 | 1.0 |
| 创建日期 | 2026-01-09 |

---

## 1. 功能验收

### 1.1 类型定义 (Phase 1)

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| StandardKLine | 包含 timestamp, open, high, low, close, volume | [ ] |
| MarketType枚举 | 包含 crypto_spot, crypto_futures, us_stock, a_stock, hk_stock | [ ] |
| MarketType.is_crypto() | 正确识别加密货币市场 | [ ] |
| Interval枚举 | 包含 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w | [ ] |
| Interval.to_hours() | 正确转换各周期为小时数 | [ ] |

### 1.2 数据源抽象层 (Phase 2)

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| KLineFetcher接口 | 定义完整的抽象方法 | [ ] |
| BinanceFetcher.fetch() | 成功获取Binance K线数据 | [ ] |
| BinanceFetcher(spot) | 支持现货市场 | [ ] |
| BinanceFetcher(futures) | 支持合约市场 | [ ] |
| FetcherFactory | 根据market_type返回正确Fetcher | [ ] |
| KLineRepository.load() | 从DB加载并转换为StandardKLine | [ ] |
| KLineRepository.save() | 将StandardKLine保存到DB | [ ] |
| 向后兼容 | 'futures' 自动映射为 'crypto_futures' | [ ] |

### 1.3 DDPS计算层 (Phase 3)

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| DDPSCalculator.calculate() | 只接收StandardKLine列表 | [ ] |
| DDPSCalculator | 不依赖数据库 | [ ] |
| interval_hours参数 | 正确传递给BetaCycleCalculator | [ ] |
| DDPSResult | 包含所有必要指标字段 | [ ] |
| 数据不足处理 | K线<180根时返回None | [ ] |
| DDPSMonitorService | 使用Repository加载数据 | [ ] |
| DDPSMonitorService | 使用Calculator计算指标 | [ ] |

### 1.4 配置与命令层 (Phase 4)

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 新配置格式 | 支持多市场配置 | [ ] |
| DDPSConfigParser | 正确解析配置 | [ ] |
| --market参数 | 支持切换市场类型 | [ ] |
| --interval参数 | 支持切换K线周期 | [ ] |
| 帮助文档 | 显示新参数说明 | [ ] |

---

## 2. 集成验收

### 2.1 端到端测试

| 测试场景 | 预期结果 | 状态 |
|----------|----------|------|
| `ddps_monitor --full` | 使用默认配置正常执行 | [ ] |
| `ddps_monitor --market crypto_spot` | 切换到现货市场 | [ ] |
| `ddps_monitor --interval 1h` | 使用1小时周期 | [ ] |
| `ddps_monitor --interval 1d` | 使用日线周期 | [ ] |
| 推送消息 | 格式正确，包含市场/周期信息 | [ ] |

### 2.2 向后兼容测试

| 测试场景 | 预期结果 | 状态 |
|----------|----------|------|
| 不带参数运行 | 使用默认配置(crypto_futures, 4h) | [ ] |
| 旧配置格式 | 自动识别并兼容 | [ ] |
| 现有API调用 | 保持正常工作 | [ ] |

---

## 3. 质量检查

### 3.1 代码质量

| 检查项 | 标准 | 状态 |
|--------|------|------|
| 类型注解 | 所有公共方法包含类型注解 | [ ] |
| 文档字符串 | 所有公共类/方法包含docstring | [ ] |
| 单一职责 | 每个类职责单一明确 | [ ] |
| 无硬编码 | 无硬编码的market_type/interval | [ ] |
| 导入规范 | 使用统一的导入路径 | [ ] |

### 3.2 测试覆盖

| 检查项 | 标准 | 状态 |
|--------|------|------|
| DDPSCalculator测试 | 覆盖不同interval场景 | [ ] |
| 边��条件测试 | 覆盖数据不足等边界情况 | [ ] |
| 单元测试通过 | 所有测试用例通过 | [ ] |

### 3.3 性能检查

| 检查项 | 标准 | 状态 |
|--------|------|------|
| 计算性能 | 与改造前一致，无明显下降 | [ ] |
| 内存占用 | 无内存泄漏 | [ ] |

---

## 4. 验收命令

### 4.1 基本功能验证

```bash
# 1. 运行单元测试
python manage.py test ddps_z.tests.test_ddps_calculator -v 2

# 2. 默认配置运行
python manage.py ddps_monitor --dry-run

# 3. 切换市场类型
python manage.py ddps_monitor --market crypto_spot --dry-run

# 4. 切换周期
python manage.py ddps_monitor --interval 1h --dry-run

# 5. 完整运行（含推送）
python manage.py ddps_monitor --full
```

### 4.2 代码检查

```bash
# 检查导入是否正常
python -c "from ddps_z.calculators import DDPSCalculator; print('OK')"
python -c "from ddps_z.datasources import KLineFetcher, BinanceFetcher, FetcherFactory, KLineRepository; print('OK')"
python -c "from ddps_z.models import StandardKLine, MarketType, Interval; print('OK')"

# 检查类型枚举
python -c "from ddps_z.models import Interval; print(Interval.to_hours('4h'))"  # 应输出 4.0
python -c "from ddps_z.models import Interval; print(Interval.to_hours('1d'))"  # 应输出 24.0
```

---

## 5. 验收签字

| 角色 | 签字 | 日期 |
|------|------|------|
| 开发者 | | |
| 审核者 | | |

---

## 6. 遗留问题

| 问题 | 影响 | 计划 |
|------|------|------|
| 股票数据源(P1) | 暂不支持us_stock/a_stock | 下个迭代实现 |
| 交易日历(P1) | 股票市场需要交易日判断 | 下个迭代实现 |
