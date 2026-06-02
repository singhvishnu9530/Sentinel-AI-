"""Auth + usage/upgrade endpoints."""

import sqlite3
import uuid

import bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from src.utils.database import get_db, now_iso, get_usage, upgrade_to_pro
from src.utils.jwt_auth import create_token, current_user_id
from fastapi import Depends

router = APIRouter(prefix="/auth")


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _validate_password(pw: str) -> str | None:
    """Return an error message if the password is too weak, else None."""
    import re
    if len(pw) < 8:
        return "Password must be at least 8 characters"
    if not re.search(r"[A-Z]", pw):
        return "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", pw):
        return "Password must contain a lowercase letter"
    if not re.search(r"[0-9]", pw):
        return "Password must contain a number"
    if not re.search(r"[^A-Za-z0-9]", pw):
        return "Password must contain a special character"
    return None


@router.post("/signup")
def signup(req: SignupRequest):
    pw_error = _validate_password(req.password)
    if pw_error:
        raise HTTPException(status_code=400, detail=pw_error)

    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    user_id = uuid.uuid4().hex  # unguessable id instead of a sequential integer
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
                (user_id, req.name, req.email, hashed, now_iso()),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")

    return {"user": get_usage(user_id)}


@router.post("/login")
def login(req: LoginRequest):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (req.email,)).fetchone()

    if not row or not bcrypt.checkpw(req.password.encode(), row["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_token(row["id"])
    return {"user": get_usage(row["id"]), "token": token}


@router.get("/usage")
def usage(user_id: str = Depends(current_user_id)):
    info = get_usage(user_id)
    if not info:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": info}


@router.post("/upgrade")
def upgrade(user_id: str = Depends(current_user_id)):
    info = upgrade_to_pro(user_id)
    if not info:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user": info}
