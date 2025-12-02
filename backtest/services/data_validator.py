"""
数据验证服务
Data Validator Service
"""
import logging
from datetime import timedelta
from typing import List, Tuple
from django.db.models import QuerySet

from backtest.models import KLine

logger = logging.getLogger(__name__)


class DataValidator:
    """数据验证器"""

    def validate_klines(
        self,
        symbol: str,
        interval: str
    ) -> Tuple[bool, List[str]]:
        """
        验证K线数据质量

        Args:
            symbol: 交易对
            interval: 时间周期

        Returns:
            (is_valid, errors): (是否有效, 错误列表)
        """
        errors = []

        # 获取数据
        klines = KLine.objects.filter(
            symbol=symbol,
            interval=interval
        ).order_by('open_time')

        if not klines.exists():
            errors.append(f"没有找到数据: {symbol} {interval}")
            return False, errors

        logger.info(f"开始验证数据: {symbol} {interval}, 共{klines.count()}条")

        # 1. 检查价格合理性
        price_errors = self._check_price_validity(klines)
        errors.extend(price_errors)

        # 2. 检查时间连续性
        gap_errors = self._check_time_gaps(klines, interval)
        errors.extend(gap_errors)

        # 3. 检查成交量异常
        volume_errors = self._check_volume_anomalies(klines)
        errors.extend(volume_errors)

        is_valid = len(errors) == 0

        if is_valid:
            logger.info(f"数据验证通过: {symbol} {interval}")
        else:
            logger.warning(f"数据验证失败: {symbol} {interval}, 错误数={len(errors)}")

        return is_valid, errors

    def _check_price_validity(self, klines: QuerySet) -> List[str]:
        """检查价格合理性"""
        errors = []

        for kline in klines:
            # high >= low
            if kline.high_price < kline.low_price:
                errors.append(
                    f"{kline.open_time}: high({kline.high_price}) < low({kline.low_price})"
                )

            # high >= open, close
            if (kline.high_price < kline.open_price or
                kline.high_price < kline.close_price):
                errors.append(
                    f"{kline.open_time}: high价格异常"
                )

            # low <= open, close
            if (kline.low_price > kline.open_price or
                kline.low_price > kline.close_price):
                errors.append(
                    f"{kline.open_time}: low价格异常"
                )

        return errors

    def _check_time_gaps(
        self,
        klines: QuerySet,
        interval: str
    ) -> List[str]:
        """检查时间缺口"""
        errors = []

        # 计算时间间隔
        interval_map = {
            '1h': timedelta(hours=1),
            '4h': timedelta(hours=4),
            '1d': timedelta(days=1),
        }
        expected_delta = interval_map.get(interval)

        if not expected_delta:
            return errors

        klines_list = list(klines)

        for i in range(1, len(klines_list)):
            prev_kline = klines_list[i-1]
            curr_kline = klines_list[i]

            actual_delta = curr_kline.open_time - prev_kline.open_time

            # 允许5分钟误差
            if abs(actual_delta - expected_delta) > timedelta(minutes=5):
                errors.append(
                    f"时间缺口: {prev_kline.open_time} -> {curr_kline.open_time}, "
                    f"间隔={actual_delta}"
                )

        return errors

    def _check_volume_anomalies(self, klines: QuerySet) -> List[str]:
        """检查成交量异常"""
        errors = []

        for kline in klines:
            # 成交量不能为负
            if kline.volume < 0:
                errors.append(f"{kline.open_time}: 成交量为负({kline.volume})")

            # quote_volume应该大致等于 (open+close)/2 * volume
            # 这里只做基本检查
            if kline.quote_volume < 0:
                errors.append(f"{kline.open_time}: 成交额为负({kline.quote_volume})")

        return errors
