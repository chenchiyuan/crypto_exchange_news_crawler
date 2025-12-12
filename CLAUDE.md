# crypto_exchange_news_crawler Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-12-09

## Active Technologies
- Python 3.12 + Django 4.2.8, python-binance 1.0.19, pandas 2.0+, numpy 1.24+ (001-price-alert-monitor, 001-006-short-grid)
- SQLite (开发) / PostgreSQL 14+ (生产), 复用现有KlineData表存储K线数据 (001-price-alert-monitor, 001-006-short-grid)
- NumPy实现的技术指标: RSI (Relative Strength Index), Bollinger Bands, Simple Moving Average (001-006-short-grid)
- VPA (Volume Price Analysis) 模式检测: 急刹车、金针探底、攻城锤、阳包阴 (001-006-short-grid)
- 多周期分析: 15m和1h K线独立检测，支持双周期确认 (001-006-short-grid)
- Python 3.12 (项目已使用) (008-marketcap-fdv-display)
- SQLite (开发) / PostgreSQL 14+ (生产) - 新增3个表: TokenMapping, MarketData, UpdateLog (008-marketcap-fdv-display)

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
- 008-marketcap-fdv-display: Added Python 3.12 (项目已使用)
- 001-006-short-grid (v1.0.0): 止盈止损智能监控规则 - 规则6(止盈信号)和规则7(止损信号)，支持4种VPA模式(急刹车/金针探底/攻城锤/阳包阴)+4种技术确认(RSI超卖/布林带回升/RSI超买加速/布林带突破扩张)，15m+1h双周期独立检测 (2025-12-12)
- 001-price-alert-monitor (v3.0.0): 推送格式优化 - 上涨/下跌分类、快速判断、速览提示，提供专业交易分析 (2025-12-09)

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
