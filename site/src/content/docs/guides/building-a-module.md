---
title: Build a Module
description: Five steps to add a new intelligence module to NEXUS -- from file creation through tests to enabling it in a live session.
sidebar:
  order: 1
---

Modules are persistent intelligence components. They extend NexusModule, implement `handle()`, and get routed by Cortex based on keyword matching. Every module has access to the full kernel context: Engram (memory), Chronicle (audit), Aegis (trust), Pulse (events), and LLM (inference).

If you want to build a task specialist with graduated sovereignty instead, see [Build an Agent](/NEXUS/guides/building-an-agent/).

---

## The Base Class

```python
# nexus/modules/base.py
class NexusModule(ABC):
    name: str              # unique identifier
    description: str       # human-readable purpose
    version: str           # semver
    requires_network: bool = False  # locked by default

    async def handle(self, message: str, context: dict) -> str: ...
    async def on_load(self, context: dict) -> None: ...
    async def on_unload(self, context: dict) -> None: ...
```

Every module must define `name`, `description`, `version`, and implement `handle()`. The base class enforces this at import time -- missing any of these raises `TypeError`.

---

## Step 1 -- Create the Module File

Create a new Python file in `nexus/modules/`. The filename becomes the conventional module identifier.

```python
# nexus/modules/summarizer.py
from nexus.modules.base import NexusModule


class SummarizerModule(NexusModule):
    name = "summarizer"
    description = "Summarizes text and documents using the local LLM."
    version = "1.0.0"

    async def on_load(self, context: dict) -> None:
        # Called once when `nexus allow summarizer` is run.
        # Subscribe to events or initialize state here.
        pass

    async def handle(self, message: str, context: dict) -> str:
        # Retrieve recent context from episodic memory
        recent = await context["engram"].query_episodic(
            "summarize", limit=3
        )

        # Build prompt
        prior = "\n".join(r["content"] for r in recent) if recent else ""
        prompt = f"Summarize the following text concisely:\n\n{message}"
        if prior:
            prompt += f"\n\nFor reference, recent summaries:\n{prior}"

        # Call the LLM
        response = await context["llm"].complete(prompt)

        # Store in episodic memory
        await context["engram"].store_episodic(
            source=self.name,
            content=response,
            tags=["summary"],
        )

        # Record a positive outcome (Aegis trust)
        await context["aegis"].record_outcome(self.name, positive=True)

        return response

    async def on_unload(self, context: dict) -> None:
        pass
```

### Context Keys

Every `handle()` call receives a context dict with these keys:

| Key | Type | What it does |
|-----|------|-------------|
| `engram` | Engram | Three-tier memory (working, episodic, semantic) |
| `chronicle` | Chronicle | Immutable audit log |
| `aegis` | Aegis | Trust scoring and permission checks |
| `pulse` | Pulse | Pub/sub event bus |
| `llm` | LLMClient | Inference (local or cloud) |

### Network Modules

If your module needs network access, set `requires_network = True`. Users must enable it with:

```bash
nexus allow --network your_module
```

All outbound data must be logged via `self._log_outbound(context, destination, summary)` -- this writes to Chronicle for audit compliance.

---

## Step 2 -- Register Routing Keywords

Open `nexus/kernel/cortex.py` and add an entry to `_MODULE_KEYWORDS`. Cortex routes incoming messages to your module when any of these words appear in the user's input.

```python
_MODULE_KEYWORDS = {
    # ... existing entries ...
    "summarizer": ["summarize", "summary", "tldr", "brief", "condense", "overview"],
}
```

Choose keywords that are specific enough to avoid false matches with other modules. If two modules both match a message, Cortex picks the one with the most keyword hits.

---

## Step 3 -- Write Tests

Create a test file mirroring the module's location:

```python
# tests/modules/test_summarizer.py
import pytest
from unittest.mock import AsyncMock
from nexus.modules.summarizer import SummarizerModule


@pytest.fixture
def module():
    return SummarizerModule()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(),
        "engram": AsyncMock(),
        "chronicle": AsyncMock(),
        "pulse": AsyncMock(),
        "aegis": AsyncMock(),
    }


def test_module_attributes(module):
    assert module.name == "summarizer"
    assert module.description
    assert module.version


@pytest.mark.asyncio
async def test_handle_calls_llm(module, context):
    context["llm"].complete.return_value = "A concise summary."
    context["engram"].query_episodic.return_value = []

    result = await module.handle("Long text to summarize.", context)

    context["llm"].complete.assert_called_once()
    assert result == "A concise summary."


@pytest.mark.asyncio
async def test_handle_stores_episodic(module, context):
    context["llm"].complete.return_value = "Summary stored."
    context["engram"].query_episodic.return_value = []

    await module.handle("Some text.", context)

    context["engram"].store_episodic.assert_called_once()
    call_kwargs = context["engram"].store_episodic.call_args.kwargs
    assert call_kwargs["source"] == "summarizer"
    assert "summary" in call_kwargs["tags"]


@pytest.mark.asyncio
async def test_handle_records_positive_outcome(module, context):
    context["llm"].complete.return_value = "Done."
    context["engram"].query_episodic.return_value = []

    await module.handle("Text.", context)

    context["aegis"].record_outcome.assert_called_once_with("summarizer", positive=True)
```

---

## Step 4 -- Run Tests

```bash
pytest tests/modules/test_summarizer.py -v
```

All tests should pass before enabling the module. The full test suite:

```bash
pytest tests/ -v
```

---

## Step 5 -- Enable the Module

```bash
nexus allow summarizer
```

The module starts with a trust score of 50. Test it in a live session:

```
> summarize this: The quick brown fox jumps over the lazy dog repeatedly.
[summarizer] A fox repeatedly jumps over a dog.
```

Check trust after a few interactions:

```bash
nexus status
# summarizer [trust: 53]
```

---

## What's Next

- [Build an Agent](/NEXUS/guides/building-an-agent/) -- task specialists with graduated sovereignty
- [Earned Autonomy](/NEXUS/concepts/earned-autonomy/) -- how trust tiers work
- [Connecting an LLM](/NEXUS/guides/connecting-an-llm/) -- local and cloud inference setup
