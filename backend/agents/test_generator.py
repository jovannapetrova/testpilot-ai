from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from models.schemas import CodeAnalysisResult, GeneratedTest
from agents.project_detector import ProjectDetectorAgent
from services.strategy_factory import StrategyFactory


@dataclass
class PythonFunctionInfo:
    name: str
    args: list[dict[str, Any]]
    defaults: dict[str, str]
    returns: list[str]
    raises: list[str]
    decorators: list[str]
    imports: set[str]
    calls: set[str]
    docstring: str | None
    is_async: bool
    is_method: bool
    class_name: str | None
    category: str
    signature_key: str
    class_can_instantiate: bool = False
    class_init_args: list[dict[str, Any]] = field(default_factory=list)
    is_property: bool = False


@dataclass
class JsModuleInfo:
    exports: list[str] = field(default_factory=list)
    functions: list[dict[str, Any]] = field(default_factory=list)
    express: dict[str, Any] | None = None
    react_components: list[str] = field(default_factory=list)
    redux: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    pure_exports: list[dict[str, Any]] = field(default_factory=list)
    node_prototype_methods: list[dict[str, Any]] = field(default_factory=list)
    module_system: str = "commonjs"


@dataclass
class JavaClassInfo:
    package: str | None
    class_name: str
    annotations: list[str]
    fields: list[dict[str, str]]
    methods: list[dict[str, Any]]
    constructors: list[dict[str, Any]]
    controller_routes: list[dict[str, str]]
    is_spring_boot: bool
    is_controller: bool
    is_pojo: bool
    kind: str = "class"
    is_abstract: bool = False


