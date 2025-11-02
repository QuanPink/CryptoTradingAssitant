"""Zone lifecycle management"""
from typing import Dict, Optional

import pandas as pd

from config.setting import settings
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ZoneManager:
    """Manages accumulation zones lifecycle"""

    def __init__(self):
        self.zones: Dict[str, Dict[str, Dict]] = {}

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
            'range_pct': zone.get('range_pct', zone['width']),
            'vol_ratio': zone.get('vol_ratio', 1.0),
            'duration_hours': zone['duration_hours'],
            'quality': zone.get('quality', 'fair')
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

    def get_zone(self, symbol: str, timeframe: str) -> Optional[Dict]:
        """Get zone for symbol and timeframe"""
        return self.zones.get(symbol, {}).get(timeframe)

    def has_zone(self, symbol: str, timeframe: str) -> bool:
        """Check if zone exists"""
        return symbol in self.zones and timeframe in self.zones[symbol]

    @staticmethod
    def is_expired(zone: Dict, hours: int) -> bool:
        """Check if zone is expired"""
        if 'detected_at' not in zone:
            return True
        return (pd.Timestamp.utcnow() - zone['detected_at']) > pd.Timedelta(hours=hours)

    def cleanup_old_zones(self, hours: int = None) -> int:
        """Clean up old zones to prevent memory leak"""
        if hours is None:
            hours = settings.ZONE_EXPIRE_HOURS

        cutoff = pd.Timestamp.utcnow() - pd.Timedelta(hours=hours)
        zones_before = sum(len(tfs) for tfs in self.zones.values())

        # Collect expired zones to remove
        zones_to_remove = []

        for symbol, timeframes in self.zones.items():
            for tf, zone in timeframes.items():
                if zone['detected_at'] < cutoff:
                    zones_to_remove.append((symbol, tf))
                    logger.debug(
                        f"Removing expired zone: {symbol} {tf} "
                        f"(age: {(pd.Timestamp.utcnow() - zone['detected_at']).total_seconds() / 3600:.1f}h)"
                    )

        # Remove expired zones
        removed_count = len(zones_to_remove)
        for symbol, tf in zones_to_remove:
            del self.zones[symbol][tf]

        # Collect and remove empty symbols
        empty_symbols = [s for s in self.zones.keys() if not self.zones[s]]
        for symbol in empty_symbols:
            del self.zones[symbol]

        zones_after = sum(len(tfs) for tfs in self.zones.values())

        if removed_count > 0:
            logger.info(
                f"🧹 Cleanup: Removed {removed_count} zones ({zones_before} → {zones_after})"
            )

        return removed_count

    def get_total_zones(self) -> int:
        """Get total number of active zones"""
        return sum(len(tfs) for tfs in self.zones.values())

    @staticmethod
    def was_recent(ts: Optional[pd.Timestamp], minutes: int) -> bool:
        """Check if timestamp was within last N minutes"""
        if ts is None:
            return False
        return (pd.Timestamp.utcnow() - ts).total_seconds() < minutes * 60

    @staticmethod
    def is_zone_significantly_different(zone_info: Dict, existing_zone: Dict) -> bool:
        """Check if new zone is significantly different from existing one"""
        upper_diff = abs(zone_info['upper'] - existing_zone['upper']) / existing_zone['upper']
        lower_diff = abs(zone_info['lower'] - existing_zone['lower']) / existing_zone['lower']

        # Require at least 0.5% change in either bound to consider it a new zone
        return upper_diff > 0.005 or lower_diff > 0.005
