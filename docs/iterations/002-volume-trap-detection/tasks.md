# 开发任务计划

**迭代编号**: 002
**迭代名称**: 巨量诱多/弃盘检测系统
**分支**: 002-volume-trap-detection
**创建日期**: 2024-12-24
**生命周期阶段**: P5 - 开发规划

---

## 任务统计

| 优先级 | 任务数 | 预估总工时 |
|-------|-------|-----------||
| P0 | 25个 | 45-55人天 |
| P1 | 5个 | 6-8人天 |
| P2 | 0个 | 0人天 |
| **总计** | **30个** | **51-63人天** |

---

## 📋 开发任务清单

### P0 核心功能 (Must Have)

---

#### **阶段一：基础设施与数据模型 (Foundation & Data Models)**

#### TASK-002-001: 创建Django应用和数据模型

- **关联需求**: [prd.md 第二部分-2.2节 数据模型设计]
- **关联架构**: [architecture.md 持久化层]
- **任务描述**:
  - 创建Django应用 `volume_trap`
  - 实现3个新模型：`VolumeTrapMonitor`, `VolumeTrapIndicators`, `VolumeTrapStateTransition`
  - 配置ForeignKey关联到 `monitor.FuturesContract`
  - 创建数据库索引优化查询性能

- **验收标准**:
  - [ ] Django应用 `volume_trap` 已创建并注册到 `INSTALLED_APPS`
  - [ ] 3个模型类已定义，符合PRD中的字段规范
  - [ ] `VolumeTrapMonitor` 包含唯一性约束：`unique_together = [['futures_contract', 'interval', 'trigger_time']]`
  - [ ] 所有索引已创建：`status`、`trigger_time`、`futures_contract`、`interval`
  - [ ] migration文件已生成且可成功执行
  - [ ] **异常路径验证**:
    - 重复触发时抛出 `IntegrityError`（唯一性约束）
    - 外键不存在时抛出 `ForeignKeyConstraintError`
  - [ ] **文档化标准合规** 📝
    - [ ] 3个模型类的docstring符合PEP 257规范
    - [ ] 通过 `scripts/check_doc_coverage.py` 验证

- **边界检查**:
  - 输入边界: `interval` 必须为 `['1h', '4h', '1d']` 之一
  - 资源状态: 确保 `FuturesContract` 表已存在且包含活跃合约数据
  - 数据完整性: 唯一性约束防止重复入库

- **预估工时**: 1.5人天

- **依赖关系**: 无（基础任务）

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试重复trigger_time触发（预期：IntegrityError）
    - 测试无效的interval值（预期：ValidationError）
  - 测试模型创建和关联查询
  - 测试索引是否生效（explain query计划）

- **文档要求**: ⭐
  - **接口契约注释**: 每个模型类需包含类级docstring，说明用途、关键字段、关联任务
  - **逻辑上下文注释**: 复杂字段（如status choices）需注释状态转换逻辑

- **状态**: 待开始

---

#### TASK-002-002: 配置项目参数和设置

- **关联需求**: [prd.md 第二部分-2.4节 技术参数配置]
- **关联架构**: [architecture.md 配置参数表]
- **任务描述**:
  - 在 `settings.py` 中添加 `VOLUME_TRAP_CONFIG` 配置字典
  - 定义9个可配置参数（RVOL_THRESHOLD=8, AMPLITUDE_THRESHOLD=3等）
  - 支持环境变量覆盖（便于测试和调优）

- **验收标准**:
  - [ ] `VOLUME_TRAP_CONFIG` 字典已定义，包含全部9个参数
  - [ ] 参数默认值符合PRD规范（如RVOL_THRESHOLD=8）
  - [ ] 支持通过环境变量覆盖（使用 `os.getenv` + 类型转换）
  - [ ] 配置参数有详细注释说明物理意义和单位
  - [ ] **异常路径验证**:
    - 环境变量类型错误时抛出 `ValueError`（携带预期类型和实际值）
  - [ ] **文档化标准合规** 📝
    - [ ] 配置字典有模块级docstring说明用途

- **边界检查**:
  - 输入边界: 数值类型参数必须>0，比例类型参数必须在0-1之间
  - 环境变量格式: 必须可转换为目标类型（int/float），否则抛出异常

- **预估工时**: 0.5人天

- **依赖关系**: 无

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试环境变量类型错误（如 `RVOL_THRESHOLD=abc`）
    - 测试参数边界值（如 `UPPER_SHADOW_THRESHOLD=1.5`，预期：ValidationError）
  - 测试默认值正确性
  - 测试环境变量覆盖功能

- **文档要求**: ⭐
  - **接口契约注释**: 每个配置参数需注释物理意义、单位、默认值理由

- **状态**: 待开始

---

#### **阶段二：检测器层实现 (Detector Layer Implementation)**

#### TASK-002-010: 实现RVOLCalculator（相对成交量计算器）

