import time
from typing import Dict, List, Optional

import pandas as pd

from config import BREAKOUT_THRESHOLDS
from src.models import AccumulationZone, BreakoutSignal, BreakoutDirection, BreakoutType, MonitoredZone, ZoneStatus
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BreakoutService:
    """
    Monitors accumulation zones for breakouts
    - Tracks multiple zones per symbol
    - Detects soft/confirmed/strong breakouts
    - Auto-cleanup old zones
    """

    def __init__(self):
        self.thresholds = BREAKOUT_THRESHOLDS
        self.monitored_zones: Dict[str, List[MonitoredZone]] = {}

    def add_zone(self, zone: AccumulationZone):
        """
        Add accumulation zone to monitoring list

        Args:
            zone: AccumulationZone to monitor
        """
        symbol = zone.symbol

        if symbol not in self.monitored_zones:
            self.monitored_zones[symbol] = []

        # Check if zone already exists
        existing = next(
            (mz for mz in self.monitored_zones[symbol] if mz.zone.key == zone.key),
            None
        )

        if not existing:
            monitored = MonitoredZone(zone=zone)
            self.monitored_zones[symbol].append(monitored)
            logger.info(f"✅ Monitoring zone: {symbol} {zone.timeframe}")
        else:
            logger.debug(f"⚠️ Zone already monitored: {symbol} {zone.timeframe}")

    def check_breakouts(self, symbol: str, timeframe: str, current_price: float, current_volume: float,
                        volume_ma: float, df: pd.DataFrame) -> Optional[BreakoutSignal]:
        """
        Check all monitored zones for breakouts

        Args:
            symbol: Trading symbol
            timeframe: Timeframe to check
            current_price: Current price
            current_volume: Current volume
            volume_ma: Volume moving average
            df: OHLCV data for candle analysis

        Returns:
            BreakoutSignal if breakout detected, None otherwise
        """
        if symbol not in self.monitored_zones:
            return None

        logger.info(
            f"🔍 Checking breakouts for {symbol} {timeframe}: "
            f"{len([z for z in self.monitored_zones[symbol] if z.zone.timeframe == timeframe])} zones"
        )

        for monitored in self.monitored_zones[symbol]:
            zone = monitored.zone

            # Only check matching timeframe and active zones
            if zone.timeframe != timeframe or not monitored.is_active:
                continue

            # Check for breakout
            breakout = self._evaluate_breakout(
                monitored, current_price, current_volume, volume_ma, df, timeframe
            )

            if breakout:
                return breakout

        return None

    def _evaluate_breakout(self, monitored: MonitoredZone, current_price: float, current_volume: float,
                           volume_ma: float, df: pd.DataFrame, timeframe: str) -> Optional[BreakoutSignal]:
        """
        Evaluate if price broke out of zone

        Returns:
            BreakoutSignal if breakout occurred, None otherwise
        """
        zone = monitored.zone
        support = zone.support
        resistance = zone.resistance

        if support <= current_price <= resistance:
            logger.debug(
                f"💤 Price in zone: {current_price:.6f} ∈ [{support:.6f}, {resistance:.6f}]"
            )

        # Case 1: Price inside zone (potential retest)
        if support <= current_price <= resistance:
            if monitored.status == ZoneStatus.BREAKOUT:
                # Price returned to zone after breakout
                monitored.reset()
                logger.info(f"🔄 Price returned to zone: {zone.symbol}")
            return None

        # Case 2: Breakout UP
        if current_price > resistance:
            break_pct = (current_price - resistance) / resistance
            direction = BreakoutDirection.UP
            breakout_level = resistance

        # Case 3: Breakout DOWN
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
        strength_score = self._calculate_strength(
            break_pct, current_volume, volume_ma, df, direction, config
        )

        # Update zone status
        if breakout_type == BreakoutType.STRONG:
            monitored.mark_completed()
        else:
            monitored.mark_breakout()

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
        return BreakoutType.SOFT  # Fallback

    def _calculate_strength(self, break_pct: float, current_volume: float, volume_ma: float, df: pd.DataFrame,
                            direction: BreakoutDirection, config: Dict) -> float:
        """
        Calculate breakout strength score (0-100)

        Score breakdown:
        - Distance (40 pts): How far price broke
        - Volume (30 pts): Volume spike magnitude
        - Candle (30 pts): Quality of breakout candle
        """
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
        """
        Evaluate quality of breakout candle

        Good breakout candle:
        - Large body (decisive move)
        - Closes near extreme (conviction)
        """
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

    def cleanup_old_zones(self, max_age_hours: float = 24):
        """
        Remove zones older than max_age_hours

        Args:
            max_age_hours: Maximum age in hours (default 24)
        """
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for symbol in self.monitored_zones.keys():
            # Filter out old zones
            self.monitored_zones[symbol] = [
                mz for mz in self.monitored_zones[symbol]
                if current_time - mz.zone.created_at <= max_age_seconds
            ]

            # Remove symbol if no zones left
            if not self.monitored_zones[symbol]:
                del self.monitored_zones[symbol]

    def get_zone_counts(self) -> Dict[str, int]:
        """
        Get counts of zones by status

        Returns:
            Dict with counts: {'ACTIVE': x, 'BREAKOUT': y, 'COMPLETED': z, 'TOTAL': n}
        """
        counts = {
            'ACTIVE': 0,
            'BREAKOUT': 0,
            'COMPLETED': 0,
            'TOTAL': 0
        }

        for zones in self.monitored_zones.values():
            counts['TOTAL'] += len(zones)
            for mz in zones:
                status_name = mz.status.value
                if status_name in counts:
                    counts[status_name] += 1

        return counts
