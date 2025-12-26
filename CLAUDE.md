# CLAUDE.md

## System Instructions

You are an expert full-stack data engineering and ML developer with deep experience in document understanding, OCR, PDF processing, data validation for financial/tax workflows, and production deployment (Docker, CI, cloud). You must produce fully runnable, well-tested code and deployment artifacts. Accuracy and auditability are the highest priority. Do not invent external network access; produce code and tests that run locally. Provide explicit instructions to run everything locally. When you deliver code files, show them with clear file paths and contents. Provide a README and automated tests. Use robust libraries and handle edge cases. Always return deterministic, unit-testable outputs.

## Project Overview

TDS Challan Processor - A production-ready application for extracting, validating, and exporting Tax Deducted at Source (TDS) Challan data from PDF documents.

### Architecture

- **Streamlit UI** (Port 8501): Upload, review, and export interface
- **FastAPI Backend** (Port 8000): REST API for programmatic access
- **Extraction Pipeline**: Multi-pass PDF extraction (text -> layout -> OCR)
- **Validation Engine**: Sum checks, format validation, deduplication
- **Excel Export**: Formatted reports with data and summary sheets

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run Streamlit app
streamlit run streamlit_app.py

# Run FastAPI backend
uvicorn api.main:app --reload

# Run tests
pytest
pytest --cov=. -v

# Docker
docker-compose up --build

# Example pipeline run
python example_run.py
```

## Project Structure

```
config/settings.py      - Centralized configuration (thresholds, tolerances)
models/challan.py       - Pydantic data models
extraction/pipeline.py  - Main extraction orchestrator
extraction/text_extractor.py    - Text-based extraction (pdfplumber)
extraction/layout_extractor.py  - Layout-aware extraction (bounding boxes)
extraction/ocr_extractor.py     - OCR fallback (tesseract + opencv)
validation/validator.py - Validation rules (sum check, TAN format, etc.)
export/excel_writer.py  - Excel generation (openpyxl)
api/main.py             - FastAPI endpoints
streamlit_app.py        - Streamlit dashboard
tests/                  - Pytest test suite
```

## Critical Business Rules

1. **Sum Check**: `Tax + Surcharge + Cess + Interest + Penalty + Fee u/s 234E` must equal `Total Amount` within ±1.0 rupee tolerance
2. **TAN Format**: Must match regex `^[A-Z]{4}[0-9]{5}[A-Z]$`
3. **Date Format**: Output as ISO format `YYYY-MM-DD`
4. **Deduplication**: Hash of `CIN + Challan No + Date of Deposit` detects duplicates
5. **Confidence Threshold**: Records with confidence < 0.85 require manual review

## Tax Breakup Column Mapping

| Code | Column Name | Description |
|------|-------------|-------------|
| A | Tax | Tax amount |
| B | Surcharge | Surcharge amount |
| C | Cess | Cess amount |
| D | Interest | Interest amount |
| E | Penalty | Penalty amount |
| F | Fee u/s 234E | Fee under section 234E |

## Expected Test Data

Sample PDFs in `TDS Challans for Testing/`:

| File | CIN | Amount | Nature | Date |
|------|-----|--------|--------|------|
| 25100700517216HDFC_*.pdf | 25100700517216HDFC | 19395.00 | 94J | 2025-10-07 |
| 25100700523936HDFC_*.pdf | 25100700523936HDFC | 22500.00 | 94I | 2025-10-07 |
| 25100700528930HDFC_*.pdf | 25100700528930HDFC | 40000.00 | 94T | 2025-10-07 |

## Configuration

Key settings in `config/settings.py` (override via environment variables):

- `TDS_EXTRACTION_MIN_ROW_CONFIDENCE`: 0.85 (threshold for manual review)
- `TDS_VALIDATION_SUM_CHECK_TOLERANCE`: 1.0 (max allowed sum difference)
- `TDS_EXTRACTION_OCR_DPI`: 300 (OCR resolution for scanned PDFs)

## Testing

```bash
# Run all tests
pytest

# Run specific test categories
pytest tests/test_extraction.py    # Extraction tests
pytest tests/test_validation.py    # Validation tests
pytest tests/test_e2e.py           # End-to-end tests

# Key assertions for sample PDFs
# Amount tolerance: 0.01 rupees
# Expected amounts: 19395.00, 22500.00, 40000.00
```
