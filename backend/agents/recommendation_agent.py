from __future__ import annotations
from models.schemas import Recommendation
from services.llm_service import LLMService

class RecommendationAgent:
    name = "Recommendation Agent"

    def __init__(self):
        self.llm = LLMService()

    def run(self, security_count: int, coverage: float, avg_complexity: float) -> list[Recommendation]:
        raw = self.llm.generate_recommendations({
            "security_count": security_count,
            "coverage": coverage,
            "complexity": avg_complexity,
        })
        recommendations = [Recommendation(**item) for item in raw]
        recommendations.extend(self._deterministic_recommendations(security_count, coverage, avg_complexity))
        return self._dedupe(recommendations)

    def _deterministic_recommendations(
        self,
        security_count: int,
        coverage: float,
        avg_complexity: float,
    ) -> list[Recommendation]:
        items: list[Recommendation] = []

        if security_count:
            items.append(Recommendation(
                title="Triage production security findings",
                priority="high",
                category="security",
                description=f"{security_count} security finding(s) were detected after context-aware grouping.",
                suggested_action="Prioritize production findings, apply remediation guidance, and add regression tests for each confirmed issue.",
                estimated_effort="medium",
                business_impact="Reduces breach and compliance risk before release.",
                why="Security findings in production code can become exploitable defects.",
            ))

        if coverage < 60:
            items.append(Recommendation(
                title="Raise coverage on core production paths",
                priority="high" if coverage < 30 else "medium",
                category="testing",
                description=f"Coverage is {coverage}%, which is below an enterprise release-confidence threshold.",
                suggested_action="Convert generated review TODOs into executable tests and prioritize low-coverage production modules.",
                estimated_effort="medium",
                business_impact="Improves release confidence and reduces regression cost.",
                why="Low coverage means refactoring and security fixes are harder to validate safely.",
            ))

        if avg_complexity > 8:
            items.append(Recommendation(
                title="Refactor complex code hotspots",
                priority="medium",
                category="quality",
                description=f"Average complexity is {round(avg_complexity, 2)}, suggesting maintainability risk.",
                suggested_action="Break complex functions into smaller units, add characterization tests, and remove duplicate logic.",
                estimated_effort="medium",
                business_impact="Reduces change failure rate and review cycle time.",
                why="Complex code has a higher defect rate and slows feature delivery.",
            ))

        return items

    def _dedupe(self, recommendations: list[Recommendation]) -> list[Recommendation]:
        unique = []
        seen = set()
        for rec in recommendations:
            key = (rec.title.lower(), rec.category.lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(rec)
        return unique
