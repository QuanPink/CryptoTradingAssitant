import time
from typing import Dict, Optional, Tuple, Any
import numpy as np
import pandas as pd

from config import ACCUMULATION_THRESHOLDS, SYMBOLS_CONFIG
from src.indicators import TechnicalIndicator
from src.models import AccumulationZone
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AccumulationService:
    def __init__(self):
        self.thresholds = ACCUMULATION_THRESHOLDS
        self.technical = TechnicalIndicator()

    def detect(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Optional[AccumulationZone]:
        """Detect accumulation and return zone"""
        logger.info(f"🔍 Checking accumulation on {timeframe}...")

        # Step 1: Enhanced range check
        range_passed, range_details = self._enhanced_range_check(df, timeframe, symbol)
        if not range_passed:
            return None

        # Step 2: Enhanced volume check
        volume_passed, volume_details = self._enhanced_volume_check(df, timeframe)
        if not volume_passed:
            return None

        # Step 3: Calculate zone boundaries
        zone_data = self._calculate_zone_boundaries(df, timeframe)

        # Step 4: Calculate comprehensive score
        score_result = self._calculate_accumulation_score(range_details, volume_details, zone_data, symbol)

        # Step 5: Apply quality threshold
        config = self.thresholds[timeframe]
        min_score = config.get('min_score', 65)
        if score_result['total_score'] < min_score:
            logger.info(f"❌ Score too low: {score_result['total_score']:.1f} < {min_score}")
            return None

        logger.info(f"✅ High quality accumulation: Score {score_result['total_score']:.1f}")

        # Step 6: Create immutable zone object
        return AccumulationZone(
            symbol=symbol,
            timeframe=timeframe,
            support=zone_data['support'],
            resistance=zone_data['resistance'],
            created_at=time.time(),
            strength_score=score_result['total_score'],
            strength_details=score_result
        )

    def _enhanced_range_check(self, df: pd.DataFrame, timeframe: str, symbol: str) -> Tuple[bool, dict]:
        """Enhanced range check with multiple factors"""
        config = ACCUMULATION_THRESHOLDS[timeframe]

        if len(df) < config['N_range'] + 5:
            return False, {}

        # Lấy data với buffer
        recent_data = df.iloc[-(config['N_range'] + 3):-1].copy()
        current_price = recent_data['close'].iloc[-1]

        # Analyze range quality
        body_highs = recent_data[['open', 'close']].max(axis=1)
        body_lows = recent_data[['open', 'close']].min(axis=1)
        body_high = body_highs.max()
        body_low = body_lows.min()
        body_range = body_high - body_low

        full_high = recent_data['high'].max()
        full_low = recent_data['low'].min()
        full_range = full_high - full_low

        # Decide body vs full range
        wick_size = full_range - body_range
        wick_ratio = (wick_size / body_range) if body_range > 0 else 0
        wick_tolerance = config.get('wick_tolerance_pct', 0.30)

        if wick_ratio <= wick_tolerance:
            use_high, use_low = full_high, full_low
            range_type = "FULL"
        else:
            use_high, use_low = body_high, body_low
            range_type = "BODY"

        actual_range = use_high - use_low
        range_pct = (actual_range / current_price) * 100

        # Factor 1: Tight range
        symbol_config = SYMBOLS_CONFIG.get(symbol, {})
        max_range_pct = symbol_config.get(timeframe, 1)
        tight_range = range_pct <= max_range_pct

        # Factor 2: High stability (low volatility)
        price_changes = recent_data['close'].pct_change().dropna()
        volatility = price_changes.std() * 100
        stability_score = max(0, 1 - (volatility * 10))
        high_stability = stability_score >= 0.7

        # Factor 3: Low wick ratio
        low_wick_ratio = wick_ratio <= wick_tolerance

        # Factor 4: Min candles in range
        min_candles_ratio = config.get('candles_in_range_ratio', 0.80)
        candles_in = self._count_candles_in_range(recent_data, use_high, use_low, timeframe)
        candles_ratio = candles_in / len(recent_data)
        min_candles_in_range = candles_ratio >= min_candles_ratio

        # Combine conditions (need 3/4)
        conditions = {
            'tight_range': tight_range,
            'high_stability': high_stability,
            'low_wick_ratio': low_wick_ratio,
            'min_candles_in_range': min_candles_in_range
        }

        passed_count = sum(conditions.values())
        is_valid = passed_count >= 3

        # Details for logging
        details = {
            'range_pct': range_pct,
            'max_allowed': max_range_pct,
            'stability_score': stability_score,
            'wick_ratio': wick_ratio,
            'candles_ratio': candles_ratio,
            'range_type': range_type,
            'conditions_passed': f"{passed_count}/4",
            'conditions': conditions
        }

        if is_valid:
            logger.info(
                f"✅ Range OK {symbol} {timeframe}: "
                f"{range_pct:.2f}% <= {max_range_pct:.2f}%, "
                f"stability: {stability_score:.2f}, "
                f"candles: {candles_in}/{len(recent_data)}, "
                f"passed: {passed_count}/4 ({range_type})"
            )
        else:
            logger.info(f"❌ Range FAIL {symbol} {timeframe}: passed: {passed_count}/4")

        return is_valid, details

    def _enhanced_volume_check(self, df: pd.DataFrame, timeframe: str) -> Tuple[bool, dict]:
        """Enhanced volume check with multi-period analysis"""
        config = self.thresholds[timeframe]

        if len(df) < config['N_volume_lookback'] + config['N_range'] + 10:
            return False, {}

        vol_data = df.iloc[:-1]
        current_range_vol = vol_data['volume'].tail(config['N_range']).mean()

        # Multi-period comparison
        immediate_vol = vol_data['volume'].tail(config['N_range'] + 5).head(5).mean()
        short_term_vol = vol_data['volume'].tail(config['N_volume_lookback'] + config['N_range']).head(
            config['N_volume_lookback']
        ).mean()

        # Calculate ratios
        threshold = config['volume_ratio_threshold']
        ratios = {
            'immediate': current_range_vol / immediate_vol if immediate_vol > 0 else 1,
            'short_term': current_range_vol / short_term_vol if short_term_vol > 0 else 1,
        }

        # Volume contraction
        contraction_signals = sum(ratio < threshold for ratio in ratios.values())
        volume_contracted = contraction_signals >= 1  # Need 1/2 periods

        # Volume consistency
        recent_volumes = vol_data['volume'].tail(config['N_range'])
        volume_std = recent_volumes.std()
        volume_mean = recent_volumes.mean()
        cv = (volume_std / volume_mean) if volume_mean > 0 else 999
        volume_consistent = cv < 0.6

        # Smart money detection
        volume_spikes = (recent_volumes > volume_mean * 2).sum()
        has_smart_money = volume_spikes >= 1

        # Combine conditions
        is_valid = volume_contracted and (volume_consistent or has_smart_money)

        details = {
            'current_volume': current_range_vol,
            'ratios': ratios,
            'contraction_signals': f"{contraction_signals}/2",
            'volume_contracted': volume_contracted,
            'volume_consistent': volume_consistent,
            'has_smart_money': has_smart_money
        }

        if is_valid:
            logger.info(
                f"✅ Volume OK: contraction {contraction_signals}/2, "
                f"consistent: {volume_consistent}, smart_money: {has_smart_money}"
            )
        else:
            logger.info(f"❌ Volume FAIL: contraction {contraction_signals}/2")

        return is_valid, details

    @staticmethod
    def _count_candles_in_range(df, range_high, range_low, timeframe):
        """Count candles with body in range"""
        config = ACCUMULATION_THRESHOLDS[timeframe]
        body_tolerance = config.get('body_exceed_tolerance', 0.03)

        count = 0
        range_size = range_high - range_low

        for _, candle in df.iterrows():
            body_high = max(candle['open'], candle['close'])
            body_low = min(candle['open'], candle['close'])

            # Allow small breach
            exceed_up = max(0, body_high - range_high)
            exceed_down = max(0, range_low - body_low)
            max_exceed = max(exceed_up, exceed_down)
            exceed_pct = max_exceed / range_size if range_size > 0 else 0

            if exceed_pct <= body_tolerance:
                count += 1

        return count

    def _calculate_zone_boundaries(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Calculate support/resistance levels"""
        config = self.thresholds[timeframe]
        recent_data = df.iloc[-(config['N_range'] + 1):-1]

        actual_high = recent_data['high'].max()
        actual_low = recent_data['low'].min()
        current_price = recent_data['close'].iloc[-1]

        # Add buffer to avoid false breakouts
        actual_range = actual_high - actual_low
        buffer_pct = config.get('zone_buffer_pct', 0.0)
        buffer = actual_range * buffer_pct

        support = actual_low - buffer
        resistance = actual_high + buffer

        return {
            'support': support,
            'resistance': resistance,
            'range_size_pct': ((resistance - support) / current_price) * 100,
            'current_price': current_price
        }

    def _calculate_accumulation_score(self, range_details: Dict, volume_details: Dict,
                                      zone_data: Dict, symbol: str) -> Dict[str, Any]:
        """Tính accumulation score đơn giản"""
        weights = {
            'range_quality': 0.40,
            'volume_analysis': 0.35,
            'price_stability': 0.25
        }

        # Range Quality Score
        range_score = self._calculate_range_score(range_details, symbol)

        # Volume Score
        volume_score = self._calculate_volume_score(volume_details)

        # Stability Score
        stability_score = range_details.get('stability_score', 0) * 100

        # Weighted total
        total_score = (
                range_score * weights['range_quality'] +
                volume_score * weights['volume_analysis'] +
                stability_score * weights['price_stability']
        )

        return {
            'total_score': round(total_score, 1),
            'components': {
                'range_quality': round(range_score, 1),
                'volume_analysis': round(volume_score, 1),
                'price_stability': round(stability_score, 1)
            }
        }

    def _calculate_range_score(self, range_details: Dict, symbol: str) -> float:
        """Tính range quality score"""
        range_pct = range_details['range_pct']
        max_allowed = range_details['max_allowed']
        candles_ratio = range_details['candles_ratio']

        # Base score based on tightness
        tightness_ratio = range_pct / max_allowed

        if tightness_ratio <= 0.6:
            base_score = 90
        elif tightness_ratio <= 0.8:
            base_score = 75
        elif tightness_ratio <= 1.0:
            base_score = 60
        else:
            base_score = 40

        # Bonus for high candles ratio
        if candles_ratio >= 0.90:
            base_score += 15
        elif candles_ratio >= 0.85:
            base_score += 10
        elif candles_ratio >= 0.80:
            base_score += 5

        return min(100, base_score)

    def _calculate_volume_score(self, volume_details: Dict) -> float:
        """Tính volume score"""
        score = 50  # Base score

        # Volume contraction
        contraction_signals = int(volume_details['contraction_signals'].split('/')[0])
        if contraction_signals == 2:
            score += 30
        elif contraction_signals == 1:
            score += 15

        # Volume consistency
        if volume_details['volume_consistent']:
            score += 10

        # Smart money
        if volume_details['has_smart_money']:
            score += 10

        return min(100, score)


class EnhancedAccumulationService(AccumulationService):
    """Extended version với trend analysis"""

    def __init__(self):
        super().__init__()
        from .trend import FastTrendAnalyzer
        self.trend_analyzer = FastTrendAnalyzer()

    def detect_with_trend(self, df: pd.DataFrame, symbol: str) -> Optional[Dict[str, Any]]:
        """Phát hiện accumulation kết hợp trend analysis"""
        # Accumulation detection
        accumulation_zone = self.detect(df, symbol)
        if not accumulation_zone:
            return None

        # Trend analysis
        trend_analysis = self.trend_analyzer.analyze_trend_fast(df)

        # Fast scoring
        bias_result = self._calculate_fast_bias(trend_analysis, accumulation_zone)

        return {
            'accumulation_zone': accumulation_zone,
            'trend_analysis': trend_analysis,
            'bias_result': bias_result,
            'signal': self._generate_signal(accumulation_zone, bias_result, df)
        }

    def _calculate_fast_bias(self, trend_data: Dict, accumulation_zone: AccumulationZone) -> Dict[str, Any]:
        """Tính bias nhanh"""
        score = 0
        signals = []

        price_data = trend_data['price_vs_ema']
        momentum = trend_data['momentum']
        volume = trend_data['volume_analysis']

        # EMA Alignment (30 points)
        alignment = price_data['ema_alignment']['alignment']
        if 'BULLISH' in alignment:
            score += 30
            signals.append(f"EMA {alignment}")
        elif 'BEARISH' in alignment:
            score -= 30
            signals.append(f"EMA {alignment}")

        # Price vs VWAP (20 points)
        if price_data['above_vwap']:
            score += 20
            signals.append("Price above VWAP")
        else:
            score -= 20
            signals.append("Price below VWAP")

        # Momentum (25 points)
        mom_score = self._score_momentum(momentum)
        score += mom_score
        if mom_score > 0:
            signals.append(f"Strong Momentum: {momentum['price_momentum']}")

        # Volume (15 points)
        vol_score = self._score_volume(volume, momentum['price_momentum'])
        score += vol_score

        # Immediate Bias (10 points)
        structure = trend_data['market_structure_fast']
        if structure['immediate_bias'] == 'BULLISH':
            score += 10
        elif structure['immediate_bias'] == 'BEARISH':
            score -= 10

        # Determine bias
        if score >= 25:
            bias = "LONG"
            confidence = min(85, 60 + score)
        elif score <= -25:
            bias = "SHORT"
            confidence = min(85, 60 + abs(score))
        else:
            bias = "NEUTRAL"
            confidence = max(30, 40 + abs(score) // 2)

        return {
            'bias': bias,
            'confidence': confidence,
            'score': score,
            'signals': signals
        }

    def _score_momentum(self, momentum: Dict) -> int:
        """Điểm momentum"""
        score = 0
        price_mom = momentum['price_momentum']

        if price_mom == "STRONG_UP":
            score += 15
        elif price_mom == "UP":
            score += 10
        elif price_mom == "STRONG_DOWN":
            score -= 15
        elif price_mom == "DOWN":
            score -= 10

        if momentum['rsi_trend'] == "BULLISH":
            score += 5
        elif momentum['rsi_trend'] == "BEARISH":
            score -= 5

        return score

    def _score_volume(self, volume: Dict, price_momentum: str) -> int:
        """Điểm volume"""
        if volume['is_spike']:
            if price_momentum in ["STRONG_UP", "UP"] and volume['volume_trend'] == 'INCREASING':
                return 15
            elif price_momentum in ["STRONG_DOWN", "DOWN"] and volume['volume_trend'] == 'INCREASING':
                return -15

        if volume['volume_trend'] == 'INCREASING':
            if price_momentum in ["STRONG_UP", "UP"]:
                return 10
            elif price_momentum in ["STRONG_DOWN", "DOWN"]:
                return -10

        return 0

    def _generate_signal(self, zone: AccumulationZone, bias_result: Dict, df: pd.DataFrame) -> Dict[str, Any]:
        """Tạo tín hiệu giao dịch"""
        current_price = df['close'].iloc[-1]

        if bias_result['confidence'] < 65:
            return {'signal': 'NO_TRADE', 'reason': 'Low confidence'}

        if bias_result['bias'] == 'LONG':
            return {
                'signal': 'LONG',
                'entry_price': current_price,
                'stop_loss': zone.support * 0.997,
                'take_profit': zone.resistance * 1.008,
                'confidence': bias_result['confidence'],
                'signals': bias_result['signals']
            }
        elif bias_result['bias'] == 'SHORT':
            return {
                'signal': 'SHORT',
                'entry_price': current_price,
                'stop_loss': zone.resistance * 1.003,
                'take_profit': zone.support * 0.992,
                'confidence': bias_result['confidence'],
                'signals': bias_result['signals']
            }
        else:
            return {'signal': 'NO_TRADE', 'reason': 'Neutral bias'}