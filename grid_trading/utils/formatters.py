"""
终端输出格式化工具

用途: 格式化筛选系统的终端输出
关联FR: FR-031, FR-032, FR-033, FR-036, FR-037
"""

from typing import List, Dict
from decimal import Decimal


def format_config_output(
    weights: List[float],
    min_volume: Decimal,
    min_days: int,
    interval: str,
    top_n: int,
) -> str:
    """
    格式化配置信息输出 (FR-036)

    Args:
        weights: 权重列表 [w1, w2, w3, w4]
        min_volume: 最小流动性阈值 (USDT)
        min_days: 最小上市天数
        interval: K线周期
        top_n: Top N数量

    Returns:
        格式化的配置信息字符串
    """
    separator = "=" * 70
    output = f"""
{separator}
🚀 做空网格标的量化筛选系统
{separator}
⏰ 配置信息:
  - 权重: NATR={weights[0]}, (1-KER)={weights[1]}, Trend={weights[2]}, Micro={weights[3]}
  - 初筛阈值: 流动性>{min_volume:,.0f} USDT, 上市>{min_days}天
  - K线周期: {interval} (300根)
  - Top N: {top_n}
"""
    return output


def format_pipeline_progress(
    step_name: str, message: str, total: int = 0, passed: int = 0, duration: float = 0
) -> str:
    """
    格式化Pipeline进度输出 (FR-033)

    Args:
        step_name: 步骤名称
        message: 步骤消息
        total: 总数 (可选)
        passed: 通过数 (可选)
        duration: 用时 (秒, 可选)

    Returns:
        格式化的进度信息字符串
    """
    separator = "-" * 70
    output = f"""
{separator}
{step_name}
{separator}
"""

    if total > 0:
        output += f"  {message} ✓ 总数: {total}"
        if passed > 0:
            output += f", 通过: {passed}"
        if duration > 0:
            output += f" (用时: {duration:.1f}秒)"
    else:
        output += f"  {message}"

    return output


def format_results_table(results: List[Dict]) -> str:
    """
    格式化结果表格 (FR-031, FR-032)

    Args:
        results: 筛选结果列表，每个元素为字典 (来自 ScreeningResult.to_terminal_row())

    Returns:
        格式化的表格字符串
    """
    if not results:
        return "  无符合条件的标的\n"

    # 表头
    header = """
| Rank | Symbol    | Price     | NATR  | KER   | VDR  | H     | Z-Sc | Slope | R²    | OVR  | Fund    | CVD | CVD_ROC | GSS    | Grid Upper | Grid Lower | Flags          |
|------|-----------|-----------|-------|-------|------|-------|------|-------|-------|------|---------|-----|---------|--------|------------|------------|----------------|"""

    # 数据行
    rows = []
    for r in results:
        row = f"| {r['rank']:<4} | {r['symbol']:<9} | {r['price']:<9} | {r['natr']:<5} | {r['ker']:<5} | {r['vdr']:<4} | {r['hurst']:<5} | {r['z_score']:<4} | {r['slope']:<5} | {r['r2']:<5} | {r['ovr']:<4} | {r['funding']:<7} | {r['cvd']:<3} | {r['cvd_roc']:<7} | {r['gss']:<6} | {r['grid_upper']:<10} | {r['grid_lower']:<10} | {r['warnings']:<14} |"
        rows.append(row)

    return header + "\n" + "\n".join(rows) + "\n"


def format_execution_summary(
    duration: float, total_symbols: int, passed_symbols: int, top_n_count: int
) -> str:
    """
    格式化执行摘要 (FR-033, FR-037)

    Args:
        duration: 总执行时长 (秒)
        total_symbols: 总标的数
        passed_symbols: 初筛通过数
        top_n_count: 最终Top N数量

    Returns:
        格式化的执行摘要字符串
    """
    separator = "=" * 70
    output = f"""
{separator}
✅ 筛选完成
{separator}
📊 执行摘要:
  - 扫描时长: {duration:.1f}秒
  - 总标的数: {total_symbols}
  - 初筛通过数: {passed_symbols}
  - 最终Top N: {top_n_count}
{separator}
"""
    return output


def format_error_output(error_type: str, error_message: str, suggestion: str) -> str:
    """
    格式化错误输出

    Args:
        error_type: 错误类型
        error_message: 错误详情
        suggestion: 解决建议

    Returns:
        格式化的错误信息字符串
    """
    separator = "=" * 70
    output = f"""
{separator}
❌ 执行失败
{separator}
❌ 错误信息:
  - 类型: {error_type}
  - 详情: {error_message}

💡 解决方案:
  - {suggestion}
{separator}
"""
    return output


def format_no_results_output(
    total_symbols: int, passed_symbols: int, reason: str
) -> str:
    """
    格式化无合格标的输出 (Edge Case, SC-008)

    Args:
        total_symbols: 总标的数
        passed_symbols: 初筛通过数
        reason: 原因描述

    Returns:
        格式化的提示信息字符串
    """
    separator = "=" * 70
    output = f"""
{separator}
⚠️ 当前市场条件不适合做空网格,建议等待
{separator}
📊 诊断信息:
  - 总标的数: {total_symbols}
  - 初筛通过数: {passed_symbols}
  - 原因: {reason}

💡 建议:
  - 降低 --min-volume 阈值
  - 等待市场进入震荡期
  - 调整权重配置
{separator}
"""
    return output
