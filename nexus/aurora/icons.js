/* ONEXUS Aurora: icon library
 * Every glyph is hand-drawn SVG. No emoji. UI icons follow the Lucide line
 * style (24px grid, 1.75 stroke, round caps) so they read as one family.
 * Agent glyphs are bespoke and sit inside an identity tile.
 */

/* The ONEXUS mark: an orbit with a core and one node on the ring. It takes
 * its color from CSS (currentColor), so it follows the mood accent. */
export const KERNEL_MARK = (size = 24) => `
<svg width="${size}" height="${size}" viewBox="0 0 24 24" class="nx-kernel-mark" fill="none" aria-hidden="true">
  <circle cx="12" cy="12" r="8.25" stroke="currentColor" stroke-width="1.75" opacity="0.9"/>
  <circle cx="12" cy="12" r="3" fill="currentColor"/>
  <circle cx="17.83" cy="6.17" r="1.9" fill="currentColor" stroke="var(--nx-surface-canvas, #0b0c0f)" stroke-width="1.4"/>
</svg>`;

/* Identity tile: a rounded square tinted with the agent's own color, the
 * glyph centered, and an optional trust ring drawn as an arc beneath it. */
export function identityDisc({ size = 44, gradient = ["#9aa8ff", "#4d5bcf"], trust = null, glyph = "" }) {
  const r = Math.round(size * 0.28);
  const ring = trust == null ? "" : `
    <svg class="nx-id-ring" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" aria-hidden="true">
      <rect x="1" y="1" width="${size - 2}" height="${size - 2}" rx="${r}" pathLength="100"
            stroke="rgba(255,255,255,0.10)" stroke-width="1.5" fill="none"/>
      <rect x="1" y="1" width="${size - 2}" height="${size - 2}" rx="${r}" pathLength="100"
            stroke="${gradient[0]}" stroke-width="1.5" fill="none" stroke-linecap="round"
            stroke-dasharray="${Math.max(0, Math.min(1, trust)) * 100} 100"/>
    </svg>`;
  const inset = trust == null ? 0 : 3;
  return `
    <div class="nx-id-disc" style="width:${size}px;height:${size}px;--id-a:${gradient[0]};--id-b:${gradient[1]};--id-r:${r}px;--id-inset:${inset}px">
      ${ring}
      <div class="nx-id-tile">${glyph}</div>
    </div>`;
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

  /* sigil — concentric radar arcs with sweep contact */
  sigil: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round">
      <path d="M4 13a7 7 0 0 1 14 0"/>
      <path d="M7 13a4 4 0 0 1 8 0" opacity="0.7"/>
      <path d="M11 13v5" opacity="0.5"/>
      <circle cx="11" cy="13" r="1.1" fill="#fff" stroke="none"/>
      <circle cx="16.4" cy="7.4" r="0.9" fill="#fff" stroke="none" opacity="0.85"/>
    </svg>`,

  /* atlas — meridian globe (world model) */
  atlas: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4">
      <circle cx="11" cy="11" r="7"/>
      <ellipse cx="11" cy="11" rx="3" ry="7" opacity="0.7"/>
      <path d="M4 11h14" opacity="0.7"/>
    </svg>`,

  /* prism — refracting triangular prism splitting a beam (cross-domain synthesis) */
  prism: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round">
      <path d="M11 4 4 16h14L11 4Z"/>
      <path d="M2 11h4" opacity="0.8"/>
      <path d="M14 11h6" opacity="0.85"/>
      <path d="M14 13.5h6" opacity="0.55"/>
      <path d="M14 8.5h6" opacity="0.55"/>
    </svg>`,

  /* chronos — clock face with a forking branch (counterfactual timeline) */
  chronos: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="9" cy="9" r="6"/>
      <path d="M9 5.5V9l2.4 1.6"/>
      <path d="M14 13l3 3" opacity="0.85"/>
      <path d="M17 16l3-1.5M17 16l-1.5 3" opacity="0.7"/>
    </svg>`,

  /* serendipity — scattered constellation + one off-axis bright node (anti-optimization) */
  serendipity: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round">
      <circle cx="6" cy="14" r="0.9" fill="#fff" stroke="none" opacity="0.5"/>
      <circle cx="11" cy="9" r="0.9" fill="#fff" stroke="none" opacity="0.5"/>
      <circle cx="16" cy="13" r="0.9" fill="#fff" stroke="none" opacity="0.5"/>
      <path d="M6 14 11 9 16 13" opacity="0.45"/>
      <path d="M15 4l0.9 2 2 0.9-2 0.9L15 10l-0.9-2-2-0.9 2-0.9z" fill="#fff" stroke="none"/>
    </svg>`,

  /* herald — pennant on a staff (messenger / negotiation) */
  herald: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">
      <path d="M6 3v16"/>
      <path d="M6 4h10l-2.4 3L16 10H6z"/>
      <circle cx="6" cy="3" r="0.9" fill="#fff" stroke="none"/>
    </svg>`,

  /* federation — two linked nodes (peer-to-peer sync) */
  federation: (s = 20) => `
    <svg width="${s}" height="${s}" viewBox="0 0 22 22" fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round">
      <circle cx="6" cy="8" r="2.4"/>
      <circle cx="16" cy="14" r="2.4"/>
      <path d="M8 9.6 14 12.4" opacity="0.7"/>
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

/* helper: build an agent identity card */
export function agentDisc(slug, { trust = null, size = 44 } = {}) {
  const gradient = GRADIENTS[slug] || ["#aaa", "#666"];
  const glyph = (GLYPHS[slug] || GLYPHS.agents)(Math.round(size * 0.5));
  return identityDisc({ size, gradient, trust, glyph });
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
