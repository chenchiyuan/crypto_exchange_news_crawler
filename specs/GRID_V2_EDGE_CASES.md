# Grid Strategy V2 - 边界条件处理方案

> **文档目的**: 定义动态网格计算中极端情况的应对策略
> **创建时间**: 2025-12-01
> **状态**: ✅ 已确认

---

## 1. 背景

Grid Strategy V2使用动态网格计算，基于成交量分析在±10%价格范围内寻找支撑压力位。

**理想情况**: 识别到4个区间
- 支撑位2 (support_2)
- 支撑位1 (support_1)
- 压力位1 (resistance_1)
- 压力位2 (resistance_2)

**实际情况**: 市场状态复杂，可能识别到的区间数量不足4个

---

## 2. 边界条件分类

### 2.1 区间数量不足的情况

| 识别到的区间数 | 支撑位数量 | 压力位数量 | 处理方案 |
|--------------|----------|----------|---------|
| **4个** | 2个 | 2个 | ✅ 标准情况，正常处理 |
| **3个** | 2个 | 1个 | ⚠️ 边界情况1：压力位不足 |
| **3个** | 1个 | 2个 | ⚠️ 边界情况2：支撑位不足 |
| **2个** | 1个 | 1个 | ⚠️ 边界情况3：双边各1个 |
| **2个** | 2个 | 0个 | ⚠️ 边界情况4：仅支撑位 |
| **2个** | 0个 | 2个 | ⚠️ 边界情况5：仅压力位 |
| **1个** | 1个 | 0个 | ⚠️ 边界情况6：仅1个支撑位 |
| **1个** | 0个 | 1个 | ⚠️ 边界情况7：仅1个压力位 |
| **0个** | 0个 | 0个 | ❌ 无效情况：不交易 |

---

## 3. 处理策略

### 3.1 核心原则

#### 原则1: 优先保证策略可运行
```
宁可减少交易频率，也不能因为数据不足导致策略崩溃
```

#### 原则2: 支撑位和压力位独立判断
```
支撑位决定能否买入
压力位决定能否卖出
```

#### 原则3: 降级使用
```
当只有1个支撑位时，视为support_1（而非support_2）
当只有1个压力位时，视为resistance_1（而非resistance_2）
```

---

### 3.2 具体处理方案

#### 方案1: 支撑位不足时（0-1个）

**场景**: 只识别到0或1个支撑位

```python
# 情况1: 没有支撑位
if support_count == 0:
    # ❌ 不执行买入操作
    logger.warning("没有识别到支撑位，跳过买入检查")
    return None

# 情况2: 只有1个支撑位
if support_count == 1:
    # ✅ 将唯一的支撑位作为support_1使用
    grid_levels = GridLevels(
        support_1=clusters[0],  # 唯一的支撑位
        support_2=None,         # 缺失
        resistance_1=...,
        resistance_2=...
    )
```

**买入逻辑调整**:
```python
def _check_buy_signals(self, current_price, current_time, grid_levels):
    """检查买入信号"""

    # 遍历支撑位（跳过None）
    for level_name in ['support_1', 'support_2']:
        level_info = getattr(grid_levels, level_name)

        # ⭐⭐⭐ 关键：检查支撑位是否存在
        if level_info is None:
            logger.debug(f"{level_name} 不存在，跳过买入检查")
            continue

        # ... 原有买入逻辑
```

---

#### 方案2: 压力位不足时（0-1个）

**场景**: 只识别到0或1个压力位

```python
# 情况1: 没有压力位
if resistance_count == 0:
    # ❌ 持仓无法卖出（无止盈目标）
    logger.warning("没有识别到压力位，已有仓位将无法止盈")
    grid_levels = GridLevels(
        support_1=...,
        support_2=...,
        resistance_1=None,  # 缺失
        resistance_2=None   # 缺失
    )

# 情况2: 只有1个压力位
if resistance_count == 1:
    # ✅ 将唯一的压力位作为resistance_1使用
    grid_levels = GridLevels(
        support_1=...,
        support_2=...,
        resistance_1=clusters[0],  # 唯一的压力位
        resistance_2=None          # 缺失
    )
```

**卖出逻辑调整**:
```python
def _check_sell_signals(self, current_price, current_time, grid_levels):
    """检查卖出信号"""

    # 遍历压力位（跳过None）
    for target_level in ['resistance_1', 'resistance_2']:
        level_info = getattr(grid_levels, target_level)

        # ⭐⭐⭐ 关键：检查压力位是否存在
        if level_info is None:
            logger.debug(f"{target_level} 不存在，跳过卖出检查")
            continue

        # ... 原有卖出逻辑
```

---

#### 方案3: 双边各1个（最小可交易配置）

