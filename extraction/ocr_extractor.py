"""
OCR-based PDF extraction for scanned/image-based PDFs.
Uses OpenCV preprocessing and Tesseract OCR.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
import tempfile
import io

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False
    logging.warning("OpenCV not available - OCR preprocessing disabled")

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logging.warning("Pytesseract not available - OCR extraction disabled")

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    logging.warning("PyMuPDF not available - PDF to image conversion limited")

from config import extraction_config
from models import FieldConfidence

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result from OCR processing."""
    text: str
    confidence: float
    bbox: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h


class OCRExtractor:
    """Extract text from scanned PDFs using OCR."""

    def __init__(self):
        self.config = extraction_config
        self._check_dependencies()

    def _check_dependencies(self):
        """Check if required dependencies are available."""
        if not TESSERACT_AVAILABLE:
            logger.warning("Tesseract OCR not available")
        if not CV2_AVAILABLE:
            logger.warning("OpenCV not available for preprocessing")
        if not PYMUPDF_AVAILABLE:
            logger.warning("PyMuPDF not available for PDF rendering")

    def is_available(self) -> bool:
        """Check if OCR extraction is available."""
        return TESSERACT_AVAILABLE and PYMUPDF_AVAILABLE

    def extract(self, pdf_path: Path) -> Tuple[Dict[str, FieldConfidence], str, float]:
        """
        Extract text from PDF using OCR.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Tuple of (extracted fields, raw OCR text, average confidence)
        """
        if not self.is_available():
            raise RuntimeError("OCR dependencies not available")

        logger.info(f"Starting OCR extraction for: {pdf_path}")

        try:
            # Convert PDF to image
            image = self._pdf_to_image(pdf_path)

            # Preprocess image
            processed = self._preprocess_image(image)

            # Run OCR
            ocr_text, avg_confidence, ocr_data = self._run_ocr(processed)

            logger.debug(f"OCR text length: {len(ocr_text)}, confidence: {avg_confidence:.2f}")

            # Extract fields from OCR text
            fields = self._extract_fields_from_ocr(ocr_text, ocr_data)

            return fields, ocr_text, avg_confidence

        except Exception as e:
            logger.error(f"OCR extraction failed for {pdf_path}: {e}")
            raise

    def _pdf_to_image(self, pdf_path: Path, dpi: int = None) -> np.ndarray:
        """Convert PDF page to image using PyMuPDF."""
        if dpi is None:
            dpi = self.config.ocr_dpi

        doc = fitz.open(pdf_path)
        page = doc[0]  # First page

        # Calculate zoom factor for desired DPI
        zoom = dpi / 72  # PDF default is 72 DPI
        mat = fitz.Matrix(zoom, zoom)

        # Render page to pixmap
        pix = page.get_pixmap(matrix=mat)

        # Convert to numpy array
        img_data = pix.tobytes("png")
        img_array = np.frombuffer(img_data, dtype=np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        doc.close()
        return image

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess image for better OCR results.

        Steps:
        1. Convert to grayscale
        2. Denoise
        3. Adaptive thresholding
        4. Deskew (if needed)
        """
        if not CV2_AVAILABLE:
            return image

        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Denoise
        denoised = cv2.fastNlMeansDenoising(
            gray,
            None,
            self.config.denoise_strength,
            7,
            21
        )

        # Adaptive thresholding
        binary = cv2.adaptiveThreshold(
            denoised,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            self.config.adaptive_threshold_block_size,
            self.config.adaptive_threshold_c
        )

        # Optional: Deskew
        binary = self._deskew(binary)

        return binary

    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """Deskew image if rotated."""
        coords = np.column_stack(np.where(image > 0))
        if len(coords) < 10:
            return image

        angle = cv2.minAreaRect(coords)[-1]

        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90

        # Only deskew if angle is significant
        if abs(angle) > 0.5:
            (h, w) = image.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(
                image, M, (w, h),
                flags=cv2.INTER_CUBIC,
                borderMode=cv2.BORDER_REPLICATE
            )
            return rotated

        return image

    def _run_ocr(self, image: np.ndarray) -> Tuple[str, float, List[Dict]]:
        """
        Run Tesseract OCR on preprocessed image.

        Returns:
            Tuple of (full text, average confidence, per-word data)
        """
        # Convert numpy array to PIL Image
        if len(image.shape) == 2:
            pil_image = Image.fromarray(image)
        else:
            pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))

        # Get detailed OCR data
        custom_config = f"--psm {self.config.ocr_psm} -l {self.config.ocr_language}"
        ocr_data = pytesseract.image_to_data(
            pil_image,
            config=custom_config,
            output_type=pytesseract.Output.DICT
        )

        # Build full text and calculate confidence
        words = []
        confidences = []

        for i, text in enumerate(ocr_data["text"]):
            if text.strip():
                words.append(text)
                conf = ocr_data["conf"][i]
                if conf > 0:  # -1 means no confidence
                    confidences.append(conf)

        full_text = " ".join(words)
        avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0

        # Build per-word data for layout analysis
        word_data = []
        for i, text in enumerate(ocr_data["text"]):
            if text.strip():
                word_data.append({
                    "text": text,
                    "x": ocr_data["left"][i],
                    "y": ocr_data["top"][i],
                    "w": ocr_data["width"][i],
                    "h": ocr_data["height"][i],
                    "conf": ocr_data["conf"][i] / 100 if ocr_data["conf"][i] > 0 else 0.5
                })

        return full_text, avg_confidence, word_data

    def _extract_fields_from_ocr(
        self,
        text: str,
        word_data: List[Dict]
    ) -> Dict[str, FieldConfidence]:
        """Extract fields from OCR text using regex patterns."""
        # Import patterns from text extractor
        from .text_extractor import TextExtractor

        fields = {}
        patterns = TextExtractor.FIELD_PATTERNS
        tax_patterns = TextExtractor.TAX_PATTERNS

        # Extract main fields
        for field_name, pattern in patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                raw_value = match.group(1).strip()
                fields[field_name] = FieldConfidence(
                    value=raw_value,
                    confidence=0.7,  # Lower confidence for OCR
                    extraction_method="ocr",
                    raw_text=raw_value
                )

        # Extract tax breakup
        for field_name, pattern in tax_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
            if match:
                raw_value = match.group(1).strip()
                try:
                    numeric = float(raw_value.replace(",", ""))
                    fields[field_name] = FieldConfidence(
                        value=numeric,
                        confidence=0.75,
                        extraction_method="ocr",
                        raw_text=raw_value
                    )
                except ValueError:
                    pass

        # Fill missing tax fields
        for field_name in tax_patterns:
            if field_name not in fields:
                fields[field_name] = FieldConfidence(
                    value=0.0,
                    confidence=0.6,
                    extraction_method="ocr_default",
                    raw_text=None
                )

        return fields


def extract_ocr_from_pdf(pdf_path: Path) -> Tuple[Dict[str, FieldConfidence], str, float]:
    """Convenience function for OCR extraction."""
    extractor = OCRExtractor()
    return extractor.extract(pdf_path)


def is_ocr_available() -> bool:
    """Check if OCR is available."""
    return OCRExtractor().is_available()
