import time
from typing import Dict, Optional

import pandas as pd

from config import ACCUMULATION_THRESHOLDS, SYMBOL_RANGE_SETTINGS
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

    def detect(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Optional[AccumulationZone]:
        """
        Main entry point: detect accumulation and return zone
        """

        logger.info(f"🔍 Checking accumulation on {timeframe}...")

        # Step 1: Check accumulation conditions
        if not self._check_range(df, timeframe, symbol):
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

    def _check_range(self, df: pd.DataFrame, timeframe: str, symbol: str) -> bool:
        """
        Check if price is in tight accumulation range
        """
        config = ACCUMULATION_THRESHOLDS[timeframe]
        n_range = config['N_range']

        if len(df) < n_range:
            return False

        recent_data = df.tail(config['N_range']).copy()
        current_price = recent_data['close'].iloc[-1]

        body_highs = recent_data[['open', 'close']].max(axis=1)
        body_lows = recent_data[['open', 'close']].min(axis=1)
        body_high = body_highs.max()
        body_low = body_lows.min()
        body_range = body_high - body_low

        full_high = recent_data['high'].max()
        full_low = recent_data['low'].min()
        full_range = full_high - full_low

        wick_size = full_range - body_range
        wick_ratio = (wick_size / body_range) if body_range > 0 else 0
        wick_tolerance = config.get('wick_tolerance', 0.30)

        if wick_ratio <= wick_tolerance:  # ← Wicks NHỎ → Dùng FULL
            use_high = full_high
            use_low = full_low
            range_type = "FULL"
        else:  # ← Wicks LỚN → Dùng BODY (lọc spike)
            use_high = body_high
            use_low = body_low
            range_type = "BODY"

        actual_range = use_high - use_low
        range_pct = (actual_range / current_price) * 100

        symbol_config = SYMBOL_RANGE_SETTINGS.get(symbol, {})
        max_range_pct = symbol_config.get(timeframe, 1)

        if range_pct > max_range_pct:
            logger.info(
                f"❌ Range check {symbol} {timeframe}: "
                f"{range_pct:.2f}% > {max_range_pct:.2f}% ({range_type})"
            )
            return False

        min_candles_ratio = config.get('candles_in_range_ratio', 0.80)
        candles_in = self._count_candles_in_range(recent_data, use_high, use_low, timeframe)
        candles_ratio = candles_in / len(recent_data)

        if candles_ratio < min_candles_ratio:
            logger.info(
                f"❌ Stability check {symbol} {timeframe}: "
                f"{candles_in}/{len(recent_data)} ({candles_ratio:.0%}) < {min_candles_ratio:.0%}"
            )
            return False

        logger.info(
            f"✅ Range OK {symbol} {timeframe}: "
            f"{range_pct:.2f}% <= {max_range_pct:.2f}%, "
            f"candles: {candles_in}/{len(recent_data)} ({range_type})"
        )

        return True

    @staticmethod
    def _count_candles_in_range(df, range_high, range_low, timeframe):
        """
        Count candles with body in range
        """
        config = ACCUMULATION_THRESHOLDS[timeframe]
        body_tolerance = config.get('body_exceed_tolerance', 0.03)

        count = 0
        range_size = range_high - range_low

        for _, candle in df.iterrows():
            body_high = max(candle['open'], candle['close'])
            body_low = min(candle['open'], candle['close'])

            # Allow small breach
            exceed_up = max(0, body_high - range_high)
            exceed_down = max(0, range_low - body_low)
            max_exceed = max(exceed_up, exceed_down)
            exceed_pct = max_exceed / range_size if range_size > 0 else 0

            if exceed_pct <= body_tolerance:
                count += 1

        return count

    def _check_volume(self, df: pd.DataFrame, timeframe: str) -> bool:
        """
        Check if volume is contracting (accumulation signature)
        """
        config = self.thresholds[timeframe]

        if len(df) < config['N_volume_lookback'] + config['N_range']:
            return False

        current_volume = df['volume'].tail(config['N_range']).mean()
        previous_volume = df['volume'].tail(config['N_volume_lookback'] + config['N_range']).head(
            config['N_volume_lookback']).mean()

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
        """
        Calculate support/resistance levels
        """
        config = self.thresholds[timeframe]
        recent_data: pd.DataFrame = df.tail(config['N_range'])

        actual_high = recent_data['high'].max()
        actual_low = recent_data['low'].min()

        # Method 2 (Optional): Use body only (filter wicks)
        # body_highs = recent_data[['open', 'close']].max(axis=1)
        # body_lows = recent_data[['open', 'close']].min(axis=1)
        # actual_high = body_highs.max()
        # actual_low = body_lows.min()

        actual_range = actual_high - actual_low
        current_price = recent_data['close'].iloc[-1]

        # Add buffer to avoid false breakouts
        buffer_pct = config.get('zone_buffer_pct', 0.0)  # Default 15%
        buffer = actual_range * buffer_pct

        support = actual_low - buffer
        resistance = actual_high + buffer

        return {
            'support': support,
            'resistance': resistance,
            'range_size_pct': ((resistance - support) / current_price) * 100
        }

    def _analyze_strength(self, df: pd.DataFrame, timeframe: str, zone_data: Dict) -> Dict:
        """
        Analyze accumulation strength (0-100 score)
        """
        config = self.thresholds[timeframe]
        score = 0
        details = {}

        # 1. Previous Trend
        trend_data = self.technical.identify_trend(
            df, config['trend_lookback'], config['ma_period']
        )
        trend_score = trend_data['trend_score']
        score += trend_score
        details['trend_score'] = trend_score
        details['trend'] = trend_data['trend']
        details['ema_slope'] = trend_data['ema_slope']

        # 2. Range Tightness
        range_size_pct = zone_data['range_size_pct']
        range_score = self._calculate_range_score(range_size_pct)
        score += range_score
        details['range_score'] = range_score
        details['range_size_pct'] = round(range_size_pct, 2)

        # 3. Volume Contraction
        volume_data = self._get_volume_data(df, timeframe)
        volume_score = self._calculate_volume_score(volume_data['volume_ratio'])
        score += volume_score
        details['volume_score'] = volume_score
        details['volume_ratio'] = round(volume_data['volume_ratio'], 2)

        # 4. Duration
        duration_bars = config['N_range']
        duration_score = min(15, duration_bars * 2)
        score += duration_score
        details['duration_score'] = duration_score

        # 5. Candle Pattern
        candle_score = 10
        score += candle_score
        details['candle_score'] = candle_score

        return {
            'strength_score': round(score, 1),
            'details': details
        }

    @staticmethod
    def _calculate_range_score(range_size_pct: float) -> float:
        """
        Score based on range tightness
        """
        if range_size_pct < 0.3:
            return 25
        elif range_size_pct < 0.5:
            return 20
        elif range_size_pct < 0.7:
            return 10
        return 0

    @staticmethod
    def _calculate_volume_score(volume_ratio: float) -> float:
        """
        Score based on volume contraction
        """
        if volume_ratio < 0.5:
            return 25
        elif volume_ratio < 0.7:
            return 20
        elif volume_ratio < 0.85:
            return 10
        return 0

    def _get_volume_data(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """
        Get volume comparison data
        """
        config = self.thresholds[timeframe]

        current_volume = df['volume'].tail(config['N_range']).mean()
        previous_volume = df['volume'].tail(config['N_volume_lookback'] + config['N_range']).head(
            config['N_volume_lookback']).mean()

        volume_ratio = current_volume / previous_volume if previous_volume > 0 else 1

        return {
            'current_volume': current_volume,
            'previous_volume': previous_volume,
            'volume_ratio': volume_ratio
        }
