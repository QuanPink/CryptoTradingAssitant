import pandas as pd

from src.indicators.technical import TechnicalIndicators
from src.utils.logger import get_logger

logger = get_logger(__name__)


class AccumulationStrategy:

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.ind = TechnicalIndicators

    def compute_accumulation_score(self) -> pd.Series:
        self.df['atr'] = self.ind.atr(self.df)

        _, _, width = self.ind.bollinger_bands(self.df)
        self.df['bb_width'] = width

        self.df['bb_squeeze'] = self.ind.bb_squeeze(self.df['bb_width']).astype(int)
        self.df['atr_compress'] = self.ind.atr_compression(self.df['atr']).astype(int)
        self.df['ms_flat'] = self.ind.market_structure_flat(self.df).astype(int)
        self.df['vol_dec'] = self.ind.volume_decreasing(self.df).astype(int)

        # 🆕 DEBUG: Log từng condition
        logger.debug("Latest candle conditions:")
        logger.debug(f"  BB Squeeze: {self.df['bb_squeeze'].iloc[-1]} (width: {self.df['bb_width'].iloc[-1]:.4f})")
        logger.debug(f"  ATR Compress: {self.df['atr_compress'].iloc[-1]} (ATR: {self.df['atr'].iloc[-1]:.4f})")
        logger.debug(f"  Market Flat: {self.df['ms_flat'].iloc[-1]}")
        logger.debug(f"  Volume Dec: {self.df['vol_dec'].iloc[-1]}")

        bb = self.df['bb_squeeze'].astype(float)
        atr = self.df['atr_compress'].astype(float)
        ms = self.df['ms_flat'].astype(float)
        vol = self.df['vol_dec'].astype(float)

        self.df['accum_score'] = (
                0.35 * bb +
                0.25 * atr +
                0.20 * ms +
                0.20 * vol
        )

        logger.debug(f"  Final Score: {self.df['accum_score'].iloc[-1]:.2f}")

        return self.df['accum_score']

    def detect_accumulation(self, threshold: float = 0.6) -> pd.Series:
        score = self.compute_accumulation_score()
        return (score >= threshold)

    def detect(self, df: pd.DataFrame, threshold: float = 0.6):
        self.df = df

        # 🆕 Check minimum data
        if len(df) < 20:
            logger.warning(f"⚠️ Insufficient data: {len(df)} candles (need 20+)")
            return None

        is_accum = self.detect_accumulation(threshold)

        # Early exit
        if not is_accum.iloc[-1]:
            logger.debug("❌ Latest candle not in accumulation")
            return None

        # Kiểm tra consistency:
        recent_accum = is_accum.iloc[-20:].sum()
        if recent_accum < 15:
            logger.debug(f"❌ Insufficient accumulation density: {recent_accum}/20")
            return None

        logger.info(f"✅ Accumulation detected: {recent_accum}/20 candles")

        accum_data = self.df.iloc[-20:]

        from src.models import AccumulationZone

        zone = AccumulationZone(
            support=accum_data['low'].min(),
            resistance=accum_data['high'].max(),
            strength_score=self.df['accum_score'].iloc[-20:].mean() * 100
        )

        logger.info(f"Zone: {zone.support:.2f} - {zone.resistance:.2f}, Score: {zone.strength_score:.1f}")

        return zone
