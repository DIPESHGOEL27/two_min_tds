"""
Layout-aware PDF extraction using bounding boxes.
Uses spatial relationships between labels and values for extraction.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass

import pdfplumber

from config import extraction_config
from models import FieldConfidence

logger = logging.getLogger(__name__)


@dataclass
class TextBlock:
    """Represents a text block with position information."""
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float = 1.0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


class LayoutExtractor:
    """Extract fields using spatial layout analysis."""

    # Label keywords to look for
    LABEL_KEYWORDS = {
        "tan": ["TAN"],
        "deductor_name": ["Name"],
        "assessment_year": ["Assessment Year"],
        "financial_year": ["Financial Year"],
        "major_head": ["Major Head"],
        "minor_head": ["Minor Head"],
        "nature_of_payment": ["Nature of Payment"],
        "total_amount": ["Amount (in Rs.)", "Amount(in Rs.)"],
        "amount_in_words": ["Amount (in words)", "Amount(in words)"],
        "cin": ["CIN"],
        "bsr_code": ["BSR code", "BSR Code"],
        "challan_no": ["Challan No", "Challan No."],
        "date_of_deposit": ["Date of Deposit"],
        "tender_date": ["Tender Date"],
        "bank_name": ["Bank Name"],
        "bank_ref_no": ["Bank Reference Number"],
        "mode_of_payment": ["Mode of Payment"],
    }

    def __init__(self):
        self.config = extraction_config

    def extract(self, pdf_path: Path) -> Dict[str, FieldConfidence]:
        """
        Extract fields using layout-aware analysis.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dictionary of extracted fields with confidence scores
        """
        logger.info(f"Starting layout extraction for: {pdf_path}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                if len(pdf.pages) == 0:
                    raise ValueError("PDF has no pages")

                page = pdf.pages[0]

                # Get words with bounding boxes
                words = page.extract_words(
                    keep_blank_chars=True,
                    x_tolerance=3,
                    y_tolerance=3,
                    extra_attrs=["fontname", "size"]
                )

                if not words:
                    logger.warning(f"No words extracted from {pdf_path}")
                    return {}

                # Convert to TextBlock objects
                text_blocks = self._words_to_blocks(words)

                # Group into lines
                lines = self._group_into_lines(text_blocks)

                # Extract fields using layout
                fields = self._extract_fields_from_layout(lines, text_blocks)

                # Extract tax breakup table
                tax_fields = self._extract_tax_table(lines, text_blocks)
                fields.update(tax_fields)

                return fields

        except Exception as e:
            logger.error(f"Layout extraction failed for {pdf_path}: {e}")
            raise

    def _words_to_blocks(self, words: List[Dict]) -> List[TextBlock]:
        """Convert pdfplumber words to TextBlock objects."""
        blocks = []
        for w in words:
            blocks.append(TextBlock(
                text=w.get("text", ""),
                x0=w.get("x0", 0),
                y0=w.get("top", 0),
                x1=w.get("x1", 0),
                y1=w.get("bottom", 0),
            ))
        return blocks

    def _group_into_lines(self, blocks: List[TextBlock], y_tolerance: float = 5) -> List[List[TextBlock]]:
        """Group text blocks into lines based on Y position."""
        if not blocks:
            return []

        # Sort by Y then X
        sorted_blocks = sorted(blocks, key=lambda b: (b.y0, b.x0))

        lines = []
        current_line = [sorted_blocks[0]]
        current_y = sorted_blocks[0].y0

        for block in sorted_blocks[1:]:
            if abs(block.y0 - current_y) <= y_tolerance:
                current_line.append(block)
            else:
                # Sort current line by X position
                lines.append(sorted(current_line, key=lambda b: b.x0))
                current_line = [block]
                current_y = block.y0

        if current_line:
            lines.append(sorted(current_line, key=lambda b: b.x0))

        return lines

    def _extract_fields_from_layout(
        self,
        lines: List[List[TextBlock]],
        all_blocks: List[TextBlock]
    ) -> Dict[str, FieldConfidence]:
        """Extract fields by finding labels and their corresponding values."""
        fields = {}

        for field_name, label_keywords in self.LABEL_KEYWORDS.items():
            for keyword in label_keywords:
                value_block = self._find_value_for_label(keyword, lines, all_blocks)
                if value_block:
                    fields[field_name] = FieldConfidence(
                        value=value_block.text.strip(),
                        confidence=0.85,
                        extraction_method="layout",
                        raw_text=value_block.text
                    )
                    break

        return fields

    def _find_value_for_label(
        self,
        label: str,
        lines: List[List[TextBlock]],
        all_blocks: List[TextBlock]
    ) -> Optional[TextBlock]:
        """Find the value block corresponding to a label."""
        label_lower = label.lower()

        for line_idx, line in enumerate(lines):
            # Build line text
            line_text = " ".join(b.text for b in line).lower()

            if label_lower in line_text:
                # Found the label line - look for value
                # Strategy 1: Look for ":" separator and get text after
                colon_idx = None
                for idx, block in enumerate(line):
                    if ":" in block.text:
                        colon_idx = idx
                        break

                if colon_idx is not None:
                    # Check if there's text after colon in same block
                    colon_block = line[colon_idx]
                    after_colon = colon_block.text.split(":", 1)
                    if len(after_colon) > 1 and after_colon[1].strip():
                        return TextBlock(
                            text=after_colon[1].strip(),
                            x0=colon_block.x0,
                            y0=colon_block.y0,
                            x1=colon_block.x1,
                            y1=colon_block.y1
                        )

                    # Look for next blocks on same line
                    if colon_idx + 1 < len(line):
                        remaining = line[colon_idx + 1:]
                        value_text = " ".join(b.text for b in remaining)
                        if value_text.strip():
                            return TextBlock(
                                text=value_text.strip(),
                                x0=remaining[0].x0,
                                y0=remaining[0].y0,
                                x1=remaining[-1].x1,
                                y1=remaining[-1].y1
                            )

                # Strategy 2: Look at next line
                if line_idx + 1 < len(lines):
                    next_line = lines[line_idx + 1]
                    # Check if next line is likely a value (not another label)
                    next_text = " ".join(b.text for b in next_line)
                    if not any(kw.lower() in next_text.lower() for kws in self.LABEL_KEYWORDS.values() for kw in kws):
                        return TextBlock(
                            text=next_text.strip(),
                            x0=next_line[0].x0,
                            y0=next_line[0].y0,
                            x1=next_line[-1].x1,
                            y1=next_line[-1].y1
                        )

        return None

    def _extract_tax_table(
        self,
        lines: List[List[TextBlock]],
        all_blocks: List[TextBlock]
    ) -> Dict[str, FieldConfidence]:
        """Extract tax breakup table (A-F values)."""
        fields = {}

        tax_labels = {
            "tax_a": ["A", "Tax"],
            "tax_b": ["B", "Surcharge"],
            "tax_c": ["C", "Cess"],
            "tax_d": ["D", "Interest"],
            "tax_e": ["E", "Penalty"],
            "tax_f": ["F", "Fee"],
        }

        for line in lines:
            line_text = " ".join(b.text for b in line)

            for field_name, identifiers in tax_labels.items():
                if field_name in fields:
                    continue

                # Check if this line contains the tax identifier
                if identifiers[0] in [b.text.strip() for b in line] or identifiers[1].lower() in line_text.lower():
                    # Look for amount pattern in this line
                    amount_match = re.search(r"[₹Rs.\s]*([0-9,]+(?:\.\d{2})?)\s*$", line_text)
                    if amount_match:
                        amount_str = amount_match.group(1)
                        try:
                            amount = float(amount_str.replace(",", ""))
                            fields[field_name] = FieldConfidence(
                                value=amount,
                                confidence=0.9,
                                extraction_method="layout_table",
                                raw_text=amount_str
                            )
                        except ValueError:
                            pass

        # Fill missing tax fields with 0
        for field_name in tax_labels:
            if field_name not in fields:
                fields[field_name] = FieldConfidence(
                    value=0.0,
                    confidence=0.7,
                    extraction_method="default",
                    raw_text=None
                )

        return fields


def extract_layout_from_pdf(pdf_path: Path) -> Dict[str, FieldConfidence]:
    """Convenience function for layout extraction."""
    extractor = LayoutExtractor()
    return extractor.extract(pdf_path)
