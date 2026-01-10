from fastapi.testclient import TestClient
import os
from backend import db
from backend.main import app



client = TestClient(app)


def setup_module():
    db_path = os.path.join("backend", "app.db")

    if os.path.exists(db_path):
        os.remove(db_path)

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


def test_login_invalid_username_shows_error_message():
    res = client.post("/auth/login", json={"username": "no_user", "password": "1234"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid credentials. Please check your username and password."


def test_login_invalid_password_shows_error_message():
    client.post("/auth/register", json={"username": "s2", "password": "1234", "role": "student"})
    res = client.post("/auth/login", json={"username": "s2", "password": "wrong"})
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid credentials. Please check your username and password."
if __name__ == "__main__":
    setup_module()
    test_student_cannot_access_instructor_page()
    test_instructor_can_access_instructor_page()
    test_login_invalid_username_shows_error_message()
    test_login_invalid_password_shows_error_message()
    print("All tests passed ✅")

