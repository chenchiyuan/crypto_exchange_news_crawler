# Implementation Plan: 自动网格交易系统

**Branch**: `004-auto-grid-trading` | **Date**: 2025-11-28 | **Spec**: [solution-proposal-v2.md](./solution-proposal-v2.md)

---

## Summary

基于VP-Squeeze四峰分析识别的支撑/压力区间，实现自动网格交易系统（Paper Trading模式）。系统包含Scanner模块（识别S/R区间）和GridBot模块（执行网格交易）。

**核心特性**:
- ✅ 复用现有VP-Squeeze分析器
- ✅ 价格进入S/R区间自动开启网格
- ✅ 模拟订单撮合（Paper Trading）
- ✅ 简单止损控制（10%）
- ✅ 手动配置参数

---

## Technical Context

**Language/Version**: Python 3.8+
**Primary Dependencies**: Django 4.2.8, PostgreSQL 14+
**Storage**: PostgreSQL (生产) / SQLite (开发)
**Testing**: pytest
**Target Platform**: Linux server
**Project Type**: Django应用（单体架构）
**Performance Goals**:
  - Scanner: 每4小时运行，10秒内完成
  - GridBot: 每分钟轮询，200ms内完成单次检查
  - 数据库查询: < 50ms

**Constraints**:
  - 单币种监控（BTC优先）
  - Paper Trading模式（无真实交易所连接）
  - 手动参数配置

**Scale/Scope**:
  - 初期支持1-2个币种
  - 每个策略最多10层网格
  - 最大仓位1000 USDT

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 核心原则验证

| 原则 | 验证 | 说明 |
|------|------|------|
| **简单至上** | ✅ PASS | 单体Django架构，避免微服务复杂性 |
| **借鉴现有代码** | ✅ PASS | 复用VP-Squeeze、K线服务、API客户端 |
| **小步提交** | ✅ PASS | 4个阶段，每阶段独立可测试 |
| **务实主义** | ✅ PASS | 跳过回测框架，专注功能实现 |
| **模块化与状态隔离** | ✅ PASS | Scanner和GridBot通过数据库通信 |
| **参数可追溯** | ✅ PASS | StrategyConfig表记录所有参数版本 |

### 量化系统特定验证

| 要求 | 状态 | 说明 |
|------|------|------|
| **回测优先** | ⚠️ DEFERRED | 用户要求本期跳过，延后到下期 |
| **风险控制第一** | ✅ PASS | 10%止损，最大仓位限制 |
| **渐进式部署** | ✅ PASS | Paper Trading → 下期回测 → 下下期实盘 |

**Justification for DEFERRED**: 用户明确要求本期专注功能实现，Paper Trading可作为前向测试积累数据。

---

## Project Structure

### Documentation (this feature)

```text
specs/004-auto-grid-trading/
├── IMPLEMENTATION_PLAN.md       # This file
├── solution-proposal-v2.md      # Approved solution
└── (将在各阶段生成)
    ├── data-model.md            # Phase 1 output
    ├── api-contracts.md         # Phase 1 output
    └── deployment-guide.md      # Phase 4 output
```

### Source Code (repository root)

```text
grid_trading/                    # 🆕 新增Django应用
├── __init__.py
├── models.py                    # 4个核心模型
│   ├── GridZone
│   ├── GridStrategy
│   ├── GridOrder
│   └── StrategyConfig
├── management/
│   └── commands/
│       ├── scanner.py           # Scanner管理命令
│       └── gridbot.py           # GridBot管理命令
├── services/
│   ├── order_simulator.py      # 模拟订单撮合引擎
│   ├── risk_manager.py          # 风险管理器
│   └── config_loader.py         # 配置加载器
├── admin.py                     # Django Admin界面
├── migrations/                  # 数据库迁移
└── tests/                       # 单元测试

config/
└── grid_trading.yaml            # 🆕 策略参数配置

vp_squeeze/                      # ✅ 复用现有模块
├── services/
│   ├── four_peaks_analyzer.py
│   ├── binance_kline_service.py
│   └── multi_timeframe_analyzer.py

monitor/                         # ✅ 复用现有模块
├── api_clients/
│   └── binance.py               # 价格查询（不含下单）

tests/
└── grid_trading/                # 🆕 新增测试
    ├── test_scanner.py
    ├── test_gridbot.py
    ├── test_order_simulator.py
    └── test_risk_manager.py
```

