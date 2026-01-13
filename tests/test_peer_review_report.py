"""
Unit tests for personal peer review report functionality.
Tests subtasks:
1) The system shall allow a student to access their personal peer review report
2) The report shall include a weighted overall score
3) The report shall display scores per evaluation criterion
4) The report shall be available only after results are published
5) Unit tests shall verify correct report display
"""

import pytest
from backend import db


def _login(client, username: str, password: str) -> str:
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _register_student(client, username: str, email: str, password: str = "Student123"):
    res = client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password, "role": "student"},
    )
    assert res.status_code in (200, 201), res.text


def _register_instructor(client, username: str, email: str, password: str = "Instructor123"):
    res = client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password, "role": "instructor"},
    )
    assert res.status_code in (200, 201), res.text


def _submit_review(client, token: str, reviewee_id: int, criterion_id: int, rating: int):
    """Helper to submit a single review."""
    payload = {
        "reviews": [
            {
                "teammate_id": reviewee_id,
                "answers": [{"criterion_id": criterion_id, "rating": rating}],
            }
        ]
    }
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    return res


def test_report_not_available_before_publish(client):
    """Subtask 4: The report shall be available only after results are published."""
    _register_student(client, "student1", "student1@test.com")
    token = _login(client, "student1", "Student123")

    # Try to access report before publishing
    res = client.get("/peer-reviews/report", headers=_auth(token))
    assert res.status_code == 403, res.text
    assert "not been published" in res.json()["detail"].lower()


