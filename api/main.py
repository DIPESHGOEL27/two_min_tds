"""
FastAPI backend for TDS Challan Processor.
Provides REST API endpoints for upload, processing, review, and export.
"""

import logging
import uuid
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import app_config
from models import ChallanRecord, ValidationStatus, ReviewStatus, ExtractionResult
from extraction import process_pdf, ExtractionPipeline
from validation import validate_batch, ChallanValidator
from export import write_excel

# Configure logging
logging.basicConfig(
    level=getattr(logging, app_config.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="TDS Challan Processor API",
    description="API for extracting, validating, and exporting TDS Challan data from PDFs",
    version="1.0.0"
)

# Enable CORS for Streamlit frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
app_config.ensure_directories()

# In-memory storage for session data (in production, use Redis/database)
sessions: Dict[str, Dict] = {}


# Request/Response models
class ProcessingStatus(BaseModel):
    session_id: str
    total_files: int
    processed: int
    status: str  # pending, processing, completed, error
    records: List[Dict] = []
    errors: Dict[str, str] = {}


class RecordUpdate(BaseModel):
    tan: Optional[str] = None
    deductor_name: Optional[str] = None
    total_amount: Optional[float] = None
    cin: Optional[str] = None
    challan_no: Optional[str] = None
    date_of_deposit: Optional[str] = None
    notes: Optional[str] = None
    review_status: Optional[str] = None


class ExportRequest(BaseModel):
    session_id: str
    include_flagged: bool = True
    include_summary: bool = True


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "TDS Challan Processor",
        "version": "1.0.0"
    }


@app.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)) -> ProcessingStatus:
    """
    Upload PDF files for processing.

    Args:
        files: List of PDF files to upload

    Returns:
        ProcessingStatus with session ID
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Validate file types
    for file in files:
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.filename}. Only PDF files are accepted."
            )

    # Create session
    session_id = str(uuid.uuid4())
    session_dir = app_config.uploads_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files
    saved_files = []
    for file in files:
        file_path = session_dir / file.filename
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        saved_files.append(file_path)
        logger.info(f"Saved file: {file_path}")

    # Initialize session
    sessions[session_id] = {
        "status": "pending",
        "files": saved_files,
        "total_files": len(saved_files),
        "processed": 0,
        "records": [],
        "errors": {},
        "created_at": datetime.now().isoformat()
    }

    return ProcessingStatus(
        session_id=session_id,
        total_files=len(saved_files),
        processed=0,
        status="pending"
    )


@app.post("/process/{session_id}")
async def process_session(session_id: str, background_tasks: BackgroundTasks) -> ProcessingStatus:
    """
    Start processing uploaded files.

    Args:
        session_id: Session ID from upload

    Returns:
        ProcessingStatus
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    if session["status"] == "processing":
        return ProcessingStatus(
            session_id=session_id,
            total_files=session["total_files"],
            processed=session["processed"],
            status="processing"
        )

    # Start processing
    session["status"] = "processing"
    background_tasks.add_task(_process_files, session_id)

    return ProcessingStatus(
        session_id=session_id,
        total_files=session["total_files"],
        processed=0,
        status="processing"
    )


async def _process_files(session_id: str):
    """Background task to process PDF files."""
    session = sessions[session_id]
    pipeline = ExtractionPipeline()
    validator = ChallanValidator()

    records = []
    errors = {}

    for pdf_path in session["files"]:
        try:
            logger.info(f"Processing: {pdf_path}")
            result = pipeline.process(pdf_path)

            if result.success and result.record:
                # Validate the record
                validator.validate(result.record)
                records.append(result.record)
            else:
                errors[pdf_path.name] = result.error_message or "Unknown error"

        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {e}")
            errors[pdf_path.name] = str(e)

        session["processed"] += 1

    session["records"] = records
    session["errors"] = errors
    session["status"] = "completed"

    logger.info(f"Session {session_id} completed: {len(records)} records, {len(errors)} errors")


@app.get("/status/{session_id}")
async def get_status(session_id: str) -> ProcessingStatus:
    """Get processing status for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    return ProcessingStatus(
        session_id=session_id,
        total_files=session["total_files"],
        processed=session["processed"],
        status=session["status"],
        records=[r.to_excel_row() for r in session.get("records", [])],
        errors=session.get("errors", {})
    )


@app.get("/records/{session_id}")
async def get_records(session_id: str) -> List[Dict]:
    """Get all extracted records for a session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    records = session.get("records", [])

    return [
        {
            "index": idx,
            "hash": r.record_hash,
            **r.to_excel_row(),
            "review_status": r.review_status.value
        }
        for idx, r in enumerate(records)
    ]


