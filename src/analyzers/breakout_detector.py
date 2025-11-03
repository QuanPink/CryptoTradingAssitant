"""Breakout detection and confirmation"""
from typing import Tuple, Optional, Dict

import pandas as pd

from config.setting import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class BreakoutDetector:
    """Multifactor breakout detection"""

    @staticmethod
    def check_breakout(df: pd.DataFrame, price: float, upper: float, lower: float,
                       timeframe: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Check for breakout

        Returns:
            (direction, quality) or (None, None)
            direction: 'up' or 'down'
            quality: 'strong', 'medium', 'weak'
        """
        buffer = settings.get_tf_setting(timeframe, 'breakout_buffer')

        # Check direction
        if price > upper * (1 + buffer):
            is_confirmed, quality = BreakoutDetector._is_confirmed_breakout(
                df, upper, "up", timeframe
            )
            return ("up", quality) if is_confirmed else (None, None)

        elif price < lower * (1 - buffer):
            is_confirmed, quality = BreakoutDetector._is_confirmed_breakout(
                df, lower, "down", timeframe
            )
            return ("down", quality) if is_confirmed else (None, None)

        return None, None

    @staticmethod
    def _is_confirmed_breakout(df: pd.DataFrame, level: float, direction: str,
                               timeframe: str) -> Tuple[bool, str]:
        """
        Multifactor breakout confirmation
        """
        buffer = settings.get_tf_setting(timeframe, 'breakout_buffer')
        confirmation_bars = settings.get_tf_setting(timeframe, 'confirmation_bars')

        # Factor 1: Price confirmation
        if direction == "up":
            breakout_level = level * (1 + buffer)
            closes = df['close'].iloc[-confirmation_bars:]
            price_confirmed = all(closes > breakout_level)
            avg_close = closes.mean()
            distance = (avg_close - level) / level
        else:
            breakout_level = level * (1 - buffer)
            closes = df['close'].iloc[-confirmation_bars:]
            price_confirmed = all(closes < breakout_level)
            distance = (level - closes.mean()) / level

        if not price_confirmed:
            logger.debug('Breakout rejected: price not confirmed')
            return False, 'rejected'

        # Factor 2: Volume confirmation
        vol_spike, short_ratio, medium_ratio = BreakoutDetector.calculate_volume_spike(df, timeframe)

        # Factor 3: Body size (strong candles vs wicks)
        recent_candles = df.iloc[-confirmation_bars:]
        body_sizes = abs(recent_candles['close'] - recent_candles['open'])
        candle_ranges = recent_candles['high'] - recent_candles['low']
        avg_body_ratio = (body_sizes / candle_ranges).mean()
        strong_candles = avg_body_ratio > 0.5

        # Decision logic
        if vol_spike:
            if strong_candles:
                result = (True, 'strong')
            else:
                result = (True, 'medium')
        elif strong_candles:
            result = (True, 'medium')
        else:
            result = (False, 'weak')

        logger.debug(
            f'Breakout confirmation: price={price_confirmed}, vol={vol_spike} '
            f'({short_ratio:.1f}x/{medium_ratio:.1f}x), candles={strong_candles}, '
            f'distance={distance:.4f}, quality={result[1]}'
        )

        return result

    @staticmethod
    def calculate_volume_spike(df: pd.DataFrame, timeframe: str) -> Tuple[bool, float, float]:
        """
        Dual-window volume spike detection

        Returns:
            (is_spike, short_ratio, medium_ratio)
        """
        current_vol = float(df['volume'].iloc[-1])

        # Get timeframe-specific settings
        short_window = settings.get_tf_setting(timeframe, 'vol_lookback_short')
        medium_window = settings.get_tf_setting(timeframe, 'vol_lookback_medium')
        short_mult = settings.get_tf_setting(timeframe, 'vol_spike_short_mult')
        medium_mult = settings.get_tf_setting(timeframe, 'vol_spike_medium_mult')

        # Ensure we have enough data
        short_window = min(short_window, len(df) - 1)
        medium_window = min(medium_window, len(df) - 1)

        # Calculate baseline volumes (exclude current candle)
        vol_short_mean = float(df['volume'].iloc[-short_window - 1:-1].mean())
        vol_medium_mean = float(df['volume'].iloc[-medium_window - 1:-1].mean())

        # Avoid division by zero
        if vol_short_mean == 0 or vol_medium_mean == 0:
            return False, 0.0, 0.0

        # Calculate ratios
        short_ratio = current_vol / vol_short_mean
        medium_ratio = current_vol / vol_medium_mean

        # Dual confirmation: must exceed BOTH thresholds
        is_spike = (short_ratio > short_mult) and (medium_ratio > medium_mult)

        logger.debug(
            f'{timeframe} Volume check: short={short_ratio:.2f}x (need >{short_mult}x), '
            f'medium={medium_ratio:.2f}x (need >{medium_mult}x), spike={is_spike}'
        )

        return is_spike, short_ratio, medium_ratio

    @staticmethod
    def check_consensus(zones: Dict, symbol: str, direction: str, current_tf: str) -> Dict:
        """Check multi-timeframe consensus"""
        if symbol not in zones:
            return {
                'consensus': False,
                'score': 0,
                'total': 0,
                'aligned_tfs': [],
                'quality': 'weak'
            }

        tf_order = {'5m': 0, '15m': 1, '30m': 2, '1h': 3}
        current_priority = tf_order.get(current_tf, 0)

        aligned_tfs = []
        total_higher_tfs = 0

        # Check all higher timeframes
        for tf, zone in zones[symbol].items():
            tf_priority = tf_order.get(tf, 0)

            if tf_priority > current_priority:
                total_higher_tfs += 1

                # Check if this TF is breaking in same direction
                breakout_key = 'breakout_up' if direction == "up" else 'breakout_down'
                if zone.get(breakout_key):
                    aligned_tfs.append(tf)

        score = len(aligned_tfs)

        # Get required consensus for this timeframe
        required = settings.get_tf_setting(current_tf, 'consensus_required')
        consensus = score >= required

        # Determine quality based on alignment
        if score >= 3:
            quality = 'excellent'
        elif score >= 2:
            quality = 'good'
        elif score >= 1:
            quality = 'medium'
        else:
            quality = 'weak'

        logger.debug(
            f'{symbol} {current_tf} {direction} - Consensus: {score}/{total_higher_tfs} '
            f'(need >={required}), quality={quality}'
        )

        return {
            'consensus': consensus,
            'score': score,
            'total': total_higher_tfs,
            'aligned_tfs': aligned_tfs,
            'quality': quality
        }

    @staticmethod
    def calculate_tp_sl(entry_price: float, direction: str, zone: Dict) -> Dict:
        """Calculate TP/SL levels"""
        upper = zone['upper']
        lower = zone['lower']
        zone_width = upper - lower

        if direction == "up":
            # Long setup
            sl = lower * 0.995
            tp = entry_price + zone_width
            risk = entry_price - sl

            # Ensure TP follows R:R = 1:2
            tp_rr = entry_price + (risk * 2)
            tp = min(tp, tp_rr)

            return {
                'entry': entry_price,
                'sl': sl,
                'tp': tp,
                'risk_pct': ((entry_price - sl) / entry_price) * 100,
                'reward_pct': ((tp - entry_price) / entry_price) * 100
            }
        else:
            # Short setup
            sl = upper * 1.005
            tp = entry_price - zone_width
            risk = sl - entry_price

            # Ensure TP follows R:R = 1:2
            tp_rr = entry_price - (risk * 2)
            tp = max(tp, tp_rr)

            return {
                'entry': entry_price,
                'sl': sl,
                'tp': tp,
                'risk_pct': ((sl - entry_price) / entry_price) * 100,
                'reward_pct': ((entry_price - tp) / entry_price) * 100
            }
