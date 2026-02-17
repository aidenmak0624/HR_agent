"""
WRITE-002: Policy Document Versioning and Lifecycle Management.

This module implements document versioning, approval workflows, and lifecycle
management for HR policy documents. Supports version tracking, approval states,
archival, and content comparison.
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List, Dict, Any
from uuid import uuid4
import difflib

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class DocumentStatus(str, Enum):
    """Document status states."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    DEPRECATED = "deprecated"


# ============================================================================
# Pydantic Models
# ============================================================================

class DocumentVersion(BaseModel):
    """Single version of a document."""
    version_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique version ID")
    document_id: str = Field(..., description="Parent document ID")
    version_number: str = Field(..., description="Version number (e.g., '1.0', '1.1')")
    content: str = Field(..., description="Document content")
    author: str = Field(..., description="Author ID")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    status: DocumentStatus = Field(default=DocumentStatus.DRAFT, description="Version status")
    change_summary: str = Field(default="", description="Summary of changes in this version")
    approved_by: Optional[str] = Field(None, description="User ID who approved this version")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")

    model_config = ConfigDict(use_enum_values=False)


class Document(BaseModel):
    """Document with version history."""
    document_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique document ID")
    title: str = Field(..., description="Document title")
    category: str = Field(..., description="Document category (e.g., 'compensation', 'pto')")
    current_version: str = Field(default="1.0", description="Current version number")
    versions: List[DocumentVersion] = Field(default_factory=list, description="All versions")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp")
    owner: str = Field(..., description="Document owner ID")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    model_config = ConfigDict(use_enum_values=False)


class DocumentConfig(BaseModel):
    """Configuration for document versioning service."""
    max_versions_retained: int = Field(50, description="Maximum versions to retain per document")
    require_approval: bool = Field(True, description="Require approval before publishing")
    auto_archive_days: int = Field(365, description="Days before auto-archiving deprecated documents")
    allowed_categories: List[str] = Field(
        default_factory=lambda: [
            "compensation",
            "pto",
            "benefits",
            "code_of_conduct",
            "hr_policies",
            "org_structure",
        ],
        description="Allowed document categories"
    )

    model_config = ConfigDict(use_enum_values=False)


# ============================================================================
# Document Versioning Service
# ============================================================================

