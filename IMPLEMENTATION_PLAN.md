# 合约市场指标实施计划

**方案**: 独立市场指标模型 + 批量优化获取
**开始时间**: 2025-11-11
**预计完成时间**: 8-12小时

---

## 阶段 1: 数据库模型与迁移
**目标**: 创建 FuturesMarketIndicators 模型，完成数据库迁移，配置 Admin 基础展示
**预计耗时**: 1-2小时

### 具体任务
1. ✅ 创建 `FuturesMarketIndicators` 模型
   - OneToOne 关联到 FuturesContract
   - 添加8个市场指标字段：
     - open_interest (持仓量)
     - volume_24h (24小时交易量)
     - funding_rate (当前资金费率)
     - funding_rate_annual (年化资金费率)
     - next_funding_time (下次结算时间)
     - funding_interval_hours (资金费率间隔)
     - funding_rate_cap (费率上限)
     - funding_rate_floor (费率下限)
   - 添加 last_updated 时间戳

2. ✅ 运行数据库迁移
   - `python manage.py makemigrations`
   - `python manage.py migrate`

3. ✅ 配置 Admin 后台
   - 创建 `FuturesMarketIndicatorsAdmin`
   - 在 `FuturesContractAdmin` 中添加 inline 展示
   - 添加自定义展示方法（格式化数值）

### 验收标准
- [x] FuturesMarketIndicators 模型创建完成
- [x] Migration 成功执行，数据库表创建
- [x] Admin 后台可以查看和管理市场指标
- [x] 通过 Django shell 可以创建测试数据

### 测试
```python
# 在 Django shell 中测试
from monitor.models import Exchange, FuturesContract, FuturesMarketIndicators
from decimal import Decimal
from django.utils import timezone

# 创建测试数据
exchange = Exchange.objects.first()
contract = FuturesContract.objects.create(
    exchange=exchange,
    symbol='TESTUSDT',
    current_price=Decimal('50000'),
    contract_type='perpetual'
)

indicators = FuturesMarketIndicators.objects.create(
    futures_contract=contract,
    open_interest=Decimal('1000000'),
    volume_24h=Decimal('50000000'),
    funding_rate=Decimal('0.0001'),
    funding_rate_annual=Decimal('10.95'),
    next_funding_time=timezone.now() + timedelta(hours=8),
    funding_interval_hours=8,
    funding_rate_cap=Decimal('0.03'),
    funding_rate_floor=Decimal('-0.03')
)

# 验证关联查询
assert contract.market_indicators == indicators
assert indicators.futures_contract == contract
```

**状态**: 未开始

---

## 阶段 2: API客户端升级 - Bybit优先
**目标**: 升级API客户端以获取市场指标数据，优先实现Bybit（最简单）
**预计耗时**: 3-4小时

### 具体任务

#### 2.1 更新 BaseFuturesClient 基类
- 添加 `fetch_contracts_with_indicators()` 抽象方法
- 定义标准返回数据格式

#### 2.2 实现 BybitFuturesClient
- 使用 `/v5/market/tickers` 一次性获取所有数据
- 解析响应数据，提取所有指标
- 添加数据验证和错误处理
- 编写单元测试

#### 2.3 实现 BinanceFuturesClient
- 实现并行请求优化：
  - `/fapi/v1/ticker/24hr` (24小时统计)
  - `/fapi/v1/premiumIndex` (资金费率)
  - `/fapi/v1/fundingInfo` (资金费率配置)
- 使用 ThreadPoolExecutor 并行请求
- 合并多个端点的数据
- 添加限流和重试机制
- 编写单元测试

#### 2.4 实现 HyperliquidFuturesClient
- 使用 info endpoint 获取数据
- 请求类型：`meta` 和 `allMids`
- 解析 Hyperliquid 特殊格式
- 处理固定1小时间隔
- 编写单元测试

### 验收标准
- [x] 所有客户端实现 `fetch_contracts_with_indicators()` 方法
- [x] Bybit 可以一次调用获取所有指标数据
- [x] Binance 并行请求耗时 < 5秒
- [x] Hyperliquid 正确解析数据
- [x] 所有客户端返回标准化格式
- [x] 单元测试覆盖率 > 80%

