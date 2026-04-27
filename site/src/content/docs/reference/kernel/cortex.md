---
title: "Cortex"
description: ""
sidebar:
  order: 1
---

## Overview

Cortex — the Nexus router and orchestrator.
Receives user input, selects the appropriate module, enforces permissions,
logs to Chronicle, and stores interactions in Engram.

- **Version:** `0.1.0`
- **Class:** `Cortex`

## API

### `set_llm(self, llm_fn) -> None`

Set the LLM inference function used by modules.

### `register_module(self, module: NexusModule) -> None`

### `unregister_module(self, name: str) -> None`

### `list_modules(self) -> list[str]`

### `async process(self, message: str) -> str`

Route a user message to the appropriate module and return the response.
