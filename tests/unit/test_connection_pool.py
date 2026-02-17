"""Unit tests for connection pool manager."""

import pytest
from datetime import datetime, timedelta
from src.core.connection_pool import (
    PoolType,
    PoolConfig,
    PoolStats,
    ConnectionHealth,
    ConnectionPoolManager,
)


class TestPoolType:
    """Tests for PoolType enumeration."""

    def test_pool_type_postgresql_value(self):
        """Test PostgreSQL pool type value."""
        assert PoolType.POSTGRESQL.value == "postgresql"

    def test_pool_type_redis_value(self):
        """Test Redis pool type value."""
        assert PoolType.REDIS.value == "redis"

    def test_pool_type_http_value(self):
        """Test HTTP pool type value."""
        assert PoolType.HTTP.value == "http"

    def test_pool_type_count(self):
        """Test pool type enumeration count."""
        assert len(PoolType) == 3

    def test_pool_type_string_representation(self):
        """Test string representation of pool types."""
        assert str(PoolType.POSTGRESQL) == "PoolType.POSTGRESQL"


class TestPoolConfig:
    """Tests for PoolConfig model."""

    def test_pool_config_defaults(self):
        """Test default values in PoolConfig."""
        config = PoolConfig(
            pool_type=PoolType.POSTGRESQL, connection_string="postgresql://localhost/test"
        )
        assert config.min_connections == 2
        assert config.max_connections == 20
        assert config.max_overflow == 10
        assert config.pool_timeout == 30
        assert config.pool_recycle == 3600
        assert config.echo is False
        assert config.health_check_interval == 60

    def test_pool_config_custom_values(self):
        """Test custom values in PoolConfig."""
        config = PoolConfig(
            pool_type=PoolType.REDIS,
            connection_string="redis://localhost:6379",
            min_connections=5,
            max_connections=50,
            pool_timeout=60,
        )
        assert config.min_connections == 5
        assert config.max_connections == 50
        assert config.pool_timeout == 60

    def test_pool_config_min_max_connections(self):
        """Test min and max connections constraints."""
        config = PoolConfig(
            pool_type=PoolType.HTTP,
            connection_string="http://localhost",
            min_connections=1,
            max_connections=1,
        )
        assert config.min_connections == 1
        assert config.max_connections == 1

    def test_pool_config_pool_recycle(self):
        """Test pool recycle configuration."""
        config = PoolConfig(
            pool_type=PoolType.POSTGRESQL,
            connection_string="postgresql://localhost/test",
            pool_recycle=7200,
        )
        assert config.pool_recycle == 7200


class TestPoolStats:
    """Tests for PoolStats model."""

    def test_pool_stats_defaults(self):
        """Test default values in PoolStats."""
        stats = PoolStats(pool_type=PoolType.POSTGRESQL)
        assert stats.active_connections == 0
        assert stats.idle_connections == 0
        assert stats.total_created == 0
        assert stats.total_recycled == 0
        assert stats.total_errors == 0
        assert stats.avg_wait_time == 0.0
        assert stats.peak_connections == 0
        assert stats.uptime_seconds == 0.0

    def test_pool_stats_custom_values(self):
        """Test custom values in PoolStats."""
        stats = PoolStats(
            pool_type=PoolType.REDIS,
            active_connections=5,
            idle_connections=10,
            total_created=100,
            avg_wait_time=5.5,
        )
        assert stats.active_connections == 5
        assert stats.idle_connections == 10
        assert stats.total_created == 100
        assert stats.avg_wait_time == 5.5

    def test_pool_stats_active_connections(self):
        """Test active connections field."""
        stats = PoolStats(pool_type=PoolType.HTTP, active_connections=15)
        assert stats.active_connections == 15

    def test_pool_stats_avg_wait_time(self):
        """Test average wait time field."""
        stats = PoolStats(pool_type=PoolType.POSTGRESQL, avg_wait_time=2.3)
        assert stats.avg_wait_time == 2.3


class TestConnectionHealth:
    """Tests for ConnectionHealth model."""

    def test_connection_health_defaults(self):
        """Test default values in ConnectionHealth."""
        health = ConnectionHealth(is_healthy=True)
        assert health.is_healthy is True
        assert health.latency_ms == 0.0
        assert health.error_message is None
        assert isinstance(health.last_check, datetime)

    def test_connection_health_custom_values(self):
        """Test custom values in ConnectionHealth."""
        health = ConnectionHealth(
            is_healthy=False, latency_ms=10.5, error_message="Connection timeout"
        )
        assert health.is_healthy is False
        assert health.latency_ms == 10.5
        assert health.error_message == "Connection timeout"

    def test_connection_health_is_healthy_flag(self):
        """Test is_healthy flag."""
        healthy = ConnectionHealth(is_healthy=True)
        unhealthy = ConnectionHealth(is_healthy=False, error_message="Error")
        assert healthy.is_healthy is True
        assert unhealthy.is_healthy is False


