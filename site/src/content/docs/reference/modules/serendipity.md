---
title: "SerendipityModule"
description: "Anti-optimization — surfaces surprising cross-domain connections"
sidebar:
  order: 14
---

## Overview

Serendipity — anti-optimization engine.
Monitors what the user focuses on, identifies adjacent fields they are NOT
looking at, and surfaces surprising cross-domain connections with deep
structural similarity. Uses an inverted relevance function — penalizes
obvious connections, rewards surprising ones.

- **Version:** `0.1.0`
- **Class:** `SerendipityModule`
- **Module name:** `serendipity`

## Tier

Tier 14 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `surprising`
- `unexpected`
- `serendip`
- `random`
- `adjacent`
- `diverse`

## Types

### `KnowledgeEntry`

| Field | Type | Default |
|-------|------|---------|
| `domain` | `str` | `—` |
| `content` | `str` | `—` |
| `tags` | `list[str]` | `—` |

### `SurprisingConnection`

| Field | Type | Default |
|-------|------|---------|
| `source_domain` | `str` | `—` |
| `content` | `str` | `—` |
| `shared_concepts` | `list[str]` | `—` |
| `surprise_score` | `float` | `—` |
| `explanation` | `str` | `—` |

## API

### `record_focus(self, area: str) -> None`

### `list_focus_areas(self) -> list[str]`

### `add_knowledge(self, domain: str, content: str, tags: list[str]) -> None`

### `list_knowledge(self) -> list[KnowledgeEntry]`

### `find_connections(self) -> list[SurprisingConnection]`

### `async handle(self, message: str, context: dict[str, Any]) -> str`
