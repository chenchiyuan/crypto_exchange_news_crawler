# 功能点清单: DDPS监控服务策略16升级

## 文档信息

| 属性 | 值 |
|------|-----|
| 迭代编号 | 038 |
| 创建日期 | 2026-01-12 |
| PRD文档 | prd.md |

---

## 功能点列表

### FP-038-001: PriceStatus数据模型扩展

**优先级**: P0 (MVP必需)

**描述**: 扩展PriceStatus数据类，增加策略16相关字段

**字段清单**:

| 字段 | 类型 | 描述 | 计算方式 |
|------|------|------|----------|
| order_price | Decimal | 策略16挂单价格 | `min(P5,close,(P5+mid)/2)×(1-0.1%)` |
| adx | float | ADX指标值 | DDPSCalculator已有 |
| beta | float | 贝塔值 | DDPSCalculator已有 |
| cycle_duration_hours | float | 周期连续时长 | DDPSCalculator已有 |
| cycle_distribution | Dict[str, float] | 42周期占比 | 新增计算 |
| holdings | List[HoldingInfo] | 持仓订单 | Strategy16回测 |

**新增数据类**:

```python
@dataclass
class HoldingInfo:
    """持仓订单信息"""
    order_id: str           # 订单ID
    buy_price: Decimal      # 买入价格
    buy_timestamp: int      # 买入时间戳(ms)
    holding_hours: float    # 持仓时长(小时)
```

**验收标准**:
- [ ] PriceStatus包含所有新增字段
- [ ] HoldingInfo数据类定义完整
- [ ] 字段类型正确

---

### FP-038-002: Strategy16Runner集成

**优先级**: P0 (MVP必需)

**描述**: 将Strategy16Runner集成到DDPSMonitorService

**实现要点**:
1. 在DDPSMonitorService.__init__中初始化Strategy16Runner
2. 在monitor()方法中调用strategy16_runner.run()获取回测结果
3. 从回测结果提取holdings、pending_order、statistics

**接口设计**:

```python
def _run_strategy16(
    self,
    symbol: str,
    interval: str,
    market_type: str
) -> Optional[Dict]:
    """
    运行策略16获取回测结果

    Returns:
        {
            'holdings': [...],      # 未平仓订单
            'pending_order': {...}, # 当前挂单
            'statistics': {...}     # 统计数据
        }
    """
```

**验收标准**:
- [ ] Strategy16Runner正确初始化
- [ ] 回测结果与detail页面一致
- [ ] holdings数据准确

---

### FP-038-003: 周期占比统计

**优先级**: P0 (MVP必需)

**描述**: 计算最近42根K线的周期状态分布

**计算逻辑**:
```python
def calculate_cycle_distribution(
    cycle_phases: List[str],
    window: int = 42
) -> Dict[str, float]:
    """
    计算周期占比

    Args:
        cycle_phases: 周期状态列表（最新在后）
        window: 统计窗口大小，默认42

    Returns:
        {
            'bull_strong': 30.0,    # 强势上涨占比%
            'bull_warning': 10.0,   # 上涨预警占比%
            'consolidation': 40.0,  # 震荡占比%
            'bear_warning': 10.0,   # 下跌预警占比%
            'bear_strong': 10.0     # 强势下跌占比%
        }
    """
```

**验收标准**:
- [ ] 统计窗口为42根K线
- [ ] 5种周期状态都有统计
- [ ] 占比总和为100%
- [ ] 百分比保留整数

---

### FP-038-004: 买入信号检测升级

**优先级**: P0 (MVP必需)

**描述**: 使用策略16逻辑检测最新K线的买入信号

**触发条件**:
- 策略16挂单条件满足（当前价格接近P5区域）
- 未达到最大持仓数量

**输出字段**:
- symbol: 交易对
- price: 当前价格
- order_price: 策略16挂单价格
- cycle_phase: 当前周期

**验收标准**:
- [ ] 买入信号基于策略16逻辑
- [ ] 包含挂单价格信息
- [ ] 与detail页面pending_order一致

---

### FP-038-005: 卖出信号检测升级

**优先级**: P0 (MVP必需)

**描述**: 使用策略16 EMA状态止盈检测卖出信号

**退出类型**:
| 周期状态 | 退出条件 | exit_type |
|----------|----------|-----------|
| 强势上涨 | EMA7下穿EMA25 | ema_cross_bull |
| 强势下跌 | High突破EMA25 | ema_break_bear |
| 震荡下跌 | High突破EMA99 | ema_break_consolidation |
| 震荡上涨 | 涨幅>=2% | limit_take_profit |

**持仓来源**: Strategy16Runner回测结果的holdings

**验收标准**:
- [ ] 卖出检测基于EMA状态止盈
- [ ] 持仓来自策略16回测
- [ ] 退出类型正确标注

---

### FP-038-006: 推送消息格式升级

**优先级**: P0 (MVP必需)

**描述**: 升级format_push_message方法，生成新格式消息

**格式规范**:

```
时间: YYYY-MM-DD HH:MM

买入信号 (N个):
  - {SYMBOL} @ {PRICE} ({CYCLE_LABEL})

卖出信号 (N个):
  - 订单#{ID} {SYMBOL}: {EXIT_LABEL} @ {EXIT_PRICE} (开仓{OPEN_PRICE}, {PROFIT_RATE}%)

上涨预警: {SYMBOLS}
下跌预警: {SYMBOLS}

价格状态:
  {SYMBOL}: {PRICE} ({CYCLE_LABEL})
    P5={P5} P95={P95}
    惯性范围: {INERTIA_LOWER}~{INERTIA_UPPER}
    概率: P{PROBABILITY}
    挂单价格: {ORDER_PRICE}
    所处周期: {CYCLE} - ADX({ADX}) - 贝塔({BETA}) - 连续{DURATION}小时
    最近42周期占比: {DISTRIBUTION}
    持仓订单 ({N}个):
      {BUY_TIME} @ {BUY_PRICE} → 持仓{HOLDING_HOURS}小时
```

**验收标准**:
- [ ] 标题格式正确
- [ ] 所有新增字段正确展示
- [ ] 周期占比格式正确
- [ ] 持仓订单按时间倒序（最新在前）

---

### FP-038-007: ddps_monitor命令更新

**优先级**: P0 (MVP必需)

**描述**: 更新ddps_monitor命令使用策略16

**变更点**:
1. 默认使用策略16
2. 新增--strategy参数支持切换策略（可选）
3. dry-run模式显示新格式预览

**验收标准**:
- [ ] 命令默认使用策略16
- [ ] dry-run显示完整新格式
- [ ] 推送成功

---

## 功能依赖关系

```
FP-038-001 (数据模型)
    ↓
FP-038-002 (Strategy16集成)
    ↓
FP-038-003 (周期占比) + FP-038-004 (买入检测) + FP-038-005 (卖出检测)
    ↓
FP-038-006 (消息格式)
    ↓
FP-038-007 (命令更新)
```

---

## 实现优先级

| 优先级 | 功能点 | 原因 |
|--------|--------|------|
| P0 | FP-038-001~007 | MVP核心功能 |

所有功能点均为P0优先级，需要在本迭代完成。
