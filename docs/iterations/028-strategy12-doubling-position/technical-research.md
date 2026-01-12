# 技术调研: 策略12 - 倍增仓位限价挂单

## 文档信息

| 属性 | 值 |
|------|-----|
| 迭代编号 | 028 |
| 迭代名称 | strategy12-doubling-position |
| 版本 | 1.0 |
| 状态 | Draft |
| 创建日期 | 2026-01-11 |
| 关联PRD | prd.md |

---

## 1. 架构兼容性评估

### 1.1 现有组件复用分析

| 组件 | 复用程度 | 说明 |
|------|----------|------|
| **LimitOrderManager** | ✅ 完全复用 | 挂单生命周期管理、资金冻结/解冻 |
| **LimitOrderPriceCalculator** | ✅ 部分复用 | calculate_buy_prices()可复用，需扩展支持不同order_interval |
| **PendingOrder** | ✅ 完全复用 | 挂单数据结构 |
| **UnifiedOrderManager** | ✅ 完全复用 | 持仓订单管理 |
| **DDPSZAdapter** | ✅ 扩展 | 新增strategy_id=12路由 |
| **ProjectLoader** | ✅ 扩展 | 解析新配置参数(multiplier, base_amount) |

### 1.2 新增组件

| 组件 | 类型 | 说明 |
|------|------|------|
| **DoublingPositionStrategy** | 新增 | 策略12核心类 |
| **TakeProfitExit** | 新增 | 固定比例止盈Exit条件 |
| **DoublingAmountCalculator** | 新增 | 倍增金额计算器（可内嵌于策略类） |

### 1.3 接口变更评估

| 接口 | 变更类型 | 影响范围 |
|------|----------|----------|
| LimitOrderPriceCalculator.__init__ | 无变更 | 复用现有参数 |
| LimitOrderManager.create_buy_order | 参数扩展 | 支持自定义amount（原为固定position_size） |
| DDPSZAdapter.process_kline | 扩展路由 | 新增strategy_id=12分支 |

---

## 2. 技术风险分析

### 2.1 风险识别

| 风险 | 等级 | 影响 | 缓解措施 |
|------|------|------|----------|
| LimitOrderManager.create_buy_order不支持自定义金额 | 中 | 需修改接口 | 扩展方法参数，保持向后兼容 |
| 倍增金额总和超过initial_cash | 低 | 资金不足 | 资金不足时跳过，已有处理逻辑 |
| 配置参数校验 | 低 | 无效配置 | 添加参数校验逻辑 |

### 2.2 技术决策

#### 决策1: LimitOrderManager.create_buy_order接口扩展

**问题**: 现有接口使用固定position_size，策略12需要每笔不同金额

**方案**:
```python
# 方案A: 扩展参数（推荐）
def create_buy_order(
    self,
    price: Decimal,
    kline_index: int,
    timestamp: int,
    amount: Optional[Decimal] = None  # 新增可选参数
) -> Optional[PendingOrder]:
    actual_amount = amount if amount else self.position_size
    ...
```

**决策**: 方案A - 扩展参数，保持向后兼容

#### 决策2: 倍增金额计算位置

**方案**:
- A) 独立DoublingAmountCalculator类
- B) 内嵌于DoublingPositionStrategy

**决策**: 方案B - 逻辑简单，直接内嵌于策略类

---

## 3. 技术选型确认

| 技术点 | 选型 | 理由 |
|--------|------|------|
| 策略实现 | 独立DoublingPositionStrategy类 | 职责清晰，不影响策略11 |
| 止盈Exit | 新增TakeProfitExit类 | 实现IExitCondition接口，可复用 |
| 配置格式 | JSON | 与现有项目配置一致 |

---

## 4. Q-Gate 3 检查清单

- [x] 架构兼容性已评估
- [x] 技术选型已确认
- [x] 技术风险已识别
- [x] 复用组件已明确
- [x] 接口变更影响可控

---

## 5. 下一步

✅ Q-Gate 3 通过，可进入 P4: 架构快速设计
