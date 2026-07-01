# Correction & status — 2026-07-01

A one-time status note, following the 2026-06-16 correction and written alongside
the SMADP and ONEXUS-Agents corrections of the same date. Unlike those two, NEXUS
did not go off track — this records where the runtime stands and the open
follow-ups.

## Where things stand

The runtime is active and healthy.

- **Shipped and building.** ONEXUS (the NEXUS runtime) is at **v1.0**, with active
  development through 2026-06-21 — the Aurora ambient UI, the Atlas relationship
  graph, the Tauri desktop standalone (`standalone/`, bundle id
  `com.allstreets.onexus`), and the "v2 — Missing Minds" cognitive modules. The
  working tree is clean and in sync with `origin/main`.
- **Integration is staged, not stalled.** The nightly ONEXUS-Agents → NEXUS
  catalog sync and the cross-repo security hardening from the June integration
  work are prepared as pull requests, held behind the deliberate no-auto-merge
  review gate rather than pushed straight to `main`. They activate on your review
  and merge.

## Open follow-ups (tracked, not blocking)

- **Reconcile the README test count.** The badge still reads **1,014 passing**
  while the body already cites **1,274** after the v2 cognitive modules landed —
  the two should be brought into agreement and refreshed against the current
  suite.
- **The pre-existing test and web-hardening items** catalogued in the integration
  final report remain open and are best worked deliberately as their own pass.

Nothing here blocks the runtime; these are hygiene plus the staged integration
awaiting your merge.

---
*hand-written 2026-07-01.*
