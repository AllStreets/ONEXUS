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
