---
title: Configuration
description: Environment variables, data directory layout, and provider configuration for NEXUS.
sidebar:
  order: 3
---

## Data Directory

NEXUS follows the [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir-spec/basedir-spec-latest.html). The default data directory is:

```
~/.local/share/nexus/
```

Override it at any time:

```bash
export NEXUS_DATA_DIR=/mnt/fast-ssd/nexus
onexus run
```

The directory is created on first run if it does not exist. All databases live here.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_DATA_DIR` | `~/.local/share/nexus/` | Root directory for all runtime data |
| `NEXUS_LLM_PORT` | `8384` | Port of the local LLM HTTP server |
| `NEXUS_DEFAULT_PROVIDER` | `local` | Default inference provider (`local`, `openai`, `anthropic`) |
| `NEXUS_OPENAI_KEY` | — | OpenAI API key (enables OpenAI provider) |
| `NEXUS_ANTHROPIC_KEY` | — | Anthropic API key (enables Anthropic provider) |
| `NEXUS_OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model name |
| `NEXUS_ANTHROPIC_MODEL` | `claude-sonnet-4-20250514` | Anthropic model name |
| `NEXUS_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `NEXUS_AGENTS_CATALOG` | — | Path to an ONEXUS-Agents catalog clone |

Variables can be set in your shell profile or in a `.env` file in the working directory.

## Inference Providers

NEXUS is model-agnostic. The kernel runs without any model connected -- connect a provider at startup via env vars or at runtime via the API.

### Cloud Providers

```bash
# OpenAI
export NEXUS_OPENAI_KEY=sk-...
export NEXUS_DEFAULT_PROVIDER=openai
onexus run

# Anthropic
export NEXUS_ANTHROPIC_KEY=sk-ant-...
export NEXUS_DEFAULT_PROVIDER=anthropic
onexus run
```

### Local Open-Source Models

Run any model locally via [llama.cpp](https://github.com/ggerganov/llama.cpp), [Ollama](https://ollama.com), or [vLLM](https://github.com/vllm-project/vllm). NEXUS connects to `localhost:8384` by default.

Compatible open-source models (all MIT or Apache 2.0):

| Model | Notes |
|-------|-------|
| Qwen 3 8B | Good balance of speed and quality |
| Qwen 3 32B | Complex reasoning, long-context tasks |
| DeepSeek-R1 7B | Code generation, technical analysis |
| Phi-4 Mini | Fast responses, lightweight |
| Llama 3.1 8B | General purpose, well-rounded |
| Gemma 2 9B | Strong multilingual support |

```bash
# llama.cpp
llama-server --model qwen3-8b-q4.gguf --port 8384 --ctx-size 8192

# Ollama
ollama serve  # then: ollama run qwen3:8b
```

### Runtime Provider Registration

Providers can be added, removed, and switched while the kernel is running:

```bash
# List providers
curl http://localhost:8000/api/providers

# Register OpenAI
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-...", "model": "gpt-4o", "set_default": true}'

# Register Anthropic
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic", "api_key": "sk-ant-...", "set_default": true}'

# Register a local model server
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "local", "base_url": "http://localhost:11434", "set_default": true}'

# Switch default
curl -X POST http://localhost:8000/api/providers/default/anthropic

# Remove a provider
curl -X DELETE http://localhost:8000/api/providers/openai
```

The provider router automatically falls back to the default if a specific provider is unhealthy.

## Persistence

All state is durable across sessions. There is no configuration file for runtime state -- everything is stored in SQLite databases inside `NEXUS_DATA_DIR`:

| Database | Contents |
|----------|----------|
| `nexus.db` | Memory (working, episodic, semantic), audit log (WAL), trust scores and outcome history |

To start completely fresh, run `onexus forget --yes` (clears Engram only) or delete the data directory entirely.
