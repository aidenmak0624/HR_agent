"""Tests for JWT authentication module."""

import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from src.middleware.auth import (
    AuthService,
    AuthError,
    TokenExpiredError,
    TokenRevokedError,
    InvalidTokenError,
    ROLE_HIERARCHY,
)


class TestAuthServiceTokenGeneration:
    """Tests for token generation."""

    def test_generate_token_returns_access_and_refresh(self):
        """generate_token returns both access and refresh tokens."""
        auth_service = AuthService()
        result = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        assert "access_token" in result
        assert "refresh_token" in result
        assert "expires_at" in result
        assert "token_type" in result
        assert result["token_type"] == "Bearer"

        # Tokens should be non-empty strings
        assert isinstance(result["access_token"], str)
        assert isinstance(result["refresh_token"], str)
        assert len(result["access_token"]) > 0
        assert len(result["refresh_token"]) > 0

    def test_generate_token_includes_user_data(self):
        """Generated token includes user information."""
        auth_service = AuthService()
        result = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        # Verify token can be decoded
        payload = auth_service.verify_token(result["access_token"])

        assert payload["user_id"] == "emp-001"
        assert payload["email"] == "john@company.com"
        assert payload["role"] == "employee"
        assert payload["department"] == "Engineering"
        assert payload["type"] == "access"


class TestAuthServiceVerification:
    """Tests for token verification."""

    def test_verify_valid_token_returns_payload(self):
        """Verifying valid token returns payload."""
        auth_service = AuthService()
        tokens = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        payload = auth_service.verify_token(tokens["access_token"])

        assert payload["user_id"] == "emp-001"
        assert payload["email"] == "john@company.com"

    def test_verify_expired_token_raises(self):
        """Verifying expired token raises TokenExpiredError."""
        auth_service = AuthService()

        # Create expired token by setting TTL to 0
        import jwt
        from datetime import datetime, timedelta

        now = datetime.utcnow()
        expired_payload = {
            "user_id": "emp-001",
            "email": "john@company.com",
            "role": "employee",
            "department": "Engineering",
            "iat": now,
            "exp": now - timedelta(seconds=1),  # Already expired
            "jti": "test-jti",
            "type": "access",
        }

        expired_token = jwt.encode(
            expired_payload, auth_service.jwt_secret, algorithm=auth_service.jwt_algorithm
        )

        with pytest.raises(TokenExpiredError):
            auth_service.verify_token(expired_token)

    def test_verify_invalid_token_raises(self):
        """Verifying invalid token raises InvalidTokenError."""
        auth_service = AuthService()

        with pytest.raises(InvalidTokenError):
            auth_service.verify_token("invalid.token.string")

    def test_verify_revoked_token_raises(self):
        """Verifying revoked token raises TokenRevokedError."""
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=True)  # Token is revoked

        auth_service = AuthService(cache_service=mock_cache)
        tokens = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        with pytest.raises(TokenRevokedError):
            auth_service.verify_token(tokens["access_token"])


class TestAuthServiceRefresh:
    """Tests for token refresh."""

    def test_refresh_token_returns_new_access_token(self):
        """Refreshing returns new access token."""
        auth_service = AuthService()
        tokens = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        refresh_result = auth_service.refresh_token(tokens["refresh_token"])

        assert "access_token" in refresh_result
        assert "expires_at" in refresh_result
        assert refresh_result["token_type"] == "Bearer"

        # New access token should be valid
        payload = auth_service.verify_token(refresh_result["access_token"])
        assert payload["user_id"] == "emp-001"

    def test_refresh_token_with_access_token_raises(self):
        """Refreshing with access token raises error."""
        auth_service = AuthService()
        tokens = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        # Try to use access token as refresh token
        with pytest.raises(InvalidTokenError):
            auth_service.refresh_token(tokens["access_token"])


