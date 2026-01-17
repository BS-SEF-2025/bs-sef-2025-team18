import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Dict, Any, Iterator

DB_PATH = str(Path(__file__).with_name("app.db"))


def get_db_path() -> str:
    env_path = os.getenv("DATABASE_PATH") or os.getenv("DATABASE_URL")
    return env_path if env_path else DB_PATH


@contextmanager
def get_conn(path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """
    IMPORTANT (Windows):
    sqlite Connection context manager does NOT close the connection.
    This wrapper ensures every connection is ALWAYS closed.
    """
    conn = sqlite3.connect(path or get_db_path(), check_same_thread=False)
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

        # ✅ Peer review submissions (stores individual reviews with round tracking)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS peer_review_submissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reviewer_id INTEGER NOT NULL,
                reviewee_id INTEGER NOT NULL,
                criterion_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                round TEXT NOT NULL DEFAULT 'round1',
                submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (reviewer_id) REFERENCES users(id),
                FOREIGN KEY (reviewee_id) REFERENCES users(id),
                FOREIGN KEY (criterion_id) REFERENCES peer_review_criteria(id)
            );
            """
        )
        # Create unique index for conflict resolution (includes round)
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_peer_review_unique 
            ON peer_review_submissions(reviewer_id, reviewee_id, criterion_id, round);
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

        # ✅ Evaluation criteria table (for instructor-defined criteria)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS criteria (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            """
        )

        # ✅ Review state table (tracks review lifecycle: draft, started, published)
        def _needs_review_state_migration() -> bool:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='review_state'"
            ).fetchone()
            if not row or not row["sql"]:
                return False
            return "draft" not in row["sql"]

        def _map_review_state(value: Optional[str]) -> str:
            if value in ("draft", "started", "published"):
                return value
            if value == "round1":
                return "draft"
            if value == "round2":
                return "started"
            return "draft"

        if _needs_review_state_migration():
            # Preserve current status if possible, then rebuild with new constraint.
            current_status_row = conn.execute(
                "SELECT status FROM review_state WHERE id = 1"
            ).fetchone()
            current_status = _map_review_state(current_status_row["status"]) if current_status_row else "draft"
            conn.execute("DROP TABLE IF EXISTS review_state")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'started', 'published'))
                );
                """
            )
            conn.execute("INSERT OR REPLACE INTO review_state (id, status) VALUES (1, ?)", (current_status,))
        else:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'started', 'published'))
                );
                """
            )

            # Initialize review_state if it doesn't exist
            existing_state = conn.execute("SELECT COUNT(*) AS c FROM review_state").fetchone()
            if existing_state and int(existing_state["c"]) == 0:
                conn.execute("INSERT INTO review_state (id, status) VALUES (1, 'draft')")

        # Migration: Add round column to peer_review_submissions if it doesn't exist
        if not _column_exists(conn, "peer_review_submissions", "round"):
            conn.execute("ALTER TABLE peer_review_submissions ADD COLUMN round TEXT NOT NULL DEFAULT 'round1'")
            # Update unique constraint to include round
            conn.execute("DROP INDEX IF EXISTS idx_peer_review_unique")
            conn.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_peer_review_unique 
                ON peer_review_submissions(reviewer_id, reviewee_id, criterion_id, round);
                """
            )

        # ✅ Submission deadline table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submission_deadline (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                deadline TEXT
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


def insert_peer_review_criteria(
    title: str, required: int, scale_min: int, scale_max: int, weight: float = 1.0
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO peer_review_criteria (title, required, scale_min, scale_max, weight)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title, required, scale_min, scale_max, weight),
        )


# =========================
# Peer Review Submissions
# =========================
def save_peer_review_submission(reviewer_id: int, reviewee_id: int, criterion_id: int, rating: int, round: str = "round1") -> None:
    """Save or update a peer review submission for a specific round."""
    with get_conn() as conn:
        # Check if review already exists for this round
        existing = conn.execute(
            """
            SELECT id FROM peer_review_submissions
            WHERE reviewer_id = ? AND reviewee_id = ? AND criterion_id = ? AND round = ?
            """,
            (reviewer_id, reviewee_id, criterion_id, round),
        ).fetchone()
        
        if existing:
            # Update existing review
            conn.execute(
                """
                UPDATE peer_review_submissions
                SET rating = ?, submitted_at = datetime('now')
                WHERE reviewer_id = ? AND reviewee_id = ? AND criterion_id = ? AND round = ?
                """,
                (rating, reviewer_id, reviewee_id, criterion_id, round),
            )
        else:
            # Insert new review
            conn.execute(
                """
                INSERT INTO peer_review_submissions (reviewer_id, reviewee_id, criterion_id, rating, round)
                VALUES (?, ?, ?, ?, ?)
                """,
                (reviewer_id, reviewee_id, criterion_id, rating, round),
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


def get_reviews_submitted_by_reviewer_for_reviewee(reviewer_id: int, reviewee_id: int, round: Optional[str] = None) -> list[dict]:
    """Get all reviews submitted by a reviewer for a specific reviewee (for editing).
    
    Args:
        reviewer_id: ID of the reviewer
        reviewee_id: ID of the reviewee
        round: Optional round filter ('round1', 'round2'). If None, returns all rounds.
    """
    with get_conn() as conn:
        if round:
            rows = conn.execute(
                """
                SELECT
                    prs.criterion_id,
                    prs.rating,
                    prs.submitted_at,
                    prs.round
                FROM peer_review_submissions prs
                WHERE prs.reviewer_id = ? AND prs.reviewee_id = ? AND prs.round = ?
                ORDER BY prs.criterion_id
                """,
                (reviewer_id, reviewee_id, round),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    prs.criterion_id,
                    prs.rating,
                    prs.submitted_at,
                    prs.round
                FROM peer_review_submissions prs
                WHERE prs.reviewer_id = ? AND prs.reviewee_id = ?
                ORDER BY prs.round, prs.criterion_id
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


def clear_results_publication() -> None:
    """Clear any published results (re-open submissions/edits)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM peer_review_results_published")


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, email, username, password_hash, role, created_at FROM users WHERE id=?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None


