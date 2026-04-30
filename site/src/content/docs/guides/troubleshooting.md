---
title: "Troubleshooting"
description: "Common issues and fixes for NEXUS installation, modules, inference, and testing"
sidebar:
  order: 5
---

## Troubleshooting

Solutions for the most common issues encountered when running NEXUS.

---

### Installation

**`nexus: command not found`**

The `nexus` CLI is a Python entry point. Ensure your Python scripts directory is on `$PATH`:

```bash
# Check where pip installed the script
pip show -f nexus | grep bin

# Add to PATH if needed (adjust for your system)
export PATH="$HOME/.local/bin:$PATH"
```

If using a virtual environment, activate it first:

```bash
source .venv/bin/activate
nexus status
```

**`ModuleNotFoundError: No module named 'nexus'`**

The package isn't installed in the active Python environment. Install with:

```bash
pip install -e .
```

The `-e` flag means editable -- changes to source are reflected immediately.

**`Python version 3.10 is not supported`**

NEXUS requires Python 3.11+. Check your version:

```bash
python --version
```

If you have multiple Python versions, use the correct one:

```bash
python3.11 -m pip install -e .
```

---

### LLM Connection

**`Connection refused on localhost:8080`**

The llama.cpp server isn't running. Start it:

```bash
llama-server \
  --model ~/.local/share/nexus/models/qwen3-8b-q4.gguf \
  --port 8080 \
  --ctx-size 8192
```

Or check if it's running on a different port:

```bash
# Find llama-server processes
ps aux | grep llama-server
```

Override the port in NEXUS:

```bash
export NEXUS_LLM_PORT=8384
nexus run
```

**`Model too large for available memory`** (local models only)

If using a local GGUF model that doesn't fit:

- Use a smaller quantization: Q4_K_M instead of Q8
- Use a smaller model: Phi-4 Mini instead of Qwen 3 8B
- Reduce context size: `--ctx-size 4096` instead of 8192
- Switch to a cloud provider (OpenAI/Anthropic) to avoid local model requirements entirely

**Cognitive modules return errors but rule-based modules work**

Cognitive modules (Council, Specter, Oracle, etc.) require an LLM. Rule-based modules (Sentry, Oracle trigger rules) work without one. Check that a provider is registered and healthy:

```bash
curl http://localhost:8000/api/providers
```

---

### Modules

**`Module 'xyz' denied -- trust too low`**

Aegis blocked the module because its trust score is 0 or below the required threshold. Enable it:

```bash
nexus allow xyz
```

New modules start at trust 50. If trust has degraded due to failures, the module needs positive outcomes to rebuild trust.

**`Module not found in routing table`**

Cortex doesn't have routing keywords for this module. Check `nexus/kernel/cortex.py` for the `_MODULE_KEYWORDS` dictionary. If you're building a new module, add keywords:

```python
_MODULE_KEYWORDS = {
    ...
    "my_module": ["keyword1", "keyword2", "keyword3"],
}
```

**Messages always route to the wrong module**

Cortex routes by keyword score -- the module with the most keyword matches wins. If your message matches another module's keywords more strongly, be more specific:

```
# Vague -- might hit the wrong module
> analyze this

# Specific -- clearly targets Vex
> scan this code for vulnerabilities
```

Check the [Routing Table](/NEXUS/reference/routing/) for all keyword-to-module mappings.

---

### Testing

**`PytestCollectionWarning: cannot collect test class 'TestCase'`**

A dataclass or class named `TestCase` is being picked up by pytest as a test class. Rename it to avoid the `Test` prefix:

```python
# Bad -- pytest tries to collect this
@dataclass
class TestCase:
    input: str
    expected: str

# Good -- not collected
@dataclass
class GeneratedTest:
    input: str
    expected: str
```

**`asyncio_mode = "auto" not working`**

Check that `pytest-asyncio` is installed and your config is set:

```bash
pip install pytest-asyncio
```

In `pyproject.toml` or `pytest.ini`:

```ini
[tool:pytest]
asyncio_mode = strict
```

With `strict` mode, mark all async tests explicitly:

```python
@pytest.mark.asyncio
async def test_my_async_function():
    ...
```

**Tests pass locally but fail in CI**

Common causes:

- **Missing dependencies:** Ensure CI installs with `pip install -e ".[dev]"` or equivalent
- **Python version mismatch:** CI might use a different Python than local
- **File system differences:** Tests that depend on file paths may break on Linux vs macOS
- **Timing issues:** Async tests with real timeouts may be flaky on slow CI runners

---

### Data & Memory

**`Database is locked`**

Another NEXUS process is accessing the same data directory. Only one instance can write at a time. Check for running processes:

```bash
ps aux | grep nexus
```

Kill stale processes or use a different data directory:

```bash
export NEXUS_DATA_DIR=/tmp/nexus-test
nexus run
```

**Memory seems to be growing without limit**

Working memory (the ephemeral tier in Engram) doesn't have automatic garbage collection yet. For long-running sessions, periodically clear it:

```bash
nexus forget --yes
```

This clears Engram but preserves Chronicle (audit) and Aegis (trust scores).

**`nexus forget` doesn't clear everything**

By design. `nexus forget --yes` clears Engram (memory) only. Chronicle (audit trail) and Aegis (trust scores) are preserved. To fully reset:

```bash
rm -rf ~/.local/share/nexus/
nexus run  # recreates fresh databases
```

---

### Network Modules

**`Herald: network access denied`**

Herald and Collective require explicit network consent:

```bash
nexus allow --network herald
```

This is a separate gate from normal module trust. Both `nexus allow herald` (trust) and `nexus allow --network herald` (network) are required.

**Collective shares my data**

Collective shares noise-injected model aggregates, never raw data. Differential privacy is applied before any information leaves your instance. Every outbound event is logged to Chronicle -- you can audit exactly what was shared.
