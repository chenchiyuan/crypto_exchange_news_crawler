# 功能点清单: 批量回测评估体系

## 文档信息
| 属性 | 值 |
|------|-----|
| 迭代编号 | 040 |
| 项目名称 | batch-backtest-evaluation |
| 创建日期 | 2026-01-13 |
| 版本 | 1.0 |

## 功能点总览

| ID | 功能点 | 优先级 | 阶段 | 状态 |
|----|--------|--------|------|------|
| FP-040-001 | 新增静态APR指标 | P0 | Phase 1 | 待开发 |
| FP-040-002 | 新增综合年化APY指标 | P0 | Phase 1 | 待开发 |
| FP-040-003 | 扩展统计输出 | P0 | Phase 1 | 待开发 |
| FP-040-004 | 批量回测命令 | P0 | Phase 2 | 待开发 |
| FP-040-005 | 交易对列表获取 | P0 | Phase 2 | 待开发 |
| FP-040-006 | CSV结果存储 | P0 | Phase 2 | 待开发 |
| FP-040-007 | 错误处理与跳过 | P0 | Phase 2 | 待开发 |
| FP-040-008 | 进度显示 | P1 | Phase 2 | 待开发 |

---

## Phase 1: 扩展回测指标

### FP-040-001: 新增静态APR指标
**优先级**: P0 | **预估工作量**: 0.5h

**描述**:
在回测结果中新增静态APR（年化收益率）指标，基于账户净值变化和回测天数线性年化。

**计算公式**:
```python
static_apr = (total_equity - initial_capital) / initial_capital / backtest_days * 365 * 100
```

**输入**:
- `total_equity`: 账户总价值（可用现金 + 挂单冻结 + 持仓市值）
- `initial_capital`: 初始资金
- `backtest_days`: 回测天数

**输出**:
- `static_apr`: 静态年化收益率（%），保留2位小数

**修改文件**:
- `strategy_adapter/strategies/strategy16_limit_entry.py`
  - `_generate_result()`: 新增`static_apr`字段计算
- `strategy_adapter/management/commands/run_strategy_backtest.py`
  - 输出显示新增一行

**验收标准**:
- [ ] 命令行输出显示`静态APR: +xx.xx%`或`静态APR: -xx.xx%`
- [ ] 返回值Dict包含`static_apr`字段
- [ ] 回测天数正确计算（end_date - start_date）

---

### FP-040-002: 新增综合年化APY指标
**优先级**: P0 | **预估工作量**: 1h

**描述**:
基于时间加权法计算综合年化APY，考虑每笔订单的持仓时间和资金占用效率。

**计算公式**:
```python
# 对每笔订单计算年化收益率
for order in all_orders:
    holding_days = max((sell_time - buy_time) / ms_per_day, 1)  # 最小1天
    annualized_rate = order_return_rate * (365 / holding_days)
    weighted_sum += annualized_rate * order_amount
    total_amount += order_amount

weighted_apy = weighted_sum / total_amount if total_amount > 0 else 0
```

**特殊处理**:
- **持仓中订单**: 使用`回测结束时间`作为卖出时间，使用`当前市值`计算收益率
- **最小持仓天数**: 1天（避免除零）
- **无订单情况**: APY = 0

**输入**:
- 所有已平仓订单列表（含金额、收益率、持仓时间）
- 所有持仓中订单列表（含金额、浮动盈亏、买入时间）
- 回测结束时间

**输出**:
- `weighted_apy`: 时间加权年化收益率（%），保留2位小数

**修改文件**:
- `strategy_adapter/strategies/strategy16_limit_entry.py`
  - `_generate_result()`: 新增APY计算逻辑
- `strategy_adapter/management/commands/run_strategy_backtest.py`
  - 输出显示新增一行

**验收标准**:
- [ ] 命令行输出显示`综合APY: +xx.xx%`或`综合APY: -xx.xx%`
- [ ] 已平仓订单正确计算持仓天数
- [ ] 持仓中订单使用回测结束时间计算
- [ ] 无订单时APY为0

---

### FP-040-003: 扩展统计输出
**优先级**: P0 | **预估工作量**: 0.5h

**描述**:
整合所有指标，确保回测结果包含完整的统计字段。

**输出字段清单**:
```
【整体统计】
  总订单数: xxx
  已平仓: xxx
  持仓中: xxx
  净利润: +xxx.xx USDT
  胜率: xx.xx%
  收益率: +xx.xx%
  静态APR: +xx.xx%   <- 新增
  综合APY: +xx.xx%   <- 新增

【资金统计】
  可用现金: xxx.xx USDT
  挂单冻结: xxx.xx USDT
  持仓成本: xxx.xx USDT
  持仓市值: xxx.xx USDT
  账户总值: xxx.xx USDT

【交易成本】
  总交易量: xxx.xx USDT
  总手续费: xxx.xx USDT
```

**修改文件**:
- `strategy_adapter/management/commands/run_strategy_backtest.py`
  - 调整输出格式，新增APR/APY行

**验收标准**:
- [ ] 所有字段正确显示
- [ ] 格式对齐美观
- [ ] 正负号正确显示

---

## Phase 2: 批量回测框架

### FP-040-004: 批量回测命令
**优先级**: P0 | **预估工作量**: 2h

**描述**:
新增`run_batch_backtest`管理命令，支持批量回测多个交易对。

**命令格式**:
```bash
python manage.py run_batch_backtest \
  --config <config.json> \
  --symbols ETHUSDT,BTCUSDT,SOLUSDT \
  --output <output.csv> \
  --auto-fetch
```

