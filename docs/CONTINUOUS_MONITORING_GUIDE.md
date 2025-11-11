# 新合约持续监控指南

本文档说明如何配置自动监控新合约上线并接收实时通知。

## 📋 快速开始

### 一键配置（推荐）

```bash
# 1. 进入项目目录
cd /path/to/crypto_exchange_news_crawler

# 2. 运行自动配置脚本
./scripts/setup_monitor_cron.sh

# 3. 按提示操作：
#   - 选择检查频率（推荐：每10分钟）
#   - 选择检测时间范围（推荐：最近30分钟）
#   - 选择监控交易所（推荐：所有交易所）
#   - 确认配置
```

### 配置示例

```
==================================================
  新合约监控 - Cron任务配置
==================================================

✓ 检测到Conda环境: crypto_exchange_monitor

配置信息：
  项目根目录: /Users/xxx/crypto_exchange_news_crawler
  环境类型: conda
  Conda环境: crypto_exchange_monitor
  Python路径: /Users/xxx/miniconda3/envs/crypto_exchange_monitor/bin/python
  管理脚本: /Users/xxx/crypto_exchange_news_crawler/manage.py

监控配置：

请选择检查频率：
  1) 每5分钟
  2) 每10分钟 (推荐)   ← 选择这个
  3) 每15分钟
  4) 每30分钟
  5) 每小时
  6) 自定义

请选择检测时间范围（监控多长时间内的新合约）：
  1) 最近15分钟 (适合高频检查)
  2) 最近30分钟 (推荐)   ← 选择这个
  3) 最近1小时
  4) 最近2小时
  5) 最近24小时
  6) 自定义

请选择监控的交易所：
  1) 所有交易所 (推荐)   ← 选择这个
  2) 仅Binance
  3) 仅Bybit
  4) 仅Hyperliquid

将要添加的Cron任务：
  检查频率: 每10分钟
  检测范围: 最近30分钟
  监控交易所: 所有交易所
  日志文件: /Users/xxx/crypto_exchange_news_crawler/logs/monitor.log

确认添加此cron任务? [y/N]: y

✅ Cron任务已成功添加！

监控系统已启动！
系统将会：
  ✓ 每10分钟检查所有交易所
  ✓ 检测最近30分钟内的新合约
  ✓ 发现新合约时自动推送通知
```

---

## 🎯 监控工作原理

### 工作流程

```
1. Cron定时触发 (每10分钟)
   ↓
2. 执行 monitor_futures 命令
   ↓
3. 从交易所API获取最新合约数据
   ↓
4. 保存到数据库
   ↓
5. 检测最近30分钟内首次出现的合约
   ↓
6. 过滤掉已发送通知的合约
   ↓
7. 发送新合约上线通知（慧诚告警推送）
   ↓
8. 记录通知状态到数据库
```

### 通知内容示例

```
📈 Bybit 永续合约上线 - TRUMPUSDT

合约代码: TRUMPUSDT
交易类型: 永续合约
交易所: Bybit (bybit)
当前价格: $10.5

状态: 活跃
首次发现: 2025-11-11 14:30:00
最后更新: 2025-11-11 14:30:00
```

---

## 📊 查看监控状态

### 查看Cron任务

```bash
# 查看所有cron任务
crontab -l

# 应该看到类似这样的行：
# */10 * * * * cd /path/to/project && conda run -n crypto_exchange_monitor python manage.py monitor_futures --exchange all --hours 0.5 >> /path/to/logs/monitor.log 2>&1 # futures_monitor
```

### 查看日志

```bash
# 实时查看监控日志
tail -f logs/monitor.log

# 查看最近100行
tail -n 100 logs/monitor.log

# 查看详细更新日志
tail -f logs/futures_updates.log

# 搜索特定日期的新合约
grep "检测到.*个新合约" logs/monitor.log
```

### 日志示例

