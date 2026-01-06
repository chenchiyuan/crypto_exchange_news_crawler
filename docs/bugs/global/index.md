# 全局Bug索引

本目录记录所有跨迭代的全局Bug。

---

## Bug列表

| Bug ID | 标题 | 严重程度 | 状态 | 发现日期 | 修复日期 | 关联迭代 |
|--------|------|----------|------|----------|----------|----------|
| 001 | 批量更新K线时找到0个活跃合约 | P0 | ✅ 已修复 | 2024-12-24 | 2024-12-24 | 003 |
| 002 | fetch_futures命令需要预先创建Exchange记录 | P0 | ✅ 已修复 | 2024-12-24 | 2024-12-24 | 003 |
| 003 | Discovery阶段检测失败 'current_close' KeyError | P0 | ✅ 已修复 | 2024-12-24 | 2024-12-24 | 002 |
| 004 | volume_trap_backtest命令 DataInsufficientError 参数缺失 | P1 | ✅ 已修复 | 2025-12-26 | 2025-12-26 | 007 |
| 005 | Volume Trap异常事件触发时间错误 | P0 | ✅ 已修复 | 2025-12-26 | 2025-12-26 | 007 |

---

## Bug详情

### Bug-001: 批量更新K线时找到0个活跃合约

**问题**: 执行 `python manage.py update_klines --interval 4h` 时显示"找到0个活跃合约"，无法批量更新K线数据。

**根因**: 数据库中 `FuturesContract` 表为空，需要预先运行 `fetch_futures` 命令初始化合约数据。

**修复方案**:
- 在 `_update_all_symbols()` 方法中添加空合约检查（13行代码）
- 显示友好提示信息，指导用户运行 `fetch_futures --all`
- 更新迭代003文档，添加"前置条件"章节

**影响模块**: `backtest/management/commands/update_klines.py`

**详细报告**: [bug-001-no-active-contracts.md](./bug-001-no-active-contracts.md)

### Bug-002: fetch_futures命令需要预先创建Exchange记录

**问题**: 执行 `python manage.py fetch_futures --exchange binance` 时提示"交易所 binance 不存在于数据库中"，无法初始化合约数据。

**根因**: 数据库中 `Exchange` 表为空，但 `fetch_futures` 命令强制要求该数据必须存在。

**修复方案**:
- 在 `fetch_futures.py` 中添加自动创建Exchange逻辑（15行代码）
- 使用 `get_or_create()` 自动创建不存在的交易所记录
- 填充合理的默认值（name, enabled, announcement_url）

**影响模块**: `monitor/management/commands/fetch_futures.py`

**详细报告**: [bug-002-missing-exchange-records.md](./bug-002-missing-exchange-records.md)

### Bug-003: Discovery阶段检测失败 'current_close' KeyError

**问题**: 执行 `python manage.py scan_volume_traps --interval 4h` 时，Discovery阶段检测失败，错误信息为 `'current_close'` KeyError。

**根因**: `amplitude_detector.calculate()` 返回字典缺少 `current_close`, `current_high`, `current_low` 三个字段，而FSM代码中访问了这些不存在的键。

**修复方案**:
- 在 `amplitude_detector.py` 返回字典中添加这三个字段（3行代码）
- 将内部已计算的值包含在返回字典中

**影响模块**: `volume_trap/detectors/amplitude_detector.py`

**详细报告**: [bug-003-discovery-keyerror.md](./bug-003-discovery-keyerror.md)

### Bug-004: volume_trap_backtest命令 DataInsufficientError 参数缺失

**问题**: 运行 `volume_trap_backtest` 命令时，1892个异常事件回测失败，错误信息为 `DataInsufficientError.__init__() missing 3 required positional arguments`。

**根因**: `backtest_engine.py` 中两处 DataInsufficientError 调用只传了一个字符串参数，但异常类需要4个参数（required, actual, symbol, interval）。

**修复方案**:
- 修复第59行调用：提供 required=1, actual=0, symbol, interval
- 修复第68行调用：提供 required=min_bars_to_lowest, actual=actual_count, symbol, interval
- 使用命名参数确保代码可读性

**影响模块**: `volume_trap/services/backtest_engine.py`

**详细报告**: [bug-004-datainsufficient-error-fix.md](./bug-004-datainsufficient-error-fix.md)

### Bug-005: Volume Trap异常事件触发时间错误

**问题**: 1892个异常事件的trigger_time被错误设置为命令运行时间（2025-12-25 09:40），导致回测时找不到触发时间后的K线数据。

**根因**: amplitude_detector.calculate()未返回current_kline_open_time字段，_check_discovery_condition()使用fallback机制导致trigger_time被设置为命令运行时间。

**修复方案**:
- 在amplitude_detector返回值中添加current_kline_open_time字段
- 移除fallback机制，确保无法获取时间字段时抛出明确错误
- 重新运行scan_volume_traps命令创建正确的异常事件

**影响模块**: `volume_trap/detectors/amplitude_detector.py`, `volume_trap/services/volume_trap_fsm.py`

**详细报告**: [bug-005-volume-trap-trigger-time-fix.md](./bug-005-volume-trap-trigger-time-fix.md)

---

## 统计信息

- **总Bug数**: 5
- **已修复**: 5
- **待修复**: 0
- **平均修复时间**: 0.3小时

---

**最后更新**: 2025-12-26
