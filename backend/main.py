import re
import sqlite3
import io
from datetime import datetime
from typing import Optional, Callable

from fastapi import FastAPI, Depends, HTTPException, Header, APIRouter, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator
from fastapi.responses import StreamingResponse

import db
from security import hash_password, verify_password
from token_service import create_access_token, decode_access_token
from seed import seed_users, seed_peer_review_criteria
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from pathlib import Path

# PDF generation imports
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

app = FastAPI(title="PeerEval Pro - Role Based Access")
BASE_DIR = Path(__file__).resolve().parent          # .../backend
FRONTEND_DIR = BASE_DIR.parent / "frontend"

app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/", include_in_schema=False)
def landing():
    return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/login.html", include_in_schema=False)
def login_page():
    return FileResponse(FRONTEND_DIR / "login.html")

@app.get("/signup.html", include_in_schema=False)
def signup_page():
    return FileResponse(FRONTEND_DIR / "signup.html")

@app.get("/dashboard.html", include_in_schema=False)
def dashboard_page():
    return FileResponse(FRONTEND_DIR / "dashboard.html")

@app.get("/styles.css", include_in_schema=False)
def styles_css():
    return FileResponse(FRONTEND_DIR / "styles.css")

@app.get("/protected.js", include_in_schema=False)
def protected_js():
    return FileResponse(FRONTEND_DIR / "protected.js")

@app.get("/signup.js", include_in_schema=False)
def signup_js():
    return FileResponse(FRONTEND_DIR / "signup.js")

@app.get("/index.html", include_in_schema=False)
def index_page():
    return FileResponse(FRONTEND_DIR / "index.html")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    
    # Get current review phase
    current_phase = db.get_review_state()
    
    # Get all criteria from peer_review_criteria table (includes default seeded + instructor-added criteria)
    all_peer_review_criteria = db.get_peer_review_criteria()
    
    # Get instructor-defined criteria for descriptions
    instructor_criteria = db.get_all_criteria()
    
    # Create a mapping of instructor criteria by name for descriptions
    instructor_by_name = {c["name"].strip().lower(): c for c in instructor_criteria}
    
    # Default criteria names (these are always shown)
    default_criteria_names = {"contribution", "communication", "quality of work", "reliability"}
    
    # Default criteria descriptions (used if not in instructor_criteria)
    default_criteria_descriptions = {
        "contribution": "Evaluate the team member's level of contribution to team projects and activities.",
        "communication": "Assess how effectively the team member communicates ideas, feedback, and information with the team.",
        "quality of work": "Rate the quality, accuracy, and thoroughness of the work produced by this team member.",
        "reliability": "Evaluate how dependable and consistent the team member is in meeting deadlines and commitments.",
    }
    
    # Filter criteria based on phase
    # Round1: Only 4 default criteria
    # Round2: 4 default + instructor-added criteria
    filtered_criteria = []
    for prc in all_peer_review_criteria:
        title = prc["title"].strip()
        title_lower = title.lower()
        
        # In round1, only show default criteria
        if current_phase == "round1":
            if title_lower not in default_criteria_names:
                continue
        # In round2, show default + instructor-added (those in criteria table)
        elif current_phase == "round2":
            if title_lower not in default_criteria_names and title_lower not in instructor_by_name:
                continue
        
        # Get description from instructor_criteria if available, otherwise use default
        description = ""
        if title_lower in instructor_by_name:
            description = instructor_by_name[title_lower]["description"]
        elif title_lower in default_criteria_descriptions:
            description = default_criteria_descriptions[title_lower]
        
        filtered_criteria.append({
            "id": prc["id"],
            "title": title,
            "description": description,
            "required": prc["required"],
            "scale": prc["scale"],
            "weight": prc["weight"],
        })
    
    return {"teammates": teammates, "criteria": filtered_criteria, "phase": current_phase}


