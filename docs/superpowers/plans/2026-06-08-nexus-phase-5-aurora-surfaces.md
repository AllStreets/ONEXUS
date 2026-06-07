# NEXUS Phase 5 — Aurora Surfaces Implementation Plan (Phase 5 of 7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the **Aurora-led visual identity** we settled in the brainstorming session — workspaces with their tone gradients, the breathing kernel mark, bespoke per-agent identity marks, the eight-mood ambient atmosphere, the four surfaces (Conversational primary, Cockpit observability overlay, Spatial catalog grid, Settings), the first-use prompt panel, and the install review modal. Everything ships as static HTML+CSS+JS served by the existing FastAPI app (matches the current `nexus/dashboard/` pattern — zero new toolchain). The classic dashboard stays available at `/dashboard` (backward compat); Aurora lives at `/aurora` and becomes the default in Phase 7.

**Architecture:**
- `nexus/aurora/` — new static asset directory (siblings to `nexus/dashboard/`).
  - `index.html` — single shell page with a top-level router (`#/workspaces`, `#/conversation/:ws`, `#/cockpit`, `#/spatial`, `#/settings`).
  - `tokens.css` — Aurora design tokens (8-mood color variables, type system, glass card, hairlines, kernel mark CSS).
  - `app.css` — surfaces' compositional CSS.
  - `mood.css` — the 8 mood meshes + film grain + drift animations.
  - `icons.js` — bespoke SVG library (kernel mark + 9 built-in identity glyphs + common UI icons; zero emojis).
  - `app.js` — surfaces' JS, polling + Cmd-K / Cmd-` / Cmd-, keybinds.
- `nexus/api/routes/aurora.py` — new FastAPI router serving `/aurora`, `/aurora/static/*`, `/api/mood/current`, `/api/mood/snapshot/:workspace_id`.
- Extended workspace, agents, and permissions endpoints (read-only views the surfaces consume).
- MoodEngine wired from kernel events: every Pulse tick + every Aegis change + active-module change feeds `MoodEngine.observe(...)` so `/api/mood/current` returns a live snapshot.

**Tech Stack:** Vanilla HTML / CSS / JS (no framework, no bundler). FastAPI serves the assets. Polling at 1 Hz for mood + permissions + pulse waveform — WebSockets are Phase 7 polish.

**Related spec:** `docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md` — §10 (Visual Identity), §11 (Mood Atlas), §12 (the four surfaces).

**Prior phase:** `phase-4-safety-ux` tag. The PermissionInbox + InstallPlan + agent install REST endpoints are in place; this phase consumes them.

---

## Pre-flight

- Branch from `phase-4-safety-ux` into `nexus-phase-5` (worktree `.worktrees/nexus-phase-5`).
- Baseline = **896 passing** (Phase 4 final).
- `source .venv/bin/activate` for every Bash invocation.

**File structure additions:**

```
nexus/
├── aurora/                          (new)
│   ├── index.html
│   ├── tokens.css
│   ├── app.css
│   ├── mood.css
│   ├── icons.js
│   └── app.js
├── api/routes/
│   └── aurora.py                    (new) — /aurora + /api/mood/*
└── ...

tests/
└── api/aurora/                      (new directory, fresh conftest to avoid the broken tests/api/conftest.py)
    ├── __init__.py
    ├── conftest.py                  (minimal — just the FastAPI TestClient fixture)
    ├── test_aurora_routes.py
    ├── test_mood_routes.py
    └── test_phase_5_smoke.py
```

The existing `tests/api/conftest.py` has a pre-existing collection error (`nexus.modules.general` missing — baseline rot). New Aurora API tests live under `tests/api/aurora/` with their own conftest.

---

## Task 1 · Design tokens + base CSS (`tokens.css` + `mood.css`)

**Why:** Every other Aurora surface CSS reads from these tokens. Establishing them first means no rewrites later.

**Files:**
- Create: `nexus/aurora/tokens.css`
- Create: `nexus/aurora/mood.css`

- [ ] **Step 1: Create `nexus/aurora/tokens.css`**

