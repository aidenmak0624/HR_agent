"""Query result caching strategy with multiple eviction policies."""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheStrategy(str, Enum):
    """Cache eviction strategy enumeration."""
    LRU = "lru"
    TTL = "ttl"
    LFU = "lfu"
    WRITE_THROUGH = "write_through"
    WRITE_BEHIND = "write_behind"


class CacheEntry(BaseModel):
    """A single cache entry."""
    key: str = Field(..., description="Cache key")
    value: Any = Field(..., description="Cached value")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    expires_at: Optional[datetime] = Field(default=None, description="Expiration timestamp")
    access_count: int = Field(default=0, ge=0, description="Number of accesses")
    last_accessed: datetime = Field(default_factory=datetime.utcnow, description="Last access time")
    size_bytes: int = Field(default=0, ge=0, description="Estimated size in bytes")
    tags: List[str] = Field(default_factory=list, description="Associated tags for invalidation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "key": "employee:12345:profile",
                "value": {"id": 12345, "name": "John Doe"},
                "created_at": "2025-02-06T10:00:00Z",
                "expires_at": "2025-02-06T10:05:00Z",
                "access_count": 5,
                "last_accessed": "2025-02-06T10:04:00Z",
                "size_bytes": 256,
                "tags": ["employee", "profile"]
            }
        }
    )


class CacheConfig(BaseModel):
    """Configuration for query cache service."""
    strategy: CacheStrategy = Field(default=CacheStrategy.LRU, description="Eviction strategy")
    max_entries: int = Field(default=1000, ge=10, description="Maximum cache entries")
    default_ttl_seconds: int = Field(default=300, ge=10, description="Default TTL in seconds")
    max_memory_mb: int = Field(default=256, ge=10, description="Maximum memory usage in MB")
    eviction_policy: str = Field(default="lru", description="Eviction policy name")
    redis_enabled: bool = Field(default=False, description="Enable Redis backend")
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")
    namespace: str = Field(default="hr_agent", description="Cache namespace prefix")
    warmup_enabled: bool = Field(default=False, description="Enable cache warmup")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "strategy": "lru",
                "max_entries": 1000,
                "default_ttl_seconds": 300,
                "max_memory_mb": 256,
                "eviction_policy": "lru",
                "redis_enabled": False,
                "redis_url": "redis://localhost:6379/0",
                "namespace": "hr_agent",
                "warmup_enabled": False
            }
        }
    )


class CacheStats(BaseModel):
    """Statistics for cache service."""
    total_hits: int = Field(default=0, ge=0, description="Total cache hits")
    total_misses: int = Field(default=0, ge=0, description="Total cache misses")
    hit_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Hit rate ratio")
    total_entries: int = Field(default=0, ge=0, description="Current entries in cache")
    memory_used_mb: float = Field(default=0.0, ge=0.0, description="Memory used in MB")
    evictions_count: int = Field(default=0, ge=0, description="Total evictions")
    avg_response_time_ms: float = Field(default=0.0, ge=0.0, description="Average response time")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_hits": 1500,
                "total_misses": 300,
                "hit_rate": 0.833,
                "total_entries": 425,
                "memory_used_mb": 128.5,
                "evictions_count": 125,
                "avg_response_time_ms": 2.3
            }
        }
    )


