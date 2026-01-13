# 验收清单: 批量回测评估体系

## 文档信息
| 属性 | 值 |
|------|-----|
| 迭代编号 | 040 |
| 项目名称 | batch-backtest-evaluation |
| 创建日期 | 2026-01-13 |
| 版本 | 1.0 |

---

## Phase 1: 扩展回测指标

### FP-040-001: 静态APR指标
| 检查项 | 状态 |
|--------|------|
| `_calculate_static_apr()` 方法存在 | [ ] |
| 返回结果包含 `static_apr` 字段 | [ ] |
| 返回结果包含 `backtest_days` 字段 | [ ] |
| APR计算公式正确: `(total_equity - initial_capital) / initial_capital / days * 365 * 100` | [ ] |
| 回测天数为0时返回0 | [ ] |
| 精度保留2位小数 | [ ] |

**测试命令**:
```bash
python manage.py run_strategy_backtest ETHUSDT \
  --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
  --auto-fetch
```

**预期输出包含**:
```
静态APR: -21.72%
```

---

### FP-040-002: 综合APY指标
| 检查项 | 状态 |
|--------|------|
| `_calculate_weighted_apy()` 方法存在 | [ ] |
| 返回结果包含 `weighted_apy` 字段 | [ ] |
| 已平仓订单正确计算持仓天数 | [ ] |
| 持仓中订单使用回测结束时间计算 | [ ] |
| 无订单时返回0 | [ ] |
| 持仓天数最小为1天（避免除零） | [ ] |
| 精度保留2位小数 | [ ] |

**计算验证**:
```
订单A: 1000USDT, +5%, 10天 → 年化 = 5% × (365/10) = 182.5%
订单B: 1000USDT, -2%, 5天 → 年化 = -2% × (365/5) = -146%
加权APY = (182.5% × 1000 + (-146%) × 1000) / 2000 = 18.25%
```

---

### FP-040-003: 扩展统计输出
| 检查项 | 状态 |
|--------|------|
| 命令行输出显示 `静态APR: +xx.xx%` | [ ] |
| 命令行输出显示 `综合APY: +xx.xx%` | [ ] |
| 正数显示 `+` 号 | [ ] |
| 负数显示 `-` 号 | [ ] |
| 格式与现有输出对齐 | [ ] |

**预期输出格式**:
```
【整体统计】
  总订单数: 180
  已平仓: 172
  持仓中: 8
  净利润: -1043.41 USDT
  胜率: 56.98%
  收益率: -21.25%
  静态APR: -21.72%    <- 新增
  综合APY: +45.32%    <- 新增
```

---

## Phase 2: 批量回测框架

### FP-040-004: 批量回测命令
| 检查项 | 状态 |
|--------|------|
| 命令 `run_batch_backtest` 可执行 | [ ] |
| `--config` 参数必填验证 | [ ] |
| `--symbols` 参数默认值为 `ALL` | [ ] |
| `--output` 参数可选 | [ ] |
| `--auto-fetch` 参数工作正常 | [ ] |
| `--help` 显示帮助信息 | [ ] |

**测试命令**:
```bash
python manage.py run_batch_backtest --help
```

---

### FP-040-005: 交易对列表获取
| 检查项 | 状态 |
|--------|------|
| 单个交易对: `--symbols ETHUSDT` 正确解析 | [ ] |
| 多个交易对: `--symbols ETHUSDT,BTCUSDT` 正确解析 | [ ] |
| ALL模式: `--symbols ALL` 获取所有活跃合约 | [ ] |
| 交易对名称转大写 | [ ] |
| 去重处理 | [ ] |
| 空列表报错提示 | [ ] |

---

### FP-040-006: CSV结果存储
| 检查项 | 状态 |
|--------|------|
| CSV文件正确生成 | [ ] |
| 编码为UTF-8 BOM | [ ] |
| Excel可正确打开 | [ ] |
| 表头包含19个字段 | [ ] |
| 数值精度正确（2位小数） | [ ] |
| 默认输出路径: `data/backtest_{timestamp}.csv` | [ ] |

