# 快速使用指南

## 🚀 一键获取所有交易所公告

```bash
# 方式1：Shell脚本（推荐）
./scripts/fetch_announcements.sh          # 获取最近24小时
./scripts/fetch_announcements.sh 1        # 获取最近1小时
./scripts/fetch_announcements.sh 48       # 获取最近48小时

# 方式2：Python命令
python manage.py fetch_all_announcements --hours 24
```

## 📋 所有可用命令

```bash
# 1. 初始化交易所数据（首次运行）
python manage.py init_exchanges

# 2. 批量获取所有交易所公告
python manage.py fetch_all_announcements --hours 24

# 3. 获取单个交易所公告
python manage.py fetch_announcements --exchange binance --hours 24

# 4. 识别新币上线
python manage.py identify_listings --exchange binance --show-details

# 5. 测试Webhook通知
python manage.py test_webhook --url YOUR_WEBHOOK_URL --test-only
```

## ⏰ 设置定时任务

```bash
# 编辑crontab
crontab -e

# 每小时执行一次，获取最近2小时的公告
0 * * * * cd /path/to/crypto_exchange_news_crawler && ./scripts/fetch_announcements.sh 2 >> logs/fetch.log 2>&1
```

## 📊 查看数据

```bash
# 查看数据库中的公告统计
sqlite3 db.sqlite3 "
SELECT
  e.name,
  COUNT(a.id) as count
FROM announcements a
JOIN exchanges e ON a.exchange_id = e.id
GROUP BY e.name;
"
```

## 📖 详细文档

查看 [docs/batch_fetch_guide.md](docs/batch_fetch_guide.md) 获取完整使用说明。
