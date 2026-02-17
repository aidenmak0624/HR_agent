"""Tests for RBAC module."""
import pytest
from src.core.rbac import (
    RoleLevel,
    DataScope,
    PermissionDeniedError,
    check_permission,
    get_data_scope,
    RBACEnforcer,
)


class TestRoleHierarchy:
    """Tests for role hierarchy ordering."""

    def test_role_hierarchy_ordering(self):
        """Verify EMPLOYEE < MANAGER < HR_GENERALIST < HR_ADMIN."""
        assert RoleLevel.EMPLOYEE.value < RoleLevel.MANAGER.value
        assert RoleLevel.MANAGER.value < RoleLevel.HR_GENERALIST.value
        assert RoleLevel.HR_GENERALIST.value < RoleLevel.HR_ADMIN.value

        # Verify specific values
        assert RoleLevel.EMPLOYEE.value == 1
        assert RoleLevel.MANAGER.value == 2
        assert RoleLevel.HR_GENERALIST.value == 3
        assert RoleLevel.HR_ADMIN.value == 4

    def test_role_name_str_property(self):
        """Test role name_str property returns lowercase."""
        assert RoleLevel.EMPLOYEE.name_str == "employee"
        assert RoleLevel.MANAGER.name_str == "manager"
        assert RoleLevel.HR_GENERALIST.name_str == "hr_generalist"
        assert RoleLevel.HR_ADMIN.name_str == "hr_admin"


class TestPermissionChecks:
    """Tests for permission checking."""

    def test_employee_can_view_own_profile(self):
        """Employee can view their own profile."""
        assert check_permission("employee", "employee_info", "view_own") is True

    def test_employee_cannot_view_all(self):
        """Employee cannot view all employee info."""
        assert check_permission("employee", "employee_info", "view_all") is False

    def test_manager_can_view_reports(self):
        """Manager can view reports."""
        assert check_permission("manager", "employee_info", "view_reports") is True

    def test_manager_can_approve_leave(self):
        """Manager can approve leave requests."""
        assert check_permission("manager", "leave", "approve") is True

    def test_employee_cannot_approve_leave(self):
        """Employee cannot approve leave requests."""
        assert check_permission("employee", "leave", "approve") is False

    def test_hr_admin_can_configure(self):
        """HR admin can configure system."""
        assert check_permission("hr_admin", "admin", "configure") is True

    def test_hr_admin_can_audit(self):
        """HR admin can view audit logs."""
        assert check_permission("hr_admin", "admin", "audit_logs") is True

    def test_hr_generalist_can_view_all_employees(self):
        """HR generalist can view all employees."""
        assert check_permission("hr_generalist", "employee_info", "view_all") is True

    def test_role_inheritance(self):
        """Higher roles inherit lower role permissions."""
        # Manager inherits employee permissions
        assert check_permission("manager", "employee_info", "view_own") is True

        # HR Generalist inherits manager permissions
        assert check_permission("hr_generalist", "leave", "approve") is True

        # HR Admin inherits all permissions
        assert check_permission("hr_admin", "employee_info", "view_own") is True
        assert check_permission("hr_admin", "leave", "approve") is True

    def test_invalid_role_returns_false(self):
        """Invalid role returns False."""
        assert check_permission("invalid_role", "employee_info", "view_own") is False

    def test_invalid_permission_returns_false(self):
        """Invalid permission returns False."""
        assert check_permission("employee", "invalid_agent", "invalid_action") is False

    def test_case_insensitive_role(self):
        """Role checking is case insensitive."""
        assert check_permission("EMPLOYEE", "employee_info", "view_own") is True
        assert check_permission("Manager", "leave", "approve") is True


