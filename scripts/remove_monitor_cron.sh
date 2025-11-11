#!/bin/bash

###############################################################################
# Cron定时任务删除脚本 - 新合约监控
# 用途：删除新合约监控的cron任务
###############################################################################

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Cron任务标识
CRON_MARKER="# futures_monitor"

echo -e "${YELLOW}==================================================${NC}"
echo -e "${YELLOW}  删除新合约监控Cron任务${NC}"
echo -e "${YELLOW}==================================================${NC}"
echo ""

# 检查是否存在任务
if ! crontab -l 2>/dev/null | grep -q "$CRON_MARKER"; then
    echo -e "${YELLOW}未找到相关的cron任务${NC}"
    echo ""
    echo "当前所有cron任务："
    crontab -l 2>/dev/null || echo "  (无)"
    exit 0
fi

# 显示将要删除的任务
echo -e "${YELLOW}找到以下任务：${NC}"
crontab -l 2>/dev/null | grep "$CRON_MARKER"
echo ""

# 确认删除
read -p "确认删除此cron任务? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

# 删除任务
echo "正在删除cron任务..."
crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab -

echo ""
echo -e "${GREEN}✅ Cron任务已成功删除！${NC}"
echo ""
echo "剩余的cron任务："
crontab -l 2>/dev/null || echo "  (无)"
echo ""
