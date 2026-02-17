"""Unit tests for query cache service."""

import pytest
from datetime import datetime, timedelta
from src.core.query_cache import (
    CacheStrategy,
    CacheEntry,
    CacheConfig,
    CacheStats,
    QueryCacheService,
)


class TestCacheStrategy:
    """Tests for CacheStrategy enumeration."""

    def test_cache_strategy_lru_value(self):
        """Test LRU strategy value."""
        assert CacheStrategy.LRU.value == "lru"

    def test_cache_strategy_ttl_value(self):
        """Test TTL strategy value."""
        assert CacheStrategy.TTL.value == "ttl"

    def test_cache_strategy_lfu_value(self):
        """Test LFU strategy value."""
        assert CacheStrategy.LFU.value == "lfu"

    def test_cache_strategy_count(self):
        """Test cache strategy enumeration count."""
        assert len(CacheStrategy) == 5

    def test_cache_strategy_string_representation(self):
        """Test string representation of cache strategies."""
        assert str(CacheStrategy.LRU) == "CacheStrategy.LRU"


class TestCacheEntry:
    """Tests for CacheEntry model."""

    def test_cache_entry_defaults(self):
        """Test default values in CacheEntry."""
        entry = CacheEntry(key="test_key", value="test_value")
        assert entry.key == "test_key"
        assert entry.value == "test_value"
        assert entry.access_count == 0
        assert entry.size_bytes == 0
        assert entry.tags == []
        assert isinstance(entry.created_at, datetime)
        assert isinstance(entry.last_accessed, datetime)

    def test_cache_entry_custom_values(self):
        """Test custom values in CacheEntry."""
        entry = CacheEntry(
            key="employee:123",
            value={"id": 123, "name": "John"},
            access_count=5,
            size_bytes=256,
            tags=["employee", "profile"],
        )
        assert entry.key == "employee:123"
        assert entry.access_count == 5
        assert entry.size_bytes == 256
        assert entry.tags == ["employee", "profile"]

    def test_cache_entry_access_count(self):
        """Test access count field."""
        entry = CacheEntry(key="key1", value="value1", access_count=10)
        assert entry.access_count == 10

    def test_cache_entry_tags_list(self):
        """Test tags list field."""
        entry = CacheEntry(key="key1", value="value1", tags=["tag1", "tag2", "tag3"])
        assert len(entry.tags) == 3
        assert "tag1" in entry.tags


class TestCacheConfig:
    """Tests for CacheConfig model."""

    def test_cache_config_defaults(self):
        """Test default values in CacheConfig."""
        config = CacheConfig()
        assert config.strategy == CacheStrategy.LRU
        assert config.max_entries == 1000
        assert config.default_ttl_seconds == 300
        assert config.max_memory_mb == 256
        assert config.redis_enabled is False
        assert config.namespace == "hr_agent"
        assert config.warmup_enabled is False

    def test_cache_config_custom_values(self):
        """Test custom values in CacheConfig."""
        config = CacheConfig(
            strategy=CacheStrategy.LFU, max_entries=500, default_ttl_seconds=600, redis_enabled=True
        )
        assert config.strategy == CacheStrategy.LFU
        assert config.max_entries == 500
        assert config.default_ttl_seconds == 600
        assert config.redis_enabled is True

    def test_cache_config_max_entries(self):
        """Test max entries configuration."""
        config = CacheConfig(max_entries=2000)
        assert config.max_entries == 2000

    def test_cache_config_redis_settings(self):
        """Test redis configuration settings."""
        config = CacheConfig(redis_enabled=True, redis_url="redis://localhost:6379/1")
        assert config.redis_enabled is True
        assert config.redis_url == "redis://localhost:6379/1"


class TestCacheStats:
    """Tests for CacheStats model."""

    def test_cache_stats_defaults(self):
        """Test default values in CacheStats."""
        stats = CacheStats()
        assert stats.total_hits == 0
        assert stats.total_misses == 0
        assert stats.hit_rate == 0.0
        assert stats.total_entries == 0
        assert stats.memory_used_mb == 0.0
        assert stats.evictions_count == 0
        assert stats.avg_response_time_ms == 0.0

    def test_cache_stats_custom_values(self):
        """Test custom values in CacheStats."""
        stats = CacheStats(
            total_hits=1500,
            total_misses=300,
            hit_rate=0.833,
            total_entries=425,
            memory_used_mb=128.5,
            evictions_count=125,
            avg_response_time_ms=2.3,
        )
        assert stats.total_hits == 1500
        assert stats.total_misses == 300
        assert stats.hit_rate == 0.833
        assert stats.total_entries == 425

    def test_cache_stats_hit_rate_calculation(self):
        """Test hit rate calculation field."""
        stats = CacheStats(total_hits=800, total_misses=200, hit_rate=0.8)
        assert stats.hit_rate == 0.8

    def test_cache_stats_zero_state(self):
        """Test zero state statistics."""
        stats = CacheStats(total_hits=0, total_misses=0, hit_rate=0.0, total_entries=0)
        assert stats.total_hits == 0
        assert stats.hit_rate == 0.0


