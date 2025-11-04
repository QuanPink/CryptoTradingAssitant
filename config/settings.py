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
MAX_ZONES_PER_SYMBOL = 10

# Accumulation detection thresholds
ACCUMULATION_THRESHOLDS: Dict[str, Dict] = {
    '5m': {
        'N_range': 6,
        'N_volume_lookback': 12,
        'K_volatility': 0.8,
        'volume_ratio_threshold': 0.75,
        'trend_lookback': 20,
        'max_wick_bars_ratio': 0.3,
        'ma_period': 20
    },
    '15m': {
        'N_range': 5,
        'N_volume_lookback': 10,
        'K_volatility': 0.7,
        'volume_ratio_threshold': 0.7,
        'trend_lookback': 15,
        'max_wick_bars_ratio': 0.25,
        'ma_period': 20
    },
    '30m': {
        'N_range': 4,
        'N_volume_lookback': 8,
        'K_volatility': 0.6,
        'volume_ratio_threshold': 0.65,
        'trend_lookback': 12,
        'max_wick_bars_ratio': 0.2,
        'ma_period': 20
    },
    '1h': {
        'N_range': 4,
        'N_volume_lookback': 8,
        'K_volatility': 0.5,
        'volume_ratio_threshold': 0.6,
        'trend_lookback': 10,
        'max_wick_bars_ratio': 0.15,
        'ma_period': 20
    }
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
