def build_ai_insights(report_data: dict) -> dict:
    overall = float(report_data.get("overall_score", 0) or 0)
    scores = {
        "Code quality and maintainability": float(report_data.get("quality_score", 0) or 0),
        "Security": float(report_data.get("security_score", 0) or 0),
        "Testing": float(report_data.get("test_score", 0) or 0),
    }

    strongest_area = max(scores, key=scores.get)
    weakest_area = min(scores, key=scores.get)

    if overall >= 85:
        risk_level = "Excellent"
    elif overall >= 70:
        risk_level = "Good"
    elif overall >= 50:
        risk_level = "Fair"
    else:
        risk_level = "Needs Improvement"

    security_findings = report_data.get("security_findings", [])
    quality_metrics = report_data.get("quality_metrics", [])
    generated_tests = report_data.get("generated_tests", [])
    coverage = report_data.get("coverage", {}) or {}

    real_security_findings = [
        finding for finding in security_findings
        if finding.get("category") == "real_secret_candidate"
        or str(finding.get("severity", "")).lower().split(".")[-1] in {"high", "critical"}
    ]
    low_confidence_secret_refs = [
        finding for finding in security_findings
        if finding.get("category") in {
            "placeholder_secret",
            "secret_reference",
            "test_fixture_secret",
            "ci_secret_reference",
            "runtime_secret_reference",
            "auth_parameter",
        }
    ]

    priority_actions = []
    if scores["Security"] < 80 and real_security_findings:
        priority_actions.append({
            "priority": "high",
            "what": "Triage production-context security findings first.",
            "why": "Production findings have the highest chance of affecting users or regulated data.",
            "impact": "Reduces breach likelihood and audit exposure.",
            "how_to_fix": "Group by fingerprint, validate exploitability, remediate secrets/injection/network issues, and add regression tests.",
            "estimated_effort": "medium",
            "business_impact": "High risk reduction for release readiness.",
        })
    elif low_confidence_secret_refs:
        priority_actions.append({
            "priority": "low",
            "what": "Validate low-confidence secret references.",
            "why": "The findings look like placeholders, CI/config references, runtime properties, or fixture values rather than leaked live secrets.",
            "impact": "Reduces audit noise and confirms deployment hygiene.",
            "how_to_fix": "Confirm references resolve through managed secrets, avoid logging resolved values, and keep examples obviously fake.",
            "estimated_effort": "small",
            "business_impact": "Improves confidence without creating unnecessary incident work.",
        })
    if scores["Testing"] < 70:
        priority_actions.append({
            "priority": "high",
            "what": "Increase coverage for core production modules.",
            "why": "Low or estimated coverage weakens confidence in generated recommendations and refactoring safety.",
            "impact": "Improves release confidence and reduces regression risk.",
            "how_to_fix": "Start with uncovered production files and turn review-only targets into executable unit/API tests.",
            "estimated_effort": "medium",
            "business_impact": "Fewer escaped regressions and faster reviews.",
        })
    if scores["Code quality and maintainability"] < 75:
        priority_actions.append({
            "priority": "medium",
            "what": "Refactor high-smell files with long methods, large classes, or duplicated logic.",
            "why": "Complex code is slower to change and harder to test.",
            "impact": "Reduces maintenance cost and improves onboarding.",
            "how_to_fix": "Use characterization tests, extract smaller functions/classes, and remove dead code indicators.",
            "estimated_effort": "medium",
            "business_impact": "Improves delivery speed for future changes.",
        })

    if not priority_actions:
        priority_actions.append({
            "priority": "low",
            "what": "Maintain current quality gates and track trends.",
            "why": "Current scores indicate a relatively healthy baseline.",
            "impact": "Prevents gradual quality regression.",
            "how_to_fix": "Keep coverage thresholds, security scans, and report comparisons in CI.",
            "estimated_effort": "low",
            "business_impact": "Sustains release confidence.",
        })

    return {
        "risk_level": risk_level,
        "main_weakness": weakest_area,
        "summary": (
            f"The project achieved an overall score of {overall}. "
            f"The strongest area is {strongest_area} with score {scores[strongest_area]}, "
            f"while the main improvement area is {weakest_area} with score {scores[weakest_area]}."
        ),
        "executive_summary": {
            "why_it_matters": "The assessment combines code quality, security, generated test readiness, and coverage evidence to estimate delivery and operational risk.",
            "business_impact": priority_actions[0]["business_impact"],
            "recommended_focus": priority_actions[0]["what"],
        },
        "priority_actions": priority_actions,
        "next_best_actions": [
            action["what"] for action in priority_actions
        ],
        "statistics": {
            "security_findings": len(security_findings),
            "quality_metrics": len(quality_metrics),
            "generated_tests": len(generated_tests),
            "coverage_percent": coverage.get("coverage_percent", 0),
            "coverage_estimated": coverage.get("estimated", False),
        },
    }
