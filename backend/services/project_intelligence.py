def build_project_intelligence(project_profile: dict, dependency_profile: dict) -> dict:
    frameworks = project_profile.get("frameworks", [])
    primary_language = project_profile.get("primary_language", "unknown")

    strengths = []
    risks = []

    if project_profile.get("has_readme"):
        strengths.append("README documentation is present.")
    else:
        risks.append("README documentation is missing.")

    if project_profile.get("has_tests"):
        strengths.append("Test-related files were detected.")
    else:
        risks.append("No explicit test files were detected.")

    if project_profile.get("has_docker"):
        strengths.append("Docker configuration detected.")
    else:
        risks.append("Docker configuration was not detected.")

    dependency_count = dependency_profile.get("total_dependencies", 0)
    repository_shape = project_profile.get("repository_shape", {})
    entrypoints = project_profile.get("entrypoints", [])

    if dependency_count == 0:
        risks.append("No dependency manifest was detected.")
    elif dependency_count <= 10:
        strengths.append("Dependency footprint is small.")
    else:
        risks.append("Dependency footprint should be reviewed.")

    if repository_shape.get("has_ci"):
        strengths.append("CI workflow configuration detected.")
    else:
        risks.append("CI workflow configuration was not detected.")

    if repository_shape.get("looks_monorepo"):
        risks.append("Repository appears to be a monorepo; analysis should be interpreted per package/service boundary.")

    if entrypoints:
        strengths.append(f"Entrypoints detected: {', '.join(entrypoints[:3])}.")

    return {
        "project_type": project_profile.get("project_type", "Generic Software Project"),
        "primary_language": primary_language,
        "frameworks": frameworks,
        "build_tools": project_profile.get("build_tools", []),
        "has_docker": project_profile.get("has_docker", False),
        "has_readme": project_profile.get("has_readme", False),
        "has_tests": project_profile.get("has_tests", False),
        "dependency_count": dependency_count,
        "dependency_files": dependency_profile.get("dependency_files", []),
        "dependency_risk_level": dependency_profile.get("risk_level", "Unknown"),
        "repository_shape": repository_shape,
        "entrypoints": entrypoints,
        "architecture_signals": {
            "is_monorepo": repository_shape.get("looks_monorepo", False),
            "has_ci": repository_shape.get("has_ci", False),
            "has_infrastructure": repository_shape.get("has_infra", False),
            "has_tests_dir": repository_shape.get("has_tests_dir", False),
        },
        "strengths": strengths,
        "risks": risks,
        "summary": (
            f"This project was identified as {project_profile.get('project_type', 'a software project')} "
            f"with primary language {primary_language}. "
            f"Detected frameworks: {', '.join(frameworks) if frameworks else 'none'}."
        ),
    }
