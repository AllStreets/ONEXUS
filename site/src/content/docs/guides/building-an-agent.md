---
title: Build an Agent
description: Build a task-specialist agent with graduated sovereignty -- five trust tiers that unlock progressively more capable behavior.
sidebar:
  order: 2
---

Agents are task specialists that start as passive skills and earn autonomy through demonstrated reliability. They extend AgentModule (which itself extends NexusModule) and implement four tier methods instead of a single `handle()`.

If you want a simpler persistent intelligence component without graduated sovereignty, see [Build a Module](/NEXUS/guides/building-a-module/).

---

## Modules vs. Agents

| | Module (NexusModule) | Agent (AgentModule) |
|---|---|---|
| **Purpose** | Persistent intelligence (perception, reasoning, memory) | Narrow task specialist (code review, log analysis, invoicing) |
| **Entry point** | `handle()` | `analyze()` + `suggest()` + `monitor()` + `coordinate()` |
| **Trust** | Binary allow/deny | Graduated sovereignty (0-100 across 5 tiers) |
| **Event watching** | Manual Pulse subscription | Automatic via `watch_events` at MONITOR+ trust |
| **Cross-agent routing** | Not built in | Built in via `coordination_targets` at SOVEREIGN trust |

---

## Trust Tiers

AgentModule routes through five trust tiers based on the agent's Aegis score:

| Tier | Score | What Unlocks |
|------|-------|-------------|
| **SKILL** | 0-24 | User invokes explicitly. `analyze()` only. |
| **ADVISOR** | 25-49 | `suggest()` appends proactive recommendations after analysis. |
| **MONITOR** | 50-74 | `monitor()` watches Pulse events in the background. |
| **AUTONOMOUS** | 75-99 | Acts within defined boundaries. Logged to Chronicle. |
| **SOVEREIGN** | 100 | `coordinate()` routes to other agents independently. |

Trust is always revocable. One bad outcome and Aegis dials it back.

---

## The Base Class

```python
# nexus/agents/base.py
class AgentModule(NexusModule):
    watch_events: list[str] = []          # Pulse topics for MONITOR+
    coordination_targets: list[str] = []  # Agent names for SOVEREIGN

    async def analyze(self, message, context) -> str: ...     # always
    async def suggest(self, message, context) -> str: ...     # ADVISOR+
    async def monitor(self, event, context) -> str: ...       # MONITOR+
    async def coordinate(self, result, context) -> str: ...   # SOVEREIGN
```

The `handle()` method is implemented by AgentModule itself -- it checks the agent's trust score and routes through the appropriate tier methods automatically. You never override `handle()` in an agent.

---

## Step 1 -- Create the Agent File

Create a new Python file in `nexus/agents/`. Every agent needs `name`, `description`, `version`, and must implement at least `analyze()`.

```python
# nexus/agents/scanner.py
from nexus.agents.base import AgentModule, TrustTier


class ScannerAgent(AgentModule):
    name = "scanner"
    description = "Scans directories for file patterns and reports findings."
    version = "0.1.0"

    watch_events = ["filesystem.changed", "scan.requested"]
    coordination_targets = ["vigil", "vex"]

    async def analyze(self, message: str, context: dict) -> str:
        """Core logic. Runs at every trust level.

        Pattern-based analysis first (no LLM required).
        LLM enhances when available.
        """
        # Pattern-based analysis -- always works
        findings = []
        keywords = ["scan", "find", "search", "look for", "check"]
        matched = [k for k in keywords if k in message.lower()]

        if not matched:
            return f"[{self.name}] Send a scan request to analyze files."

        # Extract what to scan for
        target = message.lower()
        if "large" in target or "size" in target:
            findings.append("Scan type: large file detection")
        elif "duplicate" in target:
            findings.append("Scan type: duplicate detection")
        else:
            findings.append("Scan type: general pattern match")

        result = f"[{self.name}] {'; '.join(findings)}"

        # LLM enhancement when available
        llm = context.get("llm")
        if llm:
            try:
                enhanced = await llm.complete(
                    f"Given this scan request: '{message}', "
                    f"what specific file patterns should be checked? "
                    f"Be concise."
                )
                result += f"\n[{self.name}:llm] {enhanced}"
            except Exception:
                pass  # pattern-based result is fine

        return result

    async def suggest(self, message: str, context: dict) -> str:
        """Proactive suggestions at ADVISOR+ trust (25+)."""
        if "duplicate" in message.lower():
            return "Consider running a hash-based comparison for exact matches."
        if "large" in message.lower():
            return "You can set a size threshold with 'scan large files > 100MB'."
        return ""

    async def monitor(self, event: dict, context: dict) -> str:
        """Background event watching at MONITOR+ trust (50+)."""
        payload = event.get("payload", {})
        path = payload.get("path", "")
        if path and path.endswith((".log", ".tmp", ".bak")):
            return f"Detected temporary file activity: {path}"
        return None

    async def coordinate(self, analysis_result: str, context: dict) -> str:
        """Cross-agent coordination at SOVEREIGN trust (100)."""
        cortex = context.get("cortex")
        if not cortex or not analysis_result:
            return ""

        results = []
        # Route security-relevant findings to Vex
        if "security" in analysis_result.lower() or "credential" in analysis_result.lower():
            vex_result = await cortex.route("vex", analysis_result)
            if vex_result:
                results.append(f"[vex] {vex_result}")

        return "\n".join(results)
```

