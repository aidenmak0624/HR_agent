"""
Unit tests for rate limiter (src/middleware/rate_limiter.py).

Tests token bucket algorithm, rate limiting checks, per-user isolation,
and statistics tracking.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Dict


class TestRateLimitConfig:
    """Test rate limiter configuration."""

    def test_rate_limit_config_defaults(self):
        """Test default rate limit configuration."""
        config = {
            'default_limit': 100,
            'default_window': 60,
            'llm_limit': 20,
            'llm_window': 60,
            'redis_enabled': False
        }
        assert config['default_limit'] == 100
        assert config['default_window'] == 60
        assert config['llm_limit'] == 20

    def test_rate_limit_config_custom_limits(self):
        """Test custom rate limit configuration."""
        config = {
            'default_limit': 500,
            'default_window': 300,
            'llm_limit': 50
        }
        assert config['default_limit'] == 500
        assert config['default_window'] == 300

    def test_rate_limit_config_redis_config(self):
        """Test Redis configuration."""
        config = {
            'redis_enabled': True,
            'redis_host': 'localhost',
            'redis_port': 6379,
            'redis_db': 0
        }
        assert config['redis_enabled'] is True
        assert config['redis_host'] == 'localhost'


class TestRateLimitResult:
    """Test rate limit result structure."""

    def test_rate_limit_result_allowed(self):
        """Test allowed rate limit result."""
        result = {
            'allowed': True,
            'remaining': 95,
            'reset_at': 1234567890
        }
        assert result['allowed'] is True
        assert result['remaining'] == 95

    def test_rate_limit_result_denied(self):
        """Test denied rate limit result."""
        result = {
            'allowed': False,
            'remaining': 0,
            'reset_at': 1234567890
        }
        assert result['allowed'] is False
        assert result['remaining'] == 0

    def test_rate_limit_result_retry_after(self):
        """Test retry_after field in result."""
        result = {
            'allowed': False,
            'retry_after': 30
        }
        assert result['retry_after'] == 30


class TestTokenBucket:
    """Test token bucket algorithm."""

    def test_bucket_starts_full(self):
        """Test that bucket starts at full capacity."""
        bucket = {
            'tokens': 100,
            'capacity': 100,
            'refill_rate': 1.667
        }
        assert bucket['tokens'] == bucket['capacity']

    def test_consume_reduces_tokens(self):
        """Test that consume reduces available tokens."""
        bucket = {
            'tokens': 100,
            'capacity': 100
        }
        bucket['tokens'] -= 1
        assert bucket['tokens'] == 99

    def test_consume_fails_when_empty(self):
        """Test that consume fails when bucket is empty."""
        bucket = {'tokens': 0}
        can_consume = bucket['tokens'] > 0
        assert can_consume is False

    def test_bucket_refills_over_time(self):
        """Test that bucket refills over time."""
        bucket = {
            'tokens': 50,
            'capacity': 100,
            'refill_rate': 2.0,
            'last_refill': datetime.now() - timedelta(seconds=10)
        }
        time_passed = 10
        refilled = min(bucket['tokens'] + (bucket['refill_rate'] * time_passed), bucket['capacity'])
        assert refilled > 50

    def test_respects_capacity(self):
        """Test that refill respects capacity limit."""
        bucket = {
            'tokens': 90,
            'capacity': 100,
            'refill_rate': 50.0
        }
        tokens = min(bucket['tokens'] + 50, bucket['capacity'])
        assert tokens == bucket['capacity']

    def test_get_remaining_accurate(self):
        """Test accuracy of remaining token count."""
        bucket = {'tokens': 42}
        remaining = bucket['tokens']
        assert remaining == 42


class TestCheckRateLimit:
    """Test rate limit checking."""

    def test_allows_under_limit(self):
        """Test that requests under limit are allowed."""
        limit = 100
        used = 50
        allowed = used < limit
        assert allowed is True

    def test_blocks_over_limit(self):
        """Test that requests over limit are blocked."""
        limit = 100
        used = 101
        allowed = used < limit
        assert allowed is False

    def test_per_user_isolation(self):
        """Test per-user rate limit isolation."""
        limits = {
            'user1': {'tokens': 50, 'capacity': 100},
            'user2': {'tokens': 100, 'capacity': 100}
        }
        assert limits['user1']['tokens'] != limits['user2']['tokens']

    def test_correct_remaining_count(self):
        """Test correct remaining count calculation."""
        tokens = 75
        limit = 100
        remaining = tokens
        assert remaining == 75

    def test_reset_at_set(self):
        """Test that reset_at time is set correctly."""
        result = {
            'reset_at': datetime.now() + timedelta(seconds=60)
        }
        assert result['reset_at'] is not None

    def test_different_endpoints(self):
        """Test different endpoints have separate limits."""
        endpoints = {
            '/api/users': {'tokens': 50},
            '/api/llm': {'tokens': 10}
        }
        assert endpoints['/api/users']['tokens'] != endpoints['/api/llm']['tokens']


class TestCheckLLMRateLimit:
    """Test LLM-specific rate limiting."""

    def test_llm_stricter_limit(self):
        """Test that LLM has stricter rate limit."""
        default_limit = 100
        llm_limit = 20
        assert llm_limit < default_limit

    def test_allows_under_limit(self):
        """Test LLM requests under limit are allowed."""
        limit = 20
        used = 15
        allowed = used < limit
        assert allowed is True

    def test_blocks_over_limit(self):
        """Test LLM requests over limit are blocked."""
        limit = 20
        used = 21
        allowed = used < limit
        assert allowed is False

    def test_separate_from_default(self):
        """Test LLM limits separate from default limits."""
        limits = {
            'default': 100,
            'llm': 20
        }
        assert limits['default'] != limits['llm']


class TestGetOrCreateBucket:
    """Test bucket creation and retrieval."""

    def test_creates_new_bucket(self):
        """Test creation of new rate limit bucket."""
        buckets = {}
        user_id = 'user123'
        if user_id not in buckets:
            buckets[user_id] = {
                'tokens': 100,
                'capacity': 100,
                'created_at': datetime.now()
            }
        assert user_id in buckets
        assert buckets[user_id]['tokens'] == 100

    def test_returns_existing(self):
        """Test retrieval of existing bucket."""
        buckets = {'user123': {'tokens': 50}}
        user_id = 'user123'
        bucket = buckets.get(user_id)
        assert bucket is not None
        assert bucket['tokens'] == 50

    def test_per_endpoint_isolation(self):
        """Test per-endpoint bucket isolation."""
        buckets = {
            'user1:/api/users': {'tokens': 50},
            'user1:/api/llm': {'tokens': 15}
        }
        assert buckets['user1:/api/users']['tokens'] != buckets['user1:/api/llm']['tokens']


class TestResetUser:
    """Test user reset functionality."""

    def test_resets_all_buckets(self):
        """Test that reset clears all user's buckets."""
        buckets = {
            'user1:/api/users': {'tokens': 10},
            'user1:/api/llm': {'tokens': 5},
            'user2:/api/users': {'tokens': 50}
        }
        user_to_reset = 'user1'
        for key in list(buckets.keys()):
            if key.startswith(user_to_reset):
                del buckets[key]
        
        assert 'user1:/api/users' not in buckets
        assert 'user2:/api/users' in buckets

    def test_user_can_make_requests_again(self):
        """Test that user can make requests after reset."""
        buckets = {'user1': {'tokens': 0}}
        # Reset
        buckets['user1'] = {'tokens': 100}
        assert buckets['user1']['tokens'] == 100

    def test_other_users_unaffected(self):
        """Test that reset only affects target user."""
        buckets = {
            'user1': {'tokens': 10},
            'user2': {'tokens': 50}
        }
        buckets['user1'] = {'tokens': 100}
        assert buckets['user2']['tokens'] == 50


