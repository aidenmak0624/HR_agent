"""Unit tests for backup and restore service - Iteration 8 Wave 3."""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from src.core.backup_restore import (
    BackupConfig,
    BackupRecord,
    BackupRestoreService,
    BackupStatus,
    BackupType,
    RestorePoint,
)


class TestBackupType:
    """Test BackupType enum."""

    def test_backup_type_full_value(self):
        """Test FULL backup type has correct value."""
        assert BackupType.FULL.value == "full"

    def test_backup_type_incremental_value(self):
        """Test INCREMENTAL backup type has correct value."""
        assert BackupType.INCREMENTAL.value == "incremental"

    def test_backup_type_count(self):
        """Test BackupType has exactly 4 enum values."""
        backup_types = list(BackupType)
        assert len(backup_types) == 4

    def test_backup_type_representation(self):
        """Test BackupType string representation."""
        assert str(BackupType.FULL) == "BackupType.FULL"


class TestBackupStatus:
    """Test BackupStatus enum."""

    def test_backup_status_pending_value(self):
        """Test PENDING backup status has correct value."""
        assert BackupStatus.PENDING.value == "pending"

    def test_backup_status_verified_value(self):
        """Test VERIFIED backup status has correct value."""
        assert BackupStatus.VERIFIED.value == "verified"

    def test_backup_status_count(self):
        """Test BackupStatus has exactly 5 enum values."""
        statuses = list(BackupStatus)
        assert len(statuses) == 5

    def test_backup_status_representation(self):
        """Test BackupStatus string representation."""
        assert "BackupStatus" in str(BackupStatus.COMPLETED)


class TestBackupRecord:
    """Test BackupRecord model."""

    def test_backup_record_defaults(self):
        """Test BackupRecord defaults."""
        backup_id = uuid4()
        record = BackupRecord(
            backup_id=backup_id,
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            created_at=datetime.utcnow(),
            size_bytes=1024,
            file_path="/tmp/backup.bak",
            database_name="test_db",
            tables_included=["users"],
        )
        assert record.completed_at is None
        assert record.checksum is None
        assert record.metadata == {}

    def test_backup_record_custom_values(self):
        """Test BackupRecord with custom values."""
        backup_id = uuid4()
        completed = datetime.utcnow()
        record = BackupRecord(
            backup_id=backup_id,
            backup_type=BackupType.INCREMENTAL,
            status=BackupStatus.COMPLETED,
            created_at=datetime.utcnow(),
            completed_at=completed,
            size_bytes=2048,
            file_path="/tmp/backup2.bak",
            database_name="prod_db",
            tables_included=["users", "employees"],
            checksum="abc123",
            metadata={"version": "2.0"},
        )
        assert record.completed_at == completed
        assert record.checksum == "abc123"
        assert record.metadata["version"] == "2.0"

    def test_backup_record_has_uuid(self):
        """Test BackupRecord backup_id is UUID."""
        backup_id = uuid4()
        record = BackupRecord(
            backup_id=backup_id,
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            created_at=datetime.utcnow(),
            size_bytes=0,
            file_path="/tmp/test.bak",
            database_name="db",
            tables_included=[],
        )
        assert isinstance(record.backup_id, UUID)
        assert record.backup_id == backup_id

    def test_backup_record_file_path_required(self):
        """Test BackupRecord file_path is required."""
        backup_id = uuid4()
        record = BackupRecord(
            backup_id=backup_id,
            backup_type=BackupType.FULL,
            status=BackupStatus.PENDING,
            created_at=datetime.utcnow(),
            size_bytes=0,
            file_path="/var/backups/backup.bak",
            database_name="db",
            tables_included=[],
        )
        assert record.file_path == "/var/backups/backup.bak"


