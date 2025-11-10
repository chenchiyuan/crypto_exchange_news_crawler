#!/bin/bash
# 批量获取交易所公告脚本
# 使用方法: ./scripts/fetch_announcements.sh [hours]

# 获取脚本所在目录的父目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# 切换到项目目录
cd "$PROJECT_DIR" || exit 1

# 默认获取最近24小时的公告
HOURS=${1:-24}

echo "=========================================="
echo "加密货币交易所公告监控系统"
echo "=========================================="
echo "项目目录: $PROJECT_DIR"
echo "时间范围: 最近 ${HOURS} 小时"
echo "交易所: Binance, Bybit, Bitget, Hyperliquid"
echo "=========================================="
echo ""

# 执行Django命令
python manage.py fetch_all_announcements \
    --hours "$HOURS" \
    --max-pages 3 \
    --exchanges "binance,bybit,bitget,hyperliquid"

# 检查执行结果
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ 公告获取完成"
    echo "=========================================="
else
    echo ""
    echo "=========================================="
    echo "✗ 公告获取失败"
    echo "=========================================="
    exit 1
fi
