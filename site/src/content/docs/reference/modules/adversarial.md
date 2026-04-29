---
title: "AdversarialModule"
description: "System-wide red-teaming -- analyzes logs for failures and generates stress tests"
sidebar:
  order: 22
---

## Overview

Adversarial -- system-wide red-teaming engine.
Analyzes Chronicle logs for failure patterns, inconsistencies between module responses, unhandled edge cases, and trust violations. Generates targeted stress tests and files findings as Pulse events.

- **Version:** `1.0.0`
- **Class:** `AdversarialModule`
- **Module name:** `adversarial`

## Tier

Differentiation module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `stress test`
- `red team`
- `self improve`
- `vulnerability`
- `harden`

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
