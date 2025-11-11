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

# 检测Python环境类型
ENV_TYPE=""
PYTHON_CMD=""
CONDA_ENV_NAME=""

# 1. 检测Conda环境
if command -v conda &> /dev/null; then
    if [ -f "${PROJECT_ROOT}/environment.yml" ]; then
        CONDA_ENV_NAME=$(grep "^name:" "${PROJECT_ROOT}/environment.yml" | awk '{print $2}')
        if conda env list | grep -q "^${CONDA_ENV_NAME} "; then
            ENV_TYPE="conda"
            CONDA_BIN=$(which conda)
            PYTHON_CMD="$CONDA_BIN run -n $CONDA_ENV_NAME python"
            echo -e "${GREEN}✓ 检测到Conda环境: $CONDA_ENV_NAME${NC}"
        fi
    fi
fi

# 2. 如果没有找到Conda环境，检查virtualenv
if [ -z "$ENV_TYPE" ]; then
    VENV_PATH="${PROJECT_ROOT}/venv"
    if [ -f "${VENV_PATH}/bin/python" ]; then
        ENV_TYPE="venv"
        PYTHON_CMD="${VENV_PATH}/bin/python"
        echo -e "${GREEN}✓ 检测到Virtualenv环境${NC}"
    fi
fi

# 3. 如果都没有找到，询问用户
if [ -z "$ENV_TYPE" ]; then
    echo -e "${YELLOW}未检测到Python环境，请选择：${NC}"
    echo "  1) Conda环境"
    echo "  2) Virtualenv环境"
    read -p "请选择 [1-2]: " env_choice

    case $env_choice in
        1)
            ENV_TYPE="conda"
            read -p "Conda环境名称: " CONDA_ENV_NAME
            CONDA_BIN=$(which conda)
            PYTHON_CMD="$CONDA_BIN run -n $CONDA_ENV_NAME python"
            ;;
        2)
            ENV_TYPE="venv"
            read -p "Virtualenv路径 [${PROJECT_ROOT}/venv]: " input_venv
            VENV_PATH=${input_venv:-${PROJECT_ROOT}/venv}
            PYTHON_CMD="${VENV_PATH}/bin/python"
            ;;
        *)
            echo -e "${RED}无效选择${NC}"
            exit 1
            ;;
    esac
fi

echo ""
echo -e "${YELLOW}请提供以下信息：${NC}"
read -p "项目根目录 [${PROJECT_ROOT}]: " input_root
PROJECT_ROOT=${input_root:-$PROJECT_ROOT}

read -p "用户名 [$(whoami)]: " input_user
USERNAME=${input_user:-$(whoami)}

echo ""
echo -e "${YELLOW}配置信息：${NC}"
echo "  项目根目录: $PROJECT_ROOT"
echo "  运行用户: $USERNAME"
echo "  环境类型: $ENV_TYPE"
if [ "$ENV_TYPE" = "conda" ]; then
    echo "  Conda环境: $CONDA_ENV_NAME"
    echo "  Python命令: $PYTHON_CMD"
else
    echo "  虚拟环境: $VENV_PATH"
    echo "  Python命令: $PYTHON_CMD"
fi
echo ""

# 生成配置文件
TMP_SERVICE="/tmp/futures-price-update.service"
TMP_TIMER="/tmp/futures-price-update.timer"

# 替换占位符
# 注意：需要转义特殊字符以支持conda run命令
ESCAPED_PYTHON_CMD=$(echo "$PYTHON_CMD" | sed 's/\//\\\//g')
sed -e "s|YOUR_USERNAME|$USERNAME|g" \
    -e "s|/path/to/crypto_exchange_news_crawler|$PROJECT_ROOT|g" \
    -e "s|/path/to/crypto_exchange_news_crawler/venv/bin/python|$PYTHON_CMD|g" \
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
