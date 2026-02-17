"""Tests for document generation service."""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch
from src.core.document_generator import (
    DocumentGenerator,
    DocumentTemplate,
    GeneratedDocument,
    DocumentType,
)


@pytest.fixture
def doc_generator():
    """Create document generator instance."""
    return DocumentGenerator()


class TestTemplateManagement:
    """Tests for CRUD operations on document templates."""

    def test_create_template(self, doc_generator):
        """create_template creates new template."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Custom Offer Letter",
            content="Dear {{ employee_name }}, We offer you position {{ position }}",
            required_variables=["employee_name", "position"],
        )

        assert template_id in doc_generator.templates
        template = doc_generator.templates[template_id]
        assert template.name == "Custom Offer Letter"
        assert template.document_type == DocumentType.OFFER_LETTER

    def test_create_template_invalid_syntax_raises(self, doc_generator):
        """create_template raises on invalid Jinja2 syntax."""
        with pytest.raises(ValueError, match="Invalid template syntax"):
            doc_generator.create_template(
                document_type=DocumentType.OFFER_LETTER,
                name="Bad Template",
                content="{{ unclosed_var",
                required_variables=[],
            )

    def test_get_template(self, doc_generator):
        """get_template retrieves template by ID."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Test Template",
            content="Content: {{ var1 }}",
            required_variables=["var1"],
        )

        template = doc_generator.get_template(template_id)

        assert template is not None
        assert template.template_id == template_id
        assert template.name == "Test Template"

    def test_get_template_not_found(self, doc_generator):
        """get_template returns None for nonexistent template."""
        template = doc_generator.get_template("nonexistent")

        assert template is None

    def test_list_templates(self, doc_generator):
        """list_templates returns all templates."""
        # Should have default templates
        all_templates = doc_generator.list_templates()

        assert len(all_templates) > 0
        types = [t.document_type for t in all_templates]
        assert DocumentType.OFFER_LETTER in types

    def test_list_templates_filtered_by_type(self, doc_generator):
        """list_templates can filter by document type."""
        offer_templates = doc_generator.list_templates(DocumentType.OFFER_LETTER)

        assert all(t.document_type == DocumentType.OFFER_LETTER for t in offer_templates)

    def test_update_template(self, doc_generator):
        """update_template modifies template."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.TERMINATION_LETTER,
            name="Original Name",
            content="Original content: {{ reason }}",
            required_variables=["reason"],
        )

        doc_generator.update_template(
            template_id, name="Updated Name", content="Updated content: {{ reason }}"
        )

        template = doc_generator.get_template(template_id)
        assert template.name == "Updated Name"
        assert "Updated content" in template.content
        assert template.version == 2

    def test_update_template_not_found_raises(self, doc_generator):
        """update_template raises for nonexistent template."""
        with pytest.raises(ValueError, match="Template not found"):
            doc_generator.update_template("nonexistent", name="New Name", content="New content")

    def test_delete_template(self, doc_generator):
        """delete_template removes template."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.POLICY_DOCUMENT,
            name="To Delete",
            content="This will be deleted",
            required_variables=[],
        )

        result = doc_generator.delete_template(template_id)

        assert result is True
        assert template_id not in doc_generator.templates

    def test_delete_template_not_found_raises(self, doc_generator):
        """delete_template raises for nonexistent template."""
        with pytest.raises(ValueError, match="Template not found"):
            doc_generator.delete_template("nonexistent")


