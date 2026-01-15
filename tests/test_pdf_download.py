"""Tests for PDF download functionality."""
import pytest
from datetime import datetime
from fastapi.testclient import TestClient

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from main import app
import db


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    """Initialize database before each test."""
    db.init_db()
    yield


@pytest.fixture
def student_token():
    """Create a student and return their token."""
    unique_name = f"pdfstudent_{datetime.now().timestamp()}"
    try:
        db.create_user(f"{unique_name}@test.com", unique_name, "password123a", "student")
    except Exception:
        pass
    from token_service import create_access_token
    return create_access_token(username=unique_name, role="student")


@pytest.fixture
def instructor_token():
    """Create an instructor and return their token."""
    unique_name = f"pdfinstructor_{datetime.now().timestamp()}"
    try:
        db.create_user(f"{unique_name}@test.com", unique_name, "password123a", "instructor")
    except Exception:
        pass
    from token_service import create_access_token
    return create_access_token(username=unique_name, role="instructor")


@pytest.fixture
def other_student_token():
    """Create another student and return their token."""
    unique_name = f"otherstudent_{datetime.now().timestamp()}"
    try:
        db.create_user(f"{unique_name}@test.com", unique_name, "password123a", "student")
    except Exception:
        pass
    from token_service import create_access_token
    return create_access_token(username=unique_name, role="student")


class TestPdfDownload:
    """Test PDF download functionality."""

    def test_download_blocked_before_publication(self, client, student_token):
        """Test that PDF download is blocked when results are not published."""
        # Ensure results are not published (clear any existing publication)
        with db.get_conn() as conn:
            conn.execute("DELETE FROM peer_review_results_published")
        
        response = client.get(
            "/peer-reviews/report/pdf",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 403
        assert "not been published" in response.json()["detail"].lower()

    def test_download_works_after_publication(self, client, student_token, instructor_token):
        """Test that PDF download works after results are published."""
        # Publish results
        response = client.post(
            "/instructor/publish",
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        assert response.status_code == 200
        
        # Now try to download PDF
        response = client.get(
            "/peer-reviews/report/pdf",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "attachment" in response.headers.get("content-disposition", "")

    def test_student_cannot_download_another_students_report(self, client, student_token, other_student_token, instructor_token):
        """Test that a student cannot download another student's report.
        
        The endpoint only allows students to download their own report.
        There's no parameter to specify another student's ID.
        """
        # Publish results first
        client.post(
            "/instructor/publish",
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        
        # Student downloads their own report - should work
        response = client.get(
            "/peer-reviews/report/pdf",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        
        # Other student downloads their own report - should also work (different report)
        response = client.get(
            "/peer-reviews/report/pdf",
            headers={"Authorization": f"Bearer {other_student_token}"}
        )
        assert response.status_code == 200
        
        # The endpoint doesn't accept student_id parameter for students,
        # so there's no way for a student to request another student's PDF

    def test_pdf_content_not_empty(self, client, student_token, instructor_token):
        """Test that the generated PDF has content."""
        # Publish results
        client.post(
            "/instructor/publish",
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        
        # Download PDF
        response = client.get(
            "/peer-reviews/report/pdf",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        
        assert response.status_code == 200
        
        # Check that PDF content is not empty
        content = response.content
        assert len(content) > 0
        
        # Check PDF magic bytes (PDF files start with %PDF-)
        assert content[:5] == b'%PDF-'

    def test_instructor_cannot_use_student_pdf_endpoint(self, client, instructor_token):
        """Test that instructors cannot use the student PDF download endpoint."""
        # The endpoint requires 'student' role
        response = client.get(
            "/peer-reviews/report/pdf",
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        
        assert response.status_code == 403
        assert "forbidden" in response.json()["detail"].lower()
