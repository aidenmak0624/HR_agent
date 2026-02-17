"""Simple in-memory response caching middleware for Flask applications.

Caches GET endpoint responses with configurable TTL and eviction policy.
Cache key = path + query string + user_id
Default: 30s for metrics, 60s for employee list, max 200 entries
"""

import hashlib
import logging
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

from flask import g, request

logger = logging.getLogger(__name__)


class CacheEntry:
    """Single cache entry with TTL tracking."""

    def __init__(self, data: Any, ttl: int):
        """Initialize cache entry.

        Args:
            data: Data to cache
            ttl: Time to live in seconds
        """
        self.data = data
        self.ttl = ttl
        self.created_at = time.time()

    def is_expired(self) -> bool:
        """Check if entry has expired.

        Returns:
            True if expired, False otherwise
        """
        return (time.time() - self.created_at) > self.ttl

    def get(self) -> Optional[Any]:
        """Get cached data if not expired.

        Returns:
            Cached data if not expired, None if expired
        """
        if self.is_expired():
            return None
        return self.data


class SimpleCache:
    """Simple in-memory cache with LRU eviction."""

    def __init__(self, max_entries: int = 200):
        """Initialize cache.

        Args:
            max_entries: Maximum number of cache entries (default: 200)
        """
        self.max_entries = max_entries
        self._store: Dict[str, CacheEntry] = {}
        self._access_order: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        if key not in self._store:
            return None

        entry = self._store[key]
        if entry.is_expired():
            del self._store[key]
            if key in self._access_order:
                del self._access_order[key]
            return None

        # Update access time for LRU tracking
        self._access_order[key] = time.time()
        return entry.data

    def set(self, key: str, data: Any, ttl: int = 60) -> None:
        """Set value in cache.

        Args:
            key: Cache key
            data: Data to cache
            ttl: Time to live in seconds (default: 60)
        """
        # If cache is full, evict least recently used entry
        if len(self._store) >= self.max_entries and key not in self._store:
            self._evict_oldest()

        self._store[key] = CacheEntry(data, ttl)
        self._access_order[key] = time.time()
        logger.debug(f"Cache set: {key} (ttl={ttl}s, size={len(self._store)})")

    def clear(self) -> None:
        """Clear all cache entries."""
        self._store.clear()
        self._access_order.clear()
        logger.debug("Cache cleared")

    def _evict_oldest(self) -> None:
        """Evict the least recently used entry."""
        if not self._access_order:
            return

        # Find oldest accessed key
        oldest_key = min(self._access_order, key=self._access_order.get)
        del self._store[oldest_key]
        del self._access_order[oldest_key]
        logger.debug(f"Cache evicted (LRU): {oldest_key}")

    def get_stats(self) -> Dict[str, int]:
        """Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "size": len(self._store),
            "max_entries": self.max_entries,
        }


# Global cache instance
_default_cache = SimpleCache(max_entries=200)


def get_cache() -> SimpleCache:
    """Get the global cache instance.

    Returns:
        The global SimpleCache instance
    """
    return _default_cache


def _make_cache_key(path: str, query_string: str, user_id: str) -> str:
    """Generate cache key from path, query string, and user_id.

    Args:
        path: Request path
        query_string: Query string
        user_id: User ID

    Returns:
        Cache key
    """
    key_parts = f"{path}#{query_string}#{user_id}"
    # Use hash for consistent key length
    return hashlib.md5(key_parts.encode()).hexdigest()


def cached(ttl: int = 60) -> Callable:
    """Decorator to cache GET endpoint responses.

    Args:
        ttl: Time to live in seconds (default: 60)

    Returns:
        Decorator function
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs) -> Any:
            # Only cache GET requests
            if request.method != "GET":
                return f(*args, **kwargs)

            # Build cache key
            path = request.path
            query_string = request.query_string.decode("utf-8") if request.query_string else ""
            user_id = g.get("user_context", {}).get("user_id", "anonymous")

            cache_key = _make_cache_key(path, query_string, user_id)

            # Try to get from cache
            cache = get_cache()
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached_response

            # Not cached, call the actual function
            response = f(*args, **kwargs)

            # Cache the response
            cache.set(cache_key, response, ttl=ttl)
            logger.debug(f"Cache miss and set: {cache_key} (ttl={ttl}s)")

            return response

        return decorated_function

    return decorator


def clear_cache() -> None:
    """Clear all cache entries."""
    _default_cache.clear()


def get_cache_stats() -> Dict[str, int]:
    """Get cache statistics.

    Returns:
        Dictionary with cache stats
    """
    return _default_cache.get_stats()
