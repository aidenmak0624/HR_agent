"""
Unit tests for Feature Flag Management.
Iteration 8 Wave 1 - FF-001 Test Suite
"""

import pytest
from datetime import datetime, timedelta
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock

from src.core.feature_flags import (
    FlagType,
    FlagStatus,
    FeatureFlag,
    FlagEvaluation,
    FeatureFlagConfig,
    FeatureFlagService,
)


# ============================================================================
# FlagType Enum Tests
# ============================================================================

class TestFlagType:
    """Tests for FlagType enum."""

    def test_flag_type_enum_values(self):
        """Test FlagType has correct enum values."""
        assert FlagType.BOOLEAN.value == "boolean"
        assert FlagType.PERCENTAGE.value == "percentage"
        assert FlagType.USER_LIST.value == "user_list"
        assert FlagType.SCHEDULE.value == "schedule"

    def test_flag_type_enum_count(self):
        """Test FlagType has correct number of values."""
        types = list(FlagType)
        assert len(types) == 4

    def test_flag_type_representation(self):
        """Test FlagType representation."""
        assert str(FlagType.BOOLEAN) == "FlagType.BOOLEAN"
        assert FlagType.BOOLEAN.name == "BOOLEAN"


# ============================================================================
# FlagStatus Enum Tests
# ============================================================================

class TestFlagStatus:
    """Tests for FlagStatus enum."""

    def test_flag_status_enum_values(self):
        """Test FlagStatus has correct enum values."""
        assert FlagStatus.ACTIVE.value == "active"
        assert FlagStatus.INACTIVE.value == "inactive"
        assert FlagStatus.ARCHIVED.value == "archived"

    def test_flag_status_enum_count(self):
        """Test FlagStatus has correct number of values."""
        statuses = list(FlagStatus)
        assert len(statuses) == 3

    def test_flag_status_representation(self):
        """Test FlagStatus representation."""
        assert str(FlagStatus.ACTIVE) == "FlagStatus.ACTIVE"
        assert FlagStatus.ACTIVE.name == "ACTIVE"


# ============================================================================
# FeatureFlag Tests
# ============================================================================

class TestFeatureFlag:
    """Tests for FeatureFlag model."""

    def test_feature_flag_defaults(self):
        """Test FeatureFlag with default values."""
        flag = FeatureFlag(
            name="test_feature",
            description="Test feature flag",
            flag_type=FlagType.BOOLEAN
        )

        assert isinstance(flag.flag_id, UUID)
        assert flag.name == "test_feature"
        assert flag.flag_type == FlagType.BOOLEAN
        assert flag.status == FlagStatus.INACTIVE
        assert flag.enabled is False

    def test_feature_flag_custom_values(self):
        """Test FeatureFlag with custom values."""
        flag_id = uuid4()
        created_at = datetime.utcnow()
        flag = FeatureFlag(
            flag_id=flag_id,
            name="new_feature",
            description="New feature flag",
            flag_type=FlagType.PERCENTAGE,
            status=FlagStatus.ACTIVE,
            enabled=True,
            percentage=50.0,
            created_at=created_at,
            created_by="admin"
        )

        assert flag.flag_id == flag_id
        assert flag.status == FlagStatus.ACTIVE
        assert flag.enabled is True
        assert flag.percentage == 50.0

    def test_feature_flag_uuid_generation(self):
        """Test FeatureFlag generates unique UUIDs."""
        flag1 = FeatureFlag(
            name="flag1",
            description="First flag",
            flag_type=FlagType.BOOLEAN
        )
        flag2 = FeatureFlag(
            name="flag2",
            description="Second flag",
            flag_type=FlagType.BOOLEAN
        )

        assert flag1.flag_id != flag2.flag_id

    def test_feature_flag_percentage_range(self):
        """Test FeatureFlag percentage range validation."""
        flag = FeatureFlag(
            name="pct_flag",
            description="Percentage flag",
            flag_type=FlagType.PERCENTAGE,
            percentage=75.5
        )

        assert flag.percentage == 75.5
        assert 0 <= flag.percentage <= 100


# ============================================================================
# FlagEvaluation Tests
# ============================================================================

