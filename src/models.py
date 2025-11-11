import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any, List


class BreakoutDirection(Enum):
    """Direction of breakout"""
    UP = "UP"
    DOWN = "DOWN"


class BreakoutType(Enum):
    """Type/strength of breakout"""
    SOFT = "SOFT"
    CONFIRMED = "CONFIRMED"
    STRONG = "STRONG"


class ZoneStatus(Enum):
    """Status of monitored accumulation zone"""
    ACTIVE = "ACTIVE"
    BREAKOUT = "BREAKOUT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class AccumulationZone:
    """Immutable accumulation zone data"""

    symbol: str
    timeframe: str
    support: float
    resistance: float
    created_at: float
    strength_score: float
    strength_details: Dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        """Unique identifier for this zone"""
        return f"{self.symbol}_{self.timeframe}_{self.support:.6f}_{self.resistance:.6f}"

    @property
    def range_pct(self) -> float:
        """Range size as percentage of price"""
        return (self.resistance - self.support) / self.support * 100

    @property
    def mid_price(self) -> float:
        """Middle price of accumulation zone"""
        return (self.support + self.resistance) / 2


@dataclass(frozen=True)
class BreakoutSignal:
    """Immutable breakout signal"""

    zone: AccumulationZone
    direction: BreakoutDirection
    breakout_type: BreakoutType
    current_price: float
    breakout_level: float
    strength_score: float
    volume_ratio: float
    timestamp: float

    @property
    def break_pct(self) -> float:
        """Breakout percentage from level"""
        if self.direction == BreakoutDirection.UP:
            return (self.current_price - self.breakout_level) / self.breakout_level
        else:
            return (self.breakout_level - self.current_price) / self.breakout_level

    @property
    def is_strong(self) -> bool:
        """Check if this is a strong breakout"""
        return self.breakout_type == BreakoutType.STRONG


@dataclass
class TradingSignal:
    signal: str  # LONG, SHORT, NO_TRADE
    bias: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float
    symbol: str
    timeframe: str
    entry_zone: List[float]
    entry_type: str
    stop_loss: float
    take_profit: List[float]
    risk_reward_ratio: float
    urgency: str
    accumulation_score: float
    trend_score: float
    volume_score: float
    filters_passed: List[str]
    processing_time: float
    timestamp: float = None
    details: Dict[str, Any] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.details is None:
            self.details = {}


@dataclass
class MonitoredZone:
    """Mutable zone being monitored for breakout"""

    zone: AccumulationZone
    status: ZoneStatus = ZoneStatus.ACTIVE
    last_breakout_time: Optional[float] = None

    @property
    def age_hours(self) -> float:
        """Age of zone in hours"""
        return (time.time() - self.zone.created_at) / 3600

    @property
    def is_active(self) -> bool:
        """Check if zone is still active"""
        return self.status == ZoneStatus.ACTIVE

    def mark_breakout(self):
        """Mark zone as broken"""
        self.status = ZoneStatus.BREAKOUT
        self.last_breakout_time = time.time()

    def mark_completed(self):
        """Mark zone as completed (stop monitoring)"""
        self.status = ZoneStatus.COMPLETED

    def reset(self):
        """Reset to active status (price returned to zone)"""
        self.status = ZoneStatus.ACTIVE
        self.last_breakout_time = None