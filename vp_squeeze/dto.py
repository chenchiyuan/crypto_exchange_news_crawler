"""VP-Squeeze数据传输对象"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional


@dataclass
class KLineData:
    """K线数据"""
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time: datetime
    quote_volume: float
    trade_count: int
    taker_buy_volume: float
    taker_buy_quote_volume: float

    @classmethod
    def from_binance_response(cls, data: list) -> 'KLineData':
        """从币安API响应创建"""
        return cls(
            open_time=datetime.fromtimestamp(data[0] / 1000, tz=timezone.utc),
            open=float(data[1]),
            high=float(data[2]),
            low=float(data[3]),
            close=float(data[4]),
            volume=float(data[5]),
            close_time=datetime.fromtimestamp(data[6] / 1000, tz=timezone.utc),
            quote_volume=float(data[7]),
            trade_count=int(data[8]),
            taker_buy_volume=float(data[9]),
            taker_buy_quote_volume=float(data[10]),
        )


@dataclass
class SqueezeStatus:
    """Squeeze状态"""
    active: bool
    consecutive_bars: int
    reliability: str  # 'high' or 'low'
    signals: list = field(default_factory=list)  # 每根K线的Squeeze信号


@dataclass
class VolumeProfileResult:
    """Volume Profile计算结果"""
    vpoc: float  # 成交量重心
    vah: float  # 价值区域高位
    val: float  # 价值区域低位
    hvn: list = field(default_factory=list)  # 高量节点 [{'low': float, 'high': float, 'volume': float}]
    lvn: list = field(default_factory=list)  # 低量节点 [{'low': float, 'high': float, 'volume': float}]
    profile: dict = field(default_factory=dict)  # 价格桶 -> 成交量


@dataclass
class BoxRange:
    """箱体范围"""
    support: float       # 支撑位 (VAL)
    resistance: float    # 压力位 (VAH)
    midpoint: float      # 中点 (VPOC)
    range_pct: float     # 箱体宽度百分比


@dataclass
class ConfidenceScore:
    """置信率得分"""
    confidence: float           # 综合置信率 0-1
    confidence_pct: int         # 置信率百分比 0-100
    squeeze_score: float        # Squeeze状态得分
    volume_concentration: float # 成交量集中度得分
    volatility_score: float     # 价格波动率得分
    range_score: float          # 价值区域宽度得分


@dataclass
class VPSqueezeAnalysisResult:
    """VP-Squeeze完整分析结果"""
    symbol: str
    interval: str
    timestamp: datetime
    klines_count: int

    # Squeeze状态
    squeeze: SqueezeStatus

    # Volume Profile
    volume_profile: VolumeProfileResult

    # 箱体范围和置信率
    box: Optional[BoxRange] = None
    confidence: Optional[ConfidenceScore] = None

    # 价格范围
    price_min: float = 0.0
    price_max: float = 0.0
    total_volume: float = 0.0

    # 技术指标快照
    bb_upper: Optional[float] = None
    bb_lower: Optional[float] = None
    kc_upper: Optional[float] = None
    kc_lower: Optional[float] = None

    def to_dict(self) -> dict:
        """转换为字典（用于JSON输出）"""
        result = {
            'symbol': self.symbol,
            'interval': self.interval,
            'timestamp': self.timestamp.isoformat(),
            'box': {
                'support': self.box.support if self.box else self.volume_profile.val,
                'resistance': self.box.resistance if self.box else self.volume_profile.vah,
                'midpoint': self.box.midpoint if self.box else self.volume_profile.vpoc,
                'range_pct': self.box.range_pct if self.box else 0,
            },
            'confidence': {
                'value': self.confidence.confidence if self.confidence else 0,
                'pct': self.confidence.confidence_pct if self.confidence else 0,
                'factors': {
                    'squeeze': self.confidence.squeeze_score if self.confidence else 0,
                    'volume_concentration': self.confidence.volume_concentration if self.confidence else 0,
                    'volatility': self.confidence.volatility_score if self.confidence else 0,
                    'range_width': self.confidence.range_score if self.confidence else 0,
                }
            } if self.confidence else None,
            'squeeze': {
                'active': self.squeeze.active,
                'consecutive_bars': self.squeeze.consecutive_bars,
                'reliability': self.squeeze.reliability,
            },
            'levels': {
                'val': self.volume_profile.val,
                'vah': self.volume_profile.vah,
                'vpoc': self.volume_profile.vpoc,
            },
            'hvn': self.volume_profile.hvn,
            'lvn': self.volume_profile.lvn,
            'metadata': {
                'klines_count': self.klines_count,
                'price_range': {
                    'min': self.price_min,
                    'max': self.price_max,
                },
                'total_volume': self.total_volume,
            },
        }
        return result

    def to_model(self):
        """转换为Django模型实例"""
        from vp_squeeze.models import VPSqueezeResult
        return VPSqueezeResult(
            symbol=self.symbol,
            interval=self.interval,
            analyzed_at=self.timestamp,
            klines_count=self.klines_count,
            squeeze_active=self.squeeze.active,
            squeeze_consecutive_bars=self.squeeze.consecutive_bars,
            reliability=self.squeeze.reliability,
            val=Decimal(str(self.volume_profile.val)),
            vah=Decimal(str(self.volume_profile.vah)),
            vpoc=Decimal(str(self.volume_profile.vpoc)),
            hvn_data=self.volume_profile.hvn,
            lvn_data=self.volume_profile.lvn,
            price_min=Decimal(str(self.price_min)),
            price_max=Decimal(str(self.price_max)),
            total_volume=Decimal(str(self.total_volume)),
            bb_upper=Decimal(str(self.bb_upper)) if self.bb_upper else None,
            bb_lower=Decimal(str(self.bb_lower)) if self.bb_lower else None,
            kc_upper=Decimal(str(self.kc_upper)) if self.kc_upper else None,
            kc_lower=Decimal(str(self.kc_lower)) if self.kc_lower else None,
            raw_result=self.to_dict(),
        )