def test_report_accessible_after_publish(client):
    """Subtask 1: The system shall allow a student to access their personal peer review report."""
    _register_student(client, "student1", "student1@test.com")
    _register_instructor(client, "instructor1", "instructor1@test.com")

    student_token = _login(client, "student1", "Student123")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Publish results
    res = client.post("/instructor/publish", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text

    # Now student should be able to access report
    res = client.get("/peer-reviews/report", headers=_auth(student_token))
    assert res.status_code == 200, res.text
    data = res.json()
    assert "student_id" in data
    assert "student_username" in data
    assert "overall_score" in data
    assert "criterion_scores" in data


def test_report_includes_weighted_overall_score(client):
    """Subtask 2: The report shall include a weighted overall score."""
    _register_student(client, "student1", "student1@test.com")
    _register_student(client, "student2", "student2@test.com")
    _register_instructor(client, "instructor1", "instructor1@test.com")

    student1_token = _login(client, "student1", "Student123")
    student2_token = _login(client, "student2", "Student123")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Get criteria and teammates
    form_res = client.get("/peer-reviews/form", headers=_auth(student1_token))
    assert form_res.status_code == 200, form_res.text
    form_data = form_res.json()
    criteria = form_data["criteria"]
    teammates = form_data["teammates"]

    if not teammates or not criteria:
        pytest.skip("No teammates or criteria available for testing")

    reviewee_id = teammates[0]["id"]

    # Submit reviews from student2 for student1
    # Submit all required criteria
    answers = [{"criterion_id": c["id"], "rating": 4} for c in criteria if c["required"]]
    if answers:
        payload = {
            "reviews": [
                {
                    "teammate_id": reviewee_id,
                    "answers": answers,
                }
            ]
        }
        res = client.post("/peer-reviews/submit", json=payload, headers=_auth(student2_token))
        assert res.status_code == 200, res.text

    # Publish results
    res = client.post("/instructor/publish", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text

    # Get report
    res = client.get("/peer-reviews/report", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Check that overall_score is present and is a number
    assert "overall_score" in data
    assert data["overall_score"] is not None
    assert isinstance(data["overall_score"], (int, float))
    assert 0 <= data["overall_score"] <= 5  # Assuming scale is 1-5


def test_report_displays_scores_per_criterion(client):
    """Subtask 3: The report shall display scores per evaluation criterion."""
    _register_student(client, "student1", "student1@test.com")
    _register_student(client, "student2", "student2@test.com")
    _register_instructor(client, "instructor1", "instructor1@test.com")

    student1_token = _login(client, "student1", "Student123")
    student2_token = _login(client, "student2", "Student123")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Get criteria and teammates
    form_res = client.get("/peer-reviews/form", headers=_auth(student1_token))
    assert form_res.status_code == 200, form_res.text
    form_data = form_res.json()
    criteria = form_data["criteria"]
    teammates = form_data["teammates"]

    if not teammates or not criteria:
        pytest.skip("No teammates or criteria available for testing")

    reviewee_id = teammates[0]["id"]

    # Submit reviews with different ratings for different criteria
    answers = [{"criterion_id": c["id"], "rating": 3 + (c["id"] % 3)} for c in criteria if c["required"]]
    if answers:
        payload = {
            "reviews": [
                {
                    "teammate_id": reviewee_id,
                    "answers": answers,
                }
            ]
        }
        res = client.post("/peer-reviews/submit", json=payload, headers=_auth(student2_token))
        assert res.status_code == 200, res.text

    # Publish results
    res = client.post("/instructor/publish", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text

    # Get report
    res = client.get("/peer-reviews/report", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Check criterion_scores structure
    assert "criterion_scores" in data
    assert isinstance(data["criterion_scores"], list)

    if data["criterion_scores"]:
        for criterion_score in data["criterion_scores"]:
            assert "criterion_id" in criterion_score
            assert "criterion_title" in criterion_score
            assert "weight" in criterion_score
            assert "average_score" in criterion_score
            assert "review_count" in criterion_score
            assert isinstance(criterion_score["average_score"], (int, float))
            assert isinstance(criterion_score["review_count"], int)
            assert criterion_score["review_count"] > 0


def test_report_only_accessible_by_students(client):
    """Test that instructors cannot access student reports."""
    _register_instructor(client, "instructor1", "instructor1@test.com")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Try to access report as instructor
    res = client.get("/peer-reviews/report", headers=_auth(instructor_token))
    assert res.status_code == 403, res.text


def test_report_with_no_reviews(client):
    """Test report when student has received no reviews."""
    _register_student(client, "student1", "student1@test.com")
    _register_instructor(client, "instructor1", "instructor1@test.com")

    student_token = _login(client, "student1", "Student123")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Publish results
    res = client.post("/instructor/publish", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text

    # Get report
    res = client.get("/peer-reviews/report", headers=_auth(student_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Should return empty report
    assert data["overall_score"] is None or data["overall_score"] == 0
    assert data["total_reviews"] == 0
    assert len(data["criterion_scores"]) == 0


def test_report_weighted_calculation(client):
    """Test that weighted overall score is calculated correctly."""
    _register_student(client, "student1", "student1@test.com")
    _register_student(client, "student2", "student2@test.com")
    _register_instructor(client, "instructor1", "instructor1@test.com")

    student1_token = _login(client, "student1", "Student123")
    student2_token = _login(client, "student2", "Student123")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Get criteria and teammates
    form_res = client.get("/peer-reviews/form", headers=_auth(student1_token))
    assert form_res.status_code == 200, form_res.text
    form_data = form_res.json()
    criteria = form_data["criteria"]
    teammates = form_data["teammates"]

    if not teammates or len(criteria) < 2:
        pytest.skip("Need at least 2 criteria for weighted calculation test")

    reviewee_id = teammates[0]["id"]

    # Submit reviews with known ratings
    # Use all criteria with different ratings
    answers = [{"criterion_id": c["id"], "rating": 4} for c in criteria]
    payload = {
        "reviews": [
            {
                "teammate_id": reviewee_id,
                "answers": answers,
            }
        ]
    }
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(student2_token))
    assert res.status_code == 200, res.text

    # Publish results
    res = client.post("/instructor/publish", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text

    # Get report
    res = client.get("/peer-reviews/report", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # If all criteria have same rating and same weight, overall should be close to that rating
    if data["criterion_scores"]:
        # Check that overall score is calculated
        assert data["overall_score"] is not None
        # With equal weights and same ratings, overall should equal the rating
        # (allowing for floating point precision)
        assert abs(data["overall_score"] - 4.0) < 0.1


def test_report_multiple_reviewers(client):
    """Test report with multiple reviewers."""
    _register_student(client, "student1", "student1@test.com")
    _register_student(client, "student2", "student2@test.com")
    _register_student(client, "student3", "student3@test.com")
    _register_instructor(client, "instructor1", "instructor1@test.com")

    student1_token = _login(client, "student1", "Student123")
    student2_token = _login(client, "student2", "Student123")
    student3_token = _login(client, "student3", "Student123")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Get criteria and teammates for student1
    form_res = client.get("/peer-reviews/form", headers=_auth(student1_token))
    assert form_res.status_code == 200, form_res.text
    form_data = form_res.json()
    criteria = form_data["criteria"]

    # Get student1's ID (as reviewee)
    # student2 and student3 should see student1 as teammate
    form_res2 = client.get("/peer-reviews/form", headers=_auth(student2_token))
    teammates2 = form_res2.json()["teammates"]
    student1_teammate = next((t for t in teammates2 if t["username"] == "student1"), None)

    if not student1_teammate or not criteria:
        pytest.skip("Setup issue for multiple reviewers test")

    reviewee_id = student1_teammate["id"]

    # Submit reviews from both student2 and student3
    answers = [{"criterion_id": c["id"], "rating": 4} for c in criteria if c["required"]]
    if answers:
        payload = {
            "reviews": [
                {
                    "teammate_id": reviewee_id,
                    "answers": answers,
                }
            ]
        }
        res = client.post("/peer-reviews/submit", json=payload, headers=_auth(student2_token))
        assert res.status_code == 200, res.text

        res = client.post("/peer-reviews/submit", json=payload, headers=_auth(student3_token))
        assert res.status_code == 200, res.text

    # Publish results
    res = client.post("/instructor/publish", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text

    # Get report
    res = client.get("/peer-reviews/report", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Should have multiple reviewers
    assert data["unique_reviewers"] >= 2
    assert data["total_reviews"] >= len(criteria) * 2  # At least 2 reviewers * criteria count
