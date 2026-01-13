import re
from typing import Optional, Callable

from fastapi import FastAPI, Depends, HTTPException, Header, APIRouter
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
def instructor_publish(user=Depends(require_roles("instructor"))):
    return {"page": "Publish Peer Review Results", "user": user}


# -------------------------
# Peer Review Router
# -------------------------
peer_review_router = APIRouter(prefix="/peer-reviews", tags=["peer-reviews"])


@peer_review_router.get("/form")
def get_peer_review_form(user=Depends(require_roles("student"))):
    teammates = db.get_student_teammates_except(user["username"])
    criteria = db.get_peer_review_criteria()
    return {"teammates": teammates, "criteria": criteria}


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

    return {"ok": True}


app.include_router(peer_review_router)
app.include_router(auth_router)
