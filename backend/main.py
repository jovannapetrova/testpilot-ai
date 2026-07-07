from pathlib import Path
import logging
import os
import shutil
import uuid
import zipfile
import csv
from io import StringIO

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response
from git import Repo

from agents.orchestrator import AgentOrchestrator
from services.analysis_progress import get_progress, start_analysis, fail_analysis
from services.report_storage import (
    REPORTS_DIR,
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


def run_github_analysis_background(project_id: str, url: str):
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"
    project_name = url.rstrip("/").split("/")[-1]

    try:
        Repo.clone_from(url, extracted_dir, depth=1)

        orchestrator = AgentOrchestrator()
        report = orchestrator.analyze(
            project_dir=extracted_dir,
            project_id=project_id,
            project_name=project_name,
        )

        save_analysis_report(report)

    except Exception as exc:
        logger.exception("GitHub analysis failed for project %s", project_id)
        fail_analysis(project_id, str(exc))


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


@app.post("/projects/upload")
async def upload_project(file: UploadFile = File(...)):
    if not file.filename.endswith(".zip"):
        return {"success": False, "message": "Only ZIP files are supported."}

    project_id = str(uuid.uuid4())
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"

    project_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    saved_file = project_dir / file.filename

    with saved_file.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        with zipfile.ZipFile(saved_file, "r") as zip_ref:
            zip_ref.extractall(extracted_dir)
    except zipfile.BadZipFile:
        return {"success": False, "message": "Invalid ZIP archive."}

    files = [p for p in extracted_dir.rglob("*") if p.is_file()]
    language = detect_language(files)

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
def analyze_project(project_id: str):
    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project not found.")

    if not extracted_dir.exists():
        raise HTTPException(status_code=404, detail="Extracted project folder not found.")

    project_name = project_id
    zip_files = list(project_dir.glob("*.zip"))

    if zip_files:
        project_name = zip_files[0].stem

    orchestrator = AgentOrchestrator()
    report = orchestrator.analyze(
        project_dir=extracted_dir,
        project_id=project_id,
        project_name=project_name,
    )

    metadata = save_analysis_report(report)

    return {
        "success": True,
        "message": "Multi-agent analysis completed.",
        "report": report.model_dump(mode="json"),
        "metadata": metadata,
    }


@app.post("/projects/github")
def analyze_github_repository(request: dict, background_tasks: BackgroundTasks):
    url = request.get("url", "").strip()

    if not url.startswith("https://github.com/"):
        raise HTTPException(status_code=400, detail="Only GitHub HTTPS repositories are supported.")

    project_id = str(uuid.uuid4())
    project_name = url.rstrip("/").split("/")[-1]

    project_dir = UPLOAD_DIR / project_id
    extracted_dir = project_dir / "extracted"

    project_dir.mkdir(parents=True, exist_ok=True)
    extracted_dir.mkdir(parents=True, exist_ok=True)

    start_analysis(project_id, project_name)

    background_tasks.add_task(
        run_github_analysis_background,
        project_id,
        url,
    )

    return {
        "success": True,
        "message": "GitHub analysis started.",
        "project_id": project_id,
        "project_name": project_name,
        "status": "running",
    }


@app.get("/analysis/{project_id}/progress")
def analysis_progress(project_id: str):
    progress = get_progress(project_id)

    if progress is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")

    return progress


@app.get("/reports")
def get_reports():
    return {
        "success": True,
        "reports": list_reports(),
    }


@app.get("/reports/{project_id}")
def get_report(project_id: str):
    report = load_report(project_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    return {
        "success": True,
        "report": report,
    }


@app.get("/reports/{project_id}/json")
def download_report_json(project_id: str):
    path = get_report_json_path(project_id)

    if not path.exists():
        raise HTTPException(status_code=404, detail="JSON report not found.")

    return FileResponse(
        path,
        media_type="application/json",
        filename=f"testpilot-report-{project_id}.json",
    )


@app.get("/reports/{project_id}/pdf")
def download_report_pdf(project_id: str):
    path = get_report_pdf_path(project_id)

    if not path.exists():
        raise HTTPException(status_code=404, detail="PDF report not found.")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"testpilot-report-{project_id}.pdf",
    )


@app.get("/reports/{project_id}/csv")
def download_report_csv(project_id: str):
    report = load_report(project_id)

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
def download_report_markdown(project_id: str):
    report = load_report(project_id)

    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")

    insights = report.get("metadata", {}).get("ai_insights", {})
    intelligence = report.get("metadata", {}).get("project_intelligence", {})

    md = f"""# TestPilot AI Report

## Project
**Name:** {report.get("project_name")}  
**Status:** {report.get("status")}  

## Scores
| Metric | Score |
|---|---:|
| Overall | {report.get("overall_score")} |
| Quality | {report.get("quality_score")} |
| Security | {report.get("security_score")} |
| Testing | {report.get("test_score")} |

## AI Insights
{insights.get("summary", "No AI insights available.")}

## Project Intelligence
- Project type: {intelligence.get("project_type")}
- Language: {intelligence.get("primary_language")}
- Frameworks: {", ".join(intelligence.get("frameworks", [])) or "None"}
- Dependencies: {intelligence.get("dependency_count")}

## Findings
- Security findings: {len(report.get("security_findings", []))}
- Generated tests: {len(report.get("generated_tests", []))}
- Recommendations: {len(report.get("recommendations", []))}

## Recommendations
"""

    for rec in report.get("recommendations", []):
        md += f"- **{rec.get('title')}**: {rec.get('description')}\n"

    return PlainTextResponse(
        md,
        media_type="text/markdown",
        headers={"Content-Disposition": f"attachment; filename=testpilot-{project_id}.md"},
    )


@app.get("/reports/compare/{first_id}/{second_id}")
def compare_reports(first_id: str, second_id: str):
    first = load_report(first_id)
    second = load_report(second_id)

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
def dashboard_summary():
    reports = list_reports()

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
def delete_report(project_id: str):
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
def clear_reports():
    if REPORTS_DIR.exists():
        for item in REPORTS_DIR.iterdir():
            if item.is_dir():
                shutil.rmtree(item)

    return {
        "success": True,
        "message": "All reports cleared successfully.",
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