class TestFlagEvaluation:
    """Tests for FlagEvaluation model."""

    def test_flag_evaluation_defaults(self):
        """Test FlagEvaluation with default values."""
        evaluation = FlagEvaluation(
            flag_name="test_flag",
            result=True,
            reason="Flag enabled"
        )

        assert evaluation.flag_name == "test_flag"
        assert evaluation.result is True
        assert evaluation.reason == "Flag enabled"
        assert evaluation.user_id is None

    def test_flag_evaluation_custom_values(self):
        """Test FlagEvaluation with custom values."""
        eval_time = datetime.utcnow()
        evaluation = FlagEvaluation(
            flag_name="user_flag",
            user_id="user123",
            result=False,
            reason="User not in allowed list",
            evaluated_at=eval_time
        )

        assert evaluation.user_id == "user123"
        assert evaluation.result is False
        assert evaluation.evaluated_at == eval_time

    def test_flag_evaluation_result(self):
        """Test FlagEvaluation result field."""
        enabled_eval = FlagEvaluation(
            flag_name="flag1",
            result=True,
            reason="Enabled"
        )

        disabled_eval = FlagEvaluation(
            flag_name="flag1",
            result=False,
            reason="Disabled"
        )

        assert enabled_eval.result is True
        assert disabled_eval.result is False


# ============================================================================
# FeatureFlagConfig Tests
# ============================================================================

class TestFeatureFlagConfig:
    """Tests for FeatureFlagConfig model."""

    def test_feature_flag_config_defaults(self):
        """Test FeatureFlagConfig with default values."""
        config = FeatureFlagConfig()

        assert config.cache_ttl_seconds == 60
        assert config.default_enabled is False
        assert config.audit_evaluations is False
        assert config.max_flags == 500

    def test_feature_flag_config_custom_values(self):
        """Test FeatureFlagConfig with custom values."""
        config = FeatureFlagConfig(
            cache_ttl_seconds=120,
            default_enabled=True,
            audit_evaluations=True,
            max_flags=1000
        )

        assert config.cache_ttl_seconds == 120
        assert config.default_enabled is True
        assert config.audit_evaluations is True
        assert config.max_flags == 1000

    def test_feature_flag_config_max_flags(self):
        """Test FeatureFlagConfig max_flags field."""
        config = FeatureFlagConfig(max_flags=200)

        assert config.max_flags == 200


# ============================================================================
# FeatureFlagService Init Tests
# ============================================================================

class TestFeatureFlagServiceInit:
    """Tests for FeatureFlagService initialization."""

    def test_feature_flag_service_init_with_config(self):
        """Test FeatureFlagService creates with config."""
        config = FeatureFlagConfig(max_flags=300)
        service = FeatureFlagService(config=config)

        assert service.config == config
        assert service.config.max_flags == 300

    def test_feature_flag_service_init_default_config(self):
        """Test FeatureFlagService creates with default config."""
        service = FeatureFlagService()

        assert service.config is not None
        assert service.config.max_flags == 500

    def test_feature_flag_service_init_empty_state(self):
        """Test FeatureFlagService initializes empty state."""
        service = FeatureFlagService()

        assert service._flags == {}
        assert service._evaluation_history == {}
        assert service._evaluation_count == {}


# ============================================================================
# Create Flag Tests
# ============================================================================

class TestCreateFlag:
    """Tests for FeatureFlagService.create_flag()."""

    def test_create_flag_creates_boolean(self):
        """Test create_flag creates boolean flag."""
        service = FeatureFlagService()
        flag = service.create_flag(
            "new_feature",
            "New feature flag",
            FlagType.BOOLEAN
        )

        assert flag.name == "new_feature"
        assert flag.flag_type == FlagType.BOOLEAN

    def test_create_flag_creates_percentage(self):
        """Test create_flag creates percentage flag."""
        service = FeatureFlagService()
        flag = service.create_flag(
            "rollout_feature",
            "Percentage rollout",
            FlagType.PERCENTAGE,
            percentage=25.0
        )

        assert flag.flag_type == FlagType.PERCENTAGE
        assert flag.percentage == 25.0

    def test_create_flag_creates_user_list(self):
        """Test create_flag creates user_list flag."""
        service = FeatureFlagService()
        flag = service.create_flag(
            "beta_feature",
            "Beta feature for users",
            FlagType.USER_LIST,
            allowed_users=["user1", "user2"]
        )

        assert flag.flag_type == FlagType.USER_LIST
        assert "user1" in flag.allowed_users

    def test_create_flag_creates_schedule(self):
        """Test create_flag creates schedule flag."""
        service = FeatureFlagService()
        start = datetime.utcnow()
        end = start + timedelta(days=1)

        flag = service.create_flag(
            "scheduled_feature",
            "Time-based feature",
            FlagType.SCHEDULE,
            schedule_start=start,
            schedule_end=end
        )

        assert flag.flag_type == FlagType.SCHEDULE
        assert flag.schedule_start == start


