# 任务计划: 买卖订单追踪系统

**迭代编号**: 012
**文档版本**: v1.0.0
**创建日期**: 2026-01-06
**总任务数**: 12个
**预计工作量**: 2天

---

## Phase 1: 后端核心实现

### TASK-012-001: 创建OrderTracker计算器

**状态**: ✅ 已完成

**描述**: 创建订单追踪计算器，实现订单创建、卖出检测、盈亏计算核心逻辑

**文件变更**:
- 🆕 `ddps_z/calculators/order_tracker.py`

**实现要点**:
1. 定义数据类：VirtualOrder、OrderStatistics、TradeEvent
2. 实现`create_orders_from_signals()`：从买入信号创建订单
3. 实现`check_sell_condition()`：检测EMA25回归卖出
4. 实现`calculate_profit()`：计算单笔盈亏
5. 实现`calculate_floating_profit()`：计算浮动盈亏
6. 实现`track()`主方法：编排所有计算逻辑

**验收标准**:
- [x] VirtualOrder包含所有必要字段
- [x] 订单创建时buy_quantity = 100 / buy_price
- [x] EMA25在K线[low, high]区间内时正确触发卖出
- [x] 盈亏计算精度使用Decimal

**依赖**: 无

---

### TASK-012-002: 实现统计汇总计算

**状态**: ✅ 已完成

**描述**: 实现订单统计汇总逻辑

**文件变更**:
- 📝 `ddps_z/calculators/order_tracker.py`

**实现要点**:
1. 实现`calculate_statistics()`方法
2. 计算total_orders、sold_orders、holding_orders
3. 计算win_orders、lose_orders、win_rate
4. 计算total_profit、floating_profit
5. 计算avg_profit_rate、avg_holding_periods

**验收标准**:
- [x] 胜率 = win_orders / sold_orders * 100
- [x] 浮动盈亏为所有holding订单浮动盈亏之和
- [x] 无已卖出订单时胜率为0或None

**依赖**: TASK-012-001

---

### TASK-012-003: 实现交易事件生成

**状态**: ✅ 已完成

**描述**: 从订单生成操作日志事件

**文件变更**:
- 📝 `ddps_z/calculators/order_tracker.py`

**实现要点**:
1. 实现`generate_trade_events()`方法
2. 每个订单生成一个买入事件
3. 已卖出订单额外生成卖出事件
4. 按时间戳倒序排列

**验收标准**:
- [x] 买入事件包含时间、价格、数量、金额
- [x] 卖出事件额外包含盈亏
- [x] 事件按时间倒序排列

**依赖**: TASK-012-001

---

### TASK-012-004: 导出OrderTracker到模块

**状态**: ✅ 已完成

**描述**: 在calculators包中导出OrderTracker

**文件变更**:
- 📝 `ddps_z/calculators/__init__.py`

**实现要点**:
1. 添加`from .order_tracker import OrderTracker`
2. 添加到`__all__`列表

**验收标准**:
- [x] 可以通过`from ddps_z.calculators import OrderTracker`导入

**依赖**: TASK-012-001

---

### TASK-012-005: 扩展ChartDataService

**状态**: ✅ 已完成

**描述**: 在ChartDataService中集成OrderTracker，返回订单数据

**文件变更**:
- 📝 `ddps_z/services/chart_data_service.py`

**实现要点**:
1. 在`get_chart_data()`中实例化OrderTracker
2. 调用`track()`获取订单数据
3. 在chart响应中添加orders、order_statistics、trade_events字段
4. 获取当前价格用于计算浮动盈亏

**验收标准**:
- [x] API响应包含orders数组
- [x] API响应包含order_statistics对象
- [x] API响应包含trade_events数组
- [x] 现有字段完全不变（向后兼容）

**依赖**: TASK-012-004

---

## Phase 2: 单元测试

### TASK-012-006: 编写OrderTracker单元测试

**状态**: 待完成

**描述**: 编写订单追踪计算器的完整单元测试

**文件变更**:
- 🆕 `ddps_z/tests/test_order_tracker.py`

**测试用例**:
1. test_create_order_from_signal: 订单正确创建
2. test_buy_quantity_calculation: 买入数量 = 100 / 价格
3. test_sell_condition_triggered: EMA25在区间内触发卖出
4. test_sell_condition_not_triggered: EMA25不在区间内不触发
5. test_profit_calculation_win: 盈利订单盈亏正确
6. test_profit_calculation_lose: 亏损订单盈亏正确
7. test_floating_profit: 持仓订单浮动盈亏
8. test_statistics_calculation: 统计汇总正确
9. test_win_rate_calculation: 胜率计算正确
10. test_trade_events_generation: 事件生成正确
11. test_trade_events_order: 事件按时间倒序

**验收标准**:
- [ ] 所有测试用例通过
- [ ] 覆盖核心计算逻辑

**依赖**: TASK-012-003

---

## Phase 3: 前端实现

### TASK-012-007: 实现统计面板组件

