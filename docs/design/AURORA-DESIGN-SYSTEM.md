# Aurora design system

Aurora is the ONEXUS app. This file is the contract every screen in it follows. If a screen needs something this does not cover, extend the system here and in `components.css` first, then use it. Do not solve it locally in a view.

The same tokens and rules apply to the site (`site/src/styles/custom.css` mirrors the token values).

## Files and their jobs

| File | Owns | May not |
| --- | --- | --- |
| `nexus/aurora/tokens.css` | Every value: color, type, space, radius, elevation, glow, motion, layout sizes. The base reset, focus ring and scrollbars. | Contain component or view selectors. |
| `nexus/aurora/mood.css` | The eight moods. A mood sets the whole color atmosphere: the accent, three ambient field colors, and a tint for surfaces, edges and the chrome. The ambient field and the trust washes. | Change layout or type. Push a field color past the contrast budget. |
| `nexus/aurora/components.css` | The shared component set listed below, with all of its states. | Know about any view. No `#id` selectors. |
| `nexus/aurora/scene.css` | The frame around the kernel scene canvas. | Restyle components. |
| `nexus/aurora/app.css` | The shell (chrome, sidebar, rail) and per-view layout. Composes components. | Set a literal color, font size, radius or shadow. Restyle a component's look. |
| `nexus/aurora/icons.js` | `icon(name, size)`, the Lucide-style UI set; agent marks (built-in glyphs and generated catalog marks); the ONEXUS mark. | Use emoji or third-party icon fonts. |

Load order is fixed in `index.html`: tokens, mood, components, scene, app.

## Tokens

**Neutrals.** Cool graphite, tinted by the mood (see below). Surfaces step up in lightness: `--nx-surface-sunken` (wells, code), `--nx-surface-canvas` (the app), `--nx-surface-1` (cards), `--nx-surface-2` (hover, raised), `--nx-surface-3` (pressed, selected), `--nx-surface-overlay` (modals and popovers).

**Text.** Four steps, measured against `--nx-surface-3`, the lightest surface text sits on:

| Token | Use | Contrast |
| --- | --- | --- |
| `--nx-fg-1` | Titles, primary values, anything you read first | 14:1 |
| `--nx-fg-2` | Body copy, control labels | 8.5:1 |
| `--nx-fg-3` | Metadata, helper text, eyebrow labels | 6:1 (4.8:1 at the brightest field point) |
| `--nx-fg-4` | Disabled text and text 18px or larger only | 3:1 |

**Lines.** `--nx-line-1/2/3` are separators and card edges. `--nx-line-control` is the boundary of an input, select or checkbox and clears 3:1 on every surface.

**Accent.** One family, set by the mood: `--nx-accent`, `--nx-accent-strong`, and the derived `--nx-accent-soft` (tinted fill), `--nx-accent-line` (tinted border), `--nx-accent-glow`. Derive new accent colors with `color-mix(in srgb, var(--nx-accent) N%, transparent)`, never from `--nx-accent-rgb` (kept for old markup only), so they animate with the mood. Text set on a solid accent uses `--nx-fg-on-accent`. All eight mood accents sit at the same perceived lightness, so switching mood never makes the app louder.

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

## Mood is the color of the app

The mood is central to ONEXUS, so it sets the whole color atmosphere, not just the accent. A mood defines five colors, all in `mood.css`:

| Token | Role |
| --- | --- |
| `--nx-accent` / `--nx-accent-strong` | Interactive color: focus, primary actions, live states, the active workspace |
| `--nx-mood-1`, `-2`, `-3` | The ambient field: three wide lights (top left, bottom right, and one across the center) plus a slow drift. The canvas and sunken surfaces are themselves a third of field 1, so the mood shows even where no light reaches |
| `--nx-mood-tint` | Mixed into cards and raised surfaces (7 to 11 percent), every line (14 to 26 percent) and the chrome band |

The shell regions (chrome, sidebar, rail) are mood-tinted glass over the field. Cards and panels use `--nx-glass-card`, the card surface at 82 percent, so the field colors them while text stays on a solid enough ground. Headers and primary actions carry the accent (see Signature details). The test: the mood should be nameable from any screenshot of any view. All five colors are registered with `@property`, so changing mood crossfades the whole window over about 1.4 seconds; under `prefers-reduced-motion` it snaps. `prefers-contrast: more` drops the field and the tints.

**Contrast rule.** Field colors are chosen against a luminance budget, not by eye: at the brightest point of a field, with the accent horizon on top, `--nx-fg-3` must keep 4.8:1 and `--nx-fg-2` 6.5:1. This is measured on real pixels for every mood (hide the text, screenshot, sample the brightest background behind each text box). To change a field color, keep its relative luminance at or under 0.035.