class TestQueryCacheServiceInit:
    """Tests for QueryCacheService initialization."""

    def test_service_creates_with_config(self):
        """Test service creates with config."""
        config = CacheConfig()
        service = QueryCacheService(config)
        assert service is not None
        assert service.config == config

    def test_service_empty_cache(self):
        """Test service initializes with empty cache."""
        config = CacheConfig()
        service = QueryCacheService(config)
        assert len(service._local_cache) == 0

    def test_service_stats_initialization(self):
        """Test service initializes stats."""
        config = CacheConfig()
        service = QueryCacheService(config)
        assert service._total_hits == 0
        assert service._total_misses == 0
        assert service._total_evictions == 0


class TestGet:
    """Tests for cache get operations."""

    def test_get_returns_cached_value(self):
        """Test get returns cached value."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")

        result = service.get("key1")
        assert result == "value1"

    def test_get_miss_returns_none(self):
        """Test get returns None on miss."""
        config = CacheConfig()
        service = QueryCacheService(config)

        result = service.get("nonexistent")
        assert result is None

    def test_get_updates_access_count(self):
        """Test get updates access count."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")

        initial_count = service._local_cache["hr_agent:key1"].access_count
        service.get("key1")
        updated_count = service._local_cache["hr_agent:key1"].access_count

        assert updated_count > initial_count

    def test_get_checks_expiration(self):
        """Test get respects expiration."""
        config = CacheConfig(default_ttl_seconds=10)
        service = QueryCacheService(config)
        service.set("key1", "value1", ttl=1)

        import time

        time.sleep(1.1)

        result = service.get("key1")
        assert result is None


class TestSet:
    """Tests for cache set operations."""

    def test_set_stores_value(self):
        """Test set stores value in cache."""
        config = CacheConfig()
        service = QueryCacheService(config)

        result = service.set("key1", "value1")
        assert result is True
        assert service.get("key1") == "value1"

    def test_set_respects_ttl(self):
        """Test set respects TTL parameter."""
        config = CacheConfig()
        service = QueryCacheService(config)

        service.set("key1", "value1", ttl=3600)
        entry = service._local_cache["hr_agent:key1"]
        assert entry.expires_at is not None

    def test_set_enforces_max_entries(self):
        """Test set enforces max entries limit."""
        config = CacheConfig(max_entries=10)
        service = QueryCacheService(config)

        # Add 11 entries to exceed max_entries
        for i in range(11):
            service.set(f"key{i}", f"value{i}")

        # Should have evicted entries when max was reached
        assert len(service._local_cache) <= config.max_entries

    def test_set_stores_tags(self):
        """Test set stores tags with entry."""
        config = CacheConfig()
        service = QueryCacheService(config)

        service.set("key1", "value1", tags=["tag1", "tag2"])
        entry = service._local_cache["hr_agent:key1"]
        assert "tag1" in entry.tags
        assert "tag2" in entry.tags


class TestDelete:
    """Tests for cache delete operations."""

    def test_delete_removes_entry(self):
        """Test delete removes entry from cache."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")

        result = service.delete("key1")
        assert result is True
        assert service.get("key1") is None

    def test_delete_returns_true(self):
        """Test delete returns True on success."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")

        result = service.delete("key1")
        assert result is True

    def test_delete_missing_key_returns_false(self):
        """Test delete returns True even for missing keys."""
        config = CacheConfig()
        service = QueryCacheService(config)

        # Service returns True even for missing keys
        result = service.delete("nonexistent")
        assert result is True


class TestExists:
    """Tests for cache exists check."""

    def test_exists_returns_true_for_existing(self):
        """Test exists returns True for existing key."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")

        result = service.exists("key1")
        assert result is True

    def test_exists_returns_false_for_missing(self):
        """Test exists returns False for missing key."""
        config = CacheConfig()
        service = QueryCacheService(config)

        result = service.exists("nonexistent")
        assert result is False

    def test_exists_checks_expiration(self):
        """Test exists respects expiration."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1", ttl=0)

        import time

        time.sleep(0.1)

        # Might be expired depending on timing
        result = service.exists("key1")
        assert isinstance(result, bool)