class TestDocumentGeneration:
    """Tests for generating documents with variable substitution."""

    def test_generate_document(self, doc_generator):
        """generate_document creates document from template."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Test Offer",
            content="Dear {{ employee_name }}, We offer {{ position }} at {{ salary }}.",
            required_variables=["employee_name", "position", "salary"],
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id,
            context={
                "employee_name": "John Doe",
                "position": "Senior Engineer",
                "salary": "$150,000",
            },
            generated_by="admin",
            generated_for="emp-001",
        )

        assert isinstance(doc_id, str)
        assert len(doc_id) > 0
        document = doc_generator.get_document(doc_id)
        assert document is not None
        assert "John Doe" in document.content
        assert "Senior Engineer" in document.content

    def test_generate_document_missing_required_variable(self, doc_generator):
        """generate_document raises on missing required variable."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Test",
            content="Dear {{ employee_name }}, Position: {{ position }}",
            required_variables=["employee_name", "position"],
        )

        with pytest.raises(ValueError, match="Missing required variables"):
            doc_generator.generate_document(
                template_id=template_id, context={"employee_name": "John"}  # Missing position
            )

    def test_generate_document_invalid_template(self, doc_generator):
        """generate_document raises for nonexistent template."""
        with pytest.raises(ValueError, match="Template not found"):
            doc_generator.generate_document(template_id="nonexistent", context={})

    def test_generate_document_status_draft_for_approval(self, doc_generator):
        """generate_document sets status to draft when approval required."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.EMPLOYMENT_CONTRACT,
            name="Contract",
            content="Contract for {{ name }}",
            required_variables=["name"],
            requires_approval=True,
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id, context={"name": "Jane Smith"}
        )

        document = doc_generator.get_document(doc_id)
        assert document.status == "draft"
        assert document.requires_approval is True

    def test_generate_document_status_finalized_without_approval(self, doc_generator):
        """generate_document sets status to finalized when no approval needed."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.POLICY_DOCUMENT,
            name="Policy",
            content="Policy text: {{ policy }}",
            required_variables=["policy"],
            requires_approval=False,
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id, context={"policy": "Code of Conduct"}
        )

        document = doc_generator.get_document(doc_id)
        assert document.status == "finalized"

    def test_get_document(self, doc_generator):
        """get_document retrieves generated document."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Offer",
            content="Offer for {{ person }}",
            required_variables=["person"],
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id, context={"person": "Alice"}
        )

        document = doc_generator.get_document(doc_id)
        assert document is not None
        assert document.document_id == doc_id
        assert "Alice" in document.content

    def test_get_document_content(self, doc_generator):
        """get_document_content retrieves just the content."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.TERMINATION_LETTER,
            name="Termination",
            content="Effective {{ date }}, employment terminated.",
            required_variables=["date"],
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id, context={"date": "2024-02-01"}
        )

        content = doc_generator.get_document_content(doc_id)
        assert content is not None
        assert "2024-02-01" in content

    def test_get_document_not_found(self, doc_generator):
        """get_document returns None for nonexistent document."""
        document = doc_generator.get_document("nonexistent")

        assert document is None


class TestDefaultTemplates:
    """Tests for built-in default templates."""

    def test_default_templates_exist(self, doc_generator):
        """Service initializes with default templates."""
        templates = doc_generator.list_templates()

        types = [t.document_type for t in templates]
        assert DocumentType.OFFER_LETTER in types
        assert DocumentType.EMPLOYMENT_CONTRACT in types
        assert DocumentType.TERMINATION_LETTER in types

    def test_default_offer_letter_template(self, doc_generator):
        """Default offer letter template is valid."""
        offer_templates = doc_generator.list_templates(DocumentType.OFFER_LETTER)

        assert len(offer_templates) > 0
        template = offer_templates[0]
        assert "employee_name" in template.variables
        assert "position" in template.variables

    def test_default_template_can_generate_document(self, doc_generator):
        """Can generate document using default templates."""
        templates = doc_generator.list_templates(DocumentType.OFFER_LETTER)
        template_id = templates[0].template_id

        doc_id = doc_generator.generate_document(
            template_id=template_id,
            context={
                "employee_name": "Bob",
                "position": "Manager",
                "start_date": "2024-03-01",
                "salary": "$120,000",
            },
        )

        document = doc_generator.get_document(doc_id)
        assert document is not None
        assert "Bob" in document.content


