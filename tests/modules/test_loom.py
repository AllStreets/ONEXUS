# tests/modules/test_loom.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.loom import LoomModule, PipelineStep, Pipeline


@pytest.fixture
def loom():
    return LoomModule()


def test_loom_attrs(loom):
    assert loom.name == "loom"
    assert loom.version == "0.1.0"


def test_detect_operation(loom):
    assert loom.detect_operation("extract data from CSV") == "extract"
    assert loom.detect_operation("transform dates to ISO format") == "transform"
    assert loom.detect_operation("load into database") == "load"
    assert loom.detect_operation("validate the schema") == "validate"
    assert loom.detect_operation("filter out nulls") == "filter"
    assert loom.detect_operation("join with users table") == "join"


def test_parse_steps(loom):
    text = "1. Extract data from CSV\n2. Transform dates\n3. Load into database"
    steps = loom.parse_steps(text)
    assert len(steps) == 3
    assert steps[0].operation == "extract"
    assert steps[2].operation == "load"


def test_parse_steps_with_arrows(loom):
    text = "- Read from source.csv -> staging\n- Transform staging -> clean"
    steps = loom.parse_steps(text)
    assert len(steps) == 2
    assert steps[0].source == "source.csv"
    assert steps[0].target == "staging"


def test_parse_steps_sets_dependencies(loom):
    text = "1. Step A\n2. Step B\n3. Step C"
    steps = loom.parse_steps(text)
    assert steps[1].depends_on == [steps[0].name]
    assert steps[2].depends_on == [steps[1].name]


def test_parse_steps_empty(loom):
    assert loom.parse_steps("no steps here") == []


def test_topological_sort_linear(loom):
    steps = [
        PipelineStep("a", "extract", "", ""),
        PipelineStep("b", "transform", "", "", depends_on=["a"]),
        PipelineStep("c", "load", "", "", depends_on=["b"]),
    ]
    order, errors = loom.topological_sort(steps)
    assert errors == []
    assert order == ["a", "b", "c"]


def test_topological_sort_missing_dep(loom):
    steps = [
        PipelineStep("a", "extract", "", "", depends_on=["nonexistent"]),
    ]
    order, errors = loom.topological_sort(steps)
    assert len(errors) > 0


def test_create_pipeline(loom):
    steps = [
        PipelineStep("extract", "extract", "csv", "staging"),
        PipelineStep("load", "load", "staging", "db", depends_on=["extract"]),
    ]
    pipeline = loom.create_pipeline("test_pipeline", steps)
    assert pipeline.is_valid is True
    assert pipeline.name == "test_pipeline"
    assert len(loom._pipelines) == 1


def test_visualize(loom):
    steps = [
        PipelineStep("extract", "extract", "csv", "staging"),
        PipelineStep("load", "load", "staging", "db", depends_on=["extract"]),
    ]
    pipeline = loom.create_pipeline("test", steps)
    viz = loom.visualize(pipeline)
    assert "extract" in viz
    assert "load" in viz


@pytest.mark.asyncio
async def test_handle_parses_pipeline(loom):
    context = {"llm": None, "engram": None}
    text = "1. Extract data from CSV\n2. Transform dates\n3. Load into database"
    result = await loom.handle(text, context)
    assert "[Loom]" in result
    assert "Steps: 3" in result


@pytest.mark.asyncio
async def test_handle_no_steps(loom):
    context = {"llm": None, "engram": None}
    result = await loom.handle("build me a pipeline", context)
    assert "Describe pipeline steps" in result


@pytest.mark.asyncio
async def test_handle_stores_pipeline(loom):
    context = {"llm": None, "engram": None}
    text = "1. Read from API\n2. Write to DB"
    await loom.handle(text, context)
    assert len(loom._pipelines) == 1
