"""Data models for TDS Challan Processor."""

from .challan import (
    ChallanRecord,
    TaxBreakup,
    FieldConfidence,
    ValidationStatus,
    ReviewStatus,
    ExtractionResult,
    BatchResult,
)

__all__ = [
    "ChallanRecord",
    "TaxBreakup",
    "FieldConfidence",
    "ValidationStatus",
    "ReviewStatus",
    "ExtractionResult",
    "BatchResult",
]
