# Executive Summary

This document provides a **deep technical analysis** and a **programmatic blueprint** for converting uploaded **TDS Challan PDF receipts** into a structured **TDS Excel report**. It explains the **relationship between input PDFs and the output Excel**, the **methodologies**, **frameworks**, and the **mathematical & validation logic** required to ensure correctness, auditability, and scalability.

The goal is to enable **fully automated, low-error TDS report generation** from challan receipts with clear validation flags and extensibility for future formats.

---

# 1. Problem Definition

**Input:**
- Bank-generated TDS Challan PDF receipts (single-page, semi-structured)
- Each PDF represents one challan payment

**Output:**
- A consolidated **TDS Excel sheet**
- One row per challan
- Fully validated amounts, dates, tax breakup, and identifiers

---

# 2. Relationship Between Input PDFs and Output Excel

Each challan PDF contains **key-value fields** and a **tax breakup table**. These map deterministically to Excel columns.

## 2.1 Field Mapping (PDF → Excel)

| PDF Field | Excel Column | Notes |
|---------|-------------|------|
| TAN | TAN | Primary entity identifier |
| Name | Deductor Name | Normalized (uppercase, trimmed) |
| Assessment Year | AY | String or numeric |
| Financial Year | FY | Cross-validated with date |
| Major Head | Major Head | Fixed code |
| Minor Head | Minor Head | Fixed code |
| Nature of Payment | Section Code | e.g., 94J, 94I, 94T |
| Amount (₹) | Total Amount | Parsed numeric |
| Amount (in words) | Amount Words | Used for validation |
| CIN | CIN | Unique transaction identifier |
| BSR Code | BSR Code | Bank branch identifier |
| Challan No | Challan No | Numeric string |
| Date of Deposit | Deposit Date | Normalized ISO format |
| Bank Name | Bank | Text |
| Bank Ref No | Bank Reference | Text |
| Tax A–F | Tax Components | Numeric columns |

**One PDF = One Excel row**

---

# 3. Mathematical & Validation Model

## 3.1 Amount Normalization

Let extracted amount string be:

₹ 19,395 → A = 19395.00

Steps:
- Remove currency symbol
- Remove thousand separators
- Convert to float

---

## 3.2 Tax Breakup Validation

Let tax components be:

A_tax, B_surcharge, C_cess, D_interest, E_penalty, F_fee

Then:

S = A_tax + B_surcharge + C_cess + D_interest + E_penalty + F_fee

Validation rule:

|S − Total Amount| ≤ ε  (ε = 1.0)

If violated → **FLAGGED FOR MANUAL REVIEW**

---

## 3.3 Date Normalization

Input formats may include:
- DD-MMM-YYYY
- DD/MM/YYYY

Converted to:

YYYY-MM-DD (ISO 8601)

If ambiguous:
- Infer using Financial Year

---

## 3.4 Uniqueness & Deduplication

Unique Challan Hash:

hash = CIN + Challan No + Deposit Date

Duplicate hashes indicate repeated uploads.

---

## 3.5 Confidence Scoring

Each extracted field has confidence `c ∈ [0,1]`.

Overall row confidence:

C_row = Σ(wᵢ × cᵢ)

Threshold:
- C_row ≥ 0.85 → Auto-accepted
- Otherwise → Review required

---

# 4. Extraction Methodology

## 4.1 Strategy Hierarchy

1. **Text-first PDF extraction**
2. **Layout-aware parsing** (label-value proximity)
3. **OCR fallback** for scanned PDFs
4. **Regex + spatial heuristics**

---

## 4.2 Frameworks & Libraries

| Purpose | Library |
|------|--------|
| PDF text extraction | pdfplumber / PyMuPDF |
| OCR | pytesseract |
| Image preprocessing | OpenCV |
| Table detection | Camelot / Tabula |
| Data handling | Pandas |
| Excel writing | openpyxl / xlsxwriter |
| Fuzzy matching | RapidFuzz |
| Testing | PyTest |

---

# 5. Programmatic Pipeline

## Step 1: Ingestion
- Read all PDFs from input directory

## Step 2: Preprocessing
- Convert page to image
- Grayscale, threshold, deskew

## Step 3: Text Extraction
- Extract raw text + bounding boxes

## Step 4: Field Detection
- Anchor-based regex for labels
- Nearest-right / nearest-below value detection

## Step 5: OCR Fallback
- Triggered if mandatory fields missing

## Step 6: Normalization
- Amounts → float
- Dates → ISO
- Codes → uppercase

## Step 7: Validation
- Tax sum check
- Date vs FY consistency
- Duplicate detection

## Step 8: Excel Generation
- One row per challan
- Metadata columns added

---

# 6. Excel Output Design

## Mandatory Columns
- TAN
- Deductor Name
- CIN
- Challan No
- Deposit Date
- Section Code
- Total Amount
- Tax A–F

## Additional Metadata Columns
- Source File
- Extraction Confidence
- Validation Status
- Notes

## Embedded Excel Formula Example

=IF(ABS(SUM(A2:F2)-G2)>1,"FLAG","OK")

---

# 7. Error Handling & Edge Cases

| Scenario | Handling |
|-------|---------|
| Scanned PDF | OCR fallback |
| Rotated pages | Deskew |
| Missing tax rows | Flag |
| Amount mismatch | Flag |
| Duplicate challan | Deduplicate |
| Layout variation | Spatial heuristics |

---

# 8. Project Structure

```
tds_extractor/
├── input/
├── output/
│   └── TDS_extracted.xlsx
├── src/
│   ├── extractor.py
│   ├── ocr.py
│   ├── validator.py
│   ├── writer.py
│   └── utils.py
├── tests/
├── requirements.txt
└── README.md
```

---

# 9. Quality Metrics

- Field Accuracy (%)
- Row Acceptance Rate (%)
- Manual Review Rate
- Duplicate Detection Rate

---

# 10. Extensibility

- Support for new challan formats
- Donut / LayoutLM integration
- Streamlit-based review UI
- API-based batch processing

---

# Conclusion

This architecture provides a **production-grade, auditable, and mathematically validated** pipeline for TDS report generation from challan PDFs. It minimizes manual effort, ensures compliance accuracy, and scales to large volumes with confidence scoring and automated checks.

---

**End of Document**

