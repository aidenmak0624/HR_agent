"""JWT Authentication Service for HR multi-agent platform."""

import os
import logging
import uuid
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional

import jwt
from flask import Flask, g, request

from config.settings import get_settings

logger = logging.getLogger(__name__)


# Custom Exceptions
class AuthError(Exception):
    """Base authentication error."""

    pass


class TokenExpiredError(AuthError):
    """Token has expired."""

    pass


class TokenRevokedError(AuthError):
    """Token has been revoked."""

    pass


class InvalidTokenError(AuthError):
    """Token is invalid or malformed."""

    pass


# Role Hierarchy
ROLE_HIERARCHY = {
    "employee": 1,
    "manager": 2,
    "hr_generalist": 3,
    "hr_admin": 4,
}


class AuthService:
    """JWT Authentication Service for managing tokens and user sessions."""

    ACCESS_TOKEN_TTL = 3600  # 1 hour
    REFRESH_TOKEN_TTL = 604800  # 7 days
    TOKEN_TYPE_ACCESS = "access"
    TOKEN_TYPE_REFRESH = "refresh"

    def __init__(self, cache_service: Optional[Any] = None) -> None:
        """Initialize AuthService with optional cache backend.

        Args:
            cache_service: Optional cache service for token blacklisting.
                          Should have set(key, value, ttl) and get(key) methods.
        """
        self.cache = cache_service
        self.settings = get_settings()

        # Get JWT secret from environment variable, with settings fallback
        self.jwt_secret = os.environ.get(
            "JWT_SECRET",
            self.settings.JWT_SECRET
        )

        # Warn if using default JWT secret (security risk in production)
        if self.jwt_secret == "your-secret-key-change-in-production" or self.jwt_secret == "hr-platform-secret-key-change-in-production":
            logger.warning(
                "⚠️  WARNING: Using default JWT_SECRET! This is a security risk in production. "
                "Set the JWT_SECRET environment variable to a secure value."
            )

        self.jwt_algorithm = self.settings.JWT_ALGORITHM

    def generate_token(
        self, user_id: str, email: str, role: str, department: str
    ) -> Dict[str, Any]:
        """Generate access and refresh tokens for a user.

        Args:
            user_id: Unique user identifier
            email: User email address
            role: User role (employee, manager, hr_generalist, hr_admin)
            department: User department

        Returns:
            Dictionary with access_token, refresh_token, and expires_at timestamp

        Raises:
            AuthError: If token generation fails
        """
        try:
            now = datetime.utcnow()
            jti = str(uuid.uuid4())

            # Generate access token
            access_payload = {
                "user_id": user_id,
                "email": email,
                "role": role,
                "department": department,
                "iat": now,
                "exp": now + timedelta(seconds=self.ACCESS_TOKEN_TTL),
                "jti": jti,
                "type": self.TOKEN_TYPE_ACCESS,
            }
            access_token = jwt.encode(
                access_payload, self.jwt_secret, algorithm=self.jwt_algorithm
            )

            # Generate refresh token with different JTI
            refresh_jti = str(uuid.uuid4())
            refresh_payload = {
                "user_id": user_id,
                "email": email,
                "role": role,
                "department": department,
                "iat": now,
                "exp": now + timedelta(seconds=self.REFRESH_TOKEN_TTL),
                "jti": refresh_jti,
                "type": self.TOKEN_TYPE_REFRESH,
            }
            refresh_token = jwt.encode(
                refresh_payload, self.jwt_secret, algorithm=self.jwt_algorithm
            )

            expires_at = (now + timedelta(seconds=self.ACCESS_TOKEN_TTL)).isoformat()

            return {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "token_type": "Bearer",
            }
        except Exception as e:
            raise AuthError(f"Failed to generate tokens: {str(e)}")

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token.

        Args:
            token: JWT token string

        Returns:
            Dictionary with user_id, email, role, department, jti, and type

        Raises:
            TokenExpiredError: If token has expired
            TokenRevokedError: If token has been revoked
            InvalidTokenError: If token is invalid or malformed
        """
        try:
            payload = jwt.decode(
                token, self.jwt_secret, algorithms=[self.jwt_algorithm]
            )
        except jwt.ExpiredSignatureError:
            raise TokenExpiredError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {str(e)}")

        # Check if token is revoked
        jti = payload.get("jti")
        if jti and self.is_revoked(jti):
            raise TokenRevokedError("Token has been revoked")

        return {
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "role": payload.get("role"),
            "department": payload.get("department"),
            "jti": jti,
            "type": payload.get("type"),
        }

    def refresh_token(self, refresh_token_str: str) -> Dict[str, Any]:
        """Generate a new access token using a refresh token.

        Args:
            refresh_token_str: Valid refresh token

        Returns:
            Dictionary with new access_token and expires_at

        Raises:
            InvalidTokenError: If refresh token is invalid
            TokenExpiredError: If refresh token has expired
            TokenRevokedError: If refresh token has been revoked
        """
        payload = self.verify_token(refresh_token_str)

        if payload.get("type") != self.TOKEN_TYPE_REFRESH:
            raise InvalidTokenError("Token is not a refresh token")

        # Generate new access token with same user info
        new_tokens = self.generate_token(
            payload["user_id"],
            payload["email"],
            payload["role"],
            payload["department"],
        )

        return {
            "access_token": new_tokens["access_token"],
            "expires_at": new_tokens["expires_at"],
            "token_type": "Bearer",
        }

    def revoke_token(self, jti: str) -> None:
        """Revoke a token by adding its JTI to the blacklist.

        Args:
            jti: JWT ID to revoke

        Raises:
            AuthError: If cache service is not available
        """
        if not self.cache:
            raise AuthError("Cache service not configured for token revocation")

        # Set blacklist entry with TTL matching token expiration
        blacklist_key = f"revoked_token:{jti}"
        self.cache.set(blacklist_key, True, ttl=self.REFRESH_TOKEN_TTL)

    def is_revoked(self, jti: str) -> bool:
        """Check if a token has been revoked.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is revoked, False otherwise
        """
        if not self.cache:
            return False

        blacklist_key = f"revoked_token:{jti}"
        return self.cache.get(blacklist_key) is not None


# Flask Decorators
def require_auth(f: Callable) -> Callable:
    """Decorator to enforce JWT authentication on Flask routes.

    Extracts Bearer token from Authorization header, verifies it,
    and sets g.current_user with user information.

    Raises:
        AuthError: If no token provided or token is invalid

    Usage:
        @app.route('/protected')
        @require_auth
        def protected_route():
            user_id = g.current_user['user_id']
            ...
    """

    @wraps(f)
    def decorated_function(*args, **kwargs) -> Any:
        auth_header = request.headers.get("Authorization", "")

        if not auth_header:
            raise AuthError("Missing Authorization header")

        # Extract Bearer token
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthError("Invalid Authorization header format")

        token = parts[1]

        # Verify token
        auth_service = AuthService()
        try:
            user_data = auth_service.verify_token(token)
            g.current_user = user_data
        except AuthError as e:
            raise e

        return f(*args, **kwargs)

    return decorated_function


def require_role(min_role: str) -> Callable:
    """Decorator to enforce role-based access control.

    Checks if current user has the required role or higher in hierarchy.
    Must be used after @require_auth.

    Args:
        min_role: Minimum required role (employee, manager, hr_generalist, hr_admin)

    Raises:
        AuthError: If user role is insufficient

    Usage:
        @app.route('/admin')
        @require_auth
        @require_role('hr_admin')
        def admin_route():
            ...
    """

    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs) -> Any:
            if not hasattr(g, "current_user"):
                raise AuthError("User not authenticated. Use @require_auth first.")

            user_role = g.current_user.get("role")
            if not user_role:
                raise AuthError("User role not found in token")

            min_role_level = ROLE_HIERARCHY.get(min_role)
            user_role_level = ROLE_HIERARCHY.get(user_role)

            if min_role_level is None:
                raise AuthError(f"Invalid role requirement: {min_role}")

            if user_role_level is None:
                raise AuthError(f"Invalid user role: {user_role}")

            if user_role_level < min_role_level:
                raise AuthError(
                    f"Insufficient permissions. Required role: {min_role}, "
                    f"User role: {user_role}"
                )

            return f(*args, **kwargs)

        return decorated_function

    return decorator
