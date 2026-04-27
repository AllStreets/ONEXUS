---
title: "HeraldModule"
description: "Agent-to-agent communication — discovery, auth, and message exchange"
sidebar:
  order: 9
---

## Overview

Herald — agent-to-agent communication handler.
Manages discovery, authentication, and message exchange with external agents.
Maintains reputation scores based on interaction outcomes.

- **Version:** `0.1.0`
- **Class:** `HeraldModule`
- **Module name:** `herald`

## Tier

Tier 9 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `external agent`
- `a2a`
- `communicate`
- `connected agent`

## Types

### `ExternalAgent`

| Field | Type | Default |
|-------|------|---------|
| `agent_id` | `str` | `—` |
| `name` | `str` | `—` |
| `endpoint` | `str` | `—` |
| `trust_grant` | `int` | `—` |
| `reputation` | `float` | `0.5` |
| `_successes` | `int` | `field(default=0, repr=False)` |
| `_failures` | `int` | `field(default=0, repr=False)` |

### `A2AMessage`

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `—` |
| `from_agent` | `str` | `—` |
| `to_agent` | `str` | `—` |
| `content` | `str` | `—` |
| `msg_type` | `str` | `—` |
| `timestamp` | `str` | `—` |

## API

### `register_agent(self, agent_id: str, name: str, endpoint: str, trust_grant: int) -> ExternalAgent`

### `revoke_agent(self, agent_id: str) -> None`

### `get_agent(self, agent_id: str) -> ExternalAgent | None`

### `list_agents(self) -> list[ExternalAgent]`

### `compose_message(self, to_agent: str, content: str, msg_type: str) -> A2AMessage`

### `message_history(self, agent_id: str) -> list[A2AMessage]`

### `record_interaction_outcome(self, agent_id: str, success: bool) -> None`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