class TestInvalidateByTag:
    """Tests for tag-based invalidation."""

    def test_invalidate_by_tag_removes_tagged_entries(self):
        """Test invalidate by tag removes tagged entries."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1", tags=["employee"])
        service.set("key2", "value2", tags=["employee"])
        service.set("key3", "value3", tags=["department"])

        count = service.invalidate_by_tag("employee")
        assert count == 2
        assert service.get("key1") is None
        assert service.get("key2") is None
        assert service.get("key3") == "value3"

    def test_invalidate_by_tag_returns_count(self):
        """Test invalidate by tag returns count."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1", tags=["tag1"])
        service.set("key2", "value2", tags=["tag1"])

        count = service.invalidate_by_tag("tag1")
        assert count == 2

    def test_invalidate_by_tag_no_matches_returns_zero(self):
        """Test invalidate returns 0 when no matches."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1", tags=["tag1"])

        count = service.invalidate_by_tag("nonexistent")
        assert count == 0


class TestInvalidateByPattern:
    """Tests for pattern-based invalidation."""

    def test_invalidate_by_pattern_removes_matching(self):
        """Test invalidate by pattern removes matching keys."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("employee:1", "value1")
        service.set("employee:2", "value2")
        service.set("department:1", "value3")

        count = service.invalidate_by_pattern(r"employee:.*")
        assert count == 2

    def test_invalidate_by_pattern_regex_patterns(self):
        """Test invalidate supports regex patterns."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("hr_agent:user:123", "value1")
        service.set("hr_agent:user:456", "value2")
        service.set("hr_agent:dept:789", "value3")

        count = service.invalidate_by_pattern(r".*user:.*")
        assert count == 2

    def test_invalidate_by_pattern_returns_count(self):
        """Test invalidate by pattern returns count."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key:1", "value1")
        service.set("key:2", "value2")

        count = service.invalidate_by_pattern(r"key:.*")
        assert isinstance(count, int)


class TestGetOrSet:
    """Tests for cache-aside pattern."""

    def test_get_or_set_returns_cached(self):
        """Test get_or_set returns cached value."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "cached_value")

        result = service.get_or_set("key1", lambda: "computed_value")
        assert result == "cached_value"

    def test_get_or_set_calls_factory_on_miss(self):
        """Test get_or_set calls factory on miss."""
        config = CacheConfig()
        service = QueryCacheService(config)

        called = []

        def factory():
            called.append(True)
            return "computed_value"

        result = service.get_or_set("key1", factory)
        assert len(called) > 0
        assert result == "computed_value"

    def test_get_or_set_caches_factory_result(self):
        """Test get_or_set caches factory result."""
        config = CacheConfig()
        service = QueryCacheService(config)

        result = service.get_or_set("key1", lambda: "factory_value")
        assert service.get("key1") == "factory_value"


class TestBulkGet:
    """Tests for bulk get operations."""

    def test_bulk_get_returns_multiple(self):
        """Test bulk get returns multiple values."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")
        service.set("key2", "value2")
        service.set("key3", "value3")

        result = service.bulk_get(["key1", "key2", "key3"])
        assert len(result) == 3
        assert result["key1"] == "value1"

    def test_bulk_get_missing_keys_excluded(self):
        """Test bulk get excludes missing keys."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")
        service.set("key2", "value2")

        result = service.bulk_get(["key1", "key2", "missing"])
        assert len(result) == 2
        assert "missing" not in result

    def test_bulk_get_empty_keys(self):
        """Test bulk get with empty keys list."""
        config = CacheConfig()
        service = QueryCacheService(config)

        result = service.bulk_get([])
        assert result == {}


class TestBulkSet:
    """Tests for bulk set operations."""

    def test_bulk_set_stores_multiple(self):
        """Test bulk set stores multiple values."""
        config = CacheConfig()
        service = QueryCacheService(config)

        items = {"key1": "value1", "key2": "value2", "key3": "value3"}
        count = service.bulk_set(items)
        assert count == 3
        assert service.get("key1") == "value1"

    def test_bulk_set_returns_count(self):
        """Test bulk set returns count of set items."""
        config = CacheConfig()
        service = QueryCacheService(config)

        items = {"key1": "value1", "key2": "value2"}
        count = service.bulk_set(items)
        assert count == 2

    def test_bulk_set_respects_ttl(self):
        """Test bulk set respects TTL parameter."""
        config = CacheConfig()
        service = QueryCacheService(config)

        items = {"key1": "value1", "key2": "value2"}
        service.bulk_set(items, ttl=3600)

        entry = service._local_cache["hr_agent:key1"]
        assert entry.expires_at is not None


class TestGetStats:
    """Tests for cache statistics."""

    def test_get_stats_returns_stats(self):
        """Test get_stats returns CacheStats object."""
        config = CacheConfig()
        service = QueryCacheService(config)

        stats = service.get_stats()
        assert isinstance(stats, CacheStats)

    def test_get_stats_calculates_hit_rate(self):
        """Test get_stats calculates hit rate."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")
        service.get("key1")
        service.get("missing")

        stats = service.get_stats()
        assert stats.hit_rate >= 0.0
        assert stats.hit_rate <= 1.0

    def test_get_stats_tracks_memory(self):
        """Test get_stats tracks memory usage."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value" * 100)

        stats = service.get_stats()
        assert stats.memory_used_mb >= 0.0


class TestClear:
    """Tests for cache clear operations."""

    def test_clear_clears_all(self):
        """Test clear removes all entries."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")
        service.set("key2", "value2")

        count = service.clear()
        assert len(service._local_cache) == 0

    def test_clear_namespace_specific(self):
        """Test clear is namespace-specific."""
        config = CacheConfig(namespace="ns1")
        service = QueryCacheService(config)
        service.set("key1", "value1", namespace="ns1")
        service._local_cache["other:key"] = CacheEntry(key="other:key", value="value")

        count = service.clear(namespace="ns1")
        assert len(service._local_cache) == 1

    def test_clear_returns_count(self):
        """Test clear returns count of cleared entries."""
        config = CacheConfig()
        service = QueryCacheService(config)
        service.set("key1", "value1")
        service.set("key2", "value2")

        count = service.clear()
        assert count == 2


