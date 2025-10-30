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
    """Detect and track accumulation zones"""

    def __init__(self, exchange: ccxt.Exchange, notifier: TelegramNotifier):
        self.exchange = exchange
        self.notifier = notifier
        self.timeframe = settings.TIMEFRAME
        self.lookback = settings.LOOKBACK_BARS
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
        if len(df) < self.lookback + 1:
            return None

        window_df = df.iloc[-self.lookback:]

        # Calculate ATR ratio
        atr_series = atr(df, period=14)
        atr_now = atr_series.iloc[-1]
        close_now = df['close'].iloc[-1]
        atr_ratio = atr_now / close_now if close_now > 0 else np.inf

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
        bbw = bollinger_band_width(df, period=self.lookback).iloc[-1]

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
            }
        return None

    def mark_zone(self, symbol: str, zone: Dict):
        """Mark accumulation zone for symbol"""
        now = pd.Timestamp.utcnow()
        self.zones[symbol] = {
            'upper': zone['upper'],
            'lower': zone['lower'],
            'width': zone['width'],
            'detected_at': now,
            'last_accum_notified': now,
            'breakout_up': False,
            'breakout_down': False,
            'last_breakout_notified': None,
            'last_proximity_notified': None,
        }

    def clear_zone(self, symbol: str):
        """Clear zone for symbol"""
        if symbol in self.zones:
            del self.zones[symbol]

    def was_recent(self, ts: Optional[pd.Timestamp], minutes: int) -> bool:
        """Check if timestamp was within last N minutes"""
        if ts is None:
            return False
        return (pd.Timestamp.utcnow() - ts).total_seconds() < minutes * 60

    def check_symbol(self, symbol: str):
        """Check symbol for accumulation, proximity, and breakout"""
        logger.info(f"[CHECK] Scanning {symbol}...")

        df = self.fetch_ohlcv(symbol)
        if df is None or len(df) < self.lookback:
            logger.warning(f"[SKIP] Not enough data for {symbol}")
            return

        close_price = float(df['close'].iloc[-1])

        # 1) Detect accumulation
        zone_info = self.detect_accumulation(df)
        if zone_info is not None:
            zone = self.zones.get(symbol)

            # Register new zone if bounds changed significantly
            if zone is None or \
                    abs(zone_info['upper'] - zone['upper']) / zone['upper'] > 0.002 or \
                    abs(zone_info['lower'] - zone['lower']) / zone['lower'] > 0.002:
                self.mark_zone(symbol, zone_info)

                msg = (
                    f"💤 *ACCUMULATION DETECTED*\n"
                    f"Symbol: {symbol}\n"
                    f"Range: {zone_info['lower']:.6f} - {zone_info['upper']:.6f}\n"
                    f"Width: {zone_info['width'] * 100:.3f}%\n"
                    f"Price: {close_price:.6f}\n"
                    f"Time(UTC): {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                logger.info(msg)
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
            msg = (
                f"🔔 *PRICE NEAR RESISTANCE*\n"
                f"Symbol: {symbol}\n"
                f"Price: {price:.6f}\n"
                f"Resistance: {upper:.6f}\n"
                f"Support: {lower:.6f}\n"
                f"Time(UTC): {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(msg)
            self.notifier.send_message(msg)
            zone['last_proximity_notified'] = pd.Timestamp.utcnow()

        # Near support
        if abs(price - lower) / lower <= settings.PROXIMITY_THRESHOLD and not zone.get('breakout_down', False):
            msg = (
                f"🔔 *PRICE NEAR SUPPORT*\n"
                f"Symbol: {symbol}\n"
                f"Price: {price:.6f}\n"
                f"Support: {lower:.6f}\n"
                f"Resistance: {upper:.6f}\n"
                f"Time(UTC): {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(msg)
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
        vol_spike = recent_vol > settings.VOL_SPIKE_MULTIPLIER * vol_mean

        # Breakout up
        if breakout_up and not zone.get('breakout_up', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            msg = (
                f"🚀 *BREAKOUT UP*\n"
                f"Symbol: {symbol}\n"
                f"Price: {price:.6f}\n"
                f"Resistance: {upper:.6f}\n"
                f"Support: {lower:.6f}\n"
                f"Volume: {recent_vol:.3f} (mean {vol_mean:.3f})\n"
                f"Time(UTC): {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(msg)
            self.notifier.send_message(msg)
            zone['breakout_up'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()

        # Breakout down
        if breakout_down and not zone.get('breakout_down', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            msg = (
                f"⚠️ *BREAKOUT DOWN*\n"
                f"Symbol: {symbol}\n"
                f"Price: {price:.6f}\n"
                f"Support: {lower:.6f}\n"
                f"Resistance: {upper:.6f}\n"
                f"Volume: {recent_vol:.3f} (mean {vol_mean:.3f})\n"
                f"Time(UTC): {pd.Timestamp.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            logger.info(msg)
            self.notifier.send_message(msg)
            zone['breakout_down'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()

        # Clear zone after breakout cooldown expires
        if (zone.get('breakout_up') or zone.get('breakout_down')) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            self.clear_zone(symbol)
