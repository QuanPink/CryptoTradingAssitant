"""Main entry point for Crypto Trading Assistant"""
from config.setting import settings
from health import start_health_server
from src.analyzers.accumulation_analyzer import AccumulationAnalyzer
from src.notifiers.telegram import TelegramNotifier
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


def main():
    """Main entry point"""
    logger.info("🚀 Starting Crypto Trading Assistant")

    # Start health check server (non-blocking)
    start_health_server(port=8080)

    # Initialize notifier
    notifier = TelegramNotifier(
        bot_token=settings.TELEGRAM_BOT_TOKEN,
        chat_id=settings.TELEGRAM_CHAT_ID
    )

    # Initialize analyzer
    analyzer = AccumulationAnalyzer(notifier)

    # Start main loop
    analyzer.run_analysis_loop()


if __name__ == '__main__':
    main()
