# 技术调研报告 - 量化回测指标系统

**迭代编号**: 014
**分支**: 待创建
**报告日期**: 2026-01-06
**生命周期阶段**: P3 - 技术调研

---

## 1. 现有架构调研报告

### 1.1 现有系统概览

**架构模式**: Django单体应用 + 模块化分层设计
- **应用层**: 策略实现（DDPSZStrategy等）
- **适配层**: 策略适配层（strategy_adapter模块，迭代013实现）
- **数据层**: Django ORM（backtest.KLine等）

**技术栈**:
- **后端框架**: Django 4.x + Python 3.12
- **数据库**: PostgreSQL（主要）/ SQLite（测试）
- **数据处理**: pandas 2.x, numpy, Decimal（精度计算）
- **回测引擎**: 自研策略适配层（不使用vectorbt，迭代013已明确）
- **前端展示**: 当前无（仅CLI输出）

**部署方式**: 本地开发环境

### 1.2 现有服务清单

| 服务名称 | 类型 | 职责 | 可复用性 | 复用方式 | 备注 |
|---------|------|------|---------|---------|------|
| **UnifiedOrderManager** | Atomic | 订单创建、更新、查询、基础统计 | 高 | 直接复用 | 迭代013核心组件 |
| **StrategyAdapter** | Orchestration | 策略回测流程编排 | 高 | 接口扩展 | 需扩展返回权益曲线 |
| **Order数据类** | Data Model | 订单数据结构 | 高 | 直接复用 | 已有profit_loss等字段 |
| **run_strategy_backtest** | CLI Command | 命令行回测入口 | 高 | 参数扩展 | 需新增--risk-free-rate, --save-to-db |
| **KLine模型** | Data Model | K线数据存储 | 高 | 直接复用 | 提供历史价格数据 |
| **BacktestResult模型** | Data Model | 回测结果存储 | 中 | 需评估是否复用 | backtest/models.py中已存在 |

### 1.3 架构规范与模式

**设计原则**:
- **SOLID原则**: 单一职责、开闭原则（迭代013架构决策）
- **依赖注入**: UnifiedOrderManager可通过构造函数注入
- **无状态设计**: IStrategy接口强制策略无状态
- **Decimal精度**: 所有金额和百分比计算使用Decimal

**编码规范**:
- 使用dataclass定义数据结构
- 使用logger记录关键操作
- 方法命名：calculate_xxx(), get_xxx()
- 完整的类型提示（typing模块）

**架构模式**:
- **适配器模式**: StrategyAdapter适配应用层策略
- **策略模式**: IStrategy接口 + 多策略实现
- **工厂模式**: 订单创建由UnifiedOrderManager统一管理

### 1.4 技术债务与限制

**已知问题**:
- 无权益曲线跟踪：UnifiedOrderManager仅计算总盈亏，不跟踪时间序列净值
- 无量化指标计算：仅有基础统计（胜率、盈亏），缺少MDD、夏普率等专业指标
- 无数据持久化：回测结果仅在终端输出，不保存到数据库
- 无前端展示：缺少Web UI查看回测结果

**性能瓶颈**:
- K线数据加载：大规模回测时需要优化查询
- 权益曲线重建：事后重建可能较慢（需要遍历所有K线）

**维护难点**:
- 指标计算逻辑分散：需要集中到独立模块

### 1.5 复用建议

**高复用服务**:
1. **UnifiedOrderManager**: 直接复用订单管理能力
   - 已有：create_order(), update_order(), calculate_statistics()
   - 新增：无需修改，MetricsCalculator作为独立模块调用
2. **Order数据类**: 直接复用订单数据结构
   - 已有字段足够：profit_loss, profit_loss_rate, open_timestamp, close_timestamp等
3. **run_strategy_backtest命令**: 扩展CLI参数
   - 新增：--risk-free-rate, --save-to-db

**技术栈复用**:
- 继续使用Django ORM进行数据持久化
- 继续使用pandas处理K线数据
- 继续使用Decimal保证精度

**架构模式复用**:
- 遵循单一职责原则：MetricsCalculator独立于OrderManager
- 遵循依赖注入：MetricsCalculator接受订单列表作为参数
- 遵循无状态设计：MetricsCalculator每次计算独立

---

## 2. 核心技术选型

### 2.1 前端技术栈

#### 方案A：Django模板 + Bootstrap CSS + Chart.js（推荐）

**适用场景**: 回测结果后台展示