```css
/* NEXUS Aurora — design tokens
 * Spec: docs/superpowers/specs/2026-06-06-nexus-agent-os-design.md §10–11
 */
:root {
  /* base surface */
  --nx-bg: #0c0a14;
  --nx-text-high: #f0e9ff;
  --nx-text-mid: #e8e4f0;
  --nx-text-dim: rgba(232, 228, 240, 0.62);
  --nx-text-softer: rgba(232, 228, 240, 0.42);
  --nx-hairline: rgba(255, 255, 255, 0.07);

  /* glass card */
  --nx-card-bg: rgba(255, 255, 255, 0.05);
  --nx-card-border: rgba(255, 255, 255, 0.08);
  --nx-card-radius: 14px;
  --nx-card-blur: 20px;
  --nx-card-saturate: 140%;

  /* permission class accents */
  --nx-routine:    #9affb6; /* jewel green */
  --nx-notable:    #a8b4ff; /* calm violet-blue */
  --nx-sensitive:  #f8c460; /* warm amber */
  --nx-privileged: #f86078; /* coral */

  /* trust event temperatures */
  --nx-trust-rising:   #f8c460; /* warm gold */
  --nx-trust-falling:  #8cb8d4; /* cool steel */
  --nx-trust-collapse: #f8643c; /* hot crimson */

  /* workspace home tones (5 named) */
  --nx-tone-indigo-a:  #5a6cd0;
  --nx-tone-indigo-b:  #2c3a78;
  --nx-tone-magenta-a: #c060a0;
  --nx-tone-magenta-b: #5e2050;
  --nx-tone-sage-a:    #88a888;
  --nx-tone-sage-b:    #3e5840;
  --nx-tone-plum-a:    #7e5ea0;
  --nx-tone-plum-b:    #2c1c44;
  --nx-tone-amber-a:   #e8a06c;
  --nx-tone-amber-b:   #844820;

  /* type */
  --nx-font-display: "Inter Display", "SF Pro Display", -apple-system, system-ui, sans-serif;
  --nx-font-ui:      "Inter", "SF Pro Text", -apple-system, system-ui, sans-serif;
  --nx-font-mono:    "IBM Plex Mono", "JetBrains Mono", ui-monospace, monospace;

  /* sizing */
  --nx-radius-sm: 8px;
  --nx-radius-md: 12px;
  --nx-radius-lg: 16px;
  --nx-pad-card: 18px;

  /* eyebrow label */
  --nx-eyebrow-size: 9.5px;
  --nx-eyebrow-tracking: 0.22em;
}

/* reset minimal */
* { box-sizing: border-box; }
html { background: var(--nx-bg); color-scheme: dark; }
body {
  margin: 0;
  background: var(--nx-bg);
  color: var(--nx-text-mid);
  font-family: var(--nx-font-ui);
  letter-spacing: -0.005em;
  font-size: 14px;
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
}

.nx-display { font-family: var(--nx-font-display); font-weight: 500; letter-spacing: -0.02em; }
.nx-mono    { font-family: var(--nx-font-mono); font-feature-settings: "ss01", "ss02"; }
.nx-eyebrow {
  font-size: var(--nx-eyebrow-size);
  letter-spacing: var(--nx-eyebrow-tracking);
  text-transform: uppercase;
  opacity: 0.55;
  font-weight: 500;
}
.nx-dim    { opacity: 0.62; }
.nx-softer { opacity: 0.42; }

.nx-card {
  background: var(--nx-card-bg);
  backdrop-filter: blur(var(--nx-card-blur)) saturate(var(--nx-card-saturate));
  -webkit-backdrop-filter: blur(var(--nx-card-blur)) saturate(var(--nx-card-saturate));
  border: 1px solid var(--nx-card-border);
  border-radius: var(--nx-card-radius);
}
.nx-pill {
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 9px; border-radius: 999px;
  background: var(--nx-card-bg);
  border: 1px solid var(--nx-card-border);
  font-size: 11px;
}

/* permission class pills */
.nx-pc          { padding: 2px 9px; border-radius: 999px; font-size: 11px;
                  display: inline-flex; align-items: center; gap: 5px; }
.nx-pc::before  { content: ""; width: 7px; height: 7px; border-radius: 50%; }
.nx-pc-routine   { background: rgba(154,255,182,0.10); color: #b8f4cc; border: 1px solid rgba(154,255,182,0.22); }
.nx-pc-routine::before   { background: var(--nx-routine);   box-shadow: 0 0 6px var(--nx-routine); }
.nx-pc-notable   { background: rgba(168,180,255,0.10); color: #c6cfff; border: 1px solid rgba(168,180,255,0.25); }
.nx-pc-notable::before   { background: var(--nx-notable);   box-shadow: 0 0 6px var(--nx-notable); }
.nx-pc-sensitive { background: rgba(248,196,96,0.10); color: #f8d480; border: 1px solid rgba(248,196,96,0.28); }
.nx-pc-sensitive::before { background: var(--nx-sensitive); box-shadow: 0 0 6px var(--nx-sensitive); }
.nx-pc-privileged{ background: rgba(248,100,120,0.10); color: #ffb8c0; border: 1px solid rgba(248,100,120,0.30); }
.nx-pc-privileged::before{ background: var(--nx-privileged);box-shadow: 0 0 6px var(--nx-privileged); }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.001ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.001ms !important;
  }
}

/* prefers-reduced-data → drop the mesh entirely */
@media (prefers-reduced-data: reduce) {
  .nx-mood { background-image: none !important; }
  .nx-mood::before, .nx-mood::after { display: none !important; }
}
```

- [ ] **Step 2: Create `nexus/aurora/mood.css`**

