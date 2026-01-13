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


def test_form_returns_criteria_and_teammates(client):
    # add teammate so student1 has someone to review
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    res = client.get("/peer-reviews/form", headers=_auth(token))
    assert res.status_code == 200, res.text

    data = res.json()
    assert "criteria" in data and isinstance(data["criteria"], list)
    assert "teammates" in data and isinstance(data["teammates"], list)

    # criteria should not be empty
    assert len(data["criteria"]) > 0

    # teammates should include student2 and not include student1
    usernames = [t["username"] for t in data["teammates"]]
    assert "student1" not in usernames
    assert "student2" in usernames


def test_submit_validation_missing_required_fields_returns_400(client):
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]

    # Send only ONE answer -> should fail because required criteria missing
    payload = {
        "reviews": [
            {
                "teammate_id": teammate_id,
                "answers": [
                    {"criterion_id": criteria[0]["id"], "rating": 5},
                ],
            }
        ]
    }

    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text

    errors = res.json()["detail"]
    assert isinstance(errors, list)
    assert any(e.get("message") == "Rating is required" for e in errors)


def test_submit_validation_rating_out_of_range_returns_400(client):
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]

    # Out of range rating (scale usually 1..5) -> should fail
    payload = {
        "reviews": [
            {
                "teammate_id": teammate_id,
                "answers": [
                    {"criterion_id": criteria[0]["id"], "rating": 999},
                ],
            }
        ]
    }

    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text


def test_submit_success_when_all_required_fields_present(client):
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]

    answers = [{"criterion_id": c["id"], "rating": c["scale"]["max"]} for c in criteria]

    payload = {"reviews": [{"teammate_id": teammate_id, "answers": answers}]}
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True}


def test_instructor_forbidden(client):
    token = _login(client, "instructor1", "Instructor123")

    res = client.get("/peer-reviews/form", headers=_auth(token))
    assert res.status_code == 403, res.text

    res2 = client.post("/peer-reviews/submit", json={"reviews": []}, headers=_auth(token))
    assert res2.status_code == 403, res2.text


def test_submit_validation_all_required_criteria_missing_returns_400(client):
    """Test that validation fails when all required criteria are missing"""
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    required_criteria = [c for c in criteria if c["required"]]

    # Send empty answers -> should fail because all required criteria missing
    payload = {
        "reviews": [
            {
                "teammate_id": teammate_id,
                "answers": [],
            }
        ]
    }

    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text

    errors = res.json()["detail"]
    assert isinstance(errors, list)
    # Should have errors for all required criteria
    assert len(errors) >= len(required_criteria)
    assert all(e.get("message") == "Rating is required" for e in errors)


def test_submit_validation_rating_below_minimum_returns_400(client):
    """Test that validation fails when rating is below the minimum scale value"""
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    first_criterion = criteria[0]
    scale_min = first_criterion["scale"]["min"]

    # Rating below minimum -> should fail
    payload = {
        "reviews": [
            {
                "teammate_id": teammate_id,
                "answers": [
                    {"criterion_id": first_criterion["id"], "rating": scale_min - 1},
                ],
            }
        ]
    }

    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text

    errors = res.json()["detail"]
    assert isinstance(errors, list)
    assert any(
        f"Rating must be between {scale_min}" in e.get("message", "")
        for e in errors
    )


def test_submit_validation_rating_above_maximum_returns_400(client):
    """Test that validation fails when rating is above the maximum scale value"""
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    first_criterion = criteria[0]
    scale_max = first_criterion["scale"]["max"]

    # Rating above maximum -> should fail
    payload = {
        "reviews": [
            {
                "teammate_id": teammate_id,
                "answers": [
                    {"criterion_id": first_criterion["id"], "rating": scale_max + 1},
                ],
            }
        ]
    }

    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text

    errors = res.json()["detail"]
    assert isinstance(errors, list)
    assert any(
        f"Rating must be between" in e.get("message", "") and str(scale_max) in e.get("message", "")
        for e in errors
    )