**场景**: 只有1个支撑位和1个压力位

```python
grid_levels = GridLevels(
    support_1=support_cluster,      # 唯一支撑位
    support_2=None,                 # 缺失
    resistance_1=resistance_cluster, # 唯一压力位
    resistance_2=None                # 缺失
)
```

**示例**:
```
价格: 3000 USDT
识别结果:
  support_1: 2900 USDT (唯一支撑位)
  resistance_1: 3100 USDT (唯一压力位)

交易逻辑:
  ✅ 价格跌至2900 → 买入（support_1）
  ✅ 价格涨至3100 → 卖出（resistance_1）
  ✅ 形成简单的箱体交易
```

---

#### 方案4: 仅支撑位（无压力位）

**场景**: 识别到支撑位，但没有压力位

```python
grid_levels = GridLevels(
    support_1=support_1_cluster,
    support_2=support_2_cluster if exists else None,
    resistance_1=None,  # ❌ 缺失
    resistance_2=None   # ❌ 缺失
)
```

**交易行为**:
```
✅ 可以买入（有支撑位）
❌ 无法卖出（无压力位作为止盈目标）
⚠️ 仓位会一直持有，直到下一个K线识别到压力位
```

**风险**:
- 仓位可能长期无法止盈
- 依赖止损保护

**建议**:
- 增强止损机制
- 记录"无压力位"状态，供后续分析

---

#### 方案5: 仅压力位（无支撑位）

**场景**: 识别到压力位，但没有支撑位

```python
grid_levels = GridLevels(
    support_1=None,  # ❌ 缺失
    support_2=None,  # ❌ 缺失
    resistance_1=resistance_1_cluster,
    resistance_2=resistance_2_cluster if exists else None
)
```

**交易行为**:
```
❌ 无法买入（无支撑位）
✅ 已有仓位可以卖出（有压力位）
ℹ️ 该K线只能平仓，不能开仓
```

**适用场景**:
- 价格处于上涨趋势，远离支撑位
- 只需要平仓操作

---

#### 方案6: 无任何区间

**场景**: 一个区间都没识别到

```python
if len(clusters) == 0:
    logger.warning(f"无法识别任何成交量集中区间: {current_time}")
    return None  # ❌ 返回None，跳过该K线
```

**交易行为**:
```
❌ 无法买入
❌ 无法卖出
ℹ️ 完全跳过该K线，等待下一根K线
```

---

## 4. GridLevels数据结构调整

### 4.1 修改前（强制4层）

```python
@dataclass
class GridLevels:
    """完整的4层网格"""
    resistance_2: GridLevelInfo  # 必须存在
    resistance_1: GridLevelInfo  # 必须存在
    support_1: GridLevelInfo     # 必须存在
    support_2: GridLevelInfo     # 必须存在
    timestamp: datetime
    analysis_quality: float
```

### 4.2 修改后（支持None）

```python
@dataclass
class GridLevels:
    """动态网格层级（支持1-4层）"""
    resistance_2: Optional[GridLevelInfo]  # ⭐ 可选
    resistance_1: Optional[GridLevelInfo]  # ⭐ 可选
    support_1: Optional[GridLevelInfo]     # ⭐ 可选
    support_2: Optional[GridLevelInfo]     # ⭐ 可选
    timestamp: datetime
    analysis_quality: float

    def has_support(self) -> bool:
        """是否有至少1个支撑位"""
        return self.support_1 is not None or self.support_2 is not None

    def has_resistance(self) -> bool:
        """是否有至少1个压力位"""
        return self.resistance_1 is not None or self.resistance_2 is not None

    def support_count(self) -> int:
        """支撑位数量"""
        count = 0
        if self.support_1 is not None:
            count += 1
        if self.support_2 is not None:
            count += 1
        return count

    def resistance_count(self) -> int:
        """压力位数量"""
        count = 0
        if self.resistance_1 is not None:
            count += 1
        if self.resistance_2 is not None:
            count += 1
        return count
```

---

## 5. DynamicGridCalculator修改方案

### 5.1 区间选择逻辑（放宽限制）

**修改前**:
```python
# 4. 识别成交量集中区间
clusters = find_volume_clusters_by_window(...)

if len(clusters) < 4:
    logger.warning(f"区间不足4个: {len(clusters)}")
    return None  # ❌ 直接返回None

# 5. 选择4个区间
selected_below, selected_above = select_four_clusters(...)

if len(selected_below) < 2 or len(selected_above) < 2:
    return None  # ❌ 必须上下各2个
```

