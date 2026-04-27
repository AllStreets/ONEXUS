---
title: "SentryModule"
description: "Cognitive load model — tracks user focus, fatigue, stress, and flow"
sidebar:
  order: 2
---

## Overview

Sentry — cognitive load model.
Maintains a real-time estimate of the user's cognitive state based on
behavioral signals (typing speed, message frequency, time gaps).
Outputs a state vector: focus, fatigue, stress, flow.

- **Version:** `0.1.0`
- **Class:** `SentryModule`
- **Module name:** `sentry`

## Tier

Tier 2 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `cognitive`
- `focus`
- `fatigue`
- `stress`
- `flow`
- `state`
- `energy`
- `tired`

## Types

### `CognitiveState`

| Field | Type | Default |
|-------|------|---------|
| `focus` | `float` | `0.5` |
| `fatigue` | `float` | `0.0` |
| `stress` | `float` | `0.0` |
| `flow` | `bool` | `False` |

## API

### `update_signal(self, signal_name: str, value: float) -> None`

Update a behavioral signal (0.0–1.0) and recalculate state.

### `get_state(self) -> CognitiveState`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
