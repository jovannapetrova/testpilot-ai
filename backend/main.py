from pathlib import Path
import logging
import os
import shutil
import uuid
import zipfile
import csv
import json
from io import StringIO

import uvicorn
from fastapi import Depends, FastAPI, UploadFile, File, HTTPException, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from git import Repo
from sqlalchemy.orm import Session

from agents.orchestrator import AgentOrchestrator
from models.database import Project, User, utc_now
from models.schemas import (
    ChangePasswordRequest,
    GitHubAnalyzeRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    UpdateProfileRequest,
)
from services.analysis_progress import get_progress, start_analysis, fail_analysis
from services.auth_service import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    normalize_email,
    public_user,
    verify_password,
)
from services.database import SessionLocal, get_db, init_db
from services.report_storage import (
    REPORTS_DIR,
    build_markdown_report,
    delete_report_record,
    get_report_record,
    save_analysis_report,
    list_reports,
    load_report,
    get_report_json_path,
    get_report_pdf_path,
)

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

app = FastAPI(title="TestPilot AI API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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


def project_summary(project: Project) -> dict:
    frameworks = []
    try:
        latest_report = project.reports[0] if project.reports else None
        if latest_report:
            report_data = json.loads(latest_report.report_json)
            frameworks = report_data.get("metadata", {}).get("project_intelligence", {}).get("frameworks", [])
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
        "error": project.error,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "completed_at": project.completed_at.isoformat() if project.completed_at else None,
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
) -> None:
    project = db.get(Project, project_id)
    if not project or project.user_id != user_id:
        return

    project.status = status_value
    project.updated_at = utc_now()
    if progress is not None:
        project.progress = progress
    if error:
        project.error = error
    if status_value == "completed":
        project.completed_at = utc_now()
    db.commit()


def restore_uploaded_project(project: Project, project_dir: Path, extracted_dir: Path) -> None:
    if extracted_dir.exists() and any(extracted_dir.iterdir()):
        return
    if not project.upload_blob or not project.filename:
        return

    project_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)
    saved_file = project_dir / project.filename
    saved_file.write_bytes(project.upload_blob)
    with zipfile.ZipFile(saved_file, "r") as zip_ref:
        zip_ref.extractall(extracted_dir)


def run_github_analysis_background(project_id: str, url: str, user_id: str):
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"
    project_name = url.rstrip("/").split("/")[-1]
    db = SessionLocal()

    try:
        update_project_status(db, project_id, user_id, "running", 5)
        Repo.clone_from(url, extracted_dir, depth=1)

        orchestrator = AgentOrchestrator()
        report = orchestrator.analyze(
            project_dir=extracted_dir,
            project_id=project_id,
            project_name=project_name,
        )

        save_analysis_report(report, user_id=user_id, db=db)

    except Exception as exc:
        logger.exception("GitHub analysis failed for project %s", project_id)
        fail_analysis(project_id, str(exc))
        update_project_status(db, project_id, user_id, "failed", error=str(exc))
    finally:
        db.close()


@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "TestPilot AI Backend",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "testpilot-ai-backend",
        "version": app.version,
    }


@app.post("/auth/register")
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    email = normalize_email(request.email)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        full_name=request.full_name.strip(),
        email=email,
        password_hash=hash_password(request.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return create_auth_payload(user)


@app.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == normalize_email(request.email)).first()
    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")

    user.last_login_at = utc_now()
    db.commit()
    db.refresh(user)
    return create_auth_payload(user)


@app.post("/auth/refresh")
def refresh_session(request: RefreshRequest, db: Session = Depends(get_db)):
    payload = decode_token(request.refresh_token, "refresh")
    user = db.get(User, payload.get("sub"))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User account is not available.")
    return create_auth_payload(user)


@app.post("/auth/logout")
def logout(_: User = Depends(get_current_user)):
    return {"success": True, "message": "Logged out successfully."}


@app.post("/auth/forgot-password")
def forgot_password(_: dict):
    return {
        "success": True,
        "message": "If an account exists for that email, password reset instructions will be sent when email delivery is configured.",
    }


@app.get("/users/me")
def me(current_user: User = Depends(get_current_user)):
    return {"success": True, "user": public_user(current_user)}


@app.patch("/users/me")
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


