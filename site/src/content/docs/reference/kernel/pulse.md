---
title: "Pulse"
description: ""
sidebar:
  order: 3
---

## Overview

Pulse — the Nexus message bus.
Async in-process pub/sub with priority queuing and wildcard topics.

- **Version:** `0.1.0`
- **Class:** `Pulse`

## Types

### `Message`

| Field | Type | Default |
|-------|------|---------|
| `topic` | `str` | `—` |
| `source` | `str` | `—` |
| `payload` | `dict[str, Any]` | `field(default_factory=dict)` |
| `priority` | `Priority` | `Priority.NORMAL` |
| `msg_id` | `str` | `field(default_factory=lambda: uuid.uuid4().hex[:12])` |

## API

### `subscribe(self, pattern: str, handler: _Handler) -> str`

### `unsubscribe(self, sub_id: str) -> None`

### `async publish(self, msg: Message) -> None`

### `async drain(self)`
