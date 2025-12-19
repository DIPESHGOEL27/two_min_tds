"""
Validation rules for extracted TDS Challan records.
Implements strict validation with sum checks, date normalization, and deduplication.
"""

import re
import logging
import hashlib
from datetime import datetime, date
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field

from config import validation_config
from models import ChallanRecord, ValidationStatus, TaxBreakup

logger = logging.getLogger(__name__)


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""
    field: str
    issue_type: str
    message: str
    severity: str = "error"  # error, warning, info


@dataclass
class ValidationResult:
    """Result of validation for a single record."""
    record_id: str
    is_valid: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    original_values: Dict[str, any] = field(default_factory=dict)
    corrected_values: Dict[str, any] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)


class ChallanValidator:
    """Validator for TDS Challan records."""

    def __init__(self):
        self.config = validation_config
        self._seen_hashes: Set[str] = set()

    def reset_dedupe_cache(self):
        """Reset the deduplication cache."""
        self._seen_hashes.clear()

    def validate(self, record: ChallanRecord) -> ValidationResult:
        """
        Validate a single challan record.

        Args:
            record: ChallanRecord to validate

        Returns:
            ValidationResult with issues and corrections
        """
        result = ValidationResult(
            record_id=record.record_hash or record.cin or "unknown",
            is_valid=True
        )

        # Run all validation rules
        self._validate_tan(record, result)
        self._validate_cin(record, result)
        self._validate_amounts(record, result)
        self._validate_sum_check(record, result)
        self._validate_dates(record, result)
        self._validate_required_fields(record, result)
        self._check_duplicate(record, result)

        # Update record validation flag based on results
        if result.has_errors:
            record.validation_flag = ValidationStatus.FLAG
            result.is_valid = False
        else:
            record.validation_flag = ValidationStatus.OK

        # Add issues to record notes
        if result.issues:
            issues_text = "; ".join(f"{i.field}: {i.message}" for i in result.issues)
            record.notes = issues_text

        return result

    def validate_batch(self, records: List[ChallanRecord]) -> List[ValidationResult]:
        """
        Validate a batch of records with deduplication across the batch.

        Args:
            records: List of ChallanRecords

        Returns:
            List of ValidationResults
        """
        self.reset_dedupe_cache()
        results = []

        for record in records:
            result = self.validate(record)
            results.append(result)

        return results

    def _validate_tan(self, record: ChallanRecord, result: ValidationResult):
        """Validate TAN format."""
        if not record.tan:
            result.issues.append(ValidationIssue(
                field="tan",
                issue_type="missing",
                message="TAN is missing",
                severity="error"
            ))
            return

        # TAN format: 4 letters + 5 digits + 1 letter (e.g., BLRS05586H)
        if not re.match(self.config.tan_pattern, record.tan):
            result.issues.append(ValidationIssue(
                field="tan",
                issue_type="format",
                message=f"Invalid TAN format: {record.tan}",
                severity="error"
            ))

    def _validate_cin(self, record: ChallanRecord, result: ValidationResult):
        """Validate CIN format and length."""
        if not record.cin:
            result.issues.append(ValidationIssue(
                field="cin",
                issue_type="missing",
                message="CIN is missing",
                severity="error"
            ))
            return

        if len(record.cin) < self.config.cin_min_length:
            result.issues.append(ValidationIssue(
                field="cin",
                issue_type="format",
                message=f"CIN too short: {record.cin} (min {self.config.cin_min_length} chars)",
                severity="warning"
            ))

    def _validate_amounts(self, record: ChallanRecord, result: ValidationResult):
        """Validate amount values are reasonable."""
        if record.total_amount is None:
            result.issues.append(ValidationIssue(
                field="total_amount",
                issue_type="missing",
                message="Total amount is missing",
                severity="error"
            ))
            return

        if record.total_amount < 0:
            result.issues.append(ValidationIssue(
                field="total_amount",
                issue_type="invalid",
                message=f"Negative total amount: {record.total_amount}",
                severity="error"
            ))

        if record.total_amount == 0:
            result.issues.append(ValidationIssue(
                field="total_amount",
                issue_type="suspicious",
                message="Total amount is zero",
                severity="warning"
            ))

    def _validate_sum_check(self, record: ChallanRecord, result: ValidationResult):
        """
        Validate that Tax_A + Tax_B + ... + Tax_F equals Total Amount.

        This is a critical validation for financial accuracy.
        """
        if record.total_amount is None:
            return  # Already flagged as missing

        tax_sum = record.tax_breakup.total
        difference = abs(tax_sum - record.total_amount)

        if difference > self.config.sum_check_tolerance:
            result.issues.append(ValidationIssue(
                field="tax_breakup",
                issue_type="sum_mismatch",
                message=f"Tax breakup sum ({tax_sum:.2f}) != Total amount ({record.total_amount:.2f}), diff={difference:.2f}",
                severity="error"
            ))
            result.original_values["tax_sum"] = tax_sum
            result.original_values["total_amount"] = record.total_amount

    def _validate_dates(self, record: ChallanRecord, result: ValidationResult):
        """Validate and normalize dates."""
        # Date of deposit
        if not record.date_of_deposit:
            result.issues.append(ValidationIssue(
                field="date_of_deposit",
                issue_type="missing",
                message="Date of deposit is missing",
                severity="error"
            ))
        else:
            # Check if date is reasonable (not in far future or past)
            today = date.today()
            deposit_date = record.date_of_deposit

            if deposit_date > today:
                result.issues.append(ValidationIssue(
                    field="date_of_deposit",
                    issue_type="future_date",
                    message=f"Date of deposit is in future: {deposit_date}",
                    severity="warning"
                ))

            # More than 10 years old
            if (today - deposit_date).days > 3650:
                result.issues.append(ValidationIssue(
                    field="date_of_deposit",
                    issue_type="old_date",
                    message=f"Date of deposit is more than 10 years old: {deposit_date}",
                    severity="warning"
                ))

    def _validate_required_fields(self, record: ChallanRecord, result: ValidationResult):
        """Check all required fields are present."""
        required = {
            "challan_no": record.challan_no,
            "bsr_code": record.bsr_code,
            "bank_name": record.bank_name,
            "deductor_name": record.deductor_name,
        }

        for field_name, value in required.items():
            if not value:
                result.issues.append(ValidationIssue(
                    field=field_name,
                    issue_type="missing",
                    message=f"{field_name.replace('_', ' ').title()} is missing",
                    severity="warning"
                ))

    def _check_duplicate(self, record: ChallanRecord, result: ValidationResult):
        """Check for duplicate records using hash."""
        record_hash = record.compute_hash()

        if record_hash in self._seen_hashes:
            result.issues.append(ValidationIssue(
                field="record",
                issue_type="duplicate",
                message=f"Duplicate record detected (hash: {record_hash})",
                severity="error"
            ))
        else:
            self._seen_hashes.add(record_hash)


def validate_record(record: ChallanRecord) -> ValidationResult:
    """Convenience function to validate a single record."""
    validator = ChallanValidator()
    return validator.validate(record)


def validate_batch(records: List[ChallanRecord]) -> List[ValidationResult]:
    """Convenience function to validate a batch of records."""
    validator = ChallanValidator()
    return validator.validate_batch(records)
