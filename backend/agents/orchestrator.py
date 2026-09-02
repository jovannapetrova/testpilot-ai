from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from pathlib import Path

from models.schemas import AnalysisReport, AgentLog, AgentStatus
from agents.project_detector import ProjectDetectorAgent
from agents.dependency_analyzer import DependencyAnalyzerAgent
from agents.code_analyzer import CodeAnalyzerAgent
from agents.security_agent import SecurityAgent
from agents.quality_agent import QualityAgent
from agents.test_generator import TestGeneratorAgent
from agents.coverage_agent import CoverageAgent
from agents.recommendation_agent import RecommendationAgent
from agents.report_agent import ReportAgent
from services.insights_engine import build_ai_insights
from services.project_intelligence import build_project_intelligence
from services.analysis_progress import (
    start_analysis,
    update_agent,
    finish_analysis,
    fail_analysis,
)

logger = logging.getLogger("testpilot.agents")


class AgentOrchestrator:
    def __init__(self):
        self.project_detector = ProjectDetectorAgent()
        self.dependency_analyzer = DependencyAnalyzerAgent()
        self.code_analyzer = CodeAnalyzerAgent()
        self.security_agent = SecurityAgent()
        self.quality_agent = QualityAgent()
        self.test_generator = TestGeneratorAgent()
        self.coverage_agent = CoverageAgent()
        self.recommendation_agent = RecommendationAgent()
        self.report_agent = ReportAgent()

    def analyze(self, project_dir: Path, project_id: str, project_name: str, on_progress=None) -> AnalysisReport:
        logs: list[AgentLog] = []
        start_analysis(project_id, project_name)

        def run_agent(agent_name, fn):
            logger.info("Agent started: %s for project %s", agent_name, project_id)
            update_agent(project_id, agent_name, "running", "Running")
            if on_progress:
                on_progress(agent_name, "running", "Running")

            log = AgentLog(
                name=agent_name,
                status=AgentStatus.running,
                message="Running",
                started_at=self._now(),
            )
            logs.append(log)

            try:
                data = fn()
                logger.info("Agent completed: %s for project %s", agent_name, project_id)
                log.status = AgentStatus.completed
                log.message = "Completed successfully"
                update_agent(project_id, agent_name, "completed", "Completed successfully")
                if on_progress:
                    on_progress(agent_name, "completed", "Completed successfully")
                return data
            except Exception as exc:
                logger.exception("Agent failed: %s for project %s", agent_name, project_id)
                log.status = AgentStatus.failed
                log.message = str(exc)
                update_agent(project_id, agent_name, "failed", str(exc))
                if on_progress:
                    on_progress(agent_name, "failed", str(exc))
                fail_analysis(project_id, str(exc))
                raise
            finally:
                log.finished_at = self._now()

        try:
            project_profile = run_agent(
                self.project_detector.name,
                lambda: self.project_detector.run(project_dir),
            )

            dependency_profile = run_agent(
                self.dependency_analyzer.name,
                lambda: self.dependency_analyzer.run(project_dir),
            )

            project_intelligence = build_project_intelligence(
                project_profile,
                dependency_profile,
            )

            code_analysis = run_agent(
                self.code_analyzer.name,
                lambda: self.code_analyzer.run(project_dir),
            )

            security_findings = run_agent(
                self.security_agent.name,
                lambda: self.security_agent.run(project_dir),
            )

            quality_metrics = run_agent(
                self.quality_agent.name,
                lambda: self.quality_agent.run(project_dir),
            )
            quality_analysis_metadata = getattr(
                self.quality_agent,
                "last_analysis_metadata",
                {},
            )

            generated_tests = run_agent(
                self.test_generator.name,
                lambda: self.test_generator.run(project_dir, code_analysis),
            )
            test_generation_metadata = getattr(
                self.test_generator,
                "last_generation_metadata",
                {},
            )

            execute_tests = os.getenv("ENABLE_TEST_EXECUTION", "true").lower() == "true"

            coverage = run_agent(
                self.coverage_agent.name,
                lambda: self.coverage_agent.run(project_dir, execute=execute_tests),
            )

            avg_complexity = 0
            if quality_metrics:
                avg_complexity = sum(m.complexity for m in quality_metrics) / len(quality_metrics)

            recommendations = run_agent(
                self.recommendation_agent.name,
                lambda: self.recommendation_agent.run(
                    len(security_findings),
                    coverage.coverage_percent,
                    avg_complexity,
                    security_findings=security_findings,
                    quality_metrics=quality_metrics,
                    coverage_result=coverage,
                    generation_metadata=test_generation_metadata,
                ),
            )

            quality_score = self._quality_score(quality_metrics)
            security_score = self._security_score(security_findings)
            test_score = self._test_score(
                generated_tests,
                coverage.coverage_percent,
                test_generation_metadata,
                coverage_result=coverage,
            )

            overall_score = round(
                (quality_score * 0.35)
                + (security_score * 0.35)
                + (test_score * 0.30),
                2,
            )

            preliminary_report_data = {
                "overall_score": overall_score,
                "quality_score": quality_score,
                "security_score": security_score,
                "test_score": test_score,
                "security_findings": [f.model_dump(mode="json") for f in security_findings],
                "quality_metrics": [m.model_dump(mode="json") for m in quality_metrics],
                "generated_tests": [t.model_dump(mode="json") for t in generated_tests],
                "coverage": coverage.model_dump(mode="json"),
            }

            ai_insights = build_ai_insights(preliminary_report_data)

            report = AnalysisReport(
                project_id=project_id,
                project_name=project_name,
                status="completed",
                quality_score=quality_score,
                security_score=security_score,
                test_score=test_score,
                overall_score=overall_score,
                code_analysis=code_analysis,
                security_findings=security_findings,
                quality_metrics=quality_metrics,
                generated_tests=generated_tests,
                coverage=coverage,
                recommendations=recommendations,
                agent_logs=logs,
                metadata={
                    "created_at": self._now(),
                    "analysis_type": "multi-agent",
                    "security_scoring": "context-aware-production-weighted",
                    "security_context_summary": self._security_context_summary(security_findings),
                    "security_summary": self._security_summary(security_findings),
                    "quality_summary": self._quality_summary(quality_metrics, security_findings),
                    "quality_analysis_metadata": quality_analysis_metadata,
                    "coverage_summary": coverage.model_dump(mode="json"),
                    "generated_tests_summary": self._generated_tests_summary(
                        generated_tests,
                        test_generation_metadata,
                        coverage,
                        execute_tests,
                    ),
                    "test_generation_metadata": test_generation_metadata,
                    "testing_scoring": self._testing_scoring_summary(
                        generated_tests,
                        test_generation_metadata,
                        coverage,
                    ),
                    "assessment_confidence": self._assessment_confidence(
                        coverage,
                        quality_analysis_metadata,
                        test_generation_metadata,
                    ),
                    "trend_snapshot": {
                        "overall_score": overall_score,
                        "quality_score": quality_score,
                        "security_score": security_score,
                        "test_score": test_score,
                        "coverage_percent": coverage.coverage_percent,
                        "coverage_display_label": coverage.display_label,
                        "coverage_measured": coverage.measured,
                    },
                    "quality_scoring": "multi-language-maintainability-complexity",
                    "test_generation_architecture": "strategy-factory",
                    "project_profile": project_profile,
                    "dependency_profile": dependency_profile,
                    "project_intelligence": project_intelligence,
                    "ai_insights": ai_insights,
                },
            )

            report_log = AgentLog(
                name=self.report_agent.name,
                status=AgentStatus.running,
                message="Running",
                started_at=self._now(),
            )
            logs.append(report_log)
            update_agent(project_id, self.report_agent.name, "running", "Running")
            if on_progress:
                on_progress(self.report_agent.name, "running", "Running")

            try:
                report_log.status = AgentStatus.completed
                report_log.message = "Completed successfully"
                report_log.finished_at = self._now()

                update_agent(
                    project_id,
                    self.report_agent.name,
                    "completed",
                    "Completed successfully",
                )
                if on_progress:
                    on_progress(self.report_agent.name, "completed", "Completed successfully")

                report.agent_logs = logs
                final_report = self.report_agent.run(report)

                finish_analysis(project_id)
                return final_report

            except Exception as exc:
                report_log.status = AgentStatus.failed
                report_log.message = str(exc)
                report_log.finished_at = self._now()
                update_agent(project_id, self.report_agent.name, "failed", str(exc))
                if on_progress:
                    on_progress(self.report_agent.name, "failed", str(exc))
                fail_analysis(project_id, str(exc))
                raise

        except Exception as exc:
            fail_analysis(project_id, str(exc))
            raise

    def _quality_score(self, metrics) -> float:
        if not metrics:
            return 75.0

        weighted = [(metric, self._context_weight(getattr(metric, "context", "production"))) for metric in metrics]
        total_weight = sum(weight for _, weight in weighted) or 1
        maintainability_average = sum(m.maintainability_index * weight for m, weight in weighted) / total_weight
        complexity_average = sum(m.complexity * weight for m, weight in weighted) / total_weight
        issue_count = sum(len(m.issues) * weight for m, weight in weighted)

        score = (
            max(0, min(100, maintainability_average)) * 0.55
            + max(0, 100 - max(0, complexity_average - 5) * 4) * 0.30
            + max(0, 100 - issue_count * 2) * 0.15
        )

        return round(max(5, min(100, score)), 2)

    def _security_score(self, findings) -> float:
        if not findings:
            return 100.0

        def normalize_severity(value) -> str:
            raw = getattr(value, "value", value)
            text = str(raw).lower()
            return text.split(".")[-1] if "." in text else text

        def normalize_file(value) -> str:
            return str(value or "").replace("\\", "/").lower()

        weights = {
            "critical": 16,
            "high": 6,
            "medium": 2.5,
            "low": 0.08,
            "info": 0.02,
        }

        grouped = {}

        for finding in findings:
            severity = normalize_severity(getattr(finding, "severity", "medium"))
            file_path = normalize_file(getattr(finding, "file", ""))
            issue = str(getattr(finding, "issue", ""))
            category = str(getattr(finding, "category", "") or "").lower()
            confidence = str(getattr(finding, "confidence", "") or "").lower()

            key = (issue, severity, file_path, category, confidence)
            grouped[key] = grouped.get(key, 0) + 1

        penalty = 0.0

        for (issue, severity, file_path, category, confidence), count in grouped.items():
            base_weight = weights.get(severity, 1.5)
            issue_lower = issue.lower()

            is_test = any(x in file_path for x in ["tests/", "/tests/", "test_", "_test.", ".test."])
            is_docs = any(x in file_path for x in ["docs/", "docs_src/", ".md", ".rst", ".txt"])
            is_example = any(x in file_path for x in ["examples/", "example/", "demo/", "sample/", "tutorial/"])
            is_ci = any(x in file_path for x in [".github/", "workflows/", ".gitlab-ci"])
            is_container = any(x in file_path for x in ["docker-compose", "dockerfile", "k8s/", "kubernetes/", "helm/"])

            if category in {
                "placeholder_secret",
                "secret_reference",
                "auth_parameter",
                "test_fixture_secret",
                "ci_secret_reference",
                "runtime_secret_reference",
            }:
                base_weight *= 0.04

            elif category == "real_secret_candidate":
                if is_test or is_docs or is_example or is_ci:
                    base_weight *= 0.15
                elif is_container:
                    base_weight *= 0.45
                else:
                    base_weight *= 1.0

            elif "hardcoded secret" in issue_lower:
                base_weight *= 0.12

            elif "request_without_timeout" in issue_lower:
                if is_test or is_docs or is_example:
                    base_weight *= 0.08
                else:
                    base_weight *= 0.60

            elif "assert" in issue_lower:
                if is_test:
                    base_weight *= 0.02
                else:
                    base_weight *= 0.10

            elif is_test or is_docs or is_example or is_ci:
                base_weight *= 0.12

            elif is_container:
                base_weight *= 0.45

            if severity in ["low", "info"]:
                penalty += min(base_weight * count, 1.8)
            else:
                penalty += min(base_weight * count, 10)

        return round(max(0, min(100, 100 - penalty)), 2)

    def _test_score(
        self,
        generated_tests,
        coverage: float,
        generation_metadata: dict | None = None,
        coverage_result=None,
    ) -> float:
        metadata = generation_metadata or {}
        executable_count = int(metadata.get("executable_tests", len(generated_tests)) or 0)
        smoke_count = int(metadata.get("smoke_tests", 0) or 0)
        behavioral_weight = 0
        for test in generated_tests:
            category = getattr(test, "generated_test_category", getattr(test, "test_type", "unit")) or "unit"
            assertion_strength = getattr(test, "assertion_strength", "medium") or "medium"
            if category == "smoke" or getattr(test, "test_type", "") == "smoke":
                behavioral_weight += 1
            elif assertion_strength == "high":
                behavioral_weight += 7
            elif assertion_strength == "medium":
                behavioral_weight += 5
            else:
                behavioral_weight += 3
        generation_score = min(40, behavioral_weight or (executable_count * 5 + smoke_count))
        coverage_measured = self._coverage_measured(coverage_result)
        coverage_score = min(60, coverage * 0.6) if coverage_measured else 0
        readiness_evidence_score = min(10, executable_count * 2) if not coverage_measured else 0

        return round(min(100, generation_score + coverage_score + readiness_evidence_score), 2)

    def _coverage_measured(self, coverage_result) -> bool:
        return bool(
            coverage_result
            and getattr(coverage_result, "measured", False)
            and getattr(coverage_result, "available", False)
        )

    def _testing_scoring_summary(self, generated_tests, generation_metadata: dict | None, coverage_result) -> dict:
        metadata = generation_metadata or {}
        coverage_measured = self._coverage_measured(coverage_result)
        return {
            "generated_candidate_weight": "Only executable, non-placeholder generated candidates contribute readiness points.",
            "coverage_evidence": "measured" if coverage_measured else getattr(coverage_result, "evidence_state", "unavailable"),
            "coverage_score_component": round(min(60, getattr(coverage_result, "coverage_percent", 0) * 0.6), 2) if coverage_measured else 0,
            "missing_coverage_evidence": not coverage_measured,
            "missing_evidence_note": (
                "Coverage was not treated as 0%; the testing score received only a limited readiness contribution from generated candidates."
                if not coverage_measured
                else ""
            ),
            "ready_to_execute": int(metadata.get("executable_tests", len(generated_tests)) or 0),
            "smoke_tests": int(metadata.get("smoke_tests", 0) or 0),
        }

    def _security_context_summary(self, findings) -> dict:
        summary = {
            "production": 0,
            "test": 0,
            "docs": 0,
            "example": 0,
            "config": 0,
            "system": 0,
        }

        for finding in findings:
            context = str(getattr(finding, "context", "production") or "production").lower()
            if context not in summary:
                context = "production"
            summary[context] += 1

        return summary

    def _security_summary(self, findings) -> dict:
        by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        by_category = {}
        remediation = []

        for finding in findings:
            severity = str(getattr(getattr(finding, "severity", ""), "value", getattr(finding, "severity", ""))).lower()
            by_severity[severity] = by_severity.get(severity, 0) + getattr(finding, "occurrences", 1)
            category = getattr(finding, "category", "security") or "security"
            by_category[category] = by_category.get(category, 0) + 1
            if getattr(finding, "remediation", "") and finding.remediation not in remediation:
                remediation.append(finding.remediation)

        return {
            "total_grouped_findings": len(findings),
            "by_severity": by_severity,
            "by_category": by_category,
            "top_remediation": remediation[:5],
        }

    def _quality_summary(self, metrics, security_findings=None) -> dict:
        security_findings = security_findings or []
        smells = {}
        recommendations = []
        hotspots = []
        security_by_file = {}

        for finding in security_findings:
            file_path = getattr(finding, "file", "")
            if not file_path:
                continue
            severity = str(getattr(getattr(finding, "severity", ""), "value", getattr(finding, "severity", ""))).lower()
            security_by_file[file_path] = security_by_file.get(file_path, 0) + {
                "critical": 8,
                "high": 5,
                "medium": 2,
                "low": 0.5,
                "info": 0.1,
            }.get(severity, 1)

        for metric in metrics:
            for smell in getattr(metric, "smells", [])[:10]:
                key = smell.split(":")[0]
                smells[key] = smells.get(key, 0) + 1
            for rec in getattr(metric, "recommendations", []):
                if rec not in recommendations:
                    recommendations.append(rec)
            issue_count = len(getattr(metric, "issues", []))
            if issue_count:
                risk_score = self._quality_metric_risk_score(metric, security_by_file.get(metric.file, 0))
                hotspots.append({
                    "file": metric.file,
                    "context": getattr(metric, "context", "production") or "production",
                    "issues": issue_count,
                    "maintainability": metric.maintainability_index,
                    "complexity": metric.complexity,
                    "risk_score": risk_score,
                })

        def context_rank(context: str) -> int:
            return {
                "production": 0,
                "config": 1,
                "ci": 2,
                "test": 3,
                "example": 4,
                "docs": 5,
            }.get(str(context or "production").lower(), 6)

        sorted_hotspots = sorted(
            hotspots,
            key=lambda item: (
                context_rank(item.get("context")),
                -item["risk_score"],
                -item["issues"],
            ),
        )
        production_hotspots = [
            item for item in sorted_hotspots
            if str(item.get("context", "production")).lower() in {"production", "config", "ci"}
        ]
        test_hotspots = [
            item for item in sorted_hotspots
            if str(item.get("context", "")).lower() == "test"
        ]

        return {
            "smells": smells,
            "recommendations": recommendations[:8],
            "hotspots": sorted_hotspots[:10],
            "highest_production_risk": production_hotspots[0] if production_hotspots else (sorted_hotspots[0] if sorted_hotspots else None),
            "test_suite_hotspot": test_hotspots[0] if test_hotspots else None,
        }

    def _quality_metric_risk_score(self, metric, security_weight: float = 0) -> float:
        context = getattr(metric, "context", "production")
        base = (
            len(getattr(metric, "quality_issues", []) or getattr(metric, "issues", [])) * 2.0
            + max(0, float(getattr(metric, "complexity", 0) or 0) - 4) * 1.5
            + max(0, 70 - float(getattr(metric, "maintainability_index", 70) or 70)) * 0.35
            + int(getattr(metric, "large_classes", 0) or 0) * 5
            + int(getattr(metric, "long_methods", 0) or 0) * 3
            + int(getattr(metric, "duplicate_blocks", 0) or 0) * 3
            + int(getattr(metric, "too_many_parameters", 0) or 0) * 1.5
            + int(getattr(metric, "max_nesting_depth", 0) or 0) * 0.8
            + security_weight
        )
        return round(base * self._context_weight(context), 2)

    def _context_weight(self, context: str) -> float:
        return {
            "production": 1.0,
            "config": 0.75,
            "ci": 0.65,
            "test": 0.35,
            "example": 0.2,
            "docs": 0.15,
            "api_example": 0.15,
            "constants": 0.7,
            "generated/vendor": 0.05,
        }.get(str(context or "production").lower(), 0.8)

    def _assessment_confidence(
        self,
        coverage_result,
        quality_analysis_metadata: dict | None,
        generation_metadata: dict | None,
    ) -> dict:
        quality_analysis_metadata = quality_analysis_metadata or {}
        generation_metadata = generation_metadata or {}
        notes = []
        coverage_measured = self._coverage_measured(coverage_result)
        if not coverage_measured:
            notes.append("Coverage was not measured in this run.")
        if quality_analysis_metadata.get("partial_analysis"):
            notes.append("Quality analysis was capped for performance.")
        if generation_metadata.get("needs_human_test_design"):
            notes.append("Some targets require project-specific fixtures before tests can be generated safely.")

        confidence = "high"
        if notes:
            confidence = "medium"
        if not coverage_measured and quality_analysis_metadata.get("partial_analysis"):
            confidence = "low"

        return {
            "level": confidence,
            "coverage_evidence": "measured" if coverage_measured else getattr(coverage_result, "evidence_state", "unavailable"),
            "quality_scope": "partial" if quality_analysis_metadata.get("partial_analysis") else "complete",
            "generated_test_design_gap_count": len(generation_metadata.get("needs_human_test_design", []) or []),
            "notes": notes,
        }

    def _generated_tests_summary(
        self,
        tests,
        generation_metadata: dict | None = None,
        coverage_result=None,
        execution_enabled: bool = False,
    ) -> dict:
        metadata = generation_metadata or {}
        by_type = {}
        by_framework = {}
        by_category = {}
        by_assertion_strength = {}
        by_execution_safety = {}

        for test in tests:
            by_type[test.test_type] = by_type.get(test.test_type, 0) + 1
            category = getattr(test, "generated_test_category", getattr(test, "test_type", "unit")) or "unit"
            by_category[category] = by_category.get(category, 0) + 1
            framework = test.framework or "generic"
            by_framework[framework] = by_framework.get(framework, 0) + 1
            assertion_strength = getattr(test, "assertion_strength", "medium") or "medium"
            execution_safety = getattr(test, "execution_safety", "safe") or "safe"
            by_assertion_strength[assertion_strength] = by_assertion_strength.get(assertion_strength, 0) + 1
            by_execution_safety[execution_safety] = by_execution_safety.get(execution_safety, 0) + 1

        executed_tests = sum(1 for test in tests if getattr(test, "executed", False))
        passed = sum(int(getattr(test, "passed", 0) or 0) for test in tests if getattr(test, "executed", False))
        failed = sum(int(getattr(test, "failed", 0) or 0) for test in tests if getattr(test, "executed", False))
        execution_status = "disabled" if not execution_enabled else ("executed" if executed_tests else "not_executed")
        not_executed_reason = ""
        if not execution_enabled:
            not_executed_reason = "Generated candidates were not executed because ENABLE_TEST_EXECUTION is disabled."
        elif not executed_tests:
            not_executed_reason = "Generated candidates were produced for review but no execution result was captured."

        return {
            "total": len(tests),
            "generated_candidates": len(tests),
            "by_type": by_type,
            "by_framework": by_framework,
            "by_category": by_category,
            "by_assertion_strength": by_assertion_strength,
            "by_execution_safety": by_execution_safety,
            "executable_tests": metadata.get("executable_tests", len(tests)),
            "ready_to_execute": metadata.get("executable_tests", len(tests)),
            "smoke_tests": metadata.get("smoke_tests", 0),
            "executed_tests": executed_tests,
            "passed": passed if executed_tests else None,
            "failed": failed if executed_tests else None,
            "execution_status": execution_status,
            "execution_enabled": execution_enabled,
            "not_executed_reason": not_executed_reason,
            "needs_review_tests": metadata.get("needs_review_tests", 0),
            "needs_human_test_design": len(metadata.get("needs_human_test_design", [])),
            "skipped_generation_reasons": metadata.get("skipped_generation_reasons", {}),
            "executable_candidates": metadata.get("executable_tests", len(tests)),
            "coverage_execution_state": getattr(coverage_result, "evidence_state", "unavailable") if coverage_result else "unavailable",
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
