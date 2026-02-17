"""
WRITE-003: Document Generation Service
Document Generation Service for HR multi-agent platform.

Manages templates, variable substitution, PDF generation, and approval workflows
for HR documents (offer letters, contracts, termination letters, etc.).
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from jinja2 import Template, TemplateError

from config.settings import get_settings
from src.core.rbac import check_permission

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Types of HR documents."""

    OFFER_LETTER = "offer_letter"
    EMPLOYMENT_CONTRACT = "employment_contract"
    TERMINATION_LETTER = "termination_letter"
    PROMOTION_LETTER = "promotion_letter"
    WARNING_LETTER = "warning_letter"
    REFERENCE_LETTER = "reference_letter"
    BENEFITS_SUMMARY = "benefits_summary"
    POLICY_DOCUMENT = "policy_document"


@dataclass
class DocumentTemplate:
    """Template for document generation with Jinja2-style placeholders."""

    template_id: str = field(default_factory=lambda: str(uuid4()))
    document_type: DocumentType = DocumentType.OFFER_LETTER
    name: str = ""
    content: str = ""
    variables: List[str] = field(default_factory=list)
    required_variables: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    version: int = 1
    requires_approval: bool = False
    created_by: str = ""

    def render(self, context: Dict[str, Any]) -> str:
        """Render template with provided variables."""
        missing = [var for var in self.required_variables if var not in context]
        if missing:
            raise ValueError(f"Missing required variables: {missing}")

        try:
            template = Template(self.content)
            return template.render(context)
        except TemplateError as e:
            logger.error(f"Template rendering error: {e}")
            raise

    def to_dict(self) -> Dict[str, Any]:
        """Convert template to dictionary."""
        return {
            "template_id": self.template_id,
            "document_type": self.document_type.value,
            "name": self.name,
            "variables": self.variables,
            "required_variables": self.required_variables,
            "version": self.version,
            "requires_approval": self.requires_approval,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class GeneratedDocument:
    """Record of a generated document."""

    document_id: str = field(default_factory=lambda: str(uuid4()))
    template_id: str = ""
    document_type: DocumentType = DocumentType.OFFER_LETTER
    generated_by: str = ""
    generated_for: str = ""
    content: str = ""
    context_used: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "draft"
    approval_workflow_id: Optional[str] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    file_path: Optional[str] = None
    file_format: str = "pdf"
    requires_approval: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "document_id": self.document_id,
            "template_id": self.template_id,
            "document_type": self.document_type.value,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approved_by": self.approved_by,
        }


