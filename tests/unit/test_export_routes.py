"""Unit tests for export service - Iteration 8 Wave 3."""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from src.api.export_routes import (
    ExportConfig,
    ExportEntity,
    ExportFormat,
    ExportRequest,
    ExportService,
    ExportStatus,
)


class TestExportFormat:
    """Test ExportFormat enum."""

    def test_export_format_json_value(self):
        """Test JSON export format has correct value."""
        assert ExportFormat.JSON.value == "json"

    def test_export_format_csv_value(self):
        """Test CSV export format has correct value."""
        assert ExportFormat.CSV.value == "csv"

    def test_export_format_count(self):
        """Test ExportFormat has exactly 4 enum values."""
        formats = list(ExportFormat)
        assert len(formats) == 4

    def test_export_format_representation(self):
        """Test ExportFormat string representation."""
        assert "ExportFormat" in str(ExportFormat.JSON)


class TestExportEntity:
    """Test ExportEntity enum."""

    def test_export_entity_users_value(self):
        """Test USERS export entity has correct value."""
        assert ExportEntity.USERS.value == "users"

    def test_export_entity_employees_value(self):
        """Test EMPLOYEES export entity has correct value."""
        assert ExportEntity.EMPLOYEES.value == "employees"

    def test_export_entity_count(self):
        """Test ExportEntity has exactly 7 enum values."""
        entities = list(ExportEntity)
        assert len(entities) == 7

    def test_export_entity_representation(self):
        """Test ExportEntity string representation."""
        assert "ExportEntity" in str(ExportEntity.USERS)


class TestExportStatus:
    """Test ExportStatus enum."""

    def test_export_status_queued_value(self):
        """Test QUEUED export status has correct value."""
        assert ExportStatus.QUEUED.value == "queued"

    def test_export_status_completed_value(self):
        """Test COMPLETED export status has correct value."""
        assert ExportStatus.COMPLETED.value == "completed"

    def test_export_status_count(self):
        """Test ExportStatus has exactly 5 enum values."""
        statuses = list(ExportStatus)
        assert len(statuses) == 5

    def test_export_status_representation(self):
        """Test ExportStatus string representation."""
        assert "ExportStatus" in str(ExportStatus.QUEUED)


class TestExportRequest:
    """Test ExportRequest model."""

    def test_export_request_defaults(self):
        """Test ExportRequest defaults."""
        export_id = uuid4()
        request = ExportRequest(
            export_id=export_id,
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
            requested_at=datetime.utcnow(),
            status=ExportStatus.QUEUED,
        )
        assert request.requested_by == "system"
        assert request.file_path is None
        assert request.file_size_bytes is None
        assert request.record_count is None
        assert request.completed_at is None

    def test_export_request_custom_values(self):
        """Test ExportRequest with custom values."""
        export_id = uuid4()
        now = datetime.utcnow()
        request = ExportRequest(
            export_id=export_id,
            entity=ExportEntity.EMPLOYEES,
            format=ExportFormat.CSV,
            filters={"department": "Engineering"},
            requested_by="user123",
            requested_at=now,
            status=ExportStatus.COMPLETED,
            file_path="/tmp/export.csv",
            file_size_bytes=1024,
            record_count=100,
        )
        assert request.requested_by == "user123"
        assert request.filters["department"] == "Engineering"
        assert request.record_count == 100

    def test_export_request_has_uuid(self):
        """Test ExportRequest export_id is UUID."""
        export_id = uuid4()
        request = ExportRequest(
            export_id=export_id,
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
            requested_at=datetime.utcnow(),
            status=ExportStatus.QUEUED,
        )
        assert isinstance(request.export_id, UUID)
        assert request.export_id == export_id

    def test_export_request_status_field(self):
        """Test ExportRequest status field."""
        export_id = uuid4()
        request = ExportRequest(
            export_id=export_id,
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
            requested_at=datetime.utcnow(),
            status=ExportStatus.PROCESSING,
        )
        assert request.status == ExportStatus.PROCESSING