**Structure Decision**: 选择单一Django项目结构，新增`grid_trading`应用包含所有网格交易逻辑。复用现有`vp_squeeze`和`monitor`模块，避免重复开发。

---

## Phase 0: 项目初始化

**目标**: 搭建项目基础结构，确保开发环境就绪

**状态**: ✅ 已完成 (2025-11-28)

**验收标准**:
- [x] 创建`grid_trading` Django应用
- [x] 数据库迁移就绪（4个模型表创建成功）
- [x] 测试框架配置完成（pytest可运行）
- [x] 配置文件加载逻辑验证通过

**测试**:
```bash
# 测试数据库迁移
python manage.py makemigrations grid_trading
python manage.py migrate

# 测试配置加载
python manage.py shell
>>> from grid_trading.services.config_loader import load_config
>>> config = load_config('btc')
>>> assert config['symbol'] == 'BTCUSDT'
```

---

## Phase 1: Scanner模块实现

**目标**: 复用VP-Squeeze分析器，实现S/R区间识别和存储

**状态**: ✅ 已完成 (2025-11-28)

**验收标准**:
- [x] Scanner管理命令可执行：`python manage.py scanner --symbol btc`
- [x] GridZone表正确写入4个区间（S1/S2/R1/R2）
- [x] 区间过期机制正常（4小时后自动失效）
- [x] 支持多币种（btc/eth）

**测试**:
```python
# tests/grid_trading/test_scanner.py

def test_scanner_identifies_zones():
    """测试Scanner能否正确识别S/R区间"""
    call_command('scanner', symbol='btc')

    zones = GridZone.objects.filter(symbol='BTCUSDT', is_active=True)
    assert zones.count() == 4  # S1/S2/R1/R2

    support_zones = zones.filter(zone_type='support')
    assert support_zones.count() == 2

def test_zone_expiration():
    """测试区间过期机制"""
    # 创建过期区间
    old_zone = GridZone.objects.create(
        symbol='BTCUSDT',
        zone_type='support',
        price_low=49000,
        price_high=49500,
        expires_at=timezone.now() - timedelta(hours=1)
    )

    call_command('scanner', symbol='btc')

    old_zone.refresh_from_db()
    assert not old_zone.is_active  # 应被标记为失效
```

**关键文件**:
- `grid_trading/management/commands/scanner.py`
- `grid_trading/models.py` (GridZone模型)
- `tests/grid_trading/test_scanner.py`

**状态**: 未开始

---

## Phase 2: 网格交易核心逻辑

**目标**: 实现GridBot管理命令，包含入场判断、订单布置、模拟撮合

**状态**: ✅ 已完成 (2025-11-28)

**验收标准**:
- [x] GridBot可作为守护进程运行：`python manage.py gridbot --symbol btc`
- [x] 价格进入支撑区能自动启动做多网格
- [x] 网格订单正确布置（上下各10层）
- [x] 模拟订单撮合逻辑正确（价格触及=成交）
- [x] 成交后自动补单（买单成交→上方补卖单）

**测试**:
```python
# tests/grid_trading/test_gridbot.py

def test_entry_zone_detection():
    """测试入场区间检测"""
    # 创建支撑区间
    zone = GridZone.objects.create(
        symbol='BTCUSDT',
        zone_type='support',
        price_low=49000,
        price_high=49500,
        is_active=True
    )

    # 模拟价格进入区间
    current_price = 49200

    bot = GridBot('btc')
    detected_zone = bot.check_entry_zone(current_price)

    assert detected_zone == zone

def test_grid_order_placement():
    """测试网格订单布置"""
    strategy = GridStrategy.objects.create(
        symbol='BTCUSDT',
        strategy_type='long',
        grid_step_pct=Decimal('0.008'),
        grid_levels=10,
        order_size=Decimal('0.01'),
        entry_price=Decimal('49200')
    )

    bot = GridBot('btc')
    bot.place_grid_orders(strategy, Decimal('49200'))

    buy_orders = GridOrder.objects.filter(strategy=strategy, order_type='buy')
    sell_orders = GridOrder.objects.filter(strategy=strategy, order_type='sell')

    assert buy_orders.count() == 10  # 下方10层
    assert sell_orders.count() == 10  # 上方10层

    # 验证价格梯度
    first_buy = buy_orders.order_by('price').first()
    assert first_buy.price < Decimal('49200')

def test_order_simulation():
    """测试订单模拟撮合"""
    strategy = GridStrategy.objects.create(
        symbol='BTCUSDT',
        strategy_type='long',
        grid_step_pct=Decimal('0.008'),
        grid_levels=5,
        order_size=Decimal('0.01'),
        entry_price=Decimal('50000')
    )

    # 创建买单
    buy_order = GridOrder.objects.create(
        strategy=strategy,
        order_type='buy',
        price=Decimal('49000'),
        quantity=Decimal('0.01'),
        status='pending'
    )

    # 模拟价格下跌触发成交
    bot = GridBot('btc')
    bot.check_orders(strategy, current_price=Decimal('48900'))

    buy_order.refresh_from_db()
    assert buy_order.status == 'filled'
    assert buy_order.filled_at is not None

    # 验证自动补卖单
    new_sell_order = GridOrder.objects.filter(
        strategy=strategy,
        order_type='sell',
        status='pending'
    ).first()
    assert new_sell_order is not None
    assert new_sell_order.price > buy_order.price
```

