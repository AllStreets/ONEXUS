---
title: Connecting an LLM
description: Connect NEXUS to a local open-source model, OpenAI, Anthropic, or any compatible provider.
sidebar:
  order: 2
---

NEXUS is model-agnostic. The kernel runs without any model -- connect a provider when you need inference. Three paths: cloud API, local open-source model, or runtime registration.

## Option A: Cloud Providers

The fastest way to get inference running. Set an env var and start the kernel.

### OpenAI

```bash
export NEXUS_OPENAI_KEY=sk-...
export NEXUS_DEFAULT_PROVIDER=openai
onexus run
```

Available models: `gpt-4o`, `gpt-4o-mini`, `o3`, `o3-mini`. Default: `gpt-4o-mini`. Override with `NEXUS_OPENAI_MODEL`.

### Anthropic

```bash
export NEXUS_ANTHROPIC_KEY=sk-ant-...
export NEXUS_DEFAULT_PROVIDER=anthropic
onexus run
```

Available models: `claude-opus-4-20250514`, `claude-sonnet-4-20250514`, `claude-haiku-4-5-20251001`. Default: `claude-sonnet-4-20250514`. Override with `NEXUS_ANTHROPIC_MODEL`.

## Option B: Local Open-Source Models

Run any model locally for full data sovereignty. NEXUS connects to any server exposing an OpenAI-compatible or llama.cpp HTTP API.

### llama.cpp

```bash
# Install
brew install llama.cpp  # macOS
# or build from source: https://github.com/ggerganov/llama.cpp

# Download a model (GGUF format)
huggingface-cli download Qwen/Qwen3-8B-GGUF \
  qwen3-8b-instruct-q4_k_m.gguf \
  --local-dir ~/.local/share/nexus/models/

# Start the server
llama-server \
  --model ~/.local/share/nexus/models/qwen3-8b-instruct-q4_k_m.gguf \
  --port 8384 \
  --ctx-size 8192

# Start NEXUS (auto-connects to localhost:8384)
onexus run
```

### Ollama

```bash
# Install from https://ollama.com
ollama pull qwen3:8b
ollama serve   # starts on port 11434

# Point NEXUS at Ollama
NEXUS_LLM_PORT=11434 onexus run
```

### vLLM

```bash
vllm serve Qwen/Qwen3-8B --port 8384
onexus run
```

### Recommended Open-Source Models

All MIT or Apache 2.0 licensed:

| Model | Notes |
|-------|-------|
| Qwen 3 8B | Default recommendation -- good balance of speed and quality |
| Qwen 3 32B | Complex reasoning, long-context tasks |
| DeepSeek-R1 7B | Strong code generation and technical analysis |
| Phi-4 Mini | Fast responses, lightweight |
| Llama 3.1 8B | General purpose, well-rounded |
| Gemma 2 9B | Strong multilingual support |

## Option C: Runtime Registration

Register providers while the kernel is already running. No restart required.

```bash
# Start the kernel with no model
onexus serve

# Register OpenAI at runtime
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "openai", "api_key": "sk-...", "model": "gpt-4o", "set_default": true}'

# Register Anthropic at runtime
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "anthropic", "api_key": "sk-ant-...", "set_default": true}'

# Register a local model server
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "local", "base_url": "http://localhost:11434", "set_default": true}'
```

### Provider Management

```bash
# List all providers and their health
curl http://localhost:8000/api/providers

# Switch default provider
curl -X POST http://localhost:8000/api/providers/default/anthropic

# Remove a provider
curl -X DELETE http://localhost:8000/api/providers/openai
```

The provider router automatically falls back to the default if a requested provider is unhealthy.

## Remote Endpoints

Serve the model on a different machine while NEXUS runs locally:

```bash
# On the model server
llama-server --model qwen3-32b-q4.gguf --host 0.0.0.0 --port 8384

# On the NEXUS machine -- register the remote server
curl -X POST http://localhost:8000/api/providers \
  -H "Content-Type: application/json" \
  -d '{"provider": "local", "base_url": "http://model-server.local:8384", "set_default": true}'
```

All other NEXUS behavior (memory, audit, trust) remains local. Only LLM inference is remote.

## Verifying the Connection

```bash
onexus status
```

Or check provider health via the API:

```bash
curl http://localhost:8000/api/providers
```

Modules that require inference will fail gracefully with an error message if no provider is reachable. Modules that do not use the LLM (Oracle, Sentry) continue to function normally.
