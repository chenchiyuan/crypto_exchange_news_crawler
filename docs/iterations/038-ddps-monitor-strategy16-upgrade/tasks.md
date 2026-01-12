# 任务计划: DDPS监控服务策略16升级

## 文档信息

| 属性 | 值 |
|------|-----|
| 迭代编号 | 038 |
| 创建日期 | 2026-01-12 |
| 架构文档 | architecture.md |
| 总任务数 | 10 |

---

## 任务总览

```
阶段1: 数据模型扩展
├── TASK-038-001: 新增HoldingInfo数据类
└── TASK-038-002: 扩展PriceStatus数据类

阶段2: 核心功能实现
├── TASK-038-003: 集成Strategy16Runner
└── TASK-038-004: 实现周期占比统计

阶段3: 信号检测升级
├── TASK-038-005: 升级买入信号检测
├── TASK-038-006: 升级卖出信号检测
└── TASK-038-007: 升级价格状态获取

阶段4: 输出与命令
├── TASK-038-008: 升级推送消息格式
└── TASK-038-009: 更新ddps_monitor命令

阶段5: 验证
└── TASK-038-010: 集成测试与验证
```

---

## 阶段1: 数据模型扩展

### TASK-038-001: 新增HoldingInfo数据类

**状态**: 🔲 待开始

**描述**: 在ddps_z/models.py中新增HoldingInfo数据类，用于表示持仓订单信息

**修改文件**:
- `ddps_z/models.py`

**实现步骤**:
1. 在models.py中新增HoldingInfo数据类定义
2. 包含字段: order_id, buy_price, buy_timestamp, holding_hours

**代码规范**:
```python
@dataclass
class HoldingInfo:
    """
    持仓订单信息

    用于DDPS监控推送中展示当前持仓状态。

    Attributes:
        order_id: 订单ID
        buy_price: 买入价格
        buy_timestamp: 买入时间戳(毫秒)
        holding_hours: 持仓时长(小时)
    """
    order_id: str
    buy_price: Decimal
    buy_timestamp: int
    holding_hours: float
```

**验收标准**:
- [ ] HoldingInfo类定义完整
- [ ] 字段类型正确
- [ ] 文档字符串完整

**依赖**: 无

---

### TASK-038-002: 扩展PriceStatus数据类

**状态**: 🔲 待开始

**描述**: 扩展PriceStatus数据类，增加策略16相关字段

**修改文件**:
- `ddps_z/models.py`

**实现步骤**:
1. 在PriceStatus中新增以下字段（使用Optional默认值None保持向后兼容）:
   - order_price: Optional[Decimal] - 策略16挂单价格
   - adx: Optional[float] - ADX指标值
   - beta: Optional[float] - 贝塔值
   - cycle_duration_hours: Optional[float] - 周期连续时长
   - inertia_lower: Optional[Decimal] - 惯性下界
   - inertia_upper: Optional[Decimal] - 惯性上界
   - cycle_distribution: Optional[Dict[str, float]] - 42周期占比
   - holdings: Optional[List[HoldingInfo]] - 持仓订单列表

**验收标准**:
- [ ] 所有新字段已添加
- [ ] 使用Optional保持向后兼容
- [ ] 字段文档完整

**依赖**: TASK-038-001

---

## 阶段2: 核心功能实现

### TASK-038-003: 集成Strategy16Runner到DDPSMonitorService

**状态**: 🔲 待开始

**描述**: 在DDPSMonitorService中集成Strategy16Runner，实现策略16回测能力

**修改文件**:
- `ddps_z/services/ddps_monitor_service.py`

**实现步骤**:
1. 导入Strategy16Runner
2. 在__init__中初始化strategy16_runner（可选依赖注入）
3. 新增_run_strategy16私有方法:
   - 计算最近3个月的start_time
   - 调用strategy16_runner.run()
   - 返回holdings和pending_order

**代码规范**:
```python
def _run_strategy16(
    self,
    symbol: str,
    interval: str,
    market_type: str
) -> Optional[Dict]:
    """
    运行策略16获取回测结果（限制最近3个月）

    Args:
        symbol: 交易对
        interval: K线周期
        market_type: 市场类型

    Returns:
        {
            'holdings': List[Dict],      # 未平仓订单
            'pending_order': Dict,       # 当前挂单
            'statistics': Dict           # 统计数据
        }
    """
    from datetime import datetime, timedelta
    from ddps_z.services.strategy16_runner import Strategy16Runner

    # 计算最近3个月的起始时间
    end_time = datetime.now()
    start_time = end_time - timedelta(days=90)
    start_ts = int(start_time.timestamp() * 1000)
    end_ts = int(end_time.timestamp() * 1000)

    # 运行策略16
    runner = Strategy16Runner()
    result = runner.run(
        symbol=symbol,
        interval=interval,
        market_type=market_type,
        start_time=start_ts,
        end_time=end_ts
    )

    return result
```

**验收标准**:
- [ ] Strategy16Runner正确初始化
- [ ] 回测时间范围限制为最近3个月
- [ ] 返回数据结构正确

