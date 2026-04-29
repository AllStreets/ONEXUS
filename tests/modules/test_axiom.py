# tests/modules/test_axiom.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.axiom import AxiomModule, FunctionSignature, GeneratedTest


@pytest.fixture
def axiom():
    return AxiomModule()


def test_axiom_attrs(axiom):
    assert axiom.name == "axiom"
    assert axiom.version == "0.1.0"


def test_extract_functions_basic(axiom):
    code = "def add(a: int, b: int) -> int:\n    return a + b"
    funcs = axiom.extract_functions(code)
    assert len(funcs) == 1
    assert funcs[0].name == "add"
    assert len(funcs[0].params) == 2
    assert funcs[0].return_type == "int"
    assert funcs[0].is_async is False


def test_extract_functions_async(axiom):
    code = "async def fetch(url: str) -> str:\n    pass"
    funcs = axiom.extract_functions(code)
    assert len(funcs) == 1
    assert funcs[0].is_async is True


def test_extract_functions_with_docstring(axiom):
    code = 'def greet(name: str):\n    """Say hello."""\n    pass'
    funcs = axiom.extract_functions(code)
    assert funcs[0].docstring == "Say hello."


def test_extract_functions_skips_self(axiom):
    code = "def method(self, x: int):\n    pass"
    funcs = axiom.extract_functions(code)
    assert len(funcs[0].params) == 1
    assert "self" not in funcs[0].params[0]


def test_extract_functions_none(axiom):
    assert axiom.extract_functions("x = 1\ny = 2") == []


def test_generate_test_cases_basic(axiom):
    func = FunctionSignature("add", ["a: int", "b: int"], "int", False, "")
    cases = axiom.generate_test_cases(func)
    assert len(cases) >= 3  # basic + edge cases + return type
    assert any(c.category == "happy_path" for c in cases)
    assert any(c.category == "error" for c in cases)


def test_generate_test_cases_async(axiom):
    func = FunctionSignature("fetch", ["url: str"], "str", True, "")
    cases = axiom.generate_test_cases(func)
    assert any("async" in c.code for c in cases)
    assert any("pytest.mark.asyncio" in c.code for c in cases)


def test_generate_test_cases_no_params(axiom):
    func = FunctionSignature("get_version", [], "str", False, "")
    cases = axiom.generate_test_cases(func)
    assert len(cases) >= 1  # at least basic + return type


def test_format_test_file(axiom):
    cases = [
        GeneratedTest("add", "test_add_basic", "basic test",
                 "    def test_add_basic():\n        assert add(1, 2) == 3", "happy_path"),
    ]
    output = axiom.format_test_file("add", cases)
    assert "import pytest" in output
    assert "test_add_basic" in output


@pytest.mark.asyncio
async def test_handle_generates_tests(axiom):
    context = {"llm": None, "engram": None}
    code = "def add(a: int, b: int) -> int:\n    return a + b"
    result = await axiom.handle(code, context)
    assert "[Axiom]" in result
    assert "Test Cases Generated" in result
    assert len(axiom._generated) == 1


@pytest.mark.asyncio
async def test_handle_no_functions(axiom):
    context = {"llm": None, "engram": None}
    result = await axiom.handle("just some text", context)
    assert "Provide Python function code" in result


@pytest.mark.asyncio
async def test_handle_with_llm_no_functions(axiom):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "def test_example():\n    assert True"
    context = {"llm": mock_llm, "engram": None}
    result = await axiom.handle("generate tests for this code", context)
    assert "[Axiom]" in result
    mock_llm.complete.assert_called_once()
