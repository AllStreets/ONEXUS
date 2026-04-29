---
title: "ProvenanceModule"
description: "Full reasoning tree for every conclusion -- trace how NEXUS reached any answer"
sidebar:
  order: 24
---

## Overview

Provenance -- full reasoning tree for every conclusion.
Traces Chronicle logs to build a chain from original input through every module that processed it, what each module concluded, any challenges or objections raised, and the final output derivation.

- **Version:** `1.0.0`
- **Class:** `ProvenanceModule`
- **Module name:** `provenance`

## Tier

Differentiation module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `why do you think`
- `reasoning`
- `show reasoning`
- `provenance`
- `trace`
- `how did you`

## API

### `async handle(self, message: str, context: dict[str, Any]) -> str`
