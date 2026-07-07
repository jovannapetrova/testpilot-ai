from __future__ import annotations

import json
import hashlib
import math
import re
import subprocess
import sys
from pathlib import Path

from models.schemas import SecurityFinding, FindingSeverity


class SecurityAgent:
    name = "Security Agent"

    def run(self, project_dir: Path) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []

        findings.extend(self._run_bandit(project_dir))
        findings.extend(self._simple_secret_scan(project_dir))

        return self._dedupe_findings(findings)

    def _run_bandit(self, project_dir: Path) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []

        try:
            cmd = [
                sys.executable,
                "-m",
                "bandit",
                "-r",
                str(project_dir),
                "-f",
                "json",
            ]

            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=90,
            )

            raw = proc.stdout.strip() or "{}"
            data = json.loads(raw)

            for item in data.get("results", []):
                filename = item.get("filename", "")
                rel_file = self._relative_file(filename, project_dir)

                issue = item.get("test_name", "Bandit finding")
                description = item.get("issue_text", "")
                context = self._classify_context(rel_file)

                if self._should_skip_bandit_finding(rel_file, issue):
                    continue

                raw_severity = item.get("issue_severity", "MEDIUM").lower()
                severity = self._normalize_bandit_severity(raw_severity)
                severity = self._adjust_severity_for_context(
                    file_path=rel_file,
                    issue=issue,
                    severity=severity,
                )

                findings.append(
                    SecurityFinding(
                        file=rel_file,
                        line=item.get("line_number", 0),
                        severity=severity,
                        context=context,
                        issue=issue,
                        description=self._contextual_description(context, description),
                        confidence=self._normalize_confidence(item.get("issue_confidence", "")),
                        cwe=str(item.get("issue_cwe", {}).get("id"))
                        if item.get("issue_cwe")
                        else None,
                        fingerprint=self._fingerprint(rel_file, issue, context),
                        remediation=self._remediation_for_issue(issue),
                        evidence=self._redact_evidence(description or "")[:240],
                        category=self._category_for_issue(issue),
                        impact=self._impact_for_issue(issue, context),
                        false_positive_likelihood=self._false_positive_likelihood(context, self._normalize_confidence(item.get("issue_confidence", ""))),
                        affected_files=[rel_file],
                    )
                )

        except Exception as exc:
            findings.append(
                SecurityFinding(
                    file="system",
                    line=0,
                    severity=FindingSeverity.info,
                    issue="Bandit unavailable",
                    description=str(exc),
                )
            )

        return findings

    def _simple_secret_scan(self, project_dir: Path) -> list[SecurityFinding]:
        assignment_pattern = re.compile(
            r"(?P<key>(?:api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|password|private[_-]?key|token|secret))"
            r"\s*[:=]\s*(?P<quote>['\"]?)(?P<value>[^'\"\s,#}]+)",
            re.IGNORECASE,
        )
        private_key_pattern = re.compile(r"PRIVATE KEY", re.IGNORECASE)
        findings: list[SecurityFinding] = []

        allowed_suffixes = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".env",
            ".txt",
            ".json",
            ".yml",
            ".yaml",
            ".properties",
        }

        for path in project_dir.rglob("*"):
            if not path.is_file():
                continue

            if path.suffix.lower() not in allowed_suffixes:
                continue

            rel_file = str(path.relative_to(project_dir)).replace("\\", "/")

            if self._is_ignored_file(rel_file):
                continue

            try:
                lines = path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).splitlines()
            except Exception:
                continue

            for idx, line in enumerate(lines, 1):
                clean = line.strip()

                if not clean or clean.startswith("#") or clean.startswith("//"):
                    continue

                match = assignment_pattern.search(clean)
                is_private_key = bool(private_key_pattern.search(clean))
                if match or is_private_key:
                    value = match.group("value") if match else clean
                    placeholder = self._looks_like_placeholder(value, clean)
                    context = self._classify_context(rel_file)
                    confidence = self._secret_confidence(value, clean, context, placeholder)
                    severity = self._adjust_severity_for_context(
                        file_path=rel_file,
                        issue="Potential hardcoded secret",
                        severity=self._secret_severity(context, confidence, placeholder),
                    )

                    findings.append(
                        SecurityFinding(
                            file=rel_file,
                            line=idx,
                            severity=severity,
                            context=context,
                            issue="Potential hardcoded secret",
                            description=self._contextual_description(
                                context,
                                "A possible secret, token, API key, or password "
                                "was detected. Severity is adjusted according "
                                "to whether it appears in production, tests, docs, "
                                "examples, CI, Docker, or Kubernetes configuration."
                            ),
                            confidence=confidence,
                            fingerprint=self._fingerprint(rel_file, "Potential hardcoded secret", context),
                            remediation=self._remediation_for_issue("Potential hardcoded secret"),
                            evidence=self._redact_evidence(clean)[:240],
                            category="secret-placeholder" if placeholder else "secrets",
                            impact=self._impact_for_issue("Potential hardcoded secret", context),
                            false_positive_likelihood="high" if placeholder else self._false_positive_likelihood(context, confidence),
                            affected_files=[rel_file],
                        )
                    )

        return findings

    def _relative_file(self, filename: str, project_dir: Path) -> str:
        if not filename:
            return "unknown"

        try:
            return str(Path(filename).relative_to(project_dir)).replace("\\", "/")
        except Exception:
            return str(filename).replace("\\", "/")

    def _normalize_bandit_severity(self, value: str) -> FindingSeverity:
        value = value.lower()

        if value == "high":
            return FindingSeverity.high
        if value == "medium":
            return FindingSeverity.medium
        if value == "low":
            return FindingSeverity.low

        return FindingSeverity.info

    def _normalize_confidence(self, value: str) -> str:
        text = str(value or "").lower()
        if "high" in text:
            return "high"
        if "medium" in text:
            return "medium"
        if "low" in text:
            return "low"
        return "medium"

    def _should_skip_bandit_finding(self, file_path: str, issue: str) -> bool:
        normalized = file_path.replace("\\", "/").lower()
        issue_lower = issue.lower()

        is_test = self._is_test_path(normalized)

        if is_test and issue_lower in {"assert_used", "assert used"}:
            return True

        if "node_modules/" in normalized:
            return True

        if "__pycache__/" in normalized:
            return True

        return False

    def _adjust_severity_for_context(
        self,
        file_path: str,
        issue: str,
        severity: FindingSeverity,
    ) -> FindingSeverity:
        normalized = file_path.replace("\\", "/").lower()
        issue_lower = issue.lower()

        is_test = self._is_test_path(normalized)
        is_docs = self._is_docs_path(normalized)
        is_example = self._is_example_path(normalized)
        is_ci = self._is_ci_path(normalized)
        is_container = self._is_container_config(normalized)
        is_generated = self._is_generated_or_vendor_path(normalized)
        is_api_example = self._is_api_example_path(normalized)
        is_script = normalized.startswith("scripts/")

        if "hardcoded secret" in issue_lower:
            if is_generated:
                return FindingSeverity.info
            if is_test or is_docs or is_example or is_api_example:
                return FindingSeverity.low

            if is_ci:
                return FindingSeverity.low

            if is_container:
                return FindingSeverity.medium

            if is_script:
                return FindingSeverity.medium

            return FindingSeverity.medium

        if "request_without_timeout" in issue_lower:
            if is_test or is_docs or is_example:
                return FindingSeverity.low
            return FindingSeverity.medium

        if is_test:
            return self._cap_severity(severity, FindingSeverity.low)

        if is_docs or is_example or is_ci or is_api_example:
            return self._cap_severity(severity, FindingSeverity.low)

        if is_generated:
            return self._cap_severity(severity, FindingSeverity.info)

        if is_container:
            return self._cap_severity(severity, FindingSeverity.medium)

        return severity

    def _cap_severity(
        self,
        severity: FindingSeverity,
        maximum: FindingSeverity,
    ) -> FindingSeverity:
        order = {
            FindingSeverity.info: 0,
            FindingSeverity.low: 1,
            FindingSeverity.medium: 2,
            FindingSeverity.high: 3,
            FindingSeverity.critical: 4,
        }

        if order[severity] <= order[maximum]:
            return severity

        return maximum

    def _is_test_path(self, value: str) -> bool:
        return any(
            token in value
            for token in [
                "tests/",
                "/tests/",
                "test/",
                "/test/",
                "test_",
                "_test.",
                ".test.",
                "testing/",
            ]
        )

    def _is_docs_path(self, value: str) -> bool:
        return any(
            token in value
            for token in [
                "docs/",
                "docs_src/",
                "/doc/",
                ".md",
                ".rst",
                ".txt",
            ]
        )

    def _is_example_path(self, value: str) -> bool:
        return any(
            token in value
            for token in [
                "examples/",
                "example/",
                "demo/",
                "sample/",
                "tutorial/",
            ]
        )

    def _is_ci_path(self, value: str) -> bool:
        return any(
            token in value
            for token in [
                ".github/",
                ".gitlab-ci",
                "github/workflows",
                "workflows/",
            ]
        )

    def _is_container_config(self, value: str) -> bool:
        return any(
            token in value
            for token in [
                "docker-compose",
                "dockerfile",
                "k8s/",
                "kubernetes/",
                "helm/",
                ".yaml",
                ".yml",
            ]
        )

    def _classify_context(self, file_path: str) -> str:
        normalized = file_path.replace("\\", "/").lower()

        if self._is_test_path(normalized):
            return "test"

        if self._is_docs_path(normalized):
            return "docs"

        if self._is_example_path(normalized):
            return "example"

        if self._is_ci_path(normalized) or self._is_container_config(normalized):
            if self._is_ci_path(normalized):
                return "ci"
            return "config"

        if self._is_generated_or_vendor_path(normalized):
            return "generated/vendor"

        if self._is_api_example_path(normalized):
            return "api_example"

        if self._is_constants_path(normalized):
            return "constants"

        return "production"

    def _contextual_description(self, context: str, description: str) -> str:
        label = context.capitalize()
        text = description or "Security finding detected."
        return f"[{label} context] {text}"

    def _dedupe_findings(self, findings: list[SecurityFinding]) -> list[SecurityFinding]:
        grouped: dict[tuple[str, str, str], SecurityFinding] = {}

        for finding in findings:
            key = (
                finding.file,
                finding.issue,
                finding.context,
            )

            if key not in grouped:
                grouped[key] = finding
                continue

            existing = grouped[key]
            existing.occurrences += max(1, finding.occurrences)
            existing.affected_files = sorted(set(existing.affected_files + finding.affected_files + [finding.file]))
            if finding.line and (not existing.line or finding.line < existing.line):
                existing.line = finding.line
            if finding.evidence and finding.evidence not in existing.evidence:
                existing.evidence = (existing.evidence + " | " + finding.evidence).strip(" | ")[:500]

        return sorted(
            grouped.values(),
            key=lambda item: (
                self._severity_rank(item.severity),
                0 if item.context == "production" else 1,
                item.file,
            ),
            reverse=True,
        )

    def _severity_rank(self, severity: FindingSeverity) -> int:
        return {
            FindingSeverity.info: 0,
            FindingSeverity.low: 1,
            FindingSeverity.medium: 2,
            FindingSeverity.high: 3,
            FindingSeverity.critical: 4,
        }.get(severity, 1)

    def _fingerprint(self, file_path: str, issue: str, context: str) -> str:
        normalized = re.sub(r"\d+", "<n>", f"{context}:{file_path}:{issue}".lower())
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

    def _category_for_issue(self, issue: str) -> str:
        text = issue.lower()
        if "secret" in text or "password" in text or "token" in text:
            return "secrets"
        if "injection" in text or "sql" in text or "shell" in text or "subprocess" in text:
            return "injection"
        if "assert" in text:
            return "test-only"
        if "timeout" in text or "request" in text:
            return "network"
        if "crypto" in text or "hash" in text or "ssl" in text:
            return "cryptography"
        return "security"

    def _remediation_for_issue(self, issue: str) -> str:
        text = issue.lower()
        if "hardcoded secret" in text or "password" in text or "token" in text:
            return "Move secrets to a managed secret store or environment variables, rotate exposed values, and add secret scanning to CI."
        if "subprocess" in text or "shell" in text:
            return "Avoid shell=True, pass arguments as arrays, validate input, and isolate command execution behind reviewed helpers."
        if "sql" in text:
            return "Use parameterized queries or ORM bind parameters and add tests for malicious input."
        if "timeout" in text:
            return "Set explicit network timeouts and test timeout/error paths."
        if "assert" in text:
            return "Avoid relying on assert for runtime validation in production code; raise explicit exceptions instead."
        return "Review the finding in context, add a targeted regression test, and document the accepted remediation or risk decision."

    def _redact_evidence(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(
            r"([A-Za-z0-9_.-]*(?:key|secret|token|password)[A-Za-z0-9_.-]*\s*[:=]\s*['\"]?)([^'\"\s,#}]+)",
            lambda match: match.group(1) + self._mask_secret(match.group(2)),
            text,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"-----BEGIN ([A-Z ]+)-----[\s\S]*", r"-----BEGIN \1-----<redacted>", text)
        return text

    def _mask_secret(self, value: str) -> str:
        if len(value) <= 6:
            return "<redacted>"
        return f"{value[:2]}...{value[-2:]}"

    def _looks_like_placeholder(self, value: str, line: str) -> bool:
        lowered = f"{value} {line}".lower()
        placeholders = [
            "example", "sample", "dummy", "placeholder", "changeme", "change_me",
            "your_", "xxx", "todo", "test", "fake", "redacted", "<", ">",
            "${", "process.env", "os.environ", "env.", "password", "username",
            "localhost", "127.0.0.1", "secret", "token", "apikey", "api_key",
        ]
        return any(token in lowered for token in placeholders) or value.strip() in {"", "''", '""', "none", "null"}

    def _secret_confidence(self, value: str, line: str, context: str, placeholder: bool) -> str:
        known_prefix = bool(re.search(r"\b(ghp_|github_pat_|sk-|xox[baprs]-|AKIA|AIza|ya29\.)", value))
        entropyish = len(value) >= 20 and self._entropy(value) >= 3.2 and bool(re.search(r"[A-Za-z]", value)) and bool(re.search(r"\d", value))
        if placeholder and not (known_prefix or entropyish):
            return "low"
        if context == "production" and (known_prefix or entropyish):
            return "high"
        if context in {"docs", "example", "test", "api_example", "generated/vendor"}:
            return "low"
        return "medium"

    def _secret_severity(self, context: str, confidence: str, placeholder: bool) -> FindingSeverity:
        if placeholder and confidence == "low":
            return FindingSeverity.low
        if context in {"docs", "example", "test", "api_example", "generated/vendor", "constants"}:
            return FindingSeverity.low
        if confidence == "high" and context == "production":
            return FindingSeverity.high
        return FindingSeverity.medium

    def _false_positive_likelihood(self, context: str, confidence: str) -> str:
        if confidence == "high" and context == "production":
            return "low"
        if context in {"docs", "example", "test"} or confidence == "low":
            return "high"
        return "medium"

    def _impact_for_issue(self, issue: str, context: str) -> str:
        text = issue.lower()
        if "secret" in text or "token" in text or "password" in text:
            return "Credential exposure can allow unauthorized access; impact is lower when evidence is a placeholder or non-production sample."
        if "sql" in text or "injection" in text or "shell" in text:
            return "User-controlled input may affect command or query execution paths."
        if "timeout" in text:
            return "Missing timeouts can cause resource exhaustion and unreliable production behavior."
        if context != "production":
            return "Finding is outside production code and should be reviewed with lower urgency."
        return "May increase application risk if reachable in production."

    def _entropy(self, value: str) -> float:
        if not value:
            return 0
        counts = {char: value.count(char) for char in set(value)}
        length = len(value)
        return -sum((count / length) * math.log2(count / length) for count in counts.values())

    def _is_generated_or_vendor_path(self, value: str) -> bool:
        return any(token in value for token in ["vendor/", "generated/", "gen/", "third_party/", "third-party/", "fixtures/"])

    def _is_api_example_path(self, value: str) -> bool:
        return any(token in value for token in ["api-example", "api_examples", "openapi", "swagger", "postman", "insomnia"])

    def _is_constants_path(self, value: str) -> bool:
        return any(token in value for token in ["constants.", "constant.", "defaults.", "settings.", "config."])

    def _is_ignored_file(self, value: str) -> bool:
        return any(
            token in value.lower()
            for token in [
                "node_modules/",
                ".git/",
                "__pycache__/",
                "dist/",
                "build/",
                ".venv/",
                "venv/",
            ]
        )
