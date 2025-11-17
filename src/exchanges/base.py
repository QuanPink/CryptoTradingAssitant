from abc import ABC, abstractmethod
from typing import Optional, Any

import pandas as pd


class ExchangeInterface(ABC):
    """
    Abstract interface for cryptocurrency exchange adapters
    Follows Open/Closed Principle - easy to add new exchanges
    """

    client: Any = None

    @abstractmethod
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV (candlestick) data from exchange

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            timeframe: Candle timeframe (e.g., '5m', '1h')
            limit: Number of candles to fetch

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
            None if fetch failed
        """
        pass

    @abstractmethod
    def format_symbol(self, symbol: str) -> str:
        """
        Format symbol for exchange-specific API requirements

        Args:
            symbol: Standard format 'BTC/USDT'

        Returns:
            Exchange-specific format (e.g., 'BTCUSDT' for Binance)
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get exchange name

        Returns:
            Exchange name string (e.g., 'binance', 'bybit')
        """
        pass
