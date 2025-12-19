"""
Tests for PDF extraction pipeline.
Tests text extraction, layout extraction, and the full pipeline.
"""

import pytest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from extraction import (
    ExtractionPipeline,
    TextExtractor,
    LayoutExtractor,
    process_pdf,
    process_batch,
)
from models import ValidationStatus


class TestTextExtractor:
    """Tests for text-based extraction."""

    def test_extract_sample_pdf_1(self, sample_pdf_1, expected_values):
        """Test extraction from first sample PDF."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        extractor = TextExtractor()
        fields, raw_text = extractor.extract(sample_pdf_1)

        expected = expected_values[sample_pdf_1.name]

        # Check TAN extraction
        assert "tan" in fields
        assert fields["tan"].value == expected["tan"]

        # Check CIN extraction
        assert "cin" in fields
        assert fields["cin"].value == expected["cin"]

        # Check total amount with tolerance
        assert "total_amount" in fields
        assert abs(fields["total_amount"].value - expected["total_amount"]) <= 0.01

    def test_extract_sample_pdf_2(self, sample_pdf_2, expected_values):
        """Test extraction from second sample PDF."""
        if not sample_pdf_2.exists():
            pytest.skip("Sample PDF not found")

        extractor = TextExtractor()
        fields, raw_text = extractor.extract(sample_pdf_2)

        expected = expected_values[sample_pdf_2.name]

        assert "total_amount" in fields
        assert abs(fields["total_amount"].value - expected["total_amount"]) <= 0.01

        assert "nature_of_payment" in fields
        assert fields["nature_of_payment"].value == expected["nature_of_payment"]

    def test_extract_sample_pdf_3(self, sample_pdf_3, expected_values):
        """Test extraction from third sample PDF."""
        if not sample_pdf_3.exists():
            pytest.skip("Sample PDF not found")

        extractor = TextExtractor()
        fields, raw_text = extractor.extract(sample_pdf_3)

        expected = expected_values[sample_pdf_3.name]

        assert "total_amount" in fields
        assert abs(fields["total_amount"].value - expected["total_amount"]) <= 0.01

    def test_extract_returns_raw_text(self, sample_pdf_1):
        """Test that raw text is returned."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        extractor = TextExtractor()
        fields, raw_text = extractor.extract(sample_pdf_1)

        assert raw_text
        assert "TAN" in raw_text
        assert "CIN" in raw_text

    def test_extract_tax_breakup(self, sample_pdf_1):
        """Test tax breakup extraction."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        extractor = TextExtractor()
        fields, _ = extractor.extract(sample_pdf_1)

        # Tax A should be 19395
        assert "tax_a" in fields
        assert abs(fields["tax_a"].value - 19395.0) <= 0.01

        # Other taxes should be 0
        for tax_field in ["tax_b", "tax_c", "tax_d", "tax_e", "tax_f"]:
            assert tax_field in fields
            assert fields[tax_field].value == 0.0


class TestLayoutExtractor:
    """Tests for layout-based extraction."""

    def test_layout_extraction_basic(self, sample_pdf_1):
        """Test basic layout extraction."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        extractor = LayoutExtractor()
        fields = extractor.extract(sample_pdf_1)

        # Should extract at least some fields
        assert len(fields) > 0


class TestExtractionPipeline:
    """Tests for the full extraction pipeline."""

    def test_process_pdf_success(self, sample_pdf_1, expected_values):
        """Test successful PDF processing."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.success
        assert result.record is not None

        expected = expected_values[sample_pdf_1.name]

        # Verify extracted values
        assert result.record.tan == expected["tan"]
        assert result.record.cin == expected["cin"]
        assert abs(result.record.total_amount - expected["total_amount"]) <= 0.01

    def test_process_pdf_amount_19395(self, sample_pdf_1):
        """Test extraction of 19395.00 amount."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.success
        assert abs(result.record.total_amount - 19395.00) <= 0.01

    def test_process_pdf_amount_22500(self, sample_pdf_2):
        """Test extraction of 22500.00 amount."""
        if not sample_pdf_2.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_2)

        assert result.success
        assert abs(result.record.total_amount - 22500.00) <= 0.01

    def test_process_pdf_amount_40000(self, sample_pdf_3):
        """Test extraction of 40000.00 amount."""
        if not sample_pdf_3.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_3)

        assert result.success
        assert abs(result.record.total_amount - 40000.00) <= 0.01

    def test_process_batch(self, all_sample_pdfs, expected_values):
        """Test batch processing of multiple PDFs."""
        existing_pdfs = [p for p in all_sample_pdfs if p.exists()]
        if not existing_pdfs:
            pytest.skip("No sample PDFs found")

        results = process_batch(existing_pdfs)

        assert len(results) == len(existing_pdfs)
        assert all(r.success for r in results)

        # Verify all amounts
        amounts = [r.record.total_amount for r in results]
        expected_amounts = [19395.00, 22500.00, 40000.00]

        for expected_amt in expected_amounts:
            assert any(abs(amt - expected_amt) <= 0.01 for amt in amounts)

    def test_process_pdf_returns_confidence(self, sample_pdf_1):
        """Test that confidence score is calculated."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.success
        assert 0.0 <= result.record.row_confidence <= 1.0
        # For clean PDFs, confidence should be high
        assert result.record.row_confidence >= 0.7

    def test_process_pdf_computes_hash(self, sample_pdf_1):
        """Test that deduplication hash is computed."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.success
        assert result.record.record_hash is not None
        assert len(result.record.record_hash) > 0

    def test_process_pdf_date_parsing(self, sample_pdf_1, expected_values):
        """Test date parsing to ISO format."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.success
        assert result.record.date_of_deposit is not None

        expected = expected_values[sample_pdf_1.name]
        assert result.record.date_of_deposit.isoformat() == expected["date_of_deposit"]

    def test_process_pdf_nature_of_payment(self, sample_pdf_1, expected_values):
        """Test nature of payment extraction."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.success
        expected = expected_values[sample_pdf_1.name]
        assert result.record.nature_of_payment == expected["nature_of_payment"]

    def test_extraction_method_recorded(self, sample_pdf_1):
        """Test that extraction method is recorded."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.extraction_method in ["text", "text+ocr", "layout", "ocr"]

    def test_processing_time_recorded(self, sample_pdf_1):
        """Test that processing time is recorded."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        result = process_pdf(sample_pdf_1)

        assert result.processing_time_ms > 0


class TestExtractionAccuracy:
    """Tests specifically for extraction accuracy requirements."""

    @pytest.mark.parametrize("pdf_fixture,expected_amount", [
        ("sample_pdf_1", 19395.00),
        ("sample_pdf_2", 22500.00),
        ("sample_pdf_3", 40000.00),
    ])
    def test_amount_extraction_tolerance(self, pdf_fixture, expected_amount, request):
        """Test amount extraction with 0.01 tolerance."""
        pdf_path = request.getfixturevalue(pdf_fixture)

        if not pdf_path.exists():
            pytest.skip(f"Sample PDF {pdf_fixture} not found")

        result = process_pdf(pdf_path)

        assert result.success, f"Extraction failed: {result.error_message}"
        assert result.record.total_amount is not None

        # Assert with tolerance of 0.01 as per requirements
        difference = abs(result.record.total_amount - expected_amount)
        assert difference <= 0.01, (
            f"Amount mismatch: expected {expected_amount}, "
            f"got {result.record.total_amount}, diff={difference}"
        )
