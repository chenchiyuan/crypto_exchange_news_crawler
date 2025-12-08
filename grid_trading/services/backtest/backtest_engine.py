"""
网格交易回测引擎
Grid Trading Backtest Engine

模拟网格交易策略在历史数据上的表现
"""
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
import logging

from grid_trading.models import GridConfig, OrderIntentType
from grid_trading.services.grid.engine import GridEngine
from grid_trading.services.backtest.simulated_exchange import SimulatedExchange
from grid_trading.services.backtest.kline_loader import KlineLoader, Kline

logger = logging.getLogger(__name__)


class BacktestResult:
    """回测结果"""
    
    def __init__(self):
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.total_klines = 0
        
        # PnL统计
        self.realized_pnl = Decimal('0')  # 已实现盈亏
        self.unrealized_pnl = Decimal('0')  # 未实现盈亏
        self.total_pnl = Decimal('0')  # 总盈亏
        
        # 交易统计
        self.total_trades = 0  # 总交易次数（成交次数）
        self.total_rounds = 0  # 总完整轮次（开仓-平仓）
        self.winning_rounds = 0  # 盈利轮次
        self.losing_rounds = 0  # 亏损轮次
        
        # 持仓统计
        self.max_position = Decimal('0')  # 最大持仓
        self.avg_position = Decimal('0')  # 平均持仓
        
        # 权益曲线
        self.equity_curve: List[Dict] = []  # [{timestamp, equity, pnl}, ...]
        
        # 回撤统计
        self.max_drawdown = Decimal('0')  # 最大回撤
        self.max_drawdown_pct = Decimal('0')  # 最大回撤百分比
        
    def calculate_metrics(self, initial_equity: Decimal):
        """计算性能指标"""
        self.total_pnl = self.realized_pnl + self.unrealized_pnl
        
        # 计算胜率
        if self.total_rounds > 0:
            self.win_rate = self.winning_rounds / self.total_rounds
        else:
            self.win_rate = Decimal('0')
        
        # 计算总收益率
        if initial_equity > 0:
            self.total_return_pct = (self.total_pnl / initial_equity) * 100
        else:
            self.total_return_pct = Decimal('0')
        
        # 计算最大回撤
        self._calculate_max_drawdown(initial_equity)
    
    def _calculate_max_drawdown(self, initial_equity: Decimal):
        """计算最大回撤"""
        if not self.equity_curve:
            return
        
        peak = initial_equity
        max_dd = Decimal('0')
        
        for point in self.equity_curve:
            equity = point['equity']
            if equity > peak:
                peak = equity
            
            drawdown = peak - equity
            if drawdown > max_dd:
                max_dd = drawdown
        
        self.max_drawdown = max_dd
        if peak > 0:
            self.max_drawdown_pct = (max_dd / peak) * 100


