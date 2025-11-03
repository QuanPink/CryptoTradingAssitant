"""Configuration management"""
import os
from typing import List, Dict

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

    # Monitoring & Performance
    MONITORING_INTERVAL: int = int(os.getenv('MONITORING_INTERVAL', '300'))
    HEALTH_CHECK_INTERVAL: int = int(os.getenv('HEALTH_CHECK_INTERVAL', '1800'))
    MAX_MEMORY_MB: int = int(os.getenv('MAX_MEMORY_MB', '512'))

    # Circuit Breaker
    CIRCUIT_BREAKER_FAILURES: int = int(os.getenv('CIRCUIT_BREAKER_FAILURES', '5'))
    CIRCUIT_BREAKER_TIMEOUT_MIN: int = int(os.getenv('CIRCUIT_BREAKER_TIMEOUT_MIN', '30'))

    # Retry
    MAX_RETRIES: int = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_DELAY_BASE: int = int(os.getenv('RETRY_DELAY_BASE', '2'))

    # ═══════════════════════════════════════════════════════════
    # SYMBOL-SPECIFIC ACCUMULATION RANGE THRESHOLDS
    # ═══════════════════════════════════════════════════════════

    ACCUMULATION_RANGE_THRESHOLDS = {
        'BTC/USDT': {
            '5m': {'min': 0.0008, 'max': 0.0050},  # 0.08% - 0.50%
            '15m': {'min': 0.0025, 'max': 0.0080},  # 0.25% - 0.80%
            '30m': {'min': 0.0040, 'max': 0.0150},  # 0.40% - 1.50%
            '1h': {'min': 0.0070, 'max': 0.0250}  # 0.70% - 2.50%
        },
        'ETH/USDT': {
            '5m': {'min': 0.0010, 'max': 0.0050},  # 0.10% - 0.50%
            '15m': {'min': 0.0030, 'max': 0.0080},  # 0.30% - 0.80%
            '30m': {'min': 0.0050, 'max': 0.0150},  # 0.50% - 1.50%
            '1h': {'min': 0.0070, 'max': 0.0250}  # 0.70% - 2.50%
        },
        'BNB/USDT': {
            '5m': {'min': 0.0010, 'max': 0.0050},  # 0.1% - 0.50%
            '15m': {'min': 0.0030, 'max': 0.0080},  # 0.30% - 0.80%
            '30m': {'min': 0.0050, 'max': 0.0150},  # 0.50% - 1.50%
            '1h': {'min': 0.0070, 'max': 0.0250}  # 0.70% - 2.50%
        },
        'SOL/USDT': {
            '5m': {'min': 0.0015, 'max': 0.0100},  # 0.15% - 1.00%
            '15m': {'min': 0.0040, 'max': 0.0150},  # 0.40% - 1.50%
            '30m': {'min': 0.0060, 'max': 0.0250},  # 0.60% - 2.50%
            '1h': {'min': 0.0100, 'max': 0.0350}  # 1.00% - 3.50%
        },
        'HYPE/USDT': {
            '5m': {'min': 0.0015, 'max': 0.0100},  # 0.15% - 1.00%
            '15m': {'min': 0.0050, 'max': 0.0150},  # 0.50% - 1.50%
            '30m': {'min': 0.0080, 'max': 0.0250},  # 0.80% - 2.50%
            '1h': {'min': 0.0100, 'max': 0.0350}  # 1.00% - 3.50%
        }
    }

    # Default thresholds for unknown symbols
    DEFAULT_ACCUMULATION_THRESHOLDS = {
        '5m': {'min': 0.0015, 'max': 0.0060},
        '15m': {'min': 0.0040, 'max': 0.0100},
        '30m': {'min': 0.0060, 'max': 0.0150},
        '1h': {'min': 0.0100, 'max': 0.0250}
    }

    # ═══════════════════════════════════════════════════════════
    # TIMEFRAME-SPECIFIC PARAMETERS
    # ═══════════════════════════════════════════════════════════

    TIMEFRAME_SETTINGS = {
        '5m': {
            # Volume spike detection
            'vol_spike_short_mult': 1.6,
            'vol_spike_medium_mult': 1.3,
            'vol_lookback_short': 15,
            'vol_lookback_medium': 30,

            # Breakout detection
            'breakout_buffer': 0.0003,
            'confirmation_bars': 1,

            # Accumulation detection
            'lookback_windows': [8, 9, 10, 12, 14, 16, 18, 20],
            'max_breakout_ratio': 0.10,
            'volume_suppression_ratio': 1.2,

            # Other
            'proximity_threshold': 0.0015,
            'consensus_required': 1
        },
        '15m': {
            'vol_spike_short_mult': 1.5,
            'vol_spike_medium_mult': 1.2,
            'vol_lookback_short': 12,
            'vol_lookback_medium': 24,

            'breakout_buffer': 0.0005,
            'confirmation_bars': 1,

            'lookback_windows': [10, 11, 12, 14, 16, 18, 20, 22, 24],
            'max_breakout_ratio': 0.15,
            'volume_suppression_ratio': 1.2,

            'proximity_threshold': 0.002,
            'consensus_required': 1
        },
        '30m': {
            'vol_spike_short_mult': 1.4,
            'vol_spike_medium_mult': 1.1,
            'vol_lookback_short': 10,
            'vol_lookback_medium': 20,

            'breakout_buffer': 0.0008,
            'confirmation_bars': 2,

            'lookback_windows': [12, 13, 14, 16, 18, 20, 22, 24, 26, 28],
            'max_breakout_ratio': 0.20,
            'volume_suppression_ratio': 1.3,

            'proximity_threshold': 0.002,
            'consensus_required': 1
        },
        '1h': {
            'vol_spike_short_mult': 1.3,
            'vol_spike_medium_mult': 1.0,
            'vol_lookback_short': 8,
            'vol_lookback_medium': 16,

            'breakout_buffer': 0.0012,
            'confirmation_bars': 2,

            'lookback_windows': [14, 16, 18, 20, 22, 24, 26, 28, 30, 32],
            'max_breakout_ratio': 0.25,
            'volume_suppression_ratio': 1.4,

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

    @classmethod
    def get_accumulation_range(cls, symbol: str, timeframe: str) -> Dict[str, float]:
        """
        Get accumulation range thresholds for symbol and timeframe

        Returns:
            {'min': float, 'max': float}
        """
        symbol_thresholds = cls.ACCUMULATION_RANGE_THRESHOLDS.get(
            symbol,
            cls.DEFAULT_ACCUMULATION_THRESHOLDS
        )
        return symbol_thresholds.get(timeframe, {'min': 0.001, 'max': 0.015})

    # Enable/disable caching
    ENABLE_DATA_CACHE: bool = os.getenv('ENABLE_DATA_CACHE', 'true').lower() == 'true'

    # Timeframe to seconds mapping
    TIMEFRAME_TO_SECONDS = {
        '5m': 300,
        '15m': 900,
        '30m': 1800,
        '1h': 3600
    }

    # Cache refresh intervals (Pure Optimal Strategy)
    CACHE_REFRESH_INTERVALS = {
        '5m': 900,  # 15 minutes (3x candle period)
        '15m': 1800,  # 30 minutes (2x candle period)
        '30m': 2700,  # 45 minutes (1.5x candle period)
        '1h': 3600  # 60 minutes (1x candle period)
    }

    # Incremental fetch limits (how many recent candles to fetch)
    INCREMENTAL_FETCH_LIMITS = {
        '5m': 3,  # Fetch 3 recent candles
        '15m': 3,  # Fetch 3 recent candles
        '30m': 2,  # Fetch 2 recent candles
        '1h': 2  # Fetch 2 recent candles
    }

    # Cache validation settings
    CACHE_VERIFY_TOLERANCE: float = 0.0001  # 0.01% price difference tolerance

    @classmethod
    def get_cache_refresh_interval(cls, timeframe: str) -> int:
        """Get cache refresh interval for timeframe"""
        return cls.CACHE_REFRESH_INTERVALS.get(timeframe, 900)

    @classmethod
    def get_incremental_fetch_limit(cls, timeframe: str) -> int:
        """Get incremental fetch limit for timeframe"""
        return cls.INCREMENTAL_FETCH_LIMITS.get(timeframe, 3)


settings = Settings()
