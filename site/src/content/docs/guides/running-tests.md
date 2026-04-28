---
title: Running Tests
description: Run the 470-test NEXUS suite, target specific tests, and write tests for new modules.
sidebar:
  order: 3
---

## Run All Tests

```bash
pytest tests/ -v
```

Expected output ends with:

```
470 passed in X.XXs
```

No running LLM is required. All LLM calls are mocked in the test suite.

## Test Structure

```
tests/
├── kernel/
│   ├── test_cortex.py
│   ├── test_engram.py
│   ├── test_pulse.py
│   ├── test_chronicle.py
│   └── test_aegis.py
├── inference/
│   ├── test_provider.py
│   ├── test_local.py
│   ├── test_openai_provider.py
│   ├── test_anthropic_provider.py
│   ├── test_router.py
│   └── test_llm.py
├── messaging/
│   ├── test_bridge.py
│   ├── test_telegram.py
│   ├── test_discord.py
│   └── test_manager.py
├── modules/
│   ├── test_oracle.py
│   ├── test_sentry.py
│   ├── test_atlas.py
│   ├── test_prism.py
│   ├── test_cipher.py
│   ├── test_wraith.py
│   ├── test_echo.py
│   ├── test_sigil.py
│   ├── test_herald.py
│   ├── test_weave.py
│   ├── test_specter.py
│   ├── test_serendipity.py
│   ├── test_forge.py
│   ├── test_collective.py
│   ├── test_legacy.py
│   ├── test_general.py
│   ├── test_dream_loop.py
│   ├── test_adversarial.py
│   ├── test_tripwire.py
│   ├── test_provenance.py
│   ├── test_sandbox.py
│   ├── test_symbiosis.py
│   ├── test_consciousness.py
│   └── test_ethical_prism.py
├── community/
│   ├── test_validator.py
│   ├── test_registry.py
│   └── test_installer.py
└── integration/
    └── test_message_flow.py
```

## Run Specific Tests

**By file:**
```bash
pytest tests/kernel/test_cortex.py -v
pytest tests/modules/test_atlas.py -v
```

**By test name:**
```bash
pytest tests/ -k "test_handle_calls_llm" -v
```

**By keyword (matches test names and file paths):**
```bash
pytest tests/ -k "cortex" -v
pytest tests/ -k "trust or aegis" -v
```

**Just integration tests:**
```bash
pytest tests/integration/ -v
```

## Writing Tests for a New Module

Follow this pattern for every module test file. Each module should have at minimum four tests: attributes, handle behavior, memory storage, and a logic-specific test.

```python
import pytest
from unittest.mock import AsyncMock
from nexus.modules.your_module import YourModule


@pytest.fixture
def module():
    return YourModule()


@pytest.fixture
def context():
    """Standard mock context — matches what the kernel injects at runtime."""
    return {
        "llm": AsyncMock(),
        "engram": AsyncMock(),
        "chronicle": AsyncMock(),
        "pulse": AsyncMock(),
        "aegis": AsyncMock(),
    }


def test_module_attributes(module):
    """Every module must have name, description, and version."""
    assert module.name
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_returns_string(module, context):
    """handle() must always return a string."""
    context["llm"].complete.return_value = "response"
    context["engram"].query_episodic.return_value = []

    result = await module.handle("test input", context)

    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_handle_stores_to_memory(module, context):
    """Verify the module writes to episodic memory."""
    context["llm"].complete.return_value = "stored response"
    context["engram"].query_episodic.return_value = []

    await module.handle("test input", context)

    context["engram"].store_episodic.assert_called_once()


@pytest.mark.asyncio
async def test_your_specific_logic(module, context):
    """Test the module's unique behavior."""
    context["llm"].complete.return_value = "specific output"
    context["engram"].query_episodic.return_value = []

    result = await module.handle("trigger phrase", context)

    assert "expected content" in result.lower()
```

## Common Patterns

**Testing Pulse events:**
```python
await module.handle("input", context)
context["pulse"].publish.assert_called_with(
    "your_module.completed", {"result": "..."}
)
```

**Testing LLM prompt content:**
```python
await module.handle("input", context)
call_args = context["llm"].complete.call_args
assert "expected keyword" in call_args[0][0]  # positional prompt arg
```

**Testing error handling:**
```python
context["llm"].complete.side_effect = Exception("LLM unavailable")
result = await module.handle("input", context)
assert result  # should return a string, not raise
```

## Configuration

NEXUS uses standard pytest configuration. The `pyproject.toml` or `pytest.ini` at the project root sets `asyncio_mode = "auto"` so `@pytest.mark.asyncio` decorators are optional for async tests (though explicit marking is preferred for clarity).

```bash
# Run with coverage
pytest tests/ --cov=nexus --cov-report=term-missing

# Run and stop at first failure
pytest tests/ -x

# Run and show slowest tests
pytest tests/ --durations=10
```
