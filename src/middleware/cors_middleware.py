"""
CORS and Content Security Policy Middleware for HR Multi-Agent Platform.
Enforces CORS policies and adds security headers to all responses.
Iteration 6 - SEC-001
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


class CORSConfig(BaseModel):
    """CORS configuration model."""

    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5050"],
        description="Allowed origin URLs",
    )
    allowed_methods: List[str] = Field(
        default=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        description="Allowed HTTP methods",
    )
    allowed_headers: List[str] = Field(
        default=["Content-Type", "Authorization", "X-Correlation-ID"],
        description="Allowed request headers",
    )
    expose_headers: List[str] = Field(
        default=["X-Request-ID", "X-Correlation-ID"],
        description="Headers exposed to client",
    )
    max_age: int = Field(default=3600, description="Preflight cache duration in seconds")
    allow_credentials: bool = Field(
        default=True, description="Allow credentials in CORS requests"
    )

    model_config = ConfigDict(frozen=False)


class CSPConfig(BaseModel):
    """Content Security Policy configuration model."""

    default_src: str = Field(default="'self'", description="Default CSP source")
    script_src: str = Field(
        default="'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        description="Script source policy",
    )
    style_src: str = Field(
        default="'self' 'unsafe-inline'", description="Style source policy"
    )
    img_src: str = Field(default="'self' data:", description="Image source policy")
    font_src: str = Field(default="'self'", description="Font source policy")
    connect_src: str = Field(default="'self'", description="Connect source policy")
    frame_ancestors: str = Field(
        default="'none'", description="Frame ancestors policy"
    )
    base_uri: str = Field(default="'self'", description="Base URI policy")
    form_action: str = Field(default="'self'", description="Form action policy")

    model_config = ConfigDict(frozen=False)


class CORSMiddleware:
    """
    CORS and Content Security Policy middleware.
    Enforces CORS policies and adds security headers to responses.
    """

    def __init__(
        self,
        cors_config: Optional[CORSConfig] = None,
        csp_config: Optional[CSPConfig] = None,
    ) -> None:
        """
        Initialize CORS middleware.

        Args:
            cors_config: CORS configuration (uses defaults if None)
            csp_config: CSP configuration (uses defaults if None)
        """
        self.cors_config = cors_config or CORSConfig()
        self.csp_config = csp_config or CSPConfig()
        self.requests_processed: int = 0
        self.origins_blocked: int = 0
        self.preflights_handled: int = 0

        logger.info(
            "CORS middleware initialized",
            extra={
                "allowed_origins": len(self.cors_config.allowed_origins),
                "allowed_methods": self.cors_config.allowed_methods,
            },
        )

    def process_request(
        self,
        request_headers: Dict[str, str],
        method: str,
        origin: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Process incoming request and validate CORS origin.

        Args:
            request_headers: Request headers dictionary
            method: HTTP method
            origin: Origin header value

        Returns:
            Dictionary with CORS validation result and response headers
        """
        self.requests_processed += 1

        if origin is None:
            logger.debug("No origin header in request")
            return {"allowed": True, "headers": {}}

        if not self._is_origin_allowed(origin):
            self.origins_blocked += 1
            logger.warning(
                "CORS origin blocked",
                extra={"origin": origin, "method": method},
            )
            return {
                "allowed": False,
                "error": "Origin not allowed",
                "status_code": 403,
            }

        headers = self._build_cors_headers(origin)
        logger.debug("CORS request validated", extra={"origin": origin})
        return {"allowed": True, "headers": headers}

    def process_response(
        self, response_headers: Dict[str, str], origin: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Add CORS and security headers to response.

        Args:
            response_headers: Existing response headers
            origin: Origin header from request

        Returns:
            Enhanced response headers dictionary
        """
        headers = response_headers.copy()

        if origin and self._is_origin_allowed(origin):
            cors_headers = self._build_cors_headers(origin)
            headers.update(cors_headers)

        csp_header = self._build_csp_header()
        headers["Content-Security-Policy"] = csp_header

        security_headers = self._build_security_headers()
        headers.update(security_headers)

        return headers

    def _is_origin_allowed(self, origin: str) -> bool:
        """
        Check if origin is in allowed list (supports wildcard).

        Args:
            origin: Origin URL to check

        Returns:
            True if origin is allowed, False otherwise
        """
        for allowed in self.cors_config.allowed_origins:
            if allowed == "*":
                return True
            if allowed == origin:
                return True
            if allowed.endswith("*"):
                pattern = allowed.replace("*", "")
                if origin.startswith(pattern):
                    return True

        return False

    def _build_cors_headers(self, origin: str) -> Dict[str, str]:
        """
        Build CORS response headers.

        Args:
            origin: Allowed origin

        Returns:
            Dictionary of CORS headers
        """
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Methods": ", ".join(self.cors_config.allowed_methods),
            "Access-Control-Allow-Headers": ", ".join(self.cors_config.allowed_headers),
            "Access-Control-Expose-Headers": ", ".join(self.cors_config.expose_headers),
            "Access-Control-Max-Age": str(self.cors_config.max_age),
        }

        if self.cors_config.allow_credentials:
            headers["Access-Control-Allow-Credentials"] = "true"

        return headers

    def _build_csp_header(self) -> str:
        """
        Build Content-Security-Policy header value.

        Returns:
            CSP header string
        """
        csp_directives = [
            f"default-src {self.csp_config.default_src}",
            f"script-src {self.csp_config.script_src}",
            f"style-src {self.csp_config.style_src}",
            f"img-src {self.csp_config.img_src}",
            f"font-src {self.csp_config.font_src}",
            f"connect-src {self.csp_config.connect_src}",
            f"frame-ancestors {self.csp_config.frame_ancestors}",
            f"base-uri {self.csp_config.base_uri}",
            f"form-action {self.csp_config.form_action}",
        ]

        return "; ".join(csp_directives)

    def _build_security_headers(self) -> Dict[str, str]:
        """
        Build additional security headers.

        Returns:
            Dictionary of security headers
        """
        return {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

    def handle_preflight(
        self,
        origin: str,
        method: str,
        headers: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Handle CORS preflight (OPTIONS) request.

        Args:
            origin: Request origin
            method: Requested method
            headers: Requested headers

        Returns:
            Dictionary with 204 status and CORS headers
        """
        self.preflights_handled += 1

        if not self._is_origin_allowed(origin):
            logger.warning(
                "Preflight rejected",
                extra={"origin": origin},
            )
            return {"status_code": 403, "headers": {}}

        cors_headers = self._build_cors_headers(origin)
        logger.debug("Preflight handled", extra={"origin": origin, "method": method})

        return {
            "status_code": 204,
            "headers": cors_headers,
        }

    def get_stats(self) -> Dict[str, any]:
        """
        Get middleware statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "requests_processed": self.requests_processed,
            "origins_blocked": self.origins_blocked,
            "preflights_handled": self.preflights_handled,
            "block_rate": (
                self.origins_blocked / self.requests_processed
                if self.requests_processed > 0
                else 0
            ),
        }
