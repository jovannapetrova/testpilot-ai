import os
import sys
from pathlib import Path
import json

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app  # noqa: E402
from models.database import Project, Report  # noqa: E402
from services.database import SessionLocal  # noqa: E402
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


def test_report_history_is_user_scoped_across_login():
    init_db()

    user_a = client.post(
        "/auth/register",
        json={
            "full_name": "User A",
            "email": "user-a@example.com",
            "password": "strong-password",
        },
    ).json()
    token_a = user_a["access_token"]
    user_a_id = user_a["user"]["id"]

    db = SessionLocal()
    report_data = {
        "project_id": "project-a",
        "project_name": "Private Project",
        "status": "completed",
        "overall_score": 91,
        "quality_score": 90,
        "security_score": 92,
        "test_score": 91,
        "code_analysis": {},
        "security_findings": [],
        "quality_metrics": [],
        "generated_tests": [],
        "metadata": {"project_intelligence": {"frameworks": ["FastAPI"]}},
    }
    db.add(Project(id="project-a", user_id=user_a_id, name="Private Project", source_type="upload", status="completed"))
    db.add(
        Report(
            project_id="project-a",
            user_id=user_a_id,
            project_name="Private Project",
            status="completed",
            language="Python",
            overall_score=91,
            quality_score=90,
            security_score=92,
            test_score=91,
            report_json=json.dumps(report_data),
        )
    )
    db.commit()
    db.close()

    reports_a = client.get("/reports", headers={"Authorization": f"Bearer {token_a}"})
    assert reports_a.status_code == 200
    assert [item["project_id"] for item in reports_a.json()["reports"]] == ["project-a"]

    login_a = client.post(
        "/auth/login",
        json={"email": "user-a@example.com", "password": "strong-password"},
    ).json()
    reports_after_login = client.get(
        "/reports",
        headers={"Authorization": f"Bearer {login_a['access_token']}"},
    )
    assert reports_after_login.status_code == 200
    assert len(reports_after_login.json()["reports"]) == 1

    user_b = client.post(
        "/auth/register",
        json={
            "full_name": "User B",
            "email": "user-b@example.com",
            "password": "strong-password",
        },
    ).json()
    reports_b = client.get("/reports", headers={"Authorization": f"Bearer {user_b['access_token']}"})
    assert reports_b.status_code == 200
    assert reports_b.json()["reports"] == []
