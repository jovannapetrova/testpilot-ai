from __future__ import annotations
from models.schemas import Recommendation
from services.llm_service import LLMService

class RecommendationAgent:
    name = "Recommendation Agent"

    def __init__(self):
        self.llm = LLMService()

    def run(
        self,
        security_count: int,
        coverage: float,
        avg_complexity: float,
        security_findings=None,
        quality_metrics=None,
        coverage_result=None,
        generation_metadata=None,
    ) -> list[Recommendation]:
        security_findings = security_findings or []
        quality_metrics = quality_metrics or []
        generation_metadata = generation_metadata or {}
        real_security_count = len([
            finding for finding in security_findings
            if getattr(finding, "category", "") == "real_secret_candidate"
            or str(getattr(finding, "severity", "")).lower().split(".")[-1] in {"high", "critical"}
        ])
        recommendations: list[Recommendation] = []
        if getattr(self.llm, "provider", "mock") != "mock":
            raw = self.llm.generate_recommendations({
                "security_count": real_security_count,
                "coverage": coverage,
                "complexity": avg_complexity,
            })
            recommendations = [Recommendation(**item) for item in raw]
        recommendations.extend(self._deterministic_recommendations(
            security_count,
            coverage,
            avg_complexity,
            security_findings,
            quality_metrics,
            coverage_result,
            generation_metadata,
        ))
        return self._dedupe(recommendations)

    def _deterministic_recommendations(
        self,
        security_count: int,
        coverage: float,
        avg_complexity: float,
        security_findings,
        quality_metrics,
        coverage_result,
        generation_metadata,
    ) -> list[Recommendation]:
        items: list[Recommendation] = []
        real_candidates = [
            finding for finding in security_findings
            if getattr(finding, "category", "") == "real_secret_candidate"
        ]
        reference_findings = [
            finding for finding in security_findings
            if getattr(finding, "category", "") in {
                "placeholder_secret",
                "secret_reference",
                "test_fixture_secret",
                "ci_secret_reference",
                "runtime_secret_reference",
                "auth_parameter",
            }
        ]
        production_hotspots = self._production_quality_hotspots(quality_metrics)
        coverage_measured = bool(
            coverage_result
            and getattr(coverage_result, "measured", False)
            and getattr(coverage_result, "available", False)
        )

        if real_candidates:
            files = self._target_files(real_candidates)
            items.append(Recommendation(
                title="Triage production security findings",
                priority="high",
                category="security",
                description=f"{len(real_candidates)} real secret/security candidate(s) need confirmation in {', '.join(files) or 'production code'}.",
                suggested_action="Validate exploitability, rotate any confirmed live credentials, move values to managed secrets, and add regression tests for the affected paths.",
                estimated_effort="medium",
                business_impact="Reduces breach and compliance risk before release.",
                why="Security findings in production code can become exploitable defects.",
                affected_files=files,
                evidence=f"{len(real_candidates)} real secret/security candidate(s) were grouped by the security agent.",
            ))
        elif reference_findings:
            files = self._target_files(reference_findings)
            title = "Validate CI/config secret references" if any(getattr(f, "category", "") == "ci_secret_reference" for f in reference_findings) else "Review low-confidence secret references"
            items.append(Recommendation(
                title=title,
                priority="low",
                category="security",
                description=f"Secret-like findings are low-confidence references/placeholders in {', '.join(files) or 'non-production/config contexts'}.",
                suggested_action="Confirm references point to managed secrets, keep fixture values fake, and avoid logging resolved secret values.",
                estimated_effort="small",
                business_impact="Reduces audit noise without treating placeholders as active incidents.",
                why="The findings do not look like exposed live credentials, but they should be validated for deployment hygiene.",
                affected_files=files,
                evidence=f"{len(reference_findings)} low-confidence reference or fixture finding(s) were detected.",
            ))

        if not coverage_measured:
            executable = int(generation_metadata.get("executable_tests", 0) or 0)
            smoke = int(generation_metadata.get("smoke_tests", 0) or 0)
            human_design = generation_metadata.get("needs_human_test_design", [])
            human_count = len(human_design) if isinstance(human_design, list) else int(human_design or 0)
            items.append(Recommendation(
                title="Configure measured coverage before using testing score as release evidence",
                priority="medium",
                category="testing",
                description=(
                    f"Coverage is not measured for this run ({getattr(coverage_result, 'evidence_state', 'unavailable') if coverage_result else 'unavailable'}). "
                    f"{executable + smoke} generated candidate(s) are ready for review/execution, and {human_count} target(s) require human fixture design."
                ),
                suggested_action="Enable project test execution and coverage collection in a controlled environment, then treat measured coverage as release evidence.",
                estimated_effort="medium",
                business_impact="Prevents teams from mistaking generated candidates for executed test coverage.",
                why="Missing coverage evidence is not the same as measured 0%, but it still limits release confidence.",
                affected_files=(coverage_result.uncovered_files[:5] if coverage_result else []),
                evidence=getattr(coverage_result, "reason", "") if coverage_result else "Coverage agent did not produce measured coverage.",
            ))
        elif coverage < 60:
            executable = int(generation_metadata.get("executable_tests", 0) or 0)
            human_design = generation_metadata.get("needs_human_test_design", [])
            human_count = len(human_design) if isinstance(human_design, list) else int(human_design or 0)
            files = coverage_result.uncovered_files[:5] if coverage_result else []
            scope = ", ".join(files) if files else "core production paths"
            items.append(Recommendation(
                title=f"Add behavioral tests for {scope}",
                priority="high" if coverage < 30 else "medium",
                category="testing",
                description=(
                    f"Measured coverage is {coverage}%, below an enterprise release-confidence threshold. "
                    f"{executable} generated candidate(s) can be reviewed first; {human_count} target(s) need project-specific fixtures."
                ),
                suggested_action="Prioritize uncovered production files, add boundary and error-path tests, then rerun coverage to verify the gain.",
                estimated_effort="medium",
                business_impact="Improves release confidence and reduces regression cost.",
                why="Low measured coverage means refactoring and security fixes are harder to validate safely.",
                affected_files=files,
                evidence=f"Coverage agent measured {coverage}% coverage.",
            ))

        if avg_complexity > 8:
            files = [item["file"] for item in production_hotspots[:3]]
            items.append(Recommendation(
                title="Refactor complex code hotspots",
                priority="medium",
                category="quality",
                description=f"Average complexity is {round(avg_complexity, 2)}, with highest production risk in {', '.join(files) or 'the largest production modules'}.",
                suggested_action="Break complex functions into smaller units, add characterization tests around current behavior, and consolidate grouped duplicate logic.",
                estimated_effort="medium",
                business_impact="Reduces change failure rate and review cycle time.",
                why="Complex code has a higher defect rate and slows feature delivery.",
                affected_files=files,
                evidence=f"Average complexity is {round(avg_complexity, 2)}.",
            ))

        if not items:
            items.append(Recommendation(
                title="Maintain current quality gates and monitor trend changes",
                priority="low",
                category="governance",
                description="The current analysis did not produce high-priority remediation items.",
                suggested_action="Keep running TestPilot AI before releases and compare future reports against this baseline.",
                estimated_effort="small",
                business_impact="Sustains release confidence and keeps regression signals visible.",
                why="Healthy projects still benefit from trend tracking and explicit release evidence.",
                evidence="No high-priority security, testing, or quality trigger crossed the configured thresholds.",
            ))

        return items

    def _target_files(self, findings) -> list[str]:
        files = []
        for finding in findings:
            file = getattr(finding, "file", "")
            if file and file not in files:
                files.append(file)
        return files[:3]

    def _production_quality_hotspots(self, metrics) -> list[dict]:
        def context_rank(metric) -> int:
            order = {"production": 0, "config": 1, "ci": 2, "test": 3, "example": 4, "docs": 5}
            return order.get(str(getattr(metric, "context", "production")).lower(), 6)

        hotspots = []
        for metric in metrics:
            issue_count = len(getattr(metric, "quality_issues", []) or getattr(metric, "issues", []))
            if issue_count:
                hotspots.append({"file": metric.file, "issues": issue_count, "rank": context_rank(metric)})
        return sorted(hotspots, key=lambda item: (item["rank"], -item["issues"]))

    def _dedupe(self, recommendations: list[Recommendation]) -> list[Recommendation]:
        unique = []
        seen = set()
        seen_titles = set()
        seen_actions = set()
        for rec in recommendations:
            normalized_title = " ".join(rec.title.lower().split())
            normalized_action = " ".join(rec.suggested_action.lower().split())
            key = (
                normalized_title,
                rec.category.lower(),
                normalized_action,
            )
            if key in seen:
                continue
            if normalized_title in seen_titles or normalized_action in seen_actions:
                continue
            seen.add(key)
            seen_titles.add(normalized_title)
            seen_actions.add(normalized_action)
            unique.append(rec)
        return unique
