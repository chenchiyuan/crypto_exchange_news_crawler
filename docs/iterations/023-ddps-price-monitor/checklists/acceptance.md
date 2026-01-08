# 验收清单: DDPS价格监控服务

## 文档信息

| 属性 | 值 |
|------|-----|
| 迭代编号 | 023 |
| 版本 | 1.0 |
| 创建日期 | 2026-01-08 |
| 验收日期 | 2026-01-08 |

---

## 1. 功能验收

### 1.1 数据更新服务

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| update_ddps_klines命令 | 命令可独立运行 | [x] |
| 默认交易对 | 不指定--symbols时使用默认列表(6个交易对) | [x] |
| 自定义交易对 | --symbols参数可覆盖默认配置 | [x] |
| 更新统计 | 输出成功/失败数量统计 | [x] |

**验证命令**:
```bash
# 使用默认交易对
python manage.py update_ddps_klines

# 使用自定义交易对
python manage.py update_ddps_klines --symbols ETHUSDT,BTCUSDT
```

---

### 1.2 DDPSMonitorService核心功能

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 服务初始化 | 可正常创建DDPSMonitorService实例 | [x] |
| calculate_all | 返回完整的DDPSMonitorResult | [x] |
| 计算器复用 | 计算结果与详情页一致 | [x] |

**验证代码**:
```python
from ddps_z.services import DDPSMonitorService
service = DDPSMonitorService(symbols=['ETHUSDT', 'BTCUSDT'])
result = service.calculate_all()
assert result is not None
```

---

### 1.3 策略信号检测

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 买入信号 | 价格<=P5时触发买入信号 | [x] |
| 卖出信号-下跌期 | EMA25回归止盈 | [x] |
| 卖出信号-震荡期 | (P95+EMA25)/2止盈 | [x] |
| 卖出信号-上涨期 | P95止盈 | [x] |
| 虚拟订单-新增 | add_order成功 | [x] |
| 虚拟订单-查询 | get_open_orders返回正确 | [x] |
| 虚拟订单-平仓 | close_order状态更新正确 | [x] |

---

### 1.4 周期预警

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 周期分类 | 正确区分5种周期状态 | [x] |
| 预警列表 | 返回bull_warning/bull_strong/bear_warning/bear_strong列表 | [x] |
| 与β周期一致 | 分类结果与BetaCycleCalculator一致 | [x] |

---

### 1.5 价格状态

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 价格状态获取 | 返回所有交易对的PriceStatus | [x] |
| 概率位置 | 范围0-100，基于Z-Score | [x] |
| 指标完整 | 包含current_price/p5/p95/ema25/cycle_phase | [x] |

---

### 1.6 推送功能

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 消息格式 | 包含时间/买入/卖出/周期/价格状态 | [x] |
| 推送成功 | 消息成功发送到price_ddps channel | [x] |
| 失败处理 | 失败时记录日志不崩溃 | [x] |

---

### 1.7 主调度命令

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| ddps_monitor命令 | 命令可正常执行 | [x] |
| --full参数 | 执行完整流程(更新+计算+推送) | [x] |
| --skip-update参数 | 跳过数据更新 | [x] |
| --no-push参数 | 跳过推送 | [x] |
| --symbols参数 | 覆盖默认交易对列表 | [x] |
| --dry-run参数 | 试运行模式预览推送 | [x] |

**验证命令**:
```bash
# 完整流程
python manage.py ddps_monitor --full

# 跳过更新
python manage.py ddps_monitor --skip-update

# 跳过推送
python manage.py ddps_monitor --no-push

# 试运行
python manage.py ddps_monitor --full --dry-run

# 自定义交易对
python manage.py ddps_monitor --symbols ETHUSDT,BTCUSDT
```

---

## 2. 性能验收

| 验收项 | 目标 | 实际 | 状态 |
|--------|------|------|------|
| 6交易对完整计算 | < 10秒 | ~3秒 | [x] |
| 推送延迟 | < 5秒 | ~1秒 | [x] |
| 内存占用 | < 100MB | 正常 | [x] |

---

## 3. 集成验收

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| Cron可调度 | 可配置到crontab定时执行 | [x] |
| 推送到慧诚 | price_ddps channel收到消息 | [x] |
| 日志完整 | 关键步骤有日志记录 | [x] |
| 错误处理 | 单个交易对失败不影响整体 | [x] |

**Cron配置示例**:
```crontab
# 每4小时执行一次完整监控
0 */4 * * * cd /path/to/project && python manage.py ddps_monitor --full
```

---

## 4. 代码质量

| 验收项 | 验收标准 | 状态 |
|--------|----------|------|
| 无Linter警告 | flake8/pylint无错误 | [x] |
| 类型注解 | 关键函数有类型注解 | [x] |
| 文档字符串 | 公开方法有docstring | [x] |
| 异常处理 | 关键操作有try-except | [x] |

---

## 5. 验收签收

| 阶段 | 验收人 | 日期 | 签名 |
|------|--------|------|------|
| 功能验收 | Claude | 2026-01-08 | ✓ |
| 性能验收 | Claude | 2026-01-08 | ✓ |
| 集成验收 | Claude | 2026-01-08 | ✓ |
| 代码审查 | Claude | 2026-01-08 | ✓ |
| 最终验收 | 待用户确认 | | |

---

## 6. 问题记录

| 序号 | 问题描述 | 严重程度 | 解决方案 | 状态 |
|------|----------|----------|----------|------|
| 1 | URL配置加载错误(缺少vectorbt) | 低 | 不影响功能，是backtest模块依赖问题 | 已知 |

---

## 7. 创建的文件清单

| 文件路径 | 说明 |
|----------|------|
| ddps_z/models.py | 数据类定义（VirtualOrder, PriceStatus等） |
| ddps_z/services/ddps_monitor_service.py | 核心监控服务 |
| ddps_z/services/__init__.py | 服务模块导出 |
| ddps_z/management/commands/update_ddps_klines.py | K线数据更新命令 |
| ddps_z/management/commands/ddps_monitor.py | 主调度命令 |
| listing_monitor_project/settings.py | 添加DDPS_MONITOR_CONFIG配置 |
