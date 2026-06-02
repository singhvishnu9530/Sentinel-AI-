import os
import sqlite3
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

# Override the database path BEFORE importing the app to avoid writing to production DB
import src.utils.database
TEST_DB_PATH = src.utils.database.DB_PATH.parent / "test_users.db"
src.utils.database.DB_PATH = TEST_DB_PATH

from auth_server import app
from src.utils.database import init_db


@pytest.fixture(autouse=True)
def setup_test_db():
    """Fixture to ensure each test runs on a clean, isolated database."""
    # Clean up previous test database if it exists
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except OSError:
            pass

    # Initialize the database tables
    init_db()

    yield

    # Clean up database after the test
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
        except OSError:
            pass


@pytest.fixture
def client():
    """Pytest fixture to provide the FastAPI test client."""
    return TestClient(app)


# ==========================================
# AUTH ENDPOINT TESTS
# ==========================================

def test_signup_success(client):
    """Test successful user registration."""
    response = client.post(
        "/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "Password123!"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "user" in data
    assert data["user"]["name"] == "Test User"
    assert data["user"]["email"] == "test@example.com"
    assert "id" in data["user"]


def test_signup_password_too_short(client):
    """Test signup validation fails when password is too short."""
    response = client.post(
        "/auth/signup",
        json={
            "name": "Test User",
            "email": "test@example.com",
            "password": "123"
        }
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Password must be at least 8 characters"


def test_signup_duplicate_email(client):
    """Test signup fails when email is already registered."""
    signup_data = {
        "name": "Test User",
        "email": "duplicate@example.com",
        "password": "Password123!"
    }
    # First signup
    res1 = client.post("/auth/signup", json=signup_data)
    assert res1.status_code == status.HTTP_200_OK

    # Duplicate signup
    res2 = client.post("/auth/signup", json=signup_data)
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert res2.json()["detail"] == "Email already registered"


def test_login_success(client):
    """Test successful login with valid credentials."""
    # First, register the user
    client.post(
        "/auth/signup",
        json={
            "name": "Login User",
            "email": "login@example.com",
            "password": "Secretpass1!"
        }
    )

    # Login
    response = client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "Secretpass1!"
        }
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "user" in data
    assert data["user"]["name"] == "Login User"
    assert data["user"]["email"] == "login@example.com"


def test_login_invalid_password(client):
    """Test login fails with incorrect password."""
    # Register the user
    client.post(
        "/auth/signup",
        json={
            "name": "Login User",
            "email": "login@example.com",
            "password": "Secretpass1!"
        }
    )

    # Attempt login with bad password
    response = client.post(
        "/auth/login",
        json={
            "email": "login@example.com",
            "password": "wrongpassword"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_user(client):
    """Test login fails for an email that doesn't exist."""
    response = client.post(
        "/auth/login",
        json={
            "email": "nonexistent@example.com",
            "password": "somepassword"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


# ==========================================
# CHAT ENDPOINT TESTS (MOCKED)
# ==========================================

def _auth_token(client) -> str:
    """Sign up + log in, return the JWT for authenticated requests."""
    client.post("/auth/signup", json={
        "name": "Chat User", "email": "chat@example.com", "password": "Password123!",
    })
    res = client.post("/auth/login", json={
        "email": "chat@example.com", "password": "Password123!",
    })
    return res.json()["token"]


@patch("src.utils.chat._stream_one_turn")
def test_chat_simple_text_response(mock_stream_turn, client):
    """Test chat API returns standard LLM chat streaming outputs using mock streams."""
    async def mock_stream(*args, **kwargs):
        yield "data: {\"choices\": [{\"delta\": {\"content\": \"Hello! How can I help you?\"}}]}\n\n"

    mock_stream_turn.side_effect = mock_stream

    token = _auth_token(client)
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    assert "Hello! How can I help you?" in response.text


def test_chat_requires_auth(client):
    """Chat without a token is rejected."""
    response = client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Hello"}]},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
