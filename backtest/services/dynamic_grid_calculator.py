"""
动态网格计算器
基于FourPeaksAnalyzer的成交量分析动态计算网格层级
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional, List

from vp_squeeze.services.four_peaks_analyzer import (
    aggregate_volume_heatmap,
    find_volume_clusters_by_window,
    select_four_clusters,
    select_flexible_clusters,
    calculate_ma25,
    adjust_price_with_ma25
)
from vp_squeeze.services.indicators.volume_profile import calculate_volume_profile
from vp_squeeze.services.multi_timeframe_analyzer import (
    calculate_enhanced_hvn,
    TimeframeAnalysis
)
from vp_squeeze.dto import KLineData
from backtest.models import KLine

logger = logging.getLogger(__name__)


@dataclass
class GridLevelInfo:
    """单个网格层级信息"""
    price: float  # 中心价格
    zone_low: float  # 区间下界
    zone_high: float  # 区间上界


@dataclass
class GridLevels:
    """动态网格层级（支持1-4层）"""
    resistance_2: Optional[GridLevelInfo]
    resistance_1: Optional[GridLevelInfo]
    support_1: Optional[GridLevelInfo]
    support_2: Optional[GridLevelInfo]
    timestamp: datetime
    analysis_quality: float  # 0-1，表示分析质量

    def has_support(self) -> bool:
        """是否有至少1个支撑位"""
        return self.support_1 is not None or self.support_2 is not None

    def has_resistance(self) -> bool:
        """是否有至少1个压力位"""
        return self.resistance_1 is not None or self.resistance_2 is not None

    def support_count(self) -> int:
        """支撑位数量"""
        count = 0
        if self.support_1 is not None:
            count += 1
        if self.support_2 is not None:
            count += 1
        return count

    def resistance_count(self) -> int:
        """压力位数量"""
        count = 0
        if self.resistance_1 is not None:
            count += 1
        if self.resistance_2 is not None:
            count += 1
        return count


class DynamicGridCalculator:
    """动态网格计算器 - 集成FourPeaksAnalyzer"""

    def __init__(
        self,
        symbol: str,
        lookback_periods: Optional[Dict[str, int]] = None,
        price_deviation_pct: float = 0.10
    ):
        """
        初始化动态网格计算器

        Args:
            symbol: 交易对
            lookback_periods: 各周期回看窗口
                {'4h': 180, '1h': 240, '15m': 288}
            price_deviation_pct: 价格偏离百分比（默认10%，即±10%范围内寻找支撑压力）
        """
        self.symbol = symbol
        self.lookback_periods = lookback_periods or {
            '4h': 180,  # 30天
            '1h': 240,  # 10天
            '15m': 288  # 3天
        }
        self.timeframes = ['4h', '1h', '15m']
        self.price_deviation_pct = price_deviation_pct

    def calculate_grid_levels(
        self,
        current_time: datetime
    ) -> Optional[GridLevels]:
        """
        计算当前时间点的动态网格层级

        Args:
            current_time: 当前K线时间

        Returns:
            GridLevels 或 None（数据不足时）
        """
        try:
            # 1. 执行多周期分析（基于数据库历史数据）
            analyses = self._analyze_multi_timeframe_backtest(current_time)

            if not analyses:
                logger.warning(f"多周期分析失败: {current_time}")
                return None

            # 2. 获取当前价格
            current_price = self._get_current_price(current_time)
            if current_price is None:
                return None

            # 3. 聚合成交量热力图
            heatmap = aggregate_volume_heatmap(
                analyses,
                weights={'4h': 1.5, '1h': 1.2, '15m': 1.0}
            )

            if not heatmap:
                logger.warning(f"成交量热力图为空: {current_time}")
                return None

            # 4. 识别成交量集中区间（在±price_deviation_pct范围内）
            clusters = find_volume_clusters_by_window(
                heatmap=heatmap,
                current_price=current_price,
                window_size=5,
                price_range_pct=self.price_deviation_pct
            )

            if len(clusters) == 0:
                logger.warning(f"无法识别任何成交量集中区间: {current_time}")
                return None

            # 5. 灵活选择区间（0-4个，不强制要求4个）
            selected_below, selected_above = select_flexible_clusters(
                clusters=clusters,
                current_price=current_price,
                min_distance_pct=0.05
            )

            # ⭐⭐⭐ 关键：不再强制要求上下各2个，至少有1个即可
            total_selected = len(selected_below) + len(selected_above)
            if total_selected == 0:
                logger.warning(
                    f"筛选后无可用区间: "
                    f"下方={len(selected_below)}, 上方={len(selected_above)}"
                )
                return None

            # 6. 计算MA25
            ma25 = calculate_ma25(analyses[0].klines) if analyses else None

            # 7. 构建网格层级（支持None值）
            # 支撑位
            support_2 = None
            support_1 = None

            if len(selected_below) == 2:
                # 标准情况：2个支撑位
                support_2 = self._create_grid_level(selected_below[0], ma25, False)
                support_1 = self._create_grid_level(selected_below[1], ma25, False)
            elif len(selected_below) == 1:
                # ⚠️ 边界情况：只有1个支撑位，作为support_1
                support_1 = self._create_grid_level(selected_below[0], ma25, False)
                logger.warning(
                    f"⚠️ 支撑位不足 @ {current_time.strftime('%m-%d %H:%M')}: "
                    f"只识别到1个支撑位（作为support_1），support_2缺失"
                )

            # 压力位
            resistance_2 = None
            resistance_1 = None

            if len(selected_above) == 2:
                # 标准情况：2个压力位
                resistance_1 = self._create_grid_level(selected_above[0], ma25, True)
                resistance_2 = self._create_grid_level(selected_above[1], ma25, True)
            elif len(selected_above) == 1:
                # ⚠️ 边界情况：只有1个压力位，作为resistance_1
                resistance_1 = self._create_grid_level(selected_above[0], ma25, True)
                logger.warning(
                    f"⚠️ 压力位不足 @ {current_time.strftime('%m-%d %H:%M')}: "
                    f"只识别到1个压力位（作为resistance_1），resistance_2缺失"
                )

            # 8. 计算分析质量（基于成交量强度）
            all_selected = selected_below + selected_above
            analysis_quality = self._calculate_quality(all_selected) if all_selected else 0.0

            # 9. 创建GridLevels
            grid_levels = GridLevels(
                resistance_2=resistance_2,
                resistance_1=resistance_1,
                support_1=support_1,
                support_2=support_2,
                timestamp=current_time,
                analysis_quality=analysis_quality
            )

            # 10. 日志记录（区分标准情况和边界情况）
            if len(selected_below) == 2 and len(selected_above) == 2:
                # 标准情况
                logger.info(
                    f"✓ 网格计算成功 @ {current_time.strftime('%m-%d %H:%M')}: "
                    f"价格={current_price:.2f} (±{self.price_deviation_pct*100:.0f}%范围) | "
                    f"支撑位=2个, 压力位=2个"
                )
            else:
                # 边界情况
                logger.warning(
                    f"⚠️ 网格计算(边界) @ {current_time.strftime('%m-%d %H:%M')}: "
                    f"价格={current_price:.2f} (±{self.price_deviation_pct*100:.0f}%范围) | "
                    f"支撑位={len(selected_below)}个, 压力位={len(selected_above)}个"
                )

            return grid_levels

        except Exception as e:
            logger.error(f"网格计算失败: {e}", exc_info=True)
            return None

    def _analyze_multi_timeframe_backtest(
        self,
        current_time: datetime
    ) -> List[TimeframeAnalysis]:
        """
        基于回测数据库执行多周期分析

        Args:
            current_time: 当前时间点

        Returns:
            TimeframeAnalysis列表
        """
        analyses = []

        for timeframe in self.timeframes:
            lookback_count = self.lookback_periods.get(timeframe, 100)

            # 从数据库查询历史K线
            klines_db = KLine.objects.filter(
                symbol=self.symbol,
                interval=timeframe,
                open_time__lte=current_time
            ).order_by('-open_time')[:lookback_count]

            if len(klines_db) < 10:  # 至少需要10根K线
                logger.warning(
                    f"{timeframe}周期数据不足: {len(klines_db)}, "
                    f"时间点={current_time}"
                )
                continue

            # 转换为KLineData对象
            klines = []
            for k in reversed(list(klines_db)):  # 反转回时间正序
                klines.append(KLineData(
                    open_time=k.open_time,
                    open=float(k.open_price),
                    high=float(k.high_price),
                    low=float(k.low_price),
                    close=float(k.close_price),
                    volume=float(k.volume),
                    close_time=k.close_time,
                    quote_volume=float(k.quote_volume),
                    trade_count=k.trade_count,
                    taker_buy_volume=float(k.taker_buy_volume),
                    taker_buy_quote_volume=float(k.taker_buy_quote_volume)
                ))

            # 计算Volume Profile
            vp = calculate_volume_profile(klines, resolution_pct=0.0005)

            # 计算增强HVN
            total_volume = sum(k.volume for k in klines)
            enhanced_hvns = calculate_enhanced_hvn(vp, total_volume, timeframe)

            # 计算成交量集中度（VAL-VAH区间）
            val_vah_volume = sum(
                vol for price, vol in vp.profile.items()
                if vp.val <= price <= vp.vah
            )
            volume_concentration = (
                val_vah_volume / total_volume
                if total_volume > 0 else 0
            )

            # 计算平均成交量密度
            avg_volume_density = (
                sum(hvn.volume_density for hvn in enhanced_hvns) / len(enhanced_hvns)
                if enhanced_hvns else 0
            )

            # 构建TimeframeAnalysis
            analysis = TimeframeAnalysis(
                timeframe=timeframe,
                klines=klines,
                volume_profile=vp,
                enhanced_hvns=enhanced_hvns,
                total_volume=total_volume,
                volume_concentration=volume_concentration,
                avg_volume_density=avg_volume_density
            )

            analyses.append(analysis)
            logger.debug(
                f"{timeframe}周期分析完成: "
                f"K线数={len(klines)}, HVN数={len(enhanced_hvns)}"
            )

        return analyses

    def _get_current_price(self, current_time: datetime) -> Optional[float]:
        """获取当前价格"""
        try:
            kline = KLine.objects.filter(
                symbol=self.symbol,
                interval='4h',
                open_time__lte=current_time
            ).order_by('-open_time').first()

            if kline:
                return float(kline.close_price)
            return None

        except Exception as e:
            logger.error(f"获取当前价格失败: {e}")
            return None

    def _create_grid_level(
        self,
        cluster,
        ma25: Optional[float],
        is_resistance: bool
    ) -> GridLevelInfo:
        """
        从成交量区间创建网格层级

        Args:
            cluster: VolumePeak对象（区间模式）
            ma25: MA25值
            is_resistance: 是否为压力位

        Returns:
            GridLevelInfo
        """
        # 提取保守边界
        if is_resistance:
            # 压力位使用区间低价（更保守）
            base_price = cluster.price_low
        else:
            # 支撑位使用区间高价（更保守）
            base_price = cluster.price_high

        # MA25调整
        adjusted_price, was_adjusted = adjust_price_with_ma25(
            price=base_price,
            ma25=ma25,
            adjustment_threshold=0.02
        )

        # 区间边界（保持原始区间）
        zone_low = cluster.price_low
        zone_high = cluster.price_high

        return GridLevelInfo(
            price=adjusted_price,
            zone_low=zone_low,
            zone_high=zone_high
        )

    def _calculate_quality(self, clusters: List) -> float:
        """
        计算分析质量

        基于选中区间的成交量强度
        """
        if not clusters:
            return 0.0

        avg_strength = sum(c.volume_strength for c in clusters) / len(clusters)
        return min(1.0, avg_strength)
