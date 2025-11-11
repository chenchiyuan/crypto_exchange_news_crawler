#!/bin/bash

###############################################################################
# Cron定时任务设置脚本
# 用途：自动配置合约价格定期更新的cron任务
###############################################################################

set -e  # 出错即停止

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 获取项目根目录（脚本所在目录的父目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MANAGE_PY="${PROJECT_ROOT}/manage.py"

# Cron任务标识（用于识别和删除）
CRON_MARKER="# futures_price_update"

echo -e "${GREEN}==================================================${NC}"
echo -e "${GREEN}  合约价格定期更新 - Cron任务配置${NC}"
echo -e "${GREEN}==================================================${NC}"
echo ""

# 检测Python环境类型
ENV_TYPE=""
PYTHON_BIN=""
CONDA_ENV_NAME=""

# 1. 检测Conda环境
if command -v conda &> /dev/null; then
    # 尝试从environment.yml读取环境名称
    if [ -f "${PROJECT_ROOT}/environment.yml" ]; then
        CONDA_ENV_NAME=$(grep "^name:" "${PROJECT_ROOT}/environment.yml" | awk '{print $2}')
        # 验证环境是否存在
        if conda env list | grep -q "^${CONDA_ENV_NAME} "; then
            ENV_TYPE="conda"
            # 获取conda环境的Python路径
            CONDA_PREFIX=$(conda env list | grep "^${CONDA_ENV_NAME} " | awk '{print $NF}')
            PYTHON_BIN="${CONDA_PREFIX}/bin/python"
            echo -e "${GREEN}✓ 检测到Conda环境: $CONDA_ENV_NAME${NC}"
        fi
    fi
fi

# 2. 如果没有找到Conda环境，检查virtualenv
if [ -z "$ENV_TYPE" ]; then
    VENV_PATH="${PROJECT_ROOT}/venv"
    if [ -f "${VENV_PATH}/bin/python" ]; then
        ENV_TYPE="venv"
        PYTHON_BIN="${VENV_PATH}/bin/python"
        echo -e "${GREEN}✓ 检测到Virtualenv环境${NC}"
    fi
fi

# 3. 如果都没有找到，报错
if [ -z "$ENV_TYPE" ]; then
    echo -e "${RED}错误: 未找到Python环境${NC}"
    echo ""
    echo "请先创建环境："
    echo "  Conda: conda env create -f environment.yml"
    echo "  Venv: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# 检查manage.py
if [ ! -f "$MANAGE_PY" ]; then
    echo -e "${RED}错误: 未找到manage.py: $MANAGE_PY${NC}"
    exit 1
fi

# 显示配置信息
echo ""
echo -e "${YELLOW}配置信息：${NC}"
echo "  项目根目录: $PROJECT_ROOT"
echo "  环境类型: $ENV_TYPE"
if [ "$ENV_TYPE" = "conda" ]; then
    echo "  Conda环境: $CONDA_ENV_NAME"
fi
echo "  Python路径: $PYTHON_BIN"
echo "  管理脚本: $MANAGE_PY"
echo ""

# 询问更新频率
echo -e "${YELLOW}请选择更新频率：${NC}"
echo "  1) 每5分钟"
echo "  2) 每10分钟 (推荐)"
echo "  3) 每15分钟"
echo "  4) 每30分钟"
echo "  5) 每小时"
echo "  6) 自定义"
echo ""
read -p "请选择 [1-6]: " choice

case $choice in
    1)
        CRON_SCHEDULE="*/5 * * * *"
        FREQ_DESC="每5分钟"
        ;;
    2)
        CRON_SCHEDULE="*/10 * * * *"
        FREQ_DESC="每10分钟"
        ;;
    3)
        CRON_SCHEDULE="*/15 * * * *"
        FREQ_DESC="每15分钟"
        ;;
    4)
        CRON_SCHEDULE="*/30 * * * *"
        FREQ_DESC="每30分钟"
        ;;
    5)
        CRON_SCHEDULE="0 * * * *"
        FREQ_DESC="每小时"
        ;;
    6)
        echo ""
        echo "Cron时间格式: 分 时 日 月 周"
        echo "例如: '*/10 * * * *' = 每10分钟"
        read -p "请输入cron时间表达式: " CRON_SCHEDULE
        FREQ_DESC="自定义: $CRON_SCHEDULE"
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

# 构建cron命令（根据环境类型）
if [ "$ENV_TYPE" = "conda" ]; then
    # Conda环境：使用conda run命令
    CRON_COMMAND="cd $PROJECT_ROOT && $(which conda) run -n $CONDA_ENV_NAME python $MANAGE_PY update_futures_prices --quiet >> ${PROJECT_ROOT}/logs/cron.log 2>&1"
else
    # Virtualenv环境：直接使用Python路径
    CRON_COMMAND="cd $PROJECT_ROOT && $PYTHON_BIN $MANAGE_PY update_futures_prices --quiet >> ${PROJECT_ROOT}/logs/cron.log 2>&1"
fi
CRON_ENTRY="$CRON_SCHEDULE $CRON_COMMAND $CRON_MARKER"

echo ""
echo -e "${YELLOW}将要添加的Cron任务：${NC}"
echo "  频率: $FREQ_DESC"
echo "  命令: $CRON_COMMAND"
echo ""

# 确认
read -p "确认添加此cron任务? [y/N]: " confirm
if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "已取消"
    exit 0
fi

# 检查是否已存在相同任务
if crontab -l 2>/dev/null | grep -q "$CRON_MARKER"; then
    echo -e "${YELLOW}警告: 发现已存在的定时任务${NC}"
    echo "正在删除旧任务..."
    crontab -l 2>/dev/null | grep -v "$CRON_MARKER" | crontab -
fi

# 添加新任务
echo "正在添加cron任务..."
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

# 验证
echo ""
echo -e "${GREEN}✅ Cron任务已成功添加！${NC}"
echo ""
echo -e "${YELLOW}当前所有cron任务：${NC}"
crontab -l
echo ""
echo -e "${YELLOW}提示：${NC}"
echo "  - 日志文件: ${PROJECT_ROOT}/logs/cron.log"
echo "  - 详细日志: ${PROJECT_ROOT}/logs/futures_updates.log"
echo "  - 查看任务: crontab -l"
echo "  - 删除任务: ./scripts/setup_cron.sh --remove"
echo "  - 查看日志: tail -f ${PROJECT_ROOT}/logs/cron.log"
echo ""
