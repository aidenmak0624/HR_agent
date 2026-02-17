"""Structured request logging middleware for Flask applications.

Logs request details in JSON format for structured analysis:
- HTTP method, path, status code
- Response time in milliseconds
- User ID, IP address
- Skips logging for static files and health checks
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional

from flask import Flask, g, request

logger = logging.getLogger(__name__)


class StructuredLogger:
    """Structured logging for HTTP requests in JSON format."""

    # Paths to skip logging (static files, health checks)
    SKIP_PATHS = {
        "/static/",
        "/api/v2/health",
        "/health",
        "/ping",
        "/.well-known/",
    }

    def __init__(self, app: Optional[Flask] = None):
        """Initialize the structured logger.

        Args:
            app: Flask application instance (can be set later with init_app)
        """
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Register logging hooks with Flask app.

        Args:
            app: Flask application instance
        """
        self.app = app
        app.before_request(self._before_request)
        app.after_request(self._after_request)

    def _should_skip_logging(self, path: str) -> bool:
        """Check if the request path should be skipped from logging.

        Args:
            path: Request path

        Returns:
            True if path should be skipped, False otherwise
        """
        return any(path.startswith(skip) for skip in self.SKIP_PATHS)

    def _before_request(self) -> None:
        """Hook called before each request."""
        if not hasattr(g, "request_start_time"):
            g.request_start_time = time.time()

    def _after_request(self, response):
        """Hook called after each request.

        Args:
            response: Flask response object

        Returns:
            The response object (unmodified)
        """
        # Skip logging for certain paths
        if self._should_skip_logging(request.path):
            return response

        # Calculate request duration in milliseconds
        start_time = g.get("request_start_time", time.time())
        duration_ms = (time.time() - start_time) * 1000

        # Extract user information
        user_id = g.get("user_context", {}).get("user_id", "anonymous")
        user_role = g.get("user_context", {}).get("role", "unknown")

        # Get client IP (consider X-Forwarded-For for proxies)
        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or request.remote_addr
            or "unknown"
        )

        # Build structured log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": g.get("request_id", "unknown"),
            "method": request.method,
            "path": request.path,
            "query_string": request.query_string.decode("utf-8") if request.query_string else "",
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "user_id": user_id,
            "user_role": user_role,
            "client_ip": client_ip,
            "user_agent": request.headers.get("User-Agent", "")[:200],  # Truncate long user agents
        }

        # Log at different levels based on status code
        if response.status_code >= 500:
            logger.error("HTTP_REQUEST", extra=log_entry)
        elif response.status_code >= 400:
            logger.warning("HTTP_REQUEST", extra=log_entry)
        else:
            logger.info("HTTP_REQUEST", extra=log_entry)

        return response

    @staticmethod
    def format_json_log(record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: LogRecord from Python logging

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
        }

        # Add any extra fields passed to the logger
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in (
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                ):
                    log_data[key] = value

        return json.dumps(log_data)


class JsonFormatter(logging.Formatter):
    """Custom formatter that outputs JSON-formatted logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: LogRecord from Python logging

        Returns:
            JSON-formatted log string
        """
        return StructuredLogger.format_json_log(record)


def setup_structured_logging(app: Flask) -> None:
    """Setup structured JSON logging for the Flask app.

    Args:
        app: Flask application instance
    """
    # Initialize request logging
    logger_instance = StructuredLogger(app)

    # Optionally configure JSON formatter on root logger
    # Uncomment if you want all logs in JSON format:
    # root_logger = logging.getLogger()
    # for handler in root_logger.handlers:
    #     handler.setFormatter(JsonFormatter())

    logger.info("Structured request logging enabled")
