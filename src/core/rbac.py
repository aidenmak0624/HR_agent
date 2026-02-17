"""Role-Based Access Control (RBAC) module for HR multi-agent platform."""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# Enums
class RoleLevel(Enum):
    """User role levels with hierarchical values."""

    EMPLOYEE = 1
    MANAGER = 2
    HR_GENERALIST = 3
    HR_ADMIN = 4

    @property
    def name_str(self) -> str:
        """Get role name as lowercase string."""
        return self.name.lower()


class DataScope(Enum):
    """Data access scope levels."""

    OWN = "own"  # Only own data
    TEAM = "team"  # Team members data
    DEPARTMENT = "department"  # Department data
    ALL = "all"  # All organization data


# Custom Exceptions
class PermissionDeniedError(Exception):
    """User lacks required permissions."""

    pass


@dataclass
class Permission:
    """Permission definition for an action on an agent type."""

    agent_type: str
    action: str
    min_role: RoleLevel
    data_scope: DataScope

    def __hash__(self) -> int:
        """Make Permission hashable."""
        return hash((self.agent_type, self.action))


# Permission Matrix
PERMISSION_MATRIX: Dict[Tuple[str, str], RoleLevel] = {
    # Employee Info Permissions
    ("employee_info", "view_own"): RoleLevel.EMPLOYEE,
    ("employee_info", "view_reports"): RoleLevel.MANAGER,
    ("employee_info", "view_all"): RoleLevel.HR_GENERALIST,
    # Policy Permissions
    ("policy", "search"): RoleLevel.EMPLOYEE,
    ("policy", "compliance_check"): RoleLevel.HR_GENERALIST,
    # Leave Management Permissions
    ("leave", "view_own"): RoleLevel.EMPLOYEE,
    ("leave", "view_team"): RoleLevel.MANAGER,
    ("leave", "view_all"): RoleLevel.HR_GENERALIST,
    ("leave", "approve"): RoleLevel.MANAGER,
    # Analytics Permissions
    ("analytics", "view_team"): RoleLevel.MANAGER,
    ("analytics", "view_all"): RoleLevel.HR_GENERALIST,
    # Administration Permissions
    ("admin", "configure"): RoleLevel.HR_ADMIN,
    ("admin", "audit_logs"): RoleLevel.HR_ADMIN,
}

# Data Scope Mapping
DATA_SCOPE_MAPPING: Dict[Tuple[str, RoleLevel], DataScope] = {
    # Employee Info Scopes
    ("employee_info", RoleLevel.EMPLOYEE): DataScope.OWN,
    ("employee_info", RoleLevel.MANAGER): DataScope.TEAM,
    ("employee_info", RoleLevel.HR_GENERALIST): DataScope.DEPARTMENT,
    ("employee_info", RoleLevel.HR_ADMIN): DataScope.ALL,
    # Leave Scopes
    ("leave", RoleLevel.EMPLOYEE): DataScope.OWN,
    ("leave", RoleLevel.MANAGER): DataScope.TEAM,
    ("leave", RoleLevel.HR_GENERALIST): DataScope.DEPARTMENT,
    ("leave", RoleLevel.HR_ADMIN): DataScope.ALL,
    # Analytics Scopes
    ("analytics", RoleLevel.EMPLOYEE): DataScope.OWN,
    ("analytics", RoleLevel.MANAGER): DataScope.TEAM,
    ("analytics", RoleLevel.HR_GENERALIST): DataScope.DEPARTMENT,
    ("analytics", RoleLevel.HR_ADMIN): DataScope.ALL,
    # Policy Scopes
    ("policy", RoleLevel.EMPLOYEE): DataScope.ALL,
    ("policy", RoleLevel.MANAGER): DataScope.ALL,
    ("policy", RoleLevel.HR_GENERALIST): DataScope.ALL,
    ("policy", RoleLevel.HR_ADMIN): DataScope.ALL,
}

# Sensitive Fields by Role
SENSITIVE_FIELDS = {
    "salary",
    "ssn",
    "bank_account",
    "tax_id",
    "compensation",
    "benefits_cost",
}

HR_VIEWABLE_ONLY = SENSITIVE_FIELDS  # HR roles can view sensitive fields
MANAGER_VIEWABLE_FIELDS = {"salary"}  # Managers can view salary for own team


def check_permission(user_role: str, agent_type: str, action: str) -> bool:
    """Check if user role has permission for an action on an agent type.

    Args:
        user_role: User role name (lowercase)
        agent_type: Agent type name
        action: Action name

    Returns:
        True if permission is granted, False otherwise
    """
    # Normalize user role
    user_role_upper = user_role.upper()
    if user_role_upper not in [role.name for role in RoleLevel]:
        return False

    user_role_level = RoleLevel[user_role_upper]
    required_role = PERMISSION_MATRIX.get((agent_type, action))

    if required_role is None:
        return False

    return user_role_level.value >= required_role.value