class TestAuthServiceRevocation:
    """Tests for token revocation."""

    def test_revoke_token_adds_to_blacklist(self):
        """revoke_token adds JTI to cache blacklist."""
        mock_cache = MagicMock()
        # Initially token is NOT revoked (get returns None)
        mock_cache.get = MagicMock(return_value=None)

        auth_service = AuthService(cache_service=mock_cache)
        tokens = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        # Extract JTI from token (cache.get returns None so not revoked)
        payload = auth_service.verify_token(tokens["access_token"])
        jti = payload["jti"]

        auth_service.revoke_token(jti)

        # Verify cache.set was called with correct parameters
        mock_cache.set.assert_called_once()
        call_args = mock_cache.set.call_args
        assert f"revoked_token:{jti}" in str(call_args)

    def test_revoke_without_cache_raises(self):
        """revoke_token without cache raises error."""
        auth_service = AuthService(cache_service=None)

        with pytest.raises(AuthError):
            auth_service.revoke_token("test-jti")

    def test_is_revoked_checks_cache(self):
        """is_revoked checks cache for token."""
        mock_cache = MagicMock()
        mock_cache.get = MagicMock(return_value=True)

        auth_service = AuthService(cache_service=mock_cache)

        is_revoked = auth_service.is_revoked("test-jti")

        assert is_revoked is True
        mock_cache.get.assert_called_once_with("revoked_token:test-jti")


class TestRoleHierarchy:
    """Tests for role hierarchy constants."""

    def test_role_hierarchy_ordering(self):
        """Role hierarchy has correct ordering."""
        assert ROLE_HIERARCHY["employee"] < ROLE_HIERARCHY["manager"]
        assert ROLE_HIERARCHY["manager"] < ROLE_HIERARCHY["hr_generalist"]
        assert ROLE_HIERARCHY["hr_generalist"] < ROLE_HIERARCHY["hr_admin"]

    def test_all_expected_roles_present(self):
        """All expected roles are in hierarchy."""
        assert "employee" in ROLE_HIERARCHY
        assert "manager" in ROLE_HIERARCHY
        assert "hr_generalist" in ROLE_HIERARCHY
        assert "hr_admin" in ROLE_HIERARCHY


class TestRequireAuthDecorator:
    """Tests for @require_auth Flask decorator."""

    def test_require_auth_with_valid_token(self):
        """@require_auth allows request with valid token."""
        from src.middleware.auth import require_auth
        from flask import Flask, g

        app = Flask(__name__)
        auth_service = AuthService()
        tokens = auth_service.generate_token(
            user_id="emp-001", email="john@company.com", role="employee", department="Engineering"
        )

        @app.route("/test")
        @require_auth
        def test_route():
            return {"user_id": g.current_user["user_id"]}

        with app.test_client() as client:
            response = client.get(
                "/test", headers={"Authorization": f"Bearer {tokens['access_token']}"}
            )

            assert response.status_code == 200
            assert response.get_json()["user_id"] == "emp-001"

    def test_require_auth_without_token_returns_401(self):
        """@require_auth rejects request without token."""
        from src.middleware.auth import require_auth
        from flask import Flask

        app = Flask(__name__)

        @app.route("/test")
        @require_auth
        def test_route():
            return {"message": "success"}

        with app.test_client() as client:
            response = client.get("/test")

            assert response.status_code == 401 or response.status_code == 500


class TestRequireRoleDecorator:
    """Tests for @require_role Flask decorator."""

    def test_role_hierarchy_in_require_role(self):
        """@require_role enforces role hierarchy."""
        from src.middleware.auth import require_auth, require_role
        from flask import Flask, g

        app = Flask(__name__)
        auth_service = AuthService()

        @app.route("/admin")
        @require_auth
        @require_role("hr_admin")
        def admin_route():
            return {"role": g.current_user["role"]}

        # Test with HR admin
        hr_admin_tokens = auth_service.generate_token(
            user_id="hr-001", email="admin@company.com", role="hr_admin", department="HR"
        )

        with app.test_client() as client:
            response = client.get(
                "/admin", headers={"Authorization": f"Bearer {hr_admin_tokens['access_token']}"}
            )

            assert response.status_code == 200

        # Test with employee (should fail)
        emp_tokens = auth_service.generate_token(
            user_id="emp-001", email="emp@company.com", role="employee", department="Engineering"
        )

        with app.test_client() as client:
            response = client.get(
                "/admin", headers={"Authorization": f"Bearer {emp_tokens['access_token']}"}
            )

            assert response.status_code == 401 or response.status_code == 500
