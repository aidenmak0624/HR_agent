"""
Feature Flag Management for HR Multi-Agent Platform.
Feature flag management for gradual rollout and per-agent toggles.
Iteration 8 Wave 1 - FF-001
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class FlagType(str, Enum):
    """Feature flag type."""
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    SCHEDULE = "schedule"


class FlagStatus(str, Enum):
    """Feature flag status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


# ============================================================================
# Pydantic Models
# ============================================================================

class FeatureFlag(BaseModel):
    """Feature flag definition."""
    flag_id: UUID = Field(default_factory=uuid4, description="Unique flag ID")
    name: str = Field(..., min_length=2, max_length=255, description="Flag name")
    description: str = Field(..., description="Flag description")
    flag_type: FlagType = Field(..., description="Flag type")
    status: FlagStatus = Field(default=FlagStatus.INACTIVE, description="Flag status")
    enabled: bool = Field(default=False, description="Whether flag is enabled")
    percentage: Optional[float] = Field(
        None, description="Percentage (0-100) for percentage-based flags"
    )
    allowed_users: List[str] = Field(
        default_factory=list, description="Allowed users for user list flags"
    )
    schedule_start: Optional[datetime] = Field(
        None, description="Schedule start time for scheduled flags"
    )
    schedule_end: Optional[datetime] = Field(
        None, description="Schedule end time for scheduled flags"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="User who created the flag")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


class FlagEvaluation(BaseModel):
    """Result of evaluating a feature flag."""
    flag_name: str = Field(..., description="Flag name")
    user_id: Optional[str] = Field(None, description="User ID evaluated against")
    result: bool = Field(..., description="Evaluation result")
    reason: str = Field(..., description="Reason for evaluation result")
    evaluated_at: datetime = Field(default_factory=datetime.utcnow, description="Evaluation timestamp")

    model_config = ConfigDict(frozen=False, use_enum_values=False)


class FeatureFlagConfig(BaseModel):
    """Feature flag service configuration."""
    cache_ttl_seconds: int = Field(
        default=60, description="Cache TTL for flag results"
    )
    default_enabled: bool = Field(
        default=False, description="Default enabled state for new flags"
    )
    audit_evaluations: bool = Field(
        default=False, description="Whether to audit all evaluations"
    )
    max_flags: int = Field(
        default=500, description="Maximum number of flags allowed"
    )

    model_config = ConfigDict(frozen=False)


# ============================================================================
# Feature Flag Service
# ============================================================================