def get_data_scope(user_role: str, agent_type: str) -> DataScope:
    """Get data access scope for a user role and agent type.

    Args:
        user_role: User role name (lowercase)
        agent_type: Agent type name

    Returns:
        DataScope enum indicating accessible data range

    Raises:
        PermissionDeniedError: If role/agent combination is invalid
    """
    # Normalize user role
    user_role_upper = user_role.upper()
    if user_role_upper not in [role.name for role in RoleLevel]:
        raise PermissionDeniedError(f"Invalid user role: {user_role}")

    user_role_level = RoleLevel[user_role_upper]
    scope = DATA_SCOPE_MAPPING.get((agent_type, user_role_level))

    if scope is None:
        raise PermissionDeniedError(f"No data scope defined for {agent_type} and {user_role}")

    return scope


class RBACEnforcer:
    """RBAC enforcement service for permission checks and data filtering."""

    def __init__(self) -> None:
        """Initialize RBAC enforcer."""
        pass

    def enforce(self, user_role: str, agent_type: str, action: str) -> None:
        """Enforce permission check and raise exception if denied.

        Args:
            user_role: User role name (lowercase)
            agent_type: Agent type name
            action: Action name

        Raises:
            PermissionDeniedError: If permission is denied
        """
        if not check_permission(user_role, agent_type, action):
            raise PermissionDeniedError(
                f"User role '{user_role}' lacks permission for "
                f"'{action}' on '{agent_type}' agent"
            )

    def get_allowed_actions(self, user_role: str, agent_type: str) -> List[str]:
        """Get all allowed actions for a user role on an agent type.

        Args:
            user_role: User role name (lowercase)
            agent_type: Agent type name

        Returns:
            List of allowed action names

        Raises:
            PermissionDeniedError: If role is invalid
        """
        user_role_upper = user_role.upper()
        if user_role_upper not in [role.name for role in RoleLevel]:
            raise PermissionDeniedError(f"Invalid user role: {user_role}")

        allowed_actions = [
            action
            for (agent, action), required_role in PERMISSION_MATRIX.items()
            if agent == agent_type and check_permission(user_role, agent_type, action)
        ]

        return allowed_actions

    def filter_employee_data(
        self, data: Dict[str, Any], user_role: str, requesting_user_id: str
    ) -> Dict[str, Any]:
        """Filter employee data based on user role and permissions.

        Removes sensitive fields (salary, SSN, etc.) for non-HR roles.
        Managers can only view salary for direct reports.

        Args:
            data: Employee data dictionary
            user_role: User role name (lowercase)
            requesting_user_id: ID of user requesting the data

        Returns:
            Filtered data dictionary with sensitive fields removed as needed

        Raises:
            PermissionDeniedError: If role is invalid
        """
        user_role_upper = user_role.upper()
        if user_role_upper not in [role.name for role in RoleLevel]:
            raise PermissionDeniedError(f"Invalid user role: {user_role}")

        user_role_level = RoleLevel[user_role_upper]
        filtered_data = data.copy()

        # HR Admin and HR Generalist can view all fields
        if user_role_level.value >= RoleLevel.HR_GENERALIST.value:
            return filtered_data

        # Remove all sensitive fields for non-HR roles
        for field in SENSITIVE_FIELDS:
            filtered_data.pop(field, None)

        # Manager special case: can view salary for own team
        if user_role_level == RoleLevel.MANAGER:
            # Check if this is a direct report (would need manager_id field)
            manager_id = data.get("manager_id")
            if manager_id == requesting_user_id and "salary" in data:
                filtered_data["salary"] = data["salary"]

        return filtered_data

    def get_filtered_list(
        self, data_list: List[Dict[str, Any]], user_role: str, requesting_user_id: str
    ) -> List[Dict[str, Any]]:
        """Filter a list of employee data based on user role and permissions.

        Args:
            data_list: List of employee data dictionaries
            user_role: User role name (lowercase)
            requesting_user_id: ID of user requesting the data

        Returns:
            Filtered list of employee data

        Raises:
            PermissionDeniedError: If role is invalid
        """
        return [
            self.filter_employee_data(item, user_role, requesting_user_id) for item in data_list
        ]

    def apply_data_scope_filter(
        self,
        data_list: List[Dict[str, Any]],
        user_role: str,
        agent_type: str,
        requesting_user_id: str,
        user_department: str,
        team_members: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Apply data scope filtering based on role and agent type.

        Filters data to only include records accessible per user's scope.

        Args:
            data_list: List of data records
            user_role: User role name (lowercase)
            agent_type: Agent type name
            requesting_user_id: ID of requesting user
            user_department: Department of requesting user
            team_members: List of team member IDs for TEAM scope

        Returns:
            Filtered list based on data scope

        Raises:
            PermissionDeniedError: If role or scope is invalid
        """
        scope = get_data_scope(user_role, agent_type)

        if scope == DataScope.OWN:
            return [item for item in data_list if item.get("user_id") == requesting_user_id]
        elif scope == DataScope.TEAM:
            team_ids = [requesting_user_id] + (team_members or [])
            return [item for item in data_list if item.get("user_id") in team_ids]
        elif scope == DataScope.DEPARTMENT:
            return [item for item in data_list if item.get("department") == user_department]
        elif scope == DataScope.ALL:
            return data_list
        else:
            return []
