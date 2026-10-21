/* ONEXUS Aurora: icon library
 * Every glyph is hand-drawn SVG. No emoji. UI icons follow the Lucide line
 * style (24px grid, 1.75 stroke, round caps) so they read as one family.
 * Agents are drawn as marks: see "Agent marks" below.
 */

/* The ONEXUS mark: an orbit with a core and one node on the ring. It takes
 * its color from CSS (currentColor), so it follows the mood accent. */
export const KERNEL_MARK = (size = 24) => `
<svg width="${size}" height="${size}" viewBox="0 0 24 24" class="nx-kernel-mark" fill="none" aria-hidden="true">
  <circle cx="12" cy="12" r="8.25" stroke="currentColor" stroke-width="1.75" opacity="0.9"/>
  <circle cx="12" cy="12" r="3" fill="currentColor"/>
  <circle cx="17.83" cy="6.17" r="1.9" fill="currentColor" stroke="var(--nx-surface-canvas, #0b0c0f)" stroke-width="1.4"/>
</svg>`;

/* ── Agent marks ─────────────────────────────────────────────────────────
 * Every agent has a mark: a faceted tile in its own two-color gradient,
 * with a top light, a fine inner edge and a figure on top.
 *   - Built-in agents sit on the hex "core" tile with a hand-drawn glyph.
 *   - Catalog agents get a mark generated from their slug: a tile shape,
 *     a color pair, a background pattern and a monogram, all chosen by a
 *     hash, so the same agent always looks the same.
 * Marks are one crisp SVG on a 48-unit grid and are legible from 16px up.
 */

// Rounded polygon path from points [[x, y], ...] with corner radius r.
function roundedPoly(pts, r) {
  const n = pts.length;
  let d = "";
  for (let i = 0; i < n; i++) {
    const p = pts[i], prev = pts[(i - 1 + n) % n], next = pts[(i + 1) % n];
    const v1 = [prev[0] - p[0], prev[1] - p[1]], v2 = [next[0] - p[0], next[1] - p[1]];
    const l1 = Math.hypot(...v1), l2 = Math.hypot(...v2);
    const rr = Math.min(r, l1 / 2.2, l2 / 2.2);
    const a = [p[0] + (v1[0] / l1) * rr, p[1] + (v1[1] / l1) * rr];
    const b = [p[0] + (v2[0] / l2) * rr, p[1] + (v2[1] / l2) * rr];
    d += `${i === 0 ? "M" : "L"}${a[0].toFixed(2)} ${a[1].toFixed(2)}Q${p[0]} ${p[1]} ${b[0].toFixed(2)} ${b[1].toFixed(2)}`;
  }
  return d + "Z";
}

const MARK_SHAPES = {
  // built-in agents: a pointy-top hexagon
  core: roundedPoly([[24, 2], [43, 13], [43, 35], [24, 46], [5, 35], [5, 13]], 5.5),
  squircle: "M24 2.5C38.5 2.5 45.5 9.5 45.5 24S38.5 45.5 24 45.5 2.5 38.5 2.5 24 9.5 2.5 24 2.5Z",
  chamfer: roundedPoly([[14, 3], [45, 3], [45, 34], [34, 45], [3, 45], [3, 14]], 4),
  shield: roundedPoly([[4, 4], [44, 4], [44, 28], [24, 46], [4, 28]], 5),
  octagon: roundedPoly([[15, 3], [33, 3], [45, 15], [45, 33], [33, 45], [15, 45], [3, 33], [3, 15]], 3.5),
  tab: roundedPoly([[3, 3], [33, 3], [45, 15], [45, 45], [3, 45]], 6),
  diamond: roundedPoly([[24, 1.5], [46.5, 24], [24, 46.5], [1.5, 24]], 7),
};
const CATALOG_SHAPES = ["squircle", "chamfer", "shield", "octagon", "tab", "diamond"];

