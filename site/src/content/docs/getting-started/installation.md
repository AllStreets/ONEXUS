---
title: Installation
description: Install NEXUS from source on any Python 3.11+ system.
sidebar:
  order: 1
---

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Python | 3.11 or later |
| Disk | 500 MB for NEXUS core |
| GPU | Not required |

No cloud accounts, API keys, or internet connection required after setup. The kernel runs standalone -- connect a model provider whenever you're ready.

## Install from Source

```bash
git clone https://github.com/AllStreets/ONEXUS.git
cd ONEXUS
pip install -e .
```

The editable install (`-e`) means changes to the source are immediately reflected without reinstalling.

## Verify Installation

```bash
onexus status
```

Expected output:

```
NEXUS  ready
kernel   cortex  engram  pulse  chronicle  aegis
modules  0 active
data     ~/.local/share/nexus/
```

If the command is not found, ensure your Python scripts directory is on `$PATH`. For pipx installs or virtual environments, activate the environment first.

## Optional: Connect a Model

NEXUS works without a language model for rule-based modules (Sentry, Chronicle queries, agents, etc.), but the cognitive modules (Council, Specter, Oracle, etc.) require an LLM.

Three options:

### Option A: Cloud Provider (fastest setup)

Set an environment variable and go:

```bash
# OpenAI
export NEXUS_OPENAI_KEY=sk-...
export NEXUS_DEFAULT_PROVIDER=openai

# Anthropic
export NEXUS_ANTHROPIC_KEY=sk-ant-...
export NEXUS_DEFAULT_PROVIDER=anthropic
```

Or register at runtime via the API after the kernel is already running:

```bash
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-...", "set_default": true}'
```

### Option B: Local Open-Source Model

Run any model locally via [llama.cpp](https://github.com/ggerganov/llama.cpp), [Ollama](https://ollama.com), or [vLLM](https://github.com/vllm-project/vllm):

```bash
# llama.cpp
llama-server --model qwen3-8b-q4.gguf --port 8384 --ctx-size 8192

# Ollama
ollama serve  # then: ollama run qwen3:8b
```

NEXUS auto-connects to `localhost:8384` by default. Override with `NEXUS_LLM_PORT`.

### Option C: No Model

Start the kernel without any model. Memory, trust, audit, and event routing all work. Connect a provider later when you need inference.

## Data Directory

NEXUS stores all runtime data -- memory databases, audit logs, trust scores -- in a single directory following the XDG Base Directory spec:

```
~/.local/share/nexus/
+-- nexus.db         # memory, audit log, trust scores (single SQLite)
+-- models/          # local model files (optional)
```

To relocate this directory, set `NEXUS_DATA_DIR` before first run.