**优势**:
- ✅ 与Django深度集成，无需前后端分离
- ✅ Bootstrap提供开箱即用的响应式组件
- ✅ Chart.js轻量级，适合权益曲线图展示
- ✅ 团队熟悉度高（Django模板是标准技能）
- ✅ 无需额外构建工具（Webpack等）

**风险**:
- ⚠️ 交互能力有限（相比React/Vue）
- ⚠️ 大规模数据可视化性能一般

**MVP适用性**: ✅ 高（最小技术栈，快速上线）

#### 方案B：Django REST + React（不推荐）

**适用场景**: 复杂交互式前端

**优势**:
- ✅ 交互能力强
- ✅ 生态丰富（ECharts、Ant Design等）

**风险**:
- ❌ 需要前后端分离架构
- ❌ 增加开发复杂度（API设计、CORS等）
- ❌ 违反MVP原则（过度工程）

**MVP适用性**: ❌ 低（不符合MVP最小原则）

**⭐ 推荐方案**: 方案A（Django模板 + Bootstrap + Chart.js）

**推荐理由**:
1. **MVP优先**: 最小技术栈，避免前后端分离复杂度
2. **快速迭代**: Django模板开发速度快
3. **功能满足**: 权益曲线图用Chart.js足够
4. **后续演进**: 未来可替换为React（可逆性高）

---

### 2.2 后端技术栈

#### 方案A：纯Python（numpy/pandas）实现指标计算（推荐）

**适用场景**: MetricsCalculator核心指标计算

**优势**:
- ✅ 无外部依赖，代码可控
- ✅ 与现有技术栈一致（pandas/numpy已使用）
- ✅ 易于单元测试
- ✅ 符合constitution.md的"借鉴现有代码"原则

**风险**:
- ⚠️ 需要自行实现算法（如波动率、夏普率）

**MVP适用性**: ✅ 高（完全掌控，无黑盒）

#### 方案B：引入QuantStats库（不推荐）

**适用场景**: 量化指标计算

**优势**:
- ✅ 开箱即用，包含所有常见指标

**风险**:
- ❌ 新增外部依赖（违反"无充分理由前不引入新工具"）
- ❌ 黑盒实现，难以定制
- ❌ 可能与现有Decimal精度策略冲突

**MVP适用性**: ❌ 低（过度依赖外部库）

**⭐ 推荐方案**: 方案A（纯Python实现）

**推荐理由**:
1. **技术栈一致性**: 复用pandas/numpy
2. **可测试性**: 算法实现透明，易于验证
3. **灵活性**: 可定制指标计算逻辑
4. **遵循宪章**: "在没有充分理由前，不要引入新工具"

---

### 2.3 数据存储方案

#### 方案A：Django ORM + PostgreSQL JSONField（推荐）

**适用场景**: 回测结果和权益曲线存储

**数据结构**:
```python
class BacktestResult(models.Model):
    # 基本信息
    strategy_name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=20)

    # JSON字段（灵活存储）
    equity_curve = models.JSONField()  # [{timestamp, equity}, ...]
    metrics = models.JSONField()  # {apr: 12.5, mdd: -8.4, ...}
```

**优势**:
- ✅ 复用现有数据库（PostgreSQL）
- ✅ JSONField灵活存储复杂数据
- ✅ 无需引入新存储技术
- ✅ Django ORM提供查询能力

**风险**:
- ⚠️ JSON字段查询能力有限（不影响MVP）
- ⚠️ 权益曲线可能很大（数千个时间点）

**MVP适用性**: ✅ 高（最小改动）

#### 方案B：时序数据库（InfluxDB）（不推荐）

**适用场景**: 大规模时序数据存储

**优势**:
- ✅ 专为时序数据设计

**风险**:
- ❌ 需要新增数据库依赖
- ❌ 增加运维复杂度
- ❌ 违反MVP原则

**MVP适用性**: ❌ 低（过度工程）

**⭐ 推荐方案**: 方案A（PostgreSQL JSONField）

**推荐理由**:
1. **复用现有**: 无需新增数据库
2. **灵活性**: JSON字段适合动态数据
3. **MVP原则**: 最小技术栈
4. **可演进性**: 未来可迁移到专业时序数据库

---

## 3. 关键技术决策点

### 决策点1: 权益曲线生成方式

**问题描述**: 如何生成回测过程中每个时间点的账户净值（权益曲线）？

**逻辑阐述**:
- **为何重要**: 权益曲线是计算MDD、波动率等核心风险指标的基础数据
- **影响范围**: 影响StrategyAdapter数据流、MetricsCalculator输入、计算准确性

**方案A（推荐）**: 事后从订单记录重建

**描述**:
回测完成后，从订单列表和K线数据重建权益曲线

