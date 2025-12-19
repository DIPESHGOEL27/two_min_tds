"""
Tests for FastAPI backend endpoints.
"""

import pytest
from pathlib import Path
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestAPIEndpoints:
    """Tests for API endpoints."""

    def test_root_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_endpoint(self, client):
        """Test detailed health check."""
        response = client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"

    def test_upload_no_files(self, client):
        """Test upload with no files."""
        response = client.post("/upload")
        assert response.status_code == 422  # Validation error

    def test_upload_invalid_file_type(self, client, temp_dir):
        """Test upload with non-PDF file."""
        # Create a text file
        txt_file = temp_dir / "test.txt"
        txt_file.write_text("This is not a PDF")

        with open(txt_file, "rb") as f:
            response = client.post(
                "/upload",
                files={"files": ("test.txt", f, "text/plain")}
            )

        assert response.status_code == 400
        assert "Invalid file type" in response.json()["detail"]

    def test_upload_pdf_success(self, client, sample_pdf_1):
        """Test successful PDF upload."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        with open(sample_pdf_1, "rb") as f:
            response = client.post(
                "/upload",
                files={"files": (sample_pdf_1.name, f, "application/pdf")}
            )

        assert response.status_code == 200
        data = response.json()

        assert "session_id" in data
        assert data["total_files"] == 1
        assert data["status"] == "pending"

    def test_status_invalid_session(self, client):
        """Test status with invalid session ID."""
        response = client.get("/status/invalid-session-id")
        assert response.status_code == 404

    def test_records_invalid_session(self, client):
        """Test records with invalid session ID."""
        response = client.get("/records/invalid-session-id")
        assert response.status_code == 404

    def test_delete_invalid_session(self, client):
        """Test delete with invalid session ID."""
        response = client.delete("/session/invalid-session-id")
        assert response.status_code == 404


class TestAPIWorkflow:
    """Tests for complete API workflow."""

    def test_upload_process_export_workflow(self, client, sample_pdf_1):
        """Test complete workflow: upload -> process -> export."""
        if not sample_pdf_1.exists():
            pytest.skip("Sample PDF not found")

        # Step 1: Upload
        with open(sample_pdf_1, "rb") as f:
            upload_response = client.post(
                "/upload",
                files={"files": (sample_pdf_1.name, f, "application/pdf")}
            )

        assert upload_response.status_code == 200
        session_id = upload_response.json()["session_id"]

        # Step 2: Process
        process_response = client.post(f"/process/{session_id}")
        assert process_response.status_code == 200

        # Wait for processing (in real scenario, would poll status)
        import time
        time.sleep(2)

        # Step 3: Check status
        status_response = client.get(f"/status/{session_id}")
        assert status_response.status_code == 200

        # Step 4: Get records
        records_response = client.get(f"/records/{session_id}")
        assert records_response.status_code == 200

        # Step 5: Cleanup
        delete_response = client.delete(f"/session/{session_id}")
        assert delete_response.status_code == 200