**关键文件**:
- `grid_trading/management/commands/gridbot.py`
- `grid_trading/services/order_simulator.py`
- `grid_trading/models.py` (GridStrategy, GridOrder模型)
- `tests/grid_trading/test_gridbot.py`
- `tests/grid_trading/test_order_simulator.py`

**状态**: 未开始

---

## Phase 3: 风险管理与监控

**目标**: 实现止损监控、最大仓位限制、异常处理

**状态**: ✅ 已完成 (2025-11-28)

**验收标准**:
- [x] 止损逻辑正确（亏损达10%立即平仓）
- [x] 最大仓位限制生效（超过1000 USDT拒绝开仓）
- [x] 异常情况自动告警（API失败、数据库异常）
- [x] Admin后台可查看策略状态和订单记录

**测试**:
```python
# tests/grid_trading/test_risk_manager.py

def test_stop_loss_trigger():
    """测试止损触发"""
    strategy = GridStrategy.objects.create(
        symbol='BTCUSDT',
        strategy_type='long',
        grid_step_pct=Decimal('0.008'),
        grid_levels=10,
        order_size=Decimal('0.01'),
        entry_price=Decimal('50000'),
        stop_loss_pct=Decimal('0.10'),
        status='active'
    )

    # 创建已成交的买单
    GridOrder.objects.create(
        strategy=strategy,
        order_type='buy',
        price=Decimal('50000'),
        quantity=Decimal('0.1'),
        status='filled'
    )

    # 模拟价格大幅下跌
    risk_manager = RiskManager()
    current_price = Decimal('44000')  # 下跌12%

    risk_manager.check_stop_loss(strategy, current_price)

    strategy.refresh_from_db()
    assert strategy.status == 'stopped'

    # 验证所有挂单已撤销
    pending_orders = GridOrder.objects.filter(
        strategy=strategy,
        status='pending'
    )
    assert pending_orders.count() == 0

def test_max_position_limit():
    """测试最大仓位限制"""
    config = StrategyConfig.objects.create(
        symbol='BTCUSDT',
        config_name='btc_default',
        max_position_usdt=Decimal('1000')
    )

    # 尝试超过限额的开仓
    bot = GridBot('btc')

    with pytest.raises(PositionLimitExceeded):
        bot.start_grid_strategy(
            symbol='BTCUSDT',
            zone=mock_zone,
            current_price=Decimal('50000'),
            requested_size=Decimal('1500')  # 超过1000限额
        )
```

**关键文件**:
- `grid_trading/services/risk_manager.py`
- `grid_trading/admin.py`
- `tests/grid_trading/test_risk_manager.py`

**状态**: 未开始

---

## Phase 4: 配置、部署与文档

**目标**: 完善配置系统、systemd服务、监控日志、部署文档

**状态**: ✅ 已完成 (2025-11-28)

**验收标准**:
- [x] YAML配置加载正常（`config/grid_trading.yaml`）
- [x] systemd服务可正常启动和重启
- [x] 日志轮转配置完成（logrotate）
- [x] Admin后台完整可用
- [x] 部署文档编写完成