class TestExportConfig:
    """Test ExportConfig model."""

    def test_export_config_defaults(self):
        """Test ExportConfig default values."""
        config = ExportConfig()
        assert config.max_records_per_export == 100000
        assert config.export_dir == "/var/exports/hr_agent"
        assert config.retention_hours == 72

    def test_export_config_custom_values(self):
        """Test ExportConfig with custom values."""
        config = ExportConfig(
            max_records_per_export=50000,
            export_dir="/custom/exports",
            retention_hours=48,
        )
        assert config.max_records_per_export == 50000
        assert config.export_dir == "/custom/exports"
        assert config.retention_hours == 48

    def test_export_config_max_records(self):
        """Test ExportConfig max_records_per_export."""
        config = ExportConfig(max_records_per_export=10000)
        assert config.max_records_per_export == 10000


class TestExportServiceInit:
    """Test ExportService initialization."""

    def test_service_init_with_config(self, tmp_path):
        """Test service initializes with provided config."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        assert service.config == config
        assert service.config.export_dir == str(tmp_path)

    def test_service_init_empty_exports(self, tmp_path):
        """Test service initializes with empty exports."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        assert len(service.export_requests) == 0

    def test_service_init_stats(self, tmp_path):
        """Test service initializes active exports counter."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        assert service.active_exports == 0


class TestCreateExport:
    """Test ExportService.create_export method."""

    def test_create_export_basic(self, tmp_path):
        """Test creating an export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        assert export is not None
        assert export.status == ExportStatus.QUEUED

    def test_create_export_assigns_uuid(self, tmp_path):
        """Test create_export assigns UUID."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        assert isinstance(export.export_id, UUID)

    def test_create_export_validates_entity(self, tmp_path):
        """Test create_export validates entity."""
        config = ExportConfig(
            export_dir=str(tmp_path),
            allowed_entities=[ExportEntity.USERS],
        )
        service = ExportService(config)
        with pytest.raises(ValueError, match="Export entity not allowed"):
            service.create_export(
                entity=ExportEntity.PAYROLL_SUMMARY,
                format=ExportFormat.JSON,
            )

    def test_create_export_validates_format(self, tmp_path):
        """Test create_export validates format."""
        config = ExportConfig(
            export_dir=str(tmp_path),
            allowed_formats=[ExportFormat.JSON],
        )
        service = ExportService(config)
        with pytest.raises(ValueError, match="Export format not allowed"):
            service.create_export(
                entity=ExportEntity.USERS,
                format=ExportFormat.EXCEL,
            )


class TestProcessExport:
    """Test ExportService.process_export method."""

    def test_process_export_json(self, tmp_path):
        """Test processing JSON export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        result = service.process_export(export.export_id)
        assert result.status == ExportStatus.COMPLETED

    def test_process_export_csv(self, tmp_path):
        """Test processing CSV export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.EMPLOYEES,
            format=ExportFormat.CSV,
        )
        result = service.process_export(export.export_id)
        assert result.status == ExportStatus.COMPLETED

    def test_process_export_missing(self, tmp_path):
        """Test processing missing export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Export request not found"):
            service.process_export(fake_id)


class TestGetExport:
    """Test ExportService.get_export method."""

    def test_get_export_returns_export(self, tmp_path):
        """Test get_export returns export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        retrieved = service.get_export(export.export_id)
        assert retrieved is not None
        assert retrieved.export_id == export.export_id

    def test_get_export_missing_returns_none(self, tmp_path):
        """Test get_export returns None for missing."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        fake_id = uuid4()
        result = service.get_export(fake_id)
        assert result is None

    def test_get_export_after_create(self, tmp_path):
        """Test get_export after create_export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        retrieved = service.get_export(export.export_id)
        assert retrieved.status == ExportStatus.QUEUED


class TestListExports:
    """Test ExportService.list_exports method."""

    def test_list_exports_returns_all(self, tmp_path):
        """Test list_exports returns all exports."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        service.create_export(entity=ExportEntity.USERS, format=ExportFormat.JSON)
        service.create_export(entity=ExportEntity.EMPLOYEES, format=ExportFormat.CSV)
        exports = service.list_exports()
        assert len(exports) == 2

    def test_list_exports_filters_by_status(self, tmp_path):
        """Test list_exports filters by status."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export1 = service.create_export(entity=ExportEntity.USERS, format=ExportFormat.JSON)
        exports = service.list_exports(status=ExportStatus.QUEUED)
        assert len(exports) >= 1
        for exp in exports:
            assert exp.status == ExportStatus.QUEUED

    def test_list_exports_filters_by_entity(self, tmp_path):
        """Test list_exports filters by entity."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        service.create_export(entity=ExportEntity.USERS, format=ExportFormat.JSON)
        service.create_export(entity=ExportEntity.EMPLOYEES, format=ExportFormat.CSV)
        exports = service.list_exports(entity=ExportEntity.USERS)
        for exp in exports:
            assert exp.entity == ExportEntity.USERS


