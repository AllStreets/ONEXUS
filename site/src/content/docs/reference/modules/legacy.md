---
title: "ArtifactType"
description: ""
sidebar:
  order: 17
---

## Overview

Legacy -- knowledge crystallization engine.
Distills months of decisions, outcomes, and behavioral patterns into
structured, exportable knowledge artifacts. Extracts frameworks, playbooks,
and heuristics from actual behavior -- not self-reported preferences.

- **Version:** `0.1.0`
- **Class:** `ArtifactType`
- **Module name:** `legacy`

## Tier

Tier 17 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `crystallize`
- `distill`
- `framework`
- `playbook`
- `wisdom`
- `pattern extract`

## Types

### `DecisionRecord`

| Field | Type | Default |
|-------|------|---------|
| `domain` | `str` | `—` |
| `decision` | `str` | `—` |
| `outcome` | `str` | `—` |
| `factors` | `list[str]` | `—` |

### `DecisionPattern`

| Field | Type | Default |
|-------|------|---------|
| `factor` | `str` | `—` |
| `frequency` | `int` | `—` |
| `positive_rate` | `float` | `—` |
| `domains` | `list[str]` | `—` |

### `KnowledgeArtifact`

| Field | Type | Default |
|-------|------|---------|
| `domain` | `str` | `—` |
| `artifact_type` | `ArtifactType` | `—` |
| `patterns` | `list[DecisionPattern]` | `—` |
| `content` | `str` | `—` |
| `decision_count` | `int` | `—` |
