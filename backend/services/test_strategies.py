class BaseTestStrategy:
    name = "Generic Fallback Strategy"

    def generate_python_header(self, source_file, module_name):
        return [
            "import pytest",
            "",
            f"# Generated tests for {source_file}",
            f"# Strategy: {self.name}",
            "",
            "try:",
            f"    import {module_name} as target_module",
            "except Exception:",
            "    target_module = None",
            "",
            "def test_module_can_be_imported():",
            "    assert target_module is not None",
            "",
        ]

    def python_function_test(self, fn):
        return [
            "",
            f"def test_{fn['safe_name']}_is_callable():",
            "    if target_module is None:",
            "        pytest.skip('Module could not be imported safely')",
            f"    fn = getattr(target_module, '{fn['name']}', None)",
            "    assert callable(fn)",
            "",
        ]

    def generate_javascript_tests(self, source_file, functions):
        lines = [
            f"// Generated tests for {source_file}",
            f"// Strategy: {self.name}",
            "",
            "// No executable tests were generated because this fallback strategy",
            "// could not infer safe imports, fixtures, or meaningful assertions.",
        ]

        for fn in functions:
            lines += [
                f"// Human test design required for {fn}: add framework-aware fixtures and real assertions.",
            ]

        return "\n".join(lines)

    def generate_java_tests(self, source_file, methods):
        class_name = source_file.split("/")[-1].replace(".java", "")
        lines = [
            "import org.junit.jupiter.api.Test;",
            "import static org.junit.jupiter.api.Assertions.*;",
            "",
            f"class {class_name}GeneratedTest {{",
        ]

        for method in methods:
            lines += [
                "",
                f"    // Human test design required for {method}: instantiate the target with real fixtures and assertions.",
            ]

        lines.append("}")
        return "\n".join(lines)


class PythonStrategy(BaseTestStrategy):
    name = "Generic Python / Pytest Strategy"

    def python_function_test(self, fn):
        name = fn["name"]
        safe = fn["safe_name"]
        category = fn["category"]
        call_args = fn["call_args"]

        if category == "validator":
            return [
                "",
                f"def test_{safe}_validation_contract():",
                "    if target_module is None:",
                "        pytest.skip('Module could not be imported safely')",
                f"    fn = getattr(target_module, '{name}', None)",
                "    assert callable(fn)",
                "    try:",
                f"        result = fn({call_args})",
                "        assert isinstance(result, (bool, int, str, list, dict, type(None)))",
                "    except TypeError:",
                "        pytest.skip('Requires domain-specific input')",
                "",
            ]

        if category == "calculator":
            return [
                "",
                f"def test_{safe}_is_deterministic():",
                "    if target_module is None:",
                "        pytest.skip('Module could not be imported safely')",
                f"    fn = getattr(target_module, '{name}', None)",
                "    assert callable(fn)",
                "    try:",
                f"        assert fn({call_args}) == fn({call_args})",
                "    except TypeError:",
                "        pytest.skip('Requires domain-specific input')",
                "",
            ]

        return super().python_function_test(fn)


class FastAPIStrategy(PythonStrategy):
    name = "FastAPI / Pytest TestClient Strategy"

    def generate_python_header(self, source_file, module_name):
        return super().generate_python_header(source_file, module_name) + [
            "# FastAPI hint:",
            "# from fastapi.testclient import TestClient",
            "# client = TestClient(target_module.app)",
            "",
        ]


class ReactStrategy(BaseTestStrategy):
    name = "React / Jest / Testing Library Strategy"


class JavaStrategy(BaseTestStrategy):
    name = "Java / JUnit Strategy"


class SpringStrategy(JavaStrategy):
    name = "Spring Boot / JUnit / MockMvc Strategy"
