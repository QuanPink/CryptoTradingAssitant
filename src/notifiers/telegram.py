import time

import requests

from src.utils.logger import get_logger

logger = get_logger(__name__)


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

    def send_start_notification(self, symbols: list, timeframes: list):
        """Send bot start notification"""
        message = self._format_start_message(symbols, timeframes)
        return self.send_message(message, 'Markdown')

    def send_stop_notification(self, total_accumulations: int = 0):
        """Send bot stop notification"""
        message = self._format_stop_message(total_accumulations)
        return self.send_message(message, 'Markdown')

    def send_accumulation_alert(self, symbol: str, timeframe: str, strength_result: dict, exchange: str,
                                current_price: float):
        """Send formatted accumulation alert"""
        message = self._format_accumulation_message(symbol, timeframe, strength_result, exchange, current_price)
        return self.send_message(message, 'Markdown')

    def send_breakout_alert(self, breakout_result: dict, exchange: str):
        """Send breakout alert"""
        message = self._format_breakout_message(breakout_result, exchange)
        return self.send_message(message, 'Markdown')

    @staticmethod
    def _format_start_message(symbols: list, timeframes: list) -> str:
        """Format bot start message"""
        symbols_str = ", ".join([s.replace('/USDT', '') for s in symbols])

        message = f"""
    🤖 *BOT STARTED*
    ━━━━━━━━━━━━━━━

    📊 *Monitoring:*
    • *Symbols:* {symbols_str}
    • *Timeframes:* {', '.join(timeframes)}

    ⏰ *Started at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`
    """.strip()

        return message

    @staticmethod
    def _format_stop_message(total_accumulations: int = 0) -> str:
        """Format bot stop message"""
        message = f"""
    🛑 *BOT STOPPED*
    ━━━━━━━━━━━━━━━

    📈 *Analysis Summary:*
    • *Accumulations found:* `{total_accumulations}`

    ⏰ *Stopped at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`
    """.strip()

        return message

    def _format_accumulation_message(self, symbol: str, timeframe: str, strength_result: dict, exchange: str,
                                     current_price: float) -> str:
        """Format accumulation message according to your template"""
        strength_score = strength_result['strength_score']
        strength_level = strength_result['strength_level']
        breakout_probability = strength_result['breakout_probability']
        zone = strength_result['accumulation_zone']
        range_size_pct = strength_result['score_details'].get('range_size_pct', 0)

        # Calculate accumulation duration in hours
        duration_hours = self._calculate_duration_hours(timeframe, zone['duration_bars'])

        message = f"""
    🚀 *ACCUMULATION DETECTED*
    ━━━━━━━━━━━━━━━━━
    
    🪙 *{symbol}* | ⏱️ *{timeframe}*
    
    💰 *Price:* `{current_price:,.2f}`
    📈 *Resistance:* `{zone['resistance']:,.2f}`
    📉 *Support:* `{zone['support']:,.2f}`
    
    📊 *Range:* `{range_size_pct:.2f}%`
    ⏳ *Accumulation Duration:* `{duration_hours:.1f}h`
    💪 *Strength:* `{strength_score:.1f}/100` ({strength_level})
    🎯 *Breakout:* {breakout_probability}
    
    *Exchange:* {exchange}
    """.strip()

        return message

    @staticmethod
    def _format_breakout_message(breakout_result: dict, exchange: str) -> str:
        """Format breakout message"""
        symbol = breakout_result['symbol']
        timeframe = breakout_result['timeframe']
        direction = breakout_result['direction']
        breakout_type = breakout_result['breakout_type']
        break_pct = breakout_result['break_pct'] * 100
        strength_score = breakout_result['strength_score']
        volume_ratio = breakout_result['volume_ratio']

        # Icons and emojis
        direction_icon = "📈" if direction == 'UP' else "📉"
        type_emoji = {
            'SOFT_BREAK': '🟡',
            'CONFIRMED_BREAK': '🟠',
            'STRONG_BREAK': '🔴'
        }.get(breakout_type, '⚪')

        message = f"""
    🚨 *BREAKOUT ALERT* {direction_icon}
    ━━━━━━━━━━━━━━━━━━

    🪙 *{symbol}* | ⏱️ *{timeframe}* | {type_emoji}

    💰 *Price:* `{breakout_result['current_price']:.6f}`
    🎯 *Direction:* {direction}
    📏 *Breakout:* `{break_pct:.2f}%` ({breakout_type})

    💪 *Strength Score:* `{strength_score:.1f}/100`
    📊 *Volume Ratio:* `{volume_ratio:.2f}x`

    🛡️ *Support:* `{breakout_result['support']:.6f}`
    🎯 *Resistance:* `{breakout_result['resistance']:.6f}`

    🏢 *Exchange:* {exchange}
    """.strip()

        return message

    @staticmethod
    def _calculate_duration_hours(timeframe: str, duration_bars: int) -> float:
        """Calculate accumulation duration in hours"""
        minutes_per_bar = {
            '5m': 5,
            '15m': 15,
            '30m': 30,
            '1h': 60
        }
        minutes = duration_bars * minutes_per_bar.get(timeframe, 5)
        return minutes / 60.0
