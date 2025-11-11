# Crypto Exchange News Crawler 🚀

A powerful and easy-to-use Python package for scraping cryptocurrency exchange announcements from major exchanges, with advanced futures market monitoring capabilities.

## 🎯 Features

### 公告爬取 (Announcement Crawler)
- **Multi-Exchange Support**: Scrape from 12 major crypto exchanges
- **Multiple Output Formats**: JSON, CSV, and XML support
- **Structured Data**: Clean, standardized output format
- **Rate Limiting**: Built-in delays to respect exchange servers
- **Extensible**: Easy to add new exchanges

### 合约监控 (Futures Market Monitor) 🆕
- **实时市场指标**: 追踪8个核心市场指标
  - 持仓量 (Open Interest)
  - 24小时交易量 (24H Volume)
  - 资金费率 (Funding Rate)
  - 年化费率 (Annual Funding Rate)
  - 下次结算时间 (Next Funding Time)
  - 费率上下限 (Funding Rate Cap/Floor)
  - 资金费率间隔 (Funding Interval)
- **多交易所支持**: Binance, Bybit, Hyperliquid
- **高性能获取**: 1,312个合约 < 4秒
- **Django Admin管理**: 可视化展示和管理
- **新币上线通知**: 自动检测并推送

详细文档请查看 [市场指标使用指南](docs/MARKET_INDICATORS_GUIDE.md)

## 📦 Installation Options

### Option 1: Direct Usage

```bash
git clone https://github.com/lowweihong/crypto-exchange-news-crawler.git
cd crypto-exchange-news-crawler
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install

scrapy crawl bybit -o output.json
```

### Option 2: Install from PyPI

```bash
pip install crypto-exchange-news-crawler
playwright install

## directly use proxy and uncomment DOWNLOADER_MIDDLEWARES
crypto-news crawl binance -o binance.json

crypto-news crawl bybit -s DOWNLOADER_MIDDLEWARES='{"crypto_exchange_news.middlewares.MyProxyMiddleware": 610}' -s PROXY_LIST="http://proxy1:port,http://proxy2:port"
```

### Supported Exchanges

| Exchange  | Status |
|-----------|--------|
| Bybit     | ✅ |
| Binance   | ✅ |
| OKX       | ✅ |
| Bitget    | ✅ |
| BingX     | ✅ |
| Kraken    | ✅ |
| Bitfinex  | ✅ |
| XT        | ✅ |
| Crypto.com| ✅ |
| MEXC      | ✅ |
| Deepcoin  | ✅ |
| Kucoin    | ✅ |
| Upbit     | ✅ |

```
Available options : ["bybit", "binance", "okx", "bitget", "bitfinex", "xt", "bingx", 'kraken', 'cryptocom', 'mexc', 'deepcoin', 'kucoin', 'upbit']
```
#

## 📊 Output Format

Each scraped announcement includes:

```json
{
    "news_id": "unique_identifier",
    "title": "Announcement title",
    "desc": "Announcement description",
    "url": "Full URL to announcement",
    "category_str": "Category (e.g., latest_activities, new_crypto)",
    "exchange": "Exchange name",
    "announced_at_timestamp": 1749235200,
    "timestamp": 1749232733
}
```

## ⚙️ Configuration

Key settings in `settings.py`:

- `MAX_PAGE`: Maximum number of pages to crawl (default: 2)
- `DOWNLOAD_DELAY`: Delay between requests in seconds (default: 3)
- `CONCURRENT_REQUESTS`: Number of concurrent requests (default: 8)
- `USER_AGENT`: List of user agents for rotation
- `PROXY_LIST`: Fill the list with your proxy list and remember also to open uncomment the DOWNLOADER_MIDDLEWARES part to use the proxy middleware
- `PLAYWRIGHT_LAUNCH_OPTIONS`: Browser configuration for Playwright spiders

### Custom Settings

You can override settings from the command line:

```bash
scrapy crawl bitget -s MAX_PAGE=5 -s DOWNLOAD_DELAY=2
```

## 🔧 Technical Requirements

- Python 3.7+
- Scrapy 2.11.0+
- Playwright (for Bitget spider)
- Chromium browser (automatically installed with Playwright)

## 🌐 Exchange URLs

Direct links to announcement pages:

| Exchange | Announcement URL |
|----------|------------------|
| **Binance** | https://www.binance.com/en/support/announcement |
| **OKX** | https://www.okx.com/help/category/announcements |
| **Bybit** | https://announcements.bybit.com/en/?category=&page=1 |
| **Bitget** | https://www.bitget.com/support/sections/12508313443483 |
| **BingX** | https://bingx.com/en/support/notice-center/ |
| **Kraken** | https://blog.kraken.com/category/product |
| **XT** | https://xtsupport.zendesk.com/hc/en-us/categories/10304894611993-Important-Announcements |
| **Bitfinex** | https://www.bitfinex.com/posts/ |
| **Crypto.com** | https://crypto.com/exchange/announcements |
| **MEXC** | https://www.mexc.com/support/categories/360000254192 |
| **Deepcoin** | https://support.deepcoin.online/hc/en-001/categories/360003875752-Important-Announcements |
| **Kucoin** | https://www.kucoin.com/announcement |
| **Upbit** | https://sg.upbit.com/service_center/notice |

## 📈 Futures Market Monitor Quick Start

### 获取合约市场指标

```python
# 获取Binance合约及市场指标
python manage.py fetch_futures --exchange binance

# 监控所有交易所的新币上线
python manage.py monitor_futures --hours 24

# 查看Django Admin后台
python manage.py runserver
# 访问 http://localhost:8000/admin
```

### 性能指标

- **处理速度**: 1,312个合约 < 4秒
- **支持交易所**: Binance (535合约), Bybit (557合约), Hyperliquid (220合约)
- **年化费率计算**: 自动计算并显示
- **Admin后台**: 彩色标记、千分位格式化、实时更新

### 市场指标包含

| 指标 | 说明 | Admin显示 |
|------|------|-----------|
| 持仓量 | Open Interest | 千分位格式化 |
| 24H交易量 | 24 Hour Volume | 蓝色高亮 |
| 资金费率 | Current Funding Rate | 正费率绿色/负费率红色 |
| 年化费率 | Annual Funding Rate | 根据数值颜色标记 |
| 下次结算 | Next Funding Time | 倒计时显示 |
| 费率上下限 | Funding Rate Cap/Floor | - |
| 费率间隔 | Funding Interval Hours | - |

完整使用文档请查看：[市场指标使用指南](docs/MARKET_INDICATORS_GUIDE.md)

## ⚖️ Legal & Ethical Usage

This crawler is designed for educational and research purposes. Please ensure you comply with:

- Applicable data protection laws
- Fair use guidelines

Always use the crawler responsibly and consider the impact on the target servers.

## 🤝 Contributing

Contributions welcome! Areas for improvement:
- Add support for more exchanges (Huobi, Gateio, etc.)
- Implement real-time WebSocket feeds
- Add telegram/discord notification integrations
- Improve data parsing and categorization

## Support

For issues, questions, or contributions, please create an issue in the repository.