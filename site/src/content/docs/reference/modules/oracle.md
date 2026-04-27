---
title: "OracleModule"
description: "Anticipatory trigger engine — scans for patterns and fires events"
sidebar:
  order: 1
---

## Overview

Oracle — anticipatory trigger engine.
Scans input against configurable trigger rules with keyword-weighted scoring.
Fires events when pattern density exceeds thresholds.
Observe-only: Oracle never takes actions, only surfaces information.

- **Version:** `0.1.0`
- **Class:** `OracleModule`
- **Module name:** `oracle`

## Tier

Tier 1 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `trigger`
- `alert`
- `monitor`
- `scan`
- `anticipat`
- `pattern`

## Types

### `TriggerRule`

| Field | Type | Default |
|-------|------|---------|
| `name` | `str` | `—` |
| `keywords` | `list[str]` | `—` |
| `threshold` | `float` | `—` |
| `description` | `str` | `—` |
| `weight` | `float` | `1.0` |

## API

### `add_rule(self, rule: TriggerRule) -> None`

### `remove_rule(self, name: str) -> None`

### `list_rules(self) -> list[TriggerRule]`

### `evaluate(self, text: str) -> list[dict[str, Any]]`

Score text against all rules. Return fired triggers (score > threshold).

### `async handle(self, message: str, context: dict[str, Any]) -> str`