def test_submit_validation_multiple_errors_returns_400(client):
    """Test that validation returns multiple errors when there are multiple validation failures"""
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    required_criteria = [c for c in criteria if c["required"]]

    # Create payload with multiple issues:
    # 1. Out of range rating for first criterion
    # 2. Missing other required criteria
    if len(required_criteria) > 0:
        first_criterion = required_criteria[0]
        scale_max = first_criterion["scale"]["max"]

        payload = {
            "reviews": [
                {
                    "teammate_id": teammate_id,
                    "answers": [
                        {"criterion_id": first_criterion["id"], "rating": scale_max + 10},
                    ],
                }
            ]
        }

        res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
        assert res.status_code == 400, res.text

        errors = res.json()["detail"]
        assert isinstance(errors, list)
        # Should have at least 2 errors: one for out of range, one for missing required criteria
        assert len(errors) >= 2
        # Check for out of range error
        assert any("Rating must be between" in e.get("message", "") for e in errors)
        # Check for missing required criteria error
        assert any(e.get("message") == "Rating is required" for e in errors)


def test_submit_validation_boundary_values_success(client):
    """Test that validation passes with boundary values (min and max of scale)"""
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]

    # Use boundary values: min and max for each criterion
    answers = []
    for c in criteria:
        scale_min = c["scale"]["min"]
        scale_max = c["scale"]["max"]
        # Alternate between min and max to test both boundaries
        rating = scale_min if c["id"] % 2 == 0 else scale_max
        answers.append({"criterion_id": c["id"], "rating": rating})

    payload = {"reviews": [{"teammate_id": teammate_id, "answers": answers}]}
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True}


def test_submit_validation_optional_criteria_can_be_omitted(client):
    """Test that optional criteria can be omitted without causing validation errors"""
    _register_student(client, "student2", "student2@student.demo", "Student123")

    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()

    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    required_criteria = [c for c in criteria if c["required"]]
    optional_criteria = [c for c in criteria if not c["required"]]

    # Only include required criteria, omit optional ones
    answers = [{"criterion_id": c["id"], "rating": c["scale"]["max"]} for c in required_criteria]

    payload = {"reviews": [{"teammate_id": teammate_id, "answers": answers}]}
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    
    # Should succeed if there are optional criteria, or if all criteria are required (then it should still work)
    if len(optional_criteria) > 0:
        # If there are optional criteria, submission should succeed without them
        assert res.status_code == 200, res.text
        assert res.json() == {"ok": True}
    else:
        # If all criteria are required, it should still succeed since we included all required ones
        assert res.status_code == 200, res.text
        assert res.json() == {"ok": True}


def test_submit_validation_empty_reviews_list_returns_400(client):
    """Subtask 1 & 4: Test that empty reviews list returns validation error"""
    token = _login(client, "student1", "Student123")
    
    payload = {"reviews": []}
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text
    
    errors = res.json()["detail"]
    assert isinstance(errors, list)
    assert len(errors) > 0
    assert any("No reviews submitted" in e.get("message", "") for e in errors)


def test_submit_validation_invalid_teammate_id_returns_400(client):
    """Test that invalid teammate ID returns validation error"""
    _register_student(client, "student2", "student2@student.demo", "Student123")
    
    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()
    
    criteria = form["criteria"]
    invalid_teammate_id = 99999  # Non-existent teammate ID
    
    answers = [{"criterion_id": c["id"], "rating": c["scale"]["max"]} for c in criteria]
    
    payload = {"reviews": [{"teammate_id": invalid_teammate_id, "answers": answers}]}
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text
    
    errors = res.json()["detail"]
    assert isinstance(errors, list)
    assert any("Invalid teammate" in e.get("message", "") for e in errors)


def test_submit_validation_invalid_criterion_id_returns_400(client):
    """Test that invalid criterion ID returns validation error"""
    _register_student(client, "student2", "student2@student.demo", "Student123")
    
    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()
    
    teammate_id = form["teammates"][0]["id"]
    invalid_criterion_id = 99999  # Non-existent criterion ID
    
    payload = {
        "reviews": [
            {
                "teammate_id": teammate_id,
                "answers": [{"criterion_id": invalid_criterion_id, "rating": 5}],
            }
        ]
    }
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text
    
    errors = res.json()["detail"]
    assert isinstance(errors, list)
    assert any("Invalid criterion" in e.get("message", "") for e in errors)