```
============================================================
🚀  合约监控系统启动
============================================================

📋 配置信息:
  - 目标交易所: ALL
  - 检测时间范围: 最近30分钟
  - 通知功能: 已启用
============================================================

📡 正在获取合约数据...

📡 正在获取 BINANCE 数据...
  ✓ 成功: 新增 0, 更新 535, 下线 0

📡 正在获取 BYBIT 数据...
  ✓ 成功: 新增 2, 更新 555, 下线 0

📡 正在获取 HYPERLIQUID 数据...
  ✓ 成功: 新增 0, 更新 220, 下线 0

📊 数据获取结果:
  ✓ BINANCE: 535 个合约
  ✓ BYBIT: 557 个合约
  ✓ HYPERLIQUID: 220 个合约

🔍 正在检测新合约上线...
  📢 检测到 2 个新合约，开始发送通知...
  ✓ 通知发送完成: 成功 2, 失败 0

============================================================
📊 执行摘要
============================================================
  处理交易所: BINANCE, BYBIT, HYPERLIQUID
  合约总数: 1312
  执行时间: 3.52 秒
  数据保存: 已保存到数据库
============================================================

✅ 执行完成
============================================================
```

---

## 🛠️ 管理监控任务

### 停止监控

```bash
# 运行删除脚本
./scripts/remove_monitor_cron.sh

# 或手动删除
crontab -e
# 删除包含 "# futures_monitor" 的行
```

### 修改监控配置

```bash
# 1. 先删除旧任务
./scripts/remove_monitor_cron.sh

# 2. 重新配置（会提示选择新的参数）
./scripts/setup_monitor_cron.sh
```

### 暂时禁用监控

```bash
# 编辑crontab
crontab -e

# 在监控任务行前添加 # 注释掉
# */10 * * * * cd /path/to/project ...

# 保存退出
```

### 手动执行一次监控

```bash
# 激活环境（Conda）
conda activate crypto_exchange_monitor

# 手动执行监控（检测最近24小时）
python manage.py monitor_futures --hours 24

# 测试模式（不保存数据，不发送通知）
python manage.py monitor_futures --hours 24 --test
```

---

## 🎛️ 配置建议

### 推荐配置

| 场景 | 检查频率 | 检测范围 | 说明 |
|------|---------|---------|------|
| **标准监控** | 每10分钟 | 最近30分钟 | 平衡实时性和性能 |
| **高频监控** | 每5分钟 | 最近15分钟 | 快速发现新合约 |
| **低频监控** | 每30分钟 | 最近1小时 | 节省资源 |
| **定期检查** | 每小时 | 最近2小时 | 仅需了解新上线 |

### 参数说明

**检查频率**：
- 越频繁，发现新合约越及时
- 但会增加API调用和系统负载
- 推荐：每10分钟（每天144次检查）

**检测范围**：
- 应该略大于检查频率（避免遗漏）
- 如果检查频率10分钟，范围建议30分钟
- 范围太大会导致重复通知

**交易所选择**：
- 推荐：所有交易所（全面监控）
- 也可以仅监控特定交易所（如仅Binance）

---

## 🔍 故障排查

### 问题1：没有收到通知

**检查项**：

1. **Cron任务是否运行**：
```bash
# 查看cron任务
crontab -l | grep futures_monitor

# 查看最近执行记录
tail -f logs/monitor.log
```

2. **慧诚告警配置**：
```bash
# 检查配置
cat config/futures_config.py | grep HUICHENG

# 测试推送
python manage.py test_push
```

3. **确实有新合约**：
```bash
# 手动运行检查最近24小时
python manage.py monitor_futures --hours 24
```

### 问题2：重复收到通知

**原因**：检测范围太大

**解决**：
```bash
# 减小检测范围
./scripts/remove_monitor_cron.sh
./scripts/setup_monitor_cron.sh
# 选择更小的时间范围（如15分钟）
```

### 问题3：监控任务未执行

**检查**：
```bash
# 查看系统cron服务
# Mac
sudo launchctl list | grep cron

# Linux
systemctl status cron

# 查看cron日志
# Mac
tail -f /var/log/system.log | grep cron

# Linux
sudo tail -f /var/log/syslog | grep CRON
```

### 问题4：数据库锁定

**现象**：日志显示 "database is locked"

**解决**：
1. 确保只有一个监控任务在运行
2. 使用PostgreSQL替代SQLite（生产环境）
3. 增加检查频率间隔

---

## 📈 性能监控

### 检查执行时间

