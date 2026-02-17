"""Tests for LLM Gateway module."""

import pytest
from unittest.mock import MagicMock, patch
from src.core.llm_gateway import (
    LLMGateway,
    LLMResponse,
    TaskType,
    ModelConfig,
    CircuitBreakerState,
)


class TestTaskTypeRouting:
    """Tests for task type to model routing."""

    def test_task_type_routes_to_correct_model(self):
        """Different task types route to appropriate models."""
        gateway = LLMGateway()

        # Check default models are assigned
        assert TaskType.CLASSIFICATION in gateway.DEFAULT_MODELS
        assert TaskType.SYNTHESIS in gateway.DEFAULT_MODELS
        assert TaskType.EMBEDDING in gateway.DEFAULT_MODELS
        assert TaskType.COMPLIANCE in gateway.DEFAULT_MODELS

        classification_model = gateway.DEFAULT_MODELS[TaskType.CLASSIFICATION]
        synthesis_model = gateway.DEFAULT_MODELS[TaskType.SYNTHESIS]

        assert classification_model.model_name == "gpt-4o-mini"
        assert synthesis_model.model_name == "gpt-4o-mini"

        # Classification should have lower temperature
        assert classification_model.temperature < synthesis_model.temperature

    def test_classification_model_config(self):
        """Classification model has appropriate config."""
        gateway = LLMGateway()
        config = gateway.DEFAULT_MODELS[TaskType.CLASSIFICATION]

        assert config.temperature == 0.1
        assert config.max_tokens == 256
        assert config.timeout_seconds == 10


class TestCircuitBreaker:
    """Tests for circuit breaker functionality."""

    def test_circuit_breaker_opens_after_failures(self):
        """Circuit breaker opens after threshold failures."""

        def failing_llm_call(*args, **kwargs):
            raise Exception("LLM call failed")

        gateway = LLMGateway(llm_call_handler=failing_llm_call)

        # Make multiple failing calls
        for i in range(gateway.CIRCUIT_BREAKER_THRESHOLD):
            try:
                gateway.send_prompt(TaskType.CLASSIFICATION, f"Test prompt {i}")
            except RuntimeError:
                pass

        # Circuit breaker should be open
        assert gateway.circuit_breakers.get("gpt-4o-mini") == CircuitBreakerState.OPEN

    def test_circuit_breaker_prevents_calls_when_open(self):
        """Open circuit breaker rejects new calls."""

        def failing_llm_call(*args, **kwargs):
            raise Exception("LLM call failed")

        gateway = LLMGateway(llm_call_handler=failing_llm_call)
        gateway.circuit_breakers["gpt-4o-mini"] = CircuitBreakerState.OPEN

        with pytest.raises(RuntimeError) as exc_info:
            gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")

        assert (
            "unavailable" in str(exc_info.value).lower()
            or "circuit breaker" in str(exc_info.value).lower()
        )

    def test_circuit_breaker_resets_on_success(self):
        """Circuit breaker resets to CLOSED on HALF_OPEN success."""

        def success_llm_call(*args, **kwargs):
            return "Successful response"

        gateway = LLMGateway(llm_call_handler=success_llm_call)
        gateway.circuit_breakers["gpt-4o-mini"] = CircuitBreakerState.HALF_OPEN

        response = gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")

        assert response.text == "Successful response"
        assert gateway.circuit_breakers.get("gpt-4o-mini") == CircuitBreakerState.CLOSED


class TestRetryLogic:
    """Tests for retry mechanism."""

    def test_retry_on_failure(self):
        """Failed calls are retried."""
        call_count = 0

        def flaky_llm_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return "Success on retry"

        gateway = LLMGateway(llm_call_handler=flaky_llm_call)

        response = gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")

        assert response.text == "Success on retry"
        assert call_count == 3

    def test_retry_exhaustion_raises(self):
        """Exhausted retries raise exception."""

        def always_failing_llm_call(*args, **kwargs):
            raise Exception("Permanent failure")

        gateway = LLMGateway(llm_call_handler=always_failing_llm_call)

        with pytest.raises(RuntimeError) as exc_info:
            gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")

        assert "attempt" in str(exc_info.value).lower()
        assert "failed" in str(exc_info.value).lower()


