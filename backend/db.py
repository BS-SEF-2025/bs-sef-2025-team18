import sqlite3
from typing import Optional, Dict, Any

from pathlib import Path

DB_PATH = str(Path(__file__).with_name("app.db"))



def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return any(r["name"] == column for r in rows)


def init_db() -> None:
    with get_conn() as conn:
        # Create table if it doesn't exist (new installs)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student','instructor')),
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

        # Migration for existing DB
        if not _column_exists(conn, "users", "email"):
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT;")

        if not _column_exists(conn, "users", "created_at"):
            conn.execute(
                "ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'));"
            )

        # Ensure unique email
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email);"
        )

        conn.commit()



def create_user(email: str, username: str, password_hash: str, role: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, username, password_hash, role) VALUES (?, ?, ?, ?)",
            (email, username, password_hash, role),
        )
        conn.commit()


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, username, password_hash, role, created_at FROM users WHERE username=?",
            (username,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, username, password_hash, role FROM users WHERE email=?",
            (email,),
        ).fetchone()
        return dict(row) if row else None

def user_exists(username: str) -> bool:
    """Return True if a user with given username exists."""
    return get_user_by_username(username) is not None
    
