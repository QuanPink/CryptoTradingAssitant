import numpy as np
import pandas as pd


class TechnicalIndicators:

    @staticmethod
    def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        high: pd.Series = df['high']
        low: pd.Series = df['low']
        close: pd.Series = df['close']
        prev_close = close.shift(1)

        tr = pd.concat([
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs()
        ], axis=1).max(axis=1)

        return tr.rolling(period, min_periods=1).mean()

    @staticmethod
    def bollinger_bands(df: pd.DataFrame, period: int = 20, mult: float = 2):
        ma = df['close'].rolling(period, min_periods=1).mean()
        std = df['close'].rolling(period, min_periods=1).std().fillna(0)

        upper = ma + mult * std
        lower = ma - mult * std
        width = (upper - lower) / ma.replace(0, np.nan)

        return upper, lower, width.fillna(0)

    @staticmethod
    def bb_squeeze(width_series: pd.Series, percentile: float = 15, lookback: int = 120) -> pd.Series:
        rolling_pct = width_series.rolling(lookback, min_periods=10).apply(
            lambda x: np.nanpercentile(x, percentile),
            raw=False
        )
        return (width_series <= rolling_pct).fillna(False)

    @staticmethod
    def atr_compression(atr_series: pd.Series, lookback: int = 120, percentile: float = 20) -> pd.Series:
        rolling_thresh = atr_series.rolling(lookback, min_periods=10).apply(
            lambda x: np.nanpercentile(x, percentile),
            raw=False
        )
        return (atr_series <= rolling_thresh).fillna(False)

    @staticmethod
    def market_structure_flat(df: pd.DataFrame, lookback: int = 12, range_pct: float = 0.03) -> pd.Series:
        high_max = df['high'].rolling(lookback).max()
        low_min = df['low'].rolling(lookback).min()
        price_avg = df['close'].rolling(lookback).mean()

        price_range = (high_max - low_min) / price_avg

        return (price_range < range_pct).fillna(False)

    @staticmethod
    def volume_decreasing(df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        vol_ma = df['volume'].rolling(lookback, min_periods=1).mean()
        prev_ma = vol_ma.shift(1)
        return (vol_ma < prev_ma).fillna(False)
