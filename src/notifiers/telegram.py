"""Telegram notification service"""
import time

import requests

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TelegramNotifier:
    """Send notifications via Telegram"""

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f'https://api.telegram.org/bot{bot_token}'

        self.last_send = 0
        self.min_interval = 0.5  # 500ms between messages
        self.message_queue = []

    def send_message(self, text: str, parse_mode: str = 'Markdown') -> bool:
        """Send message to Telegram"""
        if not self.bot_token or not self.chat_id:
            logger.info('Telegram not configured; skipping send.')
            return False

        now = time.time()
        time_since_last = now - self.last_send

        if time_since_last < self.min_interval:
            sleep_time = self.min_interval - time_since_last
            logger.debug(f"⏳ Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)

        url = f'{self.base_url}/sendMessage'
        payload = {
            'chat_id': self.chat_id,
            'text': text,
            'parse_mode': parse_mode
        }

        try:
            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                self.last_send = time.time()
                logger.info('✅ Telegram message sent successfully')
                return True
            elif response.status_code == 429:
                # Rate limit hit
                retry_after = response.json().get('parameters', {}).get('retry_after', 60)
                logger.warning(
                    f'⚠️ Telegram rate limit hit! Retry after {retry_after}s'
                )
                time.sleep(retry_after)
                return self.send_message(text, parse_mode)  # Retry once
            else:
                logger.warning(f'⚠️ Telegram failed: {response.status_code} {response.text}')
                return False

        except requests.exceptions.Timeout:
            logger.error('⏰ Telegram request timeout')
            return False
        except Exception as e:
            logger.error(f'💥 Error sending Telegram message: {e}')
            return False
