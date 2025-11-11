import os
from typing import Dict, Any

from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')

# Timeframes to analyze
TIMEFRAMES = ['5m']

# Priority order for exchange auto-detection
EXCHANGE_PRIORITY = ['binance', 'bybit']

CACHE_TTL_SYMBOL_DETECTION = 3600  # 1 hour

SYMBOLS_CONFIG: Dict[str, Dict[str, float]] = {
    'BTC/USDT': {'range_5m': 0.18, 'volume_min': 1000000},
    'ETH/USDT': {'range_5m': 0.22, 'volume_min': 500000},
    'BNB/USDT': {'range_5m': 0.25, 'volume_min': 200000},
    'SOL/USDT': {'range_5m': 0.25, 'volume_min': 300000},
    'HYPE/USDT': {'range_5m': 0.4, 'volume_min': 500000},
}

ACCUMULATION_THRESHOLDS: Dict[str, Dict[str, Any]] = {
    '5m': {
        'N_range': 10,
        'candles_in_range_ratio': 0.85,
        'body_exceed_tolerance': 0.015,
        'wick_tolerance_pct': 0.25,
        'zone_buffer_pct': 0.002,
        'N_volume_lookback': 12,
        'volume_ratio_threshold': 0.65,
        'trend_lookback': 20,
        'ma_period': 20,
        'min_score': 65,
    }
}

FAST_INDICATOR_CONFIG = {
    'ema_fast': 9,
    'ema_medium': 21,
    'ema_slow': 55,
    'rsi_period': 7,
    'macd_fast': 6,
    'macd_slow': 13,
    'macd_signal': 5,
    'atr_period': 14,
}

TRADING_CONFIG = {
    'min_confidence': 65,
    'max_processing_time': 2,
    'aggressive_entries': True,
    'tight_stops': True,
    'risk_per_trade': 0.02,
}
