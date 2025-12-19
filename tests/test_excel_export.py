"""
Tests for Excel export functionality.
"""

import pytest
from pathlib import Path
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from export import (
    ExcelWriter,
    write_excel,
    get_column_schema,
    EXCEL_COLUMNS,
)
from models import ChallanRecord, ValidationStatus


class TestExcelWriter:
    """Tests for ExcelWriter class."""

    def test_write_single_record(self, sample_record_1, temp_dir):
        """Test writing a single record to Excel."""
        output_path = temp_dir / "test_single.xlsx"

        writer = ExcelWriter()
        result_path = writer.write([sample_record_1], output_path)

        assert result_path.exists()
        assert result_path.suffix == ".xlsx"

        # Read and verify
        df = pd.read_excel(result_path, sheet_name="TDS Challans")
        assert len(df) == 1
        assert df.iloc[0]["TAN"] == sample_record_1.tan

    def test_write_multiple_records(
        self, sample_record_1, sample_record_2, sample_record_3, temp_dir
    ):
        """Test writing multiple records to Excel."""
        output_path = temp_dir / "test_multiple.xlsx"
        records = [sample_record_1, sample_record_2, sample_record_3]

        result_path = write_excel(records, output_path)

        assert result_path.exists()

        df = pd.read_excel(result_path, sheet_name="TDS Challans")
        assert len(df) == 3

        # Verify amounts
        amounts = df["Total Amount"].tolist()
        assert 19395.0 in amounts
        assert 22500.0 in amounts
        assert 40000.0 in amounts

    def test_write_includes_summary_sheet(self, sample_record_1, temp_dir):
        """Test that summary sheet is included."""
        output_path = temp_dir / "test_summary.xlsx"

        write_excel([sample_record_1], output_path, include_summary=True)

        # Read all sheets
        xl = pd.ExcelFile(output_path)
        assert "Summary" in xl.sheet_names

    def test_write_columns_order(self, sample_record_1, temp_dir):
        """Test that columns are in correct order."""
        output_path = temp_dir / "test_columns.xlsx"

        write_excel([sample_record_1], output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")
        actual_columns = df.columns.tolist()

        assert actual_columns == EXCEL_COLUMNS

    def test_write_flagged_records_sheet(self, flagged_record, temp_dir):
        """Test that flagged records get separate sheet."""
        # Validate to set flag
        from validation import validate_record
        validate_record(flagged_record)

        output_path = temp_dir / "test_flagged.xlsx"
        write_excel([flagged_record], output_path)

        xl = pd.ExcelFile(output_path)
        assert "Flagged Records" in xl.sheet_names

    def test_write_empty_records(self, temp_dir):
        """Test writing with empty records list."""
        output_path = temp_dir / "test_empty.xlsx"

        writer = ExcelWriter()
        result_path = writer.write([], output_path)

        assert result_path.exists()

        df = pd.read_excel(result_path, sheet_name="TDS Challans")
        assert len(df) == 0

    def test_column_schema(self):
        """Test column schema is correct."""
        schema = get_column_schema()

        assert "TAN" in schema
        assert "Total Amount" in schema
        assert "CIN" in schema
        assert "Date of Deposit" in schema
        assert "Row Confidence" in schema


class TestExcelContent:
    """Tests for Excel content accuracy."""

    def test_amount_format(self, sample_record_1, temp_dir):
        """Test that amounts are properly formatted."""
        output_path = temp_dir / "test_amount.xlsx"

        write_excel([sample_record_1], output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        # Amount should be numeric
        assert df["Total Amount"].dtype in ["float64", "int64"]
        assert abs(df.iloc[0]["Total Amount"] - 19395.0) <= 0.01

    def test_date_format(self, sample_record_1, temp_dir):
        """Test that dates are in ISO format."""
        output_path = temp_dir / "test_date.xlsx"

        write_excel([sample_record_1], output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        date_str = df.iloc[0]["Date of Deposit"]
        assert date_str == "2025-10-07"

    def test_validation_flag_values(self, sample_record_1, flagged_record, temp_dir):
        """Test validation flag column values."""
        from validation import validate_record
        validate_record(sample_record_1)
        validate_record(flagged_record)

        output_path = temp_dir / "test_flags.xlsx"
        write_excel([sample_record_1, flagged_record], output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        flags = df["Validation Flag"].tolist()
        assert "OK" in flags
        assert "FLAG" in flags

    def test_tax_breakup_columns(self, sample_record_1, temp_dir):
        """Test tax breakup columns are present and correct."""
        output_path = temp_dir / "test_tax.xlsx"

        write_excel([sample_record_1], output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        # All tax columns should be present
        tax_cols = ["Tax_A", "Tax_B", "Tax_C", "Tax_D", "Tax_E", "Tax_F"]
        for col in tax_cols:
            assert col in df.columns

        # Tax_A should equal total for sample record 1
        assert abs(df.iloc[0]["Tax_A"] - 19395.0) <= 0.01

    def test_source_file_preserved(self, sample_record_1, temp_dir):
        """Test source file name is preserved."""
        output_path = temp_dir / "test_source.xlsx"

        write_excel([sample_record_1], output_path)

        df = pd.read_excel(output_path, sheet_name="TDS Challans")

        assert df.iloc[0]["Source File"] == sample_record_1.source_file


class TestSummarySheet:
    """Tests for summary sheet content."""

    def test_summary_totals(
        self, sample_record_1, sample_record_2, sample_record_3, temp_dir
    ):
        """Test summary sheet contains correct totals."""
        records = [sample_record_1, sample_record_2, sample_record_3]
        output_path = temp_dir / "test_summary_totals.xlsx"

        write_excel(records, output_path)

        # Read summary sheet
        df_summary = pd.read_excel(output_path, sheet_name="Summary")

        # Total amount should be sum of all records
        expected_total = 19395.0 + 22500.0 + 40000.0

        # Find total in summary (looking for the row with "Total Amount (Sum)")
        summary_text = df_summary.to_string()
        assert str(int(expected_total)) in summary_text or "81895" in summary_text

    def test_summary_by_tan(
        self, sample_record_1, sample_record_2, sample_record_3, temp_dir
    ):
        """Test summary includes grouping by TAN."""
        records = [sample_record_1, sample_record_2, sample_record_3]
        output_path = temp_dir / "test_summary_tan.xlsx"

        write_excel(records, output_path)

        df_summary = pd.read_excel(output_path, sheet_name="Summary")
        summary_text = df_summary.to_string()

        # All records have same TAN, should appear in summary
        assert "BLRS05586H" in summary_text
