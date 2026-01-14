"""
Unit tests for peer review results functionality.
Tests subtasks:
1) The system shall display a list of received peer reviews
2) Each review shall show reviewer name (or anonymous if defined)
3) Ratings per criterion shall be displayed clearly
4) A calculated total score shall be shown
5) The system shall prevent access before results are published
6) Unit tests shall verify correct result display
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


def test_results_not_available_before_publish(client):
    """Subtask 5: The system shall prevent access before results are published."""
    _register_student(client, "student1", "student1@test.com")
    token = _login(client, "student1", "Student123")

    # Try to access results before publishing
    res = client.get("/peer-reviews/results", headers=_auth(token))
    assert res.status_code == 403, res.text
    assert "not been published" in res.json()["detail"].lower()


def test_results_display_list_of_reviews(client):
    """Subtask 1: The system shall display a list of received peer reviews."""
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

    # Get results
    res = client.get("/peer-reviews/results", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Check that results contain a list of reviews
    assert "reviews" in data
    assert isinstance(data["reviews"], list)
    assert len(data["reviews"]) > 0


def test_results_show_reviewer_name(client):
    """Subtask 2: Each review shall show reviewer name (or anonymous if defined)."""
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

    # Get results
    res = client.get("/peer-reviews/results", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Check that each review has reviewer information
    assert len(data["reviews"]) > 0
    for review in data["reviews"]:
        assert "reviewer_id" in review
        assert "reviewer_username" in review
        # Reviewer username should be present (or could be "Anonymous" if configured)
        assert review["reviewer_username"] is not None


def test_results_display_ratings_per_criterion(client):
    """Subtask 3: Ratings per criterion shall be displayed clearly."""
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

    # Get results
    res = client.get("/peer-reviews/results", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Check that each review has ratings per criterion
    assert len(data["reviews"]) > 0
    for review in data["reviews"]:
        assert "ratings" in review
        assert isinstance(review["ratings"], list)
        assert len(review["ratings"]) > 0
        
        for rating in review["ratings"]:
            assert "criterion_id" in rating
            assert "criterion_title" in rating
            assert "rating" in rating
            assert "criterion_weight" in rating
            assert isinstance(rating["rating"], (int, float))


def test_results_display_total_score(client):
    """Subtask 4: A calculated total score shall be shown."""
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

    # Submit reviews with known ratings
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

    # Get results
    res = client.get("/peer-reviews/results", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Check that each review has a total score
    assert len(data["reviews"]) > 0
    for review in data["reviews"]:
        assert "total_score" in review
        assert isinstance(review["total_score"], (int, float))
        # Total score should be within valid range (assuming 1-5 scale)
        assert 0 <= review["total_score"] <= 5


def test_results_multiple_reviewers(client):
    """Test results with multiple reviewers."""
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

    # Get results
    res = client.get("/peer-reviews/results", headers=_auth(student1_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Should have multiple reviews (one per reviewer)
    assert len(data["reviews"]) >= 2
    
    # Each review should have unique reviewer
    reviewer_ids = [r["reviewer_id"] for r in data["reviews"]]
    assert len(set(reviewer_ids)) >= 2


def test_results_with_no_reviews(client):
    """Test results when student has received no reviews."""
    _register_student(client, "student1", "student1@test.com")
    _register_instructor(client, "instructor1", "instructor1@test.com")

    student_token = _login(client, "student1", "Student123")
    instructor_token = _login(client, "instructor1", "Instructor123")

    # Publish results
    res = client.post("/instructor/publish", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text

    # Get results
    res = client.get("/peer-reviews/results", headers=_auth(student_token))
    assert res.status_code == 200, res.text
    data = res.json()

    # Should return empty reviews list
    assert "reviews" in data
    assert isinstance(data["reviews"], list)
    assert len(data["reviews"]) == 0
    assert "message" in data


def test_results_instructor_access(client):
    """Test that instructors can view any student's results."""
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

    # Get student1's ID
    student1_user = db.get_user_by_username("student1")
    assert student1_user is not None
    student1_id = student1_user["id"]

    # Instructor should be able to view student1's results
    res = client.get(f"/peer-reviews/results?student_id={student1_id}", headers=_auth(instructor_token))
    assert res.status_code == 200, res.text
    data = res.json()

    assert "reviews" in data
    assert data["student_id"] == student1_id
