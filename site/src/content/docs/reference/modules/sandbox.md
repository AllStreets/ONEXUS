---
title: "SandboxModule"
description: "Fork memory and simulate outcomes -- test scenarios without real consequences"
sidebar:
  order: 25
---

## Overview

Sandbox -- temporal sandbox for hypothetical scenario simulation.
Forks memory and runs proposed actions through the LLM against historical patterns without modifying real state. Projects most likely, best case, and worst case outcomes with confidence percentages.

- **Version:** `1.0.0`
- **Class:** `SandboxModule`
- **Module name:** `sandbox`

## Tier

Differentiation module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `what if`
- `simulate`
- `hypothetical`
- `sandbox`
- `fork`
- `test scenario`

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
