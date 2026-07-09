from __future__ import annotations

import os
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

    def analyze(self, project_dir: Path, project_id: str, project_name: str) -> AnalysisReport:
        logs: list[AgentLog] = []
        start_analysis(project_id, project_name)

        def run_agent(agent_name, fn):
            print(f"[AGENT START] {agent_name}", flush=True)
            update_agent(project_id, agent_name, "running", "Running")

            log = AgentLog(
                name=agent_name,
                status=AgentStatus.running,
                message="Running",
                started_at=self._now(),
            )
            logs.append(log)

            try:
                data = fn()
                print(f"[AGENT DONE] {agent_name}", flush=True)
                log.status = AgentStatus.completed
                log.message = "Completed successfully"
                update_agent(project_id, agent_name, "completed", "Completed successfully")
                return data
            except Exception as exc:
                print(f"[AGENT FAILED] {agent_name}: {exc}", flush=True)
                log.status = AgentStatus.failed
                log.message = str(exc)
                update_agent(project_id, agent_name, "failed", str(exc))
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
                    "quality_summary": self._quality_summary(quality_metrics),
                    "quality_analysis_metadata": quality_analysis_metadata,
                    "coverage_summary": coverage.model_dump(mode="json"),
                    "generated_tests_summary": self._generated_tests_summary(generated_tests, test_generation_metadata),
                    "test_generation_metadata": test_generation_metadata,
                    "trend_snapshot": {
                        "overall_score": overall_score,
                        "quality_score": quality_score,
                        "security_score": security_score,
                        "test_score": test_score,
                        "coverage_percent": coverage.coverage_percent,
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

                report.agent_logs = logs
                final_report = self.report_agent.run(report)

                finish_analysis(project_id)
                return final_report

            except Exception as exc:
                report_log.status = AgentStatus.failed
                report_log.message = str(exc)
                report_log.finished_at = self._now()
                update_agent(project_id, self.report_agent.name, "failed", str(exc))
                fail_analysis(project_id, str(exc))
                raise

        except Exception as exc:
            fail_analysis(project_id, str(exc))
            raise

    def _quality_score(self, metrics) -> float:
        if not metrics:
            return 75.0

        maintainability_average = sum(m.maintainability_index for m in metrics) / len(metrics)
        complexity_average = sum(m.complexity for m in metrics) / len(metrics)
        issue_count = sum(len(m.issues) for m in metrics)

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

    def _test_score(self, generated_tests, coverage: float, generation_metadata: dict | None = None) -> float:
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
        coverage_score = min(60, coverage * 0.6)

        if coverage == 0 and executable_count:
            coverage_score = 20

        return round(min(100, generation_score + coverage_score), 2)

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

    def _quality_summary(self, metrics) -> dict:
        smells = {}
        recommendations = []
        hotspots = []

        for metric in metrics:
            for smell in getattr(metric, "smells", [])[:10]:
                key = smell.split(":")[0]
                smells[key] = smells.get(key, 0) + 1
            for rec in getattr(metric, "recommendations", []):
                if rec not in recommendations:
                    recommendations.append(rec)
            issue_count = len(getattr(metric, "issues", []))
            if issue_count:
                hotspots.append({
                    "file": metric.file,
                    "issues": issue_count,
                    "maintainability": metric.maintainability_index,
                    "complexity": metric.complexity,
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

        return {
            "smells": smells,
            "recommendations": recommendations[:8],
            "hotspots": sorted(
                hotspots,
                key=lambda item: (
                    context_rank(next((m.context for m in metrics if m.file == item["file"]), "production")),
                    -item["issues"],
                ),
            )[:10],
        }

    def _generated_tests_summary(self, tests, generation_metadata: dict | None = None) -> dict:
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

        return {
            "total": len(tests),
            "by_type": by_type,
            "by_framework": by_framework,
            "by_category": by_category,
            "by_assertion_strength": by_assertion_strength,
            "by_execution_safety": by_execution_safety,
            "executable_tests": metadata.get("executable_tests", len(tests)),
            "smoke_tests": metadata.get("smoke_tests", 0),
            "needs_review_tests": metadata.get("needs_review_tests", 0),
            "needs_human_test_design": len(metadata.get("needs_human_test_design", [])),
            "skipped_generation_reasons": metadata.get("skipped_generation_reasons", {}),
            "executable_candidates": metadata.get("executable_tests", len(tests)),
        }

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
