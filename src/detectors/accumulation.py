import time
from typing import Dict, Optional

import pandas as pd

from config import ACCUMULATION_THRESHOLDS
from src.indicators import TechnicalIndicator
from src.models import AccumulationZone
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AccumulationService:
    """
    Unified service for detecting and analyzing accumulation zones
    Combines detection logic + strength analysis
    """

    def __init__(self):
        self.thresholds = ACCUMULATION_THRESHOLDS
        self.technical = TechnicalIndicator()

    def detect(self, df: pd.DataFrame, timeframe: str) -> Optional[AccumulationZone]:
        """
        Main entry point: detect accumulation and return zone

        Args:
            df: OHLCV DataFrame
            timeframe: Timeframe string ('5m', '15m', etc)

        Returns:
            AccumulationZone if detected, None otherwise
        """

        logger.info(f"🔍 Checking accumulation on {timeframe}...")

        # Step 1: Check accumulation conditions
        if not self._check_range(df, timeframe):
            return None

        if not self._check_volume(df, timeframe):
            return None

        # Step 2: Calculate zone boundaries
        zone_data = self._calculate_zone_boundaries(df, timeframe)

        # Step 3: Analyze strength
        strength_result = self._analyze_strength(df, timeframe, zone_data)

        # Step 4: Create immutable zone object
        return AccumulationZone(
            symbol="",  # Will be set by caller
            timeframe=timeframe,
            support=zone_data['support'],
            resistance=zone_data['resistance'],
            created_at=time.time(),
            strength_score=strength_result['strength_score'],
            strength_details=strength_result['details']
        )

    def _check_range(self, df: pd.DataFrame, timeframe: str) -> bool:
        """
        Check if price is in tight accumulation range
        Uses ATR-based volatility measurement
        """
        config = self.thresholds[timeframe]

        if len(df) < max(config['N_range'], 14):
            return False

        recent_data = df.tail(config['N_range']).copy()
        atr = self.technical.calculate_atr(df, 14)
        current_atr = atr.iloc[-1] if not atr.empty and not pd.isna(atr.iloc[-1]) else 0

        if current_atr == 0:
            return False

        current_price = recent_data['close'].iloc[-1]
        range_size = current_atr * config['K_volatility']
        range_high = current_price + range_size
        range_low = current_price - range_size

        # Count bars in range
        bars_in_range = 0
        bars_with_wick_outside = 0

        for _, bar in recent_data.iterrows():
            if self._is_bar_in_range(bar, range_high, range_low):
                bars_in_range += 1
            if bar['high'] > range_high * 1.01 or bar['low'] < range_low * 0.99:
                bars_with_wick_outside += 1

        bars_in_range_ratio = bars_in_range / len(recent_data)
        wick_outside_ratio = bars_with_wick_outside / len(recent_data)

        is_in_range = (
                bars_in_range_ratio >= 0.8 and
                wick_outside_ratio <= config['max_wick_bars_ratio']
        )

        if is_in_range:
            logger.info(
                f"✅ Range OK: {bars_in_range}/{len(recent_data)} bars in range "
                f"({bars_in_range_ratio:.1%}), wicks: {wick_outside_ratio:.1%}"
            )
        else:
            logger.info(
                f"❌ Range FAIL: {bars_in_range}/{len(recent_data)} bars in range "
                f"({bars_in_range_ratio:.1%}), wicks: {wick_outside_ratio:.1%} "
                f"[Need: ≥80% in range, wicks ≤{config['max_wick_bars_ratio']:.1%}]"
            )

        return is_in_range

    @staticmethod
    def _is_bar_in_range(bar: pd.Series, range_high: float, range_low: float) -> bool:
        """Check if candle body is mostly within range"""
        open_price, close = bar['open'], bar['close']

        body_high = max(open_price, close)
        body_low = min(open_price, close)
        body_height = body_high - body_low

        if body_height == 0:
            return range_low <= open_price <= range_high

        body_in_range_high = min(body_high, range_high)
        body_in_range_low = max(body_low, range_low)
        body_in_range_height = max(0, body_in_range_high - body_in_range_low)
        body_in_range_ratio = body_in_range_height / body_height

        return body_in_range_ratio >= 0.6

    def _check_volume(self, df: pd.DataFrame, timeframe: str) -> bool:
        """Check if volume is contracting (accumulation signature)"""
        config = self.thresholds[timeframe]

        if len(df) < config['N_volume_lookback'] + config['N_range']:
            return False

        current_volume = df['volume'].tail(config['N_range']).mean()
        previous_volume = df['volume'].tail(
            config['N_volume_lookback'] + config['N_range']
        ).head(config['N_volume_lookback']).mean()

        if previous_volume == 0:
            return False

        volume_ratio = current_volume / previous_volume
        is_contracted = volume_ratio < config['volume_ratio_threshold']

        if is_contracted:
            logger.info(
                f"✅ Volume OK: {volume_ratio:.2f} "
                f"(current: {current_volume:.0f}, previous: {previous_volume:.0f})"
            )
        else:
            logger.info(
                f"❌ Volume FAIL: ratio={volume_ratio:.2f} "
                f"(current: {current_volume:.0f}, previous: {previous_volume:.0f}) "
                f"[Need: <{config['volume_ratio_threshold']:.2f}]"
            )

        return is_contracted

    def _calculate_zone_boundaries(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Calculate support/resistance levels"""
        config = self.thresholds[timeframe]
        recent_data = df.tail(config['N_range'])

        atr = self.technical.calculate_atr(df, 14)
        current_atr = atr.iloc[-1]
        current_price = recent_data['close'].iloc[-1]

        range_size = current_atr * config['K_volatility']

        return {
            'support': current_price - range_size,
            'resistance': current_price + range_size,
            'range_size_pct': (range_size / current_price) * 100
        }

    def _analyze_strength(self, df: pd.DataFrame, timeframe: str, zone_data: Dict) -> Dict:
        """
        Analyze accumulation strength (0-100 score)

        Score breakdown:
        - Trend (25 pts): Previous trend quality
        - Range (25 pts): How tight the range is
        - Volume (25 pts): Degree of volume contraction
        - Duration (15 pts): How long accumulation lasted
        - Candles (10 pts): Quality of candle patterns
        """
        config = self.thresholds[timeframe]
        score = 0
        details = {}

        # 1. Previous Trend (25 points)
        trend_data = self.technical.identify_trend(
            df, config['trend_lookback'], config['ma_period']
        )
        trend_score = trend_data['trend_score']
        score += trend_score
        details['trend_score'] = trend_score
        details['trend'] = trend_data['trend']
        details['ema_slope'] = trend_data['ema_slope']

        # 2. Range Tightness (25 points)
        range_size_pct = zone_data['range_size_pct']
        range_score = self._calculate_range_score(range_size_pct)
        score += range_score
        details['range_score'] = range_score
        details['range_size_pct'] = round(range_size_pct, 2)

        # 3. Volume Contraction (25 points)
        volume_data = self._get_volume_data(df, timeframe)
        volume_score = self._calculate_volume_score(volume_data['volume_ratio'])
        score += volume_score
        details['volume_score'] = volume_score
        details['volume_ratio'] = round(volume_data['volume_ratio'], 2)

        # 4. Duration (15 points)
        duration_bars = config['N_range']
        duration_score = min(15, duration_bars * 2)
        score += duration_score
        details['duration_score'] = duration_score

        # 5. Candle Pattern (10 points)
        candle_score = 10  # Simplified for now
        score += candle_score
        details['candle_score'] = candle_score

        return {
            'strength_score': round(score, 1),
            'details': details
        }

    @staticmethod
    def _calculate_range_score(range_size_pct: float) -> float:
        """Score based on range tightness"""
        if range_size_pct < 0.3:
            return 25
        elif range_size_pct < 0.5:
            return 20
        elif range_size_pct < 0.7:
            return 10
        return 0

    @staticmethod
    def _calculate_volume_score(volume_ratio: float) -> float:
        """Score based on volume contraction"""
        if volume_ratio < 0.5:
            return 25
        elif volume_ratio < 0.7:
            return 20
        elif volume_ratio < 0.85:
            return 10
        return 0

    def _get_volume_data(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Get volume comparison data"""
        config = self.thresholds[timeframe]

        current_volume = df['volume'].tail(config['N_range']).mean()
        previous_volume = df['volume'].tail(
            config['N_volume_lookback'] + config['N_range']
        ).head(config['N_volume_lookback']).mean()

        volume_ratio = current_volume / previous_volume if previous_volume > 0 else 1

        return {
            'current_volume': current_volume,
            'previous_volume': previous_volume,
            'volume_ratio': volume_ratio
        }