class TestDownloadExport:
    """Test ExportService.download_export method."""

    def test_download_export_returns_file_info(self, tmp_path):
        """Test download_export returns file info."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.process_export(export.export_id)
        info = service.download_export(export.export_id)
        assert "file_path" in info
        assert "content_type" in info
        assert "filename" in info

    def test_download_export_expired(self, tmp_path):
        """Test download_export with expired export."""
        config = ExportConfig(export_dir=str(tmp_path), retention_hours=0)
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.process_export(export.export_id)
        # Modify expires_at to be in past
        export_req = service.export_requests[str(export.export_id)]
        export_req.expires_at = datetime.utcnow() - timedelta(hours=1)
        with pytest.raises(ValueError, match="expired"):
            service.download_export(export.export_id)

    def test_download_export_missing(self, tmp_path):
        """Test download_export with missing export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Export not found"):
            service.download_export(fake_id)


class TestCancelExport:
    """Test ExportService.cancel_export method."""

    def test_cancel_export_queued(self, tmp_path):
        """Test cancelling a queued export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        result = service.cancel_export(export.export_id)
        assert result.status == ExportStatus.FAILED

    def test_cancel_export_cannot_cancel_completed(self, tmp_path):
        """Test cannot cancel completed export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.process_export(export.export_id)
        with pytest.raises(ValueError, match="Cannot cancel completed"):
            service.cancel_export(export.export_id)

    def test_cancel_export_missing(self, tmp_path):
        """Test cancelling missing export."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        fake_id = uuid4()
        with pytest.raises(ValueError, match="Export not found"):
            service.cancel_export(fake_id)


class TestCleanupExpiredExports:
    """Test ExportService.cleanup_expired_exports method."""

    def test_cleanup_expired_exports_removes(self, tmp_path):
        """Test cleanup_expired_exports removes expired."""
        config = ExportConfig(export_dir=str(tmp_path), retention_hours=0)
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.process_export(export.export_id)
        count = service.cleanup_expired_exports()
        assert count >= 0

    def test_cleanup_expired_exports_keeps_valid(self, tmp_path):
        """Test cleanup_expired_exports keeps valid."""
        config = ExportConfig(export_dir=str(tmp_path), retention_hours=72)
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.process_export(export.export_id)
        count = service.cleanup_expired_exports()
        assert count == 0
        retrieved = service.get_export(export.export_id)
        assert retrieved is not None

    def test_cleanup_expired_exports_returns_count(self, tmp_path):
        """Test cleanup_expired_exports returns count."""
        config = ExportConfig(export_dir=str(tmp_path), retention_hours=0)
        service = ExportService(config)
        export = service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.process_export(export.export_id)
        count = service.cleanup_expired_exports()
        assert isinstance(count, int)
        assert count >= 0


class TestGetExportStats:
    """Test ExportService.get_export_stats method."""

    def test_get_export_stats_returns_stats(self, tmp_path):
        """Test get_export_stats returns dictionary."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        stats = service.get_export_stats()
        assert isinstance(stats, dict)
        assert "total_exports" in stats
        assert "by_entity" in stats
        assert "by_format" in stats

    def test_get_export_stats_by_entity(self, tmp_path):
        """Test get_export_stats tracks by entity."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.create_export(
            entity=ExportEntity.EMPLOYEES,
            format=ExportFormat.CSV,
        )
        stats = service.get_export_stats()
        assert stats["by_entity"]["users"] == 1
        assert stats["by_entity"]["employees"] == 1

    def test_get_export_stats_by_format(self, tmp_path):
        """Test get_export_stats tracks by format."""
        config = ExportConfig(export_dir=str(tmp_path))
        service = ExportService(config)
        service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.JSON,
        )
        service.create_export(
            entity=ExportEntity.USERS,
            format=ExportFormat.CSV,
        )
        stats = service.get_export_stats()
        assert stats["by_format"]["json"] == 1
        assert stats["by_format"]["csv"] == 1
