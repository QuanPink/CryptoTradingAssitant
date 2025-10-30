"""Configuration management"""
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings"""

    # Exchange
    EXCHANGE_ID: str = os.getenv('EXCHANGE_ID', 'binance')
    TIMEFRAME: str = os.getenv('TIMEFRAME', '5m')
    SYMBOLS: List[str] = os.getenv('SYMBOLS', 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT').split(',')

    # Data fetching
    LOOKBACK_BARS: int = int(os.getenv('LOOKBACK_BARS', '24'))
    FETCH_LIMIT: int = int(os.getenv('FETCH_LIMIT', '200'))
    POLL_INTERVAL: int = int(os.getenv('POLL_INTERVAL', '60'))

    # Accumulation thresholds
    ATR_RATIO_THRESHOLD: float = float(os.getenv('ATR_RATIO_THRESHOLD', '0.002'))
    VOL_RATIO_THRESHOLD: float = float(os.getenv('VOL_RATIO_THRESHOLD', '0.7'))
    PRICE_RANGE_THRESHOLD: float = float(os.getenv('PRICE_RANGE_THRESHOLD', '0.008'))

    # Proximity & Breakout
    PROXIMITY_THRESHOLD: float = float(os.getenv('PROXIMITY_THRESHOLD', '0.002'))
    VOL_SPIKE_MULTIPLIER: float = float(os.getenv('VOL_SPIKE_MULTIPLIER', '1.5'))

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')

    # Cooldowns (minutes)
    ACCUMULATION_COOLDOWN_MIN: int = int(os.getenv('ACCUMULATION_COOLDOWN_MIN', '60'))
    BREAKOUT_COOLDOWN_MIN: int = int(os.getenv('BREAKOUT_COOLDOWN_MIN', '60'))
    PROXIMITY_COOLDOWN_MIN: int = int(os.getenv('PROXIMITY_COOLDOWN_MIN', '30'))
    ZONE_EXPIRE_HOURS: int = int(os.getenv('ZONE_EXPIRE_HOURS', '12'))

    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE: str = os.getenv('LOG_FILE', 'data/logs/bot.log')


settings = Settings()
