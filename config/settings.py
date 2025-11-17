import os

from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID', '')

# Timeframes and symbols to analyze
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'HYPE/USDT']
TIMEFRAMES = ['30m', "1h"]

# Priority order for exchange auto-detection
EXCHANGE_PRIORITY = ['binance', 'bybit']