class BacktestEngine:
    """回测引擎"""
    
    def __init__(
        self,
        config: GridConfig,
        initial_equity: Decimal = Decimal('10000'),
        enable_slippage: bool = False
    ):
        """
        初始化回测引擎
        
        Args:
            config: 网格配置
            initial_equity: 初始权益
            enable_slippage: 是否启用滑点
        """
        self.config = config
        self.initial_equity = initial_equity
        self.current_equity = initial_equity
        
        # 创建模拟交易所
        self.exchange = SimulatedExchange(enable_slippage=enable_slippage)
        
        # 创建网格引擎
        self.grid_engine = GridEngine(config, exchange_adapter=self.exchange)
        
        # K线加载器
        self.kline_loader = KlineLoader()
        
        # 回测结果
        self.result = BacktestResult()
        
        # 追踪开仓价格（用于计算已实现盈亏）
        self.entry_prices: Dict[int, Decimal] = {}  # {level_index: entry_price}
    
    def run(
        self,
        klines: List[Kline],
        tick_interval: int = 1
    ) -> BacktestResult:
        """
        运行回测

        Args:
            klines: K线数据列表
            tick_interval: 每N根K线执行一次tick（1=每根K线）

        Returns:
            回测结果
        """
        if not klines:
            raise ValueError("K线数据为空")

        logger.info(f"开始回测: {self.config.name}")
        logger.info(f"K线数量: {len(klines)}")
        logger.info(f"时间范围: {klines[0].timestamp} - {klines[-1].timestamp}")

        # 清理回测环境：删除配置关联的所有GridLevel和OrderIntent
        from grid_trading.models import GridLevel, OrderIntent
        deleted_levels = GridLevel.objects.filter(config=self.config).delete()
        deleted_intents = OrderIntent.objects.filter(config=self.config).delete()
        logger.info(
            f"清理回测环境: 删除了 {deleted_levels[0]} 个GridLevel, "
            f"{deleted_intents[0]} 个OrderIntent"
        )

        # 初始化
        self.result.start_time = klines[0].timestamp
        self.result.end_time = klines[-1].timestamp
        self.result.total_klines = len(klines)
        
        # 启动网格引擎
        self.grid_engine.start()

        # 执行初始tick创建初始订单
        logger.info("执行初始tick创建初始订单...")
        self.grid_engine.tick(current_price=klines[0].close)

        # 遍历K线
        for i, kline in enumerate(klines):
            # 每N根K线执行一次tick
            if i % tick_interval == 0:
                self.grid_engine.tick(current_price=kline.close)
            
            # 撮合订单
            filled_orders = self.exchange.match_orders(
                kline_open=kline.open,
                kline_high=kline.high,
                kline_low=kline.low,
                kline_close=kline.close
            )
            
            # 处理成交订单
            for order_id, side, fill_price in filled_orders:
                self._on_order_filled(order_id, fill_price)
            
            # 更新权益曲线（每100根K线记录一次）
            if i % 100 == 0:
                self._update_equity_curve(kline.timestamp, kline.close)
        
        # 最后一次更新权益
        self._update_equity_curve(klines[-1].timestamp, klines[-1].close)
        
        # 停止引擎
        self.grid_engine.stop()
        
        # 计算最终指标
        self.result.calculate_metrics(self.initial_equity)
        
        logger.info(f"回测完成")
        logger.info(f"总交易次数: {self.result.total_trades}")
        logger.info(f"已实现盈亏: {self.result.realized_pnl}")
        logger.info(f"总盈亏: {self.result.total_pnl}")
        
        return self.result
    
    def _on_order_filled(self, order_id: str, fill_price: Decimal):
        """
        处理订单成交
        
        Args:
            order_id: 订单ID
            fill_price: 成交价格
        """
        # 查找OrderIntent
        from grid_trading.models import OrderIntent
        
        try:
            intent = OrderIntent.objects.get(order_id=order_id)
        except OrderIntent.DoesNotExist:
            logger.warning(f"未找到订单意图: {order_id}")
            return
        
        level_index = intent.level_index
        intent_type = intent.intent
        
        # 通知网格引擎订单成交
        self.grid_engine.on_order_filled(order_id, intent_type)
        
        # 更新交易统计
        self.result.total_trades += 1
        
        # 计算已实现盈亏
        if intent_type == OrderIntentType.ENTRY:
            # 开仓：记录开仓价格
            self.entry_prices[level_index] = fill_price
            logger.debug(
                f"开仓: level={level_index}, price={fill_price}"
            )
        
        elif intent_type == OrderIntentType.EXIT:
            # 平仓：计算已实现盈亏
            if level_index in self.entry_prices:
                entry_price = self.entry_prices[level_index]
                
                # 做空网格：开仓卖，平仓买
                # PnL = (entry_price - exit_price) * quantity
                trade_amount = Decimal(str(self.config.trade_amount))
                pnl = (entry_price - fill_price) * trade_amount
                
                self.result.realized_pnl += pnl
                self.result.total_rounds += 1
                
                if pnl > 0:
                    self.result.winning_rounds += 1
                else:
                    self.result.losing_rounds += 1
                
                logger.debug(
                    f"平仓: level={level_index}, "
                    f"entry={entry_price}, exit={fill_price}, "
                    f"pnl={pnl}"
                )
                
                # 清除开仓价格记录
                del self.entry_prices[level_index]
    
    def _update_equity_curve(self, timestamp: datetime, current_price: Decimal):
        """
        更新权益曲线
        
        Args:
            timestamp: 时间戳
            current_price: 当前价格
        """
        # 计算未实现盈亏
        unrealized = Decimal('0')
        trade_amount = Decimal(str(self.config.trade_amount))
        
        for level_index, entry_price in self.entry_prices.items():
            # 做空网格：未实现盈亏 = (entry_price - current_price) * quantity
            pnl = (entry_price - current_price) * trade_amount
            unrealized += pnl
        
        self.result.unrealized_pnl = unrealized
        
        # 计算当前权益
        current_equity = self.initial_equity + self.result.realized_pnl + unrealized
        
        # 记录权益点
        self.result.equity_curve.append({
            'timestamp': timestamp,
            'equity': current_equity,
            'realized_pnl': self.result.realized_pnl,
            'unrealized_pnl': unrealized
        })