// Curated color pairs, light then deep. Some are one hue, some cross two.
const MARK_PALETTE = [
  ["#5eead4", "#0f5257"], ["#7dd3fc", "#123a6b"], ["#a5b4fc", "#2b2f7a"],
  ["#c4b5fd", "#3d2470"], ["#f0abfc", "#5b1d5f"], ["#fda4af", "#6b1d33"],
  ["#fdba74", "#6e2d12"], ["#fcd34d", "#6b4a0c"], ["#bef264", "#335214"],
  ["#86efac", "#14532d"], ["#67e8f9", "#164e63"], ["#f9a8d4", "#6d1a46"],
  ["#5eead4", "#3b1d8f"], ["#fdba74", "#831843"], ["#a3e635", "#0e4f5c"],
  ["#93c5fd", "#7c1d6f"], ["#fde68a", "#7c2d12"], ["#d4d4d8", "#33343c"],
];

// Background patterns, clipped to the tile, drawn in white at low opacity.
const MARK_PATTERNS = {
  rings:    `<path d="M48 48m-40 0a40 40 0 0 1 40-40M48 48m-30 0a30 30 0 0 1 30-30M48 48m-20 0a20 20 0 0 1 20-20" fill="none" stroke="#fff" stroke-width="2"/>`,
  stripes:  `<path d="M-6 30 30-6M-6 44 44-6M6 54 54 6M20 54 54 20" stroke="#fff" stroke-width="3"/>`,
  grid:     `<path d="M12 0v48M24 0v48M36 0v48M0 12h48M0 24h48M0 36h48" stroke="#fff" stroke-width="1"/>`,
  chevrons: `<path d="M0 40 12 30 24 40 36 30 48 40M0 50 12 40 24 50 36 40 48 50" fill="none" stroke="#fff" stroke-width="2.4"/>`,
  facets:   `<path d="M0 0h48L0 48Z" fill="#fff" opacity="0.5"/><path d="M48 0v48L24 24Z" fill="#fff" opacity="0.25"/>`,
  waves:    `<path d="M0 34c8-6 16-6 24 0s16 6 24 0M0 42c8-6 16-6 24 0s16 6 24 0" fill="none" stroke="#fff" stroke-width="2.2"/>`,
  orbit:    `<ellipse cx="24" cy="24" rx="30" ry="11" fill="none" stroke="#fff" stroke-width="1.8" transform="rotate(-28 24 24)"/><ellipse cx="24" cy="24" rx="30" ry="11" fill="none" stroke="#fff" stroke-width="1.2" transform="rotate(32 24 24)"/>`,
  bars:     `<path d="M10 48V30M18 48V20M26 48V34M34 48V14M42 48V26" stroke="#fff" stroke-width="3.2"/>`,
};
const PATTERN_KEYS = Object.keys(MARK_PATTERNS);

function hashSlug(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return h >>> 0;
}

const MONO_SKIP = new Set(["mcp", "ai", "the", "server", "agent", "agents", "app", "js", "py", "sdk", "api", "cli"]);
function monogram(slug, two) {
  const words = String(slug || "?").replace(/([a-z])([A-Z])/g, "$1 $2").split(/[\s_.\-/]+/).filter(Boolean);
  const kept = words.filter(w => !MONO_SKIP.has(w.toLowerCase()));
  const use = kept.length ? kept : words;
  if (!use.length) return "?";
  if (two && use.length > 1) return (use[0][0] + use[1][0]).toUpperCase();
  return use[0][0].toUpperCase();
}

/* The look of a catalog agent's mark, derived from its slug alone. */
export function markSpec(slug) {
  const h = hashSlug(String(slug || ""));
  return {
    shape: CATALOG_SHAPES[h % CATALOG_SHAPES.length],
    colors: MARK_PALETTE[(h >>> 3) % MARK_PALETTE.length],
    pattern: PATTERN_KEYS[(h >>> 8) % PATTERN_KEYS.length],
    flip: ((h >>> 13) & 1) === 1,
  };
}

let _markSeq = 0;
/* Build one mark as an SVG string. `figure` is inner SVG markup drawn on the
 * 48-unit grid (a glyph or a monogram). `xmlns` makes it usable as an image. */
