from __future__ import annotations

import json
import re
from pathlib import Path


class DependencyAnalyzerAgent:
    name = "Dependency Analyzer Agent"

    def run(self, project_dir: Path) -> dict:
        dependencies = {
            "python": self._read_python_dependencies(project_dir),
            "node": self._read_package_json(project_dir),
            "java": self._read_java_build_files(project_dir),
        }

        total = sum(len(value) for value in dependencies.values())

        return {
            "agent": self.name,
            "status": "completed",
            "dependencies": dependencies,
            "total_dependencies": total,
            "dependency_files": self._dependency_files(project_dir),
            "risk_level": self._risk_level(total),
            "notes": self._notes(dependencies),
        }

    def _read_python_dependencies(self, project_dir: Path) -> list[str]:
        results = []
        results.extend(self._read_requirements(project_dir))
        results.extend(self._read_pyproject(project_dir))
        results.extend(self._read_setup_py(project_dir))
        return sorted(set(results))

    def _read_requirements(self, project_dir: Path) -> list[str]:
        path = project_dir / "requirements.txt"
        if not path.exists():
            return []

        return [
            line.strip()
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    def _read_pyproject(self, project_dir: Path) -> list[str]:
        path = project_dir / "pyproject.toml"
        if not path.exists():
            return []

        text = path.read_text(encoding="utf-8", errors="ignore")
        deps = re.findall(r'"([a-zA-Z0-9_.\-]+)[<>=!~,\s0-9.*]*"', text)
        return [dep for dep in deps if len(dep) > 1 and dep.lower() not in ["version", "name"]]

    def _read_setup_py(self, project_dir: Path) -> list[str]:
        path = project_dir / "setup.py"
        if not path.exists():
            return []

        text = path.read_text(encoding="utf-8", errors="ignore")
        deps = re.findall(r'["\']([a-zA-Z0-9_.\-]+)[<>=!~,\s0-9.*]*["\']', text)
        return [dep for dep in deps if len(dep) > 1 and dep.lower() not in ["version", "name"]]

    def _read_package_json(self, project_dir: Path) -> list[str]:
        path = project_dir / "package.json"
        if not path.exists():
            return []

        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            deps = list((data.get("dependencies") or {}).keys())
            dev_deps = list((data.get("devDependencies") or {}).keys())
            return sorted(set(deps + dev_deps))
        except Exception:
            return []

    def _read_java_build_files(self, project_dir: Path) -> list[str]:
        return [
            name
            for name in ["pom.xml", "build.gradle", "build.gradle.kts"]
            if (project_dir / name).exists()
        ]

    def _dependency_files(self, project_dir: Path) -> list[str]:
        candidates = [
            "requirements.txt",
            "pyproject.toml",
            "setup.py",
            "package.json",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
        ]
        return [name for name in candidates if (project_dir / name).exists()]

    def _risk_level(self, total: int) -> str:
        if total == 0:
            return "Unknown"
        if total <= 10:
            return "Low"
        if total <= 40:
            return "Medium"
        return "High"

    def _notes(self, dependencies: dict) -> list[str]:
        notes = []

        if dependencies["python"]:
            notes.append("Python dependency configuration detected.")
        if dependencies["node"]:
            notes.append("Node package manifest detected.")
        if dependencies["java"]:
            notes.append("Java build configuration detected.")
        if not notes:
            notes.append("No dependency manifest was detected.")

        return notes