class TestVariableValidation:
    """Tests for template variable validation."""

    def test_missing_variables_raises(self, doc_generator):
        """Template with missing variables raises error."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Strict",
            content="Employee: {{ emp_name }}, Salary: {{ salary }}",
            required_variables=["emp_name", "salary"],
        )

        with pytest.raises(ValueError):
            doc_generator.generate_document(
                template_id=template_id, context={"emp_name": "Test"}  # salary missing
            )

    def test_extra_variables_ignored(self, doc_generator):
        """Extra variables in context are ignored."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Simple",
            content="Welcome {{ name }}!",
            required_variables=["name"],
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id,
            context={"name": "Test", "extra1": "value1", "extra2": "value2"},
        )

        document = doc_generator.get_document(doc_id)
        assert document is not None

    def test_variable_extraction_from_template(self, doc_generator):
        """Variables are extracted from template content."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Multi-var",
            content="{{ first }} {{ second }} {{ third }}",
            required_variables=[],
        )

        template = doc_generator.get_template(template_id)
        assert "first" in template.variables
        assert "second" in template.variables
        assert "third" in template.variables


class TestVersionTracking:
    """Tests for template versioning."""

    def test_template_version_increments_on_update(self, doc_generator):
        """Template version increments when updated."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Versioned",
            content="Version 1",
            required_variables=[],
        )

        template = doc_generator.get_template(template_id)
        assert template.version == 1

        doc_generator.update_template(template_id, content="Version 2")
        updated = doc_generator.get_template(template_id)
        assert updated.version == 2

    def test_initial_template_version_is_one(self, doc_generator):
        """New templates start at version 1."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="New",
            content="Content",
            required_variables=[],
        )

        template = doc_generator.get_template(template_id)
        assert template.version == 1


class TestDocumentTypes:
    """Tests for all document type enums."""

    def test_all_document_types_valid(self, doc_generator):
        """All DocumentType enums are valid."""
        doc_types = [
            DocumentType.OFFER_LETTER,
            DocumentType.EMPLOYMENT_CONTRACT,
            DocumentType.TERMINATION_LETTER,
            DocumentType.PROMOTION_LETTER,
            DocumentType.WARNING_LETTER,
            DocumentType.REFERENCE_LETTER,
            DocumentType.BENEFITS_SUMMARY,
            DocumentType.POLICY_DOCUMENT,
        ]

        for doc_type in doc_types:
            template_id = doc_generator.create_template(
                document_type=doc_type,
                name=f"Test {doc_type.value}",
                content="Content",
                required_variables=[],
            )
            template = doc_generator.get_template(template_id)
            assert template.document_type == doc_type


class TestAuditTrail:
    """Tests for generation audit logging."""

    def test_audit_trail_logged_on_generation(self, doc_generator):
        """Document generation is logged in audit trail."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Audited",
            content="Content: {{ test }}",
            required_variables=["test"],
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id, context={"test": "value"}, generated_by="user123"
        )

        audit_trail = doc_generator.get_audit_trail()
        generation_events = [e for e in audit_trail if e["event_type"] == "document_generated"]

        assert len(generation_events) > 0
        latest = generation_events[-1]
        assert latest["details"]["document_id"] == doc_id

    def test_get_audit_trail_for_document(self, doc_generator):
        """Can retrieve audit trail for specific document."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Audit Test",
            content="Content: {{ x }}",
            required_variables=["x"],
        )

        doc_id = doc_generator.generate_document(template_id=template_id, context={"x": "y"})

        audit = doc_generator.get_audit_trail_for_document(doc_id)

        assert len(audit) > 0
        assert all(e.get("details", {}).get("document_id") == doc_id for e in audit)

    def test_audit_trail_on_approval(self, doc_generator):
        """Document approval is logged."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.EMPLOYMENT_CONTRACT,
            name="Contract",
            content="Content: {{ name }}",
            required_variables=["name"],
            requires_approval=True,
        )

        doc_id = doc_generator.generate_document(template_id=template_id, context={"name": "Test"})

        with patch("src.core.document_generator.check_permission", return_value=True):
            doc_generator.approve_document(
                document_id=doc_id, approved_by="approver123", approver_role="hr_admin"
            )

        audit = doc_generator.get_audit_trail_for_document(doc_id)
        approval_events = [e for e in audit if e["event_type"] == "document_approved"]

        assert len(approval_events) > 0

    def test_audit_trail_on_finalization(self, doc_generator):
        """Document finalization is logged."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.EMPLOYMENT_CONTRACT,
            name="Finalize Test",
            content="Content: {{ name }}",
            required_variables=["name"],
            requires_approval=True,  # This will create a draft status
        )

        doc_id = doc_generator.generate_document(template_id=template_id, context={"name": "Test"})

        # First approve it
        with patch("src.core.document_generator.check_permission", return_value=True):
            doc_generator.approve_document(document_id=doc_id, approved_by="approver")

        # Then finalize
        result = doc_generator.finalize_document(doc_id)
        assert result is True

        audit = doc_generator.get_audit_trail_for_document(doc_id)
        finalize_events = [e for e in audit if e["event_type"] == "document_finalized"]

        assert len(finalize_events) > 0


class TestDocumentApproval:
    """Tests for document approval workflow."""

    @patch("src.core.document_generator.check_permission")
    def test_approve_document(self, mock_perm, doc_generator):
        """approve_document changes status to approved."""
        mock_perm.return_value = True

        template_id = doc_generator.create_template(
            document_type=DocumentType.EMPLOYMENT_CONTRACT,
            name="Contract",
            content="Contract",
            required_variables=[],
            requires_approval=True,
        )

        doc_id = doc_generator.generate_document(template_id=template_id, context={})

        result = doc_generator.approve_document(
            document_id=doc_id, approved_by="approver_emp", approver_role="hr_admin"
        )

        assert result is True
        document = doc_generator.get_document(doc_id)
        assert document.status == "approved"
        assert document.approved_by == "approver_emp"
        assert document.approved_at is not None

    @patch("src.core.document_generator.check_permission")
    def test_approve_document_insufficient_permission_raises(self, mock_perm, doc_generator):
        """approve_document raises if user lacks permission."""
        mock_perm.return_value = False

        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Offer",
            content="Offer",
            required_variables=[],
            requires_approval=True,
        )

        doc_id = doc_generator.generate_document(template_id=template_id, context={})

        with pytest.raises(ValueError, match="cannot approve"):
            doc_generator.approve_document(
                document_id=doc_id, approved_by="non_admin", approver_role="employee"
            )

    def test_finalize_document(self, doc_generator):
        """finalize_document sets status to finalized."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.EMPLOYMENT_CONTRACT,
            name="Contract",
            content="Contract: {{ name }}",
            required_variables=["name"],
            requires_approval=True,
        )

        doc_id = doc_generator.generate_document(template_id=template_id, context={"name": "Test"})

        # Approve the document first (moves from draft to approved)
        with patch("src.core.document_generator.check_permission", return_value=True):
            doc_generator.approve_document(document_id=doc_id, approved_by="approver")

        # Now we can finalize
        result = doc_generator.finalize_document(doc_id)

        assert result is True
        document = doc_generator.get_document(doc_id)
        assert document.status == "finalized"

    def test_export_document_pdf(self, doc_generator):
        """export_document_pdf exports finalized document."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Offer",
            content="Offer content: {{ title }}",
            required_variables=["title"],
        )

        doc_id = doc_generator.generate_document(
            template_id=template_id, context={"title": "Senior Engineer"}
        )

        # Document is already finalized since requires_approval is False
        output_path = doc_generator.export_document_pdf(doc_id)

        assert output_path is not None
        assert isinstance(output_path, str)
        assert len(output_path) > 0
        assert "document_" in output_path

    def test_export_document_pdf_not_finalized_raises(self, doc_generator):
        """export_document_pdf raises for non-finalized document."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Offer",
            content="Content",
            required_variables=[],
            requires_approval=True,
        )

        doc_id = doc_generator.generate_document(template_id=template_id, context={})

        with pytest.raises(ValueError, match="must be finalized"):
            doc_generator.export_document_pdf(doc_id)


