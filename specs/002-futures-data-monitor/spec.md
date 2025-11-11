# Feature Specification: Futures Contract Data Monitor

**Feature Branch**: `002-futures-data-monitor`
**Created**: 2025-11-10
**Status**: Draft
**Input**: User description: "我需要获取Binance, Bybit, Bitget, Hyperliquid 4家的合约列表数据，如果发现新币上线需要单独推送。获取合约列表数据需要使用native的方式，直接使用官方指定的api获取。交易对获取之后需要存储与django admin中。我需要知道：ExchangeOI24H Vol↓ 1Y Funding─ Next Funding  Upper / Lower  Inter"

## Clarifications

### Session 2025-11-10

- Q: 合约的实时指标数据(OI、Volume、Funding Rate等)应该如何存储? → A: 直接在 FuturesContract 表中更新,只保留最新值
- Q: 如何判定一个合约是"新上线"而不是"系统首次发现的已存在合约"? → A: 首次在数据库中出现即视为新上线,但系统初次运行时不发送通知(避免大量历史通知)
- Q: 当某个交易所的API调用失败时,系统应该如何处理? → A: 对失败的交易所立即重试3次,仍失败则跳过并记录错误
- Q: 需要获取哪些类型的合约数据? → A: 仅USDT本位永续合约
- Q: 用户原始需求中提到的"Inter"指的是什么指标? → A: Interval(更新间隔时间)

### Session 2025-11-10 (优先级调整)

**范围调整**:
- **实施的交易所** (按优先级): Binance (P1) → Hyperliquid (P2) → Bybit (P3)
- **延后实施**: Bitget (暂不实现)
- **功能简化**:
  - ✅ 实施: 同步交易对列表、获取当前价格
  - ❌ 延后: 过往价格存储、历史数据同步、OI/Volume/Funding Rate等高级指标

**理由**:
- Binance作为最大交易所,数据最权威,优先实现
- Hyperliquid为新兴交易所,高优先级关注
- 先建立基础框架(交易对列表+当前价格),再逐步扩展指标
- 简化初版,快速上线验证

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Real-time Futures Contract Data (Priority: P1)

As a crypto trader, I need to view futures contract lists and current prices across multiple exchanges in one place, so I can quickly identify which contracts are available without checking multiple platforms.

**Why this priority**: This is the core value proposition - providing unified access to futures contract lists. Without this, the feature delivers no value.

**Independent Test**: Can be fully tested by accessing the admin interface and verifying that futures contract data from at least one exchange is displayed with symbol and current price. Delivers immediate value by providing data aggregation.

**Acceptance Scenarios**:

1. **Given** the system has fetched futures data, **When** I access the Django admin futures page, **Then** I see a list of all active futures contracts with their basic information (exchange, symbol, current price, contract type)
2. **Given** I'm viewing the futures list, **When** I click on a specific contract, **Then** I see detailed information including exchange name, symbol, current price, and timestamps
3. **Given** futures data exists for multiple exchanges, **When** I filter by exchange, **Then** I only see contracts from the selected exchange
4. **Given** multiple contracts exist, **When** I sort by current price, **Then** contracts are displayed in the correct order

---

### User Story 2 - Receive New Futures Listing Alerts (Priority: P2)

As a crypto trader, I need to be immediately notified when a new futures contract is listed on any monitored exchange, so I can evaluate early trading opportunities.

**Why this priority**: New listings often present trading opportunities, but only after the core data collection (P1) is working. This adds value on top of data collection.

**Independent Test**: Can be tested by manually triggering a new listing detection (or waiting for a real one) and verifying that a notification is sent through the configured channel. Works independently of P1 as long as the detection mechanism exists.

**Acceptance Scenarios**:

1. **Given** the system is monitoring futures contracts, **When** a new contract appears that wasn't present in the previous check, **Then** a notification is sent with the contract details
2. **Given** a new futures listing is detected, **When** the notification is sent, **Then** it includes exchange name, contract symbol, current price, and listing time
3. **Given** multiple new listings occur simultaneously, **When** notifications are triggered, **Then** each listing generates a separate notification
4. **Given** a contract already exists in the database, **When** it's detected again in a subsequent fetch, **Then** no duplicate notification is sent

---

### User Story 3 - Monitor Contract Status Changes (Priority: P3)

As a crypto trader, I need to see when contracts become delisted or expired, so I can adjust my trading strategy accordingly.

**Why this priority**: Status monitoring is valuable but secondary to core data viewing (P1) and new listing alerts (P2). Most traders focus on active contracts.

**Independent Test**: Can be tested by marking a contract as delisted in the system and verifying it's displayed with the appropriate status indicator in the admin interface.

**Acceptance Scenarios**:

1. **Given** a contract becomes delisted, **When** I view the futures list, **Then** I see a status indicator showing it's no longer active
2. **Given** delisted contracts exist, **When** I filter by status, **Then** I can view only active or only delisted contracts
3. **Given** a contract has been delisted for 90 days, **When** the retention period expires, **Then** the record is removed from the database

**Note**: Historical funding rate trends (原User Story 3) are out of scope for this version as the system only maintains current snapshots, not time-series data. This may be reconsidered in future phases if historical analysis becomes a priority.

---

### Edge Cases

- What happens when an exchange API is temporarily unavailable or returns errors?
- How does the system handle API rate limits from exchanges?
- What if a futures contract is delisted or expires?
- How are contracts with identical symbols on different exchanges distinguished?
- What happens if fetched data is incomplete (missing some metrics)?
- How does the system handle timezone differences for funding times across exchanges?
- What if a contract exists but has zero Open Interest or Volume?

