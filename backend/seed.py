import db
from security import hash_password


def seed_users() -> None:
    db.init_db()

    if not db.get_user_by_username("student1"):
        db.create_user(
            "student1@student.demo",   # email
            "student1",                # username
            hash_password("Student123"),
            "student",
        )

    if not db.get_user_by_username("instructor1"):
        db.create_user(
            "instructor1@inst.demo",
            "instructor1",
            hash_password("Instructor123"),
            "instructor",
        )


def seed_peer_review_criteria() -> None:
    """
    Seeds predefined evaluation criteria once.
    Safe to run every startup (only inserts if empty).
    """
    db.init_db()

    if db.count_peer_review_criteria() > 0:
        return

    predefined = [
        ("Contribution", 1, 1, 5),
        ("Communication", 1, 1, 5),
        ("Quality of Work", 1, 1, 5),
        ("Reliability", 1, 1, 5),
    ]

    for title, required, smin, smax in predefined:
        db.insert_peer_review_criteria(title, required, smin, smax)
