from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from models.schemas import AnalysisReport
from utils.file_utils import REPORT_DIR


class ReportAgent:
    name = "Report Agent"

    def run(self, report: AnalysisReport) -> AnalysisReport:
        json_path = REPORT_DIR / f"{report.project_id}_report.json"
        pdf_path = REPORT_DIR / f"{report.project_id}_report.pdf"

        json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        self._write_pdf(report, pdf_path)

        report.report_json_url = f"/api/reports/{json_path.name}"
        report.report_pdf_url = f"/api/reports/{pdf_path.name}"

        return report

    def _write_pdf(self, report: AnalysisReport, path: Path) -> None:
        doc = SimpleDocTemplate(str(path), pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("TestPilot AI", styles["Title"]))
        story.append(Paragraph("Enterprise Software Quality Assessment", styles["Heading2"]))
        story.append(Spacer(1, 12))

        insights = report.metadata.get("ai_insights", {})
        security_summary = report.metadata.get("security_summary", {})
        quality_summary = report.metadata.get("quality_summary", {})
        quality_analysis_metadata = report.metadata.get("quality_analysis_metadata", {})
        test_summary = report.metadata.get("generated_tests_summary", {})
        coverage_summary = report.metadata.get("coverage_summary", {})

        story.append(self._table([
            ["Project", report.project_name],
            ["Project ID", report.project_id],
            ["Status", report.status],
            ["Risk Level", insights.get("risk_level", "Unknown")],
        ]))

        story.append(Spacer(1, 16))
        story.append(Paragraph("Executive Summary", styles["Heading2"]))
        story.append(Paragraph(insights.get("summary", "No executive insight was generated."), styles["BodyText"]))
        story.append(Spacer(1, 8))
        story.append(self._table([
            ["Metric", "Score"],
            ["Overall Score", report.overall_score],
            ["Quality Score", report.quality_score],
            ["Security Score", report.security_score],
            ["Testing Score", report.test_score],
        ], header=True))

        story.append(Spacer(1, 16))
        story.append(Paragraph("Risk Matrix", styles["Heading2"]))
        severity = security_summary.get("by_severity", {})
        story.append(self._table([
            ["Risk Area", "Signal", "Impact"],
            ["Security", f"{security_summary.get('total_grouped_findings', len(report.security_findings))} grouped findings", "Potential exploitability, compliance, and data exposure risk."],
            ["Quality", f"{len(quality_summary.get('hotspots', []))} hotspot files", "Higher defect rate and slower delivery."],
            ["Coverage", f"{coverage_summary.get('coverage_percent', report.coverage.coverage_percent)}% coverage", "Regression risk if low or estimated."],
            ["Critical/High Findings", f"{severity.get('critical', 0)} critical / {severity.get('high', 0)} high", "Prioritize before release."],
        ], header=True))

        story.append(Spacer(1, 16))
        story.append(Paragraph("Quality Summary", styles["Heading2"]))
        story.append(self._table([
            ["Metric", "Value"],
            ["Analyzed files", report.code_analysis.total_files],
            ["Total lines", report.code_analysis.total_lines],
            ["Functions", report.code_analysis.total_functions],
            ["Classes", report.code_analysis.total_classes],
            ["Quality metrics", len(report.quality_metrics)],
            ["Top quality smells", ", ".join(list(quality_summary.get("smells", {}).keys())[:5]) or "None"],
            ["Partial analysis", quality_analysis_metadata.get("partial_analysis", False)],
            ["Quality warnings", "; ".join(quality_analysis_metadata.get("warnings", [])[:2])],
        ], header=True))

        story.append(Spacer(1, 16))
        story.append(Paragraph("Security Summary", styles["Heading2"]))
        story.append(self._table([
            ["Severity", "Count"],
            ["Critical", severity.get("critical", 0)],
            ["High", severity.get("high", 0)],
            ["Medium", severity.get("medium", 0)],
            ["Low", severity.get("low", 0)],
            ["Info", severity.get("info", 0)],
        ], header=True))

        story.append(Spacer(1, 16))
        story.append(Paragraph("Coverage Summary", styles["Heading2"]))
        story.append(self._table([
            ["Metric", "Value"],
            ["Coverage", coverage_summary.get("coverage_percent", report.coverage.coverage_percent)],
            ["Tool", coverage_summary.get("tool", report.coverage.tool)],
            ["Estimated", coverage_summary.get("estimated", report.coverage.estimated)],
            ["Reason", coverage_summary.get("reason", report.coverage.reason) or "Coverage execution completed."],
        ], header=True))

        story.append(Spacer(1, 16))
        story.append(Paragraph("Generated Tests Summary", styles["Heading2"]))
        story.append(self._table([
            ["Metric", "Value"],
            ["Generated tests", test_summary.get("total", len(report.generated_tests))],
            ["Executable tests", test_summary.get("executable_tests", len(report.generated_tests))],
            ["Smoke tests", test_summary.get("smoke_tests", 0)],
            ["Needs human test design", test_summary.get("needs_human_test_design", 0)],
            ["Types", ", ".join(f"{k}: {v}" for k, v in test_summary.get("by_type", {}).items())],
            ["Categories", ", ".join(f"{k}: {v}" for k, v in test_summary.get("by_category", {}).items())],
            ["Assertion strength", ", ".join(f"{k}: {v}" for k, v in test_summary.get("by_assertion_strength", {}).items())],
            ["Execution safety", ", ".join(f"{k}: {v}" for k, v in test_summary.get("by_execution_safety", {}).items())],
        ], header=True))

        story.append(Spacer(1, 16))
        story.append(Paragraph("AI Recommendations", styles["Heading2"]))
        recommendation_rows = [["Priority", "Recommendation", "Effort", "Suggested Action"]]

        for rec in report.recommendations[:8]:
            recommendation_rows.append([
                rec.priority,
                rec.title,
                rec.estimated_effort,
                rec.suggested_action,
            ])

        story.append(self._table(recommendation_rows, header=True))

        story.append(PageBreak())
        story.append(Paragraph("Technical Appendix", styles["Heading2"]))
        appendix_rows = [["Area", "Detail"]]
        appendix_rows.append(["Project intelligence", report.metadata.get("project_intelligence", {}).get("summary", "")])
        appendix_rows.append(["Dependency risk", report.metadata.get("dependency_profile", {}).get("risk_level", "Unknown")])
        appendix_rows.append(["Security remediation", "; ".join(security_summary.get("top_remediation", [])[:4])])
        appendix_rows.append(["Coverage notes", "; ".join(report.coverage.low_coverage_reasons[:4])])
        story.append(self._table(appendix_rows, header=True))

        story.append(Spacer(1, 16))
        story.append(Paragraph("Agent Execution Log", styles["Heading2"]))

        agent_rows = [["Agent", "Status", "Message"]]
        for log in report.agent_logs:
            agent_rows.append([
                log.name,
                str(log.status).split(".")[-1],
                log.message,
            ])

        story.append(self._table(agent_rows, header=True))

        doc.build(story)

    def _table(self, data, header=False):
        table = Table(data, repeatRows=1 if header else 0)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("PADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return table