**算法**:
```python
def build_from_orders(orders, klines, initial_cash):
    equity_curve = []
    for kline in klines:
        # 计算持仓市值
        position_value = sum(
            order.quantity * kline.close
            for order in orders if order.status == 'holding'
        )
        # 计算账户净值
        equity = cash + position_value
        equity_curve.append({
            'timestamp': kline.open_time,
            'equity': equity
        })
    return equity_curve
```

**优点**:
- ✅ 实现简单，不修改回测主流程
- ✅ 符合MVP最小改动原则
- ✅ 无性能影响（回测过程）
- ✅ 符合constitution.md的单一职责原则

**缺点**:
- ⚠️ 需要额外计算步骤（事后重建）
- ⚠️ 需要重新遍历K线数据

**实现复杂度**: 低
**MVP适配性**: ✅ 高（最小改动）

---

**方案B**: 回测过程中实时记录

**描述**:
在StrategyAdapter.adapt_for_backtest()中，每次订单变动时记录净值

**优点**:
- ✅ 数据准确，不需要重新计算

**缺点**:
- ❌ 需要修改StrategyAdapter主流程
- ❌ 增加回测过程复杂度（引入状态管理）
- ❌ 违反单一职责（StrategyAdapter关注策略编排，不应管理权益曲线）

**实现复杂度**: 高
**MVP适配性**: ❌ 低（侵入性强）

**⭐ 推荐方案**: 方案A（事后重建）

**推荐理由**:
1. **MVP优先**: 最小改动，不修改核心回测流程
2. **单一职责**: EquityCurveBuilder独立工具类
3. **可测试性**: 可单独测试重建逻辑
4. **技术债务**: 方案A不引入技术债务，后续可无痛迁移到方案B

---

### 决策点2: 无风险收益率配置方式

**问题描述**: 如何配置无风险收益率（用于夏普率、索提诺比率计算）？

**逻辑阐述**:
- **为何重要**: 无风险收益率是风险调整收益指标的关键参数
- **影响范围**: 影响夏普率、索提诺比率计算准确性

**方案A（推荐）**: CLI参数配置

**描述**:
通过`--risk-free-rate`参数配置，默认值3%

**示例**:
```bash
python manage.py run_strategy_backtest ETHUSDT --risk-free-rate 3.0
```

**优点**:
- ✅ 灵活性高，用户可根据市场环境调整
- ✅ 符合现有CLI设计模式（与--commission-rate一致）
- ✅ 易于理解和使用

**缺点**:
- ⚠️ 需要用户了解无风险收益率含义（文档可解决）

**实现复杂度**: 低
**MVP适配性**: ✅ 高（符合现有模式）

---

**方案B**: 固定硬编码值

**描述**:
在MetricsCalculator中硬编码为3%

**优点**:
- ✅ 实现简单

**缺点**:
- ❌ 不灵活，无法适应不同市场环境
- ❌ 违反配置外部化原则

**实现复杂度**: 低
**MVP适配性**: ❌ 低（不符合设计原则）

**⭐ 推荐方案**: 方案A（CLI参数配置）

**推荐理由**:
1. **灵活性**: 适应不同市场环境（加密货币可能使用0%或更高）
2. **一致性**: 与--commission-rate参数设计一致
3. **默认值合理**: 3%是传统金融市场常见值
4. **可扩展性**: 未来可支持从配置文件读取

---

### 决策点3: 指标计算模块设计

**问题描述**: MetricsCalculator应该作为独立模块，还是集成到UnifiedOrderManager中？

**逻辑阐述**:
- **为何重要**: 影响代码架构、可测试性、可维护性
- **影响范围**: 影响StrategyAdapter调用方式、UnifiedOrderManager职责

**方案A（推荐）**: 独立的MetricsCalculator模块

**描述**:
创建独立的MetricsCalculator类，接受订单列表、权益曲线等数据作为输入

**类定义**:
```python
class MetricsCalculator:
    def __init__(self, risk_free_rate=Decimal("0.03")):
        self.risk_free_rate = risk_free_rate

    def calculate_all_metrics(self, orders, equity_curve, initial_cash, days):
        """计算所有P0指标，返回完整字典"""
        return {
            'apr': self.calculate_apr(...),
            'mdd': self.calculate_mdd(...),
            'sharpe_ratio': self.calculate_sharpe_ratio(...),
            # ... 其他15个指标
        }
```

**优点**:
- ✅ 单一职责：MetricsCalculator只负责计算
- ✅ 可测试性：可独立测试
- ✅ 可复用性：其他模块也可复用
- ✅ 符合SOLID原则（constitution.md强调）

