"""
Unit tests for Admin API Routes.
Iteration 8 Wave 1 - ADM-001 Test Suite
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock

from src.api.admin_routes import (
    AdminConfig,
    UserRecord,
    RoleDefinition,
    AuditLogEntry,
    SystemConfig,
    PaginationMeta,
    AdminService,
    PermissionType,
    AuditAction,
)


# ============================================================================
# AdminConfig Tests
# ============================================================================

class TestAdminConfig:
    """Tests for AdminConfig model."""

    def test_admin_config_defaults(self):
        """Test AdminConfig uses correct default values."""
        config = AdminConfig()

        assert config.max_users == 1000
        assert config.audit_log_retention_days == 365
        assert config.session_timeout_minutes == 60
        assert config.allowed_roles == ["admin", "manager", "employee", "viewer"]

    def test_admin_config_custom_values(self):
        """Test AdminConfig with custom values."""
        config = AdminConfig(
            max_users=500,
            audit_log_retention_days=180,
            session_timeout_minutes=30,
            allowed_roles=["admin", "user"]
        )

        assert config.max_users == 500
        assert config.audit_log_retention_days == 180
        assert config.session_timeout_minutes == 30
        assert config.allowed_roles == ["admin", "user"]

    def test_admin_config_password_policy(self):
        """Test AdminConfig password policy field."""
        config = AdminConfig()

        assert "min_length" in config.password_policy
        assert config.password_policy["min_length"] == 12
        assert config.password_policy["require_uppercase"] is True
        assert config.password_policy["require_numbers"] is True
        assert config.password_policy["require_special_chars"] is True
        assert config.password_policy["max_age_days"] == 90
        assert config.password_policy["history_count"] == 5


# ============================================================================
# UserRecord Tests
# ============================================================================

class TestUserRecord:
    """Tests for UserRecord model."""

    def test_user_record_defaults(self):
        """Test UserRecord with default values."""
        user = UserRecord(
            username="john_doe",
            email="john@example.com",
            role="employee",
            department="Engineering"
        )

        assert isinstance(user.user_id, UUID)
        assert user.username == "john_doe"
        assert user.email == "john@example.com"
        assert user.role == "employee"
        assert user.department == "Engineering"
        assert user.is_active is True
        assert user.permissions == []
        assert user.metadata == {}

    def test_user_record_custom_values(self):
        """Test UserRecord with custom values."""
        user_id = uuid4()
        user = UserRecord(
            user_id=user_id,
            username="admin_user",
            email="admin@example.com",
            role="admin",
            department="Management",
            is_active=False,
            permissions=["user:read", "user:create"],
            metadata={"phone": "555-1234"}
        )

        assert user.user_id == user_id
        assert user.username == "admin_user"
        assert user.is_active is False
        assert user.permissions == ["user:read", "user:create"]
        assert user.metadata["phone"] == "555-1234"

    def test_user_record_uuid_generation(self):
        """Test UserRecord generates unique UUIDs."""
        user1 = UserRecord(
            username="user1",
            email="user1@example.com",
            role="employee",
            department="Engineering"
        )
        user2 = UserRecord(
            username="user2",
            email="user2@example.com",
            role="employee",
            department="Engineering"
        )

        assert user1.user_id != user2.user_id

    def test_user_record_permissions_list(self):
        """Test UserRecord permissions list handling."""
        permissions = ["user:read", "user:update", "audit:read"]
        user = UserRecord(
            username="manager_user",
            email="manager@example.com",
            role="manager",
            department="Management",
            permissions=permissions
        )

        assert user.permissions == permissions
        assert len(user.permissions) == 3


# ============================================================================
# RoleDefinition Tests
# ============================================================================

class TestRoleDefinition:
    """Tests for RoleDefinition model."""

    def test_role_definition_defaults(self):
        """Test RoleDefinition with default values."""
        role = RoleDefinition(
            name="custom_role",
            description="A custom role",
            permissions=["user:read", "user:update"]
        )

        assert isinstance(role.role_id, UUID)
        assert role.name == "custom_role"
        assert role.description == "A custom role"
        assert role.is_system_role is False
        assert role.created_by is None

    def test_role_definition_custom_values(self):
        """Test RoleDefinition with custom values."""
        role_id = uuid4()
        created_at = datetime.utcnow()
        role = RoleDefinition(
            role_id=role_id,
            name="senior_manager",
            description="Senior manager role",
            permissions=["user:read", "user:create", "user:update"],
            is_system_role=False,
            created_at=created_at,
            created_by="admin_user"
        )

        assert role.role_id == role_id
        assert role.is_system_role is False
        assert role.created_by == "admin_user"

    def test_role_definition_system_role_flag(self):
        """Test RoleDefinition system role flag."""
        system_role = RoleDefinition(
            name="admin",
            description="Admin role",
            permissions=[],
            is_system_role=True,
            created_by="SYSTEM"
        )

        assert system_role.is_system_role is True
        assert system_role.created_by == "SYSTEM"


# ============================================================================
# AuditLogEntry Tests
# ============================================================================

class TestAuditLogEntry:
    """Tests for AuditLogEntry model."""

    def test_audit_log_entry_defaults(self):
        """Test AuditLogEntry with default values."""
        entry = AuditLogEntry(
            action="user_created",
            resource="user:123"
        )

        assert isinstance(entry.entry_id, UUID)
        assert isinstance(entry.timestamp, datetime)
        assert entry.action == "user_created"
        assert entry.resource == "user:123"
        assert entry.status == "success"
        assert entry.details == {}
        assert entry.user_id is None

    def test_audit_log_entry_custom_values(self):
        """Test AuditLogEntry with custom values."""
        timestamp = datetime.utcnow()
        entry = AuditLogEntry(
            entry_id=uuid4(),
            timestamp=timestamp,
            user_id="admin_user",
            action="user_updated",
            resource="user:456",
            details={"field": "role", "old": "employee", "new": "manager"},
            ip_address="192.168.1.1",
            status="success"
        )

        assert entry.user_id == "admin_user"
        assert entry.action == "user_updated"
        assert entry.ip_address == "192.168.1.1"
        assert entry.details["field"] == "role"

    def test_audit_log_entry_status_field(self):
        """Test AuditLogEntry status field."""
        success_entry = AuditLogEntry(
            action="user_created",
            resource="user:789",
            status="success"
        )

        failure_entry = AuditLogEntry(
            action="user_created",
            resource="user:999",
            status="failure"
        )

        assert success_entry.status == "success"
        assert failure_entry.status == "failure"


# ============================================================================
# SystemConfig Tests
# ============================================================================

class TestSystemConfig:
    """Tests for SystemConfig model."""

    def test_system_config_defaults(self):
        """Test SystemConfig with default values."""
        config = SystemConfig(
            key="app_name",
            value="HR Agent",
            category="general"
        )

        assert isinstance(config.config_id, UUID)
        assert config.key == "app_name"
        assert config.value == "HR Agent"
        assert config.category == "general"
        assert config.is_sensitive is False

    def test_system_config_custom_values(self):
        """Test SystemConfig with custom values."""
        config_id = uuid4()
        updated_at = datetime.utcnow()
        config = SystemConfig(
            config_id=config_id,
            key="api_key",
            value="secret_key_12345",
            category="security",
            updated_at=updated_at,
            updated_by="admin_user",
            is_sensitive=True
        )

        assert config.config_id == config_id
        assert config.updated_by == "admin_user"
        assert config.is_sensitive is True

    def test_system_config_is_sensitive(self):
        """Test SystemConfig is_sensitive field."""
        sensitive_config = SystemConfig(
            key="db_password",
            value="secret_password",
            category="database",
            is_sensitive=True
        )

        non_sensitive_config = SystemConfig(
            key="app_version",
            value="1.0.0",
            category="general",
            is_sensitive=False
        )

        assert sensitive_config.is_sensitive is True
        assert non_sensitive_config.is_sensitive is False


# ============================================================================
# AdminService Tests
# ============================================================================

class TestAdminServiceInit:
    """Tests for AdminService initialization."""

    def test_admin_service_init_with_config(self):
        """Test AdminService creates with provided config."""
        config = AdminConfig(max_users=500)
        service = AdminService(config=config)

        assert service.config == config
        assert service.config.max_users == 500

    def test_admin_service_init_default_config(self):
        """Test AdminService creates with default config."""
        service = AdminService()

        assert service.config is not None
        assert service.config.max_users == 1000

    def test_admin_service_init_system_roles(self):
        """Test AdminService initializes system roles."""
        service = AdminService()

        roles = service.list_roles()
        role_names = [role.name for role in roles]

        assert "admin" in role_names
        assert "manager" in role_names
        assert "employee" in role_names
        assert "viewer" in role_names


# ============================================================================
# List Users Tests
# ============================================================================

class TestListUsers:
    """Tests for AdminService.list_users()."""

    def test_list_users_returns_users(self):
        """Test list_users returns all users."""
        service = AdminService()
        user1 = service.create_user("user1", "user1@example.com", "employee", "Eng")
        user2 = service.create_user("user2", "user2@example.com", "manager", "Sales")

        result = service.list_users()

        assert result["users"]
        assert len(result["users"]) == 2

    def test_list_users_pagination(self):
        """Test list_users pagination."""
        service = AdminService()
        for i in range(5):
            service.create_user(f"user{i}", f"user{i}@example.com", "employee", "Eng")

        result = service.list_users(page=1, per_page=2)

        assert len(result["users"]) == 2
        assert result["pagination"].total == 5
        assert result["pagination"].page == 1

    def test_list_users_filters(self):
        """Test list_users with filters."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")
        service.create_user("user2", "user2@example.com", "manager", "Sales")

        result = service.list_users(filters={"role": "employee"})

        assert len(result["users"]) == 1
        assert result["users"][0].role == "employee"


