# Batch 7a: Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the llama.cpp-only inference client with a multi-provider abstraction (local, OpenAI, Anthropic) and add two-way Telegram/Discord messaging bridges, giving NEXUS users provider choice and proactive reach.

**Architecture:** A new `InferenceProvider` ABC sits behind the existing `LLMClient` interface via a `ProviderRouter`. The messaging layer adds a `MessageBridge` ABC with Telegram and Discord implementations, managed by a `BridgeManager` that routes inbound messages through Cortex and subscribes to `notify.*` Pulse events for outbound. Zero existing module changes required.

**Tech Stack:** Python 3.11+, `openai` SDK, `anthropic` SDK, `python-telegram-bot`, `discord.py`, SQLite (existing), pytest + pytest-asyncio

---

## File Structure

### Inference (Multi-Provider)

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `nexus/inference/provider.py` | `InferenceProvider` ABC — `infer(messages, max_tokens, temperature) -> str`, `health() -> bool` |
| Create | `nexus/inference/local.py` | `LocalProvider` — wraps existing llama.cpp HTTP client, ChatML formatting |
| Create | `nexus/inference/openai_provider.py` | `OpenAIProvider` — OpenAI SDK, messages format native |
| Create | `nexus/inference/anthropic_provider.py` | `AnthropicProvider` — Anthropic SDK, messages format native |
| Create | `nexus/inference/router.py` | `ProviderRouter` — holds named providers, selects per-request, fallback logic |
| Modify | `nexus/inference/llm.py` | `LLMClient` — delegates to `ProviderRouter` internally, same external interface |
| Modify | `nexus/config.py` | Add `default_provider`, API key fields, model name fields |
| Modify | `nexus/cli.py` | Use new `LLMClient` with router, configure from `NexusConfig` |
| Create | `tests/inference/test_provider.py` | Tests for ABC contract |
| Create | `tests/inference/test_local.py` | Tests for LocalProvider |
| Create | `tests/inference/test_openai_provider.py` | Tests for OpenAIProvider |
| Create | `tests/inference/test_anthropic_provider.py` | Tests for AnthropicProvider |
| Create | `tests/inference/test_router.py` | Tests for ProviderRouter |
| Modify | `tests/inference/test_llm.py` | Update tests for new LLMClient internals |

### Messaging (Telegram + Discord)

| Action | Path | Responsibility |
|--------|------|---------------|
| Create | `nexus/messaging/__init__.py` | Package init |
| Create | `nexus/messaging/bridge.py` | `MessageBridge` ABC — `start()`, `stop()`, `send()`, `on_message()` |
| Create | `nexus/messaging/telegram.py` | `TelegramBridge` — `python-telegram-bot` wrapper |
| Create | `nexus/messaging/discord_bridge.py` | `DiscordBridge` — `discord.py` wrapper |
| Create | `nexus/messaging/manager.py` | `BridgeManager` — lifecycle, inbound→Cortex routing, Pulse→outbound |
| Modify | `nexus/config.py` | Add messaging token/channel fields |
| Modify | `nexus/cli.py` | Start BridgeManager in `run()` if tokens configured |
| Create | `tests/messaging/__init__.py` | Package init |
| Create | `tests/messaging/test_bridge.py` | Tests for ABC contract |
| Create | `tests/messaging/test_telegram.py` | Tests for TelegramBridge |
| Create | `tests/messaging/test_discord.py` | Tests for DiscordBridge |
| Create | `tests/messaging/test_manager.py` | Tests for BridgeManager |
| Create | `tests/test_batch7a_integration.py` | End-to-end integration tests |

---

## Task 1: InferenceProvider ABC

**Files:**
- Create: `nexus/inference/provider.py`
- Create: `tests/inference/test_provider.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/inference/test_provider.py
import pytest
from nexus.inference.provider import InferenceProvider


def test_provider_is_abstract():
    """InferenceProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        InferenceProvider()


def test_provider_subclass_must_implement_infer():
    """Subclass without infer() raises TypeError."""
    with pytest.raises(TypeError):
        class BadProvider(InferenceProvider):
            name = "bad"
            async def health(self) -> bool:
                return True
        BadProvider()


def test_provider_subclass_must_implement_health():
    """Subclass without health() raises TypeError."""
    with pytest.raises(TypeError):
        class BadProvider(InferenceProvider):
            name = "bad"
            async def infer(self, messages, max_tokens=1024, temperature=0.7):
                return "ok"
        BadProvider()


@pytest.mark.asyncio
async def test_valid_provider_subclass():
    """A complete subclass can be instantiated and called."""
    class StubProvider(InferenceProvider):
        name = "stub"
        async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
            return "stub response"
        async def health(self) -> bool:
            return True

    provider = StubProvider()
    assert provider.name == "stub"
    result = await provider.infer([{"role": "user", "content": "hello"}])
    assert result == "stub response"
    assert await provider.health() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/inference/test_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.inference.provider'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/inference/provider.py
"""
InferenceProvider — abstract base class for all LLM inference backends.
Every provider normalizes to OpenAI-style messages format.
"""
from abc import ABC, abstractmethod


class ProviderUnavailable(Exception):
    """Raised when no inference provider is reachable."""
    def __init__(self, provider: str):
        self.provider = provider
        super().__init__(f"Provider '{provider}' is unavailable")


class InferenceProvider(ABC):
    name: str

    @abstractmethod
    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        """Send messages in OpenAI format and return the completion text."""
        ...

    @abstractmethod
    async def health(self) -> bool:
        """Return True if this provider is reachable and ready."""
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/inference/test_provider.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/inference/provider.py tests/inference/test_provider.py
git commit -m "feat(inference): add InferenceProvider ABC and ProviderUnavailable exception"
```

---

## Task 2: LocalProvider

**Files:**
- Create: `nexus/inference/local.py`
- Create: `tests/inference/test_local.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/inference/test_local.py
import json
import pytest
from unittest.mock import patch, MagicMock
from nexus.inference.local import LocalProvider
from nexus.inference.provider import InferenceProvider


def test_local_provider_is_inference_provider():
    """LocalProvider is a subclass of InferenceProvider."""
    provider = LocalProvider(base_url="http://localhost:8384")
    assert isinstance(provider, InferenceProvider)


def test_local_provider_name():
    provider = LocalProvider(base_url="http://localhost:8384")
    assert provider.name == "local"


def test_local_provider_converts_messages_to_chatml():
    """Messages list should be converted to ChatML format."""
    provider = LocalProvider(base_url="http://localhost:8384")
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    prompt = provider._messages_to_chatml(messages)
    assert "<|im_start|>system" in prompt
    assert "You are helpful." in prompt
    assert "<|im_start|>user" in prompt
    assert "Hello" in prompt
    assert prompt.endswith("<|im_start|>assistant\n")


def test_local_provider_chatml_with_history():
    """Multi-turn conversation should produce correct ChatML."""
    provider = LocalProvider(base_url="http://localhost:8384")
    messages = [
        {"role": "system", "content": "System."},
        {"role": "user", "content": "Q1"},
        {"role": "assistant", "content": "A1"},
        {"role": "user", "content": "Q2"},
    ]
    prompt = provider._messages_to_chatml(messages)
    assert "Q1" in prompt
    assert "A1" in prompt
    assert "Q2" in prompt


@pytest.mark.asyncio
async def test_local_provider_infer_calls_endpoint():
    """infer() should POST to /completion with the ChatML prompt."""
    provider = LocalProvider(base_url="http://localhost:8384")
    messages = [{"role": "user", "content": "test"}]

    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({"content": "response text"}).encode()
    mock_response.status = 200
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        result = await provider.infer(messages)
        assert result == "response text"
        mock_urlopen.assert_called_once()
        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        body = json.loads(req.data)
        assert "<|im_start|>user" in body["prompt"]


@pytest.mark.asyncio
async def test_local_provider_infer_error_returns_message():
    """infer() should return an error string on connection failure."""
    provider = LocalProvider(base_url="http://localhost:99999")
    messages = [{"role": "user", "content": "test"}]

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        result = await provider.infer(messages)
        assert "[Inference error:" in result


def test_local_provider_health_returns_false_on_failure():
    """health() should return False when server is unreachable."""
    provider = LocalProvider(base_url="http://localhost:99999")
    with patch("urllib.request.urlopen", side_effect=Exception("refused")):
        assert provider.health() is False


def test_local_provider_health_returns_true_on_success():
    """health() should return True when /health returns 200."""
    provider = LocalProvider(base_url="http://localhost:8384")
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        assert provider.health() is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/inference/test_local.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.inference.local'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/inference/local.py
"""
LocalProvider — inference via a local llama.cpp-compatible HTTP server.
Converts OpenAI-style messages to ChatML format for the /completion endpoint.
"""
import re
import json
import urllib.request
from nexus.inference.provider import InferenceProvider


class LocalProvider(InferenceProvider):
    name = "local"

    def __init__(self, base_url: str = "http://localhost:8384"):
        self._base_url = base_url.rstrip("/")

    def _messages_to_chatml(self, messages: list[dict]) -> str:
        """Convert OpenAI-style messages list to ChatML prompt string."""
        parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            parts.append(f"<|im_start|>{role}\n{content}<|im_end|>")
        parts.append("<|im_start|>assistant\n")
        return "\n".join(parts)

    @staticmethod
    def _parse_response(raw: str) -> str:
        cleaned = re.sub(r"<\|[^>]+\|>", "", raw)
        return cleaned.strip()

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        prompt = self._messages_to_chatml(messages)
        payload = json.dumps({
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": ["<|im_end|>", "<|end|>"],
        }).encode()
        req = urllib.request.Request(
            f"{self._base_url}/completion",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read())
                return self._parse_response(data.get("content", ""))
        except Exception as e:
            return f"[Inference error: {e}]"

    def health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self._base_url}/health")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/inference/test_local.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/inference/local.py tests/inference/test_local.py
git commit -m "feat(inference): add LocalProvider wrapping llama.cpp HTTP endpoint"
```

