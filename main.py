import time

from config.setting import settings
from health import start_health_server
from src.analyzers.accumulation import AccumulationAnalyzer
from src.notifiers.telegram import TelegramNotifier
from src.utils.helpers import align_to_next_5min
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def main():
    """Main bot loop"""
    logger.info("Starting Crypto Trading Assistant")

    start_health_server(port=8080)

    # Initialize notifier
    notifier = TelegramNotifier(
        settings.TELEGRAM_BOT_TOKEN,
        settings.TELEGRAM_CHAT_ID
    )

    # Initialize analyzer
    analyzer = AccumulationAnalyzer(notifier)

    # Build startup message with exchange mapping
    exchange_map_lines = []
    for symbol in settings.SYMBOLS:
        exchange_id = analyzer.symbol_exchange_map.get(symbol, 'N/A')
        exchange_map_lines.append(f"• {symbol}: {exchange_id}")

    exchange_map_str = "\n".join(exchange_map_lines)

    logger.info(f"Exchanges: {', '.join(settings.EXCHANGES)}")
    logger.info(f"Symbols: {settings.SYMBOLS}")
    logger.info(f"Timeframes: {', '.join(settings.TIMEFRAMES)}")
    logger.info("=" * 60)

    # Send startup notification
    notifier.send_message(
        f"🤖 *Bot Started*\n\n"
        f"*Symbol Mapping:*\n{exchange_map_str}\n\n"
        f"*Timeframes:* {', '.join(settings.TIMEFRAMES)}"
    )

    # Align to next candle close
    sleep_seconds = align_to_next_5min() + 3
    logger.info(f'Waiting {sleep_seconds:.1f}s until next candle close...')
    time.sleep(sleep_seconds)

    # Main loop
    try:
        while True:
            loop_start = time.time()

            for symbol in settings.SYMBOLS:
                try:
                    analyzer.check_symbol(symbol)
                except Exception as e:
                    logger.error(f'Error processing {symbol}: {e}', exc_info=True)

            elapsed = time.time() - loop_start
            sleep_for = max(1, settings.POLL_INTERVAL - elapsed)
            logger.info(f"[LOOP DONE] Sleeping {sleep_for:.1f}s before next check...\n")
            time.sleep(sleep_for)

    except KeyboardInterrupt:
        logger.info('Bot stopped by user')
        notifier.send_message("🛑 *Bot Stopped*\nTrading assistant has been stopped by user")
    except Exception as e:
        logger.critical(f'Fatal error: {e}', exc_info=True)
        notifier.send_message(f"❌ *Bot Error*\nCritical error: {str(e)}")


if __name__ == '__main__':
    main()