# ============================================================================
# Create User Tests
# ============================================================================

class TestCreateUser:
    """Tests for AdminService.create_user()."""

    def test_create_user_creates_user(self):
        """Test create_user creates a new user."""
        service = AdminService()
        user = service.create_user("john_doe", "john@example.com", "employee", "Engineering")

        assert user.username == "john_doe"
        assert user.email == "john@example.com"
        assert user.role == "employee"
        assert user.department == "Engineering"

    def test_create_user_assigns_uuid(self):
        """Test create_user assigns UUID."""
        service = AdminService()
        user = service.create_user("test_user", "test@example.com", "employee", "Engineering")

        assert isinstance(user.user_id, UUID)

    def test_create_user_validates_role(self):
        """Test create_user validates role."""
        service = AdminService()

        with pytest.raises(ValueError, match="Invalid role"):
            service.create_user("test_user", "test@example.com", "invalid_role", "Engineering")

    def test_create_user_no_duplicates(self):
        """Test create_user prevents duplicate users."""
        service = AdminService()
        service.create_user("john_doe", "john@example.com", "employee", "Engineering")

        with pytest.raises(ValueError, match="already exists"):
            service.create_user("john_doe", "john2@example.com", "employee", "Engineering")


# ============================================================================
# Update User Tests
# ============================================================================

