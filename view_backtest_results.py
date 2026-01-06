#!/usr/bin/env python
"""
快速查看 Volume Trap 回测结果
使用方法: python view_backtest_results.py
"""

import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
django.setup()

from volume_trap.models_backtest import BacktestResult
from decimal import Decimal


def print_header(title):
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def show_summary():
    """显示汇总统计"""
    print_header("回测结果汇总")

    results = BacktestResult.objects.all()
    total_count = results.count()

    if total_count == 0:
        print("❌ 暂无回测结果")
        return

    print(f"📊 总事件数: {total_count}")

    # 盈利统计
    profitable_count = results.filter(is_profitable=True).count()
    loss_count = total_count - profitable_count
    profit_rate = profitable_count / total_count * 100

    print(f"✅ 盈利事件: {profitable_count} ({profit_rate:.1f}%)")
    print(f"❌ 亏损事件: {loss_count} ({100-profit_rate:.1f}%)")

    # 收益率统计
    profits = [float(r.final_profit_percent) for r in results]
    max_profit = max(profits)
    min_profit = min(profits)
    avg_profit = sum(profits) / len(profits)

    print(f"\n📈 收益率统计:")
    print(f"   最高: {max_profit:.2f}%")
    print(f"   最低: {min_profit:.2f}%")
    print(f"   平均: {avg_profit:.2f}%")


def show_details():
    """显示详细结果"""
    print_header("回测结果详情")

    results = BacktestResult.objects.all().order_by('final_profit_percent', reverse=True)

    if not results.exists():
        print("❌ 暂无回测结果")
        return

    # 表头
    print(f"{'ID':<5} {'交易对':<12} {'入场时间':<19} {'最终收益':<10} {'状态':<6}")
    print("-" * 60)

    # 数据行
    for result in results:
        monitor_id = str(result.monitor_id)
        symbol = result.symbol
        entry_time = result.entry_time.strftime('%Y-%m-%d %H:%M')
        final_profit = f"{float(result.final_profit_percent):.2f}%"
        status = "✅盈利" if result.is_profitable else "❌亏损"

        print(f"{monitor_id:<5} {symbol:<12} {entry_time:<19} {final_profit:<10} {status:<6}")


def show_best_worst():
    """显示最佳和最差表现"""
    print_header("最佳/最差表现")

    results = BacktestResult.objects.all()

    if not results.exists():
        print("❌ 暂无回测结果")
        return

    # 最佳表现
    best = results.order_by('-final_profit_percent').first()
    print(f"🏆 最佳表现:")
    print(f"   {best.symbol}: {float(best.final_profit_percent):.2f}%")
    print(f"   入场时间: {best.entry_time}")
    print(f"   入场价格: ${float(best.entry_price):.4f}")

    # 最差表现
    worst = results.order_by('final_profit_percent').first()
    print(f"\n💸 最差表现:")
    print(f"   {worst.symbol}: {float(worst.final_profit_percent):.2f}%")
    print(f"   入场时间: {worst.entry_time}")
    print(f"   入场价格: ${float(worst.entry_price):.4f}")


def main():
    """主函数"""
    print("\n" + "🔍" * 40)
    print("  Volume Trap 回测结果查看器")
    print("🔍" * 40)

    try:
        # 显示汇总
        show_summary()

        # 显示详情
        show_details()

        # 显示最佳/最差
        show_best_worst()

        print("\n" + "=" * 80)
        print("  查看完成")
        print("=" * 80 + "\n")

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("请确保已运行回测命令并有回测结果\n")


if __name__ == "__main__":
    main()
