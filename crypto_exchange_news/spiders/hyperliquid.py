import scrapy
import json
import time
from datetime import datetime


class HyperliquidSpider(scrapy.Spider):
    """
    Hyperliquid公告爬虫
    直接使用API获取公告数据，无需Playwright
    """
    name = "hyperliquid"

    # API URL
    api_url = "https://dzjnlsk4rxci0.cloudfront.net/mainnet/entries.json"
    base_url = "https://app.hyperliquid.xyz/announcements"

    def start_requests(self):
        """直接请求JSON API"""
        yield scrapy.Request(
            self.api_url,
            callback=self.parse,
            errback=self.handle_error
        )

    def parse(self, response):
        """解析API返回的JSON数据"""
        try:
            data = json.loads(response.text)
            entries = data.get('entries', [])

            self.logger.info(f"成功获取 {len(entries)} 条Hyperliquid公告")

            for entry in entries:
                # 解析时间戳
                created_at_str = entry.get('createdAt', '')
                try:
                    dt = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    announced_at_timestamp = int(dt.timestamp())
                except Exception as e:
                    self.logger.warning(f"时间解析失败: {created_at_str}, 使用当前时间")
                    announced_at_timestamp = int(time.time())

                # 生成唯一ID
                uuid = entry.get('uuid', '')
                news_id = f"hyperliquid_{uuid}"

                # 构建详情URL
                url = f"{self.base_url}?uuid={uuid}"

                # 构建标题
                title = entry.get('title', '')
                category = entry.get('category', 'Announcement')

                # 描述
                preview = entry.get('preview', '')

                # 返回数据
                item = {
                    'news_id': news_id,
                    'title': title,
                    'desc': preview,
                    'url': url,
                    'category_str': category,
                    'exchange': self.name,
                    'announced_at_timestamp': announced_at_timestamp,
                    'timestamp': int(time.time()),
                }

                yield item

        except json.JSONDecodeError as e:
            self.logger.error(f"JSON解析失败: {str(e)}")
        except Exception as e:
            self.logger.error(f"解析公告数据失败: {str(e)}", exc_info=True)

    def handle_error(self, failure):
        """错误处理"""
        self.logger.error(f"请求失败: {failure.value}")