# ============================================================================
# Get Flag Tests
# ============================================================================

class TestGetFlag:
    """Tests for FeatureFlagService.get_flag()."""

    def test_get_flag_returns_flag(self):
        """Test get_flag returns flag."""
        service = FeatureFlagService()
        created = service.create_flag("test_flag", "Test flag", FlagType.BOOLEAN)
        retrieved = service.get_flag("test_flag")

        assert retrieved.name == created.name
        assert retrieved.flag_id == created.flag_id

    def test_get_flag_missing_flag_raises(self):
        """Test get_flag raises for missing flag."""
        service = FeatureFlagService()

        with pytest.raises(ValueError, match="not found"):
            service.get_flag("nonexistent")

    def test_get_flag_after_create(self):
        """Test get_flag works after create."""
        service = FeatureFlagService()
        service.create_flag("my_flag", "My flag", FlagType.BOOLEAN)

        flag = service.get_flag("my_flag")

        assert flag.name == "my_flag"


# ============================================================================
# Update Flag Tests
# ============================================================================

class TestUpdateFlag:
    """Tests for FeatureFlagService.update_flag()."""

    def test_update_flag_updates_fields(self):
        """Test update_flag updates fields."""
        service = FeatureFlagService()
        service.create_flag("flag1", "Original", FlagType.BOOLEAN)

        updated = service.update_flag(
            "flag1",
            {"description": "Updated description", "enabled": True}
        )

        assert updated.description == "Updated description"
        assert updated.enabled is True

    def test_update_flag_returns_updated(self):
        """Test update_flag returns updated flag."""
        service = FeatureFlagService()
        service.create_flag("flag2", "Original", FlagType.BOOLEAN)

        updated = service.update_flag(
            "flag2",
            {"status": FlagStatus.ACTIVE}
        )

        assert updated.status == FlagStatus.ACTIVE

    def test_update_flag_missing_flag(self):
        """Test update_flag raises for missing flag."""
        service = FeatureFlagService()

        with pytest.raises(ValueError, match="not found"):
            service.update_flag("missing", {"enabled": True})


# ============================================================================
# Delete Flag Tests
# ============================================================================

class TestDeleteFlag:
    """Tests for FeatureFlagService.delete_flag()."""

    def test_delete_flag_deletes_flag(self):
        """Test delete_flag deletes flag."""
        service = FeatureFlagService()
        service.create_flag("flag_to_delete", "Delete me", FlagType.BOOLEAN)

        result = service.delete_flag("flag_to_delete")

        assert result is True

    def test_delete_flag_returns_true(self):
        """Test delete_flag returns True on success."""
        service = FeatureFlagService()
        service.create_flag("temp_flag", "Temporary", FlagType.BOOLEAN)

        result = service.delete_flag("temp_flag")

        assert result is True

    def test_delete_flag_missing_returns_false(self):
        """Test delete_flag raises for missing flag."""
        service = FeatureFlagService()

        with pytest.raises(ValueError, match="not found"):
            service.delete_flag("nonexistent")


# ============================================================================
# Archive Flag Tests
# ============================================================================

