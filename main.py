import time
from typing import Dict

import pandas as pd

from config.setting import Settings
from src.analyzers.accumulation_analyzer import AccumulationAnalyzer
from src.analyzers.accumulation_detector import AccumulationDetector
from src.analyzers.breakout_detector import BreakoutDetector
from src.analyzers.exchange_manager import ExchangeManager
from src.notifiers.telegram import TelegramNotifier
from src.utils.helpers import DataQualityChecker
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AccumulationBot:
    def __init__(self):
        self.config = Settings()
        self.exchange_manager = ExchangeManager(self.config)
        self.detector = AccumulationDetector(self.config.BOT_CONFIG)
        self.analyzer = AccumulationAnalyzer(self.config.BOT_CONFIG)

        breakout_config_dict = {
            'BREAKOUT_CONFIG': self.config.BREAKOUT_CONFIG,
            'BREAKOUT_THRESHOLDS': self.config.BREAKOUT_THRESHOLDS
        }
        self.breakout_detector = BreakoutDetector(breakout_config_dict)

        self.quality_checker = DataQualityChecker()
        self.telegram = TelegramNotifier(
            bot_token=self.config.TELEGRAM_BOT_TOKEN,
            chat_id=self.config.TELEGRAM_CHAT_ID
        )

        self.notified_accumulations = {}
        self.is_running = False

    def _cleanup_old_accumulations(self, max_age_seconds: int = 7200):  # 2 giờ
        """Dọn dẹp tích lũy cũ"""
        current_time = time.time()
        keys_to_remove = []

        # Duyệt qua dict items
        for key, detection_time in self.notified_accumulations.items():
            if current_time - detection_time > max_age_seconds:
                keys_to_remove.append(key)

        # Xóa các key cũ
        for key in keys_to_remove:
            del self.notified_accumulations[key]

        if keys_to_remove:
            print(f"   🗑️ Đã dọn {len(keys_to_remove)} tích lũy cũ")

    def start_continuous_monitoring(self):
        """Bắt đầu giám sát liên tục mỗi 1 phút"""

        if self.is_running:
            logger.info("🔄 Bot đã chạy rồi")
            return

        self.is_running = True
        self._send_start_notification()

        cycle_count = 0
        while self.is_running:
            try:
                cycle_count += 1
                self._run_monitoring_cycle(cycle_count)
            except KeyboardInterrupt:
                self._handle_keyboard_interrupt()
                break
            except Exception as e:
                self._handle_monitoring_error(e)

    def _send_start_notification(self):
        """Gửi thông báo bắt đầu"""
        symbols = self.config.SYMBOL_CONFIG
        timeframes = self.config.TIMEFRAMES_CONFIG
        self.telegram.send_start_notification(symbols, timeframes)
        logger.info("🔄 Bắt đầu giám sát LIÊN TỤC tích lũy & breakout (mỗi 1 phút)")

    def _run_monitoring_cycle(self, cycle_count: int):
        """Chạy một chu kỳ giám sát"""
        cycle_start = time.time()

        self._print_cycle_header(cycle_count)

        # Quét tất cả symbols và timeframes
        total_accumulations, total_breakouts = self._scan_all_symbols()

        # Dọn dẹp và hiển thị kết quả
        self.breakout_detector.cleanup_old_zones()
        self._cleanup_old_accumulations(7200)  # Dọn tích lũy cũ hơn 2 giờ

        print(f"\n📊 TỔNG KẾT CHU KỲ #{cycle_count}:")
        print(f"   ✅ Tích lũy phát hiện: {total_accumulations}")
        print(f"   🚀 Breakout phát hiện: {total_breakouts}")
        print(f"   📍 Zones đang theo dõi: {self._count_active_zones()}")
        print(f"   📋 Tích lũy đã báo: {len(self.notified_accumulations)}")

        # Chờ đến phút tiếp theo
        self._wait_for_next_cycle(cycle_start)

    @staticmethod
    def _print_cycle_header(cycle_count: int):
        """In header cho chu kỳ"""
        print(f"\n{'=' * 60}")
        print(f"🔄 CHU KỲ #{cycle_count}: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'=' * 60}")

    def _scan_all_symbols(self) -> tuple:
        """Quét tất cả symbols và trả về kết quả"""
        total_accumulations = 0
        total_breakouts = 0

        for symbol in self.config.SYMBOL_CONFIG:
            print(f"\n🔍 {symbol}:")
            symbol_results = self._process_symbol(symbol)
            total_accumulations += symbol_results['accumulations']
            total_breakouts += symbol_results['breakouts']

        return total_accumulations, total_breakouts

    def _process_symbol(self, symbol: str) -> Dict:
        """Xử lý một symbol trên tất cả timeframe"""
        accumulations = 0
        breakouts = 0

        for timeframe in self.config.TIMEFRAMES_CONFIG:
            result = self._process_symbol_timeframe(symbol, timeframe)
            if result and result.get('accumulation_detected'):
                accumulations += 1
            if result and result.get('breakout_detected'):
                breakouts += 1

        return {'accumulations': accumulations, 'breakouts': breakouts}

    def _cleanup_and_display_results(self, cycle_count: int, total_accumulations: int, total_breakouts: int):
        """Dọn dẹp và hiển thị kết quả chu kỳ"""
        self.breakout_detector.cleanup_old_zones()

        print(f"\n📊 TỔNG KẾT CHU KỲ #{cycle_count}:")
        print(f"   ✅ Tích lũy phát hiện: {total_accumulations}")
        print(f"   🚀 Breakout phát hiện: {total_breakouts}")
        print(f"   📍 Zones đang theo dõi: {self._count_active_zones()}")

    def _wait_for_next_cycle(self, cycle_start: float):
        """Chờ đến chu kỳ tiếp theo"""
        elapsed = time.time() - cycle_start
        sleep_time = max(1, 60 - int(elapsed))  # Ép kiểu elapsed thành int

        print(f"\n💤 Chờ {sleep_time:.1f}s đến chu kỳ tiếp theo...")
        self._countdown(sleep_time)

    def _countdown(self, sleep_time: float):
        """Đếm ngược thời gian chờ"""
        sleep_time_int = int(sleep_time)  # Đảm bảo là integer
        for i in range(sleep_time_int, 0, -10):
            if not self.is_running:
                break
            if i % 30 == 0 or i <= 10:
                print(f"   ⏳ Còn {i}s...")
            time.sleep(min(10, i))

    def _handle_keyboard_interrupt(self):
        """Xử lý khi user nhấn Ctrl+C"""
        logger.info("🛑 Dừng bot (KeyboardInterrupt)")
        self.stop_continuous_monitoring()

    @staticmethod
    def _handle_monitoring_error(error: Exception):
        """Xử lý lỗi trong giám sát"""
        logger.error(f"❌ Lỗi trong chu kỳ giám sát: {error}")
        print(f"❌ Lỗi: {error}")
        time.sleep(60)

    def stop_continuous_monitoring(self):
        """Dừng giám sát liên tục"""
        self.is_running = False

        # Gửi thông báo dừng với tổng số tích lũy
        total_accumulations = self._count_total_accumulations()
        self.telegram.send_stop_notification(total_accumulations)

        logger.info("🛑 Đã dừng giám sát liên tục")

    def _process_symbol_timeframe(self, symbol: str, timeframe: str) -> Dict:
        """Xử lý một symbol/timeframe - trả về kết quả chi tiết"""
        try:
            # 1. LẤY DATA MỚI NHẤT
            df = self.exchange_manager.fetch_ohlcv(symbol, timeframe, 100)
            if df is None or df.empty:
                return {'error': 'No data'}

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

            # 2. KIỂM TRA TÍCH LŨY
            accumulation_result = self.detector.check_accumulation(df, timeframe)

            if accumulation_result['is_accumulation']:
                result = self._handle_accumulation_detected(result, accumulation_result, df, timeframe, symbol,
                                                            current_price)

            # 3. KIỂM TRA BREAKOUT
            breakout_result = self.breakout_detector.check_breakouts(
                symbol, current_price, current_volume, volume_ma, df, timeframe
            )

            if breakout_result:
                result = self._handle_breakout_detected(result, breakout_result, symbol)

            return result

        except Exception as e:
            logger.error(f"Lỗi xử lý {symbol} {timeframe}: {e}")
            return {'error': str(e)}

    def _handle_accumulation_detected(self, result: Dict, accumulation_result: Dict, df: pd.DataFrame,
                                      timeframe: str, symbol: str, current_price: float) -> Dict:
        """Xử lý khi phát hiện tích lũy - CHỈ BÁO KHI MỚI"""
        try:
            strength_result = self.analyzer.evaluate_accumulation_strength(df, timeframe, accumulation_result)
            zone_data = strength_result['accumulation_zone']
            accumulation_key = f"{symbol}_{timeframe}_{zone_data['support']:.6f}_{zone_data['resistance']:.6f}"

            # THÊM VÀO DANH SÁCH THEO DÕI BREAKOUT
            self.breakout_detector.add_accumulation_zone(symbol, zone_data, timeframe)

            # XỬ LÝ THÔNG BÁO TELEGRAM
            telegram_sent = self._handle_telegram_notification(accumulation_key, symbol, timeframe,
                                                               strength_result, current_price)

            # TẠO KẾT QUẢ MỚI THAY VÌ SỬA ĐỔI result TRỰC TIẾP
            updated_result = {
                **result,  # Giữ nguyên tất cả các trường cũ
                'accumulation_detected': True,
                'accumulation_strength': strength_result['strength_score'],
                'telegram_sent': telegram_sent,
                'accumulation_key': accumulation_key
            }

            print(f"   ✅ {timeframe}: TÍCH LŨY (điểm: {strength_result['strength_score']:.1f})")
            if telegram_sent:
                print(f"   📤 Đã gửi Telegram cho {symbol}")

            return updated_result

        except Exception as e:
            print(f"   ❌ Lỗi trong _handle_accumulation_detected: {e}")
            # Trả về result gốc khi có lỗi, không thay đổi trạng thái
            return {**result, 'error': str(e)}

    def _handle_telegram_notification(self, accumulation_key: str, symbol: str, timeframe: str,
                                      strength_result: Dict, current_price: float) -> bool:
        """Xử lý gửi thông báo Telegram - trả về trạng thái thành công"""
        # CHỈ GỬI THÔNG BÁO NẾU LÀ TÍCH LŨY MỚI
        if accumulation_key not in self.notified_accumulations:
            exchange = self.exchange_manager.get_exchange_for_symbol(symbol)
            print(f"   📤 Đang gửi Telegram alert cho {symbol} {timeframe}...")

            success = self.telegram.send_accumulation_alert(
                symbol, timeframe, strength_result, exchange, current_price
            )

            if success:
                print(f"   ✅ Đã gửi Telegram thành công cho {symbol}")
                # LƯU THỜI GIAN PHÁT HIỆN - sử dụng dict
                self.notified_accumulations[accumulation_key] = time.time()
                return True
            else:
                print(f"   ❌ Gửi Telegram thất bại cho {symbol}")
                return False
        else:
            print("   ⏭️ Đã báo tích lũy này trước đó, bỏ qua")
            return False

    def _handle_breakout_detected(self, result: Dict, breakout_result: Dict, symbol: str) -> Dict:
        """Xử lý khi phát hiện breakout"""
        exchange = self.exchange_manager.get_exchange_for_symbol(symbol)
        self.telegram.send_breakout_alert(breakout_result, exchange)

        result['breakout_detected'] = True
        result['breakout_info'] = breakout_result
        print(
            f"   🚀 {breakout_result['timeframe']}: BREAKOUT {breakout_result['direction']} ({breakout_result['breakout_type']})")

        return result

    def _count_total_accumulations(self) -> int:
        """Đếm tổng số tích lũy đã phát hiện (từ tất cả các zone)"""
        count = 0
        for symbol, zones in self.breakout_detector.accumulation_zones.items():
            count += len(zones)
        return count

    def _count_active_zones(self) -> int:
        """Đếm số zones đang active"""
        count = 0
        for symbol, zones in self.breakout_detector.accumulation_zones.items():
            for zone in zones:
                if zone.get('status') == 'ACTIVE':
                    count += 1
        return count


def main():
    bot = AccumulationBot()

    print("🤖 ACCUMULATION & BREAKOUT BOT")
    print("=" * 50)
    print("Bắt đầu giám sát LIÊN TỤC mỗi 1 phút...")
    print("Nhấn Ctrl+C để dừng bot")
    print("=" * 50)

    try:
        bot.start_continuous_monitoring()
    except KeyboardInterrupt:
        print("\n\n🛑 Bot đã dừng bởi người dùng")
    except Exception as e:
        print(f"\n\n❌ Lỗi: {e}")


if __name__ == "__main__":
    main()
