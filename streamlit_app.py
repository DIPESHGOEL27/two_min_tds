"""
Streamlit dashboard for TDS Challan Processor.
Provides file upload, PDF preview, inline editing, and Excel export.
"""

import streamlit as st
import pandas as pd
import tempfile
import shutil
import base64
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import io

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from config import app_config, extraction_config
from models import ChallanRecord, ValidationStatus, ReviewStatus
from extraction import ExtractionPipeline
from validation import ChallanValidator, validate_batch
from export import write_excel, EXCEL_COLUMNS

# Page config
st.set_page_config(
    page_title="TDS Challan Processor",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .stAlert {
        margin-top: 1rem;
    }
    .record-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
    }
    .flag-badge {
        background-color: #ffc7ce;
        color: #9c0006;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .ok-badge {
        background-color: #c6efce;
        color: #006100;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: bold;
    }
    .confidence-high {
        color: #006100;
    }
    .confidence-medium {
        color: #9c6500;
    }
    .confidence-low {
        color: #9c0006;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    if "uploaded_files" not in st.session_state:
        st.session_state.uploaded_files = []
    if "records" not in st.session_state:
        st.session_state.records = []
    if "processing_complete" not in st.session_state:
        st.session_state.processing_complete = False
    if "errors" not in st.session_state:
        st.session_state.errors = {}
    if "temp_dir" not in st.session_state:
        st.session_state.temp_dir = None
    if "selected_record_idx" not in st.session_state:
        st.session_state.selected_record_idx = None


def save_uploaded_files(uploaded_files) -> List[Path]:
    """Save uploaded files to temporary directory."""
    if st.session_state.temp_dir is None:
        st.session_state.temp_dir = tempfile.mkdtemp()

    temp_dir = Path(st.session_state.temp_dir)
    saved_paths = []

    for uploaded_file in uploaded_files:
        file_path = temp_dir / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        saved_paths.append(file_path)

    return saved_paths


def process_pdfs(pdf_paths: List[Path]) -> tuple:
    """Process PDF files and return records and errors."""
    pipeline = ExtractionPipeline()
    validator = ChallanValidator()

    records = []
    errors = {}

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, pdf_path in enumerate(pdf_paths):
        status_text.text(f"Processing: {pdf_path.name}")

        try:
            result = pipeline.process(pdf_path)

            if result.success and result.record:
                validator.validate(result.record)
                records.append(result.record)
            else:
                errors[pdf_path.name] = result.error_message or "Extraction failed"

        except Exception as e:
            errors[pdf_path.name] = str(e)

        progress_bar.progress((idx + 1) / len(pdf_paths))

    status_text.empty()
    progress_bar.empty()

    return records, errors


def display_pdf_preview(pdf_path: Path):
    """Display PDF preview in the browser."""
    try:
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        base64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Could not display PDF: {e}")


def get_confidence_class(confidence: float) -> str:
    """Get CSS class for confidence level."""
    if confidence >= 0.9:
        return "confidence-high"
    elif confidence >= 0.7:
        return "confidence-medium"
    return "confidence-low"


def display_record_summary(records: List[ChallanRecord]):
    """Display summary statistics."""
    if not records:
        return

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Records", len(records))

    with col2:
        ok_count = sum(1 for r in records if r.validation_flag == ValidationStatus.OK)
        st.metric("Valid Records", ok_count)

    with col3:
        flag_count = sum(1 for r in records if r.validation_flag == ValidationStatus.FLAG)
        st.metric("Flagged Records", flag_count)

    with col4:
        total_amount = sum(r.total_amount or 0 for r in records)
        st.metric("Total Amount", f"₹{total_amount:,.2f}")


def display_records_table(records: List[ChallanRecord]):
    """Display records in a table with selection."""
    if not records:
        return

    # Create dataframe for display
    data = []
    for idx, record in enumerate(records):
        data.append({
            "Index": idx,
            "Source File": record.source_file,
            "TAN": record.tan or "",
            "CIN": record.cin or "",
            "Amount": record.total_amount or 0,
            "Date": str(record.date_of_deposit) if record.date_of_deposit else "",
            "Confidence": f"{record.row_confidence:.1%}",
            "Status": record.validation_flag.value,
            "Review": record.review_status.value,
        })

    df = pd.DataFrame(data)

    # Style the dataframe
    def style_status(val):
        if val == "FLAG":
            return "background-color: #ffc7ce; color: #9c0006"
        elif val == "OK":
            return "background-color: #c6efce; color: #006100"
        return ""

    styled_df = df.style.applymap(style_status, subset=["Status"])

    st.dataframe(
        styled_df,
        use_container_width=True,
        height=400
    )


def display_record_editor(record: ChallanRecord, idx: int):
    """Display editable form for a single record."""
    st.subheader(f"Edit Record: {record.source_file}")

    col1, col2 = st.columns(2)

    with col1:
        # Editable fields
        new_tan = st.text_input("TAN", value=record.tan or "", key=f"tan_{idx}")
        new_name = st.text_input("Deductor Name", value=record.deductor_name or "", key=f"name_{idx}")
        new_amount = st.number_input(
            "Total Amount",
            value=float(record.total_amount or 0),
            key=f"amount_{idx}"
        )
        new_cin = st.text_input("CIN", value=record.cin or "", key=f"cin_{idx}")
        new_challan = st.text_input("Challan No", value=record.challan_no or "", key=f"challan_{idx}")

        date_value = record.date_of_deposit if record.date_of_deposit else datetime.today().date()
        new_date = st.date_input("Date of Deposit", value=date_value, key=f"date_{idx}")

    with col2:
        st.write("**Tax Breakup**")
        new_tax_a = st.number_input("Tax (A)", value=float(record.tax_breakup.tax_a), key=f"taxa_{idx}")
        new_tax_b = st.number_input("Surcharge (B)", value=float(record.tax_breakup.tax_b), key=f"taxb_{idx}")
        new_tax_c = st.number_input("Cess (C)", value=float(record.tax_breakup.tax_c), key=f"taxc_{idx}")
        new_tax_d = st.number_input("Interest (D)", value=float(record.tax_breakup.tax_d), key=f"taxd_{idx}")
        new_tax_e = st.number_input("Penalty (E)", value=float(record.tax_breakup.tax_e), key=f"taxe_{idx}")
        new_tax_f = st.number_input("Fee 234E (F)", value=float(record.tax_breakup.tax_f), key=f"taxf_{idx}")

        tax_sum = new_tax_a + new_tax_b + new_tax_c + new_tax_d + new_tax_e + new_tax_f
        st.info(f"Tax Sum: ₹{tax_sum:,.2f}")

    new_notes = st.text_area("Notes", value=record.notes or "", key=f"notes_{idx}")

    # Validation status display
    if record.validation_flag == ValidationStatus.FLAG:
        st.warning(f"⚠️ Record flagged: {record.notes}")
    else:
        st.success("✅ Record validation passed")

    st.write(f"**Confidence Score:** {record.row_confidence:.1%}")

    # Action buttons
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("💾 Save Changes", key=f"save_{idx}"):
            # Apply changes
            record.tan = new_tan
            record.deductor_name = new_name
            record.total_amount = new_amount
            record.cin = new_cin
            record.challan_no = new_challan
            record.date_of_deposit = new_date
            record.tax_breakup.tax_a = new_tax_a
            record.tax_breakup.tax_b = new_tax_b
            record.tax_breakup.tax_c = new_tax_c
            record.tax_breakup.tax_d = new_tax_d
            record.tax_breakup.tax_e = new_tax_e
            record.tax_breakup.tax_f = new_tax_f
            record.notes = new_notes
            record.review_status = ReviewStatus.CORRECTED

            # Re-validate
            validator = ChallanValidator()
            validator.validate(record)

            st.success("Changes saved!")
            st.rerun()

    with col2:
        if st.button("✅ Accept", key=f"accept_{idx}"):
            record.review_status = ReviewStatus.ACCEPTED
            st.success("Record accepted!")
            st.rerun()

    with col3:
        if st.button("❌ Reject", key=f"reject_{idx}"):
            record.review_status = ReviewStatus.REJECTED
            st.warning("Record rejected - will be excluded from export")
            st.rerun()

    with col4:
        if st.button("🔄 Re-validate", key=f"revalidate_{idx}"):
            validator = ChallanValidator()
            validator.validate(record)
            st.rerun()


def export_to_excel(records: List[ChallanRecord]) -> bytes:
    """Export records to Excel and return as bytes."""
    # Filter out rejected records
    export_records = [
        r for r in records
        if r.review_status != ReviewStatus.REJECTED
    ]

    if not export_records:
        return None

    # Create temporary file
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        output_path = Path(tmp.name)

    write_excel(export_records, output_path, include_summary=True)

    with open(output_path, "rb") as f:
        data = f.read()

    output_path.unlink()  # Clean up
    return data


def main():
    """Main Streamlit application."""
    init_session_state()

    st.title("📄 TDS Challan Processor")
    st.markdown("Upload TDS Challan PDFs, review extracted data, and export to Excel.")

    # Sidebar
    with st.sidebar:
        st.header("Settings")

        confidence_threshold = st.slider(
            "Review Threshold",
            min_value=0.0,
            max_value=1.0,
            value=extraction_config.min_row_confidence,
            step=0.05,
            help="Records below this confidence require manual review"
        )

        st.divider()

        st.header("Session Info")
        if st.session_state.records:
            st.write(f"**Records:** {len(st.session_state.records)}")
            flagged = sum(1 for r in st.session_state.records if r.validation_flag == ValidationStatus.FLAG)
            st.write(f"**Flagged:** {flagged}")

        if st.button("🗑️ Clear Session"):
            if st.session_state.temp_dir:
                shutil.rmtree(st.session_state.temp_dir, ignore_errors=True)
            st.session_state.clear()
            st.rerun()

    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["📤 Upload", "📝 Review", "📊 Export"])

    # Tab 1: Upload
    with tab1:
        st.header("Upload TDS Challan PDFs")

        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            help="Upload one or more TDS Challan PDF files"
        )

        if uploaded_files:
            st.info(f"Selected {len(uploaded_files)} file(s)")

            if st.button("🚀 Process Files", type="primary"):
                with st.spinner("Processing..."):
                    # Save files
                    pdf_paths = save_uploaded_files(uploaded_files)
                    st.session_state.uploaded_files = pdf_paths

                    # Process
                    records, errors = process_pdfs(pdf_paths)
                    st.session_state.records = records
                    st.session_state.errors = errors
                    st.session_state.processing_complete = True

                st.success(f"Processed {len(records)} records successfully!")

                if errors:
                    st.error(f"Failed to process {len(errors)} file(s)")
                    with st.expander("View Errors"):
                        for filename, error in errors.items():
                            st.write(f"**{filename}:** {error}")

        if st.session_state.processing_complete:
            display_record_summary(st.session_state.records)

    # Tab 2: Review
    with tab2:
        st.header("Review Extracted Records")

        records = st.session_state.records

        if not records:
            st.info("No records to review. Please upload and process PDFs first.")
        else:
            # Filter options
            col1, col2 = st.columns(2)
            with col1:
                filter_status = st.selectbox(
                    "Filter by Status",
                    ["All", "OK", "FLAG"],
                    index=0
                )
            with col2:
                filter_review = st.selectbox(
                    "Filter by Review",
                    ["All", "PENDING_REVIEW", "ACCEPTED", "REJECTED", "CORRECTED"],
                    index=0
                )

            # Filter records
            filtered_records = records
            if filter_status != "All":
                filtered_records = [r for r in filtered_records if r.validation_flag.value == filter_status]
            if filter_review != "All":
                filtered_records = [r for r in filtered_records if r.review_status.value == filter_review]

            st.write(f"Showing {len(filtered_records)} of {len(records)} records")

            # Display records table
            display_records_table(filtered_records)

            # Record selector for detailed view
            st.divider()

            if filtered_records:
                record_options = [
                    f"{idx}: {r.source_file} ({r.validation_flag.value})"
                    for idx, r in enumerate(records)
                    if r in filtered_records
                ]

                selected_option = st.selectbox(
                    "Select record to edit",
                    record_options,
                    index=0 if record_options else None
                )

                if selected_option:
                    selected_idx = int(selected_option.split(":")[0])
                    selected_record = records[selected_idx]

                    col1, col2 = st.columns([1, 1])

                    with col1:
                        st.subheader("Original PDF")
                        # Find the PDF path
                        pdf_name = selected_record.source_file
                        if st.session_state.temp_dir:
                            pdf_path = Path(st.session_state.temp_dir) / pdf_name
                            if pdf_path.exists():
                                display_pdf_preview(pdf_path)
                            else:
                                st.warning("PDF file not found")

                    with col2:
                        display_record_editor(selected_record, selected_idx)

    # Tab 3: Export
    with tab3:
        st.header("Export to Excel")

        records = st.session_state.records

        if not records:
            st.info("No records to export. Please upload and process PDFs first.")
        else:
            # Export summary
            accepted = sum(1 for r in records if r.review_status == ReviewStatus.ACCEPTED)
            pending = sum(1 for r in records if r.review_status == ReviewStatus.PENDING_REVIEW)
            rejected = sum(1 for r in records if r.review_status == ReviewStatus.REJECTED)
            corrected = sum(1 for r in records if r.review_status == ReviewStatus.CORRECTED)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Accepted", accepted)
            col2.metric("Pending Review", pending)
            col3.metric("Corrected", corrected)
            col4.metric("Rejected", rejected)

            st.divider()

            # Export options
            include_pending = st.checkbox("Include pending records", value=True)

            exportable = [
                r for r in records
                if r.review_status != ReviewStatus.REJECTED
                and (include_pending or r.review_status != ReviewStatus.PENDING_REVIEW)
            ]

            st.info(f"**{len(exportable)}** records will be exported")

            if exportable:
                if st.button("📥 Generate Excel Report", type="primary"):
                    with st.spinner("Generating Excel file..."):
                        excel_data = export_to_excel(exportable)

                    if excel_data:
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"TDS_extracted_{timestamp}.xlsx"

                        st.download_button(
                            label="⬇️ Download Excel File",
                            data=excel_data,
                            file_name=filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

                        st.success("Excel file generated successfully!")
                    else:
                        st.error("No records to export")

            # Column schema info
            with st.expander("📋 Excel Column Schema"):
                schema_data = [
                    {"Column": col, "Type": "string" if col not in ["Total Amount", "Tax_A", "Tax_B", "Tax_C", "Tax_D", "Tax_E", "Tax_F", "Row Confidence"] else "number"}
                    for col in EXCEL_COLUMNS
                ]
                st.dataframe(pd.DataFrame(schema_data), use_container_width=True)


if __name__ == "__main__":
    main()
