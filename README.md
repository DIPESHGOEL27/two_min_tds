# TDS Challan Processor

A production-ready application for extracting, validating, and exporting TDS (Tax Deducted at Source) Challan data from PDF documents.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           TDS Challan Processor                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     ┌──────────────────────────────────────────────┐  │
│  │   Streamlit  │────▶│              Processing Pipeline              │  │
│  │   Dashboard  │     │                                              │  │
│  │  (Port 8501) │     │  ┌────────────┐  ┌────────────┐  ┌────────┐  │  │
│  └──────────────┘     │  │   Text     │  │  Layout    │  │  OCR   │  │  │
│         │             │  │ Extractor  │─▶│ Extractor  │─▶│Fallback│  │  │
│         │             │  └────────────┘  └────────────┘  └────────┘  │  │
│         ▼             │         │              │              │       │  │
│  ┌──────────────┐     │         └──────────────┴──────────────┘       │  │
│  │   FastAPI    │     │                        │                      │  │
│  │   Backend    │────▶│                        ▼                      │  │
│  │  (Port 8000) │     │              ┌─────────────────┐              │  │
│  └──────────────┘     │              │    Validation   │              │  │
│                       │              │   & Confidence  │              │  │
│                       │              └─────────────────┘              │  │
│                       │                        │                      │  │
│                       │                        ▼                      │  │
│                       │              ┌─────────────────┐              │  │
│                       │              │  Excel Export   │              │  │
│                       │              └─────────────────┘              │  │
│                       └──────────────────────────────────────────────┘  │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         Data Storage                                │ │
│  │   uploads/  │  output/  │  logs/                                   │ │
│  └────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-pass PDF Extraction**: Text-first extraction with layout-aware and OCR fallback
- **Robust Validation**: Sum checks, date normalization, TAN/CIN validation, deduplication
- **Human-in-the-Loop Review**: Web UI for reviewing and correcting extracted data
- **Excel Export**: Generates formatted Excel reports matching specified schema
- **Confidence Scoring**: Per-field and per-row confidence scores for quality assessment
- **Containerized Deployment**: Docker and docker-compose for easy deployment
- **Comprehensive Testing**: Unit, integration, and end-to-end tests

## Quick Start

### Local Installation

1. **Clone and navigate to the project:**

   ```bash
   cd two_min_tds
   ```

2. **Create virtual environment:**

   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install Tesseract OCR (for scanned PDFs):**

   ```bash
   # Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
   # Linux: sudo apt-get install tesseract-ocr
   # Mac: brew install tesseract
   ```

5. **Run the Streamlit app:**

   ```bash
   streamlit run streamlit_app.py
   ```

6. **Open browser:** Navigate to http://localhost:8501

### Docker Deployment (Local)

1. **Build and run with docker-compose:**

   ```bash
   docker-compose up --build
   ```

2. **Access the services:**
   - Streamlit UI: http://localhost:8501
   - FastAPI Backend: http://localhost:8000
   - API Documentation: http://localhost:8000/docs

### AWS Cloud Deployment

Deploy to AWS ECS Fargate for production use:

#### Quick Deploy (Automated)

**Windows:**

```powershell
.\deploy-to-aws.ps1 -Environment production -Region us-east-1
```

**Linux/Mac:**

```bash
chmod +x deploy-to-aws.sh
./deploy-to-aws.sh production
```

#### Manual Deploy

See detailed guides:

- **Quick Start:** [QUICKSTART_AWS.md](QUICKSTART_AWS.md)
- **Full Guide:** [AWS_DEPLOYMENT.md](AWS_DEPLOYMENT.md)

#### Features

- ✅ Auto-scaling ECS Fargate
- ✅ Application Load Balancer
- ✅ EFS persistent storage
- ✅ CloudWatch monitoring
- ✅ GitHub Actions CI/CD
- ✅ SSL/TLS support

**Estimated Cost:** ~$70/month for production

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_extraction.py