@app.put("/records/{session_id}/{record_index}")
async def update_record(
    session_id: str,
    record_index: int,
    update: RecordUpdate
) -> Dict:
    """Update a single record (for manual corrections)."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    records = session.get("records", [])

    if record_index < 0 or record_index >= len(records):
        raise HTTPException(status_code=404, detail="Record not found")

    record = records[record_index]

    # Apply updates
    if update.tan is not None:
        record.tan = update.tan
    if update.deductor_name is not None:
        record.deductor_name = update.deductor_name
    if update.total_amount is not None:
        record.total_amount = update.total_amount
    if update.cin is not None:
        record.cin = update.cin
    if update.challan_no is not None:
        record.challan_no = update.challan_no
    if update.date_of_deposit is not None:
        from datetime import datetime as dt
        try:
            record.date_of_deposit = dt.strptime(update.date_of_deposit, "%Y-%m-%d").date()
        except ValueError:
            pass
    if update.notes is not None:
        record.notes = update.notes
    if update.review_status is not None:
        record.review_status = ReviewStatus(update.review_status)

    # Re-validate
    validator = ChallanValidator()
    validator.validate(record)

    logger.info(f"Updated record {record_index} in session {session_id}")

    return {
        "index": record_index,
        "hash": record.record_hash,
        **record.to_excel_row(),
        "review_status": record.review_status.value
    }


@app.post("/records/{session_id}/{record_index}/accept")
async def accept_record(session_id: str, record_index: int) -> Dict:
    """Mark a record as accepted."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    records = session.get("records", [])

    if record_index < 0 or record_index >= len(records):
        raise HTTPException(status_code=404, detail="Record not found")

    record = records[record_index]
    record.review_status = ReviewStatus.ACCEPTED

    return {"status": "accepted", "index": record_index}


@app.post("/records/{session_id}/{record_index}/reject")
async def reject_record(session_id: str, record_index: int) -> Dict:
    """Mark a record as rejected."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    records = session.get("records", [])

    if record_index < 0 or record_index >= len(records):
        raise HTTPException(status_code=404, detail="Record not found")

    record = records[record_index]
    record.review_status = ReviewStatus.REJECTED

    return {"status": "rejected", "index": record_index}


@app.post("/export/{session_id}")
async def export_excel(session_id: str, request: ExportRequest = None) -> FileResponse:
    """
    Export records to Excel file.

    Args:
        session_id: Session ID
        request: Export options

    Returns:
        Excel file download
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    records = session.get("records", [])

    if not records:
        raise HTTPException(status_code=400, detail="No records to export")

    # Filter out rejected records
    export_records = [
        r for r in records
        if r.review_status != ReviewStatus.REJECTED
    ]

    if not export_records:
        raise HTTPException(status_code=400, detail="All records were rejected")

    # Generate Excel file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = app_config.output_dir / f"TDS_extracted_{timestamp}.xlsx"

    include_summary = request.include_summary if request else True
    write_excel(export_records, output_path, include_summary=include_summary)

    return FileResponse(
        path=output_path,
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/pdf/{session_id}/{filename}")
async def get_pdf(session_id: str, filename: str) -> FileResponse:
    """Get original PDF file for preview."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_path = app_config.uploads_dir / session_id / filename

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF not found")

    return FileResponse(
        path=pdf_path,
        filename=filename,
        media_type="application/pdf"
    )


@app.delete("/session/{session_id}")
async def delete_session(session_id: str) -> Dict:
    """Delete a session and its files."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    # Remove files
    session_dir = app_config.uploads_dir / session_id
    if session_dir.exists():
        shutil.rmtree(session_dir)

    # Remove from memory
    del sessions[session_id]

    logger.info(f"Deleted session: {session_id}")
    return {"status": "deleted", "session_id": session_id}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "active_sessions": len(sessions),
        "uploads_dir": str(app_config.uploads_dir),
        "output_dir": str(app_config.output_dir),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=app_config.api_host,
        port=app_config.api_port,
        reload=True
    )
