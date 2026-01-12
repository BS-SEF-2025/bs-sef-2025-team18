import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any

DB_PATH = str(Path(__file__).with_name("app.db"))


@contextmanager
def get_conn(path: Optional[str] = None) -> sqlite3.Connection:
    """
    IMPORTANT (Windows):
    sqlite Connection context manager does NOT close the connection.
    This wrapper ensures every connection is ALWAYS closed.
    """
    conn = sqlite3.connect(path or DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return any(r["name"] == column for r in rows)


def init_db() -> None:
    with get_conn() as conn:
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

        # Migration for existing DBs (safe to run repeatedly)
        if not _column_exists(conn, "users", "email"):
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT;")

        if not _column_exists(conn, "users", "created_at"):
            conn.execute(
                "ALTER TABLE users ADD COLUMN created_at TEXT NOT NULL DEFAULT (datetime('now'));"
            )

        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email);"
        )

        # ✅ Peer review predefined criteria (used by Submit Peer Review form)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS peer_review_criteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                required INTEGER NOT NULL DEFAULT 1,
                scale_min INTEGER NOT NULL DEFAULT 1,
                scale_max INTEGER NOT NULL DEFAULT 5
            );
            """
        )


def create_user(email: str, username: str, password_hash: str, role: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (email, username, password_hash, role) VALUES (?, ?, ?, ?)",
            (email, username, password_hash, role),
        )


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, username, password_hash, role, created_at FROM users WHERE username=?",
            (username,),
        ).fetchone()
        return dict(row) if row else None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, username, password_hash, role FROM users WHERE email=?",
            (email,),
        ).fetchone()
        return dict(row) if row else None


def user_exists(username: str) -> bool:
    return get_user_by_username(username) is not None


# =========================
# Peer Review (NEW helpers)
# =========================
def get_student_teammates_except(username: str):
    """
    Minimal safe 'teammates' implementation:
    return all students except the current user.
    (Later can be replaced with group-based membership without breaking the API.)
    """
    me = get_user_by_username(username)
    if not me:
        return []

    my_id = me["id"]

    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username
            FROM users
            WHERE role = 'student' AND id != ?
            ORDER BY username
            """,
            (my_id,),
        ).fetchall()

    return [{"id": r["id"], "username": r["username"]} for r in rows]


def get_peer_review_criteria():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, required, scale_min, scale_max
            FROM peer_review_criteria
            ORDER BY id
            """
        ).fetchall()

    return [
        {
            "id": r["id"],
            "title": r["title"],
            "required": bool(r["required"]),
            "scale": {"min": r["scale_min"], "max": r["scale_max"]},
        }
        for r in rows
    ]


def count_peer_review_criteria() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM peer_review_criteria").fetchone()
        return int(row["c"]) if row else 0


def insert_peer_review_criteria(title: str, required: int, scale_min: int, scale_max: int) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO peer_review_criteria (title, required, scale_min, scale_max)
            VALUES (?, ?, ?, ?)
            """,
            (title, required, scale_min, scale_max),
        )
