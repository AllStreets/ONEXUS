---
title: Installation
description: Install NEXUS from source on any Python 3.11+ system with 8GB RAM.
sidebar:
  order: 1
---

## Prerequisites

| Requirement | Minimum |
|-------------|---------|
| Python | 3.11 or later |
| RAM | 8 GB (16 GB recommended for larger models) |
| Disk | 500 MB for NEXUS + model storage (4–20 GB per model) |
| GPU | Not required — all inference runs on CPU |

No cloud accounts, API keys, or internet connection required after setup.

## Install from Source

```bash
git clone https://github.com/your-org/nexus.git
cd nexus
pip install -e .
```

The editable install (`-e`) means changes to the source are immediately reflected without reinstalling.

## Verify Installation

```bash
nexus status
```

Expected output:

```
NEXUS  ready
kernel   cortex  engram  pulse  chronicle  aegis
modules  0 active
data     ~/.local/share/nexus/
```

If the command is not found, ensure your Python scripts directory is on `$PATH`. For pipx installs or virtual environments, activate the environment first.

## Optional: Local LLM Setup

NEXUS works without a language model for rule-based modules (Sentry, Chronicle queries, etc.), but the intelligence tier (Atlas, Prism, Cipher, Dreamweaver) requires an LLM accessible over HTTP.

The recommended backend is [llama.cpp](https://github.com/ggerganov/llama.cpp). Install it separately:

```bash
# macOS (Homebrew)
brew install llama.cpp

# or build from source
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp && make
```

Download a model (see [Configuration](/getting-started/configuration/) for the full model table), then start the server:

```bash
llama-server \
  --model ~/.local/share/nexus/models/qwen3-8b-q4.gguf \
  --port 8080 \
  --ctx-size 8192
```

NEXUS auto-connects to `localhost:8080` by default. Override with `NEXUS_LLM_HOST` and `NEXUS_LLM_PORT`.

## Data Directory

NEXUS stores all runtime data — memory databases, audit logs, trust scores — in a single directory following the XDG Base Directory spec:

```
~/.local/share/nexus/
├── engram.db        # working, episodic, and semantic memory
├── chronicle.db     # immutable audit log
├── aegis.db         # trust scores per module
└── models/          # GGUF model files (optional)
```

To relocate this directory, set `NEXUS_DATA_DIR` before first run.
