---
title: "CollectiveModule"
description: "Federated learning -- peer model sharing with differential privacy"
sidebar:
  order: 16
---

## Overview

Collective -- federated learning coordinator.
Manages peer-to-peer model sharing with differential privacy guarantees.
Users opt in explicitly. No data leaves the machine without consent.
Noise injection ensures individual contributions cannot be extracted.

- **Version:** `0.1.0`
- **Class:** `CollectiveModule`
- **Module name:** `collective`

## Tier

Tier 16 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `federated`
- `peer`
- `distributed`
- `swarm learning`
- `model sharing`

## Types

### `FederatedConfig`

| Field | Type | Default |
|-------|------|---------|
| `model_id` | `str` | `—` |
| `min_peers` | `int` | `3` |
| `rounds` | `int` | `5` |
| `noise_scale` | `float` | `1.0` |
| `contribution_enabled` | `bool` | `False` |

### `PeerNode`

| Field | Type | Default |
|-------|------|---------|
| `peer_id` | `str` | `—` |
| `endpoint` | `str` | `—` |
| `reputation` | `float` | `0.5` |

### `ModelUpdate`

| Field | Type | Default |
|-------|------|---------|
| `model_id` | `str` | `—` |
| `noised_weights` | `dict[str, list[float]]` | `—` |
| `peer_id` | `str` | `''` |
| `round_num` | `int` | `0` |

### `AggregationResult`

| Field | Type | Default |
|-------|------|---------|
| `model_id` | `str` | `—` |
| `averaged_weights` | `dict[str, list[float]]` | `—` |
| `num_contributors` | `int` | `—` |
| `round_num` | `int` | `—` |

## API

### `register_peer(self, peer: PeerNode) -> None`

### `remove_peer(self, peer_id: str) -> None`

### `list_peers(self) -> list[PeerNode]`

### `is_contributing(self) -> bool`

### `set_contributing(self, enabled: bool) -> None`

### `create_update(self, model_id: str, weights: dict[str, list[float]]) -> ModelUpdate`

### `aggregate(self, updates: list[ModelUpdate]) -> AggregationResult`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
