#!/usr/bin/env python3
"""
Example script to run the TDS Challan Processor pipeline on sample PDFs.
This script demonstrates the extraction pipeline and generates output Excel.

Usage:
    python example_run.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from extraction import process_batch
from validation import validate_batch
from export import write_excel


def main():
    print("=" * 60)
    print("TDS Challan Processor - Example Run")
    print("=" * 60)
    print()

    # Find sample PDFs
    sample_dir = Path("TDS Challans for Testing")

    if not sample_dir.exists():
        print(f"Error: Sample PDFs directory not found: {sample_dir}")
        print("Please ensure you have the sample PDFs in the correct location.")
        sys.exit(1)

    pdf_files = list(sample_dir.glob("*.pdf"))

    if not pdf_files:
        print(f"Error: No PDF files found in {sample_dir}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files:")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    print()

    # Process all PDFs
    print("Processing PDFs...")
    print("-" * 60)
    print()

    results = process_batch(pdf_files)

    # Collect successful extractions
    records = []
    for result in results:
        if result.success:
            record = result.record
            print(f"✓ {record.source_file}")
            print(f"    TAN:        {record.tan}")
            print(f"    CIN:        {record.cin}")
            print(f"    Amount:     ₹{record.total_amount:,.2f}")
            print(f"    Date:       {record.date_of_deposit}")
            print(f"    Payment:    {record.nature_of_payment}")
            print(f"    Confidence: {record.row_confidence:.1%}")
            print()
            records.append(record)
        else:
            print(f"✗ Failed: {result.error_message}")
            print()

    # Validate records
    print("-" * 60)
    print("Validating records...")
    print()

    validation_results = validate_batch(records)

    for i, (record, result) in enumerate(zip(records, validation_results)):
        status = "OK" if result.is_valid else "FLAG"
        print(f"  [{status}] {record.source_file}")
        if result.issues:
            for issue in result.issues:
                print(f"       - {issue.field}: {issue.message}")

    print()

    ok_count = sum(1 for r in records if r.validation_flag.value == "OK")
    flag_count = sum(1 for r in records if r.validation_flag.value == "FLAG")

    print(f"  Valid (OK):  {ok_count}")
    print(f"  Flagged:     {flag_count}")
    print()

    # Export to Excel
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    output_path = output_dir / "TDS_extracted.xlsx"

    print("-" * 60)
    print("Generating Excel report...")
    print()

    write_excel(records, output_path)

    print(f"✓ Excel file generated: {output_path}")
    print()

    # Show summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()

    total_amount = sum(r.total_amount or 0 for r in records)

    print(f"  Total PDFs processed:    {len(pdf_files)}")
    print(f"  Successful extractions:  {len(records)}")
    print(f"  Valid records:           {ok_count}")
    print(f"  Flagged records:         {flag_count}")
    print()
    print(f"  Total amount extracted:  ₹{total_amount:,.2f}")
    print()

    # Verify expected amounts
    print("-" * 60)
    print("Verification against expected values:")
    print()

    expected_amounts = {
        "25100700517216HDFC_ChallanReceipt- Input Command Challan.pdf": 19395.00,
        "25100700523936HDFC_ChallanReceipt- For other Testing.pdf": 22500.00,
        "25100700528930HDFC_ChallanReceipt- For other Testing.pdf": 40000.00,
    }

    all_match = True
    for record in records:
        expected = expected_amounts.get(record.source_file)
        if expected:
            actual = record.total_amount
            diff = abs(actual - expected)
            status = "✓" if diff <= 0.01 else "✗"
            if diff > 0.01:
                all_match = False
            print(f"  {status} {record.source_file}")
            print(f"      Expected: ₹{expected:,.2f}")
            print(f"      Actual:   ₹{actual:,.2f}")
            print(f"      Diff:     ₹{diff:,.2f}")
            print()

    print("-" * 60)

    if all_match:
        print("✓ All amounts extracted correctly within tolerance (±0.01)")
        print()
        print("Expected total: ₹19,395.00 + ₹22,500.00 + ₹40,000.00 = ₹81,895.00")
        print(f"Actual total:   ₹{total_amount:,.2f}")
    else:
        print("✗ Some amounts did not match expected values")
        sys.exit(1)

    print()
    print("=" * 60)
    print("Example run completed successfully!")
    print(f"Output file: {output_path.absolute()}")
    print("=" * 60)


if __name__ == "__main__":
    main()
