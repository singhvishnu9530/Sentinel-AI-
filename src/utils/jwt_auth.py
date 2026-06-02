"""JWT helpers — sign a token at login, verify it on every protected request.

The token is signed with SECRET_KEY (server-only). The browser can read the
token but cannot forge or alter it without the key, so the user_id inside it
is trustworthy. This is what makes the client-sent identity unforgeable.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header, HTTPException

SECRET_KEY = os.getenv("JWT_SECRET", "sentinel-dev-secret-key-change-me-in-production-0123456789")
ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 24 * 7  # a week


def create_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> str:
    """Return the user_id from a valid token, or raise 401."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired — please sign in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


def current_user_id(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency — extracts & verifies the user_id from the
    `Authorization: Bearer <token>` header. Use on any protected endpoint."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.split(" ", 1)[1].strip()
    return decode_token(token)
