"""
Tests for evaluation criteria management feature.
Tests cover:
- Instructor can create criterion
- Created criterion appears in list
- Instructor can edit criterion when state is "draft"
- When state becomes "published" (or "started"), edit is blocked with 403
- Students cannot create/edit criteria (RBAC check) => 403
"""

import pytest
from fastapi.testclient import TestClient

import backend.db as db
from backend.main import app


def _login(client, username: str, password: str) -> str:
    """Helper to login and get access token."""
    res = client.post("/auth/login", json={"username": username, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _auth(token: str) -> dict:
    """Helper to create Authorization header."""
    return {"Authorization": f"Bearer {token}"}


def _register_user(client, username: str, email: str, password: str, role: str):
    """Helper to register a user. Skips if user already exists."""
    res = client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": password, "role": role},
    )
    # Accept 200, 201 (created) or 409 (already exists - OK for tests)
    assert res.status_code in (200, 201, 409), f"Unexpected status: {res.status_code}, {res.text}"


def _set_review_state(client, token: str, status: str):
    """Helper to set review state."""
    res = client.post(
        "/review/state",
        json={"status": status},
        headers=_auth(token),
    )
    assert res.status_code == 200, res.text
    return res.json()


# ============================================================
# Test: Instructor can create criterion
# ============================================================
def test_instructor_can_create_criterion(client):
    """Instructor should be able to create a new evaluation criterion."""
    _register_user(client, "inst_crit1", "inst_crit1@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit1", "Instructor123")

    # Ensure state is draft
    _set_review_state(client, token, "draft")

    res = client.post(
        "/criteria",
        json={"name": "Teamwork", "description": "Ability to work effectively in a team"},
        headers=_auth(token),
    )

    assert res.status_code == 201, res.text
    data = res.json()
    assert "id" in data
    assert data["name"] == "Teamwork"
    assert data["description"] == "Ability to work effectively in a team"
    assert "created_at" in data


# ============================================================
# Test: Created criterion appears in list
# ============================================================
def test_created_criterion_appears_in_list(client):
    """After creating a criterion, it should appear in the GET /criteria list."""
    _register_user(client, "inst_crit2", "inst_crit2@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit2", "Instructor123")

    # Ensure state is draft
    _set_review_state(client, token, "draft")

    # Create a criterion
    create_res = client.post(
        "/criteria",
        json={"name": "Communication", "description": "Clear and effective communication"},
        headers=_auth(token),
    )
    assert create_res.status_code == 201, create_res.text
    created_id = create_res.json()["id"]

    # Get all criteria
    list_res = client.get("/criteria", headers=_auth(token))
    assert list_res.status_code == 200, list_res.text

    data = list_res.json()
    assert "criteria" in data
    assert isinstance(data["criteria"], list)

    # Find the created criterion
    found = None
    for criterion in data["criteria"]:
        if criterion["id"] == created_id:
            found = criterion
            break

    assert found is not None, "Created criterion should appear in the list"
    assert found["name"] == "Communication"
    assert found["description"] == "Clear and effective communication"


# ============================================================
# Test: Instructor can edit criterion when state is "draft"
# ============================================================
def test_instructor_can_edit_criterion_when_draft(client):
    """Instructor should be able to edit criteria when review state is 'draft'."""
    _register_user(client, "inst_crit3", "inst_crit3@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit3", "Instructor123")

    # Ensure state is draft
    _set_review_state(client, token, "draft")

    # Create a criterion
    create_res = client.post(
        "/criteria",
        json={"name": "Original Name", "description": "Original description"},
        headers=_auth(token),
    )
    assert create_res.status_code == 201, create_res.text
    criterion_id = create_res.json()["id"]

    # Edit the criterion
    update_res = client.put(
        f"/criteria/{criterion_id}",
        json={"name": "Updated Name", "description": "Updated description"},
        headers=_auth(token),
    )

    assert update_res.status_code == 200, update_res.text
    data = update_res.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "Updated description"
    assert data["id"] == criterion_id


# ============================================================
# Test: Edit blocked when state is "started"
# ============================================================
def test_edit_blocked_when_state_started(client):
    """Editing criteria should be blocked with 403 when review state is 'started'."""
    _register_user(client, "inst_crit4", "inst_crit4@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit4", "Instructor123")

    # Create a criterion in draft state
    _set_review_state(client, token, "draft")
    create_res = client.post(
        "/criteria",
        json={"name": "Test Criterion", "description": "Test description"},
        headers=_auth(token),
    )
    assert create_res.status_code == 201, create_res.text
    criterion_id = create_res.json()["id"]

    # Change state to "started"
    _set_review_state(client, token, "started")

    # Try to edit - should be blocked
    update_res = client.put(
        f"/criteria/{criterion_id}",
        json={"name": "Updated Name", "description": "Updated description"},
        headers=_auth(token),
    )

    assert update_res.status_code == 403, update_res.text
    data = update_res.json()
    assert "draft" in data["detail"].lower() or "started" in data["detail"].lower()


# ============================================================
# Test: Edit blocked when state is "published"
# ============================================================
def test_edit_blocked_when_state_published(client):
    """Editing criteria should be blocked with 403 when review state is 'published'."""
    _register_user(client, "inst_crit5", "inst_crit5@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit5", "Instructor123")

    # Create a criterion in draft state
    _set_review_state(client, token, "draft")
    create_res = client.post(
        "/criteria",
        json={"name": "Test Criterion", "description": "Test description"},
        headers=_auth(token),
    )
    assert create_res.status_code == 201, create_res.text
    criterion_id = create_res.json()["id"]

    # Change state to "published"
    _set_review_state(client, token, "published")

    # Try to edit - should be blocked
    update_res = client.put(
        f"/criteria/{criterion_id}",
        json={"name": "Updated Name", "description": "Updated description"},
        headers=_auth(token),
    )

    assert update_res.status_code == 403, update_res.text
    data = update_res.json()
    assert "draft" in data["detail"].lower() or "published" in data["detail"].lower()


# ============================================================
# Test: Delete blocked when state is not "draft"
# ============================================================
def test_delete_blocked_when_state_not_draft(client):
    """Deleting criteria should be blocked when review state is not 'draft'."""
    _register_user(client, "inst_crit6", "inst_crit6@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit6", "Instructor123")

    # Create a criterion in draft state
    _set_review_state(client, token, "draft")
    create_res = client.post(
        "/criteria",
        json={"name": "Test Criterion", "description": "Test description"},
        headers=_auth(token),
    )
    assert create_res.status_code == 201, create_res.text
    criterion_id = create_res.json()["id"]

    # Change state to "published"
    _set_review_state(client, token, "published")

    # Try to delete - should be blocked
    delete_res = client.delete(
        f"/criteria/{criterion_id}",
        headers=_auth(token),
    )

    assert delete_res.status_code == 403, delete_res.text


# ============================================================
# Test: Create blocked when state is not "draft"
# ============================================================
def test_create_blocked_when_state_not_draft(client):
    """Creating criteria should be blocked with 403 when review state is not 'draft'."""
    _register_user(client, "inst_crit_create1", "inst_crit_create1@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit_create1", "Instructor123")

    # Change state to "started"
    _set_review_state(client, token, "started")

    # Try to create - should be blocked
    res = client.post(
        "/criteria",
        json={"name": "Test Criterion", "description": "Test description"},
        headers=_auth(token),
    )

    assert res.status_code == 403, res.text
    data = res.json()
    assert "draft" in data["detail"].lower() or "started" in data["detail"].lower()

    # Change state to "published"
    _set_review_state(client, token, "published")

    # Try to create - should be blocked
    res = client.post(
        "/criteria",
        json={"name": "Test Criterion 2", "description": "Test description 2"},
        headers=_auth(token),
    )

    assert res.status_code == 403, res.text
    data = res.json()
    assert "draft" in data["detail"].lower() or "published" in data["detail"].lower()


# ============================================================
# Test: Students cannot create criteria (RBAC)
# ============================================================
def test_student_cannot_create_criteria(client):
    """Students should not be able to create criteria (403 Forbidden)."""
    _register_user(client, "student_crit1", "student_crit1@test.com", "Student123", "student")
    token = _login(client, "student_crit1", "Student123")

    res = client.post(
        "/criteria",
        json={"name": "Teamwork", "description": "Ability to work in a team"},
        headers=_auth(token),
    )

    assert res.status_code == 403, res.text
    assert "forbidden" in res.json()["detail"].lower() or "not allowed" in res.json()["detail"].lower()


# ============================================================
# Test: Students cannot edit criteria (RBAC)
# ============================================================
def test_student_cannot_edit_criteria(client):
    """Students should not be able to edit criteria (403 Forbidden)."""
    _register_user(client, "inst_crit7", "inst_crit7@test.com", "Instructor123", "instructor")
    _register_user(client, "student_crit2", "student_crit2@test.com", "Student123", "student")

    instructor_token = _login(client, "inst_crit7", "Instructor123")
    student_token = _login(client, "student_crit2", "Student123")

    # Instructor creates a criterion
    _set_review_state(client, instructor_token, "draft")
    create_res = client.post(
        "/criteria",
        json={"name": "Test Criterion", "description": "Test description"},
        headers=_auth(instructor_token),
    )
    assert create_res.status_code == 201, create_res.text
    criterion_id = create_res.json()["id"]

    # Student tries to edit - should be blocked
    update_res = client.put(
        f"/criteria/{criterion_id}",
        json={"name": "Updated Name", "description": "Updated description"},
        headers=_auth(student_token),
    )

    assert update_res.status_code == 403, update_res.text


# ============================================================
# Test: Students cannot view criteria list (RBAC)
# ============================================================
def test_student_cannot_view_criteria_list(client):
    """Students should not be able to view criteria list (403 Forbidden)."""
    _register_user(client, "student_crit3", "student_crit3@test.com", "Student123", "student")
    token = _login(client, "student_crit3", "Student123")

    res = client.get("/criteria", headers=_auth(token))

    assert res.status_code == 403, res.text


# ============================================================
# Test: Students cannot delete criteria (RBAC)
# ============================================================
def test_student_cannot_delete_criteria(client):
    """Students should not be able to delete criteria (403 Forbidden)."""
    _register_user(client, "inst_crit8", "inst_crit8@test.com", "Instructor123", "instructor")
    _register_user(client, "student_crit4", "student_crit4@test.com", "Student123", "student")

    instructor_token = _login(client, "inst_crit8", "Instructor123")
    student_token = _login(client, "student_crit4", "Student123")

    # Instructor creates a criterion
    _set_review_state(client, instructor_token, "draft")
    create_res = client.post(
        "/criteria",
        json={"name": "Test Criterion", "description": "Test description"},
        headers=_auth(instructor_token),
    )
    assert create_res.status_code == 201, create_res.text
    criterion_id = create_res.json()["id"]

    # Student tries to delete - should be blocked
    delete_res = client.delete(
        f"/criteria/{criterion_id}",
        headers=_auth(student_token),
    )

    assert delete_res.status_code == 403, delete_res.text


# ============================================================
# Test: Validation - empty name/description
# ============================================================
def test_create_criterion_empty_name_returns_422(client):
    """Creating a criterion with empty name should return 422."""
    _register_user(client, "inst_crit9", "inst_crit9@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit9", "Instructor123")

    res = client.post(
        "/criteria",
        json={"name": "", "description": "Valid description"},
        headers=_auth(token),
    )

    assert res.status_code == 422, res.text


def test_create_criterion_empty_description_returns_422(client):
    """Creating a criterion with empty description should return 422."""
    _register_user(client, "inst_crit10", "inst_crit10@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit10", "Instructor123")

    res = client.post(
        "/criteria",
        json={"name": "Valid Name", "description": ""},
        headers=_auth(token),
    )

    assert res.status_code == 422, res.text


# ============================================================
# Test: Update non-existent criterion returns 404
# ============================================================
def test_update_nonexistent_criterion_returns_404(client):
    """Updating a non-existent criterion should return 404."""
    _register_user(client, "inst_crit11", "inst_crit11@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit11", "Instructor123")

    _set_review_state(client, token, "draft")

    res = client.put(
        "/criteria/99999",
        json={"name": "Updated Name", "description": "Updated description"},
        headers=_auth(token),
    )

    assert res.status_code == 404, res.text


# ============================================================
# Test: Delete non-existent criterion returns 404
# ============================================================
def test_delete_nonexistent_criterion_returns_404(client):
    """Deleting a non-existent criterion should return 404."""
    _register_user(client, "inst_crit12", "inst_crit12@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit12", "Instructor123")

    _set_review_state(client, token, "draft")

    res = client.delete(
        "/criteria/99999",
        headers=_auth(token),
    )

    assert res.status_code == 404, res.text


# ============================================================
# Test: Review state management endpoints
# ============================================================
def test_instructor_can_get_review_state(client):
    """Instructor should be able to get the current review state."""
    _register_user(client, "inst_crit13", "inst_crit13@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit13", "Instructor123")

    res = client.get("/review/state", headers=_auth(token))

    assert res.status_code == 200, res.text
    data = res.json()
    assert "status" in data
    assert data["status"] in ("draft", "started", "published")


def test_instructor_can_set_review_state(client):
    """Instructor should be able to set the review state."""
    _register_user(client, "inst_crit14", "inst_crit14@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit14", "Instructor123")

    # Set to started
    res = client.post(
        "/review/state",
        json={"status": "started"},
        headers=_auth(token),
    )

    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "started"

    # Verify it was set
    get_res = client.get("/review/state", headers=_auth(token))
    assert get_res.status_code == 200, get_res.text
    assert get_res.json()["status"] == "started"


def test_student_cannot_set_review_state(client):
    """Students should not be able to set the review state (403 Forbidden)."""
    _register_user(client, "student_crit5", "student_crit5@test.com", "Student123", "student")
    token = _login(client, "student_crit5", "Student123")

    res = client.post(
        "/review/state",
        json={"status": "started"},
        headers=_auth(token),
    )

    assert res.status_code == 403, res.text


def test_student_cannot_get_review_state(client):
    """Students should not be able to get the review state (403 Forbidden)."""
    _register_user(client, "student_crit6", "student_crit6@test.com", "Student123", "student")
    token = _login(client, "student_crit6", "Student123")

    res = client.get("/review/state", headers=_auth(token))

    assert res.status_code == 403, res.text


# ============================================================
# Test: Multiple criteria can be created and listed
# ============================================================
def test_multiple_criteria_can_be_created(client):
    """Multiple criteria can be created and all appear in the list."""
    _register_user(client, "inst_crit15", "inst_crit15@test.com", "Instructor123", "instructor")
    token = _login(client, "inst_crit15", "Instructor123")

    # Ensure state is draft
    _set_review_state(client, token, "draft")

    # Create multiple criteria
    criterion1_res = client.post(
        "/criteria",
        json={"name": "Criterion 1", "description": "Description 1"},
        headers=_auth(token),
    )
    assert criterion1_res.status_code == 201, criterion1_res.text
    criterion1 = criterion1_res.json()

    criterion2_res = client.post(
        "/criteria",
        json={"name": "Criterion 2", "description": "Description 2"},
        headers=_auth(token),
    )
    assert criterion2_res.status_code == 201, criterion2_res.text
    criterion2 = criterion2_res.json()

    # Get all criteria
    list_res = client.get("/criteria", headers=_auth(token))
    assert list_res.status_code == 200, list_res.text

    criteria = list_res.json()["criteria"]
    criterion_ids = [c["id"] for c in criteria]

    assert criterion1["id"] in criterion_ids
    assert criterion2["id"] in criterion_ids
    assert len(criteria) >= 2
