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
        self.timeframe = settings.TIMEFRAME
        self.lookback = settings.LOOKBACK_BARS
        self.lookback_windows = [12, 24]
        self.zones: Dict[str, Dict] = {}

    def fetch_ohlcv(self, symbol: str, limit: int = None) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for symbol"""
        if limit is None:
            limit = settings.FETCH_LIMIT

        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe=self.timeframe, limit=limit)
            return ohlcv_to_df(ohlcv)
        except Exception as e:
            logger.error(f'Error fetching OHLCV for {symbol}: {e}')
            return None

    def detect_accumulation(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect if market is in accumulation phase"""

        # Calculate ATR ratio
        atr_series = atr(df, period=14)
        atr_now = atr_series.iloc[-1]
        close_now = df['close'].iloc[-1]
        atr_ratio = atr_now / close_now if close_now > 0 else np.inf

        for lookback in reversed(self.lookback_windows):  # [24, 12]
            if len(df) < lookback + 1:
                continue

            window_df = df.iloc[-lookback:]

            # Calculate volume ratio
            vol_now_mean = window_df['volume'].mean()
            if len(df) >= self.lookback * 2:
                vol_prev_mean = df['volume'].iloc[-(self.lookback * 2):-self.lookback].mean()
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
                f'Conditions: atr={cond_atr}, vol={cond_vol}, range={cond_range}, '
                f'bbw={bbw:.6f}, atr_ratio={atr_ratio:.6f}'
            )

            if cond_atr and cond_vol and cond_range and cond_bbw:
                return {
                    'upper': float(price_max),
                    'lower': float(price_min),
                    'width': float(price_range),
                    'atr_ratio': float(atr_ratio),
                    'vol_ratio': float(vol_ratio),
                    'mid': float((price_max + price_min) / 2),
                    'lookback': lookback,
                    'duration_hours': lookback * 5 / 60,
                }
        return None

    def mark_zone(self, symbol: str, zone: Dict):
        """Mark accumulation zone for symbol"""
        now = pd.Timestamp.utcnow()
        self.zones[symbol] = {
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
        }

    def clear_zone(self, symbol: str):
        """Clear zone for symbol"""
        if symbol in self.zones:
            logger.info(f"Clearing zone for {symbol}")
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

    def _format_accumulation_message(self, symbol: str, zone_info: Dict, price: float) -> str:
        """Format accumulation detection message"""
        upper = zone_info['upper']
        lower = zone_info['lower']
        mid = zone_info['mid']
        width_pct = zone_info['width'] * 100

        # Calculate price position in zone (0-100%)
        if lower <= price <= upper:
            position = ((price - lower) / (upper - lower)) * 100
        else:
            position = 50  # default to middle if outside

        # Create mini chart
        chart = self._create_mini_chart(lower, upper, price)

        # Strength indicator
        duration = zone_info.get('duration_hours', 2)  # ← THÊM
        if duration >= 2:
            strength = "🟢 Mạnh (2+ giờ)" if zone_info['atr_ratio'] < 0.001 else "🟡 Trung bình (2+ giờ)"
        else:
            strength = "🟡 Trung bình (1 giờ)"

        msg = (
            f"💤 *PHÁT HIỆN TÍCH LUỸ*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 *{symbol}*\n\n"
            f"📊 *Khu vực tích luỹ:*\n"
            f"{chart}\n"
            f"├ 🔴 Kháng cự: `{upper:.6f}`\n"
            f"├ 🔵 Trung tâm: `{mid:.6f}`\n"
            f"└ 🟢 Hỗ trợ: `{lower:.6f}`\n\n"
            f"💰 Giá hiện tại: `{price:.6f}`\n"
            f"📏 Độ rộng zone: `{width_pct:.2f}%`\n"
            f"📍 Vị trí: `{position:.0f}%` trong zone\n\n"
            f"💪 Độ mạnh: {strength}\n"
            f"⏱ {pd.Timestamp.utcnow().strftime('%H:%M:%S UTC')}"
        )
        return msg

    def _format_proximity_message(self, symbol: str, price: float, level: float,
                                  level_type: str, zone: Dict) -> str:
        """Format proximity alert message"""
        upper = zone['upper']
        lower = zone['lower']
        distance_pct = abs(price - level) / level * 100

        emoji = "🔴" if level_type == "resistance" else "🟢"
        level_name = "Kháng cự" if level_type == "resistance" else "Hỗ trợ"

        # Create mini chart
        chart = self._create_mini_chart(lower, upper, price)

        msg = (
            f"{emoji} *GIÁ GẦN {level_name.upper()}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 *{symbol}*\n\n"
            f"{chart}\n\n"
            f"💰 Giá: `{price:.6f}`\n"
            f"🎯 {level_name}: `{level:.6f}`\n"
            f"📏 Khoảng cách: `{distance_pct:.3f}%`\n\n"
            f"📊 Zone: `{lower:.6f}` - `{upper:.6f}`\n"
            f"⏱ {pd.Timestamp.utcnow().strftime('%H:%M:%S UTC')}"
        )
        return msg

    @staticmethod
    def _format_breakout_message(symbol: str, price: float, direction: str,
                                 zone: Dict, vol_spike: bool, vol_ratio: float) -> str:
        """Format breakout alert message"""
        upper = zone['upper']
        lower = zone['lower']

        if direction == "up":
            emoji = "🚀"
            title = "BREAKOUT TĂNG"
            level = upper
            level_name = "Kháng cự"
            color = "🟢"
        else:
            emoji = "⚠️"
            title = "BREAKOUT GIẢM"
            level = lower
            level_name = "Hỗ trợ"
            color = "🔴"

        breakout_pct = abs(price - level) / level * 100

        # Volume confirmation
        vol_confirm = "✅ Khối lượng xác nhận" if vol_spike else "⚠️ Khối lượng thấp"

        msg = (
            f"{emoji} *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🪙 *{symbol}*\n\n"
            f"{color} Giá đã vượt {level_name.lower()}\n\n"
            f"💰 Giá hiện tại: `{price:.6f}`\n"
            f"🎯 {level_name}: `{level:.6f}`\n"
            f"📈 Breakout: `{breakout_pct:.2f}%`\n\n"
            f"📊 *Chi tiết Zone:*\n"
            f"├ Kháng cự: `{upper:.6f}`\n"
            f"└ Hỗ trợ: `{lower:.6f}`\n\n"
            f"📦 Volume: `x{vol_ratio:.2f}` {vol_confirm}\n"
            f"⏱ {pd.Timestamp.utcnow().strftime('%H:%M:%S UTC')}\n\n"
            f"{'🎯 *Setup tốt để entry!*' if vol_spike else '⚠️ *Chờ xác nhận thêm*'}"
        )
        return msg

    @staticmethod
    def _create_mini_chart(lower: float, upper: float, price: float) -> str:
        """Create a mini ASCII chart showing price position"""
        # Calculate relative positions (0-20 scale for chart)
        total_range = upper - lower
        if total_range == 0:
            return "│" * 20

        price_pos = int(((price - lower) / total_range) * 20)
        mid_pos = 10  # middle is always at 50%

        # Build chart
        chart = "┌" + "─" * 22 + "┐\n│ "
        for i in range(20):
            if i == price_pos:
                chart += "●"  # Current price
            elif i == mid_pos:
                chart += "·"  # Middle line
            else:
                chart += " "
        chart += " │\n└" + "─" * 22 + "┘"

        return chart

    def check_symbol(self, symbol: str):
        """Check symbol for accumulation, proximity, and breakout"""
        logger.info(f"[CHECK] Scanning {symbol}...")

        df = self.fetch_ohlcv(symbol)
        if df is None or len(df) < min(self.lookback_windows):
            logger.warning(f"[SKIP] Not enough data for {symbol}")
            return

        close_price = float(df['close'].iloc[-1])

        # 1) Detect accumulation
        zone_info = self.detect_accumulation(df)
        if zone_info is not None:
            zone = self.zones.get(symbol)

            # Register new zone if it doesn't exist or is significantly different
            should_notify = False
            if zone is None:
                should_notify = True
                self.mark_zone(symbol, zone_info)
            elif self._is_zone_significantly_different(zone_info, zone):
                # Update zone but don't spam notifications
                if not self.was_recent(zone.get('last_accum_notified'), settings.ACCUMULATION_COOLDOWN_MIN):
                    should_notify = True
                    self.mark_zone(symbol, zone_info)

            if should_notify:
                msg = self._format_accumulation_message(symbol, zone_info, close_price)
                logger.info(f"[ACCUMULATION] {symbol}")
                self.notifier.send_message(msg)

        # 2) Check proximity and breakout if zone exists
        if symbol not in self.zones:
            logger.info(f"[NO SIGNAL] {symbol} — no active zone")
            return

        zone = self.zones[symbol]
        upper = zone['upper']
        lower = zone['lower']

        # Check zone expiration
        if (pd.Timestamp.utcnow() - zone['detected_at']) > pd.Timedelta(hours=settings.ZONE_EXPIRE_HOURS):
            logger.info(f'Zone for {symbol} expired (>{settings.ZONE_EXPIRE_HOURS}h). Clearing.')
            self.clear_zone(symbol)
            return

        # Check proximity to support/resistance
        self._check_proximity(symbol, close_price, upper, lower, zone)

        # Check breakout
        self._check_breakout(symbol, df, close_price, upper, lower, zone)

    def _check_proximity(self, symbol: str, price: float, upper: float, lower: float, zone: Dict):
        """Check if price is near support/resistance"""
        if self.was_recent(zone.get('last_proximity_notified'), settings.PROXIMITY_COOLDOWN_MIN):
            return

        # Near resistance
        if abs(price - upper) / upper <= settings.PROXIMITY_THRESHOLD and not zone.get('breakout_up', False):
            msg = self._format_proximity_message(symbol, price, upper, "resistance", zone)
            logger.info(f"[PROXIMITY] {symbol} near resistance")
            self.notifier.send_message(msg)
            zone['last_proximity_notified'] = pd.Timestamp.utcnow()

        # Near support
        elif abs(price - lower) / lower <= settings.PROXIMITY_THRESHOLD and not zone.get('breakout_down', False):
            msg = self._format_proximity_message(symbol, price, lower, "support", zone)
            logger.info(f"[PROXIMITY] {symbol} near support")
            self.notifier.send_message(msg)
            zone['last_proximity_notified'] = pd.Timestamp.utcnow()

    def _check_breakout(self, symbol: str, df: pd.DataFrame, price: float,
                        upper: float, lower: float, zone: Dict):
        """Check for breakout from accumulation zone"""
        breakout_up = price > upper * (1 + 0.001)  # 0.1% buffer
        breakout_down = price < lower * (1 - 0.001)

        # Calculate volume spike
        recent_vol = float(df['volume'].iloc[-1])
        vol_mean = float(df['volume'].iloc[-self.lookback:].mean()) if len(df) >= self.lookback else recent_vol
        vol_ratio = recent_vol / vol_mean if vol_mean > 0 else 1.0
        vol_spike = recent_vol > settings.VOL_SPIKE_MULTIPLIER * vol_mean

        # Breakout up
        if breakout_up and not zone.get('breakout_up', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            msg = self._format_breakout_message(symbol, price, "up", zone, vol_spike, vol_ratio)
            logger.info(f"[BREAKOUT UP] {symbol}")
            self.notifier.send_message(msg)
            zone['breakout_up'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()

        # Breakout down
        elif breakout_down and not zone.get('breakout_down', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            msg = self._format_breakout_message(symbol, price, "down", zone, vol_spike, vol_ratio)
            logger.info(f"[BREAKOUT DOWN] {symbol}")
            self.notifier.send_message(msg)
            zone['breakout_down'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()

        # Clear zone after breakout cooldown expires
        if (zone.get('breakout_up') or zone.get('breakout_down')) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            self.clear_zone(symbol)
