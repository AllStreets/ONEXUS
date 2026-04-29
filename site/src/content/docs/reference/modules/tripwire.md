---
title: "TripwireModule"
description: "Mirrors your decision patterns -- alerts when you contradict your own history"
sidebar:
  order: 23
---

## Overview

Tripwire -- cognitive tripwires that mirror your decision patterns back to you.
Analyzes Chronicle for decision history, detects contradictions between current actions and historical patterns, and emits non-blocking alerts when confidence exceeds 70%.

- **Version:** `1.0.0`
- **Class:** `TripwireModule`
- **Module name:** `tripwire`

## Tier

Differentiation module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `my patterns`
- `decision history`
- `contradictions`
- `tripwire`
- `mirror`

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
