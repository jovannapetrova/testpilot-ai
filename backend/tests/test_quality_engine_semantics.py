from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ["JWT_SECRET"] = "test-secret"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.coverage_agent import CoverageAgent  # noqa: E402
from agents.orchestrator import AgentOrchestrator  # noqa: E402
from agents.recommendation_agent import RecommendationAgent  # noqa: E402
from models.schemas import CoverageResult, GeneratedTest, QualityMetric  # noqa: E402


def test_coverage_distinguishes_disabled_from_measured_zero(tmp_path):
    agent = CoverageAgent()

    disabled = agent.run(tmp_path, execute=False)
    assert disabled.coverage_percent == 0
    assert disabled.display_label == "Not measured"
    assert disabled.available is False
    assert disabled.measured is False
    assert disabled.evidence_state == "execution_disabled"

    measured_zero = CoverageResult(executed=True, tool="coverage.py")
    agent._apply_coverage_json(
        measured_zero,
        json.dumps({"totals": {"percent_covered": 0}, "files": {}}),
    )
    agent._coverage_reasons(measured_zero)
    assert measured_zero.coverage_percent == 0
    assert measured_zero.display_label == "0%"
    assert measured_zero.available is True
    assert measured_zero.measured is True
    assert "Measured coverage is 0%." in measured_zero.low_coverage_reasons


def test_coverage_distinguishes_nonzero_from_missing_report():
    agent = CoverageAgent()

    measured = CoverageResult(executed=True, tool="coverage.py")
    agent._apply_coverage_json(
        measured,
        json.dumps({"totals": {"percent_covered": 73.49}, "files": {}}),
    )
    assert measured.coverage_percent == 73.49
    assert measured.display_label == "73.49%"
    assert measured.evidence_state == "measured"

    missing = CoverageResult(executed=True, tool="coverage.py")
    agent._apply_coverage_json(missing, "")
    agent._coverage_reasons(missing)
    assert missing.coverage_percent == 0
    assert missing.display_label == "Not measured"
    assert missing.available is False
    assert missing.evidence_state == "tests_detected_no_coverage_report"


def test_testing_score_does_not_treat_unavailable_coverage_as_zero_execution():
    orchestrator = AgentOrchestrator()
    tests = [
        GeneratedTest(
            file="tests/test_generated.py",
            target="src/app.py",
            test_code="def test_generated():\n    assert 1 == 1\n",
            assertion_strength="high",
        )
    ]
    unavailable = CoverageResult(
        coverage_percent=0,
        display_label="Not measured",
        available=False,
        measured=False,
        evidence_state="execution_disabled",
    )
    measured_zero = CoverageResult(
        coverage_percent=0,
        display_label="0%",
        available=True,
        measured=True,
        evidence_state="measured",
    )

    unavailable_score = orchestrator._test_score(
        tests,
        0,
        {"executable_tests": 1, "smoke_tests": 0},
        coverage_result=unavailable,
    )
    measured_zero_score = orchestrator._test_score(
        tests,
        0,
        {"executable_tests": 1, "smoke_tests": 0},
        coverage_result=measured_zero,
    )

    assert unavailable_score > measured_zero_score
    assert unavailable_score < 25


def test_generated_tests_summary_separates_ready_executed_and_skipped_states():
    orchestrator = AgentOrchestrator()
    tests = [
        GeneratedTest(
            file="tests/test_generated.py",
            target="src/app.py",
            test_code="def test_generated():\n    result = len(['ready'])\n    assert result == 1\n",
            assertion_strength="high",
        )
    ]

    disabled = orchestrator._generated_tests_summary(
        tests,
        {
            "executable_tests": 1,
            "smoke_tests": 0,
            "needs_human_test_design": [{"target": "Service.save", "reason": "Requires database state."}],
            "skipped_generation_reasons": {"Requires database state.": 1},
        },
        CoverageResult(evidence_state="execution_disabled"),
        execution_enabled=False,
    )
    assert disabled["generated_candidates"] == 1
    assert disabled["ready_to_execute"] == 1
    assert disabled["executed_tests"] == 0
    assert disabled["passed"] is None
    assert disabled["execution_status"] == "disabled"
    assert disabled["needs_human_test_design"] == 1

    tests[0].executed = True
    tests[0].passed = 1
    executed = orchestrator._generated_tests_summary(
        tests,
        {"executable_tests": 1, "smoke_tests": 0, "needs_human_test_design": []},
        CoverageResult(evidence_state="measured"),
        execution_enabled=True,
    )
    assert executed["executed_tests"] == 1
    assert executed["passed"] == 1
    assert executed["failed"] == 0
    assert executed["execution_status"] == "executed"


def test_quality_ranking_keeps_production_hotspot_ahead_of_test_hotspot():
    orchestrator = AgentOrchestrator()
    production = QualityMetric(
        file="src/createStore.ts",
        context="production",
        complexity=9,
        maintainability_index=62,
        issues=["High estimated branching complexity"],
        quality_issues=[{"issue_type": "high_complexity"}],
    )
    test_hotspot = QualityMetric(
        file="tests/types/store.spec.ts",
        context="test",
        complexity=30,
        maintainability_index=20,
        issues=["issue"] * 20,
        quality_issues=[{"issue_type": "test_smell"}] * 20,
    )

    summary = orchestrator._quality_summary([test_hotspot, production])

    assert summary["highest_production_risk"]["file"] == "src/createStore.ts"
    assert summary["test_suite_hotspot"]["file"] == "tests/types/store.spec.ts"


def test_recommendations_are_scope_aware_for_unmeasured_coverage():
    recommendations = RecommendationAgent().run(
        security_count=0,
        coverage=0,
        avg_complexity=2,
        coverage_result=CoverageResult(
            coverage_percent=0,
            display_label="Not measured",
            available=False,
            measured=False,
            evidence_state="execution_disabled",
            reason="Test execution is disabled by configuration.",
        ),
        generation_metadata={
            "executable_tests": 4,
            "smoke_tests": 0,
            "needs_human_test_design": [{"target": "Store.configure", "reason": "Requires Redux fixture."}],
        },
    )

    titles = [item.title for item in recommendations]
    assert "Increase test coverage" not in titles
    assert any("Configure measured coverage" in title for title in titles)
    assert len(titles) == len(set(titles))