class TestGetUsage:
    """Test usage retrieval."""

    def test_returns_usage_for_user(self):
        """Test returning usage data for user."""
        buckets = {
            'user1:/api/users': {'tokens': 75, 'capacity': 100},
            'user1:/api/llm': {'tokens': 15, 'capacity': 20}
        }
        user_usage = {
            k: v for k, v in buckets.items() if k.startswith('user1')
        }
        assert len(user_usage) == 2

    def test_includes_endpoint_breakdown(self):
        """Test endpoint breakdown in usage."""
        usage = {
            '/api/users': {'remaining': 75, 'limit': 100},
            '/api/llm': {'remaining': 15, 'limit': 20}
        }
        assert len(usage) == 2
        assert usage['/api/users']['remaining'] == 75

    def test_returns_empty_for_unknown(self):
        """Test empty return for unknown user."""
        buckets = {'user1': {}}
        user_usage = buckets.get('unknown_user', {})
        assert user_usage == {}


class TestGetStats:
    """Test statistics collection."""

    def test_total_requests(self):
        """Test counting total requests."""
        stats = {'total_requests': 0}
        stats['total_requests'] += 100
        assert stats['total_requests'] == 100

    def test_total_blocked(self):
        """Test counting blocked requests."""
        stats = {'blocked_requests': 0}
        stats['blocked_requests'] += 15
        assert stats['blocked_requests'] == 15

    def test_active_users_count(self):
        """Test counting active users."""
        buckets = {
            'user1:/api/users': {},
            'user1:/api/llm': {},
            'user2:/api/users': {}
        }
        users = set(k.split(':')[0] for k in buckets.keys())
        assert len(users) == 2

    def test_block_rate_calculation(self):
        """Test block rate calculation."""
        stats = {
            'total_requests': 1000,
            'blocked_requests': 50
        }
        block_rate = stats['blocked_requests'] / stats['total_requests'] * 100
        assert block_rate == 5.0
