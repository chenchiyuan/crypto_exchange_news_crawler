# Feature Specification: Market Cap & FDV Display Integration

**Feature Branch**: `008-marketcap-fdv-display`
**Created**: 2025-12-12
**Status**: ✅ MVP Complete (2025-12-15)
**Input**: User description: "在 /screening/daily/ 列表上展示合约的市值和FDV,数据从CoinGecko API获取并存储到数据库"

## 实现概述

Feature 008已完成MVP交付，实现了市值和FDV数据的完整获取、存储和展示流程：

- **用户工作流**: 离线LLM匹配 + 批量导入映射 → 自动更新市值数据 → 前端展示
- **数据来源**: CoinGecko Demo API (10 calls/minute)
- **映射数据**: 355个币安合约成功映射到CoinGecko ID
- **覆盖率**: 100% (355/355合约成功获取市值/FDV数据)
- **前端展示**: /screening/daily/ 页面已添加FDV列，价格列之后

### 核心实现

1. **数据下载**: `download_coingecko_data.py` (19,188个代币) + `export_binance_contracts.py` (530个合约)
2. **离线匹配**: 用户使用LLM处理token.csv映射文件
3. **导入映射**: `import_token_mappings.py` (355个有效映射)
4. **更新数据**: `update_market_data.py` (批量获取市值/FDV，100个/批次)
5. **前端展示**: daily_screening.html (FDV列，智能格式化)

## Clarifications

### Session 2025-12-12

- Q: 历史日期查看时的市值/FDV数据展示策略 - 用户查看历史日期(如2025-12-10)的筛选结果时,市值和FDV应该显示什么数据? → A: 始终显示最新数据(无论查看哪天的筛选结果,市值/FDV都显示当前最新值)
- Q: 同名代币冲突的优先级规则 - 当多个代币使用相同symbol且交易量相同或不完整时,使用什么fallback规则? → A: 优先级规则链: 交易量 → 市值排名(rank) → 标记为needs_review

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 查看合约市值和FDV数据 (Priority: P1)

作为交易者,我需要在筛选列表页面直接看到每个合约的市值(Market Cap)和FDV(Fully Diluted Valuation),以便快速评估代币的市场规模和估值潜力,做出更明智的交易决策。

**为什么这是P1优先级**: 市值和FDV是评估加密货币投资价值的核心指标,直接影响用户的交易决策。这是整个功能的最终目标,提供即时可见的市场数据。

**独立测试**: 用户访问 /screening/daily/ 页面,可以看到每个合约旁边显示的市值和FDV数值。对于无数据的合约显示"-"占位符。

**验收场景**:

1. **Given** 用户访问 /screening/daily/ 页面, **When** 页面加载完成, **Then** 列表中每个合约都显示市值和FDV列
2. **Given** 数据库中存在合约的市值/FDV数据, **When** 查看该合约, **Then** 显示正确的市值和FDV数值(美元格式,带K/M/B单位缩写)
3. **Given** 数据库中不存在某个合约的市值/FDV数据, **When** 查看该合约, **Then** 市值和FDV列显示"-"
4. **Given** 用户查看市值数据, **When** 点击列标题, **Then** 可以按市值进行升序/降序排序

---

### User Story 2 - 建立币安symbol与CoinGecko ID的映射关系 (Priority: P1)

作为系统管理员,我需要一个自动化机制来建立和维护币安交易对symbol(如BTCUSDT)与CoinGecko代币ID(如bitcoin)之间的映射关系,并能够人工审核确认这些映射的准确性。

**为什么这是P1优先级**: 映射关系是获取准确市值/FDV数据的基础。没有正确的映射,就无法从CoinGecko获取对应代币的数据。这是整个数据流的起点。

**独立测试**: 运行映射生成脚本后,系统生成一个包含所有币安USDT永续合约的映射表,管理员可以审核并确认每个映射关系的正确性。

**验收场景**:

1. **Given** 系统需要建立映射关系, **When** 管理员运行映射生成脚本, **Then** 脚本自动从币安获取所有USDT永续合约列表
2. **Given** 脚本获取了币安合约列表, **When** 脚本调用CoinGecko API, **Then** 系统通过symbol匹配自动查找对应的CoinGecko ID
3. **Given** 映射关系生成完成, **When** 管理员查看输出结果, **Then** 显示清晰的映射表(包括symbol、base_token、coingecko_id、匹配状态)
4. **Given** 存在模糊或多个匹配结果, **When** 脚本处理这些情况, **Then** 标记为"需要人工确认"并记录所有候选项
5. **Given** 管理员审核映射表, **When** 确认无误后, **Then** 可以批准将映射关系写入数据库