@peer_review_router.get("/submitted/{teammate_id}")
def get_submitted_review(teammate_id: int, user=Depends(require_roles("student"))):
    """Get previously submitted review for a specific teammate (for editing).
    Only returns reviews for the current phase. Round1 submissions are locked once round2 starts.
    """
    # Verify the teammate is valid
    teammates = db.get_student_teammates_except(user["username"])
    allowed_teammate_ids = {t["id"] for t in teammates}

    if teammate_id not in allowed_teammate_ids:
        raise HTTPException(status_code=404, detail="Teammate not found")

    # Get current review phase
    current_phase = db.get_review_state()

    # Get reviewer info
    reviewer = db.get_user_by_username(user["username"])
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    reviewer_id = reviewer["id"]

    # Get submitted reviews for the current phase only
    reviews = db.get_reviews_submitted_by_reviewer_for_reviewee(reviewer_id, teammate_id, round=current_phase)

    if not reviews:
        return {"teammate_id": teammate_id, "answers": [], "submitted": False, "phase": current_phase}

    # Format as answers
    answers = [
        {"criterion_id": r["criterion_id"], "rating": r["rating"]}
        for r in reviews
    ]

    return {
        "teammate_id": teammate_id,
        "answers": answers,
        "submitted": True,
        "submitted_at": reviews[0]["submitted_at"] if reviews else None,
        "phase": current_phase
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
    # Check if submissions are open (deadline not passed)
    if not db.is_submission_open():
        raise HTTPException(status_code=403, detail="Submissions are closed.")
    
    teammates = db.get_student_teammates_except(user["username"])
    allowed_teammate_ids = {t["id"] for t in teammates}

    # Get current review phase
    current_phase = db.get_review_state()
    
    # Check if phase is valid for submissions
    if current_phase == "published":
        raise HTTPException(status_code=403, detail="Reviews are published and cannot be submitted or edited")

    # Get criteria from peer_review_criteria for validation and submission
    # Filter by phase (form endpoint already does this, but we need full list for validation)
    all_criteria = db.get_peer_review_criteria()
    
    # Filter criteria based on phase (same logic as form endpoint)
    default_criteria_names = {"contribution", "communication", "quality of work", "reliability"}
    instructor_criteria = db.get_all_criteria()
    instructor_by_name = {c["name"].strip().lower(): c for c in instructor_criteria}
    
    criteria = []
    for prc in all_criteria:
        title_lower = prc["title"].strip().lower()
        if current_phase == "round1":
            if title_lower not in default_criteria_names:
                continue
        elif current_phase == "round2":
            if title_lower not in default_criteria_names and title_lower not in instructor_by_name:
                continue
        criteria.append(prc)

    # Validate the submission
    errors = validate_peer_review_submission(body.reviews, allowed_teammate_ids, criteria)

    if errors:
        raise HTTPException(status_code=400, detail=errors)

    # Get reviewer user info
    reviewer = db.get_user_by_username(user["username"])
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")

    reviewer_id = reviewer["id"]

    # Save all reviews with the current round
    for review in body.reviews:
        for answer in review.answers:
            db.save_peer_review_submission(
                reviewer_id=reviewer_id,
                reviewee_id=review.teammate_id,
                criterion_id=answer.criterion_id,
                rating=answer.rating,
                round=current_phase,
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


@peer_review_router.get("/report/pdf")
def download_report_pdf(user=Depends(require_roles("student"))):
    """
    Download personal peer review report as a PDF.
    Only available for students after results are published.
    Students can only download their own report.
    """
    # Check if results are published
    if not db.are_results_published():
        raise HTTPException(
            status_code=403,
            detail="Results have not been published yet. Please wait for the instructor to publish results."
        )
    
    # Get student info
    student = db.get_user_by_username(user["username"])
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    student_id = student["id"]
    
    # Get all reviews for this student
    reviews = db.get_peer_reviews_for_student(student_id)
    
    # Get criteria
    criteria = db.get_peer_review_criteria()
    
    # Calculate scores per criterion
    criterion_scores = {}
    for review in reviews:
        cid = review["criterion_id"]
        if cid not in criterion_scores:
            criterion_scores[cid] = {
                "title": review["criterion_title"],
                "weight": float(review.get("criterion_weight", 1.0)),
                "ratings": [],
            }
        criterion_scores[cid]["ratings"].append(review["rating"])
    
    # Calculate averages
    criterion_results = []
    total_weighted = 0.0
    total_weight = 0.0
    for cid, data in criterion_scores.items():
        avg = sum(data["ratings"]) / len(data["ratings"]) if data["ratings"] else 0
        criterion_results.append({
            "title": data["title"],
            "weight": data["weight"],
            "average": round(avg, 2),
            "count": len(data["ratings"]),
        })
        total_weighted += avg * data["weight"]
        total_weight += data["weight"]
    
    overall_score = round(total_weighted / total_weight, 2) if total_weight > 0 else 0
    
    # Generate PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.75*inch, bottomMargin=0.75*inch)
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=22, spaceAfter=6, textColor=colors.HexColor('#1e293b'))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=12, textColor=colors.HexColor('#64748b'), spaceAfter=20)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=14, spaceBefore=20, spaceAfter=10, textColor=colors.HexColor('#334155'))
    
    elements = []
    
    # Title
    elements.append(Paragraph("Peer Review Report", title_style))
    elements.append(Paragraph(f"Generated for: <b>{student['username']}</b>", subtitle_style))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%B %d, %Y at %H:%M')}", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#e2e8f0'), spaceAfter=20))
    
    # Overall Score
    elements.append(Paragraph("Overall Performance", heading_style))
    score_color = colors.HexColor('#10b981') if overall_score >= 4 else (colors.HexColor('#f59e0b') if overall_score >= 3 else colors.HexColor('#ef4444'))
    elements.append(Paragraph(f"<font size='28' color='{score_color.hexval()}'><b>{overall_score}</b></font> <font size='12' color='#64748b'>/ 5.0</font>", styles['Normal']))
    elements.append(Paragraph(f"Based on {len(reviews)} ratings from {len(set(r['reviewer_id'] for r in reviews))} reviewers", subtitle_style))
    elements.append(Spacer(1, 20))
    
    # Criterion Scores Table
    if criterion_results:
        elements.append(Paragraph("Scores by Criterion", heading_style))
        
        table_data = [["Criterion", "Weight", "Avg Score", "Reviews"]]
        for cr in criterion_results:
            table_data.append([cr["title"], f"{cr['weight']:.1f}", f"{cr['average']:.2f}", str(cr["count"])])
        
        table = Table(table_data, colWidths=[3*inch, 1*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#334155')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#1e293b')),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ]))
        elements.append(table)
    else:
        elements.append(Paragraph("No reviews received yet.", styles['Normal']))
    
    # Footer
    elements.append(Spacer(1, 40))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#e2e8f0'), spaceAfter=10))
    elements.append(Paragraph(f"<font size='9' color='#94a3b8'>PeerEval Pro - Confidential Report</font>", styles['Normal']))
    
    doc.build(elements)
    buffer.seek(0)
    
    filename = f"peer_review_report_{student['username']}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@peer_review_router.get("/results")
def get_peer_review_results(
    user=Depends(get_current_user), 
    student_id: Optional[int] = Query(None, description="Student ID (optional for students viewing other students, required for instructors)")
):
    """
    Get individual peer review results for a student.
    Returns a list of received peer reviews, each showing reviewer name, ratings per criterion, and total score.
    Only available after results are published (unless user is an instructor).
    
    For instructors: can view any student's results by providing student_id parameter.
    For students: can view their own results, or other students' results if student_id is provided (only after results are published).
    """
    # Check if results are published (instructors can bypass this)
    # Students can only view results after instructor publishes them
    results_published = db.are_results_published()
    if user["role"] != "instructor" and not results_published:
        raise HTTPException(
            status_code=403,
            detail="Results have not been published yet. Please wait for the instructor to publish results."
        )
    
    # Determine which student's results to show
    if user["role"] == "instructor":
        # Instructors can view any student's results
        if student_id:
            student = db.get_user_by_id(student_id)
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
            if student["role"] != "student":
                raise HTTPException(status_code=400, detail="Can only view results for students")
        else:
            # If no student_id provided, return empty response
            return {
                "student_id": None,
                "student_username": None,
                "reviews": [],
                "message": "Please select a student to view their peer review results.",
                "requires_selection": True
            }
    else:
        # Students can view their own results or other students' results (if student_id provided)
        if student_id:
            # Viewing another student's results
            student = db.get_user_by_id(student_id)
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
            if student["role"] != "student":
                raise HTTPException(status_code=400, detail="Can only view results for students")
        else:
            # Viewing own results
            student = db.get_user_by_username(user["username"])
            if not student:
                raise HTTPException(status_code=404, detail="Student not found")
    
    student_id = student["id"]
    
    # Get individual peer reviews
    reviews = db.get_individual_peer_reviews_for_student(student_id)
    
    if not reviews:
        return {
            "student_id": student_id,
            "student_username": student["username"],
            "reviews": [],
            "message": "No peer reviews received yet."
        }
    
    return {
        "student_id": student_id,
        "student_username": student["username"],
        "reviews": reviews,
        "total_reviews": len(reviews)
    }


@peer_review_router.get("/all-results")
def get_all_peer_review_results(user=Depends(require_roles("student"))):
    """
    Get peer review results for all students.
    Only available to students after results are published.
    Returns a list of all students with their individual peer review results.
    """
    # Check if results are published
    results_published = db.are_results_published()
    if not results_published:
        raise HTTPException(
            status_code=403,
            detail="Results have not been published yet. Please wait for the instructor to publish results."
        )
    
    # Get all students
    students = db.get_all_students()
    
    if not students:
        return {
            "students": [],
            "message": "No students found."
        }
    
    # Get results for each student
    all_results = []
    for student in students:
        reviews = db.get_individual_peer_reviews_for_student(student["id"])
        
        # Calculate overall score from reviews if available
        overall_score = None
        if reviews:
            # Calculate weighted average from all reviews
            total_weighted_score = 0.0
            total_weight = 0.0
            for review in reviews:
                if review.get("total_score") is not None:
                    # Use the total_score from each review (which is already weighted)
                    # We'll average the total scores from all reviewers
                    total_weighted_score += review["total_score"]
                    total_weight += 1.0
            
            if total_weight > 0:
                overall_score = round(total_weighted_score / total_weight, 2)
        
        all_results.append({
            "student_id": student["id"],
            "student_username": student["username"],
            "student_email": student.get("email", ""),
            "reviews": reviews,
            "total_reviews": len(reviews),
            "overall_score": overall_score
        })
    
    # Sort by overall_score descending (highest first), then by username
    all_results.sort(key=lambda x: (x["overall_score"] if x["overall_score"] is not None else -1, x["student_username"]), reverse=True)
    
    return {
        "students": all_results,
        "total_students": len(all_results)
    }


@peer_review_router.get("/my-submitted-reviews")
def get_my_submitted_reviews(user=Depends(require_roles("student"))):
    """
    Get all reviews submitted by the authenticated student.
    Returns a list of reviews grouped by reviewee, showing who the student reviewed.
    """
    # Get reviewer info
    reviewer = db.get_user_by_username(user["username"])
    if not reviewer:
        raise HTTPException(status_code=404, detail="Reviewer not found")
    
    reviewer_id = reviewer["id"]
    
    # Get all reviews submitted by this reviewer
    reviews = db.get_reviews_submitted_by_reviewer(reviewer_id)
    
    if not reviews:
        return {
            "reviews": [],
            "total_reviews": 0,
            "message": "You haven't submitted any reviews yet."
        }
    
    return {
        "reviews": reviews,
        "total_reviews": len(reviews)
    }


# -------------------------
# Criteria Management Router
# -------------------------
criteria_router = APIRouter(prefix="/criteria", tags=["criteria"])


class CriterionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)

    @field_validator("name", "description")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty")
        return v


class CriterionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)

    @field_validator("name", "description")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be empty")
        return v


