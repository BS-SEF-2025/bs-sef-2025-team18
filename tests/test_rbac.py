import os
import gc
import time
import shutil
import sqlite3
import tempfile
import pytest
from fastapi.testclient import TestClient

import backend.db as db
from backend.main import app


# -------------------------
# Helpers
# -------------------------
def signup_body(
    email="test@example.com",
    username="user123",
    password="Test12345",
    confirm_password="Test12345",
    role="student",
):
    return {
        "email": email,
        "username": username,
        "password": password,
        "confirm_password": confirm_password,
        "role": role,
    }


def login_body(username="user123", password="Test12345"):
    return {"username": username, "password": password}


def auth_headers(token: str):
    return {"Authorization": f"Bearer {token}"}


def table_columns(conn: sqlite3.Connection, table: str) -> list[str]:
    conn.row_factory = sqlite3.Row
    return [r["name"] for r in conn.execute(f"PRAGMA table_info({table});")]


# -------------------------
# Fixture: isolated DB per test (Windows-safe cleanup)
# -------------------------
@pytest.fixture()
def client():
    """
    Each test uses a fresh temporary DB so we never touch backend/app.db.
    Windows: sqlite file can stay locked briefly -> we delete with retries.
    """
    old_db_path = db.DB_PATH

    td = tempfile.mkdtemp()
    db.DB_PATH = os.path.join(td, "test_app.db")
    db.init_db()

    try:
        with TestClient(app) as c:
            yield c
    finally:
        # restore DB_PATH first
        db.DB_PATH = old_db_path

        # force-release sqlite handles
        gc.collect()

        # retry delete (Windows file lock)
        for _ in range(60):
            try:
                shutil.rmtree(td)
                break
            except PermissionError:
                time.sleep(0.1)


# ============================================================
# 1) Users Table Setup (columns exist)
# ============================================================
def test_users_table_has_expected_columns(client):
    conn = sqlite3.connect(db.DB_PATH)
    cols = table_columns(conn, "users")
    conn.close()

    assert "id" in cols
    assert "email" in cols
    assert "username" in cols
    assert "password_hash" in cols
    assert "role" in cols
    assert "created_at" in cols


# ============================================================
# 2) Signup API
# ============================================================
def test_signup_success_creates_user(client):
    body = signup_body(email="suc@example.com", username="teststudent1", role="student")
    r = client.post("/auth/signup", json=body)
    assert r.status_code in (200, 201), r.text

    user = db.get_user_by_username("teststudent1")
    assert user is not None
    assert user["email"] == "suc@example.com"
    assert user["role"] == "student"
    assert user["password_hash"]


def test_signup_duplicate_username_returns_409(client):
    r1 = client.post("/auth/signup", json=signup_body(email="u1@example.com", username="dupuser1"))
    assert r1.status_code in (200, 201), r1.text

    r2 = client.post("/auth/signup", json=signup_body(email="u2@example.com", username="dupuser1"))
    assert r2.status_code == 409, r2.text


def test_signup_duplicate_email_returns_409(client):
    r1 = client.post("/auth/signup", json=signup_body(email="dup@example.com", username="userAAA"))
    assert r1.status_code in (200, 201), r1.text

    r2 = client.post("/auth/signup", json=signup_body(email="dup@example.com", username="userBBB"))
    assert r2.status_code == 409, r2.text


# ============================================================
# 3) Validation Errors (missing fields / mismatch / weak / invalid role)
# ============================================================
def test_signup_missing_required_fields_422(client):
    r = client.post("/auth/signup", json={})
    assert r.status_code == 422, r.text


def test_signup_password_mismatch_422(client):
    body = signup_body(
        email="m1@example.com",
        username="mismatch1",
        password="Test12345",
        confirm_password="Different123",
    )
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 422, r.text


def test_signup_weak_password_422(client):
    body = signup_body(
        email="w1@example.com",
        username="weak111",
        password="password",
        confirm_password="password",
    )
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 422, r.text


def test_signup_invalid_role_422(client):
    body = signup_body(email="r1@example.com", username="badrole1", role="admin")
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 422, r.text


def test_signup_invalid_username_format_422(client):
    body = signup_body(email="u3@example.com", username="!!bad")
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 422, r.text


def test_signup_invalid_email_format_422(client):
    body = signup_body(email="not-an-email", username="emailbad1")
    r = client.post("/auth/signup", json=body)
    assert r.status_code == 422, r.text


# ============================================================
# 4) Login API
# ============================================================
def test_login_success_returns_token_and_role(client):
    r1 = client.post(
        "/auth/signup",
        json=signup_body(email="l1@example.com", username="loginuser1", role="student"),
    )
    assert r1.status_code in (200, 201), r1.text

    r2 = client.post("/auth/login", json=login_body(username="loginuser1", password="Test12345"))
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert "access_token" in data, data
    assert data["token_type"] == "bearer"
    assert data["role"] == "student"


def test_login_unknown_user_shows_error_message(client):
    res = client.post("/auth/login", json=login_body(username="no_user", password="Test12345"))
    assert res.status_code == 401, res.text
    assert res.json()["detail"] == "Invalid credentials. Please check your username and password."


def test_login_invalid_password_shows_error_message(client):
    r1 = client.post(
        "/auth/signup",
        json=signup_body(email="s2@example.com", username="stu222", role="student"),
    )
    assert r1.status_code in (200, 201), r1.text

    res = client.post("/auth/login", json=login_body(username="stu222", password="Wrong12345"))
    assert res.status_code == 401, res.text
    assert res.json()["detail"] == "Invalid credentials. Please check your username and password."


# ============================================================
# 5) RBAC / Protected routes
# ============================================================
def test_student_cannot_access_instructor_page(client):
    r1 = client.post(
        "/auth/signup",
        json=signup_body(email="s1@example.com", username="stu111", role="student"),
    )
    assert r1.status_code in (200, 201), r1.text

    r = client.post("/auth/login", json=login_body(username="stu111", password="Test12345"))
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    assert token, r.json()

    res = client.get("/instructor/publish", headers=auth_headers(token))
    assert res.status_code == 403, res.text


def test_instructor_can_access_instructor_page(client):
    r1 = client.post(
        "/auth/signup",
        json=signup_body(email="i1@example.com", username="ins111", role="instructor"),
    )
    assert r1.status_code in (200, 201), r1.text

    r = client.post("/auth/login", json=login_body(username="ins111", password="Test12345"))
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    assert token, r.json()

    res = client.get("/instructor/publish", headers=auth_headers(token))
    assert res.status_code == 200, res.text


def test_student_results_ok_with_student_token(client):
    r1 = client.post(
        "/auth/signup",
        json=signup_body(email="s3@example.com", username="stu333", role="student"),
    )
    assert r1.status_code in (200, 201), r1.text

    r = client.post("/auth/login", json=login_body(username="stu333", password="Test12345"))
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    assert token, r.json()

    res = client.get("/student/results", headers=auth_headers(token))
    assert res.status_code == 200, res.text


def test_instructor_publish_ok_with_instructor_token(client):
    r1 = client.post(
        "/auth/signup",
        json=signup_body(email="i2@example.com", username="ins222", role="instructor"),
    )
    assert r1.status_code in (200, 201), r1.text

    r = client.post("/auth/login", json=login_body(username="ins222", password="Test12345"))
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    assert token, r.json()

    res = client.get("/instructor/publish", headers=auth_headers(token))
    assert res.status_code == 200, res.text
