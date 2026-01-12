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
