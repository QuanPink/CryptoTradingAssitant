import pandas as pd

from src.models import AccumulationZone
from src.utils.logger import get_logger

logger = get_logger(__name__)


class BiasDetector:

    @staticmethod
    def higher_lows(df: pd.DataFrame, zone: AccumulationZone) -> int:
        """Check HL inside accumulation zone"""

        inside = df[(df["high"] >= zone.support) & (df["low"] <= zone.resistance)]
        if len(inside) < 5:
            return 0

        # simple HL detection
        lows = inside["low"].values
        x = range(len(lows))
        slope = (len(x) * sum(i * lows[i] for i in x) - sum(x) * sum(lows)) / \
                (len(x) * sum(i ** 2 for i in x) - sum(x) ** 2)

        return 1 if slope > 0 else 0

    @staticmethod
    def lower_highs(df: pd.DataFrame, zone: AccumulationZone) -> int:
        """Check LH inside accumulation zone"""
        inside = df[(df["high"] >= zone.support) & (df["low"] <= zone.resistance)]
        if len(inside) < 5:
            return 0

        highs = inside["high"].values
        lh_count = sum(highs[i] < highs[i - 1] for i in range(1, len(highs)))

        return 1 if lh_count >= 2 else 0

    @staticmethod
    def volume_imbalance(df: pd.DataFrame, zone: AccumulationZone) -> str:
        inside = df[(df["high"] >= zone.support) & (df["low"] <= zone.resistance)]
        if len(inside) < 10:
            return "neutral"

        up_vol = inside[inside["close"] > inside["open"]]["volume"].sum()
        down_vol = inside[inside["close"] < inside["open"]]["volume"].sum()

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
        if (lower_wick > wick_threshold and
                last["low"] <= zone.support * 1.005):  # 0.5% buffer
            return 1

        if (upper_wick > wick_threshold and
                last["high"] >= zone.resistance * 0.995):
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
