"""
新币识别器服务
使用关键词匹配+正则表达式识别新币上线公告
"""
import re
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from django.utils import timezone

logger = logging.getLogger(__name__)


class ListingIdentifier:
    """新币上线识别器"""

    # 新币上线关键词(中英文)
    LISTING_KEYWORDS = [
        # 英文
        'new listing', 'will list', 'listed', 'listing',
        'new coin', 'new token', 'adds', 'add',
        'launch', 'launches', 'launching',
        # 中文
        '上线', '上币', '新币', '开放交易',
    ]

    # 上线类型关键词
    SPOT_KEYWORDS = ['spot', 'spot trading', '现货']
    FUTURES_KEYWORDS = [
        'futures', 'perpetual', 'usdⓢ-m', 'usdt-margined',
        'usdt perpetual', 'coin-margined',
        '合约', '永续', '永续合约'
    ]

    # 币种代码正则(1-10个大写字母/数字)
    COIN_PATTERN = re.compile(r'\b([A-Z][A-Z0-9]{0,9})\b')

    # 排除的常见词(避免误识别)
    EXCLUDE_WORDS = {
        'USDT', 'USD', 'BTC', 'ETH', 'BNB', 'BUSD',
        'NEW', 'SPOT', 'FUTURES', 'API', 'NFT', 'VIP',
        'KYC', 'AML', 'UTC', 'FAQ', 'ANNOUNCEMENT'
    }

    def identify(self, announcement) -> Optional[Dict]:
        """
        识别公告是否为新币上线

        Args:
            announcement: Announcement模型实例

        Returns:
            识别结果字典,如果不是新币上线返回None
            {
                'is_listing': True,
                'coin_symbol': 'PEPE',
                'coin_name': '',
                'listing_type': 'spot',  # 'spot' / 'futures' / 'both'
                'confidence': 0.95,      # 0.0-1.0
            }
        """
        title = announcement.title.lower()
        content = announcement.description.lower() if announcement.description else ''
        text = f"{title} {content}"

        # 1. 检查是否包含新币上线关键词
        if not self._contains_listing_keywords(text):
            return None

        # 2. 提取币种代码
        coin_symbol = self._extract_coin_symbol(announcement.title)
        if not coin_symbol:
            logger.debug(f"未能提取币种代码: {announcement.title}")
            return None

        # 3. 判断上线类型
        listing_type = self._determine_listing_type(text)

        # 4. 计算置信度
        confidence = self._calculate_confidence(text, coin_symbol)

        return {
            'is_listing': True,
            'coin_symbol': coin_symbol,
            'coin_name': '',  # 可选:通过CoinGecko API查询
            'listing_type': listing_type,
            'confidence': confidence
        }

    def _contains_listing_keywords(self, text: str) -> bool:
        """检查是否包含新币上线关键词"""
        return any(keyword in text for keyword in self.LISTING_KEYWORDS)

    def _extract_coin_symbol(self, title: str) -> Optional[str]:
        """
        从标题提取币种代码

        示例:
        - "Binance Will List Pepe (PEPE)" -> "PEPE"
        - "OKX Lists TRUMP Token" -> "TRUMP"
        """
        # 优先提取括号内的代码
        match = re.search(r'\(([A-Z][A-Z0-9]{0,9})\)', title)
        if match:
            symbol = match.group(1)
            if symbol not in self.EXCLUDE_WORDS:
                return symbol

        # 否则提取第一个大写词
        matches = self.COIN_PATTERN.findall(title)
        for symbol in matches:
            if symbol not in self.EXCLUDE_WORDS:
                return symbol

        return None

    def _determine_listing_type(self, text: str) -> str:
        """
        判断上线类型

        Returns:
            'spot' / 'futures' / 'both'
        """
        has_spot = any(kw in text for kw in self.SPOT_KEYWORDS)
        has_futures = any(kw in text for kw in self.FUTURES_KEYWORDS)

        if has_spot and has_futures:
            return 'both'
        elif has_futures:
            return 'futures'
        else:
            return 'spot'  # 默认现货

    def _calculate_confidence(self, text: str, coin_symbol: str) -> float:
        """
        计算识别置信度

        规则:
        - 标题包含"listing" + 币种代码: 0.95
        - 标题包含"list" + 币种代码: 0.90
        - 仅内容包含: 0.70
        - 其他: 0.60
        """
        coin_lower = coin_symbol.lower()

        if 'listing' in text and coin_lower in text:
            return 0.95
        elif 'list' in text and coin_lower in text:
            return 0.90
        elif coin_lower in text:
            return 0.70
        else:
            return 0.60

    def is_duplicate(self, coin_symbol: str, exchange_id: int, listing_type: str,
                    hours: int = 24) -> bool:
        """
        检查是否为重复识别(24小时内)

        Args:
            coin_symbol: 币种代码
            exchange_id: 交易所ID
            listing_type: 上线类型
            hours: 时间窗口(小时)

        Returns:
            True=重复, False=非重复
        """
        from monitor.models import Listing, Announcement

        cutoff_time = timezone.now() - timedelta(hours=hours)

        existing = Listing.objects.filter(
            coin_symbol=coin_symbol,
            listing_type=listing_type,
            announcement__exchange_id=exchange_id,
            identified_at__gte=cutoff_time
        ).exists()

        return existing

    def save_listing(self, announcement, identification_result: Dict):
        """
        保存识别出的新币上线记录

        Args:
            announcement: Announcement实例
            identification_result: identify()返回的识别结果
        """
        from monitor.models import Listing

        try:
            # 检查去重
            if self.is_duplicate(
                identification_result['coin_symbol'],
                announcement.exchange_id,
                identification_result['listing_type']
            ):
                logger.info(f"跳过重复识别: {identification_result['coin_symbol']} "
                          f"on {announcement.exchange.code}")
                return None

            # 根据置信度设置状态
            confidence = identification_result['confidence']
            if confidence >= 0.5:
                status = Listing.CONFIRMED
            else:
                status = Listing.PENDING_REVIEW

            # 创建Listing记录
            listing = Listing.objects.create(
                coin_symbol=identification_result['coin_symbol'],
                coin_name=identification_result['coin_name'],
                listing_type=identification_result['listing_type'],
                announcement=announcement,
                confidence=confidence,
                status=status,
                identified_at=timezone.now()
            )

            # 标记公告已处理
            announcement.processed = True
            announcement.save()

            logger.info(f"新币上线识别成功: {listing.coin_symbol} "
                       f"on {announcement.exchange.name} "
                       f"(置信度: {confidence:.2f}, 状态: {status})")

            return listing

        except Exception as e:
            logger.error(f"保存新币上线记录失败: {str(e)}", exc_info=True)
            return None

    def process_announcements(self, exchange_code: Optional[str] = None) -> int:
        """
        批量处理未处理的公告

        Args:
            exchange_code: 指定交易所代码,None=处理所有

        Returns:
            识别出的新币上线数量
        """
        from monitor.models import Announcement, Exchange

        # 构建查询
        query = Announcement.objects.filter(processed=False)
        if exchange_code:
            try:
                exchange = Exchange.objects.get(code=exchange_code)
                query = query.filter(exchange=exchange)
            except Exchange.DoesNotExist:
                logger.error(f"交易所不存在: {exchange_code}")
                return 0

        announcements = query.order_by('-announced_at')[:100]  # 限制100条
        identified_count = 0

        for announcement in announcements:
            result = self.identify(announcement)
            if result and result['is_listing']:
                listing = self.save_listing(announcement, result)
                if listing:
                    identified_count += 1
            else:
                # 标记为已处理(非新币上线)
                announcement.processed = True
                announcement.save()

        logger.info(f"处理完成: 识别出 {identified_count} 个新币上线")
        return identified_count
