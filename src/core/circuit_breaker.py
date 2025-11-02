"""Circuit breaker for handling symbol failures"""
from typing import Dict

import pandas as pd

from config.setting import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class CircuitBreaker:
    """Tracks symbol failures and implements circuit breaker pattern"""

    def __init__(self):
        self.failed_symbols: Dict[str, Dict] = {}

    def should_skip(self, symbol: str) -> bool:
        """Check if symbol should be skipped"""
        if symbol not in self.failed_symbols:
            return False

        failure_info = self.failed_symbols[symbol]

        if 'timeout_until' in failure_info:
            if pd.Timestamp.utcnow() < failure_info['timeout_until']:
                return True
            else:
                del self.failed_symbols[symbol]
                logger.info(f"Circuit breaker reset for {symbol}")
                return False

        return False

    def record_failure(self, symbol: str):
        """Record failure and trigger circuit breaker if needed"""
        now = pd.Timestamp.utcnow()

        if symbol not in self.failed_symbols:
            self.failed_symbols[symbol] = {'count': 1, 'last_failure': now}
        else:
            self.failed_symbols[symbol]['count'] += 1
            self.failed_symbols[symbol]['last_failure'] = now

        count = self.failed_symbols[symbol]['count']
        max_failures = settings.CIRCUIT_BREAKER_FAILURES

        if count >= max_failures:
            timeout_min = settings.CIRCUIT_BREAKER_TIMEOUT_MIN
            timeout_until = now + pd.Timedelta(minutes=timeout_min)
            self.failed_symbols[symbol]['timeout_until'] = timeout_until

            logger.warning(
                f"⚠️ Circuit breaker triggered for {symbol} "
                f"({count} failures). Timeout until {timeout_until.strftime('%H:%M:%S')}"
            )

    def record_success(self, symbol: str):
        """Clear failure count on success"""
        if symbol in self.failed_symbols:
            del self.failed_symbols[symbol]
            logger.debug(f"✅ Cleared failure record for {symbol}")

    def get_failed_count(self) -> int:
        """Get number of failed symbols"""
        return len(self.failed_symbols)