def test_submit_validation_all_required_criteria_must_be_rated(client):
    """Subtask 1: Test that ALL mandatory criteria must be rated"""
    _register_student(client, "student2", "student2@student.demo", "Student123")
    
    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()
    
    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    required_criteria = [c for c in criteria if c["required"]]
    
    # Only rate one required criterion, missing all others
    if len(required_criteria) > 1:
        answers = [{"criterion_id": required_criteria[0]["id"], "rating": 5}]
        
        payload = {"reviews": [{"teammate_id": teammate_id, "answers": answers}]}
        res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
        assert res.status_code == 400, res.text
        
        errors = res.json()["detail"]
        assert isinstance(errors, list)
        # Should have errors for all missing required criteria
        missing_required_count = len(required_criteria) - 1
        assert len([e for e in errors if "Rating is required" in e.get("message", "")]) >= missing_required_count


def test_submit_validation_rating_at_minimum_boundary_succeeds(client):
    """Subtask 2: Test that rating at minimum boundary value succeeds"""
    _register_student(client, "student2", "student2@student.demo", "Student123")
    
    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()
    
    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    
    # Use minimum value for all criteria
    answers = [{"criterion_id": c["id"], "rating": c["scale"]["min"]} for c in criteria]
    
    payload = {"reviews": [{"teammate_id": teammate_id, "answers": answers}]}
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True}


def test_submit_validation_rating_at_maximum_boundary_succeeds(client):
    """Subtask 2: Test that rating at maximum boundary value succeeds"""
    _register_student(client, "student2", "student2@student.demo", "Student123")
    
    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()
    
    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    
    # Use maximum value for all criteria
    answers = [{"criterion_id": c["id"], "rating": c["scale"]["max"]} for c in criteria]
    
    payload = {"reviews": [{"teammate_id": teammate_id, "answers": answers}]}
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 200, res.text
    assert res.json() == {"ok": True}


def test_submit_validation_multiple_reviews_with_errors(client):
    """Test validation with multiple reviews, some with errors"""
    _register_student(client, "student2", "student2@student.demo", "Student123")
    _register_student(client, "student3", "student3@student.demo", "Student123")
    
    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()
    
    teammates = form["teammates"]
    criteria = form["criteria"]
    
    # First review: valid
    # Second review: missing required criteria
    if len(teammates) >= 2:
        valid_answers = [{"criterion_id": c["id"], "rating": c["scale"]["max"]} for c in criteria]
        invalid_answers = [{"criterion_id": criteria[0]["id"], "rating": 5}]  # Only one criterion
        
        payload = {
            "reviews": [
                {"teammate_id": teammates[0]["id"], "answers": valid_answers},
                {"teammate_id": teammates[1]["id"], "answers": invalid_answers},
            ]
        }
        
        res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
        assert res.status_code == 400, res.text
        
        errors = res.json()["detail"]
        assert isinstance(errors, list)
        # Should have errors for missing required criteria in second review
        assert any("Rating is required" in e.get("message", "") for e in errors)


def test_submit_validation_error_messages_are_descriptive(client):
    """Subtask 3: Test that error messages are descriptive and helpful"""
    _register_student(client, "student2", "student2@student.demo", "Student123")
    
    token = _login(client, "student1", "Student123")
    form = client.get("/peer-reviews/form", headers=_auth(token)).json()
    
    teammate_id = form["teammates"][0]["id"]
    criteria = form["criteria"]
    first_criterion = criteria[0]
    scale_min = first_criterion["scale"]["min"]
    scale_max = first_criterion["scale"]["max"]
    
    # Test out of range error message
    payload = {
        "reviews": [
            {
                "teammate_id": teammate_id,
                "answers": [{"criterion_id": first_criterion["id"], "rating": scale_max + 1}],
            }
        ]
    }
    
    res = client.post("/peer-reviews/submit", json=payload, headers=_auth(token))
    assert res.status_code == 400, res.text
    
    errors = res.json()["detail"]
    assert isinstance(errors, list)
    # Error message should include the valid range
    assert any(
        f"Rating must be between {scale_min} and {scale_max}" in e.get("message", "")
        for e in errors
    )
