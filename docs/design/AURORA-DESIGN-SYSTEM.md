# Aurora design system

Aurora is the ONEXUS app. This file is the contract every screen in it follows. If a screen needs something this does not cover, extend the system here and in `components.css` first, then use it. Do not solve it locally in a view.

The same tokens and rules apply to the site (`site/src/styles/custom.css` mirrors the token values).

## Files and their jobs

| File | Owns | May not |
| --- | --- | --- |
| `nexus/aurora/tokens.css` | Every value: color, type, space, radius, elevation, glow, motion, layout sizes. The base reset, focus ring and scrollbars. | Contain component or view selectors. |
| `nexus/aurora/mood.css` | The eight moods. A mood re-points the accent tokens and nothing else. The ambient horizon light and the trust washes. | Change layout, type or neutrals. |
| `nexus/aurora/components.css` | The shared component set listed below, with all of its states. | Know about any view. No `#id` selectors. |
| `nexus/aurora/scene.css` | The frame around the kernel scene canvas. | Restyle components. |
| `nexus/aurora/app.css` | The shell (chrome, sidebar, rail) and per-view layout. Composes components. | Set a literal color, font size, radius or shadow. Restyle a component's look. |
| `nexus/aurora/icons.js` | `icon(name, size)`, the Lucide-style UI set; agent glyphs; the identity tile; the ONEXUS mark. | Use emoji or third-party icon fonts. |

Load order is fixed in `index.html`: tokens, mood, components, scene, app.

## Tokens

**Neutrals.** Cool graphite. Surfaces step up in lightness only: `--nx-surface-sunken` (wells, code), `--nx-surface-canvas` (the app), `--nx-surface-1` (cards), `--nx-surface-2` (hover, raised), `--nx-surface-3` (pressed, selected), `--nx-surface-overlay` (modals and popovers).

**Text.** Four steps, measured against `--nx-surface-3`, the lightest surface text sits on:

| Token | Use | Contrast |
| --- | --- | --- |
| `--nx-fg-1` | Titles, primary values, anything you read first | 14:1 |
| `--nx-fg-2` | Body copy, control labels | 8.5:1 |
| `--nx-fg-3` | Metadata, helper text, eyebrow labels | 5.3:1 |
| `--nx-fg-4` | Disabled text and text 18px or larger only | 3:1 |

**Lines.** `--nx-line-1/2/3` are separators and card edges. `--nx-line-control` is the boundary of an input, select or checkbox and clears 3:1 on every surface.

**Accent.** One family, set by the mood: `--nx-accent`, `--nx-accent-strong`, `--nx-accent-rgb`, and the derived `--nx-accent-soft` (tinted fill), `--nx-accent-line` (tinted border), `--nx-accent-glow`. Text set on a solid accent uses `--nx-fg-on-accent`. All eight mood accents sit at the same perceived lightness, so switching mood never makes the app louder.

**Status.** `--nx-ok`, `--nx-info`, `--nx-warn`, `--nx-danger` (each with an `-rgb` twin). Aegis permission classes map onto them: routine is ok, notable is info, sensitive is warn, privileged is danger. Status is always paired with a word; color is never the only signal.

**Type.** System faces (Aurora is local-first and ships no web fonts). Mono is for code, ids, paths, numbers and keyboard hints, never for UI labels.

| Token | Size | Use |
| --- | --- | --- |
| `--nx-fs-micro` | 11px | Eyebrow labels, kbd, counters. The floor: nothing is smaller. |
| `--nx-fs-caption` | 12px | Metadata, helper text |
| `--nx-fs-ui` | 13px | Controls, list rows, dense body |
| `--nx-fs-body` | 14px | Messages, reading text |
| `--nx-fs-lead` | 16px | Lead paragraphs |
| `--nx-fs-h3` | 18px | Section and modal titles |
| `--nx-fs-h2` | 22px | Panel and detail titles |
| `--nx-fs-h1` | 28px | Page titles |
| `--nx-fs-display` | 40px | The tour and the empty workspace only |

Eyebrow labels are 11px, semibold, uppercase, `--nx-track-label` (0.06em). Titles use negative tracking (`--nx-track-title`, `--nx-track-display`).

**Space.** A 4px grid: `--nx-space-1` (4) through `--nx-space-16` (64), plus half steps `-0-5` (2) and `-1-5` (6). Page padding is `--nx-page-pad-x` / `--nx-page-pad-y`.

**Radii.** `xs` 4 (kbd, tags), `sm` 6 (buttons, inputs, rows), `md` 8 (cards), `lg` 12 (panels, modals, popovers), `full` (pills, dots).

**Elevation.** Borders carry structure. Shadows only lift floating layers: `--nx-shadow-1` (resting), `--nx-shadow-2` (popover), `--nx-shadow-3` (modal). No blur except the modal scrim.

**Glow.** Reserved for three states: keyboard focus (`--nx-ring`), live (`--nx-glow-live`, a running dot or an active step) and the hovered primary action (`--nx-glow-soft`). Nothing glows at rest.

**Motion.** `--nx-dur-1` 120ms (hover, press), `--nx-dur-2` 200ms (state change), `--nx-dur-3` 320ms (enter, slide-over). Easing `--nx-ease` for entrances, `--nx-ease-io` for loops. Under `prefers-reduced-motion` every animation collapses to its end state.

## Components

All in `components.css`. A view sets layout on a component (grid placement, gap, width) and never its look.

