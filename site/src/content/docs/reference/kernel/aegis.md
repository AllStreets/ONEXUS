---
title: "Aegis"
description: ""
sidebar:
  order: 5
---

## Overview

Aegis — trust and permissions engine for Nexus.
Batch 1: binary allow/deny per module.
Batch 3 upgrades to graduated 0-100 trust with outcome-based adjustment.

- **Version:** `0.1.0`
- **Class:** `Aegis`

## API

### `init_db(self) -> None`

### `set_policy(self, module: str, allowed: bool) -> None`

### `is_allowed(self, module: str, action: str) -> bool`

### `check(self, module: str, action: str) -> None`

### `list_policies(self) -> list[dict[str, Any]]`

### `get_trust(self, module: str) -> int`

### `adjust_trust(self, module: str, delta: int, reason: str) -> int`

### `check_trust(self, module: str, required_trust: int) -> bool`

### `trust_history(self, module: str, limit: int = 50) -> list[dict[str, Any]]`