| Mood | Accent | Field 1 | Field 2 | Field 3 | Character |
| --- | --- | --- | --- | --- | --- |
| calm focus | `#4ed5d5` | `#0d2d30` | `#0c2a49` | `#0f2e22` | Aurora teal over deep sea and pine. The default. |
| deep flow | `#7ad59c` | `#0e2d1f` | `#0b2e2f` | `#302910` | Jade and lagoon with a low gold. |
| routing | `#f197c2` | `#4a1835` | `#452018` | `#2f1a52` | Magenta rose, coral and violet: busy, fanning out. |
| deliberating | `#f4b768` | `#36270f` | `#451d10` | `#451426` | Amber, copper and oxblood: a room weighing options. |
| creative | `#96b4ff` | `#19245f` | `#44221b` | `#0e2d41` | Ultramarine against a warm coral, not a purple blob. |
| reflective | `#d9a8ef` | `#3d1a4b` | `#451c31` | `#22204a` | Orchid, mulberry and dusk. |
| watchful | `#6bcbf7` | `#0d2b42` | `#1e2b37` | `#0d2c33` | Sky, steel and cold water. |
| alert | `#fb817a` | `#541317` | `#45220e` | `#3b0c1a` | Signal red, ember and blood. |

Workspace tones are a second, separate color identity: each workspace card is set in its own tone (a deep tone ground, a bloom of the light tone in one corner, a tone edge and an emblem with its initials). Text on a tone card is white at 74 to 100 percent and sits on the darker half.

## Agent marks

Agents are never drawn as a circle with a dot. Every agent has a mark from `icons.js`:

- **Built-in agents** sit on the hex *core* tile in their own gradient (`GRADIENTS`), with a hand-drawn glyph (`GLYPHS`) that states what they do: council's brackets, specter's crosshair, oracle's lens, atlas's cube and so on.
- **Catalog agents** get a mark generated from their slug by `markSpec(slug)`: one of six tile shapes (squircle, chamfer, shield, octagon, tab, diamond), one of eighteen curated color pairs, one of eight background patterns, and a one or two letter monogram. The same slug always gives the same mark.
- Marks are one SVG on a 48-unit grid with a top light, an inner edge and a soft shade under the figure. Under 24px the glyph is drawn larger so it still reads. Use 16 to 24px in rows and chips, 32px in lists, 48px on store and catalog cards, 56 to 72px in detail headers.
- `agentDisc(slug, { size, trust })` is the one call site. `trust` adds a charge bar inside the tile. `agentColors(slug)` returns the mark's color pair for tinting a card (`.nx-agent-tinted`) or a detail header (`.nx-agent-hero`); `agentMarkDataURL(slug)` gives the canvas scene the same mark.

Small dots stay only where they mean status (live, ok, warn, a permission class) and are always paired with a word.

## Signature details

A short list of details that make Aurora recognisable. They live in the "Signature details" section of `components.css` and are used the same way everywhere, never one-off.

- **Orbit tick.** Every `.nx-section-label` opens with a 10px accent tick.
- **Page header.** `.nx-page-eyebrow` (and the Watch eyebrow) is the accent, led by a 12px ONEXUS orbit mark. The title shades from `--nx-fg-1` into the accent. A mood rule, accent fading to a line, closes the header.
- **Lit primary.** `.nx-btn-primary` is a vertical accent gradient with a top light and an accent glow. Still one per surface.
- **Composer.** A gradient edge in the mood (accent, tint, line) and a soft accent shadow; on focus the edge lights fully. It is the most polished surface in the app, with the permission card.
- **Permission card.** The class color sets a 3px edge, a faint diagonal hatch and a wash fading left to right; the eyebrow leads with a shield.
- **Hex core.** Empty-state icons sit on the same hex as a built-in agent, filled with the accent. The welcome mark sits inside two orbit rings, the outer one dashed and turning once a minute.
- **Kernel stage.** The Watch scene and the rail's live scene sit on a pool of field 1 behind the core; Watch adds faint concentric orbit rings.
- **Motion with a job.** A view rises in 6px when the route changes (not on re-render). The mood pill rings once in the new accent when the mood changes. The ONEXUS mark's node travels its orbit every 14 seconds. Marks lift a touch when their row or card is hovered. Loading shimmer is accent-tinted. All of it stops under `prefers-reduced-motion`.

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
| Avatar and agent mark | `.nx-avatar`; agent marks come from `agentDisc()` (see Agent marks); `.nx-agent-tinted`, `.nx-agent-hero` | trust bar |
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
