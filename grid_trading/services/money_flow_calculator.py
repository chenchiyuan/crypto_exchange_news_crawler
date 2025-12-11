"""
资金流计算器 (Money Flow Calculator)

用途: 基于1440根1分钟K线计算24小时资金流分析指标
方案: 分层级资金流 (Tiered Money Flow) - 按订单规模分层统计

核心算法:
1. 按成交量分层 (P50和P90分位数)
   - 小单: Volume ≤ P50 (散户为主)
   - 中单: P50 < Volume ≤ P90 (中等规模)
   - 大单: Volume > P90 (机构/巨鲸)

2. 各层级分别统计主动买入和卖出金额
   - 买入金额 = Σ (Close × TakerBuyVolume)
   - 卖出金额 = Σ (Close × (Volume - TakerBuyVolume))

3. 输出指标:
   - large_net_flow: 大单净流入金额 (USDT)
   - money_flow_strength: 整体资金流强度 (0-1)
   - large_dominance: 大单主导度 (0-1)
"""

import logging
import numpy as np
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("grid_trading")


def calculate_tiered_money_flow(klines_1m: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    计算分层级资金流指标

    Args:
        klines_1m: 1440根1分钟K线数据列表，每根K线包含:
            - close: 收盘价
            - volume: 成交量（币）
            - taker_buy_base_volume: 主动买入成交量（币）

    Returns:
        Dict包含3个指标:
        {
            'large_net_flow': float,         # 大单净流入金额 (USDT)
            'money_flow_strength': float,    # 整体资金流强度 (0-1)
            'large_dominance': float         # 大单主导度 (0-1)
        }

    异常处理:
        - 数据不足时返回默认值
        - 计算异常时记录日志并降级
    """
    # 数据验证
    if not klines_1m or len(klines_1m) < 100:
        logger.warning(
            f"1分钟K线数据不足 (仅{len(klines_1m) if klines_1m else 0}根), "
            "资金流分析降级返回默认值"
        )
        return _get_default_money_flow()

    try:
        # 1. 提取数据（安全处理None值）
        closes = np.array([float(k.get("close") or 0) for k in klines_1m])
        volumes = np.array([float(k.get("volume") or 0) for k in klines_1m])
        taker_buy_volumes = np.array(
            [float(k.get("taker_buy_base_volume") or 0) for k in klines_1m]
        )

        # 数据清洗：过滤掉价格或成交量为0的异常数据
        valid_mask = (closes > 0) & (volumes > 0)
        closes = closes[valid_mask]
        volumes = volumes[valid_mask]
        taker_buy_volumes = taker_buy_volumes[valid_mask]

        if len(closes) < 100:
            logger.warning(f"有效K线不足 (仅{len(closes)}根), 资金流分析降级")
            return _get_default_money_flow()

        # 2. 计算成交量分位数阈值
        p50 = np.percentile(volumes, 50)  # 中位数 (小单上限)
        p90 = np.percentile(volumes, 90)  # 90分位数 (中单上限)

        logger.debug(f"成交量分位数: P50={p50:.4f}, P90={p90:.4f}")

        # 3. 分层计算买入和卖出金额
        small_buy, small_sell = _calculate_tier_flow(
            closes, volumes, taker_buy_volumes, 0, p50
        )
        medium_buy, medium_sell = _calculate_tier_flow(
            closes, volumes, taker_buy_volumes, p50, p90
        )
        large_buy, large_sell = _calculate_tier_flow(
            closes, volumes, taker_buy_volumes, p90, float("inf")
        )

        # 4. 计算指标

        # 4.1 大单净流入金额
        large_net_flow = large_buy - large_sell

        # 4.2 整体资金流强度 (主动买入占比)
        total_buy = small_buy + medium_buy + large_buy
        total_sell = small_sell + medium_sell + large_sell
        total_flow = total_buy + total_sell

        if total_flow > 0:
            money_flow_strength = total_buy / total_flow
        else:
            money_flow_strength = 0.5  # 默认中性

        # 4.3 大单主导度 (大单净流入占总净流入的比例)
        small_net = abs(small_buy - small_sell)
        medium_net = abs(medium_buy - medium_sell)
        large_net = abs(large_buy - large_sell)

        total_net = small_net + medium_net + large_net
        if total_net > 0:
            large_dominance = large_net / total_net
        else:
            large_dominance = 0.0

        # 5. 返回结果
        result = {
            "large_net_flow": float(large_net_flow),
            "money_flow_strength": float(money_flow_strength),
            "large_dominance": float(large_dominance),
        }

        logger.debug(
            f"资金流计算完成: "
            f"大单净={large_net_flow:.2f}, "
            f"流强={money_flow_strength:.3f}, "
            f"主导={large_dominance:.3f}"
        )

        return result

    except Exception as e:
        logger.error(f"资金流计算失败: {e}", exc_info=True)
        return _get_default_money_flow()


def _calculate_tier_flow(
    closes: np.ndarray,
    volumes: np.ndarray,
    taker_buy_volumes: np.ndarray,
    volume_min: float,
    volume_max: float,
) -> Tuple[float, float]:
    """
    计算某一层级的买入和卖出金额

    Args:
        closes: 收盘价数组
        volumes: 成交量数组
        taker_buy_volumes: 主动买入成交量数组
        volume_min: 该层级成交量下限（包含）
        volume_max: 该层级成交量上限（不包含）

    Returns:
        (buy_amount, sell_amount): 买入金额和卖出金额 (USDT)
    """
    # 筛选该层级的K线
    mask = (volumes > volume_min) & (volumes <= volume_max)

    if not np.any(mask):
        return 0.0, 0.0

    tier_closes = closes[mask]
    tier_volumes = volumes[mask]
    tier_taker_buy = taker_buy_volumes[mask]

    # 计算该层级的买入和卖出金额
    tier_buy_amount = np.sum(tier_closes * tier_taker_buy)
    tier_sell_amount = np.sum(tier_closes * (tier_volumes - tier_taker_buy))

    return float(tier_buy_amount), float(tier_sell_amount)


def _get_default_money_flow() -> Dict[str, float]:
    """
    返回默认的资金流指标（数据不足或计算失败时使用）

    Returns:
        默认指标字典
    """
    return {
        "large_net_flow": 0.0,
        "money_flow_strength": 0.5,  # 中性
        "large_dominance": 0.0,
    }


def calculate_money_flow_metrics_batch(
    klines_1m_dict: Dict[str, List[Dict[str, Any]]]
) -> Dict[str, Dict[str, float]]:
    """
    批量计算多个标的的资金流指标

    Args:
        klines_1m_dict: {symbol: klines_1m} 字典

    Returns:
        {symbol: money_flow_metrics} 字典
    """
    results = {}

    for symbol, klines_1m in klines_1m_dict.items():
        try:
            results[symbol] = calculate_tiered_money_flow(klines_1m)
        except Exception as e:
            logger.warning(f"{symbol} 资金流计算失败: {e}")
            results[symbol] = _get_default_money_flow()

    return results


def format_money_flow_display(
    large_net_flow: float, money_flow_strength: float, large_dominance: float
) -> str:
    """
    格式化资金流指标用于展示

    Args:
        large_net_flow: 大单净流入 (USDT)
        money_flow_strength: 资金流强度 (0-1)
        large_dominance: 大单主导度 (0-1)

    Returns:
        格式化后的字符串，例如:
        "大单: +$500K (主导72%)  流强: 0.64 (买盘)"
    """
    # 格式化大单净流入
    if abs(large_net_flow) >= 1_000_000:
        net_flow_str = f"{large_net_flow / 1_000_000:+.2f}M"
    elif abs(large_net_flow) >= 1_000:
        net_flow_str = f"{large_net_flow / 1_000:+.1f}K"
    else:
        net_flow_str = f"{large_net_flow:+.0f}"

    # 判断资金流方向
    if money_flow_strength > 0.55:
        flow_direction = "买盘"
    elif money_flow_strength < 0.45:
        flow_direction = "卖盘"
    else:
        flow_direction = "平衡"

    # 组装展示字符串
    display_str = (
        f"大单: {net_flow_str} (主导{large_dominance * 100:.0f}%)  "
        f"流强: {money_flow_strength:.2f} ({flow_direction})"
    )

    return display_str


# ============================================================================
# 辅助函数: 用于分析和调试
# ============================================================================


def analyze_money_flow_distribution(
    klines_1m: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    分析资金流分布（用于调试和优化阈值）

    Args:
        klines_1m: 1440根1分钟K线数据

    Returns:
        分布统计信息
    """
    if not klines_1m:
        return {}

    volumes = np.array([float(k.get("volume", 0)) for k in klines_1m])
    volumes = volumes[volumes > 0]  # 过滤0值

    if len(volumes) == 0:
        return {}

    # 计算各分位数
    percentiles = {
        "P25": np.percentile(volumes, 25),
        "P50": np.percentile(volumes, 50),
        "P75": np.percentile(volumes, 75),
        "P90": np.percentile(volumes, 90),
        "P95": np.percentile(volumes, 95),
        "P99": np.percentile(volumes, 99),
    }

    # 计算各层级数量占比
    p50 = percentiles["P50"]
    p90 = percentiles["P90"]

    small_count = np.sum(volumes <= p50)
    medium_count = np.sum((volumes > p50) & (volumes <= p90))
    large_count = np.sum(volumes > p90)

    total_count = len(volumes)

    distribution = {
        "percentiles": percentiles,
        "tier_counts": {
            "small": int(small_count),
            "medium": int(medium_count),
            "large": int(large_count),
        },
        "tier_ratios": {
            "small": small_count / total_count,
            "medium": medium_count / total_count,
            "large": large_count / total_count,
        },
    }

    return distribution
