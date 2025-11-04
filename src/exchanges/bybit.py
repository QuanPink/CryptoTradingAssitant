from typing import Optional

import ccxt
import pandas as pd

from src.utils.logger import get_logger
from .base import ExchangeInterface

logger = get_logger(__name__)


class BybitExchange(ExchangeInterface):
    """
    Bybit Futures (USDT perpetual) adapter
    """

    def __init__(self):
        """Initialize Bybit client with futures market"""
        self.client = ccxt.bybit()
        self.client.options['defaultType'] = 'future'  # Use futures market
        self.name = 'bybit'
        logger.info(f"✅ Initialized {self.name} exchange (futures)")

    def format_symbol(self, symbol: str) -> str:
        """
        Format symbol for Bybit API

        Args:
            symbol: Standard format 'BTC/USDT'

        Returns:
            Bybit format 'BTC/USDT:USDT' (slash + suffix for perpetual)
        """
        return symbol + ':USDT'

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV data from Bybit Futures

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Timeframe (e.g., '5m', '1h')
            limit: Number of candles

        Returns:
            DataFrame or None if failed
        """
        try:
            formatted_symbol = self.format_symbol(symbol)

            # Fetch from API
            ohlcv = self.client.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)

            if not ohlcv:
                logger.warning(f"No data returned for {symbol}")
                return None

            # Convert to DataFrame
            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            logger.info(
                f"📊 {symbol} {timeframe}: {len(df)} bars | "
                f"Close: {df['close'].iloc[-1]:.2f} | "
                f"Volume: {df['volume'].iloc[-1]:.0f}"
            )

            logger.debug(f"✅ Fetched {len(df)} bars for {symbol} on {timeframe}")
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
