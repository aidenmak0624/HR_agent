"""
Admin API Routes for HR Multi-Agent Platform.
User management, role management, audit log access, and system configuration.
Iteration 8 Wave 1 - ADM-001
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================


class PermissionType(str, Enum):
    """Permission types for role-based access control."""

    USER_READ = "user:read"
    USER_CREATE = "user:create"
    USER_UPDATE = "user:update"
    USER_DELETE = "user:delete"
    ROLE_READ = "role:read"
    ROLE_CREATE = "role:create"
    ROLE_UPDATE = "role:update"
    ROLE_DELETE = "role:delete"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    CONFIG_READ = "config:read"
    CONFIG_UPDATE = "config:update"
    SYSTEM_STATS = "system:stats"


class AuditAction(str, Enum):
    """Audit trail action types."""

    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DELETED = "user_deleted"
    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    CONFIG_CHANGED = "config_changed"
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILURE = "login_failure"


# ============================================================================
# Pydantic Models
# ============================================================================


class AdminConfig(BaseModel):
    """Admin system configuration."""

    max_users: int = Field(default=1000, description="Maximum number of users")
    audit_log_retention_days: int = Field(default=365, description="Days to retain audit logs")
    session_timeout_minutes: int = Field(default=60, description="Session timeout in minutes")
    password_policy: Dict[str, Any] = Field(
        default_factory=lambda: {
            "min_length": 12,
            "require_uppercase": True,
            "require_numbers": True,
            "require_special_chars": True,
            "max_age_days": 90,
            "history_count": 5,
        },
        description="Password policy configuration",
    )
    allowed_roles: List[str] = Field(
        default_factory=lambda: ["admin", "manager", "employee", "viewer"],
        description="List of allowed role names",
    )

    model_config = ConfigDict(frozen=False)


class UserRecord(BaseModel):
    """User record in the system."""

    user_id: UUID = Field(default_factory=uuid4, description="Unique user ID")
    username: str = Field(..., min_length=3, max_length=255, description="Username")
    email: str = Field(..., description="User email address")
    role: str = Field(..., description="User role")
    department: str = Field(..., description="Department name")
    is_active: bool = Field(default=True, description="Whether user is active")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional user metadata")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


class RoleDefinition(BaseModel):
    """Role definition with permissions."""

    role_id: UUID = Field(default_factory=uuid4, description="Unique role ID")
    name: str = Field(..., min_length=2, max_length=255, description="Role name")
    description: str = Field(..., description="Role description")
    permissions: List[str] = Field(default_factory=list, description="List of permissions")
    is_system_role: bool = Field(default=False, description="Whether role is system-defined")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    created_by: Optional[str] = Field(None, description="User who created the role")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


class AuditLogEntry(BaseModel):
    """Audit log entry."""

    entry_id: UUID = Field(default_factory=uuid4, description="Unique entry ID")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    user_id: Optional[str] = Field(None, description="User who performed the action")
    action: str = Field(..., description="Action performed")
    resource: str = Field(..., description="Resource affected")
    details: Dict[str, Any] = Field(default_factory=dict, description="Action details")
    ip_address: Optional[str] = Field(None, description="Source IP address")
    status: str = Field(default="success", description="Action status (success/failure)")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


class SystemConfig(BaseModel):
    """System configuration entry."""

    config_id: UUID = Field(default_factory=uuid4, description="Unique config ID")
    key: str = Field(..., description="Configuration key")
    value: Any = Field(..., description="Configuration value")
    category: str = Field(..., description="Configuration category")
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    updated_by: Optional[str] = Field(None, description="User who updated the config")
    is_sensitive: bool = Field(default=False, description="Whether value is sensitive")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total items")
    total_pages: int = Field(..., description="Total pages")

    model_config = ConfigDict(frozen=False)


# ============================================================================
# Admin Service
# ============================================================================


class AdminService:
    """
    Administrative service for user, role, audit, and system management.

    Provides functionality for managing users, roles, audit logs, and system configuration.
    """

    def __init__(self, config: Optional[AdminConfig] = None, audit_logger: Optional[Any] = None):
        """
        Initialize admin service.

        Args:
            config: AdminConfig object with settings
            audit_logger: Logger for audit trail (optional)
        """
        self.config = config or AdminConfig()
        self.audit_logger = audit_logger

        # In-memory storage
        self._users: Dict[UUID, UserRecord] = {}
        self._roles: Dict[UUID, RoleDefinition] = {}
        self._audit_logs: List[AuditLogEntry] = []
        self._system_config: Dict[str, SystemConfig] = {}
        self._start_time = datetime.utcnow()

        # Initialize system roles
        self._init_system_roles()

        logger.info("AdminService initialized with config: %s", self.config)

    def _init_system_roles(self) -> None:
        """Initialize default system roles."""
        try:
            system_roles = [
                {
                    "name": "admin",
                    "description": "System administrator with full access",
                    "permissions": [p.value for p in PermissionType],
                },
                {
                    "name": "manager",
                    "description": "Department manager with user management",
                    "permissions": ["user:read", "user:update", "audit:read", "system:stats"],
                },
                {
                    "name": "employee",
                    "description": "Standard employee",
                    "permissions": ["user:read", "system:stats"],
                },
                {
                    "name": "viewer",
                    "description": "Read-only access",
                    "permissions": ["user:read", "audit:read"],
                },
            ]

            for role_data in system_roles:
                role = RoleDefinition(
                    name=role_data["name"],
                    description=role_data["description"],
                    permissions=role_data["permissions"],
                    is_system_role=True,
                    created_by="SYSTEM",
                )
                self._roles[role.role_id] = role

            logger.info("System roles initialized")
        except Exception as e:
            logger.error("Failed to initialize system roles: %s", str(e))

    def _log_audit(
        self,
        user_id: Optional[str],
        action: str,
        resource: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        status: str = "success",
    ) -> None:
        """
        Log an audit trail entry.

        Args:
            user_id: User performing the action
            action: Action type
            resource: Resource affected
            details: Additional details
            ip_address: Source IP address
            status: Action status (success/failure)
        """
        try:
            entry = AuditLogEntry(
                user_id=user_id,
                action=action,
                resource=resource,
                details=details or {},
                ip_address=ip_address,
                status=status,
            )
            self._audit_logs.append(entry)

            # Trim old logs based on retention policy
            cutoff_date = datetime.utcnow() - timedelta(days=self.config.audit_log_retention_days)
            self._audit_logs = [log for log in self._audit_logs if log.timestamp >= cutoff_date]

            logger.info(
                "Audit logged: %s on %s by %s (status: %s)", action, resource, user_id, status
            )
        except Exception as e:
            logger.error("Failed to log audit: %s", str(e))

    def list_users(
        self, filters: Optional[Dict[str, Any]] = None, page: int = 1, per_page: int = 20
    ) -> Dict[str, Any]:
        """
        List users with optional filters and pagination.

        Args:
            filters: Filter criteria (role, department, is_active)
            page: Page number (1-based)
            per_page: Items per page

        Returns:
            Dictionary with users list and pagination metadata
        """
        try:
            users = list(self._users.values())

            # Apply filters
            if filters:
                if "role" in filters:
                    users = [u for u in users if u.role == filters["role"]]
                if "department" in filters:
                    users = [u for u in users if u.department == filters["department"]]
                if "is_active" in filters:
                    users = [u for u in users if u.is_active == filters["is_active"]]

            total = len(users)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_users = users[start_idx:end_idx]

            return {
                "users": paginated_users,
                "pagination": PaginationMeta(
                    page=page,
                    per_page=per_page,
                    total=total,
                    total_pages=(total + per_page - 1) // per_page,
                ),
            }
        except Exception as e:
            logger.error("Failed to list users: %s", str(e))
            raise

    def get_user(self, user_id: UUID) -> UserRecord:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            UserRecord

        Raises:
            ValueError: If user not found
        """
        try:
            if user_id not in self._users:
                raise ValueError(f"User {user_id} not found")

            logger.info("User retrieved: %s", user_id)
            return self._users[user_id]
        except Exception as e:
            logger.error("Failed to get user: %s", str(e))
            raise

    def create_user(
        self,
        username: str,
        email: str,
        role: str,
        department: str,
        created_by: Optional[str] = None,
    ) -> UserRecord:
        """
        Create a new user.

        Args:
            username: Username
            email: Email address
            role: User role
            department: Department

        Returns:
            Created UserRecord

        Raises:
            ValueError: If validation fails
        """
        try:
            if len(self._users) >= self.config.max_users:
                raise ValueError("Maximum user limit reached")

            if role not in self.config.allowed_roles:
                raise ValueError(f"Invalid role: {role}")

            # Check for duplicate username/email
            for user in self._users.values():
                if user.username == username:
                    raise ValueError(f"Username {username} already exists")
                if user.email == email:
                    raise ValueError(f"Email {email} already exists")

            user = UserRecord(username=username, email=email, role=role, department=department)

            self._users[user.user_id] = user

            self._log_audit(
                user_id=created_by or "SYSTEM",
                action="user_created",
                resource=f"user:{user.user_id}",
                details={
                    "username": username,
                    "email": email,
                    "role": role,
                    "department": department,
                },
            )

            logger.info("User created: %s (%s)", username, user.user_id)
            return user
        except Exception as e:
            logger.error("Failed to create user: %s", str(e))
            raise

    def update_user(
        self, user_id: UUID, updates: Dict[str, Any], updated_by: Optional[str] = None
    ) -> UserRecord:
        """
        Update user information.

        Args:
            user_id: User ID
            updates: Updates to apply
            updated_by: User performing the update

        Returns:
            Updated UserRecord

        Raises:
            ValueError: If user not found
        """
        try:
            if user_id not in self._users:
                raise ValueError(f"User {user_id} not found")

            user = self._users[user_id]
            changeset = {}

            # Apply updates
            for key, value in updates.items():
                if key in ["username", "email", "role", "department", "metadata"]:
                    if key == "role" and value not in self.config.allowed_roles:
                        raise ValueError(f"Invalid role: {value}")

                    old_value = getattr(user, key)
                    setattr(user, key, value)
                    changeset[key] = {"old": old_value, "new": value}

            self._log_audit(
                user_id=updated_by or "SYSTEM",
                action="user_updated",
                resource=f"user:{user_id}",
                details=changeset,
            )

            logger.info("User updated: %s with changes: %s", user_id, changeset)
            return user
        except Exception as e:
            logger.error("Failed to update user: %s", str(e))
            raise

    def deactivate_user(self, user_id: UUID, deactivated_by: Optional[str] = None) -> UserRecord:
        """
        Deactivate a user.

        Args:
            user_id: User ID
            deactivated_by: User performing the deactivation

        Returns:
            Updated UserRecord

        Raises:
            ValueError: If user not found
        """
        try:
            if user_id not in self._users:
                raise ValueError(f"User {user_id} not found")

            user = self._users[user_id]
            user.is_active = False

            self._log_audit(
                user_id=deactivated_by or "SYSTEM",
                action="user_deactivated",
                resource=f"user:{user_id}",
                details={"reason": "manual_deactivation"},
            )

            logger.info("User deactivated: %s", user_id)
            return user
        except Exception as e:
            logger.error("Failed to deactivate user: %s", str(e))
            raise

    def activate_user(self, user_id: UUID, activated_by: Optional[str] = None) -> UserRecord:
        """
        Activate a user.

        Args:
            user_id: User ID
            activated_by: User performing the activation

        Returns:
            Updated UserRecord

        Raises:
            ValueError: If user not found
        """
        try:
            if user_id not in self._users:
                raise ValueError(f"User {user_id} not found")

            user = self._users[user_id]
            user.is_active = True

            self._log_audit(
                user_id=activated_by or "SYSTEM",
                action="user_activated",
                resource=f"user:{user_id}",
                details={"reason": "manual_activation"},
            )

            logger.info("User activated: %s", user_id)
            return user
        except Exception as e:
            logger.error("Failed to activate user: %s", str(e))
            raise

    def list_roles(self) -> List[RoleDefinition]:
        """
        Get all roles.

        Returns:
            List of RoleDefinition objects
        """
        try:
            roles = list(self._roles.values())
            logger.info("Roles listed: %d total", len(roles))
            return roles
        except Exception as e:
            logger.error("Failed to list roles: %s", str(e))
            raise

    def create_role(
        self, name: str, description: str, permissions: List[str], created_by: Optional[str] = None
    ) -> RoleDefinition:
        """
        Create a new role.

        Args:
            name: Role name
            description: Role description
            permissions: List of permissions
            created_by: User creating the role

        Returns:
            Created RoleDefinition

        Raises:
            ValueError: If validation fails
        """
        try:
            # Check for duplicate name
            for role in self._roles.values():
                if role.name == name:
                    raise ValueError(f"Role {name} already exists")

            role = RoleDefinition(
                name=name,
                description=description,
                permissions=permissions,
                is_system_role=False,
                created_by=created_by or "SYSTEM",
            )

            self._roles[role.role_id] = role

            self._log_audit(
                user_id=created_by or "SYSTEM",
                action="role_created",
                resource=f"role:{role.role_id}",
                details={"name": name, "description": description, "permissions": permissions},
            )

            logger.info("Role created: %s (%s)", name, role.role_id)
            return role
        except Exception as e:
            logger.error("Failed to create role: %s", str(e))
            raise

    def update_role(
        self, role_id: UUID, updates: Dict[str, Any], updated_by: Optional[str] = None
    ) -> RoleDefinition:
        """
        Update a role.

        Args:
            role_id: Role ID
            updates: Updates to apply
            updated_by: User performing the update

        Returns:
            Updated RoleDefinition

        Raises:
            ValueError: If role not found or is system role
        """
        try:
            if role_id not in self._roles:
                raise ValueError(f"Role {role_id} not found")

            role = self._roles[role_id]

            if role.is_system_role:
                raise ValueError("System roles cannot be modified")

            changeset = {}

            for key, value in updates.items():
                if key in ["description", "permissions"]:
                    old_value = getattr(role, key)
                    setattr(role, key, value)
                    changeset[key] = {"old": old_value, "new": value}

            self._log_audit(
                user_id=updated_by or "SYSTEM",
                action="role_updated",
                resource=f"role:{role_id}",
                details=changeset,
            )

            logger.info("Role updated: %s with changes: %s", role_id, changeset)
            return role
        except Exception as e:
            logger.error("Failed to update role: %s", str(e))
            raise

    def delete_role(self, role_id: UUID, deleted_by: Optional[str] = None) -> bool:
        """
        Delete a role.

        Args:
            role_id: Role ID
            deleted_by: User performing the deletion

        Returns:
            True if deleted, False otherwise

        Raises:
            ValueError: If role not found or is system role
        """
        try:
            if role_id not in self._roles:
                raise ValueError(f"Role {role_id} not found")

            role = self._roles[role_id]

            if role.is_system_role:
                raise ValueError("System roles cannot be deleted")

            del self._roles[role_id]

            self._log_audit(
                user_id=deleted_by or "SYSTEM",
                action="role_deleted",
                resource=f"role:{role_id}",
                details={"name": role.name},
            )

            logger.info("Role deleted: %s", role_id)
            return True
        except Exception as e:
            logger.error("Failed to delete role: %s", str(e))
            raise

    def get_audit_logs(
        self,
        filters: Optional[Dict[str, Any]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page: int = 1,
        per_page: int = 50,
    ) -> Dict[str, Any]:
        """
        Get audit logs with filtering and pagination.

        Args:
            filters: Filter criteria (user_id, action, resource)
            start_date: Start date for filtering
            end_date: End date for filtering
            page: Page number (1-based)
            per_page: Items per page

        Returns:
            Dictionary with audit logs and pagination metadata
        """
        try:
            logs = list(self._audit_logs)

            # Apply date filters
            if start_date:
                logs = [l for l in logs if l.timestamp >= start_date]
            if end_date:
                logs = [l for l in logs if l.timestamp <= end_date]

            # Apply filters
            if filters:
                if "user_id" in filters:
                    logs = [l for l in logs if l.user_id == filters["user_id"]]
                if "action" in filters:
                    logs = [l for l in logs if l.action == filters["action"]]
                if "resource" in filters:
                    logs = [l for l in logs if l.resource == filters["resource"]]
                if "status" in filters:
                    logs = [l for l in logs if l.status == filters["status"]]

            # Sort by timestamp descending
            logs.sort(key=lambda x: x.timestamp, reverse=True)

            total = len(logs)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_logs = logs[start_idx:end_idx]

            return {
                "entries": paginated_logs,
                "pagination": PaginationMeta(
                    page=page,
                    per_page=per_page,
                    total=total,
                    total_pages=(total + per_page - 1) // per_page,
                ),
            }
        except Exception as e:
            logger.error("Failed to get audit logs: %s", str(e))
            raise

    def export_audit_logs(
        self, start_date: datetime, end_date: datetime, format: str = "json"
    ) -> Dict[str, Any]:
        """
        Export audit logs in specified format.

        Args:
            start_date: Start date for export
            end_date: End date for export
            format: Export format (json, csv)

        Returns:
            Dictionary with data and format

        Raises:
            ValueError: If format unsupported
        """
        try:
            if format not in ["json", "csv"]:
                raise ValueError(f"Unsupported format: {format}")

            logs = [l for l in self._audit_logs if start_date <= l.timestamp <= end_date]

            if format == "json":
                data = [l.model_dump() for l in logs]
            else:  # csv
                data = []
                for log in logs:
                    data.append(
                        {
                            "timestamp": log.timestamp.isoformat(),
                            "user_id": log.user_id,
                            "action": log.action,
                            "resource": log.resource,
                            "status": log.status,
                        }
                    )

            self._log_audit(
                user_id="SYSTEM",
                action="audit_exported",
                resource="audit_logs",
                details={"format": format, "log_count": len(logs)},
            )

            logger.info("Audit logs exported: %d entries in %s format", len(logs), format)
            return {
                "data": data,
                "format": format,
                "count": len(logs),
                "exported_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error("Failed to export audit logs: %s", str(e))
            raise

    def get_system_config(self, category: Optional[str] = None) -> List[SystemConfig]:
        """
        Get system configuration entries.

        Args:
            category: Optional category filter

        Returns:
            List of SystemConfig objects
        """
        try:
            configs = list(self._system_config.values())

            if category:
                configs = [c for c in configs if c.category == category]

            logger.info("System config retrieved: %d entries", len(configs))
            return configs
        except Exception as e:
            logger.error("Failed to get system config: %s", str(e))
            raise

    def update_system_config(
        self, key: str, value: Any, updated_by: Optional[str] = None
    ) -> SystemConfig:
        """
        Update system configuration.

        Args:
            key: Configuration key
            value: Configuration value
            updated_by: User performing the update

        Returns:
            Updated SystemConfig

        Raises:
            ValueError: If key invalid
        """
        try:
            if not key:
                raise ValueError("Configuration key cannot be empty")

            # Update or create config
            config = SystemConfig(
                key=key,
                value=value,
                category="system",
                updated_by=updated_by or "SYSTEM",
                is_sensitive=False,
            )

            self._system_config[key] = config

            self._log_audit(
                user_id=updated_by or "SYSTEM",
                action="config_changed",
                resource=f"config:{key}",
                details={"new_value": str(value)[:100]},  # Truncate for logging
            )

            logger.info("System config updated: %s", key)
            return config
        except Exception as e:
            logger.error("Failed to update system config: %s", str(e))
            raise

    def get_system_stats(self) -> Dict[str, Any]:
        """
        Get system statistics.

        Returns:
            Dictionary with system statistics
        """
        try:
            uptime_seconds = (datetime.utcnow() - self._start_time).total_seconds()
            active_users = sum(1 for u in self._users.values() if u.is_active)

            stats = {
                "total_users": len(self._users),
                "active_users": active_users,
                "total_roles": len(self._roles),
                "audit_log_entries": len(self._audit_logs),
                "system_config_items": len(self._system_config),
                "uptime_seconds": uptime_seconds,
                "uptime_hours": round(uptime_seconds / 3600, 2),
                "timestamp": datetime.utcnow().isoformat(),
                "module_status": {
                    "users": "operational",
                    "roles": "operational",
                    "audit": "operational",
                    "config": "operational",
                },
            }

            logger.info("System stats retrieved")
            return stats
        except Exception as e:
            logger.error("Failed to get system stats: %s", str(e))
            raise
