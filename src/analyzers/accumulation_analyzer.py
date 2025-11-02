"""Main accumulation analyzer orchestrator"""
import time
from typing import Dict

import ccxt
import pandas as pd

from config.setting import settings
from src.analyzers.accumulation_detector import AccumulationDetector
from src.analyzers.breakout_detector import BreakoutDetector
from src.analyzers.exchange_manager import ExchangeManager, ExchangeHealthError
from src.analyzers.message_formatter import MessageFormatter
from src.core.circuit_breaker import CircuitBreaker
from src.core.zone_manager import ZoneManager
from src.notifiers.telegram import TelegramNotifier
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class AccumulationAnalyzer:
    """
    Main analyzer orchestrator

    Coordinates between:
    - Exchange management
    - Accumulation detection
    - Breakout detection
    - Zone management
    - Notifications
    """

    # Titles
    _TITLE_BOT_STOPPED = 'Bot Stopped'
    _TITLE_BOT_KILLED = 'Bot Killed'

    # Shutdown message templates
    _SHUTDOWN_MESSAGES = {
        'user': {
            'emoji': '🛑',
            'title': _TITLE_BOT_STOPPED,  # ← Use constant
            'subtitle': '⏸️ Trading assistant has been stopped by user'
        },
        'sigterm': {
            'emoji': '⚠️',
            'title': _TITLE_BOT_KILLED,
            'subtitle': '🔴 Trading assistant was killed (SIGTERM)'
        },
        'sigint': {
            'emoji': '🛑',
            'title': _TITLE_BOT_STOPPED,  # ← Use constant (reuse)
            'subtitle': '⏸️ Trading assistant interrupted (Ctrl+C)'
        },
        'default': {
            'emoji': '⚠️',
            'title': _TITLE_BOT_STOPPED,  # ← Use constant (reuse)
            'subtitle': '⏸️ Trading assistant stopped'
        }
    }

    def __init__(self, notifier: TelegramNotifier):
        self.notifier = notifier
        self.timeframes = settings.TIMEFRAMES

        # Initialize components
        self.exchange_manager = ExchangeManager()
        self.zone_manager = ZoneManager()
        self.circuit_breaker = CircuitBreaker()

    def _send_startup_message(self):
        """Send startup notification to Telegram"""
        try:
            # Build symbol mapping section
            symbol_mapping = []
            for symbol in settings.SYMBOLS:
                exchange = self.exchange_manager.symbol_exchange_map.get(symbol)
                if exchange:
                    symbol_mapping.append(f"• {symbol}: {exchange}")
                else:
                    symbol_mapping.append(f"• {symbol}: ❌ unavailable")

            # Build timeframes section
            timeframes_str = ", ".join(settings.TIMEFRAMES)

            # Build full message
            msg = (
                f"🤖 *Bot Started*\n\n"
                f"✅ Trading assistant has been started\n\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 *Symbol Mapping:*\n"
                f"{chr(10).join(symbol_mapping)}\n\n"
                f"⏱️ *Timeframes:* {timeframes_str}\n\n"
                f"🔄 *Scan Interval:* {settings.POLL_INTERVAL}s\n"
            )

            self.notifier.send_message(msg)
            logger.info("📤 Sent startup message to Telegram")

        except Exception as e:
            logger.error(f"Failed to send startup message: {e}")

    def _send_shutdown_message(self, reason: str = "user"):
        """Send shutdown notification to Telegram"""
        try:
            zones_count = self.zone_manager.get_total_zones()
            failed_count = self.circuit_breaker.get_failed_count()

            # Determine message type
            if reason == "user":
                msg_type = 'user'
            elif "SIGTERM" in reason:
                msg_type = 'sigterm'
            elif "SIGINT" in reason:
                msg_type = 'sigint'
            else:
                msg_type = 'default'

            # Get message template
            template = self._SHUTDOWN_MESSAGES[msg_type]
            emoji = template['emoji']
            title = template['title']
            subtitle = template['subtitle']

            # For default type, append custom reason
            if msg_type == 'default':
                subtitle = f"⏸️ Trading assistant stopped: {reason}"

            msg = (
                f"{emoji} *{title}*\n\n"
                f"{subtitle}\n\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"📊 *Final Statistics:*\n"
                f"• Active zones: {zones_count}\n"
                f"• Failed symbols: {failed_count}\n"
            )

            self.notifier.send_message(msg)
            logger.info("📤 Sent shutdown message to Telegram")

        except Exception as e:
            logger.error(f"Failed to send shutdown message: {e}", exc_info=True)

    def check_symbol(self, symbol: str):
        """Check symbol across all timeframes"""
        if self.circuit_breaker.should_skip(symbol):
            logger.debug(f"⏭️ Skipping {symbol} (circuit breaker)")
            return

        logger.info(f"[MULTI-TF CHECK] Scanning {symbol}...")

        for timeframe in self.timeframes:
            self._check_timeframe(symbol, timeframe)

    def _check_timeframe(self, symbol: str, timeframe: str):
        """Check single timeframe"""
        # Fetch data
        df = self.exchange_manager.fetch_ohlcv(symbol, timeframe)
        if df is None or len(df) < 10:
            logger.warning(f"[SKIP] Not enough data for {symbol} {timeframe}")
            return

        price = float(df['close'].iloc[-1])

        # Check accumulation
        self._check_accumulation(symbol, timeframe, df, price)

        # Check breakout
        self._check_breakout(symbol, timeframe, df, price)

    def _check_accumulation(self, symbol: str, timeframe: str, df: pd.DataFrame, price: float):
        """Check for accumulation"""
        zone_info = AccumulationDetector.detect(df, timeframe, symbol)

        if zone_info:
            existing = self.zone_manager.get_zone(symbol, timeframe)

            should_notify = (
                    existing is None or
                    (self.zone_manager.is_zone_significantly_different(zone_info, existing) and
                     not self.zone_manager.was_recent(
                         existing.get('last_accum_notified'),
                         settings.ACCUMULATION_COOLDOWN_MIN
                     ))
            )

            if should_notify:
                self.zone_manager.mark_zone(symbol, timeframe, zone_info)
                msg = MessageFormatter.format_accumulation(symbol, timeframe, zone_info, price)
                logger.info(f"[ACCUMULATION] {symbol} {timeframe}")
                self.notifier.send_message(msg)

    def _check_breakout(self, symbol: str, timeframe: str, df: pd.DataFrame, price: float):
        """Check for breakout"""
        if not self.zone_manager.has_zone(symbol, timeframe):
            logger.debug(f"[NO ZONE] {symbol} {timeframe}")
            return

        zone = self.zone_manager.get_zone(symbol, timeframe)

        # Check expiration
        if self.zone_manager.is_expired(zone, settings.ZONE_EXPIRE_HOURS):
            logger.info(f'Zone for {symbol} {timeframe} expired (>{settings.ZONE_EXPIRE_HOURS}h)')
            self.zone_manager.clear_zone(symbol, timeframe)
            return

        # Check cooldown
        if self.zone_manager.was_recent(
                zone.get('last_breakout_notified'),
                settings.BREAKOUT_COOLDOWN_MIN
        ):
            return

        # Detect breakout
        direction, quality = BreakoutDetector.check_breakout(
            df, price, zone['upper'], zone['lower'], timeframe
        )

        if direction:
            self._handle_breakout(symbol, timeframe, df, price, zone, direction, quality)

    def _handle_breakout(self, symbol: str, timeframe: str, df: pd.DataFrame,
                         price: float, zone: Dict, direction: str, quality: str):
        """Handle detected breakout"""
        # Get volume metrics
        vol_spike, short_ratio, medium_ratio = BreakoutDetector.calculate_volume_spike(df, timeframe)

        # Check consensus
        consensus = BreakoutDetector.check_consensus(
            self.zone_manager.zones, symbol, direction, timeframe
        )

        # Filter by quality
        if consensus['quality'] not in ['excellent', 'good', 'medium']:
            logger.info(f"[FILTERED] {symbol} {timeframe} - Low consensus: {consensus['quality']}")
            return

        # Log breakout
        logger.info(
            f"[BREAKOUT {direction.upper()}] {symbol} {timeframe}\n"
            f"  Breakout Quality: {quality}\n"
            f"  Volume: {short_ratio:.2f}x / {medium_ratio:.2f}x\n"
            f"  Consensus: {consensus['score']}/{consensus['total']} ({consensus['quality']})\n"
            f"  Aligned TFs: {', '.join(consensus['aligned_tfs']) or 'none'}"
        )

        # Send notification
        msg = MessageFormatter.format_breakout(
            symbol, timeframe, price, direction, zone,
            vol_spike, short_ratio, medium_ratio, consensus, quality
        )

        self.notifier.send_message(msg)

        # Update zone
        breakout_key = f'breakout_{direction}'
        zone[breakout_key] = True
        zone['last_breakout_notified'] = pd.Timestamp.utcnow()

    # ═══════════════════════════════════════════════════════════
    # MAIN LOOP & LIFECYCLE
    # ═══════════════════════════════════════════════════════════

    def run_analysis_loop(self):
        """Main analysis loop with comprehensive error handling"""
        import gc
        import signal
        import sys

        logger.info("🚀 Starting analysis loop...")

        def signal_handler(signum, _):
            """Handle termination signals"""
            signal_name = signal.Signals(signum).name
            logger.warning(f"🛑 Received signal {signal_name} - shutting down...")
            self._send_shutdown_message(reason=f"Received {signal_name}")
            self.shutdown()
            sys.exit(0)

        # Register signal handlers
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        if not self.exchange_manager.exchanges:
            logger.error("❌ No exchanges available - cannot start")
            return

        if not any(self.exchange_manager.markets_cache.values()):
            logger.error("❌ No markets loaded - cannot start")
            return

        # Send startup notification
        self._send_startup_message()

        loop_state = {
            'last_health_check': time.time(),
            'last_cleanup': time.time(),
            'loop_count': 0
        }

        while True:
            try:
                self._run_single_loop_iteration(loop_state, gc)
            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt - shutting down...")
                self._send_shutdown_message(reason="Received SIGINT")
                self.shutdown()
                break
            except Exception as e:
                logger.error(f"💥 Critical error in main loop: {e}", exc_info=True)
                logger.info("⏳ Waiting 60s before retry...")
                time.sleep(60)

    def _validate_exchanges_health(self) -> bool:
        """Validate that at least one exchange is healthy"""
        try:
            health = self.exchange_manager.health_check()
            if not any(h['status'] == 'healthy' for h in health.values()):
                raise ExchangeHealthError("No healthy exchanges available")
            return True
        except ExchangeHealthError:
            logger.error("❌ No healthy exchanges - cannot start")
            return False
        except Exception as e:
            logger.error(f"❌ Initial health check failed: {e}")
            return False

    def _run_single_loop_iteration(self, loop_state: Dict, gc_module):
        """Execute one iteration of the main loop"""
        loop_start = time.time()
        current_time = loop_start
        loop_state['loop_count'] += 1

        # Periodic maintenance
        self._run_periodic_maintenance(current_time, loop_state, gc_module)

        # Analyze symbols
        stats = self._analyze_all_symbols()

        # Log statistics
        loop_duration = time.time() - loop_start
        self._log_loop_statistics(loop_state['loop_count'], loop_duration, stats)

        # Sleep until next iteration
        self._sleep_until_next_iteration(loop_duration)

    def _run_periodic_maintenance(self, current_time: float, loop_state: Dict, gc_module):
        """Run periodic maintenance tasks"""
        # Health check every 30 min
        if current_time - loop_state['last_health_check'] > settings.HEALTH_CHECK_INTERVAL:
            logger.info("⏰ Running periodic health check...")
            self.exchange_manager.health_check()
            self.exchange_manager.log_performance_metrics()

            # Log zone and circuit breaker stats
            zones_count = self.zone_manager.get_total_zones()
            failed_count = self.circuit_breaker.get_failed_count()
            logger.info(f"   Active zones: {zones_count}")
            logger.info(f"   Failed symbols: {failed_count}")

            loop_state['last_health_check'] = current_time

        # Cleanup every 6 hours
        if current_time - loop_state['last_cleanup'] > 21600:
            logger.info("🧹 Running periodic cleanup...")
            self.zone_manager.cleanup_old_zones()
            gc_module.collect()
            loop_state['last_cleanup'] = current_time

    def _analyze_all_symbols(self) -> Dict:
        """Analyze all configured symbols"""
        stats = {'checked': 0, 'skipped': 0, 'failed': 0}

        for symbol in settings.SYMBOLS:
            try:
                if self.circuit_breaker.should_skip(symbol):
                    stats['skipped'] += 1
                    continue

                self.check_symbol(symbol)
                self.circuit_breaker.record_success(symbol)
                stats['checked'] += 1

            except (ccxt.NetworkError, ccxt.ExchangeError) as e:
                logger.warning(f"Exchange error for {symbol}: {e}")
                self.circuit_breaker.record_failure(symbol)
                stats['failed'] += 1

            except Exception as e:
                logger.error(f"💥 Unexpected error for {symbol}: {e}", exc_info=True)
                self.circuit_breaker.record_failure(symbol)
                stats['failed'] += 1

        return stats

    @staticmethod
    def _log_loop_statistics(loop_count: int, loop_duration: float, stats: Dict):
        """Log loop statistics"""
        if loop_count % 10 == 0:  # Every 10 loops
            logger.info(
                f"📈 Loop #{loop_count} completed in {loop_duration:.2f}s - "
                f"✅ {stats['checked']} | ⏭️ {stats['skipped']} | ❌ {stats['failed']}"
            )

    @staticmethod
    def _sleep_until_next_iteration(loop_duration: float):
        """Sleep until next iteration should start"""
        sleep_time = max(0, settings.POLL_INTERVAL - loop_duration)

        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            logger.warning(
                f"⚠️ Loop exceeded POLL_INTERVAL: {loop_duration:.1f}s > {settings.POLL_INTERVAL}s"
            )

    def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Performing graceful shutdown...")

        # Log final state
        zones_count = self.zone_manager.get_total_zones()
        failed_count = self.circuit_breaker.get_failed_count()

        logger.info("📊 Final state:")
        logger.info(f"   Active zones: {zones_count}")
        logger.info(f"   Failed symbols: {failed_count}")

        # Close exchange connections
        self.exchange_manager.shutdown()

        logger.info("✅ Shutdown complete")
