from typing import Optional

import ccxt
import pandas as pd

from src.utils.logger import get_logger
from .base import ExchangeInterface

logger = get_logger(__name__)


class BybitExchange(ExchangeInterface):

    def __init__(self):
        self.client = ccxt.bybit({
            "enableRateLimit": True,
            "options": {
                "defaultType": "future",
            }
        })

    def format_symbol(self, symbol: str) -> str:
        return symbol.replace(" ", "").upper()

    @staticmethod
    def _convert_timeframe(timeframe: str) -> str:
        """
        Convert CCXT timeframe to Bybit format
        CCXT: '5m', '30m', '1h'
        Bybit: '5', '30', '60' (minutes as integer)
        """
        mapping = {
            '1m': '1',
            '3m': '3',
            '5m': '5',
            '15m': '15',
            '30m': '30',
            '1h': '60',
            '2h': '120',
            '4h': '240',
            '1d': 'D',
            '1w': 'W',
            '1M': 'M'
        }
        return mapping.get(timeframe, timeframe)

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        try:
            formatted = self.format_symbol(symbol)
            bybit_timeframe = self._convert_timeframe(timeframe)

            ohlcv = self.client.fetch_ohlcv(
                formatted,
                timeframe=bybit_timeframe,
                limit=limit,
                params={"category": "linear"}
            )

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)

            df.attrs['symbol'] = symbol
            df.attrs['timeframe'] = timeframe

            return df

        except Exception as e:
            logger.error(f"Bybit fetch error {symbol}: {e}")
            return None

    def get_name(self) -> str:
        return "bybit"
