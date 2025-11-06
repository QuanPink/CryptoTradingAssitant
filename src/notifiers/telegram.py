from __future__ import annotations

import time
from typing import List

import requests

from src.models import AccumulationZone, BreakoutSignal
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
                # Rate limit hit - retry once
                retry_after = response.json().get('parameters', {}).get('retry_after', 60)
                logger.warning(f'⚠️ Telegram rate limit hit! Retry after {retry_after}s')
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

    def send_start_notification(self, symbols: List[str], timeframes: List[str]) -> bool:
        """Send bot start notification"""
        symbols_str = ", ".join([s.replace('/USDT', '') for s in symbols])

        message = f"""
    🤖 *BOT STARTED*
    ━━━━━━━━━━━━━━━

    📊 *Monitoring:*
    • *Symbols:* {symbols_str}
    • *Timeframes:* {', '.join(timeframes)}

    ⏰ *Started at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`
    """.strip()

        return self.send_message(message)

    def send_stop_notification(self, total_accumulations: int = 0) -> bool:
        """Send bot stop notification"""
        message = f"""
    🛑 *BOT STOPPED*
    ━━━━━━━━━━━━━━━

    📈 *Analysis Summary:*
    • *Accumulations found:* `{total_accumulations}`

    ⏰ *Stopped at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`
    """.strip()

        return self.send_message(message)

    def send_accumulation_alert(self, zone: AccumulationZone, exchange: str, current_price: float) -> bool:
        """Send formatted accumulation alert"""
        duration_hours = self._calculate_duration_hours(
            zone.timeframe,
            zone.strength_details.get('duration_score', 0)
        )
        range_pct = zone.strength_details.get('range_size_pct', 0)

        if zone.strength_score >= 80:
            breakout_prob = 'VERY HIGH ⭐⭐⭐'
        elif zone.strength_score >= 70:
            breakout_prob = 'HIGH ⭐⭐'
        elif zone.strength_score >= 60:
            breakout_prob = 'MEDIUM ⭐'
        else:
            breakout_prob = 'LOW'

        message = f"""
    🚀 *ACCUMULATION DETECTED*
    ━━━━━━━━━━━━━━━━━

    🪙 *{zone.symbol}* | ⏱️ *{zone.timeframe}*

    💰 *Price:* `{current_price:,.2f}`
    📈 *Resistance:* `{zone.resistance:,.2f}`
    📉 *Support:* `{zone.support:,.2f}`

    📊 *Range:* `{range_pct:.2f}%`
    ⏳ *Accumulation Duration:* `{duration_hours:.1f}h`
    💪 *Strength:* `{zone.strength_score:.1f}/100` ({zone.strength_level.value})
    🎯 *Breakout:* {breakout_prob}

    *Exchange:* {exchange}
    """.strip()

        return self.send_message(message)

    def send_breakout_alert(self, signal: BreakoutSignal, exchange: str) -> bool:
        """Send breakout alert"""
        # Icons and emojis
        direction_icon = "📈" if signal.direction == 'UP' else "📉"
        type_emoji = {
            'SOFT_BREAK': '🟡',
            'CONFIRMED_BREAK': '🟠',
            'STRONG_BREAK': '🔴'
        }.get(signal.breakout_type.value, '⚪')

        # Calculate break percentage
        break_pct = signal.break_pct * 100

        message = f"""
    🚨 *BREAKOUT ALERT* {direction_icon}
    ━━━━━━━━━━━━━━━━━━

    🪙 *{signal.zone.symbol}* | ⏱️ *{signal.zone.timeframe}* | {type_emoji}

    💰 *Price:* `{signal.current_price:.6f}`
    🎯 *Direction:* {signal.direction.value}
    📏 *Breakout:* `{break_pct:.2f}%` ({signal.breakout_type.value})
        
    💪 *Strength Score:* `{signal.strength_score:.1f}/100`
    📊 *Volume Ratio:* `{signal.volume_ratio:.2f}x`

    🛡️ *Support:* `{signal.zone.support:.6f}`
    🎯 *Resistance:* `{signal.zone.resistance:.6f}`

    🏢 *Exchange:* {exchange}
    """.strip()

        return self.send_message(message)

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
