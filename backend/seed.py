from . import db
from .security import hash_password


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
