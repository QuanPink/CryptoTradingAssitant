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
        return symbol

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int) -> Optional[pd.DataFrame]:
        try:
            formatted = self.format_symbol(symbol)

            ohlcv = self.client.fetch_ohlcv(
                formatted,
                timeframe=timeframe,
                limit=limit,
                params={"category": "linear"}
            )

            df = pd.DataFrame(
                ohlcv,
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df

        except Exception as e:
            logger.error(f"Bybit fetch error {symbol}: {e}")
            return None

    def get_name(self) -> str:
        return "bybit"
