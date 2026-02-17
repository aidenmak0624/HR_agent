"""Connection pooling optimization for PostgreSQL and Redis."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict

try:
    import psycopg2
    from psycopg2 import pool

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class PoolType(str, Enum):
    """Connection pool type enumeration."""

    POSTGRESQL = "postgresql"
    REDIS = "redis"
    HTTP = "http"


class PoolConfig(BaseModel):
    """Configuration for connection pool."""

    pool_type: PoolType = Field(..., description="Type of pool")
    min_connections: int = Field(default=2, ge=1, description="Minimum pool size")
    max_connections: int = Field(default=20, ge=1, description="Maximum pool size")
    max_overflow: int = Field(default=10, ge=0, description="Maximum overflow connections")
    pool_timeout: int = Field(default=30, ge=1, description="Connection timeout in seconds")
    pool_recycle: int = Field(
        default=3600, ge=60, description="Connection recycle interval in seconds"
    )
    echo: bool = Field(default=False, description="Enable connection echo logging")
    connection_string: str = Field(..., description="Connection string/URL")
    health_check_interval: int = Field(
        default=60, ge=10, description="Health check interval in seconds"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pool_type": "postgresql",
                "min_connections": 2,
                "max_connections": 20,
                "max_overflow": 10,
                "pool_timeout": 30,
                "pool_recycle": 3600,
                "echo": False,
                "connection_string": "postgresql://user:pass@localhost/dbname",
                "health_check_interval": 60,
            }
        }
    )


class PoolStats(BaseModel):
    """Statistics for a connection pool."""

    pool_type: PoolType = Field(..., description="Pool type")
    active_connections: int = Field(default=0, ge=0, description="Currently active connections")
    idle_connections: int = Field(default=0, ge=0, description="Idle connections")
    total_created: int = Field(default=0, ge=0, description="Total connections created")
    total_recycled: int = Field(default=0, ge=0, description="Total connections recycled")
    total_errors: int = Field(default=0, ge=0, description="Total connection errors")
    avg_wait_time: float = Field(default=0.0, ge=0.0, description="Average wait time in ms")
    peak_connections: int = Field(default=0, ge=0, description="Peak active connections")
    uptime_seconds: float = Field(default=0.0, ge=0.0, description="Pool uptime in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pool_type": "postgresql",
                "active_connections": 5,
                "idle_connections": 10,
                "total_created": 100,
                "total_recycled": 25,
                "total_errors": 2,
                "avg_wait_time": 5.5,
                "peak_connections": 15,
                "uptime_seconds": 3600.0,
            }
        }
    )


class ConnectionHealth(BaseModel):
    """Health status of a connection."""

    is_healthy: bool = Field(..., description="Connection health status")
    latency_ms: float = Field(default=0.0, ge=0.0, description="Latency in milliseconds")
    last_check: datetime = Field(
        default_factory=datetime.utcnow, description="Last health check time"
    )
    error_message: Optional[str] = Field(default=None, description="Error message if unhealthy")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_healthy": True,
                "latency_ms": 2.5,
                "last_check": "2025-02-06T10:30:00Z",
                "error_message": None,
            }
        }
    )


class _PoolInstance:
    """Internal pool instance wrapper."""

    def __init__(self, pool_type: PoolType, config: PoolConfig):
        self.pool_type = pool_type
        self.config = config
        self.pool = None
        self.active_connections: int = 0
        self.idle_connections: int = 0
        self.total_created: int = 0
        self.total_recycled: int = 0
        self.total_errors: int = 0
        self.wait_times: List[float] = []
        self.peak_connections: int = 0
        self.created_at: datetime = datetime.utcnow()
        self.last_health_check: datetime = datetime.utcnow()
        self._connection_timestamps: Dict[int, float] = {}

    def get_uptime_seconds(self) -> float:
        """Calculate pool uptime."""
        return (datetime.utcnow() - self.created_at).total_seconds()

    def get_avg_wait_time(self) -> float:
        """Get average wait time."""
        if not self.wait_times:
            return 0.0
        return sum(self.wait_times) / len(self.wait_times)


class ConnectionPoolManager:
    """Manages multiple connection pools for different systems."""

    def __init__(self, configs: List[PoolConfig]):
        """Initialize connection pool manager.

        Args:
            configs: List of pool configurations
        """
        self._pools: Dict[PoolType, _PoolInstance] = {}
        self._connection_locks: Dict[PoolType, object] = {}
        self._initialized_pools: Dict[PoolType, bool] = {}

        for config in configs:
            self._pools[config.pool_type] = _PoolInstance(config.pool_type, config)
            self._connection_locks[config.pool_type] = object()
            self._initialized_pools[config.pool_type] = False

        logger.info(f"Initialized ConnectionPoolManager with {len(configs)} pools")

    def initialize_pool(self, pool_type: PoolType) -> bool:
        """Initialize a specific pool.

        Args:
            pool_type: Type of pool to initialize

        Returns:
            True if successful, False otherwise
        """
        if pool_type not in self._pools:
            logger.error(f"Pool type {pool_type} not configured")
            return False

        if self._initialized_pools.get(pool_type, False):
            logger.debug(f"Pool {pool_type} already initialized")
            return True

        try:
            pool_instance = self._pools[pool_type]
            config = pool_instance.config

            if pool_type == PoolType.POSTGRESQL:
                if not PSYCOPG2_AVAILABLE:
                    logger.warning("psycopg2 not available, PostgreSQL pool cannot be initialized")
                    return False
                pool_instance.pool = psycopg2.pool.SimpleConnectionPool(
                    config.min_connections, config.max_connections, config.connection_string
                )
            elif pool_type == PoolType.REDIS:
                if not REDIS_AVAILABLE:
                    logger.warning("redis not available, Redis pool cannot be initialized")
                    return False
                pool_instance.pool = redis.ConnectionPool.from_url(
                    config.connection_string,
                    max_connections=config.max_connections,
                    socket_keepalive=True,
                    health_check_interval=config.health_check_interval,
                )
            elif pool_type == PoolType.HTTP:
                # HTTP pool is managed differently (no actual pool object)
                pool_instance.pool = {}
            else:
                logger.error(f"Unknown pool type: {pool_type}")
                return False

            pool_instance.idle_connections = config.min_connections
            self._initialized_pools[pool_type] = True
            logger.info(f"Successfully initialized {pool_type} pool")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize {pool_type} pool: {str(e)}")
            pool_instance.total_errors += 1
            return False

    @contextmanager
    def get_connection(self, pool_type: PoolType):
        """Get a connection from pool in context manager style.

        Args:
            pool_type: Type of pool

        Yields:
            Connection object

        Raises:
            RuntimeError: If pool not initialized or unavailable
        """
        if pool_type not in self._pools:
            raise RuntimeError(f"Pool type {pool_type} not configured")

        if not self._initialized_pools.get(pool_type, False):
            raise RuntimeError(f"Pool {pool_type} not initialized")

        pool_instance = self._pools[pool_type]
        connection = None
        wait_start = time.time()

        try:
            # Acquire connection
            if pool_type == PoolType.POSTGRESQL:
                connection = pool_instance.pool.getconn()
            elif pool_type == PoolType.REDIS:
                connection = redis.Redis(connection_pool=pool_instance.pool)
            elif pool_type == PoolType.HTTP:
                connection = {"type": "http", "id": str(uuid.uuid4())}

            wait_time = (time.time() - wait_start) * 1000
            pool_instance.wait_times.append(wait_time)
            if len(pool_instance.wait_times) > 1000:
                pool_instance.wait_times = pool_instance.wait_times[-500:]

            pool_instance.active_connections += 1
            pool_instance.total_created += 1
            if pool_instance.active_connections > pool_instance.peak_connections:
                pool_instance.peak_connections = pool_instance.active_connections
            pool_instance.idle_connections = max(0, pool_instance.idle_connections - 1)

            conn_id = id(connection)
            pool_instance._connection_timestamps[conn_id] = time.time()

            logger.debug(
                f"Acquired {pool_type} connection (active: {pool_instance.active_connections})"
            )

            yield connection

        except Exception as e:
            logger.error(f"Error getting {pool_type} connection: {str(e)}")
            pool_instance.total_errors += 1
            raise

        finally:
            if connection is not None:
                self.release_connection(pool_type, connection)

    def release_connection(self, pool_type: PoolType, connection: Any) -> bool:
        """Release connection back to pool.

        Args:
            pool_type: Type of pool
            connection: Connection to release

        Returns:
            True if successful, False otherwise
        """
        if pool_type not in self._pools:
            logger.error(f"Pool type {pool_type} not configured")
            return False

        try:
            pool_instance = self._pools[pool_type]
            conn_id = id(connection)

            if conn_id in pool_instance._connection_timestamps:
                del pool_instance._connection_timestamps[conn_id]

            if pool_type == PoolType.POSTGRESQL:
                pool_instance.pool.putconn(connection)
            elif pool_type == PoolType.REDIS:
                # Redis client handles its own release
                pass
            elif pool_type == PoolType.HTTP:
                pass

            pool_instance.active_connections = max(0, pool_instance.active_connections - 1)
            pool_instance.idle_connections += 1

            logger.debug(
                f"Released {pool_type} connection (active: {pool_instance.active_connections})"
            )
            return True

        except Exception as e:
            logger.error(f"Error releasing {pool_type} connection: {str(e)}")
            return False

    def health_check(
        self, pool_type: Optional[PoolType] = None
    ) -> Dict[PoolType, ConnectionHealth]:
        """Check health of pool(s).

        Args:
            pool_type: Specific pool to check, or None for all

        Returns:
            Dictionary mapping pool type to health status
        """
        pools_to_check = [pool_type] if pool_type else list(self._pools.keys())
        health_status: Dict[PoolType, ConnectionHealth] = {}

        for ptype in pools_to_check:
            if ptype not in self._pools:
                health_status[ptype] = ConnectionHealth(
                    is_healthy=False, error_message=f"Pool type {ptype} not configured"
                )
                continue

            pool_instance = self._pools[ptype]

            try:
                check_start = time.time()
                error_msg = None

                if ptype == PoolType.POSTGRESQL:
                    if not pool_instance.pool:
                        error_msg = "PostgreSQL pool not initialized"
                    else:
                        conn = None
                        try:
                            conn = pool_instance.pool.getconn()
                            cursor = conn.cursor()
                            cursor.execute("SELECT 1")
                            cursor.close()
                            pool_instance.pool.putconn(conn)
                        except Exception as e:
                            error_msg = str(e)
                            if conn:
                                pool_instance.pool.putconn(conn, close=True)

                elif ptype == PoolType.REDIS:
                    if not pool_instance.pool:
                        error_msg = "Redis pool not initialized"
                    else:
                        try:
                            client = redis.Redis(connection_pool=pool_instance.pool)
                            client.ping()
                        except Exception as e:
                            error_msg = str(e)

                elif ptype == PoolType.HTTP:
                    # HTTP pool is always healthy if initialized
                    if not pool_instance.pool:
                        error_msg = "HTTP pool not initialized"

                latency = (time.time() - check_start) * 1000
                is_healthy = error_msg is None

                pool_instance.last_health_check = datetime.utcnow()

                health_status[ptype] = ConnectionHealth(
                    is_healthy=is_healthy,
                    latency_ms=latency,
                    last_check=pool_instance.last_health_check,
                    error_message=error_msg,
                )

            except Exception as e:
                logger.error(f"Health check failed for {ptype}: {str(e)}")
                pool_instance.total_errors += 1
                health_status[ptype] = ConnectionHealth(is_healthy=False, error_message=str(e))

        return health_status

    def get_pool_stats(self, pool_type: Optional[PoolType] = None) -> Dict[PoolType, PoolStats]:
        """Get statistics for pool(s).

        Args:
            pool_type: Specific pool to get stats for, or None for all

        Returns:
            Dictionary mapping pool type to stats
        """
        pools_to_check = [pool_type] if pool_type else list(self._pools.keys())
        stats: Dict[PoolType, PoolStats] = {}

        for ptype in pools_to_check:
            if ptype not in self._pools:
                continue

            pool_instance = self._pools[ptype]

            stats[ptype] = PoolStats(
                pool_type=ptype,
                active_connections=pool_instance.active_connections,
                idle_connections=pool_instance.idle_connections,
                total_created=pool_instance.total_created,
                total_recycled=pool_instance.total_recycled,
                total_errors=pool_instance.total_errors,
                avg_wait_time=pool_instance.get_avg_wait_time(),
                peak_connections=pool_instance.peak_connections,
                uptime_seconds=pool_instance.get_uptime_seconds(),
            )

        return stats

    def resize_pool(self, pool_type: PoolType, new_max: int) -> bool:
        """Resize pool maximum connections.

        Args:
            pool_type: Type of pool to resize
            new_max: New maximum connections

        Returns:
            True if successful, False otherwise
        """
        if pool_type not in self._pools:
            logger.error(f"Pool type {pool_type} not configured")
            return False

        if new_max < 1:
            logger.error("new_max must be at least 1")
            return False

        try:
            pool_instance = self._pools[pool_type]
            pool_instance.config.max_connections = new_max

            if pool_type == PoolType.POSTGRESQL and pool_instance.pool:
                # Psycopg2 pools don't support resizing, need to recreate
                old_pool = pool_instance.pool
                pool_instance.pool = psycopg2.pool.SimpleConnectionPool(
                    pool_instance.config.min_connections,
                    new_max,
                    pool_instance.config.connection_string,
                )
                # Close old pool connections
                old_pool.closeall()
            elif pool_type == PoolType.REDIS and pool_instance.pool:
                pool_instance.pool.max_connections = new_max

            logger.info(f"Resized {pool_type} pool to max {new_max} connections")
            return True

        except Exception as e:
            logger.error(f"Failed to resize {pool_type} pool: {str(e)}")
            return False

    def drain_pool(self, pool_type: PoolType) -> int:
        """Drain all connections from pool.

        Args:
            pool_type: Type of pool to drain

        Returns:
            Number of connections drained
        """
        if pool_type not in self._pools:
            logger.error(f"Pool type {pool_type} not configured")
            return 0

        try:
            pool_instance = self._pools[pool_type]
            drained = pool_instance.idle_connections

            if pool_type == PoolType.POSTGRESQL and pool_instance.pool:
                pool_instance.pool.closeall()
            elif pool_type == PoolType.REDIS and pool_instance.pool:
                pool_instance.pool.disconnect()

            pool_instance.idle_connections = 0
            pool_instance.total_recycled += drained
            self._initialized_pools[pool_type] = False

            logger.info(f"Drained {drained} connections from {pool_type} pool")
            return drained

        except Exception as e:
            logger.error(f"Error draining {pool_type} pool: {str(e)}")
            return 0

    def shutdown(self) -> bool:
        """Gracefully shutdown all pools.

        Returns:
            True if all pools shut down successfully
        """
        all_success = True

        for pool_type in list(self._pools.keys()):
            try:
                self.drain_pool(pool_type)
                logger.info(f"Successfully shut down {pool_type} pool")
            except Exception as e:
                logger.error(f"Error shutting down {pool_type} pool: {str(e)}")
                all_success = False

        return all_success

    def _create_connection(self, pool_type: PoolType) -> Optional[Any]:
        """Create a new connection (internal method).

        Args:
            pool_type: Type of pool

        Returns:
            Connection object or None on error
        """
        if pool_type not in self._pools:
            return None

        try:
            pool_instance = self._pools[pool_type]
            config = pool_instance.config

            if pool_type == PoolType.POSTGRESQL:
                if not PSYCOPG2_AVAILABLE:
                    return None
                return psycopg2.connect(config.connection_string)
            elif pool_type == PoolType.REDIS:
                if not REDIS_AVAILABLE:
                    return None
                return redis.from_url(config.connection_string)
            elif pool_type == PoolType.HTTP:
                return {"type": "http", "id": str(uuid.uuid4())}

        except Exception as e:
            logger.error(f"Error creating {pool_type} connection: {str(e)}")
            return None

    def _validate_connection(self, pool_type: PoolType, connection: Any) -> bool:
        """Validate connection health (internal method).

        Args:
            pool_type: Type of pool
            connection: Connection to validate

        Returns:
            True if valid, False otherwise
        """
        if connection is None:
            return False

        try:
            if pool_type == PoolType.POSTGRESQL:
                cursor = connection.cursor()
                cursor.execute("SELECT 1")
                cursor.close()
                return True
            elif pool_type == PoolType.REDIS:
                connection.ping()
                return True
            elif pool_type == PoolType.HTTP:
                return isinstance(connection, dict) and connection.get("type") == "http"

        except Exception as e:
            logger.debug(f"Connection validation failed: {str(e)}")
            return False

    def get_optimal_pool_size(self, pool_type: PoolType) -> dict:
        """Get recommendation for optimal pool size based on metrics.

        Args:
            pool_type: Type of pool

        Returns:
            Dictionary with size recommendations
        """
        if pool_type not in self._pools:
            return {"error": f"Pool type {pool_type} not configured"}

        try:
            pool_instance = self._pools[pool_type]
            stats = self.get_pool_stats(pool_type)[pool_type]

            # Calculate recommendation based on peak usage and wait times
            peak_ratio = stats.peak_connections / pool_instance.config.max_connections
            avg_wait = stats.avg_wait_time

            recommendation = {
                "pool_type": pool_type,
                "current_max": pool_instance.config.max_connections,
                "peak_connections": stats.peak_connections,
                "peak_ratio": peak_ratio,
                "avg_wait_time_ms": avg_wait,
                "recommended_max": max(
                    pool_instance.config.min_connections,
                    int(stats.peak_connections * 1.2),  # 20% buffer above peak
                ),
                "action": "increase"
                if peak_ratio > 0.8
                else "maintain"
                if peak_ratio > 0.5
                else "decrease",
            }

            return recommendation

        except Exception as e:
            logger.error(f"Error getting optimal pool size for {pool_type}: {str(e)}")
            return {"error": str(e)}

    def get_status(self) -> dict:
        """Get overall health status of all pools.

        Returns:
            Dictionary with overall status information
        """
        try:
            all_stats = self.get_pool_stats()
            all_health = self.health_check()

            status = {
                "timestamp": datetime.utcnow().isoformat(),
                "pools": {},
                "overall_healthy": True,
            }

            for pool_type in self._pools.keys():
                stats = all_stats.get(pool_type)
                health = all_health.get(pool_type)

                if stats and health:
                    status["pools"][pool_type.value] = {
                        "healthy": health.is_healthy,
                        "latency_ms": health.latency_ms,
                        "active_connections": stats.active_connections,
                        "idle_connections": stats.idle_connections,
                        "peak_connections": stats.peak_connections,
                        "error_rate": stats.total_errors / max(1, stats.total_created),
                        "avg_wait_time_ms": stats.avg_wait_time,
                        "uptime_seconds": stats.uptime_seconds,
                    }

                    if not health.is_healthy:
                        status["overall_healthy"] = False

            return status

        except Exception as e:
            logger.error(f"Error getting pool status: {str(e)}")
            return {"error": str(e), "overall_healthy": False}
