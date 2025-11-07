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
        self.min_interval = 0.5

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
        payload = {'chat_id': self.chat_id, 'text': text, 'parse_mode': parse_mode}

        try:
            response = requests.post(url, json=payload, timeout=30)

            if response.status_code == 200:
                self.last_send = time.time()
                logger.info('✅ Telegram message sent successfully')
                return True
            elif response.status_code == 429:
                retry_after = response.json().get('parameters', {}).get('retry_after', 30)
                logger.warning(f'⚠️ Telegram rate limit hit! Retry after {retry_after}s')
                time.sleep(retry_after)
                return self.send_message(text, parse_mode)
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
        indent = "\u00A0" * 3

        lines = [
            "🤖 *BOT STARTED*",
            "━━━━━━━━━━━━━━━",
            "",
            f"{indent}• *Symbols:* {symbols_str}",
            f"{indent}• *Timeframes:* {', '.join(timeframes)}",
            "",
            f"{indent}⏰ *Started at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            ""
        ]

        return self.send_message("\n".join(lines))

    def send_stop_notification(self, total_accumulations: int = 0) -> bool:
        """Send bot stop notification"""
        indent = "\u00A0" * 3
        lines = [
            "🛑 *BOT STOPPED*",
            "━━━━━━━━━━━━━━━",
            "",
            f"{indent}• *Accumulations found:* `{total_accumulations}`",
            "",
            f"{indent}⏰ *Stopped at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            ""
        ]

        return self.send_message("\n".join(lines))

    def send_accumulation_alert(self, zone: AccumulationZone, exchange: str, current_price: float) -> bool:
        """Send formatted accumulation alert"""
        duration_hours = self._calculate_duration_hours(
            zone.timeframe,
            zone.strength_details.get('duration_score', 0)
        )
        range_pct = zone.strength_details.get('range_size_pct', 0)

        indent = "\u00A0" * 2
        lines = [
            "🚀 *ACCUMULATION DETECTED*",
            f"{indent}━━━━━━━━━━━━━━━",
            "",
            f"{indent}🪙 *{zone.symbol}*  |  ⏱️ *{zone.timeframe}*  |  🎯 {zone.strength_score:.1f}",
            "",
            f"{indent}💰 *Price:* `{current_price:.2f}`",
            f"{indent}📈 *Resistance:* `{zone.resistance:.2f}`",
            f"{indent}📉 *Support:* `{zone.support:.2f}`",
            "",
            f"{indent}↔️ *Range:* `{range_pct:.2f}%`",
            f"{indent}⏳ *Accumulation Duration:* `{duration_hours:.1f}h`",
            "",
            f"{indent}🏢 *Exchange:* {exchange}",
            ""
        ]

        return self.send_message("\n".join(lines))

    def send_breakout_alert(self, signal: BreakoutSignal, exchange: str) -> bool:
        """Send breakout alert"""
        direction_icon = "💥" if signal.direction == 'UP' else "💣"
        break_pct = signal.break_pct * 100

        indent = "\u00A0" * 2
        lines = [
            f"{direction_icon} *BREAKOUT {signal.direction.value}*",
            f"{indent}━━━━━━━━━━━━━━━",
            "",
            f"{indent}🪙 *{signal.zone.symbol}*  |  ⏱️ *{signal.zone.timeframe}*  |  🎯 {signal.strength_score:.1f}",
            "",
            f"{indent}💰 *Price:* `{signal.current_price:.6f}`",
            f"{indent}📏 *Breakout:* `{break_pct:.2f}%` ({signal.breakout_type.value})",
            f"{indent}🔊 *Volume Ratio:* `{signal.volume_ratio:.2f}x`",
            "",
            f"{indent}📈 *Resistance:* `{signal.zone.resistance:.6f}`",
            f"{indent}📉 *Support:* `{signal.zone.support:.6f}`",
            "",
            f"{indent}🏢 *Exchange:* {exchange}",
            ""
        ]

        return self.send_message("\n".join(lines))

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
