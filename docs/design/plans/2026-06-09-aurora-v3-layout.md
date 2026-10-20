# Aurora v3 — layout & visual rebuild

**Goal:** Replace the patched-as-we-go shell with a unified layout system that
holds together at every viewport size and modernizes the visual surface.
Preserve every feature already built. No regressions.

## Why this rebuild

The current shell uses `position: fixed; inset: 16px` with hardcoded
column widths in pixels. That couples the layout to viewport math that
breaks under browser zoom, retina scaling, and small windows:

- Sub-regions overflow horizontally → "parts off the screen".
- Scroll chains are inconsistent — some content scrolls, some doesn't.
- Cockpit content density doesn't adapt to actual rendered width.
- Mood styling reaches only some elements.

The fix is to stop fighting the viewport. Use CSS Grid for the shell,
flexbox + container queries for every region, dvh units for height, and
let each region manage its own scroll.

## Layout system

### Root

```
html, body, #app-root {
  height: 100dvh;
  overflow: hidden;
  margin: 0;
}
```

`dvh` (dynamic viewport height) handles mobile browser chrome and large
zooms cleanly. `overflow: hidden` prevents body-level scroll — every
overflow lives in a child region.

### Shell

```
#app-root {
  display: grid;
  grid-template-rows: var(--chrome-h, 52px) 1fr;
}

.nx-chrome { /* row 1, fixed height */ }

.nx-body {
  /* row 2 */
  display: grid;
  grid-template-columns: var(--side-w) minmax(0, 1fr) var(--cockpit-w);
  min-height: 0;       /* let row shrink */
  overflow: hidden;    /* contain children */
}
```

`minmax(0, 1fr)` is critical — without `min` of 0 the main column can't
shrink and overflows to the right.

### Region discipline

Every region (`nx-sidebar`, `nx-main`, `nx-cockpit-rail`) uses the same
pattern:

```
.region {
  display: flex;
  flex-direction: column;
  min-width: 0;        /* allow shrink */
  min-height: 0;       /* allow shrink */
  overflow: hidden;    /* contain self */
}

.region-inner {
  flex: 1;
  min-height: 0;
  overflow-y: auto;    /* THE scroll surface */
  padding: var(--region-pad);
}
```

The composer (only in the conversation view) sits as a sibling of
`region-inner`, with `flex: none`, so it stays pinned at the bottom of
its region.

### Responsive width — driven by media queries on root

```
:root {
  --side-w: 264px;
  --cockpit-w: 348px;
  --chrome-h: 52px;
  --region-pad: 28px;
}
@media (max-width: 1440px) {
  :root { --side-w: 240px; --cockpit-w: 308px; --region-pad: 24px; }
}
@media (max-width: 1200px) {
  :root { --side-w: 220px; --cockpit-w: 280px; --region-pad: 20px; }
}
@media (max-width: 980px) {
  :root { --cockpit-w: 0px; }       /* cockpit fully retracted */
  .nx-cockpit-rail { display: none; }
  body.nx-cockpit-shown { /* manual reveal */ }
}
```

Plus a manual cockpit hide via the chrome toggle (`body.nx-cockpit-hidden`)
that overrides at any width.

### Density via container queries

Each region declares itself a query container:

```
.nx-cockpit-rail { container-type: inline-size; container-name: cockpit; }

@container cockpit (max-width: 320px) {
  /* Tighter spacing, smaller fonts, single-column breakdown */
}
@container cockpit (min-width: 360px) {
  /* Full breakdown layout, larger sparkline */
}
```

This means content adapts to its OWN width, not the viewport's — so even
if the layout system gives the cockpit a weird size, the content always
fits.

## Visual modernization

Modern surfaces have:

1. **Depth via layered shadows** — not borders. Border-only cards read as
   flat / cheap. Layered shadows + a 1px hairline read as a real surface.

   ```
   .nx-card {
     background: linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015));
     border: 1px solid rgba(232, 222, 252, 0.08);
     border-radius: 12px;
     box-shadow:
       0 1px 0 rgba(255,255,255,0.04) inset,
       0 8px 20px -10px rgba(0,0,0,0.45);
   }
   ```

