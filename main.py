import asyncio
import time
from src.detectors.accumulation import EnhancedAccumulationService
from src.notifiers.telegram import TelegramNotifier
from src.exchanges.manager import ExchangeManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradingBot:
    def __init__(self):
        self.accumulation_service = EnhancedAccumulationService()
        # self.notifier = TelegramNotifier()
        self.exchange_manager = ExchangeManager()

    async def run_accumulation_strategy(self):
        """Chạy accumulation strategy"""
        logger.info("🤖 Starting Accumulation Strategy...")

        symbols = list(self.accumulation_service.symbols_config.keys())

        while True:
            for symbol in symbols:
                try:
                    # Lấy dữ liệu 5p
                    df = self.exchange_manager.fetch_ohlcv(symbol, '5m', 100)

                    if df is None or len(df) < 50:
                        continue

                    # Phát hiện accumulation với trend
                    result = self.accumulation_service.detect_with_trend(df, symbol)

                    if result and result['signal']['signal'] != 'NO_TRADE':
                        signal = result['signal']
                        accumulation_zone = result['accumulation_zone']

                        # Tạo message
                        message = self._create_signal_message(symbol, signal, accumulation_zone)

                        # Gửi notification
                        await self.notifier.send_message(message)

                        logger.info(f"🎯 Signal for {symbol}: {signal['signal']} (Confidence: {signal['confidence']})")

                    await asyncio.sleep(0.1)  # Giãn cách giữa các symbol

                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    continue

            # Chờ đến interval tiếp theo
            await asyncio.sleep(60)  # 1 phút

    def _create_signal_message(self, symbol: str, signal: dict, zone) -> str:
        """Tạo message cho signal"""
        emoji = "🟢" if signal['signal'] == 'LONG' else "🔴" if signal['signal'] == 'SHORT' else "⚪"

        message = f"""
{emoji} *ACCUMULATION SIGNAL* {emoji}

*Symbol:* `{symbol}`
*Signal:* `{signal['signal']}`
*Confidence:* `{signal['confidence']}%`

*Entry:* `{signal['entry_price']:.6f}`
*Stop Loss:* `{signal['stop_loss']:.6f}`
*Take Profit:* `{signal['take_profit']:.6f}`

*Accumulation Zone:*
- Support: `{zone.support:.6f}`
- Resistance: `{zone.resistance:.6f}`
- Score: `{zone.strength_score}`

*Signals:* {', '.join(signal['signals'])}

*Time:* `{time.strftime('%Y-%m-%d %H:%M:%S')}`
"""
        return message


async def main():
    bot = TradingBot()

    # Chạy accumulation strategy
    await bot.run_accumulation_strategy()


if __name__ == "__main__":
    asyncio.run(main())