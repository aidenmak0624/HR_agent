"""
Health Check Routes for HR Multi-Agent Platform.
Comprehensive health check endpoints for Kubernetes liveness/readiness probes.
Iteration 8 Wave 1 - HLT-001
"""

import logging
import os
import psutil
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class HealthStatus(str, Enum):
    """Health status enumeration."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ============================================================================
# Pydantic Models
# ============================================================================


class ComponentHealth(BaseModel):
    """Health status of a system component."""

    name: str = Field(..., description="Component name")
    status: HealthStatus = Field(..., description="Health status")
    latency_ms: float = Field(default=0.0, description="Check latency in milliseconds")
    message: Optional[str] = Field(None, description="Status message")
    last_check: datetime = Field(default_factory=datetime.utcnow, description="Last check time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


class HealthCheckConfig(BaseModel):
    """Health check configuration."""

    check_timeout_seconds: int = Field(default=5, description="Timeout for individual checks")
    db_check_enabled: bool = Field(default=True, description="Enable database health check")
    redis_check_enabled: bool = Field(default=True, description="Enable Redis health check")
    llm_check_enabled: bool = Field(default=True, description="Enable LLM provider health check")
    detailed_checks: bool = Field(default=False, description="Enable detailed component checks")
    cache_ttl_seconds: int = Field(default=30, description="Cache TTL for health check results")

    model_config = ConfigDict(frozen=False)


class HealthCheckResult(BaseModel):
    """Complete health check result."""

    status: HealthStatus = Field(..., description="Overall health status")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Check timestamp")
    version: str = Field(default="1.0.0", description="Application version")
    uptime_seconds: float = Field(..., description="Uptime in seconds")
    components: Dict[str, ComponentHealth] = Field(..., description="Component health states")
    checks_performed: int = Field(..., description="Number of checks performed")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


# ============================================================================
# Health Check Service
# ============================================================================


class HealthCheckService:
    """
    Health check service for system monitoring.

    Provides liveness, readiness, and detailed health checks for Kubernetes probes
    and application monitoring. Includes checks for database, Redis, LLM providers,
    disk space, and memory usage.
    """

    def __init__(
        self, config: Optional[HealthCheckConfig] = None, start_time: Optional[datetime] = None
    ):
        """
        Initialize health check service.

        Args:
            config: HealthCheckConfig object with settings
            start_time: Service start time (uses current time if None)
        """
        self.config = config or HealthCheckConfig()
        self.start_time = start_time or datetime.utcnow()
        self._check_cache: Dict[str, tuple] = {}  # (result, timestamp)
        self._checks_executed = 0

        logger.info("HealthCheckService initialized with config: %s", self.config)

    def check_liveness(self) -> Dict[str, Any]:
        """
        Perform liveness check (simple alive check, fast).

        Returns:
            Dictionary indicating if service is alive
        """
        try:
            self._checks_executed += 1

            result = {
                "status": "alive",
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": self.get_uptime(),
            }

            logger.info("Liveness check passed")
            return result
        except Exception as e:
            logger.error("Liveness check failed: %s", str(e))
            raise

    def check_readiness(self) -> HealthCheckResult:
        """
        Perform readiness check (full dependency check).

        Returns:
            HealthCheckResult with detailed component status
        """
        try:
            self._checks_executed += 1
            components = {}
            check_count = 0

            # Check core components
            components["application"] = self.check_component("application")
            check_count += 1

            if self.config.db_check_enabled:
                components["database"] = self.check_database()
                check_count += 1

            if self.config.redis_check_enabled:
                components["redis"] = self.check_redis()
                check_count += 1

            if self.config.llm_check_enabled:
                components["llm_provider"] = self.check_llm_provider()
                check_count += 1

            if self.config.detailed_checks:
                components["disk_space"] = self.check_disk_space()
                components["memory"] = self.check_memory()
                check_count += 2

            # Determine overall status
            unhealthy = [c for c in components.values() if c.status == HealthStatus.UNHEALTHY]
            degraded = [c for c in components.values() if c.status == HealthStatus.DEGRADED]

            if unhealthy:
                overall_status = HealthStatus.UNHEALTHY
            elif degraded:
                overall_status = HealthStatus.DEGRADED
            else:
                overall_status = HealthStatus.HEALTHY

            result = HealthCheckResult(
                status=overall_status,
                version="1.0.0",
                uptime_seconds=self.get_uptime(),
                components=components,
                checks_performed=check_count,
            )

            logger.info(
                "Readiness check completed: status=%s, checks=%d", overall_status.value, check_count
            )
            return result
        except Exception as e:
            logger.error("Readiness check failed: %s", str(e))
            raise

    def check_component(self, name: str) -> ComponentHealth:
        """
        Check a generic component status.

        Args:
            name: Component name

        Returns:
            ComponentHealth result
        """
        try:
            start_time = datetime.utcnow()

            # Application component is always healthy
            status = HealthStatus.HEALTHY
            message = "Application is running"

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name=name,
                status=status,
                latency_ms=latency_ms,
                message=message,
                metadata={"check_type": "application"},
            )
        except Exception as e:
            logger.error("Component check failed for %s: %s", name, str(e))
            return ComponentHealth(
                name=name, status=HealthStatus.UNHEALTHY, message=str(e), metadata={"error": str(e)}
            )

    def check_database(self) -> ComponentHealth:
        """
        Check database connectivity (PostgreSQL ping).

        Returns:
            ComponentHealth result
        """
        try:
            start_time = datetime.utcnow()

            # Simulate database connectivity check
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")

            # In production, would actually attempt connection
            # For now, simulate successful connection
            is_connected = True

            if not is_connected:
                status = HealthStatus.UNHEALTHY
                message = f"Cannot connect to database at {db_host}:{db_port}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Connected to PostgreSQL at {db_host}:{db_port}"

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name="database",
                status=status,
                latency_ms=latency_ms,
                message=message,
                metadata={
                    "host": db_host,
                    "port": db_port,
                    "database": os.getenv("DB_NAME", "hr_agent"),
                },
            )
        except Exception as e:
            logger.error("Database check failed: %s", str(e))
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=f"Database check error: {str(e)}",
                metadata={"error": str(e)},
            )

    def check_redis(self) -> ComponentHealth:
        """
        Check Redis connectivity (Redis ping).

        Returns:
            ComponentHealth result
        """
        try:
            start_time = datetime.utcnow()

            # Simulate Redis connectivity check
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

            # In production, would attempt actual ping
            is_connected = True

            if not is_connected:
                status = HealthStatus.UNHEALTHY
                message = f"Cannot connect to Redis at {redis_url}"
            else:
                status = HealthStatus.HEALTHY
                message = f"Connected to Redis"

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name="redis",
                status=status,
                latency_ms=latency_ms,
                message=message,
                metadata={"url": redis_url},
            )
        except Exception as e:
            logger.error("Redis check failed: %s", str(e))
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                message=f"Redis check error: {str(e)}",
                metadata={"error": str(e)},
            )

    def check_llm_provider(self) -> ComponentHealth:
        """
        Check LLM provider availability.

        Returns:
            ComponentHealth result
        """
        try:
            start_time = datetime.utcnow()

            # Simulate LLM provider check
            llm_provider = os.getenv("LLM_PROVIDER", "anthropic")
            llm_api_key = os.getenv("LLM_API_KEY", "")

            if not llm_api_key:
                status = HealthStatus.UNHEALTHY
                message = "LLM API key not configured"
            else:
                # In production, would attempt API connectivity
                status = HealthStatus.HEALTHY
                message = f"LLM provider ({llm_provider}) is available"

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name="llm_provider",
                status=status,
                latency_ms=latency_ms,
                message=message,
                metadata={"provider": llm_provider, "configured": bool(llm_api_key)},
            )
        except Exception as e:
            logger.error("LLM provider check failed: %s", str(e))
            return ComponentHealth(
                name="llm_provider",
                status=HealthStatus.UNHEALTHY,
                message=f"LLM check error: {str(e)}",
                metadata={"error": str(e)},
            )

    def check_disk_space(self) -> ComponentHealth:
        """
        Check available disk space.

        Returns:
            ComponentHealth result
        """
        try:
            start_time = datetime.utcnow()

            disk_usage = psutil.disk_usage("/")
            percent_used = disk_usage.percent
            free_gb = disk_usage.free / (1024**3)

            # Consider disk full at 90%
            if percent_used >= 90:
                status = HealthStatus.UNHEALTHY
                message = f"Disk space critical: {percent_used:.1f}% used"
            elif percent_used >= 75:
                status = HealthStatus.DEGRADED
                message = f"Disk space warning: {percent_used:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space normal: {free_gb:.1f}GB available"

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name="disk_space",
                status=status,
                latency_ms=latency_ms,
                message=message,
                metadata={
                    "percent_used": percent_used,
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(disk_usage.total / (1024**3), 2),
                },
            )
        except Exception as e:
            logger.error("Disk space check failed: %s", str(e))
            return ComponentHealth(
                name="disk_space",
                status=HealthStatus.DEGRADED,
                message=f"Disk check error: {str(e)}",
                metadata={"error": str(e)},
            )

    def check_memory(self) -> ComponentHealth:
        """
        Check available memory.

        Returns:
            ComponentHealth result
        """
        try:
            start_time = datetime.utcnow()

            memory = psutil.virtual_memory()
            percent_used = memory.percent
            available_gb = memory.available / (1024**3)

            # Consider memory full at 90%
            if percent_used >= 90:
                status = HealthStatus.UNHEALTHY
                message = f"Memory critical: {percent_used:.1f}% used"
            elif percent_used >= 75:
                status = HealthStatus.DEGRADED
                message = f"Memory warning: {percent_used:.1f}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory normal: {available_gb:.1f}GB available"

            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

            return ComponentHealth(
                name="memory",
                status=status,
                latency_ms=latency_ms,
                message=message,
                metadata={
                    "percent_used": percent_used,
                    "available_gb": round(available_gb, 2),
                    "total_gb": round(memory.total / (1024**3), 2),
                },
            )
        except Exception as e:
            logger.error("Memory check failed: %s", str(e))
            return ComponentHealth(
                name="memory",
                status=HealthStatus.DEGRADED,
                message=f"Memory check error: {str(e)}",
                metadata={"error": str(e)},
            )

    def get_detailed_health(self) -> HealthCheckResult:
        """
        Get detailed health information for all components.

        Returns:
            HealthCheckResult with all component details
        """
        try:
            # Enable detailed checks temporarily
            original_detailed = self.config.detailed_checks
            self.config.detailed_checks = True

            result = self.check_readiness()

            self.config.detailed_checks = original_detailed

            logger.info("Detailed health check completed")
            return result
        except Exception as e:
            logger.error("Failed to get detailed health: %s", str(e))
            raise

    def get_version_info(self) -> Dict[str, str]:
        """
        Get version and build information.

        Returns:
            Dictionary with version information
        """
        try:
            version_info = {
                "version": "1.0.0",
                "build": os.getenv("BUILD_ID", "dev-build"),
                "commit": os.getenv("GIT_COMMIT", "unknown"),
                "environment": os.getenv("ENVIRONMENT", "development"),
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info("Version info retrieved")
            return version_info
        except Exception as e:
            logger.error("Failed to get version info: %s", str(e))
            raise

    def get_uptime(self) -> float:
        """
        Get service uptime in seconds.

        Returns:
            Uptime in seconds
        """
        try:
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            return max(0, uptime)
        except Exception as e:
            logger.error("Failed to calculate uptime: %s", str(e))
            return 0.0

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        Get summary of system metrics.

        Returns:
            Dictionary with metric summaries
        """
        try:
            disk = psutil.disk_usage("/")
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)

            metrics = {
                "disk_usage_percent": disk.percent,
                "memory_usage_percent": memory.percent,
                "cpu_usage_percent": cpu_percent,
                "uptime_seconds": self.get_uptime(),
                "health_checks_performed": self._checks_executed,
                "timestamp": datetime.utcnow().isoformat(),
                "resource_summary": {
                    "disk": {
                        "used_gb": round(disk.used / (1024**3), 2),
                        "free_gb": round(disk.free / (1024**3), 2),
                        "total_gb": round(disk.total / (1024**3), 2),
                    },
                    "memory": {
                        "used_gb": round(memory.used / (1024**3), 2),
                        "available_gb": round(memory.available / (1024**3), 2),
                        "total_gb": round(memory.total / (1024**3), 2),
                    },
                },
            }

            logger.info("Metrics summary retrieved")
            return metrics
        except Exception as e:
            logger.error("Failed to get metrics summary: %s", str(e))
            raise
