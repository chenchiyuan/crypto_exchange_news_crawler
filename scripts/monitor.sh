#!/bin/bash
# 一键监控脚本：获取公告 → 识别新币 → 发送通知
# 使用方法: ./scripts/monitor.sh [hours] [webhook_url]

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 切换到项目目录
cd "$PROJECT_DIR" || exit 1

# 默认参数
HOURS=${1:-24}
WEBHOOK_URL=${2:-}

# 如果没有提供webhook URL，尝试从环境变量读取
if [ -z "$WEBHOOK_URL" ]; then
    WEBHOOK_URL=${WEBHOOK_URL:-}
fi

echo "=========================================="
echo "🚀 加密货币新币上线监控系统"
echo "=========================================="
echo "项目目录: $PROJECT_DIR"
echo "时间范围: 最近 ${HOURS} 小时"
echo "交易所: Binance, Bybit, Bitget, Hyperliquid"

if [ -n "$WEBHOOK_URL" ]; then
    echo "通知: 已配置"
    echo "=========================================="
    echo ""

    # 执行监控（带通知）
    python manage.py monitor \
        --hours "$HOURS" \
        --max-pages 3 \
        --exchanges "binance,bybit,bitget,hyperliquid" \
        --webhook-url "$WEBHOOK_URL"
else
    echo "通知: 未配置（跳过）"
    echo "=========================================="
    echo ""

    # 执行监控（不发送通知）
    python manage.py monitor \
        --hours "$HOURS" \
        --max-pages 3 \
        --exchanges "binance,bybit,bitget,hyperliquid" \
        --skip-notification
fi

# 检查执行结果
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✅ 监控执行成功"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "❌ 监控执行失败"
    echo "=========================================="
    exit 1
fi
