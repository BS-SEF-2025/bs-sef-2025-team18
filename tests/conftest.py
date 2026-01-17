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
from backend.seed import seed_users, seed_peer_review_criteria


@pytest.fixture(autouse=True)
def test_db(tmp_path, monkeypatch):
    # Create isolated sqlite DB for tests (do NOT use backend/app.db)
    test_db_path = str(tmp_path / "test_app.db")

    # Redirect backend DB path via environment variable and module override
    monkeypatch.setenv("DATABASE_PATH", test_db_path)
    monkeypatch.setattr(db, "DB_PATH", test_db_path, raising=False)

    # Ensure clean DB file
    if os.path.exists(test_db_path):
        os.remove(test_db_path)

    # Initialize schema and seed required data
    db.init_db()
    seed_users()
    seed_peer_review_criteria()

    yield test_db_path


@pytest.fixture()
def client(test_db):
    with TestClient(app) as c:
        yield c