class TestArchiveFlag:
    """Tests for FeatureFlagService.archive_flag()."""

    def test_archive_flag_archives_flag(self):
        """Test archive_flag archives flag."""
        service = FeatureFlagService()
        service.create_flag("archived_flag", "Archive me", FlagType.BOOLEAN)

        result = service.archive_flag("archived_flag")

        assert result.status == FlagStatus.ARCHIVED

    def test_archive_flag_changes_status(self):
        """Test archive_flag changes status to archived."""
        service = FeatureFlagService()
        service.create_flag("flag_to_archive", "Archive", FlagType.BOOLEAN)

        archived = service.archive_flag("flag_to_archive")

        assert archived.status == FlagStatus.ARCHIVED

    def test_archive_flag_missing_flag(self):
        """Test archive_flag raises for missing flag."""
        service = FeatureFlagService()

        with pytest.raises(ValueError, match="not found"):
            service.archive_flag("missing_flag")


# ============================================================================
# Is Enabled Tests
# ============================================================================

class TestIsEnabled:
    """Tests for FeatureFlagService.is_enabled()."""

    def test_is_enabled_boolean_enabled(self):
        """Test is_enabled with boolean flag enabled."""
        service = FeatureFlagService()
        service.create_flag(
            "bool_flag",
            "Boolean",
            FlagType.BOOLEAN,
            enabled=True,
            status=FlagStatus.ACTIVE
        )

        result = service.is_enabled("bool_flag")

        assert result is True

    def test_is_enabled_boolean_disabled(self):
        """Test is_enabled with boolean flag disabled."""
        service = FeatureFlagService()
        service.create_flag("disabled_flag", "Disabled", FlagType.BOOLEAN, enabled=False)

        result = service.is_enabled("disabled_flag")

        assert result is False

    def test_is_enabled_percentage(self):
        """Test is_enabled with percentage flag."""
        service = FeatureFlagService()
        service.create_flag(
            "pct_flag",
            "Percentage",
            FlagType.PERCENTAGE,
            enabled=True,
            percentage=50.0
        )

        result = service.is_enabled("pct_flag", user_id="user123")

        assert isinstance(result, bool)

    def test_is_enabled_user_list(self):
        """Test is_enabled with user_list flag."""
        service = FeatureFlagService()
        service.create_flag(
            "user_flag",
            "User list",
            FlagType.USER_LIST,
            enabled=True,
            status=FlagStatus.ACTIVE,
            allowed_users=["user1", "user2"]
        )

        result1 = service.is_enabled("user_flag", user_id="user1")
        result2 = service.is_enabled("user_flag", user_id="user999")

        assert result1 is True
        assert result2 is False


# ============================================================================
# Evaluate Flag Tests
# ============================================================================

class TestEvaluateFlag:
    """Tests for FeatureFlagService.evaluate_flag()."""

    def test_evaluate_flag_boolean_evaluation(self):
        """Test evaluate_flag with boolean flag."""
        service = FeatureFlagService()
        service.create_flag(
            "eval_flag",
            "Eval",
            FlagType.BOOLEAN,
            enabled=True,
            status=FlagStatus.ACTIVE
        )

        evaluation = service.evaluate_flag("eval_flag")

        assert isinstance(evaluation, FlagEvaluation)
        assert evaluation.result is True

    def test_evaluate_flag_percentage(self):
        """Test evaluate_flag with percentage flag."""
        service = FeatureFlagService()
        service.create_flag(
            "pct_eval",
            "Percent",
            FlagType.PERCENTAGE,
            enabled=True,
            percentage=50.0
        )

        evaluation = service.evaluate_flag("pct_eval", user_id="user_test")

        assert isinstance(evaluation, FlagEvaluation)
        assert isinstance(evaluation.result, bool)

    def test_evaluate_flag_user_list(self):
        """Test evaluate_flag with user_list flag."""
        service = FeatureFlagService()
        service.create_flag(
            "user_eval",
            "Users",
            FlagType.USER_LIST,
            enabled=True,
            status=FlagStatus.ACTIVE,
            allowed_users=["alice", "bob"]
        )

        eval_alice = service.evaluate_flag("user_eval", user_id="alice")
        eval_charlie = service.evaluate_flag("user_eval", user_id="charlie")

        assert eval_alice.result is True
        assert eval_charlie.result is False

    def test_evaluate_flag_schedule(self):
        """Test evaluate_flag with schedule flag."""
        service = FeatureFlagService()
        now = datetime.utcnow()
        start = now - timedelta(hours=1)
        end = now + timedelta(hours=1)

        service.create_flag(
            "schedule_eval",
            "Scheduled",
            FlagType.SCHEDULE,
            enabled=True,
            schedule_start=start,
            schedule_end=end
        )

        evaluation = service.evaluate_flag("schedule_eval")

        assert isinstance(evaluation, FlagEvaluation)
        assert isinstance(evaluation.result, bool)


