from pathlib import Path
from datetime import datetime, timedelta, timezone
import logging
import os
import shutil
import tempfile
import uuid
import csv
import json
from io import StringIO
from urllib.parse import urlparse

import uvicorn
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response
from fastapi.exceptions import RequestValidationError
from git import Repo
from sqlalchemy.orm import Session

from agents.orchestrator import AgentOrchestrator
from models.database import PasswordResetToken, Project, User, utc_now
from models.schemas import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    GitHubAnalyzeRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    UpdateProfileRequest,
    VerifyResetCodeRequest,
)
from services.analysis_progress import AGENT_ORDER, forget_analysis, get_progress, start_analysis, fail_analysis
from services.api_errors import (
    http_exception_handler,
    raise_api_error,
    validation_exception_handler,
)
from services.auth_service import (
    create_access_token,
    create_refresh_token,
    create_verification_code,
    decode_token,
    get_current_user,
    hash_reset_code,
    hash_password,
    normalize_email,
    public_user,
    token_is_current_for_user,
    verify_password,
)
from services.database import SessionLocal, get_db, init_db
from services.email_service import (
    email_delivery_configured,
    send_password_reset_code_email,
)
from services.report_storage import (
    ActiveAnalysisDeletionError,
    build_markdown_report,
    delete_completed_report_projects,
    delete_project_analysis,
    delete_report_record,
    generate_pdf_report,
    get_report_record,
    save_analysis_report,
    list_reports,
    load_report,
)
from utils.file_utils import ArchiveValidationError, archive_limits_from_env, safe_extract_zip

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("testpilot")

CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]
CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX") or None

OPENAPI_TAGS = [
    {"name": "Health", "description": "Runtime health and deployment checks."},
    {"name": "Authentication", "description": "JWT session and password reset verification-code authentication."},
    {"name": "Users", "description": "Authenticated user profile and account management."},
    {"name": "Projects", "description": "ZIP upload, GitHub analysis and project archive operations."},
    {"name": "Analysis", "description": "Analysis progress and agent execution state."},
    {"name": "Reports", "description": "Persisted reports, exports, deletion and comparison."},
    {"name": "Dashboard", "description": "Account-level analytics and report summaries."},
]

app = FastAPI(
    title="TestPilot AI API",
    version="1.0.0",
    description="Authenticated multi-agent software quality analysis API with user-scoped persistence.",
    openapi_tags=OPENAPI_TAGS,
)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_ORIGIN_REGEX,
    allow_credentials="*" not in CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def log_startup():
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        if os.getenv("JWT_SECRET", "dev-only-change-me") == "dev-only-change-me":
            raise RuntimeError("JWT_SECRET must be configured in production.")
    init_db()
    mark_stale_analysis_jobs()
    logger.info("TestPilot AI API starting with CORS origins: %s", CORS_ORIGINS)


def detect_language(files):
    python_files = [f for f in files if f.suffix == ".py"]
    js_files = [f for f in files if f.suffix in [".js", ".jsx", ".ts", ".tsx"]]
    java_files = [f for f in files if f.suffix == ".java"]

    if len(python_files) >= max(len(js_files), len(java_files)):
        return "Python"
    if len(js_files) >= max(len(python_files), len(java_files)):
        return "JavaScript / React"
    if len(java_files) > 0:
        return "Java"

    return "Unknown"


def _now_iso(value) -> str | None:
    return value.isoformat() if value else None


def _seconds_since(value) -> int:
    if not value:
        return 0
    try:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return max(0, int((datetime.now(timezone.utc) - value).total_seconds()))
    except Exception:
        return 0


def project_summary(project: Project) -> dict:
    frameworks = []
    report_scores = {}
    try:
        latest_report = max(project.reports, key=lambda item: item.created_at) if project.reports else None
        if latest_report:
            report_data = json.loads(latest_report.report_json)
            frameworks = report_data.get("metadata", {}).get("project_intelligence", {}).get("frameworks", [])
            report_scores = {
                "overall_score": latest_report.overall_score,
                "quality_score": latest_report.quality_score,
                "security_score": latest_report.security_score,
                "test_score": latest_report.test_score,
            }
    except Exception:
        frameworks = []

    return {
        "id": project.id,
        "project_id": project.id,
        "name": project.name,
        "project_name": project.name,
        "source_type": project.source_type,
        "source_url": project.source_url,
        "filename": project.filename,
        "language": project.language,
        "frameworks": frameworks,
        "total_files": project.total_files,
        "status": project.status,
        "progress": project.progress,
        "current_stage": project.current_stage,
        "error": project.error,
        "created_at": _now_iso(project.created_at),
        "updated_at": _now_iso(project.updated_at),
        "started_at": _now_iso(project.started_at),
        "completed_at": _now_iso(project.completed_at),
        **report_scores,
    }


