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


def test_secret_taxonomy_classifies_placeholders_fixtures_ci_and_real_credentials(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)

    (tmp_path / "src" / "auth.py").write_text(
        "\n".join(
            [
                "token = create_verification_code()",
                "password = settings.password",
                "api_key = 'sk-1234567890abcdef1234567890abcdef'",
                "placeholder_secret = 'sk-test-placeholder'",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_auth.py").write_text(
        "password = 'fixture-password'\n",
        encoding="utf-8",
    )
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(
        "token: ${{ secrets.GITHUB_TOKEN }}\n",
        encoding="utf-8",
    )

    findings = SecurityAgent().run(tmp_path)
    by_category = {finding.category: finding for finding in findings}

    assert by_category["real_secret_candidate"].severity.value == "high"
    assert by_category["real_secret_candidate"].confidence == "high"
    assert by_category["placeholder_secret"].severity.value == "low"
    assert by_category["test_fixture_secret"].context == "test"
    assert by_category["ci_secret_reference"].context == "ci"
    assert not any(
        finding.category == "real_secret_candidate" and finding.line in {1, 2}
        for finding in findings
    )