@criteria_router.post("", status_code=201)
def create_criterion(body: CriterionCreate, user=Depends(require_roles("instructor"))):
    """Create a new evaluation criterion (instructor-only, allowed in round2)."""
    # Check review state - criteria can only be added in round2
    current_state = db.get_review_state()
    if current_state != "round2":
        raise HTTPException(
            status_code=403,
            detail=f"Cannot create criteria when review state is '{current_state}'. Criteria can only be created in round2."
        )
    
    try:
        # Create criterion in criteria table
        criterion_id = db.create_criterion(body.name, body.description)
        
        # Also sync to peer_review_criteria table for submissions (default: required=True, scale 1-5, weight=1.0)
        db.insert_peer_review_criteria(
            title=body.name,
            required=1,  # All criteria are required by default
            scale_min=1,
            scale_max=5,
            weight=1.0
        )
        
        criterion = db.get_criterion_by_id(criterion_id)
        return criterion
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Criterion with this name already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create criterion: {str(e)}")


@criteria_router.get("")
def get_criteria(user=Depends(require_roles("instructor"))):
    """Get all evaluation criteria (instructor-only)."""
    criteria = db.get_all_criteria()
    return {"criteria": criteria}


@criteria_router.put("/{criterion_id}")
def update_criterion(
    criterion_id: int,
    body: CriterionUpdate,
    user=Depends(require_roles("instructor")),
):
    """Update an evaluation criterion (instructor-only, allowed in round2)."""
    # Check review state - criteria can only be edited in round2
    current_state = db.get_review_state()
    if current_state != "round2":
        raise HTTPException(
            status_code=403,
            detail=f"Cannot edit criteria when review state is '{current_state}'. Criteria can only be edited in round2."
        )
    
    # Check if criterion exists
    existing = db.get_criterion_by_id(criterion_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Criterion not found")
    
    # Update the criterion
    success = db.update_criterion(criterion_id, body.name, body.description)
    if not success:
        raise HTTPException(status_code=404, detail="Criterion not found")
    
    updated = db.get_criterion_by_id(criterion_id)
    return updated


@criteria_router.delete("/{criterion_id}")
def delete_criterion(criterion_id: int, user=Depends(require_roles("instructor"))):
    """Delete an evaluation criterion (instructor-only, allowed in round1 and round2, not published)."""
    # Check review state - criteria cannot be deleted when published
    current_state = db.get_review_state()
    if current_state == "published":
        raise HTTPException(
            status_code=403,
            detail=f"Cannot delete criteria when review state is 'published'. Reviews are read-only after publishing."
        )
    
    # Check if criterion exists
    existing = db.get_criterion_by_id(criterion_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Criterion not found")
    
    # Delete the criterion
    success = db.delete_criterion(criterion_id)
    if not success:
        raise HTTPException(status_code=404, detail="Criterion not found")
    
    return {"ok": True, "message": "Criterion deleted successfully"}


# -------------------------
# Review State Router
# -------------------------
review_state_router = APIRouter(prefix="/review", tags=["review-state"])


class ReviewStateUpdate(BaseModel):
    status: str = Field(..., description="Review state: 'round1', 'round2', or 'published'")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in ("round1", "round2", "published"):
            raise ValueError("Status must be 'round1', 'round2', or 'published'")
        return v


@review_state_router.get("/state")
def get_review_state_endpoint(user=Depends(require_roles("instructor"))):
    """Get the current review state (instructor-only)."""
    status = db.get_review_state()
    return {"status": status}


@review_state_router.post("/state")
def set_review_state_endpoint(
    body: ReviewStateUpdate, user=Depends(require_roles("instructor"))
):
    """Set the review state (instructor-only)."""
    try:
        db.set_review_state(body.status)
        return {"ok": True, "status": body.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set review state: {str(e)}")


@review_state_router.put("/state")
def update_review_state_endpoint(
    body: ReviewStateUpdate, user=Depends(require_roles("instructor"))
):
    """Update the review state (instructor-only). Alias for POST /review/state."""
    return set_review_state_endpoint(body, user)


@review_state_router.post("/start-round2")
def start_round2(user=Depends(require_roles("instructor"))):
    """Start Round 2 of evaluations (instructor-only). Transitions from round1 (or draft) to round2."""
    current_state = db.get_review_state()
    
    # Allow starting Round 2 from "round1" or "draft" (for backward compatibility)
    if current_state not in ("round1", "draft"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start Round 2. Current state is '{current_state}'. Round 2 can only be started from Round 1."
        )
    
    try:
        db.set_review_state("round2")
        return {"ok": True, "status": "round2", "message": "Round 2 started successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start Round 2: {str(e)}")


app.include_router(peer_review_router)
app.include_router(auth_router)
app.include_router(criteria_router)
app.include_router(review_state_router)


# -------------------------
# Submission Deadline Router
# -------------------------
deadline_router = APIRouter(prefix="/deadline", tags=["deadline"])


class DeadlineUpdate(BaseModel):
    deadline: Optional[str] = Field(None, description="ISO datetime string or null to clear")


@deadline_router.get("")
def get_deadline(user=Depends(get_current_user)):
    """Get the current submission deadline and status."""
    deadline = db.get_submission_deadline()
    is_open = db.is_submission_open()
    return {"deadline": deadline, "is_open": is_open}


@deadline_router.post("")
def set_deadline(body: DeadlineUpdate, user=Depends(require_roles("instructor"))):
    """Set or clear the submission deadline (instructor-only)."""
    db.set_submission_deadline(body.deadline)
    is_open = db.is_submission_open()
    return {"ok": True, "deadline": body.deadline, "is_open": is_open}


@deadline_router.delete("")
def clear_deadline(user=Depends(require_roles("instructor"))):
    """Clear the submission deadline (instructor-only)."""
    db.set_submission_deadline(None)
    return {"ok": True, "deadline": None, "is_open": True}


app.include_router(deadline_router)
