from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

from models.schemas import QualityMetric
from utils.file_utils import iter_code_files, relative_path


class QualityAgent:
    name = "Quality Agent"
    max_files = 250
    last_analysis_metadata: dict = {}

    def run(self, project_dir: Path) -> list[QualityMetric]:
        metrics: list[QualityMetric] = []

        candidates = [
            path for path in iter_code_files(project_dir)
            if path.suffix.lower() in [".py", ".js", ".jsx", ".ts", ".tsx", ".java"]
            and not self._is_low_value_path(relative_path(path, project_dir))
        ]
        candidates = sorted(
            candidates,
            key=lambda path: self._priority_score(relative_path(path, project_dir)),
        )
        total_candidates = len(candidates)
        selected_candidates = candidates[: self.max_files]
        self.last_analysis_metadata = {
            "partial_analysis": total_candidates > len(selected_candidates),
            "analyzed_files": len(selected_candidates),
            "candidate_files": total_candidates,
            "warnings": [],
        }
        if total_candidates > len(selected_candidates):
            self.last_analysis_metadata["warnings"].append(
                f"Quality analysis was capped at {len(selected_candidates)} production-prioritized files out of {total_candidates} candidates."
            )

        for path in selected_candidates:
            suffix = path.suffix.lower()

            if suffix not in [".py", ".js", ".jsx", ".ts", ".tsx", ".java"]:
                continue

            rel = relative_path(path, project_dir)

            if self._is_low_value_path(rel):
                continue

            if suffix == ".py":
                metric = self._python_metric(path, rel)

            elif suffix in [".js", ".jsx", ".ts", ".tsx"]:
                metric = self._javascript_metric(path, rel)

            elif suffix == ".java":
                metric = self._java_metric(path, rel)

            else:
                continue

            metrics.append(metric)

        return metrics

    def _python_metric(self, path: Path, rel: str) -> QualityMetric:
        metric = QualityMetric(file=rel, context=self._classify_context(rel))
        text = self._read(path)

        metric.maintainability_index = self._python_maintainability_index(path)
        metric.complexity = self._python_average_complexity(path)
        self._apply_python_smells(metric, text)

        if metric.maintainability_index and metric.maintainability_index < 50:
            metric.issues.append("Low maintainability index")
            self._add_quality_issue(
                metric,
                "low_maintainability",
                1,
                max(1, len(text.splitlines())),
                f"Maintainability index is {metric.maintainability_index}.",
                "Low maintainability usually means changes are riskier and harder to review.",
                "Split high-risk modules and add focused tests around the most complex branches.",
                "medium",
                "major",
            )
            metric.recommendations.append("Split high-risk modules and add focused tests around the most complex branches.")

        if metric.complexity and metric.complexity > 10:
            metric.issues.append("High cyclomatic complexity")
            self._add_quality_issue(
                metric,
                "high_complexity",
                1,
                max(1, len(text.splitlines())),
                f"Average cyclomatic complexity is {metric.complexity}.",
                "Complex branching raises defect risk and makes boundary testing harder.",
                "Refactor complex functions using guard clauses, smaller collaborators, or strategy objects.",
                "medium",
                "major",
            )
            metric.recommendations.append("Refactor complex functions using guard clauses, smaller collaborators, or strategy objects.")

        return metric

    def _javascript_metric(self, path: Path, rel: str) -> QualityMetric:
        text = self._read(path)

        lines = self._logical_lines(text)
        functions = self._count_javascript_functions(text)
        classes = len(re.findall(r"\bclass\s+[A-Za-z_$][A-Za-z0-9_$]*", text))
        branches = self._count_branches(text)

        complexity = round(max(1, branches / max(functions, 1)), 2)
        maintainability = self._estimate_maintainability(
            lines=lines,
            complexity=complexity,
            functions=functions,
            classes=classes,
        )

        metric = QualityMetric(
            file=rel,
            context=self._classify_context(rel),
            complexity=complexity,
            maintainability_index=maintainability,
        )

        if lines > 400:
            metric.issues.append("Large JavaScript/TypeScript file")
            metric.smells.append("Large file")
            self._add_quality_issue(metric, "large_file", 1, len(text.splitlines()), f"{lines} logical lines.", "Large files are harder to review and often mix responsibilities.", "Split by feature, route, component, or domain service.", "medium", "major")

        if complexity > 10:
            metric.issues.append("High estimated branching complexity")
            metric.smells.append("High branching complexity")

        if maintainability < 50:
            metric.issues.append("Low estimated maintainability")

        self._apply_text_smells(metric, text, language="javascript")
        return metric

    def _java_metric(self, path: Path, rel: str) -> QualityMetric:
        text = self._read(path)

        lines = self._logical_lines(text)
        methods = self._count_java_methods(text)
        classes = len(
            re.findall(
                r"\b(class|interface|enum|record)\s+[A-Za-z_][A-Za-z0-9_]*",
                text,
            )
        )
        branches = self._count_branches(text)

        complexity = round(max(1, branches / max(methods, 1)), 2)
        maintainability = self._estimate_maintainability(
            lines=lines,
            complexity=complexity,
            functions=methods,
            classes=classes,
        )

        metric = QualityMetric(
            file=rel,
            context=self._classify_context(rel),
            complexity=complexity,
            maintainability_index=maintainability,
        )

        if lines > 500:
            metric.issues.append("Large Java file")
            metric.smells.append("Large file")
            self._add_quality_issue(metric, "large_file", 1, len(text.splitlines()), f"{lines} logical lines.", "Large Java files often hide multiple responsibilities.", "Extract collaborators or package-level services with focused tests.", "medium", "major")

        if complexity > 10:
            metric.issues.append("High estimated branching complexity")
            metric.smells.append("High branching complexity")

        if maintainability < 50:
            metric.issues.append("Low estimated maintainability")

        self._apply_text_smells(metric, text, language="java")
        return metric

    def _apply_python_smells(self, metric: QualityMetric, text: str) -> None:
        try:
            tree = ast.parse(text)
        except SyntaxError:
            self._apply_text_smells(metric, text, language="python")
            return

        assigned = set()
        used = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                length = self._node_length(node)
                arg_count = len([arg for arg in node.args.args if arg.arg not in {"self", "cls"}])
                nesting = self._python_nesting_depth(node)

                if length > 60:
                    metric.long_methods += 1
                    metric.smells.append(f"Long method: {node.name} ({length} lines)")
                    self._add_quality_issue(metric, "long_method", node.lineno, getattr(node, "end_lineno", node.lineno), f"{node.name} is {length} lines.", "Long methods are difficult to reason about and test thoroughly.", "Extract cohesive helper methods and preserve behavior with characterization tests.", "medium", "major")

                if arg_count > 6:
                    metric.too_many_parameters += 1
                    metric.smells.append(f"Too many parameters: {node.name} ({arg_count})")
                    self._add_quality_issue(metric, "too_many_parameters", node.lineno, node.lineno, f"{node.name} has {arg_count} non-self parameters.", "Wide signatures are harder to call correctly and evolve safely.", "Introduce a parameter object, dataclass, or configuration model.", "small", "minor")

                metric.max_nesting_depth = max(metric.max_nesting_depth, nesting)
                if nesting > 4:
                    metric.smells.append(f"Deep nesting: {node.name} (depth {nesting})")
                    self._add_quality_issue(metric, "deep_nesting", node.lineno, getattr(node, "end_lineno", node.lineno), f"{node.name} reaches nesting depth {nesting}.", "Deep nesting makes edge cases easy to miss.", "Use guard clauses and smaller decision functions.", "medium", "major")

            elif isinstance(node, ast.ClassDef):
                length = self._node_length(node)
                method_count = len([item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))])
                if length > 250 or method_count > 20:
                    metric.large_classes += 1
                    metric.smells.append(f"Large class: {node.name} ({length} lines, {method_count} methods)")
                    self._add_quality_issue(metric, "large_class", node.lineno, getattr(node, "end_lineno", node.lineno), f"{node.name} has {length} lines and {method_count} methods.", "Large classes tend to mix responsibilities and slow down changes.", "Split by responsibility and add characterization tests before refactoring.", "large", "major")

            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Store):
                    assigned.add(node.id)
                elif isinstance(node.ctx, ast.Load):
                    used.add(node.id)

        dead = sorted(name for name in assigned - used if not name.startswith("_"))[:8]
        metric.dead_code_indicators += len(dead)
        for name in dead:
            metric.smells.append(f"Potential unused local or symbol: {name}")
            self._add_quality_issue(metric, "dead_code_indicator", 1, 1, f"Assigned symbol {name} was not observed as used in the same module.", "Unused symbols add maintenance cost and may hide incomplete changes.", "Verify dynamically referenced names before removal.", "small", "minor")

        self._apply_text_smells(metric, text, language="python")
        self._quality_recommendations(metric)

    def _apply_text_smells(self, metric: QualityMetric, text: str, language: str) -> None:
        metric.duplicate_blocks_detail = self._duplicate_block_details(text, metric.file)
        metric.duplicate_blocks = len(metric.duplicate_blocks_detail)

        if metric.duplicate_blocks:
            metric.smells.append(f"Duplicate logic blocks detected: {metric.duplicate_blocks}")
            for detail in metric.duplicate_blocks_detail[:5]:
                self._add_quality_issue(
                    metric,
                    "duplicate_logic",
                    detail["first_start"],
                    detail["first_end"],
                    f"Similar block repeated at lines {detail['second_start']}-{detail['second_end']}.",
                    "Duplicated logic multiplies future defect and patch effort.",
                    "Extract a shared helper, service, or domain abstraction after adding regression tests.",
                    "medium",
                    "major",
                )

        for line_number, line in self._todo_lines(text)[:10]:
            metric.smells.append("Open TODO/FIXME/HACK markers")
            self._add_quality_issue(metric, "open_todo", line_number, line_number, line.strip()[:160], "Open markers can represent unfinished or risky behavior.", "Convert to tracked work or resolve before release.", "small", "minor")

        if language in {"javascript", "java"}:
            metric.long_methods += len(re.findall(r"\{(?:[^{}]|\{[^{}]*\}){1600,}\}", text))
            metric.too_many_parameters += len(re.findall(r"\([^)]*,[^)]*,[^)]*,[^)]*,[^)]*,[^)]*,[^)]*\)", text))
            metric.max_nesting_depth = max(metric.max_nesting_depth, self._brace_nesting_depth(text))

            if metric.long_methods:
                metric.smells.append("Long function/method bodies detected")
            if metric.too_many_parameters:
                metric.smells.append("Functions with many parameters detected")
            if metric.max_nesting_depth > 5:
                metric.smells.append(f"Deep nesting detected (depth {metric.max_nesting_depth})")

        self._quality_recommendations(metric)

    def _quality_recommendations(self, metric: QualityMetric) -> None:
        if metric.large_classes:
            metric.recommendations.append("Split large classes by responsibility and add characterization tests before refactoring.")
        if metric.long_methods:
            metric.recommendations.append("Extract long methods into smaller named units with focused tests.")
        if metric.duplicate_blocks:
            metric.recommendations.append("Consolidate duplicated logic behind shared helpers or domain services.")
        if metric.too_many_parameters:
            metric.recommendations.append("Introduce parameter objects or configuration models for wide function signatures.")
        if metric.max_nesting_depth > 4:
            metric.recommendations.append("Reduce nesting with guard clauses and smaller decision functions.")
        if metric.dead_code_indicators:
            metric.recommendations.append("Remove or verify unused code paths with coverage before deletion.")

        metric.issues = sorted(set(metric.issues + metric.smells[:8]))
        metric.recommendations = sorted(set(metric.recommendations))

    def _node_length(self, node) -> int:
        start = getattr(node, "lineno", 0) or 0
        end = getattr(node, "end_lineno", start) or start
        return max(0, end - start + 1)

    def _python_nesting_depth(self, node) -> int:
        branch_nodes = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match)

        def visit(current, depth):
            max_depth = depth
            for child in ast.iter_child_nodes(current):
                child_depth = depth + 1 if isinstance(child, branch_nodes) else depth
                max_depth = max(max_depth, visit(child, child_depth))
            return max_depth

        return visit(node, 0)

    def _brace_nesting_depth(self, text: str) -> int:
        depth = 0
        max_depth = 0
        for char in text:
            if char == "{":
                depth += 1
                max_depth = max(max_depth, depth)
            elif char == "}":
                depth = max(0, depth - 1)
        return max_depth

    def _duplicate_block_count(self, text: str) -> int:
        normalized_lines = [
            re.sub(r"\s+", " ", line.strip())
            for line in text.splitlines()
            if line.strip()
            and not line.strip().startswith(("#", "//", "*"))
            and len(line.strip()) > 8
        ]
        windows = {}
        for index in range(max(0, len(normalized_lines) - 5)):
            block = "\n".join(normalized_lines[index:index + 6])
            windows[block] = windows.get(block, 0) + 1
        return sum(1 for count in windows.values() if count > 1)

    def _duplicate_block_details(self, text: str, file_name: str) -> list[dict[str, int | str]]:
        normalized_lines: list[tuple[int, str]] = []
        for line_number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*")) or len(stripped) <= 8:
                continue
            normalized_lines.append((line_number, re.sub(r"\s+", " ", stripped)))

        windows: dict[str, tuple[int, int]] = {}
        details: list[dict[str, int | str]] = []
        for index in range(max(0, len(normalized_lines) - 5)):
            block_lines = normalized_lines[index:index + 6]
            block = "\n".join(item[1] for item in block_lines)
            start = block_lines[0][0]
            end = block_lines[-1][0]
            if block in windows:
                first_start, first_end = windows[block]
                details.append({
                    "file": file_name,
                    "first_start": first_start,
                    "first_end": first_end,
                    "second_start": start,
                    "second_end": end,
                })
            else:
                windows[block] = (start, end)
        return details[:20]

    def _todo_lines(self, text: str) -> list[tuple[int, str]]:
        return [
            (line_number, line)
            for line_number, line in enumerate(text.splitlines(), 1)
            if re.search(r"\b(TODO|FIXME|HACK)\b", line, flags=re.IGNORECASE)
        ]

    def _add_quality_issue(
        self,
        metric: QualityMetric,
        issue_type: str,
        start: int,
        end: int,
        evidence: str,
        why: str,
        remediation: str,
        effort: str,
        severity: str,
    ) -> None:
        metric.quality_issues.append({
            "issue_type": issue_type,
            "type": issue_type,
            "file": metric.file,
            "symbol": self._issue_symbol(evidence),
            "start_line": max(1, int(start or 1)),
            "end_line": max(1, int(end or start or 1)),
            "evidence": evidence,
            "why_it_matters": why,
            "why": why,
            "remediation": remediation,
            "effort": effort,
            "effort_estimate": effort,
            "severity": severity,
            "context": metric.context,
        })

    def _issue_symbol(self, evidence: str) -> str:
        match = re.match(r"([A-Za-z_$][A-Za-z0-9_$]*)", evidence or "")
        return match.group(1) if match else ""

    def _python_maintainability_index(self, path: Path) -> float:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "radon", "mi", "-j", str(path)],
                capture_output=True,
                text=True,
                timeout=8,
            )

            data = json.loads(proc.stdout or "{}")
            item = data.get(str(path), {})

            return round(float(item.get("mi", 0)), 2)

        except Exception:
            return self._python_fallback_maintainability(path)

    def _python_average_complexity(self, path: Path) -> float:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "radon", "cc", "-j", str(path)],
                capture_output=True,
                text=True,
                timeout=8,
            )

            data = json.loads(proc.stdout or "{}")
            blocks = data.get(str(path), [])

            if not blocks:
                return 0

            return round(
                sum(float(block.get("complexity", 0)) for block in blocks)
                / len(blocks),
                2,
            )

        except Exception:
            return self._python_fallback_complexity(path)

    def _python_fallback_maintainability(self, path: Path) -> float:
        text = self._read(path)
        lines = self._logical_lines(text)
        functions = len(re.findall(r"^\s*def\s+", text, re.MULTILINE))
        classes = len(re.findall(r"^\s*class\s+", text, re.MULTILINE))
        complexity = self._count_branches(text) / max(functions, 1)

        return self._estimate_maintainability(
            lines=lines,
            complexity=complexity,
            functions=functions,
            classes=classes,
        )

    def _python_fallback_complexity(self, path: Path) -> float:
        text = self._read(path)

        try:
            tree = ast.parse(text)
        except SyntaxError:
            return 0

        functions = 0
        branches = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions += 1

            if isinstance(
                node,
                (
                    ast.If,
                    ast.For,
                    ast.While,
                    ast.Try,
                    ast.BoolOp,
                    ast.IfExp,
                    ast.ExceptHandler,
                ),
            ):
                branches += 1

        if not functions:
            return 0

        return round(max(1, branches / functions), 2)

    def _estimate_maintainability(
        self,
        lines: int,
        complexity: float,
        functions: int,
        classes: int,
    ) -> float:
        score = 100.0

        score -= max(0, lines - 120) * 0.03
        score -= max(0, complexity - 4) * 4
        score -= max(0, functions - 20) * 0.3
        score -= max(0, classes - 8) * 0.4

        return round(max(5, min(100, score)), 2)

    def _logical_lines(self, text: str) -> int:
        return len(
            [
                line
                for line in text.splitlines()
                if line.strip()
                and not line.strip().startswith("#")
                and not line.strip().startswith("//")
            ]
        )

    def _count_branches(self, text: str) -> int:
        return len(
            re.findall(
                r"\b(if|else if|for|while|case|catch|switch|try|except|elif)\b|\?\s*",
                text,
            )
        )

    def _count_javascript_functions(self, text: str) -> int:
        patterns = [
            r"function\s+[A-Za-z_$][A-Za-z0-9_$]*\s*\(",
            r"=>",
            r"[A-Za-z_$][A-Za-z0-9_$]*\s*:\s*function\s*\(",
            r"exports\.[A-Za-z_$][A-Za-z0-9_$]*\s*=",
            r"module\.exports\.[A-Za-z_$][A-Za-z0-9_$]*\s*=",
        ]

        return sum(len(re.findall(pattern, text)) for pattern in patterns)

    def _count_java_methods(self, text: str) -> int:
        return len(
            re.findall(
                r"(?:public|private|protected)?\s+"
                r"(?:static\s+)?"
                r"(?:final\s+)?"
                r"[A-Za-z0-9_<>\[\], ?]+\s+"
                r"[A-Za-z_][A-Za-z0-9_]*\s*\(",
                text,
            )
        )

    def _read(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _is_low_value_path(self, rel: str) -> bool:
        value = rel.replace("\\", "/").lower()

        return any(
            token in value
            for token in [
                "node_modules/",
                ".git/",
                "__pycache__/",
                ".venv/",
                "venv/",
                "dist/",
                "build/",
            ]
        )

    def _priority_score(self, rel: str) -> int:
        value = rel.replace("\\", "/").lower()
        score = 100
        for token in [
            "src/", "app/", "lib/", "server/", "api/", "routes/",
            "controllers/", "services/", "models/",
        ]:
            if token in value:
                score -= 20
        for token in [
            "tests/", "/tests/", "__tests__/", "docs/", "examples/",
            "example/", "demo/", "tutorial/", "scripts/",
        ]:
            if token in value:
                score += 35
        return score

    def _classify_context(self, rel: str) -> str:
        value = rel.replace("\\", "/").lower()
        if any(token in value for token in ["tests/", "/tests/", "__tests__/", ".test.", ".spec.", "test_"]):
            return "test"
        if any(token in value for token in ["docs/", "docs_src/", "/doc/"]):
            return "docs"
        if any(token in value for token in ["examples/", "example/", "demo/", "tutorial/", "sample/"]):
            return "example"
        if any(token in value for token in [".github/", "dockerfile", "docker-compose", ".yml", ".yaml"]):
            return "config"
        return "production"