**状态**: ✅ 已完成

**描述**: 在详情页顶部添加订单统计面板

**文件变更**:
- 📝 `ddps_z/templates/ddps_z/detail.html`

**实现要点**:
1. 在页面顶部添加统计面板HTML结构
2. 实现`renderStatisticsPanel()`函数
3. 盈利显示绿色，亏损显示红色
4. 胜率使用百分比格式
5. 金额保留2位小数

**验收标准**:
- [x] 显示6项统计指标
- [x] 颜色正确（盈利绿/亏损红）
- [x] 响应式布局（移动端适配）

**依赖**: TASK-012-005

---

### TASK-012-008: 实现卖出点标记渲染

**状态**: ✅ 已完成

**描述**: 在K线图上渲染卖出点标记

**文件变更**:
- 📝 `ddps_z/templates/ddps_z/detail.html`

**实现要点**:
1. 实现`renderSellMarkers()`函数
2. 红色向下箭头，位置aboveBar
3. 与买入标记合并使用setMarkers
4. 只渲染已卖出订单的卖出点

**验收标准**:
- [x] 卖出点显示红色向下箭头
- [x] 位置在K线上方
- [x] 不覆盖买入标记

**依赖**: TASK-012-005

---

### TASK-012-009: 扩展悬浮Card显示订单信息

**状态**: ✅ 已完成

**描述**: 在买入点悬浮Card中添加订单状态和盈亏信息

**文件变更**:
- 📝 `ddps_z/templates/ddps_z/detail.html`

**实现要点**:
1. 修改`showBuySignalCard()`函数
2. 根据时间戳匹配对应订单
3. 显示订单状态（持仓中/已卖出）
4. 显示盈亏信息（如已卖出）
5. 显示持仓周期

**验收标准**:
- [x] Card显示订单状态
- [x] 已卖出订单显示卖出信息和盈亏
- [x] 持仓订单显示浮动盈亏

**依赖**: TASK-012-007

---

### TASK-012-010: 实现操作日志面板

**状态**: ✅ 已完成

**描述**: 在详情页底部添加操作日志面板

**文件变更**:
- 📝 `ddps_z/templates/ddps_z/detail.html`

**实现要点**:
1. 添加操作日志面板HTML结构
2. 实现`renderTradeEvents()`函数
3. 买入事件绿色标识，卖出事件红色标识
4. 显示时间、价格、数量、盈亏
5. 设置最大高度和滚动

**验收标准**:
- [x] 日志按时间倒序显示
- [x] 买入/卖出事件颜色区分
- [x] 卖出事件显示盈亏

**依赖**: TASK-012-005

---

### TASK-012-011: 实现日志筛选功能

**状态**: ✅ 已完成

**描述**: 实现操作日志的筛选功能

**文件变更**:
- 📝 `ddps_z/templates/ddps_z/detail.html`

**实现要点**:
1. 添加筛选按钮组（全部/买入/卖出）
2. 实现筛选逻辑
3. 按钮高亮当前选中状态
4. 筛选状态保存到state

**验收标准**:
- [x] 点击"买入"只显示买入事件
- [x] 点击"卖出"只显示卖出事件
- [x] 点击"全部"显示所有事件

**依赖**: TASK-012-010

---

## Phase 4: 集成测试

### TASK-012-012: 端到端功能验证

**状态**: 进行中

**描述**: 验证完整功能流程

**验证项目**:
1. 页面加载正常
2. 统计面板数据正确
3. 买入/卖出标记正确显示
4. 悬浮Card显示订单信息
5. 操作日志正确渲染
6. 筛选功能正常工作
7. 现有功能不受影响（回归测试）

**验收标准**:
- [ ] 所有功能正常工作
- [ ] 无控制台错误
- [ ] 性能符合要求（<1s加载）

**依赖**: TASK-012-011

---

## 任务依赖图

```
TASK-012-001 (OrderTracker核心)
    ├── TASK-012-002 (统计计算)
    ├── TASK-012-003 (事件生成)
    │       └── TASK-012-006 (单元测试)
    └── TASK-012-004 (模块导出)
            └── TASK-012-005 (API扩展)
                    ├── TASK-012-007 (统计面板)
                    │       └── TASK-012-009 (Card扩展)
                    ├── TASK-012-008 (卖出标记)
                    └── TASK-012-010 (操作日志)
                            └── TASK-012-011 (日志筛选)
                                    └── TASK-012-012 (集成测试)
```

---

## 执行顺序

1. **Day 1 上午**: TASK-012-001, TASK-012-002, TASK-012-003
2. **Day 1 下午**: TASK-012-004, TASK-012-005, TASK-012-006
3. **Day 2 上午**: TASK-012-007, TASK-012-008, TASK-012-009
4. **Day 2 下午**: TASK-012-010, TASK-012-011, TASK-012-012

---

**文档状态**: ✅ 任务计划完成
**下一步**: 开始执行 TASK-012-001