# ============================================================================
# List Flags Tests
# ============================================================================

class TestListFlags:
    """Tests for FeatureFlagService.list_flags()."""

    def test_list_flags_returns_all(self):
        """Test list_flags returns all flags."""
        service = FeatureFlagService()
        service.create_flag("flag1", "First", FlagType.BOOLEAN)
        service.create_flag("flag2", "Second", FlagType.BOOLEAN)

        flags = service.list_flags()

        assert len(flags) == 2

    def test_list_flags_filters_by_status(self):
        """Test list_flags filters by status."""
        service = FeatureFlagService()
        service.create_flag("active_flag", "Active", FlagType.BOOLEAN)
        service.create_flag("archived_flag", "Archive", FlagType.BOOLEAN)
        service.archive_flag("archived_flag")

        active_flags = service.list_flags(status=FlagStatus.ACTIVE)
        archived_flags = service.list_flags(status=FlagStatus.ARCHIVED)

        assert len(archived_flags) == 1

    def test_list_flags_empty_list(self):
        """Test list_flags returns empty list."""
        service = FeatureFlagService()

        flags = service.list_flags()

        assert flags == []


# ============================================================================
# Bulk Evaluate Tests
# ============================================================================

class TestBulkEvaluate:
    """Tests for FeatureFlagService.bulk_evaluate()."""

    def test_bulk_evaluate_evaluates_multiple(self):
        """Test bulk_evaluate evaluates multiple flags."""
        service = FeatureFlagService()
        service.create_flag(
            "flag1",
            "First",
            FlagType.BOOLEAN,
            enabled=True,
            status=FlagStatus.ACTIVE
        )
        service.create_flag("flag2", "Second", FlagType.BOOLEAN, enabled=False)

        results = service.bulk_evaluate(["flag1", "flag2"])

        assert len(results) == 2
        assert results["flag1"] is True
        assert results["flag2"] is False

    def test_bulk_evaluate_returns_dict(self):
        """Test bulk_evaluate returns dictionary."""
        service = FeatureFlagService()
        service.create_flag("test1", "Test 1", FlagType.BOOLEAN)
        service.create_flag("test2", "Test 2", FlagType.BOOLEAN)

        results = service.bulk_evaluate(["test1", "test2"])

        assert isinstance(results, dict)
        assert "test1" in results
        assert "test2" in results

    def test_bulk_evaluate_empty_list(self):
        """Test bulk_evaluate with empty list."""
        service = FeatureFlagService()

        results = service.bulk_evaluate([])

        assert results == {}


# ============================================================================
# Get Stats Tests
# ============================================================================

class TestGetStats:
    """Tests for FeatureFlagService.get_stats()."""

    def test_get_stats_returns_stats(self):
        """Test get_stats returns statistics."""
        service = FeatureFlagService()
        service.create_flag("flag1", "First", FlagType.BOOLEAN)

        stats = service.get_stats()

        assert stats is not None

    def test_get_stats_counts_flags(self):
        """Test get_stats counts flags."""
        service = FeatureFlagService()
        service.create_flag("flag1", "First", FlagType.BOOLEAN)
        service.create_flag("flag2", "Second", FlagType.BOOLEAN)

        stats = service.get_stats()

        assert stats["total_flags"] == 2

    def test_get_stats_evaluation_counts(self):
        """Test get_stats includes evaluation counts."""
        service = FeatureFlagService()
        service.create_flag("flag1", "First", FlagType.BOOLEAN, enabled=True)
        service.evaluate_flag("flag1")
        service.evaluate_flag("flag1")

        stats = service.get_stats()

        assert "total_evaluations" in stats
        assert "flag_evaluation_counts" in stats
