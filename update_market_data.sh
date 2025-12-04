#!/usr/bin/env bash

################################################################################
# 市场数据更新脚本
# Market Data Update Script
#
# 功能：批量更新不同周期的K线数据缓存
# 用途：筛选系统数据准备
#
# 使用方法：
#   ./update_market_data.sh                    # 默认执行，无成交量过滤
#   ./update_market_data.sh --min-volume 50M   # 添加最小成交量过滤
#
# 注意：必须使用bash执行，不要用sh！
#   正确: ./update_market_data.sh 或 bash update_market_data.sh
#   错误: sh update_market_data.sh
#
# 作者：Auto-generated
# 日期：2025-12-04
################################################################################

# 检查是否使用bash
if [ -z "$BASH_VERSION" ]; then
    echo "错误: 此脚本需要bash执行，请使用以下命令:"
    echo "  ./update_market_data.sh"
    echo "  或"
    echo "  bash update_market_data.sh"
    echo ""
    echo "不要使用: sh update_market_data.sh"
    exit 1
fi

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    printf "${BLUE}[INFO]${NC} %s - %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

log_success() {
    printf "${GREEN}[SUCCESS]${NC} %s - %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

log_warning() {
    printf "${YELLOW}[WARNING]${NC} %s - %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

log_error() {
    printf "${RED}[ERROR]${NC} %s - %s\n" "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

# 分隔线
print_separator() {
    echo "========================================================================"
}

# 检查Python环境
check_python() {
    if ! command -v python &> /dev/null; then
        log_error "Python未找到，请确保Python已安装并在PATH中"
        exit 1
    fi

    local python_version=$(python --version 2>&1)
    log_info "使用Python: $python_version"
}

# 检查manage.py存在
check_manage_py() {
    if [ ! -f "manage.py" ]; then
        log_error "manage.py未找到，请在项目根目录运行此脚本"
        exit 1
    fi
    log_success "找到manage.py"
}

# 解析命令行参数
MIN_VOLUME_ARG=""
if [ "$1" == "--min-volume" ] && [ -n "$2" ]; then
    MIN_VOLUME_ARG="--min-volume $2"
    log_info "启用成交量过滤: $2"
fi

# 显示脚本信息
print_separator
printf "${GREEN}市场数据更新脚本${NC}\n"
printf "开始时间: %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
print_separator
echo ""

# 环境检查
log_info "检查运行环境..."
check_python
check_manage_py
echo ""

# 记录开始时间
START_TIME=$(date +%s)

# 更新任务列表（避免使用关联数组，改用两个平行数组）
# 任务名称
TASK_NAMES=(
    "4h K线"
    "1分钟K线"
    "1小时K线"
    "日线K线"
)

# 任务参数
TASK_PARAMS=(
    "--warmup-klines --interval 4h --limit 300"
    "--warmup-klines --interval 1m --limit 1000"
    "--warmup-klines --interval 1h --limit 200"
    "--warmup-klines --interval 1d --limit 50"
)

# 统计变量
TOTAL_TASKS=${#TASK_NAMES[@]}
SUCCESS_COUNT=0
FAILED_COUNT=0
FAILED_TASKS=()

# 执行更新任务
log_info "开始执行 $TOTAL_TASKS 个更新任务..."
echo ""

for i in "${!TASK_NAMES[@]}"; do
    task_name="${TASK_NAMES[$i]}"
    task_params="${TASK_PARAMS[$i]}"
    task_num=$((i + 1))

    print_separator
    log_info "[$task_num/$TOTAL_TASKS] 更新 $task_name"
    print_separator

    # 构建完整命令
    cmd="python manage.py update_market_data $task_params $MIN_VOLUME_ARG"
    log_info "执行命令: $cmd"
    echo ""

    # 执行命令
    task_start=$(date +%s)

    if eval $cmd; then
        task_end=$(date +%s)
        task_duration=$((task_end - task_start))
        log_success "[$task_num/$TOTAL_TASKS] $task_name 更新完成 (耗时: ${task_duration}秒)"
        ((SUCCESS_COUNT++))
    else
        task_end=$(date +%s)
        task_duration=$((task_end - task_start))
        log_error "[$task_num/$TOTAL_TASKS] $task_name 更新失败 (耗时: ${task_duration}秒)"
        ((FAILED_COUNT++))
        FAILED_TASKS+=("$task_name")
    fi

    echo ""
done

# 计算总耗时
END_TIME=$(date +%s)
TOTAL_DURATION=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_DURATION / 60))
SECONDS=$((TOTAL_DURATION % 60))

# 显示缓存统计
print_separator
log_info "查询K线缓存统计..."
print_separator
python manage.py cache_stats
echo ""

# 输出执行总结
print_separator
printf "${GREEN}执行总结${NC}\n"
print_separator
printf "总任务数: %s\n" "$TOTAL_TASKS"
printf "${GREEN}成功任务: %s${NC}\n" "$SUCCESS_COUNT"
if [ $FAILED_COUNT -gt 0 ]; then
    printf "${RED}失败任务: %s${NC}\n" "$FAILED_COUNT"
    printf "${RED}失败列表:${NC}\n"
    for failed_task in "${FAILED_TASKS[@]}"; do
        printf "  ${RED}✗${NC} %s\n" "$failed_task"
    done
else
    printf "${GREEN}失败任务: 0${NC}\n"
fi
printf "总耗时: %s分%s秒\n" "$MINUTES" "$SECONDS"
printf "结束时间: %s\n" "$(date '+%Y-%m-%d %H:%M:%S')"
print_separator

# 退出码
if [ $FAILED_COUNT -eq 0 ]; then
    echo ""
    log_success "所有更新任务执行成功！✅"
    echo ""
    log_info "💡 下一步: 运行筛选命令"
    echo "   python manage.py screen_simple --min-volume 100000000 --top-n 20"
    echo ""
    exit 0
else
    echo ""
    log_warning "部分任务执行失败，请检查错误信息"
    echo ""
    exit 1
fi
