#!/bin/bash
# Example script to run the TDS Challan Processor pipeline on sample PDFs
# This script demonstrates the extraction pipeline and generates output Excel

set -e

echo "=========================================="
echo "TDS Challan Processor - Example Run"
echo "=========================================="

# Check if we're in the right directory
if [ ! -d "extraction" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Create output directory
mkdir -p output

# Check for sample PDFs
SAMPLE_DIR="TDS Challans for Testing"
if [ ! -d "$SAMPLE_DIR" ]; then
    echo "Error: Sample PDFs directory not found: $SAMPLE_DIR"
    exit 1
fi

echo ""
echo "Found sample PDFs:"
ls -la "$SAMPLE_DIR"/*.pdf 2>/dev/null || echo "No PDFs found"

echo ""
echo "Running extraction pipeline..."
echo ""

# Run the extraction script
python3 << 'PYTHON_SCRIPT'
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from extraction import process_batch
from validation import validate_batch
from export import write_excel

# Find sample PDFs
sample_dir = Path("TDS Challans for Testing")
pdf_files = list(sample_dir.glob("*.pdf"))

print(f"Processing {len(pdf_files)} PDF files...")
print()

# Process all PDFs
results = process_batch(pdf_files)

# Collect successful extractions
records = []
for result in results:
    if result.success:
        print(f"✓ {result.record.source_file}")
        print(f"  - TAN: {result.record.tan}")
        print(f"  - CIN: {result.record.cin}")
        print(f"  - Amount: ₹{result.record.total_amount:,.2f}")
        print(f"  - Date: {result.record.date_of_deposit}")
        print(f"  - Confidence: {result.record.row_confidence:.1%}")
        print()
        records.append(result.record)
    else:
        print(f"✗ {result.error_message}")

# Validate records
print("Validating records...")
validation_results = validate_batch(records)

ok_count = sum(1 for r in records if r.validation_flag.value == "OK")
flag_count = sum(1 for r in records if r.validation_flag.value == "FLAG")

print(f"  - Valid (OK): {ok_count}")
print(f"  - Flagged: {flag_count}")
print()

# Export to Excel
output_path = Path("output/TDS_extracted.xlsx")
write_excel(records, output_path)

print(f"Excel file generated: {output_path}")
print()

# Show summary
print("=" * 50)
print("SUMMARY")
print("=" * 50)
print(f"Total PDFs processed: {len(pdf_files)}")
print(f"Successful extractions: {len(records)}")
print(f"Total amount: ₹{sum(r.total_amount or 0 for r in records):,.2f}")
print()
print("Expected amounts: ₹19,395.00 + ₹22,500.00 + ₹40,000.00 = ₹81,895.00")
print(f"Actual total:    ₹{sum(r.total_amount or 0 for r in records):,.2f}")

# Verify amounts
amounts = sorted([r.total_amount for r in records])
expected = sorted([19395.0, 22500.0, 40000.0])

all_match = True
for actual, exp in zip(amounts, expected):
    if abs(actual - exp) > 0.01:
        all_match = False
        print(f"  ⚠ Mismatch: expected {exp}, got {actual}")

if all_match:
    print()
    print("✓ All amounts extracted correctly!")

PYTHON_SCRIPT

echo ""
echo "=========================================="
echo "Done! Output file: output/TDS_extracted.xlsx"
echo "=========================================="
