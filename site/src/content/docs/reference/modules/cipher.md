---
title: "CipherModule"
description: "Trust-scored information with provenance chains and conflict detection"
sidebar:
  order: 5
---

## Overview

Cipher — trust-scored information.
Every piece of information gets a provenance chain and computed trust score.
When sources conflict, Cipher surfaces the conflict explicitly.

- **Version:** `0.1.0`
- **Class:** `CipherModule`
- **Module name:** `cipher`

## Tier

Tier 5 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `trust`
- `source`
- `provenance`
- `conflict`
- `verify`
- `credib`

## Types

### `SourceProfile`

| Field | Type | Default |
|-------|------|---------|
| `name` | `str` | `—` |
| `base_trust` | `float` | `—` |
| `category` | `str` | `—` |

### `Claim`

| Field | Type | Default |
|-------|------|---------|
| `claim_id` | `str` | `—` |
| `value` | `str` | `—` |
| `source` | `str` | `—` |
| `trust` | `float` | `—` |

## API

### `register_source(self, profile: SourceProfile) -> None`

### `list_sources(self) -> list[SourceProfile]`

### `score(self, information: str, source: str) -> dict[str, Any]`

Score a piece of information based on its source.

### `record_claim(self, claim_id: str, value: str, source: str, trust: float) -> None`

Record a claim with its source and trust score.

### `get_conflicts(self) -> list[dict[str, Any]]`

Find claims where different sources report different values.

### `get_provenance(self, claim_id: str) -> list[dict[str, Any]]`

Get the provenance chain for a claim.

### `async handle(self, message: str, context: dict[str, Any]) -> str`