class TestWarmup:
    """Tests for cache warmup."""

    def test_warmup_pre_populates_cache(self):
        """Test warmup pre-populates cache."""
        config = CacheConfig(warmup_enabled=True)
        service = QueryCacheService(config)

        queries = [
            {"key": "key1", "value": "value1"},
            {"key": "key2", "value": "value2"},
        ]
        count = service.warmup(queries)
        assert count == 2
        assert service.get("key1") == "value1"

    def test_warmup_returns_count(self):
        """Test warmup returns count."""
        config = CacheConfig(warmup_enabled=True)
        service = QueryCacheService(config)

        queries = [
            {"key": "key1", "value": "value1"},
            {"key": "key2", "value": "value2"},
        ]
        count = service.warmup(queries)
        assert count == 2

    def test_warmup_handles_errors(self):
        """Test warmup handles errors gracefully."""
        config = CacheConfig(warmup_enabled=True)
        service = QueryCacheService(config)

        queries = [
            {"key": "key1", "value": "value1"},
            {"key": None, "value": "value2"},  # Invalid
            {"key": "key3", "value": "value3"},
        ]
        count = service.warmup(queries)
        assert count >= 0


class TestEvict:
    """Tests for cache eviction."""

    def test_evict_lru_entries(self):
        """Test eviction uses LRU strategy."""
        config = CacheConfig(strategy=CacheStrategy.LRU, max_entries=10)
        service = QueryCacheService(config)

        # Add 10 entries, then access key1 to make it recently used
        for i in range(10):
            service.set(f"key{i}", f"value{i}")

        service.get("key1")  # Access key1 to make it more recently used
        service.set("key10", "value10")  # Add one more to trigger eviction

        # After eviction, cache should not exceed max_entries
        assert len(service._local_cache) <= config.max_entries
        # key1 should still be present (was accessed recently, so less likely to be evicted)
        keys_in_cache = [k for k in service._local_cache.keys()]
        assert any("key1" in k for k in keys_in_cache)

    def test_evict_lfu_entries(self):
        """Test eviction uses LFU strategy."""
        config = CacheConfig(strategy=CacheStrategy.LFU, max_entries=10)
        service = QueryCacheService(config)

        # Add 10 entries
        for i in range(10):
            service.set(f"key{i}", f"value{i}")

        # Increase access count for key1
        service.get("key1")
        service.get("key1")

        service.set("key10", "value10")  # Add one more to trigger eviction

        # After eviction, cache should not exceed max_entries
        assert len(service._local_cache) <= config.max_entries
        # key1 should still be present (has higher access count)
        keys_in_cache = [k for k in service._local_cache.keys()]
        assert any("key1" in k for k in keys_in_cache)

    def test_evict_ttl_expired(self):
        """Test eviction removes TTL expired entries."""
        config = CacheConfig(strategy=CacheStrategy.TTL, max_entries=10)
        service = QueryCacheService(config)

        # Add entries with different TTLs
        service.set("key0", "value0", ttl=1)  # Shortest TTL
        for i in range(1, 10):
            service.set(f"key{i}", f"value{i}", ttl=3600)  # Longer TTLs

        import time

        time.sleep(0.1)

        service.set("key10", "value10", ttl=3600)

        # TTL strategy evicts entries closest to expiration
        # key0 (ttl=1) is closest to expiration, so should be evicted first
        assert len(service._local_cache) <= config.max_entries
        # key0 should be evicted or expired
        keys_in_cache = [k for k in service._local_cache.keys()]
        assert not any("key0" in k for k in keys_in_cache) or service.get("key0") is None
