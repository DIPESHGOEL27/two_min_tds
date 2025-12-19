"""
Tests for validation rules.
Tests sum check, date parsing, TAN validation, and deduplication.
"""

import pytest
from pathlib import Path
from datetime import date

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from validation import (
    ChallanValidator,
    validate_record,
    validate_batch,
    ValidationResult,
    ValidationIssue,
)
from models import ChallanRecord, TaxBreakup, ValidationStatus


class TestChallanValidator:
    """Tests for ChallanValidator."""

    def test_validate_valid_record(self, sample_record_1):
        """Test validation of a valid record."""
        validator = ChallanValidator()
        result = validator.validate(sample_record_1)

        assert result.is_valid
        assert not result.has_errors
        assert sample_record_1.validation_flag == ValidationStatus.OK

    def test_validate_sum_check_pass(self, sample_record_1):
        """Test sum check passes when taxes sum to total."""
        # Tax_A = 19395, others = 0, Total = 19395
        validator = ChallanValidator()
        result = validator.validate(sample_record_1)

        # Should pass sum check
        sum_issues = [i for i in result.issues if i.issue_type == "sum_mismatch"]
        assert len(sum_issues) == 0

    def test_validate_sum_check_fail(self, flagged_record):
        """Test sum check fails when taxes don't sum to total."""
        # Total = 10000, Tax_A = 5000 -> mismatch of 5000
        validator = ChallanValidator()
        result = validator.validate(flagged_record)

        assert not result.is_valid
        assert result.has_errors

        # Should have sum mismatch issue
        sum_issues = [i for i in result.issues if i.issue_type == "sum_mismatch"]
        assert len(sum_issues) == 1

        # Record should be flagged
        assert flagged_record.validation_flag == ValidationStatus.FLAG

    def test_validate_sum_check_tolerance(self):
        """Test sum check tolerance (within 1.0 rupee)."""
        record = ChallanRecord(
            tan="BLRS05586H",
            cin="TEST123456789HDFC",
            total_amount=10000.50,  # Slight difference
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            tax_breakup=TaxBreakup(
                tax_a=10000.00,  # Difference of 0.50
                tax_b=0.0,
                tax_c=0.0,
                tax_d=0.0,
                tax_e=0.0,
                tax_f=0.0
            ),
            source_file="test.pdf"
        )

        validator = ChallanValidator()
        result = validator.validate(record)

        # Should pass because difference (0.50) < tolerance (1.0)
        sum_issues = [i for i in result.issues if i.issue_type == "sum_mismatch"]
        assert len(sum_issues) == 0

    def test_validate_tan_format_valid(self, sample_record_1):
        """Test valid TAN format passes."""
        validator = ChallanValidator()
        result = validator.validate(sample_record_1)

        tan_issues = [i for i in result.issues if i.field == "tan"]
        # Should have no TAN issues for valid format
        tan_errors = [i for i in tan_issues if i.severity == "error"]
        assert len(tan_errors) == 0

    def test_validate_tan_format_invalid(self):
        """Test invalid TAN format is flagged."""
        record = ChallanRecord(
            tan="INVALID",  # Invalid format
            cin="TEST123456789HDFC",
            total_amount=1000.00,
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            tax_breakup=TaxBreakup(tax_a=1000.00),
            source_file="test.pdf"
        )

        validator = ChallanValidator()
        result = validator.validate(record)

        tan_issues = [i for i in result.issues if i.field == "tan" and i.issue_type == "format"]
        assert len(tan_issues) == 1

    def test_validate_tan_missing(self):
        """Test missing TAN is flagged."""
        record = ChallanRecord(
            tan=None,  # Missing
            cin="TEST123456789HDFC",
            total_amount=1000.00,
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            tax_breakup=TaxBreakup(tax_a=1000.00),
            source_file="test.pdf"
        )

        validator = ChallanValidator()
        result = validator.validate(record)

        tan_issues = [i for i in result.issues if i.field == "tan" and i.issue_type == "missing"]
        assert len(tan_issues) == 1

    def test_validate_cin_missing(self):
        """Test missing CIN is flagged."""
        record = ChallanRecord(
            tan="BLRS05586H",
            cin=None,  # Missing
            total_amount=1000.00,
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            tax_breakup=TaxBreakup(tax_a=1000.00),
            source_file="test.pdf"
        )

        validator = ChallanValidator()
        result = validator.validate(record)

        cin_issues = [i for i in result.issues if i.field == "cin" and i.issue_type == "missing"]
        assert len(cin_issues) == 1

    def test_validate_amount_missing(self):
        """Test missing amount is flagged."""
        record = ChallanRecord(
            tan="BLRS05586H",
            cin="TEST123456789HDFC",
            total_amount=None,  # Missing
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            source_file="test.pdf"
        )

        validator = ChallanValidator()
        result = validator.validate(record)

        amount_issues = [i for i in result.issues if i.field == "total_amount" and i.issue_type == "missing"]
        assert len(amount_issues) == 1

    def test_validate_date_missing(self):
        """Test missing date is flagged."""
        record = ChallanRecord(
            tan="BLRS05586H",
            cin="TEST123456789HDFC",
            total_amount=1000.00,
            challan_no="12345",
            date_of_deposit=None,  # Missing
            tax_breakup=TaxBreakup(tax_a=1000.00),
            source_file="test.pdf"
        )

        validator = ChallanValidator()
        result = validator.validate(record)

        date_issues = [i for i in result.issues if i.field == "date_of_deposit" and i.issue_type == "missing"]
        assert len(date_issues) == 1

    def test_validate_date_future(self):
        """Test future date is flagged as warning."""
        from datetime import timedelta

        future_date = date.today() + timedelta(days=365)

        record = ChallanRecord(
            tan="BLRS05586H",
            cin="TEST123456789HDFC",
            total_amount=1000.00,
            challan_no="12345",
            date_of_deposit=future_date,
            tax_breakup=TaxBreakup(tax_a=1000.00),
            source_file="test.pdf"
        )

        validator = ChallanValidator()
        result = validator.validate(record)

        future_issues = [i for i in result.issues if i.issue_type == "future_date"]
        assert len(future_issues) == 1
        assert future_issues[0].severity == "warning"


