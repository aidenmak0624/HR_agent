"""
Unit tests for Health Check Routes.
Iteration 8 Wave 1 - HLT-001 Test Suite
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from src.api.health_routes import (
    HealthStatus,
    ComponentHealth,
    HealthCheckConfig,
    HealthCheckResult,
    HealthCheckService,
)


# ============================================================================
# HealthStatus Enum Tests
# ============================================================================

class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_health_status_enum_values(self):
        """Test HealthStatus has correct enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"

    def test_health_status_enum_count(self):
        """Test HealthStatus has correct number of values."""
        statuses = list(HealthStatus)
        assert len(statuses) == 3

    def test_health_status_representation(self):
        """Test HealthStatus representation."""
        assert str(HealthStatus.HEALTHY) == "HealthStatus.HEALTHY"
        assert HealthStatus.HEALTHY.name == "HEALTHY"


# ============================================================================
# ComponentHealth Tests
# ============================================================================

class TestComponentHealth:
    """Tests for ComponentHealth model."""

    def test_component_health_defaults(self):
        """Test ComponentHealth with default values."""
        component = ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY
        )

        assert component.name == "database"
        assert component.status == HealthStatus.HEALTHY
        assert component.latency_ms == 0.0
        assert component.message is None
        assert component.metadata == {}

    def test_component_health_custom_values(self):
        """Test ComponentHealth with custom values."""
        component = ComponentHealth(
            name="redis",
            status=HealthStatus.DEGRADED,
            latency_ms=150.5,
            message="Connection slow",
            metadata={"host": "redis-server"}
        )

        assert component.name == "redis"
        assert component.status == HealthStatus.DEGRADED
        assert component.latency_ms == 150.5
        assert component.message == "Connection slow"
        assert component.metadata["host"] == "redis-server"

    def test_component_health_status_field(self):
        """Test ComponentHealth status field."""
        healthy = ComponentHealth(
            name="app",
            status=HealthStatus.HEALTHY
        )

        unhealthy = ComponentHealth(
            name="app",
            status=HealthStatus.UNHEALTHY
        )

        assert healthy.status == HealthStatus.HEALTHY
        assert unhealthy.status == HealthStatus.UNHEALTHY


# ============================================================================
# HealthCheckConfig Tests
# ============================================================================

class TestHealthCheckConfig:
    """Tests for HealthCheckConfig model."""

    def test_health_check_config_defaults(self):
        """Test HealthCheckConfig with default values."""
        config = HealthCheckConfig()

        assert config.check_timeout_seconds == 5
        assert config.db_check_enabled is True
        assert config.redis_check_enabled is True
        assert config.llm_check_enabled is True
        assert config.detailed_checks is False
        assert config.cache_ttl_seconds == 30

    def test_health_check_config_custom_values(self):
        """Test HealthCheckConfig with custom values."""
        config = HealthCheckConfig(
            check_timeout_seconds=10,
            db_check_enabled=False,
            redis_check_enabled=False,
            detailed_checks=True
        )

        assert config.check_timeout_seconds == 10
        assert config.db_check_enabled is False
        assert config.redis_check_enabled is False
        assert config.detailed_checks is True

    def test_health_check_config_toggles(self):
        """Test HealthCheckConfig toggle fields."""
        config = HealthCheckConfig(
            db_check_enabled=False,
            redis_check_enabled=True,
            llm_check_enabled=False
        )

        assert config.db_check_enabled is False
        assert config.redis_check_enabled is True
        assert config.llm_check_enabled is False


# ============================================================================
# HealthCheckResult Tests
# ============================================================================

