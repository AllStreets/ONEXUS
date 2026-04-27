---
title: "ThreatSeverity"
description: ""
sidebar:
  order: 8
---

## Overview

Sigil — ambient threat radar.
Registers, prioritizes, and tracks threats across categories:
security, reputation, financial, competitive, relationship.
Critical threats bypass normal Pulse priority.

- **Version:** `0.1.0`
- **Class:** `ThreatSeverity`
- **Module name:** `sigil`

## Tier

Tier 8 module.

## Routing Keywords

Cortex uses these keywords to route messages to this module:

- `threat`
- `danger`
- `security`
- `breach`
- `risk`
- `radar`

## Types

### `Threat`

| Field | Type | Default |
|-------|------|---------|
| `id` | `str` | `—` |
| `category` | `str` | `—` |
| `description` | `str` | `—` |
| `severity` | `ThreatSeverity` | `—` |
| `source` | `str` | `—` |
| `timestamp` | `str` | `—` |
| `acknowledged` | `bool` | `False` |
