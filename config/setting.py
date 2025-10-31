"""Configuration management"""
import os
from typing import List

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings"""

    # Exchange
    EXCHANGES: List[str] = os.getenv('EXCHANGES', 'binance,bybit').split(',')
    TIMEFRAMES: List[str] = os.getenv('TIMEFRAMES', '5m,15m,30m,1h').split(',')
    SYMBOLS: List[str] = os.getenv('SYMBOLS', 'BTC/USDT,ETH/USDT,BNB/USDT,SOL/USDT,HYPE/USDT').split(',')

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

    # Timeframe-specific parameters
    TIMEFRAME_SETTINGS = {
        '5m': {
            # Detection thresholds
            'atr_threshold': 0.0025,
            'vol_ratio_threshold': 0.65,
            'price_range_threshold': 0.01,

            # Volume spike detection
            'vol_spike_short_mult': 2.2,
            'vol_spike_medium_mult': 1.8,
            'vol_lookback_short': 15,
            'vol_lookback_medium': 30,

            # Breakout detection
            'breakout_buffer': 0.001,
            'confirmation_bars': 1,

            # Other
            'proximity_threshold': 0.0015,
            'consensus_required': 2
        },
        '15m': {
            'atr_threshold': 0.0022,
            'vol_ratio_threshold': 0.68,
            'price_range_threshold': 0.009,

            'vol_spike_short_mult': 2.0,
            'vol_spike_medium_mult': 1.7,
            'vol_lookback_short': 12,
            'vol_lookback_medium': 24,

            'breakout_buffer': 0.0015,
            'confirmation_bars': 1,

            'proximity_threshold': 0.002,
            'consensus_required': 1
        },
        '30m': {
            'atr_threshold': 0.002,
            'vol_ratio_threshold': 0.7,
            'price_range_threshold': 0.008,

            'vol_spike_short_mult': 1.8,
            'vol_spike_medium_mult': 1.6,
            'vol_lookback_short': 10,
            'vol_lookback_medium': 20,

            'breakout_buffer': 0.002,
            'confirmation_bars': 2,

            'proximity_threshold': 0.002,
            'consensus_required': 1
        },
        '1h': {
            'atr_threshold': 0.0018,
            'vol_ratio_threshold': 0.72,
            'price_range_threshold': 0.007,

            'vol_spike_short_mult': 1.6,
            'vol_spike_medium_mult': 1.5,
            'vol_lookback_short': 8,
            'vol_lookback_medium': 16,

            'breakout_buffer': 0.0025,
            'confirmation_bars': 2,

            'proximity_threshold': 0.0025,
            'consensus_required': 1
        }
    }

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

    @classmethod
    def get_tf_setting(cls, timeframe: str, key: str, default=None):
        """Get timeframe-specific setting with fallback to 15m"""
        tf_config = cls.TIMEFRAME_SETTINGS.get(timeframe, cls.TIMEFRAME_SETTINGS['15m'])
        return tf_config.get(key, default)


settings = Settings()