function markSVG({ size, shape, colors, pattern = null, flip = false, figure = "", trust = null, xmlns = false }) {
  const id = `nxm${++_markSeq}`;
  const path = MARK_SHAPES[shape] || MARK_SHAPES.squircle;
  const [a, b] = colors;
  const pat = pattern ? `<g clip-path="url(#${id}c)" opacity="0.16"${flip ? ' transform="matrix(-1 0 0 1 48 0)"' : ""}>${MARK_PATTERNS[pattern]}</g>` : "";
  const t = trust == null ? "" : (() => {
    const v = Math.max(0, Math.min(1, trust));
    return `<rect x="13" y="38.5" width="22" height="2.6" rx="1.3" fill="#000" opacity="0.35"/>
      <rect x="13" y="38.5" width="${(22 * v).toFixed(1)}" height="2.6" rx="1.3" fill="#fff" opacity="0.92"/>`;
  })();
  return `<svg ${xmlns ? 'xmlns="http://www.w3.org/2000/svg" ' : ""}class="nx-mark-svg" width="${size}" height="${size}" viewBox="0 0 48 48" aria-hidden="true" focusable="false">
    <defs>
      <linearGradient id="${id}g" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/>
      </linearGradient>
      <linearGradient id="${id}h" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stop-color="#fff" stop-opacity="0.34"/><stop offset="0.5" stop-color="#fff" stop-opacity="0"/>
      </linearGradient>
      <radialGradient id="${id}s" cx="0.5" cy="0.55" r="0.5">
        <stop offset="0" stop-color="#000" stop-opacity="0.26"/><stop offset="1" stop-color="#000" stop-opacity="0"/>
      </radialGradient>
      <clipPath id="${id}c"><path d="${path}"/></clipPath>
    </defs>
    <path d="${path}" fill="url(#${id}g)"/>
    ${pat}
    <path d="${path}" fill="url(#${id}s)"/>
    <path d="${path}" fill="url(#${id}h)"/>
    <path d="${path}" fill="none" stroke="#fff" stroke-opacity="0.28" stroke-width="1.2"/>
    ${figure}
    ${t}
  </svg>`;
}

function monogramFigure(slug, size) {
  const two = size >= 28;
  const text = monogram(slug, two);
  const fs = text.length > 1 ? 17 : 21;
  return `<text x="24" y="24" dy="0.36em" text-anchor="middle" font-family="-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', system-ui, sans-serif" font-size="${fs}" font-weight="700" letter-spacing="-0.02em" fill="#fff" fill-opacity="0.96">${text}</text>`;
}

function glyphFigure(glyph, size = 48) {
  // place a 24-unit glyph in the centre of the 48 grid; small marks get a
  // larger glyph so it still reads at 16 to 24px
  const g = size <= 24 ? 28 : 22, o = (48 - g) / 2;
  return glyph.trim().replace(/^<svg width="[\d.]+" height="[\d.]+"/, `<svg x="${o}" y="${o}" width="${g}" height="${g}" overflow="visible"`);
}

/* The identity mark for any agent, wrapped for layout. Kept under its old
 * name so existing call sites work. `gradient` sets the color pair; `glyph`
 * is a built-in glyph's SVG; `slug` drives a generated mark when no glyph. */
export function identityDisc({ size = 44, gradient = null, trust = null, glyph = "", slug = "", shape = null } = {}) {
  let svg;
  if (glyph) {
    svg = markSVG({ size, shape: shape || "core", colors: gradient || ["#9aa8ff", "#4d5bcf"], figure: glyphFigure(glyph, size), trust });
  } else {
    const spec = markSpec(slug);
    svg = markSVG({ size, shape: shape || spec.shape, colors: gradient || spec.colors, pattern: spec.pattern, flip: spec.flip, figure: monogramFigure(slug, size), trust });
  }
  return `<span class="nx-id-disc nx-mark" style="width:${size}px;height:${size}px">${svg}</span>`;
}

