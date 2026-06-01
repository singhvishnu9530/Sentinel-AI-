"""SQLite database connection, schema, and usage-limit helpers."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "data" / "users.db"

# Free-tier limits
FREE_TOKEN_LIMIT = 10_000          # tokens before a free user is blocked
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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Usage / limit helpers ─────────────────────────────────────────────────────

def get_usage(user_id: int) -> dict | None:
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


def is_blocked(user_id: int) -> dict | None:
    """If the user may NOT use the service, return their usage info; else None."""
    usage = get_usage(user_id)
    if usage and usage["locked"]:
        return usage
    return None


def add_tokens(user_id: int, tokens: int) -> dict | None:
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


def upgrade_to_pro(user_id: int) -> dict | None:
    """Mock upgrade — flip to Pro, clear the lock, lift the limit."""
    with get_db() as db:
        db.execute(
            "UPDATE users SET plan = 'pro', locked_until = NULL WHERE id = ?", (user_id,)
        )
    return get_usage(user_id)
