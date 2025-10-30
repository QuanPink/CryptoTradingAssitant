"""Helper utilities"""
import math
from typing import List

import pandas as pd


def ohlcv_to_df(ohlcv: List[List[float]]) -> pd.DataFrame:
    """Convert OHLCV list to DataFrame"""
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df


def align_to_next_5min() -> float:
    """Calculate seconds until next 5-minute mark"""
    now = pd.Timestamp.utcnow()
    minute = now.minute
    next_min = (math.floor(minute / 5) + 1) * 5

    if next_min >= 60:
        next_min = 0
        target = now.replace(minute=0, second=0, microsecond=0) + pd.Timedelta(hours=1)
    else:
        target = now.replace(minute=next_min, second=0, microsecond=0)

    delta = (target - now).total_seconds()
    return max(delta, 0)