/* Lucide-style line icons for the interface. Usage: icon("search", 16). */
const P = {
  search: '<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.35-4.35"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  "chevron-right": '<path d="m9 18 6-6-6-6"/>',
  "chevron-left": '<path d="m15 18-6-6 6-6"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  "chevron-up": '<path d="m18 15-6-6-6 6"/>',
  "arrow-right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  "arrow-left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
  "arrow-up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
  "arrow-up-right": '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
  "corner-down-left": '<path d="M20 4v7a4 4 0 0 1-4 4H4"/><path d="m9 10-5 5 5 5"/>',
  "external-link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
  settings: '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  sliders: '<path d="M20 7h-9"/><path d="M14 17H5"/><circle cx="17" cy="17" r="3"/><circle cx="7" cy="7" r="3"/>',
  folder: '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
  file: '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/>',
  "file-text": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M16 13H8"/><path d="M16 17H8"/><path d="M10 9H8"/>',
  code: '<path d="m16 18 6-6-6-6"/><path d="m8 6-6 6 6 6"/>',
  terminal: '<path d="m4 17 6-6-6-6"/><path d="M12 19h8"/>',
  play: '<path d="M6 4.5v15a.5.5 0 0 0 .76.43l12.5-7.5a.5.5 0 0 0 0-.86L6.76 4.07A.5.5 0 0 0 6 4.5Z"/>',
  pause: '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
  "skip-back": '<path d="M19 20 9 12l10-8v16Z"/><path d="M5 19V5"/>',
  "skip-forward": '<path d="m5 4 10 8-10 8V4Z"/><path d="M19 5v14"/>',
  history: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M12 7v5l4 2"/>',
  "rotate-ccw": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
  refresh: '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
  eye: '<path d="M2.06 12.35a1 1 0 0 1 0-.7 10.75 10.75 0 0 1 19.88 0 1 1 0 0 1 0 .7 10.75 10.75 0 0 1-19.88 0"/><circle cx="12" cy="12" r="3"/>',
  shield: '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
  "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  activity: '<path d="M22 12h-2.48a2 2 0 0 0-1.93 1.46l-2.35 8.36a.25.25 0 0 1-.48 0L9.24 2.18a.25.25 0 0 0-.48 0l-2.35 8.36A2 2 0 0 1 4.49 12H2"/>',
  database: '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/>',
  globe: '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
  "book-open": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
  sparkle: '<path d="M12 3.5 13.9 9l5.6 2-5.6 2L12 18.5 10.1 13l-5.6-2 5.6-2Z"/>',
  scan: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/>',
  maximize: '<path d="M15 3h6v6"/><path d="M9 21H3v-6"/><path d="m21 3-7 7"/><path d="m3 21 7-7"/>',
  "panel-right": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M15 3v18"/>',
  help: '<circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/>',
  paperclip: '<path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/>',
  "alert-triangle": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  "alert-circle": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
  info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
  lock: '<rect width="18" height="11" x="3" y="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  key: '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/><path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>',
  grid: '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
  list: '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
  users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
  branch: '<path d="M6 3v12"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/>',
  workflow: '<rect width="6" height="6" x="3" y="15" rx="1"/><rect width="6" height="6" x="15" y="15" rx="1"/><rect width="6" height="6" x="9" y="3" rx="1"/><path d="M6 15v-2a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v2"/><path d="M12 12V9"/>',
  share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="m8.59 13.51 6.83 3.98"/><path d="m15.41 6.51-6.82 3.98"/>',
  radio: '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/>',
  download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  "thumbs-up": '<path d="M7 10v12"/><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"/>',
  "thumbs-down": '<path d="M17 14V2"/><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"/>',
  package: '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 8.7 5 8.7-5"/>',
  store: '<path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="M2 7h20"/><path d="M22 7v3a2 2 0 0 1-2 2 2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 16 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 12 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 8 12a2.7 2.7 0 0 1-1.59-.63.7.7 0 0 0-.82 0A2.7 2.7 0 0 1 4 12a2 2 0 0 1-2-2V7"/>',
  cpu: '<rect width="16" height="16" x="4" y="4" rx="2"/><rect width="6" height="6" x="9" y="9" rx="1"/><path d="M15 2v2"/><path d="M15 20v2"/><path d="M2 15h2"/><path d="M2 9h2"/><path d="M20 15h2"/><path d="M20 9h2"/><path d="M9 2v2"/><path d="M9 20v2"/>',
  command: '<path d="M15 6v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3"/>',
  compass: '<circle cx="12" cy="12" r="10"/><path d="m16.24 7.76-2.12 6.36-6.36 2.12 2.12-6.36 6.36-2.12z"/>',
  contrast: '<circle cx="12" cy="12" r="10"/><path d="M12 18a6 6 0 0 0 0-12v12z"/>',
  star: '<path d="M11.53 2.3a.53.53 0 0 1 .95 0l2.31 4.68a2.12 2.12 0 0 0 1.6 1.16l5.16.76a.53.53 0 0 1 .3.9l-3.74 3.64a2.12 2.12 0 0 0-.61 1.88l.88 5.14a.53.53 0 0 1-.77.56l-4.62-2.43a2.12 2.12 0 0 0-1.97 0L6.4 21.01a.53.53 0 0 1-.77-.56l.88-5.14a2.12 2.12 0 0 0-.61-1.88L2.16 9.8a.53.53 0 0 1 .3-.91l5.16-.75a2.12 2.12 0 0 0 1.6-1.16z"/>',
  flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><path d="M4 22v-7"/>',
  repeat: '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
  wrench: '<path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/>',
  home: '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .71-1.53l7-6a2 2 0 0 1 2.58 0l7 6A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
  inbox: '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  layers: '<path d="m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z"/><path d="m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65"/><path d="m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
  hash: '<path d="M4 9h16"/><path d="M4 15h16"/><path d="M10 3 8 21"/><path d="M16 3l-2 18"/>',
  upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5"/><path d="M12 3v12"/>',
};

