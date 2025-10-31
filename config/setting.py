"""Configuration management"""
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings"""

    # Exchange
    EXCHANGE_ID: str = os.getenv('EXCHANGE_ID', 'binance')
    TIMEFRAMES: List[str] = os.getenv('TIMEFRAMES', '5m,15m,30m,1h').split(',')
    SYMBOLS: List[str] = os.getenv('SYMBOLS', 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT').split(',')

    # Data fetching
    LOOKBACK_BARS: int = int(os.getenv('LOOKBACK_BARS', '24'))
    FETCH_LIMIT: int = int(os.getenv('FETCH_LIMIT', '50'))
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

    # Timeframe metadata
    TIMEFRAME_METADATA = {
        '5m': {
            'label': '5 phút',
            'duration_factor': 5 / 60,
            'style': '⚡ Scalping',
            'risk': 'Cao',
            'sl_range': '0.3-0.8%',
            'hold_time': '< 4h'
        },
        '15m': {
            'label': '15 phút',
            'duration_factor': 15 / 60,
            'style': '📊 Intraday',
            'risk': 'Trung bình',
            'sl_range': '0.5-1.2%',
            'hold_time': '4-12h'
        },
        '30m': {
            'label': '30 phút',
            'duration_factor': 30 / 60,
            'style': '📈 Swing ngắn',
            'risk': 'Trung bình',
            'sl_range': '0.8-2%',
            'hold_time': '12-24h'
        },
        '1h': {
            'label': '1 giờ',
            'duration_factor': 1,
            'style': '🎯 Swing dài',
            'risk': 'Thấp',
            'sl_range': '1-3%',
            'hold_time': '1-3 ngày'
        }
    }


settings = Settings()
