from typing import Dict

import pandas as pd

from src.indicators.technical import TechnicalIndicator
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AccumulationDetector:
    def __init__(self, config: Dict):
        self.config = config
        self.technical = TechnicalIndicator()

    @staticmethod
    def is_bar_in_range(bar: pd.Series, range_high: float, range_low: float) -> bool:
        """Check if candle is mostly within accumulation range"""
        open_price, _, _, close = bar['open'], bar['high'], bar['low'], bar['close']

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

    def check_accumulation_range(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Check if price is in accumulation range based on ATR volatility"""
        config = self.config[timeframe]

        if len(df) < max(config['N_range'], 14):
            logger.warning(f"Not enough data for {timeframe}")
            return self._create_range_check_result(False)

        recent_data = df.tail(config['N_range']).copy()
        atr = self.technical.calculate_atr(df, 14)
        current_atr = atr.iloc[-1] if not atr.empty and not pd.isna(atr.iloc[-1]) else 0

        if current_atr == 0:
            logger.warning(f"ATR is zero for {timeframe}")
            return self._create_range_check_result(False)

        current_price = recent_data['close'].iloc[-1]
        range_size = current_atr * config['K_volatility']
        range_high = current_price + range_size
        range_low = current_price - range_size

        bars_in_range = 0
        bars_with_wick_outside = 0

        for _, bar in recent_data.iterrows():
            if self.is_bar_in_range(bar, range_high, range_low):
                bars_in_range += 1
            if bar['high'] > range_high * 1.01 or bar['low'] < range_low * 0.99:
                bars_with_wick_outside += 1

        bars_in_range_ratio = bars_in_range / len(recent_data)
        wick_outside_ratio = bars_with_wick_outside / len(recent_data)

        is_in_range = bars_in_range_ratio >= 0.8 and wick_outside_ratio <= config['max_wick_bars_ratio']

        return {
            'is_in_range': is_in_range,
            'range_high': range_high,
            'range_low': range_low,
            'bars_in_range_ratio': bars_in_range_ratio,
            'wick_outside_ratio': wick_outside_ratio,
            'range_size_pct': (range_size / current_price) * 100
        }

    def check_volume_contraction(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Check if volume is contracting during accumulation period"""
        config = self.config[timeframe]

        if len(df) < config['N_volume_lookback'] + config['N_range']:
            return {'is_volume_contracted': False, 'volume_ratio': None}

        current_volume = df['volume'].tail(config['N_range']).mean()
        previous_volume = df['volume'].tail(config['N_volume_lookback'] + config['N_range']).head(
            config['N_volume_lookback']).mean()

        if previous_volume == 0:
            return {'is_volume_contracted': False, 'volume_ratio': None}

        volume_ratio = current_volume / previous_volume
        is_volume_contracted = volume_ratio < config['volume_ratio_threshold']

        return {
            'is_volume_contracted': is_volume_contracted,
            'volume_ratio': volume_ratio,
            'current_volume': current_volume,
            'previous_volume': previous_volume
        }

    def check_accumulation(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Main function to check accumulation conditions"""
        range_check = self.check_accumulation_range(df, timeframe)
        volume_check = self.check_volume_contraction(df, timeframe)

        # Log detailed reasons
        if not range_check['is_in_range']:
            logger.info(f"❌ Range check failed: bars_in_range={range_check.get('bars_in_range_ratio', 0):.1%}")

        if not volume_check['is_volume_contracted']:
            logger.info(f"❌ Volume check failed: volume_ratio={volume_check.get('volume_ratio', 0):.2f}")

        is_accumulation = range_check['is_in_range'] and volume_check['is_volume_contracted']

        if is_accumulation:
            logger.info(f"✅ Accumulation detected on {timeframe}")

        return {
            'is_accumulation': is_accumulation,
            'range_check': range_check,
            'volume_check': volume_check,
            'timeframe': timeframe
        }

    @staticmethod
    def _create_range_check_result(is_in_range: bool) -> Dict:
        """Helper to create range check result"""
        return {
            'is_in_range': is_in_range,
            'range_high': None,
            'range_low': None,
            'bars_in_range_ratio': 0,
            'wick_outside_ratio': 0,
            'range_size_pct': 0
        }
