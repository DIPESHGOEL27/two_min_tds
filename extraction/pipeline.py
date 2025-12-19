"""
Multi-pass extraction pipeline combining text, layout, and OCR methods.
Implements the extraction strategy: text-first -> layout-aware -> OCR fallback.
"""

import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from config import extraction_config, validation_config
from models import (
    ChallanRecord,
    TaxBreakup,
    FieldConfidence,
    ExtractionResult,
    ValidationStatus,
    ReviewStatus,
)
from .text_extractor import TextExtractor
from .layout_extractor import LayoutExtractor
from .ocr_extractor import OCRExtractor, is_ocr_available

logger = logging.getLogger(__name__)


class ExtractionPipeline:
    """
    Multi-pass extraction pipeline for TDS Challan PDFs.

    Extraction strategy:
    1. Text-first: Try pdfplumber text extraction
    2. Layout-aware: Use bounding boxes for spatial analysis
    3. OCR fallback: For scanned/image PDFs
    4. Merge results: Combine with confidence weighting
    """

    # Required fields that must be present
    REQUIRED_FIELDS = ["tan", "cin", "total_amount", "date_of_deposit", "challan_no"]

    # Field weights for row confidence calculation
    FIELD_WEIGHTS = {
        "tan": 3.0,
        "cin": 3.0,
        "total_amount": 3.0,
        "date_of_deposit": 2.0,
        "challan_no": 2.0,
        "deductor_name": 1.5,
        "nature_of_payment": 1.5,
        "bsr_code": 1.0,
    }

    def __init__(self):
        self.config = extraction_config
        self.text_extractor = TextExtractor()
        self.layout_extractor = LayoutExtractor()
        self.ocr_extractor = OCRExtractor() if is_ocr_available() else None

    def process(self, pdf_path: Path) -> ExtractionResult:
        """
        Process a single PDF through the extraction pipeline.

        Args:
            pdf_path: Path to PDF file

        Returns:
            ExtractionResult with extracted record and metadata
        """
        start_time = time.time()
        warnings = []

        try:
            logger.info(f"Processing PDF: {pdf_path}")

            # Stage 1: Text extraction
            text_fields, raw_text = self._try_text_extraction(pdf_path)
            extraction_method = "text"

            # Stage 2: Layout extraction (complement text extraction)
            layout_fields = self._try_layout_extraction(pdf_path)

            # Merge text and layout results
            merged_fields = self._merge_fields(text_fields, layout_fields)

            # Stage 3: Check if we need OCR fallback
            completeness = self._calculate_completeness(merged_fields)

            if completeness < 0.7 and self.ocr_extractor and self.ocr_extractor.is_available():
                logger.info(f"Completeness {completeness:.2f} < 0.7, trying OCR")
                warnings.append(f"Low text extraction completeness ({completeness:.2%}), used OCR fallback")

                ocr_fields, ocr_text, ocr_conf = self._try_ocr_extraction(pdf_path)
                merged_fields = self._merge_fields(merged_fields, ocr_fields)
                extraction_method = "text+ocr"

            # Build challan record from merged fields
            record = self._build_record(merged_fields, pdf_path.name)

            # Calculate row confidence
            record.row_confidence = self._calculate_row_confidence(merged_fields)
            record.field_confidences = {k: v for k, v in merged_fields.items()}

            processing_time = (time.time() - start_time) * 1000

            logger.info(
                f"Extraction complete: {pdf_path.name}, "
                f"confidence={record.row_confidence:.2f}, "
                f"time={processing_time:.0f}ms"
            )

            return ExtractionResult(
                success=True,
                record=record,
                extraction_method=extraction_method,
                processing_time_ms=processing_time,
                warnings=warnings
            )

        except Exception as e:
            logger.error(f"Extraction failed for {pdf_path}: {e}")
            processing_time = (time.time() - start_time) * 1000

            return ExtractionResult(
                success=False,
                error_message=str(e),
                extraction_method="failed",
                processing_time_ms=processing_time
            )

    def _try_text_extraction(self, pdf_path: Path) -> tuple:
        """Attempt text-based extraction."""
        try:
            return self.text_extractor.extract(pdf_path)
        except Exception as e:
            logger.warning(f"Text extraction failed: {e}")
            return {}, ""

    def _try_layout_extraction(self, pdf_path: Path) -> Dict[str, FieldConfidence]:
        """Attempt layout-based extraction."""
        try:
            return self.layout_extractor.extract(pdf_path)
        except Exception as e:
            logger.warning(f"Layout extraction failed: {e}")
            return {}

    def _try_ocr_extraction(self, pdf_path: Path) -> tuple:
        """Attempt OCR-based extraction."""
        try:
            return self.ocr_extractor.extract(pdf_path)
        except Exception as e:
            logger.warning(f"OCR extraction failed: {e}")
            return {}, "", 0.0

    def _merge_fields(
        self,
        primary: Dict[str, FieldConfidence],
        secondary: Dict[str, FieldConfidence]
    ) -> Dict[str, FieldConfidence]:
        """
        Merge two field dictionaries, preferring higher confidence values.

        Args:
            primary: Primary field source (usually text extraction)
            secondary: Secondary field source (layout or OCR)

        Returns:
            Merged dictionary with best values
        """
        merged = dict(primary)

        for field_name, sec_field in secondary.items():
            if field_name not in merged:
                # Field only in secondary
                merged[field_name] = sec_field
            else:
                # Both have the field - take higher confidence
                pri_field = merged[field_name]
                if sec_field.confidence > pri_field.confidence:
                    merged[field_name] = sec_field
                elif sec_field.confidence == pri_field.confidence:
                    # Equal confidence - prefer non-empty value
                    if not pri_field.value and sec_field.value:
                        merged[field_name] = sec_field

        return merged

    def _calculate_completeness(self, fields: Dict[str, FieldConfidence]) -> float:
        """Calculate extraction completeness (0-1)."""
        if not self.REQUIRED_FIELDS:
            return 1.0

        found = sum(
            1 for f in self.REQUIRED_FIELDS
            if f in fields and fields[f].value is not None
        )
        return found / len(self.REQUIRED_FIELDS)

    def _calculate_row_confidence(self, fields: Dict[str, FieldConfidence]) -> float:
        """
        Calculate weighted row confidence from field confidences.

        Higher weight fields (TAN, CIN, Amount) contribute more to the score.
        """
        total_weight = 0.0
        weighted_sum = 0.0

        for field_name, field in fields.items():
            weight = self.FIELD_WEIGHTS.get(field_name, 1.0)
            total_weight += weight
            weighted_sum += weight * field.confidence

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def _build_record(
        self,
        fields: Dict[str, FieldConfidence],
        source_file: str
    ) -> ChallanRecord:
        """Build ChallanRecord from extracted fields."""

        def get_value(field_name: str, default=None):
            if field_name in fields:
                return fields[field_name].value
            return default

        def get_float(field_name: str, default: float = 0.0) -> float:
            val = get_value(field_name)
            if val is None:
                return default
            if isinstance(val, (int, float)):
                return float(val)
            try:
                # Clean and parse string
                cleaned = str(val).replace(",", "").replace("₹", "").replace("Rs.", "").strip()
                return float(cleaned) if cleaned else default
            except (ValueError, TypeError):
                return default

        def parse_date(field_name: str) -> Optional[datetime]:
            val = get_value(field_name)
            if val is None:
                return None
            if isinstance(val, datetime):
                return val.date()
            if isinstance(val, str):
                # Try parsing with various formats
                for fmt in validation_config.date_formats:
                    try:
                        return datetime.strptime(val, fmt).date()
                    except ValueError:
                        continue
                # Try ISO format
                try:
                    return datetime.fromisoformat(val).date()
                except ValueError:
                    pass
            return None

        # Build tax breakup
        tax_breakup = TaxBreakup(
            tax_a=get_float("tax_a"),
            tax_b=get_float("tax_b"),
            tax_c=get_float("tax_c"),
            tax_d=get_float("tax_d"),
            tax_e=get_float("tax_e"),
            tax_f=get_float("tax_f"),
        )

        # Build record
        record = ChallanRecord(
            tan=get_value("tan"),
            deductor_name=get_value("deductor_name"),
            assessment_year=get_value("assessment_year"),
            financial_year=get_value("financial_year"),
            major_head=get_value("major_head"),
            minor_head=get_value("minor_head"),
            nature_of_payment=get_value("nature_of_payment"),
            total_amount=get_float("total_amount"),
            amount_in_words=get_value("amount_in_words"),
            cin=get_value("cin"),
            bsr_code=get_value("bsr_code"),
            challan_no=get_value("challan_no"),
            date_of_deposit=parse_date("date_of_deposit"),
            tender_date=parse_date("tender_date"),
            bank_name=get_value("bank_name"),
            bank_ref_no=get_value("bank_ref_no"),
            mode_of_payment=get_value("mode_of_payment"),
            tax_breakup=tax_breakup,
            source_file=source_file,
        )

        # Compute deduplication hash
        record.compute_hash()

        return record


def process_pdf(pdf_path: Path) -> ExtractionResult:
    """Convenience function to process a single PDF."""
    pipeline = ExtractionPipeline()
    return pipeline.process(pdf_path)


def process_batch(pdf_paths: List[Path]) -> List[ExtractionResult]:
    """Process multiple PDFs."""
    pipeline = ExtractionPipeline()
    results = []

    for pdf_path in pdf_paths:
        result = pipeline.process(pdf_path)
        results.append(result)

    return results
