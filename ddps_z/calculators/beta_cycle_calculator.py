"""
β宏观周期计算器 (Beta Cycle Calculator)

基于状态机的实时周期标记，识别市场的强势上涨/下跌/震荡阶段。

核心原则：
- 当前K线只能根据历史和自身状态计算，不修改历史标记
- 实时标记，无回溯

状态转换图:
    idle ──(β>600且增加)──► bull_warning ──(β>1000)──► bull_strong ──(β≤0)──► idle
    idle ──(β<-600且减少)──► bear_warning ──(β<-1000)──► bear_strong ──(β≥0)──► idle

Related:
    - PRD: docs/iterations/018-beta-cycle-indicator/prd.md
    - Architecture: docs/iterations/018-beta-cycle-indicator/architecture.md
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings

logger = logging.getLogger(__name__)


# 周期状态标签映射
PHASE_LABELS = {
    'consolidation': '震荡',
    'bull_warning': '上涨预警',
    'bull_strong': '强势上涨',
    'bear_warning': '下跌预警',
    'bear_strong': '强势下跌',
}

# 周期状态颜色映射（Bootstrap颜色类）
PHASE_COLORS = {
    'consolidation': 'secondary',
    'bull_warning': 'success',  # 浅绿
    'bull_strong': 'success',   # 绿
    'bear_warning': 'danger',   # 浅红
    'bear_strong': 'danger',    # 红
}


class BetaCycleCalculator:
    """
    β宏观周期计算器 - 基于状态机的实时标记

    状态定义:
    - consolidation: 震荡期（默认状态）
    - bull_warning: 上涨预警 (β > 600 且增加)
    - bull_strong: 强势上涨 (已确认 β > 1000)
    - bear_warning: 下跌预警 (β < -600 且减少)
    - bear_strong: 强势下跌 (已确认 β < -1000)

    阈值说明:
    - 配置中的阈值是前端显示值（×100）
    - 原始β值需要乘以100后与阈值比较
    """

    def __init__(self, thresholds: Optional[Dict[str, int]] = None):
        """
        初始化周期计算器

        Args:
            thresholds: 可选的阈值配置，格式:
                {
                    'bull_warning': 600,
                    'bull_strong': 1000,
                    'bear_warning': -600,
                    'bear_strong': -1000,
                    'cycle_end': 0,
                }
        """
        if thresholds is None:
            thresholds = settings.DDPS_CONFIG.get('BETA_CYCLE_THRESHOLDS', {})

        self.thresholds = {
            'bull_warning': thresholds.get('bull_warning', 600),
            'bull_strong': thresholds.get('bull_strong', 1000),
            'bear_warning': thresholds.get('bear_warning', -600),
            'bear_strong': thresholds.get('bear_strong', -1000),
            'cycle_end': thresholds.get('cycle_end', 0),
        }

        # 内部状态（每次 calculate 调用时重置）
        self._reset_state()

    def _reset_state(self):
        """重置内部状态"""
        self.state = 'consolidation'  # 当前状态
        self.cycle_start_idx = None   # 当前周期开始的索引
        self.confirmed = False        # 是否已确认（达到强势阈值）
        self.max_beta_in_cycle = None # 周期内的极值β

    def _beta_to_display(self, beta: float) -> float:
        """将原始β值转换为显示值（×100）"""
        return beta * 100

    def _transition_state(
        self,
        idx: int,
        beta_display: float,
        prev_beta_display: Optional[float]
    ) -> str:
        """
        根据当前β值和状态转换规则，计算下一个状态

        Args:
            idx: 当前K线索引
            beta_display: 当前β值（显示值）
            prev_beta_display: 前一根K线的β值（显示值）

        Returns:
            新状态
        """
        bull_warning = self.thresholds['bull_warning']
        bull_strong = self.thresholds['bull_strong']
        bear_warning = self.thresholds['bear_warning']
        bear_strong = self.thresholds['bear_strong']
        cycle_end = self.thresholds['cycle_end']

        # 判断β是否在增加/减少
        beta_increasing = prev_beta_display is not None and beta_display > prev_beta_display
        beta_decreasing = prev_beta_display is not None and beta_display < prev_beta_display

        # 状态机转换逻辑
        if self.state == 'consolidation':
            # 从震荡期进入上涨预警
            if beta_display > bull_warning and beta_increasing:
                self.state = 'bull_warning'
                self.cycle_start_idx = idx
                self.confirmed = False
                self.max_beta_in_cycle = beta_display
            # 从震荡期进入下跌预警
            elif beta_display < bear_warning and beta_decreasing:
                self.state = 'bear_warning'
                self.cycle_start_idx = idx
                self.confirmed = False
                self.max_beta_in_cycle = beta_display  # 下跌时记录最小值

        elif self.state == 'bull_warning':
            # 确认强势上涨
            if beta_display > bull_strong:
                self.state = 'bull_strong'
                self.confirmed = True
            # 周期结束（未确认）
            elif beta_display <= cycle_end:
                self.state = 'consolidation'
                self.cycle_start_idx = None
                self.confirmed = False
                self.max_beta_in_cycle = None
            # 更新周期内最大β
            if self.max_beta_in_cycle is not None:
                self.max_beta_in_cycle = max(self.max_beta_in_cycle, beta_display)

        elif self.state == 'bull_strong':
            # 周期结束
            if beta_display <= cycle_end:
                self.state = 'consolidation'
                self.cycle_start_idx = None
                self.confirmed = False
                self.max_beta_in_cycle = None
            # 更新周期内最大β
            elif self.max_beta_in_cycle is not None:
                self.max_beta_in_cycle = max(self.max_beta_in_cycle, beta_display)

        elif self.state == 'bear_warning':
            # 确认强势下跌
            if beta_display < bear_strong:
                self.state = 'bear_strong'
                self.confirmed = True
            # 周期结束（未确认）
            elif beta_display >= cycle_end:
                self.state = 'consolidation'
                self.cycle_start_idx = None
                self.confirmed = False
                self.max_beta_in_cycle = None
            # 更新周期内最小β（取绝对值更大的负数）
            if self.max_beta_in_cycle is not None:
                self.max_beta_in_cycle = min(self.max_beta_in_cycle, beta_display)

        elif self.state == 'bear_strong':
            # 周期结束
            if beta_display >= cycle_end:
                self.state = 'consolidation'
                self.cycle_start_idx = None
                self.confirmed = False
                self.max_beta_in_cycle = None
            # 更新周期内最小β
            elif self.max_beta_in_cycle is not None:
                self.max_beta_in_cycle = min(self.max_beta_in_cycle, beta_display)

        return self.state

    def calculate(
        self,
        beta_list: List[float],
        timestamps: List[int],
        prices: List[float],
        interval_hours: float = 4.0
    ) -> Tuple[List[str], Dict[str, Any]]:
        """
        计算每根K线的周期标记

        Args:
            beta_list: β值序列（原始值，非显示值）
            timestamps: 时间戳序列（毫秒）
            prices: 价格序列（收盘价）
            interval_hours: K线周期（小时），默认4小时

        Returns:
            (cycle_phases, current_cycle)
            - cycle_phases: 每根K线的周期标记列表
            - current_cycle: 当前周期统计信息
        """
        n = len(beta_list)
        if n == 0:
            return [], self._empty_current_cycle()

        if len(timestamps) != n or len(prices) != n:
            logger.error("输入序列长度不一致")
            return ['consolidation'] * n, self._empty_current_cycle()

        # 重置状态
        self._reset_state()

        # 存储每根K线的周期标记
        cycle_phases = []

        # 遍历每根K线，按顺序计算状态
        prev_beta_display = None
        for i in range(n):
            beta = beta_list[i]

            # 处理无效β值
            if beta is None or (isinstance(beta, float) and (beta != beta)):  # NaN check
                cycle_phases.append('consolidation')
                continue

            beta_display = self._beta_to_display(beta)

            # 状态转换
            self._transition_state(i, beta_display, prev_beta_display)

            # 记录当前状态
            cycle_phases.append(self.state)

            # 更新前一个β值
            prev_beta_display = beta_display

        # 计算当前周期统计
        current_cycle = self._calculate_current_cycle(
            cycle_phases, beta_list, timestamps, prices, interval_hours
        )

        return cycle_phases, current_cycle

    def _empty_current_cycle(self) -> Dict[str, Any]:
        """返回空的当前周期统计"""
        return {
            'phase': 'consolidation',
            'phase_label': PHASE_LABELS['consolidation'],
            'phase_color': PHASE_COLORS['consolidation'],
            'duration_bars': 0,
            'duration_hours': 0,
            'start_time': None,
            'start_price': None,
            'current_beta': None,
            'max_beta': None,
        }

    def _calculate_current_cycle(
        self,
        cycle_phases: List[str],
        beta_list: List[float],
        timestamps: List[int],
        prices: List[float],
        interval_hours: float
    ) -> Dict[str, Any]:
        """
        计算当前周期的统计信息

        Returns:
            {
                'phase': str,           # 当前周期状态
                'phase_label': str,     # 中文标签
                'phase_color': str,     # Bootstrap颜色类
                'duration_bars': int,   # 持续K线数
                'duration_hours': float, # 持续小时数
                'start_time': str,      # 周期开始时间
                'start_price': float,   # 周期开始价格
                'current_beta': float,  # 当前β值（显示值）
                'max_beta': float,      # 周期内极值β
            }
        """
        if not cycle_phases:
            return self._empty_current_cycle()

        current_phase = cycle_phases[-1]
        current_beta = None
        if beta_list and beta_list[-1] is not None:
            current_beta = round(self._beta_to_display(beta_list[-1]), 2)

        # 找到当前周期开始的位置（从后往前找连续相同状态的起点）
        cycle_start_idx = len(cycle_phases) - 1
        for i in range(len(cycle_phases) - 2, -1, -1):
            if cycle_phases[i] != current_phase:
                cycle_start_idx = i + 1
                break
            # 如果遍历到最开始都没找到不同状态，说明整个范围都是同一个周期
            if i == 0:
                cycle_start_idx = 0

        # 计算持续时间
        duration_bars = len(cycle_phases) - cycle_start_idx
        duration_hours = duration_bars * interval_hours

        # 获取周期开始时间和价格
        start_time = None
        start_price = None
        if cycle_start_idx < len(timestamps):
            start_ts = timestamps[cycle_start_idx]
            start_time = datetime.fromtimestamp(
                start_ts / 1000, tz=timezone.utc
            ).strftime('%Y-%m-%d %H:%M')
            start_price = prices[cycle_start_idx]

        # 如果当前是震荡期，不需要计算极值β
        if current_phase == 'consolidation':
            return {
                'phase': current_phase,
                'phase_label': PHASE_LABELS[current_phase],
                'phase_color': PHASE_COLORS[current_phase],
                'duration_bars': duration_bars,
                'duration_hours': round(duration_hours, 1),
                'start_time': start_time,
                'start_price': start_price,
                'current_beta': current_beta,
                'max_beta': None,
            }

        # 计算周期内的极值β（仅对非震荡期）
        max_beta = None
        if cycle_start_idx < len(beta_list):
            cycle_betas = [
                self._beta_to_display(b)
                for b in beta_list[cycle_start_idx:]
                if b is not None
            ]
            if cycle_betas:
                if current_phase in ('bull_warning', 'bull_strong'):
                    max_beta = round(max(cycle_betas), 2)
                elif current_phase in ('bear_warning', 'bear_strong'):
                    max_beta = round(min(cycle_betas), 2)

        return {
            'phase': current_phase,
            'phase_label': PHASE_LABELS[current_phase],
            'phase_color': PHASE_COLORS[current_phase],
            'duration_bars': duration_bars,
            'duration_hours': round(duration_hours, 1),
            'start_time': start_time,
            'start_price': start_price,
            'current_beta': current_beta,
            'max_beta': max_beta,
        }
