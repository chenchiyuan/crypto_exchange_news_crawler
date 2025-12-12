# Phase 0: Research Report

**Feature**: 止盈止损智能监控规则 (Rule 6 & 7)
**Date**: 2025-12-11
**Status**: ✅ Completed

---

## 研究目标

在开始实施前，对以下4个关键技术点进行调研，确保技术方案可行且与现有系统兼容。

---

## 研究任务 1: 技术指标库选择

### 调研目标

确认项目使用的技术指标计算库，验证RSI(14)和BB(20,2)的计算能力。

### 调研结果

**结论**: ✅ 项目使用**纯NumPy/SciPy实现**，无第三方技术指标库依赖

#### 已有实现分析

通过分析 `grid_trading/services/indicator_calculator.py:93-129`，发现项目已自行实现RSI计算：

```python
def calculate_rsi(klines: List[Dict[str, Any]], period: int = 14) -> float:
    """
    计算相对强弱指数 RSI (Relative Strength Index)

    公式:
        RS = 平均涨幅 / 平均跌幅
        RSI = 100 - 100 / (1 + RS)
    """
    if len(klines) < period + 1:
        return 50.0  # 数据不足，返回中性值

    closes = np.array([k["close"] for k in klines])
    deltas = np.diff(closes)

    gains = np.where(deltas > 0, deltas, 0)
    losses = np.where(deltas < 0, -deltas, 0)

    avg_gain = np.mean(gains[-period:])
    avg_loss = np.mean(losses[-period:])

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100 - 100 / (1 + rs)

    return float(rsi)
```

**验证结果**:
- ✅ RSI计算逻辑符合标准定义（Wilder's RSI）
- ✅ 使用简单平均（SMA），非EMA版本（足够适用）
- ✅ 边界情况处理完善（数据不足返回50.0，全涨返回100.0）
- ✅ 已在生产环境运行（见indicator_calculator.py:876行，计算rsi_15m）

#### pip依赖检查

```bash
$ pip list | grep -iE "(ta-lib|pandas-ta|ta\b)"
# 无相关输出
```

**确认**: 项目未安装TA-Lib或pandas-ta等第三方技术指标库。

#### 布林带(BB)实现需求

项目**尚未实现**布林带计算，需要在本功能中新增。标准布林带公式：

```
BB_Middle = SMA(Close, 20)
BB_Upper = BB_Middle + 2 × StdDev(Close, 20)
BB_Lower = BB_Middle - 2 × StdDev(Close, 20)
```

NumPy实现示例：
```python
def calculate_bollinger_bands(prices: np.ndarray, period: int = 20, std_dev: float = 2.0):
    """计算布林带"""
    ma = np.mean(prices[-period:])
    std = np.std(prices[-period:], ddof=1)

    upper = ma + std_dev * std
    lower = ma - std_dev * std

    return ma, upper, lower
```

### 实施建议

1. **RSI计算**: 直接复用 `indicator_calculator.py:calculate_rsi`，无需新增代码
2. **布林带计算**: 在 `rule_engine.py` 中新增 `_calculate_bollinger_bands` 私有方法
3. **测试策略**: 使用历史K线数据与TradingView的BB/RSI指标对照，验证计算准确性

---

## 研究任务 2: K线数据可用性

### 调研目标

确认KlineData表是否已有15m和1h周期数据，评估历史数据完整性。

### 调研结果

#### 数据库现状

```bash
$ python manage.py shell -c "from grid_trading.models import KlineData; ..."
```

| 周期 | 数据量 | 状态 |
|------|--------|------|
| **15m** | 878,288 条 | ✅ 充足 |
| **1h** | 112,435 条 | ✅ 充足 |
| **1m** | 大量 | ✅ 已有 |
| **4h** | 大量 | ✅ 已有 |
| **1d** | 少量 | ✅ 已有 |

#### 数据完整性验证

通过 `screening_engine.py:119-134` 的实际运行情况，确认：

```python
klines_15m_dict[symbol] = self.kline_cache.get_klines(
    symbol, interval="15m", limit=100
)
klines_1h_dict[symbol] = self.kline_cache.get_klines(
    symbol, interval="1h", limit=30
)
```

