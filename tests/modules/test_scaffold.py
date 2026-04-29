# tests/modules/test_scaffold.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.scaffold import ScaffoldModule


@pytest.fixture
def scaffold():
    return ScaffoldModule()


def test_scaffold_attrs(scaffold):
    assert scaffold.name == "scaffold"
    assert scaffold.version == "0.1.0"


def test_detect_template_fastapi(scaffold):
    assert scaffold.detect_template("Build me a FastAPI backend") == "fastapi"


def test_detect_template_cli(scaffold):
    assert scaffold.detect_template("Create a CLI tool") == "cli"


def test_detect_template_default_python(scaffold):
    assert scaffold.detect_template("Make a new project") == "python"


def test_extract_project_name_quoted(scaffold):
    assert scaffold.extract_project_name('Create a project called "my_app"') == "my_app"


def test_extract_project_name_named(scaffold):
    assert scaffold.extract_project_name("Build a tool named taskrunner") == "taskrunner"


def test_extract_project_name_default(scaffold):
    assert scaffold.extract_project_name("Just make something") == "my_project"


def test_generate_python(scaffold):
    files = scaffold.generate("demo", "A demo project", "python")
    paths = [f.path for f in files]
    assert any("pyproject.toml" in p for p in paths)
    assert any("__init__.py" in p for p in paths)
    assert any("test_" in p for p in paths)


def test_generate_fastapi(scaffold):
    files = scaffold.generate("api", "REST API", "fastapi")
    paths = [f.path for f in files]
    assert any("Dockerfile" in p for p in paths)
    assert any("main.py" in p for p in paths)


def test_list_templates(scaffold):
    templates = scaffold.list_templates()
    assert "python" in templates
    assert "fastapi" in templates
    assert "cli" in templates


@pytest.mark.asyncio
async def test_handle_returns_string(scaffold):
    context = {"llm": None, "engram": None}
    result = await scaffold.handle("Create a Python project called 'demo'", context)
    assert "[Scaffold]" in result
    assert "demo" in result