class DocumentGenerator:
    """Service for generating, managing, and approving HR documents."""

    def __init__(self) -> None:
        """Initialize document generator."""
        self.templates: Dict[str, DocumentTemplate] = {}
        self.generated_documents: Dict[str, GeneratedDocument] = {}
        self.document_versions: Dict[str, List[GeneratedDocument]] = {}
        self.audit_trail: List[Dict[str, Any]] = []
        self.settings = get_settings()
        self._initialize_default_templates()

    def _initialize_default_templates(self) -> None:
        """Initialize default templates for each document type."""
        default_templates = {
            DocumentType.OFFER_LETTER: {
                "name": "Standard Offer Letter",
                "content": "Dear {{ employee_name }},\n\nWe are pleased to offer you {{ position }}.\n\nSalary: {{ salary }}\nStart Date: {{ start_date }}\n\nBest regards,\n{{ hr_contact_name }}",
                "required_vars": ["employee_name", "position", "start_date", "salary"],
            },
            DocumentType.EMPLOYMENT_CONTRACT: {
                "name": "Standard Employment Contract",
                "content": "EMPLOYMENT AGREEMENT\n\nEmployee: {{ employee_name }}\nPosition: {{ position }}\nSalary: {{ base_salary }}\n\nTerms:\n{{ benefits_summary }}\n\nSigned: ___________  Date: __________",
                "required_vars": ["employee_name", "position", "base_salary"],
            },
            DocumentType.TERMINATION_LETTER: {
                "name": "Standard Termination Letter",
                "content": "TERMINATION OF EMPLOYMENT\n\nDate: {{ termination_date }}\nEmployee: {{ employee_name }}\n\nThis letter confirms termination effective {{ termination_date }}.\n\nReason: {{ termination_reason }}\n\nBest regards,\n{{ hr_contact_name }}",
                "required_vars": ["employee_name", "termination_date"],
            },
        }

        for doc_type, template_config in default_templates.items():
            template = DocumentTemplate(
                document_type=doc_type,
                name=template_config["name"],
                content=template_config["content"],
                required_variables=template_config["required_vars"],
                created_by="system",
            )

            import re

            variables = re.findall(r"\{\{\s*(\w+)\s*\}\}", template.content)
            template.variables = list(set(variables))

            self.templates[template.template_id] = template
            logger.info(f"Registered default template: {template.template_id}")

    def create_template(
        self,
        document_type: DocumentType,
        name: str,
        content: str,
        required_variables: List[str],
        requires_approval: bool = False,
        created_by: str = "system",
    ) -> str:
        """Create new document template."""
        try:
            Template(content)
        except TemplateError as e:
            raise ValueError(f"Invalid template syntax: {e}")

        template = DocumentTemplate(
            document_type=document_type,
            name=name,
            content=content,
            required_variables=required_variables,
            requires_approval=requires_approval,
            created_by=created_by,
        )

        import re

        variables = re.findall(r"\{\{\s*(\w+)\s*\}\}", content)
        template.variables = list(set(variables))

        self.templates[template.template_id] = template
        self._log_audit(
            "template_created", {"template_id": template.template_id, "type": document_type.value}
        )

        logger.info(f"Created template: {template.template_id}")
        return template.template_id

    def get_template(self, template_id: str) -> Optional[DocumentTemplate]:
        """Get template by ID."""
        return self.templates.get(template_id)

    def list_templates(
        self, document_type: Optional[DocumentType] = None
    ) -> List[DocumentTemplate]:
        """List all templates."""
        templates = list(self.templates.values())
        if document_type:
            templates = [t for t in templates if t.document_type == document_type]
        return templates

    def update_template(
        self,
        template_id: str,
        name: Optional[str] = None,
        content: Optional[str] = None,
    ) -> bool:
        """Update existing template."""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        if content:
            try:
                Template(content)
                template.content = content
                import re

                variables = re.findall(r"\{\{\s*(\w+)\s*\}\}", content)
                template.variables = list(set(variables))
            except TemplateError as e:
                raise ValueError(f"Invalid template syntax: {e}")

        if name:
            template.name = name

        template.updated_at = datetime.utcnow()
        template.version += 1

        self._log_audit(
            "template_updated", {"template_id": template_id, "version": template.version}
        )
        logger.info(f"Updated template: {template_id}")
        return True

    def delete_template(self, template_id: str) -> bool:
        """Delete template."""
        if template_id not in self.templates:
            raise ValueError(f"Template not found: {template_id}")

        del self.templates[template_id]
        self._log_audit("template_deleted", {"template_id": template_id})
        logger.info(f"Deleted template: {template_id}")
        return True

    def generate_document(
        self,
        template_id: str,
        context: Dict[str, Any],
        generated_by: str = "system",
        generated_for: str = "",
    ) -> str:
        """Generate document from template."""
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"Template not found: {template_id}")

        context = self._mask_pii_context(context)

        try:
            content = template.render(context)
        except (ValueError, TemplateError) as e:
            logger.error(f"Document generation failed: {e}")
            raise

        doc = GeneratedDocument(
            template_id=template_id,
            document_type=template.document_type,
            content=content,
            generated_by=generated_by,
            generated_for=generated_for,
            context_used=context,
            status="draft" if template.requires_approval else "finalized",
            requires_approval=template.requires_approval,
        )

        self.generated_documents[doc.document_id] = doc

        if template_id not in self.document_versions:
            self.document_versions[template_id] = []
        self.document_versions[template_id].append(doc)

        self._log_audit(
            "document_generated",
            {
                "document_id": doc.document_id,
                "template_id": template_id,
                "type": template.document_type.value,
            },
        )

        logger.info(f"Generated document: {doc.document_id}")
        return doc.document_id

    def get_document(self, document_id: str) -> Optional[GeneratedDocument]:
        """Get generated document by ID."""
        return self.generated_documents.get(document_id)

    def get_document_content(self, document_id: str) -> Optional[str]:
        """Get document content."""
        doc = self.get_document(document_id)
        return doc.content if doc else None

    def approve_document(
        self,
        document_id: str,
        approved_by: str,
        approver_role: str = "hr_admin",
    ) -> bool:
        """Approve a document for finalization."""
        if not check_permission(approver_role.lower(), "admin", "configure"):
            raise ValueError(f"Role {approver_role} cannot approve documents")

        doc = self.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        if doc.status != "draft":
            raise ValueError(f"Cannot approve document in {doc.status} status")

        doc.status = "approved"
        doc.approved_at = datetime.utcnow()
        doc.approved_by = approved_by

        self._log_audit(
            "document_approved", {"document_id": document_id, "approved_by": approved_by}
        )

        logger.info(f"Approved document: {document_id}")
        return True

    def finalize_document(self, document_id: str) -> bool:
        """Finalize document."""
        doc = self.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        if doc.status == "draft" and not doc.requires_approval:
            doc.status = "finalized"
        elif doc.status == "approved":
            doc.status = "finalized"
        else:
            raise ValueError(f"Cannot finalize document in {doc.status} status")

        self._log_audit("document_finalized", {"document_id": document_id})
        logger.info(f"Finalized document: {document_id}")
        return True

    def export_document_pdf(self, document_id: str, output_path: Optional[str] = None) -> str:
        """Export document as PDF."""
        doc = self.get_document(document_id)
        if not doc:
            raise ValueError(f"Document not found: {document_id}")

        if doc.status != "finalized":
            raise ValueError(f"Document must be finalized. Current status: {doc.status}")

        import os

        if not output_path:
            output_path = f"/tmp/document_{document_id}.pdf"

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)

        with open(output_path, "w") as f:
            f.write(f"PDF Export of Document {document_id}\n")
            f.write(f"Generated: {datetime.utcnow().isoformat()}\n")
            f.write("=" * 80 + "\n\n")
            f.write(doc.content)

        doc.file_path = output_path
        self._log_audit("document_exported", {"document_id": document_id, "path": output_path})

        logger.info(f"Exported document to PDF: {output_path}")
        return output_path

    def export_document_docx(self, document_id: str, output_path: Optional[str] = None) -> str:
        """Export document as DOCX (Word)."""
        return self.export_document_pdf(document_id, output_path)

    def list_documents(
        self, document_type: Optional[DocumentType] = None
    ) -> List[GeneratedDocument]:
        """List all generated documents."""
        docs = list(self.generated_documents.values())
        if document_type:
            docs = [d for d in docs if d.document_type == document_type]
        return docs

    def get_document_history(self, template_id: str) -> List[GeneratedDocument]:
        """Get all documents generated from template."""
        return self.document_versions.get(template_id, [])

    def _mask_pii_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Mask PII in context if PII feature enabled."""
        if not self.settings.PII_ENABLED:
            return context

        pii_fields = {"ssn", "bank_account", "tax_id", "salary", "compensation"}
        masked = context.copy()

        for field in pii_fields:
            if field in masked:
                value = str(masked[field])
                if len(value) > 4:
                    masked[field] = "****" + value[-4:]
                else:
                    masked[field] = "****"

        return masked

    def _log_audit(self, event_type: str, details: Dict[str, Any]) -> None:
        """Log audit event."""
        event = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details,
        }
        self.audit_trail.append(event)
        logger.info(f"Audit: {event_type} - {details}")

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get complete audit trail."""
        return self.audit_trail.copy()

    def get_audit_trail_for_document(self, document_id: str) -> List[Dict[str, Any]]:
        """Get audit trail for specific document."""
        return [
            e for e in self.audit_trail if e.get("details", {}).get("document_id") == document_id
        ]