### 测试
```python
# 测试 Bybit 客户端
from monitor.api_clients.bybit import BybitFuturesClient

client = BybitFuturesClient()
contracts = client.fetch_contracts_with_indicators()

assert len(contracts) > 0
for contract in contracts[:5]:  # 测试前5个
    assert 'symbol' in contract
    assert 'current_price' in contract
    assert 'open_interest' in contract
    assert 'volume_24h' in contract
    assert 'funding_rate' in contract
    assert 'next_funding_time' in contract
    assert 'funding_interval_hours' in contract
    print(f"✓ {contract['symbol']}: OI={contract['open_interest']}, Vol={contract['volume_24h']}")
```

**状态**: 未开始

---

## 阶段 3: 服务层与计算逻辑
**目标**: 实现 FuturesFetcherService 的市场指标保存逻辑和年化资金费率计算
**预计耗时**: 2-3小时

### 具体任务

#### 3.1 实现年化资金费率计算
- 创建 `_calculate_annual_funding_rate()` 方法
- 公式：`(当前费率 / 间隔小时数 × 24) × 365`
- 处理不同交易所的间隔时间：
  - Binance: 8小时
  - Bybit: 8小时
  - Hyperliquid: 1小时
- 添加边界条件处理
- 编写单元测试

#### 3.2 实现批量保存逻辑
- 创建 `_save_contract_and_indicators()` 方法
- 使用 `update_or_create` 批量操作
- 分离合约和指标的保存逻辑
- 添加事务处理确保数据一致性
- 添加详细日志记录

#### 3.3 更新 FuturesFetcherService 主流程
- 修改 `update_all_exchanges()` 方法
- 调用新的 `fetch_contracts_with_indicators()`
- 集成年化费率计算
- 保持向后兼容性
- 添加性能监控日志

#### 3.4 错误处理与降级
- 如果指标获取失败，仍保存基础合约数据
- 添加部分失败的容错机制
- 记录详细错误日志

### 验收标准
- [x] 年化资金费率计算正确（验证3个交易所）
- [x] 批量保存逻辑可靠（事务性）
- [x] 性能满足目标（< 10秒更新所有交易所）
- [x] 错误处理完善（部分失败不影响整体）
- [x] 单元测试通过

### 测试
```python
# 测试年化资金费率计算
from monitor.services.futures_fetcher import FuturesFetcherService
from decimal import Decimal

service = FuturesFetcherService()

# Binance: 8小时间隔
annual_rate = service._calculate_annual_funding_rate(
    current_rate=Decimal('0.0001'),
    interval_hours=8
)
# 预期: (0.0001 / 8 * 24) * 365 = 10.95%
assert abs(annual_rate - Decimal('10.95')) < Decimal('0.01')

# Hyperliquid: 1小时间隔
annual_rate = service._calculate_annual_funding_rate(
    current_rate=Decimal('0.01'),  # 1% 每小时
    interval_hours=1
)
# 预期: (0.01 / 1 * 24) * 365 = 8760%
assert abs(annual_rate - Decimal('8760')) < Decimal('1')

# 端到端测试
service.update_all_exchanges()
# 验证数据库中的指标
from monitor.models import FuturesMarketIndicators
indicators_count = FuturesMarketIndicators.objects.count()
assert indicators_count > 0
print(f"✓ 成功保存 {indicators_count} 个市场指标")
```

**状态**: 未开始

---

## 阶段 4: Admin展示优化与通知集成
**目标**: 优化Admin后台展示，集成通知系统
**预计耗时**: 2-3小时

### 具体任务

#### 4.1 优化 Admin 展示
- 在 `FuturesContractAdmin` 添加市场指标列：
  - `open_interest_display`: 格式化持仓量（加千分位）
  - `volume_24h_display`: 格式化交易量
  - `funding_rate_display`: 显示当前和年化费率
  - `next_funding_display`: 倒计时显示
- 添加过滤器：
  - 按资金费率范围过滤
  - 按交易量排序
- 添加颜色标记：
  - 正资金费率：绿色
  - 负资金费率：红色
  - 高交易量：蓝色加粗

