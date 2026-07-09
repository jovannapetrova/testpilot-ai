from __future__ import annotations
from models.schemas import FindingSeverity, Recommendation
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
            ))
        elif reference_findings:
            files = self._target_files(reference_findings)
            title = "Validate CI/config secret references" if any(getattr(f, "category", "") == "ci_secret_reference" for f in reference_findings) else "Review low-confidence secret references"
            items.append(Recommendation(
                title=title,
                priority=FindingSeverity.low,
                category="security",
                description=f"Secret-like findings are low-confidence references/placeholders in {', '.join(files) or 'non-production/config contexts'}.",
                suggested_action="Confirm references point to managed secrets, keep fixture values fake, and avoid logging resolved secret values.",
                estimated_effort="small",
                business_impact="Reduces audit noise without treating placeholders as active incidents.",
                why="The findings do not look like exposed live credentials, but they should be validated for deployment hygiene.",
            ))

        if coverage < 60:
            skipped = generation_metadata.get("skipped_generation_reasons", {})
            skipped_text = ", ".join(list(skipped.keys())[:2]) or "core untested production paths"
            items.append(Recommendation(
                title="Raise coverage on core production paths",
                priority="high" if coverage < 30 else "medium",
                category="testing",
                description=f"Coverage is {coverage}%, which is below an enterprise release-confidence threshold.",
                suggested_action=f"Add executable tests around {skipped_text}; prioritize modules listed as uncovered or requiring human fixtures.",
                estimated_effort="medium",
                business_impact="Improves release confidence and reduces regression cost.",
                why="Low coverage means refactoring and security fixes are harder to validate safely.",
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
        for rec in recommendations:
            key = (
                rec.title.lower(),
                rec.category.lower(),
                rec.suggested_action.lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(rec)
        return unique
