"""
Rate Limiting Middleware for HR Multi-Agent Platform.
Token bucket rate limiting with Redis backend and in-memory fallback.
Iteration 6 - SEC-003
"""

import logging
import time
from typing import Dict, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class RateLimitConfig(BaseModel):
    """Rate limiting configuration model."""

    requests_per_minute: int = Field(
        default=60, description="Requests allowed per minute"
    )
    requests_per_hour: int = Field(
        default=1000, description="Requests allowed per hour"
    )
    llm_requests_per_minute: int = Field(
        default=10, description="LLM requests allowed per minute"
    )
    burst_multiplier: float = Field(
        default=1.5, description="Multiplier for burst allowance"
    )
    enable_redis: bool = Field(default=True, description="Enable Redis backend")
    redis_url: str = Field(
        default="redis://localhost:6379/0", description="Redis URL"
    )
    fallback_to_memory: bool = Field(
        default=True, description="Fallback to in-memory if Redis unavailable"
    )

    model_config = ConfigDict(frozen=False)


class RateLimitResult(BaseModel):
    """Result of rate limit check."""

    allowed: bool = Field(description="Whether request is allowed")
    remaining: int = Field(description="Remaining requests in window")
    limit: int = Field(description="Request limit")
    reset_at: datetime = Field(description="When limit resets")
    retry_after: int = Field(default=0, description="Seconds to wait before retry")

    model_config = ConfigDict(frozen=False)


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float) -> None:
        """
        Initialize token bucket.

        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens to add per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()

        logger.debug(
            "Token bucket created",
            extra={"capacity": capacity, "refill_rate": refill_rate},
        )

    def consume(self, tokens: int = 1) -> bool:
        """
        Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens consumed, False otherwise
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def get_remaining(self) -> int:
        """
        Get current token count.

        Returns:
            Number of remaining tokens
        """
        self._refill()
        return int(self.tokens)

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate

        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class RateLimiter:
    """
    Rate limiting middleware.
    Token bucket rate limiting with Redis backend and in-memory fallback.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None) -> None:
        """
        Initialize rate limiter.

        Args:
            config: Rate limiting configuration (uses defaults if None)
        """
        self.config = config or RateLimitConfig()
        self.buckets: Dict[str, Dict[str, TokenBucket]] = {}
        self.redis_client = None
        self.total_requests: int = 0
        self.total_blocked: int = 0
        self.active_users: set = set()

        # Try to initialize Redis if enabled
        if self.config.enable_redis:
            try:
                import redis

                self.redis_client = redis.from_url(self.config.redis_url)
                self.redis_client.ping()
                logger.info("Redis client initialized for rate limiting")
            except Exception as e:
                logger.warning(
                    f"Failed to connect to Redis: {str(e)}",
                    extra={"redis_url": self.config.redis_url},
                )
                if not self.config.fallback_to_memory:
                    raise

        logger.info(
            "Rate limiter initialized",
            extra={
                "requests_per_minute": self.config.requests_per_minute,
                "requests_per_hour": self.config.requests_per_hour,
                "redis_enabled": self.redis_client is not None,
            },
        )

    def check_rate_limit(
        self, user_id: str, endpoint: str = "default"
    ) -> RateLimitResult:
        """
        Check rate limit for user on endpoint.

        Args:
            user_id: User identifier
            endpoint: API endpoint identifier

        Returns:
            RateLimitResult with allow/deny decision
        """
        self.total_requests += 1
        self.active_users.add(user_id)

        # Try Redis first if available
        if self.redis_client:
            try:
                return self._check_redis_limit(
                    f"rate_limit:{user_id}:{endpoint}",
                    self.config.requests_per_minute,
                    60,
                )
            except Exception as e:
                logger.warning(
                    f"Redis rate limit check failed: {str(e)}",
                    extra={"user_id": user_id},
                )
                if not self.config.fallback_to_memory:
                    raise

        # Fall back to in-memory token bucket
        bucket = self._get_or_create_bucket(user_id, endpoint)
        allowed = bucket.consume(1)

        reset_at = datetime.now() + timedelta(
            seconds=60 / self.config.requests_per_minute
        )
        remaining = bucket.get_remaining()

        if not allowed:
            self.total_blocked += 1
            logger.warning(
                "Rate limit exceeded",
                extra={"user_id": user_id, "endpoint": endpoint},
            )

        return RateLimitResult(
            allowed=allowed,
            remaining=max(0, remaining),
            limit=self.config.requests_per_minute,
            reset_at=reset_at,
            retry_after=0 if allowed else 60,
        )

    def check_llm_rate_limit(self, user_id: str) -> RateLimitResult:
        """
        Check LLM-specific rate limit for user.

        Args:
            user_id: User identifier

        Returns:
            RateLimitResult for LLM endpoint
        """
        return self.check_rate_limit(user_id, "llm")

    def _get_or_create_bucket(self, user_id: str, endpoint: str) -> TokenBucket:
        """
        Get or create token bucket for user and endpoint.

        Args:
            user_id: User identifier
            endpoint: Endpoint identifier

        Returns:
            TokenBucket instance
        """
        if user_id not in self.buckets:
            self.buckets[user_id] = {}

        if endpoint not in self.buckets[user_id]:
            # Determine capacity and refill rate based on endpoint
            if endpoint == "llm":
                capacity = int(
                    self.config.llm_requests_per_minute
                    * self.config.burst_multiplier
                )
                refill_rate = self.config.llm_requests_per_minute / 60.0
            else:
                capacity = int(
                    self.config.requests_per_minute * self.config.burst_multiplier
                )
                refill_rate = self.config.requests_per_minute / 60.0

            self.buckets[user_id][endpoint] = TokenBucket(capacity, refill_rate)

        return self.buckets[user_id][endpoint]

    def _check_redis_limit(
        self, key: str, limit: int, window: int
    ) -> RateLimitResult:
        """
        Check rate limit using Redis.

        Args:
            key: Redis key
            limit: Request limit
            window: Time window in seconds

        Returns:
            RateLimitResult
        """
        try:
            pipe = self.redis_client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            results = pipe.execute()

            current_count = results[0]
            allowed = current_count <= limit
            remaining = max(0, limit - current_count)

            if not allowed:
                self.total_blocked += 1

            reset_at = datetime.now() + timedelta(seconds=window)

            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                limit=limit,
                reset_at=reset_at,
                retry_after=window if not allowed else 0,
            )
        except Exception as e:
            logger.error(f"Redis limit check error: {str(e)}")
            raise

    def reset_user(self, user_id: str) -> None:
        """
        Reset rate limit for user.

        Args:
            user_id: User identifier
        """
        if user_id in self.buckets:
            del self.buckets[user_id]

        if self.redis_client:
            try:
                pattern = f"rate_limit:{user_id}:*"
                for key in self.redis_client.scan_iter(match=pattern):
                    self.redis_client.delete(key)
            except Exception as e:
                logger.warning(f"Failed to reset Redis limits: {str(e)}")

        logger.info("User rate limit reset", extra={"user_id": user_id})

    def get_usage(self, user_id: str) -> Dict[str, any]:
        """
        Get usage statistics for user.

        Args:
            user_id: User identifier

        Returns:
            Dictionary with usage statistics
        """
        usage = {}

        if user_id in self.buckets:
            for endpoint, bucket in self.buckets[user_id].items():
                usage[endpoint] = {
                    "remaining": bucket.get_remaining(),
                    "capacity": bucket.capacity,
                    "refill_rate": bucket.refill_rate,
                }

        return usage

    def get_stats(self) -> Dict[str, any]:
        """
        Get rate limiter statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "total_requests": self.total_requests,
            "total_blocked": self.total_blocked,
            "active_users": len(self.active_users),
            "block_rate": (
                self.total_blocked / self.total_requests
                if self.total_requests > 0
                else 0
            ),
            "redis_enabled": self.redis_client is not None,
        }

    def is_allowed(self, key: str, limit: Optional[int] = None) -> tuple:
        """Check if request is allowed (compatibility with simple rate limiter).

        Args:
            key: Identifier (IP address or user_id)
            limit: Override the default limit for this request

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if limit is None:
            limit = self.config.requests_per_minute

        result = self.check_rate_limit(key, "default")
        return result.allowed, result.remaining


# Global instance for simple use cases
_default_rate_limiter = None


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Get or create the global rate limiter instance.

    Args:
        config: Optional rate limit configuration

    Returns:
        The global RateLimiter instance
    """
    global _default_rate_limiter

    if _default_rate_limiter is None:
        _default_rate_limiter = RateLimiter(config)

    return _default_rate_limiter
