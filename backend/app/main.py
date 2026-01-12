
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import secrets

from .storage import USERS

app = FastAPI(title="Peer Review System - Group 18")

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/auth/login")
def login(payload: LoginRequest):
    user = USERS.get(payload.username)

    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = secrets.token_hex(16)
    return {"token": token, "role": user.role}

