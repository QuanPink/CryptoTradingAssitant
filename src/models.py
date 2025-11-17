import time
from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class AccumulationZone:
    """Immutable accumulation zone data"""

    support: float
    resistance: float
    strength_score: float
    symbol: str = ""
    timeframe: str = ""
    created_at: float = field(default_factory=time.time)
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
