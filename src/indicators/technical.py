"""Technical indicators"""
import pandas as pd


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Calculate Average True Range"""
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    return tr.rolling(period, min_periods=1).mean()


def bollinger_band_width(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """Calculate Bollinger Bands width"""
    mid = df['close'].rolling(period).mean()
    std = df['close'].rolling(period).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    width = (upper - lower) / mid
    return width