export function icon(name, size = 16, cls = "") {
  const body = P[name] || P.info;
  return `<svg class="nx-ico${cls ? " " + cls : ""}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${body}</svg>`;
}
export const ICON_NAMES = Object.keys(P);

/* — built-in agent glyphs — 24px grid, white line art, drawn to sit inside
 * an agent mark. Each one is its own idea; none is a circle with a dot. — */
export const GLYPHS = {
  /* council — two brackets weighing a bar: deliberation, balance */
  council: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 5H5.5v14H8"/>
      <path d="M16 5h2.5v14H16"/>
      <path d="M9.5 10h5M9.5 14h5"/>
    </svg>`,

  /* specter — a crosshair set in a diamond: red-team, stress test */
  specter: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3.5 20.5 12 12 20.5 3.5 12Z"/>
      <path d="M12 8.5v7M8.5 12h7"/>
    </svg>`,

  /* autonomic — an endless loop: routines that run themselves */
  autonomic: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M7.5 8.5C4.5 8.5 3 10.4 3 12s1.5 3.5 4.5 3.5c3.5 0 5.5-7 9-7 3 0 4.5 1.9 4.5 3.5s-1.5 3.5-4.5 3.5c-3.5 0-5.5-7-9-7Z"/>
    </svg>`,

  /* oracle — a lens with a diamond iris: the first, careful read */
  oracle: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M2.5 12C5 7.5 8.5 5.5 12 5.5S19 7.5 21.5 12C19 16.5 15.5 18.5 12 18.5S5 16.5 2.5 12Z"/>
      <path d="M12 9.2 14.8 12 12 14.8 9.2 12Z" fill="#fff" stroke="none"/>
    </svg>`,

  /* wraith — lines that shorten and fade: controlled forgetting */
  wraith: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.9" stroke-linecap="round">
      <path d="M4.5 6.5h15"/>
      <path d="M4.5 12h10" opacity="0.7"/>
      <path d="M4.5 17.5h5" opacity="0.4"/>
    </svg>`,

  /* legacy — a cut crystal: memory made durable */
  legacy: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M7 4h10l4 5-9 11L3 9Z"/>
      <path d="M3 9h18M9.5 4 8 9l4 11 4-11-1.5-5" opacity="0.65"/>
    </svg>`,

  /* consciousness — one square turning inside another: inner state */
  consciousness: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="3.5"/>
      <path d="M12 7.2 16.8 12 12 16.8 7.2 12Z" opacity="0.8"/>
    </svg>`,

  /* sentry — a pulse inside a shield: watching over long tasks */
  sentry: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3 19 6v5.5c0 4.4-3 7.7-7 9.5-4-1.8-7-5.1-7-9.5V6Z"/>
      <path d="M7.5 12.5h2.2l1.3-2.5 2 4.5 1.3-2h2.2"/>
    </svg>`,

  /* echo — two chevrons mirrored across an axis: restating you */
  echo: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M9.5 6.5 4 12l5.5 5.5"/>
      <path d="M14.5 6.5 20 12l-5.5 5.5"/>
      <path d="M12 4.5v15" stroke-dasharray="1.6 2.6" opacity="0.7"/>
    </svg>`,

  /* agents (dispatcher) — three docked tiles and an open slot */
  agents: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <rect x="4" y="4" width="6.5" height="6.5" rx="1.6"/>
      <rect x="13.5" y="4" width="6.5" height="6.5" rx="1.6"/>
      <rect x="4" y="13.5" width="6.5" height="6.5" rx="1.6"/>
      <path d="M16.75 14v5.5M14 16.75h5.5"/>
    </svg>`,

  /* sigil — a radar quadrant with its sweep and one contact */
  sigil: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M4 20A16 16 0 0 1 20 4"/>
      <path d="M4 20a9.5 9.5 0 0 1 9.5-9.5" opacity="0.7"/>
      <path d="M4 20 15 7"/>
      <path d="M17 9.2l1.6 1.6-1.6 1.6-1.6-1.6Z" fill="#fff" stroke="none"/>
    </svg>`,

  /* atlas — an isometric cube: a world model with structure */
  atlas: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 3 20 7.5v9L12 21l-8-4.5v-9Z"/>
      <path d="M4 7.5 12 12l8-4.5M12 12v9" opacity="0.75"/>
    </svg>`,

  /* prism — a prism splitting one beam into three: synthesis */
  prism: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M12 4 19 18H5Z"/>
      <path d="M2 12.5h6.5" opacity="0.85"/>
      <path d="M15.5 11 22 8.5M15.5 12.5H22M15.5 14l6.5 2.5" opacity="0.7"/>
    </svg>`,

  /* chronos — a timeline that forks: the counterfactual branch */
  chronos: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12h7"/>
      <path d="M10 12l4.5-5.5H21M10 12l4.5 5.5H21" />
      <path d="M5.5 10v4" opacity="0.6"/>
    </svg>`,

  /* serendipity — a large spark and a small one, off axis */
  serendipity: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.6" stroke-linejoin="round">
      <path d="M10 3.5l1.7 4.8 4.8 1.7-4.8 1.7L10 16.5l-1.7-4.8L3.5 10l4.8-1.7Z"/>
      <path d="M17.5 14.5l.9 2.6 2.6.9-2.6.9-.9 2.6-.9-2.6-2.6-.9 2.6-.9Z" fill="#fff" stroke="none"/>
    </svg>`,

  /* herald — a pennant on a staff: the messenger */
  herald: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <path d="M6 21V3.5"/>
      <path d="M6 4.5h12l-3.2 4.2L18 13H6"/>
    </svg>`,

  /* federation — two hex nodes, linked: peer-to-peer sync */
  federation: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
      <path d="M8 3.5l4 2.3v4.6L8 12.7 4 10.4V5.8Z"/>
      <path d="M16 11.3l4 2.3v4.6l-4 2.3-4-2.3v-4.6Z"/>
      <path d="M11 11l2 1.5" opacity="0.8"/>
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
  sigil:         ["#ffb4a8", "#a82a1c"],
  atlas:         ["#7ee8b2", "#1c6a4a"],
  prism:         ["#d8b4ff", "#5a2a9c"],
  chronos:       ["#b8c4ff", "#3a4a9c"],
  serendipity:   ["#ffc4f0", "#7a2a6a"],
  herald:        ["#ffd9a8", "#9c6a2a"],
  federation:    ["#a8d8ff", "#2a5a9c"],
};

