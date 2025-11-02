"""Smart data caching with timeframe-aware strategies"""
import time
from typing import Dict, Optional, Tuple

import pandas as pd

from config.setting import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class DataCache:
    """
    Intelligent data cache with timeframe-specific refresh strategies

    Strategy (Pure Optimal):
    - 5m:  Refresh every 15 minutes (3x candle period)
    - 15m: Refresh every 30 minutes (2x candle period)
    - 30m: Refresh every 45 minutes (1.5x candle period)
    - 1h:  Refresh every 60 minutes (1x candle period)
    """

    def __init__(self):
        self.cache: Dict[Tuple[str, str], Dict] = {}
        self.stats = {
            'hits': 0,
            'misses': 0,
            'full_fetches': 0,
            'incremental_fetches': 0
        }

    def get(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """
        Get cached data if valid

        Returns:
            DataFrame if cache is valid, None otherwise
        """
        cache_key = (symbol, timeframe)
        cache_entry = self.cache.get(cache_key)

        if cache_entry is None:
            self.stats['misses'] += 1
            return None

        # Check if cache is still valid
        if self._is_cache_valid(cache_entry, timeframe):
            self.stats['hits'] += 1
            logger.debug(f"📦 Cache HIT: {symbol} {timeframe}")
            return cache_entry['data'].copy()

        # Cache expired
        self.stats['misses'] += 1
        logger.debug(f"⏰ Cache EXPIRED: {symbol} {timeframe}")
        return None

    def set(self, symbol: str, timeframe: str, df: pd.DataFrame):
        """
        Store data in cache

        Args:
            symbol: Trading symbol
            timeframe: Timeframe string
            df: Full DataFrame (will cache completed candles only)
        """
        if df is None or len(df) < 10:
            logger.warning(f"Cannot cache: insufficient data for {symbol} {timeframe}")
            return

        cache_key = (symbol, timeframe)

        # Cache only completed candles (exclude last 1-2)
        # We exclude 2 to be safe (last might be incomplete, second-last for verification)
        completed_df = df.iloc[:-2].copy()

        self.cache[cache_key] = {
            'data': completed_df,
            'timestamp': time.time(),
            'last_candle_time': completed_df.index[-1] if len(completed_df) > 0 else None,
            'timeframe': timeframe
        }

        logger.debug(
            f"💾 Cached {len(completed_df)} candles for {symbol} {timeframe} "
            f"(TTL: {settings.get_cache_refresh_interval(timeframe)}s)"
        )

    @staticmethod
    def _is_cache_valid(cache_entry: Dict, timeframe: str) -> bool:
        """Check if cache entry is still valid"""
        age = time.time() - cache_entry['timestamp']
        refresh_interval = settings.get_cache_refresh_interval(timeframe)

        is_valid = age < refresh_interval

        if not is_valid:
            logger.debug(
                f"Cache invalid: age={age:.0f}s > refresh_interval={refresh_interval}s"
            )

        return is_valid

    def clear_expired(self):
        """Remove expired cache entries"""
        expired_keys = []

        for cache_key, cache_entry in self.cache.items():
            timeframe = cache_entry['timeframe']
            if not self._is_cache_valid(cache_entry, timeframe):
                expired_keys.append(cache_key)

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.info(f"🧹 Cleared {len(expired_keys)} expired cache entries")

    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total_requests * 100) if total_requests > 0 else 0

        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'hit_rate': f"{hit_rate:.1f}%",
            'full_fetches': self.stats['full_fetches'],
            'incremental_fetches': self.stats['incremental_fetches'],
            'cached_pairs': len(self.cache)
        }

    def log_stats(self):
        """Log cache statistics"""
        stats = self.get_stats()
        logger.info(
            f"📊 Cache stats: "
            f"Hit rate: {stats['hit_rate']} | "
            f"Full: {stats['full_fetches']} | "
            f"Inc: {stats['incremental_fetches']} | "
            f"Cached: {stats['cached_pairs']}"
        )