class QueryCacheService:
    """Service for caching query results with multiple strategies."""

    def __init__(self, config: CacheConfig):
        """Initialize query cache service.

        Args:
            config: Cache configuration
        """
        self.config = config
        self._local_cache: Dict[str, CacheEntry] = {}
        self._redis_client: Optional[redis.Redis] = None
        self._total_hits: int = 0
        self._total_misses: int = 0
        self._total_evictions: int = 0
        self._response_times: List[float] = []
        self._initialized = False

        self._initialize_redis()
        self._initialized = True
        logger.info(f"Initialized QueryCacheService with strategy {config.strategy.value}")

    def _initialize_redis(self) -> None:
        """Initialize Redis connection if enabled."""
        if not self.config.redis_enabled:
            return

        if not REDIS_AVAILABLE:
            logger.warning("Redis requested but not available, using local cache only")
            return

        try:
            url = self.config.redis_url or "redis://localhost:6379/0"
            self._redis_client = redis.from_url(
                url,
                decode_responses=True,
                socket_keepalive=True,
                health_check_interval=30
            )
            self._redis_client.ping()
            logger.info("Connected to Redis for cache backend")
        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache: {e}")
            self._redis_client = None

    def _build_key(self, key: str, namespace: Optional[str] = None) -> str:
        """Build namespaced cache key.

        Args:
            key: Cache key
            namespace: Optional namespace override

        Returns:
            Namespaced key
        """
        ns = namespace or self.config.namespace
        return f"{ns}:{key}"

    def _calculate_size(self, value: Any) -> int:
        """Calculate approximate size of value in bytes.

        Args:
            value: Value to measure

        Returns:
            Approximate size in bytes
        """
        try:
            if isinstance(value, str):
                return len(value.encode('utf-8'))
            elif isinstance(value, (dict, list)):
                return len(json.dumps(value).encode('utf-8'))
            elif isinstance(value, bytes):
                return len(value)
            else:
                return len(str(value).encode('utf-8'))
        except Exception as e:
            logger.debug(f"Error calculating value size: {e}")
            return 0

    def get(self, key: str, namespace: Optional[str] = None) -> Optional[Any]:
        """Get value from cache.

        Args:
            key: Cache key
            namespace: Optional namespace override

        Returns:
            Cached value or None if not found
        """
        response_start = time.time()

        try:
            full_key = self._build_key(key, namespace)

            # Try Redis first if available
            if self._redis_client:
                try:
                    value_json = self._redis_client.get(full_key)
                    if value_json:
                        try:
                            entry_data = json.loads(value_json)
                            entry = CacheEntry(**entry_data)

                            # Check expiration
                            if entry.expires_at and entry.expires_at < datetime.utcnow():
                                self._redis_client.delete(full_key)
                                self._total_misses += 1
                                return None

                            entry.access_count += 1
                            entry.last_accessed = datetime.utcnow()
                            self._redis_client.setex(
                                full_key,
                                int((entry.expires_at - datetime.utcnow()).total_seconds()) if entry.expires_at else self.config.default_ttl_seconds,
                                json.dumps(entry.model_dump(default=str))
                            )

                            self._total_hits += 1
                            response_time = (time.time() - response_start) * 1000
                            self._response_times.append(response_time)
                            logger.debug(f"Cache hit from Redis: {key}")
                            return entry.value

                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON in Redis cache for key {key}")
                            self._redis_client.delete(full_key)
                except Exception as e:
                    logger.debug(f"Redis get error: {e}")

            # Try local cache
            if full_key in self._local_cache:
                entry = self._local_cache[full_key]

                # Check expiration
                if entry.expires_at and entry.expires_at < datetime.utcnow():
                    del self._local_cache[full_key]
                    self._total_misses += 1
                    return None

                entry.access_count += 1
                entry.last_accessed = datetime.utcnow()
                self._total_hits += 1
                response_time = (time.time() - response_start) * 1000
                self._response_times.append(response_time)
                logger.debug(f"Cache hit from local: {key}")
                return entry.value

            self._total_misses += 1
            return None

        except Exception as e:
            logger.error(f"Error getting cache value for {key}: {e}")
            self._total_misses += 1
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        namespace: Optional[str] = None
    ) -> bool:
        """Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds, uses default if None
            tags: Tags for invalidation
            namespace: Optional namespace override

        Returns:
            True if successful, False otherwise
        """
        try:
            full_key = self._build_key(key, namespace)
            ttl_seconds = ttl or self.config.default_ttl_seconds
            size = self._calculate_size(value)

            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=ttl_seconds)

            entry = CacheEntry(
                key=full_key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                access_count=0,
                last_accessed=now,
                size_bytes=size,
                tags=tags or []
            )

            # Check memory usage before adding
            current_memory = sum(e.size_bytes for e in self._local_cache.values()) / (1024 * 1024)
            if current_memory + (size / (1024 * 1024)) > self.config.max_memory_mb:
                self._evict()

            # Store in local cache
            if len(self._local_cache) >= self.config.max_entries:
                self._evict()

            self._local_cache[full_key] = entry

            # Store in Redis if available
            if self._redis_client:
                try:
                    self._redis_client.setex(
                        full_key,
                        ttl_seconds,
                        json.dumps(entry.model_dump(default=str))
                    )
                except Exception as e:
                    logger.warning(f"Failed to store in Redis: {e}")

            logger.debug(f"Set cache value: {key}")
            return True

        except Exception as e:
            logger.error(f"Error setting cache value for {key}: {e}")
            return False

    def delete(self, key: str, namespace: Optional[str] = None) -> bool:
        """Delete key from cache.

        Args:
            key: Cache key
            namespace: Optional namespace override

        Returns:
            True if successful, False otherwise
        """
        try:
            full_key = self._build_key(key, namespace)

            # Delete from local cache
            if full_key in self._local_cache:
                del self._local_cache[full_key]

            # Delete from Redis
            if self._redis_client:
                try:
                    self._redis_client.delete(full_key)
                except Exception as e:
                    logger.warning(f"Failed to delete from Redis: {e}")

            logger.debug(f"Deleted cache key: {key}")
            return True

        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False

    def exists(self, key: str, namespace: Optional[str] = None) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key
            namespace: Optional namespace override

        Returns:
            True if key exists and not expired, False otherwise
        """
        try:
            full_key = self._build_key(key, namespace)

            if full_key in self._local_cache:
                entry = self._local_cache[full_key]
                if entry.expires_at and entry.expires_at < datetime.utcnow():
                    del self._local_cache[full_key]
                    return False
                return True

            if self._redis_client:
                try:
                    return self._redis_client.exists(full_key) > 0
                except Exception as e:
                    logger.debug(f"Redis exists error: {e}")

            return False

        except Exception as e:
            logger.error(f"Error checking cache existence for {key}: {e}")
            return False

    def invalidate_by_tag(self, tag: str) -> int:
        """Invalidate all entries with a specific tag.

        Args:
            tag: Tag to invalidate

        Returns:
            Number of entries invalidated
        """
        count = 0

        try:
            # Invalidate in local cache
            keys_to_delete = [
                k for k, v in self._local_cache.items()
                if tag in v.tags
            ]
            for key in keys_to_delete:
                del self._local_cache[key]
                count += 1

            # Invalidate in Redis
            if self._redis_client:
                try:
                    # Scan for keys with tag in local records
                    for key in keys_to_delete:
                        try:
                            self._redis_client.delete(key)
                        except Exception as e:
                            logger.debug(f"Failed to delete from Redis: {e}")
                except Exception as e:
                    logger.warning(f"Redis tag invalidation error: {e}")

            logger.info(f"Invalidated {count} cache entries with tag '{tag}'")
            return count

        except Exception as e:
            logger.error(f"Error invalidating by tag {tag}: {e}")
            return 0

    def invalidate_by_pattern(self, pattern: str) -> int:
        """Invalidate entries matching a regex pattern.

        Args:
            pattern: Regex pattern to match keys

        Returns:
            Number of entries invalidated
        """
        count = 0

        try:
            regex = re.compile(pattern)
            keys_to_delete = [
                k for k in self._local_cache.keys()
                if regex.search(k)
            ]

            for key in keys_to_delete:
                del self._local_cache[key]
                count += 1

            # Invalidate in Redis
            if self._redis_client:
                try:
                    for key in keys_to_delete:
                        try:
                            self._redis_client.delete(key)
                        except Exception as e:
                            logger.debug(f"Failed to delete from Redis: {e}")
                except Exception as e:
                    logger.warning(f"Redis pattern invalidation error: {e}")

            logger.info(f"Invalidated {count} cache entries matching pattern '{pattern}'")
            return count

        except Exception as e:
            logger.error(f"Error invalidating by pattern {pattern}: {e}")
            return 0

    def get_or_set(
        self,
        key: str,
        factory_fn: Callable[[], Any],
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        namespace: Optional[str] = None
    ) -> Any:
        """Cache-aside pattern: get from cache or compute and set.

        Args:
            key: Cache key
            factory_fn: Callable that computes value if not cached
            ttl: Time to live in seconds
            tags: Tags for invalidation
            namespace: Optional namespace override

        Returns:
            Cached or computed value
        """
        try:
            # Try to get from cache
            cached = self.get(key, namespace)
            if cached is not None:
                return cached

            # Compute value
            value = factory_fn()
            if value is not None:
                self.set(key, value, ttl, tags, namespace)

            return value

        except Exception as e:
            logger.error(f"Error in get_or_set for {key}: {e}")
            # Try calling factory as fallback
            try:
                return factory_fn()
            except Exception as fallback_e:
                logger.error(f"Fallback factory call failed: {fallback_e}")
                return None

    def bulk_get(self, keys: List[str], namespace: Optional[str] = None) -> Dict[str, Any]:
        """Get multiple values from cache.

        Args:
            keys: List of cache keys
            namespace: Optional namespace override

        Returns:
            Dictionary of key -> value for found entries
        """
        result = {}

        try:
            for key in keys:
                value = self.get(key, namespace)
                if value is not None:
                    result[key] = value

            logger.debug(f"Bulk get: {len(result)}/{len(keys)} entries found")
            return result

        except Exception as e:
            logger.error(f"Error in bulk_get: {e}")
            return result

    def bulk_set(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None,
        namespace: Optional[str] = None
    ) -> int:
        """Set multiple values in cache.

        Args:
            items: Dictionary of key -> value
            ttl: Time to live in seconds
            namespace: Optional namespace override

        Returns:
            Number of successfully set entries
        """
        count = 0

        try:
            for key, value in items.items():
                if self.set(key, value, ttl, namespace=namespace):
                    count += 1

            logger.debug(f"Bulk set: {count}/{len(items)} entries set")
            return count

        except Exception as e:
            logger.error(f"Error in bulk_set: {e}")
            return count

    def get_stats(self) -> CacheStats:
        """Get cache statistics.

        Returns:
            Cache statistics
        """
        try:
            total_requests = self._total_hits + self._total_misses
            hit_rate = self._total_hits / total_requests if total_requests > 0 else 0.0
            memory_mb = sum(e.size_bytes for e in self._local_cache.values()) / (1024 * 1024)
            avg_response = sum(self._response_times) / len(self._response_times) if self._response_times else 0.0

            return CacheStats(
                total_hits=self._total_hits,
                total_misses=self._total_misses,
                hit_rate=hit_rate,
                total_entries=len(self._local_cache),
                memory_used_mb=memory_mb,
                evictions_count=self._total_evictions,
                avg_response_time_ms=avg_response
            )

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return CacheStats()

    def clear(self, namespace: Optional[str] = None) -> int:
        """Clear all cache entries in namespace.

        Args:
            namespace: Optional namespace to clear, clears all if None

        Returns:
            Number of entries cleared
        """
        count = 0

        try:
            ns = namespace or self.config.namespace

            # Clear local cache
            keys_to_delete = [k for k in self._local_cache.keys() if k.startswith(f"{ns}:")]
            for key in keys_to_delete:
                del self._local_cache[key]
                count += 1

            # Clear Redis
            if self._redis_client:
                try:
                    for key in keys_to_delete:
                        try:
                            self._redis_client.delete(key)
                        except Exception as e:
                            logger.debug(f"Failed to delete from Redis: {e}")
                except Exception as e:
                    logger.warning(f"Redis clear error: {e}")

            logger.info(f"Cleared {count} cache entries in namespace '{ns}'")
            return count

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
            return 0

    def warmup(self, queries: List[dict]) -> int:
        """Pre-populate cache with query results.

        Args:
            queries: List of dicts with 'key', 'value', and optional 'ttl', 'tags'

        Returns:
            Number of entries warmed up
        """
        count = 0

        try:
            if not self.config.warmup_enabled:
                logger.info("Cache warmup is disabled")
                return 0

            for query in queries:
                try:
                    key = query.get("key")
                    value = query.get("value")
                    ttl = query.get("ttl")
                    tags = query.get("tags", [])

                    if key and value is not None:
                        if self.set(key, value, ttl, tags):
                            count += 1

                except Exception as e:
                    logger.warning(f"Error warming up query: {e}")

            logger.info(f"Warmed up {count}/{len(queries)} cache entries")
            return count

        except Exception as e:
            logger.error(f"Error in warmup: {e}")
            return 0

    def _evict(self) -> int:
        """Evict entries based on configured strategy.

        Returns:
            Number of entries evicted
        """
        if not self._local_cache:
            return 0

        try:
            strategy = self.config.strategy
            evict_count = max(1, len(self._local_cache) // 10)  # Evict 10% at a time
            evicted = 0

            if strategy == CacheStrategy.LRU:
                # Evict least recently used
                sorted_entries = sorted(
                    self._local_cache.items(),
                    key=lambda x: x[1].last_accessed
                )
                for key, _ in sorted_entries[:evict_count]:
                    del self._local_cache[key]
                    evicted += 1

            elif strategy == CacheStrategy.LFU:
                # Evict least frequently used
                sorted_entries = sorted(
                    self._local_cache.items(),
                    key=lambda x: x[1].access_count
                )
                for key, _ in sorted_entries[:evict_count]:
                    del self._local_cache[key]
                    evicted += 1

            elif strategy == CacheStrategy.TTL:
                # Evict entries closest to expiration
                sorted_entries = sorted(
                    self._local_cache.items(),
                    key=lambda x: x[1].expires_at or datetime.utcnow() + timedelta(days=365)
                )
                for key, _ in sorted_entries[:evict_count]:
                    del self._local_cache[key]
                    evicted += 1

            else:
                # Default to LRU for other strategies
                sorted_entries = sorted(
                    self._local_cache.items(),
                    key=lambda x: x[1].last_accessed
                )
                for key, _ in sorted_entries[:evict_count]:
                    del self._local_cache[key]
                    evicted += 1

            self._total_evictions += evicted
            logger.info(f"Evicted {evicted} entries using {strategy.value} strategy")
            return evicted

        except Exception as e:
            logger.error(f"Error during eviction: {e}")
            return 0