**缺点**:
- ⚠️ 需要多一个类

**实现复杂度**: 中
**MVP适配性**: ✅ 高（符合设计原则）

---

**方案B**: 扩展UnifiedOrderManager

**描述**:
在UnifiedOrderManager中添加calculate_metrics()方法

**优点**:
- ✅ 实现简单，不需要新类

**缺点**:
- ❌ 违反单一职责原则（订单管理 + 指标计算）
- ❌ 降低可测试性
- ❌ 增加UnifiedOrderManager复杂度

**实现复杂度**: 低
**MVP适配性**: ❌ 低（违反设计原则）

**⭐ 推荐方案**: 方案A（独立的MetricsCalculator）

**推荐理由**:
1. **单一职责**: 符合constitution.md的SOLID原则
2. **可测试性**: MetricsCalculator可独立测试
3. **可维护性**: 指标计算逻辑独立，易于修改
4. **可扩展性**: 后续添加新指标只需修改MetricsCalculator
5. **符合架构原则**: 遵循迭代013的"单一职责"设计决策

---

### 决策点4: 数据持久化模型选择

**问题描述**: 是否复用backtest.BacktestResult模型，还是创建新的strategy_adapter.BacktestResult？

**逻辑阐述**:
- **为何重要**: 影响数据库设计、代码组织、模块耦合度
- **影响范围**: 影响models.py位置、URL路由、视图组织

**方案A（推荐）**: 在strategy_adapter中创建新的BacktestResult模型

**描述**:
在`strategy_adapter/models.py`（新建文件）中定义BacktestResult和BacktestOrder模型

**优点**:
- ✅ 模块独立性：strategy_adapter自包含
- ✅ 无耦合：不依赖backtest模块
- ✅ 清晰职责：回测结果属于策略适配层
- ✅ 未来扩展：strategy_adapter可独立演进

**缺点**:
- ⚠️ 数据模型重复（与backtest.BacktestResult可能类似）

**实现复杂度**: 中
**MVP适配性**: ✅ 高（模块化设计）

---

**方案B**: 扩展backtest.BacktestResult模型

**描述**:
在`backtest/models.py`中扩展现有BacktestResult模型

**优点**:
- ✅ 复用现有模型

**缺点**:
- ❌ 增加模块耦合（strategy_adapter依赖backtest）
- ❌ 职责不清：backtest模块用于Grid策略，strategy_adapter用于DDPS-Z等
- ❌ 违反单一职责

**实现复杂度**: 低
**MVP适配性**: ❌ 低（增加耦合）

**⭐ 推荐方案**: 方案A（strategy_adapter中新建模型）

**推荐理由**:
1. **模块独立性**: 符合constitution.md的单一职责原则
2. **清晰职责**: 回测结果属于策略适配层
3. **可演进性**: 未来strategy_adapter可独立发展
4. **解耦**: 减少模块间依赖

---

## 4. Gate 3 检查

### 检查清单

- [x] 所有P0功能的技术可行性已评估
- [x] 核心技术选型已完成决策（至少1个备选方案）
- [x] 关键技术风险已识别并有缓解措施
- [x] 技术调研报告结构完整
- [x] 现有架构调研完成（现有服务清单、架构规范）
- [x] 现有服务可复用性评估完成
- [x] 技术债务和演进路径识别完成
- [x] 迭代元数据已更新（待P4阶段创建iterations.json）

### 技术风险与缓解措施

| 风险项 | 风险等级 | 缓解措施 |
|-------|---------|---------|
| 权益曲线重建性能问题 | 中 | 方案：事后重建，仅在--save-to-db时执行；未来可优化为实时记录 |
| JSON字段存储大规模数据 | 低 | PostgreSQL JSONField支持大JSON，测试验证数千个时间点无问题 |
| Chart.js大规模数据渲染 | 低 | 数据点>1000时可抽样显示（显示关键点） |
| 指标计算准确性 | 中 | 方案：完整单元测试覆盖，与QuantStats结果对比验证 |

### Gate 3 检查结果

**✅ 通过** - 可以进入P4阶段

**通过理由**:
1. 所有P0功能点的技术可行性已评估
2. 4个关键技术决策点均有2+方案对比
3. 技术风险已识别并有缓解措施
4. 现有架构调研完整（服务清单、复用建议）
5. 技术选型符合MVP原则和constitution.md要求

---

**文档版本**: v1.0.0
**创建日期**: 2026-01-06
**P3阶段状态**: ✅ 已完成
**下一步**: 进入P4阶段（架构设计）