def create_auth_payload(user: User) -> dict:
    return {
        "access_token": create_access_token(user),
        "refresh_token": create_refresh_token(user),
        "token_type": "bearer",
        "user": public_user(user),
    }


def update_project_status(
    db: Session,
    project_id: str,
    user_id: str,
    status_value: str,
    progress: int | None = None,
    error: str | None = None,
    current_stage: str | None = None,
) -> None:
    project = db.get(Project, project_id)
    if not project or project.user_id != user_id:
        return

    project.status = status_value
    project.updated_at = utc_now()
    if status_value == "running" and not project.started_at:
        project.started_at = utc_now()
    if progress is not None:
        project.progress = progress
    if current_stage is not None:
        project.current_stage = current_stage
    if error:
        project.error = error
    if status_value == "running" and error is None:
        project.error = None
    if status_value in {"completed", "failed"}:
        project.completed_at = utc_now()
    db.commit()


def make_progress_callback(db: Session, project_id: str, user_id: str):
    total_agents = max(1, len(AGENT_ORDER))

    def callback(agent_name: str, stage_status: str, message: str = "") -> None:
        if stage_status == "running":
            completed = max(0, AGENT_ORDER.index(agent_name)) if agent_name in AGENT_ORDER else 0
            progress = min(95, round((completed / total_agents) * 100))
            update_project_status(
                db,
                project_id,
                user_id,
                "running",
                progress=progress,
                current_stage=agent_name,
            )
        elif stage_status == "completed":
            completed = (AGENT_ORDER.index(agent_name) + 1) if agent_name in AGENT_ORDER else total_agents
            progress = min(99, round((completed / total_agents) * 100))
            update_project_status(
                db,
                project_id,
                user_id,
                "running",
                progress=progress,
                current_stage=agent_name,
            )
        elif stage_status == "failed":
            update_project_status(
                db,
                project_id,
                user_id,
                "failed",
                error=message or "Analysis failed.",
                current_stage=agent_name,
            )

    return callback


def mark_stale_analysis_jobs() -> None:
    db = SessionLocal()
    try:
        stale_jobs = db.query(Project).filter(Project.status == "running").all()
        for project in stale_jobs:
            project.status = "failed"
            project.progress = min(project.progress or 0, 99)
            project.current_stage = "Interrupted"
            project.error = "Analysis was interrupted before completion. Please retry the analysis."
            project.updated_at = utc_now()
            project.completed_at = utc_now()
        if stale_jobs:
            logger.warning("Marked %s stale analysis job(s) as failed during startup.", len(stale_jobs))
            db.commit()
    finally:
        db.close()


def owned_report_or_404(project_id: str, user_id: str, db: Session):
    record = get_report_record(project_id, user_id, db)
    if not record:
        raise_api_error("NOT_FOUND", "Report not found.", status.HTTP_404_NOT_FOUND)
    if record.status != "completed":
        raise_api_error("NOT_FOUND", "Report not found.", status.HTTP_404_NOT_FOUND)
    return record


def remove_owned_project_artifacts(project_id: str) -> None:
    from services.report_storage import remove_project_artifacts

    remove_project_artifacts(project_id)


def _token_expired(value) -> bool:
    if not value:
        return True
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value < datetime.now(timezone.utc)


PASSWORD_RESET_GENERIC_MESSAGE = "If an account exists for that email, a verification code will be sent shortly."


def _password_reset_code_minutes() -> int:
    return max(1, int(os.getenv("PASSWORD_RESET_CODE_MINUTES", os.getenv("PASSWORD_RESET_TOKEN_MINUTES", "30"))))


def _password_reset_resend_seconds() -> int:
    return max(0, int(os.getenv("PASSWORD_RESET_RESEND_SECONDS", "60")))


def _latest_active_password_reset_code(user: User, db: Session) -> PasswordResetToken | None:
    return (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )


def _seconds_until_reset_resend(reset_code: PasswordResetToken | None) -> int:
    resend_seconds = _password_reset_resend_seconds()
    if resend_seconds <= 0 or not reset_code or not reset_code.created_at:
        return 0

    created_at = reset_code.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    elapsed = int((datetime.now(timezone.utc) - created_at).total_seconds())
    return max(0, resend_seconds - elapsed)