# Run with verbose output
pytest -v

# Run only end-to-end tests
pytest tests/test_e2e.py
```

## Project Structure

```
two_min_tds/
├── api/                      # FastAPI backend
│   ├── __init__.py
│   └── main.py              # API endpoints
├── config/                   # Configuration
│   ├── __init__.py
│   └── settings.py          # Centralized settings
├── extraction/               # PDF extraction pipeline
│   ├── __init__.py
│   ├── pipeline.py          # Main extraction orchestrator
│   ├── text_extractor.py    # Text-based extraction
│   ├── layout_extractor.py  # Layout-aware extraction
│   └── ocr_extractor.py     # OCR fallback
├── export/                   # Excel export
│   ├── __init__.py
│   └── excel_writer.py      # Excel generation
├── models/                   # Data models
│   ├── __init__.py
│   └── challan.py           # Pydantic models
├── validation/               # Validation rules
│   ├── __init__.py
│   └── validator.py         # Validation logic
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Test fixtures
│   ├── test_extraction.py   # Extraction tests
│   ├── test_validation.py   # Validation tests
│   ├── test_excel_export.py # Export tests
│   ├── test_e2e.py          # End-to-end tests
│   └── test_api.py          # API tests
├── TDS Challans for Testing/ # Sample PDFs
├── streamlit_app.py         # Streamlit UI
├── Dockerfile               # Streamlit container
├── Dockerfile.api           # API container
├── docker-compose.yml       # Container orchestration
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── CLAUDE.md                # AI assistant instructions
└── README.md                # This file
```

## Excel Output Schema

| Column            | Type              | Description                     |
| ----------------- | ----------------- | ------------------------------- |
| TAN               | string            | Tax Deduction Account Number    |
| Deductor Name     | string            | Name of the deductor            |
| Assessment Year   | string            | Assessment year (e.g., 2026-27) |
| Financial Year    | string            | Financial year (e.g., 2025-26)  |
| Major Head        | string            | Tax major head description      |
| Minor Head        | string            | Tax minor head description      |
| Nature of Payment | string            | Payment type code (e.g., 94J)   |
| Total Amount      | float             | Total challan amount            |
| Amount in Words   | string            | Amount written in words         |
| CIN               | string            | Challan Identification Number   |
| BSR Code          | string            | Bank BSR code                   |
| Challan No        | string            | Challan serial number           |
| Date of Deposit   | date (YYYY-MM-DD) | Payment date                    |
| Bank Name         | string            | Bank name                       |
| Bank Ref No       | string            | Bank reference number           |
| Tax_A             | float             | Tax amount                      |
| Tax_B             | float             | Surcharge                       |
| Tax_C             | float             | Cess                            |
| Tax_D             | float             | Interest                        |
| Tax_E             | float             | Penalty                         |
| Tax_F             | float             | Fee under section 234E          |
| Source File       | string            | Original PDF filename           |
| Row Confidence    | float (0-1)       | Extraction confidence score     |
| Validation Flag   | string            | OK or FLAG                      |
| Notes             | string            | Validation issues/notes         |

### Sample Row

```
TAN: BLRS05586H
Deductor Name: SYAMBHAVAN FOODS LLP
Assessment Year: 2026-27
Financial Year: 2025-26
Major Head: Corporation Tax (0020)
Minor Head: TDS/TCS Payable by Taxpayer (200)
Nature of Payment: 94J
Total Amount: 19395.00
CIN: 25100700517216HDFC
BSR Code: 0510016
Challan No: 12866
Date of Deposit: 2025-10-07
Bank Name: HDFC Bank
Tax_A: 19395.00
Tax_B-F: 0.00
Row Confidence: 0.95
Validation Flag: OK
```

## Configuration

All configuration is centralized in `config/settings.py` and can be overridden via environment variables.

### Key Settings

| Setting                              | Default | Description                  |
| ------------------------------------ | ------- | ---------------------------- |
| `TDS_EXTRACTION_MIN_ROW_CONFIDENCE`  | 0.85    | Threshold for manual review  |
| `TDS_VALIDATION_SUM_CHECK_TOLERANCE` | 1.0     | Max allowed sum mismatch (₹) |
| `TDS_EXTRACTION_OCR_DPI`             | 300     | OCR resolution               |
| `TDS_APP_FILE_RETENTION_HOURS`       | 24      | File cleanup period          |

See `.env.example` for all available options.

## Extraction Strategy

The pipeline uses a multi-pass approach for maximum accuracy:

1. **Text-first**: Uses `pdfplumber` to extract text and regex patterns
2. **Layout-aware**: Analyzes bounding boxes and spatial relationships
3. **OCR fallback**: For scanned PDFs, uses OpenCV preprocessing + Tesseract
4. **Merge results**: Combines extractions with confidence weighting

### Confidence Calculation

Row confidence is a weighted average of field confidences:

- **High weight (3.0)**: TAN, CIN, Total Amount
- **Medium weight (2.0)**: Date of Deposit, Challan No
- **Standard weight (1.0)**: Other fields

Records with confidence below 0.85 require manual review.

## Validation Rules

1. **Sum Check**: `Tax_A + Tax_B + ... + Tax_F` must equal `Total Amount` (±₹1.0)
2. **TAN Format**: Must match pattern `[A-Z]{4}[0-9]{5}[A-Z]`
3. **Date Parsing**: Normalized to ISO format (YYYY-MM-DD)
4. **Deduplication**: Hash of `CIN + Challan No + Date` detects duplicates
5. **Required Fields**: TAN, CIN, Amount, Date must be present

## Security & Privacy

- **File Retention**: Uploaded PDFs are stored temporarily (default: 24 hours)
- **Sensitive Data Masking**: PII can be masked in logs (configurable)
- **No External Network**: Processing runs entirely locally
- **Audit Logging**: All operations are logged for auditability

### Data Handling

```bash
# Uploaded files location
uploads/

