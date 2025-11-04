import time
from typing import Dict, Optional

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SYMBOLS,
    TIMEFRAMES,
    EXCHANGE_PRIORITY,
    MONITORING_INTERVAL
)
from src.exchanges import ExchangeManager
from src.detectors import AccumulationService, BreakoutService
from src.notifiers.telegram import TelegramNotifier
from src.utils import TTLDict
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradingBot:
    def __init__(self):
        # Exchange manager
        self.exchange_manager = ExchangeManager(EXCHANGE_PRIORITY)

        # Detection services
        self.accumulation_service = AccumulationService()
        self.breakout_service = BreakoutService()

        # Notification service
        self.telegram = TelegramNotifier(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID)

        # State management
        self.notified_accumulations = TTLDict(ttl=7200)

        self.is_running = False

    def start_monitoring(self):
        """Start continuous monitoring loop"""
        if self.is_running:
            logger.info("🔄 Bot already running")
            return

        self.is_running = True

        # Send start notification
        self.telegram.send_start_notification(SYMBOLS, TIMEFRAMES)
        logger.info("🔄 Starting continuous monitoring (every 60s)")

        cycle_count = 0

        try:
            while self.is_running:
                cycle_count += 1
                self._run_cycle(cycle_count)

        except KeyboardInterrupt:
            logger.info("🛑 Stopping bot (KeyboardInterrupt)")
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
            self.stop_monitoring()

    def _run_cycle(self, cycle_count: int):
        """Run one monitoring cycle"""
        cycle_start = time.time()

        # Print header
        print(f"\n{'=' * 60}")
        print(f"🔄 CYCLE #{cycle_count}: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")

        # Scan all symbols and timeframes
        total_accumulations = 0
        total_breakouts = 0

        for symbol in SYMBOLS:
            print(f"\n🔍 {symbol}:")

            for timeframe in TIMEFRAMES:
                result = self._process_symbol_timeframe(symbol, timeframe)

                if result:
                    if result.get('accumulation_detected'):
                        total_accumulations += 1
                    if result.get('breakout_detected'):
                        total_breakouts += 1

        # Cleanup old data
        self.breakout_service.cleanup_old_zones()
        self.notified_accumulations.cleanup()

        # Print summary
        zone_counts = self.breakout_service.get_zone_counts()
        print("\n📊 CYCLE SUMMARY:")
        print(f"   ✅ Accumulations: {total_accumulations}")
        print(f"   🚀 Breakouts: {total_breakouts}")
        print(f"   📍 Active zones: {zone_counts['ACTIVE']}")
        print(f"   📋 Notified accumulations: {len(self.notified_accumulations)}")

        # Wait for next cycle
        self._wait_next_cycle(cycle_start)

    def _process_symbol_timeframe(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """
        Process one symbol/timeframe combination

        Returns:
            Dict with results: {
                'accumulation_detected': bool,
                'breakout_detected': bool,
                'price': float
            }
        """
        try:
            # Fetch OHLCV data
            df = self.exchange_manager.fetch_ohlcv(symbol, timeframe, 100)

            if df is None or df.empty:
                logger.warning(f"No data for {symbol} {timeframe}")
                return None

            current_price = df['close'].iloc[-1]
            current_volume = df['volume'].iloc[-1]
            volume_ma = df['volume'].rolling(20).mean().iloc[-1]

            logger.info(
                f"📊 {symbol} {timeframe} - Price: {current_price:.2f}, "
                f"Volume: {current_volume:.0f} (MA: {volume_ma:.0f}, "
                f"ratio: {current_volume / volume_ma:.2f}x)"
            )

            result = {
                'symbol': symbol,
                'timeframe': timeframe,
                'accumulation_detected': False,
                'breakout_detected': False,
                'price': current_price
            }

            # Check for accumulation
            zone = self.accumulation_service.detect(df, timeframe)

            if zone:
                # Set symbol in zone
                zone = zone.__class__(
                    symbol=symbol,
                    timeframe=zone.timeframe,
                    support=zone.support,
                    resistance=zone.resistance,
                    created_at=zone.created_at,
                    strength_score=zone.strength_score,
                    strength_details=zone.strength_details
                )

                result['accumulation_detected'] = True

                # Send notification if new
                if self._should_notify_accumulation(zone):
                    exchange = self.exchange_manager.get_exchange_name(symbol)
                    self.telegram.send_accumulation_alert(zone, exchange, current_price)
                    self.notified_accumulations[zone.key] = time.time()
                    print(f"   ✅ {timeframe}: ACCUMULATION (score: {zone.strength_score:.1f})")
                    print("   📤 Telegram alert sent")
                else:
                    print(f"   ⏭️ {timeframe}: Accumulation (already notified)")

                # Add to breakout monitoring
                self.breakout_service.add_zone(zone)

            # Check for breakout
            breakout_signal = self.breakout_service.check_breakouts(
                symbol, timeframe, current_price, current_volume, volume_ma, df
            )

            if breakout_signal:
                result['breakout_detected'] = True

                exchange = self.exchange_manager.get_exchange_name(symbol)
                self.telegram.send_breakout_alert(breakout_signal, exchange)

                print(
                    f"   🚀 {timeframe}: BREAKOUT {breakout_signal.direction.value} "
                    f"({breakout_signal.breakout_type.value})"
                )

            return result

        except Exception as e:
            logger.error(f"Error processing {symbol} {timeframe}: {e}")
            return None

    def _should_notify_accumulation(self, zone) -> bool:
        """Check if we should send notification for this accumulation"""
        return zone.key not in self.notified_accumulations

    @staticmethod
    def _wait_next_cycle(cycle_start: float):
        """Wait until next cycle time"""
        elapsed = time.time() - cycle_start
        sleep_time = max(1, MONITORING_INTERVAL - int(elapsed))

        print(f"\n💤 Waiting {sleep_time}s until next cycle...")
        time.sleep(sleep_time)

    def stop_monitoring(self):
        """Stop monitoring loop"""
        self.is_running = False

        # Send stop notification
        zone_counts = self.breakout_service.get_zone_counts()
        self.telegram.send_stop_notification(zone_counts['TOTAL'])

        logger.info("🛑 Bot stopped")


def main():
    """Main entry point"""
    print("🤖 CRYPTO TRADING BOT")
    print("=" * 60)
    print("Accumulation Detection & Breakout Monitoring")
    print("=" * 60)
    print()
    print(f"📊 Symbols: {', '.join([s.replace('/USDT', '') for s in SYMBOLS])}")
    print(f"⏱️  Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"🔄 Interval: {MONITORING_INTERVAL}s")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)

    bot = TradingBot()

    try:
        bot.start_monitoring()
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user")
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        logger.error(f"Fatal error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
