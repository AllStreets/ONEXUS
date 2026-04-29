---
title: "CouncilModule"
description: "Multi-agent deliberation -- structured debate across modules with synthesized recommendations"
sidebar:
  order: 19
---

## Overview

Council -- multi-agent deliberation orchestrator.
Selects relevant modules, runs structured multi-round debate, and synthesizes a recommendation with preserved dissent. Inspired by Marvin Minsky's Society of Mind.

- **Version:** `0.1.0`
- **Class:** `CouncilModule`
- **Module name:** `council`

## Tier

Orchestration module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `deliberate`
- `debate`
- `council`
- `perspectives`
- `weigh`
- `consider`
- `should i`
- `decide`
- `pros and cons`
- `think through`
- `advise`

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
