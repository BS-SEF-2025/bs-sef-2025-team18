import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any, Iterator

DB_PATH = str(Path(__file__).with_name("app.db"))


@contextmanager
def get_conn(path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
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
                scale_max INTEGER NOT NULL DEFAULT 5,
                weight REAL NOT NULL DEFAULT 1.0
            );
            """
        )

        # ✅ Peer review submissions (stores individual reviews)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS peer_review_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reviewer_id INTEGER NOT NULL,
                reviewee_id INTEGER NOT NULL,
                criterion_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (reviewer_id) REFERENCES users(id),
                FOREIGN KEY (reviewee_id) REFERENCES users(id),
                FOREIGN KEY (criterion_id) REFERENCES peer_review_criteria(id),
                UNIQUE(reviewer_id, reviewee_id, criterion_id)
            );
            """
        )
        # Create unique index for conflict resolution
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_peer_review_unique 
            ON peer_review_submissions(reviewer_id, reviewee_id, criterion_id);
            """
        )

        # ✅ Results publication status
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS peer_review_results_published (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                published_at TEXT NOT NULL DEFAULT (datetime('now')),
                published_by INTEGER NOT NULL,
                FOREIGN KEY (published_by) REFERENCES users(id)
            );
            """
        )

        # Migration: Add weight column to criteria if it doesn't exist
        if not _column_exists(conn, "peer_review_criteria", "weight"):
            conn.execute("ALTER TABLE peer_review_criteria ADD COLUMN weight REAL NOT NULL DEFAULT 1.0;")


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


def get_all_students():
    """Get all students (for instructors)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, username, email
            FROM users
            WHERE role = 'student'
            ORDER BY username
            """
        ).fetchall()
    return [{"id": r["id"], "username": r["username"], "email": r["email"]} for r in rows]


def get_peer_review_criteria():
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, title, required, scale_min, scale_max, weight
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
            "weight": float(r["weight"]) if "weight" in r.keys() else 1.0,
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
            INSERT INTO peer_review_criteria (title, required, scale_min, scale_max, weight)
            VALUES (?, ?, ?, ?, 1.0)
            """,
            (title, required, scale_min, scale_max),
        )


# =========================
# Peer Review Submissions
# =========================
def save_peer_review_submission(reviewer_id: int, reviewee_id: int, criterion_id: int, rating: int) -> None:
    """Save or update a peer review submission."""
    with get_conn() as conn:
        # Check if review already exists
        existing = conn.execute(
            """
            SELECT id FROM peer_review_submissions
            WHERE reviewer_id = ? AND reviewee_id = ? AND criterion_id = ?
            """,
            (reviewer_id, reviewee_id, criterion_id),
        ).fetchone()
        
        if existing:
            # Update existing review
            conn.execute(
                """
                UPDATE peer_review_submissions
                SET rating = ?, submitted_at = datetime('now')
                WHERE reviewer_id = ? AND reviewee_id = ? AND criterion_id = ?
                """,
                (rating, reviewer_id, reviewee_id, criterion_id),
            )
        else:
            # Insert new review
            conn.execute(
                """
                INSERT INTO peer_review_submissions (reviewer_id, reviewee_id, criterion_id, rating)
                VALUES (?, ?, ?, ?)
                """,
                (reviewer_id, reviewee_id, criterion_id, rating),
            )


def get_peer_reviews_for_student(student_id: int) -> list[dict]:
    """Get all peer reviews received by a student."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT 
                prs.reviewer_id,
                u.username as reviewer_username,
                prs.reviewee_id,
                prs.criterion_id,
                prc.title as criterion_title,
                prc.weight as criterion_weight,
                prc.scale_min,
                prc.scale_max,
                prs.rating,
                prs.submitted_at
            FROM peer_review_submissions prs
            JOIN users u ON prs.reviewer_id = u.id
            JOIN peer_review_criteria prc ON prs.criterion_id = prc.id
            WHERE prs.reviewee_id = ?
            ORDER BY prs.submitted_at DESC
            """,
            (student_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_reviews_submitted_by_reviewer_for_reviewee(reviewer_id: int, reviewee_id: int) -> list[dict]:
    """Get all reviews submitted by a reviewer for a specific reviewee (for editing)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT 
                prs.criterion_id,
                prs.rating,
                prs.submitted_at
            FROM peer_review_submissions prs
            WHERE prs.reviewer_id = ? AND prs.reviewee_id = ?
            ORDER BY prs.criterion_id
            """,
            (reviewer_id, reviewee_id),
        ).fetchall()
        return [dict(row) for row in rows]


def are_results_published() -> bool:
    """Check if peer review results have been published."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM peer_review_results_published"
        ).fetchone()
        return int(row["c"]) > 0 if row else False


def publish_results(published_by: int) -> None:
    """Publish peer review results (only if not already published)."""
    with get_conn() as conn:
        # Check if already published
        existing = conn.execute(
            "SELECT COUNT(*) AS c FROM peer_review_results_published"
        ).fetchone()
        if existing and int(existing["c"]) > 0:
            return  # Already published
        
        # Insert the publication record
        conn.execute(
            "INSERT INTO peer_review_results_published (published_by) VALUES (?)",
            (published_by,),
        )
        # Commit is handled by the context manager


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, username, password_hash, role, created_at FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
