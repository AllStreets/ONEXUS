---
title: Earned Autonomy
description: How NEXUS modules earn trust over time through demonstrated reliability rather than blanket permissions.
sidebar:
  order: 1
---

## The Problem with Blanket Permissions

Most permission systems are binary: a module either has access or it doesn't. Grant it once and it retains that access forever, regardless of how it behaves. This is convenient but dangerous — a misbehaving module keeps its permissions indefinitely.

NEXUS takes a different approach. Trust is earned through demonstrated reliability, not granted once and forgotten.

## Aegis Trust Scores

Every module has a trust score maintained by Aegis, ranging from 0 to 100. New modules start at 50 — neutral, neither trusted nor distrusted. The score evolves based on outcomes.

```
Module enabled
       |
       v
  Trust: 50 (neutral)
       |
   +---+-------------------+
   |                       |
Positive outcome      Negative outcome
(+1 to +3)            (-2 to -10)
   |                       |
   v                       v
Trust rises            Trust falls
   |                       |
   v                       v
High trust             Trust < threshold
(elevated capability)  (module bypassed)
```

## What Counts as an Outcome

Aegis records outcomes in two categories:

**Positive outcomes:**
- User accepts or acts on a response
- Module completes a task without error
- User explicitly rates a response as helpful

**Negative outcomes:**
- Module throws an unhandled exception
- User explicitly rejects a response
- Module attempts an action outside its declared scope
- Policy violation detected by Chronicle

Outcome recording is explicit — modules call `context["aegis"].record_outcome(self.name, positive=True/False)` after they have enough signal to know whether the interaction succeeded.

## Trust Decay

Trust scores do not freeze. A module that was once reliable but has been idle for a long time slowly regresses toward the neutral midpoint (50). This prevents a high trust score earned months ago from indefinitely justifying elevated access on a module that has not been exercised recently.

Decay is slow — designed to fade over weeks, not hours.

## Why This Matters

Consider two scenarios:

**Scenario A — Traditional permissions:** You enable a code execution module. It works fine for a month. Then a new version introduces a bug that corrupts files. It still has full permissions. The damage happens silently.

**Scenario B — Earned autonomy:** You enable the same module. It builds trust over a month. The buggy update causes errors. Aegis records negative outcomes. Trust drops. Cortex starts bypassing it before the damage compounds. Chronicle has a timestamped record of exactly when the behavior changed.

Earned autonomy makes the system self-correcting. No manual intervention required to respond to a degraded module — the trust mechanism handles it automatically.

## Interacting with Trust Directly

```bash
# Check current trust scores
nexus status

# Manually revoke a module (sets trust to 0)
nexus deny atlas

# Re-enable a module (resets trust to 50)
nexus allow atlas
```

Trust scores survive `nexus deny` / `nexus allow` cycles — revoking and re-enabling a module does not erase its history. To fully reset a module's trust, delete its record from `aegis.db`.
