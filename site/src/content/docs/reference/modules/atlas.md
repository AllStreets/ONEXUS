---
title: "AtlasModule"
description: "Living world model — temporal knowledge graph with confidence decay"
sidebar:
  order: 3
---

## Overview

Atlas — the living world model.
A temporal knowledge graph where facts have confidence scores, sources,
and time-based decay. Conflicting facts coexist with competing confidence.

- **Version:** `0.1.0`
- **Class:** `AtlasModule`
- **Module name:** `atlas`

## Tier

Tier 3 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `fact`
- `know about`
- `world model`
- `knowledge`
- `who is`
- `what is`

## Types

### `Fact`

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `—` |
| `subject` | `str` | `—` |
| `predicate` | `str` | `—` |
| `obj` | `str` | `—` |
| `confidence` | `float` | `—` |
| `source` | `str` | `—` |
| `timestamp` | `str` | `—` |
| `max_age_days` | `int | None` | `—` |

## API

### `init_db(self) -> None`

### `add_fact(self, subject: str, predicate: str, obj: str, confidence: float, source: str, max_age_days: int | None = None) -> str`

### `remove_fact(self, fact_id: str) -> None`

### `query(self, subject: str | None = None, predicate: str | None = None, obj: str | None = None, apply_decay: bool = False, limit: int = 50) -> list[dict[str, Any]]`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
