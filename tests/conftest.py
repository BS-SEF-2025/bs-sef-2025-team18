import os
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend import db


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Create isolated sqlite DB for tests (do NOT use backend/app.db)
    test_db_path = str(tmp_path / "test_app.db")

    # Redirect backend.db.DB_PATH to temp DB
    monkeypatch.setattr(db, "DB_PATH", test_db_path, raising=False)

    # Ensure clean DB file
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    with TestClient(app) as c:
        yield c