**CSV表头验证**:
```csv
symbol,total_orders,closed_orders,open_positions,available_capital,frozen_capital,holding_cost,holding_value,total_equity,total_volume,total_commission,win_rate,net_profit,return_rate,static_apr,weighted_apy,backtest_days,start_date,end_date
```

---

### FP-040-007: 错误处理与跳过
| 检查项 | 状态 |
|--------|------|
| 单个交易对失败不中断整体 | [ ] |
| 失败项在CSV中可识别（数值为0或空） | [ ] |
| 错误信息记录到日志 | [ ] |
| 最终汇总显示成功/失败数量 | [ ] |

---

### FP-040-008: 进度显示
| 检查项 | 状态 |
|--------|------|
| 实时显示当前进度 `[1/50]` | [ ] |
| 显示交易对名称 | [ ] |
| 显示耗时 | [ ] |
| 显示关键统计（订单数、胜率、APR） | [ ] |

**预期格式**:
```
[1/50] ETHUSDT ... 3.2s | 订单:180 胜率:56.98% APR:-21.72%
[2/50] BTCUSDT ... 2.8s | 订单:145 胜率:62.07% APR:+15.34%
...
========================================
批量回测完成: 50/50 成功
结果保存至: data/backtest_20260113_120000.csv
```

---

## 集成测试场景

### 场景1: 单交易对回测增强
```bash
python manage.py run_strategy_backtest ETHUSDT \
  --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
  --auto-fetch
```
| 验证点 | 状态 |
|--------|------|
| 命令执行成功 | [ ] |
| 输出包含静态APR | [ ] |
| 输出包含综合APY | [ ] |

---

### 场景2: 批量回测单交易对
```bash
python manage.py run_batch_backtest \
  --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
  --symbols ETHUSDT \
  --output data/test_single.csv
```
| 验证点 | 状态 |
|--------|------|
| 命令执行成功 | [ ] |
| CSV文件生成 | [ ] |
| CSV包含1行数据（不含表头） | [ ] |
| Excel可正确打开 | [ ] |

---

### 场景3: 批量回测多交易对
```bash
python manage.py run_batch_backtest \
  --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
  --symbols ETHUSDT,BTCUSDT,SOLUSDT \
  --output data/test_multi.csv \
  --auto-fetch
```
| 验证点 | 状态 |
|--------|------|
| 命令执行成功 | [ ] |
| 进度显示正确 | [ ] |
| CSV包含3行数据 | [ ] |
| static_apr字段有值 | [ ] |
| weighted_apy字段有值 | [ ] |

---

### 场景4: 批量回测ALL模式
```bash
python manage.py run_batch_backtest \
  --config strategy_adapter/configs/strategy16_p5_ema_state_exit.json \
  --symbols ALL \
  --auto-fetch
```
| 验证点 | 状态 |
|--------|------|
| 命令执行成功 | [ ] |
| CSV包含所有活跃交易对 | [ ] |
| 部分失败不中断整体 | [ ] |
| 最终汇总正确 | [ ] |

---

## 质量检查

### 代码质量
| 检查项 | 状态 |
|--------|------|
| 无Python语法错误 | [ ] |
| 无运行时异常 | [ ] |
| 日志输出正确 | [ ] |
| 代码风格一致 | [ ] |

### 性能指标
| 指标 | 目标值 | 实际值 | 状态 |
|------|--------|--------|------|
| 单交易对回测 | <30秒 | | [ ] |
| APR计算误差 | <0.01% | | [ ] |
| APY计算误差 | <0.01% | | [ ] |

### 兼容性
| 检查项 | 状态 |
|--------|------|
| 现有run_strategy_backtest功能正常 | [ ] |
| 现有策略16回测功能正常 | [ ] |
| CSV在Excel中正确显示 | [ ] |

---

## 最终验收签字

| 角色 | 签字 | 日期 |
|------|------|------|
| 开发者 | | |
| 审核者 | | |
