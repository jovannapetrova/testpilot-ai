class BaseTestStrategy:
    name = "Generic Enterprise Test Strategy"


class PythonStrategy(BaseTestStrategy):
    name = "Generic Python / Pytest Strategy"


class FastAPIStrategy(PythonStrategy):
    name = "FastAPI / Pytest TestClient Strategy"


class ReactStrategy(BaseTestStrategy):
    name = "React / Testing Library Strategy"


class JavaStrategy(BaseTestStrategy):
    name = "Java / JUnit Strategy"


class SpringStrategy(JavaStrategy):
    name = "Spring Boot / JUnit / MockMvc Strategy"