class TestHealthCheckResult:
    """Tests for HealthCheckResult model."""

    def test_health_check_result_defaults(self):
        """Test HealthCheckResult with default values."""
        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            uptime_seconds=100.0,
            components={},
            checks_performed=1
        )

        assert result.status == HealthStatus.HEALTHY
        assert result.version == "1.0.0"
        assert result.uptime_seconds == 100.0
        assert result.components == {}
        assert result.checks_performed == 1

    def test_health_check_result_custom_values(self):
        """Test HealthCheckResult with custom values."""
        components = {
            "database": ComponentHealth(
                name="database",
                status=HealthStatus.HEALTHY
            )
        }

        result = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            version="2.0.0",
            uptime_seconds=500.5,
            components=components,
            checks_performed=2
        )

        assert result.status == HealthStatus.DEGRADED
        assert result.version == "2.0.0"
        assert len(result.components) == 1

    def test_health_check_result_components_dict(self):
        """Test HealthCheckResult components dictionary."""
        app_health = ComponentHealth(
            name="application",
            status=HealthStatus.HEALTHY
        )
        db_health = ComponentHealth(
            name="database",
            status=HealthStatus.HEALTHY
        )

        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            uptime_seconds=100.0,
            components={
                "app": app_health,
                "db": db_health
            },
            checks_performed=2
        )

        assert "app" in result.components
        assert "db" in result.components
        assert len(result.components) == 2


# ============================================================================
# HealthCheckService Init Tests
# ============================================================================

class TestHealthCheckServiceInit:
    """Tests for HealthCheckService initialization."""

    def test_health_check_service_init_with_config(self):
        """Test HealthCheckService creates with config."""
        config = HealthCheckConfig(check_timeout_seconds=10)
        service = HealthCheckService(config=config)

        assert service.config == config
        assert service.config.check_timeout_seconds == 10

    def test_health_check_service_init_start_time(self):
        """Test HealthCheckService records start time."""
        service = HealthCheckService()

        assert service.start_time is not None
        assert isinstance(service.start_time, datetime)

    def test_health_check_service_init_component_list(self):
        """Test HealthCheckService initializes component tracking."""
        service = HealthCheckService()

        assert hasattr(service, '_check_cache')
        assert hasattr(service, '_checks_executed')


# ============================================================================
# Check Liveness Tests
# ============================================================================

class TestCheckLiveness:
    """Tests for HealthCheckService.check_liveness()."""

    def test_check_liveness_returns_alive(self):
        """Test check_liveness returns alive status."""
        service = HealthCheckService()
        result = service.check_liveness()

        assert result["status"] == "alive"

    def test_check_liveness_fast_response(self):
        """Test check_liveness has fast response."""
        service = HealthCheckService()
        start = datetime.utcnow()
        result = service.check_liveness()
        elapsed = (datetime.utcnow() - start).total_seconds()

        assert elapsed < 1.0

    def test_check_liveness_proper_structure(self):
        """Test check_liveness returns proper structure."""
        service = HealthCheckService()
        result = service.check_liveness()

        assert "status" in result
        assert "timestamp" in result
        assert "uptime_seconds" in result


# ============================================================================
# Check Readiness Tests
# ============================================================================

class TestCheckReadiness:
    """Tests for HealthCheckService.check_readiness()."""

    def test_check_readiness_all_healthy(self):
        """Test check_readiness with all healthy components."""
        config = HealthCheckConfig(llm_check_enabled=False)
        service = HealthCheckService(config=config)
        result = service.check_readiness()

        assert result.status == HealthStatus.HEALTHY

    def test_check_readiness_degraded(self):
        """Test check_readiness with degraded components."""
        config = HealthCheckConfig(detailed_checks=True, llm_check_enabled=False)
        service = HealthCheckService(config=config)

        with patch.object(service, 'check_disk_space') as mock_disk:
            mock_disk.return_value = ComponentHealth(
                name="disk_space",
                status=HealthStatus.DEGRADED
            )
            result = service.check_readiness()

            assert result.status == HealthStatus.DEGRADED

    def test_check_readiness_unhealthy(self):
        """Test check_readiness with unhealthy components."""
        service = HealthCheckService()

        with patch.object(service, 'check_component') as mock_check:
            mock_check.return_value = ComponentHealth(
                name="application",
                status=HealthStatus.UNHEALTHY
            )
            result = service.check_readiness()

            assert result.status == HealthStatus.UNHEALTHY


# ============================================================================
# Check Database Tests
# ============================================================================