class TestDeduplication:
    """Tests for deduplication functionality."""

    def test_duplicate_detection(self, sample_record_1):
        """Test that duplicate records are detected."""
        # Create a duplicate record
        duplicate = ChallanRecord(
            tan=sample_record_1.tan,
            cin=sample_record_1.cin,
            total_amount=sample_record_1.total_amount,
            challan_no=sample_record_1.challan_no,
            date_of_deposit=sample_record_1.date_of_deposit,
            tax_breakup=TaxBreakup(tax_a=sample_record_1.total_amount),
            source_file="duplicate.pdf"
        )

        validator = ChallanValidator()

        # First record should pass
        result1 = validator.validate(sample_record_1)
        dup_issues_1 = [i for i in result1.issues if i.issue_type == "duplicate"]
        assert len(dup_issues_1) == 0

        # Second (duplicate) should be flagged
        result2 = validator.validate(duplicate)
        dup_issues_2 = [i for i in result2.issues if i.issue_type == "duplicate"]
        assert len(dup_issues_2) == 1

    def test_non_duplicate_records(self, sample_record_1, sample_record_2):
        """Test that different records are not flagged as duplicates."""
        validator = ChallanValidator()

        result1 = validator.validate(sample_record_1)
        result2 = validator.validate(sample_record_2)

        # Neither should be flagged as duplicate
        dup_issues_1 = [i for i in result1.issues if i.issue_type == "duplicate"]
        dup_issues_2 = [i for i in result2.issues if i.issue_type == "duplicate"]

        assert len(dup_issues_1) == 0
        assert len(dup_issues_2) == 0

    def test_dedupe_cache_reset(self, sample_record_1):
        """Test that dedupe cache can be reset."""
        duplicate = ChallanRecord(
            tan=sample_record_1.tan,
            cin=sample_record_1.cin,
            challan_no=sample_record_1.challan_no,
            date_of_deposit=sample_record_1.date_of_deposit,
            total_amount=sample_record_1.total_amount,
            tax_breakup=TaxBreakup(tax_a=sample_record_1.total_amount),
            source_file="dup.pdf"
        )

        validator = ChallanValidator()

        # First validation
        validator.validate(sample_record_1)

        # Reset cache
        validator.reset_dedupe_cache()

        # After reset, same record should not be flagged
        result = validator.validate(duplicate)
        dup_issues = [i for i in result.issues if i.issue_type == "duplicate"]
        assert len(dup_issues) == 0


class TestBatchValidation:
    """Tests for batch validation."""

    def test_validate_batch(self, sample_record_1, sample_record_2, sample_record_3):
        """Test batch validation of multiple records."""
        records = [sample_record_1, sample_record_2, sample_record_3]
        results = validate_batch(records)

        assert len(results) == 3
        # All sample records should be valid
        assert all(r.is_valid for r in results)

    def test_batch_deduplication(self, sample_record_1):
        """Test that duplicates are detected in batch."""
        duplicate = ChallanRecord(
            tan=sample_record_1.tan,
            cin=sample_record_1.cin,
            challan_no=sample_record_1.challan_no,
            date_of_deposit=sample_record_1.date_of_deposit,
            total_amount=sample_record_1.total_amount,
            tax_breakup=TaxBreakup(tax_a=sample_record_1.total_amount),
            source_file="dup.pdf"
        )

        records = [sample_record_1, duplicate]
        results = validate_batch(records)

        # Second record should have duplicate issue
        assert results[0].is_valid or not any(i.issue_type == "duplicate" for i in results[0].issues)

        dup_issues = [i for i in results[1].issues if i.issue_type == "duplicate"]
        assert len(dup_issues) == 1


class TestValidationFlag:
    """Tests for validation flag assignment."""

    def test_flag_on_sum_mismatch(self):
        """Test FLAG status when sum check fails."""
        record = ChallanRecord(
            tan="BLRS05586H",
            cin="TEST123456789HDFC",
            total_amount=10000.00,
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            tax_breakup=TaxBreakup(tax_a=5000.00),  # Mismatch
            source_file="test.pdf"
        )

        result = validate_record(record)

        assert not result.is_valid
        assert record.validation_flag == ValidationStatus.FLAG

    def test_ok_when_valid(self, sample_record_1):
        """Test OK status when validation passes."""
        result = validate_record(sample_record_1)

        assert result.is_valid
        assert sample_record_1.validation_flag == ValidationStatus.OK

    def test_notes_populated_on_issues(self):
        """Test that notes are populated with issues."""
        record = ChallanRecord(
            tan=None,  # Missing
            cin=None,  # Missing
            total_amount=None,  # Missing
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            source_file="test.pdf"
        )

        validate_record(record)

        # Notes should contain issue descriptions
        assert record.notes
        assert "missing" in record.notes.lower()
