# Feature Specification: 自动化网格交易系统

## Overview

### Feature Name
自动化网格交易系统 (Automated Grid Trading System)

### Description
一个自动化的永续合约网格交易系统,支持做空、中性、做多三种网格模式。系统能够自动对接多个交易所,实时监控市场行情,在预设价格区间内自动挂单开仓和平仓,实现震荡市场套利。系统内置完善的风控机制、错误处理和交易统计功能。

### Business Value
- **降低人工成本**: 自动化执行网格策略,无需人工盯盘和手动下单
- **提高交易效率**: 通过 WebSocket 实时数据流,毫秒级响应市场变化
- **风险可控**: 内置止损保护、持仓限制、异常恢复等多层风控机制
- **数据驱动决策**: 完整的交易统计和盈亏分析,帮助优化策略参数
- **支持多市场**: 统一接口对接多个交易所,扩展性强

### Target Users
- 量化交易员: 需要自动化执行网格策略的专业交易者
- 交易团队: 需要批量管理多个网格策略的机构团队
- 个人投资者: 希望在震荡市场中获取稳定收益的投资者

---

## Clarifications

### Session 2025-12-05
- Q: 在 MVP 阶段,哪种告警通知渠道应该优先实现? → A: MVP阶段不实现告警通知,后续单独实现
- Q: 用户配置网格时,应该如何指定网格间距? → A: 可以单独抽离服务策略,默认使用方案B(用户指定上界/下界和网格数量,系统自动计算等间距)
- Q: 当策略重启时,如果当前市场价格已经大幅偏离原网格中心（例如偏离 >10%）,系统应该如何处理? → A: 使用策略A(保持原网格中心价和边界不变,基于现有持仓继续运行)

---

## User Scenarios & Testing

### Primary User Scenarios

#### Scenario 1: 配置并启动做空网格策略
**User Goal**: 在价格震荡区间通过做空网格策略获取收益

**Steps**:
1. 用户通过 Django Admin 或命令行创建网格配置
2. 设置交易对 (如 BTCUSDT)、网格模式为 "做空"
3. 配置价格区间 (上界 65000, 下界 60000)、网格数量 (20条)、单笔金额 (0.01 BTC)
4. 设置最大持仓限制 (0.2 BTC) 和止损缓冲区 (0.5%)
5. 选择目标交易所 (如 Binance Futures)
6. 执行启动命令: `python manage.py start_grid --config my_short_grid`
7. 系统订阅 WebSocket 数据流,初始化网格价位
8. 系统在上界附近开始挂卖单,价格下跌时成交并在下方挂买单平仓
9. 用户通过 Django Admin 实时查看持仓、挂单、盈亏统计
10. 价格触及止损线时,系统自动撤单并市价平仓

**Expected Outcome**:
- 网格在 30 秒内成功初始化,开始自动挂单
- 订单成交后自动补单,保持网格完整性
- 触发止损时在 10 秒内完成全部平仓
- 所有交易记录准确记录在数据库中

#### Scenario 2: 监控和调整运行中的网格
**User Goal**: 实时监控网格运行状态并根据市场变化调整参数

**Steps**:
1. 用户访问 Django Admin 网格监控页面
2. 查看当前网格状态: 价格位置、开仓数量、未实现盈亏
3. 查看最近 200 条交易日志,了解成交情况
4. 发现市场波动加剧,决定调整止损缓冲区从 0.5% 到 1%
5. 用户暂停网格: `python manage.py stop_grid --config my_short_grid`
6. 修改配置参数
7. 重新启动网格,系统从当前持仓状态恢复
8. 系统根据新参数重新计算网格,补挂缺失订单

**Expected Outcome**:
- 监控页面 1 秒内显示最新状态
- 暂停/重启过程不丢失持仓数据
- 参数调整后网格正确重新初始化
- 历史统计数据不受影响

#### Scenario 3: 查看交易统计和盈亏分析
**User Goal**: 分析网格策略表现,优化参数配置

