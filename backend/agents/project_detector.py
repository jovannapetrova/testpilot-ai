from pathlib import Path
from services.technology_detector import TechnologyDetector


class ProjectDetectorAgent:
    name = "Project Detector Agent"

    def __init__(self):
        self.detector = TechnologyDetector()

    def run(self, project_dir: Path) -> dict:
        result = self.detector.detect(project_dir)

        return {
            "agent": self.name,
            "status": "completed",
            "project_type": self._project_type(result),
            **result,
        }

    def _project_type(self, result: dict) -> str:
        frameworks = result.get("frameworks", [])
        language = result.get("primary_language", "unknown")
        category = result.get("project_category")

        if category == "cli":
            return "CLI Application"
        if category == "web_api":
            return "Web API / Backend Service"
        if category == "frontend":
            return "Frontend Web Application"
        if category == "desktop_ui":
            return "Desktop / UI Application"
        if category == "data_ml":
            return "Data / Machine Learning Project"
        if category == "library":
            return "Reusable Library / Package"

        if "FastAPI" in frameworks:
            return "FastAPI Backend"
        if "Django" in frameworks:
            return "Django Web Application"
        if "Flask" in frameworks:
            return "Flask Web Application"
        if "React" in frameworks:
            return "React Frontend"
        if "Spring Boot" in frameworks:
            return "Spring Boot Backend"
        if "Pygame" in frameworks:
            return "Python Desktop/Game Application"
        if language == "python":
            return "Python Project"
        if language == "java":
            return "Java Project"
        if language in ["javascript", "typescript"]:
            return "JavaScript/TypeScript Project"

        return "Generic Software Project"