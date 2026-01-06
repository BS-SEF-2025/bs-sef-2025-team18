from fastapi.testclient import TestClient
import os
import db
from main import app

client = TestClient(app)


def setup_module():
    # fresh db per test run
    if os.path.exists("app.db"):
        os.remove("app.db")
    db.init_db()


def test_student_cannot_access_instructor_page():
    client.post("/auth/register", json={"username": "s1", "password": "1234", "role": "student"})
    r = client.post("/auth/login", json={"username": "s1", "password": "1234"})
    token = r.json()["access_token"]

    res = client.get("/instructor/publish", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_instructor_can_access_instructor_page():
    client.post("/auth/register", json={"username": "i1", "password": "1234", "role": "instructor"})
    r = client.post("/auth/login", json={"username": "i1", "password": "1234"})
    token = r.json()["access_token"]

    res = client.get("/instructor/publish", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
