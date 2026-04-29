# tests/modules/test_flux.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.flux import FluxModule, SQLResult


@pytest.fixture
def flux():
    return FluxModule()


def test_flux_attrs(flux):
    assert flux.name == "flux"
    assert flux.version == "0.1.0"


def test_register_schema(flux):
    flux.register_schema("users", ["id", "name", "email"])
    schemas = flux.list_schemas()
    assert "users" in schemas
    assert schemas["users"] == ["id", "name", "email"]


def test_parse_schema_create_table(flux):
    sql = """
    CREATE TABLE users (
        id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        UNIQUE (email)
    )
    """
    schemas = flux.parse_schema(sql)
    assert "users" in schemas
    assert "id" in schemas["users"]
    assert "name" in schemas["users"]
    assert "email" in schemas["users"]


def test_parse_schema_colon_format(flux):
    text = "users: id, name, email\norders: id, user_id, total"
    schemas = flux.parse_schema(text)
    assert "users" in schemas
    assert "orders" in schemas
    assert schemas["orders"] == ["id", "user_id", "total"]


def test_parse_schema_empty(flux):
    assert flux.parse_schema("nothing here") == {}


def test_estimate_complexity_simple(flux):
    assert flux.estimate_complexity("SELECT * FROM users") == "simple"


def test_estimate_complexity_moderate(flux):
    assert flux.estimate_complexity("SELECT COUNT(*) FROM users GROUP BY status") == "moderate"


def test_estimate_complexity_complex(flux):
    assert flux.estimate_complexity("SELECT * FROM users JOIN orders ON users.id = orders.user_id") == "complex"


def test_extract_tables(flux):
    query = "SELECT u.name FROM users u JOIN orders o ON u.id = o.user_id"
    tables = flux.extract_tables(query)
    assert "users" in tables
    assert "orders" in tables


def test_extract_tables_single(flux):
    tables = flux.extract_tables("SELECT * FROM products WHERE price > 10")
    assert tables == ["products"]


@pytest.mark.asyncio
async def test_handle_schema_registration(flux):
    context = {"llm": None, "engram": None}
    result = await flux.handle("users: id, name, email", context)
    assert "[Flux]" in result
    assert "Schema registered" in result
    assert "users" in flux._schemas


@pytest.mark.asyncio
async def test_handle_no_llm(flux):
    context = {"llm": None, "engram": None}
    result = await flux.handle("Show me all users", context)
    assert "LLM required" in result


@pytest.mark.asyncio
async def test_handle_with_llm(flux):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "SQL:\nSELECT * FROM users\n\nEXPLANATION:\nRetrieves all users"
    context = {"llm": mock_llm, "engram": None}
    flux.register_schema("users", ["id", "name", "email"])
    result = await flux.handle("Show me all users", context)
    assert "[Flux]" in result
    assert "SQL Query Generated" in result
    mock_llm.complete.assert_called_once()


@pytest.mark.asyncio
async def test_handle_stores_history(flux):
    mock_llm = AsyncMock()
    mock_llm.complete.return_value = "SQL:\nSELECT 1\n\nEXPLANATION:\nTest"
    context = {"llm": mock_llm, "engram": None}
    await flux.handle("test query", context)
    assert len(flux._query_history) == 1