---

### User Story 3 - 定期更新市值和FDV数据 (Priority: P2)

作为系统运维人员,我需要一个自动化脚本定期从CoinGecko API获取最新的市值和FDV数据,并存储到数据库中,以确保前端显示的数据保持最新。

**为什么这是P2优先级**: 数据更新机制确保用户看到的信息不会过时,但它是在P1(映射建立和显示功能)之后才有意义的补充功能。

**独立测试**: 运行数据更新脚本后,数据库中的市值和FDV数据更新为最新值,且更新时间戳被正确记录。

**验收场景**:

1. **Given** 数据库中存在symbol与CoinGecko ID的映射关系, **When** 运行更新脚本, **Then** 脚本批量调用CoinGecko API获取市值和FDV数据
2. **Given** 成功获取到数据, **When** 脚本处理响应, **Then** 将market_cap和fully_diluted_valuation值存储到数据库
3. **Given** 更新过程中某些symbol获取失败, **When** 脚本继续执行, **Then** 记录失败的symbol并继续处理其他symbol
4. **Given** 脚本更新完成, **When** 查看更新结果, **Then** 显示成功/失败数量和详细日志
5. **Given** 需要定期更新, **When** 配置定时任务(如每天凌晨4点), **Then** 脚本自动执行并发送通知(成功/失败报告)

---

### User Story 4 - 手动更新映射关系 (Priority: P3)

作为系统管理员,当有新的合约上线或映射关系发生变化时,我需要能够手动更新币安symbol与CoinGecko ID的映射关系,以保持数据的准确性。

**为什么这是P3优先级**: 这是维护性功能,用于处理新合约上线或修正错误映射的情况。虽然重要,但使用频率低于自动化的初始映射和数据更新。

**独立测试**: 管理员运行更新脚本时可以指定要更新的特定symbol列表,系统重新查询CoinGecko并更新映射关系。

**验收场景**:

1. **Given** 管理员需要更新特定合约的映射, **When** 运行更新脚本并指定symbol列表, **Then** 脚本只处理指定的symbol
2. **Given** 脚本查找到新的CoinGecko ID, **When** 与现有映射不同, **Then** 提示管理员确认是否覆盖
3. **Given** 管理员确认更新, **When** 脚本执行, **Then** 更新数据库中的映射关系并记录变更日志
4. **Given** 某个symbol在CoinGecko中找不到, **When** 脚本处理, **Then** 保留现有映射并记录警告信息

---

### Edge Cases

1. **CoinGecko API限流**: 当API调用超过速率限制时,系统如何处理?(建议:实现指数退避重试机制,记录失败并在下次更新时重试)

2. **同名代币冲突**: 当多个不同的代币使用相同symbol时,使用以下优先级规则自动选择: (1)优先匹配24h交易量最大的代币 (2)如交易量相同或缺失,按市值排名(market_cap_rank)选择排名更高的 (3)如仍无法区分,标记为needs_review并记录所有候选项供管理员手工确认

3. **币安下架合约**: 当某个合约从币安下架后,如何处理其历史数据和映射关系?(建议:保留历史数据但标记为"已下架",停止更新)

4. **CoinGecko数据缺失**: 当某个代币在CoinGecko中存在但没有市值/FDV数据时,如何处理?(建议:存储NULL值,前端显示"-")

5. **新合约上线**: 当币安新上线合约时,系统如何自动发现并建立映射?(建议:每日定时任务检测新合约并触发映射更新流程)

6. **FDV为无穷大**: 当代币总供应量未知导致FDV无法计算时,如何显示?(建议:CoinGecko会返回null,前端显示"-"或"∞")

7. **历史日期访问**: 当用户查看历史日期(如2025-12-10)的筛选结果时,市值和FDV列始终显示当前最新数据,不展示历史快照

## Requirements *(mandatory)*

### Functional Requirements

**数据映射管理**:

- **FR-001**: 系统必须提供命令行脚本,能够自动从币安API获取所有USDT永续合约的交易对列表
- **FR-002**: 系统必须能够将币安交易对(如BTCUSDT)转换为基础代币symbol(如BTC)
- **FR-003**: 系统必须能够调用CoinGecko API,根据代币symbol查找对应的CoinGecko ID
- **FR-004**: 系统必须能够处理一个symbol对应多个CoinGecko代币的情况,按优先级规则自动选择:(1)24h交易量最大 (2)市值排名最高 (3)仍无法区分时标记为needs_review
- **FR-005**: 映射脚本必须生成可读的输出报告,包含:symbol、base_token、coingecko_id、匹配状态、候选项列表
- **FR-006**: 系统必须将确认后的映射关系存储到数据库中,包括:symbol、coingecko_id、创建时间、更新时间
- **FR-007**: 系统必须支持手动更新特定symbol的映射关系

