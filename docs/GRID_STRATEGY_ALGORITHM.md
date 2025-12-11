# 网格交易策略算法文档

## 目录
- [一、概述](#一概述)
- [二、代币选择策略](#二代币选择策略)
- [三、网格范围计算算法](#三网格范围计算算法)
- [四、网格交易执行策略](#四网格交易执行策略)
- [五、关键参数说明](#五关键参数说明)

---

## 一、概述

本项目实现了基于成交量分析的动态网格交易系统,核心特点包括:

1. **智能代币筛选**: 通过多维指标评分体系筛选适合网格交易的代币
2. **动态网格范围**: 基于多周期成交量热力图动态计算支撑/压力位
3. **双向交易策略**: 同时做多做空,在支撑位开多单、压力位开空单
4. **风险控制**: 内置止损止盈机制和冷却期控制

---

## 二、代币选择策略

### 2.1 筛选流程

代币选择遵循**简化评分模型** (`SimpleScoring`),分为以下步骤:

#### **步骤1: 全市场扫描**
```python
# 文件: grid_trading/services/screening_engine.py (第83-100行)
```

- 从本地 `SymbolInfo` 表查询所有活跃的永续合约
- 不进行初筛过滤,所有合约都纳入分析
- 同时获取现货交易对列表用于判断是否有现货支持

#### **步骤2: 多维指标计算**
```python
# 文件: grid_trading/services/screening_engine.py (第296-378行)
# 文件: grid_trading/services/indicator_calculator.py
```

对每个代币计算以下指标:

**A. 波动率维度**
- **VDR (波动率-位移比)**: 衡量震荡性纯净度
  - 计算公式: `CIV / Displacement`
  - 数据源: 240根1分钟K线
  - 含义: 值越高表示震荡越强,趋势性越弱

- **KER (考夫曼效率比)**: 衡量价格移动效率
  - 计算公式: `Direction / Volatility`
  - 数据源: 最近10根K线
  - 含义: 值越低表示震荡越强

- **NATR (归一化ATR)**: 标准化波动率
  - 计算公式: `ATR(14) / Close × 100`
  - 数据源: 4小时K线

- **15分钟振幅累计**: 最近100根15分钟K线的振幅总和
  - 计算公式: `Σ (High - Low) / Close × 100`

**B. 趋势维度**
- **EMA99斜率**: 长期趋势方向
- **EMA20斜率**: 短期趋势方向
- **RSI(15m)**: 相对强弱指数

**C. 微观结构维度**
- **OVR (持仓量/成交量比)**: 杠杆拥挤度
  - 理想范围: 0.5-1.5

- **CVD背离**: 累积成交量差异背离检测
  - 熊市背离: 价格创新高,CVD未创新高

- **年化资金费率**: 基于历史资金费率计算年化值

**D. 辅助指标**
- **24小时交易量**: 从1440根1分钟K线计算
- **高点回落百分比**: 距离300根4小时K线最高点的回撤
- **价格分位数**: 当前价格在100根K线中的位置

### 2.2 评分体系

#### **综合指数计算**
```python
# 文件: grid_trading/services/simple_scoring.py (第259-290行)
```

采用加权评分模型:

```
综合指数 = VDR_得分 × 40% + KER_得分 × 30% + OVR_得分 × 20% + CVD_得分 × 10%
```

**各维度评分规则:**

1. **VDR得分** (40%权重)
   - VDR ≥ 10: 满分 (1.0) - 完美震荡
   - 5 ≤ VDR < 10: 线性得分 (0.5-1.0)
   - VDR < 5: 低分 (0.0-0.5)

2. **KER得分** (30%权重)
   - KER ≤ 0.1: 满分 (1.0) - 极低效率
   - 0.1 < KER < 0.3: 线性得分 (0.5-1.0)
   - KER ≥ 0.3: 低分 (0.0-0.5) - 趋势性太强

3. **OVR得分** (20%权重)
   - 0.5 ≤ OVR ≤ 1.5: 满分 (1.0) - 杠杆健康
   - OVR < 0.5: 中等分 (0.5-1.0) - 流动性可能不足
   - 1.5 < OVR < 2.0: 中等分 (0.5-1.0) - 轻微拥挤
   - OVR ≥ 2.0: 低分 (0.0-0.5) - 高杠杆拥挤

4. **CVD得分** (10%权重)
   - 有背离: 满分 (1.0)
   - 无背离: 基础分 (0.5)

### 2.3 过滤条件

在评分排序后,可应用以下可选过滤条件:

```python
# 文件: grid_trading/services/screening_engine.py (第407-451行)
```

- **最小VDR**: 过滤掉震荡性不足的代币
- **最小KER**: 过滤掉趋势性过强的代币
- **最小振幅**: 过滤掉波动性不足的代币
- **最小年化资金费率**: 过滤掉资金费率过低的代币
- **最大EMA99斜率**: 过滤掉长期上升趋势过强的代币

### 2.4 输出结果

筛选结果按**综合指数降序排列**,包含:

- 基础信息: 代币、价格、排名
- 四维指标: VDR、KER、OVR、CVD背离
- 分项得分: 各维度得分
- 综合指数: 最终排名依据
- 推荐参数: 网格上下限、止盈止损价格
- 入场建议: 推荐入场价格、触发概率、预期收益

---

## 三、网格范围计算算法

### 3.1 核心思路

网格范围基于**多周期成交量热力图**动态计算,而非固定百分比或ATR倍数。核心算法称为**四峰值分析器** (Four Peaks Analyzer)。

```python
# 文件: backtest/services/dynamic_grid_calculator.py
# 文件: vp_squeeze/services/four_peaks_analyzer.py
```

### 3.2 算法流程

#### **步骤1: 多周期成交量分析**
```python
# 文件: backtest/services/dynamic_grid_calculator.py (第237-326行)
```

对3个时间周期分别进行成交量分析:

| 周期 | 回看窗口 | 权重 | 用途 |
|-----|---------|------|-----|
| 4小时 | 180根(30天) | 1.5 | 识别中长期支撑压力 |
| 1小时 | 240根(10天) | 1.2 | 识别短期支撑压力 |
| 15分钟 | 288根(3天) | 1.0 | 识别日内支撑压力 |

每个周期计算:
- **Volume Profile**: 成交量按价格分布
- **增强HVN**: 高成交量节点(High Volume Nodes)
- **成交量集中度**: VAL-VAH区间成交量占比

#### **步骤2: 聚合成交量热力图**
```python
# 文件: vp_squeeze/services/four_peaks_analyzer.py (第65-94行)
```

将多周期成交量加权聚合到统一价格网格:

```
热力图[价格] = Σ (周期成交量 × 周期权重)
```

结果: 一个 `{price: total_volume}` 字典

#### **步骤3: 识别成交量集中区间**
```python
# 文件: vp_squeeze/services/four_peaks_analyzer.py (第97-163行)
```

使用**滑动窗口算法**识别成交量集中区间:

1. **窗口大小**: 5个价格桶
2. **扫描范围**: 当前价格 ±10% (默认)
3. **计算指标**:
   - 区间下界: 窗口最低价
   - 区间上界: 窗口最高价
   - 区间中心: (下界 + 上界) / 2
   - 区间总成交量: 窗口内所有价格桶成交量之和

4. **排序**: 按区间总成交量降序排列
5. **归一化**: 成交量强度 = 区间成交量 / 最大成交量

#### **步骤4: 灵活选择支撑/压力位**
```python
# 文件: vp_squeeze/services/four_peaks_analyzer.py (第413-480行)
```

从成交量区间列表中选择0-4个关键位:

**筛选规则:**
1. 按区间中心价格分为上方(压力位)和下方(支撑位)
2. 每组最多选2个区间
3. **最小间距约束**: 同组区间中心价相距至少5%
4. **优先级**: 成交量越大优先级越高

**排序规则:**
- 支撑位: 从低到高排序 → support_2(更低), support_1(较高)
- 压力位: 从低到高排序 → resistance_1(较低), resistance_2(更高)

**灵活性:**
- 允许只有1个支撑位 (support_2缺失)
- 允许只有1个压力位 (resistance_2缺失)
- 最少要求: 至少1个支撑位或1个压力位

#### **步骤5: 边界价格提取**
```python
# 文件: vp_squeeze/services/four_peaks_analyzer.py (第345-385行)
# 文件: backtest/services/dynamic_grid_calculator.py (第169-199行)
```

从成交量区间提取更保守的边界价格:

**提取规则:**
- **压力位**: 使用区间下界 (更保守,不容易触发)
- **支撑位**: 使用区间上界 (更保守,不容易跌破)

**MA25调整:**
如果边界价格距离MA25均线 < 2%,则调整到MA25:
```python
distance_pct = abs(price - ma25) / price
if distance_pct < 0.02:
    adjusted_price = ma25  # 磁吸到均线
```

#### **步骤6: 构建网格层级**
```python
# 文件: backtest/services/dynamic_grid_calculator.py (第206-230行)
```

最终输出一个 `GridLevels` 对象:

```python
@dataclass
class GridLevels:
    resistance_2: Optional[GridLevelInfo]  # 压力位2 (更远)
    resistance_1: Optional[GridLevelInfo]  # 压力位1 (较近)
    support_1: Optional[GridLevelInfo]     # 支撑位1 (较近)
    support_2: Optional[GridLevelInfo]     # 支撑位2 (更远)
    timestamp: datetime                     # 计算时间
    analysis_quality: float                 # 0-1, 分析质量

@dataclass
class GridLevelInfo:
    price: float       # 中心价格 (经MA25调整)
    zone_low: float    # 区间下界 (原始)
    zone_high: float   # 区间上界 (原始)
```

### 3.3 算法示例

假设当前价格为 $2000,计算过程:

1. **聚合成交量热力图**:
   ```
   $1800: 50M (4h) × 1.5 + 30M (1h) × 1.2 + 20M (15m) × 1.0 = 131M
   $1850: 80M × 1.5 + 60M × 1.2 + 40M × 1.0 = 232M
   $2150: 70M × 1.5 + 50M × 1.2 + 30M × 1.0 = 195M
   $2200: 40M × 1.5 + 25M × 1.2 + 15M × 1.0 = 105M
   ```

2. **识别成交量区间** (窗口=5):
   ```
   区间A: [$1840-$1860], 中心$1850, 总成交量232M
   区间B: [$1790-$1810], 中心$1800, 总成交量131M
   区间C: [$2140-$2160], 中心$2150, 总成交量195M
   区间D: [$2190-$2210], 中心$2200, 总成交量105M
   ```

3. **选择4个区间**:
   - 支撑位2 (support_2): 区间B, 中心$1800
   - 支撑位1 (support_1): 区间A, 中心$1850
   - 压力位1 (resistance_1): 区间C, 中心$2150
   - 压力位2 (resistance_2): 区间D, 中心$2200

4. **提取边界价格**:
   - support_2: 使用区间B上界 $1810
   - support_1: 使用区间A上界 $1860
   - resistance_1: 使用区间C下界 $2140
   - resistance_2: 使用区间D下界 $2190

5. **MA25调整** (假设MA25=$1855):
   ```
   support_1: $1860 距离MA25仅0.27% → 调整为 $1855
   ```

6. **最终网格层级**:
   ```
   resistance_2: $2190 (区间 $2190-$2210)
   resistance_1: $2140 (区间 $2140-$2160)
   support_1:    $1855 (区间 $1840-$1860, MA25调整)
   support_2:    $1810 (区间 $1790-$1810)
   ```

### 3.4 价格偏离范围控制

默认情况下,只在当前价格 **±10%** 范围内寻找支撑/压力位:

```python
# 文件: backtest/services/dynamic_grid_calculator.py (第82-99行)
price_deviation_pct: float = 0.10  # 默认±10%

# 计算有效范围
price_min = current_price * (1 - 0.10)  # 90%
price_max = current_price * (1 + 0.10)  # 110%
```

**原因:**
- 避免网格范围过宽导致资金利用率低
- 确保支撑/压力位在合理的交易范围内
- 过滤掉过远的历史价格区间

---

## 四、网格交易执行策略

### 4.1 策略概述

采用 **Grid V4 双向交易策略**:

```python
# 文件: backtest/services/grid_strategy_v4.py
```

**核心特点:**
1. **双向交易**: 同时做多和做空
2. **固定仓位**: 每个层级固定资金比例
3. **简单止盈**: 到达目标位一次性全平
4. **突破止损**: 关键位突破后+3%触发止损

### 4.2 开仓规则

#### **仓位分配**
```python
# 文件: backtest/services/grid_strategy_v4.py (第374-436行)
```

| 层级 | 触发条件 | 方向 | 仓位 | 目标位 |
|-----|---------|------|------|--------|
| 支撑位2 (S2) | 价格 ≤ support_2 | 做多 | 30% | resistance_1 |
| 支撑位1 (S1) | 价格 ≤ support_1 | 做多 | 20% | resistance_1 |
| 压力位1 (R1) | 价格 ≥ resistance_1 | 做空 | 20% | support_1 |
| 压力位2 (R2) | 价格 ≥ resistance_2 | 做空 | 30% | support_1 |

**开仓计算公式:**
```python
amount = (initial_cash × size_pct) / price
```

例如: 初始资金$10,000, 在S1($1850)开多单:
```
amount = ($10,000 × 20%) / $1850 = 1.081 个币
```

#### **防重复开仓机制**
```python
# 文件: backtest/services/grid_strategy_v4.py (第312-372行)
```

每次开仓前检查:

1. **是否已有持仓**: 同方向、同层级、同价格范围(±5%)
2. **是否在冷却期**: 最近5根K线(20小时)内是否有已平仓的仓位

**冷却期查询:**
```python
cooldown_duration = timedelta(hours=4 * 5)  # 5根4小时K线
cooldown_start = current_time - cooldown_duration

# 查询冷却期内的已平仓仓位
cooldown_positions = GridPosition.objects.filter(
    direction=direction,
    buy_level=level,
    status='closed',
    buy_time__gte=cooldown_start,
    buy_price__gte=price_low,  # ±5%范围
    buy_price__lte=price_high
)
```

### 4.3 平仓规则

#### **止盈规则** (SimpleTakeProfitExecutor)
```python
# 文件: backtest/services/simple_take_profit_executor.py
```

**多单止盈:**
- 价格 ≥ resistance_1 → 全部平仓

**空单止盈:**
- 价格 ≤ support_1 → 全部平仓

**特点:**
- 一次性全平 (不分批)
- 目标位固定 (不动态调整)

#### **止损规则** (BreakoutStopLossManager)
```python
# 文件: backtest/services/breakout_stop_loss_manager.py
```

**多单止损:**
- 价格 < support_2 (支撑位2) → 触发警戒
- 价格继续下跌3% → 执行止损

**空单止损:**
- 价格 > resistance_2 (压力位2) → 触发警戒
- 价格继续上涨3% → 执行止损

**特点:**
- 两阶段触发 (突破 + 确认)
- 止损百分比: 默认3%

### 4.4 执行优先级

```python
# 文件: backtest/services/grid_strategy_v4.py (第160-167行)
```

每根K线的处理顺序:

1. **计算动态网格**: 更新支撑/压力位
2. **检查止损**: 优先级最高,防止亏损扩大
3. **检查止盈**: 锁定利润
4. **检查开仓信号**: 寻找新的入场机会
5. **记录快照**: 保存当前状态

### 4.5 仓位管理

#### **仓位状态**
```python
# 文件: backtest/models.py - GridPosition
```

| 状态 | 说明 |
|------|-----|
| `open` | 持仓中 (未平仓) |
| `partial` | 部分平仓 (V4不使用) |
| `closed` | 已平仓 |

#### **仓位跟踪字段**
- `buy_price`: 开仓价格
- `buy_amount`: 开仓数量
- `buy_cost`: 开仓成本 (含手续费)
- `total_sold_amount`: 已平仓数量
- `sell_target_r1_price`: 止盈目标价
- `stop_loss_price`: 止损价格
- `pnl`: 已实现盈亏

---

## 五、关键参数说明

### 5.1 筛选参数

| 参数 | 默认值 | 说明 |
|-----|-------|-----|
| `vdr_weight` | 0.40 | VDR权重(震荡性) |
| `ker_weight` | 0.30 | KER权重(低效率) |
| `ovr_weight` | 0.20 | OVR权重(杠杆健康) |
| `cvd_weight` | 0.10 | CVD权重(背离信号) |
| `min_vdr` | None | 最小VDR过滤 |
| `min_ker` | None | 最小KER过滤 |
| `min_amplitude` | None | 最小振幅过滤(%) |
| `min_funding_rate` | None | 最小年化资金费率(%) |
| `max_ma99_slope` | None | 最大EMA99斜率 |

### 5.2 网格范围参数

| 参数 | 默认值 | 说明 |
|-----|-------|-----|
| `price_deviation_pct` | 0.10 | 价格偏离范围(±10%) |
| `lookback_periods['4h']` | 180 | 4小时周期回看根数(30天) |
| `lookback_periods['1h']` | 240 | 1小时周期回看根数(10天) |
| `lookback_periods['15m']` | 288 | 15分钟周期回看根数(3天) |
| `weights['4h']` | 1.5 | 4小时周期权重 |
| `weights['1h']` | 1.2 | 1小时周期权重 |
| `weights['15m']` | 1.0 | 15分钟周期权重 |
| `window_size` | 5 | 滑动窗口大小(价格桶) |
| `min_distance_pct` | 0.05 | 区间最小间距(5%) |
| `adjustment_threshold` | 0.02 | MA25调整阈值(2%) |

### 5.3 交易执行参数

| 参数 | 默认值 | 说明 |
|-----|-------|-----|
| `initial_cash` | 10000.0 | 初始资金(USDT) |
| `stop_loss_pct` | 0.03 | 止损百分比(3%) |
| `commission` | 0.001 | 手续费率(0.1%) |
| `interval` | 4h | K线周期 |
| `cooldown_bars` | 5 | 冷却期K线数量 |
| `tolerance` | 0.05 | 重复开仓检测容忍度(±5%) |

### 5.4 仓位配置

| 层级 | 仓位比例 | 方向 |
|-----|---------|------|
| support_2 | 30% | 做多 |
| support_1 | 20% | 做多 |
| resistance_1 | 20% | 做空 |
| resistance_2 | 30% | 做空 |

**总仓位上限:** 100% (最多同时开满4个层级)

---

## 附录: 相关文件索引

### 代币筛选
- `grid_trading/services/screening_engine.py`: 筛选引擎主流程
- `grid_trading/services/simple_scoring.py`: 简化评分模型
- `grid_trading/services/indicator_calculator.py`: 技术指标计算器
- `grid_trading/models/screening_result.py`: 筛选结果数据模型

### 网格范围计算
- `backtest/services/dynamic_grid_calculator.py`: 动态网格计算器
- `vp_squeeze/services/four_peaks_analyzer.py`: 四峰值分析器
- `vp_squeeze/services/indicators/volume_profile.py`: 成交量分布计算
- `vp_squeeze/services/multi_timeframe_analyzer.py`: 多周期分析器

### 交易执行
- `backtest/services/grid_strategy_v4.py`: Grid V4双向交易策略
- `backtest/services/bidirectional_position_manager.py`: 双向仓位管理器
- `backtest/services/simple_take_profit_executor.py`: 简单止盈执行器
- `backtest/services/breakout_stop_loss_manager.py`: 突破止损管理器

### 数据模型
- `backtest/models.py`: 回测数据模型 (GridPosition, BacktestResult等)
- `grid_trading/models/`: 筛选相关数据模型

---

**文档版本**: v1.0
**最后更新**: 2025-12-10
**维护者**: 加密货币网格交易系统开发团队
