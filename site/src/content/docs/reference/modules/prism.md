---
title: "PrismModule"
description: "Cross-domain synthesis — finds non-obvious connections across information sources"
sidebar:
  order: 4
---

## Overview

Prism — cross-domain synthesis engine.
Collects observations from multiple domains, finds non-obvious connections
through shared tags and context overlap, and surfaces synthesized insights.

- **Version:** `0.1.0`
- **Class:** `PrismModule`
- **Module name:** `prism`

## Tier

Tier 4 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `synthesize`
- `connection`
- `cross-domain`
- `insight`
- `relate`

## Types

### `Observation`

| Field | Type | Default |
|-------|------|---------|
| `domain` | `str` | `—` |
| `content` | `str` | `—` |
| `tags` | `list[str]` | `—` |

### `Insight`

| Field | Type | Default |
|-------|------|---------|
| `summary` | `str` | `—` |
| `domains` | `list[str]` | `—` |
| `tags` | `list[str]` | `—` |
| `observations` | `list[Observation]` | `—` |
| `connection_strength` | `float` | `—` |

## API

### `add_observation(self, domain: str, content: str, tags: list[str]) -> None`

### `list_observations(self) -> list[Observation]`

### `clear_observations(self) -> None`

### `synthesize(self) -> list[Insight]`

Find cross-domain connections through shared tags.

### `async handle(self, message: str, context: dict[str, Any]) -> str`