**参数定义**:
| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| --config | str | 是 | - | 策略配置文件路径 |
| --symbols | str | 否 | ALL | 交易对列表（逗号分隔）或ALL |
| --output | str | 否 | `data/backtest_{timestamp}.csv` | CSV输出路径 |
| --auto-fetch | flag | 否 | False | 自动拉取缺失K线 |

**新增文件**:
- `strategy_adapter/management/commands/run_batch_backtest.py`

**依赖**:
- 复用`run_strategy_backtest`核心逻辑
- 调用`Strategy16LimitEntry.run_backtest()`

**验收标准**:
- [ ] 命令可正常执行
- [ ] 支持单个交易对：`--symbols ETHUSDT`
- [ ] 支持多个交易对：`--symbols ETHUSDT,BTCUSDT`
- [ ] 支持全部交易对：`--symbols ALL`
- [ ] --auto-fetch正常工作

---

### FP-040-005: 交易对列表获取
**优先级**: P0 | **预估工作量**: 0.5h

**描述**:
获取待回测交易对列表，支持指定列表或获取全部。

**实现逻辑**:
```python
def get_symbols(symbols_arg: str) -> List[str]:
    if symbols_arg == 'ALL':
        # 从FuturesContract获取所有活跃交易对
        return FuturesContract.objects.filter(
            status='trading'
        ).values_list('symbol', flat=True)
    else:
        # 解析逗号分隔的列表
        return [s.strip() for s in symbols_arg.split(',')]
```

**数据源**: `backtest.models.FuturesContract`

**验收标准**:
- [ ] 正确解析逗号分隔列表
- [ ] ALL模式获取所有活跃合约
- [ ] 去重处理

---

### FP-040-006: CSV结果存储
**优先级**: P0 | **预估工作量**: 1h

**描述**:
将批量回测结果保存为CSV文件。

**CSV表头**:
```csv
symbol,total_orders,closed_orders,open_positions,available_capital,frozen_capital,holding_cost,holding_value,total_equity,total_volume,total_commission,win_rate,net_profit,return_rate,static_apr,weighted_apy,backtest_days,start_date,end_date
```

**字段映射**:
| 字段名 | 来源 | 类型 |
|--------|------|------|
| symbol | 交易对 | str |
| total_orders | statistics.total_orders | int |
| closed_orders | total_orders - open_positions | int |
| open_positions | statistics.open_positions | int |
| available_capital | available_capital | float |
| frozen_capital | frozen_capital | float |
| holding_cost | holding_cost | float |
| holding_value | holding_value | float |
| total_equity | total_equity | float |
| total_volume | total_volume | float |
| total_commission | total_commission | float |
| win_rate | statistics.win_rate | float |
| net_profit | statistics.total_profit | float |
| return_rate | return_rate | float |
| static_apr | static_apr | float |
| weighted_apy | weighted_apy | float |
| backtest_days | 计算值 | int |
| start_date | config.start_date | str |
| end_date | config.end_date | str |

**编码**: UTF-8 with BOM（Excel兼容）

**验收标准**:
- [ ] CSV文件正确生成
- [ ] 表头正确
- [ ] 数值精度正确（float保留2位小数）
- [ ] Excel可正确打开

---

### FP-040-007: 错误处理与跳过
**优先级**: P0 | **预估工作量**: 0.5h

**描述**:
单个交易对回测失败不影响整体流程。

**错误处理策略**:
```python
for symbol in symbols:
    try:
        result = run_single_backtest(symbol, config)
        results.append(result)
    except Exception as e:
        logger.error(f"回测失败 {symbol}: {e}")
        results.append({
            'symbol': symbol,
            'error': str(e),
            # 其他字段填充为空或0
        })
```

**验收标准**:
- [ ] 单个失败不中断整体
- [ ] 错误信息记录到日志
- [ ] CSV中失败项可识别（所有数值为0或空）

---

### FP-040-008: 进度显示
**优先级**: P1 | **预估工作量**: 0.5h

**描述**:
显示批量回测进度和关键统计。

**显示格式**:
```
[1/50] ETHUSDT ... 3.2s | 订单:180 胜率:56.98% APR:-21.72%
[2/50] BTCUSDT ... 2.8s | 订单:145 胜率:62.07% APR:+15.34%
...
[50/50] SOLUSDT ... 2.5s | 订单:120 胜率:58.33% APR:+8.45%

========================================
批量回测完成: 50/50 成功
结果保存至: data/backtest_20260113_120000.csv
```

**验收标准**:
- [ ] 实时显示当前进度
- [ ] 显示每个交易对耗时
- [ ] 显示关键统计（订单数、胜率、APR）
- [ ] 最终汇总显示成功/失败数量

---

## 依赖关系

```
FP-040-001 (APR) ──┐
                   ├──> FP-040-003 (扩展输出) ──> FP-040-004 (批量命令)
FP-040-002 (APY) ──┘                                    │
                                                        ├──> FP-040-006 (CSV存储)
FP-040-005 (交易对获取) ────────────────────────────────┘
                                                        │
FP-040-007 (错误处理) ──────────────────────────────────┤
                                                        │
FP-040-008 (进度显示) ──────────────────────────────────┘
```

## 实施顺序

### Phase 1（先行）
1. FP-040-001: 新增静态APR指标
2. FP-040-002: 新增综合年化APY指标
3. FP-040-003: 扩展统计输出

### Phase 2（后续）
4. FP-040-005: 交易对列表获取
5. FP-040-004: 批量回测命令
6. FP-040-007: 错误处理与跳过
7. FP-040-006: CSV结果存储
8. FP-040-008: 进度显示（P1）