| Component | Classes | States |
| --- | --- | --- |
| Button | `.nx-btn` (secondary, the default), `-primary`, `-tinted`, `-ghost`, `-danger`, `-ok`; sizes `-sm`, `-lg`; `-icon`, `-block` | hover, active, `:disabled`, `aria-pressed`, `aria-busy`, `.is-armed` (danger confirm) |
| Icon button | `.nx-icon-btn` | hover, `.is-on` / `aria-pressed`, disabled |
| Link | `.nx-link` | hover |
| Field | `.nx-field`, `.nx-field-label`, `.nx-field-hint`, `.nx-field-error` | |
| Input | `.nx-input`, `.nx-select`, `.nx-textarea`; `-mono`, `-lg`; `.nx-search-field` (leading icon) | hover, focus ring, `aria-invalid`, disabled |
| Check | `.nx-check` (native checkbox or radio) | |
| Kbd | `.nx-kbd` | |
| Card | `.nx-card`, `-pad`, `-interactive`, `-head`, `-title`, `-sub`, `-body`, `-foot` | hover, `.is-selected` |
| Panel | `.nx-panel`, `.nx-panel-title`, `.nx-panel-sub` | |
| Well | `.nx-well` | |
| Section heading | `.nx-section-head`, `.nx-section-label` | |
| Page header | `.nx-page-head`, `-text`, `.nx-page-eyebrow`, `.nx-page-title`, `.nx-page-sub`, `.nx-page-actions` | |
| Detail header | `.nx-detail-head`, `.nx-detail-title`, `-sub`, `-facts`, `-actions` | stacks under 640px |
| List and row | `.nx-list`, `.nx-list-boxed`, `.nx-row`, `-interactive`, `-main`, `-title`, `-sub`, `-trail` | hover, `.is-selected` |
| Key and value | `.nx-kv`, `.nx-kv-pair`, `.nx-kv-key`, `.nx-kv-val` | stacks under 560px |
| Pill | `.nx-pill`, `-mono`, `-accent`, `-ok`, `-info`, `-warn`, `-danger` | |
| Status | `.nx-status` and `.nx-dot` with `.is-ok`, `.is-info`, `.is-warn`, `.is-danger`, `.is-live` | live pulses and glows |
| Permission class | `.nx-pc-routine`, `-notable`, `-sensitive`, `-privileged` | |
| Avatar | `.nx-avatar`; agent tiles come from `identityDisc()` / `agentDisc()` | trust ring |
| Tabs | `.nx-tabs`, `.nx-tab`, `.nx-tabs-vertical` | `.active` / `aria-selected` |
| Steps | `.nx-steps`, `.nx-step`, `-marker`, `-label`, `-detail`, `-meta` | `.is-active`, `.is-done`, `.is-error` (pending is the default) |
| Progress | `.nx-progress` + `.nx-progress-bar` with `--value` 0 to 1 | `.is-indeterminate` |
| Meter | `.nx-meter`, `-fill`, `-mark` (a floor or threshold) | |
| Alert | `.nx-alert`, `-title`, `-body` | `.is-danger` (with `role="alert"`), `.is-warn`, `.is-info` |
| Empty state | `.nx-empty-state`, `-icon`, `-title`, `-body`, `-actions`, `-compact`; `.nx-empty-line` for small slots | |
| Loading | `.nx-skeleton` (`-title`, `-line`, `-short`), `.nx-loading`, `.nx-spinner` (in app.css) | |
| Modal | `.nx-scrim` (`-top`), `.nx-modal` (`-wide`), `-head`, `-title`, `-sub`, `-body`, `-foot` | enter animation |
| Popover | `.nx-popover` | |
| Permission card | `.nx-perm-card` with `.class-routine` / `-notable` / `-sensitive` / `-privileged`; `-eyebrow`, `-body`, `-actions` | stacks under 640px |
| Chip | `.nx-chip` | hover, `.selected` / `aria-pressed` |
| Stat | `.nx-stat`, `-value`, `-label` | |
| Divider, code | `.nx-divider`, `.nx-code-inline`, `.nx-code-block` | |

Icons: `icon(name, size)` from `icons.js`, 24px grid at 1.75 stroke. Use 14px inside small buttons and rows, 16px in chrome and standard buttons, 20px in empty states.

## Rules every screen follows

1. **One page header.** Every full view starts with `.nx-page-head`: an eyebrow naming the area, a title, one line of plain context, actions on the right.
2. **One primary action per surface.** Everything else is secondary, ghost or a link.
3. **States are not optional.** Each data region renders four states with the shared components: loading (`.nx-skeleton` or `.nx-loading`), empty (`.nx-empty-state` or `.nx-empty-line`), error (`.nx-alert.is-danger`, `role="alert"`) and ready.
4. **No literal values in views.** `app.css` and JS templates use tokens. An inline `style` is allowed only for data-driven values (a tone color, a progress `--value`, a canvas size).
5. **Status says what it means.** A dot or color is always paired with a word.
6. **Copy.** Plain sentences. Sentence case for titles and buttons. No em dashes or double hyphens in visible copy. No emoji.
7. **Reach.** Every control is a real `button`, `a`, `input` or `select`, reachable by Tab, with the shared focus ring. Escape closes overlays.
8. **Width.** No horizontal page scroll at 390px. The rail hides under 980px, the sidebar collapses under 720px, and multi-column layouts stack.

## Checking a change

Run `.venv/bin/python -m pytest -q tests/aurora`. Then open `/aurora` from `onexus serve` and check the view at 390, 1280 and 1440 wide, with the keyboard only, and with reduced motion on.
