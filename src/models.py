import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class BreakoutDirection(Enum):
    """Direction of breakout"""
    UP = "UP"
    DOWN = "DOWN"


class BreakoutType(Enum):
    """Type/strength of breakout"""
    SOFT = "SOFT_BREAK"
    CONFIRMED = "CONFIRMED_BREAK"
    STRONG = "STRONG_BREAK"


class ZoneStatus(Enum):
    """Status of monitored accumulation zone"""
    ACTIVE = "ACTIVE"  # Watching for breakout
    BREAKOUT = "BREAKOUT"  # Broken but still monitoring (false break)
    COMPLETED = "COMPLETED"  # Strong break, stop monitoring


class StrengthLevel(Enum):
    """Accumulation strength classification"""
    WEAK = "WEAK"
    AVERAGE = "AVERAGE"
    STRONG = "STRONG"
    VERY_STRONG = "VERY STRONG"


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

    @property
    def strength_level(self) -> StrengthLevel:
        """Get strength level from score"""
        if self.strength_score >= 80:
            return StrengthLevel.VERY_STRONG
        elif self.strength_score >= 60:
            return StrengthLevel.STRONG
        elif self.strength_score >= 40:
            return StrengthLevel.AVERAGE
        return StrengthLevel.WEAK


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


# ═══════════════════════════════════════════════════════════
# MUTABLE MODELS (for internal state management)
# ═══════════════════════════════════════════════════════════

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
