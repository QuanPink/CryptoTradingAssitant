import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DataQualityChecker:
    @staticmethod
    def check_data_quality(df: pd.DataFrame, symbol: str, timeframe: str):
        """Check data quality"""
        if df is None or df.empty:
            logger.error(f"No data to check for {symbol} on {timeframe}")
            return

        logger.info(f"Data quality check for {symbol} on {timeframe}:")
        logger.info(f" - Total bars: {len(df)}")
        logger.info(f" - Date range: {df.index[0]} to {df.index[-1]}")
        logger.info(f" - Close price range: {df['close'].min():.2f} - {df['close'].max():.2f}")
        logger.info(f" - Volume range: {df['volume'].min():.2f} - {df['volume'].max():.2f}")
        logger.info(f" - Null values: {df.isnull().sum().sum()}")