#### 4.2 创建 FuturesMarketIndicatorsInline
- 在合约详情页内联显示所有指标
- 格式化显示数值和时间
- 添加刷新按钮（可选）

#### 4.3 集成通知系统
- 修改 `FuturesNotifierService`
- 在新币上线通知中添加市场指标：
  - 初始持仓量
  - 初始资金费率
  - 预估年化收益
- 更新通知模板

#### 4.4 添加 Management Command
- 创建 `python manage.py update_market_indicators`
- 支持单独更新指标而不检测新币
- 用于定时任务（每10分钟）

### 验收标准
- [x] Admin 后台美观清晰地展示所有指标
- [x] 指标格式化正确（千分位、百分比等）
- [x] 通知消息包含市场指标
- [x] Management Command 可独立运行
- [x] 端到端测试通过

### 测试
```bash
# 测试 Management Command
python manage.py update_market_indicators

# 检查日志输出
# 预期: 显示每个交易所的更新结果和耗时

# 测试 Admin 展示
# 1. 访问 /admin/monitor/futurescontract/
# 2. 验证列表页显示市场指标列
# 3. 点击某个合约，验证详情页 inline 显示
# 4. 验证颜色标记正确

# 测试通知
python manage.py test_futures_notification --contract-id <new_contract_id>
# 验证通知内容包含市场指标
```

**状态**: 未开始

---

## 阶段 5: 测试与文档
**目标**: 完整的端到端测试，编写使用文档
**预计耗时**: 1-2小时

### 具体任务

#### 5.1 端到端测试
- 创建 `tests/test_market_indicators_e2e.py`
- 测试完整流程：
  1. 从API获取数据
  2. 保存到数据库
  3. 计算年化费率
  4. Admin 展示
  5. 通知推送
- 使用 mock 避免真实API调用

#### 5.2 性能测试
- 测试3个交易所的获取耗时
- 验证符合性能目标（< 10秒）
- 生成性能报告

#### 5.3 编写文档
- 更新 README
- 添加 API 使用示例
- 记录配置说明
- 添加故障排查指南

#### 5.4 代码审查与重构
- 自我审查代码
- 运行 linter 和格式化
- 确保测试覆盖率 > 80%
- 清理临时代码和注释

### 验收标准
- [x] 端到端测试通过
- [x] 性能测试符合目标
- [x] 文档完整清晰
- [x] 代码质量检查通过
- [x] 无 TODO 或 FIXME 残留

### 测试
```bash
# 运行所有测试
python manage.py test monitor.tests.test_market_indicators_e2e

# 运行性能测试
python manage.py test monitor.tests.test_performance

# 代码质量检查
ruff check monitor/
black monitor/

# 测试覆盖率
coverage run --source='monitor' manage.py test
coverage report
# 预期: > 80%
```

**状态**: 未开始

---

## 完成检查清单

### 功能完整性
- [ ] 所有3个交易所都能获取市场指标
- [ ] 年化资金费率计算正确
- [ ] Admin 后台展示完善
- [ ] 通知包含市场指标
- [ ] Management Command 正常工作

### 质量保证
- [ ] 单元测试覆盖率 > 80%
- [ ] 端到端测试通过
- [ ] 性能满足目标（< 10秒）
- [ ] 无 Linter 警告
- [ ] 代码格式化完成

### 文档与部署
- [ ] README 更新
- [ ] Migration 文件提交
- [ ] 提交信息清晰
- [ ] 代码已 push
- [ ] 删除此 IMPLEMENTATION_PLAN.md

---

## 当前进度追踪

**当前阶段**: 阶段 1
**整体进度**: 0%
**已完成阶段**: 0/5
**预计剩余时间**: 8-12小时

---

## 注意事项

1. **API限流**: 使用 ratelimit 装饰器，避免触发交易所限流
2. **数据一致性**: 使用数据库事务确保合约和指标一起保存
3. **错误恢复**: 部分失败不应影响整体流程
4. **向后兼容**: 保持现有功能不受影响
5. **性能监控**: 每个阶段记录详细的耗时日志

---

**最后更新**: 2025-11-11
**更新人**: Claude Code
