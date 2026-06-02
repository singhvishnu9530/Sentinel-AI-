"""Chat session persistence endpoints — server-side history per user.

user_id is taken from the verified JWT, never from the client, so one user
can never read or modify another user's sessions.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from src.utils.database import (
    delete_session,
    list_sessions,
    upsert_session,
)
from src.utils.jwt_auth import current_user_id

router = APIRouter(prefix="/api/sessions")


class SaveSessionRequest(BaseModel):
    id: str
    title: str
    messages: list
    updatedAt: str


@router.get("")
def get_sessions(user_id: str = Depends(current_user_id)):
    """All sessions for the authenticated user, newest first."""
    return {"sessions": list_sessions(user_id)}


@router.post("")
def save_session(req: SaveSessionRequest, user_id: str = Depends(current_user_id)):
    """Create or update one session for the authenticated user."""
    upsert_session(user_id, req.id, req.title, req.messages, req.updatedAt)
    return {"ok": True}


@router.delete("/{session_id}")
def remove_session(session_id: str, user_id: str = Depends(current_user_id)):
    """Delete a session (only if it belongs to the authenticated user)."""
    delete_session(user_id, session_id)
    return {"ok": True}