class TestUpdateUser:
    """Tests for AdminService.update_user()."""

    def test_update_user_updates_fields(self):
        """Test update_user updates fields."""
        service = AdminService()
        user = service.create_user("john_doe", "john@example.com", "employee", "Engineering")

        updated = service.update_user(user.user_id, {"role": "manager"})

        assert updated.role == "manager"

    def test_update_user_returns_updated(self):
        """Test update_user returns updated user."""
        service = AdminService()
        user = service.create_user("jane_doe", "jane@example.com", "employee", "Engineering")

        updated = service.update_user(user.user_id, {"department": "Sales"})

        assert updated.department == "Sales"
        assert updated.username == "jane_doe"

    def test_update_user_missing_user(self):
        """Test update_user raises for missing user."""
        service = AdminService()
        fake_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            service.update_user(fake_id, {"role": "manager"})


# ============================================================================
# Deactivate/Activate User Tests
# ============================================================================

class TestDeactivateActivateUser:
    """Tests for AdminService deactivate/activate user."""

    def test_deactivate_user_deactivates(self):
        """Test deactivate_user deactivates user."""
        service = AdminService()
        user = service.create_user("john_doe", "john@example.com", "employee", "Engineering")

        deactivated = service.deactivate_user(user.user_id)

        assert deactivated.is_active is False

    def test_activate_user_activates(self):
        """Test activate_user activates user."""
        service = AdminService()
        user = service.create_user("john_doe", "john@example.com", "employee", "Engineering")
        service.deactivate_user(user.user_id)

        activated = service.activate_user(user.user_id)

        assert activated.is_active is True

    def test_deactivate_user_missing_user(self):
        """Test deactivate_user raises for missing user."""
        service = AdminService()
        fake_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            service.deactivate_user(fake_id)


# ============================================================================
# List Roles Tests
# ============================================================================

class TestListRoles:
    """Tests for AdminService.list_roles()."""

    def test_list_roles_returns_roles(self):
        """Test list_roles returns all roles."""
        service = AdminService()

        roles = service.list_roles()

        assert roles is not None
        assert len(roles) > 0

    def test_list_roles_includes_system_roles(self):
        """Test list_roles includes system roles."""
        service = AdminService()

        roles = service.list_roles()
        system_roles = [r for r in roles if r.is_system_role]

        assert len(system_roles) >= 4

    def test_list_roles_custom_roles(self):
        """Test list_roles includes custom roles."""
        service = AdminService()
        custom_role = service.create_role("custom", "Custom role", ["user:read"])

        roles = service.list_roles()
        custom_roles = [r for r in roles if r.name == "custom"]

        assert len(custom_roles) == 1


# ============================================================================
# Create Role Tests
# ============================================================================