```css
/* Aurora mood meshes — 8 ambient states tied to kernel observations
 * Spec §11.
 */

.nx-mood {
  position: relative;
  overflow: hidden;
}
.nx-mood::before {
  content: "";
  position: absolute; inset: -25%;
  filter: blur(55px); opacity: 0.45;
  pointer-events: none;
  animation: nx-drift var(--nx-drift, 24s) ease-in-out infinite alternate;
}
.nx-mood::after {
  content: "";
  position: absolute; inset: 0;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3CfeColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.10 0'/%3E%3C/filter%3E%3Crect width='180' height='180' filter='url(%23n)'/%3E%3C/svg%3E");
  opacity: 0.40;
  mix-blend-mode: overlay;
  pointer-events: none;
}
@keyframes nx-drift { to { transform: translate(2.5%, -1.5%) rotate(4deg) scale(1.04); } }

/* — mood-calm-focus — base — indigo/violet/amber */
.nx-mood-calm-focus { --nx-drift: 24s; background-color: #0c0a14; }
.nx-mood-calm-focus::before {
  background:
    radial-gradient(60% 50% at 22% 22%, rgba(120, 96, 200, 0.55) 0%, transparent 70%),
    radial-gradient(50% 45% at 78% 30%, rgba(255, 178, 110, 0.20) 0%, transparent 70%),
    radial-gradient(55% 55% at 60% 85%, rgba(76, 92, 168, 0.42) 0%, transparent 70%);
}

/* — mood-deep-flow — jewel green / oceanic */
.nx-mood-deep-flow { --nx-drift: 38s; background-color: #060a08; }
.nx-mood-deep-flow::before {
  background:
    radial-gradient(60% 55% at 28% 25%, rgba(28, 110, 90, 0.62) 0%, transparent 70%),
    radial-gradient(50% 50% at 76% 35%, rgba(56, 152, 124, 0.42) 0%, transparent 70%),
    radial-gradient(45% 45% at 60% 88%, rgba(16, 60, 70, 0.60) 0%, transparent 70%),
    radial-gradient(25% 25% at 80% 78%, rgba(220, 184, 96, 0.18) 0%, transparent 60%);
}

/* — mood-routing — electric magenta / cyan */
.nx-mood-routing { --nx-drift: 14s; background-color: #0a0612; }
.nx-mood-routing::before {
  background:
    radial-gradient(55% 50% at 20% 22%, rgba(220, 60, 200, 0.55) 0%, transparent 70%),
    radial-gradient(50% 50% at 78% 26%, rgba(40, 200, 240, 0.50) 0%, transparent 70%),
    radial-gradient(55% 55% at 58% 86%, rgba(80, 50, 180, 0.55) 0%, transparent 70%);
}

/* — mood-deliberating — fully warm: amber/bronze/burgundy */
.nx-mood-deliberating { --nx-drift: 30s; background-color: #100806; }
.nx-mood-deliberating::before {
  background:
    radial-gradient(55% 50% at 28% 26%, rgba(232, 168, 76, 0.60) 0%, transparent 70%),
    radial-gradient(50% 50% at 76% 36%, rgba(184, 108, 52, 0.50) 0%, transparent 70%),
    radial-gradient(48% 45% at 62% 86%, rgba(112, 40, 56, 0.45) 0%, transparent 70%),
    radial-gradient(30% 25% at 84% 80%, rgba(240, 220, 168, 0.20) 0%, transparent 60%);
}

/* — mood-creative — hot coral / tangerine / magenta / teal edge */
.nx-mood-creative { --nx-drift: 20s; background-color: #110608; }
.nx-mood-creative::before {
  background:
    radial-gradient(55% 50% at 22% 22%, rgba(248, 96, 120, 0.58) 0%, transparent 65%),
    radial-gradient(45% 45% at 78% 28%, rgba(248, 140, 60, 0.50) 0%, transparent 65%),
    radial-gradient(50% 50% at 62% 84%, rgba(216, 72, 168, 0.48) 0%, transparent 70%),
    radial-gradient(28% 28% at 84% 84%, rgba(56, 168, 184, 0.28) 0%, transparent 60%);
}

/* — mood-reflective — near-monochrome plum + rose ember */
.nx-mood-reflective { --nx-drift: 42s; background-color: #06040a; }
.nx-mood-reflective::before {
  background:
    radial-gradient(60% 55% at 30% 30%, rgba(80, 36, 92, 0.72) 0%, transparent 70%),
    radial-gradient(45% 45% at 72% 32%, rgba(48, 28, 76, 0.62) 0%, transparent 70%),
    radial-gradient(22% 22% at 80% 82%, rgba(220, 144, 168, 0.18) 0%, transparent 60%);
}

/* — mood-watchful — brass/olive/slate/ember */
.nx-mood-watchful { --nx-drift: 12s; background-color: #0a0a08; }
.nx-mood-watchful::before {
  background:
    radial-gradient(55% 50% at 24% 28%, rgba(184, 152, 64, 0.50) 0%, transparent 70%),
    radial-gradient(45% 45% at 70% 30%, rgba(116, 128, 60, 0.45) 0%, transparent 70%),
    radial-gradient(40% 40% at 50% 84%, rgba(220, 130, 56, 0.40) 0%, transparent 65%),
    radial-gradient(30% 30% at 86% 80%, rgba(76, 88, 108, 0.45) 0%, transparent 65%);
}

/* — mood-alert — crimson — overrides workspace tone */
.nx-mood-alert { --nx-drift: 7s; background-color: #0a0204; }
.nx-mood-alert::before {
  background:
    radial-gradient(60% 55% at 30% 30%, rgba(140, 28, 36, 0.72) 0%, transparent 65%),
    radial-gradient(40% 40% at 78% 32%, rgba(248, 100, 88, 0.48) 0%, transparent 65%),
    radial-gradient(45% 40% at 60% 86%, rgba(40, 8, 12, 0.65) 0%, transparent 70%);
}

/* Reduce-color users get monochrome */
@media (prefers-contrast: more) {
  .nx-mood::before { background: rgba(255,255,255,0.04) !important; opacity: 0.10 !important; }
}
```

- [ ] **Step 3: Commit**

```bash
mkdir -p nexus/aurora
# (after writing the files above)
git add nexus/aurora/tokens.css nexus/aurora/mood.css
git commit -m "feat(aurora): design tokens + 8-mood ambient meshes"
```

Note: this task ships only CSS. Tests come in Task 4 once the routes serve the files.

---

## Task 2 · Bespoke icon library (`icons.js`)

**Why:** Every glyph in Aurora is custom SVG — zero emojis (user preference, see memory: `feedback-design-language`). This task ships the kernel mark + 9 built-in identity glyphs + common UI icons.

**Files:**
- Create: `nexus/aurora/icons.js`

- [ ] **Step 1: Create `nexus/aurora/icons.js`**

```javascript
/* NEXUS Aurora — bespoke icon library
 * Every glyph is hand-drawn SVG. No emojis, no third-party icon sets.
 * Spec §10.4.
 */

export const KERNEL_MARK = (size = 24) => `
<svg width="${size}" height="${size}" viewBox="0 0 24 24" class="nx-kernel-mark">
  <defs>
    <radialGradient id="nx-kernel-grad" cx="40%" cy="35%">
      <stop offset="0%"  stop-color="#fbf7ff"/>
      <stop offset="40%" stop-color="#c9b8ff"/>
      <stop offset="100%" stop-color="#5a4ac4"/>
    </radialGradient>
  </defs>
  <circle cx="12" cy="12" r="9" fill="url(#nx-kernel-grad)"/>
  <circle cx="12" cy="12" r="3.2" fill="#fff" opacity="0.85"/>
