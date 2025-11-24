# Feature Specification: VP-Squeeze算法支撑压力位计算服务

**Feature Branch**: `003-vp-squeeze-analysis`
**Created**: 2025-11-24
**Status**: Draft
**Input**: User description: "复用已有的项目结构和功能，记得服务化和组件化。输入为symbol（如eth），周期（如4h），通过币安sdk获取指定数量的k线（默认100根）。基于这些k线，计算此时symbol的压力位和支撑位。计算算法：VP-Squeeze集成模型，包含波动率指标客观确认市场处于盘整状态，然后利用成交量剖面（Volume Profile, VP）精确计算出箱体结构的支撑与压力点位。"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 量化交易脚本执行 (Priority: P1)

量化交易团队通过Django management command执行技术分析，获取ETH 4小时K线的支撑位和压力位，用于自动化交易决策。

**为什么这个优先级**: 这是核心使用场景，Django command是系统最直接的交付方式，便于集成到定时任务和自动化流程。

**独立测试**: 可以通过命令行直接执行`python manage.py vp_analysis --symbol eth --interval 4h --limit 100`，验证输出的支撑位和压力位数据完整性和正确性。

**Acceptance Scenarios**:

1. **Given** 量化交易团队需要分析当前ETH 4小时K线，**When** 执行`vp_analysis --symbol eth --interval 4h --limit 100`命令，**Then** 系统在终端输出包含VAL(支撑位)、VAH(压力位)、HVN、LVN、VPOC和Squeeze状态的结构化数据

2. **Given** 需要分析不同数据量进行回测，**When** 执行命令时指定不同limit参数(50-1000根K线)，**Then** 系统返回对应数据量的计算结果，支撑压力位准确反映数据范围

3. **Given** 市场处于高波动率趋势中，**When** 执行VP-Squeeze算法，**Then** 系统输出Squeeze=False和相应提示，支撑压力位标记为低可靠度

### User Story 2 - 交易分析师手动查询 (Priority: P2)

交易分析师通过Django管理后台查询特定币种的技术分析结果，用于人工交易决策。

**为什么这个优先级**: 为人工交易者提供直观的技术分析工具，补充自动化系统的不足。

**独立测试**: 通过Django Admin界面查询TwitterAnalysisResult模型，验证VP-Squeeze分析结果展示功能。

**Acceptance Scenarios**:

1. **Given** 分析师需要查看BTC当前的技术形态，**When** 在管理后台选择BTC 1小时周期分析，**Then** 展示完整的VP-Squeeze分析结果，包括可视化图表和技术指标

2. **Given** 需要对比不同周期的分析结果，**When** 选择1h、4h、1d三个周期进行对比，**Then** 系统并行计算并展示多周期分析结果，便于形态对比

### User Story 3 - 定时技术分析任务 (Priority: P3)

系统自动定时执行热门币种的技术分析，生成分析报告并通过通知系统推送。

**为什么这个优先级**: 自动化技术分析可以定期为所有用户提供市场洞察，提升平台价值。

**独立测试**: 通过Django management command执行技术分析任务，验证定时任务功能和通知推送。

**Acceptance Scenarios**:

1. **Given** 系统定时任务触发，**When** 执行TOP 10币种的4小时VP-Squeeze分析，**Then** 生成分析结果，保存到数据库，并通过通知系统推送分析摘要

2. **Given** 发现极低波动率盘整机会，**When** Squeeze条件成立并识别出清晰箱体，**Then** 发送高优先级通知，包含明确的支撑压力位和突破目标价位

### Edge Cases

- **数据不足**: 当请求的K线数量超过交易所可提供的数据量时，如何处理？（例如新上线币种）
- **网络异常**: 币安API调用失败时的重试机制和降级策略
- **极端市场**: 超高波动率或市场极端事件时的算法稳定性
- **多交易所**: 同一币种在不同交易所价格差异时的处理策略

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统必须提供Django management command `vp_analysis`，接受symbol、interval、limit参数，执行VP-Squeeze算法并在终端输出结果
- **FR-002**: 系统必须集成币安SDK，能够获取指定数量和周期的K线数据（OHLCV格式）
- **FR-003**: 系统必须实现VP-Squeeze集成模型算法，包含Bollinger Bands、Keltner Channels、Volume Profile三大核心指标计算
- **FR-004**: 系统必须执行波动率过滤(Squeeze Check)，判断市场是否处于盘整状态：BB_Upper < KC_Upper AND BB_Lower > KC_Lower
- **FR-005**: 当Squeeze条件成立时，系统必须计算并输出VAH(价值区域高位)、VAL(价值区域低位)、VPOC(成交量剖面重心)、HVN(高量节点)、LVN(低量节点)
- **FR-006**: 系统必须将分析结果保存到TwitterAnalysisResult模型，支持历史查询和管理后台展示
- **FR-007**: 系统必须支持批量分析模式，可一次执行多个symbol的技术分析
- **FR-008**: 系统必须复用现有的monitor services架构，实现服务化和组件化设计
- **FR-009**: 系统必须支持多种时间周期：1m、5m、15m、30m、1h、4h、1d等
- **FR-010**: 系统必须支持多交易所数据获取，当前优先支持币安，可扩展至Bybit、OKX等

