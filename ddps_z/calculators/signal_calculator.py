"""
信号计算器 (Signal Calculator)

负责计算所有DDPS-Z策略的触发信号：
- 策略1: EMA斜率未来预测做多
- 策略2: 惯性下跌中值突破做多
- 策略3: EMA斜率未来预测做空
- 策略4: 惯性上涨中值突破做空

Related:
    - PRD: docs/iterations/015-short-strategies/prd.md
    - Architecture: docs/iterations/015-short-strategies/architecture.md
    - 原PRD: docs/iterations/011-buy-signal-markers/prd.md
    - TASK: TASK-015-006
"""

import logging
from typing import Any, Dict, List, Optional

import numpy as np

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
    信号计算器 - 计算策略1~4的触发信号

    做多策略:
        策略1: EMA斜率未来预测买入
            触发条件: K线low < P5 且 未来6周期EMA预测价格 > 当前close
            公式: 未来EMA = EMA[t] + (β × 6)

        策略2: 惯性下跌中值突破买入
            前置条件: β < 0（下跌趋势）
            触发条件: 惯性mid < P5 且 K线low < (惯性mid + P5)/2

    做空策略:
        策略3: EMA斜率未来预测做空
            触发条件: K线high >= P95 且 未来6周期EMA预测价格 < 当前close
            公式: 未来EMA = EMA[t] + (β × 6)

        策略4: 惯性上涨中值突破做空
            前置条件: β > 0（上涨趋势）
            触发条件: 惯性mid > P95 且 K线high > (惯性mid + P95)/2
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
        p95: float,
        beta: float,
        inertia_mid: float
    ) -> Dict[str, Any]:
        """
        计算策略4: 惯性上涨中值突破做空

        触发条件:
            1. β > 0（上涨趋势）
            2. 惯性mid > P95（惯性预测高于P95阈值）
            3. K线high > (惯性mid + P95) / 2（价格突破中值线）

        Args:
            kline: K线数据
            p95: 当前P95阈值
            beta: 当前β斜率
            inertia_mid: 当前惯性mid值

        Returns:
            策略4触发信息字典
        """
        high = float(kline['high'])

        # 跳过无效数据
        if np.isnan(p95) or np.isnan(beta) or np.isnan(inertia_mid):
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

        # 前置条件: β > 0（上涨趋势）
        if beta <= 0:
            return result

        # 计算中值线
        mid_line = (inertia_mid + p95) / 2

        # 判断触发条件
        condition1 = inertia_mid > p95   # 惯性mid高于P95
        condition2 = high > mid_line     # 价格突破中值线

        triggered = condition1 and condition2

        if triggered:
            result['triggered'] = True
            result['reason'] = (
                f"上涨惯性中，惯性mid (${inertia_mid:,.2f}) "
                f"高于P95，且价格突破中值线 (${mid_line:,.2f})"
            )
            result['details'] = {
                'beta': beta,
                'inertia_mid': inertia_mid,
                'p95': p95,
                'mid_line': mid_line,
                'current_high': high,
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

        # 验证输入
        self._validate_inputs(
            klines, ema_series, p5_series, beta_series, inertia_mid_series,
            p95_series if (3 in enabled_strategies or 4 in enabled_strategies) else None
        )

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

            # 检查做多策略是否触发
            long_triggered = (
                (strategy1_result and strategy1_result.get('triggered', False)) or
                (strategy2_result and strategy2_result.get('triggered', False))
            )

            if long_triggered:
                strategies = []
                if strategy1_result:
                    strategies.append(strategy1_result)
                if strategy2_result:
                    strategies.append(strategy2_result)

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
                    strategy4_result = self._calculate_strategy4(
                        kline=kline,
                        p95=p95_series[i],
                        beta=beta_series[i],
                        inertia_mid=inertia_mid_series[i]
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
