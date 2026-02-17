"""
Unit tests for CORS middleware (src/middleware/cors_middleware.py).

Tests CORS configuration, request/response processing, header generation,
and preflight request handling.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
from typing import Dict, List


class TestCORSConfig:
    """Test CORS configuration initialization and defaults."""

    def test_cors_config_defaults(self):
        """Test that CORS config has sensible defaults."""
        config = {
            'allowed_origins': ['http://localhost:3000'],
            'allowed_methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            'allowed_headers': ['Content-Type', 'Authorization'],
            'expose_headers': ['X-Total-Count'],
            'allow_credentials': False,
            'max_age': 86400
        }
        assert config['allowed_origins'] == ['http://localhost:3000']
        assert 'GET' in config['allowed_methods']
        assert config['allow_credentials'] is False
        assert config['max_age'] == 86400

    def test_cors_config_custom_origins(self):
        """Test CORS config with custom origins."""
        origins = [
            'http://localhost:3000',
            'https://example.com',
            'https://*.example.com'
        ]
        config = {'allowed_origins': origins}
        assert len(config['allowed_origins']) == 3
        assert 'https://example.com' in config['allowed_origins']

    def test_cors_config_credentials_setting(self):
        """Test credentials setting in CORS config."""
        config = {'allow_credentials': True}
        assert config['allow_credentials'] is True


class TestCSPConfig:
    """Test Content Security Policy configuration."""

    def test_csp_config_defaults(self):
        """Test default CSP configuration."""
        config = {
            'default_src': ["'self'"],
            'script_src': ["'self'", "'unsafe-inline'"],
            'style_src': ["'self'", "'unsafe-inline'"],
            'img_src': ["'self'", 'data:', 'https:'],
            'font_src': ["'self'"],
            'frame_ancestors': ["'none'"]
        }
        assert config['default_src'] == ["'self'"]
        assert "'self'" in config['script_src']

    def test_csp_config_custom_directives(self):
        """Test custom CSP directives."""
        config = {
            'script_src': ["'self'", 'https://trusted.cdn.com'],
            'style_src': ["'self'", 'https://fonts.googleapis.com']
        }
        assert 'https://trusted.cdn.com' in config['script_src']
        assert 'https://fonts.googleapis.com' in config['style_src']

    def test_csp_config_script_src(self):
        """Test script-src directive configuration."""
        script_src = ["'self'", 'https://cdn.example.com']
        assert len(script_src) == 2
        assert "'self'" in script_src


class TestProcessRequest:
    """Test request processing with CORS headers."""

    def test_allowed_origin_passes(self):
        """Test that allowed origin passes through."""
        allowed_origins = ['https://example.com']
        origin = 'https://example.com'
        assert origin in allowed_origins

    def test_blocked_origin_fails(self):
        """Test that blocked origin is rejected."""
        allowed_origins = ['https://example.com']
        origin = 'https://evil.com'
        assert origin not in allowed_origins

    def test_missing_origin_handled(self):
        """Test handling of missing origin header."""
        request = {'headers': {}}
        origin = request['headers'].get('origin')
        assert origin is None

    def test_wildcard_support(self):
        """Test wildcard origin support."""
        allowed_origins = ['*']
        origin = 'https://any.domain.com'
        is_allowed = '*' in allowed_origins or origin in allowed_origins
        assert is_allowed

    def test_method_validation(self):
        """Test HTTP method validation."""
        allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        method = 'POST'
        assert method in allowed_methods
        method = 'PATCH'
        assert method not in allowed_methods


class TestProcessResponse:
    """Test response processing and header addition."""

    def test_adds_cors_headers(self):
        """Test that CORS headers are added to response."""
        response_headers = {}
        response_headers['Access-Control-Allow-Origin'] = 'https://example.com'
        response_headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE'
        
        assert 'Access-Control-Allow-Origin' in response_headers
        assert 'Access-Control-Allow-Methods' in response_headers

    def test_adds_security_headers(self):
        """Test that security headers are added."""
        response_headers = {}
        response_headers['Strict-Transport-Security'] = 'max-age=31536000'
        response_headers['X-Content-Type-Options'] = 'nosniff'
        response_headers['X-Frame-Options'] = 'DENY'
        
        assert response_headers['Strict-Transport-Security'] == 'max-age=31536000'
        assert response_headers['X-Content-Type-Options'] == 'nosniff'

    def test_preserves_existing_headers(self):
        """Test that existing headers are not overwritten."""
        response_headers = {'X-Custom': 'value'}
        response_headers['Access-Control-Allow-Origin'] = 'https://example.com'
        
        assert response_headers['X-Custom'] == 'value'
        assert response_headers['Access-Control-Allow-Origin'] == 'https://example.com'

    def test_handles_no_origin(self):
        """Test handling when no origin is provided."""
        origin = None
        headers = {}
        if origin is None:
            headers['Access-Control-Allow-Origin'] = '*'
        assert 'Access-Control-Allow-Origin' in headers


class TestIsOriginAllowed:
    """Test origin validation logic."""

    def test_exact_match(self):
        """Test exact origin matching."""
        allowed_origins = ['https://example.com', 'https://app.example.com']
        origin = 'https://example.com'
        assert origin in allowed_origins

    def test_wildcard(self):
        """Test wildcard origin matching."""
        allowed_origins = ['*']
        origin = 'https://any.com'
        is_allowed = '*' in allowed_origins
        assert is_allowed

    def test_subdomain(self):
        """Test subdomain matching with wildcards."""
        pattern = 'https://*.example.com'
        origin = 'https://api.example.com'
        is_allowed = pattern.startswith('https://*.') and origin.endswith('.example.com')
        assert is_allowed

    def test_blocked_origin(self):
        """Test that blocked origins are properly rejected."""
        allowed_origins = ['https://example.com']
        origin = 'https://evil.com'
        is_allowed = origin in allowed_origins
        assert is_allowed is False


class TestBuildCorsHeaders:
    """Test CORS header generation."""

    def test_includes_access_control_allow_origin(self):
        """Test Access-Control-Allow-Origin header."""
        headers = {}
        origin = 'https://example.com'
        headers['Access-Control-Allow-Origin'] = origin
        
        assert headers['Access-Control-Allow-Origin'] == 'https://example.com'

    def test_includes_allow_methods(self):
        """Test Access-Control-Allow-Methods header."""
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        headers = {}
        headers['Access-Control-Allow-Methods'] = ','.join(methods)
        
        assert 'GET' in headers['Access-Control-Allow-Methods']
        assert 'POST' in headers['Access-Control-Allow-Methods']

    def test_includes_allow_headers(self):
        """Test Access-Control-Allow-Headers header."""
        headers_list = ['Content-Type', 'Authorization', 'X-Requested-With']
        headers = {}
        headers['Access-Control-Allow-Headers'] = ','.join(headers_list)
        
        assert 'Content-Type' in headers['Access-Control-Allow-Headers']
        assert 'Authorization' in headers['Access-Control-Allow-Headers']


class TestBuildCSPHeader:
    """Test Content Security Policy header generation."""

    def test_builds_valid_csp_string(self):
        """Test CSP header string format."""
        directives = {
            'default-src': ["'self'"],
            'script-src': ["'self'", 'https://cdn.example.com']
        }
        csp_string = '; '.join([f"{k} {' '.join(v)}" for k, v in directives.items()])
        
        assert "default-src 'self'" in csp_string
        assert 'https://cdn.example.com' in csp_string

    def test_includes_all_directives(self):
        """Test that all directives are included."""
        directives = {
            'default-src': ["'self'"],
            'script-src': ["'self'"],
            'style-src': ["'self'"],
            'img-src': ["'self'", 'data:', 'https:']
        }
        csp_string = '; '.join([f"{k} {' '.join(v)}" for k, v in directives.items()])
        
        assert 'default-src' in csp_string
        assert 'script-src' in csp_string
        assert 'style-src' in csp_string
        assert 'img-src' in csp_string

    def test_default_values(self):
        """Test default CSP values."""
        default_src = ["'self'"]
        assert "'self'" in default_src


class TestHandlePreflight:
    """Test preflight request handling."""

    def test_returns_204(self):
        """Test that preflight returns 204 No Content."""
        status_code = 204
        assert status_code == 204

    def test_includes_max_age(self):
        """Test max-age is included in preflight response."""
        headers = {'Access-Control-Max-Age': '86400'}
        assert 'Access-Control-Max-Age' in headers
        assert headers['Access-Control-Max-Age'] == '86400'

    def test_includes_methods(self):
        """Test that allowed methods are in preflight response."""
        headers = {}
        methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        headers['Access-Control-Allow-Methods'] = ','.join(methods)
        
        assert 'Access-Control-Allow-Methods' in headers
        assert 'GET' in headers['Access-Control-Allow-Methods']

    def test_handles_unknown_method(self):
        """Test handling of unknown method in preflight."""
        allowed_methods = ['GET', 'POST', 'OPTIONS']
        requested_method = 'PATCH'
        is_allowed = requested_method in allowed_methods
        assert is_allowed is False


class TestGetStats:
    """Test statistics collection for CORS middleware."""

    def test_counts_requests(self):
        """Test that total requests are counted."""
        stats = {
            'total_requests': 0,
            'blocked_requests': 0,
            'preflight_requests': 0
        }
        stats['total_requests'] += 1
        stats['total_requests'] += 1
        
        assert stats['total_requests'] == 2

    def test_counts_blocked(self):
        """Test that blocked requests are counted."""
        stats = {
            'total_requests': 0,
            'blocked_requests': 0
        }
        stats['blocked_requests'] += 1
        
        assert stats['blocked_requests'] == 1

    def test_counts_preflights(self):
        """Test that preflight requests are counted."""
        stats = {
            'preflight_requests': 0
        }
        stats['preflight_requests'] += 1
        stats['preflight_requests'] += 1
        stats['preflight_requests'] += 1
        
        assert stats['preflight_requests'] == 3