**Steps**:
1. 用户访问统计分析页面
2. 选择时间范围 (最近 7 天)
3. 系统显示关键指标:
   - 总交易次数: 156 次
   - 成交率: 92%
   - 已实现盈亏: +0.015 BTC (+$975)
   - 未实现盈亏: -0.003 BTC (-$195)
   - 最大回撤: 2.3%
   - 网格收益率: 1.5%/天
4. 查看持仓分布图,了解哪些价位累积了较多持仓
5. 导出交易明细 CSV 文件,进行深度分析

**Expected Outcome**:
- 统计数据实时更新,延迟不超过 5 秒
- 所有指标计算准确,误差 < 0.01%
- CSV 导出包含完整的订单和成交记录
- 图表清晰展示盈亏趋势和持仓分布

### Edge Cases

#### Edge Case 1: WebSocket 连接中断
**Scenario**: 网络不稳定导致 WebSocket 连接断开

**Expected Behavior**:
- 系统在 5 秒内检测到连接中断
- 自动触发重连机制,最多重试 3 次,每次间隔 5/10/15 秒 (指数退避)
- 重连成功后重新订阅所有数据流,同步账户和订单状态
- 如果 3 次重连失败,系统进入安全模式: 撤销所有挂单,不进行新操作
- 发送告警通知给用户 (邮件/钉钉/Telegram)

#### Edge Case 2: 价格瞬间突破网格边界
**Scenario**: 市场剧烈波动,价格在 1 分钟内从 62000 跌至 59000 (跌破下界 60000)

**Expected Behavior**:
- 系统检测到价格跌破止损线 (下界 * (1 - 0.5%) = 59700)
- 立即标记策略为 "止损触发" 状态,记录触发原因和时间
- 并发执行撤单操作,撤销所有未成交挂单
- 计算当前净持仓,发起市价平仓单 (带 reduceOnly=True 保护)
- 平仓完成后清空网格状态,策略进入停止状态
- 生成止损报告,记录触发价格、持仓情况、平仓滑点

#### Edge Case 3: 交易所 API 返回限流错误
**Scenario**: 订单创建请求超过交易所速率限制 (如 Binance 1200 请求/分钟)

**Expected Behavior**:
- 系统捕获 429 错误码和 "Rate limit exceeded" 错误信息
- 立即进入冷却期,30 秒内不发送新订单请求
- 将待创建订单缓存到队列,冷却期结束后按优先级补单
- 记录限流事件到日志,包含时间戳和触发原因
- 如果频繁触发限流 (10 分钟内 > 3 次),降低轮询频率从 1 秒到 3 秒

#### Edge Case 4: 订单部分成交
**Scenario**: 限价单只成交了 70% 的数量 (下单 0.01 BTC,成交 0.007 BTC)

**Expected Behavior**:
- 系统识别订单状态为 "PARTIALLY_FILLED"
- 保留该订单在网格层状态中,继续等待剩余部分成交
- 不在该层级重复挂单,避免超额开仓
- 如果 10 分钟内未完全成交,撤销剩余部分
- 根据实际成交数量计算持仓和盈亏

#### Edge Case 5: 数据库连接失败
**Scenario**: 持久化交易日志时数据库连接超时

**Expected Behavior**:
- 系统继续运行策略核心逻辑,不因日志失败而中断交易
- 将失败的日志条目缓存到内存队列 (最多 1000 条)
- 每 10 秒尝试重新连接数据库
- 连接恢复后批量写入缓存的日志
- 如果内存队列满,丢弃最旧的日志并记录警告

---

## Functional Requirements

### FR-1: 网格配置管理
**Description**: 系统必须支持创建、修改、删除网格交易配置

**Acceptance Criteria**:
- AC1.1: 用户可以通过 Django Admin 或 Management Command 创建新配置
- AC1.2: 配置包含必填字段: 名称、交易所、交易对、网格模式、价格区间、网格数量、单笔金额
- AC1.3: 配置包含可选字段: 最大持仓、止损缓冲区、轮询间隔、时间生效 (GTX/GTC)
- AC1.4: 系统验证配置合法性: 价格区间 > 0, 网格数量 >= 5, 单笔金额符合交易所最小精度
- AC1.5: 修改运行中网格的配置时,系统提示用户需先暂停策略
- AC1.6: 删除配置时,如果策略正在运行,系统拒绝删除并提示

