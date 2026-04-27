---
title: "DreamweaverModule"
description: "Overnight synthesis — deep pattern analysis and morning briefs"
sidebar:
  order: 13
---

## Overview

Dreamweaver — overnight synthesis engine.
Ingests the day's events, finds patterns and connections during idle time,
and produces a morning brief of insights the user might have missed.

- **Version:** `0.1.0`
- **Class:** `DreamweaverModule`
- **Module name:** `dreamweaver`

## Tier

Tier 13 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `morning brief`
- `overnight`
- `synthesis`
- `sleep`
- `idle`
- `pattern`

## Types

### `Insight`

| Field | Type | Default |
|-------|------|---------|
| `pattern` | `str` | `—` |
| `supporting_events` | `list[str]` | `—` |
| `significance` | `str` | `—` |

### `SynthesisReport`

| Field | Type | Default |
|-------|------|---------|
| `insights` | `list[Insight]` | `—` |
| `event_count` | `int` | `—` |
| `themes` | `list[str]` | `—` |

## API

### `ingest(self, event: str) -> None`

### `event_count(self) -> int`

### `clear(self) -> None`

### `synthesize(self) -> SynthesisReport`

### `morning_brief(self) -> str`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
