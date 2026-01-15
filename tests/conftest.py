import os
import sys
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Add backend directory to path so imports work
backend_dir = Path(__file__).parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

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

    # Initialize the database before app starts (so tables exist for startup event)
    db.init_db()

    with TestClient(app) as c:
        yield c
