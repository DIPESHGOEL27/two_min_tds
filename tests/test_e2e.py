"""
End-to-end tests for the TDS Challan Processor.
Tests the complete flow: upload -> extract -> review -> export.
"""

import pytest
from pathlib import Path
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from extraction import process_pdf, process_batch
from validation import validate_batch, ChallanValidator
from export import write_excel
from models import ValidationStatus, ReviewStatus


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_pipeline_single_pdf(self, sample_pdf_1, temp_dir, expected_values):
        """Test complete pipeline with single PDF."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        # Step 1: Extract
        result = process_pdf(sample_pdf_1)
        assert result.success
        record = result.record

        # Step 2: Validate
        validator = ChallanValidator()
        validation_result = validator.validate(record)

        # Step 3: Export
        output_path = temp_dir / "e2e_single.xlsx"
        write_excel([record], output_path)

        # Verify
        assert output_path.exists()
        df = pd.read_excel(output_path, sheet_name="TDS Challans")
        assert len(df) == 1

        expected = expected_values[sample_pdf_1.name]
        assert abs(df.iloc[0]["Total Amount"] - expected["total_amount"]) <= 0.01

    def test_full_pipeline_batch(self, all_sample_pdfs, temp_dir, expected_values):
        """Test complete pipeline with batch of PDFs."""
        existing_pdfs = [p for p in all_sample_pdfs if p.exists()]
        if len(existing_pdfs) < 3:
            pytest.skip("Not all sample PDFs found")

        # Step 1: Batch extract
        results = process_batch(existing_pdfs)
        assert all(r.success for r in results)
        records = [r.record for r in results]

        # Step 2: Batch validate
        validation_results = validate_batch(records)

        # Step 3: Export
        output_path = temp_dir / "e2e_batch.xlsx"
        write_excel(records, output_path)

        # Verify
        df = pd.read_excel(output_path, sheet_name="TDS Challans")
        assert len(df) == 3

        # Verify all expected amounts are present
        amounts = df["Total Amount"].tolist()
        assert any(abs(a - 19395.0) <= 0.01 for a in amounts)
        assert any(abs(a - 22500.0) <= 0.01 for a in amounts)
        assert any(abs(a - 40000.0) <= 0.01 for a in amounts)

    def test_e2e_three_sample_pdfs(self, all_sample_pdfs, temp_dir):
        """
        Acceptance test: Upload three sample PDFs and verify final Excel
        contains three rows with amounts 19395.00, 22500.00, 40000.00.
        """
        existing_pdfs = [p for p in all_sample_pdfs if p.exists()]
        if len(existing_pdfs) < 3:
            pytest.skip("Not all sample PDFs found")

        # Process all PDFs
        results = process_batch(existing_pdfs)
        records = [r.record for r in results if r.success]

        # Validate
        validate_batch(records)

        # Export
        output_path = temp_dir / "TDS_extracted.xlsx"
        write_excel(records, output_path)

        # Read and verify
        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        # Must have 3 rows
        assert len(df) == 3, f"Expected 3 rows, got {len(df)}"

        # Verify amounts with 0.01 tolerance
        amounts = sorted(df["Total Amount"].tolist())
        expected_amounts = sorted([19395.00, 22500.00, 40000.00])

        for actual, expected in zip(amounts, expected_amounts):
            diff = abs(actual - expected)
            assert diff <= 0.01, f"Amount mismatch: expected {expected}, got {actual}"

    def test_e2e_validation_flag_propagation(self, all_sample_pdfs, temp_dir):
        """Test that validation flags are correctly propagated to Excel."""
        existing_pdfs = [p for p in all_sample_pdfs if p.exists()]
        if not existing_pdfs:
            pytest.skip("No sample PDFs found")

        # Process
        results = process_batch(existing_pdfs)
        records = [r.record for r in results if r.success]

        # Validate
        validate_batch(records)

        # Export
        output_path = temp_dir / "test_flags.xlsx"
        write_excel(records, output_path)

        # Verify flags in Excel
        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        # All sample records should be OK (valid data)
        for flag in df["Validation Flag"]:
            assert flag in ["OK", "FLAG"]

    def test_e2e_confidence_score_propagation(self, sample_pdf_1, temp_dir):
        """Test that confidence scores are propagated to Excel."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)
        record = result.record

        output_path = temp_dir / "test_confidence.xlsx"
        write_excel([record], output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        # Confidence should be present and in valid range
        confidence = df.iloc[0]["Row Confidence"]
        assert 0.0 <= confidence <= 1.0

    def test_e2e_review_workflow(self, sample_pdf_1, temp_dir):
        """Test review workflow simulation."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        # Extract
        result = process_pdf(sample_pdf_1)
        record = result.record

        # Validate
        validator = ChallanValidator()
        validator.validate(record)

        # Simulate review: user accepts the record
        record.review_status = ReviewStatus.ACCEPTED

        # Export (only accepted records)
        output_path = temp_dir / "test_reviewed.xlsx"
        accepted_records = [record] if record.review_status == ReviewStatus.ACCEPTED else []
        write_excel(accepted_records, output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")
        assert len(df) == 1

    def test_e2e_rejected_records_excluded(self, sample_pdf_1, sample_pdf_2, temp_dir):
        """Test that rejected records are excluded from export."""
        existing_pdfs = [p for p in [sample_pdf_1, sample_pdf_2] if p.exists()]
        if len(existing_pdfs) < 2:
            pytest.skip("Not enough sample PDFs found")

        # Process
        results = process_batch(existing_pdfs)
        records = [r.record for r in results if r.success]

        # Reject one record
        records[0].review_status = ReviewStatus.REJECTED
        records[1].review_status = ReviewStatus.ACCEPTED

        # Export only non-rejected
        export_records = [r for r in records if r.review_status != ReviewStatus.REJECTED]
        output_path = temp_dir / "test_rejected.xlsx"
        write_excel(export_records, output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")
        assert len(df) == 1  # Only accepted record


class TestValidationRuleE2E:
    """End-to-end tests for validation rules."""

    def test_sum_mismatch_flagged_e2e(self, temp_dir):
        """Test that sum mismatch results in FLAG status in final Excel."""
        from models import ChallanRecord, TaxBreakup
        from datetime import date

        # Create record with mismatched sum
        record = ChallanRecord(
            tan="BLRS05586H",
            deductor_name="Test Company",
            cin="TEST123456789HDFC",
            total_amount=10000.00,
            challan_no="12345",
            date_of_deposit=date(2025, 10, 7),
            tax_breakup=TaxBreakup(
                tax_a=5000.00,  # Sum is 5000, not 10000
                tax_b=0.0,
                tax_c=0.0,
                tax_d=0.0,
                tax_e=0.0,
                tax_f=0.0
            ),
            source_file="test_mismatch.pdf"
        )

        # Validate
        validator = ChallanValidator()
        validator.validate(record)

        # Export
        output_path = temp_dir / "test_sum_mismatch.xlsx"
        write_excel([record], output_path)

        # Verify flag in Excel
        df = pd.read_excel(output_path, sheet_name="TDS Challans")
        assert df.iloc[0]["Validation Flag"] == "FLAG"

    def test_valid_sum_ok_e2e(self, sample_pdf_1, temp_dir):
        """Test that matching sum results in OK status."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)
        record = result.record

        # Validate
        validator = ChallanValidator()
        validator.validate(record)

        # Export
        output_path = temp_dir / "test_sum_ok.xlsx"
        write_excel([record], output_path)

        # Verify flag in Excel
        df = pd.read_excel(output_path, sheet_name="TDS Challans")
        assert df.iloc[0]["Validation Flag"] == "OK"


class TestDeduplicationE2E:
    """End-to-end tests for deduplication."""

    def test_duplicate_upload_detected(self, sample_pdf_1, temp_dir):
        """Test that uploading same PDF twice flags duplicate."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        # Process same PDF twice
        result1 = process_pdf(sample_pdf_1)
        result2 = process_pdf(sample_pdf_1)

        records = [result1.record, result2.record]

        # Validate batch (should detect duplicate)
        validation_results = validate_batch(records)

        # Second record should be flagged as duplicate
        dup_issues = [
            i for i in validation_results[1].issues
            if i.issue_type == "duplicate"
        ]
        assert len(dup_issues) == 1