# Generated outputs
output/

# To purge all data
rm -rf uploads/* output/* logs/*
```

## API Reference

### Endpoints

| Method | Endpoint                        | Description           |
| ------ | ------------------------------- | --------------------- |
| GET    | `/`                             | Health check          |
| POST   | `/upload`                       | Upload PDF files      |
| POST   | `/process/{session_id}`         | Start processing      |
| GET    | `/status/{session_id}`          | Get processing status |
| GET    | `/records/{session_id}`         | Get extracted records |
| PUT    | `/records/{session_id}/{index}` | Update a record       |
| POST   | `/export/{session_id}`          | Export to Excel       |
| DELETE | `/session/{session_id}`         | Delete session        |

Full API documentation available at http://localhost:8000/docs when running.

## Improving Accuracy

### Tunable Parameters

1. **Confidence Threshold**: Lower `MIN_ROW_CONFIDENCE` to accept more records automatically
2. **Sum Tolerance**: Adjust `SUM_CHECK_TOLERANCE` for stricter/looser validation
3. **OCR Settings**: Modify `OCR_DPI`, preprocessing parameters for better OCR results

### Adding ML Model Fallback

The architecture supports ML model integration. To add:

1. Set `TDS_APP_ENABLE_ML_FALLBACK=true`
2. Implement model wrapper in `extraction/ml_extractor.py`
3. Suggested models: LayoutLM, Donut, DocTR

## Troubleshooting

### Common Issues

**OCR not working:**

```bash
# Verify Tesseract is installed
tesseract --version

# Check language data
tesseract --list-langs
```

**PDF extraction fails:**

```bash
# Check pdfplumber can read the file
python -c "import pdfplumber; print(pdfplumber.open('file.pdf').pages[0].extract_text())"
```

**Docker build fails:**

```bash
# Clear Docker cache
docker system prune -a
docker-compose build --no-cache
```

## License

Internal use only. All rights reserved.

## Support

For issues and questions, contact the development team.
