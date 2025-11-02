"""Exchange connection and data fetching management"""
import concurrent.futures
import os
import time
from typing import Dict, Optional, Set

import ccxt
import pandas as pd
import psutil

from config.setting import settings
from src.utils.helpers import ohlcv_to_df
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ExchangeHealthError(Exception):
    """Raised when no healthy exchanges are available"""
    pass


class ExchangeManager:
    """Manages exchange connections and data fetching"""

    def __init__(self):
        self.exchanges: Dict = {}
        self.markets_cache: Dict[str, Set] = {}
        self.symbol_exchange_map: Dict[str, str] = {}

        self._initialize_exchanges()
        self._load_all_markets()
        self._build_symbol_map()

    def _initialize_exchanges(self):
        """Initialize all configured exchanges with timeout"""
        for exchange_id in settings.EXCHANGES:
            try:
                exchange_class = getattr(ccxt, exchange_id)

                # Determine market type for each exchange
                if exchange_id == 'binance':
                    market_type = 'future'  # Binance USDT-M Futures
                elif exchange_id == 'bybit':
                    market_type = 'linear'  # Bybit USDT Perpetual
                else:
                    market_type = 'future'

                self.exchanges[exchange_id] = exchange_class({
                    'enableRateLimit': True,
                    'timeout': 60000,  # 30 seconds
                    'rateLimit': 1200,  # 1 second between requests
                    'verbose': False,
                    'options': {
                        'defaultType': market_type,
                        'adjustForTimeDifference': True
                    }
                })

                logger.info(f"✅ Initialized {exchange_id} exchange (FUTURES - {market_type})")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {exchange_id}: {e}")

    def _load_all_markets(self):
        """Load available markets from all exchanges in parallel"""

        logger.info("Loading markets from all exchanges...")
        start_time = time.time()

        def load_single_exchange(exchange_id: str, exchange) -> tuple:
            """Load markets for a single exchange"""
            try:
                exchange_markets = exchange.load_markets()
                logger.info(f"✅ Loaded {len(exchange_markets)} markets from {exchange_id}")
                return exchange_id, set(exchange_markets.keys())
            except Exception as e:
                logger.error(f"❌ Failed to load markets from {exchange_id}: {e}")
                return exchange_id, set()

        # ═══════════════════════════════════════════════════════════
        # PARALLEL LOADING - Load all exchanges simultaneously
        # ═══════════════════════════════════════════════════════════

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.exchanges)) as executor:
            # Submit all tasks
            futures = {
                executor.submit(load_single_exchange, exchange_id, exchange): exchange_id
                for exchange_id, exchange in self.exchanges.items()
            }

            # Collect results as they complete
            for future in concurrent.futures.as_completed(futures):
                exchange_id, market_symbols = future.result()
                self.markets_cache[exchange_id] = market_symbols

        # ═══════════════════════════════════════════════════════════

        # Validate that at least one exchange loaded successfully
        successful_exchanges = sum(1 for markets in self.markets_cache.values() if markets)

        if successful_exchanges == 0:
            raise ExchangeHealthError("Failed to load markets from any exchange")

        elapsed = time.time() - start_time
        logger.info(
            f"✅ Markets loaded in {elapsed:.1f}s - "
            f"{successful_exchanges}/{len(self.exchanges)} exchanges ready"
        )

    def _build_symbol_map(self):
        """
        Build symbol → exchange mapping with priority

        Priority: First exchange in EXCHANGES list gets priority
        """
        logger.info(f"Building symbol mapping for {len(settings.SYMBOLS)} symbols...")

        for symbol in settings.SYMBOLS:
            found = False

            # Try exchanges in priority order
            for exchange_id in settings.EXCHANGES:
                if symbol in self.markets_cache.get(exchange_id, set()):
                    self.symbol_exchange_map[symbol] = exchange_id

                    # Log with priority indication
                    if exchange_id == settings.EXCHANGES[0]:
                        logger.info(f"✅ {symbol} → {exchange_id} (primary)")
                    else:
                        logger.info(f"✅ {symbol} → {exchange_id} (fallback)")

                    found = True
                    break

            if not found:
                logger.warning(f"⚠️ {symbol} → NOT AVAILABLE on any exchange")

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = None) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data with retry mechanism"""
        if limit is None:
            limit = settings.FETCH_LIMIT

        exchange_id = self.symbol_exchange_map.get(symbol)
        if not exchange_id:
            logger.error(f'[SKIP] {symbol} not available on any exchange')
            return None

        exchange = self.exchanges[exchange_id]

        # Retry with exponential backoff
        for attempt in range(settings.MAX_RETRIES):
            result = self._attempt_fetch_ohlcv(exchange, symbol, timeframe, limit, attempt)
            if result is not None:
                return result

        logger.error(f'All retries failed for {symbol}')
        return None

    def _attempt_fetch_ohlcv(self, exchange, symbol: str, timeframe: str,
                             limit: int, attempt: int) -> Optional[pd.DataFrame]:
        """Single fetch attempt"""
        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

            if not ohlcv or len(ohlcv) == 0:
                logger.warning(f'Empty OHLCV data for {symbol} {timeframe}')
                return None

            return ohlcv_to_df(ohlcv)

        except ccxt.NetworkError as e:
            return self._handle_network_error(symbol, attempt, e)

        except ccxt.ExchangeError as e:
            logger.error(f'Exchange error for {symbol} {timeframe}: {e}')
            return None

        except Exception as e:
            logger.error(f'Unexpected error fetching {symbol} {timeframe}: {e}')
            return None

    @staticmethod
    def _handle_network_error(symbol: str, attempt: int, error: Exception) -> None:
        """Handle network error with retry logic"""
        wait_time = settings.RETRY_DELAY_BASE ** attempt
        logger.warning(
            f'Network error for {symbol} (attempt {attempt + 1}/{settings.MAX_RETRIES}): {error}'
        )

        if attempt < settings.MAX_RETRIES - 1:
            logger.debug(f'Retrying in {wait_time}s...')
            time.sleep(wait_time)

        return None

    def health_check(self) -> Dict:
        """Quick health check for exchanges"""
        health = {}

        for exchange_id, exchange in self.exchanges.items():
            start_time = time.time()
            try:
                if exchange_id == 'binance':
                    exchange.fetch_status()

                else:
                    exchange.fetch_ticker('BTC/USDT')

                latency = (time.time() - start_time) * 1000

                health[exchange_id] = {
                    'status': 'healthy',
                    'latency_ms': round(latency, 2),
                    'symbols_available': len(self.markets_cache.get(exchange_id, set()))
                }
            except Exception as e:
                health[exchange_id] = {
                    'status': 'unhealthy',
                    'error': str(e)[:100]
                }

        logger.info(f"💊 Exchange health: {health}")
        return health

    def log_performance_metrics(self):
        """Log current performance metrics"""
        try:

            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            cpu_percent = process.cpu_percent(interval=1)

            logger.info(
                f"📊 Performance metrics:\n"
                f"   Memory: {memory_mb:.1f}MB / {settings.MAX_MEMORY_MB}MB\n"
                f"   CPU: {cpu_percent:.1f}%\n"
                f"   Exchanges: {len(self.exchanges)}"
            )

            if memory_mb > settings.MAX_MEMORY_MB:
                logger.warning(
                    f"⚠️ Memory usage high: {memory_mb:.1f}MB > {settings.MAX_MEMORY_MB}MB"
                )

        except ImportError:
            logger.debug("psutil not available - skipping metrics")
        except Exception as e:
            logger.error(f"Error logging metrics: {e}")

    def shutdown(self):
        """Close all exchange connections"""
        for exchange_id in self.exchanges:
            try:
                if hasattr(self.exchanges[exchange_id], 'close'):
                    self.exchanges[exchange_id].close()
                logger.info(f"✅ Closed {exchange_id} connection")
            except Exception as e:
                logger.debug(f"Error closing {exchange_id}: {e}")
