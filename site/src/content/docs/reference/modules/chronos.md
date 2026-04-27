---
title: "ChronosModule"
description: "Temporal branching — probabilistic future modeling and counter-factuals"
sidebar:
  order: 12
---

## Overview

Chronos — temporal branching and counter-factual modeling.
Models probabilistic future timelines across multiple life domains.
Also handles counter-factuals: 'what if I had done X instead?'

- **Version:** `0.1.0`
- **Class:** `ChronosModule`
- **Module name:** `chronos`

## Tier

Tier 12 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `timeline`
- `future`
- `branch`
- `counterfactual`
- `what if`
- `temporal`

## Types

### `Branch`

| Field | Type | Default |
|-------|------|---------|
| `label` | `str` | `—` |
| `probability` | `float` | `—` |
| `outcomes` | `dict[str, str]` | `—` |
| `risk_level` | `str` | `—` |

### `Timeline`

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `—` |
| `decision` | `str` | `—` |
| `context` | `str` | `—` |
| `branches` | `list[Branch]` | `—` |
| `domains` | `list[str]` | `—` |

## API

### `create_timeline(self, decision: str, context: str = '', domains: list[str] | None = None) -> Timeline`

### `counterfactual(self, actual_decision: str, alternative: str, outcome_actual: str) -> str`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
