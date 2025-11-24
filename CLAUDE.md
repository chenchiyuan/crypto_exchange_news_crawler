# crypto_exchange_news_crawler Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-06

## Active Technologies
- Python 3.8+ (001-listing-monitor)
- PostgreSQL 14+ (生产推荐) 或 SQLite (开发测试) (001-listing-monitor)
- Python 3.8+ (项目现有标准) (001-twitter-app-integration)
- SQLite (开发) / PostgreSQL 14+ (生产) - 项目现有配置 (001-twitter-app-integration)
- Python 3.12 (项目现有) + Django 4.2.8, requests (调用币安API) (003-vp-squeeze-analysis)
- SQLite (开发) - 新建VPSqueezeResult模型 (003-vp-squeeze-analysis)

- Python 3.7+ (001-listing-monitor)

## Project Structure

```text
src/
tests/
```

## Commands

cd src [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] pytest [ONLY COMMANDS FOR ACTIVE TECHNOLOGIES][ONLY COMMANDS FOR ACTIVE TECHNOLOGIES] ruff check .

## Code Style

Python 3.7+: Follow standard conventions

## Recent Changes
- 003-vp-squeeze-analysis: Added Python 3.12 (项目现有) + Django 4.2.8, requests (调用币安API)
- 001-twitter-app-integration: Added Python 3.8+ (项目现有标准)
- 001-listing-monitor: Added Python 3.8+


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