### FR-2: 做空网格策略 (优先实现)
**Description**: 系统必须实现做空网格模式,仅在上方挂卖单开仓,下方挂买单平仓

**Acceptance Criteria**:
- AC2.1: 网格初始化时,在当前价格上方均匀分布卖单 (开仓单)
- AC2.2: 卖单成交后,系统在成交价下方一个网格间距处挂买单 (平仓单)
- AC2.3: 买单成交后,该网格层状态重置为空闲,可再次挂卖单
- AC2.4: 系统限制最大净空头持仓不超过 `maxPositionSize` 配置
- AC2.5: 当净空头持仓达到上限时,拒绝新的卖单,只允许平仓买单
- AC2.6: 所有开仓卖单带 `reduceOnly=False`,所有平仓买单带 `reduceOnly=True`

### FR-3: 中性网格策略
**Description**: 系统必须实现中性网格模式,上方挂卖单,下方挂买单,双向开仓

**Acceptance Criteria**:
- AC3.1: 网格初始化时,在当前价格上方挂卖单,下方挂买单
- AC3.2: 买单成交后,在成交价上方挂卖单平仓
- AC3.3: 卖单成交后,在成交价下方挂买单平仓
- AC3.4: 系统分别追踪多头和空头持仓,限制净持仓绝对值不超过 `maxPositionSize`
- AC3.5: 当多头持仓达到上限时,拒绝新的买单;当空头持仓达到上限时,拒绝新的卖单

### FR-4: 做多网格策略
**Description**: 系统必须实现做多网格模式,仅在下方挂买单开仓,上方挂卖单平仓

**Acceptance Criteria**:
- AC4.1: 网格初始化时,在当前价格下方均匀分布买单 (开仓单)
- AC4.2: 买单成交后,系统在成交价上方一个网格间距处挂卖单 (平仓单)
- AC4.3: 卖单成交后,该网格层状态重置为空闲,可再次挂买单
- AC4.4: 系统限制最大净多头持仓不超过 `maxPositionSize` 配置
- AC4.5: 当净多头持仓达到上限时,拒绝新的买单,只允许平仓卖单
- AC4.6: 所有开仓买单带 `reduceOnly=False`,所有平仓卖单带 `reduceOnly=True`

### FR-5: 交易所适配器
**Description**: 系统必须提供统一的交易所抽象接口,支持对接多个交易所

**Acceptance Criteria**:
- AC5.1: 定义 ExchangeAdapter 抽象基类,包含必需方法: watchAccount, watchOrders, watchDepth, watchTicker, createOrder, cancelOrder, cancelAllOrders
- AC5.2: 优先实现 Binance Futures 适配器,支持 USDT 永续合约
- AC5.3: 适配器使用 WebSocket 订阅实时数据: 账户余额/持仓、订单更新、盘口深度、最新价格
- AC5.4: WebSocket 断线时自动重连,最多重试 3 次,间隔 5/10/15 秒
- AC5.5: 适配器处理交易所特定的精度要求 (价格 tick, 数量 step)
- AC5.6: 订单创建失败时返回明确的错误信息 (余额不足、精度错误、限流等)

### FR-6: 网格初始化与恢复
**Description**: 系统必须支持首次启动时初始化网格,以及中断后从现有持仓恢复

**Acceptance Criteria**:
- AC6.1: 首次启动时,系统基于当前市场价格计算网格中心价和上下边界
- AC6.2: 网格间距 = max(价格精度, 中心价 * 网格间距百分比)
- AC6.3: 生成网格层级数组,每层记录: 索引、价格、方向 (BUY/SELL)、状态 (idle/entry-working/position-open/exit-working)
- AC6.4: 策略重启时,系统从交易所同步当前持仓和未成交订单
- AC6.5: 将现有订单映射到网格层级,避免重复挂单
- AC6.6: 识别孤立订单 (不在理想网格中的订单),自动撤销
- AC6.7: 补挂缺失的网格订单,确保网格完整性

