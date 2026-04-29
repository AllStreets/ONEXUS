---
title: "Agent Workflows"
description: "Chain agents through Cortex and Pulse -- build multi-step pipelines programmatically"
sidebar:
  order: 4
---

## Agent Workflows

Agents are independent by default -- each handles a message and returns a result. But the real power is chaining them. This guide covers the three mechanisms for building multi-agent pipelines.

---

### 1. Sequential Chaining via Cortex

The simplest pipeline: take the output of one agent and route it to another through Cortex.

```python
# Inside a custom module or script
async def security_audit(file_content: str, context: dict) -> str:
    """Run Vex (vulnerability scan) then Arbiter (code review) on the same file."""
    cortex = context["cortex"]

    # Step 1: Vulnerability scan
    vuln_report = await cortex.route(f"scan for vulnerabilities:\n{file_content}")

    # Step 2: Code quality review (separate agent, same input)
    quality_report = await cortex.route(f"review this code:\n{file_content}")

    # Step 3: Combine results
    return f"--- Security ---\n{vuln_report}\n\n--- Quality ---\n{quality_report}"
```

Cortex handles keyword matching and routing. Each agent runs independently -- they don't know about each other.

**When to use:** Simple two or three-step pipelines where each step is independent.

---

### 2. Event-Driven Chaining via Pulse

For reactive pipelines where one agent's output should automatically trigger another, use Pulse subscriptions.

```python
from nexus.modules.base import NexusModule


class AuditPipeline(NexusModule):
    name = "audit_pipeline"
    description = "Chains Vex findings into Remedy for automatic fix suggestions."
    version = "1.0.0"

    async def on_load(self, context: dict) -> None:
        # Subscribe to Vex completion events
        await context["pulse"].subscribe("vex.completed", self._on_vex_done)

    async def _on_vex_done(self, event: dict) -> None:
        """When Vex finds vulnerabilities, automatically ask Remedy for fixes."""
        findings = event.get("data", {}).get("findings", [])
        if not findings:
            return

        # Build a message for Remedy
        errors = "\n".join(f"- {f}" for f in findings)
        message = f"diagnose these issues and suggest fixes:\n{errors}"

        # Route through Cortex (hits Remedy via keyword matching)
        context = event.get("context", {})
        if context:
            fix_suggestions = await context["cortex"].route(message)
            await context["pulse"].publish("audit_pipeline.fixes", {
                "original_findings": findings,
                "suggestions": fix_suggestions,
            })

    async def handle(self, message: str, context: dict) -> str:
        return "[AuditPipeline] Listening for Vex events. Run a vulnerability scan to trigger."

    async def on_unload(self, context: dict) -> None:
        await context["pulse"].unsubscribe("vex.completed", self._on_vex_done)
```

**When to use:** Pipelines that should run automatically when conditions are met. Background workflows. Monitoring chains.

---

### 3. Multi-Agent Deliberation via Council

For decisions that benefit from multiple perspectives, use Council. It orchestrates a structured debate across relevant modules.

```
> should I migrate our database from Postgres to MongoDB?
[council] Convening deliberation...
  Round 1:
    specter: Migration risk — data model mismatch, query rewrite cost
    prism: Cross-domain analysis — your usage patterns suggest relational fits better
    ethical_prism: Contractual obligations to current hosting provider
  Round 2:
    specter: Counter to prism — document store could simplify the API layer
    prism: Agrees on API simplification but flags reporting queries
  Synthesis:
    RECOMMENDATION: Stay on Postgres. API simplification doesn't outweigh migration cost.
    DISSENT: Specter notes MongoDB could reduce API complexity if reporting moves to a warehouse.
```

Council automatically selects which modules to include based on the topic. You don't need to wire anything.

**When to use:** High-stakes decisions. Questions where you want structured debate rather than a single answer.

---

### Pipeline Patterns

#### Fan-Out: One Input, Multiple Agents

Send the same input to several agents and collect all results.

```python
async def comprehensive_review(code: str, context: dict) -> dict:
    """Run security, quality, and complexity analysis in parallel."""
    import asyncio

    cortex = context["cortex"]
    results = await asyncio.gather(
        cortex.route(f"scan for vulnerabilities:\n{code}"),    # -> Vex
        cortex.route(f"review this code:\n{code}"),            # -> Arbiter
        cortex.route(f"measure complexity:\n{code}"),          # -> Carve
    )

    return {
        "security": results[0],
        "quality": results[1],
        "complexity": results[2],
    }
```

#### Conditional Routing: Branch Based on Results

Route to different agents based on what the first agent found.

```python
async def smart_analysis(message: str, context: dict) -> str:
    """Analyze content and route to the right specialist."""
    cortex = context["cortex"]

    # Detect what kind of content this is
    if "error" in message.lower() or "traceback" in message.lower():
        return await cortex.route(f"diagnose this error:\n{message}")  # -> Remedy

    elif "contract" in message.lower() or "agreement" in message.lower():
        return await cortex.route(f"review this contract:\n{message}")  # -> Redline

    elif any(kw in message.lower() for kw in ["log", "incident", "anomaly"]):
        return await cortex.route(f"analyze these logs:\n{message}")    # -> Vigil

    else:
        return await cortex.route(message)  # -> default routing
```

#### Pipeline with Memory: Store Intermediate Results

Use Engram to persist intermediate results between pipeline stages.

```python
async def research_pipeline(topic: str, context: dict) -> str:
    """Multi-stage research: search -> analyze -> summarize."""
    cortex = context["cortex"]
    engram = context["engram"]

    # Stage 1: Extract structured data
    raw_data = await cortex.route(f"extract data from: {topic}")

    # Store intermediate result
    await engram.store_episodic(
        source="research_pipeline",
        content=raw_data,
        tags=["research", "intermediate"],
    )

    # Stage 2: Analyze with context from memory
    prior = await engram.query_episodic("research", limit=5)
    context_str = "\n".join(r["content"] for r in prior)

    analysis = await cortex.route(
        f"analyze this data in context:\n{raw_data}\n\nPrior research:\n{context_str}"
    )

    return analysis
```

---

### Pulse Event Reference

Agents emit events when they complete work. Subscribe to these for event-driven pipelines.

| Event Pattern | Emitted By | Payload |
|---------------|-----------|---------|
| `vex.completed` | Vex | `findings`, `severity_counts` |
| `arbiter.completed` | Arbiter | `issues`, `score` |
| `vigil.completed` | Vigil | `anomalies`, `timeline` |
| `council.completed` | Council | `recommendation`, `dissent`, `rounds` |
| `cortex.response` | Cortex (all routes) | `module`, `message`, `response` |

The `cortex.response` event fires on every routed message. Six modules (Prism, Serendipity, Cipher, Atlas, Weave, Legacy) subscribe to it by default to passively collect data from the conversation flow.

---

### Testing Workflows

Test multi-agent pipelines the same way you test single modules -- mock the context.

```python
import pytest
from unittest.mock import AsyncMock


@pytest.mark.asyncio
async def test_security_audit_chains_correctly():
    context = {
        "cortex": AsyncMock(),
        "pulse": AsyncMock(),
        "engram": AsyncMock(),
    }

    # Mock Cortex routing
    context["cortex"].route.side_effect = [
        "[vex] 2 vulnerabilities found",   # First call -> Vex
        "[arbiter] 1 style issue",          # Second call -> Arbiter
    ]

    # Run your pipeline
    result = await security_audit("def foo(): pass", context)

    # Verify both agents were called
    assert context["cortex"].route.call_count == 2
    assert "Security" in result
    assert "Quality" in result
```
