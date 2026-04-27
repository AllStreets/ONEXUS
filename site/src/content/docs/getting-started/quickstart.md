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

## Start with a Local LLM

If you have llama-server installed, start it first:

```bash
llama-server \
  --model ~/.local/share/nexus/models/qwen3-8b-q4.gguf \
  --port 8080 \
  --ctx-size 8192 &

nexus run
```

NEXUS detects the running server and enables LLM-backed modules automatically.

## Enable Modules

By default, no modules are active. Enable them explicitly:

```bash
# Enable a single module
nexus allow oracle

# Enable multiple modules
nexus allow oracle atlas prism
```

Modules start with a trust score of 50/100 from Aegis. Trust increases as the module produces useful outcomes and decreases on failures or policy violations.

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
llm      localhost:8080  qwen3-8b
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