### FR-7: 订单同步与幂等性
**Description**: 系统必须实现订单状态同步机制,确保网格订单与交易所一致

**Acceptance Criteria**:
- AC7.1: 系统按配置的轮询间隔 (默认 1 秒) 执行一次同步
- AC7.2: 每次同步计算理想挂单列表 (基于当前网格层状态和持仓)
- AC7.3: 对比理想列表与实际挂单,撤销多余订单,补挂缺失订单
- AC7.4: 使用四元组 `(intent, side, price, level)` 作为订单唯一标识
- AC7.5: 同步操作支持幂等性: 多次执行结果一致,不产生重复订单
- AC7.6: 订单创建失败时记录错误,该网格层进入冷却期 5 秒,避免频繁重试

### FR-8: 止损保护机制
**Description**: 系统必须监控市场价格,当价格突破网格边界时触发止损

**Acceptance Criteria**:
- AC8.1: 止损触发条件: 价格 <= 下界 * (1 - 止损缓冲区%) 或 价格 >= 上界 * (1 + 止损缓冲区%)
- AC8.2: 触发止损时,系统立即标记策略状态为 "止损中"
- AC8.3: 并发撤销所有未成交挂单,不等待撤单完成
- AC8.4: 计算当前净持仓,如果持仓 != 0,发起市价平仓单
- AC8.5: 市价单带 `reduceOnly=True` 和 `closePosition=True` 参数保护
- AC8.6: 平仓完成后,策略进入 "已停止" 状态,清空网格层状态
- AC8.7: 生成止损报告,记录: 触发时间、触发价格、持仓情况、平仓价格、滑点损失

### FR-9: 持仓限制与风控
**Description**: 系统必须实施持仓限制,防止极端市场下累积过量仓位

**Acceptance Criteria**:
- AC9.1: 每次计算理想挂单前,检查当前净持仓绝对值
- AC9.2: 对于做空网格: 如果净空头持仓 >= maxPositionSize,过滤掉所有新的卖单
- AC9.3: 对于做多网格: 如果净多头持仓 >= maxPositionSize,过滤掉所有新的买单
- AC9.4: 对于中性网格: 分别限制多头和空头持仓,净持仓绝对值 <= maxPositionSize
- AC9.5: 平仓单 (reduceOnly=True) 不受持仓限制影响,始终允许
- AC9.6: 系统记录因持仓限制而跳过的订单数量,用于统计分析

### FR-10: 交易日志与事件追踪
**Description**: 系统必须记录所有交易事件,支持事后审计和问题排查

**Acceptance Criteria**:
- AC10.1: 日志类型包含: info (信息), warn (警告), error (错误), order (订单操作), fill (成交)
- AC10.2: 每条日志记录: 时间戳、类型、详细描述、关联订单 ID (可选)、网格层级 (可选)
- AC10.3: 使用环形缓冲区 (Ring Buffer) 存储日志,容量默认 200 条,可配置
- AC10.4: 日志同时写入数据库和内存缓冲区,数据库写入失败不影响策略运行
- AC10.5: 提供日志查询 API: 按时间范围、类型、关键词筛选
- AC10.6: 关键事件必须记录: 网格初始化、订单创建、订单成交、止损触发、错误异常

### FR-11: 交易统计与分析
**Description**: 系统必须提供完整的交易统计功能,帮助用户评估策略表现

**Acceptance Criteria**:
- AC11.1: 统计周期可选: 最近 1 小时、1 天、7 天、30 天、全部
- AC11.2: 基础统计: 总交易次数、开仓次数、平仓次数、撤单次数
- AC11.3: 盈亏统计: 已实现盈亏、未实现盈亏、总盈亏、网格收益率 (%/天)
- AC11.4: 风险统计: 最大回撤、最大持仓、平均持仓、止损触发次数
- AC11.5: 效率统计: 成交率 (成交订单数 / 总挂单数)、平均成交时间
- AC11.6: 持仓分布: 展示每个网格层级的持仓数量,识别累积风险
- AC11.7: 统计数据每 60 秒更新一次,延迟不超过 5 秒
- AC11.8: 支持导出统计报告为 CSV 格式