class TestDataScope:
    """Tests for data scope determination."""

    def test_data_scope_employee_is_own(self):
        """Employee scope for employee_info is OWN."""
        scope = get_data_scope("employee", "employee_info")
        assert scope == DataScope.OWN

    def test_data_scope_manager_is_team(self):
        """Manager scope for employee_info is TEAM."""
        scope = get_data_scope("manager", "employee_info")
        assert scope == DataScope.TEAM

    def test_data_scope_hr_generalist_is_department(self):
        """HR Generalist scope for employee_info is DEPARTMENT."""
        scope = get_data_scope("hr_generalist", "employee_info")
        assert scope == DataScope.DEPARTMENT

    def test_data_scope_hr_admin_is_all(self):
        """HR Admin scope for employee_info is ALL."""
        scope = get_data_scope("hr_admin", "employee_info")
        assert scope == DataScope.ALL

    def test_data_scope_for_leave(self):
        """Test data scopes for leave management."""
        assert get_data_scope("employee", "leave") == DataScope.OWN
        assert get_data_scope("manager", "leave") == DataScope.TEAM
        assert get_data_scope("hr_generalist", "leave") == DataScope.DEPARTMENT
        assert get_data_scope("hr_admin", "leave") == DataScope.ALL

    def test_invalid_role_raises_error(self):
        """Invalid role raises PermissionDeniedError."""
        with pytest.raises(PermissionDeniedError):
            get_data_scope("invalid_role", "employee_info")

    def test_invalid_agent_type_raises_error(self):
        """Invalid agent type raises PermissionDeniedError."""
        with pytest.raises(PermissionDeniedError):
            get_data_scope("employee", "invalid_agent")


class TestDataFiltering:
    """Tests for data filtering based on role."""

    def test_filter_sensitive_data_employee_role(self):
        """Employee role strips sensitive data."""
        enforcer = RBACEnforcer()
        employee_data = {
            "id": "emp-001",
            "name": "John Doe",
            "email": "john@company.com",
            "salary": 100000,
            "ssn": "123-45-6789",
            "compensation": 120000,
        }

        filtered = enforcer.filter_employee_data(employee_data, "employee", "emp-001")

        assert "id" in filtered
        assert "name" in filtered
        assert "email" in filtered
        assert "salary" not in filtered
        assert "ssn" not in filtered
        assert "compensation" not in filtered

    def test_hr_sees_sensitive_data(self):
        """HR roles can view sensitive data."""
        enforcer = RBACEnforcer()
        employee_data = {
            "id": "emp-001",
            "name": "John Doe",
            "salary": 100000,
            "ssn": "123-45-6789",
            "compensation": 120000,
        }

        filtered = enforcer.filter_employee_data(employee_data, "hr_generalist", "hr-001")

        assert "salary" in filtered
        assert "ssn" in filtered
        assert "compensation" in filtered
        assert filtered["salary"] == 100000

    def test_manager_can_view_team_salary(self):
        """Manager can view salary for direct reports."""
        enforcer = RBACEnforcer()
        # This employee is a direct report (manager_id matches requesting user)
        employee_data = {
            "id": "emp-001",
            "name": "John Doe",
            "manager_id": "mgr-001",
            "salary": 100000,
            "ssn": "123-45-6789",
        }

        filtered = enforcer.filter_employee_data(employee_data, "manager", "mgr-001")

        # Manager can see salary for their own reports
        assert "salary" in filtered
        assert "ssn" not in filtered

    def test_invalid_role_raises_error(self):
        """Invalid role in filter_employee_data raises error."""
        enforcer = RBACEnforcer()
        employee_data = {"id": "emp-001", "name": "John Doe"}

        with pytest.raises(PermissionDeniedError):
            enforcer.filter_employee_data(employee_data, "invalid_role", "emp-001")


