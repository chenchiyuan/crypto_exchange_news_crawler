# 合约价格定期更新指南

本文档说明如何配置和使用定期更新功能来自动更新合约价格和市场指标。

## 📋 目录

- [快速开始](#快速开始)
- [方案选择](#方案选择)
- [Cron定时任务](#cron定时任务)
- [Systemd Timer](#systemd-timer)
- [手动更新](#手动更新)
- [日志查看](#日志查看)
- [故障排查](#故障排查)

---

## 快速开始

### 1. 测试命令

在配置定时任务前，先手动测试命令是否正常工作：

```bash
# 测试模式（不保存到数据库）
python manage.py update_futures_prices --dry-run

# 正常更新所有交易所
python manage.py update_futures_prices

# 仅更新指定交易所
python manage.py update_futures_prices --exchange binance

# 静默模式（适合cron，仅错误时输出）
python manage.py update_futures_prices --quiet
```

### 2. 查看帮助

```bash
python manage.py update_futures_prices --help
```

---

## 方案选择

| 方案 | 适用系统 | 优点 | 缺点 | 推荐场景 |
|------|---------|------|------|----------|
| **Cron** | Mac, Linux | 简单、系统原生 | 需要手动配置 | 所有场景 |
| **Systemd Timer** | Linux | 集成度高、日志完善 | 仅Linux | Linux服务器 |
| **手动执行** | 所有 | 灵活控制 | 需要人工介入 | 开发测试 |

**推荐方案**：
- **Mac系统**: 使用Cron
- **Linux服务器**: 使用Systemd Timer
- **开发环境**: 手动执行

---

## Cron定时任务

### 自动安装（推荐）

使用提供的脚本自动配置：

```bash
# 1. 进入项目目录
cd /path/to/crypto_exchange_news_crawler

# 2. 运行安装脚本
./scripts/setup_cron.sh

# 按提示选择更新频率（推荐：每10分钟）
```

### 手动安装

如果自动脚本不工作，可以手动配置：

```bash
# 1. 编辑crontab
crontab -e

# 2. 添加以下行（每10分钟更新一次）
*/10 * * * * cd /path/to/crypto_exchange_news_crawler && /path/to/venv/bin/python /path/to/crypto_exchange_news_crawler/manage.py update_futures_prices --quiet >> /path/to/crypto_exchange_news_crawler/logs/cron.log 2>&1 # futures_price_update

# 3. 保存并退出（ESC + :wq）
```

### Cron时间格式说明

```
* * * * * 命令
│ │ │ │ │
│ │ │ │ └─ 星期 (0-7, 0和7都表示星期日)
│ │ │ └─── 月份 (1-12)
│ │ └───── 日期 (1-31)
│ └─────── 小时 (0-23)
└───────── 分钟 (0-59)
```

**常用示例**：
```bash
*/5 * * * *    # 每5分钟
*/10 * * * *   # 每10分钟
*/30 * * * *   # 每30分钟
0 * * * *      # 每小时
0 */2 * * *    # 每2小时
0 9-17 * * *   # 每天9:00-17:00的整点
```

### 管理Cron任务

```bash
# 查看当前所有任务
crontab -l

# 删除定时任务
./scripts/remove_cron.sh

# 或手动删除
crontab -e  # 然后删除相关行
```

---

## Systemd Timer

> **仅适用于Linux系统**

### 安装

```bash
# 1. 运行安装脚本
sudo ./scripts/setup_systemd.sh

# 2. 按提示输入配置信息
```

### 管理命令

```bash
# 查看timer状态
sudo systemctl status futures-price-update.timer

# 查看下次执行时间
systemctl list-timers | grep futures

# 手动立即执行一次
sudo systemctl start futures-price-update.service

# 停止定时器
sudo systemctl stop futures-price-update.timer

# 禁用定时器
sudo systemctl disable futures-price-update.timer

# 重新启用
sudo systemctl enable futures-price-update.timer
sudo systemctl start futures-price-update.timer
```

### 查看日志

```bash
# 查看最近的执行日志
sudo journalctl -u futures-price-update.service -n 50

# 实时查看日志
sudo journalctl -u futures-price-update.service -f

# 查看特定时间段的日志
sudo journalctl -u futures-price-update.service --since "1 hour ago"
```

### 修改执行频率

编辑timer文件：

```bash
sudo nano /etc/systemd/system/futures-price-update.timer
```

修改`OnCalendar`行：

```ini
# 每5分钟
OnCalendar=*:0/5

# 每10分钟
OnCalendar=*:0/10

# 每30分钟
OnCalendar=*:0/30

# 每小时
OnCalendar=hourly
```

重新加载配置：

```bash
sudo systemctl daemon-reload
sudo systemctl restart futures-price-update.timer
```

---

## 手动更新

### 基本用法

```bash
# 更新所有交易所
python manage.py update_futures_prices

# 仅更新Binance
python manage.py update_futures_prices --exchange binance

# 仅更新Bybit
python manage.py update_futures_prices --exchange bybit

# 仅更新Hyperliquid
python manage.py update_futures_prices --exchange hyperliquid
```

### 高级选项

```bash
# 测试运行（不保存到数据库）
python manage.py update_futures_prices --dry-run

# 静默模式（仅错误时输出）
python manage.py update_futures_prices --quiet

# 详细输出
python manage.py update_futures_prices --verbosity 2

# 组合使用
python manage.py update_futures_prices --exchange binance --dry-run
```

### 命令退出码

- `0`: 全部成功
- `1`: 有失败（用于cron监控）

---

## 日志查看

### 日志文件位置

```
logs/
├── futures_updates.log     # 合约更新详细日志（10MB × 10个文件）
├── general.log             # 一般应用日志（10MB × 5个文件）
├── cron.log                # Cron执行日志（如果使用cron）
└── systemd.log             # Systemd执行日志（如果使用systemd）
```

### 查看日志

```bash
# 查看最近的更新日志
tail -f logs/futures_updates.log

# 查看最近100行
tail -n 100 logs/futures_updates.log

# 查看cron执行日志
tail -f logs/cron.log

# 搜索错误
grep ERROR logs/futures_updates.log

# 搜索特定交易所
grep "binance" logs/futures_updates.log

# 查看今天的日志
grep "$(date +%Y-%m-%d)" logs/futures_updates.log
```

### 日志格式

```
[INFO] 2025-11-11 12:00:01 monitor.management.commands.update_futures_prices 开始定期更新任务 - 交易所: binance, hyperliquid, bybit
[INFO] 2025-11-11 12:00:01 monitor.services.futures_fetcher 正在更新 binance 数据...
[INFO] 2025-11-11 12:00:03 monitor.services.futures_fetcher binance 更新成功: 新增=0, 更新=535, 下线=0, 指标=535
[INFO] 2025-11-11 12:00:06 monitor.management.commands.update_futures_prices 更新完成 - 成功=3/3, 合约=1312, 新增=0, 更新=1312, 下线=0, 指标=1312, 耗时=5.23秒
```

### 日志轮转

日志文件会自动轮转：
- **futures_updates.log**: 每个文件最大10MB，保留10个文件
- **general.log**: 每个文件最大10MB，保留5个文件

---

## 故障排查

### 问题1：Cron任务没有执行

**检查cron是否在运行**：
```bash
# Mac
sudo launchctl list | grep cron

# Linux
systemctl status cron
```

**检查crontab配置**：
```bash
crontab -l
```

**查看cron日志**：
```bash
# Mac
tail -f /var/log/system.log | grep cron

# Linux
sudo tail -f /var/log/syslog | grep CRON
```

### 问题2：命令执行失败

**检查Python路径**：
```bash
which python  # 错误：使用系统Python
/path/to/venv/bin/python  # 正确：使用虚拟环境Python
```

**检查文件权限**：
```bash
ls -l manage.py  # 应该可读
ls -ld logs/     # 应该可写
```

**手动测试命令**：
```bash
cd /path/to/crypto_exchange_news_crawler
/path/to/venv/bin/python manage.py update_futures_prices --dry-run
```

### 问题3：数据库锁定

如果看到"database is locked"错误：

```bash
# 检查是否有其他进程在使用数据库
lsof | grep db.sqlite3

# 确保只有一个更新任务在运行
ps aux | grep update_futures_prices
```

**解决方案**：
1. 增加更新间隔（如从5分钟改为10分钟）
2. 使用PostgreSQL替代SQLite（生产环境推荐）

### 问题4：API请求失败

**检查网络连接**：
```bash
# 测试Binance API
curl -I https://fapi.binance.com/fapi/v1/exchangeInfo

# 测试Bybit API
curl -I https://api.bybit.com/v5/market/tickers

# 测试Hyperliquid API
curl -I https://api.hyperliquid.xyz/info
```

**检查日志**：
```bash
grep "ERROR" logs/futures_updates.log | tail -20
```

### 问题5：日志文件过大

**清理旧日志**：
```bash
# 手动清理
rm logs/*.log.*

# 或使用logrotate（Linux）
sudo logrotate /etc/logrotate.d/futures-monitor
```

---

## 性能优化

### 1. 调整更新频率

根据实际需求平衡实时性和API配额：

| 频率 | 每日调用次数 | 适用场景 |
|------|-------------|----------|
| 5分钟 | 288次/天 | 高频交易监控 |
| 10分钟 | 144次/天 | 一般监控（推荐） |
| 30分钟 | 48次/天 | 低频监控 |
| 1小时 | 24次/天 | 数据存档 |

### 2. 分散交易所更新时间

如果API限制严格，可以为不同交易所配置不同的更新时间：

```bash
# Binance：每10分钟的第0分钟
*/10 * * * * ... --exchange binance

# Bybit：每10分钟的第3分钟
3-59/10 * * * * ... --exchange bybit

# Hyperliquid：每10分钟的第6分钟
6-59/10 * * * * ... --exchange hyperliquid
```

### 3. 监控更新性能

查看平均更新时间：

```bash
grep "更新完成" logs/futures_updates.log | grep "耗时" | tail -20
```

---

## 监控和告警

### 1. 创建监控脚本

创建`scripts/check_updates.sh`：

```bash
#!/bin/bash

# 检查最后一次更新时间
LAST_UPDATE=$(tail -1 logs/futures_updates.log | grep "更新完成" | cut -d' ' -f2,3)

if [ -z "$LAST_UPDATE" ]; then
    echo "警告：未找到更新记录"
    exit 1
fi

# 计算时间差（需要安装dateutils）
MINUTES_AGO=$(( ($(date +%s) - $(date -d "$LAST_UPDATE" +%s)) / 60 ))

if [ $MINUTES_AGO -gt 15 ]; then
    echo "警告：上次更新时间超过15分钟（${MINUTES_AGO}分钟前）"
    exit 1
else
    echo "正常：上次更新在${MINUTES_AGO}分钟前"
    exit 0
fi
```

### 2. 配置告警

将监控脚本添加到cron：

```bash
# 每15分钟检查一次，如果异常则发送邮件
*/15 * * * * /path/to/scripts/check_updates.sh || echo "合约更新异常" | mail -s "告警" your@email.com
```

---

## 最佳实践

### 1. 开发环境

```bash
# 使用测试模式
python manage.py update_futures_prices --dry-run

# 定期手动更新
python manage.py update_futures_prices
```

### 2. 生产环境

```bash
# 使用Cron或Systemd
./scripts/setup_cron.sh

# 启用静默模式
# （在cron配置中已包含 --quiet 参数）

# 定期检查日志
tail -f logs/futures_updates.log

# 配置监控告警（见上文）
```

### 3. 数据库选择

- **开发/测试**: SQLite（简单快速）
- **生产环境**: PostgreSQL（高并发，无锁问题）

### 4. 备份策略

```bash
# 定期备份数据库
0 2 * * * sqlite3 /path/to/db.sqlite3 .dump > /path/to/backups/db_$(date +\%Y\%m\%d).sql

# 保留最近30天的备份
0 3 * * * find /path/to/backups/ -name "db_*.sql" -mtime +30 -delete
```

---

## 常见问题

### Q: 如何查看下次更新时间？

**Cron**:
```bash
crontab -l | grep futures_price_update
```

**Systemd**:
```bash
systemctl list-timers | grep futures
```

### Q: 如何临时停止更新？

**Cron**:
```bash
crontab -e  # 注释掉相关行（添加#）
```

**Systemd**:
```bash
sudo systemctl stop futures-price-update.timer
```

### Q: 如何验证配置是否正确？

```bash
# 1. 测试命令
python manage.py update_futures_prices --dry-run

# 2. 检查日志目录
ls -la logs/

# 3. 查看cron配置
crontab -l

# 4. 等待一个周期后检查日志
tail -f logs/cron.log
```

### Q: 多久清理一次日志？

日志会自动轮转，无需手动清理。如需手动清理：

```bash
# 删除旧的轮转日志
rm logs/*.log.*

# 清空当前日志（保留文件）
> logs/futures_updates.log
```

---

## 技术支持

遇到问题时，请提供以下信息：

1. 系统信息：`uname -a`
2. Python版本：`python --version`
3. 错误日志：最近20行 `tail -20 logs/futures_updates.log`
4. Cron配置：`crontab -l`

---

**相关文档**：
- [市场指标使用指南](MARKET_INDICATORS_GUIDE.md)
- [Django Admin管理指南](DJANGO_ADMIN_GUIDE.md)
- [项目README](../README.md)
