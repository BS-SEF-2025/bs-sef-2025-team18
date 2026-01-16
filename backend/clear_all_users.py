"""
Script to delete all user accounts and related data from the database.

Usage:
    python clear_all_users.py

Or from project root:
    python backend/clear_all_users.py

This will:
1. Delete all peer review submissions (which reference users)
2. Delete all published results (which reference users)
3. Delete all user accounts

Alternative: You can also use the API endpoint:
    DELETE http://127.0.0.1:8000/admin/users/all
    (Requires instructor authentication)
"""
import db
from pathlib import Path

def clear_all_users():
    """Delete all users and all data that references them."""
    print("Clearing all user accounts and related data...")
    
    with db.get_conn() as conn:
        # First, delete all data that references users (to avoid foreign key constraint issues)
        print("  - Deleting peer review submissions...")
        conn.execute("DELETE FROM peer_review_submissions")
        
        print("  - Deleting published results...")
        conn.execute("DELETE FROM peer_review_results_published")
        
        # Now delete all users
        print("  - Deleting all user accounts...")
        cursor = conn.execute("DELETE FROM users")
        deleted_count = cursor.rowcount
        
        print(f"\n[SUCCESS] Successfully deleted {deleted_count} user account(s) and all related data.")
        print("  The database is now empty of all user accounts.")
    
    # Verify the deletion
    with db.get_conn() as conn:
        user_count = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        submissions_count = conn.execute("SELECT COUNT(*) AS c FROM peer_review_submissions").fetchone()["c"]
        published_count = conn.execute("SELECT COUNT(*) AS c FROM peer_review_results_published").fetchone()["c"]
        
        print(f"\nVerification:")
        print(f"  - Users remaining: {user_count}")
        print(f"  - Submissions remaining: {submissions_count}")
        print(f"  - Published results remaining: {published_count}")

if __name__ == "__main__":
    try:
        clear_all_users()
    except Exception as e:
        print(f"\n[ERROR] Error: {e}")
        import traceback
        traceback.print_exc()
