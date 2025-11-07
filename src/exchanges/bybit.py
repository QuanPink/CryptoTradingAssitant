from typing import Optional

import ccxt
import pandas as pd

from src.utils.logger import get_logger
from .base import ExchangeInterface

logger = get_logger(__name__)


class BybitExchange(ExchangeInterface):
    """Bybit Futures (USDT perpetual) adapter"""

    def __init__(self):
        """Initialize Bybit client with futures market"""
        self.client = ccxt.bybit()
        self.client.options['defaultType'] = 'future'
        self.name = 'bybit'
        logger.info(f"✅ Initialized {self.name} exchange (futures)")

    def format_symbol(self, symbol: str) -> str:
        """Format symbol for Bybit API"""
        return symbol + ':USDT'

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data from Bybit Futures"""
        try:
            formatted_symbol = self.format_symbol(symbol)

            # Fetch from API
            ohlcv = self.client.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)

            if not ohlcv:
                logger.warning(f"No data returned for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            return df

        except ccxt.BadSymbol as e:
            logger.error(f"Invalid symbol {symbol} on Bybit: {e}")
            return None
        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching {symbol} from Bybit: {e}")
            return None

    def get_name(self) -> str:
        """Get exchange name"""
        return self.name
