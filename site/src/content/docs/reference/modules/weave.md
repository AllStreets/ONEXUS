---
title: "RelationshipHealth"
description: ""
sidebar:
  order: 10
---

## Overview

Weave — social graph intelligence.
Maps contacts, tracks interaction frequency, detects decaying relationships,
and models who-knows-who connections.

- **Version:** `0.1.0`
- **Class:** `RelationshipHealth`
- **Module name:** `weave`

## Tier

Tier 10 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `contact`
- `network`
- `relationship`
- `social graph`
- `reconnect`

## Types

### `Interaction`

| Field | Type | Default |
|-------|------|---------|
| `channel` | `str` | `—` |
| `note` | `str` | `—` |
| `timestamp` | `str` | `—` |

### `Contact`

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `—` |
| `name` | `str` | `—` |
| `tags` | `list[str]` | `—` |
| `interactions` | `list[Interaction]` | `field(default_factory=list)` |
| `interaction_count` | `int` | `0` |
| `links` | `list[dict[str, str]]` | `field(default_factory=list)` |
