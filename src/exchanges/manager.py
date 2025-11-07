from typing import Optional, Dict, List

import pandas as pd

from config.settings import CACHE_TTL_SYMBOL_DETECTION
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
        """Auto-detect which exchange supports a symbol (with caching)"""
        # Check cache first
        cached = self.cache.get('symbol_exchange', symbol)
        if cached:
            logger.debug(f"Cache hit: {symbol} → {cached}")
            return cached

        # Try exchanges in priority order
        for name in self.priority:
            exchange = self.exchanges.get(name)
            if not exchange:
                continue

            try:
                # Test if symbol exists by fetching 1 candle
                df = exchange.fetch_ohlcv(symbol, '1h', limit=1)

                if df is not None and not df.empty:
                    logger.info(f"✅ Symbol {symbol} found on {name}")

                    # Cache the result
                    self.cache.set(
                        'symbol_exchange',
                        symbol,
                        name,
                        ttl=CACHE_TTL_SYMBOL_DETECTION
                    )
                    return name

            except Exception as e:
                logger.debug(f"Symbol {symbol} not on {name}: {e}")
                continue

        logger.error(f"❌ Symbol {symbol} not found on any exchange")
        return None

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data with auto-detection"""
        # Auto-detect exchange
        exchange_name = self.detect_exchange(symbol)
        if not exchange_name:
            return None

        # Get exchange instance
        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            logger.error(f"Exchange {exchange_name} not initialized")
            return None

        # Fetch data
        return exchange.fetch_ohlcv(symbol, timeframe, limit)

    def get_exchange_name(self, symbol: str) -> Optional[str]:
        """Get exchange name for a symbol"""
        return self.detect_exchange(symbol)

    def clear_cache(self):
        """Clear all cached symbol detections"""
        self.cache.clear('symbol_exchange')
        logger.info("Cleared exchange detection cache")
