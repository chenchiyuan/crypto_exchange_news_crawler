# crypto_exchange_news_crawler Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-09

## Active Technologies
- Python 3.12 + Django 4.2.8, python-binance 1.0.19, pandas 2.0+, numpy 1.24+ (001-price-alert-monitor)
- SQLite (开发) / PostgreSQL 14+ (生产), 复用现有KlineData表存储K线数据 (001-price-alert-monitor)

- Python 3.8+ + Django 4.2.8, python-binance (币安SDK), websockets, pandas, numpy (002-auto-grid-trading)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.8+: Follow standard conventions

## Recent Changes
- 001-price-alert-monitor (v3.0.0): 推送格式优化 - 上涨/下跌分类、快速判断、速览提示，提供专业交易分析 (2025-12-09)
- 001-price-alert-monitor (v2.1.0): 波动率增强 - 切换为15m振幅累计，优先从数据库获取，按波动率排序推送 (2025-12-09)
- 001-price-alert-monitor (v2.0.0): 批量推送模式 - 一次检测汇总为一条推送消息，减少通知频率89-99% (2025-12-09)
- 001-price-alert-monitor (v1.0.0): 初始版本 - 5种价格触发规则、Django Admin支持、自动合约同步 (2025-12-08)
- 002-auto-grid-trading: Added Python 3.8+ + Django 4.2.8, python-binance (币安SDK), websockets, pandas, numpy

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
