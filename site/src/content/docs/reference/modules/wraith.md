---
title: "PhantomStatus"
description: ""
sidebar:
  order: 6
---

## Overview

Wraith — phantom agent spawner.
Spawns ephemeral async micro-agents with single missions, time limits,
and auto-termination. Results merge into Engram automatically.

- **Version:** `0.1.0`
- **Class:** `PhantomStatus`
- **Module name:** `wraith`

## Tier

Tier 6 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `phantom`
- `spawn`
- `agent`
- `swarm`
- `research task`

## Types

### `Phantom`

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `—` |
| `mission` | `str` | `—` |
| `status` | `PhantomStatus` | `—` |
| `timeout_seconds` | `float` | `—` |
| `result` | `str` | `''` |
| `error` | `str` | `''` |
| `_task` | `asyncio.Task | None` | `field(default=None, repr=False)` |
