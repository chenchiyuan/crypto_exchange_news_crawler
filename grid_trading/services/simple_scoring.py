"""
简化评分模型 - 只基于4个核心指标

核心指标:
1. VDR - 波动率-位移比 (震荡性纯净度)
2. KER - 考夫曼效率比 (震荡vs趋势)
3. OVR - 持仓量/成交量比 (杠杆拥挤度)
4. CVD - CVD背离 (资金面信号)
"""

from typing import List, Tuple
from dataclasses import dataclass
from decimal import Decimal

from grid_trading.models import ScreeningResult, MarketSymbol
from grid_trading.models.volatility_metrics import VolatilityMetrics
from grid_trading.models.trend_metrics import TrendMetrics
from grid_trading.models.microstructure_metrics import MicrostructureMetrics


@dataclass
class SimpleScore:
    """简化评分结果"""

    symbol: str
    current_price: Decimal
    vdr: float
    ker: float
    ovr: float
    cvd_divergence: bool
    amplitude_sum_15m: float  # 最近100根15分钟K线振幅累计
    annual_funding_rate: float  # 年化资金费率(%)
    open_interest: Decimal  # 持仓量(USDT)

    # EMA均线斜率
    ma99_slope: float = 0.0  # EMA(99)斜率（标准化）
    ma20_slope: float = 0.0  # EMA(20)斜率（标准化）

    # 市场数据
    volume_24h_calculated: Decimal = Decimal('0')  # 24h交易量(USDT) - 从1440根1m K线计算
    vol_oi_ratio: float = 0.0  # 24h交易量/OI比率
    fdv: Decimal = None  # 完全稀释市值(USD)，可选
    oi_fdv_ratio: float = 0.0  # OI/FDV比率(%)
    has_spot: bool = False  # 是否有现货

    # 分项得分
    vdr_score: float = 0.0
    ker_score: float = 0.0
    ovr_score: float = 0.0
    cvd_score: float = 0.0

    # 综合指数
    composite_index: float = 0.0

    # 推荐网格参数
    grid_upper_limit: Decimal = None
    grid_lower_limit: Decimal = None
    grid_count: int = 0
    grid_step: Decimal = None

    # 止盈止损推荐
    take_profit_price: Decimal = None
    stop_loss_price: Decimal = None
    take_profit_pct: float = 0.0
    stop_loss_pct: float = 0.0

    # 挂单建议（新增）
    rsi_15m: float = 50.0
    recommended_entry_price: Decimal = None
    entry_trigger_prob_24h: float = 0.0
    entry_trigger_prob_72h: float = 0.0
    entry_strategy_label: str = '立即入场'
    entry_rebound_pct: float = 0.0
    entry_avg_trigger_time: float = 0.0
    entry_expected_return_24h: float = 0.0
    entry_candidates: list = None  # 3档候选方案

    # 高点回落指标（新增）
    highest_price_300: Decimal = None  # 300根4h K线的最高价
    drawdown_from_high_pct: float = 0.0  # 高点回落比例(%)

    # 价格分位指标（新增）
    price_percentile_100: float = 50.0  # 价格分位(100根4h K线)

    # 24小时资金流分析（新增）
    money_flow_large_net: float = 0.0        # 大单净流入金额 (USDT)
    money_flow_strength: float = 0.5         # 资金流强度 (0-1)
    money_flow_large_dominance: float = 0.0  # 大单主导度 (0-1)


    def to_dict(self) -> dict:
        """转换为字典用于HTML渲染"""
        return {
            'symbol': self.symbol,
            'price': float(self.current_price),
            'vdr': round(self.vdr, 2),
            'ker': round(self.ker, 3),
            'ovr': round(self.ovr, 2),
            'cvd': '✓' if self.cvd_divergence else '✗',
            'amplitude_sum_15m': round(self.amplitude_sum_15m, 2),
            'annual_funding_rate': round(self.annual_funding_rate, 2),
            'ma99_slope': round(self.ma99_slope, 2),
            'ma20_slope': round(self.ma20_slope, 2),
            'open_interest': float(self.open_interest) if self.open_interest else 0.0,
            'volume_24h_calculated': float(self.volume_24h_calculated) if self.volume_24h_calculated else 0.0,
            'vol_oi_ratio': round(self.vol_oi_ratio, 3),
            'fdv': float(self.fdv) if self.fdv else 0.0,
            'oi_fdv_ratio': round(self.oi_fdv_ratio, 2) if self.oi_fdv_ratio else 0.0,
            'has_spot': self.has_spot,
            'vdr_score': round(self.vdr_score * 100, 1),
            'ker_score': round(self.ker_score * 100, 1),
            'ovr_score': round(self.ovr_score * 100, 1),
            'cvd_score': round(self.cvd_score * 100, 1),
            'composite_index': round(self.composite_index, 4),
            'grid_upper': float(self.grid_upper_limit) if self.grid_upper_limit else 0.0,
            'grid_lower': float(self.grid_lower_limit) if self.grid_lower_limit else 0.0,
            'grid_count': self.grid_count,
            'grid_step': float(self.grid_step) if self.grid_step else 0.0,
            'take_profit_price': float(self.take_profit_price) if self.take_profit_price else 0.0,
            'stop_loss_price': float(self.stop_loss_price) if self.stop_loss_price else 0.0,
            'take_profit_pct': round(self.take_profit_pct, 2),
            'stop_loss_pct': round(self.stop_loss_pct, 2),
            # 资金流分析
            'money_flow_large_net': round(self.money_flow_large_net, 2),
            'money_flow_strength': round(self.money_flow_strength, 3),
            'money_flow_large_dominance': round(self.money_flow_large_dominance, 3),
        }


