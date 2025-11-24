"""两层箱体输出格式化"""
import json
from datetime import datetime, timezone
from vp_squeeze.services.dual_box_selector import DualBoxResult
from vp_squeeze.services.indicators.utils import format_price


def format_dual_box_text(result: DualBoxResult) -> str:
    """
    格式化两层箱体为文本输出

    Args:
        result: DualBoxResult对象

    Returns:
        格式化的文本字符串
    """
    # 综合评分可视化
    score_pct = int(result.overall_score)
    score_bar = "█" * (score_pct // 10) + "░" * (10 - score_pct // 10)

    lines = [
        "═" * 80,
        f"两层箱体通道分析: {result.symbol}",
        "═" * 80,
        "",
        "─" * 80,
        "📊 综合评分",
        "─" * 80,
        f"   总分: {score_pct}分 [{score_bar}]",
        f"   ├─ 成交量因子: {result.volume_factor:.0f}分 (权重60%)",
        f"   ├─ 位置关系:   {result.position_factor:.0f}分 (权重20%)",
        f"   └─ Squeeze:    {result.squeeze_factor:.0f}分 (权重15%)",
        "",
        "─" * 80,
        "📦 主箱体（趋势级别）",
        "─" * 80,
        f"   来源周期: {result.primary_box.timeframe}",
        f"   支撑位:   ${format_price(result.primary_box.support)}",
        f"   压力位:   ${format_price(result.primary_box.resistance)}",
        f"   中点:     ${format_price(result.primary_box.midpoint)}",
        f"   箱体宽度: {result.primary_box.range_pct:.2f}%",
        "",
        f"   成交量指标:",
        f"   ├─ 成交量集中度: {result.primary_box.volume_concentration:.1%}",
        f"   ├─ HVN节点数量:  {result.primary_box.hvn_count}个",
        f"   ├─ 成交量密度:   {result.primary_box.volume_density:.0f}",
        f"   └─ 箱体得分:     {result.primary_box.score:.0f}分",
        "",
        "─" * 80,
        "📦 次箱体（入场级别）",
        "─" * 80,
        f"   来源周期: {result.secondary_box.timeframe}",
        f"   支撑位:   ${format_price(result.secondary_box.support)}",
        f"   压力位:   ${format_price(result.secondary_box.resistance)}",
        f"   中点:     ${format_price(result.secondary_box.midpoint)}",
        f"   箱体宽度: {result.secondary_box.range_pct:.2f}%",
        "",
        f"   成交量指标:",
        f"   ├─ 成交量集中度: {result.secondary_box.volume_concentration:.1%}",
        f"   ├─ HVN节点数量:  {result.secondary_box.hvn_count}个",
        f"   ├─ 成交量密度:   {result.secondary_box.volume_density:.0f}",
        f"   └─ 箱体得分:     {result.secondary_box.score:.0f}分",
        "",
    ]

    # 强成交位
    if result.strong_support or result.strong_resistance:
        lines.extend([
            "─" * 80,
            "🎯 强成交位（多周期共振）",
            "─" * 80,
        ])

    if result.strong_support:
        s = result.strong_support
        lines.extend([
            f"   📍 强支撑位: ${format_price(s.price_center)} "
            f"(区间: ${format_price(s.price_range[0])} - ${format_price(s.price_range[1])})",
            f"      ├─ 成交量强度: {s.volume_strength}分",
            f"      ├─ 周期来源:   {', '.join(s.timeframes)}",
            f"      ├─ HVN重叠数:  {s.hvn_overlap}个",
            f"      └─ 成交量:     {s.total_volume:,.0f}",
            "",
        ])

    if result.strong_resistance:
        r = result.strong_resistance
        lines.extend([
            f"   📍 强压力位: ${format_price(r.price_center)} "
            f"(区间: ${format_price(r.price_range[0])} - ${format_price(r.price_range[1])})",
            f"      ├─ 成交量强度: {r.volume_strength}分",
            f"      ├─ 周期来源:   {', '.join(r.timeframes)}",
            f"      ├─ HVN重叠数:  {r.hvn_overlap}个",
            f"      └─ 成交量:     {r.total_volume:,.0f}",
            "",
        ])

    # 成交量共振区
    if result.resonance_zones:
        top_zones = result.resonance_zones[:5]  # 显示前5个
        lines.extend([
            "─" * 80,
            f"💎 成交量共振区（Top {len(top_zones)}）",
            "─" * 80,
        ])

        for i, zone in enumerate(top_zones, 1):
            zone_type_icon = "🔺" if zone.zone_type == 'resistance' else "🔻" if zone.zone_type == 'support' else "⚪"
            lines.append(
                f"   {zone_type_icon} #{i}: ${format_price(zone.price_center)} "
                f"[{', '.join(zone.timeframes)}] 强度={zone.strength:.0f}分"
            )
        lines.append("")

    lines.append("═" * 80)

    return "\n".join(lines)


def format_dual_box_json(result: DualBoxResult) -> str:
    """
    格式化两层箱体为JSON输出

    Args:
        result: DualBoxResult对象

    Returns:
        JSON字符串
    """
    data = {
        "symbol": result.symbol,
        "analysis_time": datetime.now(timezone.utc).isoformat(),

        "primary_box": {
            "source": result.primary_box.timeframe,
            "support": result.primary_box.support,
            "resistance": result.primary_box.resistance,
            "midpoint": result.primary_box.midpoint,
            "range_pct": result.primary_box.range_pct,
            "volume_concentration": result.primary_box.volume_concentration,
            "total_volume": result.primary_box.total_volume,
            "hvn_count": result.primary_box.hvn_count,
            "volume_density": result.primary_box.volume_density,
            "score": result.primary_box.score
        },

        "secondary_box": {
            "source": result.secondary_box.timeframe,
            "support": result.secondary_box.support,
            "resistance": result.secondary_box.resistance,
            "midpoint": result.secondary_box.midpoint,
            "range_pct": result.secondary_box.range_pct,
            "volume_concentration": result.secondary_box.volume_concentration,
            "total_volume": result.secondary_box.total_volume,
            "hvn_count": result.secondary_box.hvn_count,
            "volume_density": result.secondary_box.volume_density,
            "score": result.secondary_box.score
        },

        "strong_levels": {},

        "volume_analysis": {
            "resonance_zones": []
        },

        "channel_score": {
            "overall": result.overall_score,
            "volume_factor": result.volume_factor,
            "position_factor": result.position_factor,
            "squeeze_factor": result.squeeze_factor
        }
    }

    # 强成交位
    if result.strong_support:
        s = result.strong_support
        data["strong_levels"]["support"] = {
            "price_range": list(s.price_range),
            "center": s.price_center,
            "volume_strength": s.volume_strength,
            "sources": s.timeframes,
            "total_volume": s.total_volume,
            "hvn_overlap": s.hvn_overlap,
            "density_score": s.density_score
        }

    if result.strong_resistance:
        r = result.strong_resistance
        data["strong_levels"]["resistance"] = {
            "price_range": list(r.price_range),
            "center": r.price_center,
            "volume_strength": r.volume_strength,
            "sources": r.timeframes,
            "total_volume": r.total_volume,
            "hvn_overlap": r.hvn_overlap,
            "density_score": r.density_score
        }

    # 共振区
    for zone in result.resonance_zones:
        data["volume_analysis"]["resonance_zones"].append({
            "price_range": [zone.price_low, zone.price_high],
            "center": zone.price_center,
            "type": zone.zone_type,
            "total_volume": zone.total_volume,
            "timeframes": zone.timeframes,
            "hvn_count": zone.hvn_count,
            "strength": zone.strength
        })

    return json.dumps(data, indent=2, ensure_ascii=False)