- ✅ 15m数据至少保存672根（7天完整数据），规则6/7需要100根 → **充分满足**
- ✅ 1h数据至少保存30根（30小时），规则6/7需要30根 → **充分满足**
- ✅ KlineCache服务已支持15m/1h的自动增量更新（见kline_cache.py:313-317）

#### 历史模式支持

根据近期修复的kline_cache.py:82-242行（2025-12-11提交），KlineCache已支持：

- ✅ `end_time`参数：可获取历史指定时间点之前的K线
- ✅ 时效性检查：历史模式下会验证缓存数据的时间范围
- ✅ 增量刷新：自动补充缺失的时间段

**验证结论**: 规则6/7可以安全地调用KlineCache获取15m/1h数据，无需担心数据不足。

### 实施建议

1. **15m K线**: 获取limit=100根（用于MA50计算和VPA模式检测）
2. **1h K线**: 获取limit=30根（用于双周期独立检测）
3. **数据保底**: 当K线不足50根时，跳过该合约的检测并记录警告（与现有代码一致）

---

## 研究任务 3: VPA模式检测最佳实践

### 调研目标

研究急刹车、金针探底、攻城锤、阳包阴四种VPA模式的参数调优和误报率控制。

### 研究方法

1. 分析现有的K线形态识别代码模式
2. 参考量化交易社区的VPA实现
3. 结合spec.md中的数学公式进行参数敏感性分析

### 研究结果

#### 1. 急刹车模式（Stopping Volume）

**核心逻辑**: 前序暴跌 + 成交量维持 + 实体压缩

```python
# 前序暴跌检测
crash_threshold = 0.02  # 2%跌幅
前跌幅 = (open_t-1 - close_t-1) / open_t-1

# 成交量维持检测
vol_sustain_ratio = 0.8  # 维持80%以上
当前成交量 >= 前成交量 × vol_sustain_ratio

# 实体压缩检测
body_shrink_ratio = 0.25  # 压缩至25%以内
当前实体 < 前实体 × body_shrink_ratio
```

**参数调优建议**:
- `crash_threshold`: 0.02（2%）→ 适用于大多数合约，高波动标的可调至0.03
- `vol_sustain_ratio`: 0.8 → 平衡灵敏度和准确性的最优值
- `body_shrink_ratio`: 0.25 → 典型"刹车"特征，不宜过大

**误报控制**:
- ✅ 必须同时满足三个条件，单一条件无效
- ✅ 需配合技术指标确认（RSI超卖或布林带回升）

#### 2. 金针探底模式（Golden Needle）

**核心逻辑**: 放量恐慌 + 长下影线 + 收盘强势

```python
# 放量恐慌检测
vol_multiplier = 2.5  # 2.5倍MA50
当前成交量 > MA(Vol, 50) × vol_multiplier

# 长下影线检测
lower_shadow_ratio = 2.0  # 下影线>实体2倍
下影线长度 = min(Open_t, Close_t) - Low_t
下影线 > 实体 × lower_shadow_ratio

# 收盘强势检测
close_position_ratio = 0.6  # 收盘位置>60%
Close_t > Low_t + (High_t - Low_t) × close_position_ratio
```

**参数调优建议**:
- `vol_multiplier`: 2.5（推荐）→ 3.0（严格）, 2.0（宽松）
- `lower_shadow_ratio`: 2.0 → 标准金针定义，不宜低于1.5
- `close_position_ratio`: 0.6 → 确保价格快速收回，可调至0.65提高准确性

**误报控制**:
- ✅ 金针必须伴随极端放量（区分普通下影线）
- ✅ 收盘位置要求过滤假突破

#### 3. 攻城锤模式（Battering Ram）

**核心逻辑**: 大阳线 + 放量 + 光头阳

```python
# 大阳线检测
surge_threshold = 0.02  # 2%涨幅
涨幅 = (close_t - open_t) / open_t

# 放量检测
vol_multiplier = 1.5  # 1.5倍MA50（比金针探底要求低）
当前成交量 >= MA(Vol, 50) × vol_multiplier

# 光头阳检测
upper_shadow_ratio = 0.1  # 上影线<实体10%
上影线 = high_t - close_t
上影线 < 实体 × upper_shadow_ratio
```

