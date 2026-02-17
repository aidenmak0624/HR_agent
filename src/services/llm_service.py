"""
LLM Service - Wraps LLM provider integration with fallback & circuit breaker
Iteration 4: OpenAI primary with Google Gemini fallback
"""

import logging
import time
from typing import Any, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class LLMProvider(str, Enum):
    """Supported LLM providers."""

    GOOGLE = "google"
    OPENAI = "openai"
    FALLBACK = "fallback"


class LLMService:
    """
    LLM service wrapper with provider selection, fallback, and circuit breaker.

    Features:
    - OpenAI (gpt-4o-mini) as primary provider
    - Google Gemini as optional fallback
    - Circuit breaker for fault tolerance
    - Token counting and cost tracking
    - Health checks
    """

    def __init__(self):
        """Initialize LLM service with configured providers."""
        logger.info("Initializing LLMService...")

        from config.settings import get_settings

        self.settings = get_settings()
        self.primary_provider = LLMProvider.OPENAI
        self.fallback_provider = LLMProvider.GOOGLE
        self.current_provider = self.primary_provider

        # Circuit breaker state
        self.consecutive_failures = 0
        self.max_consecutive_failures = 3
        self.circuit_breaker_open = False

        # Initialize providers (OpenAI first as primary)
        self._init_openai_provider()
        self._init_google_provider()

        # Cost tracking
        self.total_cost_usd = 0.0
        self.request_count = 0

        logger.info("✅ LLMService initialized")

    def _init_openai_provider(self) -> None:
        """Initialize OpenAI provider (primary)."""
        try:
            from langchain_openai import ChatOpenAI

            api_key = getattr(self.settings, "OPENAI_API_KEY", "")
            if not api_key:
                logger.warning("OPENAI_API_KEY not set, OpenAI provider unavailable")
                self.openai_llm = None
                return

            model = getattr(self.settings, "LLM_DEFAULT_MODEL", "gpt-4o-mini")
            self.openai_llm = ChatOpenAI(
                model=model,
                api_key=api_key,
                temperature=0.3,
                max_tokens=2048,
            )
            logger.info(f"✅ OpenAI provider initialized (model: {model})")

        except Exception as e:
            logger.warning(f"OpenAI provider initialization failed: {e}")
            self.openai_llm = None

    def _init_google_provider(self) -> None:
        """Initialize Google Gemini provider (fallback)."""
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            if not self.settings.GOOGLE_API_KEY:
                logger.info("GOOGLE_API_KEY not set, Gemini fallback unavailable")
                self.google_llm = None
                return

            fallback_model = getattr(self.settings, "LLM_FALLBACK_MODEL", "gemini-2.0-flash")
            self.google_llm = ChatGoogleGenerativeAI(
                model=fallback_model,
                google_api_key=self.settings.GOOGLE_API_KEY,
                temperature=0.3,
                max_output_tokens=2048,
            )
            logger.info(f"✅ Google Gemini fallback initialized (model: {fallback_model})")

        except Exception as e:
            logger.warning(f"Google fallback initialization failed: {e}")
            self.google_llm = None

    # ==================== GENERATE METHODS ====================

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """
        Generate text response from LLM.

        Args:
            prompt: User prompt
            system_prompt: System context
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum output tokens

        Returns:
            Generated text response

        Raises:
            RuntimeError: If all providers fail
        """
        logger.info(f"Generate: {prompt[:50]}...")

        # Check circuit breaker
        if self.circuit_breaker_open:
            logger.warning("Circuit breaker open, attempting recovery")
            if self.consecutive_failures < self.max_consecutive_failures:
                self.circuit_breaker_open = False
                self.consecutive_failures = 0
            else:
                raise RuntimeError("LLM service unavailable (circuit breaker open)")

        # Build messages
        from langchain_core.messages import SystemMessage, HumanMessage

        messages = []
        if system_prompt:
            messages.append(SystemMessage(content=system_prompt))
        messages.append(HumanMessage(content=prompt))

        # Try primary provider (OpenAI)
        try:
            response = self._call_provider(
                self.openai_llm,
                messages,
                temperature,
                max_tokens,
                LLMProvider.OPENAI,
            )
            self.consecutive_failures = 0
            self.request_count += 1
            return response

        except Exception as e:
            logger.warning(f"Primary provider (OpenAI) failed: {e}")
            self.consecutive_failures += 1

        # Try fallback provider (Google Gemini)
        if self.google_llm:
            try:
                logger.info("Switching to fallback provider (Google Gemini)")
                response = self._call_provider(
                    self.google_llm,
                    messages,
                    temperature,
                    max_tokens,
                    LLMProvider.GOOGLE,
                )
                self.consecutive_failures = 0
                self.request_count += 1
                return response

            except Exception as e:
                logger.error(f"Fallback provider (Gemini) also failed: {e}")
                self.consecutive_failures += 1

        # Both failed
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.circuit_breaker_open = True
            logger.error("Circuit breaker opened due to repeated failures")

        raise RuntimeError("All LLM providers failed")

    def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate JSON response from LLM.

        Args:
            prompt: User prompt
            system_prompt: System context

        Returns:
            Parsed JSON dict

        Raises:
            ValueError: If response is not valid JSON
        """
        import json
        import re

        logger.info("Generate JSON...")

        response_text = self.generate(prompt, system_prompt)

        # Try direct JSON parse
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from response
        match = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", response_text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"No valid JSON in response: {response_text[:100]}")

    # ==================== HELPER METHODS ====================

    def _call_provider(
        self,
        llm: Any,
        messages: list,
        temperature: float,
        max_tokens: int,
        provider: LLMProvider,
    ) -> str:
        """
        Call LLM provider and return response.

        Args:
            llm: Language model instance
            messages: List of messages
            temperature: Sampling temperature
            max_tokens: Max output tokens
            provider: Provider identifier

        Returns:
            Response text
        """
        start_time = time.time()

        try:
            response = llm.invoke(messages)
            elapsed_ms = (time.time() - start_time) * 1000

            response_text = response.content if hasattr(response, "content") else str(response)

            logger.info(
                f"Provider {provider.value}: {elapsed_ms:.1f}ms, "
                f"tokens_out={len(response_text.split())}"
            )

            # Track cost (rough estimate)
            self._track_cost(provider, response_text)

            return response_text

        except Exception as e:
            logger.error(f"Provider {provider.value} failed: {e}")
            raise

    def _track_cost(self, provider: LLMProvider, response_text: str) -> None:
        """
        Track estimated LLM cost.

        Args:
            provider: Provider used
            response_text: Response text
        """
        try:
            # Rough token estimate: 1 token ≈ 4 characters
            tokens_out = len(response_text) // 4

            if provider == LLMProvider.OPENAI:
                # OpenAI gpt-4o-mini pricing (~$0.15/1M input, ~$0.60/1M output)
                cost = tokens_out * 0.0000006  # ~$0.60 per 1M output tokens
            elif provider == LLMProvider.GOOGLE:
                # Google Gemini fallback pricing (rough estimate)
                cost = tokens_out * 0.000001
            else:
                cost = 0.0

            self.total_cost_usd += cost

        except Exception as e:
            logger.debug(f"Cost tracking failed: {e}")

    # ==================== UTILITIES ====================

    def token_count(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: Input text

        Returns:
            Approximate token count
        """
        # Simple approximation: 1 token ≈ 4 characters
        return len(text) // 4

    def is_available(self) -> bool:
        """
        Check if LLM service is available.

        Returns:
            True if at least one provider is available
        """
        if self.circuit_breaker_open:
            return False

        return self.openai_llm is not None or self.google_llm is not None

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get LLM service health status.

        Returns:
            Health status dict
        """
        return {
            "available": self.is_available(),
            "circuit_breaker_open": self.circuit_breaker_open,
            "consecutive_failures": self.consecutive_failures,
            "openai_provider": self.openai_llm is not None,
            "google_fallback": self.google_llm is not None,
            "current_provider": self.current_provider.value,
            "request_count": self.request_count,
            "estimated_cost_usd": round(self.total_cost_usd, 6),
        }
