"""Document repository for document templates and generated documents."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base, TimestampMixin
from src.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class DocumentTemplateModel(Base, TimestampMixin):
    """
    SQLAlchemy model for document templates.

    Stores reusable document templates with variable placeholders.

    Attributes:
        id: Primary key
        name: Template name
        document_type: Type of document (offer_letter/termination/etc)
        content_template: Template content with variable placeholders
        required_variables_json: List of required variables
        version: Template version number
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    content_template: Mapped[str] = mapped_column(nullable=False)
    required_variables_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    version: Mapped[int] = mapped_column(default=1, nullable=False)

    def __repr__(self) -> str:
        return f"<DocumentTemplateModel(id={self.id}, name={self.name}, type={self.document_type})>"


class GeneratedDocumentModel(Base, TimestampMixin):
    """
    SQLAlchemy model for generated documents.

    Stores documents generated from templates with approval tracking.

    Attributes:
        id: Primary key
        template_id: Foreign key to DocumentTemplateModel
        generated_by: Employee ID who generated document
        status: Document status (draft/pending_approval/approved/rejected)
        content: Final generated content
        variables_json: Variables used for generation
        approved_by: Employee ID who approved (if approved)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """

    __tablename__ = "generated_documents"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("document_templates.id"), nullable=False)
    generated_by: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    variables_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), nullable=True)

    def __repr__(self) -> str:
        return f"<GeneratedDocumentModel(id={self.id}, template_id={self.template_id}, status={self.status})>"


class DocumentTemplateRepository(BaseRepository[DocumentTemplateModel]):
    """
    Repository for document template management.

    Handles storage and retrieval of reusable document templates.
    """

    def __init__(self) -> None:
        """Initialize document template repository."""
        super().__init__(DocumentTemplateModel)

    def get_template(self, template_id: int) -> Optional[DocumentTemplateModel]:
        """
        Get template by ID.

        Args:
            template_id: Template ID

        Returns:
            DocumentTemplateModel or None if not found
        """
        return self.get(template_id)

    def list_templates(self, document_type: Optional[str] = None) -> List[DocumentTemplateModel]:
        """
        List templates with optional type filter.

        Args:
            document_type: Filter by document type

        Returns:
            List of DocumentTemplateModel instances
        """
        filters = {}
        if document_type:
            filters["document_type"] = document_type
        return self.list(filters)

    def get_by_name(self, name: str) -> Optional[DocumentTemplateModel]:
        """
        Get template by name.

        Args:
            name: Template name

        Returns:
            DocumentTemplateModel or None if not found
        """
        try:
            with self._get_session() as session:
                stmt = select(DocumentTemplateModel).where(DocumentTemplateModel.name == name)
                return session.execute(stmt).scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting template by name: {str(e)}")
            return None

    def create_template(
        self,
        name: str,
        document_type: str,
        content_template: str,
        required_variables: Optional[List[str]] = None,
    ) -> Optional[DocumentTemplateModel]:
        """
        Create new document template.

        Args:
            name: Template name
            document_type: Type of document
            content_template: Template content
            required_variables: List of required variables

        Returns:
            Created DocumentTemplateModel or None on error
        """
        try:
            data = {
                "name": name,
                "document_type": document_type,
                "content_template": content_template,
                "required_variables_json": {"variables": required_variables or []},
            }
            template = self.create(data)
            if template:
                logger.info(f"Created template: id={template.id}, name={name}")
            return template
        except Exception as e:
            logger.error(f"Error creating template: {str(e)}")
            return None


class GeneratedDocumentRepository(BaseRepository[GeneratedDocumentModel]):
    """
    Repository for generated document persistence.

    Handles creation, tracking, and approval of generated documents.
    """

    def __init__(self) -> None:
        """Initialize generated document repository."""
        super().__init__(GeneratedDocumentModel)

    def create_document(
        self,
        template_id: int,
        generated_by: int,
        content: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Optional[GeneratedDocumentModel]:
        """
        Create new generated document.

        Args:
            template_id: Template ID
            generated_by: Employee ID of generator
            content: Generated document content
            variables: Variables used for generation

        Returns:
            Created GeneratedDocumentModel or None on error
        """
        try:
            data = {
                "template_id": template_id,
                "generated_by": generated_by,
                "content": content,
                "variables_json": variables or {},
                "status": "draft",
            }
            document = self.create(data)
            if document:
                logger.info(f"Created document: id={document.id}, template={template_id}")
            return document
        except Exception as e:
            logger.error(f"Error creating document: {str(e)}")
            return None

    def update_status(
        self,
        document_id: int,
        status: str,
        approved_by: Optional[int] = None,
    ) -> Optional[GeneratedDocumentModel]:
        """
        Update document status.

        Args:
            document_id: Document ID
            status: New status
            approved_by: Employee ID who approved (if applicable)

        Returns:
            Updated GeneratedDocumentModel or None on error
        """
        try:
            data = {"status": status}
            if approved_by:
                data["approved_by"] = approved_by

            document = self.update(document_id, data)
            if document:
                logger.info(f"Updated document {document_id} status to {status}")
            return document
        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")
            return None

    def get_documents_by_template(self, template_id: int) -> List[GeneratedDocumentModel]:
        """
        Get all documents generated from specific template.

        Args:
            template_id: Template ID

        Returns:
            List of GeneratedDocumentModel instances
        """
        return self.list({"template_id": template_id})

    def get_documents_by_generator(self, generated_by: int) -> List[GeneratedDocumentModel]:
        """
        Get all documents generated by specific user.

        Args:
            generated_by: Employee ID of generator

        Returns:
            List of GeneratedDocumentModel instances
        """
        return self.list({"generated_by": generated_by})

    def get_pending_approval(self) -> List[GeneratedDocumentModel]:
        """
        Get all documents pending approval.

        Returns:
            List of pending GeneratedDocumentModel instances
        """
        return self.list({"status": "pending_approval"})

    def approve_document(
        self,
        document_id: int,
        approver_id: int,
    ) -> Optional[GeneratedDocumentModel]:
        """
        Approve a document.

        Args:
            document_id: Document ID
            approver_id: Employee ID of approver

        Returns:
            Updated GeneratedDocumentModel or None on error
        """
        return self.update_status(document_id, "approved", approved_by=approver_id)

    def reject_document(self, document_id: int) -> Optional[GeneratedDocumentModel]:
        """
        Reject a document.

        Args:
            document_id: Document ID

        Returns:
            Updated GeneratedDocumentModel or None on error
        """
        return self.update_status(document_id, "rejected")

    def get_audit_trail(self, document_id: int) -> Dict[str, Any]:
        """
        Get audit trail for document.

        Args:
            document_id: Document ID

        Returns:
            Dictionary with document history and audit information
        """
        try:
            document = self.get(document_id)
            if not document:
                return {"error": f"Document {document_id} not found"}

            return {
                "document_id": document_id,
                "template_id": document.template_id,
                "generated_by": document.generated_by,
                "generated_at": document.created_at.isoformat() if document.created_at else None,
                "status": document.status,
                "status_updated_at": document.updated_at.isoformat() if document.updated_at else None,
                "approved_by": document.approved_by,
                "variables_used": document.variables_json,
            }
        except Exception as e:
            logger.error(f"Error getting audit trail: {str(e)}")
            return {"error": str(e)}