/* Shorthand for the most common interface icons (kept for older call sites). */
export const UI = {
  plus:    (s = 14) => icon("plus", s),
  close:   (s = 14) => icon("x", s),
  check:   (s = 14) => icon("check", s),
  chevron: (s = 14) => icon("chevron-right", s),
  search:  (s = 14) => icon("search", s),
  command: (s = 14) => icon("command", s),
};

/* The mark for an agent by slug: built-ins get their glyph on the core
 * tile, everything else a generated mark. */
export function agentDisc(slug, { trust = null, size = 44 } = {}) {
  if (GLYPHS[slug]) {
    return identityDisc({ size, gradient: GRADIENTS[slug] || ["#9aa8ff", "#4d5bcf"], trust, glyph: GLYPHS[slug](22) });
  }
  return identityDisc({ size, trust, slug });
}

/* An agent's color pair, light then deep, for tinting the surfaces around it. */
export function agentColors(slug) {
  return GLYPHS[slug] ? (GRADIENTS[slug] || ["#9aa8ff", "#4d5bcf"]) : markSpec(slug).colors;
}

/* A standalone mark as a data URL, for canvas drawing (the kernel scene). */
export function agentMarkDataURL(slug, size = 64) {
  const isBuiltin = !!GLYPHS[slug];
  const svg = isBuiltin
    ? markSVG({ size, shape: "core", colors: GRADIENTS[slug] || ["#9aa8ff", "#4d5bcf"], figure: glyphFigure(GLYPHS[slug](22), size), xmlns: true })
    : (() => { const s = markSpec(slug); return markSVG({ size, shape: s.shape, colors: s.colors, pattern: s.pattern, flip: s.flip, figure: monogramFigure(slug, size), xmlns: true }); })();
  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

/* Capability sheet for the 10 built-in agents. Each entry lists what the
 * agent does, the tools it declares, the permission classes it touches,
 * and the trust floor it requires. Surfaces on the catalog + agent
 * disc hover. */
export const BUILTIN_CAPABILITIES = {
  council: {
    tagline: "3-round deliberation across cognitive modules",
    description: "Routes the question to a panel of internal agents, lets each propose an answer, scores by confidence + dissent, returns a synthesised recommendation.",
    intents: ["deliberate", "decide", "synthesise"],
    tools: [
      { name: "engram.semantic.search", class: "Routine" },
      { name: "modules.invoke",         class: "Notable" },
    ],
    permission_classes: ["Routine", "Notable"],
    trust_floor: 0.25,
    network: false,
  },
  oracle: {
    tagline: "First-read analysis across whatever's in the workspace",
    description: "Reads workspace roots, grep + AST + semantic search, and returns a 1-page summary with citations.",
    intents: ["read", "summarise", "answer"],
    tools: [
      { name: "fs.read",                class: "Routine" },
      { name: "engram.semantic.search", class: "Routine" },
      { name: "engram.episodic.recall", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.25,
    network: false,
  },
  specter: {
    tagline: "Red-team: counter-arguments and dissenting views",
    description: "Argues against the user's premise. Surfaces hidden assumptions, failure modes, and edge cases. No flattery.",
    intents: ["challenge", "red-team", "stress-test"],
    tools: [
      { name: "engram.semantic.search", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.25,
    network: false,
  },
  wraith: {
    tagline: "Forgetting: controlled deletion + privacy hygiene",
    description: "Removes targeted entries from Engram + Chronicle. Useful after a sensitive task. Requires explicit confirmation.",
    intents: ["forget", "erase", "redact"],
    tools: [
      { name: "engram.episodic.erase",   class: "Sensitive" },
      { name: "chronicle.redact",        class: "Privileged" },
    ],
    permission_classes: ["Sensitive", "Privileged"],
    trust_floor: 0.50,
    network: false,
  },
  legacy: {
    tagline: "Crystallised memory: recall with citations",
    description: "Returns past decisions, prior threads, and persistent context with timestamps and source.",
    intents: ["recall", "remember", "cite"],
    tools: [
      { name: "engram.episodic.recall", class: "Routine" },
      { name: "engram.semantic.search", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.25,
    network: false,
  },
  echo: {
    tagline: "Mirror: what the user just said, restated",
    description: "Restates the active topic in the user's own words to surface contradictions and confirm understanding.",
    intents: ["reflect", "summarise-self", "confirm"],
    tools: [
      { name: "engram.working.read", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.25,
    network: false,
  },
  sentry: {
    tagline: "Heartbeat: watches for risks during long tasks",
    description: "Subscribes to Pulse + Chronicle, flags concerning patterns (trust drops, denied calls, runaway loops).",
    intents: ["watch", "alert", "halt-on-risk"],
    tools: [
      { name: "pulse.subscribe",     class: "Routine" },
      { name: "chronicle.subscribe", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.25,
    network: false,
  },
  autonomic: {
    tagline: "Autopilot: repetitive task chains, hands-off",
    description: "Strings tools together for chores you've already approved. Re-routes around failures, asks only on new capabilities.",
    intents: ["automate", "loop", "background"],
    tools: [
      { name: "modules.invoke",     class: "Notable" },
      { name: "fs.read",            class: "Routine" },
      { name: "fs.write",           class: "Sensitive" },
    ],
    permission_classes: ["Routine", "Notable", "Sensitive"],
    trust_floor: 0.75,
    network: false,
  },
  consciousness: {
    tagline: "Inner state: moods, regulation, salience",
    description: "Owns MoodEngine signals. Suggests transitions, flags overload, recommends pauses.",
    intents: ["regulate", "introspect", "transition-mood"],
    tools: [
      { name: "mood.observe",     class: "Routine" },
      { name: "mood.transition",  class: "Notable" },
    ],
    permission_classes: ["Routine", "Notable"],
    trust_floor: 0.50,
    network: false,
  },
  agents: {
    tagline: "Dispatcher: routes to installed third-party agents",
    description: "Looks at the installed catalog (onexus-agents) and routes to whichever runnable MCP agent best matches the intent.",
    intents: ["dispatch", "delegate", "match-tool"],
    tools: [
      { name: "agents.search",    class: "Routine" },
      { name: "agents.launch",    class: "Notable" },
      { name: "agents.call_tool", class: "Notable" },
    ],
    permission_classes: ["Routine", "Notable"],
    trust_floor: 0.50,
    network: false,
  },
  sigil: {
    tagline: "Threat radar: kernel anomaly detection with emergency bypass",
    description: "Watches Aegis trust deltas, gate verdicts, routing traffic, and the network log. Table-driven detections broadcast at emergency priority with a provenance hash; high-stakes hits auto-activate Specter (kill switch available).",
    intents: ["detect", "broadcast", "escalate"],
    tools: [
      { name: "pulse.subscribe",            class: "Routine" },
      { name: "chronicle.read.workspace",   class: "Routine" },
      { name: "pulse.broadcast.emergency",  class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.30,
    network: false,
  },
  atlas: {
    tagline: "World model: temporal facts with confidence decay",
    description: "Engram's semantic tier as a knowledge graph: facts decay deterministically until re-confirmed, contradictions coexist with competing confidences, and every answer cites its source.",
    intents: ["observe", "recall-world", "cite"],
    tools: [
      { name: "engram.read.workspace",  class: "Routine" },
      { name: "engram.write.workspace", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.30,
    network: false,
  },
  prism: {
    tagline: "Cross-domain synthesis: connections the per-workspace view can't see",
    description: "Reads across Engram partitions (Aegis-gated, always prompted) to surface recurring entities, cross-workspace contradictions, and patterns no single workspace can show, every finding citing its Engram/Atlas source.",
    intents: ["synthesise", "recurring", "contradict"],
    tools: [
      { name: "engram.read.workspace", class: "Routine" },
      { name: "engram.read.global",    class: "Sensitive" },
    ],
    permission_classes: ["Routine", "Sensitive"],
    trust_floor: 0.30,
    network: false,
  },
  chronos: {
    tagline: "Counterfactual reasoning: replay the decision DAG with one node flipped",
    description: "Reconstructs a deterministic decision graph from Chronicle's recorded history, then answers counterfactuals: flip one grant or route to denied and report which downstream actions depended on it. The kernel is never re-run.",
    intents: ["counterfactual", "timeline", "replay"],
    tools: [
      { name: "chronicle.read.workspace", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.30,
    network: false,
  },
  herald: {
    tagline: "Negotiation: structured agent-to-agent offers, counters, and commitments",
    description: "Runs an offer / counter / accept / reject / commit state machine where every step is a typed Pulse message. Each commit is gated by the initiator's capability class through Aegis, and the full transcript is recorded in Chronicle.",
    intents: ["negotiate", "propose", "commit"],
    tools: [
      { name: "chronicle.read.workspace", class: "Routine" },
      { name: "pulse.subscribe",          class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.30,
    network: false,
  },
  serendipity: {
    tagline: "Anti-optimization: the signal optimization would have hidden",
    description: "Reads Atlas facts (Aegis-gated), scores each by relevance and novelty, then deliberately surfaces high-novelty / low-relevance items on a budget. Every item cites its source; every discovery lands in Chronicle.",
    intents: ["discover", "surprise", "novelty"],
    tools: [
      { name: "engram.read.workspace", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.30,
    network: false,
  },
  federation: {
    tagline: "Peer sync: workspace-scoped, allowlist-only Atlas-fact federation",
    description: "Diffs Atlas facts between this instance and an allowlisted peer, gated per workspace through Aegis. The sync engine never touches the network; real peer HTTP flows only through the federation protocol's Aegis-routed client. Kill switch available.",
    intents: ["sync", "federate", "peer"],
    tools: [
      { name: "federation.sync.workspace",  class: "Routine" },
      { name: "network.outbound.localhost", class: "Routine" },
    ],
    permission_classes: ["Routine"],
    trust_floor: 0.80,
    network: true,
  },
};