### FR-12: 错误处理与异常恢复
**Description**: 系统必须优雅处理各类错误,确保策略稳定运行

**Acceptance Criteria**:
- AC12.1: WebSocket 连接错误: 自动重连,最多 3 次,失败后进入安全模式
- AC12.2: 订单创建错误: 记录错误原因,该网格层进入冷却期,不影响其他层级
- AC12.3: 交易所限流错误 (429): 全局冷却 30 秒,缓存待创建订单,冷却后补单
- AC12.4: 余额不足错误: 停止创建新开仓单,保留平仓单,发送余额告警
- AC12.5: 精度错误: 自动调整订单价格和数量到交易所允许的精度
- AC12.6: 数据库连接错误: 日志缓存到内存,定期重试写入,不影响交易逻辑
- AC12.7: 未捕获异常: 记录完整堆栈信息,策略进入暂停状态,发送紧急告警
- AC12.8: 所有异常都不导致进程崩溃,通过 try-catch 保护核心循环

### FR-13: 策略生命周期管理
**Description**: 系统必须支持策略的启动、暂停、恢复、停止操作

**Acceptance Criteria**:
- AC13.1: 启动命令: `python manage.py start_grid --config <name>`
- AC13.2: 启动时检查配置有效性,订阅数据流,初始化网格
- AC13.3: 暂停命令: `python manage.py pause_grid --config <name>`
- AC13.4: 暂停时停止轮询和新订单创建,保留现有挂单和持仓
- AC13.5: 恢复命令: `python manage.py resume_grid --config <name>`
- AC13.6: 恢复时从现有状态继续,不重新初始化网格
- AC13.7: 停止命令: `python manage.py stop_grid --config <name>`
- AC13.8: 停止时撤销所有挂单,市价平仓,清空状态
- AC13.9: 状态查询命令: `python manage.py grid_status --config <name>`
- AC13.10: 查询返回: 运行状态、持仓情况、挂单数量、最近错误

---

## Success Criteria

### Quantitative Metrics

1. **系统可用性**
   - 策略连续运行 24 小时无崩溃,正常运行时间 >= 99.9%
   - WebSocket 断线自动恢复成功率 >= 95%

2. **响应性能**
   - WebSocket 数据推送到订单同步完成延迟 < 2 秒
   - 止损触发到完成平仓时间 < 10 秒 (正常市场条件)
   - Django Admin 监控页面加载时间 < 3 秒

3. **交易准确性**
   - 订单价格和数量精度 100% 符合交易所要求
   - 持仓限制执行准确率 100% (无超限开仓)
   - 统计数据计算误差 < 0.01%

4. **策略效率**
   - 订单成交率 >= 90% (震荡市场)
   - 网格完整性: 理想挂单覆盖率 >= 95%
   - 订单同步幂等性: 重复执行不产生额外订单

### Qualitative Outcomes

1. **用户满意度**
   - 用户能在 10 分钟内完成网格配置并启动策略
   - 用户能通过可视化界面直观了解网格运行状态
   - 策略运行中用户无需频繁干预,自动化程度高

2. **系统可靠性**
   - 异常情况下系统能自动恢复或进入安全模式,不造成资金损失
   - 错误信息清晰,用户能快速定位问题原因
   - 关键操作 (止损、平仓) 有明确的日志和报告

3. **扩展性**
   - 新增交易所适配器只需实现标准接口,不影响核心逻辑
   - 新增网格模式 (如斐波那契网格) 可通过扩展现有架构实现
   - 统计功能易于扩展新指标,无需修改核心代码

---

## Assumptions & Constraints

### Assumptions
1. 用户拥有交易所账户和有效的 API Key/Secret
2. 服务器网络稳定,可访问交易所 WebSocket 和 REST API
3. 服务器时间与真实世界时间同步 (NTP)
4. 用户账户有足够余额支持网格策略运行 (建议至少 100 USDT)
5. 交易所账户已设置杠杆倍数 (建议 20-50x) 和单向持仓模式
6. 用户对网格交易原理有基本了解,能合理配置参数

