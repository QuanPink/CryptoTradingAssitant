"""Accumulation detection using classic price action"""
from typing import Dict, Optional

import numpy as np
import pandas as pd

from config.setting import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class AccumulationDetector:
    """Classic price action accumulation detection"""

    @staticmethod
    def detect(df: pd.DataFrame, timeframe: str, symbol: str) -> Optional[Dict]:
        """
        Detect accumulation zone

        Returns:
            Zone info dict if detected, None otherwise
        """
        lookback_windows = settings.get_tf_setting(timeframe, 'lookback_windows')

        for lookback in lookback_windows:
            if len(df) < lookback + 1:
                continue

            zone = AccumulationDetector._check_window(df, lookback, symbol, timeframe)
            if zone:
                return zone

        return None

    @staticmethod
    def _check_window(df, lookback, symbol, timeframe):
        """Check single lookback window"""
        high = df['high'].values[-lookback:]
        low = df['low'].values[-lookback:]
        close = df['close'].values[-lookback:]

        upper = np.max(high)
        lower = np.min(low)

        # Core checks
        range_ok, range_pct, range_quality = AccumulationDetector._check_price_range(
            df, lookback, symbol, timeframe
        )

        breakout_ok, breakout_ratio = AccumulationDetector._check_breakout_ratio(
            close, upper, lower, timeframe
        )

        volume_ok, vol_ratio = AccumulationDetector._check_volume_suppression(
            df, lookback, timeframe
        )

        # Decision
        if not (range_ok and breakout_ok):
            logger.debug(
                f'{symbol} {timeframe} - Core conditions failed: '
                f'range={range_ok}, breakout={breakout_ok}'
            )
            return None

        # Build zone info
        quality = AccumulationDetector._determine_quality(volume_ok, range_quality)

        return AccumulationDetector._build_zone_info(
            upper, lower, range_pct, lookback, timeframe,
            quality, range_quality, breakout_ratio, vol_ratio, symbol
        )

    @staticmethod
    def _check_price_range(df: pd.DataFrame, lookback: int,
                           symbol: str, timeframe: str) -> tuple[bool, float, str]:
        """
        Core check: Price stays within tight range

        Returns:
            (is_valid, range_pct, quality)
        """
        window = df.iloc[-lookback:]

        high = window['high'].max()
        low = window['low'].min()
        range_pct = (high - low) / low if low > 0 else np.inf

        # Get symbol-specific thresholds
        thresholds = settings.get_accumulation_range(symbol, timeframe)
        min_range = thresholds['min']
        max_range = thresholds['max']

        # Quality assessment
        if range_pct < min_range:
            quality = "too_tight"
            is_valid = False
        elif range_pct <= max_range * 0.5:
            quality = "excellent"
            is_valid = True
        elif range_pct <= max_range * 0.75:
            quality = "good"
            is_valid = True
        elif range_pct <= max_range:
            quality = "fair"
            is_valid = True
        else:
            quality = "too_wide"
            is_valid = False

        logger.debug(
            f'{symbol} {timeframe} Range: {range_pct:.4f} '
            f'({min_range:.4f}-{max_range:.4f}) → {quality.upper()}'
        )

        return is_valid, range_pct, quality

    @staticmethod
    def _check_breakout_ratio(close: np.ndarray, upper: float, lower: float, timeframe: str) -> tuple[bool, float]:
        """
        Check that most candles stay within range

        Returns:
            (is_valid, breakout_ratio)
        """

        # Vectorized operation (much faster than loop)
        breakout_count = np.sum((close > upper * 1.001) | (close < lower * 0.999))

        breakout_ratio = breakout_count / len(close)
        max_breakout = settings.get_tf_setting(timeframe, 'max_breakout_ratio')

        is_valid = breakout_ratio <= max_breakout

        logger.debug(
            f'Breakout: {breakout_count}/{len(close)} '
            f'({breakout_ratio:.1%}) vs max {max_breakout:.1%} '
            f'→ {"PASS" if is_valid else "FAIL"}'
        )

        return is_valid, breakout_ratio

    @staticmethod
    def _check_volume_suppression(df: pd.DataFrame, lookback: int,
                                  timeframe: str) -> tuple[bool, float]:
        """
        Simple filter: Volume should be declining or low

        Returns:
            (is_valid, volume_ratio)
        """
        window = df.iloc[-lookback:]

        # Current period average
        current_vol = window['volume'].mean()

        # Historical average (2x lookback)
        if len(df) >= lookback * 2:
            hist_vol = df['volume'].iloc[-(lookback * 2):-lookback].mean()
        else:
            hist_vol = df['volume'].mean()

        vol_ratio = current_vol / hist_vol if hist_vol > 0 else 1.0

        # Get threshold
        max_vol_ratio = settings.get_tf_setting(timeframe, 'volume_suppression_ratio')
        is_valid = vol_ratio < max_vol_ratio

        logger.debug(
            f'Volume: {vol_ratio:.2f}x historical (max {max_vol_ratio:.2f}x) '
            f'→ {"PASS" if is_valid else "FAIL"}'
        )

        return is_valid, vol_ratio

    @staticmethod
    def _determine_quality(volume_ok: bool, range_quality: str) -> str:
        """Determine overall quality"""
        if volume_ok and range_quality == "excellent":
            return "excellent"
        elif volume_ok:
            return "good"
        else:
            return "fair"

    @staticmethod
    def _build_zone_info(upper, lower, range_pct, lookback, timeframe,
                         quality, range_quality, breakout_ratio, vol_ratio, symbol):
        """Build zone info dict"""
        tf_meta = settings.TIMEFRAME_METADATA[timeframe]
        duration_hours = lookback * tf_meta['duration_factor']

        thresholds = settings.get_accumulation_range(symbol, timeframe)

        logger.info(
            f'[ACCUMULATION DETECTED] {symbol} {timeframe}\n'
            f'  Lookback: {lookback} bars ({duration_hours:.1f}h)\n'
            f'  Range: {range_pct:.4f} ({thresholds["min"]:.4f}-{thresholds["max"]:.4f}) '
            f'✅ [{range_quality}]\n'
            f'  Breakouts: {breakout_ratio:.1%} ✅\n'
            f'  Volume: {vol_ratio:.2f}x {"✅" if vol_ratio < settings.get_tf_setting(timeframe, "volume_suppression_ratio") else "⚠️"}\n'
            f'  Quality: {quality.upper()}'
        )

        return {
            'upper': float(upper),
            'lower': float(lower),
            'width': float(range_pct),
            'mid': float((upper + lower) / 2),
            'lookback': lookback,
            'duration_hours': duration_hours,
            'timeframe': timeframe,
            'quality': quality,
            'range_pct': float(range_pct),
            'range_quality': range_quality,
            'breakout_ratio': float(breakout_ratio),
            'vol_ratio': float(vol_ratio),
            'thresholds': thresholds
        }
