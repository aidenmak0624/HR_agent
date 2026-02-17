"""
CORE-002: LLM Gateway Module
Centralized model routing and response management for the HR multi-agent platform.
"""

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TaskType(str, Enum):
    """Task types that require LLM processing."""
    CLASSIFICATION = "classification"
    SYNTHESIS = "synthesis"
    EMBEDDING = "embedding"
    COMPLIANCE = "compliance"
    REFLECTION = "reflection"


class ModelConfig(BaseModel):
    """Configuration for an LLM model."""
    model_name: str = Field(..., description="Name of the model")
    temperature: float = Field(default=0.3, ge=0.0, le=1.0)
    max_tokens: int = Field(default=1024, gt=0)
    timeout_seconds: int = Field(default=30, gt=0)


@dataclass
class LLMResponse:
    """Response from LLM call."""
    text: str
    model_used: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cached: bool = False


@dataclass
class PIIResult:
    """Result from PII detection/stripping."""
    sanitized_text: str
    mapping: Dict[str, str] = field(default_factory=dict)
    pii_count: int = 0
    pii_types_found: list = field(default_factory=list)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Operating normally
    OPEN = "open"      # Failing, skip requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class ModelMetrics:
    """Metrics for a specific model."""
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_tokens_in: int = 0
    total_tokens_out: int = 0
    total_latency_ms: float = 0.0
    cache_hits: int = 0
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0