class DocumentVersioningService:
    """
    Policy document versioning and lifecycle management service.

    Manages document versions, approval workflows, publishing, archival,
    and provides version comparison and rollback capabilities.
    """

    def __init__(self, config: DocumentConfig, audit_logger: Optional[Any] = None) -> None:
        """
        Initialize document versioning service.

        Args:
            config: DocumentConfig instance
            audit_logger: Optional audit logger instance
        """
        self.config = config
        self.audit_logger = audit_logger
        self.documents: Dict[str, Document] = {}
        self.versions: Dict[str, DocumentVersion] = {}

        logger.info("DocumentVersioningService initialized")

    def create_document(
        self,
        title: str,
        content: str,
        author: str,
        category: str,
        tags: Optional[List[str]] = None,
    ) -> Document:
        """
        Create a new document with initial version.

        Args:
            title: Document title
            content: Document content
            author: Author ID
            category: Document category
            tags: Optional list of tags

        Returns:
            Document instance

        Raises:
            ValueError: If category is invalid
        """
        try:
            if category not in self.config.allowed_categories:
                raise ValueError(f"Invalid category: {category}")

            document = Document(
                title=title,
                category=category,
                owner=author,
                tags=tags or [],
            )

            # Create initial version
            version = DocumentVersion(
                document_id=document.document_id,
                version_number="1.0",
                content=content,
                author=author,
                status=DocumentStatus.DRAFT,
                change_summary="Initial version",
            )

            document.versions.append(version)
            self.documents[document.document_id] = document
            self.versions[version.version_id] = version

            logger.info(f"Created document: {document.document_id} (v{version.version_number})")
            self._audit_log("document_created", document.document_id, author, {
                'title': title,
                'category': category,
            })

            return document

        except Exception as e:
            logger.error(f"Error creating document: {e}")
            raise ValueError(f"Failed to create document: {e}")

    def create_version(
        self,
        document_id: str,
        content: str,
        author: str,
        change_summary: str,
    ) -> DocumentVersion:
        """
        Create a new version of an existing document.

        Args:
            document_id: Document ID
            content: New version content
            author: Author ID
            change_summary: Summary of changes

        Returns:
            DocumentVersion instance

        Raises:
            ValueError: If document not found
        """
        try:
            document = self._get_document(document_id)

            # Calculate next version number
            last_version = document.versions[-1] if document.versions else None
            if last_version:
                major, minor = map(int, last_version.version_number.split('.'))
                next_version = f"{major}.{minor + 1}"
            else:
                next_version = "1.0"

            version = DocumentVersion(
                document_id=document_id,
                version_number=next_version,
                content=content,
                author=author,
                status=DocumentStatus.DRAFT,
                change_summary=change_summary,
            )

            document.versions.append(version)
            document.updated_at = datetime.utcnow()
            self.versions[version.version_id] = version

            logger.info(f"Created version {next_version} for document {document_id}")
            self._audit_log("version_created", document_id, author, {
                'version_number': next_version,
                'change_summary': change_summary,
            })

            return version

        except Exception as e:
            logger.error(f"Error creating version: {e}")
            raise ValueError(f"Failed to create version: {e}")

    def get_document(self, document_id: str) -> Document:
        """
        Retrieve document by ID.

        Args:
            document_id: Document ID

        Returns:
            Document instance

        Raises:
            ValueError: If document not found
        """
        return self._get_document(document_id)

    def get_version(self, document_id: str, version_number: str) -> Optional[DocumentVersion]:
        """
        Retrieve specific version of a document.

        Args:
            document_id: Document ID
            version_number: Version number (e.g., '1.0')

        Returns:
            DocumentVersion or None if not found
        """
        try:
            document = self._get_document(document_id)

            for version in document.versions:
                if version.version_number == version_number:
                    return version

            logger.warning(f"Version {version_number} not found for document {document_id}")
            return None

        except Exception as e:
            logger.error(f"Error retrieving version: {e}")
            return None

    def submit_for_review(self, document_id: str, version_number: str) -> DocumentVersion:
        """
        Submit document version for review.

        Args:
            document_id: Document ID
            version_number: Version number to submit

        Returns:
            Updated DocumentVersion

        Raises:
            ValueError: If version not found or invalid state
        """
        try:
            version = self.get_version(document_id, version_number)
            if not version:
                raise ValueError(f"Version not found: {version_number}")

            if version.status != DocumentStatus.DRAFT:
                raise ValueError(f"Cannot submit version in {version.status} state")

            version.status = DocumentStatus.PENDING_REVIEW
            logger.info(f"Submitted version {version_number} for review")
            self._audit_log("version_submitted", document_id, version.author, {
                'version_number': version_number,
            })

            return version

        except Exception as e:
            logger.error(f"Error submitting for review: {e}")
            raise ValueError(f"Failed to submit for review: {e}")

    def approve_version(
        self,
        document_id: str,
        version_number: str,
        approver: str,
    ) -> DocumentVersion:
        """
        Approve a document version.

        Args:
            document_id: Document ID
            version_number: Version number to approve
            approver: Approver ID

        Returns:
            Updated DocumentVersion

        Raises:
            ValueError: If version not found or invalid state
        """
        try:
            version = self.get_version(document_id, version_number)
            if not version:
                raise ValueError(f"Version not found: {version_number}")

            if version.status != DocumentStatus.PENDING_REVIEW:
                raise ValueError(f"Cannot approve version in {version.status} state")

            version.status = DocumentStatus.APPROVED
            version.approved_by = approver
            version.approved_at = datetime.utcnow()

            logger.info(f"Approved version {version_number} of document {document_id}")
            self._audit_log("version_approved", document_id, approver, {
                'version_number': version_number,
            })

            return version

        except Exception as e:
            logger.error(f"Error approving version: {e}")
            raise ValueError(f"Failed to approve version: {e}")

    def publish_version(self, document_id: str, version_number: str) -> DocumentVersion:
        """
        Publish a document version.

        Args:
            document_id: Document ID
            version_number: Version number to publish

        Returns:
            Updated DocumentVersion

        Raises:
            ValueError: If version not found or invalid state
        """
        try:
            document = self._get_document(document_id)
            version = self.get_version(document_id, version_number)

            if not version:
                raise ValueError(f"Version not found: {version_number}")

            if self.config.require_approval and version.status != DocumentStatus.APPROVED:
                raise ValueError(f"Version must be approved before publishing")

            if version.status not in [DocumentStatus.APPROVED, DocumentStatus.DRAFT]:
                raise ValueError(f"Cannot publish version in {version.status} state")

            # Deprecate previous published versions
            for v in document.versions:
                if v.status == DocumentStatus.PUBLISHED and v.version_number != version_number:
                    v.status = DocumentStatus.DEPRECATED

            version.status = DocumentStatus.PUBLISHED
            document.current_version = version_number
            document.updated_at = datetime.utcnow()

            logger.info(f"Published version {version_number} of document {document_id}")
            self._audit_log("version_published", document_id, version.author, {
                'version_number': version_number,
            })

            return version

        except Exception as e:
            logger.error(f"Error publishing version: {e}")
            raise ValueError(f"Failed to publish version: {e}")

    def archive_document(self, document_id: str) -> Document:
        """
        Archive a document and all its versions.

        Args:
            document_id: Document ID

        Returns:
            Updated Document

        Raises:
            ValueError: If document not found
        """
        try:
            document = self._get_document(document_id)

            for version in document.versions:
                if version.status != DocumentStatus.ARCHIVED:
                    version.status = DocumentStatus.ARCHIVED

            document.updated_at = datetime.utcnow()
            logger.info(f"Archived document: {document_id}")
            self._audit_log("document_archived", document_id, "system", {})

            return document

        except Exception as e:
            logger.error(f"Error archiving document: {e}")
            raise ValueError(f"Failed to archive document: {e}")

    def compare_versions(
        self,
        document_id: str,
        version_a: str,
        version_b: str,
    ) -> Dict[str, Any]:
        """
        Compare two versions of a document.

        Args:
            document_id: Document ID
            version_a: First version number
            version_b: Second version number

        Returns:
            Dictionary with diff information

        Raises:
            ValueError: If versions not found
        """
        try:
            v_a = self.get_version(document_id, version_a)
            v_b = self.get_version(document_id, version_b)

            if not v_a or not v_b:
                raise ValueError("One or both versions not found")

            # Generate line-by-line diff
            a_lines = v_a.content.splitlines(keepends=True)
            b_lines = v_b.content.splitlines(keepends=True)

            differ = difflib.unified_diff(a_lines, b_lines)
            diff_lines = list(differ)

            result = {
                'version_a': version_a,
                'version_b': version_b,
                'differences_found': len(diff_lines) > 0,
                'diff': ''.join(diff_lines),
                'added_lines': sum(1 for line in diff_lines if line.startswith('+')),
                'removed_lines': sum(1 for line in diff_lines if line.startswith('-')),
            }

            logger.info(f"Compared versions {version_a} and {version_b}")
            return result

        except Exception as e:
            logger.error(f"Error comparing versions: {e}")
            raise ValueError(f"Failed to compare versions: {e}")

    def rollback_to_version(
        self,
        document_id: str,
        version_number: str,
    ) -> DocumentVersion:
        """
        Rollback to a previous version by creating a new version with old content.

        Args:
            document_id: Document ID
            version_number: Version to rollback to

        Returns:
            New DocumentVersion with old content

        Raises:
            ValueError: If version not found
        """
        try:
            document = self._get_document(document_id)
            target_version = self.get_version(document_id, version_number)

            if not target_version:
                raise ValueError(f"Version not found: {version_number}")

            # Create new version with content from target version
            new_version = self.create_version(
                document_id=document_id,
                content=target_version.content,
                author="system",
                change_summary=f"Rolled back to version {version_number}",
            )

            logger.info(f"Rolled back document {document_id} to version {version_number}")
            self._audit_log("version_rollback", document_id, "system", {
                'rolled_back_to': version_number,
                'new_version': new_version.version_number,
            })

            return new_version

        except Exception as e:
            logger.error(f"Error rolling back version: {e}")
            raise ValueError(f"Failed to rollback version: {e}")

    def search_documents(
        self,
        query: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: Optional[DocumentStatus] = None,
    ) -> List[Document]:
        """
        Search documents by criteria.

        Args:
            query: Search query for title/content
            category: Filter by category
            tags: Filter by tags (any match)
            status: Filter by current version status

        Returns:
            List of matching documents
        """
        try:
            results = []

            for document in self.documents.values():
                # Apply category filter
                if category and document.category != category:
                    continue

                # Apply tags filter
                if tags and not any(tag in document.tags for tag in tags):
                    continue

                # Apply status filter
                if status:
                    current_version = self.get_version(document.document_id, document.current_version)
                    if not current_version or current_version.status != status:
                        continue

                # Apply query filter
                if query:
                    query_lower = query.lower()
                    title_match = query_lower in document.title.lower()
                    content_match = False

                    for version in document.versions:
                        if query_lower in version.content.lower():
                            content_match = True
                            break

                    if not (title_match or content_match):
                        continue

                results.append(document)

            logger.info(f"Found {len(results)} documents matching search criteria")
            return results

        except Exception as e:
            logger.error(f"Error searching documents: {e}")
            return []

    def get_document_history(self, document_id: str) -> List[DocumentVersion]:
        """
        Get complete version history for a document.

        Args:
            document_id: Document ID

        Returns:
            List of DocumentVersion objects in chronological order
        """
        try:
            document = self._get_document(document_id)
            logger.info(f"Retrieved history for document {document_id} with {len(document.versions)} versions")
            return document.versions

        except Exception as e:
            logger.error(f"Error retrieving document history: {e}")
            return []

    def cleanup_old_versions(self, document_id: str) -> int:
        """
        Remove old versions exceeding max_versions_retained limit.

        Args:
            document_id: Document ID

        Returns:
            Number of versions removed

        Raises:
            ValueError: If document not found
        """
        try:
            document = self._get_document(document_id)
            initial_count = len(document.versions)

            # Keep published and current versions
            versions_to_keep = set()
            for version in document.versions:
                if version.status == DocumentStatus.PUBLISHED:
                    versions_to_keep.add(version.version_id)
                if version.version_number == document.current_version:
                    versions_to_keep.add(version.version_id)

            # Sort by creation date and keep most recent
            sortable = [
                (v, i) for i, v in enumerate(document.versions)
                if v.version_id not in versions_to_keep
            ]
            sortable.sort(key=lambda x: x[0].created_at, reverse=True)

            # Keep up to max_versions_retained
            keep_count = max(0, self.config.max_versions_retained - len(versions_to_keep))
            for v, _ in sortable[:keep_count]:
                versions_to_keep.add(v.version_id)

            # Remove versions not in keep set
            removed_count = 0
            for version in document.versions[:]:
                if version.version_id not in versions_to_keep:
                    document.versions.remove(version)
                    del self.versions[version.version_id]
                    removed_count += 1

            logger.info(f"Cleaned up {removed_count} versions from document {document_id}")
            self._audit_log("cleanup_versions", document_id, "system", {
                'removed_count': removed_count,
            })

            return removed_count

        except Exception as e:
            logger.error(f"Error cleaning up versions: {e}")
            raise ValueError(f"Failed to cleanup versions: {e}")

    def _get_document(self, document_id: str) -> Document:
        """
        Internal helper to retrieve document.

        Args:
            document_id: Document ID

        Returns:
            Document instance

        Raises:
            ValueError: If document not found
        """
        document = self.documents.get(document_id)
        if not document:
            raise ValueError(f"Document not found: {document_id}")
        return document

    def _audit_log(
        self,
        event_type: str,
        document_id: str,
        actor: str,
        details: Dict[str, Any],
    ) -> None:
        """
        Log audit event for document operations.

        Args:
            event_type: Type of event
            document_id: Document ID
            actor: User/system ID triggering event
            details: Additional event details
        """
        if self.audit_logger:
            try:
                self.audit_logger.log({
                    'event_type': event_type,
                    'document_id': document_id,
                    'actor': actor,
                    'timestamp': datetime.utcnow().isoformat(),
                    'details': details,
                })
            except Exception as e:
                logger.warning(f"Failed to write audit log: {e}")
        else:
            logger.debug(f"Audit: {event_type} on {document_id} by {actor}")
