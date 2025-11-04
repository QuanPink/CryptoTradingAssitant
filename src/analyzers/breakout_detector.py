import time
from typing import Dict, List, Optional

import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class BreakoutDetector:
    def __init__(self, config: Dict):
        self.config = config
        self.accumulation_zones: Dict[str, List[Dict]] = {}

    def add_accumulation_zone(self, symbol: str, zone: Dict, timeframe: str):
        """Add accumulation zone to breakout watchlist"""
        if symbol not in self.accumulation_zones:
            self.accumulation_zones[symbol] = []

        zone_key = f"{symbol}_{timeframe}_{zone['support']:.6f}_{zone['resistance']:.6f}"

        # KIỂM TRA VÀ IN THÔNG TIN ZONE
        print(f"   🔍 Kiểm tra zone: {zone_key}")
        print(f"      📍 Hỗ trợ: {zone['support']:.6f}")
        print(f"      📍 Kháng cự: {zone['resistance']:.6f}")

        # Kiểm tra zone đã tồn tại chưa
        existing_zone = next((z for z in self.accumulation_zones[symbol]
                              if z.get('zone_key') == zone_key), None)

        if not existing_zone:
            new_zone = {
                'zone_key': zone_key,
                'symbol': symbol,
                'timeframe': timeframe,
                'support': zone['support'],
                'resistance': zone['resistance'],
                'status': 'ACTIVE',  # ACTIVE, BREAKOUT, COMPLETED
                'created_at': time.time(),
                'last_breakout_time': None,
            }
            self.accumulation_zones[symbol].append(new_zone)
            logger.info(f"✅ Theo dõi breakout: {symbol} {timeframe}")
            print(f"   ✅ Đã thêm zone mới: {symbol} {timeframe}")
        else:
            print(f"   ⚠️ Zone đã tồn tại: {symbol} {timeframe}")

    def check_breakouts(self, symbol: str, current_price: float, current_volume: float,
                        volume_ma: float, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
        """Check for breakouts from the accumulation zones you are watching"""
        if symbol not in self.accumulation_zones:
            return None

        print(f"   🔍 Đang kiểm tra {len(self.accumulation_zones[symbol])} zones cho {symbol}")

        for zone in self.accumulation_zones[symbol]:
            if zone['timeframe'] != timeframe or zone['status'] == 'COMPLETED':
                continue

            print(f"      📊 Kiểm tra zone: {zone['support']:.6f} - {zone['resistance']:.6f}")
            print(f"      💰 Giá hiện tại: {current_price:.6f}")

            breakout_result = self._evaluate_breakout(zone, current_price, current_volume, volume_ma, df, timeframe)
            if breakout_result:
                # Cập nhật trạng thái zone
                self._update_zone_status(zone, breakout_result)
                return breakout_result

        return None

    def _evaluate_breakout(self, zone: Dict, current_price: float, current_volume: float,
                           volume_ma: float, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
        """Evaluate breakout for a zone"""
        support = zone['support']
        resistance = zone['resistance']

        # Kiểm tra giá có trong vùng tích lũy không (retest)
        if support <= current_price <= resistance:
            if zone['status'] == 'BREAKOUT':
                # Giá quay lại vùng tích lũy -> reset trạng thái
                zone['status'] = 'ACTIVE'
                zone['last_breakout_time'] = None
                logger.info(f"🔄 Giá quay lại tích lũy: {zone['symbol']}")
            return None

        # Kiểm tra breakout lên
        if current_price > resistance:
            break_pct = (current_price - resistance) / resistance
            direction = 'UP'
            breakout_level = resistance

        # Kiểm tra breakout xuống
        elif current_price < support:
            break_pct = (support - current_price) / support
            direction = 'DOWN'
            breakout_level = support
        else:
            return None

        # Xác định loại breakout theo config của bạn
        timeframe_config = self.config['BREAKOUT_CONFIG'][timeframe]
        breakout_type = self._get_breakout_type(break_pct, timeframe_config)

        # Tính điểm sức mạnh breakout
        strength_score = self._calculate_breakout_strength(
            break_pct, current_volume, volume_ma, df, direction, timeframe_config
        )

        return {
            'symbol': zone['symbol'],
            'timeframe': zone['timeframe'],
            'direction': direction,
            'breakout_type': breakout_type,
            'break_pct': break_pct,
            'current_price': current_price,
            'breakout_level': breakout_level,
            'support': support,
            'resistance': resistance,
            'strength_score': strength_score,
            'volume_ratio': current_volume / volume_ma if volume_ma > 0 else 1,
            'zone_key': zone['zone_key'],
            'is_strong_breakout': breakout_type == 'STRONG_BREAK'
        }

    @staticmethod
    def _get_breakout_type(break_pct: float, timeframe_config: Dict) -> str:
        """Xác định loại breakout theo config của bạn"""
        if break_pct >= timeframe_config['strong_break']:
            return 'STRONG_BREAK'
        elif break_pct >= timeframe_config['confirmed_break']:
            return 'CONFIRMED_BREAK'
        elif break_pct >= timeframe_config['soft_break']:
            return 'SOFT_BREAK'
        return 'MINOR_BREAK'

    def _calculate_breakout_strength(self, break_pct: float, current_volume: float,
                                     volume_ma: float, df: pd.DataFrame, direction: str,
                                     timeframe_config: Dict) -> float:
        """Tính điểm sức mạnh breakout (0-100)"""
        score = 0

        # 1. Điểm từ khoảng cách break (40 điểm)
        strong_break_threshold = timeframe_config['strong_break']
        distance_score = min(40, (break_pct / strong_break_threshold) * 40)
        score += distance_score

        # 2. Điểm từ volume (30 điểm)
        volume_ratio = current_volume / volume_ma if volume_ma > 0 else 1
        volume_threshold = timeframe_config['volume_spike_threshold']
        if volume_ratio >= volume_threshold:
            score += 30
        elif volume_ratio >= volume_threshold * 0.8:
            score += 20
        elif volume_ratio >= 1.0:
            score += 10

        # 3. Điểm từ pattern nến (30 điểm)
        candle_score = self._evaluate_candle_strength(df, direction)
        score += candle_score

        return min(100, score)

    @staticmethod
    def _evaluate_candle_strength(df: pd.DataFrame, direction: str) -> float:
        """Đánh giá sức mạnh nến breakout"""
        if len(df) < 2:
            return 0

        current_candle = df.iloc[-1]
        score = 0

        # Thân nến dài (15 điểm)
        body_size = abs(current_candle['close'] - current_candle['open'])
        total_range = current_candle['high'] - current_candle['low']

        if total_range > 0:
            body_ratio = body_size / total_range
            if body_ratio >= 0.7:
                score += 15
            elif body_ratio >= 0.5:
                score += 10
            elif body_ratio >= 0.3:
                score += 5

        # Đóng cửa ở extreme (15 điểm)
        if direction == 'UP':
            close_position = (current_candle['close'] - current_candle['low']) / total_range
            if close_position >= 0.7:
                score += 15
        else:  # DOWN
            close_position = (current_candle['high'] - current_candle['close']) / total_range
            if close_position >= 0.7:
                score += 15

        return score

    def get_monitoring_status(self) -> Dict:
        """Get the current status of monitoring"""
        active_zones = 0
        breakout_zones = 0
        completed_zones = 0

        for symbol, zones in self.accumulation_zones.items():
            for zone in zones:
                if zone['status'] == 'ACTIVE':
                    active_zones += 1
                elif zone['status'] == 'BREAKOUT':
                    breakout_zones += 1
                elif zone['status'] == 'COMPLETED':
                    completed_zones += 1

        return {
            'active_zones': active_zones,
            'breakout_zones': breakout_zones,
            'completed_zones': completed_zones,
            'total_symbols': len(self.accumulation_zones)
        }

    @staticmethod
    def _update_zone_status(zone: Dict, breakout_result: Dict):
        """Cập nhật trạng thái zone sau breakout"""
        zone['last_breakout_time'] = time.time()

        if breakout_result['is_strong_breakout']:
            # Breakout mạnh -> hoàn thành, không theo dõi nữa
            zone['status'] = 'COMPLETED'
            logger.info(f"🎯 Breakout mạnh - Kết thúc: {zone['symbol']}")
        else:
            # Breakout yếu/trung bình -> tiếp tục theo dõi
            zone['status'] = 'BREAKOUT'
            logger.info(f"⚡ Breakout - Theo dõi tiếp: {zone['symbol']}")

    def cleanup_old_zones(self):
        """Dọn dẹp zones cũ"""
        current_time = time.time()
        max_age = 24 * 3600  # 24 giờ

        for symbol, zones in self.accumulation_zones.items():
            self.accumulation_zones[symbol] = [
                zone for zone in zones
                if current_time - zone['created_at'] <= max_age
            ]
