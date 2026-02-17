"""Input sanitization middleware for Flask applications.

Sanitizes all JSON body inputs:
- Strips HTML tags from string values
- Validates email format
- Caps string lengths (1000 chars default, 5000 for specific fields)
"""

import logging
import re
from typing import Any, Dict, Optional

from flask import Flask, request, g

logger = logging.getLogger(__name__)

# HTML tag regex pattern
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')

# Email validation regex
EMAIL_PATTERN = re.compile(
    r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
)

# Fields that allow longer strings
LONG_STRING_FIELDS = {'reason', 'query', 'description', 'comments', 'feedback', 'notes'}

# Default string length limits
DEFAULT_STRING_LIMIT = 1000
LONG_STRING_LIMIT = 5000


class InputSanitizer:
    """Sanitizes input data to prevent injection attacks."""

    @staticmethod
    def strip_html(value: str) -> str:
        """Remove HTML tags from a string.

        Args:
            value: String potentially containing HTML

        Returns:
            String with HTML tags removed
        """
        if not isinstance(value, str):
            return value
        return HTML_TAG_PATTERN.sub('', value)

    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format.

        Args:
            email: Email address to validate

        Returns:
            True if valid email format, False otherwise
        """
        if not isinstance(email, str):
            return False
        return bool(EMAIL_PATTERN.match(email.lower()))

    @staticmethod
    def sanitize_string(
        value: str,
        field_name: str = "",
        strip_html: bool = True,
        max_length: Optional[int] = None,
    ) -> str:
        """Sanitize a string value.

        Args:
            value: String to sanitize
            field_name: Name of the field (used to determine max length)
            strip_html: Whether to remove HTML tags (default: True)
            max_length: Override maximum length (uses field-specific if None)

        Returns:
            Sanitized string
        """
        if not isinstance(value, str):
            return str(value) if value is not None else ""

        # Determine maximum length
        if max_length is None:
            if field_name in LONG_STRING_FIELDS:
                max_length = LONG_STRING_LIMIT
            else:
                max_length = DEFAULT_STRING_LIMIT

        # Strip leading/trailing whitespace
        value = value.strip()

        # Strip HTML if requested
        if strip_html:
            value = InputSanitizer.strip_html(value)

        # Truncate to max length
        if len(value) > max_length:
            logger.warning(
                f"String truncated for field '{field_name}': "
                f"{len(value)} -> {max_length} chars"
            )
            value = value[:max_length]

        return value

    @staticmethod
    def sanitize_dict(
        data: Dict[str, Any],
        email_fields: Optional[list[str]] = None,
    ) -> Dict[str, Any]:
        """Sanitize all string values in a dictionary.

        Args:
            data: Dictionary to sanitize
            email_fields: List of field names that contain emails

        Returns:
            Dictionary with sanitized values
        """
        if email_fields is None:
            email_fields = []

        sanitized = {}

        for key, value in data.items():
            if isinstance(value, str):
                # Check if this is an email field
                if key in email_fields:
                    value = InputSanitizer.sanitize_string(value, field_name=key, strip_html=False)
                    if value and not InputSanitizer.validate_email(value):
                        logger.warning(f"Invalid email format in field '{key}': {value}")
                else:
                    value = InputSanitizer.sanitize_string(value, field_name=key)

            elif isinstance(value, dict):
                # Recursively sanitize nested dictionaries
                value = InputSanitizer.sanitize_dict(value, email_fields)

            elif isinstance(value, (list, tuple)):
                # Sanitize items in lists/tuples
                sanitized_list = []
                for item in value:
                    if isinstance(item, str):
                        sanitized_list.append(InputSanitizer.sanitize_string(item, field_name=key))
                    elif isinstance(item, dict):
                        sanitized_list.append(InputSanitizer.sanitize_dict(item, email_fields))
                    else:
                        sanitized_list.append(item)
                value = type(value)(sanitized_list)  # Preserve list vs tuple

            sanitized[key] = value

        return sanitized


class RequestSanitizer:
    """Flask middleware for sanitizing request data."""

    def __init__(self, app: Optional[Flask] = None):
        """Initialize the request sanitizer.

        Args:
            app: Flask application instance (can be set later with init_app)
        """
        self.app = app
        if app:
            self.init_app(app)

    def init_app(self, app: Flask) -> None:
        """Register sanitization hooks with Flask app.

        Args:
            app: Flask application instance
        """
        self.app = app
        app.before_request(self._before_request)

    def _before_request(self) -> None:
        """Sanitize incoming request data."""
        # Only process JSON requests with POST/PUT/PATCH
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if request.is_json:
                try:
                    data = request.get_json(silent=True)
                    if data:
                        # Define email fields based on endpoint
                        email_fields = ['email', 'from_email', 'to_email', 'user_email']

                        # Sanitize the data
                        sanitized_data = InputSanitizer.sanitize_dict(data, email_fields)

                        # Store sanitized data in Flask context for use in route handlers
                        g.sanitized_json = sanitized_data

                        # For convenience, also make it available through request object
                        # by replacing the get_json method
                        original_get_json = request.get_json

                        def patched_get_json(*args, **kwargs):
                            return g.sanitized_json

                        request.get_json = patched_get_json

                except Exception as e:
                    logger.error(f"Error sanitizing request data: {e}")
                    # Continue anyway - don't block requests due to sanitization errors

    @staticmethod
    def get_sanitized_json(default: Optional[Dict] = None) -> Dict[str, Any]:
        """Get sanitized JSON data from the current request.

        Args:
            default: Default value if no sanitized data available

        Returns:
            Sanitized JSON data or default
        """
        if default is None:
            default = {}
        return g.get("sanitized_json", default)


def setup_request_sanitization(app: Flask) -> None:
    """Setup request sanitization for the Flask app.

    Args:
        app: Flask application instance
    """
    sanitizer = RequestSanitizer(app)
    logger.info("Request input sanitization enabled")