---

## Task 3: OpenAIProvider

**Files:**
- Create: `nexus/inference/openai_provider.py`
- Create: `tests/inference/test_openai_provider.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/inference/test_openai_provider.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from nexus.inference.openai_provider import OpenAIProvider
from nexus.inference.provider import InferenceProvider


def test_openai_provider_is_inference_provider():
    provider = OpenAIProvider(api_key="test-key")
    assert isinstance(provider, InferenceProvider)


def test_openai_provider_name():
    provider = OpenAIProvider(api_key="test-key")
    assert provider.name == "openai"


def test_openai_provider_default_model():
    provider = OpenAIProvider(api_key="test-key")
    assert provider._model == "gpt-4o-mini"


def test_openai_provider_custom_model():
    provider = OpenAIProvider(api_key="test-key", model="gpt-4o")
    assert provider._model == "gpt-4o"


@pytest.mark.asyncio
async def test_openai_provider_infer_calls_sdk():
    """infer() should call the OpenAI SDK with correct params."""
    provider = OpenAIProvider(api_key="test-key", model="gpt-4o-mini")
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Hello"},
    ]

    mock_choice = MagicMock()
    mock_choice.message.content = "Hi there!"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch.object(provider._client.chat.completions, "create", return_value=mock_completion) as mock_create:
        result = await provider.infer(messages, max_tokens=512, temperature=0.5)
        assert result == "Hi there!"
        mock_create.assert_called_once_with(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=512,
            temperature=0.5,
        )


@pytest.mark.asyncio
async def test_openai_provider_infer_error():
    """infer() should return error string on SDK failure."""
    provider = OpenAIProvider(api_key="test-key")
    messages = [{"role": "user", "content": "test"}]

    with patch.object(provider._client.chat.completions, "create", side_effect=Exception("API error")):
        result = await provider.infer(messages)
        assert "[Inference error:" in result


@pytest.mark.asyncio
async def test_openai_provider_health_success():
    """health() returns True when a simple completion succeeds."""
    provider = OpenAIProvider(api_key="test-key")

    mock_choice = MagicMock()
    mock_choice.message.content = "ok"
    mock_completion = MagicMock()
    mock_completion.choices = [mock_choice]

    with patch.object(provider._client.chat.completions, "create", return_value=mock_completion):
        result = await provider.health()
        assert result is True


@pytest.mark.asyncio
async def test_openai_provider_health_failure():
    """health() returns False when SDK throws."""
    provider = OpenAIProvider(api_key="test-key")

    with patch.object(provider._client.chat.completions, "create", side_effect=Exception("bad key")):
        result = await provider.health()
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/inference/test_openai_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.inference.openai_provider'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/inference/openai_provider.py
"""
OpenAIProvider — inference via the OpenAI API.
Uses the openai Python SDK. Messages format is native (no conversion needed).
"""
from openai import OpenAI
from nexus.inference.provider import InferenceProvider


class OpenAIProvider(InferenceProvider):
    name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self._client = OpenAI(api_key=api_key)
        self._model = model

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"[Inference error: {e}]"

    async def health(self) -> bool:
        try:
            self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/inference/test_openai_provider.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/inference/openai_provider.py tests/inference/test_openai_provider.py
git commit -m "feat(inference): add OpenAIProvider using openai SDK"
```

---

## Task 4: AnthropicProvider

**Files:**
- Create: `nexus/inference/anthropic_provider.py`
- Create: `tests/inference/test_anthropic_provider.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/inference/test_anthropic_provider.py
import pytest
from unittest.mock import patch, MagicMock
from nexus.inference.anthropic_provider import AnthropicProvider
from nexus.inference.provider import InferenceProvider


def test_anthropic_provider_is_inference_provider():
    provider = AnthropicProvider(api_key="test-key")
    assert isinstance(provider, InferenceProvider)


def test_anthropic_provider_name():
    provider = AnthropicProvider(api_key="test-key")
    assert provider.name == "anthropic"


def test_anthropic_provider_default_model():
    provider = AnthropicProvider(api_key="test-key")
    assert provider._model == "claude-sonnet-4-20250514"


def test_anthropic_provider_custom_model():
    provider = AnthropicProvider(api_key="test-key", model="claude-opus-4-20250514")
    assert provider._model == "claude-opus-4-20250514"


@pytest.mark.asyncio
async def test_anthropic_provider_infer_calls_sdk():
    """infer() should call the Anthropic SDK with correct params."""
    provider = AnthropicProvider(api_key="test-key")
    messages = [
        {"role": "system", "content": "Be helpful."},
        {"role": "user", "content": "Hello"},
    ]

    mock_content_block = MagicMock()
    mock_content_block.text = "Hi from Claude!"
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    with patch.object(provider._client.messages, "create", return_value=mock_response) as mock_create:
        result = await provider.infer(messages, max_tokens=512, temperature=0.5)
        assert result == "Hi from Claude!"
        mock_create.assert_called_once_with(
            model="claude-sonnet-4-20250514",
            system="Be helpful.",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=512,
            temperature=0.5,
        )


@pytest.mark.asyncio
async def test_anthropic_provider_infer_no_system_message():
    """infer() should work without a system message."""
    provider = AnthropicProvider(api_key="test-key")
    messages = [{"role": "user", "content": "Hello"}]

    mock_content_block = MagicMock()
    mock_content_block.text = "Hi!"
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    with patch.object(provider._client.messages, "create", return_value=mock_response) as mock_create:
        result = await provider.infer(messages)
        assert result == "Hi!"
        call_kwargs = mock_create.call_args[1]
        assert "system" not in call_kwargs or call_kwargs["system"] is None


@pytest.mark.asyncio
async def test_anthropic_provider_infer_error():
    """infer() should return error string on SDK failure."""
    provider = AnthropicProvider(api_key="test-key")
    messages = [{"role": "user", "content": "test"}]

    with patch.object(provider._client.messages, "create", side_effect=Exception("API error")):
        result = await provider.infer(messages)
        assert "[Inference error:" in result


@pytest.mark.asyncio
async def test_anthropic_provider_health_success():
    provider = AnthropicProvider(api_key="test-key")

    mock_content_block = MagicMock()
    mock_content_block.text = "ok"
    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    with patch.object(provider._client.messages, "create", return_value=mock_response):
        result = await provider.health()
        assert result is True


@pytest.mark.asyncio
async def test_anthropic_provider_health_failure():
    provider = AnthropicProvider(api_key="test-key")

    with patch.object(provider._client.messages, "create", side_effect=Exception("bad key")):
        result = await provider.health()
        assert result is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/inference/test_anthropic_provider.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.inference.anthropic_provider'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/inference/anthropic_provider.py
"""
AnthropicProvider — inference via the Anthropic (Claude) API.
Uses the anthropic Python SDK. Separates system message from user messages
per Anthropic's API contract.
"""
from anthropic import Anthropic
from nexus.inference.provider import InferenceProvider


class AnthropicProvider(InferenceProvider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self._client = Anthropic(api_key=api_key)
        self._model = model

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        try:
            # Anthropic API takes system as a separate param
            system_msg = None
            non_system = []
            for msg in messages:
                if msg["role"] == "system":
                    system_msg = msg["content"]
                else:
                    non_system.append(msg)

            kwargs: dict = {
                "model": self._model,
                "messages": non_system,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if system_msg:
                kwargs["system"] = system_msg

            response = self._client.messages.create(**kwargs)
            return response.content[0].text
        except Exception as e:
            return f"[Inference error: {e}]"

    async def health(self) -> bool:
        try:
            self._client.messages.create(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            return True
        except Exception:
            return False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/inference/test_anthropic_provider.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/inference/anthropic_provider.py tests/inference/test_anthropic_provider.py
git commit -m "feat(inference): add AnthropicProvider using anthropic SDK"
```

