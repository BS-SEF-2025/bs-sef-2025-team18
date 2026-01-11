from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Callable

from . import db
from .security import hash_password, verify_password
from .token_service import create_access_token, decode_access_token
from fastapi import APIRouter, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from . import security



app = FastAPI(title="PeerEval Pro - Role Based Access")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
auth_router = APIRouter(prefix="/auth", tags=["auth"])

class SignupBody(BaseModel):
    username: str
    password: str
    role: str  # student / instructor

@auth_router.post("/signup")
def signup(body: SignupBody):
    if body.role not in ("student", "instructor"):
        raise HTTPException(status_code=422, detail="Invalid role")

    if db.get_user_by_username(body.username):
        raise HTTPException(status_code=409, detail="Username already exists")

    password_hash = security.hash_password(body.password)
    db.create_user(body.username, password_hash, body.role)

    return {"ok": True}

from fastapi import HTTPException
from pydantic import BaseModel
import security
import db

class SignupBody(BaseModel):
    username: str
    password: str
    role: str  # 'student' or 'instructor'

@app.post("/auth/signup")
def signup(body: SignupBody):
    existing = db.get_user_by_username(body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    password_hash = security.hash_password(body.password)
    db.create_user(body.username, password_hash, body.role)
    return {"ok": True}


db.init_db()


class RegisterBody(BaseModel):
    username: str
    password: str
    role: str  # "student" or "instructor"


class LoginBody(BaseModel):
    username: str
    password: str


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


@app.post("/auth/register")
def register(body: RegisterBody):
    if body.role not in ("student", "instructor"):
        raise HTTPException(status_code=400, detail="Role must be student or instructor")

    existing = db.get_user_by_username(body.username)
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")

    db.create_user(body.username, hash_password(body.password), body.role)
    return {"ok": True}


@app.post("/auth/login")
def login(body: LoginBody):
    user = db.get_user_by_username(body.username)

    # ✅ Invalid credentials -> error message
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials. Please check your username and password."
        )

    token = create_access_token(username=user["username"], role=user["role"])
    return {"access_token": token, "token_type": "bearer", "role": user["role"]}


@app.get("/me")
def me(user=Depends(get_current_user)):
    return user


# Example protected pages/features:
@app.get("/student/results")
def student_results(user=Depends(require_roles("student"))):
    return {"page": "Student Peer Review Results", "user": user}


@app.get("/instructor/publish")
def instructor_publish(user=Depends(require_roles("instructor"))):
    return {"page": "Publish Peer Review Results", "user": user}
app.include_router(auth_router)

