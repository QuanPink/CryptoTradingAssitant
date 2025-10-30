"""Telegram notification service"""
import requests

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f'https://api.telegram.org/bot{bot_token}'

    def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Send message to Telegram"""
        if not self.bot_token or not self.chat_id:
            logger.info('Telegram not configured; skipping send.')
            return False

        url = f'{self.base_url}/sendMessage'
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            if response.status_code == 200:
                logger.info('Telegram message sent successfully')
                return True
            else:
                logger.warning(f'Telegram failed: {response.status_code} {response.text}')
                return False
        except Exception as e:
            logger.error(f'Error sending Telegram message: {e}')
            return False