```bash
# 查看平均执行时间
grep "执行时间" logs/monitor.log | tail -20

# 示例输出：
# 执行时间: 3.52 秒
# 执行时间: 3.48 秒
# 执行时间: 3.61 秒
```

### 资源使用

```bash
# 查看Python进程
ps aux | grep "monitor_futures"

# 查看日志文件大小
du -h logs/monitor.log
```

---

## 🔔 通知管理

### 查看通知记录

在Django Admin中查看：
1. 访问 http://localhost:8000/admin
2. 进入 "合约上线通知记录"
3. 查看所有发送记录

### 通知统计

```bash
# 查看成功通知数
grep "通知发送完成" logs/monitor.log | grep "成功" | wc -l

# 查看失败通知
grep "通知发送完成" logs/monitor.log | grep "失败 [1-9]"
```

---

## 📝 最佳实践

### 1. 初次部署

```bash
# 1. 标记初始部署已完成（避免推送历史数据）
python manage.py monitor_futures --mark-initial-complete

# 2. 配置定时监控
./scripts/setup_monitor_cron.sh
```

### 2. 测试配置

```bash
# 使用测试模式验证配置
python manage.py monitor_futures --hours 24 --test

# 手动执行一次（不等待cron）
python manage.py monitor_futures --hours 1
```

### 3. 日志管理

```bash
# 定期清理旧日志（保留最近30天）
find logs/ -name "monitor.log.*" -mtime +30 -delete

# 或使用logrotate（Linux）
sudo logrotate -f /etc/logrotate.d/futures-monitor
```

### 4. 监控多个项目

如果您有多个交易监控项目，可以为每个项目配置独立的cron任务：

```bash
# 项目1：每10分钟监控所有交易所
*/10 * * * * cd /path/to/project1 && python manage.py monitor_futures --hours 0.5 # project1_monitor

# 项目2：每5分钟监控仅Binance
*/5 * * * * cd /path/to/project2 && python manage.py monitor_futures --exchange binance --hours 0.25 # project2_monitor
```

---

## 🆚 监控 vs 价格更新

项目支持两种独立的定时任务：

| 功能 | 监控新合约 | 更新价格 |
|------|----------|---------|
| **命令** | `monitor_futures` | `update_futures_prices` |
| **目的** | 检测新上线合约并通知 | 更新现有合约价格和指标 |
| **推荐频率** | 每10分钟 | 每10分钟 |
| **配置脚本** | `setup_monitor_cron.sh` | `setup_cron.sh` |
| **日志文件** | `logs/monitor.log` | `logs/cron.log` |
| **是否通知** | 是（新合约） | 否 |

### 同时使用两者

```bash
# 1. 配置价格更新（每10分钟）
./scripts/setup_cron.sh

# 2. 配置新合约监控（每10分钟）
./scripts/setup_monitor_cron.sh

# 查看两个任务
crontab -l
# */10 * * * * ... update_futures_prices ... # futures_price_update
# */10 * * * * ... monitor_futures ... # futures_monitor
```

---

## 📚 相关文档

- [monitor_futures命令详细说明](../README.md#monitor_futures)
- [定期更新指南](SCHEDULED_UPDATES_GUIDE.md)
- [市场指标使用指南](MARKET_INDICATORS_GUIDE.md)
- [Conda环境管理](CONDA_SETUP.md)

---

## 💡 常见问题

### Q: 监控和价格更新有什么区别？

A:
- **监控**：检测新上线的合约，并发送通知
- **价格更新**：更新已存在合约的价格和市场指标

建议两者都配置，实现完整的监控系统。

### Q: 如何避免重复通知？

A: 系统会自动记录已发送的通知，不会重复推送同一合约。

### Q: 可以监控特定币种吗？

A: 目前监控所有新上线合约。如需过滤特定币种，可以在收到通知后手动筛选。

### Q: 如何临时停止监控但保留配置？

A:
```bash
# 注释掉cron任务
crontab -e
# 在任务行前添加 #

# 需要时删除 # 即可恢复
```

### Q: 监控任务会影响系统性能吗？

A: 影响很小。每次检查约3-5秒，每天144次（每10分钟），总计约10分钟CPU时间。

---

**祝您监控顺利！如有问题请查看日志或提Issue。** 🎉
