from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.security_agent import SecurityAgent  # noqa: E402


def test_secret_taxonomy_reduces_common_false_positives(tmp_path):
    source = tmp_path / "src"
    source.mkdir()
    app = source / "app.py"
    app.write_text(
        "\n".join(
            [
                "def encrypt(password: str) -> None:",
                "    return None",
                "api_key = 'sk-1234567890abcdef1234567890abcdef'",
            ]
        ),
        encoding="utf-8",
    )

    js = source / "config.js"
    js.write_text(
        "\n".join(
            [
                "var secret = this.secret",
                "const password = process.env.DB_PASSWORD",
            ]
        ),
        encoding="utf-8",
    )

    workflow = tmp_path / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text("token: ${{ secrets.GITHUB_TOKEN }}", encoding="utf-8")

    findings = SecurityAgent().run(tmp_path)
    categories = {finding.category for finding in findings}

    assert "auth_parameter" not in categories
    assert "runtime_secret_reference" in categories
    assert "secret_reference" in categories or "ci_secret_reference" in categories
    assert "real_secret_candidate" in categories
    assert not any(
        finding.issue == "Potential hardcoded secret"
        and finding.category in {"runtime_secret_reference", "secret_reference", "ci_secret_reference"}
        for finding in findings
    )
