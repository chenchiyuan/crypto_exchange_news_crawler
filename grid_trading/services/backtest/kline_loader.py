"""
K线数据加载器
Kline Data Loader

从数据库或CSV加载历史K线数据
"""
from decimal import Decimal
from typing import List, Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class Kline:
    """K线数据"""
    
    def __init__(
        self,
        timestamp: datetime,
        open: Decimal,
        high: Decimal,
        low: Decimal,
        close: Decimal,
        volume: Decimal
    ):
        self.timestamp = timestamp
        self.open = open
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume
    
    def __repr__(self):
        return (
            f"Kline({self.timestamp}, "
            f"O:{self.open}, H:{self.high}, L:{self.low}, C:{self.close})"
        )


class KlineLoader:
    """K线数据加载器"""
    
    def __init__(self):
        self.klines: List[Kline] = []
    
    def load_from_database(
        self,
        symbol: str,
        interval: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Kline]:
        """
        从数据库加载K线数据
        
        Args:
            symbol: 交易对
            interval: 时间间隔 (1m, 5m, 15m, 1h, etc.)
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            K线列表
        """
        # TODO: 从backtest app的KlineData模型加载
        # from backtest.models import KlineData
        # 
        # kline_data = KlineData.objects.filter(
        #     symbol=symbol,
        #     interval=interval,
        #     timestamp__gte=start_time,
        #     timestamp__lte=end_time
        # ).order_by('timestamp')
        # 
        # self.klines = [
        #     Kline(
        #         timestamp=k.timestamp,
        #         open=Decimal(str(k.open)),
        #         high=Decimal(str(k.high)),
        #         low=Decimal(str(k.low)),
        #         close=Decimal(str(k.close)),
        #         volume=Decimal(str(k.volume))
        #     )
        #     for k in kline_data
        # ]
        
        logger.info(
            f"从数据库加载 {symbol} {interval} K线数据: "
            f"{start_time} - {end_time}"
        )
        
        return self.klines
    
    def load_from_csv(self, csv_path: str) -> List[Kline]:
        """
        从CSV文件加载K线数据
        
        CSV格式：timestamp,open,high,low,close,volume
        
        Args:
            csv_path: CSV文件路径
            
        Returns:
            K线列表
        """
        import csv
        from datetime import datetime
        
        self.klines = []
        
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 解析时间戳（支持毫秒和ISO格式）
                ts_str = row['timestamp']
                if ts_str.isdigit():
                    # 毫秒时间戳
                    timestamp = datetime.fromtimestamp(int(ts_str) / 1000)
                else:
                    # ISO格式
                    timestamp = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                
                kline = Kline(
                    timestamp=timestamp,
                    open=Decimal(row['open']),
                    high=Decimal(row['high']),
                    low=Decimal(row['low']),
                    close=Decimal(row['close']),
                    volume=Decimal(row['volume'])
                )
                self.klines.append(kline)
        
        logger.info(f"从CSV加载了 {len(self.klines)} 条K线数据")
        return self.klines
    
    def get_klines(self) -> List[Kline]:
        """获取K线数据"""
        return self.klines