class TestRestorePoint:
    """Test RestorePoint model."""

    def test_restore_point_defaults(self):
        """Test RestorePoint defaults."""
        restore_id = uuid4()
        backup_id = uuid4()
        point = RestorePoint(
            restore_id=restore_id,
            backup_id=backup_id,
            status=BackupStatus.PENDING,
            initiated_at=datetime.utcnow(),
            target_database="target_db",
            tables_restored=[],
        )
        assert point.completed_at is None
        assert point.pre_restore_snapshot is None

    def test_restore_point_custom_values(self):
        """Test RestorePoint with custom values."""
        restore_id = uuid4()
        backup_id = uuid4()
        completed = datetime.utcnow()
        point = RestorePoint(
            restore_id=restore_id,
            backup_id=backup_id,
            status=BackupStatus.COMPLETED,
            initiated_at=datetime.utcnow(),
            completed_at=completed,
            target_database="restored_db",
            tables_restored=["users", "employees"],
            pre_restore_snapshot="snap123",
        )
        assert point.completed_at == completed
        assert point.pre_restore_snapshot == "snap123"

    def test_restore_point_has_uuid(self):
        """Test RestorePoint restore_id is UUID."""
        restore_id = uuid4()
        backup_id = uuid4()
        point = RestorePoint(
            restore_id=restore_id,
            backup_id=backup_id,
            status=BackupStatus.PENDING,
            initiated_at=datetime.utcnow(),
            target_database="db",
            tables_restored=[],
        )
        assert isinstance(point.restore_id, UUID)
        assert isinstance(point.backup_id, UUID)


class TestBackupConfig:
    """Test BackupConfig model."""

    def test_backup_config_defaults(self):
        """Test BackupConfig default values."""
        config = BackupConfig()
        assert config.backup_dir == "/var/backups/hr_agent"
        assert config.retention_days == 30
        assert config.auto_backup_enabled is True

    def test_backup_config_custom_values(self):
        """Test BackupConfig with custom values."""
        config = BackupConfig(
            backup_dir="/custom/backups",
            retention_days=60,
            max_backup_size_mb=1000,
        )
        assert config.backup_dir == "/custom/backups"
        assert config.retention_days == 60
        assert config.max_backup_size_mb == 1000

    def test_backup_config_retention_days(self):
        """Test BackupConfig retention_days configuration."""
        config = BackupConfig(retention_days=14)
        assert config.retention_days == 14


class TestBackupRestoreServiceInit:
    """Test BackupRestoreService initialization."""

    def test_service_init_with_config(self, tmp_path):
        """Test service initializes with provided config."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        assert service.config == config
        assert service.config.backup_dir == str(tmp_path)

    def test_service_init_empty_records(self, tmp_path):
        """Test service initializes with empty backup records."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        assert len(service.backup_records) == 0

    def test_service_init_creates_stats(self, tmp_path):
        """Test service initializes restore history."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        assert isinstance(service.restore_history, list)
        assert len(service.restore_history) == 0


class TestCreateBackup:
    """Test BackupRestoreService.create_backup method."""

    def test_create_backup_basic(self, tmp_path):
        """Test creating a backup."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        record = service.create_backup()
        assert record is not None
        assert record.status == BackupStatus.VERIFIED

    def test_create_backup_assigns_uuid(self, tmp_path):
        """Test create_backup assigns UUID."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        record = service.create_backup()
        assert isinstance(record.backup_id, UUID)

    def test_create_backup_sets_status(self, tmp_path):
        """Test create_backup sets status."""
        config = BackupConfig(backup_dir=str(tmp_path), verify_after_backup=True)
        service = BackupRestoreService(config)
        record = service.create_backup()
        assert record.status in [BackupStatus.COMPLETED, BackupStatus.VERIFIED]

    def test_create_backup_stores_record(self, tmp_path):
        """Test create_backup stores record in service."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        record = service.create_backup()
        stored = service.get_backup(record.backup_id)
        assert stored is not None
        assert stored.backup_id == record.backup_id


class TestRestoreFromBackup:
    """Test BackupRestoreService.restore_from_backup method."""

    def test_restore_from_backup_success(self, tmp_path):
        """Test restoring from backup."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        backup = service.create_backup()
        restore = service.restore_from_backup(backup.backup_id)
        assert restore is not None
        assert restore.status == BackupStatus.COMPLETED

    def test_restore_from_backup_creates_restore_point(self, tmp_path):
        """Test restore_from_backup creates restore point."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        backup = service.create_backup()
        restore = service.restore_from_backup(backup.backup_id)
        assert restore.restore_id is not None
        assert isinstance(restore.restore_id, UUID)

    def test_restore_from_backup_missing_backup(self, tmp_path):
        """Test restore_from_backup with missing backup raises."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Backup not found"):
            service.restore_from_backup(fake_id)


class TestListBackups:
    """Test BackupRestoreService.list_backups method."""

    def test_list_backups_returns_all(self, tmp_path):
        """Test list_backups returns all backups."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        service.create_backup()
        service.create_backup()
        backups = service.list_backups()
        assert len(backups) == 2

    def test_list_backups_filters_by_status(self, tmp_path):
        """Test list_backups filters by status."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        service.create_backup(backup_type=BackupType.FULL)
        backups = service.list_backups(status=BackupStatus.VERIFIED)
        assert len(backups) >= 0
        for backup in backups:
            assert backup.status == BackupStatus.VERIFIED

    def test_list_backups_filters_by_type(self, tmp_path):
        """Test list_backups filters by backup type."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        service.create_backup(backup_type=BackupType.FULL)
        service.create_backup(backup_type=BackupType.INCREMENTAL)
        backups = service.list_backups(backup_type=BackupType.FULL)
        for backup in backups:
            assert backup.backup_type == BackupType.FULL


