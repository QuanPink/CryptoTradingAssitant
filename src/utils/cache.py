import time
from threading import Lock
from typing import Any, Dict, Optional

from cachetools import TTLCache


class MemoryCache:
    """
    Simple in-memory cache manager with TTL support
    Thread-safe caching for API responses and calculations
    """

    def __init__(self, maxsize: int = 100):
        self._caches: Dict[str, TTLCache] = {}
        self.maxsize = maxsize
        self._default_ttls: Dict[str, int] = {}

    def get_cache(self, name: str, ttl: int) -> TTLCache:
        """Get or create a named cache with specific TTL"""
        if name not in self._caches:
            self._caches[name] = TTLCache(maxsize=self.maxsize, ttl=ttl)
            self._default_ttls[name] = ttl
        return self._caches[name]

    def get(self, cache_name: str, key: str) -> Optional[Any]:
        """Get value from cache by name and key"""
        cache = self._caches.get(cache_name)
        if cache is None:
            return None
        return cache.get(key)

    def set(self, cache_name: str, key: str, value: Any, ttl: int = 86400):
        """Set value in cache with specific TTL"""
        cache_ttl = ttl if ttl else self._default_ttls.get(cache_name, 86400)
        cache = self.get_cache(cache_name, cache_ttl)
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
    Thread-safe version with Lock
    """

    def __init__(self, ttl: int):
        """
        Args:
            ttl: Time-to-live in seconds
        """
        self.ttl = ttl
        self._data: Dict[str, tuple[Any, float]] = {}
        self._lock = Lock()  # ✅

    def __setitem__(self, key: str, value: Any):
        """Set item with current timestamp - THREAD SAFE"""
        with self._lock:  # ✅
            self._data[key] = (value, time.time())

    def __getitem__(self, key: str) -> Any:
        """Get item if not expired, raise KeyError if expired or missing - THREAD SAFE"""
        with self._lock:  # ✅
            if key not in self._data:
                raise KeyError(key)

            value, timestamp = self._data[key]
            if time.time() - timestamp > self.ttl:
                del self._data[key]
                raise KeyError(key)

            return value

    def __contains__(self, key: str) -> bool:
        """Check if key exists and is not expired - THREAD SAFE"""
        try:
            _ = self[key]  # Trigger expiry check (đã có lock bên trong)
            return True
        except KeyError:
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get value with default if not found or expired - THREAD SAFE"""
        try:
            return self[key]  # Đã có lock bên trong
        except KeyError:
            return default

    def items(self):
        """
        Iterate over non-expired items - THREAD SAFE
        WARNING: Returns a copy to avoid modification during iteration
        """
        with self._lock:  # ✅
            self.cleanup()
            # Return copy để tránh modification during iteration
            return list(self._data.items())

    def cleanup(self):
        """Remove all expired items - MUST BE CALLED WITH LOCK"""
        # ⚠️ Method này được gọi từ items() đã có lock
        # KHÔNG thêm lock ở đây để tránh deadlock
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in self._data.items()
            if current_time - timestamp > self.ttl
        ]
        for key in expired_keys:
            del self._data[key]

    def __len__(self) -> int:
        """Get count of non-expired items - THREAD SAFE"""
        with self._lock:  # ✅
            self.cleanup()
            return len(self._data)

    def clear(self):
        """Clear all items - THREAD SAFE"""
        with self._lock:  # ✅
            self._data.clear()
