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

    def __init__(self, notifier: TelegramNotifier):
        self.notifier = notifier
        self.timeframes = settings.TIMEFRAMES
        self.lookback_windows = [12, 24]
        self.zones: Dict[str, Dict[str, Dict]] = {}

        # Initialize multiple exchanges
        self.exchanges = {}
        self._initialize_exchanges()

        # Markets cache: exchange_name → set of symbols
        self.markets_cache = {}

        # Symbol mapping: symbol → exchange_name
        self.symbol_exchange_map = {}

        # Load markets and build mapping
        self._load_all_markets()
        self._build_symbol_map()

    def _initialize_exchanges(self):
        """Initialize all configured exchanges"""
        for exchange_id in settings.EXCHANGES:
            try:
                exchange_class = getattr(ccxt, exchange_id)
                self.exchanges[exchange_id] = exchange_class({
                    'enableRateLimit': True
                })
                logger.info(f"✅ Initialized {exchange_id} exchange")
            except Exception as e:
                logger.error(f"❌ Failed to initialize {exchange_id}: {e}")

    def _load_all_markets(self):
        """Load available markets from all exchanges"""
        logger.info("Loading markets from all exchanges...")

        for exchange_id, exchange in self.exchanges.items():
            try:
                markets = exchange.load_markets()
                # Store as set of symbols for fast lookup
                self.markets_cache[exchange_id] = set(markets.keys())
                logger.info(f"✅ Loaded {len(markets)} markets from {exchange_id}")
            except Exception as e:
                logger.error(f"❌ Failed to load markets from {exchange_id}: {e}")
                self.markets_cache[exchange_id] = set()

    def _build_symbol_map(self):
        """
        Build symbol → exchange mapping with priority

        Priority: First exchange in EXCHANGES list gets priority
        Example: If EXCHANGES=['binance', 'bybit']
        - Try binance first
        - If not found, try bybit
        - If still not found, mark as unavailable
        """
        logger.info(f"Building symbol mapping for {len(settings.SYMBOLS)} symbols...")

        for symbol in settings.SYMBOLS:
            found = False

            # Try exchanges in priority order
            for exchange_id in settings.EXCHANGES:
                if symbol in self.markets_cache.get(exchange_id, set()):
                    self.symbol_exchange_map[symbol] = exchange_id

                    # Log with priority indication
                    if exchange_id == settings.EXCHANGES[0]:
                        logger.info(f"✅ {symbol} → {exchange_id} (primary)")
                    else:
                        logger.info(f"✅ {symbol} → {exchange_id} (fallback)")

                    found = True
                    break  # Found, stop checking other exchanges

            if not found:
                logger.warning(f"⚠️ {symbol} → NOT AVAILABLE on any exchange")

    @staticmethod
    def _calculate_volume_spike_dual_window(df: pd.DataFrame, timeframe: str) -> tuple[bool, float, float]:
        """
        Dual-window volume spike detection

        Compares current volume against:
        - Short-term baseline (recent trend)
        - Medium-term baseline (overall context)

        Args:
            df: OHLCV dataframe
            timeframe: Current timeframe

        Returns:
            (is_spike, short_ratio, medium_ratio)
        """

        current_vol = float(df['volume'].iloc[-1])

        # Get timeframe-specific settings
        short_window = settings.get_tf_setting(timeframe, 'vol_lookback_short')
        medium_window = settings.get_tf_setting(timeframe, 'vol_lookback_medium')
        short_mult = settings.get_tf_setting(timeframe, 'vol_spike_short_mult')
        medium_mult = settings.get_tf_setting(timeframe, 'vol_spike_medium_mult')

        # Ensure we have enough data
        short_window = min(short_window, len(df) - 1)
        medium_window = min(medium_window, len(df) - 1)

        # Calculate baseline volumes (exclude current candle)
        vol_short_mean = float(df['volume'].iloc[-short_window - 1:-1].mean())
        vol_medium_mean = float(df['volume'].iloc[-medium_window - 1:-1].mean())

        # Avoid division by zero
        if vol_short_mean == 0 or vol_medium_mean == 0:
            return False, 0.0, 0.0

        # Calculate ratios
        short_ratio = current_vol / vol_short_mean
        medium_ratio = current_vol / vol_medium_mean

        # Dual confirmation: must exceed BOTH thresholds
        is_spike = (short_ratio > short_mult) and (medium_ratio > medium_mult)

        logger.debug(
            f'{timeframe} Volume check: short={short_ratio:.2f}x (need >{short_mult}x), '
            f'medium={medium_ratio:.2f}x (need >{medium_mult}x), spike={is_spike}'
        )

        return is_spike, short_ratio, medium_ratio

    def _check_higher_tf_consensus(self, symbol: str, direction: str, current_tf: str) -> Dict:
        """
        Check multi-timeframe consensus for signal quality

        Returns:
            {
                'consensus': bool,
                'score': int,
                'total': int,
                'aligned_tfs': List[str],
                'quality': str
            }
        """

        if symbol not in self.zones:
            return {
                'consensus': False,
                'score': 0,
                'total': 0,
                'aligned_tfs': [],
                'quality': 'weak'
            }

        tf_order = {'5m': 0, '15m': 1, '30m': 2, '1h': 3}
        current_priority = tf_order.get(current_tf, 0)

        aligned_tfs = []
        total_higher_tfs = 0

        # Check all higher timeframes
        for tf, zone in self.zones[symbol].items():
            tf_priority = tf_order.get(tf, 0)

            if tf_priority > current_priority:
                total_higher_tfs += 1

                # Check if this TF is breaking in same direction (merged logic)
                breakout_key = 'breakout_up' if direction == "up" else 'breakout_down'
                if zone.get(breakout_key):
                    aligned_tfs.append(tf)

        score = len(aligned_tfs)

        # Get required consensus for this timeframe
        required = settings.get_tf_setting(current_tf, 'consensus_required')
        consensus = score >= required

        # Determine quality based on alignment
        if score >= 3:
            quality = 'excellent'
        elif score >= 2:
            quality = 'good'
        elif score >= 1:
            quality = 'medium'
        else:
            quality = 'weak'

        logger.debug(
            f'{symbol} {current_tf} {direction} - Consensus: {score}/{total_higher_tfs} '
            f'(need >={required}), quality={quality}'
        )

        return {
            'consensus': consensus,
            'score': score,
            'total': total_higher_tfs,
            'aligned_tfs': aligned_tfs,
            'quality': quality
        }

    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = None) -> Optional[pd.DataFrame]:
        """Fetch OHLCV data for symbol"""
        if limit is None:
            limit = settings.FETCH_LIMIT

        # Get exchange for this symbol
        exchange_id = self.symbol_exchange_map.get(symbol)

        if not exchange_id:
            logger.error(f'[SKIP] {symbol} not available on any exchange')
            return None

        exchange = self.exchanges[exchange_id]

        try:
            ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            return ohlcv_to_df(ohlcv)
        except Exception as e:
            logger.error(f'Error fetching {timeframe} OHLCV for {symbol} from {exchange_id}: {e}')
            return None

    def detect_accumulation(self, df: pd.DataFrame, timeframe: str) -> Optional[Dict]:
        """Detect if market is in accumulation phase with timeframe-specific thresholds"""

        # Get timeframe-specific thresholds
        atr_threshold = settings.get_tf_setting(timeframe, 'atr_threshold')
        vol_threshold = settings.get_tf_setting(timeframe, 'vol_ratio_threshold')
        range_threshold = settings.get_tf_setting(timeframe, 'price_range_threshold')

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

            # Check conditions with timeframe-specific thresholds
            cond_atr = atr_ratio < atr_threshold
            cond_vol = vol_ratio < vol_threshold
            cond_range = price_range < range_threshold
            cond_bbw = bbw < range_threshold * 2

            logger.debug(
                f'{timeframe} - Thresholds: atr={atr_threshold:.4f}, vol={vol_threshold:.2f}, '
                f'range={range_threshold:.4f}\n'
                f'{timeframe} - Values: atr={atr_ratio:.6f}, vol={vol_ratio:.2f}, '
                f'range={price_range:.6f}, bbw={bbw:.6f}\n'
                f'{timeframe} - Conditions: atr={cond_atr}, vol={cond_vol}, '
                f'range={cond_range}, bbw={cond_bbw}'
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

    def _is_confirmed_breakout(self, df: pd.DataFrame, level: float, direction: str,
                               timeframe: str) -> tuple[bool, str]:
        """
        Multifactor breakout confirmation

        Factors:
        1. Price stays above/below level for N bars
        2. Volume spike confirmation
        3. Strong candle bodies (not wicks)
        4. Distance from breakout level

        Returns:
            (is_confirmed, quality)
            quality: 'strong', 'medium', 'weak', 'rejected'
        """

        buffer = settings.get_tf_setting(timeframe, 'breakout_buffer')
        confirmation_bars = settings.get_tf_setting(timeframe, 'confirmation_bars')

        # Factor 1: Price confirmation
        if direction == "up":
            breakout_level = level * (1 + buffer)
            closes = df['close'].iloc[-confirmation_bars:]
            price_confirmed = all(closes > breakout_level)
            avg_close = closes.mean()
            distance = (avg_close - level) / level
        else:
            breakout_level = level * (1 - buffer)
            closes = df['close'].iloc[-confirmation_bars:]
            price_confirmed = all(closes < breakout_level)
            distance = (level - closes.mean()) / level

        # Factor 2: Volume confirmation (only need vol_spike)
        vol_spike, _, _ = self._calculate_volume_spike_dual_window(df, timeframe)

        # Factor 3: Body size (strong candles vs wicks)
        recent_candles = df.iloc[-confirmation_bars:]
        body_sizes = abs(recent_candles['close'] - recent_candles['open'])
        candle_ranges = recent_candles['high'] - recent_candles['low']
        avg_body_ratio = (body_sizes / candle_ranges).mean()
        strong_candles = avg_body_ratio > 0.6

        # Scoring system (max 4 points)
        score = sum([
            price_confirmed,
            vol_spike,
            strong_candles,
            distance > buffer * 2
        ])

        # Quality rating based on score
        if score >= 4:
            quality = 'strong'
            is_confirmed = True
        elif score >= 3:
            quality = 'medium'
            is_confirmed = True
        elif score >= 2:
            quality = 'weak'
            is_confirmed = True
        else:
            quality = 'rejected'
            is_confirmed = False

        logger.debug(
            f'Breakout confirmation: price={price_confirmed}, vol={vol_spike}, '
            f'candles={strong_candles}, distance={distance:.4f}, '
            f'score={score}/4, quality={quality}'
        )

        return is_confirmed, quality

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
                                 zone: Dict, vol_spike: bool, short_ratio: float,
                                 medium_ratio: float, consensus: Dict,
                                 breakout_quality: str = 'medium') -> str:
        """Format breakout message with all quality indicators"""

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
        setup = self._calculate_tp_sl(price, direction, zone)

        msg = (
            f"{emoji} *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🪙 *{symbol}*\n"
            f"⏱ {tf_meta['style']} ({tf_meta['label']})\n\n"
            f"💰 Giá: `{price:.6f}`\n"
            f"🎯 {level_name}: `{level:.6f}`\n"
            f"📈 Breakout: *{breakout_pct:.2f}%*\n\n"
            f"📦 Volume: *{short_ratio:.1f}x* / *{medium_ratio:.1f}x* "
        )

        if vol_spike:
            msg += "✅\n"

            # Breakout quality
            quality_emoji_breakout = {
                'strong': '🔥',
                'medium': '🟢',
                'weak': '🟡'
            }

            msg += (
                f"{quality_emoji_breakout.get(breakout_quality, '🟡')} "
                f"*Độ mạnh breakout: {breakout_quality.upper()}*\n"
            )

            # Multi-TF consensus
            if consensus['score'] > 0:
                quality_emoji = {
                    'excellent': '🟢',
                    'good': '🟢',
                    'medium': '🟡',
                    'weak': '⚠️'
                }

                msg += (
                    f"{quality_emoji[consensus['quality']]} "
                    f"*Đồng thuận: {consensus['score']}/{consensus['total']} TFs*"
                )

                if consensus['aligned_tfs']:
                    msg += f" _({', '.join(consensus['aligned_tfs'])})_"

                msg += "\n"

            msg += (
                f"━━━━━━━━━━━━━━━━━━\n"
                f"🎯 *GỢI Ý SETUP*\n\n"
                f"📍 Entry: `{setup['entry']:.6f}`\n"
                f"🛑 SL: `{setup['sl']:.6f}` _(-{setup['risk_pct']:.2f}%)_\n"
                f"🎯 TP: `{setup['tp']:.6f}` _(+{setup['reward_pct']:.2f}%)_\n"
                f"📊 R:R = *1:2*\n\n"
                f"⏱ {tf_meta['hold_time']} • Risk {tf_meta['risk']}\n\n"
            )

            # Quality-based recommendation
            if consensus['quality'] == 'excellent':
                msg += "🟢 _Setup uy tín CỰC CAO_\n"
            elif consensus['quality'] == 'good':
                msg += "🟢 _Setup uy tín cao_\n"
            elif consensus['quality'] == 'medium':
                msg += "🟡 _Setup tốt_\n"

            msg += "⚠️ _Tự kiểm tra trước khi vào_"
        else:
            msg += "⚠️\n\n"
            msg += "⚠️ *VOLUME KHÔNG XÁC NHẬN*"

        return msg

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

        # 1) Detect accumulation (now with symbol parameter)
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

        # 2) Check breakout if zone exists
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

        # Check breakout (now passing df)
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
        """Check for breakout with multifactor confirmation"""

        buffer = settings.get_tf_setting(timeframe, 'breakout_buffer')

        breakout_up = price > upper * (1 + buffer)
        breakout_down = price < lower * (1 - buffer)

        # Check breakout up
        if breakout_up and not zone.get('breakout_up', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):

            # Multi-factor confirmation
            is_confirmed, breakout_quality = self._is_confirmed_breakout(df, upper, "up", timeframe)

            if is_confirmed:
                # Get volume metrics for message
                vol_spike, short_ratio, medium_ratio = self._calculate_volume_spike_dual_window(df, timeframe)

                self._handle_breakout_up(
                    symbol, timeframe, price, zone,
                    vol_spike, short_ratio, medium_ratio,
                    breakout_quality  # Pass quality
                )

        # Check breakout down
        elif breakout_down and not zone.get('breakout_down', False) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):

            is_confirmed, breakout_quality = self._is_confirmed_breakout(df, lower, "down", timeframe)

            if is_confirmed:
                vol_spike, short_ratio, medium_ratio = self._calculate_volume_spike_dual_window(df, timeframe)

                self._handle_breakout_down(
                    symbol, timeframe, price, zone,
                    vol_spike, short_ratio, medium_ratio,
                    breakout_quality
                )

        # Clear zone after cooldown
        if (zone.get('breakout_up') or zone.get('breakout_down')) and \
                not self.was_recent(zone.get('last_breakout_notified'), settings.BREAKOUT_COOLDOWN_MIN):
            self.clear_zone(symbol, timeframe)

    def _handle_breakout_up(self, symbol: str, timeframe: str, price: float, zone: Dict,
                            vol_spike: bool, short_ratio: float, medium_ratio: float,
                            breakout_quality: str = 'medium'):  # Add breakout_quality
        """Handle breakout up with quality filtering"""

        consensus = self._check_higher_tf_consensus(symbol, "up", timeframe)

        # Combined quality check
        if consensus['quality'] in ['excellent', 'good', 'medium']:
            msg = self._format_breakout_message(
                symbol, timeframe, price, "up", zone,
                vol_spike, short_ratio, medium_ratio, consensus,
                breakout_quality  # Pass to message
            )

            logger.info(
                f"[BREAKOUT UP] {symbol} {timeframe}\n"
                f"  Breakout Quality: {breakout_quality}\n"
                f"  Volume: {short_ratio:.2f}x / {medium_ratio:.2f}x\n"
                f"  Consensus: {consensus['score']}/{consensus['total']} ({consensus['quality']})\n"
                f"  Aligned TFs: {', '.join(consensus['aligned_tfs']) or 'none'}"
            )

            self.notifier.send_message(msg)
            zone['breakout_up'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()
        else:
            logger.info(
                f"[BREAKOUT FILTERED] {symbol} {timeframe} - "
                f"Low consensus: {consensus['quality']}"
            )

    def _handle_breakout_down(self, symbol: str, timeframe: str, price: float, zone: Dict,
                              vol_spike: bool, short_ratio: float, medium_ratio: float,
                              breakout_quality: str = 'medium'):
        """Handle breakout down with quality filtering"""

        consensus = self._check_higher_tf_consensus(symbol, "down", timeframe)

        # Combined quality check
        if consensus['quality'] in ['excellent', 'good', 'medium']:
            msg = self._format_breakout_message(
                symbol, timeframe, price, "down", zone,
                vol_spike, short_ratio, medium_ratio, consensus,
                breakout_quality
            )

            logger.info(
                f"[BREAKOUT DOWN] {symbol} {timeframe}\n"
                f"  Breakout Quality: {breakout_quality}\n"
                f"  Volume: {short_ratio:.2f}x / {medium_ratio:.2f}x\n"
                f"  Consensus: {consensus['score']}/{consensus['total']} ({consensus['quality']})\n"
                f"  Aligned TFs: {', '.join(consensus['aligned_tfs']) or 'none'}"
            )

            self.notifier.send_message(msg)
            zone['breakout_down'] = True
            zone['last_breakout_notified'] = pd.Timestamp.utcnow()

        else:
            logger.info(
                f"[BREAKOUT FILTERED] {symbol} {timeframe} - "
                f"Low consensus: {consensus['quality']}"
            )