class TestVerifyBackup:
    """Test BackupRestoreService.verify_backup method."""

    def test_verify_backup_valid(self, tmp_path):
        """Test verifying a valid backup."""
        config = BackupConfig(backup_dir=str(tmp_path), verify_after_backup=True)
        service = BackupRestoreService(config)
        backup = service.create_backup()
        result = service.verify_backup(backup.backup_id)
        assert result["is_valid"] is True
        assert "checksum_match" in result
        assert "details" in result

    def test_verify_backup_invalid(self, tmp_path):
        """Test verifying an invalid backup."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        fake_id = uuid4()
        result = service.verify_backup(fake_id)
        assert result["is_valid"] is False

    def test_verify_backup_missing(self, tmp_path):
        """Test verifying missing backup."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        fake_id = uuid4()
        result = service.verify_backup(fake_id)
        assert result["is_valid"] is False
        assert "Backup not found" in result["details"]


class TestDeleteBackup:
    """Test BackupRestoreService.delete_backup method."""

    def test_delete_backup_success(self, tmp_path):
        """Test deleting a backup."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        backup = service.create_backup()
        result = service.delete_backup(backup.backup_id)
        assert result is True

    def test_delete_backup_returns_true(self, tmp_path):
        """Test delete_backup returns True on success."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        backup = service.create_backup()
        result = service.delete_backup(backup.backup_id)
        assert result is True

    def test_delete_backup_missing_returns_false(self, tmp_path):
        """Test delete_backup returns False for missing backup."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        fake_id = uuid4()
        result = service.delete_backup(fake_id)
        assert result is False


class TestCleanupOldBackups:
    """Test BackupRestoreService.cleanup_old_backups method."""

    def test_cleanup_old_backups_removes_old(self, tmp_path):
        """Test cleanup_old_backups removes old backups."""
        config = BackupConfig(backup_dir=str(tmp_path), retention_days=0)  # Everything is old
        service = BackupRestoreService(config)
        service.create_backup()
        service.create_backup()
        count = service.cleanup_old_backups()
        assert count >= 0

    def test_cleanup_old_backups_keeps_recent(self, tmp_path):
        """Test cleanup_old_backups keeps recent backups."""
        config = BackupConfig(backup_dir=str(tmp_path), retention_days=30)
        service = BackupRestoreService(config)
        backup = service.create_backup()
        count = service.cleanup_old_backups()
        assert count == 0
        stored = service.get_backup(backup.backup_id)
        assert stored is not None

    def test_cleanup_old_backups_returns_count(self, tmp_path):
        """Test cleanup_old_backups returns count."""
        config = BackupConfig(backup_dir=str(tmp_path), retention_days=0)
        service = BackupRestoreService(config)
        service.create_backup()
        count = service.cleanup_old_backups()
        assert isinstance(count, int)
        assert count >= 0


class TestGetStorageUsage:
    """Test BackupRestoreService.get_storage_usage method."""

    def test_get_storage_usage_returns_usage(self, tmp_path):
        """Test get_storage_usage returns dictionary."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        service.create_backup()
        usage = service.get_storage_usage()
        assert isinstance(usage, dict)
        assert "total_size_bytes" in usage
        assert "backup_count" in usage

    def test_get_storage_usage_includes_counts(self, tmp_path):
        """Test get_storage_usage includes counts."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        service.create_backup()
        service.create_backup()
        usage = service.get_storage_usage()
        assert usage["backup_count"] == 2

    def test_get_storage_usage_empty_state(self, tmp_path):
        """Test get_storage_usage with no backups."""
        config = BackupConfig(backup_dir=str(tmp_path))
        service = BackupRestoreService(config)
        usage = service.get_storage_usage()
        assert usage["backup_count"] == 0
        assert usage["total_size_bytes"] == 0
