"""Tests for PII stripping and redaction module."""

import pytest
from src.middleware.pii_stripper import PIIStripper, PIIResult


class TestPIIStripperSSN:
    """Tests for SSN detection and stripping."""

    def test_strip_ssn_single(self):
        """SSN is detected and stripped."""
        stripper = PIIStripper()
        text = "SSN is 123-45-6789"

        result = stripper.strip(text)

        assert "123-45-6789" not in result.sanitized_text
        assert "[SSN_REDACTED]" in result.sanitized_text
        assert "123-45-6789" in result.mapping
        assert result.pii_count >= 1
        assert "SSN" in result.pii_types_found

    def test_strip_ssn_multiple(self):
        """Multiple SSNs are stripped."""
        stripper = PIIStripper()
        text = "First SSN: 123-45-6789 Second SSN: 987-65-4321"

        result = stripper.strip(text)

        assert "123-45-6789" not in result.sanitized_text
        assert "987-65-4321" not in result.sanitized_text
        assert "[SSN_REDACTED]" in result.sanitized_text
        assert result.pii_count >= 2


class TestPIIStripperEmail:
    """Tests for email detection and stripping."""

    def test_strip_email(self):
        """Email is detected and stripped."""
        stripper = PIIStripper()
        text = "email john@company.com"

        result = stripper.strip(text)

        assert "john@company.com" not in result.sanitized_text
        assert "[EMAIL_REDACTED" in result.sanitized_text
        assert "john@company.com" in result.mapping
        assert "EMAIL" in result.pii_types_found

    def test_strip_multiple_emails(self):
        """Multiple emails are stripped with numbered redactions."""
        stripper = PIIStripper()
        text = "Contact john@company.com or jane@company.com"

        result = stripper.strip(text)

        assert "john@company.com" not in result.sanitized_text
        assert "jane@company.com" not in result.sanitized_text
        assert "[EMAIL_REDACTED_1]" in result.sanitized_text
        assert "[EMAIL_REDACTED_2]" in result.sanitized_text


class TestPIIStripperPhone:
    """Tests for phone number detection and stripping."""

    def test_strip_phone(self):
        """Phone number is detected and stripped."""
        stripper = PIIStripper()
        text = "call 555-123-4567"

        result = stripper.strip(text)

        assert "555-123-4567" not in result.sanitized_text
        assert "[PHONE_REDACTED]" in result.sanitized_text
        assert "PHONE" in result.pii_types_found

    def test_strip_phone_variants(self):
        """Various phone formats are detected."""
        stripper = PIIStripper()
        text = "Call 555-123-4567 or (555) 123-4567"

        result = stripper.strip(text)

        # Both formats should be stripped
        assert "[PHONE_REDACTED]" in result.sanitized_text


class TestPIIStripperSalary:
    """Tests for salary detection and stripping."""

    def test_strip_salary(self):
        """Salary amounts are detected and stripped."""
        stripper = PIIStripper()
        text = "earns $150,000"

        result = stripper.strip(text)

        assert "$150,000" not in result.sanitized_text
        assert "[SALARY_REDACTED]" in result.sanitized_text
        assert "SALARY" in result.pii_types_found

    def test_strip_salary_with_cents(self):
        """Salary with cents is detected."""
        stripper = PIIStripper()
        text = "salary is $75,500.50"

        result = stripper.strip(text)

        assert "$75,500.50" not in result.sanitized_text
        assert "[SALARY_REDACTED]" in result.sanitized_text


class TestPIIStripperEmployeeID:
    """Tests for employee ID detection and stripping."""

    def test_strip_employee_id(self):
        """Employee ID is detected and stripped."""
        stripper = PIIStripper()
        text = "Employee EMP-12345 reports"

        result = stripper.strip(text)

        assert "EMP-12345" not in result.sanitized_text
        assert "[EMPLOYEE_ID_REDACTED]" in result.sanitized_text
        assert "EMPLOYEE_ID" in result.pii_types_found


class TestPIIRehydration:
    """Tests for restoring original PII values."""

    def test_rehydrate_restores_original(self):
        """rehydrate() restores original values from mapping."""
        stripper = PIIStripper()
        original_text = "Contact john@company.com with SSN 123-45-6789"

        result = stripper.strip(original_text)
        rehydrated = stripper.rehydrate(result.sanitized_text, result.mapping)

        assert "john@company.com" in rehydrated
        assert "123-45-6789" in rehydrated

    def test_rehydrate_multiple_pii(self):
        """rehydrate() handles multiple PII items."""
        stripper = PIIStripper()
        original = "John's email: john@company.com, SSN: 123-45-6789, salary: $100,000"

        result = stripper.strip(original)
        rehydrated = stripper.rehydrate(result.sanitized_text, result.mapping)

        assert "john@company.com" in rehydrated
        assert "123-45-6789" in rehydrated
        assert "$100,000" in rehydrated