class FeatureFlagService:
    """
    Feature flag management service for gradual rollout and feature toggles.

    Supports multiple flag types including boolean, percentage-based, user list,
    and scheduled rollouts. Provides evaluation, audit, and management capabilities.
    """

    def __init__(
        self,
        config: Optional[FeatureFlagConfig] = None,
        audit_logger: Optional[Any] = None
    ):
        """
        Initialize feature flag service.

        Args:
            config: FeatureFlagConfig object with settings
            audit_logger: Logger for audit trail (optional)
        """
        self.config = config or FeatureFlagConfig()
        self.audit_logger = audit_logger

        # In-memory storage
        self._flags: Dict[str, FeatureFlag] = {}
        self._evaluation_history: Dict[str, List[FlagEvaluation]] = {}
        self._evaluation_count: Dict[str, int] = {}

        logger.info("FeatureFlagService initialized with config: %s", self.config)

    def create_flag(
        self,
        name: str,
        description: str,
        flag_type: FlagType,
        created_by: Optional[str] = None,
        **kwargs
    ) -> FeatureFlag:
        """
        Create a new feature flag.

        Args:
            name: Flag name
            description: Flag description
            flag_type: Type of flag (boolean, percentage, user_list, schedule)
            created_by: User creating the flag
            **kwargs: Additional flag properties

        Returns:
            Created FeatureFlag

        Raises:
            ValueError: If validation fails
        """
        try:
            if len(self._flags) >= self.config.max_flags:
                raise ValueError("Maximum flag limit reached")

            if name in self._flags:
                raise ValueError(f"Flag {name} already exists")

            flag = FeatureFlag(
                name=name,
                description=description,
                flag_type=flag_type,
                created_by=created_by or "SYSTEM",
                **kwargs
            )

            # Validate flag type-specific fields
            if flag_type == FlagType.PERCENTAGE and (flag.percentage is None or not (0 <= flag.percentage <= 100)):
                raise ValueError("Percentage flag must have percentage between 0-100")

            if flag_type == FlagType.USER_LIST and not flag.allowed_users:
                raise ValueError("User list flag must have allowed_users")

            if flag_type == FlagType.SCHEDULE:
                if not flag.schedule_start or not flag.schedule_end:
                    raise ValueError("Schedule flag must have schedule_start and schedule_end")
                if flag.schedule_start >= flag.schedule_end:
                    raise ValueError("Schedule start must be before end")

            self._flags[name] = flag
            self._evaluation_history[name] = []
            self._evaluation_count[name] = 0

            self._log_audit(
                action="flag_created",
                resource=f"flag:{name}",
                user_id=created_by or "SYSTEM",
                details={
                    "name": name,
                    "type": flag_type.value,
                    "description": description
                }
            )

            logger.info("Feature flag created: %s (type: %s)", name, flag_type.value)
            return flag
        except Exception as e:
            logger.error("Failed to create flag: %s", str(e))
            raise

    def get_flag(self, name: str) -> FeatureFlag:
        """
        Get a feature flag by name.

        Args:
            name: Flag name

        Returns:
            FeatureFlag

        Raises:
            ValueError: If flag not found
        """
        try:
            if name not in self._flags:
                raise ValueError(f"Flag {name} not found")

            logger.debug("Flag retrieved: %s", name)
            return self._flags[name]
        except Exception as e:
            logger.error("Failed to get flag: %s", str(e))
            raise

    def update_flag(
        self,
        name: str,
        updates: Dict[str, Any],
        updated_by: Optional[str] = None
    ) -> FeatureFlag:
        """
        Update a feature flag.

        Args:
            name: Flag name
            updates: Updates to apply
            updated_by: User performing the update

        Returns:
            Updated FeatureFlag

        Raises:
            ValueError: If flag not found
        """
        try:
            if name not in self._flags:
                raise ValueError(f"Flag {name} not found")

            flag = self._flags[name]
            changeset = {}

            # Apply updates
            for key, value in updates.items():
                if key in [
                    "description", "enabled", "status", "percentage",
                    "allowed_users", "schedule_start", "schedule_end", "metadata"
                ]:
                    if key == "percentage" and not (0 <= value <= 100):
                        raise ValueError("Percentage must be between 0-100")

                    old_value = getattr(flag, key)
                    setattr(flag, key, value)
                    changeset[key] = {"old": old_value, "new": value}

            flag.updated_at = datetime.utcnow()

            self._log_audit(
                action="flag_updated",
                resource=f"flag:{name}",
                user_id=updated_by or "SYSTEM",
                details=changeset
            )

            logger.info("Feature flag updated: %s with changes: %s", name, changeset)
            return flag
        except Exception as e:
            logger.error("Failed to update flag: %s", str(e))
            raise

    def delete_flag(self, name: str, deleted_by: Optional[str] = None) -> bool:
        """
        Delete a feature flag.

        Args:
            name: Flag name
            deleted_by: User performing the deletion

        Returns:
            True if deleted

        Raises:
            ValueError: If flag not found
        """
        try:
            if name not in self._flags:
                raise ValueError(f"Flag {name} not found")

            del self._flags[name]
            if name in self._evaluation_history:
                del self._evaluation_history[name]
            if name in self._evaluation_count:
                del self._evaluation_count[name]

            self._log_audit(
                action="flag_deleted",
                resource=f"flag:{name}",
                user_id=deleted_by or "SYSTEM",
                details={"name": name}
            )

            logger.info("Feature flag deleted: %s", name)
            return True
        except Exception as e:
            logger.error("Failed to delete flag: %s", str(e))
            raise

    def archive_flag(self, name: str, archived_by: Optional[str] = None) -> FeatureFlag:
        """
        Archive a feature flag (soft delete).

        Args:
            name: Flag name
            archived_by: User performing the archive

        Returns:
            Archived FeatureFlag

        Raises:
            ValueError: If flag not found
        """
        try:
            if name not in self._flags:
                raise ValueError(f"Flag {name} not found")

            flag = self._flags[name]
            flag.status = FlagStatus.ARCHIVED
            flag.updated_at = datetime.utcnow()

            self._log_audit(
                action="flag_archived",
                resource=f"flag:{name}",
                user_id=archived_by or "SYSTEM",
                details={"name": name}
            )

            logger.info("Feature flag archived: %s", name)
            return flag
        except Exception as e:
            logger.error("Failed to archive flag: %s", str(e))
            raise

    def is_enabled(
        self,
        name: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if a feature flag is enabled for a user.

        Args:
            name: Flag name
            user_id: User ID to evaluate
            context: Additional context for evaluation

        Returns:
            True if flag is enabled for user

        Raises:
            ValueError: If flag not found
        """
        try:
            evaluation = self.evaluate_flag(name, user_id, context)
            return evaluation.result
        except Exception as e:
            logger.error("Failed to check if flag is enabled: %s", str(e))
            raise

    def evaluate_flag(
        self,
        name: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> FlagEvaluation:
        """
        Evaluate a feature flag for a user.

        Args:
            name: Flag name
            user_id: User ID to evaluate
            context: Additional context for evaluation

        Returns:
            FlagEvaluation with result and reason

        Raises:
            ValueError: If flag not found
        """
        try:
            if name not in self._flags:
                raise ValueError(f"Flag {name} not found")

            flag = self._flags[name]

            # Track evaluation
            if name not in self._evaluation_count:
                self._evaluation_count[name] = 0
            self._evaluation_count[name] += 1

            # Check flag status
            if flag.status == FlagStatus.INACTIVE:
                result = False
                reason = "Flag is inactive"
            elif flag.status == FlagStatus.ARCHIVED:
                result = False
                reason = "Flag is archived"
            elif not flag.enabled:
                result = False
                reason = "Flag is disabled"
            else:
                # Evaluate based on flag type
                if flag.flag_type == FlagType.BOOLEAN:
                    result = True
                    reason = "Boolean flag enabled"
                elif flag.flag_type == FlagType.PERCENTAGE:
                    if user_id and flag.percentage:
                        # Hash user_id to determine percentage inclusion
                        user_hash = hash(user_id) % 100
                        result = user_hash < flag.percentage
                        reason = f"Percentage-based: {user_hash}% < {flag.percentage}% = {result}"
                    else:
                        result = flag.percentage and flag.percentage > 0
                        reason = "Percentage-based (no user_id)"
                elif flag.flag_type == FlagType.USER_LIST:
                    result = user_id in flag.allowed_users if user_id else False
                    reason = f"User list: user_id in allowed_users = {result}"
                elif flag.flag_type == FlagType.SCHEDULE:
                    now = datetime.utcnow()
                    result = (
                        flag.schedule_start and flag.schedule_end and
                        flag.schedule_start <= now <= flag.schedule_end
                    )
                    reason = f"Schedule-based: {flag.schedule_start} <= {now} <= {flag.schedule_end} = {result}"
                else:
                    result = False
                    reason = "Unknown flag type"

            evaluation = FlagEvaluation(
                flag_name=name,
                user_id=user_id,
                result=result,
                reason=reason
            )

            # Record evaluation
            if name not in self._evaluation_history:
                self._evaluation_history[name] = []
            self._evaluation_history[name].append(evaluation)

            # Keep only last 1000 evaluations per flag
            if len(self._evaluation_history[name]) > 1000:
                self._evaluation_history[name] = self._evaluation_history[name][-1000:]

            if self.config.audit_evaluations:
                self._log_audit(
                    action="flag_evaluated",
                    resource=f"flag:{name}",
                    user_id=user_id or "SYSTEM",
                    details={"result": result, "reason": reason}
                )

            logger.debug("Flag evaluated: %s for user %s = %s", name, user_id, result)
            return evaluation
        except Exception as e:
            logger.error("Failed to evaluate flag: %s", str(e))
            raise

    def list_flags(self, status: Optional[FlagStatus] = None) -> List[FeatureFlag]:
        """
        List all feature flags with optional status filter.

        Args:
            status: Optional status filter

        Returns:
            List of FeatureFlag objects
        """
        try:
            flags = list(self._flags.values())

            if status:
                flags = [f for f in flags if f.status == status]

            logger.info("Flags listed: %d total", len(flags))
            return flags
        except Exception as e:
            logger.error("Failed to list flags: %s", str(e))
            raise

    def get_flags_for_user(self, user_id: str) -> Dict[str, bool]:
        """
        Get all enabled flags for a specific user.

        Args:
            user_id: User ID

        Returns:
            Dictionary mapping flag names to enabled status
        """
        try:
            result = {}

            for flag_name in self._flags.keys():
                try:
                    is_enabled = self.is_enabled(flag_name, user_id)
                    result[flag_name] = is_enabled
                except Exception as e:
                    logger.warning("Failed to evaluate flag %s for user %s: %s", flag_name, user_id, str(e))
                    result[flag_name] = False

            logger.info("Flags retrieved for user %s: %d flags", user_id, len(result))
            return result
        except Exception as e:
            logger.error("Failed to get flags for user: %s", str(e))
            raise

    def bulk_evaluate(
        self,
        flag_names: List[str],
        user_id: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        Bulk evaluate multiple flags for a user.

        Args:
            flag_names: List of flag names to evaluate
            user_id: User ID

        Returns:
            Dictionary mapping flag names to boolean results
        """
        try:
            result = {}

            for flag_name in flag_names:
                try:
                    is_enabled = self.is_enabled(flag_name, user_id)
                    result[flag_name] = is_enabled
                except Exception as e:
                    logger.warning("Failed to evaluate flag %s: %s", flag_name, str(e))
                    result[flag_name] = False

            logger.info("Bulk evaluation completed: %d flags for user %s", len(result), user_id)
            return result
        except Exception as e:
            logger.error("Failed to bulk evaluate flags: %s", str(e))
            raise

    def get_evaluation_history(
        self,
        flag_name: str,
        limit: int = 100
    ) -> List[FlagEvaluation]:
        """
        Get evaluation history for a flag.

        Args:
            flag_name: Flag name
            limit: Maximum number of entries to return

        Returns:
            List of FlagEvaluation objects

        Raises:
            ValueError: If flag not found
        """
        try:
            if flag_name not in self._flags:
                raise ValueError(f"Flag {flag_name} not found")

            history = self._evaluation_history.get(flag_name, [])
            # Return most recent evaluations
            return history[-limit:] if len(history) > limit else history
        except Exception as e:
            logger.error("Failed to get evaluation history: %s", str(e))
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get feature flag statistics.

        Returns:
            Dictionary with flag statistics
        """
        try:
            active_flags = sum(1 for f in self._flags.values() if f.status == FlagStatus.ACTIVE)
            enabled_flags = sum(1 for f in self._flags.values() if f.enabled)

            evaluation_counts = {}
            for flag_name, count in self._evaluation_count.items():
                evaluation_counts[flag_name] = count

            stats = {
                "total_flags": len(self._flags),
                "active_flags": active_flags,
                "inactive_flags": sum(1 for f in self._flags.values() if f.status == FlagStatus.INACTIVE),
                "archived_flags": sum(1 for f in self._flags.values() if f.status == FlagStatus.ARCHIVED),
                "enabled_flags": enabled_flags,
                "disabled_flags": len(self._flags) - enabled_flags,
                "total_evaluations": sum(self._evaluation_count.values()),
                "flag_evaluation_counts": evaluation_counts,
                "timestamp": datetime.utcnow().isoformat()
            }

            logger.info("Flag stats retrieved")
            return stats
        except Exception as e:
            logger.error("Failed to get flag stats: %s", str(e))
            raise

    def _log_audit(
        self,
        action: str,
        resource: str,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log an audit entry.

        Args:
            action: Action type
            resource: Resource affected
            user_id: User performing the action
            details: Additional details
        """
        try:
            if self.audit_logger:
                self.audit_logger.log(
                    action=action,
                    resource=resource,
                    user_id=user_id or "SYSTEM",
                    details=details or {}
                )

            logger.debug("Audit logged: %s on %s", action, resource)
        except Exception as e:
            logger.error("Failed to log audit: %s", str(e))