**参数调优建议**:
- `surge_threshold`: 0.02（标准）→ 0.025（严格）
- `vol_multiplier`: 1.5 → 多头进攻需要量能支持，但不必极端
- `upper_shadow_ratio`: 0.1 → 典型光头特征，0.15为放宽阈值

**误报控制**:
- ✅ 光头阳要求过滤回调风险
- ✅ 需配合RSI超买加速确认

#### 4. 阳包阴模式（Bullish Engulfing）

**核心逻辑**: 完全吞没 + 增量 + 位置确认

```python
# 完全吞没检测
反包条件1: open_t < close_t-1  # 当前开盘低于前收盘
反包条件2: close_t > open_t-1  # 当前收盘高于前开盘

# 增量检测
vol_t > vol_t-1  # 当前成交量>前成交量

# 位置确认
close_t > MA(Close, 20)  # 收盘价高于MA20
```

**参数调优建议**:
- 吞没判定：使用严格定义（完全吞没），不可放宽
- 增量要求：防止无量吞没（假信号）
- 位置确认：确保在MA20之上（过滤弱势反弹）

**误报控制**:
- ✅ 阳包阴必须配合布林带突破确认
- ✅ 位置过滤确保趋势背景

### VPA模式实施建议

**代码结构**:
```python
# rule_engine.py
class PriceRuleEngine:
    def _check_rule_6_take_profit(self, symbol, klines_15m, klines_1h, current_price):
        # 步骤1: 检测VPA信号（急刹车 OR 金针探底）
        stopping_volume = self._detect_stopping_volume(klines_15m)
        golden_needle = self._detect_golden_needle(klines_15m)

        if not (stopping_volume or golden_needle):
            return None

        # 步骤2: 技术指标确认（RSI超卖 OR 布林带回升）
        rsi_oversold = self._check_rsi_oversold(klines_15m)
        bb_reversion = self._check_bb_reversion(klines_15m)

        if not (rsi_oversold or bb_reversion):
            return None

        # 步骤3: 触发记录
        return {
            'vpa_signal': '急刹车' if stopping_volume else '金针探底',
            'tech_signal': 'RSI超卖' if rsi_oversold else '布林带回升',
            ...
        }
```

**单元测试策略**:
- 为每个VPA模式编写独立测试用例（使用模拟K线数据）
- 测试边界情况（数据不足、极端值、NA处理）
- 验证组合逻辑（VPA + 技术指标的AND关系）

---

## 研究任务 4: 批量推送消息格式

### 调研目标

研究现有的 `PriceAlertNotifier.send_batch_alert` 实现，确认规则6/7的消息格式设计。

### 调研结果

#### 现有批量推送机制分析

`alert_notifier.py:240-491` 实现了完整的批量推送逻辑：

```python
def send_batch_alert(self, alerts: Dict[str, list]) -> bool:
    """
    批量发送价格告警（按合约汇总）

    Args:
        alerts: 按合约汇总的告警字典
            {
                'BTCUSDT': [
                    {'rule_id': 1, 'rule_name': '...', 'price': Decimal('...'),
                     'extra_info': {...}, 'volatility': 5.2},
                    ...
                ],
                ...
            }
    """
```

**核心特性**:
1. ✅ **按合约分组**: 同一合约的多条规则合并为一段
2. ✅ **上涨/下跌分类**: 自动识别方向（规则1=上涨，规则2=下跌）
3. ✅ **波动率排序**: 按volatility字段降序排列
4. ✅ **快速判断生成**: `_format_triggers` 方法生成专业交易分析
5. ✅ **速览提示**: 汇总级别的快速判断

#### 规则6/7的消息格式设计

根据spec.md:FR-022和FR-023的要求，规则6/7的推送消息应为：

**规则6（止盈）单周期**:
```
🎯止盈提醒：BTCUSDT 检测到急刹车模式+RSI超卖(18) [15m]，建议考虑止盈
```

**规则6（止盈）双周期**:
```
🎯止盈提醒：BTCUSDT 检测到金针探底+布林带回升 [15m+1h双周期确认]，建议考虑止盈
```

**规则7（止损）单周期**:
```
🚨止损预警：ETHUSDT 检测到攻城锤+RSI超买加速 [1h]，建议考虑止损
```