def get_individual_peer_reviews_for_student(student_id: int) -> list[dict]:
    """
    Get individual peer reviews received by a student, grouped by reviewer.
    Returns a list of reviews, each containing reviewer info and all their ratings.
    """
    with get_conn() as conn:
        # Get all reviews for this student
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
            ORDER BY prs.reviewer_id, prs.criterion_id
            """,
            (student_id,),
        ).fetchall()
        
        if not rows:
            return []
        
        # Group by reviewer
        reviews_by_reviewer = {}
        for row in rows:
            reviewer_id = row["reviewer_id"]
            reviewer_username = row["reviewer_username"]
            
            if reviewer_id not in reviews_by_reviewer:
                reviews_by_reviewer[reviewer_id] = {
                    "reviewer_id": reviewer_id,
                    "reviewer_username": reviewer_username,
                    "submitted_at": row["submitted_at"],
                    "ratings": []
                }
            
            reviews_by_reviewer[reviewer_id]["ratings"].append({
                "criterion_id": row["criterion_id"],
                "criterion_title": row["criterion_title"],
                "criterion_weight": float(row["criterion_weight"]),
                "rating": row["rating"],
                "scale_min": row["scale_min"],
                "scale_max": row["scale_max"]
            })
        
        # Convert to list and calculate total scores
        result = []
        for reviewer_id, review_data in reviews_by_reviewer.items():
            ratings = review_data["ratings"]
            
            # Calculate weighted total score for this review
            total_weighted_score = 0.0
            total_weight = 0.0
            for rating_data in ratings:
                weight = rating_data["criterion_weight"]
                rating = rating_data["rating"]
                total_weighted_score += rating * weight
                total_weight += weight
            
            total_score = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0
            
            result.append({
                "reviewer_id": review_data["reviewer_id"],
                "reviewer_username": review_data["reviewer_username"],
                "submitted_at": review_data["submitted_at"],
                "ratings": ratings,
                "total_score": total_score
            })
        
        # Sort by submitted_at (most recent first)
        result.sort(key=lambda x: x["submitted_at"], reverse=True)
        
        return result


def get_reviews_submitted_by_reviewer(reviewer_id: int) -> list[dict]:
    """
    Get all reviews submitted by a reviewer, grouped by reviewee.
    Returns a list of reviews, each containing reviewee info and all ratings given to them.
    """
    with get_conn() as conn:
        # Get all reviews submitted by this reviewer
        rows = conn.execute(
            """
            SELECT 
                prs.reviewer_id,
                prs.reviewee_id,
                u.username as reviewee_username,
                prs.criterion_id,
                prc.title as criterion_title,
                prc.weight as criterion_weight,
                prc.scale_min,
                prc.scale_max,
                prs.rating,
                prs.submitted_at
            FROM peer_review_submissions prs
            JOIN users u ON prs.reviewee_id = u.id
            JOIN peer_review_criteria prc ON prs.criterion_id = prc.id
            WHERE prs.reviewer_id = ?
            ORDER BY prs.reviewee_id, prs.criterion_id
            """,
            (reviewer_id,),
        ).fetchall()
        
        if not rows:
            return []
        
        # Group by reviewee
        reviews_by_reviewee = {}
        for row in rows:
            reviewee_id = row["reviewee_id"]
            reviewee_username = row["reviewee_username"]
            
            if reviewee_id not in reviews_by_reviewee:
                reviews_by_reviewee[reviewee_id] = {
                    "reviewee_id": reviewee_id,
                    "reviewee_username": reviewee_username,
                    "submitted_at": row["submitted_at"],
                    "ratings": []
                }
            
            reviews_by_reviewee[reviewee_id]["ratings"].append({
                "criterion_id": row["criterion_id"],
                "criterion_title": row["criterion_title"],
                "criterion_weight": float(row["criterion_weight"]),
                "rating": row["rating"],
                "scale_min": row["scale_min"],
                "scale_max": row["scale_max"]
            })
        
        # Convert to list and calculate total scores
        result = []
        for reviewee_id, review_data in reviews_by_reviewee.items():
            ratings = review_data["ratings"]
            
            # Calculate weighted total score for this review
            total_weighted_score = 0.0
            total_weight = 0.0
            for rating_data in ratings:
                weight = rating_data["criterion_weight"]
                rating = rating_data["rating"]
                total_weighted_score += rating * weight
                total_weight += weight
            
            total_score = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0
            
            result.append({
                "reviewee_id": review_data["reviewee_id"],
                "reviewee_username": review_data["reviewee_username"],
                "submitted_at": review_data["submitted_at"],
                "ratings": ratings,
                "total_score": total_score
            })
        
        # Sort by submitted_at (most recent first)
        result.sort(key=lambda x: x["submitted_at"], reverse=True)
        
        return result


# =========================
# Evaluation Criteria Management
# =========================
def create_criterion(name: str, description: str) -> int:
    """Create a new evaluation criterion. Returns the ID of the created criterion."""
    with get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO criteria (name, description) VALUES (?, ?)",
            (name.strip(), description.strip()),
        )
        return cursor.lastrowid


def get_all_criteria() -> list[dict]:
    """Get all evaluation criteria."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, name, description, created_at FROM criteria ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]


