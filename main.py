import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock, Semaphore
from typing import Dict, Optional

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SYMBOLS,
    TIMEFRAMES,
    EXCHANGE_PRIORITY,
    MONITORING_INTERVAL
)
from src.detectors import AccumulationService, BreakoutService
from src.exchanges import ExchangeManager
from src.models import AccumulationZone
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
        self.accumulation_zones: Dict[str, AccumulationZone] = {}
        self.notified_accumulations = TTLDict(ttl=7200)

        self.max_workers = 5
        self.zones_lock = Lock()
        self.notified_lock = Lock()

        self.exchange_rate_limiters = {
            'binance': Semaphore(10),
            'bybit': Semaphore(2),
        }

        self.is_running = False

    @staticmethod
    def _wait_until_next_bar(interval_seconds: int):
        """
        Wait until next bar (aligned with timeframe interval).
        Avoids skipping when processing took longer than expected.
        """
        now = datetime.now()
        seconds = now.second + now.microsecond / 1_000_000
        remainder = seconds % interval_seconds
        wait_time = interval_seconds - remainder

        # Nếu xử lý đã trễ hơn interval (ví dụ >60s) => không chờ
        if wait_time < 1 or wait_time > interval_seconds:
            logger.warning("Cycle overran interval, starting next immediately.")
            return

        logger.info(f"⏳ Waiting {wait_time:.1f}s until next bar...")
        time.sleep(wait_time)

    def start_monitoring(self):
        """Start continuous monitoring loop"""
        if self.is_running:
            logger.info("🔄 Bot already running")
            return

        self.is_running = True

        # Send start notification
        self.telegram.send_start_notification(SYMBOLS, TIMEFRAMES)
        self._wait_until_next_bar(MONITORING_INTERVAL)

        cycle_count = 0
        try:
            while self.is_running:
                cycle_count += 1
                self._run_cycle(cycle_count)
                self._wait_until_next_bar(MONITORING_INTERVAL)

        except KeyboardInterrupt:
            logger.info("🛑 Stopping bot (KeyboardInterrupt)")
            self.stop_monitoring()
        except Exception as e:
            logger.error(f"❌ Fatal error: {e}", exc_info=True)
            self.stop_monitoring()

    def _run_cycle(self, cycle_count: int):
        """Run one monitoring cycle - PARALLEL VERSION"""
        # Print header
        print(f"\n{'=' * 60}")
        print(f"🔄 CYCLE #{cycle_count}: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")

        # ✅ Tạo danh sách tất cả tasks
        tasks = [
            (symbol, timeframe)
            for symbol in SYMBOLS
            for timeframe in TIMEFRAMES
        ]

        total_accumulations = 0
        total_breakouts = 0
        completed_tasks = 0
        failed_tasks = 0

        # ✅ Chạy song song với ThreadPoolExecutor
        print(f"🚀 Processing {len(tasks)} tasks with {self.max_workers} workers...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tất cả tasks
            future_to_task = {
                executor.submit(self._process_symbol_timeframe, symbol, timeframe): (symbol, timeframe)
                for symbol, timeframe in tasks
            }

            # Collect results khi hoàn thành
            for future in as_completed(future_to_task):
                symbol, timeframe = future_to_task[future]

                try:
                    result = future.result(timeout=30)  # Timeout 30s mỗi request

                    if result:
                        completed_tasks += 1
                        if result.get('accumulation_detected'):
                            total_accumulations += 1
                        if result.get('breakout_detected'):
                            total_breakouts += 1
                    else:
                        failed_tasks += 1

                except TimeoutError:
                    logger.error(f"⏱️ Timeout: {symbol} {timeframe}")
                    failed_tasks += 1
                except Exception as e:
                    logger.error(f"❌ Error: {symbol} {timeframe}: {e}")
                    failed_tasks += 1

        # Cleanup
        self.notified_accumulations.cleanup()

        # Print summary
        logger.info("\n📊 CYCLE SUMMARY:")
        logger.info(f"   ✅ Tasks completed: {completed_tasks}/{len(tasks)}")
        logger.info(f"   ❌ Tasks failed: {failed_tasks}/{len(tasks)}")
        logger.info(f"   ✅ Accumulations: {total_accumulations}")
        logger.info(f"   🚀 Breakouts: {total_breakouts}")
        logger.info(f"   📍 Active zones: {len(self.accumulation_zones)}")
        logger.info(f"   📋 Notified accumulations: {len(self.notified_accumulations)}")

        # ✅ Thread-safe zone breakdown
        with self.zones_lock:
            print("\n🔍 DEBUG - Active zones breakdown:")
            for key, zone in self.accumulation_zones.items():
                print(f"   - {key}: support={zone.support:.2f}, resistance={zone.resistance:.2f}")

    @staticmethod
    def _calculate_zone_overlap(support1: float, resistance1: float, support2: float, resistance2: float) -> float:
        """Calculate overlap percentage between two zones"""
        overlap_low = max(support1, support2)
        overlap_high = min(resistance1, resistance2)

        if overlap_low >= overlap_high:
            return 0.0

        overlap_size = overlap_high - overlap_low
        smaller_zone = min(resistance1 - support1, resistance2 - support2)

        if smaller_zone == 0:
            return 0.0

        return overlap_size / smaller_zone

    def _update_zone_storage(self, key: str, new_zone: AccumulationZone):
        """Central duplicate handling for accumulation zones"""
        with self.zones_lock:
            if key in self.accumulation_zones:
                old_zone = self.accumulation_zones[key]
                overlap = self._calculate_zone_overlap(new_zone.support, new_zone.resistance, old_zone.support,
                                                       old_zone.resistance)

                if overlap >= 0.9:
                    refreshed_zone = old_zone.__class__(
                        symbol=old_zone.symbol,
                        timeframe=old_zone.timeframe,
                        support=old_zone.support,
                        resistance=old_zone.resistance,
                        created_at=old_zone.created_at,
                        strength_score=new_zone.strength_score,
                        strength_details=new_zone.strength_details
                    )
                    self.accumulation_zones[key] = refreshed_zone
                    logger.debug(f"Keeping existing zone {key}: overlap {overlap:.0%}")
                    return

                logger.info(f"Replacing zone {key}: overlap={overlap:.0%}")
                self.accumulation_zones[key] = new_zone
            else:
                # New
                logger.info(f"Adding new zone {key}")
                self.accumulation_zones[key] = new_zone

    def _process_symbol_timeframe(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Process one symbol/timeframe combination"""
        df = None
        try:
            exchange_name = self.exchange_manager.get_exchange_name(symbol)
            rate_limiter = self.exchange_rate_limiters.get(exchange_name)

            # Acquire semaphore
            if rate_limiter:
                rate_limiter.acquire()

            try:
                # Fetch OHLCV data
                df = self.exchange_manager.fetch_ohlcv(symbol, timeframe, 50)

                if df is None or df.empty:
                    logger.warning(f"No data for {symbol} {timeframe}")
                    return None

                current_price = df['close'].iloc[-1]
                current_volume = df['volume'].iloc[-1]
                volume_ma = df['volume'].rolling(20).mean().iloc[-1]

                result = {
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'accumulation_detected': False,
                    'breakout_detected': False,
                    'price': current_price
                }

                key = f"{symbol}_{timeframe}"

                # Check for accumulation
                zone = self.accumulation_service.detect(df, timeframe, symbol)

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
                    key = f"{symbol}_{timeframe}"

                    self._update_zone_storage(key, zone)
                    with self.notified_lock:
                        if zone.key not in self.notified_accumulations:
                            exchange = self.exchange_manager.get_exchange_name(symbol)
                            self.telegram.send_accumulation_alert(zone, exchange, current_price)
                            self.notified_accumulations[zone.key] = time.time()
                            print(f"   ✅ {timeframe}: ACCUMULATION (score: {zone.strength_score:.1f})")
                            print("   📤 Telegram alert sent")
                        else:
                            print(f"   ⏭️ {timeframe}: Accumulation (already notified)")

                else:
                    with self.zones_lock:
                        if key in self.accumulation_zones:
                            logger.warning(
                                f"❌ Accumulation FAILED: {key} - "
                                f"No longer meets accumulation criteria"
                            )
                            del self.accumulation_zones[key]

                # Check for breakout
                breakout_signal = self.breakout_service.check_breakouts(self.accumulation_zones, symbol, timeframe,
                                                                        current_price, current_volume, volume_ma, df)

                if breakout_signal:
                    result['breakout_detected'] = True

                    exchange = self.exchange_manager.get_exchange_name(symbol)
                    self.telegram.send_breakout_alert(breakout_signal, exchange)

                    print(
                        f"   🚀 {timeframe}: BREAKOUT {breakout_signal.direction.value} "
                        f"({breakout_signal.breakout_type.value})"
                    )

                    key = f"{symbol}_{timeframe}"
                    with self.zones_lock:
                        if key in self.accumulation_zones:
                            del self.accumulation_zones[key]
                            logger.info(f"🗑️ Removed zone after breakout: {key}")

                return result

            finally:
                # ✅ Release semaphore
                if rate_limiter:
                    rate_limiter.release()

        except Exception as e:
            logger.error(f"Error processing {symbol} {timeframe}: {e}")
            return None
        finally:
            if df is not None:
                del df

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
        self.telegram.send_stop_notification(len(self.accumulation_zones))

        logger.info("🛑 Bot stopped")


def main():
    """Main entry point"""
    print("=" * 60)
    print("Accumulation Detection & Breakout Monitoring")
    print("=" * 60)
    print()
    print(f"📊 Symbols: {', '.join([s.replace('/USDT', '') for s in SYMBOLS])}")
    print(f"⏱️  Timeframes: {', '.join(TIMEFRAMES)}")
    print(f"🔄 Interval: {MONITORING_INTERVAL}s")
    print()
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
