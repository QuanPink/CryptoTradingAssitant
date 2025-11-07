import time
from typing import Dict, Optional

import pandas as pd

from config import BREAKOUT_THRESHOLDS
from src.models import AccumulationZone, BreakoutSignal, BreakoutDirection, BreakoutType
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BreakoutService:
    """Monitors accumulation zones for breakouts"""

    def __init__(self):
        self.thresholds = BREAKOUT_THRESHOLDS

    @staticmethod
    def _calculate_overlap(support1: float, resistance1: float, support2: float, resistance2: float) -> float:
        """Calculate overlap percentage between two zones"""
        overlap_low = max(support1, support2)
        overlap_high = min(resistance1, resistance2)

        # No overlap
        if overlap_low >= overlap_high:
            return 0.0

        # Calculate overlap size
        overlap_size = overlap_high - overlap_low
        zone1_size = resistance1 - support1
        zone2_size = resistance2 - support2

        # Overlap as % of smaller zone
        smaller_zone_size = min(zone1_size, zone2_size)

        if smaller_zone_size == 0:
            return 0.0

        return overlap_size / smaller_zone_size

    def check_breakouts(self, zones: Dict[str, AccumulationZone], symbol: str, timeframe: str, current_price: float,
                        current_volume: float, volume_ma: float, df: pd.DataFrame) -> Optional[BreakoutSignal]:
        """Check all monitored zones for breakouts"""
        key = f"{symbol}_{timeframe}"
        if key not in zones:
            return None

        zone = zones[key]

        logger.info(
            f"🔍 Checking breakouts for {symbol} {timeframe}: "
        )

        return self._evaluate_breakout_pure(zone, current_price, current_volume, volume_ma, df, timeframe)

    def _evaluate_breakout_pure(self, zone: AccumulationZone, current_price: float, current_volume: float,
                                volume_ma: float, df: pd.DataFrame, timeframe: str) -> Optional[BreakoutSignal]:
        """Pure function - no side effects"""
        support = zone.support
        resistance = zone.resistance

        # Check if price in zone
        if support <= current_price <= resistance:
            logger.debug(
                f"💤 Price in zone: {current_price:.6f} ∈ [{support:.6f}, {resistance:.6f}]"
            )
            return None

        # Case 1: Breakout UP
        if current_price > resistance:
            break_pct = (current_price - resistance) / resistance
            direction = BreakoutDirection.UP
            breakout_level = resistance

        # Case 2: Breakout DOWN
        elif current_price < support:
            break_pct = (support - current_price) / support
            direction = BreakoutDirection.DOWN
            breakout_level = support

        else:
            return None

        # Classify breakout type
        config = self.thresholds[timeframe]
        breakout_type = self._classify_breakout(break_pct, config)

        # Calculate breakout strength
        strength_score = self._calculate_strength(break_pct, current_volume, volume_ma, df, direction, config)

        logger.info(
            f"🚀 Breakout detected: {zone.symbol} {direction.value} "
            f"{break_pct * 100:.2f}% ({breakout_type.value})"
        )

        return BreakoutSignal(
            zone=zone,
            direction=direction,
            breakout_type=breakout_type,
            current_price=current_price,
            breakout_level=breakout_level,
            strength_score=strength_score,
            volume_ratio=current_volume / volume_ma if volume_ma > 0 else 1,
            timestamp=time.time()
        )

    @staticmethod
    def _classify_breakout(break_pct: float, config: Dict) -> BreakoutType:
        """Classify breakout by percentage distance"""
        if break_pct >= config['strong_break']:
            return BreakoutType.STRONG
        elif break_pct >= config['confirmed_break']:
            return BreakoutType.CONFIRMED
        elif break_pct >= config['soft_break']:
            return BreakoutType.SOFT
        return BreakoutType.SOFT

    def _calculate_strength(self, break_pct: float, current_volume: float, volume_ma: float, df: pd.DataFrame,
                            direction: BreakoutDirection, config: Dict) -> float:
        """Calculate breakout strength score (0-100)"""
        score = 0.0

        # 1. Distance score (40 points)
        strong_threshold = config['strong_break']
        distance_score = min(40, (break_pct / strong_threshold) * 40)
        score += distance_score

        # 2. Volume score (30 points)
        volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
        volume_threshold = config['volume_spike_threshold']

        if volume_ratio >= volume_threshold:
            score += 30
        elif volume_ratio >= volume_threshold * 0.8:
            score += 20
        elif volume_ratio >= 1.0:
            score += 10

        # 3. Candle quality (30 points)
        candle_score = self._evaluate_candle_quality(df, direction)
        score += candle_score

        return round(min(100.0, score), 1)

    @staticmethod
    def _evaluate_candle_quality(df: pd.DataFrame, direction: BreakoutDirection) -> float:
        """Evaluate quality of breakout candle"""
        if len(df) < 2:
            return 0

        candle = df.iloc[-1]

        # Calculate body and range
        body_size = abs(candle['close'] - candle['open'])
        total_range = candle['high'] - candle['low']

        if total_range == 0:
            return 0

        # Score breakdown
        body_score = BreakoutService._score_body_size(body_size, total_range)
        close_score = BreakoutService._score_close_position(candle, total_range, direction)

        return body_score + close_score

    @staticmethod
    def _score_body_size(body_size: float, total_range: float) -> float:
        """Score based on body to range ratio (0-15 points)"""
        body_ratio = body_size / total_range

        if body_ratio >= 0.7:
            return 15
        elif body_ratio >= 0.5:
            return 10
        elif body_ratio >= 0.3:
            return 5
        return 0

    @staticmethod
    def _score_close_position(candle, total_range: float, direction: BreakoutDirection) -> float:
        """Score based on close position (0-15 points)"""
        if direction == BreakoutDirection.UP:
            close_position = (candle['close'] - candle['low']) / total_range
        else:  # DOWN
            close_position = (candle['high'] - candle['close']) / total_range

        return 15 if close_position >= 0.7 else 0
