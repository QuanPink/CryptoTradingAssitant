import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')

    # Timeframes to analyze
    TIMEFRAMES_CONFIG = ['5m', '15m', '30m', '1h']

    # List of symbols to analyze
    SYMBOL_CONFIG = [
        'BTC/USDT',
        'ETH/USDT',
        'BNB/USDT',
        'SOL/USDT',
        'HYPE/USDT'
    ]

    # Configuration parameters
    BOT_CONFIG = {
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

    # Priority order for exchange auto-detection
    EXCHANGE_PRIORITY = ['binance', 'bybit']

    # BREAKOUT CONFIGURATION
    BREAKOUT_CONFIG = {
        'monitoring_interval': 60,
        'max_zones_per_symbol': 10,
        'zone_timeout_hours': 24,
    }

    # BREAKOUT CONFIGURATION
    BREAKOUT_THRESHOLDS = {
        '5m': {
            'soft_break': 0.0015,  # 0.15%
            'confirmed_break': 0.003,  # 0.3%
            'strong_break': 0.005,  # 0.5%
            'volume_spike_threshold': 1.5,
            'cooldown_period': 30,  # 30 nến
            'multi_tf_confirmation': ['15m', '30m']  # Các TF cần confirm
        },
        '15m': {
            'soft_break': 0.0012,
            'confirmed_break': 0.0025,
            'strong_break': 0.004,
            'volume_spike_threshold': 1.8,
            'cooldown_period': 20,
            'multi_tf_confirmation': ['5m', '30m']
        },
        '30m': {
            'soft_break': 0.001,
            'confirmed_break': 0.002,
            'strong_break': 0.003,
            'volume_spike_threshold': 2.0,
            'cooldown_period': 15,
            'multi_tf_confirmation': ['15m', '1h']
        },
        '1h': {
            'soft_break': 0.0008,
            'confirmed_break': 0.0015,
            'strong_break': 0.0025,
            'volume_spike_threshold': 2.2,
            'cooldown_period': 10,
            'multi_tf_confirmation': ['30m', '4h']
        }
    }
