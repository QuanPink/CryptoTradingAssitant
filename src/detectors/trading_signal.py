from src.detectors.accumulation import AccumulationStrategy
from src.detectors.bias import BiasDetector
from src.detectors.entry import EntryBuilder
from src.utils.logger import get_logger

logger = get_logger(__name__)


class TradingSignalBuilder:

    def __init__(self):
        self.bias_detector = BiasDetector()
        self.entry_builder = EntryBuilder()

    def generate_signal(self, df):
        # Check data đủ
        if len(df) < 50:
            logger.warning("⚠️ Insufficient data")
            return None

        accum_detector = AccumulationStrategy(df)
        zone = accum_detector.detect(df)

        if zone is None:
            logger.debug("No accumulation detected")
            return None

        bias, bias_conf = self.bias_detector.detect_bias(df, zone)

        if bias == "NO_TRADE":
            logger.info("⚠️ Accumulation found but no clear bias")
            return {
                "accumulation_zone": zone,
                "signal": {"signal": "NO_TRADE", "confidence": 0}
            }

        trade = self.entry_builder.build_trade_plan(df, zone, bias)

        if trade is None:
            logger.warning("❌ Cannot build trade plan")
            return None

        confidence = (bias_conf * 0.4 + zone.strength_score * 0.6)

        logger.info(f"🎯 Signal: {bias} | Entry: {trade['entry']:.2f} | Conf: {confidence:.1f}")

        return {
            "symbol": df.attrs.get("symbol", "UNKNOWN"),  # 🆕 Add symbol
            "timeframe": df.attrs.get("timeframe", "UNKNOWN"),
            "accumulation_zone": zone,
            "signal": {
                "signal": bias,
                **trade,
                "confidence": confidence,
                "timestamp": df.index[-1]
            }
        }
