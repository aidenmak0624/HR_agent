"""
CORE-004: PII Stripping Middleware
Detects and redacts personally identifiable information from HR data.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PIIResult:
    """Result from PII detection and stripping."""
    sanitized_text: str
    mapping: Dict[str, str] = field(default_factory=dict)
    pii_count: int = 0
    pii_types_found: List[str] = field(default_factory=list)


class PIIStripper:
    """
    Detects and redacts personally identifiable information.
    
    Supports detection and redaction of:
    - Social Security Numbers (SSN)
    - Email addresses
    - Phone numbers
    - Names (from context)
    - Employee IDs
    - Salary/dollar amounts
    """
    
    # PII Patterns
    SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    )
    PHONE_PATTERN = re.compile(
        r'(?:\+1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}\b'
    )
    EMPLOYEE_ID_PATTERN = re.compile(r'\bEMP-\d+\b')
    SALARY_PATTERN = re.compile(r'\$[\d,]+(?:\.\d{2})?')
    
    def __init__(self, enable_name_detection: bool = True):
        """
        Initialize PII Stripper.
        
        Args:
            enable_name_detection: Whether to detect names from context
        """
        self.enable_name_detection = enable_name_detection
    
    def strip(
        self,
        text: str,
        employee_context: Optional[List[str]] = None
    ) -> PIIResult:
        """
        Strip PII from text and return mapping for rehydration.
        
        Args:
            text: Text to process
            employee_context: List of employee names to detect and redact
        
        Returns:
            PIIResult with sanitized text and mapping dict
        """
        if not text:
            return PIIResult(sanitized_text='', mapping={}, pii_count=0)
        
        sanitized_text = text
        mapping = {}
        pii_types_found = set()
        
        # Process SSN
        ssn_matches = list(self.SSN_PATTERN.finditer(sanitized_text))
        for match in reversed(ssn_matches):  # Reverse to maintain indices
            original = match.group()
            redacted = '[SSN_REDACTED]'
            mapping[original] = redacted
            pii_types_found.add('SSN')
            sanitized_text = (
                sanitized_text[:match.start()] +
                redacted +
                sanitized_text[match.end():]
            )
        
        # Process Email
        email_counter = 1
        email_matches = list(self.EMAIL_PATTERN.finditer(sanitized_text))
        for match in reversed(email_matches):
            original = match.group()
            redacted = f'[EMAIL_REDACTED_{email_counter}]'
            mapping[original] = redacted
            pii_types_found.add('EMAIL')
            sanitized_text = (
                sanitized_text[:match.start()] +
                redacted +
                sanitized_text[match.end():]
            )
            email_counter += 1
        
        # Process Phone
        phone_matches = list(self.PHONE_PATTERN.finditer(sanitized_text))
        for match in reversed(phone_matches):
            original = match.group()
            redacted = '[PHONE_REDACTED]'
            mapping[original] = redacted
            pii_types_found.add('PHONE')
            sanitized_text = (
                sanitized_text[:match.start()] +
                redacted +
                sanitized_text[match.end():]
            )
        
        # Process Employee ID
        emp_id_matches = list(self.EMPLOYEE_ID_PATTERN.finditer(sanitized_text))
        for match in reversed(emp_id_matches):
            original = match.group()
            redacted = '[EMPLOYEE_ID_REDACTED]'
            mapping[original] = redacted
            pii_types_found.add('EMPLOYEE_ID')
            sanitized_text = (
                sanitized_text[:match.start()] +
                redacted +
                sanitized_text[match.end():]
            )
        
        # Process Salary
        salary_matches = list(self.SALARY_PATTERN.finditer(sanitized_text))
        for match in reversed(salary_matches):
            original = match.group()
            redacted = '[SALARY_REDACTED]'
            mapping[original] = redacted
            pii_types_found.add('SALARY')
            sanitized_text = (
                sanitized_text[:match.start()] +
                redacted +
                sanitized_text[match.end():]
            )
        
        # Process Names from context
        if self.enable_name_detection and employee_context:
            person_counter = 1
            for name in sorted(employee_context, key=len, reverse=True):
                name_pattern = re.compile(r'\b' + re.escape(name) + r'\b')
                matches = list(name_pattern.finditer(sanitized_text))
                for match in reversed(matches):
                    redacted = f'[PERSON_{person_counter}]'
                    mapping[name] = redacted
                    pii_types_found.add('NAME')
                    sanitized_text = (
                        sanitized_text[:match.start()] +
                        redacted +
                        sanitized_text[match.end():]
                    )
                person_counter += 1
        
        return PIIResult(
            sanitized_text=sanitized_text,
            mapping=mapping,
            pii_count=len(mapping),
            pii_types_found=sorted(list(pii_types_found))
        )
    
    def rehydrate(self, text: str, mapping: Dict[str, str]) -> str:
        """
        Restore original PII values from mapping.
        
        Args:
            text: Sanitized text with redaction placeholders
            mapping: Mapping from original to redacted values
        
        Returns:
            Text with original values restored
        """
        result = text
        
        # Reverse mapping to go from redacted back to original
        reverse_mapping = {v: k for k, v in mapping.items()}
        
        for redacted, original in reverse_mapping.items():
            result = result.replace(redacted, original)
        
        return result
    
    def is_pii_safe(self, text: str) -> bool:
        """
        Check if text contains any PII patterns.
        
        Args:
            text: Text to check
        
        Returns:
            True if no PII found, False otherwise
        """
        if self.SSN_PATTERN.search(text):
            return False
        if self.EMAIL_PATTERN.search(text):
            return False
        if self.PHONE_PATTERN.search(text):
            return False
        if self.EMPLOYEE_ID_PATTERN.search(text):
            return False
        if self.SALARY_PATTERN.search(text):
            return False
        
        return True


class PIIMiddleware:
    """Flask middleware for automatic PII stripping and rehydration."""
    
    def __init__(self, app: Any = None, stripper: Optional[PIIStripper] = None):
        """
        Initialize PII middleware.
        
        Args:
            app: Flask application instance
            stripper: PIIStripper instance (creates default if None)
        """
        self.app = app
        self.stripper = stripper or PIIStripper()
        
        if app:
            self.init_app(app)
    
    def init_app(self, app: Any) -> None:
        """Register middleware with Flask app."""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self) -> None:
        """Strip PII from request before processing."""
        try:
            from flask import g, request
        except ImportError:
            logger.warning("Flask not available for PII middleware")
            return
        
        g.pii_mapping = {}
        g.pii_stripped = False
        
        # Process request body if JSON
        if request.is_json and request.get_data():
            try:
                data = request.get_json(silent=True)
                if data:
                    data_str = json.dumps(data)
                    result = self.stripper.strip(data_str)
                    
                    if result.pii_count > 0:
                        g.pii_mapping = result.mapping
                        g.pii_stripped = True
                        logger.info(
                            f"Stripped {result.pii_count} PII items "
                            f"from request: {result.pii_types_found}"
                        )
            except Exception as e:
                logger.warning(f"Error stripping request PII: {str(e)}")
    
    def after_request(self, response: Any) -> Any:
        """Rehydrate PII in response before sending."""
        try:
            from flask import g
        except ImportError:
            return response
        
        if not hasattr(g, 'pii_mapping') or not g.pii_mapping:
            return response
        
        try:
            if response.is_json:
                data = response.get_json(silent=True)
                if data:
                    data_str = json.dumps(data)
                    rehydrated = self.stripper.rehydrate(data_str, g.pii_mapping)
                    response.set_data(rehydrated)
                    logger.info("Rehydrated PII in response")
        except Exception as e:
            logger.warning(f"Error rehydrating response PII: {str(e)}")
        
        return response
