"""VP-Squeeze核心分析器"""
import logging
from datetime import datetime, timezone

from vp_squeeze.dto import VPSqueezeAnalysisResult, BoxRange, ConfidenceScore
from vp_squeeze.services.binance_kline_service import fetch_klines, normalize_symbol
from vp_squeeze.services.indicators.bollinger_bands import calculate_bollinger_bands
from vp_squeeze.services.indicators.keltner_channels import calculate_keltner_channels
from vp_squeeze.services.indicators.volume_profile import calculate_volume_profile
from vp_squeeze.services.indicators.squeeze_detector import detect_squeeze
from vp_squeeze.services.confidence_calculator import (
    calculate_box_range,
    calculate_confidence,
)

logger = logging.getLogger(__name__)


def analyze(
    symbol: str,
    interval: str,
    limit: int = 100,
    verbose: bool = False
) -> VPSqueezeAnalysisResult:
    """
    执行VP-Squeeze分析

    流程:
        1. 获取K线数据
        2. 计算Bollinger Bands
        3. 计算Keltner Channels
        4. 检测Squeeze状态
        5. 计算Volume Profile
        6. 生成分析结果

    Args:
        symbol: 交易对（如 'eth' 或 'ETHUSDT'）
        interval: 时间周期（如 '4h'）
        limit: K线数量，默认100
        verbose: 是否输出详细日志

    Returns:
        VPSqueezeAnalysisResult对象
    """
    # 标准化symbol
    binance_symbol = normalize_symbol(symbol)

    if verbose:
        logger.info(f"开始分析 {binance_symbol} {interval}，K线数量: {limit}")

    # 1. 获取K线数据
    klines = fetch_klines(symbol, interval, limit)

    if verbose:
        logger.info(f"获取到 {len(klines)} 根K线")

    # 提取价格和成交量数据
    closes = [k.close for k in klines]
    highs = [k.high for k in klines]
    lows = [k.low for k in klines]
    volumes = [k.volume for k in klines]

    # 2. 计算Bollinger Bands
    bb = calculate_bollinger_bands(closes)

    if verbose:
        logger.info(f"BB计算完成: upper={bb['upper'][-1]:.2f}, lower={bb['lower'][-1]:.2f}")

    # 3. 计算Keltner Channels
    kc = calculate_keltner_channels(highs, lows, closes)

    if verbose:
        logger.info(f"KC计算完成: upper={kc['upper'][-1]:.2f}, lower={kc['lower'][-1]:.2f}")

    # 4. 检测Squeeze状态
    squeeze_status = detect_squeeze(bb, kc)

    if verbose:
        status_str = "有效" if squeeze_status.active else "无效"
        logger.info(f"Squeeze状态: {status_str}，连续 {squeeze_status.consecutive_bars} 根K线")

    # 5. 计算Volume Profile
    vp_result = calculate_volume_profile(klines)

    if verbose:
        logger.info(f"VP计算完成: VAL={vp_result.val:.2f}, VAH={vp_result.vah:.2f}, VPOC={vp_result.vpoc:.2f}")

    # 6. 计算统计信息
    price_min = min(lows)
    price_max = max(highs)
    total_volume = sum(volumes)

    # 获取最新的技术指标值
    bb_upper = bb['upper'][-1] if bb['upper'] else None
    bb_lower = bb['lower'][-1] if bb['lower'] else None
    kc_upper = kc['upper'][-1] if kc['upper'] else None
    kc_lower = kc['lower'][-1] if kc['lower'] else None

    # 7. 计算箱体范围
    box_range_calc = calculate_box_range(
        val=vp_result.val,
        vah=vp_result.vah,
        vpoc=vp_result.vpoc
    )
    box = BoxRange(
        support=box_range_calc.support,
        resistance=box_range_calc.resistance,
        midpoint=box_range_calc.midpoint,
        range_pct=box_range_calc.range_pct
    )

    if verbose:
        logger.info(f"箱体范围: 支撑={box.support:.2f}, 压力={box.resistance:.2f}, 宽度={box.range_pct:.2f}%")

    # 8. 计算置信率
    current_price = closes[-1] if closes else vp_result.vpoc
    confidence_calc = calculate_confidence(
        squeeze_active=squeeze_status.active,
        squeeze_consecutive_bars=squeeze_status.consecutive_bars,
        val=vp_result.val,
        vah=vp_result.vah,
        vpoc=vp_result.vpoc,
        profile=vp_result.profile,
        total_volume=total_volume,
        bb_upper=bb_upper,
        bb_lower=bb_lower,
        current_price=current_price
    )
    confidence = ConfidenceScore(
        confidence=confidence_calc.confidence,
        confidence_pct=confidence_calc.confidence_pct,
        squeeze_score=confidence_calc.squeeze_score,
        volume_concentration=confidence_calc.volume_concentration,
        volatility_score=confidence_calc.volatility_score,
        range_score=confidence_calc.range_score
    )

    if verbose:
        logger.info(f"置信率: {confidence.confidence_pct}% (Squeeze={confidence.squeeze_score:.2f}, "
                    f"成交量={confidence.volume_concentration:.2f}, 波动率={confidence.volatility_score:.2f}, "
                    f"区间={confidence.range_score:.2f})")

    # 构建结果
    result = VPSqueezeAnalysisResult(
        symbol=binance_symbol,
        interval=interval,
        timestamp=datetime.now(timezone.utc),
        klines_count=len(klines),
        squeeze=squeeze_status,
        volume_profile=vp_result,
        box=box,
        confidence=confidence,
        price_min=price_min,
        price_max=price_max,
        total_volume=total_volume,
        bb_upper=bb_upper,
        bb_lower=bb_lower,
        kc_upper=kc_upper,
        kc_lower=kc_lower,
    )

    if verbose:
        logger.info(f"分析完成: {binance_symbol} {interval}")

    return result


def save_result(result: VPSqueezeAnalysisResult) -> None:
    """
    保存分析结果到数据库

    Args:
        result: VPSqueezeAnalysisResult对象
    """
    model_instance = result.to_model()
    model_instance.save()
    logger.info(f"分析结果已保存: {result.symbol} {result.interval}")