---

## Task 5: ProviderRouter

**Files:**
- Create: `nexus/inference/router.py`
- Create: `tests/inference/test_router.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/inference/test_router.py
import pytest
from unittest.mock import AsyncMock
from nexus.inference.router import ProviderRouter
from nexus.inference.provider import InferenceProvider, ProviderUnavailable


class FakeProvider(InferenceProvider):
    name = "fake"

    def __init__(self, response: str = "fake response", healthy: bool = True):
        self._response = response
        self._healthy = healthy

    async def infer(self, messages: list[dict], max_tokens: int = 1024, temperature: float = 0.7) -> str:
        return self._response

    async def health(self) -> bool:
        return self._healthy


def test_router_register_provider():
    router = ProviderRouter(default="fake")
    provider = FakeProvider()
    router.register(provider)
    assert "fake" in router.providers


def test_router_list_providers():
    router = ProviderRouter(default="fake")
    router.register(FakeProvider())
    assert router.list_providers() == ["fake"]


@pytest.mark.asyncio
async def test_router_infer_uses_default():
    """Without specifying a provider, uses the default."""
    router = ProviderRouter(default="fake")
    router.register(FakeProvider(response="default answer"))
    result = await router.infer([{"role": "user", "content": "hi"}])
    assert result == "default answer"


@pytest.mark.asyncio
async def test_router_infer_with_specific_provider():
    """Can request a specific provider by name."""
    router = ProviderRouter(default="fake")
    router.register(FakeProvider(response="default"))

    other = FakeProvider(response="other answer")
    other.name = "other"
    router.register(other)

    result = await router.infer([{"role": "user", "content": "hi"}], provider="other")
    assert result == "other answer"


@pytest.mark.asyncio
async def test_router_fallback_to_default_on_unhealthy():
    """If requested provider is unhealthy, falls back to default."""
    router = ProviderRouter(default="healthy")

    healthy = FakeProvider(response="healthy answer", healthy=True)
    healthy.name = "healthy"
    router.register(healthy)

    unhealthy = FakeProvider(response="never seen", healthy=False)
    unhealthy.name = "broken"
    router.register(unhealthy)

    result = await router.infer([{"role": "user", "content": "hi"}], provider="broken")
    assert result == "healthy answer"


@pytest.mark.asyncio
async def test_router_raises_when_all_unhealthy():
    """Raises ProviderUnavailable when default is also unhealthy."""
    router = ProviderRouter(default="broken")

    broken = FakeProvider(response="never", healthy=False)
    broken.name = "broken"
    router.register(broken)

    with pytest.raises(ProviderUnavailable):
        await router.infer([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_router_raises_for_unknown_provider():
    """Raises ProviderUnavailable for unregistered provider name."""
    router = ProviderRouter(default="fake")
    router.register(FakeProvider())

    with pytest.raises(ProviderUnavailable):
        await router.infer([{"role": "user", "content": "hi"}], provider="nonexistent")


@pytest.mark.asyncio
async def test_router_health_aggregates():
    """health() returns dict of provider -> bool."""
    router = ProviderRouter(default="a")

    a = FakeProvider(healthy=True)
    a.name = "a"
    router.register(a)

    b = FakeProvider(healthy=False)
    b.name = "b"
    router.register(b)

    health = await router.health()
    assert health == {"a": True, "b": False}


@pytest.mark.asyncio
async def test_router_passes_params():
    """max_tokens and temperature are forwarded to the provider."""
    mock_provider = AsyncMock(spec=InferenceProvider)
    mock_provider.name = "mock"
    mock_provider.health = AsyncMock(return_value=True)
    mock_provider.infer = AsyncMock(return_value="ok")

    router = ProviderRouter(default="mock")
    router.register(mock_provider)

    await router.infer([{"role": "user", "content": "hi"}], max_tokens=256, temperature=0.3)
    mock_provider.infer.assert_called_once_with(
        [{"role": "user", "content": "hi"}],
        max_tokens=256,
        temperature=0.3,
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/inference/test_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.inference.router'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/inference/router.py
"""
ProviderRouter — selects and delegates to a named InferenceProvider.
Supports per-request provider selection with fallback to the default.
"""
from nexus.inference.provider import InferenceProvider, ProviderUnavailable


class ProviderRouter:
    def __init__(self, default: str = "local"):
        self._default = default
        self._providers: dict[str, InferenceProvider] = {}

    @property
    def providers(self) -> dict[str, InferenceProvider]:
        return dict(self._providers)

    def register(self, provider: InferenceProvider) -> None:
        self._providers[provider.name] = provider

    def list_providers(self) -> list[str]:
        return list(self._providers.keys())

    async def infer(
        self,
        messages: list[dict],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        provider: str | None = None,
    ) -> str:
        target_name = provider or self._default

        # Try the requested provider
        target = self._providers.get(target_name)
        if target is None:
            raise ProviderUnavailable(target_name)

        if await target.health():
            return await target.infer(messages, max_tokens=max_tokens, temperature=temperature)

        # Requested provider unhealthy — fall back to default
        if target_name != self._default:
            fallback = self._providers.get(self._default)
            if fallback and await fallback.health():
                return await fallback.infer(messages, max_tokens=max_tokens, temperature=temperature)

        raise ProviderUnavailable(target_name)

    async def health(self) -> dict[str, bool]:
        return {name: await p.health() for name, p in self._providers.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/inference/test_router.py -v`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/inference/router.py tests/inference/test_router.py
git commit -m "feat(inference): add ProviderRouter with fallback and health aggregation"
```

---

## Task 6: Update LLMClient to Use ProviderRouter

**Files:**
- Modify: `nexus/inference/llm.py`
- Modify: `tests/inference/test_llm.py`

- [ ] **Step 1: Write the failing tests**

Replace `tests/inference/test_llm.py` with:

```python
# tests/inference/test_llm.py
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from nexus.inference.llm import LLMClient
from nexus.inference.provider import InferenceProvider
from nexus.inference.router import ProviderRouter


@pytest.fixture
def mock_router():
    router = MagicMock(spec=ProviderRouter)
    router.infer = AsyncMock(return_value="routed response")
    router.health = AsyncMock(return_value={"local": True})
    router.list_providers = MagicMock(return_value=["local"])
    return router


@pytest.fixture
def llm(mock_router):
    return LLMClient(router=mock_router)


@pytest.mark.asyncio
async def test_llm_infer_delegates_to_router(llm, mock_router):
    """infer() with a raw prompt string should wrap it in messages and route."""
    result = await llm.infer("What is 2+2?")
    assert result == "routed response"
    mock_router.infer.assert_called_once()
    call_args = mock_router.infer.call_args
    messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][0]
    assert any("2+2" in m["content"] for m in messages)