2. **Glass on chrome** — `backdrop-filter: blur(20px) saturate(180%)` on
   the chrome bar + sidebar so the ambient atmosphere shows through.

3. **Bigger, more confident display type** — workspace titles at 32px
   instead of 28px; tighter `letter-spacing: -0.02em` for headlines.

4. **Color science** — instead of pure black backgrounds, lean into deep
   purple-tinted darks (`#0a0712`, `#0d0916`). All mood gradients soften
   color stops (transparent at 65–75% instead of 60%) so the bleed feels
   atmospheric, not patchy.

5. **Mood reaches every accent** — `--nx-mood-primary` drives the
   workspace pill highlight, composer focus ring, attach button hover,
   launch button, capability sheet edge, search-hit URL color, workshop
   run button, and the chrome traffic light hover glow.

6. **Motion** — every transition uses a custom spring curve
   `cubic-bezier(0.32, 0.72, 0, 1)` for that "snappy but soft" feel.

## Scroll guarantees

| Region | Scroll surface | Always pinned |
|--------|---------------|---------------|
| Chrome bar | none (always 52px) | — |
| Sidebar | `.nx-sidebar-inner` | user footer below |
| Main canvas (conversation) | `.nx-main-inner` | composer below |
| Main canvas (other views) | `.nx-main-inner` | — |
| Cockpit rail | `.nx-cockpit-inner` | footer (kernel.network.io = ∅) below |

The composer sits outside `nx-main-inner` so it never scrolls away. The
workshop's textarea + output panel are both children of `nx-main-inner`
so they scroll together.

## Feature preservation

Everything below must still work after the rebuild — listed for sanity:

**Shell**: chrome traffic lights (close/focus/fullscreen), cockpit toggle, mood pill, live clock.
**Sidebar**: search, workspaces list with active state + tone dots + delete trash, "+ new workspace" with ⌘N hint, recent agents, links to workshop / search / catalog / settings, user footer.
**Main · conversation**: breadcrumb home, "+ new thread" button, agent message (disc, name, time, body, diff cards, "remembered" pill, trust feedback buttons), user message bubble with attached file chips, inline permission prompt, typing indicator, composer with attach button + drag-drop overlay + attached file strip + ⌘⏎ kbd.
**Main · workspaces grid**: tone-colored tiles, click to switch, "+ new" tile.
**Main · catalog**: search + category + runnable-only filters, agent cards with launch buttons.
**Main · workshop**: language selector, code editor, run button, output panel.
**Main · search**: query input, hit cards.
**Main · settings**: tab nav + panels.
**Cockpit**: trust card (sparkline + delta + class chips), recent permissions log, ambient mood mesh card, mood reasons, agent disc row → capability sheet on click, footer (v1.0 · 1075 tests · kernel.network.io = ∅).
**Overlays**: ⌘K switcher, ⌘N new-workspace form, ⌘\` expanded cockpit, install review, first-use permission prompt, first-open tour.
**Keyboard**: ⌘K ⌘N ⌘\` ⌘, ⌘E ⌘/ ⌘⏎ Esc.
**Server**: cache-busting versioned static URLs, no-store headers.

## Execution sequence

1. Write this plan (done).
2. Replace `index.html` shell with the new grid scaffold + 3 inner-wrappers.
3. Rewrite `app.css` from the top down: root vars, shell grid, regions, components, overlays.
4. Update `app.js` renderers to emit the new wrappers.
5. Run Playwright at 1280 / 1440 / 1680 / 1920 viewports.
6. Run pytest to confirm no backend regressions.
7. Push.

## Self-review checklist

- [ ] At every viewport ≥ 980px, no horizontal overflow anywhere.
- [ ] At every viewport, mouse wheel scrolls the region under the cursor.
- [ ] Composer stays pinned regardless of thread length.
- [ ] Cockpit content never overflows the rail.
- [ ] Mood class change visibly shifts the whole shell within 1.5s.
- [ ] All 12 features from the prior verification round still pass.
