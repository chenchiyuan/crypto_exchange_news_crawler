"""
信号计算器 (Signal Calculator)

负责计算所有DDPS-Z策略的触发信号：
- 策略1: EMA斜率未来预测做多
- 策略2: 惯性下跌中值突破做多
- 策略3: EMA斜率未来预测做空
- 策略4: 惯性中值突破做空 + EMA斜率预测
- 策略6: 震荡区间突破做多
- 策略7: 动态周期自适应做多

Related:
    - PRD: docs/iterations/015-short-strategies/prd.md
    - Architecture: docs/iterations/015-short-strategies/architecture.md
    - 原PRD: docs/iterations/011-buy-signal-markers/prd.md
    - TASK: TASK-015-006, TASK-021-003, TASK-021-004
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

from ddps_z.calculators.ema_calculator import EMACalculator
from ddps_z.calculators.beta_cycle_calculator import BetaCycleCalculator

logger = logging.getLogger(__name__)


class SignalError(Exception):
    """信号计算异常基类"""
    pass


class DataInsufficientError(SignalError):
    """数据不足异常 (ERR_DATA_INSUFFICIENT)"""
    pass


class InvalidBetaError(SignalError):
    """无效β序列异常 (ERR_INVALID_BETA)"""
    pass


class InvalidKlineError(SignalError):
    """无效K线数据异常 (ERR_INVALID_KLINE)"""
    pass


# 向后兼容别名
BuySignalError = SignalError


class SignalCalculator:
    """
    信号计算器 - 计算策略1~7的触发信号

    做多策略:
        策略1: EMA斜率未来预测买入
            触发条件: K线low < P5 且 未来6周期EMA预测价格 > 当前close
            公式: 未来EMA = EMA[t] + (β × 6)

        策略2: 惯性下跌中值突破买入
            前置条件: β < 0（下跌趋势）
            触发条件: 惯性mid < P5 且 K线low < (惯性mid + P5)/2

        策略6: 震荡区间突破买入
            前置条件: 当前处于震荡阶段（consolidation）
            触发条件: K线low <= P5

        策略7: 动态周期自适应买入
            触发条件: K线low <= P5（无周期限制）
            特点: 买入信号简单，卖出策略根据周期动态选择

    做空策略:
        策略3: EMA斜率未来预测做空
            触发条件: K线high >= P95 且 未来6周期EMA预测价格 < 当前close
            公式: 未来EMA = EMA[t] + (β × 6)

        策略4: 惯性中值突破做空 + EMA斜率预测
            触发条件:
                1. K线high > (惯性mid + P95)/2（价格突破压力位）
                2. 未来6周期EMA预测价格 < 当前close（趋势向下）
    """

    # 策略配置
    FUTURE_PERIODS = 6  # 预测未来周期数

    # 策略ID和名称
    STRATEGY_1_ID = 'strategy_1'
    STRATEGY_1_NAME = 'EMA斜率未来预测'
    STRATEGY_2_ID = 'strategy_2'
    STRATEGY_2_NAME = '惯性下跌中值突破'
    STRATEGY_3_ID = 'strategy_3'
    STRATEGY_3_NAME = 'EMA斜率未来预测做空'
    STRATEGY_4_ID = 'strategy_4'
    STRATEGY_4_NAME = '惯性上涨中值突破做空'
    STRATEGY_6_ID = 'strategy_6'
    STRATEGY_6_NAME = '震荡区间突破'
    STRATEGY_7_ID = 'strategy_7'
    STRATEGY_7_NAME = '动态周期自适应'

    def __init__(self):
        """初始化信号计算器"""
        pass

    def _validate_inputs(
        self,
        klines: List[Dict],
        ema_series: np.ndarray,
        p5_series: np.ndarray,
        beta_series: np.ndarray,
        inertia_mid_series: np.ndarray,
        p95_series: Optional[np.ndarray] = None
    ) -> None:
        """
        验证输入数据

        Raises:
            DataInsufficientError: 数据不足或长度不一致
            InvalidBetaError: β序列包含NaN或Inf
            InvalidKlineError: K线数据缺少必要字段
        """
        # 检查K线数据
        if not klines:
            raise DataInsufficientError("K线数据为空")

        n = len(klines)

        # 检查序列长度一致性
        if len(ema_series) != n:
            raise DataInsufficientError(
                f"EMA序列长度({len(ema_series)})与K线数量({n})不一致"
            )
        if len(p5_series) != n:
            raise DataInsufficientError(
                f"P5序列长度({len(p5_series)})与K线数量({n})不一致"
            )
        if len(beta_series) != n:
            raise DataInsufficientError(
                f"β序列长度({len(beta_series)})与K线数量({n})不一致"
            )
        if len(inertia_mid_series) != n:
            raise DataInsufficientError(
                f"惯性mid序列长度({len(inertia_mid_series)})与K线数量({n})不一致"
            )
        if p95_series is not None and len(p95_series) != n:
            raise DataInsufficientError(
                f"P95序列长度({len(p95_series)})与K线数量({n})不一致"
            )

        # 检查β序列是否包含Inf
        if np.any(np.isinf(beta_series)):
            raise InvalidBetaError("β序列包含Inf值")

        # 检查K线必要字段
        required_fields = ['open_time', 'high', 'low', 'close']
        for i, kline in enumerate(klines):
            for field in required_fields:
                if field not in kline:
                    raise InvalidKlineError(
                        f"K线索引{i}缺少必要字段: {field}"
                    )

    def _calculate_strategy1(
        self,
        kline: Dict,
        ema: float,
        p5: float,
        beta: float
    ) -> Dict[str, Any]:
        """
        计算策略1: EMA斜率未来预测买入

        触发条件:
            1. K线low < P5（价格跌破P5静态阈值）
            2. 未来6周期EMA预测价格 > 当前close（趋势向好）

        Args:
            kline: K线数据
            ema: 当前EMA值
            p5: 当前P5阈值
            beta: 当前β斜率

        Returns:
            策略1触发信息字典
        """
        low = float(kline['low'])
        close = float(kline['close'])

        # 跳过无效数据
        if np.isnan(ema) or np.isnan(p5) or np.isnan(beta):
            return {
                'id': self.STRATEGY_1_ID,
                'name': self.STRATEGY_1_NAME,
                'triggered': False,
            }

        # 计算未来6周期EMA预测
        future_ema = ema + (beta * self.FUTURE_PERIODS)

        # 判断触发条件
        condition1 = low < p5           # 价格跌破P5
        condition2 = future_ema > close  # 未来EMA高于当前收盘价

        triggered = condition1 and condition2

        result = {
            'id': self.STRATEGY_1_ID,
            'name': self.STRATEGY_1_NAME,
            'triggered': triggered,
        }

        if triggered:
            result['reason'] = (
                f"价格跌破P5 (${p5:,.2f})，"
                f"但未来{self.FUTURE_PERIODS}周期EMA预测 (${future_ema:,.2f}) "
                f"高于当前收盘价"
            )
            result['details'] = {
                'current_low': low,
                'p5': p5,
                'future_ema': future_ema,
                'current_close': close,
                'beta': beta,
            }

        return result

    def _calculate_strategy2(
        self,
        kline: Dict,
        p5: float,
        beta: float,
        inertia_mid: float
    ) -> Dict[str, Any]:
        """
        计算策略2: 惯性下跌中值突破买入

        触发条件:
            1. β < 0（下跌趋势）
            2. 惯性mid < P5（惯性预测低于P5阈值）
            3. K线low < (惯性mid + P5) / 2（价格跌破中值线）

        Args:
            kline: K线数据
            p5: 当前P5阈值
            beta: 当前β斜率
            inertia_mid: 当前惯性mid值

        Returns:
            策略2触发信息字典
        """
        low = float(kline['low'])

        # 跳过无效数据
        if np.isnan(p5) or np.isnan(beta) or np.isnan(inertia_mid):
            return {
                'id': self.STRATEGY_2_ID,
                'name': self.STRATEGY_2_NAME,
                'triggered': False,
            }

        result = {
            'id': self.STRATEGY_2_ID,
            'name': self.STRATEGY_2_NAME,
            'triggered': False,
        }

        # 前置条件: β < 0（下跌趋势）
        if beta >= 0:
            return result

        # 计算中值线
        mid_line = (inertia_mid + p5) / 2

        # 判断触发条件
        condition1 = inertia_mid < p5   # 惯性mid低于P5
        condition2 = low < mid_line     # 价格跌破中值线

        triggered = condition1 and condition2

        if triggered:
            result['triggered'] = True
            result['reason'] = (
                f"下跌惯性中，惯性mid (${inertia_mid:,.2f}) "
                f"低于P5，且价格跌破中值线 (${mid_line:,.2f})"
            )
            result['details'] = {
                'beta': beta,
                'inertia_mid': inertia_mid,
                'p5': p5,
                'mid_line': mid_line,
                'current_low': low,
            }

        return result

    def _calculate_strategy3(
        self,
        kline: Dict,
        ema: float,
        p95: float,
        beta: float
    ) -> Dict[str, Any]:
        """
        计算策略3: EMA斜率未来预测做空

        触发条件:
            1. K线high >= P95（价格触及P95上界）
            2. 未来6周期EMA预测价格 < 当前close（趋势向下）

        Args:
            kline: K线数据
            ema: 当前EMA值
            p95: 当前P95阈值
            beta: 当前β斜率

        Returns:
            策略3触发信息字典
        """
        high = float(kline['high'])
        close = float(kline['close'])

        # 跳过无效数据
        if np.isnan(ema) or np.isnan(p95) or np.isnan(beta):
            return {
                'id': self.STRATEGY_3_ID,
                'name': self.STRATEGY_3_NAME,
                'triggered': False,
            }

        # 计算未来6周期EMA预测
        future_ema = ema + (beta * self.FUTURE_PERIODS)

        # 判断触发条件
        condition1 = high >= p95          # 价格触及P95上界
        condition2 = future_ema < close   # 未来EMA低于当前收盘价

        triggered = condition1 and condition2

        result = {
            'id': self.STRATEGY_3_ID,
            'name': self.STRATEGY_3_NAME,
            'triggered': triggered,
        }

        if triggered:
            result['reason'] = (
                f"价格触及P95 (${p95:,.2f})，"
                f"且未来{self.FUTURE_PERIODS}周期EMA预测 (${future_ema:,.2f}) "
                f"低于当前收盘价"
            )
            result['details'] = {
                'current_high': high,
                'p95': p95,
                'future_ema': future_ema,
                'current_close': close,
                'beta': beta,
            }

        return result

    def _calculate_strategy4(
        self,
        kline: Dict,
        ema: float,
        p95: float,
        beta: float,
        inertia_mid: float,
        beta_99: Optional[float] = None,
        cycle_phase: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        计算策略4: 惯性中值突破做空

        🔧 Bug-023修复: 修正为使用inertia_mid而非inertia_upper
        🔧 优化: 添加未来EMA预测条件，增强做空信号可靠性
        🔧 迭代优化: 增加前置条件（非上涨区间 OR ema99斜率为负）
        🔧 简化优化: 主条件1改为直接判断价格突破P95

        触发条件:
            前置条件（满足其一）:
                - 当前处于非上涨区间（震荡/下跌）
                - ema99斜率为负
            主条件:
                1. kline['high'] > P95（价格突破P95上界）
                2. 未来6周期EMA预测价格 < 当前close（趋势向下）

        Args:
            kline: K线数据
            ema: 当前EMA值
            p95: 当前P95阈值
            beta: 当前β斜率
            inertia_mid: 当前惯性中值（保留参数以保持接口兼容）
            beta_99: EMA99斜率（可选）
            cycle_phase: 当前周期状态（可选）

        Returns:
            策略4触发信息字典
        """
        high = float(kline['high'])
        close = float(kline['close'])

        # 跳过无效数据
        if np.isnan(ema) or np.isnan(p95) or np.isnan(beta):
            return {
                'id': self.STRATEGY_4_ID,
                'name': self.STRATEGY_4_NAME,
                'triggered': False,
            }

        result = {
            'id': self.STRATEGY_4_ID,
            'name': self.STRATEGY_4_NAME,
            'triggered': False,
        }

        # === 前置条件判断（满足其一即可） ===
        precondition_met = False
        precondition_reason = ""

        # 条件1: 非上涨区间（震荡或下跌）
        non_bullish_phase = False
        if cycle_phase is not None:
            # 非上涨区间：排除bull_warning和bull_strong
            non_bullish_phase = cycle_phase not in ('bull_warning', 'bull_strong')
            if non_bullish_phase:
                precondition_reason = f"处于{cycle_phase}阶段（非上涨区间）"

        # 条件2: ema99斜率为负
        ema99_negative = False
        if beta_99 is not None and not np.isnan(beta_99):
            ema99_negative = beta_99 < 0
            if ema99_negative:
                if precondition_reason:
                    precondition_reason += f"且EMA99斜率为负({beta_99:.2f})"
                else:
                    precondition_reason = f"EMA99斜率为负({beta_99:.2f})"

        # 判断前置条件是否满足
        precondition_met = non_bullish_phase or ema99_negative

        # 如果前置条件不满足，直接返回
        if not precondition_met:
            return result

        # === 主条件判断 ===
        # 计算未来6周期EMA预测
        future_ema = ema + (beta * self.FUTURE_PERIODS)

        # 判断触发条件
        condition1 = high > p95                # 价格突破P95上界
        condition2 = future_ema < close        # 未来EMA低于当前收盘价

        triggered = condition1 and condition2

        if triggered:
            result['triggered'] = True
            result['reason'] = (
                f"✅ {precondition_reason}，"
                f"价格突破P95上界 (${p95:,.2f})，"
                f"且未来{self.FUTURE_PERIODS}周期EMA预测 (${future_ema:,.2f}) "
                f"低于当前收盘价"
            )
            result['details'] = {
                'p95': p95,
                'current_high': high,
                'future_ema': future_ema,
                'current_close': close,
                'beta': beta,
                'beta_99': beta_99,
                'cycle_phase': cycle_phase,
                'precondition': precondition_reason,
            }

        return result

    def _calculate_strategy6(
        self,
        kline: Dict,
        p5: float,
        cycle_phase: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        计算策略6: 震荡区间突破买入

        触发条件:
            前置条件: 当前处于震荡阶段（consolidation）
            主条件: K线low <= P5（价格触及支撑位）

        Args:
            kline: K线数据
            p5: 当前P5阈值
            cycle_phase: 当前周期状态（可选）

        Returns:
            策略6触发信息字典
        """
        low = float(kline['low'])
        close = float(kline['close'])

        # 跳过无效数据
        if np.isnan(p5):
            return {
                'id': 'strategy_6',
                'name': '震荡区间突破',
                'triggered': False,
            }

        result = {
            'id': 'strategy_6',
            'name': '震荡区间突破',
            'triggered': False,
        }

        # 前置条件: 处于震荡阶段
        if cycle_phase is None or cycle_phase != 'consolidation':
            return result

        # 主条件: 价格触及P5支撑位
        if low <= p5:
            result['triggered'] = True
            result['reason'] = (
                f"震荡期价格触及P5支撑位 (${p5:,.2f})"
            )
            result['details'] = {
                'cycle_phase': cycle_phase,
                'p5': p5,
                'current_low': low,
                'buy_price': close,
            }

        return result

    def _calculate_strategy7(
        self,
        kline: Dict,
        p5: float
    ) -> Dict[str, Any]:
        """
        计算策略7: 动态周期自适应买入

        🔧 TASK-021-003: 策略7核心逻辑
        🔧 关联功能点: FP-021-003
        🔧 关联迭代: 021 - 动态周期自适应策略

        触发条件:
            K线low <= P5（无周期限制，与策略6的关键差异）

        策略7的核心特点:
            - 买入信号: 简单的P5触及逻辑（任何周期都可触发）
            - 卖出策略: 动态根据周期选择Exit Condition
              - 震荡期: P95止盈 + 5%止损
              - 下跌期: EMA25回归 + 5%止损
              - 上涨期: Mid止盈 + 5%止损

        Args:
            kline: K线数据（必须包含'low', 'close'）
            p5: 当前P5阈值

        Returns:
            策略7触发信息字典，格式：
            {
                'id': 'strategy_7',
                'name': '动态周期自适应',
                'triggered': bool,
                'reason': str,  # 如果triggered=True
                'details': {
                    'p5': float,
                    'current_low': float,
                    'buy_price': float
                }
            }
        """
        low = float(kline['low'])
        close = float(kline['close'])

        # 跳过无效数据
        if np.isnan(p5):
            return {
                'id': 'strategy_7',
                'name': '动态周期自适应',
                'triggered': False,
            }

        result = {
            'id': 'strategy_7',
            'name': '动态周期自适应',
            'triggered': False,
        }

        # 主条件: 价格触及P5支撑位（无周期限制）
        if low <= p5:
            result['triggered'] = True
            result['reason'] = (
                f"价格触及P5支撑位 (${p5:,.2f})，触发动态周期自适应买入"
            )
            result['details'] = {
                'p5': p5,
                'current_low': low,
                'buy_price': close,
            }

        return result

    def calculate(
        self,
        klines: List[Dict],
        ema_series: np.ndarray,
        p5_series: np.ndarray,
        beta_series: np.ndarray,
        inertia_mid_series: np.ndarray,
        p95_series: Optional[np.ndarray] = None,
        enabled_strategies: List[int] = None
    ) -> Dict[str, List[Dict]]:
        """
        计算信号

        遍历每根K线，评估各策略的触发条件，
        返回做多信号和做空信号列表。

        Args:
            klines: K线OHLC数据列表，每个元素需包含:
                    open_time, high, low, close
            ema_series: EMA序列 (numpy array)
            p5_series: P5价格序列 (numpy array)
            beta_series: β斜率序列 (numpy array)
            inertia_mid_series: 惯性mid序列 (numpy array)
            p95_series: P95价格序列 (numpy array, 做空策略需要)
            enabled_strategies: 启用的策略ID列表，默认[1, 2]

        Returns:
            字典，包含:
            - long_signals: 做多信号列表
            - short_signals: 做空信号列表
            每个信号包含:
            - timestamp: int (毫秒时间戳)
            - kline_index: int (K线索引)
            - strategies: List[Dict] (策略触发信息)
            - price: float (开仓价格)
            - direction: str ('long' 或 'short')

        Raises:
            DataInsufficientError: 数据不足或长度不一致
            InvalidBetaError: β序列包含NaN或Inf
            InvalidKlineError: K线数据缺少必要字段
        """
        if enabled_strategies is None:
            enabled_strategies = [1, 2]

        logger.info(f"SignalCalculator.calculate 开始: enabled_strategies={enabled_strategies}, K线数={len(klines)}")

        # 验证输入
        self._validate_inputs(
            klines, ema_series, p5_series, beta_series, inertia_mid_series,
            p95_series if (3 in enabled_strategies or 4 in enabled_strategies) else None
        )

        # === 计算EMA99和beta_99（用于策略4优化） ===
        ema99_series = None
        beta99_series = None
        if 4 in enabled_strategies:
            try:
                # 提取收盘价序列
                prices = np.array([float(k['close']) for k in klines])

                # 计算EMA99
                ema99_calculator = EMACalculator(period=99)
                ema99_series = ema99_calculator.calculate_ema_series(prices)

                # 计算beta_99（EMA99的斜率）
                # beta = EMA[i] - EMA[i-1]
                beta99_series = np.full(len(ema99_series), np.nan)
                for i in range(1, len(ema99_series)):
                    if not np.isnan(ema99_series[i]) and not np.isnan(ema99_series[i-1]):
                        beta99_series[i] = ema99_series[i] - ema99_series[i-1]

                logger.info(f"EMA99和beta_99计算完成")
            except Exception as e:
                logger.warning(f"EMA99计算失败: {e}，将不使用EMA99条件")
                ema99_series = None
                beta99_series = None

        # === 计算β宏观周期状态（用于策略4、策略6） ===
        cycle_phases = None
        if 4 in enabled_strategies or 6 in enabled_strategies:
            try:
                # 提取时间戳和收盘价
                timestamps = []
                prices = []
                for k in klines:
                    ts = k['open_time']
                    if hasattr(ts, 'timestamp'):
                        timestamps.append(int(ts.timestamp() * 1000))
                    else:
                        timestamps.append(int(ts))
                    prices.append(float(k['close']))

                # 使用BetaCycleCalculator计算周期状态
                cycle_calculator = BetaCycleCalculator()
                cycle_phases, _ = cycle_calculator.calculate(
                    beta_list=beta_series.tolist(),
                    timestamps=timestamps,
                    prices=prices,
                    interval_hours=4.0
                )
                logger.info(f"β宏观周期计算完成: {len(cycle_phases)}个状态")

                # DEBUG: 输出周期分布统计
                from collections import Counter
                phase_counts = Counter(cycle_phases)
                logger.info(f"周期分布统计:")
                for phase, count in sorted(phase_counts.items()):
                    percentage = count / len(cycle_phases) * 100
                    logger.info(f"  {phase}: {count} ({percentage:.1f}%)")

            except Exception as e:
                logger.warning(f"周期状态计算失败: {e}，将不使用周期条件")
                cycle_phases = None

        long_signals = []
        short_signals = []

        # 判断是否需要做空策略
        need_short = 3 in enabled_strategies or 4 in enabled_strategies
        if need_short and p95_series is None:
            raise DataInsufficientError("做空策略需要P95序列")

        for i, kline in enumerate(klines):
            # 获取时间戳
            open_time = kline['open_time']
            if hasattr(open_time, 'timestamp'):
                timestamp = int(open_time.timestamp() * 1000)
            else:
                timestamp = int(open_time)

            # === 做多策略 ===
            strategy1_result = None
            strategy2_result = None
            strategy6_result = None
            strategy7_result = None

            if 1 in enabled_strategies:
                strategy1_result = self._calculate_strategy1(
                    kline=kline,
                    ema=ema_series[i],
                    p5=p5_series[i],
                    beta=beta_series[i]
                )

            if 2 in enabled_strategies:
                strategy2_result = self._calculate_strategy2(
                    kline=kline,
                    p5=p5_series[i],
                    beta=beta_series[i],
                    inertia_mid=inertia_mid_series[i]
                )

            if 6 in enabled_strategies:
                # 获取当前K线的cycle_phase
                current_cycle_phase = None
                if cycle_phases is not None and i < len(cycle_phases):
                    current_cycle_phase = cycle_phases[i]

                strategy6_result = self._calculate_strategy6(
                    kline=kline,
                    p5=p5_series[i],
                    cycle_phase=current_cycle_phase
                )

            if 7 in enabled_strategies:
                strategy7_result = self._calculate_strategy7(
                    kline=kline,
                    p5=p5_series[i]
                )

            # 检查做多策略是否触发
            long_triggered = (
                (strategy1_result and strategy1_result.get('triggered', False)) or
                (strategy2_result and strategy2_result.get('triggered', False)) or
                (strategy6_result and strategy6_result.get('triggered', False)) or
                (strategy7_result and strategy7_result.get('triggered', False))
            )

            if long_triggered:
                strategies = []
                if strategy1_result:
                    strategies.append(strategy1_result)
                if strategy2_result:
                    strategies.append(strategy2_result)
                if strategy6_result:
                    strategies.append(strategy6_result)
                if strategy7_result:
                    strategies.append(strategy7_result)

                signal = {
                    'timestamp': timestamp,
                    'kline_index': i,
                    'strategies': strategies,
                    'price': float(kline['close']),
                    'direction': 'long',
                    'buy_price': float(kline['close']),  # 向后兼容
                }
                long_signals.append(signal)

            # === 做空策略 ===
            if need_short:
                strategy3_result = None
                strategy4_result = None

                if 3 in enabled_strategies:
                    strategy3_result = self._calculate_strategy3(
                        kline=kline,
                        ema=ema_series[i],
                        p95=p95_series[i],
                        beta=beta_series[i]
                    )

                if 4 in enabled_strategies:
                    # 获取当前K线的beta_99和cycle_phase
                    current_beta99 = None
                    if beta99_series is not None and i < len(beta99_series):
                        current_beta99 = beta99_series[i]

                    current_cycle_phase = None
                    if cycle_phases is not None and i < len(cycle_phases):
                        current_cycle_phase = cycle_phases[i]

                    strategy4_result = self._calculate_strategy4(
                        kline=kline,
                        ema=ema_series[i],
                        p95=p95_series[i],
                        beta=beta_series[i],
                        inertia_mid=inertia_mid_series[i],
                        beta_99=current_beta99,
                        cycle_phase=current_cycle_phase
                    )

                # 检查做空策略是否触发
                short_triggered = (
                    (strategy3_result and strategy3_result.get('triggered', False)) or
                    (strategy4_result and strategy4_result.get('triggered', False))
                )

                if short_triggered:
                    strategies = []
                    if strategy3_result:
                        strategies.append(strategy3_result)
                    if strategy4_result:
                        strategies.append(strategy4_result)

                    signal = {
                        'timestamp': timestamp,
                        'kline_index': i,
                        'strategies': strategies,
                        'price': float(kline['close']),
                        'direction': 'short',
                    }
                    short_signals.append(signal)

        logger.info(
            f"信号计算完成: 共{len(klines)}根K线，"
            f"发现{len(long_signals)}个做多点，{len(short_signals)}个做空点"
        )

        return {
            'long_signals': long_signals,
            'short_signals': short_signals,
        }

    def calculate_buy_signals(
        self,
        klines: List[Dict],
        ema_series: np.ndarray,
        p5_series: np.ndarray,
        beta_series: np.ndarray,
        inertia_mid_series: np.ndarray
    ) -> List[Dict]:
        """
        计算买入信号（向后兼容接口）

        遍历每根K线，评估策略1和策略2的触发条件，
        只返回至少有一个策略触发的K线。

        这是原BuySignalCalculator.calculate()的兼容包装。

        Args:
            klines: K线OHLC数据列表
            ema_series: EMA序列 (numpy array)
            p5_series: P5价格序列 (numpy array)
            beta_series: β斜率序列 (numpy array)
            inertia_mid_series: 惯性mid序列 (numpy array)

        Returns:
            买入信号列表（与原接口格式一致）
        """
        result = self.calculate(
            klines=klines,
            ema_series=ema_series,
            p5_series=p5_series,
            beta_series=beta_series,
            inertia_mid_series=inertia_mid_series,
            enabled_strategies=[1, 2]
        )
        return result['long_signals']


# 向后兼容别名
BuySignalCalculator = SignalCalculator
