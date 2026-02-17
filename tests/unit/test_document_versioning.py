"""
Unit tests for document_versioning.py module.

Tests cover DocumentVersioningService and all related models with comprehensive
coverage of document lifecycle, versioning, approval workflows, and content comparison.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import uuid

from src.core.document_versioning import (
    DocumentStatus,
    DocumentVersion,
    Document,
    DocumentConfig,
    DocumentVersioningService,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def doc_config():
    """Create a DocumentConfig for testing."""
    return DocumentConfig(max_versions_retained=50, require_approval=True, auto_archive_days=365)


@pytest.fixture
def doc_service(doc_config):
    """Create a DocumentVersioningService instance."""
    return DocumentVersioningService(doc_config)


@pytest.fixture
def sample_document(doc_service):
    """Create a sample document."""
    return doc_service.create_document(
        title="Company Leave Policy",
        content="Employee leave policies...",
        author="admin",
        category="pto",
        tags=["leave", "policy"],
    )


# ============================================================================
# Test DocumentStatus Enum
# ============================================================================


class TestDocumentStatus:
    """Tests for DocumentStatus enum."""

    def test_status_draft(self):
        """Test DRAFT status exists."""
        assert DocumentStatus.DRAFT == "draft"

    def test_status_pending_review(self):
        """Test PENDING_REVIEW status exists."""
        assert DocumentStatus.PENDING_REVIEW == "pending_review"

    def test_status_published(self):
        """Test PUBLISHED status exists."""
        assert DocumentStatus.PUBLISHED == "published"

    def test_status_enum_count(self):
        """Test DocumentStatus enum has 6 values."""
        assert len(DocumentStatus) == 6

    def test_status_string_representation(self):
        """Test status string representation."""
        assert str(DocumentStatus.DRAFT.value) == "draft"


# ============================================================================
# Test DocumentVersion Model
# ============================================================================


class TestDocumentVersion:
    """Tests for DocumentVersion model."""

    def test_version_defaults(self):
        """Test DocumentVersion default values."""
        version = DocumentVersion(
            document_id="doc-123", version_number="1.0", content="Test content", author="author1"
        )
        assert version.status == DocumentStatus.DRAFT
        assert version.change_summary == ""
        assert version.approved_by is None

    def test_version_custom_values(self):
        """Test DocumentVersion with custom values."""
        version = DocumentVersion(
            document_id="doc-123",
            version_number="1.5",
            content="Updated content",
            author="author2",
            status=DocumentStatus.PENDING_REVIEW,
            change_summary="Fixed typos",
        )
        assert version.version_number == "1.5"
        assert version.change_summary == "Fixed typos"

    def test_version_uuid(self):
        """Test DocumentVersion generates unique version_id."""
        v1 = DocumentVersion(
            document_id="doc-123", version_number="1.0", content="Content 1", author="author1"
        )
        v2 = DocumentVersion(
            document_id="doc-123", version_number="1.0", content="Content 2", author="author1"
        )
        assert v1.version_id != v2.version_id
        assert len(v1.version_id) > 0

    def test_version_number_format(self):
        """Test DocumentVersion version number format."""
        version = DocumentVersion(
            document_id="doc-123", version_number="2.1", content="Content", author="author1"
        )
        assert version.version_number == "2.1"


# ============================================================================
# Test Document Model
# ============================================================================


class TestDocument:
    """Tests for Document model."""

    def test_document_defaults(self):
        """Test Document default values."""
        doc = Document(title="Test Document", category="compensation", owner="owner1")
        assert doc.current_version == "1.0"
        assert isinstance(doc.versions, list)
        assert doc.tags == []

    def test_document_custom_values(self):
        """Test Document with custom values."""
        doc = Document(
            title="Policy Document",
            category="pto",
            owner="owner2",
            current_version="2.0",
            tags=["policy", "urgent"],
        )
        assert doc.category == "pto"
        assert len(doc.tags) == 2

    def test_document_uuid(self):
        """Test Document generates unique document_id."""
        doc1 = Document(title="Doc 1", category="compensation", owner="owner1")
        doc2 = Document(title="Doc 2", category="pto", owner="owner2")
        assert doc1.document_id != doc2.document_id
        assert len(doc1.document_id) > 0

    def test_document_tags_list(self):
        """Test Document tags is a list."""
        doc = Document(
            title="Document", category="benefits", owner="owner1", tags=["important", "review"]
        )
        assert isinstance(doc.tags, list)
        assert "important" in doc.tags


# ============================================================================
# Test DocumentConfig Model
# ============================================================================


class TestDocumentConfig:
    """Tests for DocumentConfig model."""

    def test_config_defaults(self):
        """Test DocumentConfig default values."""
        config = DocumentConfig()
        assert config.max_versions_retained == 50
        assert config.require_approval is True
        assert config.auto_archive_days == 365

    def test_config_custom_values(self):
        """Test DocumentConfig with custom values."""
        config = DocumentConfig(
            max_versions_retained=100, require_approval=False, auto_archive_days=180
        )
        assert config.max_versions_retained == 100
        assert config.require_approval is False

    def test_config_max_versions(self):
        """Test DocumentConfig max_versions_retained."""
        config = DocumentConfig(max_versions_retained=25)
        assert config.max_versions_retained == 25

    def test_config_require_approval(self):
        """Test DocumentConfig require_approval setting."""
        config = DocumentConfig(require_approval=True)
        assert config.require_approval is True


# ============================================================================
# Test DocumentVersioningService Initialization
# ============================================================================


class TestDocumentVersioningServiceInit:
    """Tests for DocumentVersioningService initialization."""

    def test_service_creates_with_config(self, doc_config):
        """Test service initializes with config."""
        service = DocumentVersioningService(doc_config)
        assert service is not None

    def test_service_stores_config(self, doc_config):
        """Test service stores configuration."""
        service = DocumentVersioningService(doc_config)
        assert service.config == doc_config

    def test_service_empty_state(self, doc_config):
        """Test service starts with empty state."""
        service = DocumentVersioningService(doc_config)
        assert len(service.documents) == 0
        assert len(service.versions) == 0


# ============================================================================
# Test Create Document
# ============================================================================


class TestCreateDocument:
    """Tests for DocumentVersioningService.create_document method."""

    def test_creates_document(self, doc_service):
        """Test create_document creates a document."""
        doc = doc_service.create_document(
            title="Policy", content="Content", author="author1", category="compensation"
        )
        assert isinstance(doc, Document)
        assert doc.title == "Policy"

    def test_assigns_uuid(self, doc_service):
        """Test create_document assigns document_id."""
        doc = doc_service.create_document(
            title="Test", content="Content", author="author1", category="pto"
        )
        assert len(doc.document_id) > 0

    def test_first_version(self, doc_service):
        """Test create_document creates first version."""
        doc = doc_service.create_document(
            title="Document", content="Initial content", author="author1", category="benefits"
        )
        assert len(doc.versions) == 1
        assert doc.versions[0].version_number == "1.0"

    def test_sets_status(self, doc_service):
        """Test create_document sets status to DRAFT."""
        doc = doc_service.create_document(
            title="Document", content="Content", author="author1", category="compensation"
        )
        assert doc.versions[0].status == DocumentStatus.DRAFT


# ============================================================================
# Test Create Version
# ============================================================================


class TestCreateVersion:
    """Tests for DocumentVersioningService.create_version method."""

    def test_increments_version(self, sample_document, doc_service):
        """Test create_version increments version number."""
        version = doc_service.create_version(
            document_id=sample_document.document_id,
            content="Updated content",
            author="author2",
            change_summary="Updated section",
        )
        assert version.version_number == "1.1"

    def test_stores_content(self, sample_document, doc_service):
        """Test create_version stores new content."""
        new_content = "Completely new content"
        version = doc_service.create_version(
            document_id=sample_document.document_id,
            content=new_content,
            author="author2",
            change_summary="Full rewrite",
        )
        assert version.content == new_content

    def test_requires_document(self, doc_service):
        """Test create_version requires existing document."""
        with pytest.raises(ValueError):
            doc_service.create_version(
                document_id="nonexistent",
                content="Content",
                author="author1",
                change_summary="Update",
            )

    def test_change_summary(self, sample_document, doc_service):
        """Test create_version stores change summary."""
        summary = "Major content update"
        version = doc_service.create_version(
            document_id=sample_document.document_id,
            content="New content",
            author="author2",
            change_summary=summary,
        )
        assert version.change_summary == summary


# ============================================================================
# Test Submit For Review
# ============================================================================


class TestSubmitForReview:
    """Tests for DocumentVersioningService.submit_for_review method."""

    def test_updates_status(self, sample_document, doc_service):
        """Test submit_for_review updates status."""
        version = doc_service.submit_for_review(
            document_id=sample_document.document_id, version_number="1.0"
        )
        assert version.status == DocumentStatus.PENDING_REVIEW

    def test_requires_document(self, doc_service):
        """Test submit_for_review requires existing document."""
        with pytest.raises(ValueError):
            doc_service.submit_for_review(document_id="nonexistent", version_number="1.0")

    def test_requires_version(self, sample_document, doc_service):
        """Test submit_for_review requires existing version."""
        with pytest.raises(ValueError):
            doc_service.submit_for_review(
                document_id=sample_document.document_id, version_number="99.0"
            )


# ============================================================================
# Test Approve Version
# ============================================================================


class TestApproveVersion:
    """Tests for DocumentVersioningService.approve_version method."""

    def test_sets_approved(self, sample_document, doc_service):
        """Test approve_version sets approved status."""
        doc_service.submit_for_review(document_id=sample_document.document_id, version_number="1.0")
        version = doc_service.approve_version(
            document_id=sample_document.document_id, version_number="1.0", approver="approver1"
        )
        assert version.status == DocumentStatus.APPROVED

    def test_records_approver(self, sample_document, doc_service):
        """Test approve_version records approver ID."""
        doc_service.submit_for_review(document_id=sample_document.document_id, version_number="1.0")
        version = doc_service.approve_version(
            document_id=sample_document.document_id, version_number="1.0", approver="reviewer123"
        )
        assert version.approved_by == "reviewer123"

    def test_requires_pending_review(self, sample_document, doc_service):
        """Test approve_version requires PENDING_REVIEW status."""
        with pytest.raises(ValueError):
            doc_service.approve_version(
                document_id=sample_document.document_id, version_number="1.0", approver="approver1"
            )


# ============================================================================
# Test Publish Version
# ============================================================================


class TestPublishVersion:
    """Tests for DocumentVersioningService.publish_version method."""

    def test_sets_published(self, sample_document, doc_service):
        """Test publish_version sets published status."""
        doc_service.submit_for_review(document_id=sample_document.document_id, version_number="1.0")
        doc_service.approve_version(
            document_id=sample_document.document_id, version_number="1.0", approver="approver1"
        )
        version = doc_service.publish_version(
            document_id=sample_document.document_id, version_number="1.0"
        )
        assert version.status == DocumentStatus.PUBLISHED

    def test_requires_approval(self, sample_document, doc_service):
        """Test publish_version requires approval."""
        with pytest.raises(ValueError, match="approved"):
            doc_service.publish_version(
                document_id=sample_document.document_id, version_number="1.0"
            )

    def test_updates_document(self, sample_document, doc_service):
        """Test publish_version updates document current version."""
        doc_service.submit_for_review(document_id=sample_document.document_id, version_number="1.0")
        doc_service.approve_version(
            document_id=sample_document.document_id, version_number="1.0", approver="approver1"
        )
        doc_service.publish_version(document_id=sample_document.document_id, version_number="1.0")
        doc = doc_service.get_document(sample_document.document_id)
        assert doc.current_version == "1.0"


# ============================================================================
# Test Archive Document
# ============================================================================


class TestArchiveDocument:
    """Tests for DocumentVersioningService.archive_document method."""

    def test_archives_document(self, sample_document, doc_service):
        """Test archive_document archives the document."""
        archived = doc_service.archive_document(sample_document.document_id)
        assert isinstance(archived, Document)

    def test_updates_status(self, sample_document, doc_service):
        """Test archive_document updates status to archived."""
        doc_service.archive_document(sample_document.document_id)
        doc = doc_service.get_document(sample_document.document_id)
        assert all(v.status == DocumentStatus.ARCHIVED for v in doc.versions)

    def test_returns_document(self, sample_document, doc_service):
        """Test archive_document returns updated document."""
        result = doc_service.archive_document(sample_document.document_id)
        assert result.document_id == sample_document.document_id


# ============================================================================
# Test Compare Versions
# ============================================================================


class TestCompareVersions:
    """Tests for DocumentVersioningService.compare_versions method."""

    def test_returns_diff(self, sample_document, doc_service):
        """Test compare_versions returns diff information."""
        doc_service.create_version(
            document_id=sample_document.document_id,
            content="Modified content",
            author="author2",
            change_summary="Changed",
        )
        diff = doc_service.compare_versions(
            document_id=sample_document.document_id, version_a="1.0", version_b="1.1"
        )
        assert isinstance(diff, dict)
        assert "diff" in diff

    def test_same_content(self, sample_document, doc_service):
        """Test compare_versions with identical content."""
        v1 = sample_document.versions[0]
        doc_service.create_version(
            document_id=sample_document.document_id,
            content=v1.content,
            author="author2",
            change_summary="No changes",
        )
        diff = doc_service.compare_versions(
            document_id=sample_document.document_id, version_a="1.0", version_b="1.1"
        )
        assert diff["differences_found"] is False

    def test_version_not_found(self, sample_document, doc_service):
        """Test compare_versions with missing version."""
        with pytest.raises(ValueError):
            doc_service.compare_versions(
                document_id=sample_document.document_id, version_a="1.0", version_b="99.0"
            )


# ============================================================================
# Test Search Documents
# ============================================================================


class TestSearchDocuments:
    """Tests for DocumentVersioningService.search_documents method."""

    def test_finds_by_query(self, doc_service):
        """Test search_documents finds documents by query."""
        doc_service.create_document(
            title="Leave Policy", content="Leave information", author="admin", category="pto"
        )
        results = doc_service.search_documents(query="Leave")
        assert len(results) > 0

    def test_finds_by_category(self, doc_service):
        """Test search_documents finds by category."""
        doc_service.create_document(
            title="Compensation Guide",
            content="Salary information",
            author="admin",
            category="compensation",
        )
        results = doc_service.search_documents(category="compensation")
        assert len(results) > 0
        assert all(d.category == "compensation" for d in results)

    def test_finds_by_tags(self, doc_service):
        """Test search_documents finds by tags."""
        doc_service.create_document(
            title="Document",
            content="Content",
            author="admin",
            category="benefits",
            tags=["urgent", "review"],
        )
        results = doc_service.search_documents(tags=["urgent"])
        assert len(results) > 0


# ============================================================================
# Additional Integration Tests
# ============================================================================


class TestDocumentLifecycle:
    """Integration tests for complete document lifecycle."""

    def test_full_workflow(self, doc_service):
        """Test complete document lifecycle workflow."""
        # Create document
        doc = doc_service.create_document(
            title="HR Policy", content="Initial content", author="author1", category="hr_policies"
        )
        assert doc.versions[0].status == DocumentStatus.DRAFT

        # Submit for review
        doc_service.submit_for_review(doc.document_id, "1.0")
        version = doc_service.get_version(doc.document_id, "1.0")
        assert version.status == DocumentStatus.PENDING_REVIEW

        # Approve
        doc_service.approve_version(doc.document_id, "1.0", "approver1")
        version = doc_service.get_version(doc.document_id, "1.0")
        assert version.status == DocumentStatus.APPROVED

        # Publish
        doc_service.publish_version(doc.document_id, "1.0")
        version = doc_service.get_version(doc.document_id, "1.0")
        assert version.status == DocumentStatus.PUBLISHED

    def test_multiple_versions(self, doc_service):
        """Test creating and managing multiple versions."""
        doc = doc_service.create_document(
            title="Document", content="Version 1", author="author1", category="compensation"
        )

        doc_service.create_version(
            document_id=doc.document_id,
            content="Version 2",
            author="author2",
            change_summary="Update",
        )

        doc = doc_service.get_document(doc.document_id)
        assert len(doc.versions) == 2
        assert doc.versions[1].version_number == "1.1"
