---
title: "ForgeModule"
description: "Autonomous negotiation — multi-round structured bargaining with guardrails"
sidebar:
  order: 15
---

## Overview

Forge — autonomous negotiation engine.
Handles structured multi-round negotiations within user-defined parameters.
Operates within Aegis-defined boundaries and escalates when hitting limits.

- **Version:** `0.1.0`
- **Class:** `ForgeModule`
- **Module name:** `forge`

## Tier

Tier 15 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `negotiat`
- `bargain`
- `offer`
- `counter-offer`
- `concession`
- `deal`

## Types

### `NegotiationConfig`

| Field | Type | Default |
|-------|------|---------|
| `domain` | `str` | `—` |
| `floor` | `float` | `—` |
| `ceiling` | `float` | `—` |
| `target` | `float` | `—` |
| `max_rounds` | `int` | `—` |
| `concession_limit` | `float` | `—` |

### `Offer`

| Field | Type | Default |
|-------|------|---------|
| `round_num` | `int` | `—` |
| `amount` | `float` | `—` |
| `from_party` | `str` | `—` |
| `timestamp` | `str` | `''` |

### `NegotiationState`

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `—` |
| `config` | `NegotiationConfig` | `—` |
| `status` | `str` | `—` |
| `current_round` | `int` | `0` |
| `offers` | `list[Offer]` | `field(default_factory=list)` |
| `our_last` | `float` | `0.0` |

## API

### `create_negotiation(self, config: NegotiationConfig) -> str`

### `get_state(self, neg_id: str) -> NegotiationState`

### `make_offer(self, neg_id: str) -> Offer`

### `receive_counter(self, neg_id: str, amount: float) -> str`

### `get_history(self, neg_id: str) -> list[Offer]`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