### Key Entities

- **SymbolAnalysisRequest**: 存储技术分析请求参数(symbol, interval, limit, created_at)
- **VP-SqueezeResult**: 存储算法计算结果，包含所有技术指标数值和Squeeze状态
- **KLineData**: 存储从交易所获取的原始K线数据(OHLCV格式)
- **TechnicalIndicators**: 存储Bollinger Bands、Keltner Channels、Volume Profile等中间计算结果
- **SupportResistanceLevels**: 存储最终输出的支撑压力位(VAL、VAH、HVN、LVN、VPOC)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Django command `vp_analysis`能够在5秒内完成单个币种的技术分析（命令执行时间<5秒）
- **SC-002**: VP-Squeeze算法计算准确率达到95%以上，能够准确识别盘整状态和支撑压力位
- **SC-003**: 系统支持批量分析模式，可同时处理10个币种的技术分析，无性能下降
- **SC-004**: 算法在低波动率盘整市场中，支撑压力位预测准确率达到80%以上
- **SC-005**: 集成到现有项目后，不影响现有公告监控和合约监控功能的正常运行
- **SC-006**: 所有技术分析结果自动保存，支持通过Django Admin后台查询和展示
- **SC-007**: 提供完整的Django management commands，支持批量分析和定时任务集成

## Clarifications

### Session 2025-11-24

- **Q**: 是否需要提供REST API接口？ → **A**: 不需要，移除REST API需求，专注Django management command实现
- **Q**: Volume Profile实现细节？ → **A**: 选择A - 基于价格区间线性划分：固定价格分辨率（1 USD或0.5 USD）创建价格桶，将K线成交量平均分配到价格范围内，累计成交量并计算VPOC、VAH(70%价值区域上限)、VAL(70%价值区域下限)

#### 币安SDK集成

- **Q**: 市场类型选择（期货/现货）？ → **A**: 先支持现货市场 (is_futures=False)
- **Q**: Symbol格式标准化？ → **A**: 使用映射表，用户输入`eth`通过map映射到`ETHUSDT`
- **Q**: K线数据缓存策略？ → **A**: 不缓存，每次分析都实时获取API数据
- **Q**: API调用错误处理？ → **A**: 抛出异常终止，由调用方处理

#### VP-Squeeze算法参数

- **Q**: Bollinger Bands参数？ → **A**: 标准参数 Period=20, Multiplier=2.0
- **Q**: Keltner Channels参数？ → **A**: 标准参数 EMA=20, ATR=10, Multiplier=1.5
- **Q**: Squeeze判定逻辑？ → **A**: 连续3根K线满足 (BB_Upper < KC_Upper) AND (BB_Lower > KC_Lower) 条件
- **Q**: Volume Profile价格分辨率？ → **A**: 按价格比例，使用当前价格的0.1%作为分辨率

#### 输出与存储

- **Q**: Command输出格式？ → **A**: 两者皆可，默认人类可读文本，`--json`参数输出JSON格式
- **Q**: 数据持久化？ → **A**: 新建独立模型VPSqueezeResult，与Twitter分析解耦
- **Q**: Symbol映射表范围？ → **A**: 先支持TOP 10主流币（BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, DOT, MATIC），后续按需扩展
- **Q**: 非Squeeze状态输出？ → **A**: 仍然输出VP数据，但标记为"低可靠度"

#### 批量分析与代码组织

- **Q**: 批量分析模式？ → **A**: 两者皆可，`--symbol eth,btc`支持自定义多币种，`--group top10`支持预设组合
- **Q**: 代码组织位置？ → **A**: 新建 `vp_squeeze/` 独立Django app
- **Q**: HVN/LVN识别逻辑？ → **A**: 百分位数方式，HVN为前20%高量区间，LVN为后20%低量区间
- **Q**: 日志与调试？ → **A**: 默认静默只输出结果，`-v/--verbose`显示详细计算过程

#### Edge Cases与技术依赖

- **Q**: 数据不足处理？ → **A**: 设定最低阈值30根K线，不足时返回错误提示
- **Q**: 计算库依赖？ → **A**: 纯Python实现，手写SMA、EMA、STD、ATR等计算逻辑，无额外依赖
- **Q**: 价格精度？ → **A**: 动态精度，价格>100保留2位，10-100保留3位，<10保留4位
- **Q**: 时间周期验证？ → **A**: 严格校验，仅允许币安支持的周期（1m,3m,5m,15m,30m,1h,2h,4h,6h,8h,12h,1d,3d,1w,1M），其他报错
