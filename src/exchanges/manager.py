import time
from typing import Optional, Dict, List

import pandas as pd

from src.utils.cache import MemoryCache
from src.utils.logger import get_logger
from .base import ExchangeInterface
from .binance import BinanceExchange
from .bybit import BybitExchange

logger = get_logger(__name__)


class ExchangeManager:
    """
    Manages multiple exchanges with:
    - Auto-detection of which exchange supports each symbol
    - Caching of detection results
    - Priority-based exchange selection
    """

    def __init__(self, priority: List[str]):
        """Initialize exchange manager"""
        self.exchanges: Dict[str, ExchangeInterface] = {}
        self.priority = priority
        self.cache = MemoryCache()
        self._initialize_exchanges()

    def _initialize_exchanges(self):
        """Initialize all exchanges in priority order"""
        for name in self.priority:
            try:
                if name == 'binance':
                    self.exchanges[name] = BinanceExchange()
                elif name == 'bybit':
                    self.exchanges[name] = BybitExchange()
                else:
                    logger.warning(f"Unknown exchange: {name}")

            except Exception as e:
                logger.error(f"Failed to initialize {name}: {e}")

    def detect_exchange(self, symbol: str) -> Optional[str]:

        cached = self.cache.get('symbol_exchange', symbol)
        if cached:
            logger.debug(f"Cache hit: {symbol} → {cached}")
            return cached

        for name in self.priority:
            ex = self.exchanges[name]

            try:
                markets = ex.client.load_markets()
                formatted = ex.format_symbol(symbol)
                if formatted in markets:
                    logger.info(f"✅Symbol {symbol} supported by {name}")
                    self.cache.set("symbol_exchange", symbol, name)
                    return name

            except Exception as e:
                logger.warning(f"Failed loading markets for {name}: {e}")
                continue

        logger.error(f"{symbol} not found on any exchange")
        return None

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100, max_retries: int = 3) -> Optional[
        pd.DataFrame]:
        """Fetch OHLCV data with auto-detection"""
        exchange_name = self.detect_exchange(symbol)
        if not exchange_name:
            return None

        # Get exchange instance
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            logger.error(f"Exchange {exchange_name} not initialized")
            return None

        for attempt in range(max_retries):
            try:
                df = exchange.fetch_ohlcv(symbol, timeframe, limit)
                if df is not None:
                    return df
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)

        logger.error(f"Failed to fetch {symbol} after {max_retries} attempts")
        return None

    def get_exchange_name(self, symbol: str) -> Optional[str]:
        """Get exchange name for a symbol"""
        return self.detect_exchange(symbol)

    def clear_cache(self):
        """Clear all cached symbol detections"""
        self.cache.clear('symbol_exchange')
        logger.info("Cleared exchange detection cache")
