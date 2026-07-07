from services.test_strategies import (
    BaseTestStrategy,
    PythonStrategy,
    FastAPIStrategy,
    ReactStrategy,
    JavaStrategy,
    SpringStrategy,
)


class StrategyFactory:
    def select_test_strategy(self, project_profile: dict):
        frameworks = project_profile.get("frameworks", [])
        language = project_profile.get("primary_language", "unknown")
        category = project_profile.get("project_category", "generic")

        if category == "frontend" or "React" in frameworks:
            return ReactStrategy()

        if category == "web_api" and "FastAPI" in frameworks:
            return FastAPIStrategy()

        if "Spring Boot" in frameworks:
            return SpringStrategy()

        if language == "java":
            return JavaStrategy()

        if language == "python":
            return PythonStrategy()

        return BaseTestStrategy()