@pytest.mark.asyncio
async def test_llm_chat_delegates_to_router(llm, mock_router):
    """chat() should convert system/user/history to messages and route."""
    result = await llm.chat(
        system="Be helpful.",
        user="Hello",
        history=[{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}],
    )
    assert result == "routed response"
    mock_router.infer.assert_called_once()
    call_args = mock_router.infer.call_args
    messages = call_args[0][0]
    roles = [m["role"] for m in messages]
    assert "system" in roles
    assert roles.count("user") == 2  # history user + current user


@pytest.mark.asyncio
async def test_llm_chat_no_history(llm, mock_router):
    """chat() without history sends system + user messages."""
    await llm.chat(system="System.", user="Question")
    messages = mock_router.infer.call_args[0][0]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


@pytest.mark.asyncio
async def test_llm_infer_with_provider(llm, mock_router):
    """infer() can specify a provider name."""
    await llm.infer("test", provider="openai")
    assert mock_router.infer.call_args[1].get("provider") == "openai"


@pytest.mark.asyncio
async def test_llm_chat_with_provider(llm, mock_router):
    """chat() can specify a provider name."""
    await llm.chat(system="S", user="U", provider="anthropic")
    assert mock_router.infer.call_args[1].get("provider") == "anthropic"


@pytest.mark.asyncio
async def test_llm_infer_passes_max_tokens_and_temperature(llm, mock_router):
    """infer() forwards max_tokens and temperature to the router."""
    await llm.infer("test", max_tokens=256, temperature=0.3)
    kwargs = mock_router.infer.call_args[1]
    assert kwargs["max_tokens"] == 256
    assert kwargs["temperature"] == 0.3


def test_llm_health(llm, mock_router):
    """health() delegates to the router."""
    mock_router.health = MagicMock(return_value={"local": True})
    # Note: health is sync in old API, but now wraps router
    # We test that it doesn't crash
    assert llm.health() is not None


def test_llm_backward_compat_base_url():
    """LLMClient still accepts base_url for backward compatibility."""
    client = LLMClient(base_url="http://localhost:8384")
    assert client._router is not None


def test_llm_accepts_router():
    """LLMClient accepts a pre-built router."""
    router = MagicMock(spec=ProviderRouter)
    client = LLMClient(router=router)
    assert client._router is router
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/inference/test_llm.py -v`
Expected: FAIL — `LLMClient.__init__() got an unexpected keyword argument 'router'`

- [ ] **Step 3: Rewrite LLMClient**

Replace `nexus/inference/llm.py` with:

```python
"""
LLM inference client for Nexus.
Delegates to a ProviderRouter for multi-provider support.
Backward-compatible: accepts base_url for local-only setups.
"""
from nexus.inference.provider import InferenceProvider
from nexus.inference.router import ProviderRouter
from nexus.inference.local import LocalProvider


class LLMClient:
    def __init__(
        self,
        router: ProviderRouter | None = None,
        base_url: str = "http://localhost:8384",
    ):
        if router is not None:
            self._router = router
        else:
            # Backward-compatible: create a router with just the local provider
            self._router = ProviderRouter(default="local")
            self._router.register(LocalProvider(base_url=base_url))

    async def infer(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        provider: str | None = None,
    ) -> str:
        """Infer from a raw prompt string. Wraps in a user message for the router."""
        messages = [{"role": "user", "content": prompt}]
        return await self._router.infer(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            provider=provider,
        )

    async def chat(
        self,
        system: str,
        user: str,
        history: list[dict[str, str]] | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        provider: str | None = None,
    ) -> str:
        """Build a messages list from system/user/history and route."""
        messages: list[dict] = [{"role": "system", "content": system}]
        for msg in history or []:
            messages.append(msg)
        messages.append({"role": "user", "content": user})
        return await self._router.infer(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            provider=provider,
        )

    def health(self) -> bool:
        """Synchronous health check — checks if the default local provider is up."""
        local = self._router._providers.get("local")
        if local and isinstance(local, LocalProvider):
            return local.health()
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/inference/test_llm.py -v`
Expected: 10 passed

- [ ] **Step 5: Run the full inference test suite**

Run: `.venv/bin/python -m pytest tests/inference/ -v`
Expected: All tests pass (provider + local + openai + anthropic + router + llm)

- [ ] **Step 6: Commit**

```bash
git add nexus/inference/llm.py tests/inference/test_llm.py
git commit -m "refactor(inference): LLMClient now delegates to ProviderRouter

Backward-compatible: base_url still works for local-only setups.
New: router param accepts a pre-built ProviderRouter for multi-provider."
```

---

## Task 7: Update NexusConfig for Multi-Provider

**Files:**
- Modify: `nexus/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
# Add these tests to the existing test_config.py

