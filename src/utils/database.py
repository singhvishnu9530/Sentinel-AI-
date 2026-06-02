"""SQLite database connection, schema, and usage-limit helpers."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "users.db"

# Free-tier limits
FREE_TOKEN_LIMIT = 1_000_000       # tokens before a free user is blocked
LOCK_DAYS = 7                      # how long the lock lasts if they don't upgrade


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                tokens_used INTEGER NOT NULL DEFAULT 0,
                locked_until TEXT
            )
        """)
        # Migrate older DBs that predate the usage columns.
        cols = {r["name"] for r in db.execute("PRAGMA table_info(users)").fetchall()}
        for col, ddl in [
            ("plan", "ALTER TABLE users ADD COLUMN plan TEXT NOT NULL DEFAULT 'free'"),
            ("tokens_used", "ALTER TABLE users ADD COLUMN tokens_used INTEGER NOT NULL DEFAULT 0"),
            ("locked_until", "ALTER TABLE users ADD COLUMN locked_until TEXT"),
        ]:
            if col not in cols:
                db.execute(ddl)

        # Chat sessions — one row per analysis conversation, scoped to a user.
        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                messages TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Usage / limit helpers ─────────────────────────────────────────────────────

def get_usage(user_id: str) -> dict | None:
    """Return the user's plan, token usage, and lock status."""
    with get_db() as db:
        row = db.execute(
            "SELECT id, name, email, plan, tokens_used, locked_until FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return None

    locked = False
    locked_until = row["locked_until"]
    if row["plan"] == "free" and locked_until:
        try:
            locked = datetime.fromisoformat(locked_until) > datetime.now(timezone.utc)
        except ValueError:
            locked = False

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "plan": row["plan"],
        "tokens_used": row["tokens_used"],
        "token_limit": None if row["plan"] == "pro" else FREE_TOKEN_LIMIT,
        "locked": locked,
        "locked_until": locked_until if locked else None,
    }


def is_blocked(user_id: str) -> dict | None:
    """If the user may NOT use the service, return their usage info; else None."""
    usage = get_usage(user_id)
    if usage and usage["locked"]:
        return usage
    return None


def add_tokens(user_id: str, tokens: int) -> dict | None:
    """Add token usage. If a free user crosses the limit, lock them for LOCK_DAYS."""
    with get_db() as db:
        row = db.execute(
            "SELECT plan, tokens_used FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if not row:
            return None

        new_total = row["tokens_used"] + max(0, tokens)
        locked_until = None
        if row["plan"] == "free" and new_total >= FREE_TOKEN_LIMIT:
            locked_until = (datetime.now(timezone.utc) + timedelta(days=LOCK_DAYS)).isoformat()
            db.execute(
                "UPDATE users SET tokens_used = ?, locked_until = ? WHERE id = ?",
                (new_total, locked_until, user_id),
            )
        else:
            db.execute(
                "UPDATE users SET tokens_used = ? WHERE id = ?", (new_total, user_id)
            )
    return get_usage(user_id)


def upgrade_to_pro(user_id: str) -> dict | None:
    """Mock upgrade — flip to Pro, clear the lock, lift the limit."""
    with get_db() as db:
        db.execute(
            "UPDATE users SET plan = 'pro', locked_until = NULL WHERE id = ?", (user_id,)
        )
    return get_usage(user_id)


# ── Chat session persistence ──────────────────────────────────────────────────

import json as _json


def list_sessions(user_id: str) -> list[dict]:
    """All sessions for a user, newest first. `messages` is parsed back to a list."""
    with get_db() as db:
        rows = db.execute(
            "SELECT id, title, messages, updated_at FROM sessions "
            "WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
    sessions = []
    for r in rows:
        try:
            messages = _json.loads(r["messages"])
        except Exception:
            messages = []
        sessions.append({
            "id": r["id"],
            "title": r["title"],
            "messages": messages,
            "updatedAt": r["updated_at"],
        })
    return sessions


def upsert_session(user_id: str, session_id: str, title: str, messages: list, updated_at: str) -> None:
    """Insert or update one session (scoped to the user)."""
    with get_db() as db:
        db.execute(
            """
            INSERT INTO sessions (id, user_id, title, messages, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                messages = excluded.messages,
                updated_at = excluded.updated_at
            WHERE sessions.user_id = ?
            """,
            (session_id, user_id, title, _json.dumps(messages), updated_at, user_id),
        )


def delete_session(user_id: str, session_id: str) -> None:
    """Delete a session, but only if it belongs to this user."""
    with get_db() as db:
        db.execute(
            "DELETE FROM sessions WHERE id = ? AND user_id = ?", (session_id, user_id)
        )
