"""Structured JSON logging configuration for the HR platform."""
from __future__ import annotations

import json
import logging
import logging.handlers
import time
import uuid
from contextlib import contextmanager
from typing import Any, Optional

# Try to import pythonjsonlogger for JSON formatting
try:
    from pythonjsonlogger import jsonlogger

    JSON_LOGGER_AVAILABLE = True
except ImportError:
    JSON_LOGGER_AVAILABLE = False


class CorrelationIdFilter(logging.Filter):
    """Add correlation ID to all log records for request tracing.

    This filter adds a unique correlation_id to each log record,
    enabling request tracing across distributed systems.
    """

    def __init__(self):
        """Initialize the filter with a thread-local storage."""
        super().__init__()
        self._correlation_id = None

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation_id to the log record.

        Args:
            record: Log record to filter

        Returns:
            True to allow the log record to be processed
        """
        if not hasattr(record, "correlation_id"):
            record.correlation_id = self.get_correlation_id()
        return True

    @staticmethod
    def get_correlation_id() -> str:
        """Get or create a correlation ID.

        Returns:
            Correlation ID string
        """
        return str(uuid.uuid4())

    @staticmethod
    def set_correlation_id(correlation_id: str) -> None:
        """Set correlation ID for current context.

        Args:
            correlation_id: Correlation ID to set
        """
        # In a production system, this would use contextvars
        pass


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string
        """
        log_obj = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "user_id"):
            log_obj["user_id"] = record.user_id

        if hasattr(record, "request_id"):
            log_obj["request_id"] = record.request_id

        return json.dumps(log_obj)


class RequestLogger:
    """Middleware class for logging HTTP requests (Flask/FastAPI compatible).

    Logs request method, path, status code, duration, user info, and correlation ID.
    """

    def __init__(self, logger: logging.Logger):
        """Initialize request logger.

        Args:
            logger: Logger instance to use
        """
        self.logger = logger

    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        user_id: Optional[int] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """Log HTTP request details.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path
            status_code: HTTP response status code
            duration_ms: Request duration in milliseconds
            user_id: User ID if authenticated
            correlation_id: Correlation ID for tracing
        """
        log_level = logging.WARNING if status_code >= 400 else logging.INFO

        message = f"{method} {path} {status_code} in {duration_ms:.2f}ms"

        extra = {
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
        }

        if user_id:
            extra["user_id"] = user_id

        self.logger.log(log_level, message, extra=extra)

    @staticmethod
    def create_middleware(logger: logging.Logger):
        """Create Flask middleware for request logging.

        Args:
            logger: Logger instance to use

        Returns:
            Flask before/after request handlers
        """
        request_logger = RequestLogger(logger)

        def before_request() -> None:
            """Record request start time."""
            from flask import g

            g._request_start_time = time.time()
            g.correlation_id = str(uuid.uuid4())

        def after_request(response):
            """Log request after response."""
            from flask import g, request

            if hasattr(g, "_request_start_time"):
                duration_ms = (time.time() - g._request_start_time) * 1000
                user_id = getattr(g, "user_id", None)

                request_logger.log_request(
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                    user_id=user_id,
                    correlation_id=getattr(g, "correlation_id", None),
                )
            return response

        return before_request, after_request


@contextmanager
def log_performance(operation_name: str, logger: Optional[logging.Logger] = None):
    """Context manager for logging operation performance.

    Usage:
        with log_performance("database_query"):
            # perform operation
            pass

    Args:
        operation_name: Name of the operation being timed
        logger: Logger instance (defaults to root logger)

    Yields:
        None
    """
    if logger is None:
        logger = logging.getLogger()

    start_time = time.time()
    logger.debug(f"Starting operation: {operation_name}")

    try:
        yield
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Operation {operation_name} failed after {duration_ms:.2f}ms",
            exc_info=True,
        )
        raise
    else:
        duration_ms = (time.time() - start_time) * 1000
        logger.info(f"Operation {operation_name} completed in {duration_ms:.2f}ms")


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure structured JSON logging for the application.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured root logger
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Add correlation ID filter
    correlation_filter = CorrelationIdFilter()
    root_logger.addFilter(correlation_filter)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.addFilter(correlation_filter)

    # Set formatter
    if JSON_LOGGER_AVAILABLE:
        formatter = jsonlogger.JsonFormatter(
            fmt="%(timestamp)s %(level)s %(name)s %(message)s %(correlation_id)s"
        )
    else:
        formatter = JSONFormatter()

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Ensure parent logger is properly configured
    if not logging.root.handlers:
        setup_logging()

    return logger