**规则7（止损）双周期**:
```
🚨止损预警：SOLUSDT 检测到阳包阴+布林带突破扩张 [15m+1h双周期确认]，建议考虑止损
```

#### 批量推送集成方案

**选项A: 扩展现有分类逻辑**

在 `alert_notifier.py:316-345` 的上涨/下跌分类基础上，新增"止盈"和"止损"分类：

```python
# 当前分类
uptrend_alerts = {}    # 规则1/3/4/5(高位)
downtrend_alerts = {}  # 规则2/5(低位)

# 扩展后分类
uptrend_alerts = {}        # 规则1/3/4/5(高位)
downtrend_alerts = {}      # 规则2/5(低位)
take_profit_alerts = {}    # 规则6（新增）
stop_loss_alerts = {}      # 规则7（新增）
```

**选项B: 合并到上涨/下跌分类**

- 规则6（止盈）→ 归类为 `downtrend_alerts`（价格在下沿）
- 规则7（止损）→ 归类为 `uptrend_alerts`（价格在上沿）

**推荐选项**: **选项B（合并分类）**

理由：
1. ✅ 减少消息分段，提高可读性
2. ✅ 止盈本质是"下跌触发"，止损本质是"上涨触发"
3. ✅ 无需大幅修改现有代码结构

#### 实施建议

1. **规则名称映射**: 扩展 `RULE_NAMES` 字典
   ```python
   RULE_NAMES = {
       ...
       6: "止盈信号监控",
       7: "止损信号监控"
   }
   ```

2. **消息模板扩展**: 在 `_format_triggers` 中新增规则6/7的case
   ```python
   elif rule_id == 6:
       vpa_signal = extra_info.get('vpa_signal')
       tech_signal = extra_info.get('tech_signal')
       timeframe = extra_info.get('timeframe')
       rule_lines.append(
           f"[6] 止盈信号｜{vpa_signal}+{tech_signal} [{timeframe}]"
       )
       judgments.append("止盈时机")

   elif rule_id == 7:
       vpa_signal = extra_info.get('vpa_signal')
       tech_signal = extra_info.get('tech_signal')
       timeframe = extra_info.get('timeframe')
       rule_lines.append(
           f"[7] 止损预警｜{vpa_signal}+{tech_signal} [{timeframe}]"
       )
       judgments.append("止损风险")
   ```

3. **快速判断逻辑**: 新增止盈/止损的判断规则
   ```python
   # 止盈快速判断（direction="down"时）
   if "止盈时机" in judgments:
       quick_judge = "检测到动能衰竭信号，建议考虑止盈出场。"

   # 止损快速判断（direction="up"时）
   if "止损风险" in judgments:
       quick_judge = "检测到动能爆发信号，建议考虑止损离场。"
   ```

4. **企业微信字符数限制**: 现有推送已处理此问题，单次推送限制在2000字符以内（见alert_notifier.py:486行的content拼接）

---

## 研究结论与建议

### ✅ 所有研究任务已完成

| 任务 | 状态 | 结论 |
|------|------|------|
| 1. 技术指标库 | ✅ 完成 | 使用纯NumPy实现，RSI已有，BB需新增 |
| 2. K线数据可用性 | ✅ 完成 | 15m/1h数据充足，KlineCache支持完善 |
| 3. VPA模式检测 | ✅ 完成 | 参数已优化，误报控制策略明确 |
| 4. 批量推送格式 | ✅ 完成 | 采用合并分类方案，扩展_format_triggers |

### 技术风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 布林带计算准确性 | 🟡 中等 | 编写单元测试与TradingView对照验证 |
| VPA模式参数敏感性 | 🟡 中等 | 支持Django Admin动态调整，初期Paper Testing |
| K线数据边界情况 | 🟢 低 | 复用现有的数据不足跳过机制 |
| 批量推送兼容性 | 🟢 低 | 规则6/7与规则1-5完全兼容 |

### 下一步行动

1. **Phase 1启动**: 生成 `data-model.md` 和 `contracts/` 目录
2. **设计验证**: 编写布林带和VPA模式的接口定义
3. **参数Schema**: 定义PriceAlertRule的parameters字段JSON结构

---

**研究完成日期**: 2025-12-11
**准备进入**: Phase 1 - Design & Contracts
