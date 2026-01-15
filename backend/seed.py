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
    Seeds default criteria into peer_review_criteria table ONLY (for students to use).
    These criteria will appear in Rating Criteria for students but NOT in Evaluation Criteria for instructors.
    Instructors can still add their own criteria through the UI.
    """
    db.init_db()
    
    # ALWAYS remove seeded criteria from criteria table (instructor view) - keep it clean
    # This ensures they never show up in the Evaluation Criteria list for instructors
    seeded_names = {"Contribution", "Communication", "Quality of Work", "Reliability"}
    all_criteria = db.get_all_criteria()
    
    for criterion in all_criteria:
        criterion_name = criterion["name"].strip()
        # Use case-insensitive comparison to catch variations
        if criterion_name in seeded_names or criterion_name.lower() in {name.lower() for name in seeded_names}:
            try:
                db.delete_criterion(criterion["id"])
                print(f"Removed seeded criterion from instructor Evaluation Criteria list: {criterion_name}")
            except Exception as e:
                print(f"Error removing criterion {criterion_name}: {e}")
    
    # Seed default criteria into peer_review_criteria table (for students)
    predefined = [
        ("Contribution", "Evaluate the team member's level of contribution to team projects and activities.", 1, 1, 5),
        ("Communication", "Assess how effectively the team member communicates ideas, feedback, and information with the team.", 1, 1, 5),
        ("Quality of Work", "Rate the quality, accuracy, and thoroughness of the work produced by this team member.", 1, 1, 5),
        ("Reliability", "Evaluate how dependable and consistent the team member is in meeting deadlines and commitments.", 1, 1, 5),
    ]
    
    # Get existing peer_review_criteria to avoid duplicates
    existing_prc = db.get_peer_review_criteria()
    existing_prc_titles = {prc["title"].strip().lower() for prc in existing_prc}
    
    # Create each default criterion in peer_review_criteria if it doesn't exist
    for name, description, required, smin, smax in predefined:
        name_lower = name.strip().lower()
        if name_lower not in existing_prc_titles:
            db.insert_peer_review_criteria(name, required, smin, smax)
            print(f"Seeded default criterion for students: {name}")
            existing_prc_titles.add(name_lower)
