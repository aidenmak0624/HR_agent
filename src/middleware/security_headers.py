"""
Security Headers Middleware for HR Multi-Agent Platform.
Aggregates all security-related response headers.
Iteration 6 - SEC-004 (part of security audit)
"""

import logging
from typing import Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class SecurityHeadersConfig(BaseModel):
    """Security headers configuration model."""

    enable_hsts: bool = Field(
        default=True, description="Enable HTTP Strict Transport Security"
    )
    hsts_max_age: int = Field(
        default=31536000, description="HSTS max-age in seconds (1 year)"
    )
    enable_csp: bool = Field(
        default=True, description="Enable Content Security Policy"
    )
    enable_xfo: bool = Field(
        default=True, description="Enable X-Frame-Options"
    )
    xfo_value: str = Field(
        default="DENY", description="X-Frame-Options value"
    )
    enable_xcto: bool = Field(
        default=True, description="Enable X-Content-Type-Options"
    )
    enable_referrer_policy: bool = Field(
        default=True, description="Enable Referrer-Policy"
    )
    referrer_policy: str = Field(
        default="strict-origin-when-cross-origin",
        description="Referrer-Policy value",
    )
    enable_permissions_policy: bool = Field(
        default=True, description="Enable Permissions-Policy"
    )
    custom_headers: Dict[str, str] = Field(
        default={}, description="Custom security headers"
    )

    model_config = ConfigDict(frozen=False)


class SecurityHeadersMiddleware:
    """
    Security headers middleware.
    Aggregates all security-related response headers.
    """

    def __init__(self, config: Optional[SecurityHeadersConfig] = None) -> None:
        """
        Initialize security headers middleware.

        Args:
            config: Security headers configuration (uses defaults if None)
        """
        self.config = config or SecurityHeadersConfig()

        logger.info(
            "Security headers middleware initialized",
            extra={
                "hsts_enabled": self.config.enable_hsts,
                "csp_enabled": self.config.enable_csp,
                "xfo_enabled": self.config.enable_xfo,
                "permissions_policy_enabled": self.config.enable_permissions_policy,
            },
        )

    def get_headers(self) -> Dict[str, str]:
        """
        Get all security headers as dictionary.

        Returns:
            Dictionary of security headers
        """
        headers = {}

        # HSTS
        if self.config.enable_hsts:
            headers["Strict-Transport-Security"] = self._hsts_header()

        # X-Frame-Options
        if self.config.enable_xfo:
            headers["X-Frame-Options"] = self._xfo_header()

        # X-Content-Type-Options
        if self.config.enable_xcto:
            headers["X-Content-Type-Options"] = self._xcto_header()

        # Referrer-Policy
        if self.config.enable_referrer_policy:
            headers["Referrer-Policy"] = self._referrer_header()

        # Permissions-Policy
        if self.config.enable_permissions_policy:
            headers["Permissions-Policy"] = self._permissions_policy()

        # Additional security headers
        headers["X-XSS-Protection"] = "1; mode=block"
        headers["X-Content-Type-Options"] = "nosniff"

        # Custom headers
        if self.config.custom_headers:
            headers.update(self.config.custom_headers)

        return headers

    def _hsts_header(self) -> str:
        """
        Build Strict-Transport-Security header value.

        Returns:
            HSTS header string
        """
        return f"max-age={self.config.hsts_max_age}; includeSubDomains; preload"

    def _xfo_header(self) -> str:
        """
        Build X-Frame-Options header value.

        Returns:
            X-Frame-Options header string
        """
        return self.config.xfo_value

    def _xcto_header(self) -> str:
        """
        Build X-Content-Type-Options header value.

        Returns:
            X-Content-Type-Options header string
        """
        return "nosniff"

    def _referrer_header(self) -> str:
        """
        Build Referrer-Policy header value.

        Returns:
            Referrer-Policy header string
        """
        return self.config.referrer_policy

    def _permissions_policy(self) -> str:
        """
        Build Permissions-Policy header value.

        Returns:
            Permissions-Policy header string
        """
        permissions = [
            'camera=()',
            'microphone=()',
            'geolocation=()',
            'payment=()',
            'usb=()',
            'magnetometer=()',
            'gyroscope=()',
            'accelerometer=()',
        ]

        return ", ".join(permissions)

    def apply_to_response(self, response_headers: Dict[str, str]) -> Dict[str, str]:
        """
        Apply security headers to response.

        Args:
            response_headers: Existing response headers

        Returns:
            Response headers with security headers applied
        """
        headers = response_headers.copy()
        security_headers = self.get_headers()
        headers.update(security_headers)

        logger.debug(
            "Security headers applied",
            extra={"header_count": len(security_headers)},
        )

        return headers

    def validate_headers(self, headers: Dict[str, str]) -> List[str]:
        """
        Validate response headers for missing security headers.

        Args:
            headers: Response headers to validate

        Returns:
            List of warnings for missing recommended headers
        """
        warnings = []

        recommended_headers = {
            "Strict-Transport-Security": "HSTS protection",
            "X-Frame-Options": "Clickjacking protection",
            "X-Content-Type-Options": "MIME type sniffing protection",
            "Content-Security-Policy": "XSS and injection protection",
            "X-XSS-Protection": "Browser XSS protection",
            "Referrer-Policy": "Referrer privacy control",
            "Permissions-Policy": "Feature permissions control",
        }

        for header, description in recommended_headers.items():
            if header not in headers:
                warnings.append(f"Missing {header}: {description}")

        logger.debug(
            "Header validation completed",
            extra={"warnings": len(warnings)},
        )

        return warnings
