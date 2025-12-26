"""
Data models for TDS Challan extraction and processing.
"""

from datetime import date, datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from enum import Enum
import hashlib


class ValidationStatus(str, Enum):
    """Validation status for extracted records."""
    OK = "OK"
    FLAG = "FLAG"
    PENDING = "PENDING"


class ReviewStatus(str, Enum):
    """Human review status."""
    PENDING_REVIEW = "PENDING_REVIEW"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CORRECTED = "CORRECTED"


class FieldConfidence(BaseModel):
    """Confidence score for a single extracted field."""
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    extraction_method: str = "unknown"  # text, layout, ocr, ml
    raw_text: Optional[str] = None


class TaxBreakup(BaseModel):
    """Tax breakup details (A-F)."""
    tax_a: float = Field(default=0.0, description="Tax amount")
    tax_b: float = Field(default=0.0, description="Surcharge")
    tax_c: float = Field(default=0.0, description="Cess")
    tax_d: float = Field(default=0.0, description="Interest")
    tax_e: float = Field(default=0.0, description="Penalty")
    tax_f: float = Field(default=0.0, description="Fee under section 234E")

    @property
    def total(self) -> float:
        """Calculate sum of all tax components."""
        return self.tax_a + self.tax_b + self.tax_c + self.tax_d + self.tax_e + self.tax_f


class ChallanRecord(BaseModel):
    """Complete extracted challan record."""

    # Core identification
    tan: Optional[str] = None
    deductor_name: Optional[str] = None
    assessment_year: Optional[str] = None
    financial_year: Optional[str] = None

    # Tax head information
    major_head: Optional[str] = None
    minor_head: Optional[str] = None
    nature_of_payment: Optional[str] = None

    # Amount details
    total_amount: Optional[float] = None
    amount_in_words: Optional[str] = None

    # Challan identification
    cin: Optional[str] = None
    bsr_code: Optional[str] = None
    challan_no: Optional[str] = None
    date_of_deposit: Optional[date] = None
    tender_date: Optional[date] = None

    # Bank details
    bank_name: Optional[str] = None
    bank_ref_no: Optional[str] = None
    mode_of_payment: Optional[str] = None

    # Tax breakup
    tax_breakup: TaxBreakup = Field(default_factory=TaxBreakup)

    # Metadata
    source_file: str = ""
    row_confidence: float = 0.0
    validation_flag: ValidationStatus = ValidationStatus.PENDING
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    notes: str = ""

    # Field-level confidence scores
    field_confidences: Dict[str, FieldConfidence] = Field(default_factory=dict)

    # Deduplication hash
    record_hash: Optional[str] = None

    def compute_hash(self) -> str:
        """Compute deduplication hash based on CIN + ChallanNo + DateOfDeposit."""
        hash_input = f"{self.cin or ''}{self.challan_no or ''}{self.date_of_deposit or ''}"
        self.record_hash = hashlib.sha256(hash_input.encode()).hexdigest()[:16]
        return self.record_hash

    @field_validator('date_of_deposit', 'tender_date', mode='before')
    @classmethod
    def parse_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            # Will be handled by extraction logic
            return None
        return v

    def to_excel_row(self) -> Dict[str, Any]:
        """Convert to dictionary for Excel export."""
        return {
            "TAN": self.tan or "",
            "Deductor Name": self.deductor_name or "",
            "Assessment Year": self.assessment_year or "",
            "Financial Year": self.financial_year or "",
            "Major Head": self.major_head or "",
            "Minor Head": self.minor_head or "",
            "Nature of Payment": self.nature_of_payment or "",
            "Total Amount": self.total_amount or 0.0,
            "Amount in Words": self.amount_in_words or "",
            "CIN": self.cin or "",
            "BSR Code": self.bsr_code or "",
            "Challan No": self.challan_no or "",
            "Date of Deposit": self.date_of_deposit.isoformat() if self.date_of_deposit else "",
            "Bank Name": self.bank_name or "",
            "Bank Ref No": self.bank_ref_no or "",
            "Tax": self.tax_breakup.tax_a,
            "Surcharge": self.tax_breakup.tax_b,
            "Cess": self.tax_breakup.tax_c,
            "Interest": self.tax_breakup.tax_d,
            "Penalty": self.tax_breakup.tax_e,
            "Fee u/s 234E": self.tax_breakup.tax_f,
            "Source File": self.source_file,
            "Row Confidence": round(self.row_confidence, 4),
            "Validation Flag": self.validation_flag.value,
            "Notes": self.notes,
        }


class ExtractionResult(BaseModel):
    """Result of PDF extraction process."""
    success: bool
    record: Optional[ChallanRecord] = None
    error_message: Optional[str] = None
    extraction_method: str = "unknown"
    processing_time_ms: float = 0.0
    warnings: list = Field(default_factory=list)


class BatchResult(BaseModel):
    """Result of batch processing."""
    total_files: int
    successful: int
    failed: int
    flagged: int
    records: list[ChallanRecord] = Field(default_factory=list)
    errors: Dict[str, str] = Field(default_factory=dict)