def _issue_password_reset_code(user: User, db: Session) -> str:
    now = utc_now()
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now})
    code = create_verification_code()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hash_reset_code(code),
            expires_at=now + timedelta(minutes=_password_reset_code_minutes()),
        )
    )
    db.commit()
    return code


def _find_valid_password_reset_code(
    email: str,
    code: str,
    db: Session,
) -> tuple[User | None, PasswordResetToken | None]:
    user = db.query(User).filter(User.email == normalize_email(email)).first()
    if not user or not user.is_active:
        return user, None

    reset_code = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.token_hash == hash_reset_code(code),
            PasswordResetToken.used_at.is_(None),
        )
        .first()
    )

    if not reset_code or _token_expired(reset_code.expires_at):
        return user, None

    return user, reset_code


def restore_uploaded_project(project: Project, project_dir: Path, extracted_dir: Path) -> None:
    if extracted_dir.exists() and any(extracted_dir.iterdir()):
        return
    if not project.upload_blob or not project.filename:
        return

    project_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)
    saved_file = project_dir / project.filename
    saved_file.write_bytes(project.upload_blob)
    safe_extract_zip(saved_file, extracted_dir, archive_limits_from_env())


def run_github_analysis_background(project_id: str, url: str, user_id: str):
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"
    project_name = url.rstrip("/").split("/")[-1]
    db = SessionLocal()

    try:
        update_project_status(db, project_id, user_id, "running", 5, current_stage="Cloning repository")
        try:
            Repo.clone_from(url, extracted_dir, depth=1)
        except Exception as exc:
            logger.warning("GitHub clone failed for project %s: %s", project_id, exc)
            public_message = "Repository could not be cloned. Confirm that the URL is public and accessible."
            fail_analysis(project_id, public_message)
            update_project_status(
                db,
                project_id,
                user_id,
                "failed",
                error=public_message,
                current_stage="Clone failed",
            )
            return

        files = [p for p in extracted_dir.rglob("*") if p.is_file()]
        project = db.get(Project, project_id)
        if project and project.user_id == user_id:
            project.language = detect_language(files)
            project.total_files = len(files)
            project.updated_at = utc_now()
            db.commit()

        update_project_status(db, project_id, user_id, "running", 10, current_stage="Repository cloned")

        orchestrator = AgentOrchestrator()
        report = orchestrator.analyze(
            project_dir=extracted_dir,
            project_id=project_id,
            project_name=project_name,
            on_progress=make_progress_callback(db, project_id, user_id),
        )

        save_analysis_report(report, user_id=user_id, db=db)

    except Exception as exc:
        logger.exception("GitHub analysis failed for project %s", project_id)
        public_message = "Analysis failed while processing this repository."
        fail_analysis(project_id, public_message)
        update_project_status(
            db,
            project_id,
            user_id,
            "failed",
            error=public_message,
            current_stage="Analysis failed",
        )
    finally:
        db.close()


@app.get("/", tags=["Health"], summary="Backend service root")
def health_check():
    return {
        "status": "online",
        "service": "TestPilot AI Backend",
    }


@app.get("/health", tags=["Health"], summary="Health check")
def health():
    return {
        "status": "healthy",
        "service": "testpilot-ai-backend",
        "version": app.version,
    }


@app.post("/auth/register", tags=["Authentication"], summary="Register a user account")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    email = normalize_email(request.email)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise_api_error(
            "DUPLICATE_EMAIL",
            "An account with this email already exists.",
            status.HTTP_409_CONFLICT,
        )

    user = User(
        full_name=request.full_name.strip(),
        email=email,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_auth_payload(user)


@app.post("/auth/login", tags=["Authentication"], summary="Create an authenticated JWT session")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == normalize_email(request.email)).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise_api_error(
            "INVALID_CREDENTIALS",
            "Incorrect email or password.",
            status.HTTP_401_UNAUTHORIZED,
        )
    if not user.is_active:
        raise_api_error("FORBIDDEN", "This account is disabled.", status.HTTP_403_FORBIDDEN)

    user.last_login_at = utc_now()
    db.commit()
    db.refresh(user)
    return create_auth_payload(user)


