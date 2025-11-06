import os
from typing import List, Dict

from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')

# List of symbols to analyze
SYMBOLS: List[str] = [
    'BTC/USDT',
    'ETH/USDT',
    'BNB/USDT',
    'SOL/USDT',
    'HYPE/USDT'
]

# Timeframes to analyze
TIMEFRAMES = ['5m', '15m', '30m', '1h']

# Priority order for exchange auto-detection
EXCHANGE_PRIORITY = ['binance', 'bybit']

CACHE_TTL_SYMBOL_DETECTION = 3600  # 1 hour
CACHE_TTL_NOTIFIED_ACCUMULATION = 7200  # 2 hours
CACHE_TTL_ACCUMULATION_ZONES = 86400  # 24 hours

MONITORING_INTERVAL = 60
MAX_ZONES_PER_SYMBOL = 25

# Accumulation detection thresholds
ACCUMULATION_THRESHOLDS: Dict[str, Dict] = {
    '5m': {
        'N_range': 6,
        'candles_in_range_ratio': 0.80,  # 80% nến trong range
        'body_exceed_tolerance': 0.03,
        'wick_tolerance_pct': 0.30,
        'zone_buffer_pct': 0.0,
        'N_volume_lookback': 12,
        'volume_ratio_threshold': 0.85,
        'trend_lookback': 20,
        'ma_period': 20,
    },
    '15m': {
        'N_range': 6,
        'candles_in_range_ratio': 0.80,  # 80% nến trong range
        'body_exceed_tolerance': 0.04,
        'wick_tolerance_pct': 0.25,
        'zone_buffer_pct': 0.0,
        'N_volume_lookback': 10,
        'volume_ratio_threshold': 0.8,
        'trend_lookback': 15,
        'ma_period': 20,
    },
    '30m': {
        'N_range': 5,
        'candles_in_range_ratio': 0.80,  # 80% nến trong range
        'body_exceed_tolerance': 0.03,
        'wick_tolerance_pct': 0.2,
        'zone_buffer_pct': 0.0,
        'N_volume_lookback': 8,
        'volume_ratio_threshold': 0.75,
        'trend_lookback': 12,
        'ma_period': 20,
    },
    '1h': {
        'N_range': 4,
        'candles_in_range_ratio': 0.80,  # 80% nến trong range
        'body_exceed_tolerance': 0.02,
        'wick_tolerance_pct': 0.15,
        'zone_buffer_pct': 0.0,
        'N_volume_lookback': 8,
        'volume_ratio_threshold': 0.7,
        'trend_lookback': 10,
        'ma_period': 20,
    }
}

# Range thresholds (% của giá)
SYMBOL_RANGE_SETTINGS: Dict[str, Dict[str, float]] = {
    'BTC/USDT': {
        '5m': 0.3,  # Range tối đa 0.3%
        '15m': 0.6,
        '30m': 0.9,
        '1h': 1.2,
    },
    'ETH/USDT': {
        '5m': 0.35,
        '15m': 0.9,
        '30m': 1.5,
        '1h': 2.0,
    },
    'BNB/USDT': {
        '5m': 0.40,
        '15m': 1,
        '30m': 1.5,
        '1h': 2.3,
    },
    'SOL/USDT': {
        '5m': 0.50,
        '15m': 0.65,
        '30m': 1,
        '1h': 1.30,
    },
    'HYPE/USDT': {
        '5m': 0.55,
        '15m': 1.0,
        '30m': 1.5,
        '1h': 3.0,
    },
}

# Breakout detection thresholds
BREAKOUT_THRESHOLDS: Dict[str, Dict] = {
    '5m': {
        'soft_break': 0.0015,  # 0.15%
        'confirmed_break': 0.003,  # 0.3%
        'strong_break': 0.005,  # 0.5%
        'volume_spike_threshold': 1.5,
        'cooldown_period': 30,  # candles
    },
    '15m': {
        'soft_break': 0.0012,
        'confirmed_break': 0.0025,
        'strong_break': 0.004,
        'volume_spike_threshold': 1.8,
        'cooldown_period': 20,
    },
    '30m': {
        'soft_break': 0.001,
        'confirmed_break': 0.002,
        'strong_break': 0.003,
        'volume_spike_threshold': 2.0,
        'cooldown_period': 15,
    },
    '1h': {
        'soft_break': 0.0008,
        'confirmed_break': 0.0015,
        'strong_break': 0.0025,
        'volume_spike_threshold': 2.2,
        'cooldown_period': 10,
    }
}
