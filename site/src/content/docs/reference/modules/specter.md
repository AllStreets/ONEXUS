---
title: "StakeLevel"
description: ""
sidebar:
  order: 11
---

## Overview

Specter — adversarial red-team agent.
Runs structured adversarial analysis on high-stakes decisions:
counter-arguments, failure modes, hidden assumptions, worst-case scenarios.
Auto-activates based on detected stake level.

- **Version:** `0.1.0`
- **Class:** `StakeLevel`
- **Module name:** `specter`

## Tier

Tier 11 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `red team`
- `adversarial`
- `counter-argument`
- `devil's advocate`
- `risk analysis`

## Types

### `RedTeamReport`

| Field | Type | Default |
|-------|------|---------|
| `decision` | `str` | `—` |
| `stake_level` | `StakeLevel` | `—` |
| `counter_arguments` | `list[str]` | `—` |
| `failure_modes` | `list[str]` | `—` |
| `hidden_assumptions` | `list[str]` | `—` |
| `worst_case` | `str` | `—` |
| `recommendation` | `str` | `—` |
