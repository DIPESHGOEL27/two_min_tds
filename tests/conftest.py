"""
Pytest configuration and fixtures for TDS Challan Processor tests.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import date

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from models import ChallanRecord, TaxBreakup, ValidationStatus, ReviewStatus


# Path to sample PDFs
SAMPLE_PDFS_DIR = Path(__file__).parent.parent / "TDS Challans for Testing"


@pytest.fixture
def sample_pdf_dir() -> Path:
    """Return path to sample PDF directory."""
    return SAMPLE_PDFS_DIR


@pytest.fixture
def sample_pdf_1() -> Path:
    """First sample PDF - 19395.00 amount."""
    return SAMPLE_PDFS_DIR / "25100700517216HDFC_ChallanReceipt- Input Command Challan.pdf"


@pytest.fixture
def sample_pdf_2() -> Path:
    """Second sample PDF - 22500.00 amount."""
    return SAMPLE_PDFS_DIR / "25100700523936HDFC_ChallanReceipt- For other Testing.pdf"


@pytest.fixture
def sample_pdf_3() -> Path:
    """Third sample PDF - 40000.00 amount."""
    return SAMPLE_PDFS_DIR / "25100700528930HDFC_ChallanReceipt- For other Testing.pdf"


@pytest.fixture
def all_sample_pdfs(sample_pdf_1, sample_pdf_2, sample_pdf_3) -> list:
    """List of all sample PDFs."""
    return [sample_pdf_1, sample_pdf_2, sample_pdf_3]


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    temp = tempfile.mkdtemp()
    yield Path(temp)
    shutil.rmtree(temp, ignore_errors=True)


@pytest.fixture
def sample_record_1() -> ChallanRecord:
    """Sample record matching first PDF."""
    return ChallanRecord(
        tan="BLRS05586H",
        deductor_name="SYAMBHAVAN FOODS LLP",
        assessment_year="2026-27",
        financial_year="2025-26",
        major_head="Corporation Tax (0020)",
        minor_head="TDS/TCS Payable by Taxpayer (200)",
        nature_of_payment="94J",
        total_amount=19395.00,
        amount_in_words="Rupees Nineteen Thousand Three Hundred And Ninety Five Only",
        cin="25100700517216HDFC",
        bsr_code="0510016",
        challan_no="12866",
        date_of_deposit=date(2025, 10, 7),
        bank_name="HDFC Bank",
        bank_ref_no="N2528040495795",
        tax_breakup=TaxBreakup(
            tax_a=19395.00,
            tax_b=0.0,
            tax_c=0.0,
            tax_d=0.0,
            tax_e=0.0,
            tax_f=0.0
        ),
        source_file="25100700517216HDFC_ChallanReceipt- Input Command Challan.pdf",
        row_confidence=0.95,
        validation_flag=ValidationStatus.OK
    )


@pytest.fixture
def sample_record_2() -> ChallanRecord:
    """Sample record matching second PDF."""
    return ChallanRecord(
        tan="BLRS05586H",
        deductor_name="SYAMBHAVAN FOODS LLP",
        assessment_year="2026-27",
        financial_year="2025-26",
        major_head="Income Tax (Other than Companies) (0021)",
        minor_head="TDS/TCS Payable by Taxpayer (200)",
        nature_of_payment="94I",
        total_amount=22500.00,
        amount_in_words="Rupees Twenty Two Thousand Five Hundred Only",
        cin="25100700523936HDFC",
        bsr_code="0510016",
        challan_no="14644",
        date_of_deposit=date(2025, 10, 7),
        bank_name="HDFC Bank",
        bank_ref_no="N2528040497398",
        tax_breakup=TaxBreakup(
            tax_a=22500.00,
            tax_b=0.0,
            tax_c=0.0,
            tax_d=0.0,
            tax_e=0.0,
            tax_f=0.0
        ),
        source_file="25100700523936HDFC_ChallanReceipt- For other Testing.pdf",
        row_confidence=0.95,
        validation_flag=ValidationStatus.OK
    )


@pytest.fixture
def sample_record_3() -> ChallanRecord:
    """Sample record matching third PDF."""
    return ChallanRecord(
        tan="BLRS05586H",
        deductor_name="SYAMBHAVAN FOODS LLP",
        assessment_year="2026-27",
        financial_year="2025-26",
        major_head="Income Tax (Other than Companies) (0021)",
        minor_head="TDS/TCS Payable by Taxpayer (200)",
        nature_of_payment="94T",
        total_amount=40000.00,
        amount_in_words="Rupees Forty Thousand Only",
        cin="25100700528930HDFC",
        bsr_code="0510016",
        challan_no="15903",
        date_of_deposit=date(2025, 10, 7),
        bank_name="HDFC Bank",
        bank_ref_no="N2528040498645",
        tax_breakup=TaxBreakup(
            tax_a=40000.00,
            tax_b=0.0,
            tax_c=0.0,
            tax_d=0.0,
            tax_e=0.0,
            tax_f=0.0
        ),
        source_file="25100700528930HDFC_ChallanReceipt- For other Testing.pdf",
        row_confidence=0.95,
        validation_flag=ValidationStatus.OK
    )


@pytest.fixture
def flagged_record() -> ChallanRecord:
    """Sample record with sum mismatch (should be flagged)."""
    return ChallanRecord(
        tan="BLRS05586H",
        deductor_name="Test Company",
        total_amount=10000.00,
        cin="TEST123456789HDFC",
        challan_no="99999",
        date_of_deposit=date(2025, 10, 7),
        tax_breakup=TaxBreakup(
            tax_a=5000.00,  # Sum = 5000, but total = 10000 -> mismatch
            tax_b=0.0,
            tax_c=0.0,
            tax_d=0.0,
            tax_e=0.0,
            tax_f=0.0
        ),
        source_file="test.pdf"
    )


# Expected extraction values for assertions
EXPECTED_VALUES = {
    "25100700517216HDFC_ChallanReceipt- Input Command Challan.pdf": {
        "cin": "25100700517216HDFC",
        "total_amount": 19395.00,
        "nature_of_payment": "94J",
        "date_of_deposit": "2025-10-07",
        "tan": "BLRS05586H",
        "challan_no": "12866",
    },
    "25100700523936HDFC_ChallanReceipt- For other Testing.pdf": {
        "cin": "25100700523936HDFC",
        "total_amount": 22500.00,
        "nature_of_payment": "94I",
        "date_of_deposit": "2025-10-07",
        "tan": "BLRS05586H",
        "challan_no": "14644",
    },
    "25100700528930HDFC_ChallanReceipt- For other Testing.pdf": {
        "cin": "25100700528930HDFC",
        "total_amount": 40000.00,
        "nature_of_payment": "94T",
        "date_of_deposit": "2025-10-07",
        "tan": "BLRS05586H",
        "challan_no": "15903",
    },
}


@pytest.fixture
def expected_values():
    """Return expected extraction values for test assertions."""
    return EXPECTED_VALUES
