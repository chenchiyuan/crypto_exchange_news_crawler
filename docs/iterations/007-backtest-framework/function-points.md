# Volume Trap 策略回测框架 - 功能点清单

## 概述
本功能点清单基于《Volume Trap 策略回测框架 - 产品需求文档 (PRD)》提取，用于指导开发实现。

---

## P0 功能点 (核心功能)

### 1. 回测数据模型
**模块**: `volume_trap/models_backtest.py`
**优先级**: P0
**类型**: 数据模型
**描述**: 创建BacktestResult和BacktestStatistics模型

#### 1.1 BacktestResult 模型
**字段**:
- monitor (ForeignKey): 关联异常事件
- symbol (CharField): 交易对符号
- interval (CharField): K线周期
- entry_time (DateTimeField): 入场时间
- entry_price (DecimalField): 入场价格
- lowest_time (DateTimeField): 最低点时间
- lowest_price (DecimalField): 最低价格
- bars_to_lowest (IntegerField): 到达最低点K线数
- max_profit_percent (DecimalField): 最大盈利百分比
- has_rebound (BooleanField): 是否反弹
- rebound_high_price (DecimalField): 反弹最高价
- rebound_percent (DecimalField): 反弹幅度
- max_drawdown_percent (DecimalField): 最大回撤
- exit_time (DateTimeField): 出场时间
- exit_price (DecimalField): 出场价格
- final_profit_percent (DecimalField): 最终收益率
- is_profitable (BooleanField): 是否盈利
- observation_bars (IntegerField): 观察K线数
- status (CharField): 回测状态

**约束条件**:
- monitor字段唯一（一对一关系）
- 价格字段精度：20位数字，8位小数
- 时间字段建立索引

**验收标准**:
- [ ] 模型定义完整
- [ ] 字段约束正确
- [ ] 数据库迁移成功
- [ ] 与VolumeTrapMonitor关联正确

#### 1.2 BacktestStatistics 模型
**字段**:
- name (CharField): 统计名称
- market_type (CharField): 市场类型
- interval (CharField): K线周期
- total_trades (IntegerField): 总交易数
- profitable_trades (IntegerField): 盈利交易数
- win_rate (DecimalField): 胜率
- avg_profit_percent (DecimalField): 平均收益率
- max_profit_percent (DecimalField): 最大单笔收益
- min_profit_percent (DecimalField): 最小单笔收益
- avg_max_drawdown (DecimalField): 平均最大回撤
- worst_drawdown (DecimalField): 最差回撤
- profit_factor (DecimalField): 盈亏比

**约束条件**:
- name字段唯一
- 百分比字段精度：10位数字，2位小数

**验收标准**:
- [ ] 模型定义完整
- [ ] 统计指标字段正确
- [ ] 索引建立合理

### 2. 回测引擎核心
**模块**: `volume_trap/services/backtest_engine.py`
**优先级**: P0
**类型**: 业务逻辑
**描述**: 实现单个异常事件的回测分析逻辑

#### 2.1 VolumeTrapBacktestEngine 类
**方法**:
- `run_backtest(monitor, observation_period)`: 运行单个回测
- `_get_entry_kline(monitor)`: 获取入场K线
- `_analyze_price_performance(entry_kline, holding_klines)`: 分析价格表现
- `_find_lowest_point(kline_list)`: 找到最低点
- `_find_rebound_point(kline_list, lowest_idx)`: 找到反弹点
- `_calculate_max_drawdown(entry_price, kline_list)`: 计算最大回撤
- `_calculate_final_result(entry_price, kline_list)`: 计算最终结果

**核心算法**:
- 最低点查找：遍历K线找到最低价，记录位置
- 反弹检测：最低点后找到反弹高点，计算反弹幅度
- 最大回撤：做空视角下持仓期间的最大浮亏
- 收益率计算：(入场价 - 出场价) / 入场价 × 100%

**验收标准**:
- [ ] 单次回测计算正确
- [ ] 边界条件处理正确（数据不足等）
- [ ] 回测结果保存成功
- [ ] 性能满足要求（<2秒）

#### 2.2 BatchBacktestRunner 类
**方法**:
- `run_batch_backtest(monitors_queryset, observation_period)`: 批量回测

**功能特性**:
- 支持筛选条件查询
- 错误处理和跳过机制
- 进度反馈

**验收标准**:
- [ ] 批量处理稳定
- [ ] 错误处理完善
- [ ] 执行报告详细

### 3. 整体统计服务
**模块**: `volume_trap/services/statistics_service.py`
**优先级**: P0
**类型**: 业务逻辑
**描述**: 计算整体策略的聚合统计指标

#### 3.1 StatisticsCalculator 类
**方法**:
- `calculate_overall_stats(backtest_results)`: 计算整体统计
- `calculate_win_rate(results)`: 计算胜率
- `calculate_profit_metrics(results)`: 计算收益指标
- `calculate_risk_metrics(results)`: 计算风险指标
- `calculate_time_metrics(results)`: 计算时间指标

**统计维度**:
- 按市场类型分组
- 按K线周期分组
- 按状态筛选分组

**验收标准**:
- [ ] 统计指标计算准确
- [ ] 支持多维度统计
- [ ] 统计结果持久化

---

## P1 功能点 (重要功能)

### 4. API接口
**模块**: `volume_trap/api_views.py`
**优先级**: P1
**类型**: 接口层
**描述**: 提供REST API供前端调用

