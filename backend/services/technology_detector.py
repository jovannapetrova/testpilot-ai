import json
import re
from pathlib import Path


class TechnologyDetector:
    def detect(self, project_dir: Path) -> dict:
        files = [
            p for p in project_dir.rglob("*")
            if p.is_file() and not self._is_ignored_path(p, project_dir)
        ]
        names = {p.name.lower() for p in files}
        rel_paths = {self._rel(p, project_dir).lower() for p in files}
        suffixes = [p.suffix.lower() for p in files]

        languages = {
            "python": suffixes.count(".py"),
            "javascript": suffixes.count(".js") + suffixes.count(".jsx"),
            "typescript": suffixes.count(".ts") + suffixes.count(".tsx"),
            "java": suffixes.count(".java"),
            "csharp": suffixes.count(".cs"),
            "cpp": suffixes.count(".cpp") + suffixes.count(".hpp") + suffixes.count(".h"),
            "go": suffixes.count(".go"),
            "php": suffixes.count(".php"),
            "ruby": suffixes.count(".rb"),
            "rust": suffixes.count(".rs"),
            "elixir": suffixes.count(".ex") + suffixes.count(".exs"),
        }

        primary_language = (
            max(languages, key=languages.get)
            if any(languages.values())
            else "unknown"
        )

        frameworks = []
        build_tools = []

        if "requirements.txt" in names or "pyproject.toml" in names:
            build_tools.append("Python packaging")

        if "package.json" in names:
            build_tools.append("Node package manager")

        if "pom.xml" in names:
            build_tools.append("Maven")

        if "build.gradle" in names or "build.gradle.kts" in names:
            build_tools.append("Gradle")

        if "go.mod" in names:
            build_tools.append("Go modules")

        if "cargo.toml" in names:
            build_tools.append("Cargo")

        if "gemfile" in names:
            build_tools.append("Bundler")

        if "composer.json" in names:
            build_tools.append("Composer")

        if any(name.endswith(".csproj") or name.endswith(".sln") for name in names):
            build_tools.append(".NET")

        text_blobs = self._read_small_files(files)
        package_info = self._package_dependency_signals(files)
        production_files = [p for p in files if self._is_production_source(p, project_dir)]
        framework_confidence: dict[str, str] = {}

        # -----------------------
        # Framework detection
        # -----------------------

        if "fastapi" in text_blobs or self._contains_code(production_files, "FastAPI("):
            frameworks.append("FastAPI")
            framework_confidence["FastAPI"] = "high" if self._contains_code(production_files, "FastAPI(") else "medium"

        if "flask" in text_blobs or self._contains_code(production_files, "Flask("):
            frameworks.append("Flask")
            framework_confidence["Flask"] = "high" if self._contains_code(production_files, "Flask(") else "medium"

        if "django" in text_blobs or "manage.py" in names or any("settings.py" in p for p in rel_paths):
            frameworks.append("Django")

        if "pygame" in text_blobs:
            frameworks.append("Pygame")

        react_score = self._react_score(production_files, project_dir, package_info)
        if react_score:
            frameworks.append("React")
            framework_confidence["React"] = "high" if react_score >= 3 else "medium"

        express_score = self._express_score(production_files, project_dir, package_info)
        if express_score >= 3:
            frameworks.append("Express")
            framework_confidence["Express"] = "high" if express_score >= 4 else "medium"

        redux_score = self._redux_score(production_files, package_info)
        if redux_score:
            frameworks.append("Redux")
            framework_confidence["Redux"] = "high" if redux_score >= 2 else "medium"

        if "spring-boot" in text_blobs or "springframework" in text_blobs or self._contains_code(production_files, "@SpringBootApplication"):
            frameworks.append("Spring Boot")
            framework_confidence["Spring Boot"] = "high" if self._contains_code(production_files, "@SpringBootApplication") else "medium"

        framework_signals = {
            "GraphQL": ["graphql", "apollo-server", "graphene", ".graphql"],
            "NestJS": ["@nestjs", "nestjs"],
            "Next.js": ["next.config", "/next/"],
            "Vue": ["vue", ".vue"],
            "Angular": ["@angular", "angular.json"],
            "Svelte": ["svelte", "svelte.config"],
            ".NET": ["microsoft.aspnetcore", ".csproj", ".sln"],
            "Laravel": ["laravel/framework", "artisan"],
            "Ruby on Rails": ["rails", "config/routes.rb"],
            "Phoenix": ["phoenix", "mix.exs"],
            "Go HTTP": ["net/http", "gin-gonic", "fiber"],
            "Rust Web": ["actix-web", "rocket", "axum"],
        }

        haystack = "\n".join([text_blobs, "\n".join(rel_paths)])
        for framework, signals in framework_signals.items():
            if any(signal in haystack for signal in signals):
                frameworks.append(framework)

        frameworks = sorted(set(frameworks))
        build_tools = sorted(set(build_tools))

        return {
            "primary_language": primary_language,
            "languages": languages,
            "frameworks": frameworks,
            "build_tools": build_tools,
            "project_category": self._project_category(
                files,
                text_blobs,
                frameworks,
                primary_language,
            ),
            "total_files": len(files),
            "has_docker": (
                "dockerfile" in names
                or "docker-compose.yml" in names
                or "compose.yml" in names
            ),
            "has_readme": any(name.startswith("readme") for name in names),
            "has_tests": any(
                "test" in p.name.lower() or "tests" in str(p).lower()
                for p in files
            ),
            "repository_shape": self._repository_shape(rel_paths),
            "entrypoints": self._entrypoints(rel_paths),
            "framework_confidence": framework_confidence,
            "package_boundaries": self._package_boundaries(files, project_dir),
        }

    def _project_category(
        self,
        files: list[Path],
        text_blobs: str,
        frameworks: list[str],
        language: str,
    ) -> str:

        names = {p.name.lower() for p in files}

        if "GraphQL" in frameworks:
            return "graphql_api"

        # Frontend
        if (
            "React" in frameworks
            or "Vue" in frameworks
            or "Angular" in frameworks
            or "Next.js" in frameworks
            or "Svelte" in frameworks
            or any(p.suffix.lower() in [".jsx", ".tsx"] for p in files)
        ):
            return "frontend"

        # Web APIs
        if any(
            framework in frameworks
            for framework in [
                "FastAPI",
                "Flask",
                "Django",
                "Express",
                "Spring Boot",
                "NestJS",
                ".NET",
                "Laravel",
                "Ruby on Rails",
                "Phoenix",
                "Go HTTP",
                "Rust Web",
            ]
        ):
            return "web_api"

        # Reusable libraries
        if any(
            filename in names
            for filename in [
                "setup.py",
                "pyproject.toml",
                "requirements.txt",
                "cargo.toml",
                "go.mod",
                "gemfile",
            ]
        ):
            return "library"

        # CLI
        if any(
            keyword in text_blobs
            for keyword in [
                "click",
                "argparse",
                "typer",
                "fire",
            ]
        ):
            return "cli"

        # Desktop UI
        if "Pygame" in frameworks:
            return "desktop_ui"

        # ML / Data
        if any(
            keyword in text_blobs
            for keyword in [
                "numpy",
                "pandas",
                "sklearn",
                "tensorflow",
                "keras",
                "torch",
                "xgboost",
            ]
        ):
            return "data_ml"

        # Generic backend/service
        if language in [
            "python",
            "java",
            "javascript",
            "typescript",
            "go",
            "php",
            "csharp",
            "go",
            "rust",
            "ruby",
            "elixir",
        ]:
            return "backend_service"

        return "generic"

    def _read_small_files(self, files: list[Path]) -> str:
        content = []

        interesting = {
            "requirements.txt",
            "package.json",
            "pom.xml",
            "build.gradle",
            "build.gradle.kts",
            "pyproject.toml",
            "setup.py",
            "go.mod",
            "cargo.toml",
            "gemfile",
            "composer.json",
            "mix.exs",
        }

        for path in files:
            if path.name.lower() in interesting:
                try:
                    content.append(
                        path.read_text(
                            encoding="utf-8",
                            errors="ignore",
                        ).lower()
                    )
                except Exception:
                    pass

        return "\n".join(content)

    def _is_ignored_path(self, path: Path, base: Path) -> bool:
        rel = self._rel(path, base).lower()
        return any(
            token in rel
            for token in [
                "node_modules/",
                ".git/",
                "__pycache__/",
                ".venv/",
                "venv/",
                "dist/",
                "build/",
                "target/",
                ".gradle/",
            ]
        )

    def _rel(self, path: Path, base: Path) -> str:
        try:
            return str(path.relative_to(base)).replace("\\", "/")
        except Exception:
            return str(path).replace("\\", "/")

    def _contains_code(self, files: list[Path], needle: str) -> bool:
        suffixes = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rb", ".php", ".rs", ".ex"}
        for path in files[:600]:
            if path.suffix.lower() not in suffixes:
                continue
            try:
                if needle.lower() in path.read_text(encoding="utf-8", errors="ignore").lower():
                    return True
            except Exception:
                continue
        return False

    def _package_dependency_signals(self, files: list[Path]) -> dict[str, set[str]]:
        dependencies: set[str] = set()
        for path in files:
            if path.name.lower() != "package.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                continue
            for key in ["dependencies", "devDependencies", "peerDependencies", "optionalDependencies"]:
                if isinstance(data.get(key), dict):
                    dependencies.update(str(name).lower() for name in data[key].keys())
        return {"node_dependencies": dependencies}

    def _is_production_source(self, path: Path, base: Path) -> bool:
        rel = self._rel(path, base).lower()
        if path.suffix.lower() not in {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".rb", ".php", ".rs", ".ex"}:
            return False
        return not any(
            token in rel
            for token in [
                "tests/", "/tests/", "__tests__/", "test/", "/test/", ".test.",
                ".spec.", "docs/", "docs_src/", "examples/", "example/",
                "demo/", "tutorial/", "sample/", "scripts/",
            ]
        )

    def _express_score(self, files: list[Path], base: Path, package_info: dict[str, set[str]]) -> int:
        deps = package_info.get("node_dependencies", set())
        score = 1 if "express" in deps else 0
        saw_import = False
        saw_app = False
        saw_export = False
        route_pattern = re.compile(r"\b(?:app|router)\.(?:get|post|put|patch|delete|use)\s*\(", re.IGNORECASE)
        for path in files[:500]:
            if path.suffix.lower() not in {".js", ".jsx", ".ts", ".tsx"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            saw_import = saw_import or bool(re.search(r"require\(['\"]express['\"]\)|from\s+['\"]express['\"]", text))
            saw_app = saw_app or "express()" in text or "express.Router(" in text or route_pattern.search(text) is not None
            saw_export = saw_export or bool(re.search(r"module\.exports|exports\.|export\s+default|export\s+\{", text))
        return score + int(saw_import) + int(saw_app) + int(saw_export)

    def _react_score(self, files: list[Path], base: Path, package_info: dict[str, set[str]]) -> int:
        deps = package_info.get("node_dependencies", set())
        score = 1 if "react" in deps else 0
        saw_component = False
        saw_import = False
        for path in files[:500]:
            if path.suffix.lower() not in {".jsx", ".tsx", ".js", ".ts"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            saw_import = saw_import or bool(re.search(r"from\s+['\"]react['\"]|require\(['\"]react['\"]\)", text))
            saw_component = saw_component or bool(re.search(r"export\s+(?:default\s+)?(?:function|const)\s+[A-Z][A-Za-z0-9_]*|<[A-Z][A-Za-z0-9_]*[\s/>]", text))
        return score + int(saw_import) + int(saw_component)

    def _redux_score(self, files: list[Path], package_info: dict[str, set[str]]) -> int:
        deps = package_info.get("node_dependencies", set())
        score = 1 if "redux" in deps or "@reduxjs/toolkit" in deps else 0
        for path in files[:500]:
            if path.suffix.lower() not in {".js", ".jsx", ".ts", ".tsx"}:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if re.search(r"createSlice|configureStore|combineReducers|switch\s*\(\s*action\.type\s*\)", text):
                return score + 1
        return score

    def _package_boundaries(self, files: list[Path], base: Path) -> list[dict[str, str]]:
        boundaries = []
        for path in files:
            if path.name.lower() in {"package.json", "pyproject.toml", "pom.xml", "build.gradle", "build.gradle.kts", "go.mod", "cargo.toml"}:
                boundaries.append({"manifest": self._rel(path, base), "directory": self._rel(path.parent, base)})
        return boundaries[:25]

    def _repository_shape(self, rel_paths: set[str]) -> dict:
        return {
            "has_src": any(path.startswith("src/") or "/src/" in path for path in rel_paths),
            "has_app": any(path.startswith("app/") or "/app/" in path for path in rel_paths),
            "has_tests_dir": any(path.startswith("tests/") or "/tests/" in path for path in rel_paths),
            "has_ci": any(path.startswith(".github/") or "workflows/" in path for path in rel_paths),
            "has_infra": any(token in path for path in rel_paths for token in ["dockerfile", "docker-compose", "k8s/", "helm/"]),
            "looks_monorepo": sum(1 for path in rel_paths if path.endswith("package.json") or path.endswith("pyproject.toml") or path.endswith("pom.xml")) > 1,
        }

    def _entrypoints(self, rel_paths: set[str]) -> list[str]:
        candidates = [
            "main.py",
            "app.py",
            "manage.py",
            "src/main.ts",
            "src/main.js",
            "server.js",
            "index.js",
            "cmd/",
            "src/main/java/",
            "Program.cs",
        ]
        return sorted({path for path in rel_paths if any(path == item.lower() or path.startswith(item.lower()) for item in candidates)})[:12]
