from typing import Optional, Dict

import ccxt
import pandas as pd

from config.settings import Settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ExchangeManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.exchanges = {}
        self._initialize_exchanges()
        self.symbol_cache: Dict[str, str] = {}

    def _initialize_exchanges(self):
        """Initialize all exchanges in priority order"""
        for exchange_name in self.settings.EXCHANGE_PRIORITY:
            try:
                if exchange_name == 'binance':
                    exchange = ccxt.binance()
                    exchange.options['defaultType'] = 'future'
                    self.exchanges[exchange_name] = exchange
                elif exchange_name == 'bybit':
                    exchange = ccxt.bybit()
                    exchange.options['defaultType'] = 'future'
                    self.exchanges[exchange_name] = exchange
                logger.info(f"Initialized {exchange_name} exchange")
            except Exception as e:
                logger.error(f"Failed to initialize {exchange_name}: {str(e)}")

    def _detect_exchange_for_symbol(self, symbol: str) -> Optional[str]:
        """Auto-detect which exchange supports this symbol"""
        # Check cache first
        if symbol in self.symbol_cache:
            return self.symbol_cache[symbol]

        # Try exchanges in priority order
        for exchange_name in self.settings.EXCHANGE_PRIORITY:
            exchange = self.exchanges.get(exchange_name)
            if not exchange:
                continue

            try:
                # Test if symbol exists by fetching ticker
                exchange.fetch_ticker(symbol)
                logger.info(f"✅ Symbol {symbol} found on {exchange_name}")
                self.symbol_cache[symbol] = exchange_name
                return exchange_name
            except (ccxt.BadSymbol, ccxt.ExchangeError, ccxt.NetworkError):
                continue
            except Exception as e:
                logger.warning(f"Error checking {symbol} on {exchange_name}: {str(e)}")
                continue

        logger.error(f"❌ Symbol {symbol} not found on any exchange")
        return None

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data with auto-exchange detection"""
        # Auto-detect exchange for symbol
        exchange_name = self._detect_exchange_for_symbol(symbol)
        if not exchange_name:
            return None

        exchange = self.exchanges.get(exchange_name)
        if not exchange:
            logger.error(f"Exchange {exchange_name} not initialized")
            return None

        try:
            logger.info(f"📡 Fetching {symbol} from {exchange_name} ({timeframe})")

            # Convert symbol format if needed
            formatted_symbol = self._format_symbol_for_exchange(symbol, exchange_name)

            ohlcv = exchange.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)

            if not ohlcv or len(ohlcv) == 0:
                logger.error(f"No data returned for {symbol}")
                return None

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            logger.info(f"✅ Data fetched: {len(df)} bars, Close: {df['close'].iloc[-1]:.2f}")
            return df

        except Exception as e:
            logger.error(f"Error fetching data for {symbol} from {exchange_name}: {str(e)}")
            # Remove from cache on error
            if symbol in self.symbol_cache:
                del self.symbol_cache[symbol]
            return None

    @staticmethod
    def _format_symbol_for_exchange(symbol: str, exchange_name: str) -> str:
        """Format symbol according to exchange requirements"""
        if exchange_name == 'binance':
            return symbol.replace('/', '')
        elif exchange_name == 'bybit':
            return symbol + ':USDT'
        return symbol

    def get_exchange_for_symbol(self, symbol: str) -> Optional[str]:
        """Get the exchange name for a symbol (from cache or auto-detect)"""
        return self._detect_exchange_for_symbol(symbol)
