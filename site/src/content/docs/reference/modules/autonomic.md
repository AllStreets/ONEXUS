---
title: "AutonomicModule"
description: "Earned autonomous action -- observes patterns, learns routines, acts within trust boundaries"
sidebar:
  order: 20
---

## Overview

Autonomic -- earned autonomous action engine.
Observes patterns, learns routines, and gradually takes autonomous action as trust is earned through successful outcomes. Every action is auditable, every decision is adversarially checked, and trust retreats on failure.

- **Version:** `0.1.0`
- **Class:** `AutonomicModule`
- **Module name:** `autonomic`

## Tier

Orchestration module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `automate`
- `routine`
- `autopilot`
- `autonomous`
- `on my behalf`
- `handle it`
- `take care of`
- `manage for me`
- `do it for me`
- `autonomic`
- `trust status`
- `domain trust`

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
