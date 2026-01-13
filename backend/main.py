import re
from typing import Optional, Callable

from fastapi import FastAPI, Depends, HTTPException, Header, APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

import db
from security import hash_password, verify_password
from token_service import create_access_token, decode_access_token
from seed import seed_users, seed_peer_review_criteria

app = FastAPI(title="PeerEval Pro - Role Based Access")

# ✅ CORS (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Init DB + seed only after app starts
@app.on_event("startup")
def _startup():
    db.init_db()
    seed_users()
    seed_peer_review_criteria()


# -------------------------
# Auth Router
# -------------------------
auth_router = APIRouter(prefix="/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def password_is_strong(pw: str) -> bool:
    return len(pw) >= 8 and any(c.isdigit() for c in pw) and any(c.isalpha() for c in pw)


class SignupBody(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=200)
    confirm_password: str = Field(min_length=8, max_length=200)
    role: str  # student / instructor

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("Username must be 3–20 characters (letters, numbers, underscore).")
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", v):
            raise ValueError("Invalid email format.")
        return v

    @model_validator(mode="after")
    def validate_all(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        if not password_is_strong(self.password):
            raise ValueError("Password must be at least 8 characters and contain letters and numbers.")
        if self.role not in ("student", "instructor"):
            raise ValueError("Invalid role.")
        return self


@auth_router.post("/signup", status_code=201)
def signup(body: SignupBody):
    if db.get_user_by_username(body.username):
        raise HTTPException(status_code=409, detail="Username already exists.")
    if db.get_user_by_email(body.email):
        raise HTTPException(status_code=409, detail="Email already exists.")

    password_hash = hash_password(body.password)
    db.create_user(body.email, body.username, password_hash, body.role)
    return {"ok": True}


class RegisterBody(BaseModel):
    email: str
    username: str
    password: str
    role: str


@auth_router.post("/register")
def register(body: RegisterBody):
    if body.role not in ("student", "instructor"):
        raise HTTPException(status_code=400, detail="Role must be student or instructor")

    if db.get_user_by_username(body.username):
        raise HTTPException(status_code=409, detail="Username already exists")

    db.create_user(body.email, body.username, hash_password(body.password), body.role)
    return {"ok": True}


class LoginBody(BaseModel):
    username: str
    password: str


@auth_router.post("/login")
def login(body: LoginBody):
    user = db.get_user_by_username(body.username)

    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials. Please check your username and password.")

    token = create_access_token(username=user["username"], role=user["role"])
    return {"access_token": token, "role": user["role"]}


# -------------------------
# Auth dependencies & protected routes
# -------------------------
def get_current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = decode_access_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {"username": payload["sub"], "role": payload["role"]}


def require_roles(*allowed_roles: str) -> Callable:
    allowed = set(allowed_roles)

    def _dep(user=Depends(get_current_user)):
        if user["role"] not in allowed:
            raise HTTPException(status_code=403, detail="Forbidden: role not allowed")
        return user

    return _dep


@app.get("/me")
def me(user=Depends(get_current_user)):
    return user


@app.get("/student/results")
def student_results(user=Depends(require_roles("student"))):
    return {"page": "Student Peer Review Results", "user": user}


@app.get("/instructor/publish")
def get_publish_status(user=Depends(require_roles("instructor"))):
    """Get the current publish status of peer review results."""
    is_published = db.are_results_published()
    return {"published": is_published}


@app.get("/instructor/students")
def get_all_students(user=Depends(require_roles("instructor"))):
    """Get list of all students (for instructors to select when viewing reports)."""
    students = db.get_all_students()
    return {"students": students}


@app.get("/instructor/submissions")
def get_submission_status(user=Depends(require_roles("instructor"))):
    """Get submission status - which students have submitted reviews."""
    import sqlite3
    from pathlib import Path
    
    students = db.get_all_students()
    criteria = db.get_peer_review_criteria()
    total_criteria = len(criteria)
    
    DB_PATH = str(Path(__file__).parent / "app.db")
    
    submission_status = []
    for student in students:
        student_id = student["id"]
        
        # Get all reviews submitted by this student
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            # Count unique reviewees this student has reviewed
            reviewed_row = conn.execute(
                """
                SELECT COUNT(DISTINCT reviewee_id) as count
                FROM peer_review_submissions
                WHERE reviewer_id = ?
                """,
                (student_id,)
            ).fetchone()
            
            # Count total submissions by this student
            total_row = conn.execute(
                """
                SELECT COUNT(*) as count
                FROM peer_review_submissions
                WHERE reviewer_id = ?
                """,
                (student_id,)
            ).fetchone()
            
            reviewed_count_val = reviewed_row["count"] if reviewed_row else 0
            total_submissions_val = total_row["count"] if total_row else 0
        finally:
            conn.close()
        
        # Calculate if submission is complete
        # A complete submission means they've reviewed all their teammates
        try:
            teammates = db.get_student_teammates_except(student["username"])
            expected_reviews = len(teammates) * total_criteria if total_criteria > 0 else 0
        except Exception:
            # If student has no teammates or error, set to 0
            teammates = []
            expected_reviews = 0
        
        submission_status.append({
            "student_id": student_id,
            "username": student["username"],
            "email": student.get("email", ""),
            "teammates_count": len(teammates),
            "reviewed_count": reviewed_count_val,
            "total_submissions": total_submissions_val,
            "expected_submissions": expected_reviews,
            "is_complete": total_submissions_val >= expected_reviews if expected_reviews > 0 else False,
            "submission_percentage": round((total_submissions_val / expected_reviews * 100) if expected_reviews > 0 else 0, 1)
        })
    
    return {
        "submissions": submission_status,
        "total_students": len(students),
        "total_criteria": total_criteria
    }


@app.post("/instructor/publish")
def publish_results(user=Depends(require_roles("instructor"))):
    """Publish peer review results so students can view their reports."""
    instructor = db.get_user_by_username(user["username"])
    if not instructor:
        raise HTTPException(status_code=404, detail="Instructor not found")
    
    # Check if already published
    is_already_published = db.are_results_published()
    if is_already_published:
        return {"ok": True, "message": "Results are already published. Students can view their reports.", "already_published": True}
    
    # Publish the results
    try:
        db.publish_results(published_by=instructor["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to publish results: {str(e)}")
    
    # Verify publication was successful
    if not db.are_results_published():
        raise HTTPException(status_code=500, detail="Failed to publish results. Publication was not recorded. Please try again.")
    
    return {"ok": True, "message": "Results published successfully. Students can now view their reports."}


# -------------------------
# Peer Review Router
# -------------------------
peer_review_router = APIRouter(prefix="/peer-reviews", tags=["peer-reviews"])


@peer_review_router.get("/form")
def get_peer_review_form(user=Depends(require_roles("student"))):
    teammates = db.get_student_teammates_except(user["username"])
    criteria = db.get_peer_review_criteria()
    return {"teammates": teammates, "criteria": criteria}


@peer_review_router.get("/submitted/{teammate_id}")
def get_submitted_review(teammate_id: int, user=Depends(require_roles("student"))):
    """Get previously submitted review for a specific teammate (for editing)."""
    # Verify the teammate is valid
    teammates = db.get_student_teammates_except(user["username"])
    allowed_teammate_ids = {t["id"] for t in teammates}
    
    if teammate_id not in allowed_teammate_ids:
        raise HTTPException(status_code=404, detail="Teammate not found")
    
    # Get reviewer info
    reviewer = db.get_user_by_username(user["username"])
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")
    
    reviewer_id = reviewer["id"]
    
    # Get submitted reviews
    reviews = db.get_reviews_submitted_by_reviewer_for_reviewee(reviewer_id, teammate_id)
    
    if not reviews:
        return {"teammate_id": teammate_id, "answers": [], "submitted": False}
    
    # Format as answers
    answers = [
        {"criterion_id": r["criterion_id"], "rating": r["rating"]}
        for r in reviews
    ]
    
    return {
        "teammate_id": teammate_id,
        "answers": answers,
        "submitted": True,
        "submitted_at": reviews[0]["submitted_at"] if reviews else None
    }


class AnswerIn(BaseModel):
    criterion_id: int
    rating: int


class ReviewForTeammateIn(BaseModel):
    teammate_id: int
    answers: list[AnswerIn]


class SubmitPeerReviewBody(BaseModel):
    reviews: list[ReviewForTeammateIn]


def validate_peer_review_submission(
    reviews: list[ReviewForTeammateIn],
    allowed_teammate_ids: set[int],
    criteria: list[dict],
) -> list[dict]:
    """
    Validates peer review submission data.
    
    Subtask 1: Verifies that all mandatory criteria have been rated.
    Subtask 2: Ensures that all ratings are within the allowed scale range.
    
    Args:
        reviews: List of reviews to validate
        allowed_teammate_ids: Set of valid teammate IDs
        criteria: List of all criteria with their properties
        
    Returns:
        List of error dictionaries. Empty list if validation passes.
        Each error dict contains: teammate_id, criterion_id (optional), message
    """
    errors = []
    criteria_by_id = {c["id"]: c for c in criteria}
    required_criteria_ids = {c["id"]: c for c in criteria if c["required"]}

    if not reviews:
        return [{"message": "No reviews submitted"}]

    for r in reviews:
        # Validate teammate
        if r.teammate_id not in allowed_teammate_ids:
            errors.append({"teammate_id": r.teammate_id, "message": "Invalid teammate"})
            continue

        answered_ids = set()

        # Validate each answer
        for a in r.answers:
            crit = criteria_by_id.get(a.criterion_id)
            if not crit:
                errors.append(
                    {"teammate_id": r.teammate_id, "criterion_id": a.criterion_id, "message": "Invalid criterion"}
                )
                continue

            smin = crit["scale"]["min"]
            smax = crit["scale"]["max"]

            # Subtask 2: Ensure rating is within allowed scale range
            if a.rating is None:
                errors.append(
                    {"teammate_id": r.teammate_id, "criterion_id": a.criterion_id, "message": "Rating is required"}
                )
                continue

            if not (smin <= a.rating <= smax):
                errors.append(
                    {
                        "teammate_id": r.teammate_id,
                        "criterion_id": a.criterion_id,
                        "message": f"Rating must be between {smin} and {smax}",
                    }
                )
                continue

            answered_ids.add(a.criterion_id)

        # Subtask 1: Verify that all mandatory criteria have been rated
        missing_required = set(required_criteria_ids.keys()) - answered_ids
        for cid in missing_required:
            criterion_title = required_criteria_ids[cid]["title"]
            errors.append({
                "teammate_id": r.teammate_id,
                "criterion_id": cid,
                "message": f"Rating is required for mandatory criterion: {criterion_title}",
            })

    return errors


@peer_review_router.post("/submit")
def submit_peer_review(body: SubmitPeerReviewBody, user=Depends(require_roles("student"))):
    teammates = db.get_student_teammates_except(user["username"])
    allowed_teammate_ids = {t["id"] for t in teammates}

    criteria = db.get_peer_review_criteria()

    # Validate the submission
    errors = validate_peer_review_submission(body.reviews, allowed_teammate_ids, criteria)

    if errors:
        raise HTTPException(status_code=400, detail=errors)

    # Get reviewer user info
    reviewer = db.get_user_by_username(user["username"])
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    reviewer_id = reviewer["id"]

    # Save all reviews
    for review in body.reviews:
        for answer in review.answers:
            db.save_peer_review_submission(
                reviewer_id=reviewer_id,
                reviewee_id=review.teammate_id,
                criterion_id=answer.criterion_id,
                rating=answer.rating,
            )

    return {"ok": True}


@peer_review_router.get("/report")
def get_personal_report(
    user=Depends(get_current_user), 
    student_id: Optional[int] = Query(None, description="Student ID (required for instructors)")
):
    """
    Get personal peer review report for the authenticated student.
    Returns weighted overall score and scores per evaluation criterion.
    Only available after results are published (unless user is an instructor).
    
    For instructors: can view any student's report by providing student_id parameter.
    For students: can only view their own report, and only after results are published.
    """
    # Check if results are published (instructors can bypass this)
    # Students can only view their reports after instructor publishes them
    results_published = db.are_results_published()
    if user["role"] != "instructor" and not results_published:
        raise HTTPException(
            status_code=403,
            detail="Results have not been published yet. Please wait for the instructor to publish results."
        )
    
    # Determine which student's report to show
    if user["role"] == "instructor":
        # Instructors can view any student's report
        if student_id:
            student = db.get_user_by_id(student_id)
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
            if student["role"] != "student":
                raise HTTPException(status_code=400, detail="Can only view reports for students")
        else:
            # If no student_id provided, return empty response (frontend will show selector)
            return {
                "student_id": None,
                "student_username": None,
                "overall_score": None,
                "criterion_scores": [],
                "total_reviews": 0,
                "unique_reviewers": 0,
                "message": "Please select a student to view their report.",
                "requires_selection": True
            }
    else:
        # Students can only view their own report
        student = db.get_user_by_username(user["username"])
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
    
    student_id = student["id"]
    
    # Get all reviews for this student
    reviews = db.get_peer_reviews_for_student(student_id)
    
    if not reviews:
        return {
            "student_id": student_id,
            "student_username": student["username"],
            "overall_score": None,
            "criterion_scores": [],
            "total_reviews": 0,
            "unique_reviewers": 0,
            "message": "No peer reviews received yet."
        }
    
    # Get all criteria with weights
    criteria = db.get_peer_review_criteria()
    criteria_by_id = {c["id"]: c for c in criteria}
    
    # Calculate scores per criterion
    criterion_scores = {}
    criterion_review_counts = {}
    
    for review in reviews:
        criterion_id = review["criterion_id"]
        rating = review["rating"]
        # Get weight from review data (column alias: criterion_weight)
        # sqlite3.Row doesn't support .get(), so access directly
        # The column is aliased as criterion_weight in the query
        try:
            weight = float(review["criterion_weight"])
        except (KeyError, TypeError):
            weight = 1.0
        
        if criterion_id not in criterion_scores:
            criterion_scores[criterion_id] = {
                "criterion_id": criterion_id,
                "criterion_title": review["criterion_title"],
                "weight": weight,
                "total_rating": 0,
                "review_count": 0,
                "average_score": 0.0,
            }
            criterion_review_counts[criterion_id] = 0
        
        criterion_scores[criterion_id]["total_rating"] += rating
        criterion_review_counts[criterion_id] += 1
    
    # Calculate averages
    criterion_results = []
    total_weighted_score = 0.0
    total_weight = 0.0
    
    for criterion_id, score_data in criterion_scores.items():
        count = criterion_review_counts[criterion_id]
        avg_score = score_data["total_rating"] / count if count > 0 else 0.0
        score_data["review_count"] = count
        score_data["average_score"] = round(avg_score, 2)
        
        # Calculate weighted contribution
        weight = score_data["weight"]
        weighted_contribution = avg_score * weight
        total_weighted_score += weighted_contribution
        total_weight += weight
        
        criterion_results.append(score_data)
    
    # Calculate weighted overall score
    overall_score = round(total_weighted_score / total_weight, 2) if total_weight > 0 else 0.0
    
    # Sort by criterion ID for consistency
    criterion_results.sort(key=lambda x: x["criterion_id"])
    
    return {
        "student_id": student_id,
        "student_username": student["username"],
        "overall_score": overall_score,
        "criterion_scores": criterion_results,
        "total_reviews": len(reviews),
        "unique_reviewers": len(set(r["reviewer_id"] for r in reviews)),
    }


app.include_router(peer_review_router)
app.include_router(auth_router)
