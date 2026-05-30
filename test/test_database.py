import os
import sqlite3
from pathlib import Path
import pytest

# Set up test database path before importing any db functions
import src.utils.database
TEST_DB_PATH = Path(__file__).parent / "test_temp_users.db"
src.utils.database.DB_PATH = TEST_DB_PATH

from src.utils.database import get_db, init_db, now_iso

@pytest.fixture(autouse=True)
def clean_test_db():
    """Ensure we start with a clean test database file for each test, and remove it afterward."""
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except OSError:
            pass

    yield

    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except OSError:
            pass


def test_init_db_creates_table():
    """Verify init_db initializes the database and creates the users table."""
    assert not TEST_DB_PATH.exists()
    
    # Initialize the database
    init_db()
    
    assert TEST_DB_PATH.exists()
    
    # Verify the table schema
    with sqlite3.connect(TEST_DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == "users"
        
        # Verify columns
        cursor.execute("PRAGMA table_info(users);")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        assert "id" in columns
        assert "name" in columns
        assert "email" in columns
        assert "password_hash" in columns
        assert "created_at" in columns


def test_get_db_context_manager():
    """Verify get_db context manager yields a connection and commits transactions."""
    init_db()
    
    # Write a test row
    with get_db() as db:
        db.execute(
            "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            ("Db Test User", "db_test@example.com", "hash123", now_iso())
        )
    
    # Read the test row in a new connection to confirm it committed
    with sqlite3.connect(TEST_DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", ("db_test@example.com",))
        row = cursor.fetchone()
        assert row is not None
        assert row["name"] == "Db Test User"
        assert row["password_hash"] == "hash123"


def test_now_iso():
    """Verify now_iso returns a non-empty string in valid ISO format."""
    timestamp = now_iso()
    assert isinstance(timestamp, str)
    assert len(timestamp) > 0
    # Must end with Z or offset, e.g. +00:00
    assert "T" in timestamp
