"""两层箱体通道分析器 - 主入口"""
import logging
from datetime import datetime, timezone

from vp_squeeze.services.multi_timeframe_analyzer import analyze_multi_timeframe
from vp_squeeze.services.dual_box_selector import select_dual_box, DualBoxResult
from vp_squeeze.services.binance_kline_service import normalize_symbol

logger = logging.getLogger(__name__)


def analyze_dual_box(
    symbol: str,
    timeframes: list = None,
    limit: int = 100,
    verbose: bool = False
) -> DualBoxResult:
    """
    执行两层箱体通道分析

    流程:
        1. 多周期成交量分析（15m, 1h, 4h）
        2. 检测成交量共振区
        3. 选择主箱体和次箱体
        4. 识别强支撑/压力位
        5. 综合评分

    Args:
        symbol: 交易对（如 'eth' 或 'ETHUSDT'）
        timeframes: 时间周期列表，默认 ['15m', '1h', '4h']
        limit: K线数量，默认100
        verbose: 是否输出详细日志

    Returns:
        DualBoxResult对象
    """
    if timeframes is None:
        timeframes = ['15m', '1h', '4h']

    # 标准化symbol
    binance_symbol = normalize_symbol(symbol)

    if verbose:
        logger.info(f"开始两层箱体分析: {binance_symbol}, 周期: {timeframes}")

    # 1. 多周期成交量分析
    analyses, resonance_zones = analyze_multi_timeframe(
        symbol=binance_symbol,
        timeframes=timeframes,
        limit=limit,
        verbose=verbose
    )

    if verbose:
        logger.info(f"发现 {len(resonance_zones)} 个成交量共振区")

    # 2. 选择两层箱体
    result = select_dual_box(
        analyses=analyses,
        resonance_zones=resonance_zones,
        symbol=binance_symbol
    )

    if verbose:
        logger.info(f"主箱体: {result.primary_box.timeframe}, "
                   f"次箱体: {result.secondary_box.timeframe}")
        logger.info(f"综合评分: {result.overall_score:.0f}分 "
                   f"(成交量={result.volume_factor:.0f}, "
                   f"位置={result.position_factor:.0f})")

    return result
