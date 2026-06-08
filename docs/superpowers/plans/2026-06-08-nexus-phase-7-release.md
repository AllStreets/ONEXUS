# NEXUS Phase 7 — Release Polish Implementation Plan (Phase 7 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Take NEXUS from "all 6 prior phases shipped" to **release-ready**. The work is heavy on cleanup + polish + final integration:

- Delete the 65 pre-existing test-collection errors (orphaned test files importing modules that were deleted).
- Fix the 28 pre-existing test failures (drift in test fixtures against the current API).
- Wrap federation calls in `as_agent("federation")` so the Phase 6 gating actually fires for peer traffic.
- Wire WebSocket push for mood + permissions (so the Aurora surfaces stop polling).
- Add the trust-event temperature trio overlays (rising/falling/collapse) — last bit of the mood atlas brought to life.
- Time-of-day mood modulation (5–10% bias).
- Accessibility audit sweep with automated checks.
- Rewrite the top-level `README.md` to match the as-shipped reality.
- A final full-app integration smoke that exercises every surface + every gate.
- Tag `v1.0` (or `phase-7-release`).

After Phase 7: the repo is ready to be released as v1.0.

**Architecture:** No new subsystems. This is cleanup + small features + docs.

**Prior phase:** `phase-6-network-gateway` tag. The 6 core phases are all merged and tagged.

---

## Pre-flight

- Branch from `phase-6-network-gateway` into `nexus-phase-7` (worktree `.worktrees/nexus-phase-7`).
- Baseline = **962 passing**, 28 failing, 65 collection errors.
- **Phase 7's regression target is different from prior phases:** by the end, the count should be **higher** (cleanup adds tests passing or removes test files; we'll cross 1000 passing easily) and the failure count should be **strictly lower** (ideally 0).
- `source .venv/bin/activate` for every Bash invocation.

---

## Task 1 · Delete orphaned test files

**Why:** 65 collection errors all come from test files that import modules that no longer exist (e.g., `nexus.modules.general`, `nexus.benchmarks`, `nexus.sdk`, `nexus.modules.vigil`, `nexus.modules.weave`, batch-integration tests for deleted batch features). Deleting them is the single biggest cleanup win.

**Steps:**

- [ ] Run `pytest --continue-on-collection-errors -q 2>&1 | grep "^ERROR " | head -80` to list every collection error.

- [ ] For each error, inspect the file. If the error is `ModuleNotFoundError: No module named '<module>'` and `<module>` doesn't exist in the codebase, delete the test file.

- [ ] If a test file references multiple deleted modules + some live ones, surgically remove the broken imports and any tests that use them. Keep tests that test live code.

- [ ] Expected to delete approximately 8–15 test files entirely (the batch integration suites + the sdk tests + the modules tests for deleted modules).

- [ ] Verify the count after deletion: `pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3` should show 0 collection errors.

- [ ] Commit:

```bash
git rm <each-deleted-file>
git commit -m "chore(tests): delete orphaned tests importing deleted modules (collection errors → 0)"
```

---

## Task 2 · Fix the 28 baseline failures

**Why:** Drift between test fixtures and the current API. Most are trivial.

Known categories (from `.baseline_failures.txt`):
- `tests/inference/test_local.py` — 2 health tests using `provider.health()` synchronously but it's async now
- `tests/inference/test_openai_provider.py` — 2 tests using sync `OpenAI` but we use `AsyncOpenAI` now
- `tests/kernel/test_aegis.py` — 10 tests using `aegis.is_allowed()` which doesn't exist; they should use `aegis.check()`
- `tests/modules/test_echo.py`, `test_legacy.py`, `test_oracle.py`, `test_specter.py` — 5 attribute assertions that drifted
- `tests/replay/test_engine.py` — 6 tests on replay APIs that evolved
- `tests/site/test_generate_docs.py` — 1 test on doc-gen
- `tests/test_cli.py::test_cli_version` — expects "0.1.0" but version is now "0.2.0"

**Steps:**