**测试**:
```bash
# 测试systemd服务
sudo systemctl start gridbot@btc
sudo systemctl status gridbot@btc
journalctl -u gridbot@btc -f

# 测试配置加载
python manage.py shell
>>> from grid_trading.services.config_loader import load_config
>>> config = load_config('btc')
>>> assert config['atr_multiplier'] == 0.8

# 测试日志
tail -f logs/grid_trading.log
```

**部署文档内容**:
1. 环境准备（PostgreSQL, Python虚拟环境）
2. 数据库初始化
3. 配置文件说明
4. systemd服务配置
5. 监控和告警设置
6. 常见问题排查

**关键文件**:
- `config/grid_trading.yaml`
- `scripts/systemd/gridbot@.service`
- `scripts/systemd/scanner@.service`
- `scripts/systemd/scanner@.timer`
- `scripts/systemd/strategy-monitor@.service`
- `scripts/logrotate/grid_trading`
- `specs/004-auto-grid-trading/deployment-guide.md`

---

## Complexity Tracking

本项目复杂度较低，符合"简单至上"原则，无需特别记录。

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (初始化)
  ↓
Phase 1 (Scanner) ← 独立，可并行开发
  ↓
Phase 2 (GridBot) ← 依赖Phase 1的GridZone模型
  ↓
Phase 3 (风险管理) ← 依赖Phase 2的GridStrategy和GridOrder
  ↓
Phase 4 (部署文档) ← 依赖所有前序阶段完成
```

### 并行机会

- Phase 1和Phase 2的测试可同时编写
- Phase 3的RiskManager可在Phase 2开发中期提前实现
- Phase 4的文档可在各阶段完成后逐步积累

---

## Rollout Strategy

### 开发环境验证（本地）

```bash
# 1. 初始化项目
python manage.py migrate
python manage.py createsuperuser

# 2. 运行Scanner
python manage.py scanner --symbol btc

# 3. 手动测试GridBot（短暂运行）
python manage.py gridbot --symbol btc --duration 60  # 运行60秒后停止

# 4. 检查Admin后台
python manage.py runserver
# 访问 http://localhost:8000/admin
```

### 类生产环境测试（VPS）

```bash
# 1. 部署代码
git clone ...
cd crypto_exchange_news_crawler
git checkout 004-auto-grid-trading

# 2. 配置systemd服务
sudo cp scripts/systemd/gridbot@.service /etc/systemd/system/
sudo systemctl enable gridbot@btc
sudo systemctl start gridbot@btc

# 3. 监控日志
journalctl -u gridbot@btc -f

# 4. 定期检查
# 每日查看Admin后台的策略状态和盈亏
```

### 生产部署（延后）

本期仅Paper Trading，无真实交易，暂不涉及生产部署。

---

## Risk Mitigation

### 技术风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| **数据库锁竞争** | 中 | 中 | 使用PostgreSQL行锁，减少事务时间 |
| **模拟撮合不准** | 高 | 低 | Paper Trading允许误差，后期对比真实数据优化 |
| **GridBot崩溃** | 中 | 中 | systemd自动重启，添加健康检查 |

### 业务风险

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|---------|
| **S/R识别错误** | 中 | 高 | 止损保护（10%），定期人工复盘 |
| **无信号确认接飞刀** | 高 | 高 | 严格止损，初期小仓位运行 |
| **参数不优导致亏损** | 中 | 中 | Paper Trading积累数据，手动调参 |

---

## Success Metrics

### 技术指标

- [ ] Scanner成功率 > 95%（每天运行6次，至少5次成功）
- [ ] GridBot稳定性 > 99%（运行24小时无崩溃）
- [ ] 数据库查询延迟 < 50ms（P95）
- [ ] 订单撮合准确率 > 90%（与真实成交对比）

### 业务指标（Paper Trading）

- [ ] 运行30天无严重Bug
- [ ] 至少完成10次完整网格周期（开仓→成交→平仓）
- [ ] 止损触发率 < 30%（说明S/R识别有效）
- [ ] 模拟盈亏记录完整（可追溯每笔订单）

---

## Notes

- 本期开发重点：**功能完整性** > **参数最优化**
- Paper Trading是为了验证系统逻辑，不追求高收益
- 严格遵守小步提交原则，每个Phase完成后立即提交
- 遇到阻塞问题遵守"3次尝试规则"

---

**计划创建时间**: 2025-11-28
**实际完成时间**: 2025-11-28
**当前状态**: ✅ 所有阶段已完成