</svg>`;

/* — identity disc + ring (used by every agent glyph) — */
export function identityDisc({ size = 44, gradient = ["#9aa8ff", "#4d5bcf"], trust = null, glyph = "" }) {
  const ring = trust == null ? "" : `
    <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" style="position:absolute;inset:0;">
      <circle cx="${size/2}" cy="${size/2}" r="${size/2 - 2}"
              stroke="rgba(255,255,255,0.08)" stroke-width="2" fill="none"/>
      <circle cx="${size/2}" cy="${size/2}" r="${size/2 - 2}"
              stroke="rgba(255,255,255,0.55)" stroke-width="2" fill="none"
              stroke-linecap="round"
              stroke-dasharray="${2 * Math.PI * (size/2 - 2)}"
              stroke-dashoffset="${2 * Math.PI * (size/2 - 2) * (1 - trust)}"
              transform="rotate(-90 ${size/2} ${size/2})"/>
    </svg>`;
  return `
    <div class="nx-id-disc" style="position:relative;width:${size}px;height:${size}px;">
      ${ring}
      <div style="position:absolute;inset:${trust == null ? 0 : 4}px;border-radius:50%;
                  background:radial-gradient(circle at 35% 30%, ${gradient[0]} 0%, ${gradient[1]} 70%);
                  box-shadow:0 0 0 1px rgba(255,255,255,0.08), 0 8px 24px -8px ${gradient[1]}88;
                  display:flex;align-items:center;justify-content:center;">
        ${glyph}
      </div>
    </div>`;
}

/* — 9 built-in agent glyphs — all stroke="#fff", small viewbox — */
export const GLYPHS = {
  /* council — four compass points + centre */
  council: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="#fff">
      <circle cx="11" cy="3"  r="1.6"/>
      <circle cx="19" cy="11" r="1.6"/>
      <circle cx="11" cy="19" r="1.6"/>
      <circle cx="3"  cy="11" r="1.6"/>
      <circle cx="11" cy="11" r="1.3" opacity="0.8"/>
    </svg>`,

  /* specter — warning triangle with line + dot */
  specter: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none"
         stroke="#fff" stroke-width="1.5" stroke-linejoin="round">
      <path d="M11 4l6.5 12h-13z"/>
      <path d="M11 11v3" stroke-linecap="round"/>
      <circle cx="11" cy="16.2" r="0.7" fill="#fff" stroke="none"/>
    </svg>`,

  /* autonomic — concentric rings (autopilot) */
  autonomic: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4">
      <circle cx="11" cy="11" r="2"/>
      <path d="M5 11a6 6 0 0 1 12 0"/>
      <path d="M2 11a9 9 0 0 1 18 0" opacity="0.55"/>
    </svg>`,

  /* oracle — eye-and-pupil */
  oracle: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.5">
      <path d="M2 11c2.5-4 6-6 9-6s6.5 2 9 6c-2.5 4-6 6-9 6s-6.5-2-9-6z"/>
      <circle cx="11" cy="11" r="2.3" fill="#fff" stroke="none"/>
    </svg>`,

  /* wraith — wisp with three trailing dots */
  wraith: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round">
      <path d="M4 8c0-3 3-4 7-4s7 2 7 5c0 2-2 4-4 4-1.5 0-2.5-1-4-1s-2.5 1-3 1z"/>
      <circle cx="6"  cy="16" r="0.9" fill="#fff" stroke="none" opacity="0.85"/>
      <circle cx="10" cy="18" r="0.8" fill="#fff" stroke="none" opacity="0.55"/>
      <circle cx="14" cy="17" r="0.7" fill="#fff" stroke="none" opacity="0.30"/>
    </svg>`,

  /* legacy — open book / parchment */
  legacy: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linejoin="round">
      <path d="M4 5l7 1 7-1v12l-7 1-7-1z"/>
      <path d="M11 6v12" opacity="0.5"/>
    </svg>`,

  /* consciousness — spiral */
  consciousness: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round">
      <path d="M11 11
               m-1 0 a1 1 0 1 1 2 0
               a3 3 0 1 1 -4 0
               a5 5 0 1 1 7 0
               a7 7 0 1 1 -10 0"/>
    </svg>`,

  /* sentry — minimalist heartbeat */
  sentry: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
      <path d="M2 11h4l2-4 3 8 2-6 2 2h5"/>
    </svg>`,

  /* echo — nested arcs */
  echo: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.5" stroke-linecap="round">
      <path d="M4 15a7 7 0 0 1 14 0"/>
      <path d="M7 15a4 4 0 0 1 8 0" opacity="0.7"/>
      <circle cx="11" cy="15" r="0.9" fill="#fff"/>
    </svg>`,

  /* agents (dispatcher) — three small docked tiles */
  agents: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linejoin="round">
      <rect x="3" y="3" width="6" height="6" rx="1.4"/>
      <rect x="13" y="3" width="6" height="6" rx="1.4"/>
      <rect x="3" y="13" width="6" height="6" rx="1.4"/>
      <rect x="13" y="13" width="6" height="6" rx="1.4" opacity="0.5" stroke-dasharray="2 2"/>
    </svg>`,
};

/* default gradient palette for each built-in (matches manifest "identity.gradient") */
export const GRADIENTS = {
  council:       ["#ffd2a0", "#c47a32"],
  specter:       ["#ff9eb8", "#8c2e54"],
  autonomic:     ["#c8a0ff", "#5e3a9c"],
  oracle:        ["#a8e8ff", "#346b9c"],
  wraith:        ["#9affc8", "#2a6a4e"],
  legacy:        ["#ffd680", "#9c6a1a"],
  consciousness: ["#e0c8ff", "#5a3a8c"],
  sentry:        ["#ffb878", "#8c4218"],
  echo:          ["#a8e8ff", "#346b9c"],
  agents:        ["#c8c8ff", "#3a3a8c"],
};

/* common UI icons — all line-stroke, no fills (cohesive language) */
export const UI = {
  plus:    (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M6 2v8M2 6h8"/></svg>`,
  close:   (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><path d="M3 3l6 6M9 3l-6 6"/></svg>`,
  chevron: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M4 3l3 3-3 3"/></svg>`,
  search:  (s = 14) => `<svg width="${s}" height="${s}" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"><circle cx="6" cy="6" r="4.5"/><path d="m12.5 12.5-3-3"/></svg>`,
  command: (s = 12) => `<svg width="${s}" height="${s}" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 1.5h5v5a2 2 0 0 1-2 2v-7m5 5v-5h-5"/></svg>`,
};

/* helper: build an agent identity card */
export function agentDisc(slug, { trust = null, size = 44 } = {}) {
  const gradient = GRADIENTS[slug] || ["#aaa", "#666"];
  const glyph = (GLYPHS[slug] || GLYPHS.agents)(Math.round(size * 0.45));
  return identityDisc({ size, gradient, trust, glyph });
}
```

- [ ] **Step 2: Commit**

```bash
git add nexus/aurora/icons.js
git commit -m "feat(aurora): bespoke icon library — kernel mark + 10 built-in glyphs"
```

---

## Task 3 · Aurora HTML shell + `/aurora` route

**Why:** A single-page shell with a hash-router. The other surfaces (workspaces, conversation, cockpit, spatial, settings) are sub-views inside this shell.

**Files:**
- Create: `nexus/aurora/index.html`
- Create: `nexus/aurora/app.css`
- Create: `nexus/aurora/app.js`
- Create: `nexus/api/routes/aurora.py`
- Modify: `nexus/api/server.py` (wire the router)
- Create: `tests/api/aurora/__init__.py`
- Create: `tests/api/aurora/conftest.py`
- Create: `tests/api/aurora/test_aurora_routes.py`

- [ ] **Step 1: Write the failing test**

`tests/api/aurora/conftest.py`:

```python
import pytest
from fastapi.testclient import TestClient
from nexus.api.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("NEXUS_DATA_DIR", str(tmp_path))
    return TestClient(create_app())