### Constraints
1. **技术约束**:
   - 系统运行在 Django 环境,使用 Python 3.8+
   - 数据库使用 PostgreSQL 或 MySQL
   - WebSocket 库使用 `websockets` 或 `python-binance`

2. **交易所限制**:
   - 订单数量受交易所最大挂单数限制 (如 Binance 200 个/symbol)
   - API 请求受速率限制 (如 Binance 1200 请求/分钟)
   - 最小下单金额和精度由交易所规则决定

3. **性能限制**:
   - 单个网格策略轮询间隔不低于 500ms (避免过度消耗资源)
   - 单服务器建议运行网格数量 <= 20 个
   - 环形日志缓冲区容量 <= 1000 条 (避免内存溢出)

4. **业务约束**:
   - 初期仅支持 USDT 永续合约,不支持币本位合约
   - 初期仅支持做空/中性/做多网格,不支持复杂变种 (如马丁格尔网格)
   - 网格间距为固定百分比,不支持动态调整

---

## Key Entities

### GridConfig (网格配置)
**Description**: 存储网格策略的所有配置参数

**Attributes**:
- `name` (string): 配置名称,唯一标识
- `exchange` (string): 交易所代码 (binance/okx/bybit)
- `symbol` (string): 交易对 (BTCUSDT)
- `grid_mode` (enum): 网格模式 (short/neutral/long)
- `upper_price` (decimal): 价格上界
- `lower_price` (decimal): 价格下界
- `grid_levels` (integer): 网格总数
- `trade_amount` (decimal): 单笔开仓数量
- `max_position_size` (decimal): 最大持仓限制
- `stop_loss_buffer_pct` (decimal): 止损缓冲区百分比
- `refresh_interval_ms` (integer): 轮询间隔 (毫秒)
- `price_tick` (decimal): 价格精度
- `qty_step` (decimal): 数量精度
- `is_active` (boolean): 是否启用
- `created_at` (datetime): 创建时间
- `updated_at` (datetime): 更新时间

### GridLevel (网格层级)
**Description**: 单个网格价位的状态信息

**Attributes**:
- `config_id` (foreign key): 关联的网格配置
- `level_index` (integer): 层级索引 (-15 ~ 15)
- `price` (decimal): 网格价位
- `side` (enum): 方向 (BUY/SELL)
- `status` (enum): 状态 (idle/entry_working/position_open/exit_working)
- `entry_order_id` (string): 开仓订单 ID
- `exit_order_id` (string): 平仓订单 ID
- `entry_client_id` (string): 开仓订单客户端 ID
- `exit_client_id` (string): 平仓订单客户端 ID
- `blocked_until` (bigint): 冷却时间戳 (毫秒)
- `created_at` (datetime): 创建时间
- `updated_at` (datetime): 更新时间

### OrderIntent (订单意图)
**Description**: 追踪订单的业务意图,用于状态同步

**Attributes**:
- `config_id` (foreign key): 关联的网格配置
- `order_id` (string): 交易所订单 ID
- `client_order_id` (string): 客户端订单 ID
- `level_index` (integer): 网格层级
- `intent` (enum): 意图 (ENTRY/EXIT)
- `side` (enum): 方向 (BUY/SELL)
- `price` (decimal): 订单价格
- `amount` (decimal): 订单数量
- `status` (string): 订单状态 (NEW/FILLED/CANCELED)
- `created_at` (datetime): 创建时间
- `resolved_at` (datetime): 完结时间

### TradeLog (交易日志)
**Description**: 记录所有交易事件,用于审计和调试

**Attributes**:
- `config_id` (foreign key): 关联的网格配置
- `log_type` (enum): 日志类型 (info/warn/error/order/fill)
- `detail` (text): 详细描述
- `timestamp` (bigint): Unix 毫秒时间戳
- `order_id` (string, optional): 关联订单 ID
- `level_index` (integer, optional): 网格层级
- `created_at` (datetime): 创建时间

### GridStatistics (网格统计)
**Description**: 存储网格策略的统计分析数据

