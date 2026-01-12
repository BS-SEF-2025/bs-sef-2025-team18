import re
from typing import Optional, Callable

from fastapi import FastAPI, Depends, HTTPException, Header, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator, model_validator

from . import db
from .security import hash_password, verify_password
from .token_service import create_access_token, decode_access_token
from .seed import seed_users

app = FastAPI(title="PeerEval Pro - Role Based Access")

# ✅ CORS (for Live Server on 5500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://127.0.0.1:3000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Init DB + seed only after app starts
@app.on_event("startup")
def _startup():
    db.init_db()
    seed_users()


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
        # simple email check
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
    # duplicate username
    if db.get_user_by_username(body.username):
        raise HTTPException(status_code=409, detail="Username already exists.")

    # duplicate email
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
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


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


app.include_router(auth_router)