- **关联需求**: [function-points.md F2.1 RVOL计算引擎]
- **关联架构**: [architecture.md 检测器层-成交量检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/rvol_calculator.py`
  - 实现 `RVOLCalculator` 类，计算 `RVOL = V_current / MA(V, 20)`
  - 使用pandas向量化计算提升性能
  - 支持自定义lookback_period和threshold

- **验收标准**:
  - [ ] `RVOLCalculator` 类已实现，包含 `calculate()` 方法
  - [ ] 输入：symbol, interval, current_kline, threshold（默认8）
  - [ ] 输出：dict包含 `rvol_ratio`, `ma_volume`, `triggered`
  - [ ] 数据不足时（<21根K线）返回None并记录warning日志
  - [ ] 计算结果与Excel手工验证一致（误差<0.01%）
  - [ ] **异常路径验证**:
    - [ ] interval不合法时立即抛出 `ValueError(expected=['1h','4h','1d'], actual=...)`
    - [ ] K线数据不足时抛出 `DataInsufficientError(required=21, actual=...)`
    - [ ] current_kline.volume=0时抛出 `InvalidDataError(field='volume', value=0)`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和 `calculate()` 方法有完整的docstring（Args/Returns/Raises）
    - [ ] 通过 `sphinx-apidoc` 可生成API文档

- **边界检查**:
  - 输入边界:
    - `interval` 必须为 `['1h', '4h', '1d']`
    - `threshold` 必须 > 0
    - `lookback_period` 必须 >= 5 且 <= 100
  - 资源状态: KLine表必须有足够的历史数据（>= lookback_period + 1）
  - 数据质量: volume字段必须 > 0

- **预估工时**: 1.5人天

- **依赖关系**: [TASK-002-001]（依赖KLine模型）

- **测试策略**: 单元测试 + 集成测试
  - **异常测试**:
    - 测试invalid interval（预期：ValueError）
    - 测试数据不足场景（预期：DataInsufficientError）
    - 测试volume=0场景（预期：InvalidDataError）
  - 测试RVOL计算准确性（对比Excel公式）
  - 测试阈值触发逻辑
  - 测试pandas向量化性能（>100倍速度提升）

- **文档要求**: ⭐
  - **接口契约注释**:
    ```python
    def calculate(self, symbol: str, interval: str, threshold: float = 8.0) -> Optional[dict]:
        """计算相对成交量（RVOL）指标。

        Args:
            symbol: 交易对符号，如'BTCUSDT'
            interval: K线周期，必须为'1h', '4h', '1d'之一
            threshold: RVOL触发阈值，默认8倍

        Returns:
            Optional[dict]: 包含rvol_ratio, ma_volume, triggered。数据不足返回None。

        Raises:
            ValueError: interval不合法
            DataInsufficientError: K线数据不足21根

        Context:
            - PRD: F2.1 RVOL计算引擎
            - Task: TASK-002-010
        """
    ```
  - **逻辑上下文注释**: 向量化计算部分需注释性能优化原因

- **状态**: 待开始

---

#### TASK-002-011: 实现AmplitudeDetector（振幅异常检测器）

- **关联需求**: [function-points.md F2.2 振幅异常检测]
- **关联架构**: [architecture.md 检测器层-价格检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/amplitude_detector.py`
  - 实现振幅计算：`amplitude = (high - low) / low × 100`
  - 实现上影线比例：`upper_shadow = (high - close) / (high - low)`
  - 判断是否触发：`amplitude_ratio > 3 AND upper_shadow > 0.5`

- **验收标准**:
  - [ ] `AmplitudeDetector` 类已实现
  - [ ] 输出包含：`amplitude_ratio`, `upper_shadow_ratio`, `triggered`
  - [ ] 上影线比例计算正确（high=low时返回0）
  - [ ] 振幅倍数 = 当前振幅 / 过去30根均值
  - [ ] **异常路径验证**:
    - [ ] K线数据不足31根时抛出 `DataInsufficientError(required=31, actual=...)`
    - [ ] low_price=0时抛出 `InvalidDataError(field='low_price', value=0, context='除零错误')`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring
    - [ ] 上影线比例计算逻辑有注释说明边界处理

- **边界检查**:
  - 输入边界: K线数据必须>=31根
  - 数据质量: `low_price` 必须>0，`high_price` >= `low_price`

- **预估工时**: 2人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试数据不足场景
    - 测试low=0场景（除零错误）
    - 测试high<low场景（数据异常）
  - 测试振幅倍数计算
  - 测试上影线比例边界（high=low时应返回0）
  - 测试触发条件组合逻辑

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 上影线比例计算需注释业务含义（脉冲行为识别）

- **状态**: 待开始

---

#### TASK-002-012: 实现VolumeRetentionAnalyzer（成交量留存分析器）

- **关联需求**: [function-points.md F3.1 成交量留存率监控]
- **关联架构**: [architecture.md 检测器层-成交量检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/volume_retention_analyzer.py`
  - 计算触发后3-5根K线的平均成交量
  - 计算留存率：`retention_ratio = avg(V_post) / V_trigger × 100`
  - 判断是否<15%阈值

- **验收标准**:
  - [ ] `VolumeRetentionAnalyzer` 类已实现
  - [ ] 输入：Monitor记录、触发后K线列表、阈值（默认15%）
  - [ ] 输出：`avg_volume_post`, `retention_ratio`, `triggered`
  - [ ] 后续K线不足3根时返回None
  - [ ] **异常路径验证**:
    - [ ] V_trigger=0时抛出 `InvalidDataError(field='trigger_volume', value=0)`
    - [ ] 后续K线<3根时抛出 `DataInsufficientError(required=3, actual=...)`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring

- **边界检查**:
  - 输入边界: 后续K线数>=3
  - 数据质量: V_trigger > 0

- **预估工时**: 1.5人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试V_trigger=0场景
    - 测试后续K线不足场景
  - 测试留存率计算准确性
  - 测试阈值触发逻辑

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 注释业务规则（区分洗盘和弃盘）

- **状态**: 待开始

---

#### TASK-002-013: 实现KeyLevelBreachDetector（关键位跌破检测器）

- **关联需求**: [function-points.md F3.2 关键位跌破检测]
- **关联架构**: [architecture.md 检测器层-价格检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/key_level_breach_detector.py`
  - 计算关键位：`key_level = min((high+low)/2, low)`
  - 判断跌破：`current_close < key_level`
  - 计算跌破幅度

- **验收标准**:
  - [ ] `KeyLevelBreachDetector` 类已实现
  - [ ] 输入：触发K线high/low、当前close
  - [ ] 输出：`key_level`, `breach_percentage`, `triggered`
  - [ ] 中轴计算正确：`(trigger_high + trigger_low) / 2`
  - [ ] 关键位取min值正确
  - [ ] **异常路径验证**:
    - [ ] trigger_high < trigger_low时抛出 `InvalidDataError`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring

- **边界检查**:
  - 输入边界: trigger_high >= trigger_low
  - 数据质量: 所有价格字段>0

- **预估工时**: 1人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试high<low场景
  - 测试关键位计算
  - 测试跌破判断
  - 测试跌破幅度计算

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 注释关键位定义原因（支撑位识别）

- **状态**: 待开始

---

#### TASK-002-014: 实现PriceEfficiencyAnalyzer（价差效率分析器）

- **关联需求**: [function-points.md F3.3 价差效率计算]
- **关联架构**: [architecture.md 检测器层-价格检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/price_efficiency_analyzer.py`
  - 计算PE：`PE = |close - open| / volume`
  - 计算历史30天PE均值
  - 判断是否异常：`PE > 历史均值 × 2`

- **验收标准**:
  - [ ] `PriceEfficiencyAnalyzer` 类已实现
  - [ ] 输入：最近5根K线、历史30天K线、异常倍数（默认2）
  - [ ] 输出：`current_pe`, `historical_pe_mean`, `triggered`
  - [ ] PE计算处理volume=0情况（返回0或跳过）
  - [ ] **异常路径验证**:
    - [ ] K线数据不足时抛出 `DataInsufficientError`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring

- **边界检查**:
  - 输入边界: 历史K线数>=30根
  - 数据质量: volume字段处理0值情况

- **预估工时**: 2人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试数据不足场景
    - 测试volume=0场景（应跳过或返回0）
  - 测试PE计算准确性
  - 测试历史均值计算
  - 测试异常判断逻辑

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 注释业务含义（卖盘深度分析）

- **状态**: 待开始

---

#### TASK-002-015: 实现MovingAverageCrossDetector（均线交叉检测器）

- **关联需求**: [function-points.md F4.1 均线系统计算]
- **关联架构**: [architecture.md 检测器层-趋势检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/moving_average_cross_detector.py`
  - 计算MA(7)和MA(25)
  - 计算MA(25)斜率：`(MA25_current - MA25_prev) / MA25_prev`
  - 判断死叉：`MA(7) < MA(25) AND MA25_slope < 0`

- **验收标准**:
  - [ ] `MovingAverageCrossDetector` 类已实现
  - [ ] 输入：最近25根K线、短期周期（默认7）、长期周期（默认25）
  - [ ] 输出：`ma7`, `ma25`, `ma25_slope`, `death_cross`
  - [ ] MA计算使用pandas向量化
  - [ ] 斜率计算正确
  - [ ] **异常路径验证**:
    - [ ] K线不足25根时抛出 `DataInsufficientError`
    - [ ] MA25_prev=0时抛出 `InvalidDataError`（除零错误）
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring

- **边界检查**:
  - 输入边界: K线数>=25根
  - 数据质量: close_price必须>0

- **预估工时**: 1.5人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试数据不足场景
    - 测试MA25_prev=0场景
  - 测试MA计算准确性
  - 测试斜率计算
  - 测试死叉判断

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 注释业务含义（趋势反转识别）

- **状态**: 待开始

---

#### TASK-002-016: 实现OBVDivergenceAnalyzer（OBV背离分析器）

- **关联需求**: [function-points.md F4.2 OBV持续性分析]
- **关联架构**: [architecture.md 检测器层-趋势检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/obv_divergence_analyzer.py`
  - 计算OBV：`OBV[i] = OBV[i-1] + volume[i] × sign(close[i] - close[i-1])`
  - 检测底背离：价格新低时OBV未创新低
  - 判断单边下滑：连续5根K线无底背离

- **验收标准**:
  - [ ] `OBVDivergenceAnalyzer` 类已实现
  - [ ] 输入：最近N根K线（N可配置）、背离检测窗口（默认5）
  - [ ] 输出：`obv_series`, `divergence_detected`, `single_side_decline`
  - [ ] OBV计算公式正确
  - [ ] 底背离检测逻辑正确
  - [ ] **异常路径验证**:
    - [ ] K线不足时抛出 `DataInsufficientError`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring
    - [ ] OBV计算逻辑有详细注释

- **边界检查**:
  - 输入边界: K线数>=lookback_periods+1
  - 数据质量: volume必须>0

- **预估工时**: 2.5人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试数据不足场景
  - 测试OBV计算准确性
  - 测试底背离检测
  - 测试单边下滑判断

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: OBV计算和背离检测逻辑需详细注释

- **状态**: 待开始

---

#### TASK-002-017: 实现ATRCompressionDetector（ATR压缩检测器）

- **关联需求**: [function-points.md F4.3 ATR波动率压缩检测]
- **关联架构**: [architecture.md 检测器层-趋势检测器]
- **任务描述**:
  - 创建 `volume_trap/detectors/atr_compression_detector.py`
  - 计算TR：`TR = max(high-low, abs(high-close_prev), abs(low-close_prev))`
  - 计算ATR(14)：使用EMA平滑
  - 判断压缩：连续5根递减 AND ATR<历史均值×0.5

- **验收标准**:
  - [ ] `ATRCompressionDetector` 类已实现
  - [ ] 输入：最近14根K线（ATR）、最近30根K线（基线）、压缩阈值（默认0.5）
  - [ ] 输出：`atr_current`, `atr_baseline`, `is_decreasing`, `is_compressed`
  - [ ] TR计算正确
  - [ ] ATR(14)使用EMA平滑
  - [ ] 连续递减检测正确
  - [ ] **异常路径验证**:
    - [ ] K线不足30根时抛出 `DataInsufficientError`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring
    - [ ] TR和ATR计算逻辑有注释

- **边界检查**:
  - 输入边界: K线数>=30根
  - 数据质量: price字段必须>0

- **预估工时**: 2.5人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试数据不足场景
  - 测试TR计算
  - 测试ATR EMA平滑
  - 测试递减检测
  - 测试压缩判断

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: TR和EMA计算逻辑需注释

- **状态**: 待开始

---

#### **阶段三：状态机与条件评估器 (State Machine & Evaluator)**

#### TASK-002-020: 实现ConditionEvaluator（条件评估器）

- **关联需求**: [prd.md 第二部分-功能模块拆解]
- **关联架构**: [architecture.md 检测器层-条件评估器]
- **任务描述**:
  - 创建 `volume_trap/evaluators/condition_evaluator.py`
  - 实现3个评估方法：
    - `evaluate_discovery_condition()`: 组合RVOL + Amplitude
    - `evaluate_confirmation_condition()`: 组合VolumeRetention + KeyLevel + PE
    - `evaluate_validation_condition()`: 组合MA + OBV + ATR
  - 纯逻辑组合，无状态

- **验收标准**:
  - [ ] `ConditionEvaluator` 类已实现
  - [ ] 3个评估方法已实现，返回boolean
  - [ ] 评估逻辑清晰：AND组合多个检测结果
  - [ ] 输入为dict（检测器结果）
  - [ ] **异常路径验证**:
    - [ ] 输入dict缺少required key时抛出 `KeyError`
  - [ ] **文档化标准合规** 📝
    - [ ] 类和3个方法有完整docstring
    - [ ] 组合逻辑有注释说明

- **边界检查**:
  - 输入边界: 检测器结果dict必须包含required keys

- **预估工时**: 1.5人天

- **依赖关系**: [TASK-002-010 至 TASK-002-017]（依赖所有检测器）

- **测试策略**: 单元测试
  - **异常测试**:
    - 测试缺少key场景
  - 测试组合逻辑正确性
  - 测试边界条件（如某个检测器返回None）

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 组合条件需注释业务规则来源

- **状态**: 待开始

---

#### TASK-002-021: 实现VolumeTrapStateMachine（状态机核心）

- **关联需求**: [prd.md 第二部分-功能模块拆解]
- **关联架构**: [architecture.md 状态机管理层]
- **任务描述**:
  - 创建 `volume_trap/services/volume_trap_fsm.py`
  - 实现三阶段状态机逻辑：
    - Discovery（发现）: 全量扫描 → 创建Monitor记录
    - Confirmation（确认）: pending → suspected_abandonment
    - Validation（验证）: suspected → confirmed_abandonment
  - 使用依赖注入模式注入所有检测器
  - 调用ConditionEvaluator进行状态转换判断

- **验收标准**:
  - [ ] `VolumeTrapStateMachine` 类已实现
  - [ ] 构造函数注入8个检测器 + 1个评估器
  - [ ] `scan()` 方法实现三阶段扫描逻辑
  - [ ] 状态转换时创建StateTransition日志
  - [ ] 状态转换时创建Indicators快照（选择性存储）
  - [ ] 支持按interval参数筛选
  - [ ] **异常路径验证**:
    - [ ] 检测器返回None时跳过该交易对（记录warning）
    - [ ] 数据库写入失败时抛出并回滚事务
  - [ ] **文档化标准合规** 📝
    - [ ] 类和关键方法有完整docstring
    - [ ] 三阶段逻辑有详细注释

- **边界检查**:
  - 输入边界: interval必须为['1h','4h','1d']
  - 资源状态: 检测器必须已初始化
  - 事务完整性: 使用Django transaction.atomic确保原子性

- **预估工时**: 3-4人天

- **依赖关系**: [TASK-002-020]（依赖ConditionEvaluator）

- **测试策略**: 单元测试 + 集成测试
  - **异常测试**:
    - 测试检测器返回None场景
    - 测试数据库写入失败场景
  - 测试三阶段逻辑流转
  - 测试状态转换日志创建
  - 测试快照创建时机

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 三阶段逻辑需详细注释业务流程

- **状态**: 待开始

---

#### TASK-002-022: 实现InvalidationDetector（失效检测器）

- **关联需求**: [function-points.md F5.1 价格收复检测]
- **关联架构**: [architecture.md 状态机管理层]
- **任务描述**:
  - 创建 `volume_trap/services/invalidation_detector.py`
  - 检测价格收复：`current_close > P_trigger`
  - 更新status为invalidated
  - 记录StateTransition日志

- **验收标准**:
  - [ ] `InvalidationDetector` 类已实现
  - [ ] `check_all()` 方法扫描所有非invalidated记录
  - [ ] 收盘价>P_trigger时更新状态
  - [ ] 创建StateTransition日志
  - [ ] 支持按interval筛选
  - [ ] **异常路径验证**:
    - [ ] P_trigger=0时跳过（记录error）
  - [ ] **文档化标准合规** 📝
    - [ ] 类和方法有完整docstring

- **边界检查**:
  - 输入边界: interval必须为['1h','4h','1d']
  - 数据质量: P_trigger必须>0

- **预估工时**: 1人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 单元测试 + 集成测试
  - **异常测试**:
    - 测试P_trigger=0场景
  - 测试失效检测逻辑
  - 测试状态更新
  - 测试日志创建

- **文档要求**: ⭐
  - **接口契约注释**: 完整Args/Returns/Raises
  - **逻辑上下文注释**: 注释失效机制的业务含义

- **状态**: 待开始

---

#### **阶段四：Django Management Commands**

#### TASK-002-030: 实现update_klines命令

- **关联需求**: [function-points.md F6.1 K线数据更新任务]
- **关联架构**: [architecture.md 管理命令层]
- **任务描述**:
  - 创建 `volume_trap/management/commands/update_klines.py`
  - 触发KLineDataSyncService同步K线数据
  - 支持 `--interval` 参数
  - 记录详细日志

- **验收标准**:
  - [ ] Command类已实现，继承自BaseCommand
  - [ ] 支持 `--interval` 参数（1h/4h/1d）
  - [ ] 调用KLineDataSyncService.sync_all_contracts()
  - [ ] 输出成功/失败统计
  - [ ] 详细日志记录（info/warning/error级别）
  - [ ] **异常路径验证**:
    - [ ] interval参数错误时打印usage并退出（exit code=1）
    - [ ] 同步失败时记录error日志但不中断（容错机制）
  - [ ] **文档化标准合规** 📝
    - [ ] Command类有docstring说明用途
    - [ ] handle()方法有注释

- **边界检查**:
  - 输入边界: interval必须为['1h','4h','1d']
  - 执行频率: 每个周期结束后5分钟（由Cron控制）

- **预估工时**: 1.5人天

- **依赖关系**: [TASK-002-001]（复用现有KLine数据管道）

- **测试策略**: 集成测试
  - **异常测试**:
    - 测试invalid interval参数
    - 测试同步失败场景（模拟API错误）
  - 测试命令执行
  - 测试日志输出

- **文档要求**: ⭐
  - **接口契约注释**: Command类docstring
  - **逻辑上下文注释**: 关键步骤需注释

- **状态**: 待开始

---

#### TASK-002-031: 实现scan_volume_traps命令

- **关联需求**: [function-points.md F6.2 监控扫描任务]
- **关联架构**: [architecture.md 管理命令层]
- **任务描述**:
  - 创建 `volume_trap/management/commands/scan_volume_traps.py`
  - 调用VolumeTrapStateMachine.scan()
  - 支持 `--interval` 参数
  - 输出三阶段统计结果

- **验收标准**:
  - [ ] Command类已实现
  - [ ] 支持 `--interval` 参数
  - [ ] 调用FSM.scan()执行三阶段扫描
  - [ ] 输出统计：phase1_triggered, phase2_passed, phase3_passed
  - [ ] 详细日志记录
  - [ ] **异常路径验证**:
    - [ ] FSM异常时记录error并退出（exit code=1）
  - [ ] **文档化标准合规** 📝
    - [ ] Command类有docstring

- **边界检查**:
  - 输入边界: interval必须为['1h','4h','1d']
  - 执行频率: 每个周期结束后10分钟

- **预估工时**: 1.5人天

- **依赖关系**: [TASK-002-021]

- **测试策略**: 集成测试
  - **异常测试**:
    - 测试FSM异常场景
  - 测试命令执行
  - 测试统计输出

- **文档要求**: ⭐
  - **接口契约注释**: Command类docstring

- **状态**: 待开始

---

#### TASK-002-032: 实现check_invalidations命令

- **关联需求**: [function-points.md F6.3 失效检测任务]
- **关联架构**: [architecture.md 管理命令层]
- **任务描述**:
  - 创建 `volume_trap/management/commands/check_invalidations.py`
  - 调用InvalidationDetector.check_all()
  - 支持 `--interval` 参数
  - 输出失效记录数

- **验收标准**:
  - [ ] Command类已实现
  - [ ] 支持 `--interval` 参数
  - [ ] 调用InvalidationDetector.check_all()
  - [ ] 输出失效记录数统计
  - [ ] **异常路径验证**:
    - [ ] 检测器异常时记录error
  - [ ] **文档化标准合规** 📝
    - [ ] Command类有docstring

- **边界检查**:
  - 输入边界: interval必须为['1h','4h','1d']
  - 执行频率: 每个周期结束后15分钟

- **预估工时**: 1人天

- **依赖关系**: [TASK-002-022]

- **测试策略**: 集成测试
  - **异常测试**:
    - 测试检测器异常场景
  - 测试命令执行
  - 测试统计输出

- **文档要求**: ⭐
  - **接口契约注释**: Command类docstring

- **状态**: 待开始

---

#### **阶段五：REST API实现**

#### TASK-002-040: 实现MonitorListAPI（监控池列表）

- **关联需求**: [function-points.md F7.1 监控池列表API]
- **关联架构**: [architecture.md API服务层]
- **任务描述**:
  - 创建 `volume_trap/views.py` 和 `volume_trap/serializers.py`
  - 实现GET /api/volume-trap/monitors/
  - 支持status、interval筛选
  - 支持分页（page、page_size）
  - 返回Monitor记录 + 最新Indicators快照

- **验收标准**:
  - [ ] MonitorListAPIView已实现（继承DRF viewsets）
  - [ ] 支持query参数：status, interval, page, page_size
  - [ ] 返回JSON：monitors列表 + pagination信息
  - [ ] 每条记录包含最新Indicators快照
  - [ ] 响应时间<1秒（500条记录）
  - [ ] **异常路径验证**:
    - [ ] invalid status参数返回400（Bad Request）
    - [ ] page超出范围返回404
  - [ ] **文档化标准合规** 📝
    - [ ] APIView和Serializer有docstring

- **边界检查**:
  - 输入边界: status必须为['pending','suspected','confirmed','invalidated']
  - 分页: page>=1, page_size 1-100

- **预估工时**: 1.5人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 集成测试 + 性能测试
  - **异常测试**:
    - 测试invalid参数
    - 测试page超出范围
  - 测试API响应格式
  - 测试筛选逻辑
  - 测试分页功能
  - 测试性能（500条<1秒）

- **文档要求**: ⭐
  - **接口契约注释**: APIView和Serializer有docstring

- **状态**: 待开始

---

### P1 重要功能 (Should Have)

#### TASK-002-050: 实现MonitorDetailAPI（详情API）

- **关联需求**: [function-points.md F7.2 详情API]
- **关联架构**: [architecture.md API服务层]
- **任务描述**:
  - 实现GET /api/volume-trap/monitors/<id>/
  - 返回完整监控记录 + 所有Indicators快照 + StateTransition日志

- **验收标准**:
  - [ ] MonitorDetailAPIView已实现
  - [ ] 返回完整Monitor记录
  - [ ] 包含所有Indicators快照（按时间倒序）
  - [ ] 包含所有StateTransition日志
  - [ ] 响应时间<1秒
  - [ ] **异常路径验证**:
    - [ ] ID不存在返回404
  - [ ] **文档化标准合规** 📝

- **边界检查**:
  - 输入边界: ID必须为正整数

- **预估工时**: 1人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 集成测试
  - 测试API响应格式
  - 测试关联数据查询

- **文档要求**: ⭐

- **状态**: 待开始

---

#### TASK-002-051: 实现StatisticsAPI（统计API）

- **关联需求**: [function-points.md F7.3 统计API]
- **关联架构**: [architecture.md API服务层]
- **任务描述**:
  - 实现GET /api/volume-trap/stats/
  - 返回各状态数量、周期分布、近7天趋势

- **验收标准**:
  - [ ] StatisticsAPIView已实现
  - [ ] 支持interval筛选（可选）
  - [ ] 返回各状态数量统计
  - [ ] 返回各周期分布
  - [ ] 返回近7天新增趋势
  - [ ] 响应时间<1秒
  - [ ] **文档化标准合规** 📝

- **边界检查**:
  - 输入边界: interval为可选参数

- **预估工时**: 1人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 集成测试
  - 测试统计准确性
  - 测试趋势计算

- **文档要求**: ⭐

- **状态**: 待开始

---

#### TASK-002-052: 实现监控池清理策略

- **关联需求**: [function-points.md F5.2 监控池清理策略]
- **关联架构**: [architecture.md 失效机制]
- **任务描述**:
  - 创建Django management command: `cleanup_old_data`
  - 清理失效记录和过期记录（保留180天）
  - 软删除或归档

- **验收标准**:
  - [ ] cleanup_old_data命令已实现
  - [ ] 支持 `--days` 参数（默认180）
  - [ ] 失效记录立即标记可清理
  - [ ] 其他状态记录保留180天
  - [ ] 清理操作有日志记录
  - [ ] **文档化标准合规** 📝

- **边界检查**:
  - 输入边界: days>=1

- **预估工时**: 1人天

- **依赖关系**: [TASK-002-001]

- **测试策略**: 集成测试
  - 测试清理逻辑
  - 测试日志记录

- **文档要求**: ⭐

- **状态**: 待开始

---

#### TASK-002-053: 编写Crontab配置文档

- **关联需求**: [architecture.md 附录：Cron配置完整示例]
- **关联架构**: [architecture.md 部署架构图]
- **任务描述**:
  - 创建 `docs/iterations/002-volume-trap-detection/crontab-setup.md`
  - 提供1h/4h/1d周期的完整Crontab配置示例
  - 说明执行时机和依赖关系

- **验收标准**:
  - [ ] crontab-setup.md已创建
  - [ ] 包含完整的Cron配置示例
  - [ ] 说明执行时机（05分、10分、15分）
  - [ ] 说明日志路径配置
  - [ ] 包含维护任务配置（日志归档、数据清理）

- **预估工时**: 0.5人天

- **依赖关系**: [TASK-002-030, TASK-002-031, TASK-002-032]

- **测试策略**: 文档review
  - review Cron语法正确性
  - review时间配置合理性

- **文档要求**: ⭐

- **状态**: 待开始

---

## 技术任务

### 环境搭建

- [ ] **TASK-002-100**: 开发环境配置
  - 安装依赖：Django, DRF, pandas, numpy
  - 配置数据库（PostgreSQL）
  - 配置开发工具（black, flake8, pytest）
  - **预估工时**: 0.5人天

- [ ] **TASK-002-101**: CI/CD流水线设置
  - 配置GitHub Actions workflow
  - 添加测试覆盖率检查（pytest-cov, ≥80%）
  - 添加Linter检查（flake8）
  - **添加文档覆盖率检查** 📝 ⭐
    - 运行 `scripts/check_doc_coverage.py`
    - 要求100%公共接口覆盖
  - **预估工时**: 1人天

- [ ] **TASK-002-102**: 代码规范配置
  - 配置black格式化
  - 配置flake8规则
  - 配置pre-commit hooks
  - **预估工时**: 0.5人天

- [ ] **TASK-002-103**: 文档风格定义 ⭐ **新增**
  - 已完成（docs/comment-templates.md）
  - 配置Sphinx文档生成工具
  - 创建文档覆盖率检查脚本
  - **预估工时**: 1人天（已在Step 1.5完成）

### 基础设施

- [ ] **TASK-002-110**: 数据库迁移脚本
  - 执行 `python manage.py makemigrations volume_trap`
  - 执行 `python manage.py migrate`
  - 验证表结构和索引
  - **预估工时**: 0.5人天
  - **依赖**: [TASK-002-001]

- [ ] **TASK-002-111**: API文档生成
  - 配置DRF Spectacular
  - 生成OpenAPI 3.0 schema
  - 配置Swagger UI
  - **预估工时**: 0.5人天
  - **依赖**: [TASK-002-040]

- [ ] **TASK-002-112**: 监控和日志系统
  - 配置Django logging
  - 配置日志rotation
  - 配置error tracking（可选：Sentry）
  - **预估工时**: 1人天

---

## 开发里程碑

| 里程碑 | 包含任务 | 预计完成时间 | 验收标准 |
|-------|---------|------------|---------|
| **M1: 基础设施完成** | TASK-002-001, 002-002, 002-100至002-103 | Day 3 | 数据模型已创建，开发环境已配置，文档规范已确立 |
| **M2: 检测器层完成** | TASK-002-010至002-017 | Day 15 | 8个检测器全部实现并通过单元测试，测试覆盖率≥80% |
| **M3: 状态机完成** | TASK-002-020至002-022 | Day 20 | 状态机核心逻辑实现，通过集成测试 |
| **M4: Commands完成** | TASK-002-030至002-032 | Day 25 | 3个Django命令实现，可手动执行 |
| **M5: API完成** | TASK-002-040, 002-050, 002-051 | Day 28 | REST API实现，API文档生成 |
| **M6: 质量保证** | 所有P0任务 | Day 35 | 测试覆盖率≥80%，文档覆盖率100%，通过Gate 6 |
| **M7: 文档和交付** | 所有任务 | Day 40 | Crontab配置完成，交付文档完整 |

---

## 风险评估

### 高风险任务

#### 风险1: 全量扫描性能瓶颈
- **任务**: TASK-002-021（VolumeTrapStateMachine）
- **风险**: 500+交易对×3周期全量扫描可能超过5分钟性能目标
- **缓解措施**:
  - 使用Django ORM批量查询（`prefetch_related`）
  - 使用pandas向量化计算
  - 增量计算策略（仅计算最新K线）
  - 性能测试（模拟500+交易对）
  - 备用方案：迁移到Celery异步处理

#### 风险2: OBV和ATR计算复杂度
- **任务**: TASK-002-016（OBVDivergenceAnalyzer），TASK-002-017（ATRCompressionDetector）
- **风险**: 算法实现复杂，底背离和ATR压缩判断逻辑容易出错
- **缓解措施**:
  - 参考成熟技术指标库（如TA-Lib）
  - 充分的单元测试（对比Excel手工计算）
  - Code Review重点关注算法正确性

#### 风险3: 数据完整性问题
- **任务**: 所有检测器任务
- **风险**: K线数据缺失或延迟导致计算错误
- **缓解措施**:
  - 在每个检测器中实施数据完整性检查（Guard Clauses）
  - 数据不足时抛出明确异常（携带上下文）
  - 在FSM层统一处理数据异常（记录warning并跳过）

### 技术依赖

#### 依赖1: Django现有数据管道
- **依赖**: KLine、FuturesContract模型，Binance API集成
- **风险**: 现有数据管道不稳定或数据质量问题
- **应对**:
  - 复用前验证现有数据管道可用性
  - 添加数据质量监控和告警

#### 依赖2: 外部Cron调度器
- **依赖**: 系统crontab或Kubernetes CronJob
- **风险**: Cron配置错误或执行失败
- **应对**:
  - 提供详细的Crontab配置文档
  - 添加命令执行日志和监控
  - 支持手动执行和补数据

---

## 质量门禁标准 (Gate 6)

### 功能完整性
- [ ] 所有P0任务已完成（25个）
- [ ] 测试用例全部通过
- [ ] 测试覆盖率达标（≥80%）

### Fail-Fast合规 ⚡
- [ ] **代码无空catch块**
- [ ] **无静默返回**（null/-1/空字符串作为错误标记）
- [ ] **异常携带上下文信息**（预期值vs实际值）
- [ ] **所有公共方法有Guard Clauses**

### 文档化率检查 📝 ⭐ **新增硬性标准**
- [ ] **公共接口（类、函数、方法）注释覆盖率100%**
- [ ] **复杂逻辑块注释完整**（业务上下文描述）
- [ ] **注释与代码逻辑一致**，无脱节
- [ ] **维护标记规范**（TODO/FIXME/NOTE关联任务ID）
- [ ] **通过自动化文档提取工具验证**（sphinx-build无error）

### 代码质量
- [ ] 代码通过Linter检查（flake8）
- [ ] **Linter异常约束**：
  - [ ] 强制检查代码中是否含有空的catch块
  - [ ] 检查是否有泛化的异常捕获（如bare except）
- [ ] 无严重安全漏洞（OWASP Top 10）

### 可追溯性
- [ ] 可追溯性矩阵完整（每个任务关联PRD、Architecture、Function-Points）
- [ ] 迭代元数据已更新（.powerby/iterations.json）

---

**文档版本**: v1.0.0
**创建日期**: 2024-12-24
**最后更新**: 2024-12-24
**生命周期阶段**: P5 - 开发规划
