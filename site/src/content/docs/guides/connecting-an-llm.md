---
title: Connecting an LLM
description: Set up a local LLM with llama.cpp or Ollama, configure NEXUS to connect, and switch models.
sidebar:
  order: 2
---

## Default Setup: llama.cpp

NEXUS connects to LLMs via the llama.cpp HTTP server API. This is the default and recommended path.

### 1. Install llama.cpp

```bash
# macOS (Homebrew — includes llama-server binary)
brew install llama.cpp

# Linux — build from source
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
make -j$(nproc)
# llama-server binary is at ./llama-server
```

### 2. Download a Model

All recommended models are MIT or Apache 2.0 licensed. Download in GGUF format.

| Model | Q4 Size | Min RAM | Notes |
|-------|---------|---------|-------|
| Qwen 3 8B | ~5 GB | 8 GB | Default recommendation |
| Qwen 3 32B | ~20 GB | 24 GB | Best quality, large RAM |
| DeepSeek-R1 7B | ~4.5 GB | 8 GB | Strong code generation |
| Phi-4 Mini | ~2.5 GB | 6 GB | Fastest, lowest RAM |

```bash
# Using huggingface-cli (pip install huggingface_hub)
huggingface-cli download Qwen/Qwen3-8B-GGUF \
  qwen3-8b-instruct-q4_k_m.gguf \
  --local-dir ~/.local/share/nexus/models/
```

### 3. Start the Server

```bash
llama-server \
  --model ~/.local/share/nexus/models/qwen3-8b-instruct-q4_k_m.gguf \
  --port 8080 \
  --ctx-size 8192 \
  --threads 8
```

Leave this running. NEXUS connects on startup. Start NEXUS in a separate terminal:

```bash
nexus run
```

## Environment Variable Overrides

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_LLM_HOST` | `localhost` | Hostname or IP of the llama-server |
| `NEXUS_LLM_PORT` | `8080` | Port llama-server is listening on |

```bash
# Example: model on a different port
NEXUS_LLM_PORT=11434 nexus run

# Example: model on a remote machine
NEXUS_LLM_HOST=192.168.1.100 NEXUS_LLM_PORT=8080 nexus run
```

## Using Ollama

Ollama exposes a compatible API at `localhost:11434`. NEXUS works with Ollama without any code changes.

```bash
# Install Ollama from https://ollama.com
ollama pull qwen3:8b
ollama serve   # starts on port 11434

# Run NEXUS against Ollama
NEXUS_LLM_PORT=11434 nexus run
```

Note: Ollama's API path differs slightly from llama.cpp's (`/api/generate` vs `/completion`). Verify the `LLMClient` in `nexus/kernel/llm.py` uses the correct endpoint for your backend.

## Remote Endpoints

For running NEXUS on a low-resource machine while serving the model on a more powerful one:

```bash
# On the model server — bind to all interfaces
llama-server \
  --model ~/models/qwen3-32b-q4.gguf \
  --host 0.0.0.0 \
  --port 8080

# On the NEXUS machine
NEXUS_LLM_HOST=model-server.local NEXUS_LLM_PORT=8080 nexus run
```

All other NEXUS behavior (memory, audit, trust) remains local. Only LLM inference is remote.

## Verifying the Connection

```bash
nexus status
```

A connected LLM shows:

```
llm  localhost:8080  qwen3-8b  (connected)
```

A disconnected or unreachable LLM shows:

```
llm  localhost:8080  (unreachable)
```

Modules that call `context["llm"]` will fail gracefully with an error message if the LLM is unreachable. Modules that do not use the LLM (Oracle, Sentry, General) continue to function normally.