class TestCaching:
    """Tests for response caching."""

    def test_cache_hit_returns_cached(self):
        """Cache hit returns cached response without LLM call."""
        call_count = 0

        def counting_llm_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return f"Response {call_count}"

        mock_cache = MagicMock()
        # First call: cache miss, second call: cache hit
        cached_response = {
            "text": "Cached response",
            "model_used": "gpt-4o-mini",
            "tokens_in": 10,
            "tokens_out": 20,
            "latency_ms": 100,
        }
        import json

        mock_cache.get = MagicMock(return_value=json.dumps(cached_response))

        gateway = LLMGateway(
            cache_backend=mock_cache, llm_call_handler=counting_llm_call, enable_caching=True
        )

        response1 = gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")

        # Should use cache
        response2 = gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")

        assert response2.cached is True
        assert response2.text == "Cached response"

    def test_cache_disabled_skips_cache(self):
        """Caching disabled skips cache operations."""
        call_count = 0

        def counting_llm_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return f"Response {call_count}"

        mock_cache = MagicMock()

        gateway = LLMGateway(
            cache_backend=mock_cache, llm_call_handler=counting_llm_call, enable_caching=False
        )

        gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")
        gateway.send_prompt(TaskType.CLASSIFICATION, "Test prompt")

        # Cache should not be accessed
        mock_cache.get.assert_not_called()


class TestMetricsTracking:
    """Tests for metrics collection."""

    def test_get_stats_returns_metrics(self):
        """get_stats() returns comprehensive metrics."""

        def success_llm_call(*args, **kwargs):
            return "Response"

        gateway = LLMGateway(llm_call_handler=success_llm_call)

        gateway.send_prompt(TaskType.CLASSIFICATION, "Test 1")
        gateway.send_prompt(TaskType.SYNTHESIS, "Test 2")

        stats = gateway.get_stats()

        assert len(stats) > 0

        for model_name, model_stats in stats.items():
            assert "call_count" in model_stats
            assert "success_count" in model_stats
            assert "failure_count" in model_stats
            assert "success_rate" in model_stats
            assert "circuit_breaker_state" in model_stats

    def test_metrics_track_success_rate(self):
        """Metrics track success rate correctly."""
        call_count = 0

        def sometimes_failing_llm_call(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise Exception("Simulated failure")
            return "Success"

        gateway = LLMGateway(llm_call_handler=sometimes_failing_llm_call)

        # Make calls that alternate succeed/fail
        for i in range(4):
            try:
                gateway.send_prompt(TaskType.CLASSIFICATION, f"Test {i}")
            except RuntimeError:
                pass

        stats = gateway.get_stats()
        model_stats = list(stats.values())[0]

        assert model_stats["success_rate"] > 0.0


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_llm_response_creation(self):
        """LLMResponse can be created with required fields."""
        response = LLMResponse(
            text="Test response",
            model_used="gpt-4o-mini",
            tokens_in=10,
            tokens_out=20,
            latency_ms=150.5,
            cached=False,
        )

        assert response.text == "Test response"
        assert response.model_used == "gpt-4o-mini"
        assert response.cached is False

    def test_llm_response_cached_flag(self):
        """LLMResponse cached flag is tracked."""
        cached_response = LLMResponse(text="Cached", model_used="test", cached=True)

        fresh_response = LLMResponse(text="Fresh", model_used="test", cached=False)

        assert cached_response.cached is True
        assert fresh_response.cached is False


class TestModelConfig:
    """Tests for ModelConfig."""

    def test_model_config_validation(self):
        """ModelConfig validates parameters."""
        config = ModelConfig(
            model_name="test-model", temperature=0.5, max_tokens=512, timeout_seconds=15
        )

        assert config.model_name == "test-model"
        assert config.temperature == 0.5
        assert config.max_tokens == 512
        assert config.timeout_seconds == 15

    def test_model_config_defaults(self):
        """ModelConfig has sensible defaults."""
        config = ModelConfig(model_name="test-model")

        assert config.temperature == 0.3
        assert config.max_tokens == 1024
        assert config.timeout_seconds == 30


class TestPromptSending:
    """Tests for send_prompt method."""

    def test_send_prompt_returns_llm_response(self):
        """send_prompt returns LLMResponse."""

        def mock_llm_call(*args, **kwargs):
            return "Test response"

        gateway = LLMGateway(llm_call_handler=mock_llm_call)

        response = gateway.send_prompt(TaskType.CLASSIFICATION, "What is the policy?")

        assert isinstance(response, LLMResponse)
        assert response.text == "Test response"
        assert response.model_used == "gpt-4o-mini"

    def test_send_prompt_records_metrics(self):
        """send_prompt records call metrics."""

        def mock_llm_call(*args, **kwargs):
            return "Response"

        gateway = LLMGateway(llm_call_handler=mock_llm_call)

        gateway.send_prompt(TaskType.SYNTHESIS, "Test prompt")

        stats = gateway.get_stats()
        assert len(stats) > 0
        assert stats["gpt-4o-mini"]["call_count"] == 1
        assert stats["gpt-4o-mini"]["success_count"] == 1
