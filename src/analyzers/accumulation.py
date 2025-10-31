from typing import Dict, Optional

import ccxt
import numpy as np
import pandas as pd

from config.setting import settings
from src.indicators.technical import atr, bollinger_band_width
from src.notifiers.telegram import TelegramNotifier
from src.utils.helpers import ohlcv_to_df
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class AccumulationAnalyzer:
    """Detect and track accumulation zones with improved logic"""

    def __init__(self, exchange: ccxt.Exchange, notifier: TelegramNotifier):
        self.exchange = exchange
        self.notifier = notifier
        self.timeframes = settings.TIMEFRAMES
        self.lookback_windows = [12, 24]
        self.zones: Dict[str, Dict[str, Dict]] = {}

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = None) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for symbol"""
        if limit is None:
            limit = settings.FETCH_LIMIT

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            return ohlcv_to_df(ohlcv)
        except Exception as e:
            logger.error(f'Error fetching {timeframe} OHLCV for {symbol}: {e}')
            return None

    def detect_accumulation(self, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
        """Detect if market is in accumulation phase"""

        # Calculate ATR ratio
        atr_series = atr(df, period=14)
        atr_now = atr_series.iloc[-1]
        close_now = df['close'].iloc[-1]
        atr_ratio = atr_now / close_now if close_now > 0 else np.inf

        for lookback in reversed(self.lookback_windows):
            if len(df) < lookback + 1:
                continue

            window_df = df.iloc[-lookback:]

            # Calculate volume ratio
            vol_now_mean = window_df['volume'].mean()
            if len(df) >= lookback * 2:
                vol_prev_mean = df['volume'].iloc[-(lookback * 2):-lookback].mean()
            else:
                vol_prev_mean = df['volume'].mean()
            vol_ratio = vol_now_mean / vol_prev_mean if vol_prev_mean > 0 else 1.0

            # Calculate price range
            price_max = window_df['high'].max()
            price_min = window_df['low'].min()
            price_range = (price_max - price_min) / price_min if price_min > 0 else np.inf

            # Calculate Bollinger Band width
            bbw = bollinger_band_width(df, period=lookback).iloc[-1]

            # Check conditions
            cond_atr = atr_ratio < settings.ATR_RATIO_THRESHOLD
            cond_vol = vol_ratio < settings.VOL_RATIO_THRESHOLD
            cond_range = price_range < settings.PRICE_RANGE_THRESHOLD
            cond_bbw = bbw < settings.PRICE_RANGE_THRESHOLD * 2

            logger.debug(
                f'{timeframe} - Conditions: atr={cond_atr}, vol={cond_vol}, '
                f'range={cond_range}, bbw={bbw:.6f}, atr_ratio={atr_ratio:.6f}'
            )

            if cond_atr and cond_vol and cond_range and cond_bbw:
                tf_meta = settings.TIMEFRAME_METADATA[timeframe]
                duration_hours = lookback * tf_meta['duration_factor']

                return {
                    'upper': float(price_max),
                    'lower': float(price_min),
                    'width': float(price_range),
                    'atr_ratio': float(atr_ratio),
                    'vol_ratio': float(vol_ratio),
                    'mid': float((price_max + price_min) / 2),
                    'lookback': lookback,
                    'duration_hours': duration_hours,
                    'timeframe': timeframe
                }
        return None

    @staticmethod
    def _calculate_tp_sl(entry_price: float, direction: str, zone: Dict) -> Dict:
        """Hybrid approach: Zone-based with ATR validation"""

        upper = zone['upper']
        lower = zone['lower']
        zone_width = upper - lower
        atr_ratio = zone.get('atr_ratio', 0.002)
        atr_value = entry_price * atr_ratio

        if direction == "up":
            # Long setup
            sl_zone = lower * 0.995
            sl_atr = entry_price - (atr_value * 2)
            sl = min(sl_zone, sl_atr)

            tp_zone = entry_price + zone_width
            risk = entry_price - sl
            tp_rr = entry_price + (risk * 2)
            tp = min(tp_zone, tp_rr)

            return {
                'entry': entry_price,
                'sl': sl,
                'tp': tp,
                'risk_pct': ((entry_price - sl) / entry_price) * 100,
                'reward_pct': ((tp - entry_price) / entry_price) * 100
            }
        else:
            # Short setup
            sl_zone = upper * 1.005
            sl_atr = entry_price + (atr_value * 2)
            sl = max(sl_zone, sl_atr)

            tp_zone = entry_price - zone_width
            risk = sl - entry_price
            tp_rr = entry_price - (risk * 2)
            tp = max(tp_zone, tp_rr)

            return {
                'entry': entry_price,
                'sl': sl,
                'tp': tp,
                'risk_pct': ((sl - entry_price) / entry_price) * 100,
                'reward_pct': ((entry_price - tp) / entry_price) * 100
            }

    def mark_zone(self, symbol: str, timeframe: str, zone: Dict):
        """Mark accumulation zone for symbol"""
        now = pd.Timestamp.utcnow()

        if symbol not in self.zones:
            self.zones[symbol] = {}

        self.zones[symbol][timeframe] = {
            'upper': zone['upper'],
            'lower': zone['lower'],
            'mid': zone['mid'],
            'width': zone['width'],
            'detected_at': now,
            'last_accum_notified': now,
            'breakout_up': False,
            'breakout_down': False,
            'last_breakout_notified': None,
            'last_proximity_notified': None,
            'atr_ratio': zone['atr_ratio'],
            'vol_ratio': zone['vol_ratio'],
            'duration_hours': zone['duration_hours']
        }

        logger.info(f"Marked {timeframe} zone for {symbol}: {zone['lower']:.2f} - {zone['upper']:.2f}")

    def clear_zone(self, symbol: str, timeframe: str):
        """Clear zone for symbol on specific timeframe"""
        if symbol in self.zones and timeframe in self.zones[symbol]:
            logger.info(f"Clearing {timeframe} zone for {symbol}")
            del self.zones[symbol][timeframe]

            # Clean up symbol entry if no timeframes left
            if not self.zones[symbol]:
                del self.zones[symbol]

    @staticmethod
    def was_recent(ts: Optional[pd.Timestamp], minutes: int) -> bool:
        """Check if timestamp was within last N minutes"""
        if ts is None:
            return False
        return (pd.Timestamp.utcnow() - ts).total_seconds() < minutes * 60

    @staticmethod
    def _is_zone_significantly_different(zone_info: Dict, existing_zone: Dict) -> bool:
        """Check if new zone is significantly different from existing one"""
        upper_diff = abs(zone_info['upper'] - existing_zone['upper']) / existing_zone['upper']
        lower_diff = abs(zone_info['lower'] - existing_zone['lower']) / existing_zone['lower']

        # Require at least 0.5% change in either bound to consider it a new zone
        return upper_diff > 0.005 or lower_diff > 0.005

    @staticmethod
    def _format_accumulation_message(symbol: str, timeframe: str, zone_info: Dict, price: float) -> str:
        """Format accumulation detection message"""
        upper = zone_info['upper']
        lower = zone_info['lower']
        width_pct = zone_info['width'] * 100
        duration = zone_info['duration_hours']

        # Get timeframe metadata
        tf_meta = settings.TIMEFRAME_METADATA[timeframe]

        # Calculate price position in zone (0-100%)
        if lower <= price <= upper:
            position = ((price - lower) / (upper - lower)) * 100
        else:
            position = 50  # default to middle if outside

        # Strength indicator
        if duration >= 12:
            strength = "🟢 Cực mạnh" if zone_info['atr_ratio'] < 0.001 else "🟢 Mạnh"
        elif duration >= 6:
            strength = "🟢 Mạnh" if zone_info['atr_ratio'] < 0.001 else "🟡 Trung bình"
        else:
            strength = "🟡 Trung bình"

        msg = (
            f"💤 *PHÁT HIỆN TÍCH LUỸ*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🪙 *{symbol}*\n"
            f"⏱ {tf_meta['style']} ({tf_meta['label']})\n\n"
            f"💰 Giá hiện tại: `{price:.6f}`\n"
            f"🔴 Kháng cự: `{upper:.6f}`\n"
            f"🟢 Hỗ trợ: `{lower:.6f}`\n\n"
            f"📊 Độ rộng *{width_pct:.2f}%* • Vị trí *{position:.0f}%*\n"
            f"⏳ Tích luỹ *{duration:.1f}h* • {strength}\n\n"
            f"💪 Độ mạnh: {strength}\n\n"
        )
        return msg

    @staticmethod
    def _format_proximity_message(symbol: str, timeframe: str, price: float, level: float,
                                  level_type: str) -> str:
        """Format proximity alert message"""
        distance_pct = abs(price - level) / level * 100
        tf_meta = settings.TIMEFRAME_METADATA[timeframe]

        if level_type == "resistance":
            emoji = "🔴"
            title = "GIÁ GẦN KHÁNG CỰ"
            level_name = "Kháng cự"
        else:
            emoji = "🟢"
            title = "GIÁ GẦN HỖ TRỢ"
            level_name = "Hỗ trợ"

        msg = (
            f"{emoji} *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🪙 *{symbol}*\n\n"
            f"⏱ {tf_meta['style']} ({tf_meta['label']})\n\n"
            f"💰 Giá hiện tại: `{price:.6f}`\n"
            f"🎯 {level_name}: `{level:.6f}`\n\n"
            f"📏 Khoảng cách: *{distance_pct:.2f}%*\n\n"
        )
        return msg

    def _format_breakout_message(self, symbol: str, timeframe: str, price: float, direction: str,
                                 zone: Dict, vol_spike: bool, vol_ratio: float) -> str:
        """Format breakout alert message with TP/SL"""
        tf_meta = settings.TIMEFRAME_METADATA[timeframe]

        if direction == "up":
            emoji = "🚀"
            title = "BREAKOUT TĂNG"
            level = zone['upper']
            level_name = "Kháng cự"
        else:
            emoji = "📉"
            title = "BREAKOUT GIẢM"
            level = zone['lower']
            level_name = "Hỗ trợ"

        breakout_pct = abs(price - level) / level * 100

        # Calculate TP/SL
        setup = self._calculate_tp_sl(price, direction, zone)

        # Check if aligned with higher timeframes
        higher_tf_confirm = self._check_higher_tf_alignment(symbol, direction, timeframe)

        msg = (
            f"{emoji} *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🪙 *{symbol}*\n\n"
            f"⏱ Timeframe: *{tf_meta['label']}* {tf_meta['style']}\n\n"
            f"💰 Giá hiện tại: `{price:.6f}`\n"
            f"🎯 {level_name}: `{level:.6f}`\n"
            f"📈 Breakout: *{breakout_pct:.2f}%*\n\n"
            f"📦 Volume: *x{vol_ratio:.1f}* "
        )

        # Volume assessment
        if vol_spike:
            msg += "✅\n\n"

            # Higher TF confirmation
            if higher_tf_confirm:
                msg += "✅ _Confirm TF cao hơn_\n"

            msg += (
                f"\n━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *GỢI Ý SETUP*\n\n"
                f"📍 Entry: `{setup['entry']:.6f}`\n"
                f"🛑 SL: `{setup['sl']:.6f}` _(-{setup['risk_pct']:.2f}%)_\n"
                f"🎯 TP: `{setup['tp']:.6f}` _(+{setup['reward_pct']:.2f}%)_\n"
                f"📊 R:R = *1:2*\n\n"
                f"⏱ {tf_meta['hold_time']} • Risk {tf_meta['risk']}\n\n"
            )

            if higher_tf_confirm:
                msg += "✅ _Setup chất lượng cao_\n"
            else:
                msg += "🟡 _Setup tốt (chưa confirm TF cao)_\n"

            msg += "⚠️ _Tự kiểm tra trước khi vào_"
        else:
            msg += "⚠️\n\n"
            msg += (
                f"━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⚠️ *VOLUME KHÔNG XÁC NHẬN*\n\n"
                f"Breakout có thể là fake:\n"
                f"• Volume thấp (x{vol_ratio:.1f})\n"
                f"• Chờ volume tăng\n"
                f"• Hoặc giá test lại {level_name.lower()}\n\n"
                f"🔍 _Quan sát thêm, chưa vào lệnh_"
            )

        return msg

    def _check_higher_tf_alignment(self, symbol: str, direction: str, current_tf: str) -> bool:
        """Check if breakout aligns with higher timeframes"""
        if symbol not in self.zones:
            return False

        # Timeframe priority (higher = more important)
        tf_order = {'5m': 0, '15m': 1, '30m': 2, '1h': 3}
        current_priority = tf_order.get(current_tf, 0)

        # Check higher timeframes
        for tf, zone in self.zones[symbol].items():
            if tf_order.get(tf, 0) > current_priority:
                # Check if also breaking out on higher TF
                if (direction == "up" and zone.get('breakout_up')) or \
                        (direction == "down" and zone.get('breakout_down')):
                    return True

        return False

    def check_symbol(self, symbol: str):
        """Check symbol across all timeframes"""
        logger.info(f"[MULTI-TF CHECK] Scanning {symbol}...")

        # Check each timeframe
        for timeframe in self.timeframes:
            self._check_timeframe(symbol, timeframe)

    def _check_timeframe(self, symbol: str, timeframe: str):
        """Check accumulation on specific timeframe"""
        logger.debug(f"[CHECK] {symbol} on {timeframe}")

        df = self.fetch_ohlcv(symbol, timeframe)
        if df is None or len(df) < min(self.lookback_windows):
            logger.warning(f"[SKIP] Not enough data for {symbol} {timeframe}")
            return

        close_price = float(df['close'].iloc[-1])

        # 1) Detect accumulation
        zone_info = self.detect_accumulation(df, timeframe)

        if zone_info is not None:
            # Get existing zone for this timeframe
            existing_zone = self.zones.get(symbol, {}).get(timeframe)

            # Register new zone if it doesn't exist or is significantly different
            should_notify = False
            if existing_zone is None:
                should_notify = True
                self.mark_zone(symbol, timeframe, zone_info)
            elif self._is_zone_significantly_different(zone_info, existing_zone):
                # Update zone but don't spam notifications
                if not self.was_recent(existing_zone.get('last_accum_notified'),
                                       settings.ACCUMULATION_COOLDOWN_MIN):
                    should_notify = True
                    self.mark_zone(symbol, timeframe, zone_info)

            if should_notify:
                msg = self._format_accumulation_message(symbol, timeframe, zone_info, close_price)
                logger.info(f"[ACCUMULATION] {symbol} {timeframe}")
                self.notifier.send_message(msg)

        # 2) Check proximity and breakout if zone exists
        if symbol not in self.zones or timeframe not in self.zones[symbol]:
            logger.debug(f"[NO ZONE] {symbol} {timeframe}")
            return

        zone = self.zones[symbol][timeframe]
        upper = zone['upper']
        lower = zone['lower']

        # Check zone expiration
        if (pd.Timestamp.utcnow() - zone['detected_at']) > pd.Timedelta(hours=settings.ZONE_EXPIRE_HOURS):
            logger.info(f'Zone for {symbol} {timeframe} expired (>{settings.ZONE_EXPIRE_HOURS}h)')
            self.clear_zone(symbol, timeframe)
            return

        # Check proximity to support/resistance
        # self._check_proximity(symbol, timeframe, close_price, upper, lower, zone)

        # Check breakout
        self._check_breakout(symbol, timeframe, df, close_price, upper, lower, zone)

    # def _check_proximity(self, symbol: str, timeframe: str, price: float,
    #                      upper: float, lower: float, zone: Dict):
    #     """Check if price is near support/resistance"""
    #     if self.was_recent(zone.get('last_proximity_notified'), settings.PROXIMITY_COOLDOWN_MIN):
    #         return
    #
    #     # Near resistance
    #     if abs(price - upper) / upper <= settings.PROXIMITY_THRESHOLD and not zone.get('breakout_up', False):
    #         msg = self._format_proximity_message(symbol, timeframe, price, upper, "resistance")
    #         logger.info(f"[PROXIMITY] {symbol} {timeframe} near resistance")
    #         self.notifier.send_message(msg)
    #         zone['last_proximity_notified'] = pd.Timestamp.utcnow()
    #
    #     # Near support
    #     elif abs(price - lower) / lower <= settings.PROXIMITY_THRESHOLD and not zone.get('breakout_down', False):
    #         msg = self._format_proximity_message(symbol, timeframe, price, lower, "support")
    #         logger.info(f"[PROXIMITY] {symbol} {timeframe} near support")
    #         self.notifier.send_message(msg)
    #         zone['last_proximity_notified'] = pd.Timestamp.utcnow()

    def _check_breakout(self, symbol: str, timeframe: str, df: pd.DataFrame, price: float,
                        upper: float, lower: float, zone: Dict):
        """Check for breakout from accumulation zone"""
        breakout_up = price > upper * (1 + 0.001)  # 0.1% buffer
        breakout_down = price < lower * (1 - 0.001)

        # Calculate volume spike
        recent_vol = float(df['volume'].iloc[-1])
        lookback = min(24, len(df))
        vol_mean = float(df['volume'].iloc[-lookback:].mean())
        vol_ratio = recent_vol / vol_mean if vol_mean > 0 else 1.0
        vol_spike = recent_vol > settings.VOL_SPIKE_MULTIPLIER * vol_mean

        # Breakout up
        if breakout_up and not zone.get('breakout_up', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            msg = self._format_breakout_message(symbol, timeframe, price, "up", zone, vol_spike, vol_ratio)
            logger.info(f"[BREAKOUT UP] {symbol} {timeframe}")
            self.notifier.send_message(msg)
            zone['breakout_up'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()

        # Breakout down
        elif breakout_down and not zone.get('breakout_down', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            msg = self._format_breakout_message(symbol, timeframe, price, "down", zone, vol_spike, vol_ratio)
            logger.info(f"[BREAKOUT DOWN] {symbol} {timeframe}")
            self.notifier.send_message(msg)
            zone['breakout_down'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()

        # Clear zone after breakout cooldown expires
        if (zone.get('breakout_up') or zone.get('breakout_down')) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            self.clear_zone(symbol, timeframe)
