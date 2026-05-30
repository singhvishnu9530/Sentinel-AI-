"""Auth endpoints — signup and login."""

import sqlite3

import bcrypt
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from src.utils.database import get_db, now_iso

router = APIRouter(prefix="/auth")


class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/signup")
def signup(req: SignupRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    hashed = bcrypt.hashpw(req.password.encode(), bcrypt.gensalt()).decode()
    try:
        with get_db() as db:
            cursor = db.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (req.name, req.email, hashed, now_iso()),
            )
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Email already registered")

    return {"user": {"id": user_id, "name": req.name, "email": req.email}}


@router.post("/login")
def login(req: LoginRequest):
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (req.email,)).fetchone()

    if not row or not bcrypt.checkpw(req.password.encode(), row["password_hash"].encode()):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    return {"user": {"id": row["id"], "name": row["name"], "email": row["email"]}}
