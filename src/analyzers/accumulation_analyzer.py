from typing import Dict

import pandas as pd

from src.indicators.technical import TechnicalIndicator


class AccumulationAnalyzer:
    def __init__(self, config: Dict):
        self.config = config
        self.technical = TechnicalIndicator()

    def evaluate_accumulation_strength(self, df: pd.DataFrame, timeframe: str, accumulation_data: Dict) -> Dict:
        """Evaluate accumulation strength on 100-point scale"""
        config = self.config[timeframe]
        score = 0
        details = {}

        # 1. Previous Trend (25 points)
        trend_data = self.technical.identify_trend(df, config['trend_lookback'], config['ma_period'])
        trend_score = round(trend_data['trend_score'], 1)
        score += trend_score
        details['trend_score'] = trend_score
        details['trend'] = trend_data['trend']
        details['ema_slope'] = round(trend_data['ema_slope'], 2)

        # 2. Range Tightness (25 points)
        range_size_pct = accumulation_data['range_check']['range_size_pct']
        range_score = self._calculate_range_score(range_size_pct)
        score += range_score
        details['range_score'] = range_score
        details['range_size_pct'] = round(range_size_pct, 2)

        # 3. Volume Contraction (25 points)
        volume_ratio = accumulation_data['volume_check']['volume_ratio']
        volume_score = self._calculate_volume_score(volume_ratio)
        score += volume_score
        details['volume_score'] = volume_score
        if volume_ratio is not None:
            details['volume_ratio'] = round(volume_ratio, 2)

        # 4. Duration (15 points)
        duration_bars = config['N_range']
        duration_score = min(15, duration_bars * 2)
        score += duration_score
        details['duration_score'] = duration_score

        # 5. Candle Pattern (10 points)
        wick_ratio = accumulation_data['range_check']['wick_outside_ratio']
        bars_in_range_ratio = accumulation_data['range_check']['bars_in_range_ratio']
        candle_score = self._calculate_candle_score(wick_ratio, bars_in_range_ratio)
        score += candle_score
        details['candle_score'] = candle_score
        details['wick_ratio'] = round(wick_ratio, 2)  # Làm tròn
        details['bars_in_range_ratio'] = round(bars_in_range_ratio, 2)

        strength_score = round(score, 1)
        strength_level = self._get_strength_level(strength_score)
        breakout_probability = self._get_breakout_probability(trend_data['trend'])

        return {
            'strength_score': strength_score,
            'strength_level': strength_level,
            'breakout_probability': breakout_probability,
            'score_details': details,
            'accumulation_zone': {
                'support': accumulation_data['range_check']['range_low'],
                'resistance': accumulation_data['range_check']['range_high'],
                'duration_bars': duration_bars
            }
        }

    @staticmethod
    def _calculate_range_score(range_size_pct: float) -> int:
        if range_size_pct < 0.3:
            return 25
        elif range_size_pct < 0.5:
            return 20
        elif range_size_pct < 0.7:
            return 10
        return 0

    @staticmethod
    def _calculate_volume_score(volume_ratio: float) -> int:
        if volume_ratio is None: return 0
        if volume_ratio < 0.5:
            return 25
        elif volume_ratio < 0.7:
            return 20
        elif volume_ratio < 0.85:
            return 10
        return 0

    @staticmethod
    def _calculate_candle_score(wick_ratio: float, bars_in_range_ratio: float) -> int:
        if wick_ratio <= 0.1 and bars_in_range_ratio >= 0.9:
            return 10
        elif wick_ratio <= 0.2 and bars_in_range_ratio >= 0.8:
            return 5
        return 0

    @staticmethod
    def _get_strength_level(score: float) -> str:
        if score >= 80:
            return "VERY STRONG"
        elif score >= 60:
            return "STRONG"
        elif score >= 40:
            return "AVERAGE"
        return "WEAK"

    @staticmethod
    def _get_breakout_probability(trend: str) -> str:
        if trend == 'UPTREND':
            return "UP"
        elif trend == 'DOWNTREND':
            return "DOWN"
        return "UNKNOWN"
