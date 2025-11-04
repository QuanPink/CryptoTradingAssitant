import time
from typing import Any, Dict, Optional

from cachetools import TTLCache


class MemoryCache:
    """
    Simple in-memory cache manager with TTL support
    Thread-safe caching for API responses and calculations
    """

    def __init__(self, maxsize: int = 1000):
        self._caches: Dict[str, TTLCache] = {}
        self.maxsize = maxsize

    def get_cache(self, name: str, ttl: int) -> TTLCache:
        """Get or create a named cache with specific TTL"""
        if name not in self._caches:
            self._caches[name] = TTLCache(maxsize=self.maxsize, ttl=ttl)
        return self._caches[name]

    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get value from cache by name and key"""
        cache = self._caches.get(cache_name)
        if cache is None:
            return None
        return cache.get(key)

    def set(self, cache_name: str, key: str, value: Any, ttl: int = 300):
        """Set value in cache with specific TTL"""
        cache = self.get_cache(cache_name, ttl)
        cache[key] = value

    def delete(self, cache_name: str, key: str):
        """Delete specific key from cache"""
        cache = self._caches.get(cache_name)
        if cache and key in cache:
            del cache[key]

    def clear(self, cache_name: str):
        """Clear entire named cache"""
        if cache_name in self._caches:
            self._caches[cache_name].clear()

    def clear_all(self):
        """Clear all caches"""
        for cache in self._caches.values():
            cache.clear()


class TTLDict:
    """
    Dictionary with automatic TTL-based expiry
    Used for state management with auto-cleanup
    """

    def __init__(self, ttl: int):
        """
        Args:
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl
        self._data: Dict[str, tuple[Any, float]] = {}

    def __setitem__(self, key: str, value: Any):
        """Set item with current timestamp"""
        self._data[key] = (value, time.time())

    def __getitem__(self, key: str) -> Any:
        """Get item if not expired, raise KeyError if expired or missing"""
        if key not in self._data:
            raise KeyError(key)

        value, timestamp = self._data[key]
        if time.time() - timestamp > self.ttl:
            del self._data[key]
            raise KeyError(key)

        return value

    def __contains__(self, key: str) -> bool:
        """Check if key exists and is not expired"""
        try:
            _ = self[key]  # Trigger expiry check
            return True
        except KeyError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get value with default if not found or expired"""
        try:
            return self[key]
        except KeyError:
            return default

    def items(self):
        """
        Iterate over non-expired items
        WARNING: Returns a copy to avoid modification during iteration
        """
        self.cleanup()
        return dict(self._data).items()

    def cleanup(self):
        """Remove all expired items"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._data.items()
            if current_time - timestamp > self.ttl
        ]
        for key in expired_keys:
            del self._data[key]

    def __len__(self) -> int:
        """Get count of non-expired items"""
        self.cleanup()
        return len(self._data)

    def clear(self):
        """Clear all items"""
        self._data.clear()