@app.post("/auth/refresh", tags=["Authentication"], summary="Refresh a JWT session")
def refresh_session(request: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(request.refresh_token, "refresh")
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise_api_error(
            "SESSION_EXPIRED",
            "Your session is invalid or expired. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        )
    if not token_is_current_for_user(payload, user):
        raise_api_error(
            "SESSION_EXPIRED",
            "Your password was changed. Please sign in again.",
            status.HTTP_401_UNAUTHORIZED,
        )
    return create_auth_payload(user)


@app.post("/auth/logout", tags=["Authentication"], summary="End the current stateless JWT session")
def logout(_: User = Depends(get_current_user)):
    return {"success": True, "message": "Logged out successfully."}


@app.post("/auth/forgot-password", tags=["Authentication"], summary="Request a password reset verification code")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == normalize_email(request.email)).first()
    delivery_ready = email_delivery_configured()
    resend_after_seconds = _password_reset_resend_seconds()

    if user and user.is_active and delivery_ready:
        active_code = _latest_active_password_reset_code(user, db)
        if _seconds_until_reset_resend(active_code) == 0:
            code = _issue_password_reset_code(user, db)
            send_password_reset_code_email(user.email, code)

    return {
        "success": True,
        "delivery_configured": delivery_ready,
        "message": PASSWORD_RESET_GENERIC_MESSAGE,
        "resend_after_seconds": resend_after_seconds,
    }


@app.post("/auth/verify-reset-code", tags=["Authentication"], summary="Verify a password reset code")
def verify_reset_code(request: VerifyResetCodeRequest, db: Session = Depends(get_db)):
    _, reset_code = _find_valid_password_reset_code(request.email, request.code, db)
    if not reset_code:
        raise_api_error(
            "INVALID_RESET_CODE",
            "The verification code is invalid or expired. Request a new code.",
            status.HTTP_400_BAD_REQUEST,
        )

    return {
        "success": True,
        "message": "Verification code accepted. Choose a new password.",
        "expires_at": _now_iso(reset_code.expires_at),
    }


@app.post("/auth/reset-password", tags=["Authentication"], summary="Reset a password with a verified code")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    user, reset_code = _find_valid_password_reset_code(request.email, request.code, db)
    if not user or not reset_code:
        raise_api_error(
            "INVALID_RESET_CODE",
            "The verification code is invalid or expired. Request a new code.",
            status.HTTP_400_BAD_REQUEST,
        )

    changed_at = utc_now()
    user.password_hash = hash_password(request.new_password)
    user.password_changed_at = changed_at
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": changed_at})
    db.commit()
    return {"success": True, "message": "Password reset successful. You can now sign in."}


@app.get("/users/me", tags=["Users"], summary="Get current user profile")
def me(current_user: User = Depends(get_current_user)):
    return {"success": True, "user": public_user(current_user)}


@app.patch("/users/me", tags=["Users"], summary="Update current user profile")
def update_profile(
    request: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current_user.id)
    if request.full_name is not None:
        user.full_name = request.full_name.strip()
    if request.avatar_url is not None:
        user.avatar_url = request.avatar_url.strip() or None
    db.commit()
    db.refresh(user)
    return {"success": True, "user": public_user(user)}


@app.post("/users/me/change-password", tags=["Users"], summary="Change current user password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current_user.id)
    if not verify_password(request.current_password, user.password_hash):
        raise_api_error(
            "INVALID_CREDENTIALS",
            "Current password is incorrect.",
            status.HTTP_400_BAD_REQUEST,
        )
    user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully."}


@app.delete("/users/me", tags=["Users"], summary="Delete current user account and owned data")
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current_user.id)
    owned_project_ids = [project.id for project in user.projects] if user else []
    db.delete(user)
    db.commit()
    for project_id in owned_project_ids:
        remove_owned_project_artifacts(project_id)
    return {"success": True, "message": "Account deleted successfully."}


@app.post("/projects/upload", tags=["Projects"], summary="Upload and validate a ZIP project")
async def upload_project(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filename = Path(file.filename or "").name
    if not filename or not filename.lower().endswith(".zip"):
        raise_api_error(
            "INVALID_ARCHIVE",
            "Only ZIP project archives are supported.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    project_id = str(uuid.uuid4())
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"
    limits = archive_limits_from_env()

    project_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    saved_file = project_dir / filename

    upload_bytes = await file.read()
    if len(upload_bytes) > limits.max_upload_bytes:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise_api_error(
            "UPLOAD_TOO_LARGE",
            "The uploaded archive is larger than the configured upload limit.",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    with saved_file.open("wb") as buffer:
        buffer.write(upload_bytes)

    try:
        safe_extract_zip(saved_file, extracted_dir, limits)
    except ArchiveValidationError as exc:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise_api_error(exc.code, exc.message, exc.status_code)

    files = [p for p in extracted_dir.rglob("*") if p.is_file()]
    if not files:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise_api_error(
            "INVALID_ARCHIVE",
            "The archive does not contain analyzable files.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    language = detect_language(files)

    project = Project(
        id=project_id,
        user_id=current_user.id,
        name=Path(filename).stem,
        source_type="upload",
        filename=filename,
        language=language,
        total_files=len(files),
        status="queued",
        progress=0,
        current_stage="Uploaded",
        upload_blob=upload_bytes,
    )
    db.add(project)
    db.commit()

    return {
        "success": True,
        "message": "Project uploaded and extracted successfully.",
        "project_id": project_id,
        "filename": filename,
        "language": language,
        "total_files": len(files),
        "python_files": len([f for f in files if f.suffix == ".py"]),
        "javascript_files": len([f for f in files if f.suffix in [".js", ".jsx", ".ts", ".tsx"]]),
        "java_files": len([f for f in files if f.suffix == ".java"]),
    }


@app.post("/projects/{project_id}/analyze", tags=["Projects"], summary="Run multi-agent analysis for an uploaded project")
def analyze_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"
    project = db.get(Project, project_id)

    if not project or project.user_id != current_user.id:
        raise_api_error("NOT_FOUND", "Project not found.", status.HTTP_404_NOT_FOUND)

    try:
        restore_uploaded_project(project, project_dir, extracted_dir)
    except ArchiveValidationError as exc:
        update_project_status(
            db,
            project_id,
            current_user.id,
            "failed",
            error=exc.message,
            current_stage="Archive validation failed",
        )
        raise_api_error(exc.code, exc.message, exc.status_code)

    if not extracted_dir.exists():
        raise_api_error("NOT_FOUND", "Extracted project folder not found.", status.HTTP_404_NOT_FOUND)

    update_project_status(db, project_id, current_user.id, "running", 5, current_stage="Preparing analysis")
    project_name = project.name or project_id
    zip_files = list(project_dir.glob("*.zip"))

    if zip_files:
        project_name = zip_files[0].stem

    try:
        orchestrator = AgentOrchestrator()
        report = orchestrator.analyze(
            project_dir=extracted_dir,
            project_id=project_id,
            project_name=project_name,
            on_progress=make_progress_callback(db, project_id, current_user.id),
        )
    except Exception:
        logger.exception("ZIP analysis failed for project %s", project_id)
        public_message = "Analysis failed while processing this project."
        update_project_status(
            db,
            project_id,
            current_user.id,
            "failed",
            error=public_message,
            current_stage="Analysis failed",
        )
        raise_api_error("ANALYSIS_FAILED", public_message, status.HTTP_500_INTERNAL_SERVER_ERROR)

    metadata = save_analysis_report(report, user_id=current_user.id, db=db)

    return {
        "success": True,
        "message": "Multi-agent analysis completed.",
        "report": report.model_dump(mode="json"),
        "metadata": metadata,
    }


@app.post("/projects/github", tags=["Projects"], summary="Start analysis for a public GitHub repository")
def analyze_github_repository(
    request: GitHubAnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    url = request.url.strip()

    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.scheme != "https" or parsed.netloc.lower() != "github.com" or len(path_parts) < 2:
        raise_api_error(
            "INVALID_GITHUB_URL",
            "Enter a valid public GitHub HTTPS repository URL.",
            status.HTTP_400_BAD_REQUEST,
        )

    project_id = str(uuid.uuid4())
    project_name = path_parts[1].removesuffix(".git")

    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"

    project_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    db.add(
        Project(
            id=project_id,
            user_id=current_user.id,
            name=project_name,
            source_type="github",
            source_url=url,
            status="queued",
            progress=0,
            current_stage="Queued",
        )
    )
    db.commit()
    start_analysis(project_id, project_name)

    background_tasks.add_task(
        run_github_analysis_background,
        project_id,
        url,
        current_user.id,
    )

    return {
        "success": True,
        "message": "GitHub analysis started.",
        "project_id": project_id,
        "project_name": project_name,
        "status": "queued",
    }


@app.get("/analysis/{project_id}/progress", tags=["Analysis"], summary="Get persisted analysis progress")
def analysis_progress(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise_api_error("NOT_FOUND", "Analysis not found.", status.HTTP_404_NOT_FOUND)

    progress = get_progress(project_id)

    if progress is None:
        total_agents = len(AGENT_ORDER) if project.status in {"running", "completed", "failed"} else 0
        completed_agents = total_agents if project.status == "completed" else 0
        return {
            "project_id": project.id,
            "project_name": project.name,
            "status": project.status,
            "progress": project.progress,
            "current_agent": project.current_stage or project.status.title(),
            "started_at": _now_iso(project.started_at or project.created_at),
            "finished_at": _now_iso(project.completed_at),
            "elapsed_seconds": _seconds_since(project.started_at or project.created_at) if project.status == "running" else 0,
            "eta_seconds": None,
            "completed_agents": completed_agents,
            "total_agents": total_agents,
            "agents": [],
            "error": project.error,
        }

    return progress


@app.get("/projects", tags=["Projects"], summary="List current user's projects")
def get_projects(
    source_type: str | None = None,
    status_filter: str | None = None,
    search: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Project).filter(Project.user_id == current_user.id)
    if source_type:
        query = query.filter(Project.source_type == source_type)
    if status_filter:
        query = query.filter(Project.status == status_filter)
    if search:
        query = query.filter(Project.name.ilike(f"%{search}%"))
    projects = query.order_by(Project.created_at.desc()).all()
    return {"success": True, "projects": [project_summary(project) for project in projects]}


@app.delete("/projects/{project_id}", tags=["Projects"], summary="Delete one owned completed or failed analysis")
def delete_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = delete_project_analysis(project_id, current_user.id, db)
    except ActiveAnalysisDeletionError:
        raise_api_error(
            "ANALYSIS_ACTIVE",
            "This analysis is still queued or running. Wait for it to finish before deleting it.",
            status.HTTP_409_CONFLICT,
        )

    if not result:
        raise_api_error("NOT_FOUND", "Analysis not found.", status.HTTP_404_NOT_FOUND)

    forget_analysis(project_id)
    return {
        "success": True,
        "message": "Analysis deleted successfully.",
        **result,
    }


@app.get("/reports", tags=["Reports"], summary="List current user's persisted reports")
def get_reports(
    search: str | None = None,
    status_filter: str | None = None,
    sort: str = "newest",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = list_reports(user_id=current_user.id, db=db)
    if status_filter and status_filter != "completed":
        reports = []
    if search:
        needle = search.lower()
        reports = [
            report for report in reports
            if needle in " ".join([
                str(report.get("project_name", "")),
                str(report.get("source_url", "")),
                str(report.get("language", "")),
                " ".join(report.get("frameworks", []) or []),
                str(report.get("status", "")),
            ]).lower()
        ]
    if status_filter:
        reports = [report for report in reports if report.get("status") == status_filter]
    reverse = sort != "oldest"
    reports = sorted(reports, key=lambda item: item.get("created_at") or "", reverse=reverse)
    return {
        "success": True,
        "reports": reports,
    }


@app.get("/reports/{project_id}", tags=["Reports"], summary="Load a persisted analysis report")
def get_report(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = load_report(project_id, user_id=current_user.id, db=db)

    if not report:
        raise_api_error("NOT_FOUND", "Report not found.", status.HTTP_404_NOT_FOUND)

    return {
        "success": True,
        "report": report,
    }


@app.get("/reports/{project_id}/json", tags=["Reports"], summary="Download a JSON report export")
def download_report_json(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = owned_report_or_404(project_id, current_user.id, db)
    return Response(
        content=record.report_json,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=testpilot-report-{project_id}.json"},
    )


@app.get("/reports/{project_id}/pdf", tags=["Reports"], summary="Download a PDF report export")
def download_report_pdf(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = owned_report_or_404(project_id, current_user.id, db)
    if record and record.pdf_blob:
        return Response(
            content=record.pdf_blob,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=testpilot-report-{project_id}.pdf"},
        )

    try:
        report_data = json.loads(record.report_json)
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_path = Path(temp_dir) / "report.pdf"
            generate_pdf_report(pdf_path, report_data)
            pdf_blob = pdf_path.read_bytes()
        record.pdf_blob = pdf_blob
        db.commit()
        return Response(
            content=pdf_blob,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=testpilot-report-{project_id}.pdf"},
        )
    except Exception:
        logger.exception("PDF export failed for project %s.", project_id)
        raise_api_error(
            "REPORT_NOT_READY",
            "PDF report is not available for this analysis yet.",
            status.HTTP_404_NOT_FOUND,
        )


@app.get("/reports/{project_id}/csv", tags=["Reports"], summary="Download a CSV report export")
def download_report_csv(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = owned_report_or_404(project_id, current_user.id, db)
    report = json.loads(record.report_json)

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Metric", "Value"])
    writer.writerow(["Project", report.get("project_name")])
    writer.writerow(["Overall Score", report.get("overall_score")])
    writer.writerow(["Quality Score", report.get("quality_score")])
    writer.writerow(["Security Score", report.get("security_score")])
    writer.writerow(["Testing Score", report.get("test_score")])
    coverage = report.get("coverage", {}) or {}
    test_summary = report.get("metadata", {}).get("generated_tests_summary", {}) or {}
    coverage_available = (
        coverage.get("available")
        or coverage.get("measured")
        or (coverage.get("executed") and not coverage.get("estimated"))
    )
    coverage_label = coverage.get("display_label") or (
        f"{coverage.get('coverage_percent', 0)}%"
        if coverage_available
        else "Not measured"
    )
    executed_tests = int(test_summary.get("executed_tests", 0) or 0)
    writer.writerow(["Coverage", coverage_label])
    writer.writerow(["Coverage Evidence State", coverage.get("evidence_state", "unavailable")])
    writer.writerow(["Security Findings", len(report.get("security_findings", []))])
    writer.writerow(["Generated Test Candidates", len(report.get("generated_tests", []))])
    writer.writerow(["Ready To Execute", test_summary.get("ready_to_execute", test_summary.get("executable_tests", len(report.get("generated_tests", []))))])
    writer.writerow(["Executed Generated Tests", executed_tests])
    writer.writerow(["Passed Generated Tests", test_summary.get("passed") if executed_tests else "N/A"])
    writer.writerow(["Failed Generated Tests", test_summary.get("failed") if executed_tests else "N/A"])
    writer.writerow(["Needs Human Test Design", test_summary.get("needs_human_test_design", 0)])
    writer.writerow(["Recommendations", len(report.get("recommendations", []))])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=testpilot-{project_id}.csv"},
    )


@app.get("/reports/{project_id}/markdown", tags=["Reports"], summary="Download a Markdown report export")
def download_report_markdown(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = owned_report_or_404(project_id, current_user.id, db)
    if record and record.markdown_text:
        return PlainTextResponse(
            record.markdown_text,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=testpilot-{project_id}.md"},
        )

    report = json.loads(record.report_json)
    md = build_markdown_report(report)
    record.markdown_text = md
    db.commit()

    return PlainTextResponse(
        md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=testpilot-{project_id}.md"},
    )


@app.get("/reports/compare/{first_id}/{second_id}", tags=["Reports"], summary="Compare two owned reports")
def compare_reports(
    first_id: str,
    second_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    first = load_report(first_id, user_id=current_user.id, db=db)
    second = load_report(second_id, user_id=current_user.id, db=db)

    if not first or not second:
        raise_api_error("NOT_FOUND", "One or both reports not found.", status.HTTP_404_NOT_FOUND)

    def metric_value(report: dict, key: str) -> float | None:
        if key not in report or report.get(key) is None:
            return None
        try:
            return round(float(report.get(key)), 2)
        except (TypeError, ValueError):
            return None

    def diff(key):
        first_value = metric_value(first, key)
        second_value = metric_value(second, key)
        if first_value is None or second_value is None:
            return None
        return round(second_value - first_value, 2)

    def report_label(report: dict, other: dict) -> str:
        name = report.get("project_name") or "Unnamed report"
        if name == (other.get("project_name") or "Unnamed report"):
            suffix = str(report.get("project_id") or "")[:8]
            return f"{name} ({suffix})" if suffix else name
        return name

    first_label = report_label(first, second)
    second_label = report_label(second, first)

    def compare_metric(label: str, key: str, unit: str = "points") -> dict:
        first_value = metric_value(first, key)
        second_value = metric_value(second, key)
        if first_value is None or second_value is None:
            return {
                "key": key,
                "label": label,
                "first_value": first_value,
                "second_value": second_value,
                "delta": None,
                "absolute_delta": None,
                "direction": "missing",
                "summary": f"{label} is unavailable for one or both reports.",
            }

        delta = round(second_value - first_value, 2)
        absolute_delta = abs(delta)
        if delta > 0:
            direction = "second_higher"
            summary = f"{second_label} is {absolute_delta:g} {unit} higher than {first_label}."
        elif delta < 0:
            direction = "second_lower"
            summary = f"{second_label} is {absolute_delta:g} {unit} lower than {first_label}."
        else:
            direction = "equal"
            summary = f"{first_label} and {second_label} are equal for {label.lower()}."

        return {
            "key": key,
            "label": label,
            "first_value": first_value,
            "second_value": second_value,
            "delta": delta,
            "absolute_delta": absolute_delta,
            "direction": direction,
            "summary": summary,
        }

    metrics = [
        compare_metric("Overall Score", "overall_score"),
        compare_metric("Quality Score", "quality_score"),
        compare_metric("Security Score", "security_score"),
        compare_metric("Testing Score", "test_score"),
    ]

    return {
        "success": True,
        "comparison": {
            "first": first,
            "second": second,
            "first_label": first_label,
            "second_label": second_label,
            "metrics": metrics,
            "delta": {
                "overall": diff("overall_score"),
                "quality": diff("quality_score"),
                "security": diff("security_score"),
                "testing": diff("test_score"),
                "coverage": round(
                    float(second.get("coverage", {}).get("coverage_percent", 0) or 0)
                    - float(first.get("coverage", {}).get("coverage_percent", 0) or 0),
                    2,
                ),
                "security_findings": len(second.get("security_findings", [])) - len(first.get("security_findings", [])),
                "generated_tests": len(second.get("generated_tests", [])) - len(first.get("generated_tests", [])),
            },
        },
    }


@app.get("/dashboard/summary", tags=["Dashboard"], summary="Get dashboard analytics summary")
def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    all_reports = list_reports(user_id=current_user.id, db=db)
    reports = [report for report in all_reports if report.get("status") == "completed"]
    active_projects = (
        db.query(Project)
        .filter(Project.user_id == current_user.id, Project.status.in_(["queued", "running"]))
        .order_by(Project.created_at.desc())
        .limit(5)
        .all()
    )
    active_project_summaries = [project_summary(project) for project in active_projects]

    if not reports:
        return {
            "success": True,
            "summary": {
                "total_reports": 0,
                "avg_overall": 0,
                "avg_quality": 0,
                "avg_security": 0,
                "avg_testing": 0,
                "latest_reports": [],
                "trend": [],
                "framework_distribution": {},
                "risk_distribution": {},
                "security_findings": 0,
                "generated_tests": 0,
                "total_completed_reports": 0,
                "active_projects": active_project_summaries,
                "running_projects": len(active_project_summaries),
            },
        }

    def avg(key):
        return round(sum(float(r.get(key, 0) or 0) for r in reports) / len(reports), 2)

    trend = [
        {
            "project_id": report.get("project_id"),
            "project_name": report.get("project_name"),
            "overall_score": report.get("overall_score", 0),
            "quality_score": report.get("quality_score", 0),
            "security_score": report.get("security_score", 0),
            "test_score": report.get("test_score", 0),
            "coverage_percent": report.get("coverage_percent", 0),
            "created_at": report.get("created_at"),
        }
        for report in reports[:20]
    ]

    frameworks = {}
    risk_levels = {}
    total_security_findings = 0
    total_generated_tests = 0
    for report in reports:
        total_security_findings += int(report.get("security_findings_count", 0) or 0)
        total_generated_tests += int(report.get("generated_tests_count", 0) or 0)
        for framework in report.get("frameworks", []) or []:
            frameworks[framework] = frameworks.get(framework, 0) + 1
        risk = report.get("risk_level", "Unknown")
        risk_levels[risk] = risk_levels.get(risk, 0) + 1

    return {
        "success": True,
        "summary": {
            "total_reports": len(reports),
            "total_completed_reports": len(reports),
            "avg_overall": avg("overall_score"),
            "avg_quality": avg("quality_score"),
            "avg_security": avg("security_score"),
            "avg_testing": avg("test_score"),
            "latest_reports": reports[:5],
            "trend": trend,
            "framework_distribution": frameworks,
            "risk_distribution": risk_levels,
            "security_findings": total_security_findings,
            "generated_tests": total_generated_tests,
            "active_projects": active_project_summaries,
            "running_projects": len(active_project_summaries),
        },
    }


@app.delete("/reports/{project_id}", tags=["Reports"], summary="Delete one owned report and project")
def delete_report(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        deleted = delete_report_record(project_id, current_user.id, db)
    except ActiveAnalysisDeletionError:
        raise_api_error(
            "ANALYSIS_ACTIVE",
            "This analysis is still queued or running. Wait for it to finish before deleting it.",
            status.HTTP_409_CONFLICT,
        )

    if deleted:
        forget_analysis(project_id)
        return {
            "success": True,
            "message": "Report deleted successfully.",
            "project_id": project_id,
        }

    raise_api_error("NOT_FOUND", "Report not found.", status.HTTP_404_NOT_FOUND)


@app.delete("/reports", tags=["Reports"], summary="Delete all current user's completed reports and linked analyses")
def clear_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = delete_completed_report_projects(current_user.id, db)
    for project_id in result["project_ids"]:
        forget_analysis(project_id)

    return {
        "success": True,
        "message": "All completed reports cleared successfully.",
        "deleted_projects": result["deleted_projects"],
        "deleted_reports": result["deleted_reports"],
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