```

`tests/api/aurora/__init__.py`: empty.

`tests/api/aurora/test_aurora_routes.py`:

```python
"""Tests that /aurora serves the new dashboard shell + static assets."""


def test_aurora_index_returns_html(client):
    r = client.get("/aurora")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "NEXUS" in r.text
    # Bespoke iconography must NOT contain emojis (user preference)
    assert "🚀" not in r.text and "🔥" not in r.text


def test_aurora_serves_tokens_css(client):
    r = client.get("/aurora/static/tokens.css")
    assert r.status_code == 200
    assert "text/css" in r.headers["content-type"]
    assert "--nx-bg" in r.text  # design tokens present


def test_aurora_serves_mood_css(client):
    r = client.get("/aurora/static/mood.css")
    assert r.status_code == 200
    assert "nx-mood-calm-focus" in r.text
    assert "nx-mood-alert" in r.text


def test_aurora_serves_icons_js(client):
    r = client.get("/aurora/static/icons.js")
    assert r.status_code == 200
    assert "KERNEL_MARK" in r.text
    assert "GLYPHS" in r.text


def test_classic_dashboard_still_works(client):
    """The existing /dashboard route must keep working (backward compat per spec §13.4)."""
    r = client.get("/dashboard")
    assert r.status_code == 200
```

- [ ] **Step 2: Create `nexus/api/routes/aurora.py`**

```python
"""Aurora — the new visual surface. Serves /aurora and its static assets.

Classic /dashboard remains available (spec §13.4 backward-compat).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, HTMLResponse, Response


router = APIRouter(tags=["aurora"])
_STATIC_DIR = Path(__file__).parent.parent.parent / "aurora"


@router.get("/aurora", response_class=HTMLResponse)
async def aurora_index():
    return FileResponse(_STATIC_DIR / "index.html", media_type="text/html")


@router.get("/aurora/static/{filename:path}")
async def aurora_static(filename: str):
    path = _STATIC_DIR / filename
    if not path.exists() or not path.is_file():
        return Response(status_code=404)
    media_type = {
        ".css": "text/css",
        ".js": "application/javascript",
        ".html": "text/html",
        ".svg": "image/svg+xml",
    }.get(path.suffix, "application/octet-stream")
    return FileResponse(path, media_type=media_type)
```

- [ ] **Step 3: Create `nexus/aurora/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NEXUS</title>
  <link rel="stylesheet" href="/aurora/static/tokens.css">
  <link rel="stylesheet" href="/aurora/static/mood.css">
  <link rel="stylesheet" href="/aurora/static/app.css">
</head>
<body class="nx-mood nx-mood-calm-focus" data-mood="calm_focus">
  <header class="nx-header">
    <div class="nx-header-left">
      <span id="nx-kernel-mark"></span>
      <span class="nx-display" style="font-size:14px">NEXUS</span>
    </div>
    <div class="nx-header-right">
      <button id="nx-workspaces-btn" class="nx-pill" title="Workspaces (⌘K)">
        <span id="nx-active-workspace">No workspace</span>
      </button>
      <button id="nx-cockpit-btn" class="nx-pill" title="Cockpit (⌘\\`)">cockpit</button>
      <button id="nx-spatial-btn" class="nx-pill" title="Catalog">catalog</button>
      <button id="nx-settings-btn" class="nx-pill" title="Settings (⌘,)">settings</button>
    </div>
  </header>

  <main id="nx-view" class="nx-view">
    <!-- view content rendered by app.js per route -->
  </main>

  <div id="nx-overlay-root"></div>

  <script type="module" src="/aurora/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: Create `nexus/aurora/app.css`**

```css
.nx-header {
  position: fixed; top: 0; left: 0; right: 0; height: 48px; z-index: 10;
  display: flex; align-items: center; justify-content: space-between;
  padding: 0 18px;
  background: linear-gradient(to bottom, rgba(12,10,20,0.85), transparent);
  backdrop-filter: blur(12px);
}
.nx-header-left, .nx-header-right { display: flex; align-items: center; gap: 10px; }

.nx-kernel-mark {
  filter: drop-shadow(0 0 4px rgba(168, 180, 255, 0.7))
          drop-shadow(0 0 12px rgba(168, 180, 255, 0.35));
  animation: nx-breath 4.5s ease-in-out infinite;
}
@keyframes nx-breath {
  0%, 100% { opacity: 0.78; transform: scale(0.96); }
  50%      { opacity: 1;    transform: scale(1.04); }
}

.nx-view {
  position: relative; z-index: 1;
  padding: 64px 24px 24px;
  min-height: 100vh;
}

.nx-empty { padding: 40px; text-align: center; opacity: 0.6; }

/* Overlay root for ⌘K, ⌘`, install review, first-use prompt */
#nx-overlay-root { position: fixed; inset: 0; pointer-events: none; z-index: 100; }
#nx-overlay-root > * { pointer-events: auto; }
```

- [ ] **Step 5: Create `nexus/aurora/app.js`**

```javascript
import { KERNEL_MARK } from "/aurora/static/icons.js";

/* —— bootstrap —— */
document.getElementById("nx-kernel-mark").innerHTML = KERNEL_MARK(14);

/* —— router (Phase 5 placeholder; surfaces filled in later tasks) —— */
function route(hash) {
  const v = document.getElementById("nx-view");
  if (!hash || hash === "#" || hash === "#/") {
    v.innerHTML = `<div class="nx-empty"><div class="nx-display" style="font-size:22px">NEXUS Aurora</div>
                   <p class="nx-dim">surfaces will land in subsequent Phase 5 tasks.</p></div>`;
    return;
  }
  v.innerHTML = `<div class="nx-empty nx-dim">unknown route: ${hash}</div>`;
}
window.addEventListener("hashchange", () => route(location.hash));
route(location.hash);

/* —— keybindings (Phase 5 stubs; actual handlers added by later tasks) —— */
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); document.getElementById("nx-workspaces-btn").click(); }
  if ((e.metaKey || e.ctrlKey) && e.key === "`") { e.preventDefault(); document.getElementById("nx-cockpit-btn").click(); }
  if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); document.getElementById("nx-settings-btn").click(); }
});

/* polling for mood — keeps the body class in sync */
async function pollMood() {
  try {
    const r = await fetch("/api/mood/current");
    if (r.ok) {
      const body = await r.json();
      const cls = "nx-mood-" + body.mood.replace(/_/g, "-");
      const current = [...document.body.classList].find(c => c.startsWith("nx-mood-"));
      if (current && current !== cls) document.body.classList.remove(current);
      if (!document.body.classList.contains(cls)) document.body.classList.add(cls);
      document.body.dataset.mood = body.mood;
    }
  } catch {}
}
setInterval(pollMood, 2000);
pollMood();
```

- [ ] **Step 6: Wire the router in `nexus/api/server.py`**

After the existing `app.include_router(...)` block, add:

```python
    from nexus.api.routes.aurora import router as aurora_router
    app.include_router(aurora_router)
```

Note: the `/api/mood/current` endpoint is added in Task 4; it'll 404 until then, and the polling JS handles that silently.

- [ ] **Step 7: Run the tests**

```bash
pytest tests/api/aurora/test_aurora_routes.py -v
```

Expected: 5 passed.

- [ ] **Step 8: Regression**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3
```

Expected: 901 passing (896 + 5 new).

- [ ] **Step 9: Commit**

```bash
git add nexus/aurora/index.html nexus/aurora/app.css nexus/aurora/app.js \
        nexus/api/routes/aurora.py nexus/api/server.py \
        tests/api/aurora/
git commit -m "feat(aurora): HTML shell + /aurora route + static asset serving"
```

---

## Task 4 · `/api/mood/current` endpoint

**Why:** The Aurora shell polls this every 2s to drive the body class (which selects the mood mesh). Returns `{mood, tone, drift_seconds, reason}` from `MoodEngine.current()`.

**Files:**
- Create: `nexus/api/routes/mood.py`
- Modify: `nexus/api/server.py` (wire router; create + store a `MoodEngine` instance on `app.state`)
- Create: `tests/api/aurora/test_mood_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for /api/mood/current."""