**依赖**: TASK-038-002

---

### TASK-038-004: 实现周期占比统计

**状态**: 🔲 待开始

**描述**: 在DDPSMonitorService中实现_calculate_cycle_distribution私有方法

**修改文件**:
- `ddps_z/services/ddps_monitor_service.py`

**实现步骤**:
1. 新增_calculate_cycle_distribution私有方法
2. 统计最近42根K线的周期状态分布
3. 返回各周期占比（百分比，整数）

**代码规范**:
```python
def _calculate_cycle_distribution(
    self,
    cycle_phases: List[str],
    window: int = 42
) -> Dict[str, float]:
    """
    计算周期占比

    Args:
        cycle_phases: 周期状态列表（时间升序，最新在后）
        window: 统计窗口大小，默认42

    Returns:
        各周期状态的占比（百分比）
        {
            'bull_strong': 30.0,
            'bull_warning': 10.0,
            'consolidation': 40.0,
            'bear_warning': 10.0,
            'bear_strong': 10.0
        }
    """
    from collections import Counter

    # 取最近window根K线
    recent_phases = cycle_phases[-window:] if len(cycle_phases) >= window else cycle_phases

    if not recent_phases:
        return {}

    # 统计各周期数量
    counter = Counter(recent_phases)
    total = len(recent_phases)

    # 计算占比
    distribution = {}
    for phase in ['bull_strong', 'bull_warning', 'consolidation', 'bear_warning', 'bear_strong']:
        count = counter.get(phase, 0)
        distribution[phase] = round(count / total * 100)

    return distribution
```

**验收标准**:
- [ ] 统计窗口为42根K线
- [ ] 5种周期状态都有统计
- [ ] 占比为整数百分比

**依赖**: 无

---

## 阶段3: 信号检测升级

### TASK-038-005: 升级买入信号检测

**状态**: 🔲 待开始

**描述**: 升级get_buy_signals方法，使用策略16的pending_order作为买入信号来源

**修改文件**:
- `ddps_z/services/ddps_monitor_service.py`

**实现步骤**:
1. 新增_convert_pending_order_to_buy_signal私有方法
2. 修改get_buy_signals方法:
   - 遍历_indicators_cache
   - 对每个symbol调用_run_strategy16获取pending_order
   - 将pending_order转换为BuySignal格式

**代码规范**:
```python
def _convert_pending_order_to_buy_signal(
    self,
    symbol: str,
    pending_order: Dict,
    cycle_phase: str,
    current_price: Decimal
) -> Optional[BuySignal]:
    """
    将策略16的pending_order转换为BuySignal格式
    """
    if not pending_order:
        return None

    order_price = Decimal(str(pending_order.get('order_price', 0)))
    if order_price <= 0:
        return None

    return BuySignal(
        symbol=symbol,
        price=current_price,
        cycle_phase=cycle_phase,
        p5=Decimal(str(pending_order.get('p5', 0))),
        trigger_condition=f"策略16挂单 @ {order_price:.2f}"
    )
```

**验收标准**:
- [ ] 买入信号来自策略16 pending_order
- [ ] BuySignal格式正确
- [ ] 包含挂单价格信息

**依赖**: TASK-038-003

---

### TASK-038-006: 升级卖出信号检测

**状态**: 🔲 待开始

**描述**: 升级get_exit_signals方法，基于策略16的holdings检测卖出信号

**修改文件**:
- `ddps_z/services/ddps_monitor_service.py`

**实现步骤**:
1. 修改get_exit_signals方法:
   - 从策略16结果获取已平仓订单（最新一根K线平仓的）
   - 转换为ExitSignal格式
2. 更新退出类型标签映射

**退出类型映射**:
```python
EXIT_LABELS = {
    'ema_cross_bull': 'EMA状态止盈(强势上涨)',
    'ema_break_bear': 'EMA状态止盈(强势下跌)',
    'ema_break_consolidation': 'EMA状态止盈(震荡下跌)',
    'limit_take_profit': '2%限价止盈(震荡上涨)',
    'stop_loss': '止损',
}
```

**验收标准**:
- [ ] 卖出信号基于策略16逻辑
- [ ] 退出类型标签正确
- [ ] 盈亏计算准确

**依赖**: TASK-038-003

---

### TASK-038-007: 升级价格状态获取

**状态**: 🔲 待开始

**描述**: 升级get_price_status方法，填充所有新增字段

**修改文件**:
- `ddps_z/services/ddps_monitor_service.py`

**实现步骤**:
1. 修改_calculate_symbol_indicators方法:
   - 调用_run_strategy16获取holdings和pending_order
   - 调用_calculate_cycle_distribution获取周期占比
   - 将所有新字段添加到返回字典
2. 修改get_price_status方法:
   - 使用扩展后的PriceStatus
   - 填充所有新增字段

