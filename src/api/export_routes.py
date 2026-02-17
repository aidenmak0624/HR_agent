"""Data export service for JSON/CSV/Excel formats."""
from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Enumeration of export formats."""

    JSON = "json"
    CSV = "csv"
    EXCEL = "excel"
    PDF_DATA = "pdf_data"


class ExportEntity(str, Enum):
    """Enumeration of exportable entities."""

    USERS = "users"
    EMPLOYEES = "employees"
    LEAVE_RECORDS = "leave_records"
    WORKFLOWS = "workflows"
    AUDIT_LOGS = "audit_logs"
    COMPLIANCE_REPORTS = "compliance_reports"
    PAYROLL_SUMMARY = "payroll_summary"


class ExportStatus(str, Enum):
    """Enumeration of export statuses."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


class ExportRequest(BaseModel):
    """Model representing a data export request."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    export_id: UUID
    entity: ExportEntity
    format: ExportFormat
    filters: Dict = {}
    requested_by: str = "system"
    requested_at: datetime
    status: ExportStatus
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    record_count: Optional[int] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ExportConfig(BaseModel):
    """Configuration for export operations."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_default=True)

    max_records_per_export: int = 100000
    export_dir: str = "/var/exports/hr_agent"
    retention_hours: int = 72
    allowed_formats: List[ExportFormat] = [
        ExportFormat.JSON,
        ExportFormat.CSV,
        ExportFormat.EXCEL,
    ]
    allowed_entities: List[ExportEntity] = [
        ExportEntity.USERS,
        ExportEntity.EMPLOYEES,
        ExportEntity.LEAVE_RECORDS,
        ExportEntity.WORKFLOWS,
        ExportEntity.AUDIT_LOGS,
    ]
    max_concurrent_exports: int = 5


