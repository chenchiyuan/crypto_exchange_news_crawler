# PRD: 多策略组合回测系统

> **迭代编号**: 017
> **创建时间**: 2026-01-07
> **状态**: Confirmed (已确认)
> **优先级**: P0

---

## 1. 背景与目标

### 1.1 背景

当前回测系统采用单策略模式，每次回测只能运行一个策略（如DDPS-Z策略1-4）。用户希望能够：

1. **组合多策略**：在同一回测项目中运行多个独立策略
2. **统一资金管理**：多策略共享同一资金池
3. **灵活配置**：每个策略可配置独立的买入条件和多个卖出条件（止盈/止损）
4. **项目化管理**：回测配置可保存为JSON文件，支持复用

### 1.2 核心价值

| 核心假设 | 验证方式 |
|---------|---------|
| 多策略组合能提升整体收益风险比 | 对比单策略vs组合策略的夏普率 |
| JSON配置提升回测效率 | 用户反馈：配置复用率 |
| 共享资金管理更真实模拟实盘 | 资金利用率统计 |

### 1.3 MVP目标

- 支持JSON配置文件定义回测项目
- 支持加载2-5个策略组合运行
- 支持每个策略配置多个卖出条件
- 共享资金池管理
- CLI命令支持：`python manage.py run_strategy_backtest --config project.json`

---

## 2. 用户故事

### US-001: 定义回测项目
**作为** 量化交易者
**我希望** 通过JSON文件定义回测项目配置
**以便** 复用和分享回测配置

### US-002: 组合多策略
**作为** 量化交易者
**我希望** 在一个回测项目中组合多个买入策略
**以便** 测试策略组合效果

### US-003: 配置卖出条件
**作为** 量化交易者
**我希望** 为每个策略配置多个卖出条件（止盈、止损、EMA回归等）
**以便** 优化出场时机

### US-004: 共享资金管理
**作为** 量化交易者
**我希望** 多策略共享同一资金池
**以便** 真实模拟实盘资金分配

---

## 3. 功能需求

### 3.1 JSON配置结构（草案）

```json
{
  "project_name": "DDPS-Z多策略组合测试",
  "description": "测试策略1+2+3组合效果",
  "version": "1.0",

  "backtest_config": {
    "symbol": "ETHUSDT",
    "interval": "4h",
    "market_type": "futures",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_cash": 10000,
    "commission_rate": 0.001
  },

  "capital_management": {
    "mode": "shared",
    "position_size_mode": "fixed",
    "position_size": 100,
    "max_positions": 10
  },

  "strategies": [
    {
      "id": "strategy_1",
      "name": "EMA斜率做多",
      "type": "ddps-z",
      "enabled": true,
      "entry": {
        "strategy_id": 1
      },
      "exits": [
        {
          "type": "ema_reversion",
          "params": {"ema_period": 25}
        },
        {
          "type": "stop_loss",
          "params": {"percentage": 5}
        },
        {
          "type": "take_profit",
          "params": {"percentage": 10}
        }
      ]
    },
    {
      "id": "strategy_2",
      "name": "惯性下跌做多",
      "type": "ddps-z",
      "enabled": true,
      "entry": {
        "strategy_id": 2
      },
      "exits": [
        {
          "type": "ema_reversion",
          "params": {"ema_period": 25}
        },
        {
          "type": "trailing_stop",
          "params": {"trigger": 5, "trail": 2}
        }
      ]
    }
  ]
}
```

### 3.2 核心功能列表

| ID | 功能 | 优先级 | 说明 |
|----|------|--------|------|
| F1 | JSON配置解析器 | P0 | 解析并验证回测项目配置 |
| F2 | 多策略加载器 | P0 | 动态加载多个策略实例 |
| F3 | 卖出条件组合器 | P0 | 支持多种卖出条件组合 |
| F4 | 共享资金管理器 | P0 | 多策略共享资金池 |
| F5 | CLI参数扩展 | P0 | --config 参数支持 |
| F6 | 策略Mixin基类 | P1 | 可复用的策略组件 |
| F7 | 配置验证器 | P1 | JSON Schema验证 |

---

## 4. 决策点（已确认）

### DP-1: 多策略信号冲突处理 ✅

**问题**: 当多个策略同时产生买入信号时，如何处理？

**决定**: **方案A - 全部执行**
- 每个信号都创建独立订单（资金允许的情况下）
- 理由：最简单，MVP优先

---