@app.post("/users/me/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current_user.id)
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    user.password_hash = hash_password(request.new_password)
    db.commit()
    return {"success": True, "message": "Password changed successfully."}


@app.delete("/users/me")
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user = db.get(User, current_user.id)
    db.delete(user)
    db.commit()
    return {"success": True, "message": "Account deleted successfully."}


@app.post("/projects/upload")
async def upload_project(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".zip"):
        return {"success": False, "message": "Only ZIP files are supported."}

    project_id = str(uuid.uuid4())
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"

    project_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    saved_file = project_dir / file.filename

    upload_bytes = await file.read()
    with saved_file.open("wb") as buffer:
        buffer.write(upload_bytes)

    try:
        with zipfile.ZipFile(saved_file, "r") as zip_ref:
            zip_ref.extractall(extracted_dir)
    except zipfile.BadZipFile:
        return {"success": False, "message": "Invalid ZIP archive."}

    files = [p for p in extracted_dir.rglob("*") if p.is_file()]
    language = detect_language(files)

    project = Project(
        id=project_id,
        user_id=current_user.id,
        name=Path(file.filename).stem,
        source_type="upload",
        filename=file.filename,
        language=language,
        total_files=len(files),
        status="queued",
        progress=0,
        upload_blob=upload_bytes,
    )
    db.add(project)
    db.commit()

    return {
        "success": True,
        "message": "Project uploaded and extracted successfully.",
        "project_id": project_id,
        "filename": file.filename,
        "language": language,
        "total_files": len(files),
        "python_files": len([f for f in files if f.suffix == ".py"]),
        "javascript_files": len([f for f in files if f.suffix in [".js", ".jsx", ".ts", ".tsx"]]),
        "java_files": len([f for f in files if f.suffix == ".java"]),
    }


@app.post("/projects/{project_id}/analyze")
def analyze_project(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"
    project = db.get(Project, project_id)

    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found.")

    restore_uploaded_project(project, project_dir, extracted_dir)

    if not extracted_dir.exists():
        raise HTTPException(status_code=404, detail="Extracted project folder not found.")

    update_project_status(db, project_id, current_user.id, "running", 5)
    project_name = project.name or project_id
    zip_files = list(project_dir.glob("*.zip"))

    if zip_files:
        project_name = zip_files[0].stem

    orchestrator = AgentOrchestrator()
    report = orchestrator.analyze(
        project_dir=extracted_dir,
        project_id=project_id,
        project_name=project_name,
    )

    metadata = save_analysis_report(report, user_id=current_user.id, db=db)

    return {
        "success": True,
        "message": "Multi-agent analysis completed.",
        "report": report.model_dump(mode="json"),
        "metadata": metadata,
    }


@app.post("/projects/github")
def analyze_github_repository(
    request: GitHubAnalyzeRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    url = request.url.strip()

    if not url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub HTTPS repositories are supported.")

    project_id = str(uuid.uuid4())
    project_name = url.rstrip("/").split("/")[-1]

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
            status="running",
            progress=0,
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
        "status": "running",
    }


@app.get("/analysis/{project_id}/progress")
def analysis_progress(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    progress = get_progress(project_id)

    if progress is None:
        return {
            "project_id": project.id,
            "project_name": project.name,
            "status": project.status,
            "progress": project.progress,
            "current_agent": project.status.title(),
            "started_at": project.created_at.isoformat() if project.created_at else None,
            "finished_at": project.completed_at.isoformat() if project.completed_at else None,
            "elapsed_seconds": 0,
            "eta_seconds": None,
            "completed_agents": 0,
            "total_agents": 0,
            "agents": [],
            "error": project.error,
        }

    return progress


@app.get("/projects")
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


@app.get("/reports")
def get_reports(
    search: str | None = None,
    status_filter: str | None = None,
    sort: str = "newest",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = list_reports(user_id=current_user.id, db=db)
    if search:
        needle = search.lower()
        reports = [report for report in reports if needle in str(report.get("project_name", "")).lower()]
    if status_filter:
        reports = [report for report in reports if report.get("status") == status_filter]
    reverse = sort != "oldest"
    reports = sorted(reports, key=lambda item: item.get("created_at") or "", reverse=reverse)
    return {
        "success": True,
        "reports": reports,
    }


@app.get("/reports/{project_id}")
def get_report(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = load_report(project_id, user_id=current_user.id, db=db)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    return {
        "success": True,
        "report": report,
    }


@app.get("/reports/{project_id}/json")
def download_report_json(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_report_record(project_id, current_user.id, db)
    if record:
        return Response(
            content=record.report_json,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=testpilot-report-{project_id}.json"},
        )

    path = get_report_json_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="JSON report not found.")

    return FileResponse(
        path,
        media_type="application/json",
        filename=f"testpilot-report-{project_id}.json",
    )


@app.get("/reports/{project_id}/pdf")
def download_report_pdf(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_report_record(project_id, current_user.id, db)
    if record and record.pdf_blob:
        return Response(
            content=record.pdf_blob,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=testpilot-report-{project_id}.pdf"},
        )

    path = get_report_pdf_path(project_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF report not found.")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"testpilot-report-{project_id}.pdf",
    )


@app.get("/reports/{project_id}/csv")
def download_report_csv(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    report = load_report(project_id, user_id=current_user.id, db=db)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    output = StringIO()
    writer = csv.writer(output)

    writer.writerow(["Metric", "Value"])
    writer.writerow(["Project", report.get("project_name")])
    writer.writerow(["Overall", report.get("overall_score")])
    writer.writerow(["Quality", report.get("quality_score")])
    writer.writerow(["Security", report.get("security_score")])
    writer.writerow(["Testing", report.get("test_score")])
    writer.writerow(["Security Findings", len(report.get("security_findings", []))])
    writer.writerow(["Generated Tests", len(report.get("generated_tests", []))])
    writer.writerow(["Recommendations", len(report.get("recommendations", []))])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=testpilot-{project_id}.csv"},
    )


@app.get("/reports/{project_id}/markdown")
def download_report_markdown(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = get_report_record(project_id, current_user.id, db)
    if record and record.markdown_text:
        return PlainTextResponse(
            record.markdown_text,
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=testpilot-{project_id}.md"},
        )

    report = load_report(project_id, user_id=current_user.id, db=db)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    md = build_markdown_report(report)

    return PlainTextResponse(
        md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=testpilot-{project_id}.md"},
    )


@app.get("/reports/compare/{first_id}/{second_id}")
def compare_reports(
    first_id: str,
    second_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    first = load_report(first_id, user_id=current_user.id, db=db)
    second = load_report(second_id, user_id=current_user.id, db=db)

    if not first or not second:
        raise HTTPException(status_code=404, detail="One or both reports not found.")

    def diff(key):
        return round(float(second.get(key, 0)) - float(first.get(key, 0)), 2)

    return {
        "success": True,
        "comparison": {
            "first": first,
            "second": second,
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


@app.get("/dashboard/summary")
def dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = list_reports(user_id=current_user.id, db=db)

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
            "coverage_percent": report.get("coverage", {}).get("coverage_percent", 0),
            "created_at": report.get("metadata", {}).get("created_at"),
        }
        for report in reports[:20]
    ]

    frameworks = {}
    risk_levels = {}
    for report in reports:
        intelligence = report.get("metadata", {}).get("project_intelligence", {})
        for framework in intelligence.get("frameworks", []):
            frameworks[framework] = frameworks.get(framework, 0) + 1
        risk = report.get("metadata", {}).get("ai_insights", {}).get("risk_level", "Unknown")
        risk_levels[risk] = risk_levels.get(risk, 0) + 1

    return {
        "success": True,
        "summary": {
            "total_reports": len(reports),
            "avg_overall": avg("overall_score"),
            "avg_quality": avg("quality_score"),
            "avg_security": avg("security_score"),
            "avg_testing": avg("test_score"),
            "latest_reports": reports[:5],
            "trend": trend,
            "framework_distribution": frameworks,
            "risk_distribution": risk_levels,
        },
    }


@app.delete("/reports/{project_id}")
def delete_report(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if delete_report_record(project_id, current_user.id, db):
        return {
            "success": True,
            "message": "Report deleted successfully.",
            "project_id": project_id,
        }

    report_dir = REPORTS_DIR / project_id

    if not report_dir.exists():
        raise HTTPException(status_code=404, detail="Report not found.")

    shutil.rmtree(report_dir)

    return {
        "success": True,
        "message": "Report deleted successfully.",
        "project_id": project_id,
    }


@app.delete("/reports")
def clear_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reports = db.query(Project).filter(Project.user_id == current_user.id).all()
    for project in reports:
        db.delete(project)
    db.commit()

    return {
        "success": True,
        "message": "All reports cleared successfully.",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