def get_criterion_by_id(criterion_id: int) -> Optional[Dict[str, Any]]:
    """Get a criterion by ID."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, description, created_at FROM criteria WHERE id = ?",
            (criterion_id,),
        ).fetchone()
        return dict(row) if row else None


def update_criterion(criterion_id: int, name: str, description: str) -> bool:
    """Update a criterion. Returns True if updated, False if not found."""
    with get_conn() as conn:
        cursor = conn.execute(
            "UPDATE criteria SET name = ?, description = ? WHERE id = ?",
            (name.strip(), description.strip(), criterion_id),
        )
        return cursor.rowcount > 0


def delete_criterion(criterion_id: int) -> bool:
    """Delete a criterion. Returns True if deleted, False if not found."""
    with get_conn() as conn:
        cursor = conn.execute("DELETE FROM criteria WHERE id = ?", (criterion_id,))
        return cursor.rowcount > 0


# =========================
# Review State Management
# =========================
def get_review_state() -> str:
    """Get the current review state status. Returns 'draft' by default if not set."""
    with get_conn() as conn:
        row = conn.execute("SELECT status FROM review_state WHERE id = 1").fetchone()
        if not row:
            return "draft"
        status = row["status"]
        if status == "round1":
            return "draft"
        if status == "round2":
            return "started"
        return status


def set_review_state(status: str) -> None:
    """Set the review state status. Must be 'draft', 'started', or 'published'."""
    if status in ("round1", "round2"):
        status = "draft" if status == "round1" else "started"
    if status not in ("draft", "started", "published"):
        raise ValueError(f"Invalid status: {status}. Must be 'draft', 'started', or 'published'")
    
    with get_conn() as conn:
        # Use INSERT OR REPLACE to ensure id=1 always exists
        conn.execute(
            "INSERT OR REPLACE INTO review_state (id, status) VALUES (1, ?)",
            (status,),
        )


# =========================
# Submission Deadline Management
# =========================
def get_submission_deadline() -> Optional[str]:
    """Get the current submission deadline. Returns ISO datetime string or None if not set."""
    with get_conn() as conn:
        row = conn.execute("SELECT deadline FROM submission_deadline WHERE id = 1").fetchone()
        return row["deadline"] if row else None


def set_submission_deadline(deadline: Optional[str]) -> None:
    """Set or clear the submission deadline. Pass None to clear."""
    with get_conn() as conn:
        if deadline is None:
            conn.execute("DELETE FROM submission_deadline WHERE id = 1")
        else:
            conn.execute(
                "INSERT OR REPLACE INTO submission_deadline (id, deadline) VALUES (1, ?)",
                (deadline,),
            )


def is_submission_open() -> bool:
    """Check if submissions are currently open (deadline not passed or not set)."""
    from datetime import datetime
    deadline = get_submission_deadline()
    if deadline is None:
        return True  # No deadline = always open
    try:
        deadline_dt = datetime.fromisoformat(deadline.replace('Z', '+00:00'))
        now = datetime.now(deadline_dt.tzinfo) if deadline_dt.tzinfo else datetime.now()
        return now < deadline_dt
    except Exception:
        return True  # If parsing fails, allow submissions