**验收标准**:
- [ ] order_price正确（来自pending_order）
- [ ] adx/beta/cycle_duration_hours正确（来自DDPSCalculator）
- [ ] inertia_lower/inertia_upper正确
- [ ] cycle_distribution正确（42周期占比）
- [ ] holdings正确（转换为HoldingInfo列表）

**依赖**: TASK-038-003, TASK-038-004

---

## 阶段4: 输出与命令

### TASK-038-008: 升级推送消息格式

**状态**: 🔲 待开始

**描述**: 升级format_push_message方法，生成新格式的推送消息

**修改文件**:
- `ddps_z/services/ddps_monitor_service.py`

**实现步骤**:
1. 更新价格状态部分的格式化逻辑
2. 新增以下内容:
   - 挂单价格行
   - 所处周期详情行（ADX/贝塔/连续时长）
   - 42周期占比行
   - 持仓订单列表

**输出格式示例**:
```
价格状态:
  ETHUSDT: 3500.50 (上涨预警)
    P5=3400.00 P95=3700.00
    惯性范围: 3450.00~3550.00
    概率: P42
    挂单价格: 3380.12
    所处周期: 上涨预警 - ADX(30) - 贝塔(0.012) - 连续48小时
    最近42周期占比: 强势上涨(30%), 震荡(50%), 强势下跌(20%)
    持仓订单 (2个):
      01-10 08:00 @ 3200.00 → 持仓56小时
      01-08 16:00 @ 3100.00 → 持仓104小时
```

**验收标准**:
- [ ] 所有新增字段正确展示
- [ ] 周期占比格式正确
- [ ] 持仓订单按时间倒序（最新在前）
- [ ] 格式美观易读

**依赖**: TASK-038-007

---

### TASK-038-009: 更新ddps_monitor命令

**状态**: 🔲 待开始

**描述**: 更新ddps_monitor命令，确保使用策略16

**修改文件**:
- `ddps_z/management/commands/ddps_monitor.py`

**实现步骤**:
1. 确认默认使用策略16（无需添加新参数，Service已升级）
2. 更新命令帮助文档
3. 测试dry-run模式显示新格式

**验收标准**:
- [ ] 命令正常运行
- [ ] dry-run显示完整新格式
- [ ] 帮助文档更新

**依赖**: TASK-038-008

---

## 阶段5: 验证

### TASK-038-010: 集成测试与验证

**状态**: 🔲 待开始

**描述**: 执行完整的集成测试，验证所有功能

**测试步骤**:
1. **数据模型测试**:
   ```bash
   python -c "from ddps_z.models import HoldingInfo, PriceStatus; print('数据模型OK')"
   ```

2. **Dry-run测试**:
   ```bash
   python manage.py ddps_monitor --dry-run --market crypto_futures --interval 4h
   ```

3. **验证检查清单**:
   - [ ] 买入信号来自策略16
   - [ ] 卖出信号基于EMA状态止盈
   - [ ] 持仓订单与策略16一致
   - [ ] 挂单价格正确
   - [ ] 周期占比统计正确
   - [ ] 推送格式符合规范

**验收标准**:
- [ ] 所有测试通过
- [ ] dry-run输出正确
- [ ] 无错误日志

**依赖**: TASK-038-009

---

## 任务依赖图

```
TASK-038-001 (HoldingInfo)
    │
    ▼
TASK-038-002 (PriceStatus扩展)
    │
    ▼
TASK-038-003 (Strategy16集成) ◄──── TASK-038-004 (周期占比)
    │                                     │
    ├─────────────┬───────────────────────┤
    ▼             ▼                       ▼
TASK-038-005  TASK-038-006           TASK-038-007
(买入信号)    (卖出信号)             (价格状态)
    │             │                       │
    └─────────────┴───────────────────────┘
                  │
                  ▼
           TASK-038-008 (消息格式)
                  │
                  ▼
           TASK-038-009 (命令更新)
                  │
                  ▼
           TASK-038-010 (测试验证)
```

---

## 进度跟踪

| 任务ID | 描述 | 状态 | 完成时间 |
|--------|------|------|----------|
| TASK-038-001 | HoldingInfo数据类 | ✅ 已完成 | 2026-01-12 |
| TASK-038-002 | PriceStatus扩展 | ✅ 已完成 | 2026-01-12 |
| TASK-038-003 | Strategy16集成 | ✅ 已完成 | 2026-01-12 |
| TASK-038-004 | 周期占比统计 | ✅ 已完成 | 2026-01-12 |
| TASK-038-005 | 买入信号升级 | ✅ 已完成 | 2026-01-12 |
| TASK-038-006 | 卖出信号升级 | ✅ 已完成 | 2026-01-12 |
| TASK-038-007 | 价格状态升级 | ✅ 已完成 | 2026-01-12 |
| TASK-038-008 | 消息格式升级 | ✅ 已完成 | 2026-01-12 |
| TASK-038-009 | 命令更新 | ✅ 已完成 | 2026-01-12 |
| TASK-038-010 | 集成测试 | ✅ 已完成 | 2026-01-12 |

**状态图例**: 🔲 待开始 | 🔄 进行中 | ✅ 已完成
