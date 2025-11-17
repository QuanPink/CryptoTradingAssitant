import asyncio
import time
from typing import List, Dict

from config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TIMEFRAMES, SYMBOLS, EXCHANGE_PRIORITY
from src.detectors.trading_signal import TradingSignalBuilder
from src.exchanges.manager import ExchangeManager
from src.notifiers.telegram import TelegramNotifier
from src.utils.logger import get_logger

logger = get_logger(__name__)

# try:
#     from debug_monitor import show_system_stats
#
#     DEBUG_MODE = True
# except ImportError:
#     DEBUG_MODE = False
#
#
#     def show_system_stats():
#         # as
#         pass


class TradingBot:
    def __init__(self):
        self.notifier = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)
        self.exchange_manager = ExchangeManager(EXCHANGE_PRIORITY)
        self.timeframe = TIMEFRAMES
        self.signal_builder = TradingSignalBuilder()
        self.sent_signals: Dict[str, Dict] = {}

    async def run_accumulation_strategy(self):
        """Chạy accumulation strategy"""
        logger.info("🤖 Starting Accumulation Strategy...")

        self.notifier.send_start_notification(SYMBOLS, TIMEFRAMES)

        total_signals = 0

        try:
            while True:
                # if DEBUG_MODE:
                #     show_system_stats()

                total_signals = await self._process_symbols(SYMBOLS, total_signals)
                await asyncio.sleep(30)
        except KeyboardInterrupt:
            logger.info("🛑 Received Ctrl+C, stopping bot...")

            # if DEBUG_MODE:
            #     print("\n📊 FINAL STATS:")
            #     # show_system_stats()
            #     print(f"🎯 Total Signals: {total_signals}")
        finally:
            self.notifier.send_stop_notification(total_signals)
            logger.info("👋 Bot stopped gracefully")

    async def _process_symbols(self, symbols: List[str], total_signals: int) -> int:
        """Process all symbols and return updated signal count"""
        for symbol in symbols:
            for timeframe in TIMEFRAMES:
                try:
                    total_signals = self._process_single_symbol(symbol, timeframe, total_signals)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error processing {symbol} on {timeframe}: {e}")
                    continue

        return total_signals

    def _process_single_symbol(self, symbol: str, timeframe: str, total_signals: int) -> int:
        """Process a single symbol and return updated signal count"""
        # Fetch data
        df = self.exchange_manager.fetch_ohlcv(symbol, timeframe, 100)

        if df is None or len(df) < 50:
            return total_signals

        # Detect accumulation with trend
        result = self.signal_builder.generate_signal(df)

        signal_key = f"{symbol}_{timeframe}"

        # ✅ Handle no accumulation or NO_TRADE
        if not result or result['signal']['signal'] == 'NO_TRADE':
            self._cleanup_signal_tracking(signal_key, result)
            return total_signals

        # ✅ Check if  should skip duplicate signal
        if self._should_skip_signal(signal_key, result):
            return total_signals

        # ✅ Send and track new signal
        return self._send_and_track_signal(symbol, result, df, timeframe, total_signals)

    def _cleanup_signal_tracking(self, signal_key: str, result: dict):
        """Remove signal from tracking if no longer valid"""
        if signal_key not in self.sent_signals:
            return

        reason = "no accumulation" if not result else "NO_TRADE"
        logger.info(f"🗑️ Removing {signal_key} from tracking ({reason})")
        del self.sent_signals[signal_key]

    def _should_skip_signal(self, signal_key: str, result: dict) -> bool:
        """Check if signal should be skipped (duplicate)"""
        if signal_key not in self.sent_signals:
            return False

        prev_signal = self.sent_signals[signal_key]
        zone = result['accumulation_zone']
        signal = result['signal']

        # Check if same zone and signal type
        if self._is_same_zone_and_signal(prev_signal, zone, signal):
            logger.info(
                f"⏭️ SKIP {signal_key}: Already sent {signal['signal']} "
                f"for zone ({zone.support:.2f}-{zone.resistance:.2f})"
            )
            return True

        return False

    @staticmethod
    def _is_same_zone_and_signal(prev_signal: dict, zone, signal: dict) -> bool:
        """Check if zone and signal type are the same as previous"""
        prev_zone = prev_signal['zone']
        same_zone = (
                abs(prev_zone['support'] - zone.support) < 1 and
                abs(prev_zone['resistance'] - zone.resistance) < 1
        )
        same_signal_type = prev_signal['signal'] == signal['signal']
        return same_zone and same_signal_type

    def _send_and_track_signal(self, symbol: str, result: dict, df, timeframe: str, total_signals: int) -> int:
        """Send signal notification and track it"""
        zone = result['accumulation_zone']
        signal = result['signal']
        current_price = df['close'].iloc[-1]
        signal_key = f"{symbol}_{timeframe}"

        # Send notification
        self._send_signal_notification(symbol, result, total_signals + 1)

        # Track signal
        self.sent_signals[signal_key] = {
            'signal': signal['signal'],
            'zone': {
                'support': zone.support,
                'resistance': zone.resistance
            },
            'sent_at': time.time(),
            'entry_price': current_price
        }

        return total_signals + 1

    def _send_signal_notification(self, symbol: str, result: dict, signal_number: int):
        """Send signal notification to Telegram"""
        signal = result['signal']
        accumulation_zone = result['accumulation_zone']
        exchange = self.exchange_manager.get_exchange_name(symbol) or 'unknown'

        self.notifier.send_signal_alert(
            symbol=symbol,
            signal=signal,
            zone=accumulation_zone,
            exchange=exchange,
        )

        logger.info(
            f"🎯 Signal #{signal_number} for {symbol}: {signal['signal']} "
            f"(Confidence: {signal['confidence']}%)"
        )


async def main():
    bot = TradingBot()

    await bot.run_accumulation_strategy()


if __name__ == "__main__":
    asyncio.run(main())
