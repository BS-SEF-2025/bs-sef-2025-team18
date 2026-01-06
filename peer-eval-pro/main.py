from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional, Callable

import db
from security import hash_password, verify_password
from token_service import create_access_token, decode_access_token

app = FastAPI(title="PeerEval Pro - Role Based Access")

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