def test_mood_current_defaults_to_calm_focus(client):
    r = client.get("/api/mood/current")
    assert r.status_code == 200
    body = r.json()
    assert body["mood"] == "calm_focus"
    assert body["drift_seconds"] > 0
    assert "reason" in body


def test_mood_observe_changes_current(client):
    # Force a state change via the observe endpoint, then check current
    r = client.post("/api/mood/observe",
                    json={"trust_collapse": True})
    assert r.status_code == 200
    r2 = client.get("/api/mood/current")
    assert r2.json()["mood"] == "alert"


def test_mood_observe_unknown_field_400(client):
    r = client.post("/api/mood/observe", json={"banana": True})
    assert r.status_code == 400
```

- [ ] **Step 2: Implement `nexus/api/routes/mood.py`**

```python
"""REST endpoints for the workspace MoodEngine."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from nexus.workspaces.mood import MoodEngine


router = APIRouter(prefix="/api/mood", tags=["mood"])


def _get_engine(request: Request) -> MoodEngine:
    engine = getattr(request.app.state, "mood_engine", None)
    if engine is None:
        engine = MoodEngine()
        request.app.state.mood_engine = engine
    return engine


class ObserveBody(BaseModel):
    """Mirror of MoodEngine._State fields (Phase 3)."""
    # all fields optional — surface only sets what it observes
    pulse_per_min: float | None = None
    active_agents: int | None = None
    active_module: str | None = None
    resident_agents: list[str] | None = None
    oracle_flagged: bool | None = None
    trust_collapse: bool | None = None
    sustained_focus_minutes: float | None = None
    is_late_hour: bool | None = None


@router.get("/current")
async def current(request: Request) -> dict:
    engine = _get_engine(request)
    snap = engine.current()
    return {
        "mood": snap.mood.value,
        "tone": snap.tone.value if snap.tone is not None else None,
        "drift_seconds": snap.drift_seconds,
        "reason": snap.reason,
    }


@router.post("/observe")
async def observe(request: Request, body: ObserveBody) -> dict:
    engine = _get_engine(request)
    fields = body.model_dump(exclude_none=True)
    try:
        engine.observe(**fields)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    snap = engine.current()
    return {"mood": snap.mood.value, "reason": snap.reason}
```

Note: the Phase 3 `MoodEngine.observe(**kwargs)` raises `ValueError` on unknown fields — that's what gives 400.

Caveat: the test `test_mood_observe_unknown_field_400` adds the `banana` field. Since `ObserveBody` won't accept it (pydantic strict-ish), pydantic itself returns 422. To get the explicit 400, configure the pydantic model to allow extras and then let `engine.observe(banana=True)` raise: set `model_config = ConfigDict(extra="allow")` on `ObserveBody`. Adjust per actual behaviour during implementation; the test asserts 400 — either bridge the gap by handling 422 → 400 or by allowing extras.

The simplest fix: keep `ObserveBody` strict and update the test to expect **422** (FastAPI's default for invalid body), OR explicitly allow extras and pass them through. **Recommend** the latter so future fields don't require a schema change.

- [ ] **Step 3: Wire in `nexus/api/server.py`**

```python
    from nexus.api.routes.mood import router as mood_router
    app.include_router(mood_router)
```

- [ ] **Step 4: Run + regression**

```bash
pytest tests/api/aurora/test_mood_routes.py -v        # 3 passed
pytest --continue-on-collection-errors --tb=no -q 2>&1 | tail -3   # 904 passing
```

- [ ] **Step 5: Commit**

```bash
git add nexus/api/routes/mood.py nexus/api/server.py tests/api/aurora/test_mood_routes.py
git commit -m "feat(api): add /api/mood/current and /api/mood/observe endpoints"
```

---

## Task 5 · Workspaces switcher (Cmd-K)

**Why:** The first surface a user sees. Shows the workspace tiles with home tones + agent stacks + last-active timestamp + an active marker.

**Files:**
- Modify: `nexus/aurora/app.css` (add switcher styles)
- Modify: `nexus/aurora/app.js` (add switcher view + ⌘K binding)
- Modify: `nexus/aurora/index.html` (no change needed; switcher renders into `#nx-overlay-root`)

The plan covers this in detail at: `git show main:docs/superpowers/plans/2026-06-08-nexus-phase-5-aurora-surfaces.md` once committed. For brevity here, the subagent should:

1. Add a `#/workspaces` view (route) that renders a grid of workspace tiles by fetching `GET /api/workspaces` (existing).
2. Add a Cmd-K binding that pushes `#/workspaces` to the URL.
3. Each tile renders the workspace's home tone gradient, name, resident agent identity discs (small), and last-active text.
4. Tile click → `POST /api/workspaces/{id}/switch` (existing endpoint from Phase 3) → push `#/conversation/{id}`.
5. A trailing "new workspace" tile opens an inline form that POSTs `/api/workspaces`.

Tests are minimal — verify the workspaces route loads + the API endpoints return the expected JSON shape (`tests/api/aurora/test_phase_5_smoke.py` placeholder; flesh out in Task 11 smoke test).

Commit message: `feat(aurora): workspaces switcher view with Cmd-K binding`.

---

## Task 6 · Conversational surface

**Why:** The primary in-room view. Three columns: workspaces + resident roster on the left, conversation in the center, ambient mood + kernel status on the right.

**Files:**
- Modify: `nexus/aurora/app.css` (three-column grid + conversation styles)
- Modify: `nexus/aurora/app.js` (conversation route + send/receive logic)

Route: `#/conversation/:workspaceId`.

Backend already provides:
- `POST /api/messages` (existing) — send a message; returns Cortex's response with `{module, response}`.
- `GET /api/chronicle/recent?source=cortex&action=route&limit=20` (existing) — pull routing decisions for the "picked by cortex" attribution line.

UI requirements per spec §12.1:
- Left column: small workspaces list (selected one highlighted), eyebrow "Roster" with each resident agent as `agentDisc(slug, {trust, size: 22})` + trust score.
- Center: conversation messages; each agent response shows `agentDisc(slug, {size: 28})` + name + a small `nx-mono` attribution `picked by cortex · 0.78 match · 0.67 trust`.
- Center bottom: input box with the kernel mark, placeholder `Ask anything, or @ to call a specific agent…`, and a `⌘K` hint pill.
- Right column: a glass card showing the current mood ("Calm focus"), pulse rate, last few Chronicle entries.

Commit message: `feat(aurora): conversational primary surface with 3-column layout`.

---

## Task 7 · Cockpit overlay (Cmd-`)

**Why:** Spec §12.2. Observability layer over the conversational surface; six panels.

**Files:**
- Modify: `nexus/aurora/app.css` (cockpit grid + signal/scanline styles)
- Modify: `nexus/aurora/app.js` (Cmd-` toggle + cockpit content)
- Modify: `nexus/aurora/icons.js` if any new icons are needed (signal traces are inline SVG)

Cockpit content (per spec §12.2):
1. **Pulse waveform** (spans 2 rows) — 60s rolling window, 3 traces (cortex.route / aegis.check / chronicle). Source: `GET /api/events/pulse-rate?topics=cortex.route,aegis.check,chronicle&window=60` (add this read-only endpoint in this task).
2. **Resident agents** — name + identityDisc + memory + trust. Source: `GET /api/agents/resident?workspace_id=...` (use the WorkspaceRuntime data exposed via existing or new endpoint).
3. **Trust gradient 24h** — per-agent sparkline. Source: `GET /api/trust/history?window=24h`.
4. **Last route · concierge synthesis** (spans 2 cols) — most recent route trace from Chronicle.
5. **Chronicle live tail** (spans 2 cols) — recent Chronicle entries.
6. **Network gateway** + **Engram partition stats** — `GET /api/network/recent` and `GET /api/engram/partition-stats?workspace_id=...`.

Add the new GET endpoints in `nexus/api/routes/cockpit.py` with simple read-only implementations.

Commit message: `feat(aurora): Cockpit observability overlay with 6 panels`.

---

## Task 8 · Spatial catalog grid

**Why:** Spec §12.3. The "browse all agents" view. System agents and third-party agents in one grid; each card has an identity disc with trust ring + bespoke glyph + tagline + status + install button when applicable.

**Files:**
- Modify: `nexus/aurora/app.css` (grid + card styles)
- Modify: `nexus/aurora/app.js` (spatial route + install button → calls `/api/agents/install`)

Source endpoints (existing or new):
- `GET /api/agents` — installed + system agents (combine the existing `agents/catalog` reader + `installed_slugs` from Phase 4 installer).
- `GET /api/agents/catalog` — the full ONEXUS-Agents catalog (existing Phase 1 endpoint).

Each card:
- `agentDisc(slug, {trust: trustValue, size: 48})` (uses Task 2's helper)
- Name + tagline
- Status indicator: green dot for resident, dim grey for sleeping, install button for installable
- For installable agents: clicking "Install" opens the Install Review Modal (Task 9) with the agent's manifest pre-loaded.

Commit message: `feat(aurora): Spatial catalog grid with bespoke identity discs`.

---

## Task 9 · Settings panels + first-use prompt + install review modal

**Why:** Three smaller surfaces — Settings (tabbed) + the two modal panels (install review + first-use prompt) that the safety UX backend (Phase 4) now drives.

**Files:**
- Modify: `nexus/aurora/app.css`
- Modify: `nexus/aurora/app.js`

Settings tabs (per spec §12.4): General / Workspaces / Agents / Security / Providers / About.

The two modals each render off existing Phase 4 endpoints:
- **Install Review Modal:** `POST /api/agents/install` with `confirm: false` → renders the plan groups (color-coded by class). Buttons: Cancel / Install with restrictions (opens per-capability editor) / Install. On click → re-POST with `confirm: true`.
- **First-Use Prompt Panel:** polls `GET /api/permissions/pending` at 1 Hz; when a ticket appears, slides in a glass card with the four buttons (Allow once / Always in workspace / Always everywhere / Don't allow). On click → `POST /api/permissions/decide`.

Commit message: `feat(aurora): Settings + install review modal + first-use prompt panel`.

---

## Task 10 · Mood engine wiring (kernel → MoodEngine → /api/mood/current)

**Why:** Phase 3 built `MoodEngine.observe(...)` but nothing calls it from the kernel. This task wires kernel events into the engine so `/api/mood/current` returns live data.

**Files:**
- Modify: `nexus/api/server.py` (subscribe to Pulse on startup; route events → MoodEngine.observe)

In `create_app()` add a startup hook:

```python
@app.on_event("startup")
async def _wire_mood_engine():
    pulse = app.state.kernel.pulse
    engine = getattr(app.state, "mood_engine", None) or MoodEngine()
    app.state.mood_engine = engine

    async def on_route(msg):
        # msg.payload has {target, message_preview, intent_scores, ...}
        engine.observe(active_module=msg.payload.get("target"))

    async def on_trust_collapse(msg):
        engine.observe(trust_collapse=True)

    pulse.subscribe("cortex.route", on_route)
    pulse.subscribe("aegis.trust_collapse", on_trust_collapse)
```

(If `app.state.kernel` doesn't exist yet, this task also adds it — set `app.state.kernel = SimpleNamespace(pulse=Pulse(), ...)` during init.)

Test that `POST /api/messages` followed by `GET /api/mood/current` shows a state change (e.g., active_module reflects whichever module Cortex routed to).

Commit message: `feat(aurora): wire kernel Pulse events into MoodEngine`.

---

## Task 11 · End-to-end Phase 5 smoke

**Why:** Prove the full surface stack loads and the four routes render their expected sentinel markers.

**Files:**
- Create: `tests/api/aurora/test_phase_5_smoke.py`

Tests:
1. `GET /aurora` returns HTML with `id="nx-kernel-mark"` and the bespoke icon import.
2. `GET /aurora/static/icons.js` contains all 9 GLYPHS keys + KERNEL_MARK + UI helpers.
3. `GET /api/mood/current` returns 200 with `{mood, drift_seconds, reason}`.
4. After `POST /api/permissions/decide` with an unknown id → 404 (Phase 4 surface still works under Aurora server).
5. `GET /dashboard` (classic) is still 200.

Commit message: `test(aurora): end-to-end Phase 5 smoke`.

---

## Task 12 · Accessibility audit + docs + tag

**Why:** Spec §11.5 — accessibility is non-negotiable. Verify Reduce Motion / Reduce Color / contrast / non-color signals.

- [ ] **Step 1: Manual checks**

- With `prefers-reduced-motion: reduce` (DevTools → Emulate CSS), the mesh stops drifting. Verify by inspecting `tokens.css` (already enforced via media query).
- With `prefers-contrast: more`, the mesh collapses to monochrome (already in `tokens.css`).
- Every state has a non-color signal: mood name appears in `data-mood`; permission class pills include the class name in text.

- [ ] **Step 2: Create `docs/agents/surfaces.md`**

Briefly document the four surfaces, the routing model (#/workspaces, #/conversation/:ws, #/cockpit, #/spatial, #/settings), the polling intervals (1 Hz mood + permissions; 2 Hz pulse waveform), the Cmd-K / Cmd-` / Cmd-, keybindings, and accessibility commitments.

- [ ] **Step 3: Verify regression baseline**

```bash
pytest --continue-on-collection-errors --tb=no -q 2>&1 | grep -E "^FAILED" | awk '{print $2}' | sort > /tmp/p5_failures.txt
diff .baseline_failures.txt /tmp/p5_failures.txt && echo "[FAILURE SET IDENTICAL TO BASELINE]"
```

- [ ] **Step 4: Commit + tag**

```bash
git add docs/agents/surfaces.md
git commit -m "docs(aurora): Phase 5 — surfaces"
git tag -a phase-5-aurora-surfaces -m "Phase 5 Aurora surfaces complete: Conversational + Cockpit + Spatial + Settings, mood engine wired, bespoke iconography

- Design tokens: 8-mood meshes, type system, glass card, kernel mark CSS
- Bespoke icon library: kernel mark + 10 built-in identity glyphs (zero emojis)
- HTML shell + hash router at /aurora
- /api/mood/current + /api/mood/observe wired into MoodEngine
- Workspaces switcher (Cmd-K), Conversational primary (3-column), Cockpit (Cmd-\\\`, 6 panels), Spatial catalog grid
- Install review modal + first-use prompt panel (Phase 4 endpoints consumed)
- Settings: General / Workspaces / Agents / Security / Providers / About
- Accessibility: prefers-reduced-motion + prefers-contrast handled
- Classic /dashboard preserved

Suite: <count> passing.
Failure set byte-identical to baseline."
```

---

## Self-Review

| Spec section | Implementing task | Notes |
|---|---|---|
| §10 Visual identity | Tasks 1, 2, 3 | Design tokens + icons + shell |
| §11 Mood atlas | Tasks 1, 4, 10 | mood.css + /api/mood + kernel-event wiring |
| §12.1 Conversational | Task 6 | 3-column view |
| §12.2 Cockpit | Task 7 | 6 panels + Cmd-` |
| §12.3 Spatial | Task 8 | catalog grid |
| §12.4 Settings | Task 9 | 6 tabs |
| §9.2 Install review (UI) | Task 9 | modal renders Phase 4 install plan |
| §9.3 First-use prompt (UI) | Task 9 | slides into conversational |
| §11.5 Accessibility | Tasks 1, 12 | CSS media queries + audit |

**Open issues for Phase 6:**
- WebSocket streams for live mood / pulse / permissions (Phase 5 uses polling).
- LLM provider routing through `aegis.network()` (Phase 6's main job).
