"""Redis cache module with graceful fallback."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

try:
    import redis
    from redis.asyncio import Redis as AsyncRedis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheManager:
    """Redis cache manager with fallback for unavailable Redis.

    Provides caching functionality with automatic fallback when Redis is unavailable.
    All methods return None or False gracefully if Redis is not available.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize cache manager.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self.client: Optional[redis.Redis] = None
        self.async_client: Optional[AsyncRedis] = None
        self._initialized = False
        self._connect()

    def _connect(self) -> None:
        """Establish Redis connection with graceful fallback."""
        if not REDIS_AVAILABLE:
            logger.warning("Redis not available, cache operations will be disabled")
            self._initialized = False
            return

        try:
            # Parse redis URL and create connection
            self.client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            # Test connection
            self.client.ping()
            logger.info("Connected to Redis successfully")
            self._initialized = True
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Cache operations disabled.")
            self.client = None
            self._initialized = False

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or Redis unavailable
        """
        if not self._initialized or not self.client:
            return None

        try:
            value = self.client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.warning(f"Cache get failed for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise or if Redis unavailable
        """
        if not self._initialized or not self.client:
            return False

        try:
            self.client.setex(key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.warning(f"Cache set failed for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key

        Returns:
            True if successful, False otherwise or if Redis unavailable
        """
        if not self._initialized or not self.client:
            return False

        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete failed for key {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if key exists, False otherwise or if Redis unavailable
        """
        if not self._initialized or not self.client:
            return False

        try:
            return self.client.exists(key) > 0
        except Exception as e:
            logger.warning(f"Cache exists check failed for key {key}: {e}")
            return False

    def get_or_set(self, key: str, setter_fn, ttl: int = 3600) -> Optional[Any]:
        """Get value from cache or compute and set it.

        Args:
            key: Cache key
            setter_fn: Callable that returns value if not in cache
            ttl: Time to live in seconds

        Returns:
            Cached or computed value, None if both cache and setter fail
        """
        # Try to get from cache
        cached_value = self.get(key)
        if cached_value is not None:
            return cached_value

        # Compute value
        try:
            value = setter_fn()
            if value is not None:
                self.set(key, value, ttl)
            return value
        except Exception as e:
            logger.warning(f"Cache get_or_set failed for key {key}: {e}")
            return None

    # Session store methods
    def store_session(self, session_id: str, session_data: dict, ttl: int = 86400) -> bool:
        """Store session data.

        Args:
            session_id: Session ID
            session_data: Session data dictionary
            ttl: Time to live in seconds (default: 24 hours)

        Returns:
            True if successful, False otherwise
        """
        return self.set(f"session:{session_id}", session_data, ttl)

    def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve session data.

        Args:
            session_id: Session ID

        Returns:
            Session data dictionary or None if not found
        """
        return self.get(f"session:{session_id}")

    def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session.

        Args:
            session_id: Session ID

        Returns:
            True if successful, False otherwise
        """
        return self.delete(f"session:{session_id}")

    # Rate limiter methods
    def check_rate_limit(self, user_id: str, limit: int = 60, window: int = 60) -> tuple[bool, int]:
        """Check if user is within rate limit.

        Args:
            user_id: User ID
            limit: Maximum requests allowed
            window: Time window in seconds

        Returns:
            Tuple of (allowed: bool, remaining: int)
        """
        if not self._initialized or not self.client:
            # Allow requests if Redis unavailable
            return True, limit

        try:
            key = f"rate_limit:{user_id}"
            current = self.client.incr(key)

            if current == 1:
                # First request in window, set expiration
                self.client.expire(key, window)

            allowed = current <= limit
            remaining = max(0, limit - current)
            return allowed, remaining
        except Exception as e:
            logger.warning(f"Rate limit check failed for user {user_id}: {e}")
            # Allow if check fails
            return True, limit

    # HRIS cache methods
    def cache_hris_response(self, employee_id: str, hris_data: dict) -> bool:
        """Cache HRIS API response.

        Args:
            employee_id: Employee ID
            hris_data: HRIS response data

        Returns:
            True if successful, False otherwise
        """
        return self.set(f"hris:{employee_id}", hris_data, ttl=300)  # 5 min TTL

    def get_hris_cache(self, employee_id: str) -> Optional[dict]:
        """Retrieve cached HRIS data.

        Args:
            employee_id: Employee ID

        Returns:
            Cached HRIS data or None if not found/expired
        """
        return self.get(f"hris:{employee_id}")

    # Response cache methods
    def cache_response(self, query_hash: str, role: str, response: dict, ttl: int = 3600) -> bool:
        """Cache agent response.

        Args:
            query_hash: Hash of the query
            role: User role
            response: Response data
            ttl: Time to live in seconds

        Returns:
            True if successful, False otherwise
        """
        cache_key = f"response:{role}:{query_hash}"
        return self.set(cache_key, response, ttl)

    def get_cached_response(self, query_hash: str, role: str) -> Optional[dict]:
        """Retrieve cached response.

        Args:
            query_hash: Hash of the query
            role: User role

        Returns:
            Cached response or None if not found/expired
        """
        cache_key = f"response:{role}:{query_hash}"
        return self.get(cache_key)

    def health_check(self) -> bool:
        """Check Redis connection health.

        Returns:
            True if Redis is healthy, False otherwise
        """
        if not REDIS_AVAILABLE:
            return False

        try:
            if self.client:
                self.client.ping()
                return True
            return False
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False


# Global cache manager instance
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(redis_url: str = "redis://localhost:6379/0") -> CacheManager:
    """Get or create the global cache manager instance.

    Args:
        redis_url: Redis connection URL

    Returns:
        CacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager(redis_url)
    return _cache_manager
