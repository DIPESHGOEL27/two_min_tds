"""
Text-first PDF extraction using pdfplumber.
This is the primary extraction method for born-digital PDFs.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

import pdfplumber

from config import extraction_config, validation_config
from models import FieldConfidence

logger = logging.getLogger(__name__)


class TextExtractor:
    """Extract text content from PDF using pdfplumber."""

    # Field patterns for regex-based extraction
    FIELD_PATTERNS = {
        "tan": r"TAN\s*:?\s*([A-Z]{4}[0-9]{5}[A-Z])",
        "deductor_name": r"Name\s*:?\s*([A-Z][A-Za-z0-9\s&.,()-]+?)(?=\n|Assessment|$)",
        "assessment_year": r"Assessment\s*Year\s*:?\s*(\d{4}-\d{2})",
        "financial_year": r"Financial\s*Year\s*:?\s*(\d{4}-\d{2})",
        "major_head": r"Major\s*Head\s*:?\s*(.+?)(?=\n|Minor|$)",
        "minor_head": r"Minor\s*Head\s*:?\s*(.+?)(?=\n|Nature|$)",
        "nature_of_payment": r"Nature\s*of\s*Payment\s*:?\s*(\d{2,3}[A-Z]?|\w+)",
        "total_amount": r"Amount\s*\(in\s*Rs\.\)\s*:?\s*[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)",
        "amount_in_words": r"Amount\s*\(in\s*words\)\s*:?\s*(.+?)(?=\n|CIN|$)",
        "cin": r"CIN\s*:?\s*([A-Z0-9]+)",
        "bsr_code": r"BSR\s*[Cc]ode\s*:?\s*(\d+)",
        "challan_no": r"Challan\s*No\.?\s*:?\s*(\d+)",
        "date_of_deposit": r"Date\s*of\s*Deposit\s*:?\s*(\d{2}[-/][A-Za-z]{3}[-/]\d{4}|\d{2}[-/]\d{2}[-/]\d{4})",
        "tender_date": r"Tender\s*Date\s*:?\s*(\d{2}[-/][A-Za-z]{3}[-/]\d{4}|\d{2}[-/]\d{2}[-/]\d{4})",
        "bank_name": r"Bank\s*Name\s*:?\s*([A-Za-z\s]+Bank)",
        "bank_ref_no": r"Bank\s*Reference\s*Number\s*:?\s*([A-Z0-9]+)",
        "mode_of_payment": r"Mode\s*of\s*Payment\s*:?\s*([A-Za-z\s]+)",
    }

    # Tax breakup patterns
    TAX_PATTERNS = {
        "tax_a": r"A\s+Tax\s+[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)",
        "tax_b": r"B\s+Surcharge\s+[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)",
        "tax_c": r"C\s+Cess\s+[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)",
        "tax_d": r"D\s+Interest\s+[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)",
        "tax_e": r"E\s+Penalty\s+[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)",
        "tax_f": r"F\s+Fee\s+under\s+section\s+234E\s+[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)",
    }

    def __init__(self):
        self.config = extraction_config

    def extract(self, pdf_path: Path) -> Tuple[Dict[str, FieldConfidence], str]:
        """
        Extract fields from PDF using text extraction.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (extracted fields dict, raw text)
        """
        logger.info(f"Starting text extraction for: {pdf_path}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # For TDS challans, we expect single-page documents
                if len(pdf.pages) == 0:
                    raise ValueError("PDF has no pages")

                # Extract text from first page (TDS challans are single-page)
                page = pdf.pages[0]
                text = page.extract_text() or ""

                if not text.strip():
                    logger.warning(f"No text extracted from {pdf_path}")
                    return {}, ""

                logger.debug(f"Extracted text length: {len(text)}")

                # Extract all fields
                fields = self._extract_fields(text)
                tax_fields = self._extract_tax_breakup(text)
                fields.update(tax_fields)

                return fields, text

        except Exception as e:
            logger.error(f"Text extraction failed for {pdf_path}: {e}")
            raise

    def _extract_fields(self, text: str) -> Dict[str, FieldConfidence]:
        """Extract main fields using regex patterns."""
        fields = {}

        for field_name, pattern in self.FIELD_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)

            if match:
                raw_value = match.group(1).strip()
                cleaned_value = self._clean_value(field_name, raw_value)

                # Calculate confidence based on pattern match quality
                confidence = self._calculate_field_confidence(field_name, raw_value, cleaned_value)

                fields[field_name] = FieldConfidence(
                    value=cleaned_value,
                    confidence=confidence,
                    extraction_method="text_regex",
                    raw_text=raw_value
                )
                logger.debug(f"Extracted {field_name}: {cleaned_value} (conf: {confidence:.2f})")
            else:
                logger.debug(f"Field not found: {field_name}")

        return fields

    def _extract_tax_breakup(self, text: str) -> Dict[str, FieldConfidence]:
        """Extract tax breakup fields (A-F)."""
        fields = {}

        for field_name, pattern in self.TAX_PATTERNS.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)

            if match:
                raw_value = match.group(1).strip()
                # Parse numeric value
                numeric_value = self._parse_amount(raw_value)

                fields[field_name] = FieldConfidence(
                    value=numeric_value,
                    confidence=0.95 if numeric_value is not None else 0.5,
                    extraction_method="text_regex",
                    raw_text=raw_value
                )
            else:
                # Default to 0 if not found (common for surcharge, cess etc.)
                fields[field_name] = FieldConfidence(
                    value=0.0,
                    confidence=0.8,  # High confidence for 0 default
                    extraction_method="default",
                    raw_text=None
                )

        return fields

    def _clean_value(self, field_name: str, value: str) -> Any:
        """Clean and normalize extracted values."""
        if not value:
            return None

        value = value.strip()

        # Field-specific cleaning
        if field_name == "total_amount":
            return self._parse_amount(value)

        elif field_name in ("date_of_deposit", "tender_date"):
            return self._parse_date(value)

        elif field_name == "tan":
            # TAN should be uppercase alphanumeric
            return value.upper().strip()

        elif field_name == "cin":
            return value.upper().strip()

        elif field_name == "nature_of_payment":
            # Extract just the code (e.g., "94J", "94I")
            match = re.search(r"(\d{2,3}[A-Z]?)", value)
            return match.group(1) if match else value

        elif field_name == "deductor_name":
            # Clean up name - remove extra whitespace
            return " ".join(value.split())

        elif field_name in ("major_head", "minor_head"):
            # Clean up head descriptions
            return " ".join(value.split())

        return value

    def _parse_amount(self, value: str) -> Optional[float]:
        """Parse currency amount from string."""
        if not value:
            return None

        # Remove currency symbols, commas, and whitespace
        cleaned = re.sub(r"[₹Rs.,\s]", "", value)

        try:
            return float(cleaned)
        except ValueError:
            logger.warning(f"Could not parse amount: {value}")
            return None

    def _parse_date(self, value: str) -> Optional[str]:
        """Parse date string to ISO format."""
        if not value:
            return None

        for fmt in validation_config.date_formats:
            try:
                parsed = datetime.strptime(value, fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {value}")
        return None

    def _calculate_field_confidence(
        self,
        field_name: str,
        raw_value: str,
        cleaned_value: Any
    ) -> float:
        """Calculate confidence score for extracted field."""
        if cleaned_value is None:
            return 0.3  # Low confidence if parsing failed

        base_confidence = 0.9  # High base for successful regex match

        # Adjust based on field type
        if field_name == "tan":
            # Validate TAN format
            if re.match(validation_config.tan_pattern, str(cleaned_value)):
                return 0.98
            return 0.6

        elif field_name == "cin":
            # CIN should be reasonably long
            if len(str(cleaned_value)) >= validation_config.cin_min_length:
                return 0.95
            return 0.7

        elif field_name == "total_amount":
            # Numeric value successfully parsed
            if isinstance(cleaned_value, (int, float)) and cleaned_value > 0:
                return 0.95
            return 0.6

        elif field_name in ("date_of_deposit", "tender_date"):
            # Date successfully parsed
            if cleaned_value:
                return 0.95
            return 0.5

        return base_confidence


def extract_text_from_pdf(pdf_path: Path) -> Tuple[Dict[str, FieldConfidence], str]:
    """Convenience function for text extraction."""
    extractor = TextExtractor()
    return extractor.extract(pdf_path)
