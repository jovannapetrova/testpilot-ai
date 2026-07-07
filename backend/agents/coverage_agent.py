from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from models.schemas import CoverageResult


class CoverageAgent:
    name = "Coverage Agent"

    def run(self, project_dir: Path, execute: bool = True) -> CoverageResult:
        if not execute:
            return self._estimated(project_dir, "Test execution disabled by configuration.")

        strategy = self._detect_strategy(project_dir)

        if strategy == "python":
            return self._run_python_coverage(project_dir)

        if strategy == "node":
            return self._run_node_coverage(project_dir)

        if strategy == "maven":
            return self._run_command_coverage(
                project_dir,
                ["mvn", "test", "jacoco:report", "-q"],
                "jacoco",
                "Maven/JaCoCo coverage attempted.",
            )

        if strategy == "gradle":
            return self._run_command_coverage(
                project_dir,
                ["gradle", "test", "jacocoTestReport", "--quiet"],
                "jacoco",
                "Gradle/JaCoCo coverage attempted.",
            )

        return self._estimated(project_dir, "No supported test runner or test directory was detected.")

    def _detect_strategy(self, project_dir: Path) -> str | None:
        has_tests = any(
            path.is_dir() and path.name.lower() in {"tests", "test", "__tests__"}
            for path in project_dir.rglob("*")
            if not self._is_ignored(path, project_dir)
        )

        if has_tests and any((project_dir / name).exists() for name in ["pytest.ini", "pyproject.toml", "setup.cfg", "requirements.txt"]):
            return "python"

        if (project_dir / "package.json").exists():
            return "node"

        if (project_dir / "pom.xml").exists():
            return "maven"

        if (project_dir / "build.gradle").exists() or (project_dir / "build.gradle.kts").exists():
            return "gradle"

        if has_tests:
            return "python"

        return None

    def _run_python_coverage(self, project_dir: Path) -> CoverageResult:
        result = CoverageResult(executed=False, tool="coverage.py")

        if not self._has_test_files(project_dir, {".py"}):
            return self._estimated(project_dir, "Python files detected but no pytest-compatible test files were found.")

        try:
            cmd = [sys.executable, "-m", "coverage", "run", "-m", "pytest", "-q"]
            proc = subprocess.run(cmd, cwd=str(project_dir), capture_output=True, text=True, timeout=120)
            result.executed = True
            result.output = (proc.stdout + "\n" + proc.stderr).strip()
            result.passed, result.failed = self._parse_test_counts(result.output)

            report = subprocess.run(
                [sys.executable, "-m", "coverage", "json", "-o", "-"],
                cwd=str(project_dir),
                capture_output=True,
                text=True,
                timeout=45,
            )

            result.output += "\n\n" + (report.stdout or report.stderr)
            self._apply_coverage_json(result, report.stdout)
            self._coverage_reasons(result)
            return result

        except Exception as exc:
            return self._estimated(project_dir, f"Python coverage execution failed: {exc}")

    def _run_node_coverage(self, project_dir: Path) -> CoverageResult:
        result = CoverageResult(executed=False, tool="jest/npm coverage")

        try:
            package = json.loads((project_dir / "package.json").read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            return self._estimated(project_dir, "package.json could not be parsed.")

        scripts = package.get("scripts") or {}
        if "test" not in scripts:
            return self._estimated(project_dir, "package.json has no test script.")

        command = ["npm", "test", "--", "--coverage", "--watchAll=false"]
        try:
            proc = subprocess.run(command, cwd=str(project_dir), capture_output=True, text=True, timeout=120)
            result.executed = True
            result.output = (proc.stdout + "\n" + proc.stderr).strip()
            result.passed, result.failed = self._parse_test_counts(result.output)
            result.coverage_percent = self._parse_percent_from_text(result.output)
            self._coverage_reasons(result)
            return result
        except Exception as exc:
            return self._estimated(project_dir, f"Node/Jest coverage execution failed: {exc}")

    def _run_command_coverage(
        self,
        project_dir: Path,
        command: list[str],
        tool: str,
        note: str,
    ) -> CoverageResult:
        result = CoverageResult(executed=False, tool=tool)
        try:
            proc = subprocess.run(command, cwd=str(project_dir), capture_output=True, text=True, timeout=180)
            result.executed = True
            result.output = f"{note}\n" + (proc.stdout + "\n" + proc.stderr).strip()
            result.passed, result.failed = self._parse_test_counts(result.output)
            result.coverage_percent = self._parse_percent_from_text(result.output)
            if result.coverage_percent == 0:
                result.low_coverage_reasons.append("Coverage percentage was not available in command output; inspect generated JaCoCo reports.")
            self._coverage_reasons(result)
            return result
        except Exception as exc:
            return self._estimated(project_dir, f"{tool} coverage execution failed: {exc}")

    def _estimated(self, project_dir: Path, reason: str) -> CoverageResult:
        source_files = self._source_files(project_dir)
        test_files = self._test_files(project_dir)
        ratio = len(test_files) / max(len(source_files), 1)
        estimate = round(min(85, ratio * 70), 2) if test_files else 0.0

        result = CoverageResult(
            executed=False,
            estimated=True,
            coverage_percent=estimate,
            output=f"Estimated coverage only. {reason}",
            reason=reason,
            tool="static estimate",
            low_coverage_reasons=[],
            uncovered_files=[str(path.relative_to(project_dir)).replace("\\", "/") for path in source_files[:15]],
        )
        self._coverage_reasons(result)
        return result

    def _apply_coverage_json(self, result: CoverageResult, raw: str) -> None:
        try:
            data = json.loads(raw)
        except Exception:
            result.coverage_percent = self._parse_percent_from_text(raw)
            return

        totals = data.get("totals") or {}
        result.coverage_percent = round(float(totals.get("percent_covered", 0) or 0), 2)
        files = data.get("files") or {}
        result.uncovered_files = [
            file for file, details in files.items()
            if float((details.get("summary") or {}).get("percent_covered", 0) or 0) < 50
        ][:15]

    def _coverage_reasons(self, result: CoverageResult) -> None:
        if result.coverage_percent >= 80:
            return
        if result.estimated:
            result.low_coverage_reasons.append("Coverage is estimated because tests could not be executed reliably.")
        if result.failed:
            result.low_coverage_reasons.append("Some tests failed, so coverage may be incomplete.")
        if result.coverage_percent == 0:
            result.low_coverage_reasons.append("No executable coverage data was produced.")
        elif result.coverage_percent < 50:
            result.low_coverage_reasons.append("Less than half of measured source lines were covered by tests.")
        if result.uncovered_files:
            result.low_coverage_reasons.append("Several source files have low or missing coverage.")

    def _parse_test_counts(self, output: str) -> tuple[int, int]:
        passed = 0
        failed = 0
        pass_match = re.search(r"(\d+)\s+passed", output)
        fail_match = re.search(r"(\d+)\s+failed", output)
        if pass_match:
            passed = int(pass_match.group(1))
        if fail_match:
            failed = int(fail_match.group(1))
        return passed, failed

    def _parse_percent_from_text(self, text: str) -> float:
        matches = re.findall(r"(\d+(?:\.\d+)?)%", text)
        if not matches:
            return 0.0
        return round(max(float(value) for value in matches), 2)

    def _has_test_files(self, project_dir: Path, suffixes: set[str]) -> bool:
        return any(path.suffix.lower() in suffixes for path in self._test_files(project_dir))

    def _source_files(self, project_dir: Path) -> list[Path]:
        suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rb", ".php", ".rs"}
        return [
            path for path in project_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in suffixes
            and not self._is_test_path(path, project_dir)
            and not self._is_ignored(path, project_dir)
        ]

    def _test_files(self, project_dir: Path) -> list[Path]:
        return [
            path for path in project_dir.rglob("*")
            if path.is_file()
            and self._is_test_path(path, project_dir)
            and not self._is_ignored(path, project_dir)
        ]

    def _is_test_path(self, path: Path, base: Path) -> bool:
        rel = str(path.relative_to(base)).replace("\\", "/").lower()
        return any(token in rel for token in ["tests/", "/tests/", "test/", "/test/", "test_", "_test.", ".test.", ".spec.", "__tests__/"])

    def _is_ignored(self, path: Path, base: Path) -> bool:
        try:
            rel = str(path.relative_to(base)).replace("\\", "/").lower()
        except Exception:
            rel = str(path).replace("\\", "/").lower()
        return any(token in rel for token in ["node_modules/", ".git/", "__pycache__/", ".venv/", "venv/", "dist/", "build/", "target/", ".gradle/"])
