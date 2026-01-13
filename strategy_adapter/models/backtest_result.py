"""
回测结果数据类

本模块定义了标准化的回测结果数据结构BacktestResult。
所有策略的run_backtest方法应返回此类型（或通过to_dict转为Dict）。

设计原则：
- 类型安全：使用dataclass提供类型检查
- 向后兼容：to_dict()方法返回与旧格式兼容的字典
- 可扩展：extra_stats字段支持策略特有统计

迭代编号: 042 (回测结果协议抽象)
创建日期: 2026-01-13
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any


@dataclass
class BacktestResult:
    """
    回测结果标准数据结构

    所有策略的run_backtest方法应返回此类型。
    使用to_dict()方法可转换为字典格式，保持向后兼容。

    Attributes:
        total_orders: 总订单数（已平仓）
        winning_orders: 盈利订单数
        losing_orders: 亏损订单数
        open_positions: 持仓中订单数
        win_rate: 胜率 (%)
        net_profit: 净利润
        return_rate: 收益率 (%)
        initial_capital: 初始资金
        total_equity: 账户总值
        available_capital: 可用现金
        frozen_capital: 挂单冻结
        holding_cost: 持仓成本
        holding_value: 持仓市值
        holding_unrealized_pnl: 持仓浮盈浮亏
        total_volume: 总交易量
        total_commission: 总手续费
        last_close_price: 最后收盘价
        static_apr: 静态APR (%)
        weighted_apy: 综合APY (%)
        backtest_days: 回测天数
        start_date: 开始日期 (YYYY-MM-DD)
        end_date: 结束日期 (YYYY-MM-DD)
        extra_stats: 策略特有统计（字典形式）
        orders: 订单详情列表

    Example:
        >>> result = BacktestResult(
        ...     total_orders=100,
        ...     winning_orders=65,
        ...     losing_orders=35,
        ...     win_rate=65.0,
        ...     net_profit=1500.0,
        ...     return_rate=15.0
        ... )
        >>> result_dict = result.to_dict()
        >>> print(result_dict['win_rate'])
        65.0
    """

    # === 核心统计 ===
    total_orders: int = 0           # 总订单数（已平仓）
    winning_orders: int = 0         # 盈利订单数
    losing_orders: int = 0          # 亏损订单数
    open_positions: int = 0         # 持仓中订单数
    win_rate: float = 0.0           # 胜率 (%)
    net_profit: float = 0.0         # 净利润
    return_rate: float = 0.0        # 收益率 (%)

    # === 资金统计 ===
    initial_capital: float = 0.0    # 初始资金
    total_equity: float = 0.0       # 账户总值
    available_capital: float = 0.0  # 可用现金
    frozen_capital: float = 0.0     # 挂单冻结
    holding_cost: float = 0.0       # 持仓成本
    holding_value: float = 0.0      # 持仓市值
    holding_unrealized_pnl: float = 0.0  # 持仓浮盈浮亏

    # === 交易统计 ===
    total_volume: float = 0.0       # 总交易量
    total_commission: float = 0.0   # 总手续费
    last_close_price: float = 0.0   # 最后收盘价

    # === 年化指标 ===
    static_apr: float = 0.0         # 静态APR (%)
    weighted_apy: float = 0.0       # 综合APY (%)
    backtest_days: int = 0          # 回测天数
    start_date: str = ''            # 开始日期
    end_date: str = ''              # 结束日期

    # === 扩展字段 ===
    extra_stats: Dict[str, Any] = field(default_factory=dict)
    orders: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式

        此方法保持向后兼容，返回与旧格式一致的字典：
        - 展开extra_stats到顶层
        - 添加兼容字段别名（total_trades, remaining_holdings等）
        - 添加statistics嵌套结构

        Returns:
            Dict[str, Any]: 与旧格式兼容的字典

        Example:
            >>> result = BacktestResult(total_orders=10)
            >>> d = result.to_dict()
            >>> d['total_orders'] == d['total_trades']  # 兼容别名
            True
        """
        result = asdict(self)

        # 展开extra_stats到顶层
        extra = result.pop('extra_stats', {})
        result.update(extra)

        # 添加兼容字段别名
        result['total_trades'] = result['total_orders']
        result['winning_trades'] = result['winning_orders']
        result['losing_trades'] = result['losing_orders']
        result['remaining_holdings'] = result['open_positions']
        result['total_profit_loss'] = result['net_profit']

        # 添加statistics嵌套（兼容旧代码）
        result['statistics'] = {
            'total_orders': result['total_orders'],
            'winning_orders': result['winning_orders'],
            'losing_orders': result['losing_orders'],
            'open_positions': result['open_positions'],
            'win_rate': result['win_rate'],
            'total_profit': result['net_profit'],
            'net_profit': result['net_profit'],
            'initial_capital': result['initial_capital'],
            'final_capital': result['total_equity'],
            'return_rate': result['return_rate'],
            'total_volume': result['total_volume'],
            'total_commission': result['total_commission'],
            'static_apr': result['static_apr'],
            'weighted_apy': result['weighted_apy'],
            'backtest_days': result['backtest_days'],
        }

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BacktestResult':
        """
        从字典构建BacktestResult

        支持从旧格式字典构建，自动处理字段别名。

        Args:
            data: 字典数据

        Returns:
            BacktestResult: 构建的实例

        Example:
            >>> d = {'total_trades': 10, 'win_rate': 60.0}
            >>> result = BacktestResult.from_dict(d)
            >>> result.total_orders
            10
        """
        # 字段别名映射（旧名 -> 新名）
        alias_map = {
            'total_trades': 'total_orders',
            'winning_trades': 'winning_orders',
            'losing_trades': 'losing_orders',
            'remaining_holdings': 'open_positions',
            'total_profit_loss': 'net_profit',
        }

        # 构建参数字典
        kwargs = {}

        # 定义所有标准字段
        standard_fields = {
            'total_orders', 'winning_orders', 'losing_orders', 'open_positions',
            'win_rate', 'net_profit', 'return_rate', 'initial_capital',
            'total_equity', 'available_capital', 'frozen_capital',
            'holding_cost', 'holding_value', 'holding_unrealized_pnl',
            'total_volume', 'total_commission', 'last_close_price',
            'static_apr', 'weighted_apy', 'backtest_days',
            'start_date', 'end_date', 'orders'
        }

        # 处理标准字段
        for key, value in data.items():
            # 处理别名
            target_key = alias_map.get(key, key)
            if target_key in standard_fields:
                kwargs[target_key] = value

        # 处理orders字段
        if 'orders' in data:
            kwargs['orders'] = data['orders']

        return cls(**kwargs)
