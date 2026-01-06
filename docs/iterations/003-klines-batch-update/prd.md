# PRD - K线批量更新增强

**迭代编号**: 003
**迭代名称**: K线批量更新增强
**创建日期**: 2024-12-24
**版本**: v1.0.0

---

## 📋 目录

1. [产品概述](#产品概述)
2. [核心价值](#核心价值)
3. [功能需求](#功能需求)
4. [非功能需求](#非功能需求)
5. [范围边界](#范围边界)
6. [验收标准](#验收标准)

---

## 产品概述

### 背景
当前 `update_klines` 命令只支持单个交易对更新，需要手动逐个指定 `--symbol` 参数。在巨量诱多/弃盘检测系统（迭代002）中，需要监控500+个活跃合约的K线数据，手动更新效率极低。

### 目标用户
- **量化开发者**：需要批量更新K线数据用于回测和策略开发
- **系统运维人员**：需要自动化更新K线数据，减少手动操作
- **数据分析师**：需要完整的K线历史数据用于分析

### 使用场景

#### 场景1：定时任务批量更新
**角色**：系统运维人员
**目标**：每小时自动更新所有合约的最新K线数据
**操作流程**：
```bash
# Crontab配置
0 * * * * cd /project && python manage.py update_klines --interval 1h
```

#### 场景2：新合约首次数据初始化
**角色**：量化开发者
**目标**：新合约上线后，批量获取所有合约的历史数据
**操作流程**：
```bash
# 强制更新所有合约的最近100条K线
python manage.py update_klines --interval 4h --limit 100 --force
```

#### 场景3：单个合约增量更新（兼容现有用法）
**角色**：开发者
**目标**：只更新特定交易对的数据
**操作流程**：
```bash
# 保持现有用法
python manage.py update_klines --symbol BTCUSDT --interval 4h
```

---

## 前置条件

### 数据依赖

批量更新功能依赖 `FuturesContract` 模型作为交易对数据源，需要预先初始化合约数据。

#### ⚠️ 重要：首次使用前必须初始化合约数据

**初始化命令**：
```bash
# 方式1: 初始化所有交易所的合约数据（推荐）
python manage.py fetch_futures --all

# 方式2: 初始化特定交易所的合约数据
python manage.py fetch_futures --exchange binance
```

**为什么需要FuturesContract**：
1. **多交易所支持**: 区分不同交易所的同名合约（如币安BTCUSDT vs Hyperliquid BTCUSDT）
2. **状态管理**: 只更新活跃合约（`status='active'`），跳过已下线的合约
3. **新币发现**: 通过 `first_seen` 字段检测新上线的合约
4. **统一数据源**: 与迭代002的巨量诱多检测系统共享合约列表

#### 错误提示

如果未初始化合约数据，执行批量更新时会看到：
```
⚠️  未找到任何活跃合约数据。
请先运行以下命令初始化合约数据:
  python manage.py fetch_futures --all
或指定特定交易所:
  python manage.py fetch_futures --exchange binance
```

#### 单个交易对更新不受影响

如果使用 `--symbol` 参数指定单个交易对，**无需**初始化 FuturesContract 数据：
```bash
# 不依赖FuturesContract，可直接使用
python manage.py update_klines --symbol BTCUSDT --interval 4h
```

---

## 核心价值

### MVP核心价值（一句话）
**增强 `update_klines` 命令，支持批量、增量和强制更新K线数据，减少手动操作，提高数据更新效率。**

### 核心收益
1. **效率提升**：从手动更新500次 → 自动批量更新1次，节省时间99%
2. **数据完整性**：自动扫描所有合约，避免遗漏
3. **灵活性**：支持全量/增量/强制三种更新模式

---

## 功能需求

### P0 功能（Must Have - 本次实现）

#### P0-F1: 默认批量更新所有合约
**优先级**: P0
**功能描述**：当不指定 `--symbol` 参数时，自动扫描所有 `status=active` 的 FuturesContract 并批量更新
**输入**：
- `--interval`（必填）：K线周期，如 `1h`、`4h`、`1d`
- `--limit`（可选）：每个交易对获取的K线数量，默认2000（4h周期约一年数据）

**输出**：
- 控制台显示每个交易对的更新进度和结果
- 最终显示统计信息（成功/失败数量）

**业务规则**：
1. 从 `monitor.FuturesContract` 查询所有 `status='active'` 的合约
2. 按 `symbol` 字母顺序逐个更新
3. 每次更新间隔 0.1秒（避免API限流）
4. 单个交易对失败不影响其他交易对

**验收标准**：
```bash
# 执行命令
python manage.py update_klines --interval 4h

# 预期输出
正在更新所有活跃合约的K线数据 (interval=4h, limit=2000)...
找到 520 个活跃合约

[1/520] AAVEUSDT: ✓ 新增 1850 条
[2/520] ADAUSDT: ✓ 新增 1920 条
[3/520] ALGOUSDT: ✗ 错误: Connection timeout
...
[520/520] ZRXUSDT: ✓ 新增 1800 条

=== 更新完成 ===
  成功: 518 个
  失败: 2 个
  总耗时: 12分23秒
```

---

#### P0-F2: 支持单个交易对更新（向后兼容）
**优先级**: P0
**功能描述**：保持现有 `--symbol` 参数功能，确保向后兼容
**输入**：
- `--symbol`（必填）：交易对代码，如 `BTCUSDT`
- `--interval`（必填）：K线周期
- `--limit`（可选）：获取数量，默认2000

**业务规则**：
1. 如果指定了 `--symbol`，则只更新该交易对
2. 行为与现有命令完全一致

**验收标准**：
```bash
# 执行命令
python manage.py update_klines --symbol BTCUSDT --interval 4h

# 预期输出
更新数据: BTCUSDT 4h...
✓ 更新完成: 新增1850条
```

---

#### P0-F3: 增量更新机制
**优先级**: P0
**功能描述**：查询数据库中已有的最新K线，只获取缺失的部分
**实现逻辑**：
1. 查询 `KLine` 表，获取该交易对+周期的最新 `open_time`
2. 如果数据库为空，获取最近 `limit` 条
3. 如果数据库有数据，调用 `update_latest_data(limit)`（已有实现）

**业务规则**：
- 增量更新由 `DataFetcher.update_latest_data()` 自动实现
- `_save_klines()` 方法已通过 `open_time` 唯一性检查防止重复

**验收标准**：
```python
# 测试场景1: 数据库为空
# 执行: python manage.py update_klines --symbol BTCUSDT --interval 4h --limit 2000
# 预期: 新增2000条K线

# 测试场景2: 数据库已有330天数据（1980条4h K线）
# 执行: python manage.py update_klines --symbol BTCUSDT --interval 4h --limit 2000
# 预期: 新增0-20条（取决于币安最新数据）
```

---

#### P0-F4: 强制更新模式
**优先级**: P0
**功能描述**：通过 `--force` 参数强制更新全部数据，忽略已有数据
**输入**：
- `--force`（可选）：布尔标志，默认False

**实现逻辑**：
1. 如果 `--force=True`，删除该交易对+周期的所有K线数据
2. 然后重新获取 `limit` 条数据

**业务规则**：
- 删除数据前需要确认（生产环境风险）
- 删除使用 `KLine.objects.filter(...).delete()`

**验收标准**：
```bash
# 执行命令
python manage.py update_klines --symbol BTCUSDT --interval 4h --limit 2000 --force

# 预期输出
⚠️  强制更新模式：将删除 BTCUSDT 4h 的所有现有数据
已删除 1950 条历史数据
正在重新获取 2000 条K线...
✓ 更新完成: 新增2000条
```

---

#### P0-F5: 错误处理与容错
**优先级**: P0
**功能描述**：批量更新时，单个交易对失败不影响其他交易对
**错误类型**：
1. API请求超时
2. 网络连接失败
3. 数据格式错误
4. 数据库写入失败

**业务规则**：
1. 使用 `try-except` 捕获单个交易对的异常
2. 记录错误日志（symbol + 错误信息）
3. 继续处理下一个交易对
4. 最终输出失败交易对列表

**验收标准**：
```bash
# 模拟场景：部分交易对API失败

# 预期输出
[1/10] BTCUSDT: ✓ 新增 5 条
[2/10] ETHUSDT: ✗ 错误: Connection timeout
[3/10] BNBUSDT: ✓ 新增 3 条
...

=== 更新完成 ===
  成功: 8 个
  失败: 2 个
  失败列表:
    - ETHUSDT: Connection timeout
    - LTCUSDT: Database write error
```

---

#### P0-F6: 进度显示与统计
**优先级**: P0
**功能描述**：批量更新时显示实时进度和最终统计信息
**显示内容**：
- 总合约数量
- 当前进度（N/总数）
- 每个交易对的更新结果（成功/失败）
- 最终统计（成功数、失败数、耗时）

**业务规则**：
- 使用 `self.stdout.write()` 输出进度
- 使用 `self.style.SUCCESS()` 和 `self.style.ERROR()` 着色

**验收标准**：参见 P0-F1 的预期输出

---

### P1 功能（Should Have - 暂不实现）

#### P1-F1: 并发更新
**优先级**: P1
**功能描述**：使用多线程/多进程并发更新，提高效率
**延后理由**：增加复杂度，API限流风险高，先验证同步模式效果

#### P1-F2: 数据完整性检查
**优先级**: P1
**功能描述**：更新后自动检查数据缺口并补全
**延后理由**：现有机制已足够，优先级低

---

## 非功能需求

### 性能要求

| 指标 | 目标值 | 备注 |
|------|--------|------|
| 单个交易对更新时间 | ≤ 5秒 | 包含API请求和数据库写入（2000条数据） |
| 批量更新500个交易对总耗时 | ≤ 30分钟 | 平均每个3秒（含分批API请求） |
| API调用频率 | ≤ 10次/秒 | 避免触发币安限流（1200次/分钟） |
| 数据库批量插入效率 | ≥ 500条/秒 | 使用 bulk_create |

### 可靠性要求

| 要求 | 说明 |
|------|------|
| 单点故障容错 | 单个交易对失败不影响其他 |
| 数据一致性 | 通过 `open_time` 唯一性约束防止重复 |
| 异常恢复 | 失败的交易对可通过 `--symbol` 单独重试 |

### 可维护性要求

| 要求 | 说明 |
|------|------|
| 代码复用 | 最大化复用现有 DataFetcher 服务 |
| 日志记录 | 使用 logging 记录关键操作和错误 |
| 参数验证 | 参数错误时给出清晰的错误提示 |

---

## 范围边界

### In-Scope（本次实现）
- ✅ P0-F1: 默认批量更新所有合约
- ✅ P0-F2: 支持单个交易对更新（向后兼容）
- ✅ P0-F3: 增量更新机制
- ✅ P0-F4: 强制更新模式
- ✅ P0-F5: 错误处理与容错
- ✅ P0-F6: 进度显示与统计

### Out-of-Scope（不在本次范围）
- ❌ 多线程/异步并发更新
- ❌ 数据完整性自动检查和补全
- ❌ 实时数据推送
- ❌ Web界面管理
- ❌ 历史数据回填（使用现有 fetch_historical_data）

---

## 验收标准

### 功能验收

| 测试场景 | 测试步骤 | 预期结果 |
|----------|----------|----------|
| **批量更新所有合约** | `python manage.py update_klines --interval 4h` | 更新所有active合约，显示进度和统计 |
| **单个交易对更新** | `python manage.py update_klines --symbol BTCUSDT --interval 4h` | 只更新BTCUSDT，行为与现有命令一致 |
| **增量更新** | 数据库已有数据，执行更新命令 | 只新增缺失的K线，无重复数据 |
| **强制更新** | `python manage.py update_klines --symbol BTCUSDT --interval 4h --force` | 删除旧数据，重新获取 |
| **错误容错** | 模拟网络故障（部分交易对失败） | 失败交易对不影响其他，输出失败列表 |
| **参数验证** | 不指定 `--interval` | 显示参数错误提示 |

### 性能验收

| 指标 | 测试方法 | 通过标准 |
|------|----------|----------|
| 批量更新总耗时 | 更新500个交易对，记录耗时 | ≤ 30分钟 |
| API调用频率 | 监控API调用日志 | ≤ 10次/秒 |
| 数据无重复 | 查询数据库，检查 `open_time` 重复 | 重复率 = 0% |

---

## 附录

### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--symbol` | str | 否 | None | 指定交易对，不指定则更新所有 |
| `--interval` | str | 是 | - | K线周期（1h/4h/1d） |
| `--limit` | int | 否 | 2000 | 每个交易对获取的K线数量（4h约一年） |
| `--force` | bool | 否 | False | 强制更新（删除旧数据） |

### 示例命令

```bash
# 示例1: 批量更新所有合约的4h K线（默认获取2000条）
python manage.py update_klines --interval 4h

# 示例2: 批量更新所有合约的1h K线，每个获取5000条
python manage.py update_klines --interval 1h --limit 5000

# 示例3: 单个交易对更新（向后兼容）
python manage.py update_klines --symbol BTCUSDT --interval 4h

# 示例4: 强制更新单个交易对（重置数据）
python manage.py update_klines --symbol ETHUSDT --interval 4h --limit 2000 --force

# 示例5: 批量强制更新所有合约
python manage.py update_klines --interval 4h --force
```

---

**文档版本**: v1.0.0
**最后更新**: 2024-12-24
**相关文档**:
- 初始化文档: `docs/iterations/003-klines-batch-update/init.md`
- 功能点清单: `docs/iterations/003-klines-batch-update/function-points.md`（待生成）
