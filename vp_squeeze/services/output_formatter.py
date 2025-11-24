"""VP-Squeeze输出格式化器"""
import json
from typing import List
from vp_squeeze.dto import VPSqueezeAnalysisResult
from vp_squeeze.services.indicators.utils import format_price


def format_text_output(result: VPSqueezeAnalysisResult) -> str:
    """
    格式化为人类可读的文本输出

    Args:
        result: VPSqueezeAnalysisResult对象

    Returns:
        格式化的文本字符串
    """
    squeeze_icon = "✓" if result.squeeze.active else "✗"
    squeeze_text = "有效" if result.squeeze.active else "无效"

    # 置信率
    confidence_pct = result.confidence.confidence_pct if result.confidence else 0
    confidence_bar = "█" * (confidence_pct // 10) + "░" * (10 - confidence_pct // 10)

    lines = [
        "═" * 65,
        f"VP-Squeeze Analysis: {result.symbol} ({result.interval}) | {result.timestamp:%Y-%m-%d %H:%M} UTC",
        "═" * 65,
        "",
        "─" * 65,
        "📦 箱体范围",
        "─" * 65,
    ]

    if result.box:
        lines.extend([
            f"   支撑位:   ${format_price(result.box.support)}",
            f"   压力位:   ${format_price(result.box.resistance)}",
            f"   中点:     ${format_price(result.box.midpoint)}",
            f"   箱体宽度: {result.box.range_pct:.2f}%",
        ])
    else:
        lines.extend([
            f"   支撑位:   ${format_price(result.volume_profile.val)}",
            f"   压力位:   ${format_price(result.volume_profile.vah)}",
            f"   中点:     ${format_price(result.volume_profile.vpoc)}",
        ])

    lines.extend([
        "",
        "─" * 65,
        "📊 置信率",
        "─" * 65,
        f"   综合置信率: {confidence_pct}% [{confidence_bar}]",
    ])

    if result.confidence:
        lines.extend([
            f"   ├─ Squeeze状态:   {result.confidence.squeeze_score * 100:.0f}% (权重30%)",
            f"   ├─ 成交量集中度: {result.confidence.volume_concentration * 100:.0f}% (权重35%)",
            f"   ├─ 价格波动率:   {result.confidence.volatility_score * 100:.0f}% (权重20%)",
            f"   └─ 区间宽度:     {result.confidence.range_score * 100:.0f}% (权重15%)",
        ])

    lines.extend([
        "",
        "─" * 65,
        f"📈 Squeeze状态: {squeeze_icon} {squeeze_text} (连续{result.squeeze.consecutive_bars}根K线)",
        "─" * 65,
        "",
    ])

    # 高量节点
    if result.volume_profile.hvn:
        lines.extend([
            "─" * 65,
            "📈 高量节点 (HVN) - 强支撑/阻力区",
            "─" * 65,
        ])
        for hvn in result.volume_profile.hvn[:3]:  # 最多显示3个
            lines.append(f"   • ${format_price(hvn['low'])} - ${format_price(hvn['high'])}")
        lines.append("")

    # 低量节点
    if result.volume_profile.lvn:
        lines.extend([
            "📉 低量节点 (LVN) - 价格快速穿越区",
            "─" * 65,
        ])
        for lvn in result.volume_profile.lvn[:3]:  # 最多显示3个
            lines.append(f"   • ${format_price(lvn['low'])} - ${format_price(lvn['high'])}")
        lines.append("")

    lines.append("═" * 65)

    return "\n".join(lines)


def format_json_output(result: VPSqueezeAnalysisResult) -> str:
    """
    格式化为JSON输出

    Args:
        result: VPSqueezeAnalysisResult对象

    Returns:
        JSON字符串
    """
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


def format_batch_text_output(results: List[VPSqueezeAnalysisResult]) -> str:
    """
    格式化批量分析的文本输出

    Args:
        results: VPSqueezeAnalysisResult对象列表

    Returns:
        格式化的文本字符串
    """
    if not results:
        return "无分析结果"

    lines = [
        "═" * 95,
        f"VP-Squeeze 批量分析结果 | {results[0].timestamp:%Y-%m-%d %H:%M} UTC",
        f"共分析 {len(results)} 个交易对",
        "═" * 95,
        "",
    ]

    # 汇总表格（新增置信率列）
    lines.extend([
        f"{'交易对':<12} {'周期':<6} {'支撑位':<14} {'压力位':<14} {'箱体宽度':<10} {'置信率':<8} {'Squeeze':<8}",
        "─" * 95,
    ])

    for r in results:
        squeeze_status = "✓有效" if r.squeeze.active else "✗无效"
        confidence_pct = r.confidence.confidence_pct if r.confidence else 0
        box_range_pct = r.box.range_pct if r.box else 0
        support = r.box.support if r.box else r.volume_profile.val
        resistance = r.box.resistance if r.box else r.volume_profile.vah

        lines.append(
            f"{r.symbol:<12} {r.interval:<6} "
            f"${format_price(support):<13} ${format_price(resistance):<13} "
            f"{box_range_pct:>6.2f}%    {confidence_pct:>3}%     {squeeze_status:<8}"
        )

    lines.extend([
        "",
        "═" * 95,
    ])

    # 高置信率交易对（置信率>=60%）
    high_confidence = [r for r in results if r.confidence and r.confidence.confidence_pct >= 60]
    if high_confidence:
        # 按置信率排序
        high_confidence.sort(key=lambda x: x.confidence.confidence_pct, reverse=True)
        lines.extend([
            "",
            f"🎯 发现 {len(high_confidence)} 个高置信率（≥60%）交易对:",
        ])
        for r in high_confidence:
            support = r.box.support if r.box else r.volume_profile.val
            resistance = r.box.resistance if r.box else r.volume_profile.vah
            lines.append(
                f"   • {r.symbol}: 支撑=${format_price(support)}, "
                f"压力=${format_price(resistance)}, "
                f"置信率={r.confidence.confidence_pct}%"
            )

    return "\n".join(lines)


def format_batch_json_output(results: List[VPSqueezeAnalysisResult]) -> str:
    """
    格式化批量分析的JSON输出

    Args:
        results: VPSqueezeAnalysisResult对象列表

    Returns:
        JSON字符串
    """
    data = {
        'count': len(results),
        'timestamp': results[0].timestamp.isoformat() if results else None,
        'results': [r.to_dict() for r in results],
        'summary': {
            'active_squeeze_count': sum(1 for r in results if r.squeeze.active),
            'symbols_analyzed': [r.symbol for r in results],
        }
    }
    return json.dumps(data, indent=2, ensure_ascii=False)