#### 4.1 回测结果API
**端点**:
- `GET /api/volume-trap/backtest/{id}/`: 获取单个回测详情
- `GET /api/volume-trap/backtest/`: 批量查询回测结果
- `POST /api/volume-trap/backtest/run/`: 触发批量回测

**请求参数**:
- `id`: 回测结果ID
- `page`: 页码
- `page_size`: 每页数量
- `status`: 状态筛选
- `symbol`: 交易对筛选
- `interval`: 周期筛选

**响应格式**:
```json
{
  "id": 1,
  "symbol": "BTCUSDT",
  "interval": "4h",
  "entry_price": "98234.56",
  "final_profit_percent": "15.32",
  "max_profit_percent": "18.45",
  "max_drawdown_percent": "-3.21",
  "is_profitable": true,
  "created_at": "2024-12-26T10:00:00Z"
}
```

**验收标准**:
- [ ] API功能完整
- [ ] 响应格式统一
- [ ] 支持分页和排序
- [ ] 错误处理完善

#### 4.2 统计API
**端点**:
- `GET /api/volume-trap/statistics/`: 获取整体统计

**响应格式**:
```json
{
  "total_trades": 156,
  "profitable_trades": 98,
  "win_rate": "62.82",
  "avg_profit_percent": "8.45",
  "max_profit_percent": "25.67",
  "worst_drawdown": "-12.34",
  "profit_factor": "1.85"
}
```

**验收标准**:
- [ ] 统计数据准确
- [ ] 支持筛选条件
- [ ] 响应速度满足要求

### 5. 回测结果详情页
**模块**: `volume_trap/views/backtest_detail.py`
**优先级**: P1
**类型**: 页面
**描述**: 显示单个异常事件的完整回测分析

#### 5.1 页面结构
**组件**:
- **基本信息区域**: 交易对、周期、入场时间等
- **K线图表**: 使用Chart.js或类似库，显示K线并标注入场点、最低点、反弹点
- **指标面板**: 展示关键指标卡片
- **持仓数据表**: 显示持仓期间的详细价格数据

**图表要求**:
- X轴：时间
- Y轴：价格
- 标注：入场点（绿色）、最低点（红色）、反弹点（橙色）

**验收标准**:
- [ ] 页面布局清晰
- [ ] 图表标注准确
- [ ] 指标展示直观
- [ ] 响应式设计

### 6. 整体统计面板
**模块**: `volume_trap/views/statistics_dashboard.py`
**优先级**: P1
**类型**: 页面
**描述**: 展示整体策略表现统计

#### 6.1 页面结构
**组件**:
- **关键指标卡片**: 胜率、盈亏比、平均收益、最大回撤
- **收益分布图**: 直方图显示收益分布
- **回撤分析图**: 折线图显示回撤趋势
- **分组统计表**: 按周期、状态分组的详细统计

**验收标准**:
- [ ] 数据展示层次清晰
- [ ] 图表交互良好
- [ ] 支持数据导出

---

## P2 功能点 (增强功能)

### 7. 参数优化功能
**模块**: `volume_trap/services/parameter_optimizer.py`
**优先级**: P2
**类型**: 业务逻辑
**描述**: 支持不同持仓周期的回测对比

**功能**:
- 支持设置不同的持仓K线数（10、20、30等）
- 对比不同参数下的策略表现
- 推荐最优参数

**验收标准**:
- [ ] 参数对比功能完整
- [ ] 推荐算法合理

### 8. 回测报告导出
**模块**: `volume_trap/services/report_exporter.py`
**优先级**: P2
**类型**: 工具
**描述**: 导出详细的回测分析报告

**格式**:
- PDF报告（包含图表和详细数据）
- Excel表格（纯数据）

**验收标准**:
- [ ] 导出格式正确
- [ ] 包含完整数据
- [ ] 文件下载功能正常

---

## 技术依赖

### 数据库
- Django ORM
- PostgreSQL/MySQL

### 前端技术栈
- Django Templates
- Chart.js（图表库）
- Bootstrap或Tailwind CSS（样式）

### 后端依赖
- Django REST Framework（API）
- Pandas（数据处理，可选）

---

## 开发顺序建议

1. **阶段1**: 完成P0核心功能
   - 创建数据模型
   - 实现回测引擎
   - 实现统计服务

2. **阶段2**: 完成P1重要功能
   - 开发API接口
   - 实现前端页面
   - 集成测试

3. **阶段3**: 完成P2增强功能
   - 参数优化
   - 报告导出

---

## 测试要求

### 单元测试
- 回测引擎核心逻辑测试
- 统计计算测试
- API接口测试

### 集成测试
- 端到端回测流程测试
- 页面功能测试
- 数据一致性测试

### 性能测试
- 批量回测性能测试
- 大数据量查询测试

---

## 风险评估

### 技术风险
- **数据量风险**: K线数据量大，可能影响查询性能
  - **缓解措施**: 添加必要索引，优化查询语句

- **计算复杂度风险**: 批量回测计算量大
  - **缓解措施**: 使用异步任务，支持进度反馈

### 业务风险
- **指标准确性风险**: 回测指标计算可能存在偏差
  - **缓解措施**: 详细测试，交叉验证

### 集成风险
- **系统兼容性风险**: 与现有系统集成可能产生冲突
  - **缓解措施**: 充分测试，灰度发布