**Attributes**:
- `config_id` (foreign key): 关联的网格配置
- `period_start` (datetime): 统计周期起始时间
- `period_end` (datetime): 统计周期结束时间
- `total_trades` (integer): 总交易次数
- `filled_entry_orders` (integer): 成交开仓单数
- `filled_exit_orders` (integer): 成交平仓单数
- `canceled_orders` (integer): 撤单数
- `realized_pnl` (decimal): 已实现盈亏
- `unrealized_pnl` (decimal): 未实现盈亏
- `total_pnl` (decimal): 总盈亏
- `max_position_size` (decimal): 最大持仓
- `avg_position_size` (decimal): 平均持仓
- `current_position_size` (decimal): 当前持仓
- `stop_loss_triggered_count` (integer): 止损触发次数
- `max_drawdown` (decimal): 最大回撤
- `created_at` (datetime): 创建时间

---

## Non-Functional Requirements

### Performance
- 订单同步延迟: < 2 秒 (从接收 WebSocket 推送到完成同步)
- 止损响应时间: < 10 秒 (从触发到完成平仓)
- 统计数据更新频率: 每 60 秒
- 系统支持并发运行 20 个网格策略 (单服务器)

### Scalability
- 支持新增交易所适配器,无需修改核心策略逻辑
- 支持新增网格模式 (如斐波那契网格),通过扩展现有架构
- 数据库设计支持百万级交易日志记录

### Security
- API Key/Secret 加密存储,不明文记录日志
- 所有订单带客户端 ID,防止重复执行
- 止损保护强制执行,不可通过配置禁用
- 平仓单强制带 `reduceOnly=True`,防止误开仓

### Reliability
- WebSocket 断线自动重连,最多 3 次
- 订单创建失败自动重试,指数退避
- 数据库写入失败不影响策略核心逻辑
- 未捕获异常不导致进程崩溃

### Maintainability
- 代码遵循 PEP8 规范,类型注解完整
- 核心算法有单元测试覆盖,覆盖率 >= 80%
- 日志记录详细,包含时间戳和上下文信息
- 配置参数有清晰注释,说明作用和默认值

---

## Out of Scope

以下功能**不在**本次实现范围内:

1. **复杂网格变种**:
   - 马丁格尔网格 (递增数量)
   - 斐波那契网格 (非等比间距)
   - 动态网格 (根据波动率调整间距)

2. **多币种组合**:
   - 同时运行多个交易对的联动网格
   - 跨交易所套利网格

3. **高级止盈功能**:
   - 移动止盈 (trailing stop)
   - 分批止盈 (部分平仓)

4. **机器学习优化**:
   - 基于历史数据自动优化网格参数
   - 预测最佳入场时机

5. **移动端应用**:
   - iOS/Android App
   - 推送通知到手机

6. **社交功能**:
   - 策略分享和复制跟单
   - 社区排行榜

7. **现货网格**:
   - 仅支持永续合约,不支持现货网格

8. **回测功能**:
   - 基于历史数据的策略回测和优化

---

## Dependencies

### External Systems
- **交易所 API**: Binance Futures WebSocket 和 REST API
- **数据库**: PostgreSQL 或 MySQL
- **时间同步**: NTP 服务器

### Internal Systems
- Django 项目现有的用户认证系统
- Django ORM 和数据库迁移机制
- Django Admin 管理后台

### Third-Party Libraries
- `websockets` 或 `python-binance`: WebSocket 连接
- `ccxt` (可选): 多交易所统一接口
- `decimal`: 高精度数学计算
- `asyncio`: 异步编程支持

---

## Related Features/Modules

### Existing Modules to Integrate
- **筛选系统** (`grid_trading/services/screening_engine.py`): 可用于筛选适合网格交易的币种
- **交易日志** (`grid_trading/logging/trade_log.py`): 可复用环形缓冲区实现
- **Django Models** (`grid_trading/django_models.py`): 扩展现有模型

### Potential Future Enhancements
- 与筛选系统集成: 自动筛选高波动率币种启动网格
- 回测引擎: 基于历史数据验证网格参数
- 策略优化器: 自动调整网格间距和持仓限制
- 风险管理: 多策略组合的总风险控制

---

## Open Questions

暂无需要澄清的问题。所有核心需求已基于参考文档和行业标准明确定义。
