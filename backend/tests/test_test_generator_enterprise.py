from __future__ import annotations

import sys
from pathlib import Path
from textwrap import dedent

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agents.test_generator import TestGeneratorAgent
from models.schemas import CodeAnalysisResult, CodeFileSummary


def _analysis_for(*paths: str) -> CodeAnalysisResult:
    return CodeAnalysisResult(
        files=[
            CodeFileSummary(path=path, lines=25, functions=[], classes=[], imports=[])
            for path in paths
        ],
        total_files=len(paths),
    )


def _all_test_code(generated) -> str:
    return "\n\n".join(test.test_code for test in generated)


def test_python_generation_emits_real_assertions_and_tracks_unsafe_targets(tmp_path):
    source = tmp_path / "src" / "calculator.py"
    source.parent.mkdir()
    source.write_text(
        dedent(
            """
            import os
            import requests

            def add(left: int, right: int = 1) -> int:
                return left + right

            def normalize_name(name: str) -> str:
                if not name:
                    raise ValueError("name is required")
                return name.strip().lower()

            def read_api_token() -> str:
                return os.environ["API_TOKEN"]

            def get(url: str):
                return requests.get(url)

            class NeedsFixture:
                def __init__(self, endpoint: str):
                    self.endpoint = endpoint

                def request(self):
                    return requests.get(self.endpoint)
            """
        ).strip()
    )

    agent = TestGeneratorAgent()
    generated = agent.run(tmp_path, _analysis_for("src/calculator.py"))
    code = _all_test_code(generated)

    assert generated
    assert "pytest.skip" not in code
    assert "assert True" not in code
    assert "assertTrue(true)" not in code
    assert "expect(true)" not in code
    assert "patch.object(target_module.os, 'environ', {}) as" not in code
    assert "pytest.raises" in code
    assert "assert result" in code or "assert response" in code
    assert "NeedsFixture.request" in {
        item["target"] for item in agent.last_generation_metadata["needs_human_test_design"]
    }
    for test in generated:
        compile(test.test_code, test.file, "exec")


def test_python_web_generation_detects_fastapi_and_flask_clients(tmp_path):
    fastapi_app = tmp_path / "api.py"
    fastapi_app.write_text(
        dedent(
            """
            from fastapi import FastAPI

            app = FastAPI()

            @app.get("/health")
            def health():
                return {"status": "ok"}
            """
        ).strip()
    )
    flask_app = tmp_path / "web.py"
    flask_app.write_text(
        dedent(
            """
            from flask import Flask

            app = Flask(__name__)

            @app.route("/status")
            def status():
                return {"status": "ok"}
            """
        ).strip()
    )

    generated = TestGeneratorAgent().run(tmp_path, _analysis_for("api.py", "web.py"))
    code = _all_test_code(generated)

    assert "from fastapi.testclient import TestClient" in code
    assert "app.test_client()" in code
    assert "assert response.status_code < 500" in code


def test_javascript_generation_detects_express_and_avoids_fake_export_tests(tmp_path):
    package_json = tmp_path / "package.json"
    package_json.write_text('{"dependencies":{"express":"^4.18.0"},"devDependencies":{"jest":"^29.0.0"}}')
    app_file = tmp_path / "app.js"
    app_file.write_text(
        dedent(
            """
            const express = require("express");
            const app = express();

            app.get("/health", (_req, res) => res.json({ status: "ok" }));

            module.exports = app;
            """
        ).strip()
    )

    generated = TestGeneratorAgent().run(tmp_path, CodeAnalysisResult())
    code = _all_test_code(generated)

    assert "supertest" in code
    assert "request(app).get('/health')" in code
    assert "expect(typeof 'send').toBe('string')" not in code
    assert "expect(true)" not in code


def test_java_generation_detects_spring_boot_and_mockmvc(tmp_path):
    source_dir = tmp_path / "src" / "main" / "java" / "com" / "example"
    source_dir.mkdir(parents=True)
    (source_dir / "DemoApplication.java").write_text(
        dedent(
            """
            package com.example;

            import org.springframework.boot.autoconfigure.SpringBootApplication;

            @SpringBootApplication
            public class DemoApplication {}
            """
        ).strip()
    )
    (source_dir / "HealthController.java").write_text(
        dedent(
            """
            package com.example;

            import org.springframework.web.bind.annotation.GetMapping;
            import org.springframework.web.bind.annotation.RestController;

            @RestController
            public class HealthController {
                @GetMapping("/health")
                public String health() {
                    return "ok";
                }
            }
            """
        ).strip()
    )

    generated = TestGeneratorAgent().run(tmp_path, CodeAnalysisResult())
    code = _all_test_code(generated)

    assert "@SpringBootTest" in code
    assert "contextLoads()" in code
    assert "MockMvc" in code
    assert "mockMvc.perform(get(\"/health\"))" in code
    assert "assertTrue(true)" not in code
