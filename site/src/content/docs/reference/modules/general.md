---
title: "GeneralModule"
description: "General-purpose conversation and question answering"
sidebar:
  order: 0
---

## Overview

General — the built-in default module.
Handles any user message by forwarding to the LLM with a system prompt.
Falls back to a static response when no LLM is available.

- **Version:** `0.1.0`
- **Class:** `GeneralModule`
- **Module name:** `general`

## Tier

General purpose module.

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