## Requirements *(mandatory)*

### Functional Requirements

**MVP阶段 (仅实现基础功能)**:

- **FR-001**: System MUST fetch USDT-margined perpetual futures contract lists from Binance (P1), Hyperliquid (P2), and Bybit (P3) using their official public APIs
- **FR-002**: System MUST retrieve the following **basic** metrics for each futures contract: Exchange name, Contract Symbol, Current Price (Mark Price or Last Price)
- **FR-003**: System MUST store all fetched futures contract data persistently, with current price updated in-place on each fetch cycle
- **FR-004**: System MUST provide a Django admin interface to view and manage futures contract data
- **FR-005**: System MUST detect new futures contract listings by comparing current API data with stored historical data. On initial system deployment, newly discovered contracts are recorded but no notifications are sent.
- **FR-006**: System MUST send notifications when new futures contracts are detected (excluding the initial deployment phase)
- **FR-007**: System MUST update existing contract data on each fetch cycle without creating duplicate records
- **FR-008**: System MUST handle API failures gracefully by immediately retrying failed requests up to 3 times with exponential backoff. If all retries fail, the system skips that exchange for the current cycle, logs the error, and continues processing other exchanges.
- **FR-009**: System MUST distinguish between contracts with identical symbols on different exchanges using a composite unique identifier (exchange + symbol)
- **FR-010**: System MUST display sortable and filterable lists in Django admin (by exchange, symbol, price)
- **FR-011**: System MUST fetch data every 5 minutes from each exchange
- **FR-012**: Notifications MUST be sent via the existing 慧诚告警推送 (Alert Push Service)
- **FR-013**: System MUST retain contract records for 90 days after delisting. Active contracts are retained indefinitely.

**延后实施 (Phase 2)**:
- Open Interest (OI)
- 24-hour Trading Volume
- Funding Rate, Next Funding Time, Upper/Lower Bounds
- Last Update Interval
- Historical price data and time-series storage

### Key Entities

**MVP阶段实体**:

- **FuturesContract**: Represents a single USDT perpetual futures contract on an exchange
  - Exchange reference (Binance, Hyperliquid, Bybit)
  - Contract symbol (e.g., BTCUSDT)
  - Contract type (always "perpetual" for this feature)
  - Current status (active, delisted)
  - Current price (Mark Price or Last Price)
  - First seen timestamp (for new listing detection)
  - Last updated timestamp

- **FuturesListingNotification**: Record of notifications sent for new listings
  - Reference to FuturesContract
  - Notification channel used
  - Timestamp sent
  - Status (success, failed, pending)
  - Error message (if failed)

**Phase 2 扩展字段** (延后实施):
  - Open Interest (current value)
  - 24-hour trading volume (current value)
  - Current funding rate
  - Next funding time
  - Funding rate upper bound
  - Funding rate lower bound
  - Last update interval (seconds since last refresh)

## Success Criteria *(mandatory)*

### Measurable Outcomes (MVP阶段)

- **SC-001**: System successfully fetches futures data from all 3 exchanges (Binance, Hyperliquid, Bybit) within 30 seconds per fetch cycle
- **SC-002**: New futures listings are detected and notifications sent within 60 seconds of the contract appearing on the exchange
- **SC-003**: Admin interface displays contract symbol and current price for 100% of active contracts
- **SC-004**: System maintains 99% uptime for data fetching over a 7-day period
- **SC-005**: Zero duplicate notifications are sent for the same new listing
- **SC-006**: Users can sort and filter futures contracts by exchange, symbol, and price in under 2 seconds
- **SC-007**: Contract records are retained for the configured retention period (90 days after delisting) without data loss

## Assumptions

- Exchange APIs are publicly accessible and don't require authentication for basic contract data and price information
- Each exchange provides sufficient rate limits for periodic polling (typically 1200-6000 requests/minute)
- Futures contract symbols follow standard naming conventions on each exchange (except Hyperliquid uses "BTC" instead of "BTCUSDT")
- The existing Django project structure and notification system from feature 001 can be extended
- Network connectivity to exchange APIs is generally reliable
- Exchange API documentation is accurate and up-to-date

## Dependencies

- Existing Django project (listing_monitor_project) from feature 001-listing-monitor
- Existing notification service (慧诚告警推送) from feature 001
- Official API documentation for:
  - Binance Futures API (Priority 1)
  - Hyperliquid API (Priority 2)
  - Bybit Derivatives API (Priority 3)
- Python libraries for HTTP requests (requests or httpx)
- Database schema migration capability

## Scope Boundaries

### In Scope (MVP阶段)
- Fetching USDT-margined perpetual futures contracts only
- Storing contract list and current price in Django admin
- Detecting and notifying about new contract listings (after initial deployment)
- Three exchanges in priority order: Binance (P1), Hyperliquid (P2), Bybit (P3)
- Basic metrics: Exchange, Symbol, Current Price, Status, Timestamps
- Retry mechanism for API failures (3 attempts with exponential backoff)

### Out of Scope (MVP阶段 - 延后至Phase 2)
- Open Interest (OI) tracking
- 24-hour trading volume
- Funding Rate, Next Funding Time, Upper/Lower bounds
- Update Interval tracking
- Historical price data and time-series storage
- Bitget exchange integration (deferred)

### Permanently Out of Scope
- Quarterly, bi-quarterly, or coin-margined futures contracts
- Real-time WebSocket data streams (using polling instead)
- Trading functionality (view-only)
- Price charts or technical analysis
- Options contracts
- Other exchanges beyond the specified ones
- Mobile app interface (Django admin web only)
- Historical data export or reporting features
- Advanced analytics or predictions based on the data
