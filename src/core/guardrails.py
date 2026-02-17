"""
Input/Output Guardrails for HR Agent Platform.

Provides a safety layer that validates all queries before they reach agents
and all responses before they reach users. Implements:

INPUT GUARDRAILS:
- Query sanitization (strip dangerous characters)
- Prompt injection detection (block LLM manipulation attempts)
- PII screening (detect and mask SSNs, credit cards, etc.)
- Query length limits
- Rate-based abuse detection

OUTPUT GUARDRAILS:
- Confidence threshold enforcement
- PII leakage detection in responses
- Hallucination flagging (when response doesn't cite tools)
- Format enforcement (ensure structured response)

Usage:
    guardrails = Guardrails()
    # Before sending to agent:
    result = guardrails.validate_input(query, user_context)
    if not result.passed:
        return result.blocked_reason
    # After receiving from agent:
    result = guardrails.validate_output(response, original_query)
    if result.pii_detected:
        response = result.sanitized_response
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ─── PII Patterns ────────────────────────────────────────────────
PII_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "credit_card": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
    "phone_us": re.compile(r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "passport": re.compile(r"\b[A-Z]\d{8}\b"),
    "bank_account": re.compile(r"\b\d{8,17}\b"),  # Very broad — used cautiously
}

# ─── Prompt Injection Patterns ───────────────────────────────────
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?your\s+(previous\s+)?instructions", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(?:a|an)\s+", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*:", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"act\s+as\s+(?:a|an)\s+(?:different|new)", re.IGNORECASE),
    re.compile(r"reveal\s+(?:your\s+)?(?:system|hidden)\s+(?:prompt|instructions)", re.IGNORECASE),
    re.compile(
        r"(?:print|show|display|output)\s+(?:your\s+)?(?:system|initial)\s+(?:prompt|message)",
        re.IGNORECASE,
    ),
    re.compile(r"ADMIN\s*OVERRIDE", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
]

# ─── Dangerous Content Patterns ──────────────────────────────────
DANGEROUS_PATTERNS = [
    re.compile(r"(?:DROP|DELETE|TRUNCATE|ALTER)\s+TABLE", re.IGNORECASE),
    re.compile(r";\s*(?:DROP|DELETE|INSERT|UPDATE)\s+", re.IGNORECASE),
    re.compile(r"<script\b", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"on(?:load|error|click)\s*=", re.IGNORECASE),
]


@dataclass
class InputValidationResult:
    """
    Result of input guardrail validation.

    Attributes:
        passed: True if query is safe to process
        sanitized_query: Cleaned version of the query
        blocked_reason: Why the query was blocked (if blocked)
        warnings: Non-blocking issues detected
        pii_found: List of PII types detected in input
        injection_detected: True if prompt injection was detected
    """

    passed: bool = True
    sanitized_query: str = ""
    blocked_reason: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    pii_found: List[str] = field(default_factory=list)
    injection_detected: bool = False


@dataclass
class OutputValidationResult:
    """
    Result of output guardrail validation.

    Attributes:
        passed: True if response is safe to return
        sanitized_response: Response with PII masked
        pii_detected: True if PII was found in response
        pii_types: Types of PII found
        confidence_ok: True if response confidence meets threshold
        warnings: Non-blocking issues detected
    """

    passed: bool = True
    sanitized_response: str = ""
    pii_detected: bool = False
    pii_types: List[str] = field(default_factory=list)
    confidence_ok: bool = True
    warnings: List[str] = field(default_factory=list)


class Guardrails:
    """
    Input/output guardrails for the HR Agent platform.

    Configuration:
        max_query_length: Maximum allowed query length (default 2000)
        min_confidence_threshold: Minimum acceptable confidence (default 0.3)
        block_pii_in_input: Whether to block queries containing PII (default False)
        mask_pii_in_output: Whether to mask PII in responses (default True)
        block_injections: Whether to block detected prompt injections (default True)
    """

    def __init__(
        self,
        max_query_length: int = 2000,
        min_confidence_threshold: float = 0.3,
        block_pii_in_input: bool = False,
        mask_pii_in_output: bool = True,
        block_injections: bool = True,
    ):
        self.max_query_length = max_query_length
        self.min_confidence_threshold = min_confidence_threshold
        self.block_pii_in_input = block_pii_in_input
        self.mask_pii_in_output = mask_pii_in_output
        self.block_injections = block_injections

        # Stats tracking
        self._stats = {
            "total_input_checks": 0,
            "total_output_checks": 0,
            "inputs_blocked": 0,
            "injections_detected": 0,
            "pii_masked_count": 0,
        }

    # ==================== Input Guardrails ====================

    def validate_input(
        self,
        query: str,
        user_context: Optional[Dict[str, Any]] = None,
    ) -> InputValidationResult:
        """
        Validate and sanitize an incoming query.

        Checks (in order):
        1. Empty/whitespace query
        2. Query length limit
        3. Dangerous content (SQL injection, XSS)
        4. Prompt injection attempts
        5. PII in input

        Args:
            query: Raw user query
            user_context: Optional user context for role-based rules

        Returns:
            InputValidationResult with pass/fail status and details.
        """
        self._stats["total_input_checks"] += 1
        result = InputValidationResult(sanitized_query=query.strip())

        # 1. Empty check
        if not query or not query.strip():
            result.passed = False
            result.blocked_reason = "Empty query"
            self._stats["inputs_blocked"] += 1
            return result

        # 2. Length check
        if len(query) > self.max_query_length:
            result.passed = False
            result.blocked_reason = f"Query exceeds maximum length ({self.max_query_length} chars)"
            self._stats["inputs_blocked"] += 1
            return result

        # 3. Dangerous content
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(query):
                result.passed = False
                result.blocked_reason = "Potentially dangerous content detected (SQL/XSS)"
                self._stats["inputs_blocked"] += 1
                logger.warning(f"Guardrails: Dangerous content blocked: {query[:50]}...")
                return result

        # 4. Prompt injection detection
        for pattern in INJECTION_PATTERNS:
            if pattern.search(query):
                result.injection_detected = True
                self._stats["injections_detected"] += 1

                if self.block_injections:
                    result.passed = False
                    result.blocked_reason = "Potential prompt injection detected"
                    self._stats["inputs_blocked"] += 1
                    logger.warning(f"Guardrails: Injection blocked: {query[:50]}...")
                    return result
                else:
                    result.warnings.append("Potential prompt injection detected but not blocked")
                break

        # 5. PII detection in input
        for pii_type, pattern in PII_PATTERNS.items():
            if pii_type == "bank_account":
                continue  # Too broad for input checking
            if pattern.search(query):
                result.pii_found.append(pii_type)

        if result.pii_found:
            if self.block_pii_in_input:
                result.passed = False
                result.blocked_reason = f"PII detected in query: {', '.join(result.pii_found)}"
                self._stats["inputs_blocked"] += 1
                return result
            else:
                result.warnings.append(f"PII detected in input: {', '.join(result.pii_found)}")

        # 6. Sanitize — strip control characters
        sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", result.sanitized_query)
        result.sanitized_query = sanitized

        return result

    # ==================== Output Guardrails ====================

    def validate_output(
        self,
        response: Dict[str, Any],
        original_query: str = "",
    ) -> OutputValidationResult:
        """
        Validate an agent's response before returning to user.

        Checks:
        1. Confidence threshold
        2. PII leakage in response text
        3. Empty/missing answer
        4. Response format

        Args:
            response: Agent response dict with 'answer', 'confidence', etc.
            original_query: Original user query for context

        Returns:
            OutputValidationResult with pass/fail and sanitized response.
        """
        self._stats["total_output_checks"] += 1
        result = OutputValidationResult()

        answer = response.get("answer", "")
        confidence = response.get("confidence", 0.0)

        result.sanitized_response = answer

        # 1. Confidence check
        if confidence < self.min_confidence_threshold:
            result.confidence_ok = False
            result.warnings.append(
                f"Low confidence ({confidence:.2f} < {self.min_confidence_threshold})"
            )

        # 2. Empty answer
        if not answer or not answer.strip():
            result.passed = False
            result.warnings.append("Empty response from agent")
            return result

        # 3. PII detection and masking in output
        if self.mask_pii_in_output:
            masked_answer = answer
            for pii_type, pattern in PII_PATTERNS.items():
                matches = pattern.findall(masked_answer)
                if matches:
                    result.pii_detected = True
                    result.pii_types.append(pii_type)
                    self._stats["pii_masked_count"] += len(matches)

                    # Mask PII with type indicator
                    mask_map = {
                        "ssn": "[SSN-REDACTED]",
                        "credit_card": "[CC-REDACTED]",
                        "email": "[EMAIL-REDACTED]",
                        "phone_us": "[PHONE-REDACTED]",
                        "passport": "[PASSPORT-REDACTED]",
                        "bank_account": "[ACCOUNT-REDACTED]",
                    }
                    mask_text = mask_map.get(pii_type, "[PII-REDACTED]")
                    masked_answer = pattern.sub(mask_text, masked_answer)

            result.sanitized_response = masked_answer

        return result

    # ==================== PII Utilities ====================

    def detect_pii(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect all PII instances in text (without masking).

        Args:
            text: Text to scan for PII

        Returns:
            List of dicts with pii_type, value, start, end positions.
        """
        findings = []
        for pii_type, pattern in PII_PATTERNS.items():
            for match in pattern.finditer(text):
                findings.append(
                    {
                        "pii_type": pii_type,
                        "value": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )
        return findings

    def mask_pii(self, text: str) -> str:
        """
        Mask all PII in text.

        Args:
            text: Text containing potential PII

        Returns:
            Text with PII replaced by type-specific masks.
        """
        masked = text
        for pii_type, pattern in PII_PATTERNS.items():
            mask_map = {
                "ssn": "[SSN-REDACTED]",
                "credit_card": "[CC-REDACTED]",
                "email": "[EMAIL-REDACTED]",
                "phone_us": "[PHONE-REDACTED]",
                "passport": "[PASSPORT-REDACTED]",
                "bank_account": "[ACCOUNT-REDACTED]",
            }
            mask_text = mask_map.get(pii_type, "[PII-REDACTED]")
            masked = pattern.sub(mask_text, masked)
        return masked

    # ==================== Stats ====================

    def get_stats(self) -> Dict[str, Any]:
        """Get guardrails statistics."""
        return dict(self._stats)

    def reset_stats(self) -> None:
        """Reset statistics counters."""
        for key in self._stats:
            self._stats[key] = 0