**市值和FDV数据获取**:

- **FR-008**: 系统必须提供命令行脚本,能够批量调用CoinGecko API获取市值和FDV数据
- **FR-009**: 系统必须使用CoinGecko的 `/coins/markets` API端点获取数据
- **FR-010**: 系统必须能够处理API响应中的market_cap和fully_diluted_valuation字段
- **FR-011**: 系统必须将获取到的数据存储到数据库,包括:symbol、market_cap、fdv、更新时间
- **FR-012**: 系统必须记录每次更新的成功/失败状态和详细日志
- **FR-013**: 当API调用失败时,系统必须实现重试机制(最多3次,指数退避)
- **FR-014**: 系统必须能够处理部分成功/部分失败的批量更新场景

**前端展示**:

- **FR-015**: /screening/daily/ 页面必须新增"市值"列,显示当前最新的market_cap数据(无论查看任何日期的筛选结果)
- **FR-016**: /screening/daily/ 页面必须新增"FDV"列,显示当前最新的fully_diluted_valuation数据(无论查看任何日期的筛选结果)
- **FR-017**: 市值和FDV必须以美元金额格式显示,使用K(千)、M(百万)、B(十亿)单位缩写
- **FR-018**: 当数据库中不存在某个合约的市值/FDV数据时,必须显示"-"占位符
- **FR-019**: 市值和FDV列必须支持点击排序(升序/降序)
- **FR-020**: 数据显示必须包含数据更新时间的提示信息(鼠标悬停显示)

**数据维护**:

- **FR-021**: 系统必须支持配置定时任务,自动执行数据更新脚本
- **FR-022**: 系统必须在每次数据更新后发送通知,包含成功/失败统计和错误详情
- **FR-023**: 系统必须保留历史更新日志,至少保存30天
- **FR-024**: 系统必须提供查询工具,能够查看任意symbol的当前映射关系和最新数据

### Key Entities

- **TokenMapping (代币映射表)**:
  - symbol: 币安交易对符号(如BTCUSDT)
  - base_token: 基础代币符号(如BTC)
  - coingecko_id: CoinGecko平台的代币ID(如bitcoin)
  - match_status: 匹配状态(auto_matched, manual_confirmed, needs_review)
  - alternatives: 候选CoinGecko ID列表(JSON格式,用于needs_review状态)
  - created_at: 创建时间
  - updated_at: 最后更新时间

- **MarketData (市场数据表)**:
  - symbol: 币安交易对符号
  - market_cap: 市值(美元)
  - fully_diluted_valuation: 全稀释估值(美元)
  - data_source: 数据来源(固定为"coingecko")
  - fetched_at: 数据获取时间
  - created_at: 记录创建时间
  - updated_at: 记录更新时间

- **UpdateLog (更新日志表)**:
  - batch_id: 批次ID
  - symbol: 处理的交易对符号
  - operation_type: 操作类型(mapping_update, data_fetch)
  - status: 状态(success, failure)
  - error_message: 错误信息(如果失败)
  - executed_at: 执行时间

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户在 /screening/daily/ 页面可以看到至少90%监控合约的市值和FDV数据
- **SC-002**: 映射关系生成脚本能够在5分钟内完成所有币安USDT永续合约的映射(假设有500+合约)
- **SC-003**: 市值/FDV数据更新脚本能够在15分钟内完成所有合约的数据获取
- **SC-004**: 页面加载时,市值和FDV列的数据展示不影响页面加载性能(增加的加载时间<200ms)
- **SC-005**: 自动映射匹配的准确率达到85%以上,需要人工审核的合约不超过15%
- **SC-006**: 数据更新的成功率达到95%以上(考虑到API限流和网络问题)
- **SC-007**: 用户可以通过点击市值或FDV列标题进行排序,排序响应时间<100ms

## Assumptions *(mandatory)*

1. **CoinGecko API访问权限**: 假设项目已经拥有CoinGecko API密钥,并且具有足够的API调用额度(至少支持每日更新所有监控合约的数据)