def test_config_default_provider(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.default_provider == "local"


def test_config_default_provider_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DEFAULT_PROVIDER", "openai")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.default_provider == "openai"


def test_config_api_keys_default_none(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_api_key is None
    assert cfg.anthropic_api_key is None


def test_config_api_keys_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_OPENAI_KEY", "sk-test-123")
    monkeypatch.setenv("NEXUS_ANTHROPIC_KEY", "ant-test-456")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_api_key == "sk-test-123"
    assert cfg.anthropic_api_key == "ant-test-456"


def test_config_model_names_default(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_model == "gpt-4o-mini"
    assert cfg.anthropic_model == "claude-sonnet-4-20250514"


def test_config_model_names_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_OPENAI_MODEL", "gpt-4o")
    monkeypatch.setenv("NEXUS_ANTHROPIC_MODEL", "claude-opus-4-20250514")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.openai_model == "gpt-4o"
    assert cfg.anthropic_model == "claude-opus-4-20250514"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -v -k "provider or api_key or model_names"`
Expected: FAIL — `AttributeError: 'NexusConfig' has no attribute 'default_provider'`

- [ ] **Step 3: Update NexusConfig**

Add these helper functions and fields to `nexus/config.py`:

```python
# Add these factory functions after the existing ones

def _default_provider() -> str:
    return os.environ.get("NEXUS_DEFAULT_PROVIDER", "local")


def _default_openai_key() -> Optional[str]:
    return os.environ.get("NEXUS_OPENAI_KEY")


def _default_anthropic_key() -> Optional[str]:
    return os.environ.get("NEXUS_ANTHROPIC_KEY")


def _default_openai_model() -> str:
    return os.environ.get("NEXUS_OPENAI_MODEL", "gpt-4o-mini")


def _default_anthropic_model() -> str:
    return os.environ.get("NEXUS_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
```

Add these fields to the `NexusConfig` dataclass after the existing fields:

```python
    default_provider: str = field(default_factory=_default_provider)
    openai_api_key: Optional[str] = field(default_factory=_default_openai_key)
    anthropic_api_key: Optional[str] = field(default_factory=_default_anthropic_key)
    openai_model: str = field(default_factory=_default_openai_model)
    anthropic_model: str = field(default_factory=_default_anthropic_model)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add nexus/config.py tests/test_config.py
git commit -m "feat(config): add multi-provider fields (default_provider, API keys, model names)"
```

---

## Task 8: Update CLI to Wire Multi-Provider

**Files:**
- Modify: `nexus/cli.py`

- [ ] **Step 1: Update the `run()` command**

Replace lines 69-131 of `nexus/cli.py` (the `run()` function) with:

```python
@main.command()
def run():
    """Start the Nexus interactive session."""
    cfg = NexusConfig()

    from nexus.kernel.engram import Engram
    from nexus.kernel.chronicle import Chronicle
    from nexus.kernel.aegis import Aegis
    from nexus.kernel.pulse import Pulse
    from nexus.kernel.cortex import Cortex
    from nexus.modules.general import GeneralModule
    from nexus.inference.llm import LLMClient
    from nexus.inference.router import ProviderRouter
    from nexus.inference.local import LocalProvider

    engram = Engram(cfg.db_path)
    engram.init_db()
    chronicle = Chronicle(cfg.db_path)
    chronicle.init_db()
    aegis = Aegis(cfg.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(
        engram=engram,
        chronicle=chronicle,
        aegis=aegis,
        pulse=pulse,
        config=cfg,
    )

    general = GeneralModule()
    cortex.register_module(general)
    aegis.set_policy("general", allowed=True)

    # Build the provider router
    router = ProviderRouter(default=cfg.default_provider)

    # Always register local provider
    local = LocalProvider(base_url=f"http://localhost:{cfg.llm_port}")
    router.register(local)

    # Register cloud providers if API keys are configured
    if cfg.openai_api_key:
        from nexus.inference.openai_provider import OpenAIProvider
        router.register(OpenAIProvider(api_key=cfg.openai_api_key, model=cfg.openai_model))
        click.echo(f"OpenAI provider registered (model: {cfg.openai_model})")

    if cfg.anthropic_api_key:
        from nexus.inference.anthropic_provider import AnthropicProvider
        router.register(AnthropicProvider(api_key=cfg.anthropic_api_key, model=cfg.anthropic_model))
        click.echo(f"Anthropic provider registered (model: {cfg.anthropic_model})")

    llm_client = LLMClient(router=router)

    if local.health():
        click.echo(f"Local LLM connected at localhost:{cfg.llm_port}")
    else:
        if cfg.default_provider == "local":
            click.echo("Local LLM not detected — running in offline mode.")
            click.echo(f"Start llama.cpp on port {cfg.llm_port} for local inference.")
        else:
            click.echo(f"Using {cfg.default_provider} as default provider.")

    cortex.set_llm(lambda msg: llm_client.chat(
        system="You are Nexus, an autonomous intelligence operating system. Be helpful, precise, and concise.",
        user=msg,
    ))

    click.echo("")
    click.echo("NEXUS v" + __version__)
    click.echo("Type a message. Ctrl+C to exit.")
    click.echo("---")

    async def session():
        while True:
            try:
                user_input = click.prompt("", prompt_suffix="> ")
            except (click.Abort, EOFError):
                click.echo("\nSession ended.")
                break
            if not user_input.strip():
                continue
            response = await cortex.process(user_input)
            click.echo(response)
            click.echo("")

    asyncio.run(session())
```

- [ ] **Step 2: Run the full test suite to verify nothing breaks**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All 288 tests pass

- [ ] **Step 3: Commit**

```bash
git add nexus/cli.py
git commit -m "feat(cli): wire multi-provider router into nexus run command"
```

---

## Task 9: MessageBridge ABC

**Files:**
- Create: `nexus/messaging/__init__.py`
- Create: `nexus/messaging/bridge.py`
- Create: `tests/messaging/__init__.py`
- Create: `tests/messaging/test_bridge.py`

- [ ] **Step 1: Create the package init files**

```python
# nexus/messaging/__init__.py
```

```python
# tests/messaging/__init__.py
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/messaging/test_bridge.py
import pytest
from nexus.messaging.bridge import MessageBridge


def test_bridge_is_abstract():
    """MessageBridge cannot be instantiated directly."""
    with pytest.raises(TypeError):
        MessageBridge()


def test_bridge_subclass_must_implement_start():
    with pytest.raises(TypeError):
        class Bad(MessageBridge):
            name = "bad"
            async def stop(self) -> None: pass
            async def send(self, chat_id: str, text: str) -> None: pass
            async def on_message(self, callback) -> None: pass
        Bad()


def test_bridge_subclass_must_implement_send():
    with pytest.raises(TypeError):
        class Bad(MessageBridge):
            name = "bad"
            async def start(self) -> None: pass
            async def stop(self) -> None: pass
            async def on_message(self, callback) -> None: pass
        Bad()


@pytest.mark.asyncio
async def test_valid_bridge_subclass():
    """A complete subclass can be instantiated."""
    class StubBridge(MessageBridge):
        name = "stub"
        async def start(self) -> None: pass
        async def stop(self) -> None: pass
        async def send(self, chat_id: str, text: str) -> None: pass
        async def on_message(self, callback) -> None:
            self._callback = callback

    bridge = StubBridge()
    assert bridge.name == "stub"
    await bridge.start()
    await bridge.stop()
    await bridge.send("123", "hello")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/messaging/test_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.messaging'`

- [ ] **Step 4: Write the implementation**

```python
# nexus/messaging/bridge.py
"""
MessageBridge — abstract base class for messaging platform integrations.
Each bridge handles connection, sending, and receiving for one platform.
"""
from abc import ABC, abstractmethod
from typing import Callable, Awaitable


# Callback signature: async def handler(chat_id: str, text: str, source: str) -> str
MessageCallback = Callable[[str, str, str], Awaitable[str]]


class MessageBridge(ABC):
    name: str

    @abstractmethod
    async def start(self) -> None:
        """Connect to the platform and begin listening."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Disconnect cleanly."""
        ...

    @abstractmethod
    async def send(self, chat_id: str, text: str) -> None:
        """Send a message to a specific chat/channel."""
        ...

    @abstractmethod
    async def on_message(self, callback: MessageCallback) -> None:
        """Register a callback for inbound messages."""
        ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/messaging/test_bridge.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add nexus/messaging/__init__.py nexus/messaging/bridge.py tests/messaging/__init__.py tests/messaging/test_bridge.py
git commit -m "feat(messaging): add MessageBridge ABC for platform integrations"
```

---

## Task 10: TelegramBridge

**Files:**
- Create: `nexus/messaging/telegram.py`
- Create: `tests/messaging/test_telegram.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/messaging/test_telegram.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexus.messaging.telegram import TelegramBridge
from nexus.messaging.bridge import MessageBridge


def test_telegram_bridge_is_message_bridge():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    assert isinstance(bridge, MessageBridge)


def test_telegram_bridge_name():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    assert bridge.name == "telegram"


def test_telegram_bridge_stores_config():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123", "456"])
    assert bridge._token == "fake-token"
    assert bridge._allowed_chat_ids == {"123", "456"}


@pytest.mark.asyncio
async def test_telegram_bridge_on_message_registers_callback():
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)
    assert bridge._callback is callback


@pytest.mark.asyncio
async def test_telegram_bridge_ignores_unauthorized_chat():
    """Messages from non-allowed chats should be ignored."""
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)

    # Simulate an update from unauthorized chat
    mock_update = MagicMock()
    mock_update.message.chat_id = 999
    mock_update.message.text = "hello"
    mock_context = MagicMock()

    await bridge._handle_message(mock_update, mock_context)
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_telegram_bridge_processes_authorized_chat():
    """Messages from allowed chats should be processed."""
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock(return_value="nexus response")
    await bridge.on_message(callback)

    mock_update = MagicMock()
    mock_update.message.chat_id = 123
    mock_update.message.text = "hello nexus"
    mock_context = MagicMock()
    mock_context.bot.send_message = AsyncMock()

    await bridge._handle_message(mock_update, mock_context)
    callback.assert_called_once_with("123", "hello nexus", "telegram")
    mock_context.bot.send_message.assert_called_once_with(
        chat_id=123, text="nexus response"
    )


@pytest.mark.asyncio
async def test_telegram_bridge_send():
    """send() should call the bot's send_message."""
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    bridge._app = MagicMock()
    bridge._app.bot.send_message = AsyncMock()

    await bridge.send("123", "outbound message")
    bridge._app.bot.send_message.assert_called_once_with(
        chat_id=123, text="outbound message"
    )


@pytest.mark.asyncio
async def test_telegram_bridge_ignores_empty_messages():
    """Empty or None text messages should be ignored."""
    bridge = TelegramBridge(token="fake-token", allowed_chat_ids=["123"])
    callback = AsyncMock()
    await bridge.on_message(callback)

    mock_update = MagicMock()
    mock_update.message.chat_id = 123
    mock_update.message.text = None
    mock_context = MagicMock()

    await bridge._handle_message(mock_update, mock_context)
    callback.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/messaging/test_telegram.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.messaging.telegram'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/messaging/telegram.py
"""
TelegramBridge — two-way Telegram messaging for NEXUS.
Uses python-telegram-bot. Only processes messages from allowed chat IDs.
"""
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from nexus.messaging.bridge import MessageBridge, MessageCallback


class TelegramBridge(MessageBridge):
    name = "telegram"

    def __init__(self, token: str, allowed_chat_ids: list[str]):
        self._token = token
        self._allowed_chat_ids = set(allowed_chat_ids)
        self._callback: MessageCallback | None = None
        self._app: Application | None = None

    async def start(self) -> None:
        self._app = Application.builder().token(self._token).build()
        self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        await self._app.initialize()
        await self._app.start()
        await self._app.updater.start_polling()

    async def stop(self) -> None:
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    async def send(self, chat_id: str, text: str) -> None:
        if self._app:
            await self._app.bot.send_message(chat_id=int(chat_id), text=text)

    async def on_message(self, callback: MessageCallback) -> None:
        self._callback = callback

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return

        chat_id = str(update.message.chat_id)
        if chat_id not in self._allowed_chat_ids:
            return

        if self._callback:
            response = await self._callback(chat_id, update.message.text, "telegram")
            await context.bot.send_message(chat_id=update.message.chat_id, text=response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/messaging/test_telegram.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/messaging/telegram.py tests/messaging/test_telegram.py
git commit -m "feat(messaging): add TelegramBridge with chat ID allowlisting"
```

---

## Task 11: DiscordBridge

**Files:**
- Create: `nexus/messaging/discord_bridge.py`
- Create: `tests/messaging/test_discord.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/messaging/test_discord.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexus.messaging.discord_bridge import DiscordBridge
from nexus.messaging.bridge import MessageBridge


def test_discord_bridge_is_message_bridge():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    assert isinstance(bridge, MessageBridge)


def test_discord_bridge_name():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    assert bridge.name == "discord"


def test_discord_bridge_stores_config():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123", "456"])
    assert bridge._token == "fake-token"
    assert bridge._allowed_channel_ids == {"123", "456"}


@pytest.mark.asyncio
async def test_discord_bridge_on_message_registers_callback():
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)
    assert bridge._callback is callback


@pytest.mark.asyncio
async def test_discord_bridge_ignores_unauthorized_channel():
    """Messages from non-allowed channels should be ignored."""
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)

    mock_message = MagicMock()
    mock_message.channel.id = 999
    mock_message.content = "hello"
    mock_message.author.bot = False

    await bridge._handle_message(mock_message)
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_discord_bridge_ignores_bot_messages():
    """Bot messages should be ignored to prevent loops."""
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="response")
    await bridge.on_message(callback)

    mock_message = MagicMock()
    mock_message.channel.id = 123
    mock_message.content = "hello"
    mock_message.author.bot = True

    await bridge._handle_message(mock_message)
    callback.assert_not_called()


@pytest.mark.asyncio
async def test_discord_bridge_processes_authorized_channel():
    """Messages from allowed channels should be processed."""
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock(return_value="nexus response")
    await bridge.on_message(callback)

    mock_message = MagicMock()
    mock_message.channel.id = 123
    mock_message.content = "hello nexus"
    mock_message.author.bot = False
    mock_message.channel.send = AsyncMock()

    await bridge._handle_message(mock_message)
    callback.assert_called_once_with("123", "hello nexus", "discord")
    mock_message.channel.send.assert_called_once_with("nexus response")


@pytest.mark.asyncio
async def test_discord_bridge_send():
    """send() should fetch the channel and send a message."""
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    mock_channel = MagicMock()
    mock_channel.send = AsyncMock()

    bridge._client = MagicMock()
    bridge._client.get_channel = MagicMock(return_value=mock_channel)

    await bridge.send("123", "outbound message")
    mock_channel.send.assert_called_once_with("outbound message")


@pytest.mark.asyncio
async def test_discord_bridge_ignores_empty_messages():
    """Empty messages should be ignored."""
    bridge = DiscordBridge(token="fake-token", allowed_channel_ids=["123"])
    callback = AsyncMock()
    await bridge.on_message(callback)

    mock_message = MagicMock()
    mock_message.channel.id = 123
    mock_message.content = ""
    mock_message.author.bot = False

    await bridge._handle_message(mock_message)
    callback.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/messaging/test_discord.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.messaging.discord_bridge'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/messaging/discord_bridge.py
"""
DiscordBridge — two-way Discord messaging for NEXUS.
Uses discord.py. Only processes messages from allowed channel IDs.
Ignores bot messages to prevent feedback loops.
"""
import asyncio
import discord
from nexus.messaging.bridge import MessageBridge, MessageCallback


class DiscordBridge(MessageBridge):
    name = "discord"

    def __init__(self, token: str, allowed_channel_ids: list[str]):
        self._token = token
        self._allowed_channel_ids = set(allowed_channel_ids)
        self._callback: MessageCallback | None = None
        intents = discord.Intents.default()
        intents.message_content = True
        self._client = discord.Client(intents=intents)

        @self._client.event
        async def on_message(message: discord.Message):
            await self._handle_message(message)

    async def start(self) -> None:
        asyncio.create_task(self._client.start(self._token))

    async def stop(self) -> None:
        await self._client.close()

    async def send(self, chat_id: str, text: str) -> None:
        channel = self._client.get_channel(int(chat_id))
        if channel:
            await channel.send(text)

    async def on_message(self, callback: MessageCallback) -> None:
        self._callback = callback

    async def _handle_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        if not message.content:
            return

        channel_id = str(message.channel.id)
        if channel_id not in self._allowed_channel_ids:
            return

        if self._callback:
            response = await self._callback(channel_id, message.content, "discord")
            await message.channel.send(response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/messaging/test_discord.py -v`
Expected: 9 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/messaging/discord_bridge.py tests/messaging/test_discord.py
git commit -m "feat(messaging): add DiscordBridge with channel ID allowlisting"
```

---

## Task 12: BridgeManager

**Files:**
- Create: `nexus/messaging/manager.py`
- Create: `tests/messaging/test_manager.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/messaging/test_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexus.messaging.manager import BridgeManager
from nexus.messaging.bridge import MessageBridge
from nexus.kernel.pulse import Pulse, Message


class FakeBridge(MessageBridge):
    name = "fake"

    def __init__(self):
        self._started = False
        self._stopped = False
        self._callback = None
        self._sent: list[tuple[str, str]] = []

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._stopped = True

    async def send(self, chat_id: str, text: str) -> None:
        self._sent.append((chat_id, text))

    async def on_message(self, callback) -> None:
        self._callback = callback


@pytest.fixture
def pulse():
    return Pulse()


@pytest.fixture
def mock_cortex():
    cortex = MagicMock()
    cortex.process = AsyncMock(return_value="nexus says hello")
    return cortex


@pytest.fixture
def manager(pulse, mock_cortex):
    return BridgeManager(pulse=pulse, cortex_process=mock_cortex.process)


def test_manager_register_bridge(manager):
    bridge = FakeBridge()
    manager.register(bridge)
    assert "fake" in manager._bridges


@pytest.mark.asyncio
async def test_manager_start_starts_all_bridges(manager):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()
    assert bridge._started is True


@pytest.mark.asyncio
async def test_manager_stop_stops_all_bridges(manager):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()
    await manager.stop()
    assert bridge._stopped is True


@pytest.mark.asyncio
async def test_manager_routes_inbound_to_cortex(manager, mock_cortex):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()

    # Simulate an inbound message via the registered callback
    assert bridge._callback is not None
    response = await bridge._callback("chat123", "hello nexus", "fake")
    mock_cortex.process.assert_called_once_with("hello nexus")
    assert response == "nexus says hello"


@pytest.mark.asyncio
async def test_manager_subscribes_to_notify_events(manager, pulse):
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()

    # Publish a notify event
    await pulse.publish(Message(
        topic="notify.dream_loop",
        source="dream_loop",
        payload={"text": "I found a pattern!"},
    ))
    await pulse.drain()

    assert len(bridge._sent) == 1
    assert bridge._sent[0][1] == "I found a pattern!"


@pytest.mark.asyncio
async def test_manager_notify_sends_to_all_bridges(manager, pulse):
    bridge1 = FakeBridge()
    bridge1.name = "fake1"
    bridge2 = FakeBridge()
    bridge2.name = "fake2"
    manager.register(bridge1)
    manager.register(bridge2)
    await manager.start()

    await pulse.publish(Message(
        topic="notify.test",
        source="test",
        payload={"text": "broadcast"},
    ))
    await pulse.drain()

    assert len(bridge1._sent) == 1
    assert len(bridge2._sent) == 1


@pytest.mark.asyncio
async def test_manager_no_bridges_is_fine(manager):
    """Manager with no bridges should start and stop without errors."""
    await manager.start()
    await manager.stop()


@pytest.mark.asyncio
async def test_manager_notify_without_text_uses_topic(manager, pulse):
    """Notify events without a 'text' key should use the topic as fallback."""
    bridge = FakeBridge()
    manager.register(bridge)
    await manager.start()

    await pulse.publish(Message(
        topic="notify.alert",
        source="test",
        payload={"severity": "high"},
    ))
    await pulse.drain()

    assert len(bridge._sent) == 1
    assert "notify.alert" in bridge._sent[0][1]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/messaging/test_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'nexus.messaging.manager'`

- [ ] **Step 3: Write the implementation**

```python
# nexus/messaging/manager.py
"""
BridgeManager — lifecycle manager for messaging bridges.
Routes inbound messages to Cortex, subscribes to Pulse notify.* events for outbound.
"""
from typing import Callable, Awaitable
from nexus.messaging.bridge import MessageBridge
from nexus.kernel.pulse import Pulse, Message


class BridgeManager:
    def __init__(
        self,
        pulse: Pulse,
        cortex_process: Callable[[str], Awaitable[str]],
    ):
        self._pulse = pulse
        self._cortex_process = cortex_process
        self._bridges: dict[str, MessageBridge] = {}
        self._pulse_sub_id: str | None = None

    def register(self, bridge: MessageBridge) -> None:
        self._bridges[bridge.name] = bridge

    async def start(self) -> None:
        """Start all bridges and subscribe to notify events."""
        for bridge in self._bridges.values():
            await bridge.on_message(self._handle_inbound)
            await bridge.start()

        self._pulse_sub_id = self._pulse.subscribe("notify.*", self._handle_notify)

    async def stop(self) -> None:
        """Stop all bridges and unsubscribe from Pulse."""
        if self._pulse_sub_id:
            self._pulse.unsubscribe(self._pulse_sub_id)

        for bridge in self._bridges.values():
            await bridge.stop()

    async def _handle_inbound(self, chat_id: str, text: str, source: str) -> str:
        """Route an inbound message from any bridge through Cortex."""
        return await self._cortex_process(text)

    async def _handle_notify(self, msg: Message) -> None:
        """Forward a Pulse notify event to all active bridges."""
        text = msg.payload.get("text", f"[{msg.topic}] {msg.payload}")
        for bridge in self._bridges.values():
            # Send to all known chat IDs for this bridge
            for chat_id in getattr(bridge, "_allowed_chat_ids", set()) | getattr(bridge, "_allowed_channel_ids", set()):
                await bridge.send(chat_id, text)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/messaging/test_manager.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add nexus/messaging/manager.py tests/messaging/test_manager.py
git commit -m "feat(messaging): add BridgeManager for lifecycle and Pulse-to-bridge routing"
```

---

## Task 13: Update NexusConfig for Messaging

**Files:**
- Modify: `nexus/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_config.py`:

```python
def test_config_telegram_defaults(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.telegram_token is None
    assert cfg.telegram_chat_ids == []


def test_config_telegram_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_TELEGRAM_TOKEN", "tg-token-123")
    monkeypatch.setenv("NEXUS_TELEGRAM_CHAT_IDS", "111,222,333")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.telegram_token == "tg-token-123"
    assert cfg.telegram_chat_ids == ["111", "222", "333"]


def test_config_discord_defaults(tmp_path):
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.discord_token is None
    assert cfg.discord_channel_ids == []


def test_config_discord_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DISCORD_TOKEN", "dc-token-456")
    monkeypatch.setenv("NEXUS_DISCORD_CHANNEL_IDS", "aaa,bbb")
    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")
    assert cfg.discord_token == "dc-token-456"
    assert cfg.discord_channel_ids == ["aaa", "bbb"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_config.py -v -k "telegram or discord"`
Expected: FAIL — `AttributeError: 'NexusConfig' has no attribute 'telegram_token'`

- [ ] **Step 3: Update NexusConfig**

Add these factory functions and fields to `nexus/config.py`:

```python
# Add after the existing provider factory functions

def _default_telegram_token() -> Optional[str]:
    return os.environ.get("NEXUS_TELEGRAM_TOKEN")


def _default_telegram_chat_ids() -> list[str]:
    val = os.environ.get("NEXUS_TELEGRAM_CHAT_IDS", "")
    return [s.strip() for s in val.split(",") if s.strip()] if val else []


def _default_discord_token() -> Optional[str]:
    return os.environ.get("NEXUS_DISCORD_TOKEN")


def _default_discord_channel_ids() -> list[str]:
    val = os.environ.get("NEXUS_DISCORD_CHANNEL_IDS", "")
    return [s.strip() for s in val.split(",") if s.strip()] if val else []
```

Add these fields to `NexusConfig`:

```python
    telegram_token: Optional[str] = field(default_factory=_default_telegram_token)
    telegram_chat_ids: list[str] = field(default_factory=_default_telegram_chat_ids)
    discord_token: Optional[str] = field(default_factory=_default_discord_token)
    discord_channel_ids: list[str] = field(default_factory=_default_discord_channel_ids)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_config.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add nexus/config.py tests/test_config.py
git commit -m "feat(config): add Telegram and Discord messaging fields"
```

---

## Task 14: Wire Messaging into CLI

**Files:**
- Modify: `nexus/cli.py`

- [ ] **Step 1: Update `run()` to start BridgeManager**

Add the following block to `nexus/cli.py`'s `run()` function, after the `cortex.set_llm(...)` call and before the `click.echo("")` line:

```python
    # Start messaging bridges if configured
    from nexus.messaging.manager import BridgeManager
    bridge_manager = BridgeManager(pulse=pulse, cortex_process=cortex.process)

    if cfg.telegram_token and cfg.telegram_chat_ids:
        from nexus.messaging.telegram import TelegramBridge
        tg_bridge = TelegramBridge(token=cfg.telegram_token, allowed_chat_ids=cfg.telegram_chat_ids)
        bridge_manager.register(tg_bridge)
        click.echo(f"Telegram bridge registered ({len(cfg.telegram_chat_ids)} allowed chats)")

    if cfg.discord_token and cfg.discord_channel_ids:
        from nexus.messaging.discord_bridge import DiscordBridge
        dc_bridge = DiscordBridge(token=cfg.discord_token, allowed_channel_ids=cfg.discord_channel_ids)
        bridge_manager.register(dc_bridge)
        click.echo(f"Discord bridge registered ({len(cfg.discord_channel_ids)} allowed channels)")
```

Update the `session()` async function to start/stop the bridge manager:

```python
    async def session():
        await bridge_manager.start()
        try:
            while True:
                try:
                    user_input = click.prompt("", prompt_suffix="> ")
                except (click.Abort, EOFError):
                    click.echo("\nSession ended.")
                    break
                if not user_input.strip():
                    continue
                response = await cortex.process(user_input)
                click.echo(response)
                click.echo("")
        finally:
            await bridge_manager.stop()
```

- [ ] **Step 2: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add nexus/cli.py
git commit -m "feat(cli): wire messaging bridges into nexus run lifecycle"
```

---

## Task 15: Update pyproject.toml Dependencies

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add new dependencies**

Add to the `dependencies` list in `pyproject.toml`:

```toml
dependencies = [
    "click>=8.1",
    "opentelemetry-api>=1.20",
    "opentelemetry-sdk>=1.20",
    "sqlite-vec>=0.1.1",
    "llama-cpp-python>=0.2.50",
    "smolagents>=1.0",
    "litellm>=1.30",
    "openai>=1.0",
    "anthropic>=0.30",
    "python-telegram-bot>=21.0",
    "discord.py>=2.3",
]
```

- [ ] **Step 2: Install updated dependencies**

Run: `.venv/bin/pip install -e ".[all]"` or `.venv/bin/pip install -e .`

- [ ] **Step 3: Run the full test suite to verify nothing broke**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add openai, anthropic, python-telegram-bot, discord.py"
```

---

## Task 16: Integration Tests

**Files:**
- Create: `tests/test_batch7a_integration.py`

- [ ] **Step 1: Write the integration tests**

```python
# tests/test_batch7a_integration.py
"""
Batch 7a integration tests — multi-provider inference and messaging bridges.
Tests the full flow from config through router to LLMClient, and
BridgeManager inbound/outbound with Pulse.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from nexus.config import NexusConfig
from nexus.inference.llm import LLMClient
from nexus.inference.router import ProviderRouter
from nexus.inference.local import LocalProvider
from nexus.inference.provider import InferenceProvider
from nexus.messaging.manager import BridgeManager
from nexus.messaging.bridge import MessageBridge
from nexus.kernel.pulse import Pulse, Message
from nexus.kernel.cortex import Cortex
from nexus.kernel.engram import Engram
from nexus.kernel.chronicle import Chronicle
from nexus.kernel.aegis import Aegis
from nexus.modules.general import GeneralModule


# --- Multi-Provider Integration ---

@pytest.mark.asyncio
async def test_llm_client_with_multi_provider_router():
    """LLMClient with a router containing multiple providers routes correctly."""
    class StubProvider(InferenceProvider):
        name = "stub"
        async def infer(self, messages, max_tokens=1024, temperature=0.7):
            return "stub says hi"
        async def health(self):
            return True

    router = ProviderRouter(default="stub")
    router.register(StubProvider())
    client = LLMClient(router=router)

    result = await client.chat(system="System.", user="Hello")
    assert result == "stub says hi"


@pytest.mark.asyncio
async def test_llm_client_backward_compat_with_local():
    """LLMClient created with just base_url still works."""
    client = LLMClient(base_url="http://localhost:8384")
    assert "local" in client._router.list_providers()


@pytest.mark.asyncio
async def test_router_provider_fallback():
    """When requested provider is unhealthy, falls back to default."""
    class HealthyProvider(InferenceProvider):
        name = "healthy"
        async def infer(self, messages, max_tokens=1024, temperature=0.7):
            return "healthy response"
        async def health(self):
            return True

    class UnhealthyProvider(InferenceProvider):
        name = "sick"
        async def infer(self, messages, max_tokens=1024, temperature=0.7):
            return "never seen"
        async def health(self):
            return False

    router = ProviderRouter(default="healthy")
    router.register(HealthyProvider())
    router.register(UnhealthyProvider())

    result = await router.infer([{"role": "user", "content": "hi"}], provider="sick")
    assert result == "healthy response"


# --- Messaging Integration ---

class InMemoryBridge(MessageBridge):
    name = "memory"

    def __init__(self):
        self._callback = None
        self._sent: list[tuple[str, str]] = []
        self._started = False
        self._allowed_chat_ids = {"test-chat"}

    async def start(self):
        self._started = True
    async def stop(self):
        self._started = False
    async def send(self, chat_id, text):
        self._sent.append((chat_id, text))
    async def on_message(self, callback):
        self._callback = callback


@pytest.mark.asyncio
async def test_bridge_manager_routes_inbound_through_cortex(tmp_config, mock_llm_response):
    """Inbound bridge message -> Cortex -> module -> response."""
    engram = Engram(tmp_config.db_path)
    engram.init_db()
    chronicle = Chronicle(tmp_config.db_path)
    chronicle.init_db()
    aegis = Aegis(tmp_config.db_path)
    aegis.init_db()
    pulse = Pulse()

    cortex = Cortex(engram=engram, chronicle=chronicle, aegis=aegis, pulse=pulse, config=tmp_config)
    general = GeneralModule()
    cortex.register_module(general)
    aegis.set_policy("general", allowed=True)
    cortex.set_llm(mock_llm_response("nexus response"))

    bridge = InMemoryBridge()
    manager = BridgeManager(pulse=pulse, cortex_process=cortex.process)
    manager.register(bridge)
    await manager.start()

    response = await bridge._callback("test-chat", "hello", "memory")
    assert "nexus response" in response
    await manager.stop()


@pytest.mark.asyncio
async def test_bridge_manager_forwards_notify_events():
    """Pulse notify.* events are forwarded to all bridges."""
    pulse = Pulse()
    cortex_process = AsyncMock(return_value="ok")

    bridge = InMemoryBridge()
    manager = BridgeManager(pulse=pulse, cortex_process=cortex_process)
    manager.register(bridge)
    await manager.start()

    await pulse.publish(Message(
        topic="notify.dream_loop",
        source="dream_loop",
        payload={"text": "Found a pattern in your emails"},
    ))
    await pulse.drain()

    assert len(bridge._sent) == 1
    assert "Found a pattern" in bridge._sent[0][1]
    await manager.stop()


@pytest.mark.asyncio
async def test_config_reads_provider_settings(tmp_path, monkeypatch):
    """NexusConfig reads all provider and messaging settings from env."""
    monkeypatch.setenv("NEXUS_DEFAULT_PROVIDER", "openai")
    monkeypatch.setenv("NEXUS_OPENAI_KEY", "sk-test")
    monkeypatch.setenv("NEXUS_ANTHROPIC_KEY", "ant-test")
    monkeypatch.setenv("NEXUS_TELEGRAM_TOKEN", "tg-token")
    monkeypatch.setenv("NEXUS_TELEGRAM_CHAT_IDS", "111,222")
    monkeypatch.setenv("NEXUS_DISCORD_TOKEN", "dc-token")
    monkeypatch.setenv("NEXUS_DISCORD_CHANNEL_IDS", "aaa")

    cfg = NexusConfig(data_dir=tmp_path / "nexus_data")

    assert cfg.default_provider == "openai"
    assert cfg.openai_api_key == "sk-test"
    assert cfg.anthropic_api_key == "ant-test"
    assert cfg.telegram_token == "tg-token"
    assert cfg.telegram_chat_ids == ["111", "222"]
    assert cfg.discord_token == "dc-token"
    assert cfg.discord_channel_ids == ["aaa"]
```

- [ ] **Step 2: Run integration tests**

Run: `.venv/bin/python -m pytest tests/test_batch7a_integration.py -v`
Expected: 6 passed

- [ ] **Step 3: Run the full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All tests pass (288 existing + new inference + messaging + integration)

- [ ] **Step 4: Commit**

```bash
git add tests/test_batch7a_integration.py
git commit -m "test: add Batch 7a integration tests for multi-provider and messaging"
```

---

## Task 17: Update README and Site

**Files:**
- Modify: `README.md`
- Modify: `site/src/components/Hero.astro`
- Modify: `site/src/content/docs/index.mdx`
- Modify: `site/src/content/docs/architecture/overview.md`
- Modify: `site/src/content/docs/architecture/modules.md`
- Modify: `site/src/content/docs/guides/running-tests.md`

This task updates all documentation to reflect the new multi-provider and messaging capabilities. The exact test count and module count should be determined by running `pytest tests/ -v` and counting, but the infrastructure adds no new modules (only kernel-level capabilities), so the module count stays at **25** (Batch 7b will bump it to 34). The test count will increase based on the actual number of tests added.

- [ ] **Step 1: Count the actual tests**

Run: `.venv/bin/python -m pytest tests/ -v --co -q | tail -1`
This will output the total test count. Use this number in all updates below. The plan estimates ~350 tests but use the actual count.

- [ ] **Step 2: Update README.md**

Update the badges, architecture section, What's Built section, and project structure to include:
- New test count in badge
- "Multi-Provider Inference" subsection under What's Built describing provider abstraction, OpenAI/Anthropic support
- "Messaging Integrations" subsection describing Telegram/Discord bridges
- New files in project structure: `nexus/inference/provider.py`, `local.py`, `openai_provider.py`, `anthropic_provider.py`, `router.py`, `nexus/messaging/` directory

- [ ] **Step 3: Update Hero.astro**

Update the test count stat value to match actual.

- [ ] **Step 4: Update index.mdx**

No module count change for 7a. Update test count reference if present.

- [ ] **Step 5: Update architecture docs**

Update `overview.md` test count. Update `running-tests.md` test count (both references). No module count changes for 7a.

- [ ] **Step 6: Run site build to verify**

Run: `cd site && npm run build` (if available)

- [ ] **Step 7: Commit all doc updates**

```bash
git add README.md site/
git commit -m "docs: update README and site for Batch 7a (multi-provider, messaging)"
```