### Design Principles

Every agent should follow these patterns:

1. **Pattern-based first** -- `analyze()` must produce useful output without an LLM using regex, keyword matching, or structural analysis
2. **LLM-enhanced second** -- when a model is available, use it to deepen the analysis
3. **No cloud required** -- agents run locally with zero network dependencies
4. **8GB RAM floor** -- keep memory usage reasonable; no loading large models or datasets

---

## Step 2 -- Register Routing Keywords

Open `nexus/kernel/cortex.py` and add an entry to `_MODULE_KEYWORDS`:

```python
_MODULE_KEYWORDS = {
    # ... existing entries ...
    "scanner": ["scan", "find files", "search files", "directory", "file pattern"],
}
```

Agents use the same keyword routing as modules. Cortex doesn't distinguish between them -- both are NexusModule subclasses to the router.

---

## Step 3 -- Write Tests

```python
# tests/agents/test_scanner.py
import pytest
from unittest.mock import AsyncMock
from nexus.agents.scanner import ScannerAgent


@pytest.fixture
def agent():
    return ScannerAgent()


@pytest.fixture
def context():
    return {
        "llm": AsyncMock(),
        "engram": AsyncMock(),
        "chronicle": AsyncMock(),
        "pulse": AsyncMock(),
        "aegis": AsyncMock(),
        "cortex": AsyncMock(),
    }


def test_agent_attributes(agent):
    assert agent.name == "scanner"
    assert agent.description
    assert agent.version
    assert agent.watch_events
    assert agent.coordination_targets


@pytest.mark.asyncio
async def test_analyze_pattern_based(agent, context):
    """analyze() works without LLM."""
    context["llm"] = None
    result = await agent.analyze("scan for large files", context)
    assert "[scanner]" in result
    assert "large file" in result.lower()


@pytest.mark.asyncio
async def test_analyze_with_llm(agent, context):
    """analyze() enhances with LLM when available."""
    context["llm"].complete.return_value = "Check *.log and *.tmp patterns"
    result = await agent.analyze("scan for large files", context)
    assert "[scanner:llm]" in result


@pytest.mark.asyncio
async def test_suggest_at_advisor(agent, context):
    """suggest() returns recommendations."""
    result = await agent.suggest("scan for duplicate files", context)
    assert "hash" in result.lower()


@pytest.mark.asyncio
async def test_monitor_detects_temp_files(agent, context):
    """monitor() flags temporary file activity."""
    event = {"payload": {"path": "/tmp/debug.log"}}
    result = await agent.monitor(event, context)
    assert "temporary" in result.lower()


@pytest.mark.asyncio
async def test_coordinate_routes_to_vex(agent, context):
    """coordinate() sends security findings to Vex."""
    context["cortex"].route.return_value = "Found credential exposure"
    result = await agent.coordinate("[scanner] security issue found", context)
    assert "vex" in result.lower()
```

---

## Step 4 -- Run Tests

```bash
pytest tests/agents/test_scanner.py -v
```

Full suite:

```bash
pytest tests/ -v
```

---

## Step 5 -- Enable the Agent

```bash
nexus allow scanner
```

The agent starts at trust 0 (SKILL tier). Only `analyze()` runs. As Aegis observes successful outcomes, trust rises:

```
Score 0   -> SKILL:      analyze() only
Score 25  -> ADVISOR:    analyze() + suggest()
Score 50  -> MONITOR:    + background event watching
Score 75  -> AUTONOMOUS: + acts without user invocation
Score 100 -> SOVEREIGN:  + coordinates with other agents
```

Test it:

```
> scan my project for large files
[scanner] Scan type: large file detection
[scanner:advisor] You can set a size threshold with 'scan large files > 100MB'.
```

---

## Trust Lifecycle

```
          +1 per successful response
          ─────────────────────────>
  SKILL ──── ADVISOR ──── MONITOR ──── AUTONOMOUS ──── SOVEREIGN
          <─────────────────────────
          -5 per unhandled exception
          Revocable at any time by Aegis
```

Cortex automatically adjusts trust after every interaction:
- Successful response: `+1`
- Unhandled exception: `-5`
- Manual override: `nexus deny scanner` drops to 0

---

## What's Next

- [Build a Module](/NEXUS/guides/building-a-module/) -- simpler persistent intelligence components
- [Earned Autonomy](/NEXUS/concepts/earned-autonomy/) -- deep dive into the trust tier system
- [Agent Discovery](/NEXUS/community/agents/) -- browse the 25 built-in agents
- [Agent Workflows](/NEXUS/guides/agent-workflows/) -- multi-agent coordination patterns