class TestMultiplePIIItems:
    """Tests for handling multiple PII items in text."""

    def test_multiple_pii_stripped(self):
        """Multiple PII items are all stripped."""
        stripper = PIIStripper()
        text = (
            "Employee EMP-12345 john@company.com "
            "SSN 123-45-6789 earns $150,000 "
            "call 555-123-4567"
        )

        result = stripper.strip(text)

        assert "EMP-12345" not in result.sanitized_text
        assert "john@company.com" not in result.sanitized_text
        assert "123-45-6789" not in result.sanitized_text
        assert "$150,000" not in result.sanitized_text
        assert "555-123-4567" not in result.sanitized_text

        assert result.pii_count >= 5
        assert len(result.mapping) >= 5


class TestNoPIIDetected:
    """Tests for text without PII."""

    def test_no_pii_unchanged(self):
        """Text without PII is unchanged."""
        stripper = PIIStripper()
        text = "This is clean text with no sensitive information"

        result = stripper.strip(text)

        assert result.sanitized_text == text
        assert result.pii_count == 0
        assert len(result.mapping) == 0

    def test_empty_text_returns_empty(self):
        """Empty text returns empty result."""
        stripper = PIIStripper()

        result = stripper.strip("")

        assert result.sanitized_text == ""
        assert result.pii_count == 0


class TestPIISafetyCheck:
    """Tests for checking if text is PII-safe."""

    def test_is_pii_safe_clean_text(self):
        """Clean text is marked as PII safe."""
        stripper = PIIStripper()
        text = "This is clean text with no PII"

        assert stripper.is_pii_safe(text) is True

    def test_is_pii_safe_with_ssn(self):
        """Text with SSN is not safe."""
        stripper = PIIStripper()
        text = "Employee SSN: 123-45-6789"

        assert stripper.is_pii_safe(text) is False

    def test_is_pii_safe_with_email(self):
        """Text with email is not safe."""
        stripper = PIIStripper()
        text = "Contact john@company.com"

        assert stripper.is_pii_safe(text) is False

    def test_is_pii_safe_with_phone(self):
        """Text with phone is not safe."""
        stripper = PIIStripper()
        text = "Call 555-123-4567"

        assert stripper.is_pii_safe(text) is False

    def test_is_pii_safe_with_salary(self):
        """Text with salary is not safe."""
        stripper = PIIStripper()
        text = "Salary: $150,000"

        assert stripper.is_pii_safe(text) is False


class TestPIIResult:
    """Tests for PIIResult dataclass."""

    def test_pii_result_has_required_fields(self):
        """PIIResult contains all required fields."""
        result = PIIResult(
            sanitized_text="clean text",
            mapping={"original": "[REDACTED]"},
            pii_count=1,
            pii_types_found=["TEST"],
        )

        assert result.sanitized_text == "clean text"
        assert result.mapping == {"original": "[REDACTED]"}
        assert result.pii_count == 1
        assert result.pii_types_found == ["TEST"]

    def test_pii_result_default_mapping(self):
        """PIIResult has default empty mapping."""
        result = PIIResult(sanitized_text="test")

        assert result.mapping == {}
        assert result.pii_count == 0
        assert result.pii_types_found == []


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_pii_in_different_contexts(self):
        """PII is detected in various contexts."""
        stripper = PIIStripper()
        text = (
            "Employee john@company.com with EMP-001 "
            "and backup jane@company.com has SSN 123-45-6789"
        )

        result = stripper.strip(text)

        assert "john@company.com" not in result.sanitized_text
        assert "jane@company.com" not in result.sanitized_text
        assert "EMP-001" not in result.sanitized_text
        assert "123-45-6789" not in result.sanitized_text
        assert result.pii_count >= 4

    def test_case_insensitive_pattern_matching(self):
        """Case variations are handled."""
        stripper = PIIStripper()
        # Emails should be case-insensitive
        text = "Contact JOHN@COMPANY.COM"

        result = stripper.strip(text)

        # Email pattern matching should work
        assert result.pii_count >= 1

    def test_rehydration_idempotent(self):
        """Rehydrating multiple times returns same result."""
        stripper = PIIStripper()
        text = "Email: john@company.com and SSN: 123-45-6789"

        result = stripper.strip(text)

        rehydrated1 = stripper.rehydrate(result.sanitized_text, result.mapping)
        rehydrated2 = stripper.rehydrate(rehydrated1, result.mapping)

        # Second rehydration shouldn't change anything
        assert rehydrated1 == rehydrated2
