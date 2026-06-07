# Aurora Surfaces (Phase 5)

The visual layer of NEXUS. Four surfaces, one shell, one design system.

## Where it lives

```
nexus/aurora/
├── index.html            # single-page shell with hash router
├── tokens.css            # design tokens (color, type, glass card, perm-class pills, a11y)
├── mood.css              # 8 mood meshes + film grain + drift animations
├── app.css               # surface-specific layout + Cockpit Signal aesthetic
├── icons.js              # bespoke SVG library (zero emojis)
└── app.js                # router + Cmd-K / Cmd-` / Cmd-, keybinds + all surfaces
```

Served at **`/aurora`** by `nexus/api/routes/aurora.py`. Classic `/dashboard`
is preserved (spec §13.4 — backward compat during the transition window).

## The four surfaces (spec §12)

| Route               | Surface           | Keybind | Built in Task |
|---------------------|-------------------|---------|---------------|
| `#/workspaces`      | Workspaces switcher | ⌘K    | T5            |
| `#/conversation/:ws`| Conversational primary | (default) | T6   |
| Cockpit overlay     | Observability     | ⌘\`     | T7            |
| `#/spatial`         | Catalog grid      | (header)| T8            |
| `#/settings`        | Settings          | ⌘,      | T9            |

## Visual identity

- **Aurora atmosphere** — every page has a `nx-mood` body class that selects
  one of 8 gradient meshes (`tokens.css` + `mood.css`).
- **Kernel mark** — a small breathing radial-gradient orb that appears in the
  header, conversational input, and Cockpit. Custom SVG; defined in
  `icons.js:KERNEL_MARK`.
- **Bespoke per-agent identity marks** — every built-in (council, specter,
  autonomic, oracle, wraith, legacy, consciousness, sentry, echo, agents) has
  a unique geometric line-glyph in `icons.js:GLYPHS`. Each has a tone-coloured
  gradient disc + an optional trust ring around it (`identityDisc`).
- **Permission class pills** — Routine green, Notable violet-blue, Sensitive
  amber, Privileged coral (`tokens.css`).
- **Cockpit Signal aesthetic** — faint grid, scanline, oscilloscope-trace
  waveform in cyan/violet/amber.
- **Zero emojis** — enforced by `test_no_emojis_in_aurora_assets` in the
  Phase 5 smoke suite. Every icon is custom SVG.

## API endpoints used

- `GET /api/workspaces` — list + active marker
- `POST /api/workspaces` — create from form
- `POST /api/workspaces/{id}/switch` — set active
- `GET /api/mood/current` — current mood snapshot
- `POST /api/mood/observe` — push observations (used by tests)
- `GET /api/permissions/pending` — poll for first-use prompts
- `POST /api/permissions/decide` — resolve a prompt
- `POST /api/agents/install` — review (confirm=false) or persist (confirm=true)
- `GET /api/spatial/agents` — aggregated system + installed agents
- `GET /api/cockpit/pulse-rate` — 12-point pulse waveform
- `GET /api/cockpit/snapshot` — bundle for the 6 panels
- `POST /api/messages` — send a message to Cortex

## Polling

- `/api/mood/current` — every 2s, updates the body class to match.
- `/api/permissions/pending` — every 1.5s, surfaces first-use prompts when new
  tickets appear.
- Cockpit polls `pulse-rate` + `snapshot` only when open.

WebSockets (push instead of poll) are Phase 7 polish.

## Mood engine integration

Kernel events feed the mood engine (Phase 5 Task 10):

- `cortex.route` Pulse event → updates `MoodSignals.active_agent`
- `aegis.trust_change` Pulse event with `new_score < 0.5` → sets
  `MoodSignals.trust_collapsed = True` → mood transitions to `alert`

The signals are stored on `app.state.mood_signals`; `/api/mood/current`
re-evaluates the engine on every call.

## Accessibility (non-negotiable per spec §11.5)

- `prefers-reduced-motion: reduce` freezes the mood mesh drift and disables
  every transition (`tokens.css`).
- `prefers-contrast: more` collapses the mesh to monochrome (`mood.css`).
- `prefers-reduced-data: reduce` drops the mesh entirely.
- Every state has a non-color signal: mood name in `data-mood`, permission
  class name in the pill text, trust score in monospace.
- Bespoke icons all use stroke + fill that pass contrast on the midnight
  base.

## What's NOT in Phase 5

- WebSocket streams (`/ws/mood`, `/ws/pulse`, `/ws/permissions`) — Phase 7.
- Federation rewire through `aegis.network()` — Phase 6.
- LLM providers routing through `aegis.network()` — Phase 6.
- The 28 baseline failures + 65 collection errors (pre-existing test rot) —
  Phase 7 cleanup pass.
