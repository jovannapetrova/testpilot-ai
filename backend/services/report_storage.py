from pathlib import Path
import json
from datetime import datetime, timezone
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "storage" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def save_analysis_report(report: Any) -> dict:
    report_data = report.model_dump(mode="json")
    project_id = report_data["project_id"]

    folder = REPORTS_DIR / project_id
    folder.mkdir(parents=True, exist_ok=True)

    json_path = folder / "report.json"
    pdf_path = folder / "report.pdf"
    metadata_path = folder / "metadata.json"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    metadata = {
        "project_id": project_id,
        "project_name": report_data.get("project_name"),
        "language": report_data.get("metadata", {})
        .get("project_profile", {})
        .get("primary_language", "unknown"),
        "status": report_data.get("status"),
        "overall_score": report_data.get("overall_score"),
        "quality_score": report_data.get("quality_score"),
        "security_score": report_data.get("security_score"),
        "test_score": report_data.get("test_score"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "json_path": str(json_path),
        "pdf_path": str(pdf_path),
    }

    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    generate_pdf_report(pdf_path, report_data)

    return metadata


def list_reports() -> list[dict]:
    reports = []

    for metadata_path in REPORTS_DIR.glob("*/metadata.json"):
        try:
            with metadata_path.open("r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except Exception:
            continue

    return sorted(reports, key=lambda x: x.get("created_at", ""), reverse=True)


def load_report(project_id: str) -> dict | None:
    path = REPORTS_DIR / project_id / "report.json"

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_report_json_path(project_id: str) -> Path:
    return REPORTS_DIR / project_id / "report.json"


def get_report_pdf_path(project_id: str) -> Path:
    return REPORTS_DIR / project_id / "report.pdf"


def group_findings(findings: list[dict]) -> list[dict]:
    grouped = {}

    for finding in findings:
        key = (
            finding.get("issue", "Unknown"),
            finding.get("severity", "info"),
            finding.get("file", "Unknown"),
        )

        if key not in grouped:
            grouped[key] = {
                "issue": key[0],
                "severity": key[1],
                "file": key[2],
                "count": 0,
            }

        grouped[key]["count"] += 1

    return sorted(grouped.values(), key=lambda item: item["count"], reverse=True)


def severity_distribution(findings: list[dict]) -> dict:
    result = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "info": 0,
    }

    for finding in findings:
        severity = str(finding.get("severity", "info")).lower()

        if "." in severity:
            severity = severity.split(".")[-1]

        result[severity] = result.get(severity, 0) + 1

    return result


def score_label(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Fair"
    return "Needs Improvement"


def table(data, widths=None):
    t = Table(data, colWidths=widths)

    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("PADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )

    return t


def generate_pdf_report(pdf_path: Path, report: dict) -> None:
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="TitleCustom",
            parent=styles["Title"],
            fontSize=28,
            spaceAfter=16,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontSize=15,
            spaceBefore=18,
            spaceAfter=10,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["BodyText"],
            fontSize=9,
        )
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=1.4 * cm,
        leftMargin=1.4 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
    )

    story = []

    overall = float(report.get("overall_score", 0) or 0)
    quality = float(report.get("quality_score", 0) or 0)
    security = float(report.get("security_score", 0) or 0)
    testing = float(report.get("test_score", 0) or 0)

    metadata = report.get("metadata", {})
    insights = metadata.get("ai_insights", {})

    story.append(Paragraph("TestPilot AI", styles["TitleCustom"]))
    story.append(
        Paragraph(
            "Professional Multi-Agent Software Quality Assessment",
            styles["Heading2"],
        )
    )
    story.append(Spacer(1, 14))

    story.append(
        table(
            [
                ["Project", report.get("project_name")],
                ["Project ID", report.get("project_id")],
                ["Status", report.get("status")],
                ["Generated", datetime.now().strftime("%Y-%m-%d %H:%M")],
                ["Risk Level", score_label(overall)],
            ],
            [4 * cm, 12 * cm],
        )
    )

    story.append(Spacer(1, 18))
    story.append(Paragraph("Executive Summary", styles["SectionTitle"]))

    story.append(
        table(
            [
                ["Metric", "Score", "Assessment"],
                ["Overall Score", overall, score_label(overall)],
                ["Quality Score", quality, score_label(quality)],
                ["Security Score", security, score_label(security)],
                ["Testing Score", testing, score_label(testing)],
            ],
            [6 * cm, 4 * cm, 6 * cm],
        )
    )

    if insights:
        story.append(Paragraph("AI Executive Insights", styles["SectionTitle"]))
        story.append(Paragraph(str(insights.get("summary", "")), styles["BodyText"]))
        story.append(Spacer(1, 8))

        story.append(
            table(
                [
                    ["Insight", "Value"],
                    ["Risk Level", insights.get("risk_level", "")],
                    ["Main Weakness", insights.get("main_weakness", "")],
                    [
                        "Security Findings",
                        insights.get("statistics", {}).get("security_findings", 0),
                    ],
                    [
                        "Generated Tests",
                        insights.get("statistics", {}).get("generated_tests", 0),
                    ],
                ],
                [6 * cm, 10 * cm],
            )
        )

    code = report.get("code_analysis", {})

    story.append(Paragraph("Code Analysis", styles["SectionTitle"]))
    story.append(
        table(
            [
                ["Metric", "Value"],
                ["Analyzed files", code.get("total_files")],
                ["Total lines", code.get("total_lines")],
                ["Functions", code.get("total_functions")],
                ["Classes", code.get("total_classes")],
            ],
            [8 * cm, 8 * cm],
        )
    )

    findings = report.get("security_findings", [])
    grouped = group_findings(findings)
    distribution = severity_distribution(findings)

    story.append(Paragraph("Security Overview", styles["SectionTitle"]))
    story.append(
        table(
            [
                ["Severity", "Count"],
                ["Critical", distribution.get("critical", 0)],
                ["High", distribution.get("high", 0)],
                ["Medium", distribution.get("medium", 0)],
                ["Low-risk", distribution.get("low", 0)],
                ["Info", distribution.get("info", 0)],
                ["Grouped unique issues", len(grouped)],
            ],
            [8 * cm, 8 * cm],
        )
    )

    if grouped:
        story.append(Paragraph("Grouped Security Findings", styles["SectionTitle"]))

        rows = [["Issue", "Severity", "Occurrences", "File"]]

        for item in grouped[:12]:
            rows.append(
                [
                    Paragraph(str(item["issue"]), styles["SmallText"]),
                    item["severity"],
                    item["count"],
                    Paragraph(str(item["file"]), styles["SmallText"]),
                ]
            )

        story.append(table(rows, [4 * cm, 3 * cm, 3 * cm, 6 * cm]))

    metrics = report.get("quality_metrics", [])

    if metrics:
        story.append(PageBreak())
        story.append(Paragraph("Quality Metrics", styles["SectionTitle"]))

        rows = [["File", "Complexity", "Maintainability", "Issues"]]

        for metric in metrics[:15]:
            rows.append(
                [
                    Paragraph(str(metric.get("file", "")), styles["SmallText"]),
                    metric.get("complexity", 0),
                    metric.get("maintainability_index", 0),
                    len(metric.get("issues", [])),
                ]
            )

        story.append(table(rows, [7 * cm, 3 * cm, 4 * cm, 2 * cm]))

    tests = report.get("generated_tests", [])

    if tests:
        story.append(Paragraph("Generated Tests Summary", styles["SectionTitle"]))

        rows = [["Target", "File", "Type"]]

        for test in tests[:12]:
            rows.append(
                [
                    Paragraph(str(test.get("target", "")), styles["SmallText"]),
                    Paragraph(str(test.get("file", "")), styles["SmallText"]),
                    "AI-generated",
                ]
            )

        story.append(table(rows, [5 * cm, 8 * cm, 3 * cm]))

    recs = report.get("recommendations", [])

    if recs:
        story.append(PageBreak())
        story.append(Paragraph("AI Recommendations", styles["SectionTitle"]))

        rows = [["Priority", "Recommendation", "Suggested Action"]]

        for rec in recs[:10]:
            rows.append(
                [
                    str(rec.get("priority", "")),
                    Paragraph(str(rec.get("title", "")), styles["SmallText"]),
                    Paragraph(
                        str(rec.get("suggested_action", rec.get("description", ""))),
                        styles["SmallText"],
                    ),
                ]
            )

        story.append(table(rows, [3 * cm, 5 * cm, 8 * cm]))

    story.append(Spacer(1, 16))
    story.append(Paragraph("Agent Execution Log", styles["SectionTitle"]))

    logs = report.get("agent_logs", [])

    rows = [["Agent", "Status", "Message"]]

    for log in logs:
        status = str(log.get("status", "")).split(".")[-1]

        rows.append(
            [
                Paragraph(str(log.get("name", "")), styles["SmallText"]),
                status,
                Paragraph(str(log.get("message", "")), styles["SmallText"]),
            ]
        )

    if len(rows) == 1:
        rows.append(
            [
                "No logs",
                "-",
                "This report does not contain agent execution logs.",
            ]
        )

    story.append(table(rows, [6 * cm, 3 * cm, 7 * cm]))

    doc.build(story)