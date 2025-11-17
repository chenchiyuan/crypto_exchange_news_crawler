"""
爬虫调用服务
调用现有Scrapy爬虫获取交易所公告
"""
import subprocess
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path
from django.utils import timezone

logger = logging.getLogger(__name__)


class CrawlerService:
    """爬虫调用服务,集成现有Scrapy爬虫"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.scrapy_project = self.project_root / 'crypto_exchange_news'

    def fetch_announcements(self, exchange_code: str, max_pages: int = 2,
                           hours: Optional[int] = None) -> List[Dict]:
        """
        调用Scrapy爬虫获取指定交易所的公告

        智能增量获取：只返回指定时间范围内的公告

        Args:
            exchange_code: 交易所代码(如'binance', 'bybit', 'bitget')
            max_pages: 最大爬取页数,默认2页
            hours: 只获取最近N小时的公告,None=获取全部

        Returns:
            公告列表,每个公告包含:
            - news_id: 公告唯一ID
            - title: 标题
            - desc: 描述
            - url: 详情URL
            - announced_at_timestamp: 发布时间戳
            - category_str: 分类
        """
        if hours:
            logger.info(f"开始获取 {exchange_code} 交易所最近{hours}小时的公告,最大页数: {max_pages}")
        else:
            logger.info(f"开始获取 {exchange_code} 交易所公告,最大页数: {max_pages}")

        # 映射交易所代码到爬虫名称
        spider_map = {
            'binance': 'binance',
            'bybit': 'bybit',
            'bitget': 'bitget',
            'hyperliquid': 'hyperliquid',
        }

        spider_name = spider_map.get(exchange_code.lower())
        if not spider_name:
            logger.error(f"不支持的交易所: {exchange_code}")
            return []

        # 调用Scrapy爬虫(使用JSON输出)
        output_file = self.scrapy_project / f'scrapy_output_{exchange_code}.json'

        # 执行前删除旧文件（避免追加导致的JSON格式错误）
        if output_file.exists():
            logger.debug(f"删除旧输出文件: {output_file}")
            output_file.unlink()

        try:
            cmd = [
                sys.executable, '-m', 'scrapy', 'crawl', spider_name,
                '-s', f'MAX_PAGE={max_pages}',
                '-O', str(output_file)  # 使用 -O（大写）强制覆盖模式
            ]

            # 执行爬虫
            result = subprocess.run(
                cmd,
                cwd=str(self.scrapy_project),
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )

            if result.returncode != 0:
                logger.error(f"Scrapy爬虫执行失败: {result.stderr}")
                return []

            # 读取爬取结果
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    announcements = json.load(f)

                total_count = len(announcements)

                # 时间过滤：只保留指定时间范围内的公告
                if hours:
                    cutoff_timestamp = (timezone.now() - timedelta(hours=hours)).timestamp()
                    filtered_announcements = []

                    # 按时间戳降序排序（最新的在前）
                    announcements.sort(key=lambda x: x.get('announced_at_timestamp', 0), reverse=True)

                    for ann in announcements:
                        ann_timestamp = ann.get('announced_at_timestamp', 0)
                        if ann_timestamp >= cutoff_timestamp:
                            filtered_announcements.append(ann)
                        else:
                            # 已经遇到超出时间范围的公告，后续的更旧，直接退出
                            break

                    filtered_count = len(filtered_announcements)
                    skipped_count = total_count - filtered_count

                    logger.info(f"成功获取 {total_count} 条公告，过滤后保留 {filtered_count} 条最近{hours}小时的公告（跳过 {skipped_count} 条旧公告）")
                    return filtered_announcements
                else:
                    logger.info(f"成功获取 {total_count} 条公告")
                    return announcements
            else:
                logger.warning(f"未找到爬取结果文件: {output_file}")
                return []

        except subprocess.TimeoutExpired:
            logger.error(f"爬虫执行超时(5分钟)")
            return []
        except Exception as e:
            logger.error(f"爬虫调用失败: {str(e)}", exc_info=True)
            return []
        finally:
            # 无论成功或失败，都清理输出文件
            if output_file.exists():
                logger.debug(f"清理输出文件: {output_file}")
                output_file.unlink()

    def parse_announcement_date(self, date_str: str) -> Optional[datetime]:
        """
        解析公告发布时间

        Args:
            date_str: 时间字符串(多种格式)

        Returns:
            datetime对象,解析失败返回None
        """
        # 支持多种时间格式
        formats = [
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%Y/%m/%d %H:%M:%S',
            '%Y/%m/%d',
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.warning(f"无法解析时间字符串: {date_str}")
        return None

    def save_announcements_to_db(self, exchange_code: str, announcements: List[Dict]):
        """
        将爬取的公告保存到数据库

        Args:
            exchange_code: 交易所代码
            announcements: 公告列表
        """
        from monitor.models import Exchange, Announcement

        try:
            # 获取交易所对象
            exchange = Exchange.objects.get(code=exchange_code)
        except Exchange.DoesNotExist:
            logger.error(f"交易所不存在: {exchange_code}")
            return

        saved_count = 0
        skipped_count = 0
        invalid_count = 0  # 无效时间戳的公告

        for ann_data in announcements:
            try:
                # 解析发布时间(优先使用时间戳)
                announced_at = None

                if 'announced_at_timestamp' in ann_data and ann_data['announced_at_timestamp']:
                    # 从时间戳转换为timezone-aware datetime
                    try:
                        announced_at = timezone.make_aware(
                            datetime.fromtimestamp(ann_data['announced_at_timestamp'])
                        )
                    except (ValueError, OSError) as e:
                        logger.warning(f"时间戳转换失败: {ann_data['announced_at_timestamp']}, 错误: {str(e)}")

                elif 'date' in ann_data and ann_data['date']:
                    # 从字符串解析
                    announced_at = self.parse_announcement_date(ann_data['date'])
                    if announced_at:
                        # 确保是timezone-aware
                        if timezone.is_naive(announced_at):
                            announced_at = timezone.make_aware(announced_at)

                # 如果没有有效的发布时间，跳过此公告
                if announced_at is None:
                    logger.warning(f"跳过无发布时间的公告: {ann_data.get('title', 'Unknown')} (news_id: {ann_data.get('news_id', 'Unknown')})")
                    invalid_count += 1
                    continue

                # 创建或更新公告
                announcement, created = Announcement.objects.get_or_create(
                    news_id=ann_data.get('news_id', ''),
                    defaults={
                        'title': ann_data.get('title', ''),
                        'description': ann_data.get('desc', ''),
                        'url': ann_data.get('url', ''),
                        'announced_at': announced_at,
                        'category': ann_data.get('category_str', ann_data.get('category', '')),
                        'exchange': exchange,
                        'processed': False,
                    }
                )

                if created:
                    saved_count += 1
                else:
                    skipped_count += 1

            except Exception as e:
                logger.error(f"保存公告失败: {str(e)}", exc_info=True)
                continue

        # 构建详细的日志信息
        log_parts = [f"新增 {saved_count} 条"]
        if skipped_count > 0:
            log_parts.append(f"跳过重复 {skipped_count} 条")
        if invalid_count > 0:
            log_parts.append(f"跳过无效时间 {invalid_count} 条")

        logger.info(f"保存完成: {', '.join(log_parts)}")
