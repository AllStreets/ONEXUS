---
title: "Chronicle"
description: ""
sidebar:
  order: 4
---

## Overview

Chronicle — immutable audit trail for every Nexus action.
SQLite-backed, queryable, exportable for compliance.

- **Version:** `0.1.0`
- **Class:** `Chronicle`

## API

### `init_db(self) -> None`

### `log(self, source: str, action: str, payload: dict[str, Any] | None = None) -> str`

### `query(self, source: str | None = None, action: str | None = None, since: str | None = None, until: str | None = None, limit: int = 100) -> list[dict[str, Any]]`