class TestGeneratorAgent:
    name = "Test Generator Agent"

    def __init__(self):
        self.project_detector = ProjectDetectorAgent()
        self.strategy_factory = StrategyFactory()
        self.last_generation_metadata = self._empty_generation_metadata()

    def run(self, project_dir: Path, code_analysis: CodeAnalysisResult) -> list[GeneratedTest]:
        self.last_generation_metadata = self._empty_generation_metadata()
        project_profile = self.project_detector.run(project_dir)
        strategy = self.strategy_factory.select_test_strategy(project_profile)

        generated: list[GeneratedTest] = []
        generated.extend(self._generate_python_tests(project_dir, code_analysis, strategy.name))
        generated.extend(self._generate_javascript_tests(project_dir, strategy.name))
        generated.extend(self._generate_java_tests(project_dir, strategy.name))

        deduped = self._dedupe_generated_tests(generated)
        self.last_generation_metadata["executable_tests"] = len([test for test in deduped if test.test_type != "smoke"])
        self.last_generation_metadata["smoke_tests"] = len([test for test in deduped if test.test_type == "smoke"])
        self.last_generation_metadata["needs_review_tests"] = 0
        return deduped

    def _empty_generation_metadata(self) -> dict[str, Any]:
        return {
            "executable_tests": 0,
            "smoke_tests": 0,
            "needs_review_tests": 0,
            "needs_human_test_design": [],
            "skipped_generation_reasons": {},
        }

    # ------------------------------------------------------------------
    # Python / FastAPI / Flask
    # ------------------------------------------------------------------

    def _generate_python_tests(
        self,
        project_dir: Path,
        code_analysis: CodeAnalysisResult,
        strategy_name: str,
    ) -> list[GeneratedTest]:
        results: list[GeneratedTest] = []
        used_output_files: set[str] = set()

        files = [
            file for file in code_analysis.files
            if file.path.endswith(".py")
            and not self._is_test_file(file.path)
            and not self._is_ignored_path(file.path)
        ]
        files = sorted(files, key=lambda item: self._priority_score(item.path))[:45]

        for file in files:
            source_path = project_dir / file.path
            if not source_path.exists():
                continue

            code = self._read_text(source_path)
            if not code:
                continue

            module_name = file.path.replace("\\", "/").removesuffix(".py").replace("/", ".")
            functions = self._filter_python_functions_for_generation(
                self._discover_python_functions(code)
            )
            web_app = self._detect_python_web_app(code)

            if not functions and not web_app:
                continue

            lines = self._python_header(file.path, module_name, strategy_name)
            used_test_names: set[str] = set()
            reasons: list[str] = []
            test_type = "unit"
            framework = None
            target_kind = "module"
            needs_review = False
            confidence = "medium"

            if web_app:
                framework = web_app["framework"]
                test_type = "api"
                target_kind = "route"
                confidence = "high" if web_app["routes"] else "medium"
                lines.extend(self._python_web_tests(web_app, used_test_names))
                reasons.append(
                    f"Detected {framework} app and generated client-based route checks that assert responses do not fail with 5xx status codes."
                )

            emitted_python_targets: set[str] = set()
            for fn in functions[:12]:
                identity = self._python_generation_identity(fn)
                if identity in emitted_python_targets:
                    continue
                emitted_python_targets.add(identity)
                test_lines, fn_reason, fn_needs_review = self._python_function_tests(fn, used_test_names)
                if not test_lines:
                    continue
                lines.extend(test_lines)
                reasons.append(fn_reason)

            if len(lines) <= 16:
                continue

            output_name = self._unique_output_name(
                f"tests/test_{Path(file.path).stem}_generated.py",
                used_output_files,
            )

            results.append(
                GeneratedTest(
                    file=output_name,
                    target=file.path,
                    test_code="\n".join(lines),
                    rationale=self._rationale(
                        "Test Generator v2",
                        reasons,
                        needs_review,
                    ),
                    test_type=test_type,
                    confidence=confidence,
                    needs_review=needs_review,
                    framework=framework,
                    target_kind=target_kind,
                    assertion_strength="high" if test_type == "api" else "medium",
                    execution_safety="safe" if not needs_review else "mocked_or_boundary",
                    generated_test_category=test_type,
                )
            )

        return results

    def _python_header(self, source_file: str, module_name: str, strategy_name: str) -> list[str]:
        return [
            "import inspect",
            "from unittest.mock import MagicMock, patch",
            "import pytest",
            "",
            f"# Generated tests for {source_file}",
            f"# Strategy: Test Generator v2 layered strategy ({strategy_name})",
            "",
            "try:",
            f"    import {module_name} as target_module",
            "except Exception:",
            "    target_module = None",
            "",
            "def _target_module():",
            "    assert target_module is not None",
            "    return target_module",
            "",
        ]

    def _python_function_tests(
        self,
        fn: PythonFunctionInfo,
        used_test_names: set[str],
    ) -> tuple[list[str], str, bool]:
        lines: list[str] = []
        safe_name = self._python_safe_test_subject(fn)

        if fn.is_property:
            self._record_human_test_design(fn, "Property access may execute project-specific logic and needs an object fixture.")
            return (
                [],
                f"{self._python_display_name(fn)} is a property; generated one review TODO instead of treating it as a normal function.",
                True,
            )

        if fn.is_async:
            self._record_human_test_design(fn, "Async function needs event-loop and async fixture design.")
            return (
                [],
                f"{self._python_display_name(fn)} is async; generated a reviewable contract because project async test setup is unknown.",
                True,
            )

        if self._python_is_network_risk(fn):
            if self._python_patch_targets(fn):
                lines.extend(self._python_mock_test(fn, used_test_names))
                return (
                    lines,
                    f"{self._python_display_name(fn)} looks like network/client API code; generated mock-based coverage and avoided real runtime calls.",
                    True,
                )

            self._record_human_test_design(fn, "Likely network/API method; valid transport/client fixtures are required.")
            return (
                [],
                f"{self._python_display_name(fn)} looks like network/client API code; generated review TODO instead of calling it directly.",
                True,
            )

        if fn.is_method:
            if fn.class_can_instantiate:
                method_lines = self._python_class_method_tests(fn, used_test_names)
                if not method_lines:
                    self._record_human_test_design(fn, "Class method requires domain fixtures for meaningful assertions.")
                    return (
                        [],
                        f"{self._python_display_name(fn)} needs domain-specific assertions and was not emitted as a placeholder.",
                        True,
                    )
                lines.extend(method_lines)
                return (
                    lines,
                    f"{self._python_display_name(fn)} belongs to a safely instantiable class; generated class-qualified method checks.",
                    self._python_method_needs_review(fn),
                )

            self._record_human_test_design(fn, "Class method requires a safe object fixture or constructor arguments.")
            return (
                lines,
                f"{self._python_display_name(fn)} is a class method; generated one class-qualified review TODO instead of fabricating an instance.",
                True,
            )

        if self._python_needs_mocks(fn):
            if not self._python_patch_targets(fn):
                self._record_human_test_design(fn, "External dependency calls were detected but no safe module-level patch target could be inferred.")
                return (
                    [],
                    f"{self._python_display_name(fn)} requires mocks but no safe patch target was inferred.",
                    True,
                )
            lines.extend(self._python_mock_test(fn, used_test_names))
            return (
                lines,
                f"{self._python_display_name(fn)} calls external resources; generated mock-based pytest coverage for requests/files/env/database-style calls.",
                True,
            )

        if self._python_is_simple_pure_function(fn):
            cases = self._python_cases_for_function(fn)
            if cases:
                test_name = self._unique_test_name(f"test_{safe_name}_is_deterministic_for_representative_inputs", used_test_names)
                lines.extend([
                    "",
                    "@pytest.mark.parametrize('args', [",
                ])
                for case in cases[:4]:
                    lines.append(f"    {case},")
                lines.extend([
                    "])",
                    f"def {test_name}(args):",
                    "    module = _target_module()",
                    f"    fn = getattr(target_module, '{fn.name}', None)",
                    "    first = fn(*args)",
                    "    second = fn(*args)",
                    "    assert first == second",
                    "    assert first is None or first is not Ellipsis",
                    "",
                ])

                if fn.raises:
                    lines.extend(self._python_raises_tests(fn, used_test_names))

                return (
                    lines,
                    f"{self._python_display_name(fn)} appears side-effect-light; generated parametrized deterministic assertions plus boundary cases from signature hints.",
                    False,
                )

        if fn.raises:
            lines.extend(self._python_raises_tests(fn, used_test_names))
            return (
                lines,
                f"{self._python_display_name(fn)} raises explicit exceptions; generated pytest.raises-style boundary coverage while avoiding unsafe runtime assumptions.",
                True,
            )

        self._record_human_test_design(fn, "Function depends on domain-specific inputs or runtime state that cannot be inferred safely.")
        return (
            [],
            f"{self._python_display_name(fn)} could not be executed safely from static analysis; generated a reviewable test with clear reason.",
            True,
        )

    def _python_review_todo(
        self,
        fn: PythonFunctionInfo,
        used_test_names: set[str],
        reason: str,
    ) -> list[str]:
        self._record_human_test_design(fn, reason)
        return []

    def _python_mock_test(self, fn: PythonFunctionInfo, used_test_names: set[str]) -> list[str]:
        test_name = self._unique_test_name(
            f"test_{self._python_safe_test_subject(fn)}_uses_external_dependencies_with_mocks",
            used_test_names,
        )
        patches = self._python_patch_targets(fn)
        args = self._python_default_args(fn)
        target_expr = self._python_callable_expression(fn)

        lines = [
            "",
            f"def {test_name}():",
            "    module = _target_module()",
            f"    fn = {target_expr}",
            "    assert callable(fn)",
        ]

        if not patches:
            self._record_human_test_design(fn, "External dependencies were detected but no valid mock patch target could be inferred.")
            return []

        context_parts = []
        mock_index = 0
        mock_names = []
        for patch_target in patches:
            if patch_target["creates_mock"]:
                mock_name = f"mock_{mock_index}"
                context_parts.append(f"{patch_target['expr']} as {mock_name}")
                mock_names.append(mock_name)
                mock_index += 1
            else:
                context_parts.append(patch_target["expr"])

        context = ", ".join(context_parts)
        lines.extend([
            f"    with {context}:",
        ])
        for mock_name in mock_names:
            lines.extend([
                f"        {mock_name}.return_value = MagicMock()",
                f"        {mock_name}.return_value.__enter__.return_value = {mock_name}.return_value",
                f"        {mock_name}.return_value.json.return_value = {{}}",
                f"        {mock_name}.return_value.status_code = 200",
            ])
        lines.extend([
            f"        result = fn({args})",
            "        assert result is None or result is not Ellipsis",
            "",
        ])
        return lines

    def _python_raises_tests(self, fn: PythonFunctionInfo, used_test_names: set[str]) -> list[str]:
        exception = fn.raises[0] if fn.raises else "Exception"
        if exception in {"Exception", "BaseException"}:
            exception = "Exception"
        test_name = self._unique_test_name(
            f"test_{self._python_safe_test_subject(fn)}_raises_for_invalid_boundary_input",
            used_test_names,
        )
        args = self._python_invalid_args(fn)
        target_expr = self._python_callable_expression(fn)
        return [
            "",
            f"def {test_name}():",
            "    module = _target_module()",
            f"    fn = {target_expr}",
            "    assert callable(fn)",
            f"    with pytest.raises(({exception}, TypeError, ValueError, AssertionError)):",
            f"        fn({args})",
            "",
        ]

    def _python_class_method_tests(
        self,
        fn: PythonFunctionInfo,
        used_test_names: set[str],
    ) -> list[str]:
        safe_name = self._python_safe_test_subject(fn)
        ctor_args = ", ".join(
            self._python_value_for_arg(arg, "normal", fn.class_name or "", index)
            for index, arg in enumerate(fn.class_init_args)
        )
        lines: list[str] = []

        if self._python_is_simple_pure_function(fn) and not self._python_is_network_risk(fn):
            cases = self._python_cases_for_function(fn)
            if cases:
                deterministic_name = self._unique_test_name(
                    f"test_{safe_name}_is_deterministic_for_representative_inputs",
                    used_test_names,
                )
                lines.extend([
                    "@pytest.mark.parametrize('args', [",
                ])
                for case in cases[:3]:
                    lines.append(f"    {case},")
                lines.extend([
                    "])",
                    f"def {deterministic_name}(args):",
                    "    module = _target_module()",
                    f"    cls = getattr(target_module, '{fn.class_name}', None)",
                    f"    instance = cls({ctor_args})",
                    f"    method = getattr(instance, '{fn.name}')",
                    "    first = method(*args)",
                    "    second = method(*args)",
                    "    assert first == second",
                    "",
                ])

        if fn.raises:
            lines.extend(self._python_raises_tests(fn, used_test_names))

        return lines

    def _python_web_tests(self, web_app: dict[str, Any], used_test_names: set[str]) -> list[str]:
        framework = web_app["framework"]
        app_name = web_app["app_name"]
        routes = web_app["routes"][:10]

        lines = [
            "",
            f"def {self._unique_test_name('test_web_application_object_is_exposed', used_test_names)}():",
            "    module = _target_module()",
            f"    app = getattr(target_module, '{app_name}', None)",
            "    assert app is not None",
            "",
        ]

        if framework == "fastapi":
            lines.extend([
                "def _generated_fastapi_client():",
                "    module = _target_module()",
                "    TestClient = pytest.importorskip('fastapi.testclient').TestClient",
                f"    app = getattr(target_module, '{app_name}', None)",
                "    if app is None:",
                "        raise AssertionError('FastAPI app object was not exported')",
                "    return TestClient(app)",
                "",
            ])
            client_factory = "_generated_fastapi_client"

        elif framework == "flask":
            lines.extend([
                "def _generated_flask_client():",
                "    module = _target_module()",
                f"    app = getattr(target_module, '{app_name}', None)",
                "    if app is None or not hasattr(app, 'test_client'):",
                "        raise AssertionError('Flask app object was not exported')",
                "    app.config.update(TESTING=True)",
                "    return app.test_client()",
                "",
            ])
            client_factory = "_generated_flask_client"
        else:
            return lines

        for route in routes:
            path = route["path"]
            if self._route_has_path_params(path):
                self._python_route_todo(route, used_test_names, client_factory)
                continue

            test_name = self._unique_test_name(
                f"test_{route['method']}_{self._route_test_name(path)}_responds_without_server_error",
                used_test_names,
            )
            lines.extend([
                f"def {test_name}():",
                f"    client = {client_factory}()",
                f"    response = client.{route['method']}('{path}')",
                "    assert response.status_code < 500",
                "",
            ])

        return lines

    def _python_route_todo(
        self,
        route: dict[str, str],
        used_test_names: set[str],
        client_factory: str,
    ) -> list[str]:
        self._record_skipped_generation(
            f"{route['method'].upper()} {route['path']}",
            "Route has path parameters; valid representative path values are required.",
        )
        return []

    def _discover_python_functions(self, code: str) -> list[PythonFunctionInfo]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        imports = self._python_imports(tree)
        class_metadata = self._python_class_metadata(tree)
        functions: list[PythonFunctionInfo] = []

        for parent in ast.walk(tree):
            class_name = parent.name if isinstance(parent, ast.ClassDef) else None
            body = parent.body if isinstance(parent, (ast.Module, ast.ClassDef)) else []

            for node in body:
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                if self._ignore_python_function(node.name):
                    continue

                is_method = class_name is not None
                args = self._python_args(node, is_method)
                decorators = [self._ast_name(decorator) for decorator in node.decorator_list]
                class_info = class_metadata.get(class_name or "", {})
                functions.append(
                    PythonFunctionInfo(
                        name=node.name,
                        args=args,
                        defaults=self._python_defaults(node),
                        returns=self._python_return_kinds(node),
                        raises=self._python_raises(node),
                        decorators=decorators,
                        imports=imports,
                        calls=self._python_calls(node),
                        docstring=ast.get_docstring(node),
                        is_async=isinstance(node, ast.AsyncFunctionDef),
                        is_method=is_method,
                        class_name=class_name,
                        category=self._classify_function(node.name),
                        signature_key=self._python_signature_key(node, is_method),
                        class_can_instantiate=bool(class_info.get("can_instantiate", False)),
                        class_init_args=list(class_info.get("init_args", [])),
                        is_property=any(
                            decorator in {"property", "cached_property", "functools.cached_property"}
                            or decorator.endswith(".property")
                            or decorator.endswith(".setter")
                            or decorator.endswith(".deleter")
                            for decorator in decorators
                        ),
                    )
                )

        unique: dict[tuple[str | None, str, str], PythonFunctionInfo] = {}
        for fn in functions:
            unique[(fn.class_name, fn.name, fn.signature_key)] = fn
        return list(unique.values())

    def _filter_python_functions_for_generation(
        self,
        functions: list[PythonFunctionInfo],
    ) -> list[PythonFunctionInfo]:
        filtered = []
        seen_review_keys = set()

        for fn in functions:
            if fn.is_property:
                continue

            if fn.name.startswith("__") and fn.name.endswith("__"):
                if fn.name not in {"__str__", "__repr__", "__eq__"}:
                    continue
                if not fn.is_method or not fn.class_can_instantiate:
                    continue

            if fn.is_method and not fn.class_can_instantiate:
                key = (fn.class_name, fn.name, fn.signature_key)
                if key in seen_review_keys:
                    continue
                seen_review_keys.add(key)

            filtered.append(fn)

        return filtered

    def _python_class_metadata(self, tree: ast.AST) -> dict[str, dict[str, Any]]:
        metadata: dict[str, dict[str, Any]] = {}

        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue

            init_node = next(
                (
                    item for item in node.body
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name == "__init__"
                ),
                None,
            )

            if init_node is None:
                metadata[node.name] = {"can_instantiate": True, "init_args": []}
                continue

            init_args = self._python_args(init_node, True)
            defaults = self._python_defaults(init_node)
            required_args = [arg for arg in init_args if arg["name"] not in defaults]
            metadata[node.name] = {
                "can_instantiate": len(required_args) == 0,
                "init_args": init_args,
            }

        return metadata

    def _python_imports(self, tree: ast.AST) -> set[str]:
        imports: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        return imports

    def _python_args(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> list[dict[str, Any]]:
        args = []
        for arg in node.args.args:
            if is_method and arg.arg in {"self", "cls"}:
                continue
            annotation = self._ast_name(arg.annotation) if arg.annotation else None
            args.append({"name": arg.arg, "annotation": annotation})
        return args

    def _python_signature_key(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_method: bool) -> str:
        args = self._python_args(node, is_method)
        parts = []
        defaults = self._python_defaults(node)
        for arg in args:
            name = arg["name"]
            annotation = arg.get("annotation") or ""
            has_default = name in defaults
            parts.append(f"{name}:{annotation}:{has_default}")
        return "|".join(parts)

    def _python_defaults(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, str]:
        defaults: dict[str, str] = {}
        positional = node.args.args[-len(node.args.defaults):] if node.args.defaults else []
        for arg, value in zip(positional, node.args.defaults):
            defaults[arg.arg] = self._literal_python_value(value)
        return defaults

    def _python_return_kinds(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        kinds = []
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                kinds.append(type(child.value).__name__ if child.value is not None else "None")
        return sorted(set(kinds))

    def _python_raises(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        raises = []
        for child in ast.walk(node):
            if isinstance(child, ast.Raise) and child.exc is not None:
                if isinstance(child.exc, ast.Call):
                    raises.append(self._ast_name(child.exc.func))
                else:
                    raises.append(self._ast_name(child.exc))
        return [item for item in sorted(set(raises)) if item]

    def _python_calls(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
        calls = set()
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                calls.add(self._ast_name(child.func))
        return calls

    def _python_is_simple_pure_function(self, fn: PythonFunctionInfo) -> bool:
        if not fn.args:
            return True
        unsafe_tokens = {
            "requests", "httpx", "open", "os.system", "subprocess", "socket",
            "connect", "execute", "commit", "cursor", "session", "query",
            "save", "delete", "write", "remove", "unlink", "request", "stream",
            "send", "client", "transport",
        }
        joined = " ".join(sorted(fn.calls | fn.imports)).lower()
        return not any(token in joined for token in unsafe_tokens)

    def _python_needs_mocks(self, fn: PythonFunctionInfo) -> bool:
        tokens = " ".join(sorted(fn.calls)).lower()
        return any(
            token in tokens
            for token in [
                "requests", "httpx", "open", "os.environ", "subprocess",
                "connect", "cursor", "execute", "session", "repository", "client",
                "request", "stream", "send", "transport",
            ]
        )

    def _python_is_network_risk(self, fn: PythonFunctionInfo) -> bool:
        risky_names = {
            "get", "post", "put", "patch", "delete", "request", "stream",
            "client", "send", "build_request", "send_handling_auth",
            "send_handling_redirects", "send_single_request", "auth_flow",
            "sync_auth_flow", "async_auth_flow", "handle_request",
            "handle_async_request", "get_environment_proxies",
        }
        lower_name = fn.name.lower()

        if lower_name in risky_names and not self._python_body_proves_pure(fn):
            return True

        tokens = " ".join(sorted(fn.calls | fn.imports)).lower()
        return any(
            token in tokens
            for token in [
                "requests.", "httpx.", "socket.", "urllib.", "httpcore.",
                "transport", "send", "stream", "request", "auth_flow",
            ]
        )

    def _python_body_proves_pure(self, fn: PythonFunctionInfo) -> bool:
        if fn.raises:
            return False

        allowed_calls = {
            "len", "str", "int", "float", "bool", "list", "dict", "tuple", "set",
            "sorted", "sum", "min", "max", "abs", "round", "isinstance",
        }
        meaningful_calls = {call for call in fn.calls if call}
        if meaningful_calls and not meaningful_calls.issubset(allowed_calls):
            return False

        network_imports = {"requests", "httpx", "httpcore", "urllib", "socket"}
        return not bool(fn.imports & network_imports)

    def _python_patch_targets(self, fn: PythonFunctionInfo) -> list[dict[str, Any]]:
        patchable = []
        for call in sorted(fn.calls):
            lower = call.lower()
            if lower.startswith(("requests.", "httpx.", "subprocess.")):
                owner, attr = call.rsplit(".", 1)
                patchable.append({"expr": f"patch.object(target_module.{owner}, '{attr}')", "creates_mock": True})
            elif call in {"Client", "AsyncClient"}:
                patchable.append({"expr": f"patch.object(target_module, '{call}')", "creates_mock": True})
            elif lower in {"request", "send", "stream"}:
                patchable.append({"expr": f"patch.object(target_module, '{call}')", "creates_mock": True})
            elif lower.endswith((".request", ".send", ".stream")):
                owner, attr = call.rsplit(".", 1)
                root = owner.split(".", 1)[0]
                if owner == "self" or root not in fn.imports:
                    continue
                patchable.append({"expr": f"patch.object(target_module.{owner}, '{attr}')", "creates_mock": True})
            elif lower == "open":
                patchable.append({"expr": "patch('builtins.open')", "creates_mock": True})
            elif "os.environ" in lower:
                patchable.append({"expr": "patch.object(target_module.os, 'environ', {})", "creates_mock": False})
        return patchable[:3]

    def _python_cases_for_function(self, fn: PythonFunctionInfo) -> list[str]:
        if not fn.args:
            return ["()"]

        normal = tuple(self._python_value_for_arg(arg, "normal", fn.name, index) for index, arg in enumerate(fn.args))
        boundary = tuple(self._python_value_for_arg(arg, "boundary", fn.name, index) for index, arg in enumerate(fn.args))
        empty = tuple(self._python_value_for_arg(arg, "empty", fn.name, index) for index, arg in enumerate(fn.args))

        cases = []
        seen = set()
        for values in [normal, boundary, empty]:
            rendered = self._python_tuple_literal(values)
            if rendered not in seen:
                seen.add(rendered)
                cases.append(rendered)
        return cases

    def _python_default_args(self, fn: PythonFunctionInfo) -> str:
        return ", ".join(self._python_value_for_arg(arg, "normal", fn.name, index) for index, arg in enumerate(fn.args))

    def _python_invalid_args(self, fn: PythonFunctionInfo) -> str:
        if not fn.args:
            return ""
        return ", ".join("None" for _arg in fn.args)

    def _python_safe_test_subject(self, fn: PythonFunctionInfo) -> str:
        if fn.class_name:
            return self._safe_identifier(f"{fn.class_name}_{fn.name}")
        return self._safe_identifier(fn.name)

    def _python_display_name(self, fn: PythonFunctionInfo) -> str:
        if fn.class_name:
            return f"{fn.class_name}.{fn.name}"
        return fn.name

    def _python_callable_expression(self, fn: PythonFunctionInfo) -> str:
        if not fn.is_method:
            return f"getattr(target_module, '{fn.name}', None)"

        ctor_args = ", ".join(
            self._python_value_for_arg(arg, "normal", fn.class_name or "", index)
            for index, arg in enumerate(fn.class_init_args)
        )
        return (
            f"getattr(getattr(target_module, '{fn.class_name}')({ctor_args}), "
            f"'{fn.name}', None)"
        )

    def _python_generation_identity(self, fn: PythonFunctionInfo) -> str:
        return "::".join([
            fn.class_name or "<module>",
            fn.name,
            fn.signature_key,
        ])

    def _python_method_needs_review(self, fn: PythonFunctionInfo) -> bool:
        return (
            fn.is_async
            or bool(fn.raises)
            or self._python_needs_mocks(fn)
            or self._python_is_network_risk(fn)
            or not self._python_is_simple_pure_function(fn)
        )

    def _python_value_for_arg(
        self,
        arg: dict[str, Any],
        mode: str,
        function_name: str = "",
        index: int = 0,
    ) -> str:
        name = arg["name"].lower()
        annotation = str(arg.get("annotation") or "").lower()
        function_lower = function_name.lower()

        if "divide" in function_lower and index > 0:
            return "1"
        if any(token in annotation for token in ["int", "float"]) or name in {"a", "b", "x", "y", "n", "count", "index", "limit", "offset", "page", "size", "value", "number", "amount", "total"}:
            return "0" if mode != "normal" else "1"
        if any(token in annotation for token in ["str"]) or any(token in name for token in ["text", "name", "email", "title", "label"]):
            return "''" if mode != "normal" else "'test'"
        if any(token in annotation for token in ["list", "sequence", "tuple"]) or any(token in name for token in ["items", "list", "array", "records"]):
            return "[]" if mode != "normal" else "[1, 2, 3]"
        if any(token in annotation for token in ["dict", "mapping"]) or any(token in name for token in ["payload", "data", "config", "body", "json"]):
            return "{}"
        if any(token in annotation for token in ["bool"]) or any(token in name for token in ["flag", "active", "enabled"]):
            return "False" if mode != "normal" else "True"
        if any(token in name for token in ["id", "pk", "uuid"]):
            return "0" if mode != "normal" else "1"
        if any(token in name for token in ["file", "path"]):
            return "''" if mode != "normal" else "'test.txt'"
        return "None" if mode == "empty" else "'test'"

    def _python_tuple_literal(self, values: tuple[str, ...]) -> str:
        if len(values) == 1:
            return f"({values[0]},)"
        return f"({', '.join(values)})"

    def _detect_python_web_app(self, code: str) -> dict[str, Any] | None:
        framework = None
        app_name = None
        routes: list[dict[str, str]] = []

        try:
            tree = ast.parse(code)
        except SyntaxError:
            tree = None

        if tree:
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    call_name = self._ast_name(node.value.func)
                    if call_name in {"FastAPI", "fastapi.FastAPI"}:
                        framework = "fastapi"
                    elif call_name in {"Flask", "flask.Flask"}:
                        framework = "flask"

                    if framework:
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                app_name = target.id
                                break

                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        route = self._route_from_python_decorator(decorator)
                        if route:
                            routes.append(route)

        if not framework:
            if "FastAPI(" in code:
                framework = "fastapi"
            elif "Flask(" in code:
                framework = "flask"

        if not app_name:
            match = re.search(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:FastAPI|Flask)\s*\(", code)
            app_name = match.group(1) if match else "app"

        if framework and (routes or app_name):
            return {"framework": framework, "app_name": app_name, "routes": self._dedupe_routes(routes)}
        return None

    def _route_from_python_decorator(self, decorator: ast.AST) -> dict[str, str] | None:
        if not isinstance(decorator, ast.Call):
            return None

        func = decorator.func
        method = None

        if isinstance(func, ast.Attribute):
            method = func.attr.lower()
        elif isinstance(func, ast.Name) and func.id == "route":
            method = "get"

        if method not in {"route", "get", "post", "put", "patch", "delete"}:
            return None

        if not decorator.args or not isinstance(decorator.args[0], ast.Constant):
            return None

        path = decorator.args[0].value
        if not isinstance(path, str):
            return None

        methods = []
        for keyword in decorator.keywords:
            if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple)):
                for item in keyword.value.elts:
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        methods.append(item.value.lower())

        if method == "route":
            method = methods[0] if methods else "get"

        return {"method": method, "path": path}

    # ------------------------------------------------------------------
    # JavaScript / TypeScript / Express / React
    # ------------------------------------------------------------------

    def _generate_javascript_tests(self, project_dir: Path, strategy_name: str) -> list[GeneratedTest]:
        results: list[GeneratedTest] = []
        used_output_files: set[str] = set()

        paths = [
            p for p in project_dir.rglob("*")
            if p.suffix.lower() in {".js", ".jsx", ".ts", ".tsx"}
            and not self._is_test_file(str(p.relative_to(project_dir)))
            and not self._is_ignored_path(str(p.relative_to(project_dir)))
        ]
        paths = sorted(paths, key=lambda p: self._priority_score(str(p.relative_to(project_dir))))[:45]

        for path in paths:
            relative = str(path.relative_to(project_dir)).replace("\\", "/")
            code = self._read_text(path)
            if not code:
                continue

            info = self._analyze_javascript_module(code, path.suffix.lower())
            if not info.exports and not info.express and not info.react_components:
                if info.functions:
                    self._record_skipped_generation(
                        relative,
                        "JavaScript/TypeScript functions were found but no public export was detected.",
                    )
                continue

            test_code, test_type, framework, target_kind, confidence, needs_review, reasons = self._build_javascript_test(
                relative,
                info,
                strategy_name,
            )
            if not test_code.strip():
                self._record_skipped_generation(relative, "No executable JavaScript/TypeScript generated test could be inferred.")
                continue

            output_name = self._unique_output_name(f"tests/{path.stem}.generated.test.js", used_output_files)
            results.append(
                GeneratedTest(
                    file=output_name,
                    target=relative,
                    test_code=test_code,
                    rationale=self._rationale("Test Generator v2", reasons, needs_review),
                    test_type=test_type,
                    confidence=confidence,
                    needs_review=needs_review,
                    framework=framework,
                    target_kind=target_kind,
                    assertion_strength="high" if test_type in {"api", "component"} else "medium",
                    execution_safety="safe",
                    generated_test_category=test_type,
                )
            )

        return results

    def _build_javascript_test(
        self,
        relative: str,
        info: JsModuleInfo,
        strategy_name: str,
    ) -> tuple[str, str, str | None, str, str, bool, list[str]]:
        import_path = "../" + re.sub(r"\.(js|jsx|ts|tsx)$", "", relative.replace("\\", "/"))
        lines = [
            f"// Generated tests for {relative}",
            f"// Strategy: Test Generator v2 layered strategy ({strategy_name})",
            "",
        ]

        reasons: list[str] = []
        needs_review = False
        framework = None
        test_type = "unit"
        target_kind = "module"
        confidence = "medium"

        if info.react_components:
            framework = "react"
            test_type = "component"
            target_kind = "component"
            confidence = "medium"
            lines.extend(self._javascript_react_tests(import_path, info))
            reasons.append("Detected React components and generated React Testing Library render smoke tests.")

        elif info.express and info.express.get("routes"):
            framework = "express"
            test_type = "api"
            target_kind = "route"
            confidence = "high"
            lines.extend(self._javascript_express_tests(import_path, info.express))
            reasons.append("Detected exported Express app/router and generated Jest + Supertest route checks.")

        else:
            if not info.exports:
                return "", "unit", None, "module", "low", False, [
                    "No explicit exports were found; no placeholder Jest test was generated."
                ]
            lines.extend(self._javascript_module_tests(import_path, info))
            if len(lines) <= 3:
                return "", "unit", None, "module", "low", False, [
                    "Exports were detected, but no safely executable behavioral Jest assertions could be inferred."
                ]
            reasons.append("Detected behavioral JavaScript/TypeScript exports and generated Jest assertions for safe library functions.")

        return "\n".join(lines), test_type, framework, target_kind, confidence, needs_review, reasons

    def _javascript_module_tests(self, import_path: str, info: JsModuleInfo) -> list[str]:
        lines = [
            f"const targetModule = require('{import_path}');",
            "",
            "describe('generated behavioral module tests', () => {",
        ]

        emitted = 0
        for item in info.redux.get("reducers", [])[:8]:
            name = item["name"]
            safe = self._safe_identifier(name)
            lines.extend([
                "",
                f"  test('{safe} returns initial state and preserves unknown actions', () => {{",
                f"    const reducer = targetModule['{name}'] || targetModule.default;",
                "    const initial = reducer(undefined, { type: '@@generated/INIT' });",
                "    expect(initial).toBeDefined();",
                "    const existingState = Array.isArray(initial) ? [...initial] : (initial && typeof initial === 'object' ? { ...initial } : initial);",
                "    const unchanged = reducer(existingState, { type: '@@generated/UNKNOWN' });",
                "    expect(unchanged).toEqual(existingState);",
                "  });",
            ])
            emitted += 1

        for item in info.redux.get("action_creators", [])[:8]:
            name = item["name"]
            safe = self._safe_identifier(name)
            args = ", ".join(self._javascript_sample_arg(index) for index in range(item.get("arity", 0)))
            lines.extend([
                "",
                f"  test('{safe} returns a Redux-style action object', () => {{",
                f"    const actionCreator = targetModule['{name}'];",
                f"    const action = actionCreator({args});",
                "    expect(action).toEqual(expect.objectContaining({ type: expect.any(String) }));",
                "  });",
            ])
            emitted += 1

        for item in info.redux.get("redux_core", [])[:6]:
            name = item["name"]
            safe = self._safe_identifier(name)
            if name.lower() == "combinereducers":
                lines.extend([
                    "",
                    f"  test('{safe} combines reducers and preserves unknown actions', () => {{",
                    "    const combineReducers = targetModule.default || targetModule.combineReducers;",
                    "    const reducer = combineReducers({",
                    "      count: (state = 0, action) => action.type === 'inc' ? state + 1 : state",
                    "    });",
                    "    expect(reducer(undefined, { type: '@@generated/INIT' })).toEqual({ count: 0 });",
                    "    expect(reducer({ count: 2 }, { type: '@@generated/UNKNOWN' })).toEqual({ count: 2 });",
                    "  });",
                ])
                emitted += 1
            elif name.lower() == "bindactioncreators":
                lines.extend([
                    "",
                    f"  test('{safe} binds action creators to dispatch', () => {{",
                    "    const bindActionCreators = targetModule.bindActionCreators || targetModule.default;",
                    "    const dispatched = [];",
                    "    const actions = { add: value => ({ type: 'add', value }) };",
                    "    const bound = bindActionCreators(actions, action => dispatched.push(action));",
                    "    bound.add(3);",
                    "    expect(dispatched).toEqual([{ type: 'add', value: 3 }]);",
                    "  });",
                ])
                emitted += 1
            elif name.lower() == "compose":
                lines.extend([
                    "",
                    f"  test('{safe} composes functions right to left', () => {{",
                    "    const compose = targetModule.compose || targetModule.default;",
                    "    const result = compose(value => value * 2, value => value + 3)(4);",
                    "    expect(result).toBe(14);",
                    "  });",
                ])
                emitted += 1
            elif name.lower() == "applymiddleware":
                lines.extend([
                    "",
                    f"  test('{safe} applies middleware around dispatch', () => {{",
                    "    const applyMiddleware = targetModule.applyMiddleware || targetModule.default;",
                    "    const calls = [];",
                    "    const middleware = () => next => action => { calls.push(action.type); return next(action); };",
                    "    const createStore = reducer => {",
                    "      let state = reducer(undefined, { type: '@@init' });",
                    "      return { getState: () => state, dispatch: action => { state = reducer(state, action); return action; } };",
                    "    };",
                    "    const enhancedCreateStore = applyMiddleware(middleware)(createStore);",
                    "    const store = enhancedCreateStore((state = 0, action) => action.type === 'inc' ? state + 1 : state);",
                    "    store.dispatch({ type: 'inc' });",
                    "    expect(calls).toEqual(['inc']);",
                    "    expect(store.getState()).toBe(1);",
                    "  });",
                ])
                emitted += 1
            elif name.lower() in {"createstore", "legacy_createstore"}:
                lines.extend([
                    "",
                    f"  test('{safe} creates a store that dispatches reducer updates', () => {{",
                    f"    const createStore = targetModule['{name}'] || targetModule.default;",
                    "    const reducer = (state = { count: 0 }, action) => action.type === 'inc' ? { count: state.count + 1 } : state;",
                    "    const store = createStore(reducer);",
                    "    expect(store.getState()).toEqual({ count: 0 });",
                    "    store.dispatch({ type: 'inc' });",
                    "    expect(store.getState()).toEqual({ count: 1 });",
                    "  });",
                ])
                emitted += 1

        for item in info.pure_exports[:8]:
            name = item["name"]
            safe = self._safe_identifier(name)
            args = ", ".join(self._javascript_value_for_arg(arg, index) for index, arg in enumerate(item.get("args", [])))
            lines.extend([
                "",
                f"  test('{safe} is deterministic for representative inputs', () => {{",
                f"    const fn = targetModule['{name}'] || targetModule.default;",
                f"    const first = fn({args});",
                f"    const second = fn({args});",
                "    expect(first).toEqual(second);",
                "    expect(first).not.toBeUndefined();",
                "  });",
            ])
            emitted += 1

        for item in info.node_prototype_methods[:6]:
            owner = item["owner"]
            name = item["name"]
            safe = self._safe_identifier(f"{owner}_{name}")
            if name == "status":
                lines.extend([
                    "",
                    f"  test('{safe} sets status code and rejects invalid values', () => {{",
                    "    const subject = Object.create(targetModule);",
                    "    const returned = subject.status(201);",
                    "    expect(returned).toBe(subject);",
                    "    expect(subject.statusCode).toBe(201);",
                    "    expect(() => subject.status('bad')).toThrow();",
                    "    expect(() => subject.status(42)).toThrow();",
                    "  });",
                ])
                emitted += 1
            elif name.lower() in {"createstore", "legacy_createstore"}:
                lines.extend([
                    "",
                    f"  test('{safe} creates a store that dispatches reducer updates', () => {{",
                    f"    const createStore = targetModule['{name}'] || targetModule.default;",
                    "    const reducer = (state = { count: 0 }, action) => action.type === 'inc' ? { count: state.count + 1 } : state;",
                    "    const store = createStore(reducer);",
                    "    expect(store.getState()).toEqual({ count: 0 });",
                    "    store.dispatch({ type: 'inc' });",
                    "    expect(store.getState()).toEqual({ count: 1 });",
                    "  });",
                ])
                emitted += 1

        if not emitted:
            return []

        lines.append("});")
        return lines

    def _javascript_express_tests(self, import_path: str, express: dict[str, Any]) -> list[str]:
        lines = [
            "const request = require('supertest');",
            f"const targetModule = require('{import_path}');",
            "",
            "const app = targetModule.default || targetModule.app || targetModule.router || targetModule;",
            "",
            "describe('generated Express API tests', () => {",
        ]

        for route in express.get("routes", [])[:10]:
            path = route["path"]
            if self._route_has_path_params(path):
                self._record_skipped_generation(
                    f"express:{route['method'].upper()} {path}",
                    "Route has path parameters; valid representative path values are required.",
                )
                continue

            test_name = self._safe_identifier(f"{route['method']} {path} responds without server error")
            lines.extend([
                "",
                f"  test('{test_name}', async () => {{",
                f"    const response = await request(app).{route['method']}('{path}');",
                "    expect(response.status).toBeLessThan(500);",
                "  });",
            ])

        lines.append("});")
        return lines

    def _javascript_react_tests(self, import_path: str, info: JsModuleInfo) -> list[str]:
        default_component = info.react_components[0]
        lines = [
            "import React from 'react';",
            "import { render, screen } from '@testing-library/react';",
            f"import * as targetModule from '{import_path}';",
            "",
            "describe('generated React component tests', () => {",
        ]

        for component in info.react_components[:6]:
            safe = self._safe_identifier(component)
            lines.extend([
                "",
                f"  test('{safe} renders without crashing', () => {{",
                f"    const Component = targetModule.{component} || targetModule.default;",
                "    expect(Component).toBeDefined();",
                "    const { container } = render(<Component />);",
                "    expect(container.firstChild).not.toBeNull();",
                "  });",
            ])

        if not info.react_components:
            lines.extend([
                "",
                "  test('default component renders without crashing', () => {",
                f"    const Component = targetModule.default || targetModule.{default_component};",
                "    expect(Component).toBeDefined();",
                "    const { container } = render(<Component />);",
                "    expect(container.firstChild).not.toBeNull();",
                "  });",
            ])

        lines.append("});")
        return lines

    def _analyze_javascript_module(self, code: str, suffix: str) -> JsModuleInfo:
        info = JsModuleInfo()
        info.module_system = "esm" if re.search(r"\bexport\b|\bimport\b", code) else "commonjs"
        info.exports = self._discover_javascript_exports(code)
        info.functions = self._discover_javascript_functions(code)
        info.express = self._detect_express_app(code)
        info.react_components = self._discover_react_components(code, suffix)
        info.redux = self._discover_redux_patterns(code, info.exports, info.functions)
        info.pure_exports = self._discover_pure_javascript_exports(code, info.exports, info.functions)
        info.node_prototype_methods = self._discover_node_prototype_methods(code)
        return info

    def _discover_javascript_exports(self, code: str) -> list[str]:
        found: list[str] = []
        patterns = [
            r"exports\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=",
            r"module\.exports\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=",
            r"export\s+(?:function|const|let|var|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)",
            r"export\s+default\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)",
        ]
        for pattern in patterns:
            found.extend(re.findall(pattern, code))

        named_exports = re.findall(r"export\s*\{([^}]+)\}", code)
        for group in named_exports:
            for part in group.split(","):
                pieces = re.split(r"\s+as\s+", part.strip())
                name = pieces[-1].strip() if pieces else ""
                if name:
                    found.append(name)

        if re.search(r"module\.exports\s*=", code) or re.search(r"export\s+default", code):
            found.append("default")

        return self._unique_list([item for item in found if item not in {"default.default"}])

    def _discover_javascript_functions(self, code: str) -> list[dict[str, Any]]:
        patterns = [
            r"function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:<[^>{}]+>)?\s*\(([^)]*)\)",
            r"export\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:<[^>{}]+>)?\s*\(([^)]*)\)",
            r"export\s+default\s+function\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*(?:<[^>{}]+>)?\s*\(([^)]*)\)",
            r"exports\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*function\s*(?:[A-Za-z_$][A-Za-z0-9_$]*)?\s*\(([^)]*)\)",
            r"module\.exports\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*function\s*(?:[A-Za-z_$][A-Za-z0-9_$]*)?\s*\(([^)]*)\)",
            r"(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*=>",
            r"(?:const|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*(?:async\s*)?([A-Za-z_$][A-Za-z0-9_$]*)\s*=>",
            r"([A-Za-z_$][A-Za-z0-9_$]*)\s*:\s*function\s*\(([^)]*)\)",
        ]
        found: list[dict[str, Any]] = []
        for pattern in patterns:
            for name, args in re.findall(pattern, code):
                arg_count = 1 if args and re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", args) else self._js_arg_count(args)
                found.append({"name": name, "arity": arg_count})

        unique = {}
        for item in found:
            if item["name"] not in {"if", "for", "while", "switch", "catch"}:
                unique[item["name"]] = item
        return list(unique.values())

    def _discover_redux_patterns(
        self,
        code: str,
        exports: list[str],
        functions: list[dict[str, Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        exported = set(exports)
        reducers: list[dict[str, Any]] = []
        action_creators: list[dict[str, Any]] = []
        redux_core: list[dict[str, Any]] = []

        for fn in functions:
            name = fn["name"]
            if name not in exported and "default" not in exported:
                continue

            if name in {"combineReducers", "createStore", "legacy_createStore", "bindActionCreators", "compose", "applyMiddleware"}:
                redux_core.append(fn)
                continue

            reducer_pattern = (
                rf"(function\s+{re.escape(name)}\s*\([^)]*(state|action)[^)]*\)|"
                rf"(const|let|var)\s+{re.escape(name)}\s*=\s*\([^)]*(state|action)[^)]*\)\s*=>)"
            )
            body_match = re.search(
                rf"{re.escape(name)}[\s\S]{{0,900}}(?:switch\s*\(\s*action\.type\s*\)|case\s+[\"'`][^\"'`]+[\"'`]|return\s+state)",
                code,
            )
            if re.search(reducer_pattern, code) and body_match:
                reducers.append(fn)
                continue

            action_match = re.search(
                rf"{re.escape(name)}[\s\S]{{0,500}}return\s*(?:\(|){{[\s\S]{{0,300}}\btype\s*:",
                code,
            )
            arrow_action_match = re.search(
                rf"{re.escape(name)}\s*=\s*(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*=>\s*(?:\(|){{[\s\S]{{0,300}}\btype\s*:",
                code,
            )
            if action_match or arrow_action_match:
                action_creators.append(fn)

        return {
            "reducers": self._unique_dicts(reducers, "name"),
            "action_creators": self._unique_dicts(action_creators, "name"),
            "redux_core": self._unique_dicts(redux_core, "name"),
        }

    def _discover_pure_javascript_exports(
        self,
        code: str,
        exports: list[str],
        functions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        exported = set(exports)
        pure: list[dict[str, Any]] = []
        for fn in functions:
            name = fn["name"]
            if name not in exported:
                continue
            if name in {"combineReducers", "createStore", "legacy_createStore", "bindActionCreators", "compose", "applyMiddleware"}:
                continue
            if not self._javascript_function_looks_pure(code, name):
                continue
            enriched = dict(fn)
            enriched["args"] = self._javascript_function_args(code, name)
            pure.append(enriched)
        return self._unique_dicts(pure, "name")

    def _javascript_function_looks_pure(self, code: str, name: str) -> bool:
        window = self._javascript_function_window(code, name)
        if not window or "return" not in window:
            return False
        unsafe = [
            "fetch(", "axios", "request(", "http.", "https.", "fs.", "writeFile",
            "readFile", "process.env", "Date.now", "Math.random", "new Date",
            "setTimeout", "setInterval", "document.", "window.", "this.",
        ]
        if any(token in window for token in unsafe):
            return False
        return bool(re.search(r"\breturn\b\s+[^;}{]+[;}]|=>\s*[^({;][^;\n]*", window))

    def _javascript_function_window(self, code: str, name: str) -> str:
        match = re.search(
            rf"(?:export\s+)?(?:default\s+)?function\s+{re.escape(name)}\s*(?:<[^>{{}}]+>)?\s*\([^)]*\)\s*{{|"
            rf"exports\.{re.escape(name)}\s*=\s*function\s*(?:[A-Za-z_$][A-Za-z0-9_$]*)?\s*\([^)]*\)\s*{{|"
            rf"(?:const|let|var)\s+{re.escape(name)}\s*=\s*(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*=>",
            code,
        )
        if not match:
            return ""
        return code[match.start(): match.start() + 900]

    def _javascript_function_args(self, code: str, name: str) -> list[str]:
        patterns = [
            rf"function\s+{re.escape(name)}\s*(?:<[^>{{}}]+>)?\s*\(([^)]*)\)",
            rf"exports\.{re.escape(name)}\s*=\s*function\s*(?:[A-Za-z_$][A-Za-z0-9_$]*)?\s*\(([^)]*)\)",
            rf"(?:const|let|var)\s+{re.escape(name)}\s*=\s*\(([^)]*)\)\s*=>",
            rf"(?:const|let|var)\s+{re.escape(name)}\s*=\s*([A-Za-z_$][A-Za-z0-9_$]*)\s*=>",
        ]
        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                raw = match.group(1)
                if re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", raw.strip()):
                    return [raw.strip()]
                return [part.strip().split(":")[0].strip().lstrip("...") for part in raw.split(",") if part.strip()]
        return []

    def _discover_node_prototype_methods(self, code: str) -> list[dict[str, Any]]:
        methods = []
        for owner, name, args in re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\.([A-Za-z_$][A-Za-z0-9_$]*)\s*=\s*function\s*(?:[A-Za-z_$][A-Za-z0-9_$]*)?\s*\(([^)]*)\)", code):
            if owner in {"res", "req", "app", "router"}:
                methods.append({"owner": owner, "name": name, "args": self._split_args(args)})
        return self._unique_dicts(methods, "name")

    def _detect_express_app(self, code: str) -> dict[str, Any] | None:
        if "express(" not in code and "express.Router(" not in code:
            return None
        if not re.search(r"module\.exports|exports\.|export\s+default|export\s+\{", code):
            return None

        routes = []
        route_pattern = r"(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*[\"'`]([^\"'`]+)[\"'`]"
        for method, path in re.findall(route_pattern, code, flags=re.IGNORECASE):
            routes.append({"method": method.lower(), "path": path})
        routes = self._dedupe_routes(routes)
        return {"routes": routes} if routes else None

    def _discover_react_components(self, code: str, suffix: str) -> list[str]:
        if suffix not in {".jsx", ".tsx", ".js", ".ts"}:
            return []
        has_react_import = bool(re.search(r"from\s+['\"]react['\"]|require\(['\"]react['\"]\)|import\s+React\b", code))
        has_jsx_suffix = suffix in {".jsx", ".tsx"}
        has_jsx_element = bool(re.search(r"<[A-Z][A-Za-z0-9_]*(?:\s|>|/)", code))
        if not has_react_import and not (has_jsx_suffix and has_jsx_element):
            return []

        components = []
        components.extend(re.findall(r"export\s+default\s+function\s+([A-Z][A-Za-z0-9_]*)", code))
        components.extend(re.findall(r"export\s+function\s+([A-Z][A-Za-z0-9_]*)", code))
        components.extend(re.findall(r"(?:const|function)\s+([A-Z][A-Za-z0-9_]*)\s*[=(]", code))
        if re.search(r"export\s+default\s+[A-Z][A-Za-z0-9_]*", code):
            components.extend(re.findall(r"export\s+default\s+([A-Z][A-Za-z0-9_]*)", code))
        return self._unique_list(components)

    # ------------------------------------------------------------------
    # Java / Spring
    # ------------------------------------------------------------------

    def _generate_java_tests(self, project_dir: Path, strategy_name: str) -> list[GeneratedTest]:
        results: list[GeneratedTest] = []
        used_output_files: set[str] = set()

        paths = [
            p for p in project_dir.rglob("*.java")
            if not self._is_test_file(str(p.relative_to(project_dir)))
            and not self._is_ignored_path(str(p.relative_to(project_dir)))
        ]
        paths = sorted(paths, key=lambda p: self._priority_score(str(p.relative_to(project_dir))))[:45]

        for path in paths:
            relative = str(path.relative_to(project_dir)).replace("\\", "/")
            code = self._read_text(path)
            if not code:
                continue

            info = self._analyze_java_class(code, path.stem)
            test_code, test_type, framework, target_kind, confidence, needs_review, reasons = self._build_java_test(
                info,
                strategy_name,
            )
            if not test_code.strip():
                self._record_skipped_generation(relative, "No executable Java/JUnit test could be inferred without project fixtures.")
                continue

            output_name = self._unique_output_name(f"src/test/java/{info.class_name}GeneratedTest.java", used_output_files)
            results.append(
                GeneratedTest(
                    file=output_name,
                    target=relative,
                    test_code=test_code,
                    rationale=self._rationale("Test Generator v2", reasons, needs_review),
                    test_type=test_type,
                    confidence=confidence,
                    needs_review=needs_review,
                    framework=framework,
                    target_kind=target_kind,
                    assertion_strength="high" if test_type in {"integration", "api"} else "medium",
                    execution_safety="safe",
                    generated_test_category="smoke" if target_kind == "application_context" else test_type,
                )
            )

        return results

    def _build_java_test(
        self,
        info: JavaClassInfo,
        strategy_name: str,
    ) -> tuple[str, str, str | None, str, str, bool, list[str]]:
        lines: list[str] = []
        reasons: list[str] = []
        needs_review = False
        framework = "spring" if (info.is_spring_boot or info.is_controller) else None
        test_type = "unit"
        target_kind = "class"
        confidence = "medium"

        if info.package:
            lines.extend([f"package {info.package};", ""])

        if not self._is_valid_java_identifier(info.class_name):
            return "", test_type, framework, target_kind, "low", False, [
                "Java class name could not be parsed safely; no invalid test class was generated."
            ]

        if info.is_spring_boot:
            test_type = "smoke"
            target_kind = "application_context"
            confidence = "high"
            lines.extend([
                "import org.junit.jupiter.api.Test;",
                "import org.springframework.boot.test.context.SpringBootTest;",
                "",
                f"// Strategy: Test Generator v2 layered strategy ({strategy_name})",
                "@SpringBootTest",
                f"class {info.class_name}GeneratedTest {{",
                "",
                "    @Test",
                "    void contextLoads() {",
                "    }",
                "}",
            ])
            reasons.append("Detected Spring Boot application entry point and generated the standard contextLoads integration check.")
            return "\n".join(lines), test_type, framework, target_kind, confidence, needs_review, reasons

        if info.is_controller:
            test_type = "api"
            target_kind = "controller"
            confidence = "medium"
            lines.extend(self._java_controller_test(info, strategy_name))
            if len(lines) <= (2 if info.package else 0):
                return "", test_type, framework, target_kind, "low", False, [
                    "Controller was detected but no concrete request mappings were found."
                ]
            reasons.append("Detected Spring MVC controller and generated MockMvc skeletons for discovered mappings.")
            return "\n".join(lines), test_type, framework, target_kind, confidence, needs_review, reasons

        if not info.is_pojo:
            return "", test_type, framework, target_kind, "low", False, [
                "Java class requires constructor/dependency fixtures; no placeholder test was generated."
            ]

        pojo_tests = self._java_pojo_tests(info)
        if not pojo_tests:
            return "", test_type, framework, target_kind, "low", False, [
                "No safe getter/setter round-trip assertions could be inferred."
            ]

        lines.extend([
            "import org.junit.jupiter.api.Test;",
            "import static org.junit.jupiter.api.Assertions.*;",
            "",
            f"// Strategy: Test Generator v2 layered strategy ({strategy_name})",
            f"class {info.class_name}GeneratedTest {{",
        ])
        lines.extend(pojo_tests)
        reasons.append("Detected simple fields/getters/setters and generated POJO accessor contract checks.")

        lines.append("}")
        return "\n".join(lines), test_type, framework, target_kind, confidence, needs_review, reasons

    def _java_controller_test(self, info: JavaClassInfo, strategy_name: str) -> list[str]:
        lines = [
            "import org.junit.jupiter.api.Test;",
            "import org.springframework.beans.factory.annotation.Autowired;",
            "import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;",
            "import org.springframework.test.web.servlet.MockMvc;",
            "",
            "import static org.junit.jupiter.api.Assertions.assertTrue;",
            "import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;",
            "",
            f"// Strategy: Test Generator v2 layered strategy ({strategy_name})",
            f"@WebMvcTest({info.class_name}.class)",
            f"class {info.class_name}GeneratedTest {{",
            "",
            "    @Autowired",
            "    private MockMvc mockMvc;",
        ]

        if not info.controller_routes:
            return []

        for route in info.controller_routes[:8]:
            method = route["method"].lower()
            path = route["path"]
            safe = self._safe_java_identifier(f"{method}_{self._route_test_name(path)}")
            lines.extend([
                "",
                "    @Test",
                f"    void {safe}RespondsWithoutServerError() throws Exception {{",
                f"        mockMvc.perform({method}(\"{path}\"))",
                "            .andExpect(result -> assertTrue(result.getResponse().getStatus() < 500));",
                "    }",
            ])

        lines.append("}")
        return lines

    def _java_pojo_tests(self, info: JavaClassInfo) -> list[str]:
        lines: list[str] = []
        instantiation = self._java_instantiation_expression(info)
        if not instantiation:
            return []
        for field_info in info.fields[:6]:
            field_name = field_info["name"]
            field_type = field_info["type"]
            getter = f"get{field_name[:1].upper()}{field_name[1:]}"
            boolean_getter = f"is{field_name[:1].upper()}{field_name[1:]}"
            setter = f"set{field_name[:1].upper()}{field_name[1:]}"
            method_names = {method["name"] for method in info.methods}
            actual_getter = getter if getter in method_names else boolean_getter if boolean_getter in method_names else None
            if not actual_getter or setter not in method_names:
                continue
            sample = self._java_sample_value(field_type)
            safe = self._safe_java_identifier(field_name)
            lines.extend([
                "",
                "    @Test",
                f"    void {safe}GetterAndSetterRoundTrip() {{",
                f"        {info.class_name} instance = {instantiation};",
                f"        instance.{setter}({sample});",
                f"        assertEquals({sample}, instance.{actual_getter}());",
                "    }",
            ])
        return lines

    def _java_constructor_todo(self, info: JavaClassInfo) -> list[str]:
        return []

    def _analyze_java_class(self, code: str, fallback_name: str) -> JavaClassInfo:
        parse_code = self._strip_java_comments(code)
        package_match = re.search(r"^\s*package\s+([A-Za-z0-9_.]+)\s*;", parse_code, flags=re.MULTILINE)
        class_match = re.search(
            r"^\s*(?:@[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*)*"
            r"(?:(?:public|protected|private|abstract|final|sealed|non-sealed|static)\s+)*"
            r"(class|record|interface|enum)\s+([A-Za-z_][A-Za-z0-9_]*)\b",
            parse_code,
            flags=re.MULTILINE,
        )
        kind = class_match.group(1) if class_match else "class"
        class_name = class_match.group(2) if class_match else fallback_name
        if not self._is_valid_java_identifier(class_name):
            class_name = fallback_name if self._is_valid_java_identifier(fallback_name) else "GeneratedSubject"
        annotations = re.findall(r"@([A-Za-z_][A-Za-z0-9_]*)", parse_code)
        methods = self._discover_java_methods(parse_code)
        fields = self._discover_java_fields(parse_code)
        constructors = self._discover_java_constructors(code, class_name)
        routes = self._discover_java_controller_routes(parse_code)
        is_controller = any(annotation in annotations for annotation in ["Controller", "RestController"])
        is_spring_boot = "@SpringBootApplication" in parse_code or "SpringApplication.run(" in parse_code
        has_no_arg_constructor = not constructors or any(len(item["args"]) == 0 for item in constructors)
        is_abstract = bool(re.search(rf"\babstract\s+class\s+{re.escape(class_name)}\b", parse_code))
        is_interface = kind == "interface"

        return JavaClassInfo(
            package=package_match.group(1) if package_match else None,
            class_name=class_name,
            kind=kind,
            is_abstract=is_abstract,
            annotations=annotations,
            fields=fields,
            methods=methods,
            constructors=constructors,
            controller_routes=routes,
            is_spring_boot=is_spring_boot,
            is_controller=is_controller,
            is_pojo=bool(fields) and has_no_arg_constructor and not is_interface and not is_controller and not is_spring_boot,
        )

    def _discover_java_methods(self, code: str) -> list[dict[str, Any]]:
        pattern = (
            r"(?:public|private|protected)?\s+"
            r"(?:static\s+)?(?:final\s+)?"
            r"([A-Za-z0-9_<>\[\], ?]+)\s+"
            r"([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]*)\)"
        )
        methods = []
        ignored = {"if", "for", "while", "switch", "catch", "return", "new"}
        for return_type, name, args in re.findall(pattern, code):
            if name not in ignored:
                methods.append({"name": name, "return_type": return_type.strip(), "args": self._split_args(args)})
        return self._unique_dicts(methods, "name")

    def _discover_java_fields(self, code: str) -> list[dict[str, str]]:
        pattern = r"(?:private|protected|public)\s+(?:static\s+)?(?:final\s+)?([A-Za-z0-9_<>\[\], ?]+)\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|;)"
        return [
            {"type": field_type.strip(), "name": name}
            for field_type, name in re.findall(pattern, code)
            if self._is_valid_java_identifier(name)
        ]

    def _discover_java_constructors(self, code: str, class_name: str) -> list[dict[str, Any]]:
        pattern = rf"(?:public|private|protected)?\s+{re.escape(class_name)}\s*\(([^)]*)\)"
        return [{"args": self._split_args(args)} for args in re.findall(pattern, code)]

    def _java_instantiation_expression(self, info: JavaClassInfo) -> str:
        if info.kind in {"interface", "enum", "record"}:
            return ""
        safe_ctor = not info.constructors or any(len(item["args"]) == 0 for item in info.constructors)
        if not safe_ctor:
            return ""
        if info.is_abstract:
            return f"new {info.class_name}() {{}}"
        return f"new {info.class_name}()"

    def _strip_java_comments(self, code: str) -> str:
        code = re.sub(r"/\*[\s\S]*?\*/", "", code)
        code = re.sub(r"//.*", "", code)
        return code

    def _is_valid_java_identifier(self, value: str) -> bool:
        if not re.match(r"^[A-Za-z_$][A-Za-z0-9_$]*$", value or ""):
            return False
        return value not in {
            "abstract", "assert", "boolean", "break", "byte", "case", "catch",
            "char", "class", "const", "continue", "default", "do", "double",
            "else", "enum", "extends", "final", "finally", "float", "for",
            "goto", "if", "implements", "import", "instanceof", "int",
            "interface", "long", "native", "new", "package", "private",
            "protected", "public", "return", "short", "static", "strictfp",
            "super", "switch", "synchronized", "this", "throw", "throws",
            "transient", "try", "void", "volatile", "while", "record",
        }

    def _discover_java_controller_routes(self, code: str) -> list[dict[str, str]]:
        routes = []
        method_map = {
            "GetMapping": "get",
            "PostMapping": "post",
            "PutMapping": "put",
            "PatchMapping": "patch",
            "DeleteMapping": "delete",
            "RequestMapping": "get",
        }
        for annotation, args in re.findall(r"@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)\s*(?:\(([^)]*)\))?", code):
            path = "/"
            path_match = re.search(r"[\"']([^\"']+)[\"']", args or "")
            if path_match:
                path = path_match.group(1)
            routes.append({"method": method_map.get(annotation, "get"), "path": path})
        return self._dedupe_routes(routes)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _record_human_test_design(self, fn: PythonFunctionInfo, reason: str) -> None:
        target = self._python_display_name(fn)
        entry = {
            "target": target,
            "language": "python",
            "reason": reason,
            "signature": fn.signature_key,
            "target_kind": "method" if fn.is_method else "function",
        }
        existing = {
            (item.get("target"), item.get("signature"), item.get("reason"))
            for item in self.last_generation_metadata["needs_human_test_design"]
        }
        key = (entry["target"], entry["signature"], entry["reason"])
        if key not in existing:
            self.last_generation_metadata["needs_human_test_design"].append(entry)
        self._record_skipped_generation(target, reason)

    def _record_skipped_generation(self, target: str, reason: str) -> None:
        reasons = self.last_generation_metadata["skipped_generation_reasons"]
        reasons[reason] = reasons.get(reason, 0) + 1

    def _rationale(self, generator: str, reasons: list[str], needs_review: bool) -> str:
        summary = " ".join(reason for reason in reasons if reason)
        review = " Generated tests contain executable assertions only. Targets requiring fixtures are listed separately in metadata." if needs_review else " No fake pass-only assertions were generated."
        return f"{generator}: {summary}{review}".strip()

    def _priority_score(self, path: str) -> int:
        value = path.replace("\\", "/").lower()
        score = 100
        production_boosts = [
            "src/", "app/", "lib/", "server/", "api/", "routes/", "controllers/",
            "services/", "models/", "main.", "index.", "application.", "resource/",
        ]
        low_value = [
            "tests/", "/tests/", "test/", "/test/", "test_", "docs/", "docs_src/",
            "examples/", "example/", "tutorial/", ".github/", "scripts/", "demo/",
            "website/", "site/", "www/",
        ]
        for token in production_boosts:
            if token in value:
                score -= 25
        for token in low_value:
            if token in value:
                score += 40
        return score

    def _is_test_file(self, path: str) -> bool:
        value = path.replace("\\", "/").lower()
        return any(token in value for token in [
            "tests/", "/tests/", "test/", "/test/", "test_", "_test.",
            ".test.", ".spec.", "spec/", "__tests__/",
        ])

    def _is_ignored_path(self, path: str) -> bool:
        value = path.replace("\\", "/").lower()
        return any(token in value for token in [
            "node_modules/", "venv/", ".venv/", "__pycache__/", "dist/",
            "build/", ".git/", "docs/", "docs_src/", "examples/", "example/",
            "tutorial/", "website/", "site/", "www/", "sample_projects/", "uploads/", "storage/", "target/",
            ".mvn/", ".gradle/",
        ])

    def _ignore_python_function(self, name: str) -> bool:
        if name in {"__str__", "__repr__", "__eq__"}:
            return False
        if name.startswith("__") and name.endswith("__"):
            return True
        return name.startswith("_") and not name.startswith("__")

    def _classify_function(self, name: str) -> str:
        lower = name.lower()
        if lower.startswith(("is_", "has_", "can_", "should_")) or any(token in lower for token in ["validate", "check", "verify", "exists", "contains", "classify"]):
            return "validator"
        if any(token in lower for token in ["calculate", "compute", "sum", "add", "subtract", "minus", "multiply", "divide", "average", "score", "total", "count"]):
            return "calculator"
        if any(token in lower for token in ["parse", "load", "read", "extract"]):
            return "parser"
        if any(token in lower for token in ["format", "convert", "normalize", "clean", "transform"]):
            return "utility"
        return "generic"

    def _ast_name(self, node: ast.AST | None) -> str:
        if node is None:
            return ""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._ast_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        if isinstance(node, ast.Subscript):
            return self._ast_name(node.value)
        if isinstance(node, ast.Call):
            return self._ast_name(node.func)
        if isinstance(node, ast.Constant):
            return repr(node.value)
        return type(node).__name__

    def _literal_python_value(self, node: ast.AST) -> str:
        try:
            return repr(ast.literal_eval(node))
        except Exception:
            return "None"

    def _dedupe_routes(self, routes: list[dict[str, str]]) -> list[dict[str, str]]:
        unique = []
        seen = set()
        for route in routes:
            method = str(route.get("method", "get")).lower()
            path = str(route.get("path", "/")) or "/"
            key = (method, path)
            if key not in seen:
                seen.add(key)
                unique.append({"method": method, "path": path})
        return unique

    def _route_has_path_params(self, path: str) -> bool:
        return any(token in path for token in ["{", "}", "<", ">", ":"])

    def _route_test_name(self, path: str) -> str:
        cleaned = path.strip("/") or "root"
        cleaned = cleaned.replace("{", "").replace("}", "").replace("<", "").replace(">", "").replace(":", "")
        return self._safe_identifier(cleaned.replace("/", "_").replace("-", "_"))

    def _js_arg_count(self, args: str) -> int:
        args = args.strip()
        if not args:
            return 0
        return len([arg for arg in args.split(",") if arg.strip()])

    def _javascript_sample_arg(self, index: int) -> str:
        samples = ["'generated'", "1", "true", "{}"]
        return samples[index % len(samples)]

    def _javascript_value_for_arg(self, name: str, index: int) -> str:
        lower = (name or "").lower()
        if any(token in lower for token in ["type", "name", "key", "text", "path", "url", "format"]):
            return "'generated'"
        if any(token in lower for token in ["count", "index", "size", "length", "num", "id", "value"]):
            return "1"
        if any(token in lower for token in ["flag", "enabled", "active"]):
            return "true"
        if any(token in lower for token in ["list", "items", "array"]):
            return "[]"
        if any(token in lower for token in ["options", "config", "obj", "object", "state", "action"]):
            return "{}"
        return self._javascript_sample_arg(index)

    def _split_args(self, args: str) -> list[str]:
        return [arg.strip() for arg in args.split(",") if arg.strip()]

    def _java_sample_value(self, field_type: str) -> str:
        lowered = field_type.lower()
        if lowered in {"int", "integer", "long", "short", "byte"}:
            return "1"
        if lowered in {"double", "float", "bigdecimal"}:
            return "1.0"
        if lowered in {"boolean", "bool"}:
            return "true"
        if "string" in lowered:
            return "\"test\""
        return "null"

    def _unique_test_name(self, base: str, used: set[str]) -> str:
        safe = self._safe_identifier(base)
        if safe not in used:
            used.add(safe)
            return safe
        counter = 2
        while f"{safe}_{counter}" in used:
            counter += 1
        final = f"{safe}_{counter}"
        used.add(final)
        return final

    def _unique_output_name(self, base: str, used: set[str]) -> str:
        if base not in used:
            used.add(base)
            return base
        path = Path(base)
        counter = 2
        while True:
            candidate = str(path.with_name(f"{path.stem}_{counter}{path.suffix}")).replace("\\", "/")
            if candidate not in used:
                used.add(candidate)
                return candidate
            counter += 1

    def _dedupe_generated_tests(self, tests: list[GeneratedTest]) -> list[GeneratedTest]:
        unique = []
        seen = set()
        for test in tests:
            normalized_code = re.sub(r"\s+", " ", test.test_code).strip()
            key = (test.target.replace("\\", "/").lower(), test.file.lower(), normalized_code)
            if key in seen:
                continue
            seen.add(key)
            unique.append(test)
        return unique

    def _unique_list(self, values: list[str]) -> list[str]:
        result = []
        seen = set()
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result

    def _unique_dicts(self, values: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
        result = []
        seen = set()
        for value in values:
            identity = value.get(key)
            if identity and identity not in seen:
                seen.add(identity)
                result.append(value)
        return result

    def _safe_identifier(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", value)
        if not safe:
            safe = "generated_test"
        if safe[0].isdigit():
            safe = f"test_{safe}"
        return safe

    def _safe_java_identifier(self, value: str) -> str:
        safe = re.sub(r"[^A-Za-z0-9_]", "", value)
        if not safe:
            safe = "Generated"
        if safe[0].isdigit():
            safe = f"Generated{safe}"
        if not self._is_valid_java_identifier(safe):
            safe = f"Generated{safe[:1].upper()}{safe[1:]}"
        return safe
