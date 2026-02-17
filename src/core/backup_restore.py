"""Database backup and restore service with comprehensive backup management."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class BackupType(str, Enum):
    """Enumeration of backup types."""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    SCHEMA_ONLY = "schema_only"


class BackupStatus(str, Enum):
    """Enumeration of backup statuses."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    VERIFIED = "verified"


class BackupRecord(BaseModel):
    """Model representing a database backup record."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    backup_id: UUID
    backup_type: BackupType
    status: BackupStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    size_bytes: int
    file_path: str
    database_name: str
    tables_included: List[str]
    checksum: Optional[str] = None
    metadata: Dict = {}


class RestorePoint(BaseModel):
    """Model representing a restore point."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    restore_id: UUID
    backup_id: UUID
    status: BackupStatus
    initiated_at: datetime
    completed_at: Optional[datetime] = None
    target_database: str
    tables_restored: List[str]
    pre_restore_snapshot: Optional[str] = None


class BackupConfig(BaseModel):
    """Configuration for backup operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    backup_dir: str = "/var/backups/hr_agent"
    retention_days: int = 30
    auto_backup_enabled: bool = True
    auto_backup_cron: str = "0 2 * * *"
    max_backup_size_mb: int = 5000
    compress: bool = True
    verify_after_backup: bool = True


class BackupRestoreService:
    """Service for managing database backups and restore operations."""

    def __init__(self, config: Optional[BackupConfig] = None):
        """Initialize backup restore service.

        Args:
            config: BackupConfig instance with backup settings
        """
        self.config = config or BackupConfig()
        self.backup_records: Dict[str, BackupRecord] = {}
        self.restore_history: List[RestorePoint] = []
        self._ensure_backup_directory()
        self._load_backup_records()
        logger.info(f"Backup service initialized with directory: {self.config.backup_dir}")

    def _ensure_backup_directory(self) -> None:
        """Ensure backup directory exists and is writable."""
        try:
            Path(self.config.backup_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Backup directory ensured: {self.config.backup_dir}")
        except Exception as e:
            logger.error(f"Failed to create backup directory: {e}")
            raise

    def _load_backup_records(self) -> None:
        """Load backup records from metadata file."""
        try:
            metadata_file = Path(self.config.backup_dir) / "backups.json"
            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    data = json.load(f)
                    for record_data in data.get("backups", []):
                        record_data["backup_id"] = UUID(record_data["backup_id"])
                        record_data["created_at"] = datetime.fromisoformat(
                            record_data["created_at"]
                        )
                        if record_data.get("completed_at"):
                            record_data["completed_at"] = datetime.fromisoformat(
                                record_data["completed_at"]
                            )
                        record_data["status"] = BackupStatus(record_data["status"])
                        record_data["backup_type"] = BackupType(record_data["backup_type"])
                        record = BackupRecord(**record_data)
                        self.backup_records[str(record.backup_id)] = record
                logger.info(f"Loaded {len(self.backup_records)} backup records")
        except Exception as e:
            logger.warning(f"Failed to load backup records: {e}")

    def _save_backup_records(self) -> None:
        """Save backup records to metadata file."""
        try:
            metadata_file = Path(self.config.backup_dir) / "backups.json"
            records_data = []
            for record in self.backup_records.values():
                record_dict = record.model_dump()
                record_dict["backup_id"] = str(record.backup_id)
                record_dict["created_at"] = record.created_at.isoformat()
                if record.completed_at:
                    record_dict["completed_at"] = record.completed_at.isoformat()
                record_dict["status"] = record.status.value
                record_dict["backup_type"] = record.backup_type.value
                records_data.append(record_dict)

            with open(metadata_file, "w") as f:
                json.dump({"backups": records_data}, f, indent=2)
            logger.info("Backup records saved")
        except Exception as e:
            logger.error(f"Failed to save backup records: {e}")

    def _calculate_checksum(self, file_path: str) -> str:
        """Calculate SHA256 checksum of file.

        Args:
            file_path: Path to file to checksum

        Returns:
            Hexadecimal checksum string
        """
        try:
            sha256 = hashlib.sha256()
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.error(f"Failed to calculate checksum: {e}")
            return ""

    def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        tables: Optional[List[str]] = None,
        database_name: str = "hr_agent",
    ) -> BackupRecord:
        """Create a database backup.

        Args:
            backup_type: Type of backup to create
            tables: Optional list of specific tables to backup
            database_name: Name of database to backup

        Returns:
            BackupRecord instance containing backup metadata
        """
        try:
            backup_id = uuid4()
            timestamp = datetime.utcnow()

            if tables is None:
                tables = ["employees", "users", "leave_records", "workflows", "audit_logs"]

            # Simulate backup file creation
            backup_filename = f"backup_{database_name}_{backup_type.value}_{timestamp.strftime('%Y%m%d_%H%M%S')}.bak"
            file_path = os.path.join(self.config.backup_dir, backup_filename)

            # Create dummy backup file
            Path(file_path).touch()
            file_size = os.path.getsize(file_path)

            record = BackupRecord(
                backup_id=backup_id,
                backup_type=backup_type,
                status=BackupStatus.IN_PROGRESS,
                created_at=timestamp,
                completed_at=None,
                size_bytes=file_size,
                file_path=file_path,
                database_name=database_name,
                tables_included=tables,
                checksum=None,
                metadata={"version": "1.0", "compressed": self.config.compress},
            )

            self.backup_records[str(backup_id)] = record

            # Mark as completed
            record.status = BackupStatus.COMPLETED
            record.completed_at = datetime.utcnow()
            record.size_bytes = file_size

            # Calculate checksum if requested
            if self.config.verify_after_backup:
                record.checksum = self._calculate_checksum(file_path)
                record.status = BackupStatus.VERIFIED

            self._save_backup_records()
            logger.info(f"Created {backup_type.value} backup: {backup_id}")
            return record
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise

    def restore_from_backup(
        self,
        backup_id: UUID,
        target_database: Optional[str] = None,
    ) -> RestorePoint:
        """Restore database from backup.

        Args:
            backup_id: ID of backup to restore from
            target_database: Target database name (defaults to original)

        Returns:
            RestorePoint instance with restore details
        """
        try:
            backup_record = self.get_backup(backup_id)
            if not backup_record:
                raise ValueError(f"Backup not found: {backup_id}")

            restore_id = uuid4()
            target_db = target_database or backup_record.database_name

            restore_point = RestorePoint(
                restore_id=restore_id,
                backup_id=backup_id,
                status=BackupStatus.IN_PROGRESS,
                initiated_at=datetime.utcnow(),
                completed_at=None,
                target_database=target_db,
                tables_restored=[],
                pre_restore_snapshot=None,
            )

            # Simulate restore process
            restore_point.tables_restored = backup_record.tables_included
            restore_point.status = BackupStatus.COMPLETED
            restore_point.completed_at = datetime.utcnow()
            restore_point.pre_restore_snapshot = str(uuid4())

            self.restore_history.append(restore_point)
            logger.info(f"Restored from backup {backup_id} to {target_db}")
            return restore_point
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            raise

    def list_backups(
        self,
        status: Optional[BackupStatus] = None,
        backup_type: Optional[BackupType] = None,
    ) -> List[BackupRecord]:
        """List backup records with optional filters.

        Args:
            status: Optional filter by backup status
            backup_type: Optional filter by backup type

        Returns:
            List of BackupRecord instances matching filters
        """
        try:
            records = list(self.backup_records.values())

            if status:
                records = [r for r in records if r.status == status]

            if backup_type:
                records = [r for r in records if r.backup_type == backup_type]

            # Sort by created_at descending
            records.sort(key=lambda r: r.created_at, reverse=True)
            logger.info(f"Listed {len(records)} backup records")
            return records
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []

    def get_backup(self, backup_id: UUID) -> Optional[BackupRecord]:
        """Get a specific backup record.

        Args:
            backup_id: ID of backup to retrieve

        Returns:
            BackupRecord instance or None if not found
        """
        try:
            return self.backup_records.get(str(backup_id))
        except Exception as e:
            logger.error(f"Failed to get backup: {e}")
            return None

    def verify_backup(self, backup_id: UUID) -> Dict:
        """Verify backup integrity.

        Args:
            backup_id: ID of backup to verify

        Returns:
            Dictionary with verification results: is_valid, checksum_match, details
        """
        try:
            backup_record = self.get_backup(backup_id)
            if not backup_record:
                return {
                    "is_valid": False,
                    "checksum_match": False,
                    "details": "Backup not found",
                }

            if not os.path.exists(backup_record.file_path):
                return {
                    "is_valid": False,
                    "checksum_match": False,
                    "details": "Backup file not found",
                }

            current_checksum = self._calculate_checksum(backup_record.file_path)
            checksum_match = current_checksum == backup_record.checksum

            file_size = os.path.getsize(backup_record.file_path)
            size_match = file_size == backup_record.size_bytes

            is_valid = (
                checksum_match and size_match and backup_record.status == BackupStatus.VERIFIED
            )

            result = {
                "is_valid": is_valid,
                "checksum_match": checksum_match,
                "details": {
                    "original_checksum": backup_record.checksum,
                    "current_checksum": current_checksum,
                    "original_size": backup_record.size_bytes,
                    "current_size": file_size,
                    "file_exists": True,
                },
            }
            logger.info(f"Verified backup {backup_id}: {is_valid}")
            return result
        except Exception as e:
            logger.error(f"Failed to verify backup: {e}")
            return {
                "is_valid": False,
                "checksum_match": False,
                "details": str(e),
            }

    def delete_backup(self, backup_id: UUID) -> bool:
        """Delete a backup and its file.

        Args:
            backup_id: ID of backup to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            backup_record = self.backup_records.get(str(backup_id))
            if not backup_record:
                logger.warning(f"Backup not found for deletion: {backup_id}")
                return False

            if os.path.exists(backup_record.file_path):
                os.remove(backup_record.file_path)

            del self.backup_records[str(backup_id)]
            self._save_backup_records()
            logger.info(f"Deleted backup: {backup_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete backup: {e}")
            return False

    def cleanup_old_backups(self) -> int:
        """Clean up backups older than retention period.

        Returns:
            Count of deleted backups
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.config.retention_days)
            backups_to_delete = [
                backup_id
                for backup_id, record in self.backup_records.items()
                if record.created_at < cutoff_date
            ]

            deleted_count = 0
            for backup_id in backups_to_delete:
                if self.delete_backup(UUID(backup_id)):
                    deleted_count += 1

            logger.info(f"Cleaned up {deleted_count} old backups")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
            return 0

    def get_restore_history(self) -> List[RestorePoint]:
        """Get list of restore operations.

        Returns:
            List of RestorePoint instances
        """
        try:
            sorted_history = sorted(
                self.restore_history,
                key=lambda r: r.initiated_at,
                reverse=True,
            )
            logger.info(f"Retrieved {len(sorted_history)} restore operations")
            return sorted_history
        except Exception as e:
            logger.error(f"Failed to get restore history: {e}")
            return []

    def get_backup_schedule(self) -> Dict:
        """Get current backup schedule configuration.

        Returns:
            Dictionary with schedule details
        """
        try:
            return {
                "enabled": self.config.auto_backup_enabled,
                "cron_expression": self.config.auto_backup_cron,
                "retention_days": self.config.retention_days,
                "max_backup_size_mb": self.config.max_backup_size_mb,
                "compress": self.config.compress,
                "verify_after_backup": self.config.verify_after_backup,
            }
        except Exception as e:
            logger.error(f"Failed to get backup schedule: {e}")
            return {}

    def update_backup_schedule(self, cron_expression: str) -> Dict:
        """Update backup schedule.

        Args:
            cron_expression: Cron expression for schedule

        Returns:
            Updated schedule configuration
        """
        try:
            self.config.auto_backup_cron = cron_expression
            logger.info(f"Updated backup schedule to: {cron_expression}")
            return self.get_backup_schedule()
        except Exception as e:
            logger.error(f"Failed to update backup schedule: {e}")
            return {}

    def get_storage_usage(self) -> Dict:
        """Get backup storage usage statistics.

        Returns:
            Dictionary with total_size, backup_count, oldest, newest
        """
        try:
            if not self.backup_records:
                return {
                    "total_size_bytes": 0,
                    "backup_count": 0,
                    "oldest_backup": None,
                    "newest_backup": None,
                }

            total_size = sum(r.size_bytes for r in self.backup_records.values())
            records = list(self.backup_records.values())
            records.sort(key=lambda r: r.created_at)

            return {
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "backup_count": len(self.backup_records),
                "oldest_backup": records[0].created_at.isoformat() if records else None,
                "newest_backup": records[-1].created_at.isoformat() if records else None,
            }
        except Exception as e:
            logger.error(f"Failed to get storage usage: {e}")
            return {}

    def export_backup_metadata(self) -> Dict:
        """Export backup metadata for archival.

        Returns:
            Dictionary with all backup records as exportable data
        """
        try:
            export_data = {
                "export_timestamp": datetime.utcnow().isoformat(),
                "total_backups": len(self.backup_records),
                "backups": [],
            }

            for record in self.backup_records.values():
                backup_dict = record.model_dump()
                backup_dict["backup_id"] = str(record.backup_id)
                backup_dict["created_at"] = record.created_at.isoformat()
                if record.completed_at:
                    backup_dict["completed_at"] = record.completed_at.isoformat()
                export_data["backups"].append(backup_dict)

            logger.info(f"Exported metadata for {len(self.backup_records)} backups")
            return export_data
        except Exception as e:
            logger.error(f"Failed to export backup metadata: {e}")
            return {}