class TestDocumentListing:
    """Tests for listing and retrieving documents."""

    def test_list_documents(self, doc_generator):
        """list_documents returns all generated documents."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Offer",
            content="{{ name }}",
            required_variables=["name"],
        )

        doc_generator.generate_document(template_id, {"name": "A"})
        doc_generator.generate_document(template_id, {"name": "B"})

        documents = doc_generator.list_documents()

        assert len(documents) >= 2

    def test_list_documents_filtered_by_type(self, doc_generator):
        """list_documents can filter by document type."""
        offer_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Offer",
            content="{{ x }}",
            required_variables=["x"],
        )
        term_id = doc_generator.create_template(
            document_type=DocumentType.TERMINATION_LETTER,
            name="Termination",
            content="{{ y }}",
            required_variables=["y"],
        )

        doc_generator.generate_document(offer_id, {"x": "a"})
        doc_generator.generate_document(term_id, {"y": "b"})

        offers = doc_generator.list_documents(DocumentType.OFFER_LETTER)

        assert all(d.document_type == DocumentType.OFFER_LETTER for d in offers)

    def test_get_document_history(self, doc_generator):
        """get_document_history retrieves all documents from template."""
        template_id = doc_generator.create_template(
            document_type=DocumentType.OFFER_LETTER,
            name="Offer",
            content="{{ emp }}",
            required_variables=["emp"],
        )

        doc_generator.generate_document(template_id, {"emp": "emp1"})
        doc_generator.generate_document(template_id, {"emp": "emp2"})
        doc_generator.generate_document(template_id, {"emp": "emp3"})

        history = doc_generator.get_document_history(template_id)

        assert len(history) == 3