class LLMGateway:
    """
    Centralized LLM routing and management.
    
    Handles model selection, retry logic, circuit breaking, caching,
    and metrics tracking for LLM calls.
    """
    
    DEFAULT_MODELS: Dict[TaskType, ModelConfig] = {
        TaskType.CLASSIFICATION: ModelConfig(
            model_name="gpt-4o-mini",
            temperature=0.1,
            max_tokens=256,
            timeout_seconds=10
        ),
        TaskType.SYNTHESIS: ModelConfig(
            model_name="gpt-4o-mini",
            temperature=0.3,
            max_tokens=2048,
            timeout_seconds=30
        ),
        TaskType.EMBEDDING: ModelConfig(
            model_name="sentence-transformers/all-MiniLM-L6-v2",
            temperature=0.0,
            max_tokens=384,
            timeout_seconds=5
        ),
        TaskType.COMPLIANCE: ModelConfig(
            model_name="gpt-4o-mini",
            temperature=0.0,
            max_tokens=1024,
            timeout_seconds=20
        ),
        TaskType.REFLECTION: ModelConfig(
            model_name="gpt-4o-mini",
            temperature=0.1,
            max_tokens=512,
            timeout_seconds=15
        ),
    }
    
    CIRCUIT_BREAKER_THRESHOLD = 5  # failures before opening
    CIRCUIT_BREAKER_RESET_SECONDS = 60
    RETRY_ATTEMPTS = 3
    RETRY_BACKOFF = [1.0, 2.0, 4.0]  # seconds
    
    def __init__(
        self,
        cache_backend: Optional[Any] = None,
        llm_call_handler: Optional[Callable] = None,
        enable_caching: bool = True
    ):
        """
        Initialize LLM Gateway.
        
        Args:
            cache_backend: Redis or similar cache client (optional)
            llm_call_handler: Custom function to call LLM (for testing/injection)
            enable_caching: Whether to use response caching
        """
        self.cache = cache_backend
        self.enable_caching = enable_caching
        self._llm_call_handler = llm_call_handler or self._default_llm_call
        self.metrics: Dict[str, ModelMetrics] = {}
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.circuit_breaker_reset_times: Dict[str, datetime] = {}
        
    def send_prompt(
        self,
        task_type: TaskType,
        prompt: str,
        **kwargs: Any
    ) -> LLMResponse:
        """
        Send a prompt to the appropriate LLM for the task type.
        
        Args:
            task_type: Type of task to classify the request
            prompt: The prompt text to send
            **kwargs: Additional arguments (e.g., context, user_id)
        
        Returns:
            LLMResponse with text, metadata, and metrics
        
        Raises:
            Exception: If all retry attempts fail
        """
        model_config = self.DEFAULT_MODELS[task_type]
        cache_key = self._make_cache_key(task_type, prompt)
        
        # Try cache first
        if self.enable_caching and self.cache:
            cached_response = self._get_from_cache(cache_key)
            if cached_response:
                self._record_cache_hit(model_config.model_name)
                return cached_response
        
        # Check circuit breaker
        if not self._is_circuit_available(model_config.model_name):
            logger.warning(
                f"Circuit breaker OPEN for model {model_config.model_name}"
            )
            raise RuntimeError(
                f"Model {model_config.model_name} is unavailable (circuit breaker open)"
            )
        
        # Retry logic with exponential backoff
        last_exception = None
        for attempt in range(self.RETRY_ATTEMPTS):
            try:
                start_time = time.time()
                response_text = self._llm_call_handler(
                    model_config=model_config,
                    prompt=prompt,
                    **kwargs
                )
                latency_ms = (time.time() - start_time) * 1000
                
                # Create response
                llm_response = LLMResponse(
                    text=response_text,
                    model_used=model_config.model_name,
                    latency_ms=latency_ms,
                    cached=False
                )
                
                # Cache the response
                if self.enable_caching and self.cache:
                    self._save_to_cache(cache_key, llm_response)
                
                # Record success
                self._record_success(
                    model_config.model_name,
                    latency_ms,
                    tokens_in=len(prompt.split()),
                    tokens_out=len(response_text.split())
                )
                
                return llm_response
                
            except Exception as e:
                last_exception = e
                logger.warning(
                    f"LLM call attempt {attempt + 1} failed: {str(e)}"
                )
                self._record_failure(model_config.model_name)
                
                if attempt < self.RETRY_ATTEMPTS - 1:
                    backoff_time = self.RETRY_BACKOFF[attempt]
                    logger.info(f"Retrying in {backoff_time}s...")
                    time.sleep(backoff_time)
        
        # All retries failed
        raise RuntimeError(
            f"LLM call failed after {self.RETRY_ATTEMPTS} attempts: {str(last_exception)}"
        ) from last_exception
    
    def _default_llm_call(
        self,
        model_config: ModelConfig,
        prompt: str,
        **kwargs: Any
    ) -> str:
        """
        Default LLM call implementation using OpenAI (primary) with Gemini fallback.

        This can be overridden by providing a custom llm_call_handler.

        Args:
            model_config: Model configuration
            prompt: Prompt text
            **kwargs: Additional arguments

        Returns:
            Response text from the model
        """
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=model_config.model_name,
                temperature=model_config.temperature,
                max_tokens=model_config.max_tokens,
            )
            response = llm.invoke(prompt)
            return response.content if hasattr(response, 'content') else str(response)

        except Exception as e:
            logger.warning(f"OpenAI call failed, trying Gemini fallback: {e}")

            try:
                from langchain_google_genai import ChatGoogleGenerativeAI

                llm = ChatGoogleGenerativeAI(
                    model="gemini-2.0-flash",
                    temperature=model_config.temperature,
                    max_output_tokens=model_config.max_tokens,
                )
                response = llm.invoke(prompt)
                return response.content if hasattr(response, 'content') else str(response)

            except Exception as fallback_err:
                logger.error(f"Both OpenAI and Gemini failed: {fallback_err}")
                raise RuntimeError(f"All LLM providers failed") from e
    
    def _make_cache_key(self, task_type: TaskType, prompt: str) -> str:
        """Generate a cache key for a prompt."""
        combined = f"{task_type.value}:{prompt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _get_from_cache(self, cache_key: str) -> Optional[LLMResponse]:
        """Retrieve cached response."""
        if not self.cache:
            return None
        
        try:
            cached_data = self.cache.get(cache_key)
            if cached_data:
                data_dict = json.loads(cached_data)
                response = LLMResponse(
                    text=data_dict['text'],
                    model_used=data_dict['model_used'],
                    tokens_in=data_dict.get('tokens_in', 0),
                    tokens_out=data_dict.get('tokens_out', 0),
                    latency_ms=data_dict.get('latency_ms', 0),
                    cached=True
                )
                return response
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {str(e)}")
        
        return None
    
    def _save_to_cache(self, cache_key: str, response: LLMResponse) -> None:
        """Save response to cache."""
        if not self.cache:
            return
        
        try:
            cache_data = {
                'text': response.text,
                'model_used': response.model_used,
                'tokens_in': response.tokens_in,
                'tokens_out': response.tokens_out,
                'latency_ms': response.latency_ms
            }
            self.cache.setex(
                cache_key,
                86400,  # 24 hour TTL
                json.dumps(cache_data)
            )
        except Exception as e:
            logger.warning(f"Cache save failed: {str(e)}")
    
    def _is_circuit_available(self, model_name: str) -> bool:
        """Check if circuit breaker allows requests."""
        if model_name not in self.circuit_breakers:
            self.circuit_breakers[model_name] = CircuitBreakerState.CLOSED
            return True
        
        state = self.circuit_breakers[model_name]
        
        if state == CircuitBreakerState.CLOSED:
            return True
        
        if state == CircuitBreakerState.OPEN:
            reset_time = self.circuit_breaker_reset_times.get(model_name)
            if reset_time and datetime.now() >= reset_time:
                self.circuit_breakers[model_name] = CircuitBreakerState.HALF_OPEN
                return True
            return False
        
        return True  # HALF_OPEN allows one attempt
    
    def _record_success(
        self,
        model_name: str,
        latency_ms: float,
        tokens_in: int = 0,
        tokens_out: int = 0
    ) -> None:
        """Record a successful LLM call."""
        if model_name not in self.metrics:
            self.metrics[model_name] = ModelMetrics()
        
        metrics = self.metrics[model_name]
        metrics.call_count += 1
        metrics.success_count += 1
        metrics.total_latency_ms += latency_ms
        metrics.total_tokens_in += tokens_in
        metrics.total_tokens_out += tokens_out
        metrics.consecutive_failures = 0
        
        # Reset circuit breaker on success
        if self.circuit_breakers.get(model_name) == CircuitBreakerState.HALF_OPEN:
            self.circuit_breakers[model_name] = CircuitBreakerState.CLOSED
    
    def _record_failure(self, model_name: str) -> None:
        """Record a failed LLM call and check circuit breaker."""
        if model_name not in self.metrics:
            self.metrics[model_name] = ModelMetrics()
        
        metrics = self.metrics[model_name]
        metrics.call_count += 1
        metrics.failure_count += 1
        metrics.consecutive_failures += 1
        metrics.last_failure_time = datetime.now()
        
        # Open circuit breaker if threshold reached
        if metrics.consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            self.circuit_breakers[model_name] = CircuitBreakerState.OPEN
            self.circuit_breaker_reset_times[model_name] = (
                datetime.now() + timedelta(seconds=self.CIRCUIT_BREAKER_RESET_SECONDS)
            )
            logger.error(
                f"Circuit breaker OPENED for {model_name} "
                f"(consecutive failures: {metrics.consecutive_failures})"
            )
    
    def _record_cache_hit(self, model_name: str) -> None:
        """Record a cache hit."""
        if model_name not in self.metrics:
            self.metrics[model_name] = ModelMetrics()
        
        self.metrics[model_name].cache_hits += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for all models.
        
        Returns:
            Dictionary with statistics per model
        """
        stats = {}
        
        for model_name, metrics in self.metrics.items():
            success_rate = (
                (metrics.success_count / metrics.call_count)
                if metrics.call_count > 0 else 0.0
            )
            avg_latency = (
                (metrics.total_latency_ms / metrics.success_count)
                if metrics.success_count > 0 else 0.0
            )
            
            stats[model_name] = {
                'call_count': metrics.call_count,
                'success_count': metrics.success_count,
                'failure_count': metrics.failure_count,
                'success_rate': success_rate,
                'total_tokens_in': metrics.total_tokens_in,
                'total_tokens_out': metrics.total_tokens_out,
                'average_latency_ms': avg_latency,
                'cache_hits': metrics.cache_hits,
                'last_failure_time': (
                    metrics.last_failure_time.isoformat()
                    if metrics.last_failure_time else None
                ),
                'circuit_breaker_state': (
                    self.circuit_breakers.get(model_name, CircuitBreakerState.CLOSED).value
                )
            }
        
        return stats
