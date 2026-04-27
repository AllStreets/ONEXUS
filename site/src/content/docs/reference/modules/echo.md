---
title: "EchoModule"
description: "Behavioral fingerprinting — learns writing style and decision patterns"
sidebar:
  order: 7
---

## Overview

Echo — behavioral fingerprinting and skill transfer.
Observes how the user writes across domains, builds behavioral profiles,
and can score new text for style match. Patterns transfer across domains.

- **Version:** `0.1.0`
- **Class:** `EchoModule`
- **Module name:** `echo`

## Tier

Tier 7 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `behavioral`
- `fingerprint`
- `style`
- `voice`
- `profile`
- `writing`

## Types

### `BehavioralProfile`

| Field | Type | Default |
|-------|------|---------|
| `domain` | `str` | `—` |
| `sample_count` | `int` | `0` |
| `avg_word_count` | `float` | `0.0` |
| `avg_sentence_length` | `float` | `0.0` |
| `top_phrases` | `list[str]` | `field(default_factory=list)` |
| `formality_score` | `float` | `0.5` |
| `_word_counts` | `list[int]` | `field(default_factory=list, repr=False)` |
| `_sentence_lengths` | `list[float]` | `field(default_factory=list, repr=False)` |
| `_word_freq` | `Counter` | `field(default_factory=Counter, repr=False)` |

## API

### `observe(self, domain: str, text: str) -> None`

Record a text sample for a domain and update the profile.

### `get_profile(self, domain: str) -> BehavioralProfile | None`

### `list_domains(self) -> list[str]`

### `match_style(self, domain: str, text: str) -> float`

Score how well a text matches the observed style for a domain (0.0-1.0).

### `async handle(self, message: str, context: dict[str, Any]) -> str`