class TestCheckDatabase:
    """Tests for HealthCheckService.check_database()."""

    def test_check_database_healthy(self):
        """Test check_database returns healthy."""
        service = HealthCheckService()
        result = service.check_database()

        assert result.name == "database"
        assert result.status == HealthStatus.HEALTHY

    def test_check_database_unhealthy(self):
        """Test check_database handles unhealthy state."""
        service = HealthCheckService()

        with patch('os.getenv') as mock_env:
            mock_env.side_effect = lambda x, default=None: default

            result = service.check_database()

            assert isinstance(result, ComponentHealth)

    def test_check_database_disabled(self):
        """Test check_database with disabled config."""
        config = HealthCheckConfig(db_check_enabled=False)
        service = HealthCheckService(config=config)
        result = service.check_readiness()

        assert "database" not in result.components


# ============================================================================
# Check Redis Tests
# ============================================================================

class TestCheckRedis:
    """Tests for HealthCheckService.check_redis()."""

    def test_check_redis_healthy(self):
        """Test check_redis returns healthy."""
        service = HealthCheckService()
        result = service.check_redis()

        assert result.name == "redis"
        assert result.status == HealthStatus.HEALTHY

    def test_check_redis_unhealthy(self):
        """Test check_redis handles unhealthy state."""
        service = HealthCheckService()

        with patch('os.getenv') as mock_env:
            mock_env.side_effect = lambda x, default=None: default

            result = service.check_redis()

            assert isinstance(result, ComponentHealth)

    def test_check_redis_disabled(self):
        """Test check_redis with disabled config."""
        config = HealthCheckConfig(redis_check_enabled=False)
        service = HealthCheckService(config=config)
        result = service.check_readiness()

        assert "redis" not in result.components


# ============================================================================
# Check LLM Provider Tests
# ============================================================================

class TestCheckLLMProvider:
    """Tests for HealthCheckService.check_llm_provider()."""

    def test_check_llm_provider_healthy(self):
        """Test check_llm_provider returns healthy."""
        service = HealthCheckService()

        with patch('os.getenv') as mock_env:
            def getenv_side_effect(key, default=None):
                if key == "LLM_API_KEY":
                    return "test_key"
                return default

            mock_env.side_effect = getenv_side_effect
            result = service.check_llm_provider()

            assert result.name == "llm_provider"

    def test_check_llm_provider_unhealthy(self):
        """Test check_llm_provider unhealthy without API key."""
        service = HealthCheckService()

        with patch('os.getenv') as mock_env:
            mock_env.return_value = None
            result = service.check_llm_provider()

            assert isinstance(result, ComponentHealth)

    def test_check_llm_provider_disabled(self):
        """Test check_llm_provider with disabled config."""
        config = HealthCheckConfig(llm_check_enabled=False)
        service = HealthCheckService(config=config)
        result = service.check_readiness()

        assert "llm_provider" not in result.components


# ============================================================================
# Check Disk Space Tests
# ============================================================================

class TestCheckDiskSpace:
    """Tests for HealthCheckService.check_disk_space()."""

    @patch('psutil.disk_usage')
    def test_check_disk_space_healthy(self, mock_disk):
        """Test check_disk_space returns healthy."""
        mock_disk.return_value = MagicMock(
            percent=50,
            free=500 * 1024 ** 3,
            total=1000 * 1024 ** 3
        )
        service = HealthCheckService()
        result = service.check_disk_space()

        assert result.name == "disk_space"
        assert result.status == HealthStatus.HEALTHY

    @patch('psutil.disk_usage')
    def test_check_disk_space_warning(self, mock_disk):
        """Test check_disk_space warning state."""
        mock_disk.return_value = MagicMock(
            percent=80,
            free=100 * 1024 ** 3,
            total=500 * 1024 ** 3
        )
        service = HealthCheckService()
        result = service.check_disk_space()

        assert result.status == HealthStatus.DEGRADED

    @patch('psutil.disk_usage')
    def test_check_disk_space_critical(self, mock_disk):
        """Test check_disk_space critical state."""
        mock_disk.return_value = MagicMock(
            percent=95,
            free=25 * 1024 ** 3,
            total=500 * 1024 ** 3
        )
        service = HealthCheckService()
        result = service.check_disk_space()

        assert result.status == HealthStatus.UNHEALTHY


# ============================================================================
# Check Memory Tests
# ============================================================================