class SimpleScoring:
    """
    简化评分模型

    只基于4个核心指标计算综合指数:
    - VDR: 震荡性纯净度 (权重40%)
    - KER: 低效率波动 (权重30%)
    - OVR: 低杠杆拥挤 (权重20%)
    - CVD: 背离信号 (权重10%)
    """

    def __init__(
        self,
        vdr_weight: float = 0.40,
        ker_weight: float = 0.30,
        ovr_weight: float = 0.20,
        cvd_weight: float = 0.10,
    ):
        """
        初始化简化评分模型

        Args:
            vdr_weight: VDR权重 (默认40%)
            ker_weight: KER权重 (默认30%)
            ovr_weight: OVR权重 (默认20%)
            cvd_weight: CVD权重 (默认10%)
        """
        self.vdr_weight = vdr_weight
        self.ker_weight = ker_weight
        self.ovr_weight = ovr_weight
        self.cvd_weight = cvd_weight

        # 验证权重之和为1
        total = vdr_weight + ker_weight + ovr_weight + cvd_weight
        assert abs(total - 1.0) < 0.001, f"权重之和必须为1.0, 当前为{total}"

    def calculate_vdr_score(self, vdr: float) -> float:
        """
        计算VDR得分 (波动率-位移比)

        理想值: VDR越高越好 (震荡性越强)

        评分规则:
        - VDR >= 10: 满分 (1.0) - 完美震荡
        - 5 <= VDR < 10: 线性得分 (0.5-1.0)
        - VDR < 5: 低分 (0.0-0.5)

        Args:
            vdr: 波动率-位移比

        Returns:
            0.0-1.0得分
        """
        if vdr >= 10.0:
            return 1.0
        elif vdr >= 5.0:
            # 5-10之间线性映射到0.5-1.0
            return 0.5 + (vdr - 5.0) / 10.0
        else:
            # 0-5之间线性映射到0.0-0.5
            return vdr / 10.0

    def calculate_ker_score(self, ker: float) -> float:
        """
        计算KER得分 (考夫曼效率比)

        理想值: KER越低越好 (震荡性越强，趋势性越弱)

        评分规则:
        - KER <= 0.1: 满分 (1.0) - 极低效率，完美震荡
        - 0.1 < KER < 0.3: 线性得分 (0.5-1.0)
        - KER >= 0.3: 低分 (0.0-0.5) - 趋势性太强

        Args:
            ker: 考夫曼效率比

        Returns:
            0.0-1.0得分
        """
        if ker <= 0.1:
            return 1.0
        elif ker < 0.3:
            # 0.1-0.3之间反向映射到0.5-1.0
            return 1.0 - (ker - 0.1) * 2.5  # (0.3-0.1)^-1 = 5, 映射到0.5范围 = 2.5
        else:
            # KER >= 0.3，趋势性太强，低分
            # 0.3-1.0映射到0.5-0.0
            return max(0.0, 0.5 - (ker - 0.3) * 0.714)  # (1-0.3)^-1 * 0.5 ≈ 0.714

    def calculate_ovr_score(self, ovr: float) -> float:
        """
        计算OVR得分 (持仓量/成交量比)

        理想值: OVR适中最好 (0.5-1.5)

        评分规则:
        - 0.5 <= OVR <= 1.5: 满分 (1.0) - 杠杆健康
        - OVR < 0.5: 中等分 (0.5-1.0) - 流动性可能不足
        - 1.5 < OVR < 2.0: 中等分 (0.5-1.0) - 轻微拥挤
        - OVR >= 2.0: 低分 (0.0-0.5) - 高杠杆拥挤

        Args:
            ovr: 持仓量/成交量比

        Returns:
            0.0-1.0得分
        """
        if 0.5 <= ovr <= 1.5:
            return 1.0
        elif ovr < 0.5:
            # 0-0.5映射到0.5-1.0
            return 0.5 + ovr
        elif ovr < 2.0:
            # 1.5-2.0映射到1.0-0.5
            return 1.0 - (ovr - 1.5)
        else:
            # OVR >= 2.0，高杠杆拥挤
            # 2.0-5.0映射到0.5-0.0
            return max(0.0, 0.5 - (ovr - 2.0) / 6.0)

    def calculate_cvd_score(self, has_divergence: bool) -> float:
        """
        计算CVD得分 (CVD背离检测)

        理想值: 有熊市背离最好

        评分规则:
        - 有背离: 满分 (1.0)
        - 无背离: 基础分 (0.5)

        Args:
            has_divergence: 是否检测到CVD背离

        Returns:
            0.5或1.0得分
        """
        return 1.0 if has_divergence else 0.5

    def calculate_composite_index(
        self,
        vdr: float,
        ker: float,
        ovr: float,
        cvd_divergence: bool,
    ) -> Tuple[float, float, float, float, float]:
        """
        计算综合指数

        Args:
            vdr: 波动率-位移比
            ker: 考夫曼效率比
            ovr: 持仓量/成交量比
            cvd_divergence: 是否有CVD背离

        Returns:
            (vdr_score, ker_score, ovr_score, cvd_score, composite_index)
        """
        vdr_score = self.calculate_vdr_score(vdr)
        ker_score = self.calculate_ker_score(ker)
        ovr_score = self.calculate_ovr_score(ovr)
        cvd_score = self.calculate_cvd_score(cvd_divergence)

        composite = (
            self.vdr_weight * vdr_score
            + self.ker_weight * ker_score
            + self.ovr_weight * ovr_score
            + self.cvd_weight * cvd_score
        )

        return vdr_score, ker_score, ovr_score, cvd_score, composite

    def score_and_rank(
        self,
        indicators_data: List[Tuple[MarketSymbol, VolatilityMetrics, TrendMetrics, MicrostructureMetrics, float, float, float, float, float, float, dict]],
        klines_1m_dict: dict = None,
        klines_15m_dict: dict = None,
        spot_symbols: set = None
    ) -> List[SimpleScore]:
        """
        对所有标的评分并排序

        Args:
            indicators_data: 包含三维指标的列表 (market_symbol, vol, trend, micro, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct, price_percentile_100, money_flow_metrics)
            klines_1m_dict: 1分钟K线数据字典 (用于计算24h交易量)
            klines_15m_dict: 15分钟K线数据字典 (用于挂单概率统计)
            spot_symbols: 现货交易对集合

        Returns:
            按综合指数降序排列的SimpleScore列表
        """
        from grid_trading.services.indicator_calculator import calculate_volume_24h_from_1m_klines
        from grid_trading.services.entry_optimizer import generate_entry_recommendations

        results = []
        spot_symbols = spot_symbols or set()
        klines_1m_dict = klines_1m_dict or {}
        klines_15m_dict = klines_15m_dict or {}

        for market_symbol, vol, trend, micro, atr_daily, atr_hourly, rsi_15m, highest_price_300, drawdown_pct, price_percentile_100, money_flow_metrics in indicators_data:
            # 计算分项得分和综合指数
            vdr_score, ker_score, ovr_score, cvd_score, composite = self.calculate_composite_index(
                vdr=vol.vdr,
                ker=vol.ker,
                ovr=micro.ovr,
                cvd_divergence=micro.has_cvd_divergence,
            )

            # 计算网格参数
            from grid_trading.models.screening_result import calculate_grid_parameters
            upper, lower, grid_count = calculate_grid_parameters(
                market_symbol.current_price, atr_daily, atr_hourly
            )

            # 计算网格步长
            grid_step = Decimal(str(0.5 * atr_hourly))

            # 计算止盈止损（做空网格）
            # 做空策略：止损=网格上限（价格突破上限），止盈=网格下限（价格触及下限）
            stop_loss_price = upper
            take_profit_price = lower

            stop_loss_pct = float((stop_loss_price - market_symbol.current_price) / market_symbol.current_price * 100)
            take_profit_pct = float((market_symbol.current_price - take_profit_price) / market_symbol.current_price * 100)

            # 计算OI/FDV比率（FDV暂时为None，需要集成第三方API）
            fdv = None  # TODO: 集成CoinGecko或CMC API获取FDV数据
            oi_fdv_ratio = 0.0
            if fdv and float(fdv) > 0:
                oi_fdv_ratio = float(market_symbol.open_interest / fdv * 100)

            # 检查是否有现货
            has_spot = market_symbol.symbol in spot_symbols

            # 计算24h交易量 (从1440根1m K线)
            klines_1m = klines_1m_dict.get(market_symbol.symbol, [])
            volume_24h_calculated = Decimal(str(calculate_volume_24h_from_1m_klines(klines_1m)))

            # 计算Vol/OI比率
            vol_oi_ratio = 0.0
            if float(market_symbol.open_interest) > 0:
                vol_oi_ratio = float(volume_24h_calculated / market_symbol.open_interest)

            # ========== 计算挂单建议 ==========
            klines_15m = klines_15m_dict.get(market_symbol.symbol, [])
            entry_rec = None
            if klines_15m and len(klines_15m) >= 672:  # 至少7天数据
                try:
                    entry_rec = generate_entry_recommendations(
                        symbol=market_symbol.symbol,
                        current_price=float(market_symbol.current_price),
                        grid_lower=float(lower),
                        rsi_15m=rsi_15m,
                        ema99_slope=trend.ma99_slope,
                        natr=vol.natr,
                        klines_15m=klines_15m
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger("grid_trading")
                    logger.warning(f"{market_symbol.symbol} 挂单建议计算失败: {e}")

            # 提取挂单建议数据
            entry_candidates = []
            if entry_rec and entry_rec.get('recommended'):
                rec = entry_rec['recommended']
                recommended_entry_price = Decimal(str(rec['entry_price']))
                entry_trigger_prob_24h = rec.get('trigger_prob_24h', 0.0)
                entry_trigger_prob_72h = rec.get('trigger_prob_72h', 0.0)
                entry_strategy_label = rec.get('label', '立即入场')
                entry_rebound_pct = rec.get('rebound_pct', 0.0) * 100  # 转为百分比
                entry_avg_trigger_time = rec.get('avg_trigger_time', 0.0)
                entry_expected_return_24h = rec.get('expected_return_24h', 0.0)

                # 保存所有3个候选方案
                if entry_rec.get('candidates'):
                    for cand in entry_rec['candidates']:
                        entry_candidates.append({
                            'label': cand.get('label', ''),
                            'entry_price': float(cand.get('entry_price', 0)),
                            'rebound_pct': round(cand.get('rebound_pct', 0) * 100, 2),  # 转为百分比
                            'trigger_prob_24h': round(cand.get('trigger_prob_24h', 0), 3),
                            'trigger_prob_72h': round(cand.get('trigger_prob_72h', 0), 3),
                            'avg_trigger_time': round(cand.get('avg_trigger_time', 0), 1),
                            'profit_potential': round(cand.get('profit_potential', 0), 3),
                            'expected_return_24h': round(cand.get('expected_return_24h', 0), 3),
                        })
            else:
                # 降级：使用当前价
                recommended_entry_price = market_symbol.current_price
                entry_trigger_prob_24h = 1.0
                entry_trigger_prob_72h = 1.0
                entry_strategy_label = '立即入场'
                entry_rebound_pct = 0.0
                entry_avg_trigger_time = 0.0
                entry_expected_return_24h = take_profit_pct / 100  # 使用止盈百分比作为估计
                # 降级时也创建一个默认候选
                entry_candidates = [{
                    'label': '立即入场',
                    'entry_price': float(market_symbol.current_price),
                    'rebound_pct': 0.0,
                    'trigger_prob_24h': 1.0,
                    'trigger_prob_72h': 1.0,
                    'avg_trigger_time': 0.0,
                    'profit_potential': take_profit_pct / 100,
                    'expected_return_24h': take_profit_pct / 100,
                }]

            results.append(
                SimpleScore(
                    symbol=market_symbol.symbol,
                    current_price=market_symbol.current_price,
                    vdr=vol.vdr,
                    ker=vol.ker,
                    ovr=micro.ovr,
                    cvd_divergence=micro.has_cvd_divergence,
                    amplitude_sum_15m=vol.amplitude_sum_15m,
                    annual_funding_rate=micro.annual_funding_rate,
                    open_interest=market_symbol.open_interest,
                    ma99_slope=trend.ma99_slope,
                    ma20_slope=trend.ma20_slope,
                    volume_24h_calculated=volume_24h_calculated,
                    vol_oi_ratio=vol_oi_ratio,
                    fdv=fdv,
                    oi_fdv_ratio=oi_fdv_ratio,
                    has_spot=has_spot,
                    vdr_score=vdr_score,
                    ker_score=ker_score,
                    ovr_score=ovr_score,
                    cvd_score=cvd_score,
                    composite_index=composite,
                    grid_upper_limit=upper,
                    grid_lower_limit=lower,
                    grid_count=grid_count,
                    grid_step=grid_step,
                    take_profit_price=take_profit_price,
                    stop_loss_price=stop_loss_price,
                    take_profit_pct=take_profit_pct,
                    stop_loss_pct=stop_loss_pct,
                    # 挂单建议
                    rsi_15m=rsi_15m,
                    recommended_entry_price=recommended_entry_price,
                    entry_trigger_prob_24h=entry_trigger_prob_24h,
                    entry_trigger_prob_72h=entry_trigger_prob_72h,
                    entry_strategy_label=entry_strategy_label,
                    entry_rebound_pct=entry_rebound_pct,
                    entry_avg_trigger_time=entry_avg_trigger_time,
                    entry_expected_return_24h=entry_expected_return_24h,
                    entry_candidates=entry_candidates,
                    # 高点回落指标
                    highest_price_300=Decimal(str(highest_price_300)),
                    drawdown_from_high_pct=drawdown_pct,
                    # 价格分位指标
                    price_percentile_100=price_percentile_100,
                    # 24小时资金流分析
                    money_flow_large_net=money_flow_metrics.get('large_net_flow', 0.0),
                    money_flow_strength=money_flow_metrics.get('money_flow_strength', 0.5),
                    money_flow_large_dominance=money_flow_metrics.get('large_dominance', 0.0),
                )
            )

        # 按综合指数降序排序（分数相同时按symbol字母序，确保稳定性）
        results.sort(key=lambda x: (-x.composite_index, x.symbol))

        return results
