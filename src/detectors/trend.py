import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple
from config.settings import FAST_INDICATOR_CONFIG
from ..indicators.technical import TechnicalIndicator


class FastTrendAnalyzer:
    def __init__(self):
        self.config = FAST_INDICATOR_CONFIG
        self.technical = TechnicalIndicator()

    def analyze_trend_fast(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Phân tích trend siêu nhanh cho 5p"""
        current_price = df['close'].iloc[-1]

        # 1. EMA Analysis
        ema_9 = df['close'].ewm(span=self.config['ema_fast']).mean().iloc[-1]
        ema_21 = df['close'].ewm(span=self.config['ema_medium']).mean().iloc[-1]
        ema_55 = df['close'].ewm(span=self.config['ema_slow']).mean().iloc[-1]

        # 2. VWAP
        vwap = self._calculate_vwap(df).iloc[-1]

        # 3. RSI Fast
        rsi_7 = self.technical.calculate_rsi(df['close'], self.config['rsi_period'])

        # 4. MACD Fast
        macd_fast, macd_signal, macd_hist = self._calculate_macd_fast(df['close'])

        # 5. Volume Analysis
        volume_analysis = self._analyze_volume_fast(df)

        return {
            'price_vs_ema': {
                'above_ema9': current_price > ema_9,
                'above_ema21': current_price > ema_21,
                'above_ema55': current_price > ema_55,
                'above_vwap': current_price > vwap,
                'ema_alignment': self._check_ema_alignment_enhanced(ema_9, ema_21, ema_55, current_price),
            },
            'momentum': {
                'rsi_7': rsi_7.iloc[-1] if hasattr(rsi_7, 'iloc') else rsi_7[-1],
                'rsi_trend': self._get_rsi_trend(rsi_7),
                'macd_hist_trend': self._get_macd_trend_fast(macd_hist),
                'price_momentum': self._get_price_momentum(df),
            },
            'volume_analysis': volume_analysis,
            'market_structure_fast': {
                'immediate_bias': self._get_immediate_bias(df),
                'key_levels': self._find_immediate_levels(df),
            }
        }

    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """Calculate VWAP"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        vwap = (typical_price * df['volume']).cumsum() / df['volume'].cumsum()
        return vwap

    def _calculate_macd_fast(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD với parameters nhanh"""
        ema_fast = prices.ewm(span=self.config['macd_fast']).mean()
        ema_slow = prices.ewm(span=self.config['macd_slow']).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=self.config['macd_signal']).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist

    def _check_ema_alignment_enhanced(self, ema_9: float, ema_21: float, ema_55: float, current_price: float) -> Dict[str, Any]:
        """EMA alignment chi tiết"""
        bullish_alignment = ema_9 > ema_21 > ema_55 and current_price > ema_9
        bearish_alignment = ema_9 < ema_21 < ema_55 and current_price < ema_9

        ema_diff_strength = (ema_9 - ema_21) / ema_21 * 100 if ema_21 > 0 else 0

        if bullish_alignment:
            if ema_diff_strength > 0.3:
                alignment = 'STRONG_BULLISH'
            elif ema_diff_strength > 0.1:
                alignment = 'BULLISH'
            else:
                alignment = 'WEAK_BULLISH'
        elif bearish_alignment:
            if ema_diff_strength < -0.3:
                alignment = 'STRONG_BEARISH'
            elif ema_diff_strength < -0.1:
                alignment = 'BEARISH'
            else:
                alignment = 'WEAK_BEARISH'
        else:
            alignment = 'NEUTRAL'

        return {
            'alignment': alignment,
            'ema_diff_pct': ema_diff_strength,
            'bullish_alignment': bullish_alignment,
            'bearish_alignment': bearish_alignment
        }

    def _get_price_momentum(self, df: pd.DataFrame) -> str:
        """Xác định momentum giá ngắn hạn"""
        recent_closes = df['close'].tail(5)

        if len(recent_closes) < 4:
            return "NEUTRAL"

        current_close = recent_closes.iloc[-1]
        prev_close_3 = recent_closes.iloc[-4]

        price_change_pct = (current_close - prev_close_3) / prev_close_3 * 100

        if price_change_pct > 0.3:
            return "STRONG_UP"
        elif price_change_pct > 0.1:
            return "UP"
        elif price_change_pct < -0.3:
            return "STRONG_DOWN"
        elif price_change_pct < -0.1:
            return "DOWN"
        else:
            return "NEUTRAL"

    def _analyze_volume_fast(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Volume analysis nhanh"""
        recent_volume = df['volume'].tail(10)
        current_volume = recent_volume.iloc[-1]
        avg_volume_5 = recent_volume.tail(5).mean()
        avg_volume_10 = recent_volume.mean()

        return {
            'volume_ratio': current_volume / avg_volume_5 if avg_volume_5 > 0 else 1,
            'volume_trend': 'INCREASING' if current_volume > avg_volume_10 * 1.2 else 'DECREASING',
            'is_spike': current_volume > avg_volume_5 * 1.8,
        }

    def _get_immediate_bias(self, df: pd.DataFrame) -> str:
        """Xác định bias ngay lập tức"""
        recent = df.tail(5)

        if len(recent) < 2:
            return "NEUTRAL"

        highs = recent['high']
        lows = recent['low']

        if highs.iloc[-1] > highs.iloc[-2] and lows.iloc[-1] > lows.iloc[-2]:
            return "BULLISH"
        elif highs.iloc[-1] < highs.iloc[-2] and lows.iloc[-1] < lows.iloc[-2]:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def _get_rsi_trend(self, rsi: pd.Series) -> str:
        """Xác định RSI trend"""
        if len(rsi) < 3:
            return "NEUTRAL"

        current_rsi = rsi.iloc[-1] if hasattr(rsi, 'iloc') else rsi[-1]
        prev_rsi = rsi.iloc[-2] if hasattr(rsi, 'iloc') else rsi[-2]

        if current_rsi > prev_rsi and current_rsi > 50:
            return "BULLISH"
        elif current_rsi < prev_rsi and current_rsi < 50:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def _get_macd_trend_fast(self, macd_hist: pd.Series) -> str:
        """Xác định MACD trend"""
        if len(macd_hist) < 3:
            return "NEUTRAL"

        current_hist = macd_hist.iloc[-1] if hasattr(macd_hist, 'iloc') else macd_hist[-1]
        prev_hist = macd_hist.iloc[-2] if hasattr(macd_hist, 'iloc') else macd_hist[-2]

        if current_hist > 0 and current_hist > prev_hist:
            return "BULLISH"
        elif current_hist < 0 and current_hist < prev_hist:
            return "BEARISH"
        else:
            return "NEUTRAL"

    def _find_immediate_levels(self, df: pd.DataFrame) -> Dict[str, float]:
        """Tìm key levels gần nhất"""
        recent = df.tail(20)
        return {
            'support': recent['low'].min(),
            'resistance': recent['high'].max(),
        }