class TestRBACEnforcer:
    """Tests for RBACEnforcer class."""

    def test_enforce_permission_allowed(self):
        """enforce() does not raise when permission granted."""
        enforcer = RBACEnforcer()
        # Should not raise
        enforcer.enforce("employee", "employee_info", "view_own")

    def test_enforce_permission_denied_raises(self):
        """enforce() raises PermissionDeniedError when denied."""
        enforcer = RBACEnforcer()

        with pytest.raises(PermissionDeniedError) as exc_info:
            enforcer.enforce("employee", "admin", "configure")

        assert "lacks permission" in str(exc_info.value)

    def test_get_allowed_actions_employee(self):
        """Employee gets appropriate allowed actions."""
        enforcer = RBACEnforcer()
        actions = enforcer.get_allowed_actions("employee", "employee_info")

        assert "view_own" in actions
        assert "view_reports" not in actions
        assert "view_all" not in actions

    def test_get_allowed_actions_manager(self):
        """Manager gets appropriate allowed actions."""
        enforcer = RBACEnforcer()
        actions = enforcer.get_allowed_actions("manager", "leave")

        assert "view_own" in actions
        assert "view_team" in actions
        assert "approve" in actions
        assert "view_all" not in actions

    def test_get_allowed_actions_hr_admin(self):
        """HR admin gets all actions."""
        enforcer = RBACEnforcer()
        actions = enforcer.get_allowed_actions("hr_admin", "admin")

        assert "configure" in actions
        assert "audit_logs" in actions

    def test_get_allowed_actions_invalid_role(self):
        """Invalid role raises error."""
        enforcer = RBACEnforcer()

        with pytest.raises(PermissionDeniedError):
            enforcer.get_allowed_actions("invalid_role", "employee_info")

    def test_get_filtered_list(self):
        """Test filtering a list of employee records."""
        enforcer = RBACEnforcer()
        data_list = [
            {"id": "emp-001", "name": "John", "salary": 100000},
            {"id": "emp-002", "name": "Jane", "salary": 120000},
        ]

        filtered = enforcer.get_filtered_list(data_list, "employee", "emp-001")

        assert len(filtered) == 2
        for item in filtered:
            assert "salary" not in item

    def test_apply_data_scope_filter_own(self):
        """apply_data_scope_filter respects OWN scope."""
        enforcer = RBACEnforcer()
        data_list = [
            {"user_id": "emp-001", "name": "John", "value": 100},
            {"user_id": "emp-002", "name": "Jane", "value": 200},
        ]

        filtered = enforcer.apply_data_scope_filter(
            data_list, "employee", "employee_info", "emp-001", "Engineering"
        )

        assert len(filtered) == 1
        assert filtered[0]["user_id"] == "emp-001"

    def test_apply_data_scope_filter_team(self):
        """apply_data_scope_filter respects TEAM scope."""
        enforcer = RBACEnforcer()
        data_list = [
            {"user_id": "mgr-001", "name": "Manager", "value": 100},
            {"user_id": "emp-001", "name": "Report1", "value": 200},
            {"user_id": "emp-002", "name": "Report2", "value": 300},
            {"user_id": "emp-003", "name": "Other", "value": 400},
        ]

        filtered = enforcer.apply_data_scope_filter(
            data_list,
            "manager",
            "employee_info",
            "mgr-001",
            "Engineering",
            team_members=["emp-001", "emp-002"],
        )

        assert len(filtered) == 3
        user_ids = {item["user_id"] for item in filtered}
        assert user_ids == {"mgr-001", "emp-001", "emp-002"}

    def test_apply_data_scope_filter_department(self):
        """apply_data_scope_filter respects DEPARTMENT scope."""
        enforcer = RBACEnforcer()
        data_list = [
            {"user_id": "emp-001", "department": "Engineering", "value": 100},
            {"user_id": "emp-002", "department": "Engineering", "value": 200},
            {"user_id": "emp-003", "department": "Sales", "value": 300},
        ]

        filtered = enforcer.apply_data_scope_filter(
            data_list, "hr_generalist", "employee_info", "hr-001", "Engineering"
        )

        assert len(filtered) == 2
        for item in filtered:
            assert item["department"] == "Engineering"

    def test_apply_data_scope_filter_all(self):
        """apply_data_scope_filter returns all for ALL scope."""
        enforcer = RBACEnforcer()
        data_list = [
            {"user_id": "emp-001", "department": "Engineering"},
            {"user_id": "emp-002", "department": "Sales"},
            {"user_id": "emp-003", "department": "Marketing"},
        ]

        filtered = enforcer.apply_data_scope_filter(
            data_list, "hr_admin", "employee_info", "hr-001", "Engineering"
        )

        assert len(filtered) == 3