**修改后**:
```python
# 4. 识别成交量集中区间
clusters = find_volume_clusters_by_window(...)

if len(clusters) == 0:
    logger.warning(f"无法识别任何区间: {current_time}")
    return None  # ❌ 无区间则返回None

# 5. 灵活选择区间（1-4个）
selected_below, selected_above = select_flexible_clusters(
    clusters=clusters,
    current_price=current_price,
    min_distance_pct=0.05
)

# ⭐⭐⭐ 关键：不要求必须有4个，至少有1个即可
logger.info(
    f"区间选择: 支撑位={len(selected_below)}个, "
    f"压力位={len(selected_above)}个"
)
```

### 5.2 新增灵活选择函数

```python
def select_flexible_clusters(
    clusters: List[VolumePeak],
    current_price: float,
    min_distance_pct: float = 0.05
) -> Tuple[List[VolumePeak], List[VolumePeak]]:
    """
    灵活选择支撑位和压力位（1-4个）

    Args:
        clusters: 成交量区间列表
        current_price: 当前价格
        min_distance_pct: 最小间距百分比

    Returns:
        (selected_below, selected_above)
        - selected_below: 支撑位列表（0-2个）
        - selected_above: 压力位列表（0-2个）
    """
    below = [c for c in clusters if c.price_high < current_price]
    above = [c for c in clusters if c.price_low > current_price]

    # 排序（支撑位从高到低，压力位从低到高）
    below.sort(key=lambda x: x.price_high, reverse=True)
    above.sort(key=lambda x: x.price_low)

    # 选择最多2个支撑位
    selected_below = []
    for cluster in below:
        if len(selected_below) >= 2:
            break

        # 检查与已选区间的距离
        if selected_below:
            last_price = selected_below[-1].price_high
            distance_pct = abs(cluster.price_high - last_price) / last_price
            if distance_pct < min_distance_pct:
                continue

        selected_below.append(cluster)

    # 选择最多2个压力位
    selected_above = []
    for cluster in above:
        if len(selected_above) >= 2:
            break

        # 检查与已选区间的距离
        if selected_above:
            last_price = selected_above[-1].price_low
            distance_pct = abs(cluster.price_low - last_price) / last_price
            if distance_pct < min_distance_pct:
                continue

        selected_above.append(cluster)

    return selected_below, selected_above
```

### 5.3 GridLevels构建逻辑

```python
# 6. 构建网格层级（支持None）

# 支撑位
support_2 = None
support_1 = None

if len(selected_below) == 2:
    # 标准情况：2个支撑位
    support_2 = self._create_grid_level(selected_below[0], ma25, False)
    support_1 = self._create_grid_level(selected_below[1], ma25, False)
elif len(selected_below) == 1:
    # ⚠️ 边界情况：只有1个支撑位，作为support_1
    support_1 = self._create_grid_level(selected_below[0], ma25, False)
    logger.warning("只识别到1个支撑位，作为support_1使用")

# 压力位
resistance_2 = None
resistance_1 = None

if len(selected_above) == 2:
    # 标准情况：2个压力位
    resistance_1 = self._create_grid_level(selected_above[0], ma25, True)
    resistance_2 = self._create_grid_level(selected_above[1], ma25, True)
elif len(selected_above) == 1:
    # ⚠️ 边界情况：只有1个压力位，作为resistance_1
    resistance_1 = self._create_grid_level(selected_above[0], ma25, True)
    logger.warning("只识别到1个压力位，作为resistance_1使用")

# 7. 计算分析质量
all_selected = selected_below + selected_above
analysis_quality = self._calculate_quality(all_selected) if all_selected else 0.0

# 8. 创建GridLevels
grid_levels = GridLevels(
    resistance_2=resistance_2,  # 可能为None
    resistance_1=resistance_1,  # 可能为None
    support_1=support_1,        # 可能为None
    support_2=support_2,        # 可能为None
    timestamp=current_time,
    analysis_quality=analysis_quality
)

# 9. 日志记录
logger.info(
    f"✓ 网格计算成功 @ {current_time.strftime('%m-%d %H:%M')}: "
    f"价格={current_price:.2f} | "
    f"支撑位={grid_levels.support_count()}个, "
    f"压力位={grid_levels.resistance_count()}个"
)

return grid_levels
```

---

## 6. 测试用例

### 测试1: 标准情况（4个区间）

```python
输入:
  clusters = [S2, S1, R1, R2]
  current_price = 3000

预期输出:
  GridLevels(
      support_2=S2,
      support_1=S1,
      resistance_1=R1,
      resistance_2=R2
  )

交易行为:
  ✅ 可以在S1/S2买入
  ✅ 可以在R1/R2卖出
```

### 测试2: 仅1个支撑位 + 2个压力位

```python
输入:
  clusters = [S1, R1, R2]
  current_price = 3000

预期输出:
  GridLevels(
      support_2=None,    # ❌ 缺失
      support_1=S1,      # ✅ 唯一支撑位
      resistance_1=R1,
      resistance_2=R2
  )

交易行为:
  ✅ 只能在S1买入（S2不存在）
  ✅ 可以在R1/R2卖出
```

