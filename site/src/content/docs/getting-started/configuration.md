---
title: Configuration
description: Environment variables, data directory layout, and model selection for NEXUS.
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
nexus run
```

The directory is created on first run if it does not exist. All databases and model files live here.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_DATA_DIR` | `~/.local/share/nexus/` | Root directory for all runtime data |
| `NEXUS_LLM_HOST` | `localhost` | Hostname of the llama.cpp HTTP server |
| `NEXUS_LLM_PORT` | `8080` | Port of the llama.cpp HTTP server |
| `NEXUS_LOG_LEVEL` | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Variables can be set in your shell profile or in a `.env` file in the working directory.

## Model Selection

NEXUS works with any GGUF model served over the llama.cpp HTTP API. All bundled model recommendations are MIT or Apache 2.0 licensed.

| Model | Size (Q4) | RAM Needed | Best For |
|-------|-----------|------------|----------|
| Qwen 3 8B | ~5 GB | 8 GB | Default — good balance of speed and quality |
| Qwen 3 32B | ~20 GB | 24 GB | Complex reasoning, long-context tasks |
| DeepSeek-R1 7B | ~4.5 GB | 8 GB | Code generation, technical analysis |
| Phi-4 Mini | ~2.5 GB | 6 GB | Fast responses, lower RAM systems |

### Downloading Models

Models are standard GGUF files. Download from Hugging Face or any compatible source:

```bash
# Example: Qwen 3 8B Q4_K_M
huggingface-cli download Qwen/Qwen3-8B-GGUF \
  qwen3-8b-instruct-q4_k_m.gguf \
  --local-dir ~/.local/share/nexus/models/
```

### Pointing NEXUS at a Model

Start llama-server with your chosen model before running NEXUS:

```bash
llama-server \
  --model ~/.local/share/nexus/models/qwen3-8b-instruct-q4_k_m.gguf \
  --port 8080 \
  --ctx-size 8192 \
  --threads 8
```

NEXUS does not manage model downloads or server lifecycle — it connects to whatever is running at `NEXUS_LLM_HOST:NEXUS_LLM_PORT`.

## Persistence

All state is durable across sessions. There is no configuration file for runtime state — everything is stored in SQLite databases inside `NEXUS_DATA_DIR`:

| Database | Contents |
|----------|----------|
| `engram.db` | Working memory (ephemeral), episodic memory (FTS5), semantic memory (sqlite-vec embeddings) |
| `chronicle.db` | Immutable append-only audit log (SQLite WAL mode) |
| `aegis.db` | Per-module trust scores and outcome history |

To start completely fresh, run `nexus forget --yes` (clears Engram only) or delete the data directory entirely.
