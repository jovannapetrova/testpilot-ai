import io
import json
import os
import sys
import zipfile
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import app, mark_stale_analysis_jobs  # noqa: E402
from models.database import PasswordResetToken, Project, Report, utc_now  # noqa: E402
from services.database import SessionLocal, init_db  # noqa: E402

client = TestClient(app)


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8]}@example.com"


def _register(prefix: str = "user") -> dict:
    init_db()
    response = client.post(
        "/auth/register",
        json={
            "full_name": f"{prefix.title()} User",
            "email": _email(prefix),
            "password": "strong-password",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _auth_headers(session: dict) -> dict:
    return {"Authorization": f"Bearer {session['access_token']}"}


def _zip_bytes(entries: dict[str, str]) -> bytes:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    payload.seek(0)
    return payload.getvalue()


def _report_payload(project_id: str, project_name: str, score: int = 90) -> dict:
    return {
        "project_id": project_id,
        "project_name": project_name,
        "status": "completed",
        "overall_score": score,
        "quality_score": score,
        "security_score": score,
        "test_score": score,
        "code_analysis": {},
        "security_findings": [],
        "quality_metrics": [],
        "generated_tests": [],
        "coverage": {"coverage_percent": 0, "estimated": True},
        "recommendations": [],
        "metadata": {"project_intelligence": {"frameworks": ["FastAPI"]}},
    }


def _insert_report(user_id: str, project_id: str, project_name: str, score: int = 90) -> None:
    db = SessionLocal()
    try:
        db.add(Project(id=project_id, user_id=user_id, name=project_name, source_type="upload", status="completed"))
        db.add(
            Report(
                project_id=project_id,
                user_id=user_id,
                project_name=project_name,
                status="completed",
                language="Python",
                overall_score=score,
                quality_score=score,
                security_score=score,
                test_score=score,
                report_json=json.dumps(_report_payload(project_id, project_name, score)),
                pdf_blob=b"%PDF-1.4\n%test\n",
                markdown_text="# Test",
            )
        )
        db.commit()
    finally:
        db.close()


def _capture_reset_codes(monkeypatch):
    deliveries = []
    monkeypatch.setattr("main.email_delivery_configured", lambda: True)

    def send_code(email: str, code: str) -> bool:
        deliveries.append({"email": email, "code": code})
        return True

    monkeypatch.setattr("main.send_password_reset_code_email", send_code)
    return deliveries


def test_register_rejects_invalid_and_duplicate_email():
    init_db()
    invalid = client.post(
        "/auth/register",
        json={"full_name": "Bad Email", "email": "not-an-email", "password": "strong-password"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"

    email = _email("duplicate")
    first = client.post(
        "/auth/register",
        json={"full_name": "Duplicate User", "email": email, "password": "strong-password"},
    )
    assert first.status_code == 200

    duplicate = client.post(
        "/auth/register",
        json={"full_name": "Duplicate User", "email": email, "password": "strong-password"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "DUPLICATE_EMAIL"


def test_login_refresh_current_user_and_change_password_flow():
    session = _register("auth")
    email = session["user"]["email"]

    wrong = client.post("/auth/login", json={"email": email, "password": "wrong-password"})
    assert wrong.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"

    refresh = client.post("/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert refresh.status_code == 200

    bad_refresh = client.post("/auth/refresh", json={"refresh_token": "not-a-token"})
    assert bad_refresh.status_code == 401
    assert bad_refresh.json()["error"]["code"] == "SESSION_EXPIRED"

    profile = client.get("/users/me", headers=_auth_headers(session))
    assert profile.status_code == 200
    assert profile.json()["user"]["email"] == email

    change = client.post(
        "/users/me/change-password",
        headers=_auth_headers(session),
        json={"current_password": "strong-password", "new_password": "new-strong-password"},
    )
    assert change.status_code == 200

    old_login = client.post("/auth/login", json={"email": email, "password": "strong-password"})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"email": email, "password": "new-strong-password"})
    assert new_login.status_code == 200


def test_password_reset_code_flow_is_one_time_and_rejects_old_password(monkeypatch):
    session = _register("reset")
    email = session["user"]["email"]
    deliveries = _capture_reset_codes(monkeypatch)

    forgot = client.post("/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    assert forgot.json()["message"] == "If an account exists for that email, a verification code will be sent shortly."
    assert "debug_reset_token" not in forgot.json()
    assert len(deliveries) == 1
    code = deliveries[0]["code"]
    assert len(code) == 6
    assert code.isdigit()

    verify = client.post("/auth/verify-reset-code", json={"email": email, "code": code})
    assert verify.status_code == 200

    reset = client.post(
        "/auth/reset-password",
        json={
            "email": email,
            "code": code,
            "new_password": "changed-password",
            "confirm_password": "changed-password",
        },
    )
    assert reset.status_code == 200

    reuse = client.post(
        "/auth/reset-password",
        json={
            "email": email,
            "code": code,
            "new_password": "changed-again",
            "confirm_password": "changed-again",
        },
    )
    assert reuse.status_code == 400
    assert reuse.json()["error"]["code"] == "INVALID_RESET_CODE"

    old_login = client.post("/auth/login", json={"email": email, "password": "strong-password"})
    assert old_login.status_code == 401

    new_login = client.post("/auth/login", json={"email": email, "password": "changed-password"})
    assert new_login.status_code == 200

    old_profile = client.get("/users/me", headers=_auth_headers(session))
    assert old_profile.status_code == 401

    old_refresh = client.post("/auth/refresh", json={"refresh_token": session["refresh_token"]})
    assert old_refresh.status_code == 401


def test_password_reset_rejects_invalid_and_expired_codes(monkeypatch):
    session = _register("expired-reset")
    email = session["user"]["email"]
    deliveries = _capture_reset_codes(monkeypatch)

    invalid = client.post("/auth/verify-reset-code", json={"email": email, "code": "000000"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_RESET_CODE"

    forgot = client.post("/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    expired_code = deliveries[-1]["code"]
    db = SessionLocal()
    try:
        row = db.query(PasswordResetToken).filter(PasswordResetToken.used_at.is_(None)).order_by(PasswordResetToken.created_at.desc()).first()
        row.expires_at = utc_now() - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    expired = client.post("/auth/verify-reset-code", json={"email": email, "code": expired_code})
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "INVALID_RESET_CODE"


def test_password_reset_resend_is_rate_limited_and_invalidates_previous_code(monkeypatch):
    session = _register("resend")
    email = session["user"]["email"]
    previous_resend = os.environ.get("PASSWORD_RESET_RESEND_SECONDS")
    os.environ["PASSWORD_RESET_RESEND_SECONDS"] = "60"
    deliveries = _capture_reset_codes(monkeypatch)
    generated_codes = iter(["111111", "222222"])
    monkeypatch.setattr("main.create_verification_code", lambda: next(generated_codes))

    try:
        first = client.post("/auth/forgot-password", json={"email": email})
        assert first.status_code == 200
        assert first.json()["resend_after_seconds"] == 60
        assert deliveries[-1]["code"] == "111111"

        throttled = client.post("/auth/forgot-password", json={"email": email})
        assert throttled.status_code == 200
        assert len(deliveries) == 1

        db = SessionLocal()
        try:
            row = db.query(PasswordResetToken).filter(PasswordResetToken.used_at.is_(None)).order_by(PasswordResetToken.created_at.desc()).first()
            row.created_at = utc_now() - timedelta(seconds=61)
            db.commit()
        finally:
            db.close()

        resent = client.post("/auth/forgot-password", json={"email": email})
        assert resent.status_code == 200
        assert deliveries[-1]["code"] == "222222"

        old_code = client.post("/auth/verify-reset-code", json={"email": email, "code": "111111"})
        assert old_code.status_code == 400

        new_code = client.post("/auth/verify-reset-code", json={"email": email, "code": "222222"})
        assert new_code.status_code == 200
    finally:
        if previous_resend is None:
            os.environ.pop("PASSWORD_RESET_RESEND_SECONDS", None)
        else:
            os.environ["PASSWORD_RESET_RESEND_SECONDS"] = previous_resend


def test_forgot_password_keeps_unknown_email_response_generic(monkeypatch):
    deliveries = _capture_reset_codes(monkeypatch)

    known_session = _register("known-reset")
    known = client.post("/auth/forgot-password", json={"email": known_session["user"]["email"]})
    unknown = client.post("/auth/forgot-password", json={"email": _email("unknown-reset")})

    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json()["message"] == unknown.json()["message"]
    assert "debug_reset_token" not in unknown.json()
    assert len(deliveries) == 1


def test_forgot_password_smtp_failure_uses_generic_response(monkeypatch):
    session = _register("smtp-failure")
    monkeypatch.setattr("main.email_delivery_configured", lambda: True)
    monkeypatch.setattr("main.send_password_reset_code_email", lambda email, code: False)

    response = client.post("/auth/forgot-password", json={"email": session["user"]["email"]})

    assert response.status_code == 200
    assert response.json()["message"] == "If an account exists for that email, a verification code will be sent shortly."
    assert "debug_reset_token" not in response.json()


def test_password_reset_validates_password_strength_and_confirmation(monkeypatch):
    session = _register("reset-validation")
    email = session["user"]["email"]
    deliveries = _capture_reset_codes(monkeypatch)

    forgot = client.post("/auth/forgot-password", json={"email": email})
    assert forgot.status_code == 200
    code = deliveries[-1]["code"]

    short_password = client.post(
        "/auth/reset-password",
        json={"email": email, "code": code, "new_password": "short", "confirm_password": "short"},
    )
    assert short_password.status_code == 422

    mismatch = client.post(
        "/auth/reset-password",
        json={
            "email": email,
            "code": code,
            "new_password": "valid-password",
            "confirm_password": "different-password",
        },
    )
    assert mismatch.status_code == 422


def test_magic_link_endpoints_are_removed():
    request = client.post("/auth/magic-link/request", json={"email": _email("magic-removed")})
    verify = client.post("/auth/magic-link/verify", json={"token": "not-a-token"})

    assert request.status_code == 404
    assert verify.status_code == 404


def test_report_download_delete_and_compare_are_user_scoped():
    user_a = _register("owner")
    user_b = _register("intruder")
    project_a = f"project-{uuid4().hex[:8]}"
    project_b = f"project-{uuid4().hex[:8]}"
    _insert_report(user_a["user"]["id"], project_a, "Private Project", 88)
    _insert_report(user_b["user"]["id"], project_b, "Other Project", 70)

    forbidden_get = client.get(f"/reports/{project_a}", headers=_auth_headers(user_b))
    assert forbidden_get.status_code == 404

    forbidden_json = client.get(f"/reports/{project_a}/json", headers=_auth_headers(user_b))
    assert forbidden_json.status_code == 404

    forbidden_pdf = client.get(f"/reports/{project_a}/pdf", headers=_auth_headers(user_b))
    assert forbidden_pdf.status_code == 404

    forbidden_delete = client.delete(f"/reports/{project_a}", headers=_auth_headers(user_b))
    assert forbidden_delete.status_code == 404

    compare_cross_user = client.get(f"/reports/compare/{project_a}/{project_b}", headers=_auth_headers(user_a))
    assert compare_cross_user.status_code == 404

    owner_report = client.get(f"/reports/{project_a}", headers=_auth_headers(user_a))
    assert owner_report.status_code == 200


def test_report_comparison_includes_directional_metric_summaries():
    user = _register("compare")
    project_one = f"project-{uuid4().hex[:8]}"
    project_two = f"project-{uuid4().hex[:8]}"
    _insert_report(user["user"]["id"], project_one, "Redux", 77)
    _insert_report(user["user"]["id"], project_two, "Express", 73)

    response = client.get(
        f"/reports/compare/{project_one}/{project_two}",
        headers=_auth_headers(user),
    )

    assert response.status_code == 200
    comparison = response.json()["comparison"]
    overall = comparison["metrics"][0]
    assert overall["label"] == "Overall Score"
    assert overall["direction"] == "second_lower"
    assert overall["absolute_delta"] == 4
    assert "Express is 4 points lower than Redux." == overall["summary"]
    assert comparison["delta"]["overall"] == -4


def test_dashboard_summary_uses_only_completed_owned_reports():
    user_a = _register("dashboard-owner")
    user_b = _register("dashboard-other")
    project_a = f"project-{uuid4().hex[:8]}"
    project_failed = f"project-{uuid4().hex[:8]}"
    project_b = f"project-{uuid4().hex[:8]}"
    _insert_report(user_a["user"]["id"], project_a, "Completed Owned", 80)
    _insert_report(user_b["user"]["id"], project_b, "Other User", 10)

    db = SessionLocal()
    try:
        db.add(Project(id=project_failed, user_id=user_a["user"]["id"], name="Failed Owned", source_type="upload", status="failed"))
        db.add(
            Report(
                project_id=project_failed,
                user_id=user_a["user"]["id"],
                project_name="Failed Owned",
                status="failed",
                language="Python",
                overall_score=10,
                quality_score=10,
                security_score=10,
                test_score=10,
                report_json=json.dumps(_report_payload(project_failed, "Failed Owned", 10) | {"status": "failed"}),
            )
        )
        db.commit()
    finally:
        db.close()

    summary = client.get("/dashboard/summary", headers=_auth_headers(user_a))

    assert summary.status_code == 200
    data = summary.json()["summary"]
    assert data["total_reports"] == 1
    assert data["avg_overall"] == 80
    assert [report["project_id"] for report in data["latest_reports"]] == [project_a]


def test_zip_upload_rejects_malformed_traversal_and_too_many_files():
    session = _register("zip")

    malformed = client.post(
        "/projects/upload",
        headers=_auth_headers(session),
        files={"file": ("broken.zip", b"not a real zip", "application/zip")},
    )
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "INVALID_ARCHIVE"

    traversal = client.post(
        "/projects/upload",
        headers=_auth_headers(session),
        files={"file": ("traversal.zip", _zip_bytes({"../evil.py": "print('bad')"}), "application/zip")},
    )
    assert traversal.status_code == 422
    assert traversal.json()["error"]["code"] == "INVALID_ARCHIVE"

    previous_limit = os.environ.get("MAX_ARCHIVE_FILES")
    os.environ["MAX_ARCHIVE_FILES"] = "1"
    try:
        too_many = client.post(
            "/projects/upload",
            headers=_auth_headers(session),
            files={"file": ("many.zip", _zip_bytes({"a.py": "print(1)", "b.py": "print(2)"}), "application/zip")},
        )
        assert too_many.status_code == 413
        assert too_many.json()["error"]["code"] == "UPLOAD_TOO_LARGE"
    finally:
        if previous_limit is None:
            os.environ.pop("MAX_ARCHIVE_FILES", None)
        else:
            os.environ["MAX_ARCHIVE_FILES"] = previous_limit


def test_valid_zip_upload_persists_project_for_owner_only():
    owner = _register("zip-owner")
    other = _register("zip-other")

    upload = client.post(
        "/projects/upload",
        headers=_auth_headers(owner),
        files={"file": ("valid.zip", _zip_bytes({"app.py": "def add(a, b):\n    return a + b\n"}), "application/zip")},
    )
    assert upload.status_code == 200
    project_id = upload.json()["project_id"]

    owner_projects = client.get("/projects", headers=_auth_headers(owner))
    assert project_id in [project["project_id"] for project in owner_projects.json()["projects"]]

    other_progress = client.get(f"/analysis/{project_id}/progress", headers=_auth_headers(other))
    assert other_progress.status_code == 404


def test_github_invalid_url_and_clone_failure_set_persistent_failed_state(monkeypatch):
    session = _register("github")

    invalid = client.post("/projects/github", headers=_auth_headers(session), json={"url": "https://example.com/repo"})
    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "INVALID_GITHUB_URL"

    def fail_clone(*_, **__):
        raise RuntimeError("clone denied")

    monkeypatch.setattr("main.Repo.clone_from", fail_clone)
    response = client.post(
        "/projects/github",
        headers=_auth_headers(session),
        json={"url": "https://github.com/example/repo"},
    )
    assert response.status_code == 200
    project_id = response.json()["project_id"]

    progress = client.get(f"/analysis/{project_id}/progress", headers=_auth_headers(session))
    assert progress.status_code == 200
    assert progress.json()["status"] == "failed"
    assert "could not be cloned" in progress.json()["error"].lower()


def test_stale_running_jobs_are_marked_failed_on_recovery():
    session = _register("stale")
    project_id = f"project-{uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        db.add(
            Project(
                id=project_id,
                user_id=session["user"]["id"],
                name="Interrupted",
                source_type="github",
                source_url="https://github.com/example/repo",
                status="running",
                progress=42,
                current_stage="Security Agent",
            )
        )
        db.commit()
    finally:
        db.close()

    mark_stale_analysis_jobs()

    progress = client.get(f"/analysis/{project_id}/progress", headers=_auth_headers(session))
    assert progress.status_code == 200
    assert progress.json()["status"] == "failed"
    assert progress.json()["current_agent"] == "Interrupted"


def test_account_deletion_cascades_owned_projects_reports_and_tokens(monkeypatch):
    session = _register("delete")
    project_id = f"project-{uuid4().hex[:8]}"
    _insert_report(session["user"]["id"], project_id, "Delete Me", 75)
    _capture_reset_codes(monkeypatch)
    forgot = client.post("/auth/forgot-password", json={"email": session["user"]["email"]})
    assert forgot.status_code == 200

    delete = client.delete("/users/me", headers=_auth_headers(session))
    assert delete.status_code == 200

    db = SessionLocal()
    try:
        assert db.get(Project, project_id) is None
        assert db.query(Report).filter(Report.project_id == project_id).first() is None
        assert db.query(PasswordResetToken).filter(PasswordResetToken.user_id == session["user"]["id"]).first() is None
    finally:
        db.close()
