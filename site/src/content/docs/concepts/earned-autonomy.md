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

## Graduated Sovereignty for Agents

Agents take earned autonomy further with **graduated sovereignty** -- five discrete trust tiers that unlock progressively more capable behavior as an agent proves itself reliable.

```
Trust Score    Tier          Unlocked Behavior
───────────    ──────────    ──────────────────────────────────────
  0-24         SKILL         User invokes explicitly. No initiative.
 25-49         ADVISOR       Suggests actions when relevant context detected.
 50-74         MONITOR       Proactively watches Pulse events, reports findings.
 75-99         AUTONOMOUS    Acts within defined boundaries without asking.
  100          SOVEREIGN     Coordinates with other agents independently.
```

Every agent implements four tier methods:

| Method | Trust Level | Purpose |
|--------|------------|---------|
| `analyze()` | All | Core logic. Runs at every trust level. |
| `suggest()` | ADVISOR+ | Proactive suggestions appended to analysis results. |
| `monitor()` | MONITOR+ | Background event watching via Pulse subscriptions. |
| `coordinate()` | SOVEREIGN | Cross-agent routing for combined analysis. |

### How Tiers Unlock

When Cortex routes a message to an agent, `AgentModule.handle()` checks the agent's current Aegis trust score and activates the appropriate tier methods:

1. `analyze()` always runs -- this is the core agent logic
2. If trust >= 25, `suggest()` runs and appends proactive suggestions
3. If trust >= 75, the action is logged to Chronicle as an autonomous event
4. If trust >= 100 and the agent has `coordination_targets`, `coordinate()` routes results to other agents

At MONITOR+ trust, agents also subscribe to Pulse events listed in their `watch_events` attribute. When those events fire, the agent's `monitor()` method runs in the background, and findings are published back to Pulse.

### Trust is Always Revocable

A single negative outcome can drop an agent's trust below a tier threshold, immediately revoking that tier's capabilities. An agent at AUTONOMOUS (trust 80) that causes an error might drop to ADVISOR (trust 35) -- it can still suggest, but it can no longer act independently. This is automatic, enforced by Aegis on every call, and logged permanently by Chronicle.