### 测试3: 2个支撑位 + 仅1个压力位

```python
输入:
  clusters = [S2, S1, R1]
  current_price = 3000

预期输出:
  GridLevels(
      support_2=S2,
      support_1=S1,
      resistance_1=R1,   # ✅ 唯一压力位
      resistance_2=None  # ❌ 缺失
  )

交易行为:
  ✅ 可以在S1/S2买入
  ✅ 只能在R1卖出（R2不存在）
```

### 测试4: 最小配置（1个支撑位 + 1个压力位）

```python
输入:
  clusters = [S1, R1]
  current_price = 3000

预期输出:
  GridLevels(
      support_2=None,
      support_1=S1,
      resistance_1=R1,
      resistance_2=None
  )

交易行为:
  ✅ 可以在S1买入
  ✅ 可以在R1卖出
  ℹ️ 简单箱体交易
```

### 测试5: 仅支撑位（无压力位）

```python
输入:
  clusters = [S2, S1]
  current_price = 3000

预期输出:
  GridLevels(
      support_2=S2,
      support_1=S1,
      resistance_1=None,  # ❌ 无压力位
      resistance_2=None
  )

交易行为:
  ✅ 可以在S1/S2买入
  ❌ 无法卖出（等待下一个K线识别到压力位）
```

### 测试6: 仅压力位（无支撑位）

```python
输入:
  clusters = [R1, R2]
  current_price = 3000

预期输出:
  GridLevels(
      support_2=None,     # ❌ 无支撑位
      support_1=None,
      resistance_1=R1,
      resistance_2=R2
  )

交易行为:
  ❌ 无法买入
  ✅ 已有仓位可以在R1/R2卖出
```

### 测试7: 无区间

```python
输入:
  clusters = []
  current_price = 3000

预期输出:
  None  # ❌ 无法计算网格

交易行为:
  ❌ 跳过该K线
  ℹ️ 等待下一根K线
```

---

## 7. 日志规范

### 7.1 正常情况日志

```python
logger.info(
    f"✓ 网格计算成功 @ 09-01 04:00: "
    f"价格=4463.29 (±10%范围) | "
    f"支撑位=2个, 压力位=2个"
)
```

### 7.2 边界情况日志

```python
# 情况1: 只有1个支撑位
logger.warning(
    f"⚠️ 支撑位不足 @ 09-01 04:00: "
    f"价格=4463.29 | "
    f"识别到1个支撑位（作为support_1），support_2缺失"
)

# 情况2: 没有压力位
logger.warning(
    f"⚠️ 无压力位 @ 09-01 04:00: "
    f"价格=4463.29 | "
    f"无法识别压力位，已有仓位将无法止盈"
)

# 情况3: 无任何区间
logger.error(
    f"❌ 网格计算失败 @ 09-01 04:00: "
    f"价格=4463.29 | "
    f"无法识别任何成交量集中区间，跳过该K线"
)
```

---

## 8. 验收标准

### ✅ 代码层面

- [ ] GridLevels支持None值（resistance_1/2, support_1/2）
- [ ] 添加has_support()、has_resistance()辅助方法
- [ ] select_flexible_clusters()支持1-4个区间
- [ ] _check_buy_signals检查支撑位是否为None
- [ ] _check_sell_signals检查压力位是否为None
- [ ] 完善日志记录（区分标准情况和边界情况）

### ✅ 功能层面

- [ ] 只有1个支撑位时，视为support_1
- [ ] 只有1个压力位时，视为resistance_1
- [ ] 没有支撑位时，不执行买入
- [ ] 没有压力位时，仓位不卖出
- [ ] 无任何区间时，跳过该K线

### ✅ 测试层面

- [ ] 通过测试用例1-7
- [ ] 回测不因边界情况崩溃
- [ ] 日志清晰记录边界情况

---

## 9. 实现顺序

1. **修改数据结构**
   - GridLevels添加Optional类型
   - 添加辅助方法

2. **修改DynamicGridCalculator**
   - 实现select_flexible_clusters()
   - 修改calculate_grid_levels()逻辑

3. **修改GridStrategyV2**
   - _check_buy_signals()添加None检查
   - _check_sell_signals()添加None检查

4. **完善日志**
   - 区分标准情况和边界情况
   - 记录支撑位/压力位数量

5. **运行回测验证**
   - 使用9-11月数据测试
   - 检查是否出现边界情况
   - 验证处理逻辑正确

---

**文档状态**: ✅ 已确认，待实现
**预期完成时间**: 2025-12-01
**负责人**: Claude
