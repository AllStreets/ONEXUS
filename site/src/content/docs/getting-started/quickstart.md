---
title: Quickstart
description: Start a NEXUS session, enable your first modules, and send your first message.
sidebar:
  order: 2
---

## Start a Session

```bash
nexus run
```

This launches the NEXUS interactive session. The kernel boots (Cortex, Engram, Pulse, Chronicle, Aegis), loads any previously enabled modules, and drops into the prompt.

```
NEXUS ready. Type a message or 'help'.
>
```

## Connect a Model (Optional)

The kernel runs without a model. Connect one when you need inference:

```bash
# Cloud provider (fastest setup)
export NEXUS_OPENAI_KEY=sk-...
export NEXUS_DEFAULT_PROVIDER=openai
onexus run

# Or local open-source model
llama-server --model qwen3-8b-q4.gguf --port 8384 &
onexus run

# Or register at runtime after startup
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic", "api_key": "sk-ant-...", "set_default": true}'
```

## Enable Modules

By default, no modules are active. Enable them explicitly:

```bash
# Enable a single module
nexus allow oracle

# Enable multiple modules
nexus allow oracle atlas prism
```

Modules start with a trust score of 0.0 from Aegis. Trust increases (+0.12) as the module produces correct outcomes and decreases (-0.22) on failures -- the asymmetry is intentional.

To revoke a module:

```bash
nexus deny atlas
```

## Check Status

```bash
nexus status
```

```
NEXUS  running
kernel   cortex  engram  pulse  chronicle  aegis
modules  oracle [trust: 52]  atlas [trust: 50]
data     ~/.local/share/nexus/
llm      localhost:8384  qwen3-8b
```

## First Interaction

With Oracle enabled:

```
> what files changed in my project today?
[oracle] scanning filesystem...
3 files modified in ~/projects/nexus since 00:00
  nexus/kernel/cortex.py   14:32
  nexus/modules/atlas.py   11:05
  tests/test_atlas.py      11:08
```

With Atlas enabled (requires LLM):

```
> summarize what changed in cortex.py
[atlas] reading file and calling LLM...
cortex.py: Added wildcard routing support to _route(). Messages
matching '*' are now broadcast to all active modules. Trust gate
still enforced per module before dispatch.
```

## Forget All Memory

To wipe all stored memory and start fresh:

```bash
nexus forget --yes
```

This clears Engram (all three tiers) but leaves the audit trail in Chronicle and trust scores in Aegis intact.

## Build Your Own

NEXUS has two extensibility paths:

- **[Build a Module](/NEXUS/guides/building-a-module/)** -- persistent intelligence components (perception, reasoning, memory). Extend `NexusModule`, implement `handle()`, register keywords in Cortex.

- **[Build an Agent](/NEXUS/guides/building-an-agent/)** -- task specialists with graduated sovereignty. Extend `AgentModule`, implement `analyze()` + `suggest()` + `monitor()` + `coordinate()`. Agents start at trust 0 and earn autonomy through demonstrated reliability.

Both paths get full access to the kernel: Engram (memory), Chronicle (audit), Aegis (trust), Pulse (events), and LLM (inference).
