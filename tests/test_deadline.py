"""Tests for submission deadline functionality."""
import pytest
from datetime import datetime, timedelta
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
    # Clear deadline before each test
    db.set_submission_deadline(None)
    yield


@pytest.fixture
def instructor_token(client):
    """Get instructor auth token."""
    # Create instructor if not exists
    try:
        db.create_user("instructor@test.com", "testinstructor", "hashedpw123", "instructor")
    except Exception:
        pass
    
    response = client.post("/auth/login", json={
        "username": "testinstructor",
        "password": "hashedpw123"
    })
    # If login fails, the user might exist with different password, try registering fresh
    if response.status_code != 200:
        # Use a unique username
        unique_name = f"instructor_{datetime.now().timestamp()}"
        db.create_user(f"{unique_name}@test.com", unique_name, "password123a", "instructor")
        from token_service import create_access_token
        return create_access_token(username=unique_name, role="instructor")
    return response.json()["access_token"]


@pytest.fixture
def student_token(client):
    """Get student auth token."""
    unique_name = f"student_{datetime.now().timestamp()}"
    try:
        db.create_user(f"{unique_name}@test.com", unique_name, "password123a", "student")
    except Exception:
        pass
    from token_service import create_access_token
    return create_access_token(username=unique_name, role="student")


class TestDeadlineFunctionality:
    """Test deadline-related functionality."""

    def test_submissions_allowed_before_deadline(self, client, instructor_token, student_token):
        """Test that submissions are allowed when deadline is in the future."""
        # Set deadline to 1 hour in the future
        future_deadline = (datetime.now() + timedelta(hours=1)).isoformat()
        
        response = client.post(
            "/deadline",
            json={"deadline": future_deadline},
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_open"] is True

        # Check deadline status as student
        response = client.get(
            "/deadline",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_open"] is True

    def test_submissions_blocked_after_deadline(self, client, instructor_token, student_token):
        """Test that submissions are blocked when deadline has passed."""
        # Set deadline to 1 hour in the past
        past_deadline = (datetime.now() - timedelta(hours=1)).isoformat()
        
        response = client.post(
            "/deadline",
            json={"deadline": past_deadline},
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_open"] is False

        # Verify student sees submissions as closed
        response = client.get(
            "/deadline",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_open"] is False

        # Try to submit a peer review (should fail)
        response = client.post(
            "/peer-reviews/submit",
            json={"reviews": [{"teammate_id": 999, "answers": []}]},
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 403
        assert "Submissions are closed" in response.json()["detail"]

    def test_reopen_submissions(self, client, instructor_token, student_token):
        """Test that instructor can reopen submissions by clearing or updating deadline."""
        # First set a past deadline
        past_deadline = (datetime.now() - timedelta(hours=1)).isoformat()
        client.post(
            "/deadline",
            json={"deadline": past_deadline},
            headers={"Authorization": f"Bearer {instructor_token}"}
        )

        # Verify closed
        response = client.get("/deadline", headers={"Authorization": f"Bearer {student_token}"})
        assert response.json()["is_open"] is False

        # Clear deadline to reopen
        response = client.delete(
            "/deadline",
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_open"] is True

        # Verify reopened
        response = client.get("/deadline", headers={"Authorization": f"Bearer {student_token}"})
        assert response.json()["is_open"] is True

        # Can also reopen by setting a future deadline
        past_deadline = (datetime.now() - timedelta(hours=1)).isoformat()
        client.post(
            "/deadline",
            json={"deadline": past_deadline},
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        
        future_deadline = (datetime.now() + timedelta(hours=1)).isoformat()
        response = client.post(
            "/deadline",
            json={"deadline": future_deadline},
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_open"] is True

    def test_only_instructor_can_change_deadline(self, client, instructor_token, student_token):
        """Test that only instructors can modify the deadline."""
        future_deadline = (datetime.now() + timedelta(hours=1)).isoformat()

        # Student should NOT be able to set deadline
        response = client.post(
            "/deadline",
            json={"deadline": future_deadline},
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 403

        # Student should NOT be able to clear deadline
        response = client.delete(
            "/deadline",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 403

        # Instructor CAN set deadline
        response = client.post(
            "/deadline",
            json={"deadline": future_deadline},
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        assert response.status_code == 200

        # Instructor CAN clear deadline
        response = client.delete(
            "/deadline",
            headers={"Authorization": f"Bearer {instructor_token}"}
        )
        assert response.status_code == 200

    def test_no_deadline_means_always_open(self, client, student_token):
        """Test that when no deadline is set, submissions are always open."""
        # Ensure no deadline
        db.set_submission_deadline(None)
        
        response = client.get(
            "/deadline",
            headers={"Authorization": f"Bearer {student_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["deadline"] is None
        assert data["is_open"] is True