class TestConnectionPoolManagerInit:
    """Tests for ConnectionPoolManager initialization."""

    def test_manager_creates_with_configs(self):
        """Test manager creates with multiple configs."""
        configs = [
            PoolConfig(
                pool_type=PoolType.POSTGRESQL, connection_string="postgresql://localhost/test"
            ),
            PoolConfig(pool_type=PoolType.REDIS, connection_string="redis://localhost:6379"),
        ]
        manager = ConnectionPoolManager(configs)
        assert manager is not None

    def test_manager_stores_configs(self):
        """Test manager stores configurations."""
        configs = [PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")]
        manager = ConnectionPoolManager(configs)
        assert PoolType.HTTP in manager._pools

    def test_manager_empty_pools(self):
        """Test manager initializes with empty pool dict."""
        config = PoolConfig(
            pool_type=PoolType.POSTGRESQL, connection_string="postgresql://localhost/test"
        )
        manager = ConnectionPoolManager([config])
        assert manager._initialized_pools.get(PoolType.POSTGRESQL) is False


class TestInitializePool:
    """Tests for pool initialization."""

    def test_initialize_http_pool(self):
        """Test initializing HTTP pool."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        result = manager.initialize_pool(PoolType.HTTP)
        assert result is True
        assert manager._initialized_pools[PoolType.HTTP] is True

    def test_initialize_pool_already_initialized(self):
        """Test initializing already initialized pool."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)
        result = manager.initialize_pool(PoolType.HTTP)
        assert result is True

    def test_initialize_invalid_pool_type(self):
        """Test initializing invalid pool type."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        result = manager.initialize_pool(PoolType.POSTGRESQL)
        assert result is False

    def test_initialize_pool_sets_idle_connections(self):
        """Test pool initialization sets idle connections."""
        config = PoolConfig(
            pool_type=PoolType.HTTP, connection_string="http://localhost", min_connections=3
        )
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)
        pool_instance = manager._pools[PoolType.HTTP]
        assert pool_instance.idle_connections == 3


class TestGetConnection:
    """Tests for getting connections from pool."""

    def test_get_connection_returns_connection(self):
        """Test getting connection returns a connection object."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        with manager.get_connection(PoolType.HTTP) as conn:
            assert conn is not None
            assert isinstance(conn, dict)

    def test_get_connection_tracks_active(self):
        """Test getting connection increments active counter."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        initial_active = manager._pools[PoolType.HTTP].active_connections
        with manager.get_connection(PoolType.HTTP):
            active = manager._pools[PoolType.HTTP].active_connections
            assert active > initial_active

    def test_get_connection_not_initialized(self):
        """Test getting connection from non-initialized pool raises error."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])

        with pytest.raises(RuntimeError):
            with manager.get_connection(PoolType.HTTP):
                pass


class TestReleaseConnection:
    """Tests for releasing connections back to pool."""

    def test_release_connection_success(self):
        """Test releasing connection successfully."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        with manager.get_connection(PoolType.HTTP) as conn:
            pass

        # After context exit, connection should be released
        assert manager._pools[PoolType.HTTP].active_connections == 0

    def test_release_connection_decrements_active(self):
        """Test releasing connection decrements active counter."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        with manager.get_connection(PoolType.HTTP) as conn:
            active = manager._pools[PoolType.HTTP].active_connections
            assert active > 0

        assert manager._pools[PoolType.HTTP].active_connections == 0

    def test_release_invalid_pool_type(self):
        """Test releasing to invalid pool type."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])

        result = manager.release_connection(PoolType.POSTGRESQL, {})
        assert result is False


class TestHealthCheck:
    """Tests for health checking pools."""

    def test_health_check_all_pools(self):
        """Test health check on all pools."""
        configs = [PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")]
        manager = ConnectionPoolManager(configs)
        manager.initialize_pool(PoolType.HTTP)

        health = manager.health_check()
        assert PoolType.HTTP in health
        assert isinstance(health[PoolType.HTTP], ConnectionHealth)

    def test_health_check_specific_pool(self):
        """Test health check on specific pool."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        health = manager.health_check(PoolType.HTTP)
        assert PoolType.HTTP in health
        assert len(health) == 1

    def test_health_check_returns_health_dict(self):
        """Test health check returns proper dict structure."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        health = manager.health_check(PoolType.HTTP)
        assert isinstance(health, dict)
        assert all(isinstance(v, ConnectionHealth) for v in health.values())


class TestGetPoolStats:
    """Tests for getting pool statistics."""

    def test_get_pool_stats_returns_stats(self):
        """Test getting stats returns PoolStats object."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        stats = manager.get_pool_stats(PoolType.HTTP)
        assert PoolType.HTTP in stats
        assert isinstance(stats[PoolType.HTTP], PoolStats)

    def test_get_pool_stats_specific_pool(self):
        """Test getting stats for specific pool."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        stats = manager.get_pool_stats(PoolType.HTTP)
        assert len(stats) == 1
        assert PoolType.HTTP in stats

    def test_get_pool_stats_all_pools(self):
        """Test getting stats for all pools."""
        configs = [PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")]
        manager = ConnectionPoolManager(configs)
        manager.initialize_pool(PoolType.HTTP)

        stats = manager.get_pool_stats()
        assert len(stats) >= 1


class TestResizePool:
    """Tests for resizing pools."""

    def test_resize_pool_successfully(self):
        """Test resizing pool successfully."""
        config = PoolConfig(
            pool_type=PoolType.HTTP, connection_string="http://localhost", max_connections=20
        )
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        result = manager.resize_pool(PoolType.HTTP, 30)
        assert result is True
        assert manager._pools[PoolType.HTTP].config.max_connections == 30

    def test_resize_pool_invalid_size(self):
        """Test resizing with invalid size."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        result = manager.resize_pool(PoolType.HTTP, 0)
        assert result is False

    def test_resize_pool_not_found(self):
        """Test resizing non-existent pool."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])

        result = manager.resize_pool(PoolType.POSTGRESQL, 10)
        assert result is False


class TestDrainPool:
    """Tests for draining pools."""

    def test_drain_pool_connections(self):
        """Test draining connections from pool."""
        config = PoolConfig(
            pool_type=PoolType.HTTP, connection_string="http://localhost", min_connections=3
        )
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        drained = manager.drain_pool(PoolType.HTTP)
        assert drained > 0

    def test_drain_pool_returns_count(self):
        """Test drain returns number of drained connections."""
        config = PoolConfig(
            pool_type=PoolType.HTTP, connection_string="http://localhost", min_connections=5
        )
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        drained = manager.drain_pool(PoolType.HTTP)
        assert isinstance(drained, int)

    def test_drain_empty_pool(self):
        """Test draining empty pool."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        drained = manager.drain_pool(PoolType.HTTP)
        assert drained >= 0


class TestShutdown:
    """Tests for shutting down pools."""

    def test_shutdown_all_pools(self):
        """Test shutting down all pools."""
        configs = [PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")]
        manager = ConnectionPoolManager(configs)
        manager.initialize_pool(PoolType.HTTP)

        result = manager.shutdown()
        assert result is True

    def test_shutdown_returns_bool(self):
        """Test shutdown returns boolean."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        result = manager.shutdown()
        assert isinstance(result, bool)

    def test_shutdown_cleans_state(self):
        """Test shutdown cleans pool state."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        manager.shutdown()
        assert manager._initialized_pools[PoolType.HTTP] is False


class TestGetOptimalPoolSize:
    """Tests for getting optimal pool size recommendations."""

    def test_get_optimal_pool_size_calculates_recommendation(self):
        """Test calculating pool size recommendation."""
        config = PoolConfig(
            pool_type=PoolType.HTTP, connection_string="http://localhost", max_connections=20
        )
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        recommendation = manager.get_optimal_pool_size(PoolType.HTTP)
        assert "recommended_max" in recommendation
        assert "peak_ratio" in recommendation

    def test_get_optimal_pool_size_zero_usage(self):
        """Test recommendation with zero usage."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        recommendation = manager.get_optimal_pool_size(PoolType.HTTP)
        assert "error" not in recommendation or recommendation.get("peak_connections") == 0

    def test_get_optimal_pool_size_includes_peak(self):
        """Test recommendation includes peak connections."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        recommendation = manager.get_optimal_pool_size(PoolType.HTTP)
        assert "peak_connections" in recommendation


class TestGetStatus:
    """Tests for getting overall pool status."""

    def test_get_status_returns_overall_status(self):
        """Test getting overall status."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        status = manager.get_status()
        assert "timestamp" in status
        assert "pools" in status
        assert "overall_healthy" in status

    def test_get_status_healthy_pools(self):
        """Test status for healthy pools."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        status = manager.get_status()
        assert "timestamp" in status
        assert "pools" in status
        assert "overall_healthy" in status
        assert isinstance(status["overall_healthy"], bool)
        # Verify the status dict structure
        assert "http" in status["pools"]
        assert "healthy" in status["pools"]["http"]
        assert "latency_ms" in status["pools"]["http"]
        assert "active_connections" in status["pools"]["http"]

    def test_get_status_counts_pools(self):
        """Test status includes pool counts."""
        config = PoolConfig(pool_type=PoolType.HTTP, connection_string="http://localhost")
        manager = ConnectionPoolManager([config])
        manager.initialize_pool(PoolType.HTTP)

        status = manager.get_status()
        assert len(status["pools"]) > 0
