"""
Central configuration for TDS Challan Processor.
All tunable parameters are exposed here with sensible defaults.
"""

from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class ExtractionConfig(BaseSettings):
    """Configuration for PDF extraction pipeline."""

    # Confidence thresholds
    min_field_confidence: float = Field(
        default=0.7,
        description="Minimum confidence for individual field extraction"
    )
    min_row_confidence: float = Field(
        default=0.85,
        description="Below this threshold, record requires manual review"
    )

    # Field weights for row confidence calculation
    weight_tan: float = 3.0
    weight_cin: float = 3.0
    weight_total_amount: float = 3.0
    weight_date: float = 2.0
    weight_other: float = 1.0

    # OCR settings
    ocr_dpi: int = 300
    ocr_language: str = "eng"
    ocr_psm: int = 6  # Page segmentation mode: assume uniform block of text

    # Image preprocessing for OCR
    denoise_strength: int = 10
    adaptive_threshold_block_size: int = 11
    adaptive_threshold_c: int = 2

    # Bounding box proximity (pixels) for layout-aware matching
    label_value_max_distance_x: int = 300
    label_value_max_distance_y: int = 50

    class Config:
        env_prefix = "TDS_EXTRACTION_"


class ValidationConfig(BaseSettings):
    """Configuration for validation rules."""

    # Sum check tolerance (in rupees)
    sum_check_tolerance: float = Field(
        default=1.0,
        description="Max allowed difference between Tax_A-F sum and Total Amount"
    )

    # Date formats to try when parsing
    date_formats: list = Field(
        default=[
            "%d-%b-%Y",      # 07-Oct-2025
            "%d/%m/%Y",      # 07/10/2025
            "%Y-%m-%d",      # 2025-10-07
            "%d-%m-%Y",      # 07-10-2025
            "%d %b %Y",      # 07 Oct 2025
            "%d %B %Y",      # 07 October 2025
        ]
    )

    # TAN validation regex pattern
    tan_pattern: str = r"^[A-Z]{4}[0-9]{5}[A-Z]$"

    # CIN validation (should end with bank code like HDFC, ICIC, etc.)
    cin_min_length: int = 15

    class Config:
        env_prefix = "TDS_VALIDATION_"


class AppConfig(BaseSettings):
    """Main application configuration."""

    # Paths
    base_dir: Path = Path(__file__).parent.parent
    uploads_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "uploads")
    output_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "output")
    logs_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "logs")

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Streamlit settings
    streamlit_port: int = 8501

    # File retention (hours) - 0 means keep forever
    file_retention_hours: int = 24

    # Processing
    max_upload_size_mb: int = 50
    max_batch_size: int = 100

    # Logging
    log_level: str = "INFO"
    mask_sensitive_data: bool = True

    # Enable/disable ML fallback
    enable_ml_fallback: bool = False

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    class Config:
        env_prefix = "TDS_APP_"


# Global configuration instances
extraction_config = ExtractionConfig()
validation_config = ValidationConfig()
app_config = AppConfig()
