---
title: "DreamLoopModule"
description: "Background pattern discovery -- replays recent memories to find insights during idle time"
sidebar:
  order: 21
---

## Overview

Dream Loop -- background pattern discovery during idle time.
Replays recent episodic memories through the LLM to find recurring themes, behavioral patterns, and connections between seemingly unrelated interactions. Surfaces insights via Pulse notify events.

- **Version:** `1.0.0`
- **Class:** `DreamLoopModule`
- **Module name:** `dream_loop`

## Tier

Differentiation module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `dream`
- `dreams`
- `insights`
- `idle`
- `background`
- `patterns while idle`

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
