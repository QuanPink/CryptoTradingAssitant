from __future__ import annotations

import time
from typing import List

import requests

from src.models import AccumulationZone
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
            f"{indent}━━━━━━━━━━━━━━━",
            "",
            f"{indent}• *Symbols:* {symbols_str}",
            f"{indent}• *Timeframes:* {', '.join(timeframes)}",
            "",
            f"⏰ *Started at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            ""
        ]

        return self.send_message("\n".join(lines))

    def send_stop_notification(self, total_accumulations: int = 0) -> bool:
        """Send bot stop notification"""
        indent = "\u00A0" * 3
        lines = [
            "🛑 *BOT STOPPED*",
            f"{indent}━━━━━━━━━━━━━━━",
            "",
            f"{indent}• *Accumulations found:* `{total_accumulations}`",
            "",
            f"⏰ *Stopped at:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            ""
        ]

        return self.send_message("\n".join(lines))

    def send_signal_alert(self, symbol: str, signal: dict, zone: AccumulationZone, exchange: str, timeframe: str) -> bool:
        """Send accumulation + trading signal in one alert"""

        signal_type = signal['signal']
        emoji = "🟢" if signal_type == 'LONG' else "🔴"

        entry = signal['entry']
        tp = signal['take_profit_1']  # ✅ Dùng take_profit_1
        sl = signal['stop_loss']

        indent = "\u00A0" * 2
        lines = [
            f"{emoji} *ACCUMULATION SIGNAL*",
            f"{indent}━━━━━━━━━━━━━━━",
            "",
            f"{indent}🪙 *{symbol}*  |  ⏱️ *{timeframe}*",
            "",
            f"{indent}💰 *Signal:* `{signal_type}`",
            f"{indent}🎯 *Confidence:* `{signal['confidence']:.1f}%`",
            "",
            f"{indent}📍 *Entry:* `{signal['entry']:.6f}`",
            f"{indent}🎯 *Take Profit:* `{tp:.6f}` ({self._calculate_pct(entry, tp):.2f}%)",
            f"{indent}🛑 *Stop Loss:* `{sl:.6f}` ({self._calculate_pct(entry, sl):.2f}%)",
        ]

        # Risk:Reward ratio
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        lines.append(f"{indent}💎 *Risk:Reward:* `1:{rr_ratio:.2f}`")

        # Accumulation Zone
        lines.extend([
            "",
            f"{indent}*Accumulation Zone:*",
            f"{indent}• Support: `{zone.support:.6f}`",
            f"{indent}• Resistance: `{zone.resistance:.6f}`",
            f"{indent}• Score: `{zone.strength_score:.1f}`",
        ])

        # Key signals
        if signal.get('signals'):
            escaped_signals = [s.replace('_', '\\_') for s in signal['signals']]
            signals_str = ', '.join(escaped_signals)
            lines.extend([
                "",
                f"{indent}*Signals:* {signals_str}",
            ])

        # Footer
        lines.extend([
            "",
            f"{indent}🏢 *Exchange:* {exchange}",
            f"{indent}⏰ *Time:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`",
            ""
        ])

        return self.send_message("\n".join(lines))

    @staticmethod
    def _calculate_pct(entry: float, target: float) -> float:
        """Calculate percentage change"""
        return ((target - entry) / entry) * 100
