#!/bin/bash
# Grid Strategy V2 回测播放器演示脚本

echo "============================================"
echo "  Grid Strategy V2 回测播放器"
echo "============================================"
echo ""

# 检查服务器是否运行
if ! curl -s http://127.0.0.1:8001/backtest/api/backtests/ > /dev/null 2>&1; then
    echo "⚠️  Django服务器未运行，正在启动..."
    echo ""
    python manage.py runserver 0.0.0.0:8001 &
    SERVER_PID=$!
    echo "等待服务器启动..."
    sleep 5
else
    echo "✅ Django服务器已运行"
    echo ""
fi

# 检查回测数据
echo "📊 检查回测数据..."
BACKTEST_COUNT=$(curl -s http://127.0.0.1:8001/backtest/api/backtests/ | python -c "import sys, json; data=json.load(sys.stdin); print(data['total'])" 2>/dev/null)

if [ "$BACKTEST_COUNT" -gt 0 ]; then
    echo "✅ 找到 $BACKTEST_COUNT 个回测记录"
    echo ""
    echo "📈 回测详情:"
    curl -s http://127.0.0.1:8001/backtest/api/backtests/ | python -c "
import sys, json
data = json.load(sys.stdin)
for bt in data['backtests']:
    print(f\"   - {bt['name']}\")
    print(f\"     收益率: {bt['total_return']*100:.2f}%\")
    print(f\"     交易次数: {bt['total_trades']}\")
    print(f\"     创建时间: {bt['created_at']}\")
    print()
"
else
    echo "❌ 未找到回测数据"
    echo ""
    echo "💡 运行以下命令生成回测数据:"
    echo "   python manage.py run_backtest --symbol ETHUSDT --interval 4h --strategy grid_v2 --days 30"
    exit 1
fi

echo "============================================"
echo "  🚀 准备就绪！"
echo "============================================"
echo ""
echo "访问播放器:"
echo "  👉 http://127.0.0.1:8001/backtest/player/"
echo ""
echo "功能说明:"
echo "  - 点击K线查看详细状态"
echo "  - 绿色↑标记 = 买入事件"
echo "  - 橙色↓标记 = 卖出事件"
echo "  - 红色×标记 = 止损事件"
echo "  - 拖动时间轴快速导航"
echo ""
echo "API接口:"
echo "  - GET /backtest/api/backtests/ (回测列表)"
echo "  - GET /backtest/api/backtests/{id}/ (回测详情)"
echo "  - GET /backtest/api/backtests/{id}/snapshots/ (快照列表)"
echo "  - GET /backtest/api/backtests/{id}/snapshots/{index}/ (K线详情)"
echo ""
echo "详细文档: WEB_BACKTEST_PLAYER_GUIDE.md"
echo "============================================"

# 自动打开浏览器（macOS）
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo ""
    read -p "是否在浏览器中打开播放器？(y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open "http://127.0.0.1:8001/backtest/player/"
    fi
fi
