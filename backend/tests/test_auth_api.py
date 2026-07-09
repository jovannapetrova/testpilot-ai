import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402
from services.database import init_db  # noqa: E402


client = TestClient(app)


def test_register_login_and_profile_flow():
    init_db()

    register = client.post(
        "/auth/register",
        json={
            "full_name": "Test User",
            "email": "test@example.com",
            "password": "strong-password",
        },
    )

    assert register.status_code == 200
    body = register.json()
    assert body["access_token"]
    assert body["user"]["email"] == "test@example.com"
    assert "password_hash" not in body["user"]

    login = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "strong-password",
            "remember_me": True,
        },
    )

    assert login.status_code == 200
    token = login.json()["access_token"]

    profile = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert profile.status_code == 200
    assert profile.json()["user"]["full_name"] == "Test User"


def test_reports_are_protected():
    response = client.get("/reports")
    assert response.status_code == 401
