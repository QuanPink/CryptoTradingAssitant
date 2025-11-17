import pandas as pd

from src.models import AccumulationZone
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BiasDetector:

    @staticmethod
    def _inside_zone(df: pd.DataFrame, zone: AccumulationZone) -> pd.DataFrame:
        mask = (df["high"] >= zone.support) & (df["low"] <= zone.resistance)
        return df[mask]

    @staticmethod
    def higher_lows(df: pd.DataFrame, zone: AccumulationZone) -> int:
        """Check HL inside accumulation zone"""

        inside = BiasDetector._inside_zone(df, zone)
        if len(inside) < 5:
            return 0

        lows = inside["low"].rolling(3, center=True).min().dropna()
        if len(lows) < 3:
            return 0

        return int(lows.iloc[-1] > lows.iloc[0])

    @staticmethod
    def lower_highs(df: pd.DataFrame, zone: AccumulationZone) -> int:
        """Check LH inside accumulation zone"""
        inside = BiasDetector._inside_zone(df, zone)
        if len(inside) < 5:
            return 0

        highs = inside["high"].rolling(3, center=True).max().dropna()
        if len(highs) < 3:
            return 0

        return int(highs.iloc[-1] < highs.iloc[0])

    @staticmethod
    def volume_imbalance(df: pd.DataFrame, zone: AccumulationZone) -> str:
        inside = BiasDetector._inside_zone(df, zone)
        if len(inside) < 10:
            return "neutral"

        up_vol = inside[inside.close > inside.open].volume.mean() or 0
        down_vol = inside[inside.close < inside.open].volume.mean() or 0

        if up_vol > down_vol * 1.2:
            return "up"
        if down_vol > up_vol * 1.2:
            return "down"
        return "neutral"

    @staticmethod
    def absorption_wick(df: pd.DataFrame, zone: AccumulationZone) -> int:
        """Large wicks rejecting zone boundaries"""
        last = df.iloc[-1]

        # ATR làm threshold động
        atr = (df["high"] - df["low"]).tail(14).mean()

        upper_wick = last["high"] - max(last["open"], last["close"])
        lower_wick = min(last["open"], last["close"]) - last["low"]

        # Wick phải > 40% ATR
        wick_threshold = atr * 0.4

        # Check rejection at zone boundaries
        if lower_wick > wick_threshold and abs(last["low"] - zone.support) <= zone.support * 0.005:
            return 1

        if upper_wick > wick_threshold and abs(last["high"] - zone.resistance) <= zone.resistance * 0.005:
            return -1

        return 0

    def detect_bias(self, df: pd.DataFrame, zone: AccumulationZone):
        hl = self.higher_lows(df, zone)
        lh = self.lower_highs(df, zone)
        vol_bias = self.volume_imbalance(df, zone)
        absorption = self.absorption_wick(df, zone)

        logger.debug(f"Bias signals: HL={hl}, LH={lh}, Vol={vol_bias}, Absorption={absorption}")

        long_score = hl + (1 if vol_bias == "up" else 0) + (1 if absorption > 0 else 0)
        short_score = lh + (1 if vol_bias == "down" else 0) + (1 if absorption < 0 else 0)

        logger.debug(f"Scores: Long={long_score}, Short={short_score}")

        if long_score > short_score:
            logger.info(f"✅ LONG bias detected (score: {long_score * 10})")
            return "LONG", long_score * 10
        if short_score > long_score:
            logger.info(f"✅ SHORT bias detected (score: {short_score * 10})")
            return "SHORT", short_score * 10

        logger.debug("⚠️ NO_TRADE - no clear bias")
        return "NO_TRADE", 0