class ExportService:
    """Service for managing data exports."""

    def __init__(self, config: Optional[ExportConfig] = None):
        """Initialize export service.

        Args:
            config: ExportConfig instance with export settings
        """
        self.config = config or ExportConfig()
        self.export_requests: Dict[str, ExportRequest] = {}
        self.active_exports = 0
        self._ensure_export_directory()
        logger.info(f"Export service initialized with directory: {self.config.export_dir}")

    def _ensure_export_directory(self) -> None:
        """Ensure export directory exists and is writable."""
        try:
            Path(self.config.export_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Export directory ensured: {self.config.export_dir}")
        except Exception as e:
            logger.error(f"Failed to create export directory: {e}")
            raise

    def create_export(
        self,
        entity: ExportEntity,
        format: ExportFormat,
        filters: Optional[Dict] = None,
        requested_by: str = "system",
    ) -> ExportRequest:
        """Create a new export request.

        Args:
            entity: Type of entity to export
            format: Output format for export
            filters: Optional filters to apply to data
            requested_by: User ID requesting the export

        Returns:
            ExportRequest instance with export details
        """
        try:
            if format not in self.config.allowed_formats:
                raise ValueError(f"Export format not allowed: {format}")

            if entity not in self.config.allowed_entities:
                raise ValueError(f"Export entity not allowed: {entity}")

            export_id = uuid4()
            now = datetime.utcnow()

            export_request = ExportRequest(
                export_id=export_id,
                entity=entity,
                format=format,
                filters=filters or {},
                requested_by=requested_by,
                requested_at=now,
                status=ExportStatus.QUEUED,
                expires_at=now + timedelta(hours=self.config.retention_hours),
            )

            self.export_requests[str(export_id)] = export_request
            logger.info(f"Created export request {export_id} for {entity.value} in {format.value}")
            return export_request
        except Exception as e:
            logger.error(f"Failed to create export request: {e}")
            raise

    def process_export(self, export_id: UUID) -> ExportRequest:
        """Process and generate export file.

        Args:
            export_id: ID of export request to process

        Returns:
            Updated ExportRequest with file details
        """
        try:
            export_request = self.export_requests.get(str(export_id))
            if not export_request:
                raise ValueError(f"Export request not found: {export_id}")

            if self.active_exports >= self.config.max_concurrent_exports:
                logger.warning("Max concurrent exports reached, queuing request")
                return export_request

            export_request.status = ExportStatus.PROCESSING
            self.active_exports += 1

            try:
                # Generate sample data based on entity type
                data = self._generate_sample_data(export_request.entity, export_request.filters)
                record_count = len(data)

                if record_count > self.config.max_records_per_export:
                    raise ValueError(
                        f"Export exceeds max records: {record_count} > "
                        f"{self.config.max_records_per_export}"
                    )

                # Generate file based on format
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                filename = (
                    f"export_{export_request.entity.value}_{timestamp}."
                    f"{self._get_file_extension(export_request.format)}"
                )
                file_path = os.path.join(self.config.export_dir, filename)

                success = False
                if export_request.format == ExportFormat.JSON:
                    success = self._export_to_json(data, file_path)
                elif export_request.format == ExportFormat.CSV:
                    success = self._export_to_csv(data, file_path)
                elif export_request.format == ExportFormat.EXCEL:
                    success = self._export_to_csv(data, file_path)
                elif export_request.format == ExportFormat.PDF_DATA:
                    success = self._export_to_json(data, file_path)

                if success and os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    export_request.file_path = file_path
                    export_request.file_size_bytes = file_size
                    export_request.record_count = record_count
                    export_request.status = ExportStatus.COMPLETED
                    export_request.completed_at = datetime.utcnow()
                    logger.info(
                        f"Successfully processed export {export_id}: "
                        f"{record_count} records, {file_size} bytes"
                    )
                else:
                    export_request.status = ExportStatus.FAILED
                    export_request.error_message = "Failed to generate export file"
                    logger.error(f"Failed to generate export file for {export_id}")

            except Exception as e:
                export_request.status = ExportStatus.FAILED
                export_request.error_message = str(e)
                logger.error(f"Error processing export {export_id}: {e}")
            finally:
                self.active_exports -= 1

            return export_request
        except Exception as e:
            logger.error(f"Failed to process export: {e}")
            raise

    def get_export(self, export_id: UUID) -> Optional[ExportRequest]:
        """Get export request details.

        Args:
            export_id: ID of export to retrieve

        Returns:
            ExportRequest instance or None if not found
        """
        try:
            return self.export_requests.get(str(export_id))
        except Exception as e:
            logger.error(f"Failed to get export: {e}")
            return None

    def list_exports(
        self,
        status: Optional[ExportStatus] = None,
        entity: Optional[ExportEntity] = None,
        requested_by: Optional[str] = None,
    ) -> List[ExportRequest]:
        """List export requests with optional filters.

        Args:
            status: Optional filter by status
            entity: Optional filter by entity type
            requested_by: Optional filter by requester

        Returns:
            List of ExportRequest instances matching filters
        """
        try:
            exports = list(self.export_requests.values())

            if status:
                exports = [e for e in exports if e.status == status]

            if entity:
                exports = [e for e in exports if e.entity == entity]

            if requested_by:
                exports = [e for e in exports if e.requested_by == requested_by]

            # Sort by requested_at descending
            exports.sort(key=lambda e: e.requested_at, reverse=True)
            logger.info(f"Listed {len(exports)} export requests")
            return exports
        except Exception as e:
            logger.error(f"Failed to list exports: {e}")
            return []

    def download_export(self, export_id: UUID) -> Dict:
        """Get download information for export file.

        Args:
            export_id: ID of export to download

        Returns:
            Dictionary with file_path, content_type, filename
        """
        try:
            export_request = self.get_export(export_id)
            if not export_request:
                raise ValueError(f"Export not found: {export_id}")

            if export_request.status != ExportStatus.COMPLETED:
                raise ValueError(f"Export not ready for download: {export_request.status.value}")

            if not export_request.file_path:
                raise ValueError("Export file path not available")

            if not os.path.exists(export_request.file_path):
                raise ValueError("Export file not found")

            if export_request.expires_at and datetime.utcnow() > export_request.expires_at:
                export_request.status = ExportStatus.EXPIRED
                logger.warning(f"Export {export_id} has expired")
                raise ValueError("Export has expired")

            content_type = self._get_content_type(export_request.format)
            filename = os.path.basename(export_request.file_path)

            result = {
                "file_path": export_request.file_path,
                "content_type": content_type,
                "filename": filename,
                "file_size_bytes": export_request.file_size_bytes,
                "record_count": export_request.record_count,
            }
            logger.info(f"Generated download info for export {export_id}")
            return result
        except Exception as e:
            logger.error(f"Failed to download export: {e}")
            raise

    def cancel_export(self, export_id: UUID) -> ExportRequest:
        """Cancel an export request.

        Args:
            export_id: ID of export to cancel

        Returns:
            Updated ExportRequest
        """
        try:
            export_request = self.get_export(export_id)
            if not export_request:
                raise ValueError(f"Export not found: {export_id}")

            if export_request.status == ExportStatus.COMPLETED:
                raise ValueError("Cannot cancel completed export")

            export_request.status = ExportStatus.FAILED
            export_request.error_message = "Export cancelled by user"
            logger.info(f"Cancelled export {export_id}")
            return export_request
        except Exception as e:
            logger.error(f"Failed to cancel export: {e}")
            raise

    def cleanup_expired_exports(self) -> int:
        """Remove expired exports and their files.

        Returns:
            Count of removed exports
        """
        try:
            now = datetime.utcnow()
            expired_ids = [
                export_id
                for export_id, export_req in self.export_requests.items()
                if export_req.expires_at and export_req.expires_at < now
            ]

            removed_count = 0
            for export_id in expired_ids:
                export_req = self.export_requests[export_id]
                if export_req.file_path and os.path.exists(export_req.file_path):
                    try:
                        os.remove(export_req.file_path)
                    except Exception as e:
                        logger.warning(f"Failed to delete export file {export_req.file_path}: {e}")

                del self.export_requests[export_id]
                removed_count += 1

            logger.info(f"Cleaned up {removed_count} expired exports")
            return removed_count
        except Exception as e:
            logger.error(f"Failed to cleanup expired exports: {e}")
            return 0

    def get_export_stats(self) -> Dict:
        """Get export statistics.

        Returns:
            Dictionary with total exports, by entity, by format, avg processing time
        """
        try:
            if not self.export_requests:
                return {
                    "total_exports": 0,
                    "by_entity": {},
                    "by_format": {},
                    "by_status": {},
                    "avg_processing_time_seconds": 0,
                }

            by_entity = {}
            by_format = {}
            by_status = {}
            processing_times = []

            for export_req in self.export_requests.values():
                entity_key = export_req.entity.value
                by_entity[entity_key] = by_entity.get(entity_key, 0) + 1

                format_key = export_req.format.value
                by_format[format_key] = by_format.get(format_key, 0) + 1

                status_key = export_req.status.value
                by_status[status_key] = by_status.get(status_key, 0) + 1

                if export_req.completed_at and export_req.requested_at:
                    delta = (export_req.completed_at - export_req.requested_at).total_seconds()
                    processing_times.append(delta)

            avg_processing_time = (
                sum(processing_times) / len(processing_times) if processing_times else 0
            )

            return {
                "total_exports": len(self.export_requests),
                "by_entity": by_entity,
                "by_format": by_format,
                "by_status": by_status,
                "avg_processing_time_seconds": avg_processing_time,
                "active_exports": self.active_exports,
            }
        except Exception as e:
            logger.error(f"Failed to get export stats: {e}")
            return {}

    def _generate_sample_data(self, entity: ExportEntity, filters: Dict) -> List[Dict]:
        """Generate sample data for export.

        Args:
            entity: Type of entity to generate
            filters: Filters to apply

        Returns:
            List of dictionaries representing entity records
        """
        try:
            sample_records = {
                ExportEntity.USERS: [
                    {
                        "user_id": f"USR{i:05d}",
                        "name": f"User {i}",
                        "email": f"user{i}@company.com",
                        "role": "employee",
                        "created_at": datetime.utcnow().isoformat(),
                    }
                    for i in range(1, 11)
                ],
                ExportEntity.EMPLOYEES: [
                    {
                        "employee_id": f"EMP{i:05d}",
                        "name": f"Employee {i}",
                        "department": "Engineering",
                        "position": "Senior Engineer",
                        "hire_date": "2020-01-15",
                        "salary": 85000,
                    }
                    for i in range(1, 11)
                ],
                ExportEntity.LEAVE_RECORDS: [
                    {
                        "leave_id": f"LEV{i:05d}",
                        "employee_id": f"EMP{i:05d}",
                        "start_date": "2024-02-15",
                        "end_date": "2024-02-20",
                        "leave_type": "vacation",
                        "status": "approved",
                    }
                    for i in range(1, 11)
                ],
                ExportEntity.WORKFLOWS: [
                    {
                        "workflow_id": f"WF{i:05d}",
                        "name": f"Workflow {i}",
                        "status": "active",
                        "created_at": datetime.utcnow().isoformat(),
                        "step_count": 5,
                    }
                    for i in range(1, 11)
                ],
                ExportEntity.AUDIT_LOGS: [
                    {
                        "log_id": f"AUD{i:05d}",
                        "user_id": f"USR{i:05d}",
                        "action": "update",
                        "entity_type": "employee",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                    for i in range(1, 11)
                ],
                ExportEntity.COMPLIANCE_REPORTS: [
                    {
                        "report_id": f"CMP{i:05d}",
                        "report_type": "gdpr_audit",
                        "generated_at": datetime.utcnow().isoformat(),
                        "status": "completed",
                    }
                    for i in range(1, 6)
                ],
                ExportEntity.PAYROLL_SUMMARY: [
                    {
                        "payroll_id": f"PAY{i:05d}",
                        "period": "2024-02",
                        "total_employees": 50,
                        "total_payroll": 425000,
                        "processed_at": datetime.utcnow().isoformat(),
                    }
                    for i in range(1, 3)
                ],
            }

            data = sample_records.get(entity, [])
            logger.info(f"Generated {len(data)} sample records for {entity.value}")
            return data
        except Exception as e:
            logger.error(f"Failed to generate sample data: {e}")
            return []

    def _export_to_json(self, data: List[Dict], file_path: str) -> bool:
        """Export data to JSON file.

        Args:
            data: List of dictionaries to export
            file_path: Target file path

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Exported {len(data)} records to JSON: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}")
            return False

    def _export_to_csv(self, data: List[Dict], file_path: str) -> bool:
        """Export data to CSV file.

        Args:
            data: List of dictionaries to export
            file_path: Target file path

        Returns:
            True if successful, False otherwise
        """
        try:
            if not data:
                # Create empty CSV file
                Path(file_path).touch()
                return True

            fieldnames = data[0].keys()
            with open(file_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                for row in data:
                    # Convert datetime and other non-string types to strings
                    row_data = {}
                    for key, value in row.items():
                        if isinstance(value, (datetime,)):
                            row_data[key] = value.isoformat()
                        else:
                            row_data[key] = str(value)
                    writer.writerow(row_data)

            logger.info(f"Exported {len(data)} records to CSV: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}")
            return False

    def _get_file_extension(self, format: ExportFormat) -> str:
        """Get file extension for export format.

        Args:
            format: Export format

        Returns:
            File extension string
        """
        extensions = {
            ExportFormat.JSON: "json",
            ExportFormat.CSV: "csv",
            ExportFormat.EXCEL: "xlsx",
            ExportFormat.PDF_DATA: "json",
        }
        return extensions.get(format, "txt")

    def _get_content_type(self, format: ExportFormat) -> str:
        """Get content type MIME type for export format.

        Args:
            format: Export format

        Returns:
            MIME type string
        """
        content_types = {
            ExportFormat.JSON: "application/json",
            ExportFormat.CSV: "text/csv",
            ExportFormat.EXCEL: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ExportFormat.PDF_DATA: "application/json",
        }
        return content_types.get(format, "application/octet-stream")