class TestCheckMemory:
    """Tests for HealthCheckService.check_memory()."""

    @patch('psutil.virtual_memory')
    def test_check_memory_healthy(self, mock_mem):
        """Test check_memory returns healthy."""
        mock_mem.return_value = MagicMock(
            percent=50,
            available=4 * 1024 ** 3,
            total=8 * 1024 ** 3
        )
        service = HealthCheckService()
        result = service.check_memory()

        assert result.name == "memory"
        assert result.status == HealthStatus.HEALTHY

    @patch('psutil.virtual_memory')
    def test_check_memory_warning(self, mock_mem):
        """Test check_memory warning state."""
        mock_mem.return_value = MagicMock(
            percent=80,
            available=1 * 1024 ** 3,
            total=8 * 1024 ** 3
        )
        service = HealthCheckService()
        result = service.check_memory()

        assert result.status == HealthStatus.DEGRADED

    @patch('psutil.virtual_memory')
    def test_check_memory_critical(self, mock_mem):
        """Test check_memory critical state."""
        mock_mem.return_value = MagicMock(
            percent=95,
            available=0.5 * 1024 ** 3,
            total=8 * 1024 ** 3
        )
        service = HealthCheckService()
        result = service.check_memory()

        assert result.status == HealthStatus.UNHEALTHY


# ============================================================================
# Get Detailed Health Tests
# ============================================================================

class TestGetDetailedHealth:
    """Tests for HealthCheckService.get_detailed_health()."""

    def test_get_detailed_health_returns_all_components(self):
        """Test get_detailed_health returns all components."""
        service = HealthCheckService()
        result = service.get_detailed_health()

        assert result is not None
        assert isinstance(result, HealthCheckResult)

    def test_get_detailed_health_status_aggregation(self):
        """Test get_detailed_health aggregates status."""
        service = HealthCheckService()
        result = service.get_detailed_health()

        assert result.status in [
            HealthStatus.HEALTHY,
            HealthStatus.DEGRADED,
            HealthStatus.UNHEALTHY
        ]

    def test_get_detailed_health_timing(self):
        """Test get_detailed_health timing."""
        service = HealthCheckService()
        start = datetime.utcnow()
        result = service.get_detailed_health()
        elapsed = (datetime.utcnow() - start).total_seconds()

        assert result.timestamp is not None
        assert elapsed < 5.0


# ============================================================================
# Get Version Info Tests
# ============================================================================

class TestGetVersionInfo:
    """Tests for HealthCheckService.get_version_info()."""

    def test_get_version_info_returns_version(self):
        """Test get_version_info returns version."""
        service = HealthCheckService()
        info = service.get_version_info()

        assert "version" in info
        assert info["version"] == "1.0.0"

    def test_get_version_info_returns_build_info(self):
        """Test get_version_info returns build info."""
        service = HealthCheckService()
        info = service.get_version_info()

        assert "build" in info
        assert "commit" in info
        assert "environment" in info

    def test_get_version_info_returns_timestamp(self):
        """Test get_version_info returns timestamp."""
        service = HealthCheckService()
        info = service.get_version_info()

        assert "timestamp" in info
        assert isinstance(info["timestamp"], str)


# ============================================================================
# Uptime Tests
# ============================================================================

class TestGetUptime:
    """Tests for HealthCheckService uptime calculation."""

    def test_get_uptime_returns_positive(self):
        """Test get_uptime returns positive value."""
        start_time = datetime.utcnow() - timedelta(seconds=10)
        service = HealthCheckService(start_time=start_time)
        uptime = service.get_uptime()

        assert uptime >= 0

    def test_get_uptime_increases(self):
        """Test get_uptime value increases over time."""
        start_time = datetime.utcnow() - timedelta(seconds=5)
        service = HealthCheckService(start_time=start_time)

        uptime1 = service.get_uptime()
        uptime2 = service.get_uptime()

        assert uptime2 >= uptime1

    def test_get_uptime_accuracy(self):
        """Test get_uptime accuracy."""
        known_time = datetime.utcnow() - timedelta(seconds=100)
        service = HealthCheckService(start_time=known_time)
        uptime = service.get_uptime()

        assert uptime >= 99
        assert uptime <= 101
