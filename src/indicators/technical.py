from typing import Dict, Tuple
import numpy as np
import pandas as pd
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TechnicalIndicator:
    """
    Technical analysis indicators
    - ATR (Average True Range) for volatility
    - EMA (Exponential Moving Average) for trends
    - Trend detection algorithm
    """

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range (ATR) for volatility measurement"""
        if df is None or df.empty:
            return pd.Series(dtype=float)

        try:
            high_low = df['high'] - df['low']
            high_close = np.abs(df['high'] - df['close'].shift())
            low_close = np.abs(df['low'] - df['close'].shift())

            true_range = np.maximum(np.maximum(high_low, high_close), low_close)
            atr = true_range.rolling(window=period).mean()

            return atr

        except Exception as e:
            logger.error(f"Error calculating ATR: {str(e)}")
            return pd.Series(dtype=float)

    @staticmethod
    def calculate_ema(df: pd.DataFrame, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        if df is None or df.empty or 'close' not in df.columns:
            return pd.Series(dtype=float)

        try:
            return df['close'].ewm(span=period, adjust=False).mean()
        except Exception as e:
            logger.error(f"Error calculating EMA: {str(e)}")
            return pd.Series(dtype=float)

    @staticmethod
    def identify_trend(df: pd.DataFrame, lookback: int, ma_period: int = 20) -> Dict[str, float]:
        """
        Identify previous trend direction and strength using EMA
        """
        # Validate inputs
        if (df is None or df.empty or len(df) < max(lookback, ma_period) or
                'close' not in df.columns):
            return {
                'trend': 'SIDEWAYS',
                'strength': 0,
                'trend_score': 0,
                'ema_slope': 0
            }

        try:
            # Calculate EMA
            ema_series = TechnicalIndicator.calculate_ema(df, ma_period)

            if ema_series.empty:
                return {
                    'trend': 'SIDEWAYS',
                    'strength': 0,
                    'trend_score': 0,
                    'ema_slope': 0
                }

            # Get recent data for trend analysis
            recent_data = df.tail(lookback).copy()
            recent_ema = ema_series.tail(lookback)

            # Calculate trend strength based on EMA slope
            if len(recent_ema) >= 2:
                ema_slope = (recent_ema.iloc[-1] - recent_ema.iloc[0]) / recent_ema.iloc[0] * 100
            else:
                ema_slope = 0

            # Calculate how many bars are above/below EMA
            bars_above_ema = int((recent_data['close'] > recent_ema).sum())
            bars_below_ema = int((recent_data['close'] < recent_ema).sum())

            # Determine trend
            if ema_slope > 0.5 and bars_above_ema > bars_below_ema:
                trend = 'UPTREND'
                trend_score = min(25, abs(ema_slope) * 2)
            elif ema_slope < -0.5 and bars_below_ema > bars_above_ema:
                trend = 'DOWNTREND'
                trend_score = min(25, abs(ema_slope) * 2)
            else:
                trend = 'SIDEWAYS'
                trend_score = 5

            return {
                'trend': trend,
                'strength': abs(ema_slope),
                'trend_score': trend_score,
                'ema_slope': ema_slope
            }

        except Exception as e:
            logger.error(f"Error identifying trend: {str(e)}")
            return {
                'trend': 'SIDEWAYS',
                'strength': 0,
                'trend_score': 0,
                'ema_slope': 0
            }

    @staticmethod
    def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def calculate_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """Calculate Volume Weighted Average Price"""
        typical_price = (high + low + close) / 3
        vwap = (typical_price * volume).cumsum() / volume.cumsum()
        return vwap

    @staticmethod
    def calculate_macd_fast(prices: pd.Series, fast: int = 6, slow: int = 13, signal: int = 5) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD với parameters nhanh cho 5p"""
        ema_fast = prices.ewm(span=fast).mean()
        ema_slow = prices.ewm(span=slow).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal).mean()
        macd_histogram = macd - macd_signal
        return macd, macd_signal, macd_histogram

    def vwap(self, df: pd.DataFrame) -> pd.Series:
        return self.calculate_vwap(df['high'], df['low'], df['close'], df['volume'])

    def atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        return self.calculate_atr(df, period)

    def macd_fast(self, prices: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
        return self.calculate_macd_fast(prices)