### DP-2: 卖出条件触发逻辑 ✅

**问题**: 多个卖出条件配置后，如何决定触发顺序？

**决定**: **方案B - 最先满足**
- 检查所有条件，最先满足时间的触发
- 理由：更符合实盘逻辑

---

### DP-3: 策略与订单的关联 ✅

**问题**: 订单应该如何关联到触发它的策略？

**决定**: **方案A - 订单标记策略ID**
- 每个订单记录触发策略ID
- 理由：统一管理，标记来源

---

### DP-4: 资金分配模式 ✅

**问题**: 共享资金池如何分配给多策略？

**决定**: **方案A - 先到先得**
- 信号先到先分配资金
- 理由：MVP简单实现

---

### DP-5: 卖出条件类型支持范围 ✅

**问题**: MVP阶段支持哪些卖出条件类型？

**决定**: **方案A - 基础3种**
- ema_reversion, stop_loss, take_profit
- 理由：MVP聚焦核心

---

### DP-6: 配置文件位置 ✅

**问题**: JSON配置文件应放在哪里？

**决定**: **方案C - 用户指定**
- CLI传入任意路径
- 理由：最灵活

---

## 5. 非功能需求

### 5.1 性能
- 支持同时加载5个以上策略
- 回测10年数据（约22000根4H K线）耗时 < 60秒

### 5.2 可扩展性
- 新策略类型只需实现接口
- 新卖出条件类型可插拔添加

### 5.3 兼容性
- 兼容现有单策略模式（无--config参数时）
- 兼容现有BacktestResult数据结构

---

## 6. 架构影响

### 6.1 需要修改的模块

| 模块 | 修改类型 | 说明 |
|------|----------|------|
| `interfaces/strategy.py` | 扩展 | 添加卖出条件接口 |
| `core/strategy_adapter.py` | 重构 | 支持多策略编排 |
| `core/unified_order_manager.py` | 扩展 | 添加策略ID字段 |
| `management/commands/run_strategy_backtest.py` | 扩展 | 添加--config参数 |
| `models/order.py` | 扩展 | 添加strategy_id字段 |

### 6.2 新增模块

| 模块 | 说明 |
|------|------|
| `core/project_loader.py` | JSON配置加载器 |
| `core/multi_strategy_adapter.py` | 多策略适配器 |
| `exits/` | 卖出条件模块目录 |
| `exits/base.py` | 卖出条件基类 |
| `exits/ema_reversion.py` | EMA回归卖出 |
| `exits/stop_loss.py` | 止损卖出 |
| `exits/take_profit.py` | 止盈卖出 |

---

## 7. 风险与依赖

### 7.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 多策略信号同步复杂度高 | 逻辑错误导致回测结果不准确 | 单元测试覆盖关键路径 |
| JSON配置格式变更 | 旧配置不兼容 | 版本号+迁移脚本 |

### 7.2 依赖

- 迭代015（做空策略）已完成
- 迭代016（K线图增强）已完成

---

## 8. 验收标准

### AC-1: 配置加载
- [ ] 能正确加载符合Schema的JSON配置
- [ ] 配置验证失败时给出明确错误信息

### AC-2: 多策略执行
- [ ] 支持2-5个策略同时运行
- [ ] 每个策略独立产生买入信号
- [ ] 策略信号按时间排序执行

### AC-3: 卖出条件
- [ ] 支持EMA回归卖出
- [ ] 支持止损卖出（百分比）
- [ ] 支持止盈卖出（百分比）
- [ ] 多条件按最先满足触发

### AC-4: 资金管理
- [ ] 共享资金池正确扣减和回收
- [ ] 资金不足时跳过新订单
- [ ] 资金守恒（初始 = 最终现金 + 持仓 + 已实现盈亏）

### AC-5: 兼容性
- [ ] 无--config参数时行为不变
- [ ] 回测结果可保存到数据库

---

## 附录

### A. 相关文档

- [现有IStrategy接口](../../strategy_adapter/interfaces/strategy.py)
- [现有StrategyAdapter](../../strategy_adapter/core/strategy_adapter.py)
- [DDPSZStrategy实现](../../strategy_adapter/adapters/ddpsz_adapter.py)

### B. 术语表

| 术语 | 说明 |
|------|------|
| Entry | 入场/买入条件 |
| Exit | 出场/卖出条件 |
| Mixin | 可组合的功能模块 |
| Trailing Stop | 移动止损 |
