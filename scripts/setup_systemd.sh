#!/bin/bash

###############################################################################
# Systemd Timer安装脚本
# 用途：在Linux系统上使用systemd timer替代cron
###############################################################################

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查是否为Linux系统
if [[ "$(uname)" != "Linux" ]]; then
    echo -e "${RED}错误: Systemd仅支持Linux系统${NC}"
    echo "Mac用户请使用 setup_cron.sh"
    exit 1
fi

# 检查systemd
if ! command -v systemctl &> /dev/null; then
    echo -e "${RED}错误: 未找到systemd${NC}"
    echo "请使用 setup_cron.sh 代替"
    exit 1
fi

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# 服务文件路径
SERVICE_FILE="${SCRIPT_DIR}/systemd/futures-price-update.service"
TIMER_FILE="${SCRIPT_DIR}/systemd/futures-price-update.timer"
SYSTEM_SERVICE_DIR="/etc/systemd/system"

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}  Systemd Timer 安装${NC}"
echo -e "${GREEN}==================================================${NC}"
echo ""

# 检查服务文件
if [ ! -f "$SERVICE_FILE" ] || [ ! -f "$TIMER_FILE" ]; then
    echo -e "${RED}错误: 未找到systemd配置文件${NC}"
    exit 1
fi

echo -e "${YELLOW}请提供以下信息：${NC}"
read -p "项目根目录 [${PROJECT_ROOT}]: " input_root
PROJECT_ROOT=${input_root:-$PROJECT_ROOT}

read -p "用户名 [$(whoami)]: " input_user
USERNAME=${input_user:-$(whoami)}

read -p "Python虚拟环境路径 [${PROJECT_ROOT}/venv]: " input_venv
VENV_PATH=${input_venv:-${PROJECT_ROOT}/venv}

echo ""
echo -e "${YELLOW}配置信息：${NC}"
echo "  项目根目录: $PROJECT_ROOT"
echo "  运行用户: $USERNAME"
echo "  虚拟环境: $VENV_PATH"
echo ""

# 生成配置文件
TMP_SERVICE="/tmp/futures-price-update.service"
TMP_TIMER="/tmp/futures-price-update.timer"

# 替换占位符
sed -e "s|YOUR_USERNAME|$USERNAME|g" \
    -e "s|/path/to/crypto_exchange_news_crawler|$PROJECT_ROOT|g" \
    "$SERVICE_FILE" > "$TMP_SERVICE"

cp "$TIMER_FILE" "$TMP_TIMER"

echo -e "${YELLOW}将要安装以下文件：${NC}"
echo "  Service: $SYSTEM_SERVICE_DIR/futures-price-update.service"
echo "  Timer: $SYSTEM_SERVICE_DIR/futures-price-update.timer"
echo ""

read -p "确认安装? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

# 需要root权限
if [ "$EUID" -ne 0 ]; then
    echo -e "${YELLOW}需要root权限，将使用sudo...${NC}"
    SUDO="sudo"
else
    SUDO=""
fi

# 复制文件
echo "正在安装systemd单元文件..."
$SUDO cp "$TMP_SERVICE" "$SYSTEM_SERVICE_DIR/futures-price-update.service"
$SUDO cp "$TMP_TIMER" "$SYSTEM_SERVICE_DIR/futures-price-update.timer"

# 设置权限
$SUDO chmod 644 "$SYSTEM_SERVICE_DIR/futures-price-update.service"
$SUDO chmod 644 "$SYSTEM_SERVICE_DIR/futures-price-update.timer"

# 重新加载systemd
echo "正在重新加载systemd..."
$SUDO systemctl daemon-reload

# 启用并启动timer
echo "正在启用并启动timer..."
$SUDO systemctl enable futures-price-update.timer
$SUDO systemctl start futures-price-update.timer

# 清理临时文件
rm -f "$TMP_SERVICE" "$TMP_TIMER"

echo ""
echo -e "${GREEN}✅ Systemd Timer安装成功！${NC}"
echo ""
echo -e "${YELLOW}常用命令：${NC}"
echo "  查看状态: sudo systemctl status futures-price-update.timer"
echo "  查看日志: sudo journalctl -u futures-price-update.service"
echo "  手动执行: sudo systemctl start futures-price-update.service"
echo "  停止定时: sudo systemctl stop futures-price-update.timer"
echo "  禁用定时: sudo systemctl disable futures-price-update.timer"
echo "  查看调度: systemctl list-timers"
echo ""
echo -e "${YELLOW}当前状态：${NC}"
$SUDO systemctl status futures-price-update.timer --no-pager
echo ""