- [ ] For each failing test, either:
  - **Fix the test** to match the current API (preferred when the test still describes intended behaviour), OR
  - **Mark it `@pytest.mark.skip(reason="...")` with a tracking comment** (last resort — only when fixing would require non-trivial rework that doesn't belong in Phase 7).

- [ ] Target: 0 failing tests at the end of Task 2.

- [ ] Commit (one per logical group):
  - `chore(tests): fix inference provider tests (async signatures)`
  - `chore(tests): fix aegis tests (use check() not is_allowed())`
  - `chore(tests): fix module attribute tests after manifest migration`
  - `chore(tests): fix replay engine tests after API evolution`
  - `chore(tests): bump expected version to 0.2.0`

---

## Task 3 · Federation `as_agent("federation")` wrapping

**Why:** Phase 6 added the infrastructure but every federation call still bypasses Aegis (no agent context set). Wrap each `await self._http.<method>` in `nexus/federation/discovery.py` and `protocol.py` with `async with as_agent("federation"):`.

**Steps:**

- [ ] In each of `nexus/federation/discovery.py` and `protocol.py`, find every `await self._http.<method>(...)` call and wrap it.

- [ ] Add a federation test that verifies a peer call (when `self._http is not None`) actually goes through `aegis.network` with `network.outbound.<host>` capability.

- [ ] Commit: `feat(federation): wrap peer calls in as_agent("federation") for full Aegis gating`

---

## Task 4 · Time-of-day mood modulation

**Why:** Spec §11.4 — quiet 5–10% bias on the active mood based on local hour.

**Files:**
- Modify: `nexus/workspaces/mood.py` (extend `MoodEngine` with `time_of_day_factor` field)
- Create: `tests/workspaces/test_mood_time_of_day.py`

The modulation is purely a returned-snapshot annotation; the surface (CSS) uses it to bias hue without changing the mood class:

```python
@dataclass
class MoodSnapshot:
    mood: Mood
    ...
    tod_bias: float  # -1.0 to +1.0, where -1 = night desaturated, +1 = morning gold-boost
```

Surface reads `tod_bias` and CSS computes `filter: hue-rotate(...)`.

**Steps:**

- [ ] Add `MoodSnapshot.tod_bias` field
- [ ] Compute bias from local clock: morning (06-10) → +0.5; midday (10-17) → 0; evening (17-22) → +0.5 (violet); night (22-06) → -0.5 (desat)
- [ ] Test: at a fixed hour, the snapshot has the expected `tod_bias`
- [ ] Commit: `feat(mood): time-of-day bias on MoodSnapshot`

---

## Task 5 · Trust event temperature trio overlays

**Why:** Spec §11.2. When trust rises (warm gold), falls (cool steel), or collapses (hot crimson), a 1.5s wash overlays the current mood without replacing it.

**Files:**
- Modify: `nexus/aurora/mood.css` — add `.nx-trust-wash` keyframe overlays (warm-rising, cool-falling, hot-collapse)
- Modify: `nexus/aurora/app.js` — listen for trust changes (poll Chronicle for recent `aegis.trust_change` entries) and trigger the overlay class on body
- Create: `tests/aurora/test_trust_overlays.py`

**Steps:**

- [ ] Add CSS keyframe animations for 3 wash classes (1.5s fade in + fade out)
- [ ] In `app.js`, poll `/api/chronicle/recent?source=aegis&action=trust_change&limit=1` every 2s; when a new entry appears, classify it (rising / falling / collapse) and add the class to `body` for 1.5s
- [ ] Tests: CSS contains the three keyframes; app.js contains the polling + classify logic
- [ ] Commit: `feat(aurora): trust-event temperature trio overlays (rising/falling/collapse)`

---

## Task 6 · WebSocket streams (mood + permissions)

**Why:** Replace polling with push for the two most-frequent endpoints.

**Files:**
- Modify: `nexus/api/routes/mood.py` — add `@router.websocket("/api/mood/ws")`
- Modify: `nexus/api/routes/permissions.py` — add `@router.websocket("/api/permissions/ws")`
- Modify: `nexus/aurora/app.js` — connect WebSocket if available, fall back to polling otherwise
- Create: `tests/aurora/test_websockets.py`

The WS endpoints push every state change (mood transition / new permission ticket). When no client connects, no work is done. Surfaces still poll as a fallback if the WS dies.

**Steps:**

- [ ] Implement the two WebSocket endpoints
- [ ] Update app.js: try WS first, fall back to polling on disconnect
- [ ] Tests: WS endpoints respond, surfaces send right messages
- [ ] Commit: `feat(api): WebSocket push for mood + permissions`

---

## Task 7 · Accessibility automated checks

**Why:** Spec §11.5 — accessibility is non-negotiable. Codify the checks so regressions can't slip in.

**Files:**
- Create: `tests/aurora/test_accessibility.py`

Tests:
1. tokens.css contains `@media (prefers-reduced-motion: reduce)` block disabling animations
2. mood.css contains `@media (prefers-contrast: more)` block
3. tokens.css contains `@media (prefers-reduced-data: reduce)` block
4. icons.js — every glyph has stroke + accessible-label-able structure
5. Every surface route returns valid HTML with `<title>NEXUS</title>` and `lang="en"`
6. No emoji bytes anywhere in `nexus/aurora/*` (re-uses Phase 5 invariant)

**Steps:**
- [ ] Write the 6 tests
- [ ] Run them; they should all pass already (Phase 5 work satisfies them)
- [ ] Commit: `test(aurora): codify accessibility invariants`

---

## Task 8 · `README.md` rewrite for release

**Why:** The current README describes NEXUS as it was before Phase 1. The shipped reality is wildly different: the unified agent OS, the Aurora surfaces, the safety model, the workspace layer.

**Files:**
- Rewrite: `README.md`

The new README should:
- Open with the one-line elevator: *"NEXUS — the operating system for agents."*
- Show the layered architecture (4 layers: Surfaces / Workspace / Agent Runtime / Kernel)
- Explain the four surfaces (Workspaces → Conversational → Cockpit → Spatial) at a glance
- Explain the safety model (4 permission classes + install review + first-use prompt)
- Explain the local-first invariant (kernel does zero network I/O; verified by static test)
- Quickstart: `pip install -e ".[all]"` → `onexus serve` → open `/aurora`
- Link to: `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` and `docs/agents/*.md`
- Status badges: tests passing count, Python version, license

Length: aim for ~250 lines of clear, dense Markdown. No marketing fluff.

**Steps:**

- [ ] Write the new README
- [ ] Commit: `docs(readme): rewrite for v1 release — describe the shipped OS`

---

## Task 9 · Full-app release smoke

**Why:** A single test that exercises every surface + every gate together, end-to-end. Acts as the v1 acceptance criterion.

**Files:**
- Create: `tests/release/test_v1_acceptance.py`
- Create: `tests/release/__init__.py`

The test:
1. Boots a real FastAPI app via `create_app()`
2. Visits `/aurora` — expects HTML with the kernel mark
3. Calls `GET /api/mood/current` — gets a valid mood
4. Creates a workspace via `POST /api/workspaces`
5. Switches to it via `POST /api/workspaces/{id}/switch`
6. Sends a message via `POST /api/messages` — gets a Cortex response
7. Calls `GET /api/permissions/pending` — empty
8. Installs an agent manifest via `POST /api/agents/install` — gets a plan
9. Calls `GET /api/spatial/agents` — sees system agents + the just-installed one
10. Calls `GET /api/cockpit/snapshot` — sees the 7 panel keys
11. Asserts the failure set is byte-identical to baseline (or empty)
12. Asserts `nexus.kernel.*` modules don't import httpx (Phase 6 invariant)

**Steps:**

- [ ] Write the test
- [ ] Run; expect all assertions to pass
- [ ] Commit: `test(release): v1 acceptance smoke covering all surfaces + safety + invariants`

---

## Task 10 · Final tag + release notes

**Why:** A clean tag marks v1.

**Files:**
- Create: `docs/RELEASE_NOTES_v1.md`

The release notes summarize what shipped (each of the 7 phases in one paragraph), the public API surface, known limitations, the upgrade story.

**Steps:**

- [ ] Write release notes
- [ ] Commit: `docs: v1 release notes`
- [ ] Tag:

```bash
git tag -a v1.0 -m "NEXUS v1.0 — the operating system for agents

Seven phases shipped:
1. Foundation — manifest schema, agent adapters, Aegis arbiter
2. Built-in Migration — 10 built-ins on the unified runtime
3. Workspaces — isolated rooms with their own roster, memory, grants, tone
4. Safety UX — capability gating, install review, first-use prompt
5. Aurora Surfaces — four beautiful surfaces (Conversational, Cockpit, Spatial, Settings)
6. Network Gateway — every byte through aegis.network()
7. Release — test rot eliminated, accessibility verified, WebSockets, README

Local-first by invariant test. Bespoke iconography. Zero emojis.
Trust-gated permissions with the temperature trio overlays.

Suite: <count> passing. Failures: <count>. Collection errors: <count>."
git tag -a phase-7-release -m "Phase 7 polish complete; matches v1.0"
```

- [ ] Optional: push the tag to remote.

Phase 7 is done. NEXUS is **release-ready**.

---

## Self-review

This phase is mostly cleanup. The novel features are:
- Time-of-day modulation
- Trust event overlays
- WebSocket push
- Federation `as_agent` wrapping

Everything else is hygiene work to get to a clean release state.

**Risks:**
- Test rot deletion (Task 1) might delete tests that should have been fixed. Mitigation: only delete files whose imports point to genuinely-deleted modules.
- README rewrite (Task 8) is subjective. Mitigation: stay tight on the architecture map; let the docs do the heavy lifting.
- WebSocket (Task 6) adds complexity. Mitigation: keep polling as fallback so removing WS would still leave a working app.
