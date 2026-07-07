from __future__ import annotations

import ast
import re
from pathlib import Path

from models.schemas import CodeAnalysisResult, CodeFileSummary
from utils.file_utils import iter_code_files, relative_path


class CodeAnalyzerAgent:
    name = "Code Analyzer Agent"

    def run(self, project_dir: Path) -> CodeAnalysisResult:
        result = CodeAnalysisResult()

        for path in iter_code_files(project_dir):
            rel = relative_path(path, project_dir)
            suffix = path.suffix.lower().replace(".", "") or "unknown"

            result.languages[suffix] = result.languages.get(suffix, 0) + 1

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = len(text.splitlines())
            summary = CodeFileSummary(path=rel, lines=lines)

            if path.suffix.lower() == ".py":
                self._analyze_python(text, summary)

            elif path.suffix.lower() in [".js", ".jsx", ".ts", ".tsx"]:
                self._analyze_javascript(text, summary)

            elif path.suffix.lower() == ".java":
                self._analyze_java(text, summary)

            result.files.append(summary)
            result.total_lines += lines
            result.total_functions += len(summary.functions)
            result.total_classes += len(summary.classes)

        result.total_files = len(result.files)

        return result

    def _analyze_python(self, text: str, summary: CodeFileSummary) -> None:
        try:
            tree = ast.parse(text)

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    summary.functions.append(node.name)

                elif isinstance(node, ast.ClassDef):
                    summary.classes.append(node.name)

                elif isinstance(node, ast.Import):
                    summary.imports += [alias.name for alias in node.names]

                elif isinstance(node, ast.ImportFrom) and node.module:
                    summary.imports.append(node.module)

        except SyntaxError:
            return

    def _analyze_javascript(self, text: str, summary: CodeFileSummary) -> None:
        function_patterns = [
            r"function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*\(",
            r"const\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\(",
            r"let\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\(",
            r"var\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*\(",
            r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:\s*function\s*\(",
            r"exports\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=",
            r"module\.exports\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=",
        ]

        class_patterns = [
            r"class\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        ]

        import_patterns = [
            r"import\s+.*?\s+from\s+[\"']([^\"']+)[\"']",
            r"require\([\"']([^\"']+)[\"']\)",
        ]

        for pattern in function_patterns:
            summary.functions.extend(re.findall(pattern, text))

        for pattern in class_patterns:
            summary.classes.extend(re.findall(pattern, text))

        for pattern in import_patterns:
            summary.imports.extend(re.findall(pattern, text))

        summary.functions = sorted(set(summary.functions))
        summary.classes = sorted(set(summary.classes))
        summary.imports = sorted(set(summary.imports))

    def _analyze_java(self, text: str, summary: CodeFileSummary) -> None:
        class_patterns = [
            r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\binterface\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)",
            r"\brecord\s+([A-Za-z_][A-Za-z0-9_]*)",
        ]

        method_pattern = (
            r"(?:public|private|protected)?\s+"
            r"(?:static\s+)?"
            r"(?:final\s+)?"
            r"[A-Za-z0-9_<>\[\], ?]+\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*\("
        )

        import_pattern = r"import\s+([A-Za-z0-9_.*]+);"

        for pattern in class_patterns:
            summary.classes.extend(re.findall(pattern, text))

        summary.functions.extend(re.findall(method_pattern, text))
        summary.imports.extend(re.findall(import_pattern, text))

        summary.functions = sorted(set(summary.functions))
        summary.classes = sorted(set(summary.classes))
        summary.imports = sorted(set(summary.imports))