2. **币安合约类型**: 假设只处理USDT永续合约(symbol以USDT结尾),不包括币本位合约或其他交易对

3. **数据时效性要求**: 假设市值和FDV数据每日更新一次即可满足需求,不需要实时更新

4. **CoinGecko数据格式**: 假设CoinGecko API返回的数据格式稳定,遵循官方文档规范

5. **用户权限**: 假设映射关系的建立和审核操作仅限系统管理员执行,普通用户只能查看数据

6. **数据单位**: 假设所有市值和FDV数据都以美元(USD)为单位,无需支持其他货币

7. **数据库容量**: 假设现有数据库有足够空间存储新增的映射关系和市场数据表

8. **前端框架**: 假设现有的 /screening/daily/ 页面可以通过标准的Django模板扩展来添加新列

## Dependencies *(optional)*

### External Services

- **CoinGecko API**:
  - 用途: 获取代币的市值、FDV和ID映射数据
  - 依赖端点:
    - GET /coins/list (用于获取所有代币列表和ID映射)
    - GET /coins/markets (用于获取市值和FDV数据)
  - 风险: API限流、服务不可用、数据格式变更

- **币安API**:
  - 用途: 获取所有USDT永续合约列表
  - 依赖端点: 交易对信息接口(已在项目中使用)
  - 风险: 新合约上线、合约下架

### Internal Dependencies

- **现有数据库模型**: 需要确保新增的表与现有的ScreeningResult、MonitoredContract等模型兼容

- **定时任务框架**: 需要使用Django的Celery或cron job来实现定期数据更新

- **通知系统**: 需要集成项目现有的推送通知机制(如果存在)来发送更新报告

## Out of Scope *(optional)*

以下内容明确不在本次功能范围内:

1. **实时价格更新**: 不支持市值和FDV的实时刷新,只提供每日定时更新
2. **历史数据图表**: 不展示市值和FDV的历史变化趋势图
3. **多货币支持**: 只支持美元(USD)显示,不支持其他法币或加密货币单位
4. **详细数据钻取**: 不提供点击市值/FDV后跳转到详细分析页面的功能
5. **链上合约地址(CA)**: 虽然参考指南提到CA,但不在本次需求中实现
6. **手动编辑数据**: 管理员不能直接编辑市值/FDV数值,只能通过重新获取API数据来更新
7. **多个区块链平台**: 只处理币安永续合约,不涉及其他交易所或链上DEX的数据

## Notes *(optional)*

### 技术实现建议

1. **API限流应对**:
   - CoinGecko免费API有限流(50次/分钟),建议批量查询时使用延迟机制
   - 可以考虑分批次处理,每批50个symbol,批次间延迟1分钟

2. **数据缓存策略**:
   - 市值和FDV数据可以缓存24小时,减少不必要的API调用
   - 前端可以使用Django模板标签直接从数据库读取,无需额外缓存层

3. **映射关系维护**:
   - 建议建立一个"映射关系审核"的Django Admin界面,方便管理员批量审核和修改
   - 对于needs_review状态的映射,可以提供一个候选列表供管理员选择

4. **错误处理**:
   - CoinGecko API可能返回429(Too Many Requests)或503(Service Unavailable)
   - 建议实现指数退避算法:首次失败等待1秒,第二次2秒,第三次4秒

5. **数据一致性**:
   - 考虑使用数据库事务确保映射关系和市场数据的原子性更新
   - 更新失败时应该能够回滚到上一个稳定状态

### 用户交互注意事项

1. **数据缺失提示**: 当显示"-"时,鼠标悬停应该显示tooltip解释原因(例如:"该代币在CoinGecko中无数据"或"数据获取失败,将在下次更新重试")

2. **排序逻辑**: 当按市值或FDV排序时,显示"-"的合约应该始终排在最后

3. **单位缩写**: 确保数字格式化逻辑清晰:
   - < 1,000: 显示完整数字
   - >= 1,000 and < 1,000,000: 使用K(如 850K)
   - >= 1,000,000 and < 1,000,000,000: 使用M(如 125M)
   - >= 1,000,000,000: 使用B(如 2.5B)

### 未来扩展可能性

虽然以下功能不在当前范围,但设计时可以为未来预留扩展性:

1. **更多CoinGecko数据**: 24h交易量、市值排名、链上合约地址等
2. **多数据源对比**: 除了CoinGecko,未来可能集成CoinMarketCap或Messari的数据
3. **数据质量评分**: 为每个代币的数据可靠性提供一个评分(基于数据源、更新频率等)