class TestCreateRole:
    """Tests for AdminService.create_role()."""

    def test_create_role_creates(self):
        """Test create_role creates a new role."""
        service = AdminService()
        role = service.create_role("viewer_plus", "Extended viewer", ["user:read", "audit:read"])

        assert role.name == "viewer_plus"
        assert role.description == "Extended viewer"
        assert "user:read" in role.permissions

    def test_create_role_assigns_uuid(self):
        """Test create_role assigns UUID."""
        service = AdminService()
        role = service.create_role("tester", "Tester role", ["user:read"])

        assert isinstance(role.role_id, UUID)

    def test_create_role_stores(self):
        """Test create_role stores role."""
        service = AdminService()
        role = service.create_role("auditor", "Auditor role", ["audit:read", "audit:export"])

        retrieved = service.get_flag(role.name) if hasattr(service, 'get_flag') else None
        roles = service.list_roles()
        stored_role = [r for r in roles if r.role_id == role.role_id]

        assert len(stored_role) == 1


# ============================================================================
# Delete Role Tests
# ============================================================================

class TestDeleteRole:
    """Tests for AdminService.delete_role()."""

    def test_delete_role_deletes_non_system(self):
        """Test delete_role deletes non-system roles."""
        service = AdminService()
        role = service.create_role("temp_role", "Temporary role", ["user:read"])

        result = service.delete_role(role.role_id)

        assert result is True

    def test_delete_role_prevents_system_deletion(self):
        """Test delete_role prevents system deletion."""
        service = AdminService()
        roles = service.list_roles()
        system_role = [r for r in roles if r.is_system_role][0]

        with pytest.raises(ValueError, match="System roles cannot be deleted"):
            service.delete_role(system_role.role_id)

    def test_delete_role_missing_role(self):
        """Test delete_role raises for missing role."""
        service = AdminService()
        fake_id = uuid4()

        with pytest.raises(ValueError, match="not found"):
            service.delete_role(fake_id)


# ============================================================================
# Get Audit Logs Tests
# ============================================================================

class TestGetAuditLogs:
    """Tests for AdminService.get_audit_logs()."""

    def test_get_audit_logs_returns_logs(self):
        """Test get_audit_logs returns audit logs."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")

        logs = service.get_audit_logs()

        assert logs["entries"] is not None
        assert len(logs["entries"]) > 0

    def test_get_audit_logs_filters_by_date(self):
        """Test get_audit_logs filters by date."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")

        now = datetime.utcnow()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        logs = service.get_audit_logs(start_date=past, end_date=future)

        assert len(logs["entries"]) > 0

    def test_get_audit_logs_pagination(self):
        """Test get_audit_logs pagination."""
        service = AdminService()
        for i in range(5):
            service.create_user(f"user{i}", f"user{i}@example.com", "employee", "Engineering")

        logs = service.get_audit_logs(page=1, per_page=2)

        assert logs["pagination"].page == 1
        assert logs["pagination"].per_page == 2


# ============================================================================
# Export Audit Logs Tests
# ============================================================================

class TestExportAuditLogs:
    """Tests for AdminService.export_audit_logs()."""

    def test_export_audit_logs_json(self):
        """Test export_audit_logs exports JSON."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")

        now = datetime.utcnow()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        result = service.export_audit_logs(past, future, format="json")

        assert result["format"] == "json"
        assert isinstance(result["data"], list)

    def test_export_audit_logs_csv(self):
        """Test export_audit_logs exports CSV."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")

        now = datetime.utcnow()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        result = service.export_audit_logs(past, future, format="csv")

        assert result["format"] == "csv"
        assert isinstance(result["data"], list)

    def test_export_audit_logs_date_range(self):
        """Test export_audit_logs respects date range."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")

        now = datetime.utcnow()
        past = now - timedelta(hours=1)
        future = now + timedelta(hours=1)

        result = service.export_audit_logs(past, future)

        assert result["count"] >= 1


# ============================================================================
# Get System Stats Tests
# ============================================================================

class TestGetSystemStats:
    """Tests for AdminService.get_system_stats()."""

    def test_get_system_stats_returns_stats(self):
        """Test get_system_stats returns statistics."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")

        stats = service.get_system_stats()

        assert stats is not None

    def test_get_system_stats_includes_user_count(self):
        """Test get_system_stats includes user count."""
        service = AdminService()
        service.create_user("user1", "user1@example.com", "employee", "Engineering")
        service.create_user("user2", "user2@example.com", "manager", "Sales")

        stats = service.get_system_stats()

        assert "total_users" in stats
        assert stats["total_users"] == 2

    def test_get_system_stats_includes_uptime(self):
        """Test get_system_stats includes uptime."""
        service = AdminService()

        stats = service.get_system_stats()

        assert "uptime_seconds" in stats
        assert stats["uptime_seconds"] >= 0
