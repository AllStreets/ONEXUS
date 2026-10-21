/* ───────────────────────────────────────────────────────────────────────────
 * ONEXUS Aurora — application bootstrap and renderers.
 * Layout: persistent window shell with sidebar + main + cockpit rail.
 * Overlays for ⌘K switcher / ⌘N new workspace / ⌘0 cockpit / ⌘P settings.
 * ─────────────────────────────────────────────────────────────────────────── */

import { KERNEL_MARK, agentDisc, identityDisc, GRADIENTS, GLYPHS, UI, BUILTIN_CAPABILITIES, icon, agentColors } from "/aurora/static/icons.js";
import { renderMarkdown } from "/aurora/static/md.js";
import { KernelScene } from "/aurora/static/scene.js";

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  workspaces: [],
  active: null,
  workspaceAgentCounts: {}, // workspace_id -> distinct-agents-you've-chatted-with
  thread: new Map(),       // workspace_id -> array of message records
  attachments: new Map(),  // workspace_id -> array of pending file uploads
  codebases: new Map(),    // workspace_id -> registered codebase roots
  codebaseTrees: new Map(),// "<codebase_id>|<rel path>" -> cached tree entries
  codebaseOpen: new Set(), // expanded "<codebase_id>|<rel path>" keys
  codebasePanel: new Set(),// workspace_ids with the codebases panel open
  _codebaseErr: null,      // last codebase action error (shown in the panel)
  agents: [],              // catalog/runtime metadata
  runnableCount: 0,        // live count of runnable (MCP-adapter) catalog agents
  catalogTotal: 0,         // live count of ALL catalog agents (for search/picker labels)
  coreOnDuty: 0,           // live count of always-on cortex modules + routing ("agents on duty")
  recentAgents: [],
  // cache-bust query string appended to guide image src so users always
  // see the latest PNGs even if their browser cached the old ones
  _guideCacheBust: Date.now(),
  trust: {                 // last 60m aggregate
    delta: 0,
    direction: "rising",   // rising | falling | collapse
    history: [],           // [{t, score}]
    breakdown: { routine: 0, notable: 0, sensitive: 0, privileged: 0, denied: 0 },
  },
  perms: {
    pending: [],
    recent: [],            // last N decisions for cockpit log
  },
  kernelViz: {            // N1.3 live kernel visualization
    routes: [],           // last kernel.route payloads
    gates: [],            // last kernel.gate payloads
    detections: [],       // last sigil.detection payloads
    trustSeries: {},      // module -> rolling trust scores
  },
  scene: {                // N1 — the live Kernel Scene (constellation renderer)
    modules: [],          // [{name, colorA, colorB, trust, tier}] from /cortex/modules + /trust
    instances: {},        // surface-id -> KernelScene
    ledger: [],           // newest-first feed of human-legible kernel events
    counters: { routes: 0, gates: 0, denies: 0, memory: 0 },
  },
  mood: {
    mood: "calm_focus",
    tone: null,
    reason: "",
  },
  n2: {                    // N2 surfaces: morning brief, atlas graph, chronos
    brief: null,           // latest /api/dreamweaver/brief
    atlasGraph: null,      // latest /api/atlas/graph
    chronos: null,         // latest /api/chronos/timeline + counterfactual result
  },
  n3: {                    // N3 surfaces: herald negotiation + federation sync
    herald: [],            // recent herald.* Pulse events (offer/counter/.../commit)
    fedSync: { pushed: 0, merged: 0, last: null },  // federation sync counters
  },
  user: { initials: "you", name: "you" },
};

// ── Boot ──────────────────────────────────────────────────────────────────
async function boot() {
  document.getElementById("nx-kernel-mark").innerHTML = KERNEL_MARK(16);
  startClock();
  attachShellHandlers();
  attachKeybinds();
  installClipboardShortcuts();
  await loadAll();
  renderSidebar();
  renderCockpitRail();
  subscribeStreams();
  // Hydrate the kernel roster and light the always-on cockpit-rail mini scene.
  loadKernelScene().then(() => {
    const railCanvas = document.getElementById("nx-rail-scene-canvas");
    if (railCanvas) registerScene("rail", railCanvas, { compact: true });
  });
  // On a full load/reload, land on the workspace home rather than restoring a
  // tool surface (workshop, watch, memory, …). So ⌘R / refresh always brings you
  // back to your workspace, not whatever tool page you happened to be on.
  // Conversations and the guided tour still restore in place.
  const TOOL_ROUTE = /^#\/(workshop|cortex|watch|memory|store|catalog|settings|atlas|chronos|search|workspaces)\b/;
  const startHash = TOOL_ROUTE.test(location.hash) ? "" : location.hash;
  await route(startHash);
  maybeShowTour();
}

// ── First-open guided tour ────────────────────────────────────────────────
const TOUR_FLAG = "nx.tour.seen.v1";

function maybeShowTour() {
  if (location.hash.includes("tour")) { renderTour(0); return; }
  if (location.search.includes("tour")) { renderTour(0); return; }
  try {
    if (localStorage.getItem(TOUR_FLAG)) return;
  } catch { return; }
  renderTour(0);
}

function markTourSeen() {
  try { localStorage.setItem(TOUR_FLAG, String(Date.now())); } catch {}
}

const TOUR_SCENES = [
  {
    eyebrow: "ONEXUS",
    title: "An operating system for agents.",
    body: "ONEXUS runs agents the way iOS runs apps. This is a short tour: eight scenes, about a minute, skip whenever you like.",
    diagram: () => sceneWelcome(),
  },
  {
    eyebrow: "01 · Workspaces",
    title: "Each room is its own world.",
    body: "A workspace owns its agents, its memory, its grants, and its home tone. Switch between them with ⌘K. Each one stays private to itself.",
    diagram: () => sceneWorkspaces(),
  },
  {
    eyebrow: "02 · Conversation",
    title: "Talk to a room of agents at once.",
    body: "Send a message and Cortex routes it to whoever is best placed to answer. Mention an agent with @ to call it directly.",
    diagram: () => sceneConversation(),
  },
  {
    eyebrow: "03 · Safety model",
    title: "Every sensitive tool call asks first.",
    body: "Aegis classifies every capability as routine, notable, sensitive or privileged. Sensitive calls pause until you allow once, allow always in this workspace, or deny.",
    diagram: () => sceneSafety(),
  },
  {
    eyebrow: "04 · Trust",
    title: "Trust is earned, asymmetrically.",
    body: "Outcomes nudge an agent's trust score. Above 0.75 it earns auto-grants on notable calls. Below 0.50, every grant collapses at once.",
    diagram: () => sceneTrust(),
  },
  {
    eyebrow: "05 · Cockpit",
    title: "See what the kernel sees.",
    body: "The right rail keeps trust, permissions, mood, and the agent roster live in view. Press ⌘0 for the expanded six-panel cockpit.",
    diagram: () => sceneCockpit(),
  },
  {
    eyebrow: "06 · Agents",
    title: "Ten built-in. Seven thousand more in the catalog.",
    body: "Council deliberates, Specter red-teams, Oracle reads, Legacy remembers, Wraith forgets, Sentry watches. Install third-party agents like apps.",
    diagram: () => sceneAgents(),
  },
  {
    eyebrow: "Ready",
    title: "Your turn.",
    body: "⌘K switches workspace, ⌘N makes a new one, ⌘0 opens the cockpit and ⌘P opens settings. Hover a workspace to delete it.",
    diagram: () => sceneReady(),
  },
];

// Wrap a DOM-replacement function in the View Transitions API so the swap
// crossfades instead of flashing. The `update` callback is queued as a
// microtask by the browser, so handler wiring that depends on the new DOM
// must live in `after` — which runs as soon as the update completes,
// regardless of whether view-transitions are supported.
function withSmoothSwap(update, after) {
  if (typeof document.startViewTransition === "function") {
    const t = document.startViewTransition(update);
    t.updateCallbackDone.then(() => after && after()).catch(() => after && after());
  } else {
    update();
    if (after) after();
  }
}

function renderTour(index) {
  const root = document.getElementById("nx-overlay-root");
  const scene = TOUR_SCENES[index];
  const total = TOUR_SCENES.length;
  const dots = TOUR_SCENES.map((_, i) =>
    `<button type="button" class="nx-tour-dot ${i === index ? "active" : (i < index ? "done" : "")}" data-i="${i}" aria-label="Scene ${i + 1} of ${TOUR_SCENES.length}" ${i === index ? 'aria-current="step"' : ""}></button>`
  ).join("");
  const html = `
    <div class="nx-tour-overlay" id="nx-tour-overlay" role="dialog" aria-modal="true" aria-label="Tour">
      <button class="nx-tour-skip nx-btn nx-btn-sm nx-btn-ghost" type="button" id="nx-tour-skip" aria-label="Skip tour">Skip<span class="nx-kbd">esc</span></button>
      <div class="nx-tour-stage">
        <div class="nx-tour-diagram" id="nx-tour-diagram" aria-hidden="true">${scene.diagram()}</div>
        <div class="nx-tour-eyebrow">${escapeHtml(scene.eyebrow)}</div>
        <h2 class="nx-tour-title">${escapeHtml(scene.title)}</h2>
        <p class="nx-tour-body">${escapeHtml(scene.body)}</p>
      </div>
      <div class="nx-tour-nav">
        <button class="nx-tour-prev nx-btn nx-btn-icon" type="button" id="nx-tour-prev" ${index === 0 ? "disabled" : ""} aria-label="Previous scene">${icon("arrow-left", 16)}</button>
        <div class="nx-tour-dots">${dots}</div>
        <button class="nx-tour-next nx-btn nx-btn-primary" type="button" id="nx-tour-next" aria-label="${index === total - 1 ? "Begin" : "Next scene"}">
          ${index === total - 1 ? "Begin" : "Next"}${icon("arrow-right", 16)}
        </button>
      </div>
    </div>
  `;
  withSmoothSwap(
    () => { root.innerHTML = html; },
    () => {
      const close = () => {
        markTourSeen();
        closeOverlay();
      };
      document.getElementById("nx-tour-skip").addEventListener("click", close);
      document.getElementById("nx-tour-prev").addEventListener("click", () => {
        if (index > 0) renderTour(index - 1);
      });
      document.getElementById("nx-tour-next").addEventListener("click", () => {
        if (index === total - 1) close();
        else renderTour(index + 1);
      });
      root.querySelectorAll(".nx-tour-dot").forEach(dot => {
        dot.addEventListener("click", () => renderTour(Number(dot.dataset.i)));
      });
      // Keyboard: Esc closes, ←/→ navigate. The listener is bound to window so
      // it works regardless of focus, but we tear it down when the tour DOM
      // goes away — otherwise a later arrow-key press would re-render the
      // tour ON TOP of whatever overlay is now showing (e.g. the help guide).
      const overlayEl = document.getElementById("nx-tour-overlay");
      const onKey = (e) => {
        if (!document.body.contains(overlayEl)) {
          window.removeEventListener("keydown", onKey);
          return;
        }
        if (e.key === "Escape") { close(); }
        else if (e.key === "ArrowRight") { if (index < total - 1) renderTour(index + 1); }
        else if (e.key === "ArrowLeft")  { if (index > 0) renderTour(index - 1); }
      };
      window.addEventListener("keydown", onKey, { once: false });
      const observer = new MutationObserver(() => {
        if (!document.body.contains(overlayEl)) {
          window.removeEventListener("keydown", onKey);
          observer.disconnect();
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  );
}

// Tour scenes: flat line drawings in the shell's own language (graphite
// surfaces, hairlines, one accent). Motion is a slow boomerang
// (alternate-infinite) and stops entirely under prefers-reduced-motion.

const TOUR_MARK = (r = 30) => `
  <circle r="${r}" fill="none" stroke="var(--nx-accent)" stroke-width="${(r / 12).toFixed(1)}" opacity="0.9"/>
  <circle r="${(r * 0.36).toFixed(1)}" fill="var(--nx-accent)" class="nx-tour-anim-core"/>
  <circle cx="${(r * 0.707).toFixed(1)}" cy="${(-r * 0.707).toFixed(1)}" r="${(r * 0.23).toFixed(1)}" fill="var(--nx-accent)" stroke="var(--nx-surface-canvas)" stroke-width="${(r / 10).toFixed(1)}"/>`;

function sceneWelcome() {
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(200 130)">
        <circle r="112" fill="none" stroke="var(--nx-line-2)" stroke-width="1" class="nx-tour-anim-ring2"/>
        <circle r="84" fill="none" stroke="var(--nx-line-3)" stroke-width="1" stroke-dasharray="2 6" class="nx-tour-anim-ring1"/>
        <circle r="62" fill="color-mix(in srgb, var(--nx-accent) 6%, transparent)"/>
        ${TOUR_MARK(40)}
      </g>
    </svg>
  `;
}

function sceneWorkspaces() {
  // Four rooms, each a graphite card marked by its tone, around the mark.
  const cx = 200, cy = 130;
  const tones = [
    { x: cx - 78, y: cy - 44, c: "var(--nx-tone-indigo-a)", n: "Research" },
    { x: cx + 78, y: cy - 44, c: "var(--nx-tone-sage-a)", n: "Home lab" },
    { x: cx - 78, y: cy + 44, c: "var(--nx-tone-magenta-a)", n: "Writing" },
    { x: cx + 78, y: cy + 44, c: "var(--nx-tone-amber-a)", n: "Release" },
  ];
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
      <g class="nx-tour-anim-rooms" style="transform-origin:${cx}px ${cy}px">
        ${tones.map(t => `
          <g>
            <rect x="${t.x - 60}" y="${t.y - 30}" width="120" height="60" rx="8" fill="var(--nx-surface-1)" stroke="var(--nx-line-3)"/>
            <rect x="${t.x - 60}" y="${t.y - 30}" width="120" height="2" fill="${t.c}"/>
            <rect x="${t.x - 48}" y="${t.y - 18}" width="12" height="12" rx="3" fill="${t.c}"/>
            <text x="${t.x - 48}" y="${t.y + 16}" font-family="var(--nx-font-ui)" font-size="12" font-weight="600" fill="var(--nx-fg-1)">${t.n}</text>
          </g>
        `).join("")}
      </g>
      <g transform="translate(${cx} ${cy})">${TOUR_MARK(10)}</g>
    </svg>
  `;
}

function sceneConversation() {
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(150 70)" class="nx-tour-anim-bubble-b">
        <rect x="0" y="0" width="200" height="34" rx="12" fill="var(--nx-surface-2)" stroke="var(--nx-line-3)"/>
        <text x="16" y="22" font-family="var(--nx-font-ui)" font-size="12" fill="var(--nx-fg-1)">Summarize the kernel runtime</text>
      </g>
      <g transform="translate(50 132)">
        <rect x="0" y="0" width="30" height="30" rx="8" fill="#163645" stroke="rgba(168,232,255,0.35)" class="nx-tour-anim-disc"/>
        <path d="M7 15c2.5-4 5-6 8-6s5.5 2 8 6c-2.5 4-5 6-8 6s-5.5-2-8-6z" fill="none" stroke="#c9efff" stroke-width="1.4" transform="translate(0 0)"/>
        <text x="44" y="12" font-family="var(--nx-font-ui)" font-size="12" font-weight="600" fill="var(--nx-fg-1)">Oracle</text>
        <g class="nx-tour-anim-bubble-a">
          <rect x="44" y="22" width="240" height="8" rx="4" fill="var(--nx-gray-400)"/>
          <rect x="44" y="38" width="200" height="8" rx="4" fill="var(--nx-gray-400)"/>
          <rect x="44" y="54" width="140" height="8" rx="4" fill="var(--nx-gray-400)"/>
        </g>
      </g>
    </svg>
  `;
}

function sceneSafety() {
  // The real permission card: class and capability, who and where, and the
  // three decisions. The outer group does the static row offset; the inner
  // group runs the CSS slide-in, since a CSS transform would replace an SVG
  // transform on the same element.
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
      <g transform="translate(200 130)">
        <rect x="-170" y="-62" width="340" height="124" rx="10"
              fill="rgba(var(--nx-warn-rgb), 0.06)" stroke="rgba(var(--nx-warn-rgb), 0.45)" stroke-width="1"
              class="nx-tour-anim-card"/>
        <circle cx="-146" cy="-32" r="5" fill="var(--nx-warn)" class="nx-tour-anim-pulse-dot"/>
        <circle cx="-146" cy="-32" r="10" fill="none" stroke="rgba(var(--nx-warn-rgb), 0.6)" stroke-width="1" class="nx-tour-anim-ping"/>
        <text x="-128" y="-28" font-family="var(--nx-font-ui)" font-size="11" font-weight="700" letter-spacing="0.8" fill="var(--nx-warn)">SENSITIVE · FS.WRITE</text>
        <text x="-128" y="-6" font-family="var(--nx-font-ui)" font-size="12" fill="var(--nx-fg-1)">oracle on src/kernel/cortex.py</text>
        <g transform="translate(0 30)">
          <g class="nx-tour-anim-pills">
            <rect x="-146" y="-14" width="82" height="28" rx="6" fill="var(--nx-accent)"/>
            <text x="-105" y="4" font-family="var(--nx-font-ui)" font-size="11.5" font-weight="600" fill="var(--nx-fg-on-accent)" text-anchor="middle">Allow once</text>
            <rect x="-56" y="-14" width="122" height="28" rx="6" fill="var(--nx-surface-2)" stroke="var(--nx-line-3)"/>
            <text x="5" y="4" font-family="var(--nx-font-ui)" font-size="11.5" font-weight="500" fill="var(--nx-fg-1)" text-anchor="middle">Always in workspace</text>
            <rect x="74" y="-14" width="56" height="28" rx="6" fill="none" stroke="rgba(var(--nx-danger-rgb), 0.5)"/>
            <text x="102" y="4" font-family="var(--nx-font-ui)" font-size="11.5" font-weight="500" fill="var(--nx-danger)" text-anchor="middle">Deny</text>
          </g>
        </g>
      </g>
    </svg>
  `;
}

function sceneTrust() {
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true">
      <defs>
        <linearGradient id="t-fill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="var(--nx-warn)" stop-opacity="0.18"/>
          <stop offset="100%" stop-color="var(--nx-warn)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <g transform="translate(60 40)">
        <text x="0" y="20" font-family="var(--nx-font-display)" font-size="24" font-weight="600" fill="var(--nx-fg-1)">+0.12</text>
        <text x="74" y="19" font-family="var(--nx-font-ui)" font-size="12" font-weight="600" fill="var(--nx-warn)">Rising</text>
        <line x1="0" y1="80" x2="280" y2="80" stroke="var(--nx-line-1)"/>
        <line x1="0" y1="130" x2="280" y2="130" stroke="var(--nx-line-1)"/>
        <line x1="0" y1="180" x2="280" y2="180" stroke="var(--nx-line-2)"/>
        <path d="M0 180 L0 160 L35 156 L70 152 L105 140 L140 130 L175 124 L210 108 L245 96 L280 84 L280 180 Z" fill="url(#t-fill)" class="nx-tour-anim-area"/>
        <path d="M0 160 L35 156 L70 152 L105 140 L140 130 L175 124 L210 108 L245 96 L280 84"
              fill="none" stroke="var(--nx-warn)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
              class="nx-tour-anim-line"/>
        <circle cx="280" cy="84" r="4" fill="var(--nx-warn)" class="nx-tour-anim-dot"/>
      </g>
    </svg>
  `;
}

function sceneCockpit() {
  const p = (x, y, w, h, d, accent) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="6" fill="var(--nx-surface-1)" stroke="${accent ? "var(--nx-accent-line)" : "var(--nx-line-3)"}" class="nx-tour-anim-panel" style="animation-delay:${d}s"/>`;
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(60 40)">
        ${p(0, 0, 136, 56, 0, true)}${p(146, 0, 68, 56, 0.2)}${p(224, 0, 56, 56, 0.4)}
        ${p(0, 66, 214, 50, 0.6)}${p(224, 66, 56, 50, 0.8)}
        ${p(0, 126, 280, 54, 1.0)}
        <path d="M12 40 L40 34 L68 30 L96 24 L124 18" fill="none" stroke="var(--nx-warn)" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="140" cy="153" r="7" fill="var(--nx-accent)" opacity="0.9"/>
        <circle cx="100" cy="146" r="3" fill="var(--nx-fg-3)"/><circle cx="180" cy="160" r="3" fill="var(--nx-fg-3)"/>
        <circle cx="70" cy="160" r="3" fill="var(--nx-fg-3)"/><circle cx="210" cy="144" r="3" fill="var(--nx-fg-3)"/>
      </g>
    </svg>
  `;
}

function sceneAgents() {
  const SLUGS = ["council", "oracle", "specter", "wraith", "echo", "autonomic", "legacy", "consciousness"];
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(200 130)">
        <circle r="84" fill="none" stroke="var(--nx-line-2)" stroke-dasharray="2 6"/>
        <g class="nx-tour-anim-discs">
        ${SLUGS.map((s, i) => {
          const angle = (i / SLUGS.length) * Math.PI * 2 - Math.PI / 2;
          const x = Math.cos(angle) * 84, y = Math.sin(angle) * 84;
          const g = GRADIENTS[s] || ["#c8c8ff", "#3a3a8c"];
          return `<rect x="${(x - 15).toFixed(1)}" y="${(y - 15).toFixed(1)}" width="30" height="30" rx="8"
                    fill="color-mix(in srgb, ${g[1]} 40%, #16191e)" stroke="${g[0]}" stroke-opacity="0.45"
                    class="nx-tour-anim-disc-pop" style="animation-delay:${(i * 0.1).toFixed(2)}s"/>`;
        }).join("")}
        </g>
        ${TOUR_MARK(18)}
      </g>
    </svg>
  `;
}

function sceneReady() {
  const keys = ["⌘K", "⌘N", "⌘0", "⌘P"];
  return `
    <svg viewBox="0 0 400 260" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(200 104)">
        <circle r="64" fill="none" stroke="var(--nx-line-3)" class="nx-tour-anim-ring1"/>
        <circle r="88" fill="none" stroke="var(--nx-line-2)" class="nx-tour-anim-ring2"/>
        ${TOUR_MARK(32)}
      </g>
      <g transform="translate(${200 - (keys.length * 52 - 8) / 2} 216)">
        ${keys.map((k, i) => `<rect x="${i * 52}" y="0" width="44" height="28" rx="5" fill="var(--nx-surface-1)" stroke="var(--nx-line-3)"/>
          <text x="${i * 52 + 22}" y="18" font-family="var(--nx-font-ui)" font-size="12" font-weight="500" fill="var(--nx-fg-2)" text-anchor="middle">${k}</text>`).join("")}
      </g>
    </svg>
  `;
}

// ── Data loaders ──────────────────────────────────────────────────────────
async function loadAll() {
  await Promise.allSettled([
    loadWorkspaces(),
    loadAgents(),
    loadTrust(),
    loadPermissions(),
    loadMood(),
  ]);
}

async function loadWorkspaces() {
  try {
    const r = await fetch("/api/workspaces");
    if (!r.ok) return;
    const body = await r.json();
    state.workspaces = body.workspaces || [];
    state.active = body.active || null;
  } catch {}
  // Overlay "agents you've actually talked to" counts from chronicle.
  // The /api/workspaces feed only knows about cfg.resident_agents (empty by
  // default), so without this the sidebar tile would always say "0 agents".
  try {
    const r = await fetch("/api/chat-history/workspaces");
    if (r.ok) {
      const body = await r.json();
      const counts = {};
      (body.workspaces || []).forEach(w => {
        if (w.workspace_id) counts[w.workspace_id] = w.agent_count || 0;
      });
      state.workspaceAgentCounts = counts;
    }
  } catch {}
}

// Fetch the live total of runnable (MCP-adapter) catalog agents and refresh
// the agents label. Cheap (limit=1; we only read `total`). Safe to call on a
// timer — the catalog count changes only when a nightly rebuild lands.
async function refreshRunnableCount() {
  try {
    const r = await fetch("/api/agents?runnable_only=true&limit=1");
    if (r.ok) {
      const n = Number((await r.json()).total ?? 0);
      if (Number.isFinite(n) && n > 0) state.runnableCount = n;
    }
  } catch {}
  try {
    const rt = await fetch("/api/agents?limit=1");
    if (rt.ok) {
      const n = Number((await rt.json()).total ?? 0);
      if (Number.isFinite(n) && n > 0) state.catalogTotal = n;
    }
  } catch {}
  try {
    // Always-on cognitive roster (council, oracle, specter, …) + the cortex
    // router. This is the truthful "agents on duty" floor — resident the moment
    // the kernel boots, regardless of a workspace's declared resident_agents.
    const rm = await fetch("/api/cortex/modules");
    if (rm.ok) {
      const n = Number((await rm.json()).count ?? 0);
      if (Number.isFinite(n) && n >= 0) state.coreOnDuty = n;
    }
  } catch {}
  const label = document.getElementById("nx-agents-label");
  if (label && state.agents) {
    const totalBuiltin = state.agents.filter(a => a.is_builtin).length || 10;
    label.textContent = `${totalBuiltin} built-in · ${state.runnableCount || 0} runnable`;
  }
  renderChromeContext();
}

async function loadAgents() {
  // Recent agents = the ones you've actually USED (from chronicle). This
  // takes priority over the catalog/system list — the sidebar should
  // reflect your activity, not a generic curated set.
  try {
    const r = await fetch("/api/chat-history/recent-agents?limit=12");
    if (r.ok) {
      const body = await r.json();
      state.recentAgents = (body.agents || []).map(a => ({
        slug: a.slug,
        kind: a.kind,
        category: a.category || (a.kind === "builtin" ? "built-in" : ""),
        tagline: a.tagline || "",
        chat_count: a.chat_count,
        last_active_at: a.last_active_at,
        last_workspace: a.last_workspace,
        last_workspace_name: a.last_workspace_name,
        last_workspace_tone: a.last_workspace_tone,
      }));
    }
  } catch {}
  try {
    // Pull built-in / system agents first (these are the resident set).
    const r = await fetch("/api/agents?category=system&limit=20");
    if (r.ok) {
      const body = await r.json();
      state.agents = body.agents || [];
    }
  } catch {}
  // Live count of runnable (MCP-adapter) agents in the catalog — drives the
  // "RUNNABLE" figure in the agents label. limit=1 keeps it cheap; we only
  // need the total.
  await refreshRunnableCount();
  // If chronicle had no usage yet, fall back to listing running MCP
  // subprocess agents so the sidebar still has something to show on a
  // fresh install. Real usage replaces this as soon as the user dispatches.
  if (state.recentAgents.length === 0) {
    try {
      const r = await fetch("/api/agents/running");
      if (r.ok) {
        const running = await r.json();
        state.recentAgents = running.slice(0, 6).map(a => ({
          slug: a.slug, kind: "catalog", category: a.category || "running",
          chat_count: 0, last_active_at: null, is_running: true,
        }));
      }
    } catch {}
  }
}

async function loadTrust() {
  // Read trust_change events from chronicle (one call, regardless of how many
  // modules are registered). Aegis logs every adjustment as a chronicle entry.
  try {
    const r = await fetch("/api/chronicle?source=aegis&event_type=aegis.trust_change&limit=100");
    if (!r.ok) return;
    const body = await r.json();
    const entries = body.entries || [];
    const cutoff = Date.now() - 60 * 60 * 1000;
    const recent = entries
      .map(e => {
        const p = e.payload || {};
        return {
          timestamp: e.timestamp,
          delta: typeof p.delta === "number" ? p.delta : 0,
          new_score: typeof p.new_score === "number" ? p.new_score : 1.0,
          module: p.module || "",
        };
      })
      .filter(e => {
        const t = Date.parse(e.timestamp);
        return !isNaN(t) && t >= cutoff;
      })
      .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));

    state.trust.history = recent;
    state.trust.delta = recent.reduce((s, e) => s + (e.delta || 0), 0);
    // Direction follows the NET 60-minute delta, not whether any single event
    // ever dipped (a +0.86 net is "rising", never "collapse"). Collapse is
    // reserved for a net loss where the latest events left an agent under 0.50.
    const latestLow = recent.slice(-5).some(e => e.new_score < 0.50);
    if (state.trust.delta > 0.01) state.trust.direction = "rising";
    else if (state.trust.delta < -0.01) state.trust.direction = latestLow ? "collapse" : "falling";
    else state.trust.direction = "steady";
  } catch {}
  await loadTrustBreakdown();
}

// Trust-class breakdown for the cockpit card — counts real 60-minute activity,
// not just permission tickets (which stay empty when everything auto-allows).
// routine = agent routes (each routed agent gets a routine handle grant);
// gate verdicts bucket by permission class; deny verdicts count as denied;
// trust adjustments count as notable activity.
async function loadTrustBreakdown() {
  const bd = { routine: 0, notable: 0, sensitive: 0, privileged: 0, denied: 0 };
  const cutoff = Date.now() - 60 * 60 * 1000;
  const inWindow = (ts) => { const t = Date.parse(ts); return !isNaN(t) && t >= cutoff; };
  try {
    const [aegisR, cortexR] = await Promise.all([
      fetch("/api/chronicle?source=aegis&limit=300").then(r => r.ok ? r.json() : null).catch(() => null),
      fetch("/api/chronicle?source=cortex&limit=300").then(r => r.ok ? r.json() : null).catch(() => null),
    ]);
    for (const e of (aegisR?.entries || [])) {
      if (!inWindow(e.timestamp)) continue;
      const p = e.payload || {};
      const v = String(p.verdict || "").toLowerCase();
      const pc = String(p.permission_class || "").toLowerCase();
      if (v === "deny") bd.denied++;
      if (pc && bd[pc] !== undefined) bd[pc]++;
      else if ((e.action || "").includes("trust_change")) bd.notable++;
    }
    for (const e of (cortexR?.entries || [])) {
      if (!inWindow(e.timestamp)) continue;
      const a = e.action || "";
      if (a === "route" || a === "multi_run" || a === "multi_launch_start") bd.routine++;
    }
  } catch {}
  state.trust.breakdown = bd;
}

async function loadPermissions() {
  try {
    const p = await fetch("/api/permissions/pending");
    if (p.ok) {
      const body = await p.json();
      state.perms.pending = body.pending || [];
    }
  } catch {}
  // Recent decisions — try the convenience endpoint first, fall back to chronicle
  try {
    const r = await fetch("/api/permissions/recent?limit=20");
    if (r.ok) {
      const body = await r.json();
      state.perms.recent = body.events || [];
      return;
    }
  } catch {}
  try {
    const r = await fetch("/api/chronicle?source=aegis&limit=40");
    if (r.ok) {
      const body = await r.json();
      // Filter to permission-shaped events
      state.perms.recent = (body.entries || [])
        .filter(e => /permission|fs_|net_|trust|grant/.test(e.action || ""))
        .slice(0, 8)
        .map(formatChronicleAsPerm);
    }
  } catch {}
}

function formatChronicleAsPerm(e) {
  const payload = e.payload || {};
  const action = e.action || "";
  let status = "auto", pc = "routine";
  if (action === "permission_granted") { status = "allowed"; pc = (payload.permission_class || "notable").toLowerCase(); }
  else if (action === "permission_revoked" || action === "fs_access_denied" || action.includes("denied")) {
    status = "denied"; pc = "privileged";
  } else if (action.startsWith("fs_") || action.startsWith("net_")) {
    status = "auto"; pc = "routine";
  } else if (action.includes("trust_change")) {
    status = "auto"; pc = "notable";
  }
  return {
    capability: payload.capability || action,
    target: payload.path || payload.url || payload.target || payload.module || "",
    status,
    permission_class: pc,
    time: e.timestamp,
  };
}

async function loadMood() {
  try {
    const r = await fetch("/api/mood/current");
    if (!r.ok) return;
    const body = await r.json();
    state.mood.mood = body.mood;
    state.mood.tone = body.tone;
    state.mood.reason = body.reason || "";
    applyMood(body.mood);
  } catch {}
}

function applyMood(moodKey) {
  const cls = "nx-mood-" + (moodKey || "calm_focus").replace(/_/g, "-");
  const current = [...document.body.classList].find(c => c.startsWith("nx-mood-"));
  if (current && current !== cls) document.body.classList.remove(current);
  if (!document.body.classList.contains(cls)) document.body.classList.add(cls);
  document.body.dataset.mood = moodKey;
  // Update mood-label in chrome
  const lbl = document.getElementById("nx-mood-label");
  if (lbl) lbl.textContent = (moodKey || "calm focus").replace(/_/g, " ");
  // Tint the live kernel scene to match the shell's mood.
  if (typeof forEachScene === "function") forEachScene((s) => s.setMood(moodAccent(moodKey)));
}

// ── Chrome ─────────────────────────────────────────────────────────────────
function startClock() {
  const el = document.getElementById("nx-clock");
  const tick = () => {
    const d = new Date();
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    el.textContent = `${hh}:${mm}`;
  };
  tick();
  setInterval(tick, 30 * 1000);
}

function attachShellHandlers() {
  document.getElementById("nx-new-ws").addEventListener("click", openNewWorkspaceForm);
  document.getElementById("nx-mood-pill").addEventListener("click", openMoodPicker);
  document.getElementById("nx-open-catalog").addEventListener("click", () => location.hash = "#/catalog");
  document.getElementById("nx-open-store").addEventListener("click", () => location.hash = "#/store");
  document.getElementById("nx-open-settings").addEventListener("click", () => location.hash = "#/settings");
  document.getElementById("nx-open-workshop").addEventListener("click", () => location.hash = "#/workshop");
  document.getElementById("nx-open-search").addEventListener("click", () => location.hash = "#/search");
  document.getElementById("nx-open-cortex")?.addEventListener("click", () => location.hash = "#/cortex");
  document.getElementById("nx-open-watch")?.addEventListener("click", () => location.hash = "#/watch");
  document.getElementById("nx-open-memory")?.addEventListener("click", () => location.hash = "#/memory");
  document.getElementById("nx-open-watch-rail")?.addEventListener("click", (e) => { e.stopPropagation(); location.hash = "#/watch"; });
  document.getElementById("nx-search-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      const q = e.target.value.trim();
      if (q) location.hash = `#/catalog?q=${encodeURIComponent(q)}`;
    }
  });
  // Click the ONEXUS brand OR the workspace context → return to home
  // (clears the active thread and shows the welcome state + prompt cards).
  const goHomeOfCurrentWorkspace = () => {
    if (!state.active) {
      location.hash = "#/workspaces";
      return;
    }
    state.thread.set(state.active, []);
    location.hash = `#/conversation/${state.active}`;
    renderConversation(state.active);
  };
  document.getElementById("nx-chrome-home").addEventListener("click", goHomeOfCurrentWorkspace);
  document.getElementById("nx-chrome-context").addEventListener("click", goHomeOfCurrentWorkspace);

  // Chrome controls (window-level controls are provided by the browser).
  document.getElementById("nx-tl-focus").addEventListener("click", () => {
    document.body.classList.toggle("nx-focus-mode");
  });
  document.getElementById("nx-cockpit-toggle").addEventListener("click", () => {
    document.body.classList.toggle("nx-cockpit-hidden");
  });
  // Narrow screens: the sidebar becomes a drawer. Any navigation closes it.
  const sideToggle = document.getElementById("nx-side-toggle");
  const setSide = (open) => {
    document.body.classList.toggle("nx-side-open", open);
    sideToggle?.setAttribute("aria-expanded", String(open));
  };
  sideToggle?.addEventListener("click", () => setSide(!document.body.classList.contains("nx-side-open")));
  document.getElementById("nx-sidebar").addEventListener("click", (e) => {
    if (e.target.closest("button") && !e.target.closest(".nx-ws-trash")) setSide(false);
  });
  window.addEventListener("hashchange", () => setSide(false));
  document.getElementById("nx-open-guide").addEventListener("click", () => renderGuide(0));
  document.getElementById("nx-open-tour").addEventListener("click", () => renderTour(0));
  document.getElementById("nx-tl-fullscreen").addEventListener("click", async () => {
    try {
      if (!document.fullscreenElement) {
        // Vendor prefixes for Safari + older WebKit
        const el = document.documentElement;
        if (el.requestFullscreen) await el.requestFullscreen();
        else if (el.webkitRequestFullscreen) await el.webkitRequestFullscreen();
        else if (el.msRequestFullscreen) await el.msRequestFullscreen();
        else throw new Error("Fullscreen API not supported in this browser");
      } else {
        if (document.exitFullscreen) await document.exitFullscreen();
        else if (document.webkitExitFullscreen) await document.webkitExitFullscreen();
      }
    } catch (e) {
      // Surface the real reason so users (or me) can diagnose
      const msg = (e && e.message) || String(e);
      alert(`Fullscreen blocked by the browser:\n\n${msg}\n\nTip: press F11 (Windows/Linux) or ⌃⌘F (macOS) to toggle native browser fullscreen.`);
    }
  });
}

// ── Sidebar ────────────────────────────────────────────────────────────────
function renderSidebar() {
  // Workspaces
  const list = document.getElementById("nx-ws-list");
  if (!state.workspaces.length) {
    list.innerHTML = `<div class="nx-empty-line nx-side-empty">No workspaces yet. Press ⌘N to make one.</div>`;
  } else {
    list.innerHTML = state.workspaces.map(w => {
      const tone = (w.tone || "indigo").toLowerCase();
      // Agent count = max(distinct agents you've actually chatted with,
      //                    resident_agents declared in cfg)
      // Chronicle count comes from /api/chat-history/workspaces via loadWorkspaces.
      const liveCount = (state.workspaceAgentCounts || {})[w.workspace_id] || 0;
      const declaredCount = w.resident_agents?.length || 0;
      const agentCount = Math.max(liveCount, declaredCount);
      const isActive = w.workspace_id === state.active;
      const meta = `${agentCount}`;
      return `
        <div class="nx-ws-row ${isActive ? "active" : ""}" data-id="${w.workspace_id}">
          <button class="nx-ws-pill" data-id="${w.workspace_id}" aria-label="Open workspace ${escapeHtml(w.name)}, ${agentCount} agents" ${isActive ? 'aria-current="true"' : ""}>
            <span class="ws-dot" style="--tone:var(--nx-tone-${escapeHtml(tone)}-a, var(--nx-accent))"></span>
            <span class="ws-name">${escapeHtml(w.name || w.workspace_id)}</span>
            <span class="ws-meta" title="${agentCount} agent${agentCount === 1 ? "" : "s"}">${escapeHtml(meta)}</span>
          </button>
          <button class="nx-ws-trash" data-id="${w.workspace_id}" data-name="${escapeHtml(w.name)}"
                  aria-label="Delete workspace ${escapeHtml(w.name)}" title="Delete workspace">
            ${icon("trash", 14)}
          </button>
        </div>
      `;
    }).join("");
    list.querySelectorAll(".nx-ws-pill").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        // Clicking the already-active workspace = return to its home
        const alreadyActive = state.active === id;
        if (alreadyActive) {
          state.thread.set(id, []);
          renderConversation(id);
          return;
        }
        await fetch(`/api/workspaces/${encodeURIComponent(id)}/switch`, { method: "POST" });
        await loadWorkspaces();
        renderSidebar();
        renderChromeContext();
        location.hash = `#/conversation/${id}`;
      });
    });
    list.querySelectorAll(".nx-ws-trash").forEach(btn => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const id = btn.dataset.id;
        const name = btn.dataset.name;
        if (!confirm(`Delete workspace "${name}"? This is permanent. Its memory and grants will be removed.`)) return;
        try {
          const r = await fetch(`/api/workspaces/${encodeURIComponent(id)}`, { method: "DELETE" });
          if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: "delete failed" }));
            alert(`Could not delete: ${err.detail || r.status}`);
            return;
          }
          // Remove from thread state
          state.thread.delete(id);
          await loadWorkspaces();
          renderSidebar();
          renderChromeContext();
          // If we were viewing the deleted workspace, redirect
          if (location.hash === `#/conversation/${id}` || state.active !== id) {
            if (state.active) location.hash = `#/conversation/${state.active}`;
            else location.hash = "#/workspaces";
          }
        } catch (err) {
          alert(`Network error: ${err.message}`);
        }
      });
    });
  }

  // Recent agents — sourced from /api/chat-history/recent-agents.
  // Replaces the prior "top 3 catalog" placeholder with agents you've
  // actually USED, scrollable, with relative timestamps and smart click
  // targets (built-in → Cortex launcher pre-selected; catalog → Cortex
  // launcher too since multi-launch handles catalog agents now).
  const recentEl = document.getElementById("nx-recent-agents");
  if (!state.recentAgents.length) {
    recentEl.innerHTML = `<div class="nx-empty-line nx-side-empty">No agents used yet. Start one from Cortex launch (⌘L).</div>`;
  } else {
    recentEl.innerHTML = state.recentAgents.map(a => {
      const lastTxt = a.last_active_at
        ? chatHistoryRelative(a.last_active_at)
        : (a.is_running ? "running" : "not used yet");
      const kindBadge = a.kind === "catalog"
        ? `<span class="nx-recent-kind cat">catalog</span>`
        : (a.kind === "builtin" ? `<span class="nx-recent-kind">core</span>` : "");
      const displayName = a.kind === "catalog" && a.slug.length > 18
        ? a.slug.slice(0, 16) + "…"
        : a.slug;
      return `
        <button class="nx-agent-row" data-slug="${escapeHtml(a.slug)}" data-kind="${escapeHtml(a.kind || "builtin")}" data-workspace="${escapeHtml(a.last_workspace || "")}" title="${escapeHtml(a.tagline || a.category || a.slug)} · click to resume">
          ${agentDisc(a.slug, { size: 24 })}
          <div class="nx-recent-meta">
            <div class="ag-name">${escapeHtml(displayName)} ${kindBadge}</div>
            <div class="ag-sub">${escapeHtml(a.chat_count ? `${a.chat_count} ${a.chat_count === 1 ? "chat" : "chats"} · ${lastTxt}` : lastTxt)}</div>
          </div>
        </button>
      `;
    }).join("");
    recentEl.querySelectorAll(".nx-agent-row").forEach(row => {
      row.addEventListener("click", () => {
        const slug = row.dataset.slug;
        // Built-in and catalog agents both work in the Cortex launcher
        // (multi-launch can pick from either). Pre-select the chip via
        // the agent hash param so the chosen one is ready to dispatch.
        location.hash = `#/cortex?agent=${encodeURIComponent(slug)}`;
      });
    });
  }

  // User footer initials
  const initialsEl = document.getElementById("nx-user-initials");
  initialsEl.textContent = state.user.initials;
}

function renderChromeContext() {
  const el = document.getElementById("nx-chrome-context");
  if (!el) return;
  if (!state.active) { el.innerHTML = `<span class="nx-chrome-ws">No workspace</span>`; return; }
  const w = state.workspaces.find(ws => ws.workspace_id === state.active);
  const name = w ? w.name : state.active;
  // "On duty" = the larger of this workspace's declared/active agents and the
  // always-on cortex roster (cortex routing + council + oracle + …). The core
  // modules are resident whenever the kernel is up, so the count is never 0
  // while the system is live, and it tracks the real module set as it changes.
  const declared = w?.resident_agents?.length || 0;
  const chatted = (state.workspaceAgentCounts || {})[state.active] || 0;
  const count = Math.max(declared, chatted, state.coreOnDuty || 0);
  el.innerHTML = `<span class="nx-chrome-ws">${escapeHtml(name)}</span><span class="nx-chrome-duty"><span class="nx-dot is-live" aria-hidden="true"></span>${count} on duty</span>`;
}

// ── Cockpit rail ──────────────────────────────────────────────────────────
function renderCockpitRail() {
  renderTrustCard();
  renderPermLog();
  renderMoodCard();
  renderAgentDiscs();
  renderKernelViz();
  renderMorningBrief();
  loadMorningBrief();
  renderHeraldPanel();
  renderFederationSync();
  loadHeraldPanel();
}

function renderTrustCard() {
  const el = document.getElementById("nx-trust-card");
  if (!el) return;
  const dir = state.trust.direction;
  el.classList.remove("falling", "collapse");
  if (dir === "falling")  el.classList.add("falling");
  if (dir === "collapse") el.classList.add("collapse");
  const dStr = state.trust.delta > 0 ? `+${state.trust.delta.toFixed(2)}`
            : state.trust.delta.toFixed(2);
  const bd = state.trust.breakdown || {};
  const cells = [
    { cls: "routine",   lbl: "routine",   val: bd.routine   || 0 },
    { cls: "notable",   lbl: "notable",   val: bd.notable   || 0 },
    { cls: "sensitive", lbl: "sensitive", val: bd.sensitive || 0 },
    { cls: "denied",    lbl: "denied",    val: bd.denied    || 0 },
  ];
  el.innerHTML = `
    <div class="nx-trust-head">
      <span class="nx-trust-delta">${dStr}</span>
      <span class="nx-trust-state">${escapeHtml(dir)}</span>
    </div>
    <svg class="nx-trust-spark" viewBox="0 0 320 92" preserveAspectRatio="none" aria-hidden="true">
      ${trustSparkSVG(state.trust.history, dir)}
    </svg>
    <div class="nx-trust-breakdown">
      ${cells.map(c => `
        <span class="b-cell ${c.cls}">
          <span class="b-dot" aria-hidden="true"></span>
          <span class="b-val">${c.val}</span>
          <span class="b-lbl">${c.lbl}</span>
        </span>
      `).join("")}
    </div>
  `;
}

function trustSparkSVG(history, direction) {
  const w = 320, h = 92;
  if (!history.length) {
    // Draw a flat baseline
    return `<line x1="0" y1="${h * 0.78}" x2="${w}" y2="${h * 0.78}" stroke="rgba(255,255,255,0.10)" stroke-width="1" stroke-dasharray="2 4"/>`;
  }
  // Map history to (x,y) points; cumulative trust delta over time → simple stepped curve
  let acc = 0;
  const points = history.map((e, i) => {
    acc += (e.delta || 0);
    return { x: (i / Math.max(history.length - 1, 1)) * w, t: e.timestamp, acc };
  });
  const minAcc = Math.min(0, ...points.map(p => p.acc));
  const maxAcc = Math.max(0.5, ...points.map(p => p.acc));
  const range = maxAcc - minAcc || 1;
  const y = (acc) => h - ((acc - minAcc) / range) * h * 0.7 - h * 0.15;

  const pts = points.map(p => `${p.x.toFixed(1)},${y(p.acc).toFixed(1)}`).join(" L");
  const colorLine = direction === "collapse" ? "var(--nx-trust-collapse)"
                  : direction === "falling"  ? "var(--nx-trust-falling)"
                                              : "var(--nx-trust-rising)";
  const colorArea = colorLine;
  const last = points[points.length - 1];
  return `
    <defs>
      <linearGradient id="ts-area" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${colorArea}" stop-opacity="0.16"/>
        <stop offset="100%" stop-color="${colorArea}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="M ${pts} L ${w},${h} L 0,${h} Z" fill="url(#ts-area)"/>
    <path d="M ${pts}" fill="none" stroke="${colorLine}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>
  `;
}

// ── Kernel live visualization (N1.3) ───────────────────────────────────────
function handleKernelEvent(m) {
  const kv = state.kernelViz;
  // Drive the live Kernel Scene (constellation) on every event, in parallel
  // with the legible text ledger below.
  driveScenes(m);
  renderWatchStat();
  let touched = true;
  if (m.topic === "kernel.route") {
    kv.routes.unshift(m.payload || {});
    kv.routes = kv.routes.slice(0, 8);
  } else if (m.topic === "kernel.gate") {
    kv.gates.unshift(m.payload || {});
    kv.gates = kv.gates.slice(0, 8);
  } else if (m.topic === "sigil.detection") {
    kv.detections.unshift(m.payload || {});
    kv.detections = kv.detections.slice(0, 6);
  } else if (m.topic === "aegis.trust_change") {
    const p = m.payload || {};
    if (p.module && typeof p.new_score === "number") {
      const series = kv.trustSeries[p.module] = kv.trustSeries[p.module] || [];
      series.push(p.new_score);
      if (series.length > 24) series.shift();
    }
  } else if (m.topic === "dreamweaver.brief") {
    // N2.2 — overnight distillation finished; refresh the morning-brief card.
    state.n2.brief = m.payload || null;
    renderMorningBrief();
    touched = false;
  } else if (m.topic && m.topic.startsWith("herald.")) {
    // N3.1 — agent-to-agent negotiation events stream over the Pulse relay.
    const kind = m.topic.slice("herald.".length);
    state.n3.herald.unshift({ kind, payload: m.payload || {} });
    state.n3.herald = state.n3.herald.slice(0, 8);
    renderHeraldPanel();
    touched = false;
  } else if (m.topic === "federation" || (m.topic && m.topic.startsWith("federation."))) {
    // N3.2 — federation sync push/merge counts (best-effort; engine logs to
    // Chronicle, but live events refresh the panel without polling).
    const p = m.payload || {};
    const action = p.action || (m.topic.includes("merge") ? "sync_merge" : "");
    if (action === "sync_push" || m.topic.includes("push")) {
      state.n3.fedSync.pushed += (p.count || 0);
      state.n3.fedSync.last = "push";
    } else if (action === "sync_merge" || m.topic.includes("merge")) {
      state.n3.fedSync.merged += (p.merged || 0);
      state.n3.fedSync.last = "merge";
    }
    renderFederationSync();
    touched = false;
  } else {
    touched = false;
  }
  if (m.priority === 0) emergencyVeil(m);   // Pulse EMERGENCY -> full-surface alert
  if (touched) renderKernelViz();
}

// ── N2 surfaces: morning brief / Atlas graph / Chronos timeline ─────────────
async function loadMorningBrief() {
  try {
    const r = await fetch("/api/dreamweaver/brief");
    if (!r.ok) return;
    state.n2.brief = await r.json();
    renderMorningBrief();
  } catch {}
}

function renderMorningBrief() {
  const el = document.getElementById("nx-morning-brief");
  if (!el) return;
  const b = state.n2.brief;
  if (!b || !b.headline) {
    el.innerHTML = `<div class="nx-empty-line">No brief yet. Dreamweaver writes one overnight.</div>`;
    return;
  }
  const topics = (b.topics || []).slice(0, 8);
  const chips = topics.map(t =>
    `<span class="nx-brief-chip">${escapeHtml(t.topic)}<span class="nx-brief-count">${escapeHtml(String(t.count))}</span></span>`
  ).join("");
  el.innerHTML = `
    <div class="nx-brief-head">${escapeHtml(b.headline)}</div>
    ${b.date ? `<div class="nx-brief-date nx-dim">${escapeHtml(b.date)}</div>` : ""}
    <div class="nx-brief-chips">${chips || `<span class="nx-empty-line">No recurring topics.</span>`}</div>`;
}

// ── N3 surfaces: Herald negotiation + federation sync ──────────────────────
async function loadHeraldPanel() {
  try {
    const r = await fetch("/api/herald");
    if (!r.ok) return;
    const body = await r.json();
    state.n3.heraldOpen = (body.negotiations || []).length;
    renderHeraldPanel();
  } catch {}
}

function renderHeraldPanel() {
  const el = document.getElementById("nx-herald-panel");
  if (!el) return;
  const events = state.n3.herald || [];
  const open = state.n3.heraldOpen || 0;
  if (!events.length && !open) {
    el.innerHTML = `<div class="nx-empty-line">No negotiations. Offers, counters and Aegis-gated commits appear here.</div>`;
    return;
  }
  const rows = events.map(e => {
    const p = e.payload || {};
    const cap = p.capability ? ` · ${escapeHtml(p.capability)}` : "";
    return `<div class="nx-herald-row"><span class="nx-herald-kind">${escapeHtml(e.kind)}</span><span class="nx-dim">${escapeHtml(String(p.negotiation_id || ""))}${cap}</span></div>`;
  }).join("");
  el.innerHTML = `
    <div class="nx-herald-meta nx-dim">${open} open · last ${events.length} event${events.length === 1 ? "" : "s"}</div>
    ${rows}`;
}

function renderFederationSync() {
  const el = document.getElementById("nx-fedsync-panel");
  if (!el) return;
  const s = state.n3.fedSync || { pushed: 0, merged: 0, last: null };
  el.innerHTML = `
    <div class="nx-fedsync-row">
      <span class="nx-fedsync-stat nx-stat"><span class="nx-fedsync-val nx-stat-value">${s.pushed}</span><span class="nx-stat-label">pushed</span></span>
      <span class="nx-fedsync-stat nx-stat"><span class="nx-fedsync-val nx-stat-value">${s.merged}</span><span class="nx-stat-label">merged</span></span>
    </div>
    <div class="nx-fedsync-note">Workspace-scoped, allowlist only, Aegis-gated.</div>`;
}

async function renderAtlasGraph() {
  const main = document.getElementById("nx-main");
  if (!main) return;
  let data = state.n2.atlasGraph;
  try {
    const r = await fetch("/api/atlas/graph");
    if (r.ok) { data = await r.json(); state.n2.atlasGraph = data; }
  } catch {}
  data = data || { nodes: [], edges: [] };
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  // Sunburst layout: facts radiate from their subject hub, labels fan outward
  // and are anchored by hemisphere so they never overlap. Confidence drives the
  // node size + opacity; decayed facts sit slightly further out and dimmer.
  const W = 1100, H = 760, cx = W / 2, cy = H / 2;
  const R = Math.min(W, H) * 0.33;
  const pos = {};
  const n = Math.max(nodes.length, 1);
  // dominant subject(s) — most facts share one subject, so we anchor the hub
  const subjectCounts = {};
  nodes.forEach(x => { subjectCounts[x.subject] = (subjectCounts[x.subject] || 0) + 1; });
  const hubSubject = Object.entries(subjectCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || "";
  nodes.forEach((nd, i) => {
    const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
    const conf = Math.max(0.05, Math.min(1, nd.confidence ?? 0.5));
    const radius = R + (1 - conf) * 70 + (nd.decayed ? 30 : 0);
    pos[nd.id] = { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius, angle, conf, nd };
  });
  // spokes from the hub to each fact — illuminated, gently flowing connective
  // strings in the fact's own colour (green = live, steel = decayed).
  const spokeSVG = nodes.map((nd, i) => {
    const p = pos[nd.id];
    const col = nd.decayed ? "var(--nx-trust-falling)" : "var(--nx-ok)";
    const glowOp = (0.05 + 0.10 * p.conf).toFixed(3);
    const flowOp = (0.30 + 0.55 * p.conf).toFixed(3);
    const delay = (i * 0.13).toFixed(2);
    return `<line class="nx-atlas-glow" x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" stroke="${col}" style="opacity:${glowOp}"/>
      <line class="nx-atlas-spoke" x1="${cx}" y1="${cy}" x2="${p.x.toFixed(1)}" y2="${p.y.toFixed(1)}" stroke="${col}" style="opacity:${flowOp};animation-delay:-${delay}s"/>`;
  }).join("");
  const edgeSVG = edges.map(e => {
    const a = pos[e.src], b = pos[e.dst];
    if (!a || !b) return "";
    return `<line class="nx-atlas-edge" x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" style="opacity:0.4"><title>${escapeHtml(e.label || "related")}</title></line>`;
  }).join("");
  const nodeSVG = nodes.map(nd => {
    const p = pos[nd.id];
    const cls = nd.decayed ? "nx-atlas-node decayed" : "nx-atlas-node";
    const op = (0.35 + 0.65 * p.conf).toFixed(3);
    const right = Math.cos(p.angle) >= 0;
    const lx = p.x + (right ? 12 : -12);
    const anchor = right ? "start" : "end";
    const label = `${nd.subject} ${nd.relation} ${nd.object}`;
    const short = nd.object || label;   // labels just show the object; subject is the hub
    return `<g class="${cls}" style="opacity:${op}">
        <circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="${(4 + 7 * p.conf).toFixed(1)}"/>
        <text x="${lx.toFixed(1)}" y="${(p.y + 4).toFixed(1)}" text-anchor="${anchor}">${escapeHtml(short)}</text>
        <title>${escapeHtml(label)}, confidence ${p.conf.toFixed(2)}${nd.decayed ? " (decayed)" : ""} · ${escapeHtml(nd.source_ref || "unrecorded")}</title>
      </g>`;
  }).join("");
  const hubSVG = nodes.length ? `
    <circle cx="${cx}" cy="${cy}" r="34" fill="var(--nx-surface-2)" stroke="var(--nx-accent)" stroke-width="1.5"/>
    <circle cx="${cx}" cy="${cy}" r="44" fill="none" stroke="var(--nx-accent-line)" stroke-width="1"/>
    <text x="${cx}" y="${cy + 5}" text-anchor="middle" class="nx-atlas-hub-label">${escapeHtml(hubSubject)}</text>` : "";
  main.innerHTML = `
    <div class="nx-main-inner">
    <section class="nx-view nx-atlas-view">
      <header class="nx-view-head nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Atlas · world model</div>
          <h1 class="nx-page-title">World model graph</h1>
          <p class="nx-page-sub">${nodes.length} fact${nodes.length === 1 ? "" : "s"}${hubSubject ? `, centred on <b>${escapeHtml(hubSubject)}</b>` : ""}. Distance and dimness show decay; size and opacity show live confidence.</p>
        </div>
        <div class="nx-page-actions"><span class="nx-status is-ok">Live</span><span class="nx-status">Decayed</span></div>
      </header>
      ${nodes.length ? `<div class="nx-atlas-frame nx-card"><svg class="nx-atlas-canvas" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Atlas knowledge graph">
        ${spokeSVG}${edgeSVG}${nodeSVG}${hubSVG}
      </svg></div>` : emptyStateHTML({ icon: "share", title: "No facts recorded yet", body: `Teach Atlas with <code class="nx-code-inline">observe: subject | relation | object</code>.` })}
    </section>
    </div>`;
}

async function renderChronosTimeline() {
  const main = document.getElementById("nx-main");
  if (!main) return;
  let data = null;
  try {
    const r = await fetch("/api/chronos/timeline?limit=80");
    if (r.ok) data = await r.json();
  } catch {}
  const rows = (data && data.timeline) || [];
  state.n2.chronos = { timeline: rows, result: state.n2.chronos?.result || null };
  const rowsHTML = rows.slice().reverse().map(d => {
    const branch = d.branch_point;
    const cls = branch ? "nx-chronos-row nx-chronos-branch" : "nx-chronos-row";
    const btn = branch
      ? `<button class="nx-chronos-flip nx-btn nx-btn-sm nx-btn-tinted" type="button" data-id="${escapeHtml(d.id)}" data-module="${escapeHtml(d.module || "")}" data-action="${escapeHtml(d.kind === "grant" ? "permission_granted" : d.action)}">${icon("branch", 12)}What if?</button>`
      : "";
    return `<div class="${cls}">
        <span class="nx-chronos-time">${escapeHtml((d.timestamp || "").slice(0, 19).replace("T", " "))}</span>
        <span class="nx-chronos-kind">${escapeHtml(d.kind)}</span>
        <span class="nx-chronos-mod">${escapeHtml(d.module || "-")}</span>
        <span class="nx-chronos-prev nx-dim">${escapeHtml((d.preview || "").slice(0, 48))}</span>
        ${btn}
      </div>`;
  }).join("");
  const res = state.n2.chronos.result;
  const resultHTML = res && res.flipped ? `
    <div class="nx-chronos-result">
      <div class="nx-chronos-result-head">${icon("branch", 14)}If ${escapeHtml(res.flipped.module || "?")}'s ${escapeHtml(res.flipped.action)} had been denied, this would not have happened:</div>
      ${(res.would_not_have_happened || []).map(a =>
        `<div class="nx-chronos-pruned">${escapeHtml(a.module || "-")} · ${escapeHtml(a.action)} · ${escapeHtml((a.preview || "").slice(0, 48))}</div>`
      ).join("") || `<div class="nx-empty-line">Nothing downstream depended on it.</div>`}
    </div>` : "";
  main.innerHTML = `
    <div class="nx-main-inner">
    <section class="nx-view nx-chronos-view">
      <header class="nx-view-head nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Chronos · counterfactuals</div>
          <h1 class="nx-page-title">Decision timeline</h1>
          <p class="nx-page-sub">${rows.length} decision${rows.length === 1 ? "" : "s"}. Branch points (grants and routes) can be flipped to preview the counterfactual. The kernel is never re-run.</p>
        </div>
      </header>
      ${resultHTML}
      ${rowsHTML ? `<div class="nx-chronos-head" aria-hidden="true"><span>Time</span><span>Kind</span><span>Module</span><span>Preview</span><span></span></div><div class="nx-chronos-list">${rowsHTML}</div>` : emptyStateHTML({ icon: "branch", title: "No decisions recorded yet", body: "Run an agent and every route and grant will appear here, in order." })}
    </section>
    </div>`;
  main.querySelectorAll(".nx-chronos-flip").forEach(btn => {
    btn.addEventListener("click", () =>
      runCounterfactual(btn.dataset.module, btn.dataset.action, btn.dataset.id));
  });
}

async function runCounterfactual(module, action, eventId) {
  try {
    const body = (module && action) ? { module, action } : { event_id: eventId };
    const r = await fetch("/api/chronos/counterfactual", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) return;
    const result = await r.json();
    state.n2.chronos = { timeline: state.n2.chronos?.timeline || [], result };
    renderChronosTimeline();
  } catch {}
}

function moduleSparkSVG(series, w = 64, h = 16) {
  if (!series || series.length < 2) {
    return `<line x1="0" y1="${h - 3}" x2="${w}" y2="${h - 3}" stroke="rgba(255,255,255,0.2)" stroke-width="1"/>`;
  }
  const min = Math.min(...series), max = Math.max(...series);
  const range = (max - min) || 1;
  const pts = series.map((v, i) =>
    `${(i / (series.length - 1) * w).toFixed(1)},${(h - 2 - (v - min) / range * (h - 4)).toFixed(1)}`
  ).join(" L");
  return `<path d="M ${pts}" fill="none" stroke="var(--nx-trust-rising)" stroke-width="1.25" stroke-linecap="round" vector-effect="non-scaling-stroke"/>`;
}

function radarPingHTML(det) {
  return `
    <div class="nx-radar-row" title="${escapeHtml(det.description || "")}">
      <span class="nx-radar" aria-hidden="true"><svg viewBox="0 0 20 20" width="18" height="18">
        <circle cx="10" cy="10" r="3" fill="none" stroke="var(--nx-trust-collapse)" stroke-width="1"/>
        <circle cx="10" cy="10" r="7" fill="none" stroke="var(--nx-trust-collapse)" stroke-width="1" opacity="0.5"/>
        <circle cx="10" cy="10" r="2" fill="var(--nx-trust-collapse)" class="nx-radar-ping-dot"/>
      </svg></span>
      <span class="nx-radar-rule">${escapeHtml(det.rule || "")}</span>
      <span class="nx-radar-module nx-dim">${escapeHtml(det.module || "")}</span>
    </div>`;
}

function kernelVizHTML() {
  const kv = state.kernelViz;
  const routes = kv.routes.slice(0, 4).map(r => {
    const top = (r.signals && r.signals[0]) ? r.signals[0].name : "";
    return `<div class="nx-kv-row nx-kv-route">
      <span class="nx-kv-tag">route</span>
      <span class="nx-kv-target">${escapeHtml(r.target || "?")}</span>
      <span class="nx-kv-trail">${escapeHtml(top)}</span>
    </div>`;
  }).join("") || `<div class="nx-empty-line">No routing yet.</div>`;
  const gates = kv.gates.slice(0, 4).map(g => {
    const v = String(g.verdict || "").toLowerCase();
    const pc = String(g.permission_class || "routine").toLowerCase();
    return `<div class="nx-kv-row">
      <span class="nx-kv-gate-dot v-${v} pc-${pc}" aria-hidden="true"></span>
      <span class="nx-kv-cap" title="${escapeHtml(g.capability || "")}">${escapeHtml(truncate(g.capability || "", 26))}</span>
      <span class="nx-kv-trail">${escapeHtml(g.agent || "")} · ${escapeHtml(v)}</span>
    </div>`;
  }).join("");
  const sparks = Object.entries(kv.trustSeries).slice(0, 5).map(([mod, series]) => `
    <div class="nx-kv-row nx-kv-spark">
      <span class="nx-kv-mod">${escapeHtml(mod)}</span>
      <svg viewBox="0 0 64 16" width="64" height="16" preserveAspectRatio="none" aria-hidden="true">${moduleSparkSVG(series)}</svg>
      <span class="nx-kv-trail nx-mono">${series[series.length - 1].toFixed(2)}</span>
    </div>`).join("");
  const pings = kv.detections.map(radarPingHTML).join("");
  return `
    ${routes}
    ${gates}
    ${sparks ? `<div class="nx-kv-divider"></div>${sparks}` : ""}
    ${pings ? `<div class="nx-kv-divider"></div>${pings}` : ""}
  `;
}

function renderKernelViz() {
  const el = document.getElementById("nx-kernel-viz");
  if (el) el.innerHTML = kernelVizHTML();
  const overlayEl = document.getElementById("nx-cockpit-kernel-live");
  if (overlayEl) overlayEl.innerHTML = kernelVizHTML();
}

function emergencyVeil(m) {
  const root = document.getElementById("nx-overlay-root");
  if (!root || root.querySelector(".nx-emergency-veil")) return;
  const p = m.payload || {};
  const veil = document.createElement("div");
  veil.className = "nx-emergency-veil";
  veil.innerHTML = `
    <div class="nx-emergency-card" role="alertdialog" aria-label="Emergency broadcast">
      <div class="nx-emergency-title">${icon("alert-triangle", 16)}<span>Emergency: ${escapeHtml(p.rule || m.topic || "broadcast")}</span></div>
      <div class="nx-emergency-body">${escapeHtml(p.description || "")}${p.module ? " · module: " + escapeHtml(p.module) : ""}</div>
      <button class="nx-emergency-dismiss nx-btn nx-btn-danger" type="button">Acknowledge</button>
    </div>`;
  root.appendChild(veil);
  const close = () => veil.remove();
  veil.querySelector(".nx-emergency-dismiss").addEventListener("click", close);
  setTimeout(close, 12000);
}

// ── N1 — The Kernel Scene (live constellation renderer) ─────────────────────
// One KernelScene class (scene.js) drives every surface: the full-screen Watch
// view, the ⌘0 cockpit panel, and the cockpit-rail mini. They all subscribe to
// the same /api/events/ws Pulse relay via driveScenes(), so cognition renders
// identically wherever it's shown.

// Aegis trust tiers — mirrors kernel/aegis.py thresholds so the ring colour and
// tier label match what the kernel actually enforces.
function tierForTrust(t) {
  if (t >= 1.0) return "AUTONOMOUS";
  if (t >= 0.75) return "EXECUTOR";
  if (t >= 0.50) return "MONITOR";
  if (t >= 0.25) return "ADVISOR";
  return "OBSERVER";
}

// mood → accent hex (matches the dominant tone of each mood.css palette) so the
// scene's atmosphere breathes with the shell.
// Mirrors the --nx-accent value of each mood in mood.css.
const MOOD_ACCENT = {
  calm_focus: "#4ed5d5", deep_flow: "#7ad59c", routing: "#f197c2",
  deliberating: "#f4b768", creative: "#96b4ff", reflective: "#d9a8ef",
  watchful: "#6bcbf7", alert: "#fb817a",
};
function moodAccent(mood) { return MOOD_ACCENT[mood] || MOOD_ACCENT.calm_focus; }

// Build the node descriptors the scene lays out: every on-duty module, coloured
// by its bespoke identity gradient, sized by its live Aegis trust.
function sceneModuleDescriptors(moduleNames, trustMap) {
  return (moduleNames || []).map((name) => {
    const g = GRADIENTS[name] || ["#aab", "#556"];
    const trust = typeof trustMap[name] === "number" ? trustMap[name] : 0.5;
    return { name, colorA: g[0], colorB: g[1], trust, tier: tierForTrust(trust) };
  });
}

async function loadKernelScene() {
  try {
    const [mr, tr] = await Promise.all([
      fetch("/api/cortex/modules").then((r) => r.ok ? r.json() : null).catch(() => null),
      fetch("/api/trust").then((r) => r.ok ? r.json() : null).catch(() => null),
    ]);
    const names = (mr && mr.modules) ? mr.modules.slice() : [];
    const trustMap = {};
    if (tr && Array.isArray(tr.scores)) for (const s of tr.scores) trustMap[s.module] = s.trust;
    // seed rolling trust series so the cockpit sparklines have a baseline
    for (const [m, v] of Object.entries(trustMap)) {
      const series = state.kernelViz.trustSeries[m] = state.kernelViz.trustSeries[m] || [];
      if (!series.length) series.push(v);
    }
    state.scene.modules = sceneModuleDescriptors(names, trustMap);
    forEachScene((s) => s.setModules(state.scene.modules));
    renderWatchCast();
    renderWatchStat();
  } catch {}
}

function forEachScene(fn) { for (const s of Object.values(state.scene.instances)) { try { fn(s); } catch {} } }

function registerScene(id, canvas, opts = {}) {
  unregisterScene(id);
  const scene = new KernelScene(canvas, opts);
  if (state.scene.modules.length) scene.setModules(state.scene.modules);
  scene.setMood(moodAccent(state.mood.mood));
  scene.start();
  state.scene.instances[id] = scene;
  // hydrate roster lazily if we haven't yet
  if (!state.scene.modules.length) loadKernelScene();
  return scene;
}
function unregisterScene(id) {
  const s = state.scene.instances[id];
  if (s) { s.destroy(); delete state.scene.instances[id]; }
}

// Translate a Pulse event into scene motion + a legible ledger line.
function driveScenes(m) {
  const p = m.payload || {};
  const C = state.scene.counters;
  if (m.topic === "kernel.route") {
    C.routes++;
    forEachScene((s) => s.route(p));
    const top = (p.signals && p.signals[0]) ? p.signals[0].name : "";
    pushLedger("route", `<b>${escapeHtml(p.target || "?")}</b>${top ? " · " + escapeHtml(top) : ""}`);
  } else if (m.topic === "kernel.gate") {
    const v = String(p.verdict || "").toLowerCase();
    if (v === "deny") C.denies++; else C.gates++;
    forEachScene((s) => s.gate(p));
    pushLedger(v === "deny" ? "deny" : "gate",
      `${escapeHtml(truncate(p.capability || "", 28))} <span class="nx-dim">${escapeHtml(p.agent || "")} · ${escapeHtml(v)}</span>`);
  } else if (m.topic === "aegis.trust_change") {
    forEachScene((s) => s.trust(p));
    if (p.module && typeof p.new_score === "number") {
      const dir = (p.new_score >= (p.old_score ?? p.new_score)) ? "↑" : "↓";
      pushLedger("trust", `<b>${escapeHtml(p.module)}</b> ${dir} ${p.new_score.toFixed(2)} <span class="nx-dim">${escapeHtml(p.reason || "")}</span>`);
    }
  } else if (m.topic === "engram.write") {
    C.memory++;
    forEachScene((s) => s.memory(p));
    pushLedger("memory", `<span class="nx-dim">${escapeHtml((p.tier || "episodic"))}</span> ${escapeHtml(truncate(p.preview || p.source || "", 34))}`);
  } else if (m.topic === "sigil.detection") {
    forEachScene((s) => s.detection(p));
    pushLedger("alert", `<b>${escapeHtml(p.rule || "anomaly")}</b> <span class="nx-dim">${escapeHtml(p.module || "")}</span>`);
  }
  if (m.priority === 0) forEachScene((s) => s.emergency(p));
}

function pushLedger(kind, html) {
  state.scene.ledger.unshift({ kind, html, t: Date.now() });
  if (state.scene.ledger.length > 60) state.scene.ledger.length = 60;
  renderLedger();
}

const LEDGER_KIND_CLASS = { route: "route", gate: "gate", deny: "deny", trust: "trust", memory: "memory", alert: "alert" };
const LEDGER_KIND_LABEL = { route: "route", gate: "gate", deny: "deny", trust: "trust", memory: "write", alert: "alert" };

function renderLedger() {
  const el = document.getElementById("nx-watch-ledger");
  if (!el) return;
  if (!state.scene.ledger.length) {
    el.innerHTML = `<div class="nx-ledger-empty nx-empty-line">Waiting for kernel activity. Dispatch an agent to watch it think.</div>`;
    return;
  }
  el.innerHTML = state.scene.ledger.map((e) => `
    <div class="nx-ledger-row">
      <span class="nx-ledger-kind nx-lk-${LEDGER_KIND_CLASS[e.kind] || "route"}">${LEDGER_KIND_LABEL[e.kind] || e.kind}</span>
      <span class="nx-ledger-body">${e.html}</span>
    </div>`).join("");
}

function renderWatchStat() {
  const el = document.getElementById("nx-watch-stat");
  if (!el) return;
  const C = state.scene.counters;
  el.innerHTML = `
    <span class="nx-watch-chip"><span class="nx-watch-pulse"></span><b>${state.coreOnDuty || state.scene.modules.length}</b> on duty</span>
    <span class="nx-watch-chip"><b>${C.routes}</b> routes</span>
    <span class="nx-watch-chip"><b>${C.denies}</b> denied</span>`;
}

// ── The Watch view — the headline full-surface kernel scene ─────────────────
async function renderWatch() {
  unregisterScene("watch");
  const main = document.getElementById("nx-main");
  main.innerHTML = `
    <div class="nx-watch">
      <div class="nx-watch-stage">
        <div class="nx-watch-head">
          <div class="nx-watch-eyebrow nx-eyebrow">ONEXUS · Kernel</div>
          <h1 class="nx-watch-title">Watch it think.</h1>
          <div class="nx-watch-sub">Cortex routes, Aegis grants and denies, Engram remembers. The kernel's cognition, live, with nothing hidden.</div>
        </div>
        <div class="nx-watch-stat" id="nx-watch-stat"></div>
        <canvas class="nx-watch-canvas" id="nx-watch-canvas"></canvas>
      </div>
      <div class="nx-watch-rail">
        <div class="nx-watch-rail-sec">
          <div class="nx-watch-rail-label nx-section-label">Reading the scene</div>
          <div class="nx-legend-row"><span class="nx-legend-mark" style="--c:var(--nx-accent);--m:11px"></span><span>The <b>core</b> is Cortex. Every route begins here.</span></div>
          <div class="nx-legend-row"><span class="nx-legend-mark line" style="--c:var(--nx-fg-1)"></span><span>A travelling bead is a <b>route</b> to a module.</span></div>
          <div class="nx-legend-row"><span class="nx-legend-mark ring" style="--c:var(--nx-ok)"></span><span>A green flare: Aegis <b>allowed</b> a capability.</span></div>
          <div class="nx-legend-row"><span class="nx-legend-mark ring" style="--c:var(--nx-trust-collapse)"></span><span>A red flare or veil: <b>denied</b>, or an anomaly.</span></div>
          <div class="nx-legend-row"><span class="nx-legend-mark line" style="--c:var(--nx-warn)"></span><span>A warm bar under a mark: <b>trust</b> rose. A cool one: it fell.</span></div>
          <div class="nx-legend-row"><span class="nx-legend-mark" style="--c:var(--nx-info)"></span><span>Motes sink into <b>memory strata</b> as Engram writes.</span></div>
        </div>
        <div class="nx-watch-rail-sec">
          <div class="nx-section-head"><div class="nx-watch-rail-label nx-section-label">On duty</div><span class="nx-watch-hint">Click to direct</span></div>
          <div class="nx-cast" id="nx-watch-cast"></div>
        </div>
        <div class="nx-watch-rail-sec grow">
          <div class="nx-section-head"><div class="nx-watch-rail-label nx-section-label">Live ledger</div><a href="#/memory" class="nx-cp-watch-link nx-link">Full replay</a></div>
          <div class="nx-ledger" id="nx-watch-ledger"></div>
        </div>
      </div>
    </div>`;
  const canvas = document.getElementById("nx-watch-canvas");
  // Clicking a node (in the scene) or a cast chip opens that module's character
  // sheet — the cognitive modules are participants you watch AND direct.
  registerScene("watch", canvas, { compact: false, onPick: (name) => openCapabilitySheet(name) });
  if (!state.scene.modules.length) await loadKernelScene();
  forEachScene((s) => s.setModules(state.scene.modules));
  renderLedger();
  renderWatchStat();
  renderWatchCast();
}

// The cast — every on-duty cognitive module as a clickable character chip.
function renderWatchCast() {
  const el = document.getElementById("nx-watch-cast");
  if (!el) return;
  const mods = state.scene.modules;
  if (!mods.length) { el.innerHTML = `<div class="nx-loading"><span class="nx-spinner" aria-hidden="true"></span>Loading the modules</div>`; return; }
  el.innerHTML = mods.map(m => {
    const tier = tierForTrust(m.trust);
    return `
      <button type="button" class="nx-cast-chip" data-slug="${escapeHtml(m.name)}" title="${escapeHtml(m.name)} · ${escapeHtml(tier.toLowerCase())} · trust ${m.trust.toFixed(2)}. Click to open.">
        <span class="nx-cast-disc">${agentDisc(m.name, { size: 22 })}</span>
        <span class="nx-cast-name">${escapeHtml(m.name)}</span>
      </button>`;
  }).join("");
  el.querySelectorAll(".nx-cast-chip[data-slug]").forEach(c =>
    c.addEventListener("click", () => openCapabilitySheet(c.dataset.slug)));
}

// ── N6 — Memory & Replay (Engram + Chronicle made visible) ──────────────────
const _replayState = { events: [], idx: 0, playing: false, timer: null };

// Bespoke transport glyphs (no emoji — design invariant). Inline SVG only.
const ICON_PLAY = icon("play", 14);
const ICON_PAUSE = icon("pause", 14);
const ICON_STEP = icon("skip-forward", 14);
const REPLAY_LABEL = `<span class="nx-replay-ico">${ICON_PLAY}</span>Replay`;
const PAUSE_LABEL = `<span class="nx-replay-ico">${ICON_PAUSE}</span>Pause`;

// Map a Chronicle/replay event to a legible (kind, label, summary) triple.
function replayEventView(e) {
  const src = e.source || "", et = e.event_type || "", d = e.data || {};
  let kind = "event", label = et || src, summary = "";
  if (src === "cortex" && et === "route") { kind = "route"; label = "route"; summary = `→ ${d.target || "?"}${d.trust_tier ? " · " + d.trust_tier : ""}`; }
  else if (src === "cortex" && et === "response") { kind = "response"; label = "response"; summary = `${d.module || ""} · ${truncate(d.response_preview || "", 60)}`; }
  else if (et === "trust_change" || typeof d.new_score === "number") { kind = "trust"; label = "trust"; const dir = (d.new_score >= (d.old_score ?? d.new_score)) ? "↑" : "↓"; summary = `${d.module || ""} ${dir} ${typeof d.new_score === "number" ? d.new_score.toFixed(2) : ""} ${d.reason || ""}`; }
  else if (et.includes("gate") || d.verdict) { kind = String(d.verdict || "").toLowerCase() === "deny" ? "deny" : "gate"; label = (d.verdict || "gate").toLowerCase(); summary = `${truncate(d.capability || "", 40)} · ${d.agent || ""}`; }
  else if (src === "engram" || et.includes("write")) { kind = "memory"; label = "write"; summary = `${d.tier || "episodic"} · ${truncate(d.preview || "", 48)}`; }
  else if (src === "sigil" || et === "detection") { kind = "alert"; label = "anomaly"; summary = `${d.rule || ""} ${d.module || ""}`; }
  else if (src === "dreamweaver") { kind = "brief"; label = "brief"; summary = truncate(d.headline || "", 56); }
  else { summary = truncate(JSON.stringify(d), 60); }
  return { kind, label, summary };
}

async function renderMemory() {
  const main = document.getElementById("nx-main");
  main.innerHTML = `<div class="nx-main-inner"><header class="nx-page-head"><div class="nx-page-head-text"><div class="nx-eyebrow nx-page-eyebrow">Engram · Chronicle</div><h1 class="nx-page-title">Memory and replay</h1></div></header><div class="nx-mem-tiers" aria-busy="true">${[0, 1, 2].map(() => `<div class="nx-mem-tier"><span class="nx-skeleton nx-skeleton-short"></span><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-short"></span></div>`).join("")}</div></div>`;
  const j = (url) => fetch(url).then(r => r.ok ? r.json() : null).catch(() => null);
  const [activity, episodic, atlas, timeline] = await Promise.all([
    j("/api/chronicle?source=cortex&limit=16"), j("/api/memory/episodic?limit=12"),
    j("/api/atlas/graph?limit=16"), j("/api/replay/timeline?limit=120"),
  ]);
  // "Working" memory is empty by design (transient k/v), so the first tier shows
  // live session activity instead — the agent turns happening right now.
  const ACT = { route: "routed", multi_run: "ran", response: "replied", continue: "continued", multi_launch_start: "launched" };
  const acts = (activity?.entries || []).filter(e => ACT[e.action || ""]);
  const epi = (episodic && episodic.results) ? episodic.results : [];
  const facts = (atlas && atlas.nodes) ? atlas.nodes : [];
  // Chronicle is newest-first; replay reads chronologically (oldest → newest).
  _replayState.events = ((timeline && timeline.events) ? timeline.events : []).slice().reverse();
  _replayState.idx = Math.max(0, _replayState.events.length - 1);
  _replayState.playing = false;

  const tierCard = (label, count, body) => `
    <div class="nx-mem-tier">
      <div class="nx-mem-tier-head"><span class="nx-mem-tier-label">${label}</span><span class="nx-mem-tier-count">${count}</span></div>
      <div class="nx-mem-tier-body">${body || `<div class="nx-empty-line">Nothing here yet.</div>`}</div>
    </div>`;

  const activityBody = acts.slice(0, 8).map(e => {
    const p = e.payload || {};
    const who = p.module || p.target || "cortex";
    return `<div class="nx-mem-row col"><span class="nx-mem-src">${escapeHtml(who)} · ${escapeHtml(ACT[e.action])}</span><span class="nx-mem-v nx-dim">${escapeHtml(truncate(p.response_preview || p.message_preview || "", 64))}</span></div>`;
  }).join("");
  const epiBody = epi.slice(0, 7).map(m =>
    `<div class="nx-mem-row col"><span class="nx-mem-src">${escapeHtml(m.source || "")}</span><span class="nx-mem-v nx-dim">${escapeHtml(truncate((m.content || "").replace(/\n/g, " "), 64))}</span></div>`).join("");
  const atlasBody = facts.slice(0, 8).map(f => {
    const conf = typeof f.confidence === "number" ? f.confidence : 0;
    const stored = typeof f.stored_confidence === "number" ? f.stored_confidence : conf;
    const decayPct = Math.round(conf * 100), storedPct = Math.round(stored * 100);
    return `<div class="nx-fact">
      <div class="nx-fact-triple"><b>${escapeHtml(f.subject || "")}</b> <span class="nx-dim">${escapeHtml(f.relation || "")}</span> ${escapeHtml(f.object || "")}</div>
      <div class="nx-fact-conf" title="confidence ${conf.toFixed(3)} (stored ${stored.toFixed(3)})">
        <div class="nx-fact-conf-track"><div class="nx-fact-conf-stored" style="width:${storedPct}%"></div><div class="nx-fact-conf-fill" style="width:${decayPct}%"></div></div>
        <span class="nx-fact-conf-val ${f.decayed ? "decayed" : ""}">${decayPct}%${f.decayed ? " decayed" : ""}</span>
      </div>
    </div>`;
  }).join("");

  main.innerHTML = `
    <div class="nx-main-inner nx-mem">
      <header class="nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Engram · Chronicle</div>
          <h1 class="nx-page-title">Memory and replay</h1>
          <p class="nx-page-sub">See what the swarm remembers, and replay every decision it made, in order, from the append-only Chronicle.</p>
        </div>
      </header>

      <div class="nx-mem-tiers">
        ${tierCard("Live session", acts.length, activityBody)}
        ${tierCard("Episodic", (episodic && episodic.count) || epi.length, epiBody)}
        <div class="nx-mem-tier">
          <div class="nx-mem-tier-head"><span class="nx-mem-tier-label">Atlas world model</span><a class="nx-mem-tier-link nx-link" href="#/atlas">Graph</a></div>
          <div class="nx-mem-tier-body">${atlasBody || `<div class="nx-empty-line">No facts yet.</div>`}</div>
          <div class="nx-mem-tier-foot">The solid bar is decayed confidence; the faint bar is stored. Facts fade until they are confirmed again.</div>
        </div>
      </div>

      <section class="nx-replay">
        <div class="nx-replay-head">
          <div class="nx-section-label">Chronicle replay · ${_replayState.events.length} decisions</div>
          <div class="nx-replay-controls">
            <button class="nx-replay-btn nx-btn nx-btn-sm" type="button" id="nx-replay-play" title="Play or pause the run">${REPLAY_LABEL}</button>
            <button class="nx-replay-btn nx-btn nx-btn-sm nx-btn-ghost" type="button" id="nx-replay-step" title="Step one decision">Step <span class="nx-replay-ico">${ICON_STEP}</span></button>
            <input type="range" id="nx-replay-scrub" class="nx-replay-scrub" aria-label="Replay position" min="0" max="${Math.max(0, _replayState.events.length - 1)}" value="${_replayState.idx}">
          </div>
        </div>
        <div class="nx-replay-body">
          <div class="nx-replay-list" id="nx-replay-list"></div>
          <div class="nx-replay-detail" id="nx-replay-detail"></div>
        </div>
      </section>
    </div>`;

  document.getElementById("nx-replay-play").addEventListener("click", toggleReplayPlay);
  document.getElementById("nx-replay-step").addEventListener("click", () => { stepReplay(1); });
  document.getElementById("nx-replay-scrub").addEventListener("input", (e) => { pauseReplay(); selectReplay(parseInt(e.target.value, 10)); });
  renderReplayList();
  // Seed the detail panel WITHOUT scrolling the page (scrollIntoView on the last
  // row was yanking the whole view down to the replay section on open).
  selectReplay(_replayState.idx, false);
  // Always open at the top of the page.
  main.scrollTop = 0;
  requestAnimationFrame(() => { main.scrollTop = 0; });
}

function renderReplayList() {
  const el = document.getElementById("nx-replay-list");
  if (!el) return;
  const evs = _replayState.events;
  if (!evs.length) { el.innerHTML = emptyStateHTML({ icon: "history", title: "Nothing to replay yet", body: "Run a swarm, then replay it here.", compact: true }); return; }
  el.innerHTML = evs.map((e, i) => {
    const v = replayEventView(e);
    return `<button type="button" class="nx-replay-row ${i === _replayState.idx ? "active" : ""}" data-i="${i}">
      <span class="nx-replay-tag nx-lk-${v.kind === "response" ? "route" : v.kind === "brief" ? "memory" : v.kind}">${escapeHtml(v.label)}</span>
      <span class="nx-replay-sum">${escapeHtml(v.summary)}</span>
      <span class="nx-replay-time nx-dim">${escapeHtml(formatTime(e.timestamp))}</span>
    </button>`;
  }).join("");
  el.querySelectorAll(".nx-replay-row[data-i]").forEach(r =>
    r.addEventListener("click", () => { pauseReplay(); selectReplay(parseInt(r.dataset.i, 10)); }));
}

function selectReplay(i, scroll = true) {
  const evs = _replayState.events;
  if (!evs.length) return;
  _replayState.idx = Math.max(0, Math.min(evs.length - 1, i));
  const scrub = document.getElementById("nx-replay-scrub");
  if (scrub) scrub.value = _replayState.idx;
  // highlight active row; only scroll the row into view on user interaction
  // (scroll=false on initial render so the page doesn't jump to the replay).
  const list = document.getElementById("nx-replay-list");
  if (list) {
    list.querySelectorAll(".nx-replay-row").forEach((r, idx) => r.classList.toggle("active", idx === _replayState.idx));
    const active = list.querySelector(".nx-replay-row.active");
    if (active && scroll) active.scrollIntoView({ block: "nearest" });
  }
  const e = evs[_replayState.idx];
  const v = replayEventView(e);
  const detail = document.getElementById("nx-replay-detail");
  if (detail) {
    detail.innerHTML = `
      <div class="nx-replay-detail-tag nx-lk-${v.kind === "response" ? "route" : v.kind === "brief" ? "memory" : v.kind}">${escapeHtml(v.label)}</div>
      <div class="nx-replay-detail-when nx-mono nx-dim">${escapeHtml(e.timestamp || "")} · ${escapeHtml(e.source || "")}</div>
      <pre class="nx-replay-detail-data">${escapeHtml(JSON.stringify(e.data || {}, null, 2))}</pre>`;
  }
}

function stepReplay(dir) {
  if (_replayState.idx >= _replayState.events.length - 1 && dir > 0) { pauseReplay(); return; }
  selectReplay(_replayState.idx + dir);
}

function toggleReplayPlay() { _replayState.playing ? pauseReplay() : playReplay(); }
function playReplay() {
  if (!_replayState.events.length) return;
  // restart from the top if we're already at the end
  if (_replayState.idx >= _replayState.events.length - 1) selectReplay(0);
  _replayState.playing = true;
  const btn = document.getElementById("nx-replay-play");
  if (btn) btn.innerHTML = PAUSE_LABEL;
  _replayState.timer = setInterval(() => {
    if (_replayState.idx >= _replayState.events.length - 1) { pauseReplay(); return; }
    selectReplay(_replayState.idx + 1);
  }, 650);
}
function pauseReplay() {
  _replayState.playing = false;
  if (_replayState.timer) { clearInterval(_replayState.timer); _replayState.timer = null; }
  const btn = document.getElementById("nx-replay-play");
  if (btn) btn.innerHTML = REPLAY_LABEL;
}

function renderPermLog() {
  const el = document.getElementById("nx-perm-log");
  if (!el) return;
  const rows = state.perms.recent.slice(0, 6);
  if (!rows.length) {
    el.innerHTML = `<div class="nx-empty-line">No permission activity yet.</div>`;
    return;
  }
  el.innerHTML = rows.map(r => {
    const pc = (r.permission_class || "routine").toLowerCase();
    const status = (r.status || "auto").toLowerCase();
    const t = formatTime(r.time);
    return `
      <div class="nx-perm-row">
        <span class="nx-perm-dot class-${pc}"></span>
        <div class="nx-perm-cap">
          <span class="cap" title="${escapeHtml(r.capability || "")}">${escapeHtml(r.capability || "")}</span>
          ${r.target ? `<span class="tgt" title="${escapeHtml(r.target)}">${escapeHtml(r.target)}</span>` : ""}
        </div>
        <div class="nx-perm-meta">
          <span class="nx-perm-status s-${status}">${escapeHtml(status)}</span>
          ${t ? `<span class="nx-perm-time">${escapeHtml(t)}</span>` : ""}
        </div>
      </div>
    `;
  }).join("");
}

function renderMoodCard() {
  const el = document.getElementById("nx-mood-card");
  if (!el) return;
  const name = (state.mood.mood || "calm_focus").replace(/_/g, " ");
  const reason = state.mood.reason || "";
  const key = (state.mood.mood || "calm_focus").replace(/_/g, "-");
  el.innerHTML = `
    <span class="nx-mood-mesh nx-mood-preview-${escapeHtml(key)}" aria-hidden="true"></span>
    <div class="nx-mood-caption">
      <div class="nx-mood-caption-name">${escapeHtml(name)}</div>
      <div class="nx-mood-caption-sub">${escapeHtml(reason || "Ambient, following the kernel")}</div>
    </div>
  `;
  // reasons block
  const r = document.getElementById("nx-mood-reasons");
  r.innerHTML = `
    <div>${state.workspaces.length} workspace${state.workspaces.length === 1 ? "" : "s"} · ${state.perms.pending.length} pending</div>
  `;
}

function renderAgentDiscs() {
  const el = document.getElementById("nx-agent-discs");
  if (!el) return;
  const BUILTINS = ["oracle", "council", "wraith", "echo", "prism", "chronos"];
  const totalBuiltin = state.agents.filter(a => a.is_builtin).length || 10;
  document.getElementById("nx-agents-label").textContent =
    `${totalBuiltin} built-in · ${state.runnableCount || 0} runnable`;
  const overflow = Math.max(0, totalBuiltin - BUILTINS.length);
  el.innerHTML = BUILTINS.map(slug => `<button class="nx-disc-btn" data-slug="${slug}" title="${escapeHtml(BUILTIN_CAPABILITIES[slug]?.tagline || slug)}">${agentDisc(slug, { size: 28 })}</button>`).join("") +
    (overflow > 0 ? `<button class="nx-agent-overflow" type="button" title="Browse the catalog">+${overflow}</button>` : "");
  const overEl = el.querySelector(".nx-agent-overflow");
  if (overEl) overEl.addEventListener("click", () => location.hash = "#/catalog");
  // Click any built-in disc → show its capability sheet
  el.querySelectorAll(".nx-disc-btn[data-slug]").forEach(btn => {
    btn.addEventListener("click", () => openCapabilitySheet(btn.dataset.slug));
  });
}

// The trust sheet — one surface for any agent (built-in OR catalog). Renders
// the static identity immediately, then hydrates live Aegis trust, ONEXUS
// benchmark pedigree, and the agent's own slice of the Chronicle audit trail.
// "Safety is a feature you can see" — VISION-AGENTIC-OS §4.
function trustMeterHTML(score, floor) {
  const pct = Math.round(Math.max(0, Math.min(1, score)) * 100);
  const tier = tierForTrust(score);
  const floorPct = floor != null ? Math.round(floor * 100) : null;
  const col = score >= 0.75 ? "var(--nx-routine)" : score >= 0.5 ? "var(--nx-notable)" : score >= 0.25 ? "var(--nx-sensitive)" : "var(--nx-privileged)";
  return `
    <div class="nx-trust-meter">
      <div class="nx-trust-meter-top">
        <span class="nx-trust-meter-score" style="color:${col}">${score.toFixed(2)}</span>
        <span class="nx-trust-meter-tier nx-pill">${escapeHtml(tier.charAt(0) + tier.slice(1).toLowerCase())}</span>
      </div>
      <div class="nx-trust-meter-track nx-meter">
        <div class="nx-trust-meter-fill nx-meter-fill" style="width:${pct}%;background:${col}"></div>
        ${floorPct != null ? `<div class="nx-trust-meter-floor nx-meter-mark" style="left:${floorPct}%" title="Trust floor ${floor.toFixed(2)}"></div>` : ""}
      </div>
      <div class="nx-trust-meter-foot">${floorPct != null ? `Floor ${floor.toFixed(2)}. ` : ""}Below 0.50, Aegis collapses every grant.</div>
    </div>`;
}

async function openCapabilitySheet(slug) {
  const caps = BUILTIN_CAPABILITIES[slug];
  const isBuiltin = !!caps;
  const root = document.getElementById("nx-overlay-root");
  const gradient = GRADIENTS[slug] || ["#a87af5", "#5a4ac4"];
  const floorSeed = isBuiltin ? caps.trust_floor : null;
  root.innerHTML = `
    <div class="nx-cap-overlay nx-scrim" id="nx-cap-overlay" role="dialog" aria-modal="true" aria-labelledby="nx-cap-name">
      <div class="nx-cap-sheet nx-modal" style="--cap-grad-a:${gradient[0]};--cap-grad-b:${gradient[1]}">
        <div class="nx-modal-body nx-cap-body">
        <div class="nx-cap-head nx-detail-head">
          ${agentDisc(slug, { size: 56 })}
          <div>
            <div class="nx-cap-eyebrow nx-eyebrow">${isBuiltin ? "Built-in agent" : "Catalog agent"}</div>
            <h2 class="nx-cap-name nx-detail-title" id="nx-cap-name">${escapeHtml(slug)}</h2>
            <div class="nx-cap-tag nx-detail-sub" id="nx-cap-tag">${escapeHtml(isBuiltin ? caps.tagline : "Loading")}</div>
          </div>
          <button class="nx-cap-close nx-icon-btn" type="button" id="nx-cap-close" aria-label="Close">${icon("x", 16)}</button>
        </div>
        ${isBuiltin ? `<p class="nx-cap-desc">${escapeHtml(caps.description)}</p>` : `<p class="nx-cap-desc" id="nx-cap-desc"></p>`}

        <div class="nx-cap-section nx-cap-section-trust">
          <div class="nx-cap-label nx-section-label">Live trust</div>
          <div id="nx-cap-trust">${trustMeterHTML(floorSeed != null ? floorSeed : 0.5, floorSeed)}</div>
        </div>

        ${!isBuiltin ? `
        <div class="nx-cap-section nx-cap-section-pedigree">
          <div class="nx-cap-label nx-section-label">ONEXUS benchmark pedigree</div>
          <div id="nx-cap-pedigree" class="nx-pedigree-grid">${[0, 1, 2].map(() => `<div class="nx-pedigree-cell"><span class="nx-skeleton nx-skeleton-title"></span><span class="nx-skeleton nx-skeleton-short"></span></div>`).join("")}</div>
        </div>` : ""}

        <div class="nx-cap-grid">
          ${isBuiltin ? `
          <div class="nx-cap-section">
            <div class="nx-cap-label nx-section-label">Intents</div>
            <div class="nx-cap-chips">${caps.intents.map(i => `<span class="cap-chip nx-pill">${escapeHtml(i)}</span>`).join("")}</div>
          </div>
          <div class="nx-cap-section">
            <div class="nx-cap-label nx-section-label">Permission classes</div>
            <div class="nx-cap-chips">${caps.permission_classes.map(c => `
              <span class="cap-chip nx-pc nx-pc-${c.toLowerCase()}">${escapeHtml(c)}</span>
            `).join("")}</div>
          </div>
          <div class="nx-cap-section nx-cap-section-tools">
            <div class="nx-cap-label nx-section-label">Tools declared</div>
            <div class="nx-cap-tools">
              ${caps.tools.map(t => `
                <div class="cap-tool">
                  <span class="cap-tool-dot class-${t.class.toLowerCase()}"></span>
                  <span class="cap-tool-name">${escapeHtml(t.name)}</span>
                  <span class="cap-tool-class">${escapeHtml(t.class)}</span>
                </div>
              `).join("")}
            </div>
          </div>
          <div class="nx-cap-section">
            <div class="nx-cap-label nx-section-label">Network</div>
            <div class="nx-cap-net ${caps.network ? 'on' : 'off'}"><span class="nx-status ${caps.network ? "is-warn" : "is-ok"}">${caps.network ? "Reaches the network" : "Local only"}</span></div>
          </div>` : ""}
        </div>

        <div class="nx-cap-section nx-cap-section-history">
          <div class="nx-cap-label nx-section-label">Chronicle, recent decisions for this agent</div>
          <div id="nx-cap-history" class="nx-cap-history"><div class="nx-loading"><span class="nx-spinner" aria-hidden="true"></span>Reading the audit log</div></div>
        </div>
        </div>

        <div class="nx-cap-actions nx-modal-foot">
          <button class="nx-cap-revoke nx-btn nx-btn-danger" type="button" id="nx-cap-revoke" title="Drop trust to 0.00 and collapse every standing grant">Revoke trust</button>
          <button class="nx-cap-watch nx-btn nx-btn-ghost" type="button" id="nx-cap-watch">${icon("activity", 14)}Watch live</button>
          <button class="nx-cap-watch nx-btn" type="button" id="nx-cap-compose">${icon("workflow", 14)}Compose</button>
          <button class="nx-cap-mention nx-btn nx-btn-primary" type="button" data-slug="${slug}">${icon("message", 14)}Message @${slug}</button>
        </div>
      </div>
    </div>
  `;
  document.getElementById("nx-cap-close").addEventListener("click", closeOverlay);
  document.getElementById("nx-cap-overlay").addEventListener("click", (e) => {
    if (e.target.id === "nx-cap-overlay") closeOverlay();
  });
  document.querySelector(".nx-cap-mention").addEventListener("click", () => {
    closeOverlay();
    if (!state.active) return;
    if (!location.hash.startsWith("#/conversation/")) location.hash = `#/conversation/${state.active}`;
    setTimeout(() => {
      const ci = document.getElementById("nx-composer-input");
      if (ci) { ci.value = `@${slug} `; ci.focus(); }
    }, 200);
  });
  document.getElementById("nx-cap-watch").addEventListener("click", () => { closeOverlay(); location.hash = "#/watch"; });
  document.getElementById("nx-cap-compose")?.addEventListener("click", () => { closeOverlay(); location.hash = `#/cortex?agent=${encodeURIComponent(slug)}`; });
  document.getElementById("nx-cap-revoke").addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    if (btn.dataset.armed !== "1") { btn.dataset.armed = "1"; btn.textContent = "Click again to confirm"; btn.classList.add("armed", "is-armed"); return; }
    btn.disabled = true; btn.textContent = "Revoking";
    try {
      await fetch(`/api/trust/${encodeURIComponent(slug)}/revoke`, { method: "POST" });
      await hydrateTrustSheet(slug, floorSeed);
      btn.classList.remove("armed", "is-armed"); btn.dataset.armed = "0";
    } catch {}
    btn.disabled = false; btn.textContent = "Revoke trust";
  });
  // async hydrate the live sections
  hydrateTrustSheet(slug, floorSeed);
  if (!isBuiltin) hydrateCatalogPedigree(slug);
}

async function hydrateTrustSheet(slug, floorSeed) {
  // live trust meter
  try {
    const r = await fetch(`/api/trust/${encodeURIComponent(slug)}`);
    const el = document.getElementById("nx-cap-trust");
    if (el) {
      if (r.ok) {
        const d = await r.json();
        el.innerHTML = trustMeterHTML(typeof d.trust === "number" ? d.trust : (floorSeed ?? 0.5), floorSeed);
      } else {
        el.innerHTML = trustMeterHTML(floorSeed ?? 0.0, floorSeed) +
          `<div class="nx-trust-meter-foot">No live trust record yet. It is shown at its trust floor until its first run.</div>`;
      }
    }
  } catch {}
  // chronicle history for this agent (gate verdicts + trust changes)
  try {
    const r = await fetch(`/api/chronicle?source=aegis&limit=120`);
    const el = document.getElementById("nx-cap-history");
    if (el && r.ok) {
      const body = await r.json();
      const rows = (body.entries || []).filter(e => {
        const p = e.payload || {};
        return p.module === slug || p.agent === slug;
      }).slice(0, 10);
      if (!rows.length) { el.innerHTML = `<div class="nx-empty-line">No recorded decisions for this agent yet.</div>`; return; }
      el.innerHTML = rows.map(e => {
        const p = e.payload || {};
        const t = formatTime(e.timestamp);
        if (typeof p.new_score === "number") {
          const dir = (p.new_score >= (p.old_score ?? p.new_score)) ? "↑" : "↓";
          return `<div class="nx-cap-hrow"><span class="nx-cap-htag trust">trust</span><span class="nx-cap-hbody">${dir} ${p.new_score.toFixed(2)} <span class="nx-dim">${escapeHtml(p.reason || "")}</span></span><span class="nx-cap-htime nx-dim">${escapeHtml(t)}</span></div>`;
        }
        const v = String(p.verdict || e.action || "").toLowerCase();
        return `<div class="nx-cap-hrow"><span class="nx-cap-htag ${v === "deny" ? "deny" : "gate"}">${escapeHtml(v || "event")}</span><span class="nx-cap-hbody">${escapeHtml(truncate(p.capability || e.action || "", 40))}</span><span class="nx-cap-htime nx-dim">${escapeHtml(t)}</span></div>`;
      }).join("");
    }
  } catch {}
}

async function hydrateCatalogPedigree(slug) {
  try {
    const r = await fetch(`/api/agents/${encodeURIComponent(slug)}`);
    if (!r.ok) return;
    const a = await r.json();
    const tagEl = document.getElementById("nx-cap-tag");
    if (tagEl) tagEl.textContent = a.tagline || "No tagline";
    const descEl = document.getElementById("nx-cap-desc");
    if (descEl) descEl.textContent = (a.category ? a.category.replace(/-/g, " ") + " · " : "") + (a.runnable ? "declares MCP" : "listed");
    const el = document.getElementById("nx-cap-pedigree");
    if (!el) return;
    const fmt = (n) => n == null ? "n/a" : (n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1) + "k" : String(n));
    const stat = (label, val, sub = "") => `<div class="nx-pedigree-cell"><div class="nx-pedigree-val">${val}</div><div class="nx-pedigree-lbl">${label}${sub ? ` <span class="nx-softer">${sub}</span>` : ""}</div></div>`;
    el.innerHTML =
      stat("Benchmark score", a.composite_score != null ? a.composite_score.toFixed(3) : "n/a") +
      stat("Rank in category", a.rank_in_category != null ? "#" + a.rank_in_category : "n/a", a.category ? a.category.replace(/-/g, " ") : "") +
      stat("GitHub stars", fmt(a.stars)) +
      stat("Downloads, 30 days", fmt(a.downloads_30d)) +
      stat("Trust floor", a.trust_floor != null ? a.trust_floor.toFixed(2) : "n/a") +
      stat("License", `<span class="nx-pedigree-small">${escapeHtml(a.license || "n/a")}</span>`) +
      (a.source_github ? `<a class="nx-pedigree-cell link" href="https://github.com/${escapeHtml(a.source_github)}" target="_blank" rel="noopener"><div class="nx-pedigree-val">${icon("external-link", 16)}</div><div class="nx-pedigree-lbl">Source on GitHub</div></a>` : "");
  } catch {}
}

// ── Main view: conversation ────────────────────────────────────────────────
async function renderConversation(workspaceId) {
  const main = document.getElementById("nx-main");
  let ws = state.workspaces.find(w => w.workspace_id === workspaceId);
  if (!ws) {
    try {
      const r = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}`);
      if (r.ok) ws = await r.json();
    } catch {}
  }
  if (!ws) {
    main.innerHTML = `<div class="nx-main-inner">${emptyStateHTML({ icon: "folder", title: "Workspace not found", body: `There is no workspace called ${escapeHtml(workspaceId)}. It may have been deleted.`, actions: `<a class="nx-btn" href="#/workspaces">See all workspaces</a>` })}</div>`;
    return;
  }
  renderChromeContext();

  const thread = state.thread.get(workspaceId) || [];
  const pending = state.perms.pending.filter(p => !p.workspace_id || p.workspace_id === workspaceId);
  const now = new Date();
  const stamp = `${String(now.getHours()).padStart(2,"0")}:${String(now.getMinutes()).padStart(2,"0")}`;
  const isEmpty = thread.length === 0 && pending.length === 0;
  const onDuty = (ws.resident_agents || [])[0];
  const meta = onDuty
    ? `Started by you · ${onDuty} on duty${(ws.resident_agents || []).length > 1 ? ` · ${(ws.resident_agents || [])[1]} listening` : ""}`
    : `Started by you · council routing`;

  const attachedFiles = state.attachments?.get(workspaceId) || [];
  // Use a <label for="..."> wrapping the paperclip — clicking a label for a
  // file input is a native browser primitive and opens the picker without any
  // JS click chain. Works in every browser, including Safari which is picky
  // about programmatic .click() on hidden inputs.
  const composerHTML = `
    ${renderCodebasePanelHTML(workspaceId)}
    <form class="nx-composer" id="nx-composer" autocomplete="off">
      <label class="nx-attach-btn nx-icon-btn" id="nx-attach-btn" for="nx-file-input" title="Attach a file (or drag and drop)" aria-label="Attach a file">
        ${icon("paperclip", 16)}
      </label>
      <button type="button" class="nx-attach-btn nx-icon-btn ${state.codebasePanel.has(workspaceId) ? "is-on" : ""}" id="nx-codebase-btn" title="Browse codebases to attach source files" aria-label="Browse codebases" aria-expanded="${state.codebasePanel.has(workspaceId)}">
        ${icon("code", 16)}
      </button>
      <input type="file" id="nx-file-input" multiple aria-hidden="true" class="nx-file-input-vis">
      <input id="nx-composer-input"
             placeholder="${attachedFiles.length ? `Message with ${attachedFiles.length} file${attachedFiles.length===1?'':'s'} attached` : 'Message the agents in this workspace'}"
             aria-label="Compose a message"
             autofocus>
      <div class="nx-composer-kbd" aria-hidden="true">
        <span class="nx-kbd">⌘</span><span class="nx-kbd">⏎</span><span class="hint">to send</span>
      </div>
    </form>
    ${attachedFiles.length ? `
      <div class="nx-attached-strip">
        ${attachedFiles.map(f => `
          <span class="nx-attached-chip" data-id="${escapeHtml(f.id)}" title="${escapeHtml(f.name)} · ${(f.size/1024).toFixed(1)} KB">
            ${icon("file", 13)}
            <span class="chip-name">${escapeHtml(truncate(f.name, 24))}</span>
            <span class="chip-sz">${(f.size/1024).toFixed(1)} KB</span>
            <button type="button" class="chip-x" data-id="${escapeHtml(f.id)}" aria-label="Remove ${escapeHtml(f.name)}">${icon("x", 12)}</button>
          </span>
        `).join("")}
      </div>
    ` : ""}
  `;

  if (isEmpty) {
    // Empty state — full-canvas welcome, no breadcrumb/title duplication.
    // Composer sits OUTSIDE the scrollable inner so it always stays at the bottom.
    main.innerHTML = `
      <div class="nx-main-inner">
        ${renderEmptyThreadHTML(ws)}
      </div>
      ${composerHTML}
    `;
  } else {
    // Active conversation: show breadcrumb + title + thread
    const firstUserMessage = thread.find(m => m.role === "user");
    const title = firstUserMessage
      ? truncate(firstUserMessage.body, 60)
      : `Session in ${ws.name}`;
    main.innerHTML = `
      <div class="nx-main-inner">
        <div class="nx-conv-head">
          <div class="nx-conv-head-row">
            <div class="nx-conv-crumb">
              <button class="crumb-link" id="nx-crumb-home" data-id="${escapeHtml(ws.workspace_id)}" type="button">
                <span class="crumb-dim">Workspace</span>
                <span class="crumb-sep" aria-hidden="true">/</span>
                <span class="crumb-strong">${escapeHtml(ws.name || ws.workspace_id)}</span>
              </button>
              <span class="crumb-dim">Today, ${stamp}</span>
            </div>
            <div class="nx-conv-head-actions">
              <button class="nx-conv-action nx-btn nx-btn-sm" id="nx-new-thread" type="button" title="Start a new thread in this workspace">
                ${icon("plus", 14)}
                <span>New thread</span>
              </button>
            </div>
          </div>
          <div class="nx-conv-title">${escapeHtml(title)}</div>
          <div class="nx-conv-meta">${escapeHtml(meta)}</div>
        </div>
        <div class="nx-thread" id="nx-thread">
          ${thread.map(renderMessageHTML).join("") + pending.map(renderPendingPermissionHTML).join("")}
        </div>
      </div>
      ${composerHTML}
    `;
    // Wire the home crumb and the new-thread button
    const goHome = () => {
      state.thread.set(workspaceId, []);
      renderConversation(workspaceId);
    };
    document.getElementById("nx-crumb-home")?.addEventListener("click", goHome);
    document.getElementById("nx-new-thread")?.addEventListener("click", goHome);
  }

  // Wire prompt suggestion cards (empty state) — two variants:
  // data-prompt   = seed the composer with a starter prompt and send
  // data-resume-agent = open the Cortex launcher with that agent pre-selected
  main.querySelectorAll(".nx-prompt-card[data-prompt]").forEach(card => {
    card.addEventListener("click", async () => {
      const input = document.getElementById("nx-composer-input");
      if (input) input.value = card.dataset.prompt;
      await sendMessage(workspaceId);
    });
  });
  main.querySelectorAll(".nx-prompt-card[data-resume-agent]").forEach(card => {
    card.addEventListener("click", () => {
      location.hash = `#/cortex?agent=${encodeURIComponent(card.dataset.resumeAgent)}`;
    });
  });

  // File attach: the paperclip is a <label for="nx-file-input">, so clicking
  // it opens the picker natively. We only need to handle the change event.
  const fileInput = document.getElementById("nx-file-input");
  fileInput?.addEventListener("change", async (e) => {
    const files = Array.from(e.target.files || []);
    for (const f of files) await uploadFile(workspaceId, f);
    e.target.value = "";  // allow re-picking the same file
  });

  // Strip chips remove an attachment
  main.querySelectorAll(".chip-x[data-id]").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.preventDefault(); e.stopPropagation();
      const id = btn.dataset.id;
      const list = state.attachments?.get(workspaceId) || [];
      state.attachments.set(workspaceId, list.filter(f => f.id !== id));
      renderConversation(workspaceId);
    });
  });

  // Codebases panel — register roots, browse trees, attach files.
  wireCodebasePanel(workspaceId);

  // Drop anywhere on the main canvas — use addEventListener not the on*
  // properties so they survive re-renders cleanly. The dragover handler MUST
  // preventDefault for drop to fire at all.
  const onDragOver = (e) => {
    if (!e.dataTransfer?.types?.includes("Files")) return;
    e.preventDefault();
    main.classList.add("nx-dragover");
  };
  const onDragLeave = (e) => {
    // Only clear when leaving the main canvas, not when crossing inner edges
    if (e.relatedTarget && main.contains(e.relatedTarget)) return;
    main.classList.remove("nx-dragover");
  };
  const onDrop = async (e) => {
    if (!e.dataTransfer?.files?.length) return;
    e.preventDefault();
    main.classList.remove("nx-dragover");
    const files = Array.from(e.dataTransfer.files);
    for (const f of files) await uploadFile(workspaceId, f);
  };
  main.addEventListener("dragover", onDragOver);
  main.addEventListener("dragleave", onDragLeave);
  main.addEventListener("drop", onDrop);

  // Copy/paste attach: paste a copied file or a screenshot straight into the
  // composer. Plain-text pastes fall through to normal typing.
  const composerInput = document.getElementById("nx-composer-input");
  const onPaste = async (e) => {
    const cd = e.clipboardData;
    if (!cd) return;
    const files = [];
    for (const item of Array.from(cd.items || [])) {
      if (item.kind !== "file") continue;
      let f = item.getAsFile();
      if (!f) continue;
      if (!f.name) {
        // Clipboard images arrive unnamed — give them a real filename.
        const ext = (f.type.split("/")[1] || "bin").replace("jpeg", "jpg");
        f = new File([f], `pasted-${Date.now()}.${ext}`, { type: f.type });
      }
      files.push(f);
    }
    for (const f of Array.from(cd.files || [])) {
      if (!files.some(x => x.name === f.name && x.size === f.size)) files.push(f);
    }
    if (!files.length) return;  // plain text -> let the paste happen normally
    e.preventDefault();
    for (const f of files) await uploadFile(workspaceId, f);
  };
  composerInput?.addEventListener("paste", onPaste);

  // Welcome guide link — open the 12-page guide
  document.getElementById("nx-welcome-guide")?.addEventListener("click", () => renderGuide(0));

  // Tour link — bring the screenshot's narrative to life:
  //   1) Pre-populate the thread with user → oracle (diff cards) → user pick
  //   2) Bump some trust scores so the cockpit sparkline shows real motion
  //   3) Seed a sensitive fs.write permission ticket → inline prompt renders
  const tour = document.getElementById("nx-tour-link");
  if (tour) {
    tour.addEventListener("click", async () => {
      tour.disabled = true;
      tour.textContent = "Loading the tour…";
      const t = state.thread.get(workspaceId) || [];
      const now = new Date();
      const minus = (s) => new Date(now.getTime() - s * 1000).toISOString();
      t.push({
        role: "user",
        body: "Refactor the kernel runtime. Three candidates, smallest blast radius first.",
        ts: minus(140),
      });
      t.push({
        role: "agent", agent: "oracle", ts: minus(120),
        body: "I traced the dependency graph across 47 files in src/kernel/. Three refactor candidates match your scope. Diffs below, ordered by smallest blast radius:",
        attachments: [
          { kind: "diff", path: "src/agents/runtime.py", adds: 12, dels: 34, selected: false },
          { kind: "diff", path: "src/kernel/cortex.py", adds: 8,  dels: 2,  selected: true  },
          { kind: "diff", path: "src/aegis/grants.py",  adds: 5,  dels: 1,  selected: false },
        ],
      });
      t.push({ role: "user", body: "second one looks clean. apply it.", ts: minus(80) });
      state.thread.set(workspaceId, t);

      // Bump trust on a few modules so the sparkline shows motion
      try {
        await Promise.allSettled([
          fetch("/api/trust/oracle/adjust", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ delta: 0.04, reason: "tour:correct-citation" }),
          }),
          fetch("/api/trust/echo/adjust", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ delta: 0.02, reason: "tour:answer-validated" }),
          }),
          fetch("/api/trust/council/adjust", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ delta: 0.03, reason: "tour:dissent-useful" }),
          }),
        ]);
      } catch {}

      // Fire the sensitive permission prompt (the wow moment from the hero)
      try {
        await fetch("/api/permissions/seed", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            agent_slug: "oracle",
            capability: "fs.write",
            permission_class: "Sensitive",
            workspace_id: workspaceId,
            target: "src/kernel/cortex.py",
            preview: "Apply candidate #2, which replaces the inline router fallback with explicit dispatch.",
          }),
        });
      } catch {}

      await Promise.allSettled([loadPermissions(), loadTrust()]);
      renderCockpitRail();
      await renderConversation(workspaceId);
    });
  }

  // Wire feedback buttons on every agent message
  main.querySelectorAll(".nx-msg-agent[data-module]").forEach(msgNode => {
    msgNode.querySelectorAll(".nx-fb-btn[data-fb]").forEach(btn => {
      btn.addEventListener("click", async () => {
        const module = msgNode.dataset.module;
        const accepted = btn.dataset.fb === "up";
        const id = msgNode.dataset.messageId;
        try {
          await fetch("/api/messages/feedback", {
            method: "POST", headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ module, accepted }),
          });
          // Update cached thread state so the highlight persists across re-renders
          const t = state.thread.get(workspaceId) || [];
          const m = t.find(x => x.id === id);
          if (m) m.feedback = accepted ? "up" : "down";
          // Reflect immediately + reload trust + rerender
          await loadTrust();
          renderCockpitRail();
          renderConversation(workspaceId);
        } catch {}
      });
    });
  });

  // Wire pending permission buttons
  main.querySelectorAll(".nx-perm-prompt[data-ticket]").forEach(node => {
    node.querySelectorAll("[data-decision]").forEach(btn => {
      btn.addEventListener("click", async () => {
        await fetch("/api/permissions/decide", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ticket_id: node.dataset.ticket,
            decision: btn.dataset.decision,
          }),
        });
        await loadPermissions();
        renderCockpitRail();
        renderConversation(workspaceId);
      });
    });
  });

  // Composer
  document.getElementById("nx-composer").addEventListener("submit", (e) => {
    e.preventDefault();
    sendMessage(workspaceId);
  });
  document.getElementById("nx-composer-input").addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      sendMessage(workspaceId);
    }
  });

  // Scroll the inner container to its bottom so latest messages are visible
  const inner = document.querySelector(".nx-main-inner");
  if (inner) inner.scrollTop = inner.scrollHeight;

  // Restore any in-flight composer text + focus from previous render (so that
  // when the conversation re-renders we don't blow away what the user is typing)
  const ci = document.getElementById("nx-composer-input");
  if (ci && state._pendingComposer && state._pendingComposer.id === workspaceId) {
    ci.value = state._pendingComposer.value;
    if (state._pendingComposer.focused) ci.focus();
  }
}

// Keep the live composer state in `state._pendingComposer` so re-renders
// don't wipe what the user is typing.
function _wireComposerStatePreservation() {
  document.addEventListener("input", (e) => {
    if (e.target && e.target.id === "nx-composer-input") {
      const id = location.hash.startsWith("#/conversation/")
        ? decodeURIComponent(location.hash.slice("#/conversation/".length))
        : null;
      if (id) {
        state._pendingComposer = { id, value: e.target.value, focused: true };
      }
    }
  });
  document.addEventListener("focusout", (e) => {
    if (e.target && e.target.id === "nx-composer-input" && state._pendingComposer) {
      state._pendingComposer.focused = false;
    }
  });
}
_wireComposerStatePreservation();

function renderEmptyThreadHTML(ws) {
  // If the user has actually used any agents recently, swap the four
  // generic prompt cards for cards that resume those agents (Cortex
  // launcher with chip pre-selected). Falls back to the original
  // curated suggestions when there's no usage history yet.
  const recent = (state.recentAgents || []).slice(0, 4);
  const cards = recent.length >= 1
    ? recent.map(a => {
        const last = a.last_active_at ? chatHistoryRelative(a.last_active_at) : "ready";
        const hint = a.tagline
          ? a.tagline
          : (a.kind === "catalog"
              ? `catalog · ${a.category || "agent"}`
              : `${a.chat_count || 0} prior ${(a.chat_count || 0) === 1 ? "chat" : "chats"} · ${last}`);
        const label = a.kind === "catalog" ? a.slug : `Talk to ${a.slug}`;
        return `
          <button class="nx-prompt-card" data-resume-agent="${escapeHtml(a.slug)}" title="Resume ${escapeHtml(a.slug)} in the Cortex launcher">
            <div class="nx-prompt-glyph">${agentDisc(a.slug, { size: 32 })}</div>
            <div class="nx-prompt-text">
              <div class="nx-prompt-label">${escapeHtml(label)}</div>
              <div class="nx-prompt-hint">${escapeHtml(hint)}</div>
            </div>
            <div class="nx-prompt-arrow">${icon("arrow-up-right", 16)}</div>
          </button>
        `;
      }).join("")
    : [
        { glyph: "council",       label: "Convene the council",  hint: "Get a 3-round deliberation across the cognitive modules.", prompt: "Council: I'm refactoring my kernel runtime. What should I be careful about?" },
        { glyph: "oracle",        label: "Ask the oracle",        hint: "A first read across whatever is in this workspace.",      prompt: "Oracle: read this repo and summarise its architecture in 5 bullets." },
        { glyph: "specter",       label: "Red-team a plan",       hint: "Counter-arguments and dissenting views, no flattery.",     prompt: "Specter: red-team my decision to switch from postgres to sqlite." },
        { glyph: "legacy",        label: "Pull from memory",      hint: "Recall what was decided last time, with citations.",       prompt: "Legacy: what have I tried for this problem before?" },
      ].map(s => `
          <button class="nx-prompt-card" data-prompt="${escapeHtml(s.prompt)}">
            <div class="nx-prompt-glyph">${agentDisc(s.glyph, { size: 32 })}</div>
            <div class="nx-prompt-text">
              <div class="nx-prompt-label">${escapeHtml(s.label)}</div>
              <div class="nx-prompt-hint">${escapeHtml(s.hint)}</div>
            </div>
            <div class="nx-prompt-arrow">${icon("corner-down-left", 16)}</div>
          </button>
        `).join("");

  return `
    <div class="nx-welcome">
      <div class="nx-welcome-orb">${KERNEL_MARK(44)}</div>
      <div class="nx-eyebrow nx-welcome-eyebrow">Workspace</div>
      <h1>${escapeHtml(ws.name)}</h1>
      <p>A workspace is a room with its own agents, memory and grants. Send a
         message to start, or pick a thread below. Every tool call passes
         through <span class="nx-welcome-term">Aegis</span> and every event lands in
         <span class="nx-welcome-term">Chronicle</span>.</p>
      <div class="nx-prompt-grid" id="nx-prompt-grid">
        ${cards}
      </div>
      <div class="nx-welcome-links">
        <button class="nx-tour-link nx-btn nx-btn-ghost" id="nx-tour-link" type="button" data-workspace="${escapeHtml(ws.workspace_id)}">
          ${icon("shield-check", 16)}<span>See the safety model: fire a sample permission prompt</span>
        </button>
        <button class="nx-tour-link nx-btn nx-btn-ghost" id="nx-welcome-guide" type="button">
          ${icon("book-open", 16)}<span>Open the guide, ${GUIDE_PAGES.length} pages</span><span class="nx-kbd">?</span>
        </button>
      </div>
    </div>
  `;
}

function renderMessageHTML(m) {
  if (m.role === "user") {
    const atts = (m.attachments || []).filter(a => a.kind === "file");
    const attHTML = atts.length ? `
      <div class="nx-msg-user-files">
        ${atts.map(a => `
          <span class="nx-file-chip">
            ${icon("file", 12)}
            <span>${escapeHtml(a.name)}</span>
            <span class="chip-sz">${(a.size/1024).toFixed(1)} KB</span>
          </span>
        `).join("")}
      </div>
    ` : "";
    return `
      <div class="nx-msg-user">
        <div class="nx-msg-bubble">
          ${m.body ? escapeHtml(m.body) : ""}
          ${attHTML}
        </div>
      </div>
    `;
  }
  const slug = m.agent || "oracle";
  const time = formatTime(m.ts) || "";
  if (m.typing) {
    return `
      <div class="nx-msg-agent is-typing">
        ${agentDisc(slug, { size: 32 })}
        <div class="nx-msg-col">
          <div class="nx-msg-head">
            <span class="nx-msg-name">Routing</span>
            <span class="nx-msg-meta">Cortex is picking a module</span>
          </div>
          <div class="nx-typing"><span></span><span></span><span></span></div>
        </div>
      </div>
    `;
  }
  const diffs = (m.attachments || []).filter(a => a.kind === "diff");
  const diffHTML = diffs.length ? `
    <div class="nx-diff-stack">
      ${diffs.map(d => `
        <div class="nx-diff-card ${d.selected ? "selected" : ""}" data-path="${escapeHtml(d.path)}">
          <span class="nx-diff-icon" aria-hidden="true">${icon("file-text", 14)}</span>
          <span class="nx-diff-path">${escapeHtml(d.path)}</span>
          <span class="nx-diff-adds">+${d.adds || 0}</span>
          <span class="nx-diff-dels">−${d.dels || 0}</span>
          <span class="nx-diff-trail" aria-hidden="true">${d.selected ? icon("check", 14) : ""}</span>
        </div>
      `).join("")}
    </div>
  ` : "";
  const fb = m.feedback;  // null | 'up' | 'down'
  // Agent message bodies render through the escape-first markdown pipeline
  // (md.js). While a reply is still streaming we show the raw text with
  // pre-wrap (cheap incremental updates); on completion the body is
  // re-rendered as markdown. User messages stay plain-escaped.
  const bodyHTML = m.streaming
    ? `<div class="nx-msg-body nx-msg-streaming">${escapeHtml(m.body)}<span class="nx-stream-caret" aria-hidden="true"></span></div>`
    : `<div class="nx-msg-body nx-msg-md">${m.html || renderMarkdown(m.body)}</div>`;
  return `
    <div class="nx-msg-agent" data-message-id="${escapeHtml(m.id || "")}" data-module="${escapeHtml(slug)}">
      ${agentDisc(slug, { size: 32 })}
      <div class="nx-msg-col">
        <div class="nx-msg-head">
          <span class="nx-msg-name">${escapeHtml(slug)}</span>
          <span class="nx-msg-meta">${escapeHtml(time)}</span>
          ${m.memory_id ? `<span class="nx-msg-memory nx-pill nx-pill-ok" title="Stored in Engram: ${escapeHtml(m.memory_id)}">${icon("database", 12)}Remembered</span>` : ""}
        </div>
        ${bodyHTML}
        ${diffHTML}
        <div class="nx-msg-footer">
          <button class="nx-fb-btn nx-icon-btn ${fb === 'up' ? 'on' : ''}" type="button" data-fb="up" aria-pressed="${fb === 'up'}" aria-label="Useful" title="Mark this response as useful (raises ${escapeHtml(slug)}'s trust)">
            ${icon("thumbs-up", 14)}
          </button>
          <button class="nx-fb-btn nx-icon-btn ${fb === 'down' ? 'on down' : ''}" type="button" data-fb="down" aria-pressed="${fb === 'down'}" aria-label="Not useful" title="Mark this response as unhelpful (lowers ${escapeHtml(slug)}'s trust)">
            ${icon("thumbs-down", 14)}
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderPendingPermissionHTML(p) {
  const pc = (p.permission_class || "sensitive").toLowerCase();
  const slug = p.agent_slug || "oracle";
  return `
    <div class="nx-msg-agent">
      ${agentDisc(slug, { size: 32 })}
      <div class="nx-msg-col">
        <div class="nx-msg-head">
          <span class="nx-msg-name">${escapeHtml(slug)}</span>
          <span class="nx-msg-meta">Requesting access</span>
        </div>
        <div class="nx-msg-body">
          Needs <span class="nx-cap">${escapeHtml(p.capability)}</span>${p.target ? ` on <span class="nx-code">${escapeHtml(p.target)}</span>` : ""}.
          ${p.preview ? ` ${escapeHtml(p.preview)}` : ""} How should Aegis remember this?
        </div>
        <div class="nx-perm-prompt nx-perm-card class-${pc}" data-ticket="${escapeHtml(p.id)}" role="group" aria-label="Permission request from ${escapeHtml(slug)}">
          <span class="nx-perm-pulse" aria-hidden="true"></span>
          <div class="nx-perm-info">
            <div class="nx-perm-eyebrow nx-perm-card-eyebrow">${escapeHtml(pc)} · <span class="nx-mono">${escapeHtml(p.capability || "")}</span></div>
            <div class="nx-perm-body nx-perm-card-body">${p.target ? `${escapeHtml(slug)} on <code>${escapeHtml(p.target)}</code>` : `${escapeHtml(slug)}, no target given`}</div>
          </div>
          <div class="nx-perm-actions nx-perm-card-actions">
            <button class="nx-perm-btn allow nx-btn nx-btn-sm nx-btn-primary" type="button" data-decision="allow_once">Allow once</button>
            <button class="nx-perm-btn always nx-btn nx-btn-sm" type="button" data-decision="allow_always_in_workspace">Always in this workspace</button>
            <button class="nx-perm-btn deny nx-btn nx-btn-sm nx-btn-danger" type="button" data-decision="deny">Deny</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function _msgId() { return "m_" + Math.random().toString(36).slice(2, 10); }

async function uploadFile(workspaceId, file) {
  if (!file) return;
  const form = new FormData();
  form.append("workspace_id", workspaceId);
  form.append("file", file);
  try {
    const r = await fetch("/api/files", { method: "POST", body: form });
    if (!r.ok) {
      const txt = await r.text();
      console.error("upload failed:", txt);
      return;
    }
    const meta = await r.json();
    const list = state.attachments.get(workspaceId) || [];
    list.push(meta);
    state.attachments.set(workspaceId, list);
    renderConversation(workspaceId);
  } catch (e) {
    console.error("upload error:", e);
  }
}

// ── Codebases panel ────────────────────────────────────────────────────────
// A workspace can register local directories ("codebase roots") through
// POST /api/codebases. The panel browses them one directory level at a time
// (lazy: GET /tree on first expand, cached in state.codebaseTrees) and a
// click on a file pulls its content (GET /file) and pushes it through the
// existing upload/attachment flow, so it lands in the composer exactly like
// a dragged-in file — Engram record, Chronicle log, dedupe and all.

function _cbKey(codebaseId, rel) { return `${codebaseId}|${rel}`; }

function renderCodebaseLevelHTML(codebaseId, rel, depth) {
  const entries = state.codebaseTrees.get(_cbKey(codebaseId, rel)) || [];
  if (!entries.length) {
    return `<div class="nx-cb-empty" style="padding-left:${14 + depth * 14}px">Empty folder</div>`;
  }
  return entries.map(e => {
    const childRel = rel ? `${rel}/${e.name}` : e.name;
    const pad = 14 + depth * 14;
    if (e.type === "dir") {
      const open = state.codebaseOpen.has(_cbKey(codebaseId, childRel));
      return `
        <button type="button" class="nx-cb-row nx-cb-dir ${open ? "open" : ""}"
                data-cb-dir data-cb-id="${escapeHtml(codebaseId)}" data-cb-rel="${encodeURIComponent(childRel)}"
                style="padding-left:${pad}px">
          <span class="nx-cb-arrow" aria-hidden="true">${icon("chevron-right", 12)}</span>
          ${icon("folder", 13)}
          <span class="nx-cb-name">${escapeHtml(e.name)}</span>
        </button>
        ${open ? renderCodebaseLevelHTML(codebaseId, childRel, depth + 1) : ""}
      `;
    }
    return `
      <button type="button" class="nx-cb-row nx-cb-file"
              data-cb-file data-cb-id="${escapeHtml(codebaseId)}" data-cb-rel="${encodeURIComponent(childRel)}"
              style="padding-left:${pad}px" title="Attach ${escapeHtml(e.name)} to the composer">
        ${icon("file", 13)}
        <span class="nx-cb-name">${escapeHtml(e.name)}</span>
        <span class="nx-cb-size">${((e.size || 0) / 1024).toFixed(1)} KB</span>
      </button>
    `;
  }).join("");
}

function renderCodebasePanelHTML(workspaceId) {
  if (!state.codebasePanel.has(workspaceId)) return "";
  const roots = state.codebases.get(workspaceId) || [];
  const rows = roots.map(r => {
    const open = state.codebaseOpen.has(_cbKey(r.id, ""));
    return `
      <div class="nx-cb-root">
        <div class="nx-cb-root-row">
          <button type="button" class="nx-cb-row nx-cb-dir ${open ? "open" : ""}"
                  data-cb-dir data-cb-id="${escapeHtml(r.id)}" data-cb-rel=""
                  title="${escapeHtml(r.path)}">
            <span class="nx-cb-arrow" aria-hidden="true">${icon("chevron-right", 12)}</span>
            ${icon("folder", 13)}
            <span class="nx-cb-name">${escapeHtml(r.name)}</span>
            <span class="nx-cb-path">${escapeHtml(truncate(r.path, 48))}</span>
          </button>
          <button type="button" class="nx-cb-remove nx-icon-btn" data-cb-remove data-cb-id="${escapeHtml(r.id)}"
                  title="Unregister this codebase" aria-label="Unregister ${escapeHtml(r.name)}">${icon("x", 14)}</button>
        </div>
        ${open ? renderCodebaseLevelHTML(r.id, "", 1) : ""}
      </div>
    `;
  }).join("");
  return `
    <div class="nx-codebase-panel" id="nx-codebase-panel">
      <div class="nx-cb-head">
        <span class="nx-cb-title nx-section-label">Codebases</span>
        <span class="nx-cb-hint">Read only. Click a file to attach it.</span>
      </div>
      ${rows || `<div class="nx-cb-empty">No codebases registered for this workspace yet.</div>`}
      <form class="nx-cb-add" id="nx-cb-add">
        <input id="nx-cb-path" class="nx-input nx-input-mono" placeholder="/absolute/path/to/repo" aria-label="Absolute path to a local codebase" autocomplete="off">
        <button type="submit" class="nx-btn">Register</button>
      </form>
      ${state._codebaseErr ? `<div class="nx-cb-err nx-alert is-danger" role="alert">${icon("alert-circle", 16)}<div class="nx-alert-body">${escapeHtml(state._codebaseErr)}</div></div>` : ""}
    </div>
  `;
}

async function loadCodebases(workspaceId) {
  try {
    const r = await fetch(`/api/codebases?workspace_id=${encodeURIComponent(workspaceId)}`);
    if (r.ok) state.codebases.set(workspaceId, (await r.json()).codebases || []);
  } catch {}
}

async function _cbDetail(r, fallback) {
  try {
    const body = await r.json();
    return body.detail || fallback;
  } catch { return fallback; }
}

function wireCodebasePanel(workspaceId) {
  document.getElementById("nx-codebase-btn")?.addEventListener("click", async () => {
    if (state.codebasePanel.has(workspaceId)) {
      state.codebasePanel.delete(workspaceId);
    } else {
      state.codebasePanel.add(workspaceId);
      state._codebaseErr = null;
      await loadCodebases(workspaceId);
    }
    renderConversation(workspaceId);
  });

  const panel = document.getElementById("nx-codebase-panel");
  if (!panel) return;

  document.getElementById("nx-cb-add")?.addEventListener("submit", async (e) => {
    e.preventDefault(); e.stopPropagation();
    const input = document.getElementById("nx-cb-path");
    const path = (input?.value || "").trim();
    if (!path) return;
    state._codebaseErr = null;
    try {
      const r = await fetch("/api/codebases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: workspaceId, path }),
      });
      if (!r.ok) {
        state._codebaseErr = await _cbDetail(r, `register failed (HTTP ${r.status})`);
      } else {
        await loadCodebases(workspaceId);
      }
    } catch (err) {
      state._codebaseErr = `register failed: ${err.message}`;
    }
    renderConversation(workspaceId);
  });

  panel.querySelectorAll("[data-cb-remove]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.cbId;
      state._codebaseErr = null;
      try { await fetch(`/api/codebases/${encodeURIComponent(id)}`, { method: "DELETE" }); } catch {}
      for (const key of [...state.codebaseOpen]) if (key.startsWith(`${id}|`)) state.codebaseOpen.delete(key);
      for (const key of [...state.codebaseTrees.keys()]) if (key.startsWith(`${id}|`)) state.codebaseTrees.delete(key);
      await loadCodebases(workspaceId);
      renderConversation(workspaceId);
    });
  });

  panel.querySelectorAll("[data-cb-dir]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.cbId;
      const rel = decodeURIComponent(btn.dataset.cbRel || "");
      const key = _cbKey(id, rel);
      state._codebaseErr = null;
      if (state.codebaseOpen.has(key)) {
        state.codebaseOpen.delete(key);
      } else {
        if (!state.codebaseTrees.has(key)) {
          try {
            const r = await fetch(`/api/codebases/${encodeURIComponent(id)}/tree?path=${encodeURIComponent(rel)}`);
            if (!r.ok) {
              state._codebaseErr = await _cbDetail(r, `browse failed (HTTP ${r.status})`);
              renderConversation(workspaceId);
              return;
            }
            state.codebaseTrees.set(key, (await r.json()).entries || []);
          } catch (err) {
            state._codebaseErr = `browse failed: ${err.message}`;
            renderConversation(workspaceId);
            return;
          }
        }
        state.codebaseOpen.add(key);
      }
      renderConversation(workspaceId);
    });
  });

  panel.querySelectorAll("[data-cb-file]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.cbId;
      const rel = decodeURIComponent(btn.dataset.cbRel || "");
      state._codebaseErr = null;
      try {
        const r = await fetch(`/api/codebases/${encodeURIComponent(id)}/file?path=${encodeURIComponent(rel)}`);
        if (!r.ok) {
          state._codebaseErr = await _cbDetail(r, `attach failed (HTTP ${r.status})`);
          renderConversation(workspaceId);
          return;
        }
        const body = await r.json();
        // Reuse the standard attachment flow: the file content becomes a
        // pending upload, exactly as if it were dragged into the surface.
        const file = new File([body.content], body.name, { type: "text/plain" });
        await uploadFile(workspaceId, file);
      } catch (err) {
        state._codebaseErr = `attach failed: ${err.message}`;
        renderConversation(workspaceId);
      }
    });
  });
}

async function sendMessage(workspaceId) {
  const input = document.getElementById("nx-composer-input");
  const body = input.value.trim();
  const files = state.attachments.get(workspaceId) || [];
  if (!body && files.length === 0) return;

  // Keyword launcher: typing "cortex <prompt>" (or just "cortex") opens the
  // Cortex multi-agent launcher with the rest of the message prefilled.
  // Useful when the user wants to fan a question to several agents at once
  // instead of letting cortex pick a single best.
  const cortexMatch = body.match(/^cortex\b\s*(.*)$/i);
  if (cortexMatch) {
    input.value = "";
    const rest = (cortexMatch[1] || "").trim();
    location.hash = rest ? `#/cortex?prompt=${encodeURIComponent(rest)}` : "#/cortex";
    return;
  }

  input.value = "";
  if (state._pendingComposer && state._pendingComposer.id === workspaceId) {
    state._pendingComposer = null;
  }
  // Move attached files into the message + clear the pending strip
  const attachments = files.map(f => ({ kind: "file", name: f.name, size: f.size, id: f.id }));
  state.attachments.set(workspaceId, []);

  // Append user message locally
  const thread = state.thread.get(workspaceId) || [];
  thread.push({ id: _msgId(), role: "user", body, ts: new Date().toISOString(), attachments });
  state.thread.set(workspaceId, thread);
  renderConversation(workspaceId);

  // The actual message sent to the agent includes the file references
  let messageForAgent = body;
  if (attachments.length) {
    const list = attachments.map(a => `- ${a.name} (${(a.size/1024).toFixed(1)} KB)`).join("\n");
    messageForAgent = `${body || "Attached files for you to consider:"}\n\nAttached:\n${list}`;
  }

  // Add a pending typing indicator message so the user sees the system thinking
  const typingId = _msgId();
  thread.push({ id: typingId, role: "agent", agent: "council", body: "", ts: new Date().toISOString(), typing: true });
  state.thread.set(workspaceId, thread);
  renderConversation(workspaceId);

  // Preferred path: consume the SSE stream and render the reply token by
  // token. Falls back to the plain POST endpoint on any stream failure.
  const streamedOk = await streamAgentReply(workspaceId, thread, typingId, messageForAgent);
  if (streamedOk) return;

  try {
    const r = await fetch("/api/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: messageForAgent, workspace_id: workspaceId }),
    });
    // Remove the typing placeholder
    const idx = thread.findIndex(m => m.id === typingId);
    if (idx >= 0) thread.splice(idx, 1);

    if (r.ok) {
      const resp = await r.json();
      const agentBody = resp.response || resp.message || resp.reply || "";
      const agent = resp.agent || resp.routed_to || resp.module || "oracle";
      thread.push({
        id: _msgId(),
        role: "agent",
        agent,
        body: agentBody,
        ts: new Date().toISOString(),
        memory_id: resp.memory_id || null,
        feedback: null,
      });
      state.thread.set(workspaceId, thread);
      renderConversation(workspaceId);
      // Refresh trust + permissions in case routing produced events
      loadTrust().then(() => loadPermissions()).then(renderCockpitRail);
    } else {
      const errText = await r.text();
      thread.push({ id: _msgId(), role: "agent", agent: "specter", body: `Routing failed (${r.status}): ${errText}`, ts: new Date().toISOString() });
      state.thread.set(workspaceId, thread);
      renderConversation(workspaceId);
    }
  } catch (err) {
    const idx = thread.findIndex(m => m.id === typingId);
    if (idx >= 0) thread.splice(idx, 1);
    thread.push({ id: _msgId(), role: "agent", agent: "specter", body: `Routing error: ${err.message}`, ts: new Date().toISOString() });
    state.thread.set(workspaceId, thread);
    renderConversation(workspaceId);
  }
}

// ── Streaming send path ────────────────────────────────────────────────────
// POST /api/messages/stream returns SSE frames:
//   {type:"chunk", content, module} · {type:"done", module, memory_id}
//   · {type:"error", detail}
// The agent message is appended to the thread on the FIRST chunk and its
// body grows in place (cheap targeted DOM update, no full re-render per
// token). On the terminal frame the message is finalized and re-rendered
// through the markdown pipeline. Returns false when the caller should fall
// back to the non-streaming endpoint.
async function streamAgentReply(workspaceId, thread, typingId, messageForAgent) {
  let msg = null;

  const ensureMsg = (module) => {
    if (msg) return msg;
    const idx = thread.findIndex(m => m.id === typingId);
    if (idx >= 0) thread.splice(idx, 1);
    msg = {
      id: _msgId(), role: "agent", agent: module || "oracle",
      body: "", ts: new Date().toISOString(),
      streaming: true, memory_id: null, feedback: null,
    };
    thread.push(msg);
    state.thread.set(workspaceId, thread);
    renderConversation(workspaceId);
    return msg;
  };

  // Targeted incremental update: rewrite only the streaming bubble's body.
  const paintChunk = () => {
    const node = document.querySelector(`.nx-msg-agent[data-message-id="${msg.id}"] .nx-msg-body`);
    if (!node) { renderConversation(workspaceId); return; }
    node.innerHTML = `${escapeHtml(msg.body)}<span class="nx-stream-caret" aria-hidden="true"></span>`;
    const inner = document.querySelector(".nx-main-inner");
    if (inner) inner.scrollTop = inner.scrollHeight;
  };

  try {
    const r = await fetch("/api/messages/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: messageForAgent, workspace_id: workspaceId }),
    });
    if (!r.ok || !r.body) return false;

    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    let sawDone = false;

    let done = false;
    while (!done) {
      const { value, done: readerDone } = await reader.read();
      done = readerDone;
      if (value) buf += decoder.decode(value, { stream: true });
      let sep;
      while ((sep = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, sep);
        buf = buf.slice(sep + 2);
        for (const line of frame.split("\n")) {
          if (!line.startsWith("data: ")) continue;
          let ev;
          try { ev = JSON.parse(line.slice(6)); } catch { continue; }
          if (ev.type === "chunk") {
            const m = ensureMsg(ev.module);
            if (ev.module) m.agent = ev.module;
            m.body += ev.content || "";
            paintChunk();
          } else if (ev.type === "done") {
            sawDone = true;
            const m = ensureMsg(ev.module);
            if (ev.module) m.agent = ev.module;
            m.memory_id = ev.memory_id || null;
            m.streaming = false;
          } else if (ev.type === "error") {
            throw new Error(ev.detail || "stream error");
          }
        }
      }
    }

    if (!sawDone && !msg) return false;  // stream produced nothing usable
    if (msg) msg.streaming = false;       // finalize even on a truncated stream
    state.thread.set(workspaceId, thread);
    renderConversation(workspaceId);      // full render → markdown pipeline
    loadTrust().then(() => loadPermissions()).then(renderCockpitRail);
    return true;
  } catch {
    // Roll back any partial streamed bubble so the fallback path doesn't
    // duplicate the reply. If the bubble had already consumed the typing
    // placeholder, reinstate it so the fallback POST still shows the
    // system thinking.
    if (msg) {
      const i = thread.indexOf(msg);
      if (i >= 0) thread.splice(i, 1);
      if (!thread.some(m => m.id === typingId)) {
        thread.push({ id: typingId, role: "agent", agent: msg.agent || "council", body: "", ts: new Date().toISOString(), typing: true });
      }
      state.thread.set(workspaceId, thread);
      renderConversation(workspaceId);
    }
    return false;
  }
}

// ── Main view: workspaces grid (no active workspace) ──────────────────────
function renderWorkspacesGrid() {
  const main = document.getElementById("nx-main");
  if (!state.workspaces.length) {
    main.innerHTML = `
      <div class="nx-main-inner">
        <div class="nx-welcome">
          <div class="nx-welcome-orb">${KERNEL_MARK(44)}</div>
          <h1>Welcome to ONEXUS</h1>
          <p>An operating system for agents. Each room, a workspace, has its own
             agents, memory and grants. Create your first one to get started.</p>
          <button class="nx-welcome-cta nx-btn nx-btn-primary nx-btn-lg" id="nx-welcome-create" type="button">${icon("plus", 16)}Create your first workspace<span class="nx-kbd">⌘N</span></button>
        </div>
      </div>
    `;
    document.getElementById("nx-welcome-create").addEventListener("click", openNewWorkspaceForm);
    return;
  }
  const tiles = state.workspaces.map(w => {
    const tone = (w.tone || "indigo").toLowerCase();
    const isActive = w.workspace_id === state.active;
    const agents = Math.max((state.workspaceAgentCounts || {})[w.workspace_id] || 0, (w.resident_agents || []).length);
    return `
    <div class="nx-ws-tile nx-tone-${escapeHtml(tone)} ${isActive ? "active" : ""}" role="button" tabindex="0"
         data-id="${w.workspace_id}" style="--tone:var(--nx-tone-${escapeHtml(tone)}-a, var(--nx-accent));--tone-b:var(--nx-tone-${escapeHtml(tone)}-b, var(--nx-accent-strong))" aria-label="Open workspace ${escapeHtml(w.name)}">
      <div class="tile-top">
        <span class="tile-swatch" aria-hidden="true">${workspaceEmblem(w, 36)}</span>
        ${isActive ? `<span class="nx-status is-live">Active</span>` : ""}
      </div>
      <div class="tile-name">${escapeHtml(w.name)}</div>
      <div class="tile-eyebrow">${escapeHtml(tone.charAt(0).toUpperCase() + tone.slice(1))} · ${agents} agent${agents === 1 ? "" : "s"}</div>
      <div class="tile-footer">
        <div class="disc-stack">
          ${(w.resident_agents || []).slice(0, 3).map(a => agentDisc(a, { size: 22 })).join("")}
        </div>
        <span class="tile-seen">
          ${isActive ? "Open now" : (w.last_active_at ? `Seen ${escapeHtml(chatHistoryRelative(w.last_active_at))}` : "Not opened yet")}
        </span>
      </div>
    </div>
  `;
  }).join("");
  main.innerHTML = `
    <div class="nx-main-inner">
      <header class="nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Rooms</div>
          <h1 class="nx-page-title">Workspaces</h1>
          <p class="nx-page-sub">
            ${state.workspaces.length} workspace${state.workspaces.length === 1 ? "" : "s"}. Press ⌘K to switch, ⌘N for a new one.
          </p>
        </div>
        <div class="nx-page-actions">
          <button class="nx-btn nx-btn-primary" id="nx-head-new-workspace" type="button">${icon("plus", 16)}New workspace</button>
        </div>
      </header>
      <div class="nx-ws-grid">
        ${tiles}
        <button class="nx-ws-tile new" id="nx-inline-new-workspace" type="button">
          ${icon("plus", 20)}
          <span>New workspace</span>
        </button>
      </div>
    </div>
  `;
  document.getElementById("nx-head-new-workspace")?.addEventListener("click", openNewWorkspaceForm);
  main.querySelectorAll(".nx-ws-tile[data-id]").forEach(el => {
    const open = async () => {
      await fetch(`/api/workspaces/${el.dataset.id}/switch`, { method: "POST" });
      await loadWorkspaces();
      renderSidebar();
      location.hash = `#/conversation/${el.dataset.id}`;
    };
    el.addEventListener("click", open);
    el.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(); } });
  });
  document.getElementById("nx-inline-new-workspace").addEventListener("click", openNewWorkspaceForm);
}

// ── Main view: agent store ────────────────────────────────────────────────
//
// Agents from the catalog that a program proved install: each was built from its
// published package, started in a locked-down container and asked for its tools over
// MCP (ONEXUS-Agents pipeline/recipes). Installing builds or downloads that image, checks
// it again on this machine, and records it; launching runs it with none of your files
// and only the hosts you approve. Backed by /api/store.

// Taglines come from upstream repositories; the store shows them without emoji.
const noEmoji = (t) => String(t || "").replace(/[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu, "").replace(/\s{2,}/g, " ").trim();
const KIND_LABEL = { npm: "npm package", pypi: "PyPI package", oci: "Container image" };
const FROM_LABEL = { "server.json": "its server.json", "readme-config": "its README's MCP config", "package-manifest": "its package manifest" };

function storeHeaderHTML(title, sub, actions = "") {
  return `<header class="nx-page-head">
      <div class="nx-page-head-text">
        <div class="nx-eyebrow nx-page-eyebrow">Agent store</div>
        <h1 class="nx-page-title">${title}</h1>
        ${sub ? `<p class="nx-page-sub">${sub}</p>` : ""}
      </div>
      ${actions ? `<div class="nx-page-actions">${actions}</div>` : ""}
    </header>`;
}

async function renderStore(hash) {
  const slug = decodeURIComponent((hash.match(/^#\/store\/([^?]+)/) || [])[1] || "");
  if (slug) return renderStoreAgent(slug);
  const main = document.getElementById("nx-main");
  const params = new URLSearchParams(hash.split("?")[1] || "");
  const q = params.get("q") || "";
  const show = params.get("show") === "installed" ? "installed" : "all";
  main.innerHTML = `<div class="nx-main-inner">
      ${storeHeaderHTML(`<span class="nx-skeleton nx-skeleton-title"></span>`, "")}
      <div class="nx-store-grid" aria-busy="true">${Array.from({ length: 6 }, () => `<div class="nx-card nx-card-pad"><span class="nx-skeleton nx-skeleton-avatar"></span><span class="nx-skeleton nx-skeleton-title"></span><span class="nx-skeleton nx-skeleton-line"></span></div>`).join("")}</div>
    </div>`;
  let body;
  try {
    const r = await fetch(`/api/store/agents?q=${encodeURIComponent(q)}`);
    body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `the store answered ${r.status}`);
  } catch (e) {
    main.innerHTML = `<div class="nx-main-inner">${storeHeaderHTML("Install an agent", "")}
      <div class="nx-alert is-danger" role="alert">${icon("alert-circle", 16)}<div class="nx-alert-body"><div class="nx-alert-title">Could not load the store</div>${escapeHtml(e.message)}</div></div></div>`;
    return;
  }
  const all = body.agents || [];
  const installedCount = all.filter(a => a.installed).length;
  const agents = show === "installed" ? all.filter(a => a.installed) : all;
  const s = body.summary || {};
  const sub = `${s.verified_installable ?? all.length} agents that were built from their published package, started in a locked-down container and asked for their tools. Each one runs with none of your files and only the hosts you approve.`;
  main.innerHTML = `<div class="nx-main-inner">
      ${storeHeaderHTML("Install an agent", sub, `<a class="nx-btn nx-btn-ghost" href="#/catalog">${icon("grid", 16)}Browse the whole catalog</a>`)}
      <form class="nx-toolbar nx-store-filters" id="nx-store-filters" role="search">
        <div class="nx-search-field nx-store-search">
          ${icon("search", 14)}
          <input type="search" id="nx-store-q" class="nx-input" value="${escapeHtml(q)}" placeholder="Search by name, purpose or tool" aria-label="Search the store">
        </div>
        <div class="nx-store-show" role="group" aria-label="Show">
          <button type="button" class="nx-chip" data-show="all" aria-pressed="${show === "all"}">All ${all.length}</button>
          <button type="button" class="nx-chip" data-show="installed" aria-pressed="${show === "installed"}">Installed ${installedCount}</button>
        </div>
      </form>
      ${agents.length ? `<div class="nx-store-grid">${agents.map(storeCardHTML).join("")}</div>`
        : emptyStateHTML(show === "installed" && !q
          ? { icon: "package", title: "Nothing installed yet", body: "Pick an agent from the store to install it. It runs confined, and you choose what it can reach.", actions: `<a class="nx-btn" href="#/store">See all agents</a>` }
          : { icon: "search", title: "No agents match", body: `Nothing in the store matches “${escapeHtml(q)}”. The whole catalog has more, though most of it can't be installed by a program yet.`, actions: `<a class="nx-btn" href="#/store">Clear the search</a> <a class="nx-btn nx-btn-ghost" href="#/catalog?q=${encodeURIComponent(q)}">Search the catalog</a>` })}
      ${s.without_recipe != null ? `<p class="nx-store-note">${(s.entries_read || 0).toLocaleString()} catalog agents say they speak MCP. ${s.recipes} had an install a program could read exactly, and ${s.verified_installable} passed the check. The rest are apps that use MCP, or need something only their author can fill in.</p>` : ""}
    </div>`;
  const go = (next) => {
    const p = new URLSearchParams();
    const val = document.getElementById("nx-store-q").value.trim();
    if (val) p.set("q", val);
    if (next === "installed") p.set("show", "installed");
    location.hash = `#/store${p.toString() ? "?" + p : ""}`;
  };
  document.getElementById("nx-store-filters").addEventListener("submit", (e) => { e.preventDefault(); go(show); });
  const qEl = document.getElementById("nx-store-q");
  qEl.addEventListener("input", debounceCortexInput(() => go(show), 300));
  if (q) { qEl.focus(); qEl.setSelectionRange(q.length, q.length); }
  main.querySelectorAll(".nx-store-show [data-show]").forEach(b => b.addEventListener("click", () => go(b.dataset.show)));
}

function storeCardHTML(a) {
  const stars = fmtCount(a.stars);
  return `<a class="nx-card nx-card-pad nx-card-interactive nx-store-card nx-agent-tinted" href="#/store/${encodeURIComponent(a.slug)}" style="${agentTintStyle(a.slug)}">
      <div class="nx-store-card-head">
        ${agentDisc(a.slug, { size: 48 })}
        <div class="nx-store-card-id">
          <div class="nx-card-title">${escapeHtml(a.name)}</div>
          <div class="nx-card-sub">${escapeHtml((a.category || "").replace(/-/g, " "))}</div>
        </div>
        ${a.installed ? `<span class="nx-status is-ok">Installed</span>` : ""}
      </div>
      <p class="nx-store-card-tag">${escapeHtml(noEmoji(a.tagline))}</p>
      <div class="nx-store-card-facts">
        <span class="nx-pill nx-pill-mono">${a.tools.length} ${a.tools.length === 1 ? "tool" : "tools"}</span>
        <span class="nx-pill">${escapeHtml(KIND_LABEL[a.kind] || a.kind)}</span>
        ${a.needs_keys.length ? `<span class="nx-pill nx-pill-warn">Needs ${a.needs_keys.length === 1 ? "a key" : a.needs_keys.length + " keys"}</span>` : ""}
        ${stars ? `<span class="nx-card-stars" title="GitHub stars">${STAR_GLYPH}${stars}</span>` : ""}
      </div>
    </a>`;
}

async function renderStoreAgent(slug) {
  const main = document.getElementById("nx-main");
  main.innerHTML = `<div class="nx-main-inner" aria-busy="true"><span class="nx-skeleton nx-skeleton-title"></span><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-line"></span></div>`;
  let a;
  try {
    const r = await fetch(`/api/store/agents/${encodeURIComponent(slug)}`);
    a = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(a.detail || `the store answered ${r.status}`);
  } catch (e) {
    main.innerHTML = `<div class="nx-main-inner">${storeHeaderHTML(escapeHtml(slug), "")}
      <div class="nx-alert is-danger" role="alert">${icon("alert-circle", 16)}<div class="nx-alert-body"><div class="nx-alert-title">Could not load this agent</div>${escapeHtml(e.message)}</div></div>
      <a class="nx-btn" href="#/store">${icon("arrow-left", 16)}Back to the store</a></div>`;
    return;
  }
  const v = a.verified || {};
  const inst = a.install || {};
  const what = inst.kind === "oci" ? `${inst.image}` : `${inst.package}@${inst.version}`;
  const commit = (a.source || {}).commit || "";
  const hosts = (a.hosts || {}).proposed || [];
  const evidence = (a.hosts || {}).evidence || {};
  const rec = a.record;
  const tools = v.tools || [];
  const actions = rec
    ? `<button class="nx-btn nx-btn-primary" type="button" id="nx-store-launch">${icon("play", 16)}Launch</button>
       <button class="nx-btn nx-btn-danger" type="button" id="nx-store-remove">${icon("trash", 16)}Remove</button>`
    : a.installable
      ? `<button class="nx-btn nx-btn-primary" type="button" id="nx-store-install">${icon("download", 16)}Install</button>`
      : `<span class="nx-status is-warn">Not installable</span>`;
  main.innerHTML = `<div class="nx-main-inner nx-store-detail">
      <a class="nx-link nx-store-back" href="#/store">${icon("arrow-left", 14)}Agent store</a>
      <header class="nx-detail-head nx-agent-hero" style="${agentTintStyle(a.slug)}">
        ${agentDisc(a.slug, { size: 72 })}
        <div class="nx-detail-text">
          <h1 class="nx-detail-title">${escapeHtml(a.name)}</h1>
          <p class="nx-detail-sub">${escapeHtml(noEmoji(a.tagline))}</p>
          <div class="nx-detail-facts">
            ${rec ? `<span class="nx-status is-ok">Installed</span>` : ""}
            <span class="nx-pill">${escapeHtml(a.license || "Unknown license")}</span>
            ${a.stars ? `<span class="nx-card-stars">${STAR_GLYPH}${fmtCount(a.stars)}</span>` : ""}
            ${a.repo ? `<a class="nx-link" href="https://github.com/${escapeHtml(a.repo)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.repo)}${icon("external-link", 12)}</a>` : ""}
          </div>
        </div>
        <div class="nx-detail-actions">${actions}</div>
      </header>
      <div id="nx-store-msg"></div>
      <div class="nx-store-sections">
        <section class="nx-panel">
          <div class="nx-section-head"><div class="nx-section-label">Tools it offers, ${tools.length}</div></div>
          <ul class="nx-list nx-store-tools">${tools.slice(0, 14).map(t => `<li class="nx-row"><span class="nx-code-inline">${escapeHtml(t)}</span></li>`).join("")}</ul>
          ${tools.length > 14 ? `<button class="nx-btn nx-btn-ghost nx-btn-sm" type="button" id="nx-store-more">Show all ${tools.length}</button>` : ""}
        </section>
        <section class="nx-panel">
          <div class="nx-section-head"><div class="nx-section-label">Network</div></div>
          ${hosts.length ? `<p class="nx-store-p">It talks to these, found in its own code. You choose which to allow when you install; nothing else is reachable.</p>
            <ul class="nx-list nx-store-hosts">${hosts.map(h => `<li class="nx-row"><div class="nx-row-main"><div class="nx-row-title nx-code-inline">${escapeHtml(h)}</div><div class="nx-row-sub">${escapeHtml((evidence[h] || []).join(", "))}</div></div>${rec && rec.hosts.includes(h) ? `<span class="nx-status is-ok">Allowed</span>` : ""}</li>`).join("")}</ul>`
          : `<p class="nx-store-p">No hosts found in its code, so it installs with no network at all.</p>`}
          <div class="nx-section-head"><div class="nx-section-label">Keys</div></div>
          ${(a.env || []).length ? `<ul class="nx-list">${a.env.map(e => `<li class="nx-row"><div class="nx-row-main"><div class="nx-row-title nx-code-inline">${escapeHtml(e.name)}</div>${e.description ? `<div class="nx-row-sub">${escapeHtml(e.description)}</div>` : ""}</div><span class="nx-pill ${e.required ? "nx-pill-warn" : ""}">${e.required ? "Required" : "Optional"}</span>${rec && rec.keys_given.includes(e.name) ? `<span class="nx-status is-ok">Saved</span>` : ""}</li>`).join("")}</ul>`
          : `<p class="nx-store-p">It doesn't need any keys.</p>`}
        </section>
        <section class="nx-panel nx-store-how">
          <div class="nx-section-head"><div class="nx-section-label">How it runs</div></div>
          <dl class="nx-kv">
            <div class="nx-kv-pair"><dt class="nx-kv-key">Installs</dt><dd class="nx-kv-val"><span class="nx-code-inline">${escapeHtml(what)}</span>, ${escapeHtml(KIND_LABEL[inst.kind] || "")}</dd></div>
            <div class="nx-kv-pair"><dt class="nx-kv-key">Recipe</dt><dd class="nx-kv-val">Read from ${escapeHtml(FROM_LABEL[a.derived_from] || "its repository")}${commit ? ` at <a class="nx-link" href="https://github.com/${escapeHtml(a.repo || "")}/commit/${escapeHtml(commit)}" target="_blank" rel="noopener noreferrer"><span class="nx-code-inline">${escapeHtml(commit.slice(0, 7))}</span></a>` : ""}</dd></div>
            <div class="nx-kv-pair"><dt class="nx-kv-key">Checked</dt><dd class="nx-kv-val">${v.ok ? `Started confined and answered with ${tools.length} tools${v.at ? `, ${escapeHtml(new Date(v.at).toLocaleDateString())}` : ""}` : escapeHtml(v.reason || "Not verified")}</dd></div>
            <div class="nx-kv-pair"><dt class="nx-kv-key">Sandbox</dt><dd class="nx-kv-val">None of your files, a read-only system, no extra privileges, 1 GB of memory</dd></div>
            ${rec ? `<div class="nx-kv-pair"><dt class="nx-kv-key">Installed</dt><dd class="nx-kv-val">${escapeHtml(new Date(rec.installed_at).toLocaleString())}</dd></div>` : ""}
          </dl>
        </section>
      </div>
    </div>`;
  const more = document.getElementById("nx-store-more");
  more?.addEventListener("click", () => {
    main.querySelector(".nx-store-tools").innerHTML = tools.map(t => `<li class="nx-row"><span class="nx-code-inline">${escapeHtml(t)}</span></li>`).join("");
    more.remove();
  });
  document.getElementById("nx-store-install")?.addEventListener("click", (e) => openStoreInstall(a, e.currentTarget));
  document.getElementById("nx-store-launch")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    btn.disabled = true; btn.setAttribute("aria-busy", "true");
    const r = await fetch(`/api/agents/${encodeURIComponent(a.slug)}/launch`, { method: "POST" }).catch(() => null);
    const out = r ? await r.json().catch(() => ({})) : {};
    btn.removeAttribute("aria-busy"); btn.disabled = false;
    storeMessage(r && r.ok
      ? { kind: "info", title: "Running, confined", body: `${a.name} is running in its container. It shows in Kernel watch and its calls go through Aegis.` }
      : { kind: "danger", title: "It didn't start", body: out.detail || out.message || "No answer from ONEXUS." });
  });
  const rm = document.getElementById("nx-store-remove");
  rm?.addEventListener("click", async () => {
    if (!rm.classList.contains("is-armed")) {
      rm.classList.add("is-armed");
      rm.innerHTML = `${icon("trash", 16)}Remove ${escapeHtml(a.name)}?`;
      setTimeout(() => { rm.classList.remove("is-armed"); rm.innerHTML = `${icon("trash", 16)}Remove`; }, 4000);
      return;
    }
    rm.disabled = true;
    const r = await fetch(`/api/store/agents/${encodeURIComponent(a.slug)}`, { method: "DELETE" }).catch(() => null);
    if (r && r.ok) renderStoreAgent(a.slug);
    else storeMessage({ kind: "danger", title: "Couldn't remove it", body: "ONEXUS didn't confirm the removal. Try again." });
  });
}

function storeMessage({ kind, title, body }) {
  const el = document.getElementById("nx-store-msg");
  if (!el) return;
  el.innerHTML = `<div class="nx-alert is-${kind}" ${kind === "danger" ? 'role="alert"' : 'role="status"'}>${icon(kind === "danger" ? "alert-circle" : "check", 16)}<div class="nx-alert-body"><div class="nx-alert-title">${escapeHtml(title)}</div>${escapeHtml(body)}</div></div>`;
}

// The install dialog: keys, then which hosts it may reach, then live progress. Hosts the
// agent's own declared keys point at start allowed; hosts found only in its code start off,
// so nothing is reachable unless the evidence or the person says so.
function openStoreInstall(a, opener) {
  const hosts = (a.hosts || {}).proposed || [];
  const evidence = (a.hosts || {}).evidence || {};
  const keyBacked = (h) => (evidence[h] || []).some(x => x.startsWith("env "));
  const wrap = document.createElement("div");
  wrap.className = "nx-scrim nx-store-overlay";
  wrap.innerHTML = `<div class="nx-modal" role="dialog" aria-modal="true" aria-labelledby="nx-si-title">
      <div class="nx-modal-head">
        <div><h2 class="nx-modal-title" id="nx-si-title">Install ${escapeHtml(a.name)}</h2>
        <p class="nx-modal-sub">It runs in a container with none of your files. Choose what it can reach.</p></div>
        <button class="nx-icon-btn" type="button" data-close aria-label="Close">${icon("x", 16)}</button>
      </div>
      <form class="nx-si-form" id="nx-si-form"><div class="nx-modal-body">
        ${(a.env || []).length ? `<div class="nx-section-label">Keys</div>
          ${a.env.map(e => `<label class="nx-field"><span class="nx-field-label">${escapeHtml(e.name)}${e.required ? "" : " (optional)"}</span>
            <input class="nx-input nx-input-mono" name="env:${escapeHtml(e.name)}" type="${e.secret ? "password" : "text"}" autocomplete="off" ${e.required ? "required" : ""}>
            ${e.description ? `<span class="nx-field-hint">${escapeHtml(e.description)}</span>` : ""}</label>`).join("")}
          <p class="nx-field-hint">Kept in a file only your user can read, given to this agent only, never logged.</p>` : ""}
        <div class="nx-section-label">Network access</div>
        ${hosts.length ? `<p class="nx-field-hint">Ticked hosts are ones its own keys point at. Without a host it still starts, but tools that need that host will fail. You can change this later.</p>
          <ul class="nx-list nx-si-hosts">${hosts.map(h => `<li class="nx-row"><label class="nx-check"><input type="checkbox" name="host" value="${escapeHtml(h)}" ${keyBacked(h) ? "checked" : ""}><span class="nx-code-inline">${escapeHtml(h)}</span></label><span class="nx-row-sub">${escapeHtml((evidence[h] || [])[0] || "")}</span></li>`).join("")}</ul>`
          : `<p class="nx-field-hint">No hosts found in its code. It will have no network.</p>`}
        <label class="nx-field"><span class="nx-field-label">Allow another host</span>
          <input class="nx-input nx-input-mono" name="extra" placeholder="api.example.com" autocomplete="off"></label>
        <div class="nx-alert is-danger" role="alert" id="nx-si-err" hidden></div>
        </div>
        <div class="nx-modal-foot">
          <button class="nx-btn nx-btn-ghost" type="button" data-close>Cancel</button>
          <button class="nx-btn nx-btn-primary" type="submit">${icon("download", 16)}Install</button>
        </div>
      </form>
    </div>`;
  document.body.appendChild(wrap);
  const modal = wrap.querySelector(".nx-modal");
  let polling = null;
  const close = () => { clearInterval(polling); wrap.remove(); document.removeEventListener("keydown", onKey); opener?.focus(); };
  const onKey = (e) => {
    if (e.key === "Escape") { e.preventDefault(); close(); return; }
    if (e.key !== "Tab") return;
    const f = [...modal.querySelectorAll("button, input, a[href]")].filter(x => !x.disabled && x.offsetParent);
    if (!f.length) return;
    if (e.shiftKey && document.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); }
    else if (!e.shiftKey && document.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
  };
  document.addEventListener("keydown", onKey);
  wrap.addEventListener("click", (e) => { if (e.target === wrap || e.target.closest("[data-close]")) close(); });
  (modal.querySelector("input") || modal.querySelector("button[type=submit]")).focus();

  const form = modal.querySelector("#nx-si-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const env = {};
    for (const [k, val] of fd.entries()) if (k.startsWith("env:") && String(val).trim()) env[k.slice(4)] = String(val).trim();
    const chosen = fd.getAll("host").map(String);
    const extra = String(fd.get("extra") || "").trim().toLowerCase();
    if (extra) chosen.push(extra);
    const err = modal.querySelector("#nx-si-err");
    const btn = form.querySelector("button[type=submit]");
    btn.disabled = true; btn.setAttribute("aria-busy", "true");
    const r = await fetch(`/api/store/agents/${encodeURIComponent(a.slug)}/install`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ hosts: chosen, env }),
    }).catch(() => null);
    const job = r ? await r.json().catch(() => ({})) : {};
    if (!r || !r.ok) {
      btn.disabled = false; btn.removeAttribute("aria-busy");
      err.hidden = false;
      err.innerHTML = `${icon("alert-circle", 16)}<div class="nx-alert-body"><div class="nx-alert-title">Can't install yet</div>${escapeHtml(job.detail || "No answer from ONEXUS.")}</div>`;
      return;
    }
    showProgress(job);
    polling = setInterval(async () => {
      const s = await fetch(`/api/store/jobs/${job.id}`).then(x => x.json()).catch(() => null);
      if (!s) return;
      showProgress(s);
      if (s.state !== "running") clearInterval(polling);
    }, 700);
  });

  const STEP_LABEL = { get: "Get the image", check: "Start it confined and ask for its tools", save: "Save the install" };
  function showProgress(job) {
    const steps = job.steps.map((st, i) => `<li class="nx-step ${st.status === "done" ? "is-done" : st.status === "running" ? "is-active" : st.status === "failed" ? "is-error" : ""}">
        <span class="nx-step-marker">${st.status === "done" ? icon("check", 12) : st.status === "failed" ? icon("x", 12) : i + 1}</span>
        <div><div class="nx-step-label">${STEP_LABEL[st.name] || st.name}</div>${st.detail ? `<div class="nx-step-detail">${escapeHtml(st.detail)}</div>` : ""}</div>
        <span class="nx-step-meta">${st.status === "running" ? "working" : ""}</span></li>`).join("");
    const done = job.state === "done", failed = job.state === "failed";
    (modal.querySelector("#nx-si-form") || modal.querySelector(".nx-si-progress")).outerHTML = `<div class="nx-si-progress"><div class="nx-modal-body" aria-live="polite">
        <ol class="nx-steps">${steps}</ol>
        ${done ? `<div class="nx-alert is-info" role="status">${icon("check", 16)}<div class="nx-alert-body"><div class="nx-alert-title">Installed</div>It offered ${job.tools.length} tools. Launch it here or from Cortex.</div></div>` : ""}
        ${failed ? `<div class="nx-alert is-danger" role="alert">${icon("alert-circle", 16)}<div class="nx-alert-body"><div class="nx-alert-title">The install stopped</div>${escapeHtml(job.error)} Nothing was saved.</div></div>` : ""}
        </div>
        <div class="nx-modal-foot">
          ${done ? `<button class="nx-btn nx-btn-primary" type="button" id="nx-si-done">Done</button>`
            : failed ? `<button class="nx-btn" type="button" data-close>Close</button>`
            : `<button class="nx-btn nx-btn-ghost" type="button" data-close>Hide, keep installing</button>`}
        </div>
      </div>`;
    modal.querySelector("#nx-si-done")?.addEventListener("click", () => { close(); renderStoreAgent(a.slug); });
    (modal.querySelector("#nx-si-done") || modal.querySelector("[data-close]"))?.focus();
  }
}

// ── Main view: catalog (spatial grid) ─────────────────────────────────────
async function renderCatalog() {
  const main = document.getElementById("nx-main");
  main.innerHTML = `<div class="nx-main-inner">
      <header class="nx-page-head"><div class="nx-page-head-text">
        <div class="nx-eyebrow nx-page-eyebrow">Agent store</div>
        <span class="nx-skeleton nx-skeleton-title"></span><span class="nx-skeleton nx-skeleton-short"></span>
      </div></header>
      <div class="nx-spatial" aria-busy="true">${Array.from({ length: 6 }, () => `<div class="nx-spatial-card nx-card"><span class="nx-skeleton nx-skeleton-avatar"></span><span class="nx-skeleton nx-skeleton-title"></span><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-short"></span></div>`).join("")}</div>
    </div>`;
  // Parse hash for filters
  const filters = {};
  (location.hash.split("?")[1] || "").split("&").forEach(p => {
    const [k,v] = p.split("=");
    if (k && v) filters[decodeURIComponent(k)] = decodeURIComponent(v);
  });
  const runnableOnly = filters.runnable !== "0";
  const category = filters.category || "";
  const search = filters.q || "";
  try {
    const params = new URLSearchParams();
    params.set("limit", "48");
    if (runnableOnly) params.set("runnable_only", "true");
    if (category) params.set("category", category);
    const endpoint = search ? `/api/agents/search?q=${encodeURIComponent(search)}&limit=48` : `/api/agents?${params}`;
    // Which catalog agents the store can install, and which are installed (optional: the
    // catalog still renders if the store is unavailable).
    const storeP = fetch("/api/store/agents").then(x => x.ok ? x.json() : { agents: [] }).catch(() => ({ agents: [] }));
    const r = await fetch(endpoint);
    if (!r.ok) throw new Error("catalog fetch failed");
    const body = await r.json();
    const agents = body.agents || [];
    const cats = body.categories || [];
    const store = new Map(((await storeP).agents || []).map(x => [x.slug, x]));
    agents.forEach(a => { a._store = store.get(a.slug) || null; });
    main.innerHTML = `
      <div class="nx-main-inner">
        <header class="nx-spatial-header nx-page-head">
          <div class="nx-page-head-text">
            <div class="nx-eyebrow nx-page-eyebrow">Agent catalog</div>
            <h1 class="nx-page-title">${(state.catalogTotal || body.total || 0).toLocaleString()} agents in the catalog</h1>
            <p class="nx-page-sub">${search ? `${agents.length} matching “${escapeHtml(search)}” across the whole catalog` : `Showing ${agents.length} ${category ? "in " + escapeHtml(category.replace(/-/g, " ")) : "featured"}, ranked by ONEXUS benchmark score`}${runnableOnly && !search ? ", only the ones that declare MCP" : ""}. <a class="nx-link" href="#/store">${store.size} install in one click</a>.</p>
          </div>
        </header>
        <form class="nx-cat-filters nx-toolbar" id="nx-cat-filters" role="search">
          <div class="nx-search-field nx-cat-search">
            ${icon("search", 14)}
            <input type="search" id="nx-cat-q" class="nx-input" value="${escapeHtml(search)}" placeholder="Search the catalog" aria-label="Search the catalog">
          </div>
          <select id="nx-cat-cat" class="nx-select" aria-label="Category">
            <option value="">All categories</option>
            ${cats.map(c => `<option value="${escapeHtml(c)}" ${c===category?"selected":""}>${escapeHtml(c.replace(/-/g, " "))}</option>`).join("")}
          </select>
          <label class="nx-cat-toggle nx-check">
            <input type="checkbox" id="nx-cat-runnable" ${runnableOnly?"checked":""}>
            Declares MCP only
          </label>
        </form>
        ${agents.length ? `<div class="nx-spatial">
          ${agents.map(renderCatalogCard).join("")}
        </div>` : emptyStateHTML({ icon: "search", title: "No agents match", body: search ? `Nothing in the catalog matches “${escapeHtml(search)}”. Try a shorter word or clear the filters.` : "No agents in this category yet. Try another category or turn off Declares MCP only.", actions: `<a class="nx-btn" href="#/catalog">Clear filters</a>` })}
      </div>
    `;
    // Wire filter changes
    const applyFilters = () => {
      const q = document.getElementById("nx-cat-q").value.trim();
      const cat = document.getElementById("nx-cat-cat").value;
      const run = document.getElementById("nx-cat-runnable").checked;
      const params = new URLSearchParams();
      if (q) params.set("q", q);
      if (cat) params.set("category", cat);
      params.set("runnable", run ? "1" : "0");
      location.hash = `#/catalog?${params}`;
    };
    document.getElementById("nx-cat-filters").addEventListener("submit", (e) => { e.preventDefault(); applyFilters(); });
    document.getElementById("nx-cat-cat").addEventListener("change", applyFilters);
    document.getElementById("nx-cat-runnable").addEventListener("change", applyFilters);
    // Live search across the WHOLE catalog (server-side), debounced so it
    // fires as you type — not just on Enter.
    const qEl = document.getElementById("nx-cat-q");
    qEl.addEventListener("input", debounceCortexInput(applyFilters, 300));
    // The live search re-renders the page; keep the cursor in the search box.
    if (search) {
      qEl.focus();
      qEl.setSelectionRange(qEl.value.length, qEl.value.length);
    }
    // Wire card actions
    main.querySelectorAll(".nx-spatial-card[data-slug]").forEach(card => {
      const slug = card.dataset.slug;
      card.querySelector(".trust-btn")?.addEventListener("click", (e) => {
        e.stopPropagation();
        openCapabilitySheet(slug);
      });
      // Catalog → Compose: pre-select this agent in the Cortex launcher.
      card.querySelector(".compose-btn")?.addEventListener("click", (e) => {
        e.stopPropagation();
        location.hash = `#/cortex?agent=${encodeURIComponent(slug)}`;
      });
      card.querySelector(".launch-btn")?.addEventListener("click", async (e) => {
        e.stopPropagation();
        const btn = e.currentTarget;
        btn.disabled = true;
        btn.textContent = "Launching";
        btn.setAttribute("aria-busy", "true");
        try {
          const r = await fetch(`/api/agents/${encodeURIComponent(slug)}/launch`, { method: "POST" });
          const body = await r.json().catch(() => ({}));
          btn.textContent = r.ok ? "Running" : (body.detail || body.message || "Failed");
          if (r.ok) btn.classList.add("on");
        } catch (e) {
          btn.textContent = "Error";
        } finally {
          btn.removeAttribute("aria-busy");
          setTimeout(() => { btn.disabled = false; }, 1200);
        }
      });
    });
  } catch (e) {
    main.innerHTML = `<div class="nx-main-inner">
      <header class="nx-page-head"><div class="nx-page-head-text"><div class="nx-eyebrow nx-page-eyebrow">Agent store</div><h1 class="nx-page-title">Catalog</h1></div></header>
      <div class="nx-alert is-danger" role="alert">${icon("alert-circle", 16)}<div class="nx-alert-body"><div class="nx-alert-title">Could not load the catalog</div>${escapeHtml(e.message)}. Check that the ONEXUS-Agents catalog is available, then reload.</div></div>
    </div>`;
  }
}

// Compact number formatting for app-store pedigree (1234 → 1.2k, 145000 → 145k).
function fmtCount(n) {
  if (n == null) return null;
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + "m";
  if (n >= 1000) return (n / 1000).toFixed(n >= 10_000 ? 0 : 1) + "k";
  return String(n);
}
const STAR_GLYPH = icon("star", 12);

function renderCatalogCard(a) {
  // Launch only where launching works: built-in agents, store installs and hand-written
  // adapters. "runnable" in the catalog only means the agent says it speaks MCP.
  const st = a._store;
  const launchable = a.is_builtin || (st && st.installed) || (a.adapter_ref || "").startsWith("adapters/");
  const status = a.is_builtin ? ["is-ok", "Built in"] : st ? (st.installed ? ["is-ok", "Installed"] : ["is-info", "Installs"])
    : launchable ? ["is-ok", "Adapter"] : a.runnable ? ["", "Declares MCP"] : ["", "Listed"];
  // ONEXUS benchmark pedigree — the grading that turns a catalog into an app store.
  const score = typeof a.composite_score === "number" ? a.composite_score : null;
  const scorePct = score != null ? Math.round(score * 100) : null;
  const stars = fmtCount(a.stars);
  const rank = a.rank_in_category;
  return `
    <div class="nx-spatial-card nx-card nx-agent-tinted" data-slug="${escapeHtml(a.slug)}" style="${agentTintStyle(a.slug)}">
      <div class="nx-card-top">
        ${agentDisc(a.slug, { size: 48, trust: a.trust_floor ?? null })}
        ${rank != null && rank <= 3 ? `<span class="nx-card-rank nx-pill nx-pill-warn" title="Rank ${rank} in ${escapeHtml(a.category || "category")}">#${rank} in category</span>` : ""}
      </div>
      <div class="name">${escapeHtml(a.name || a.slug)}</div>
      <div class="tagline">${escapeHtml(noEmoji(a.tagline || a.description || ""))}</div>
      ${score != null ? `
        <div class="nx-card-bench" title="ONEXUS benchmark score ${score.toFixed(3)}">
          <span class="nx-card-bench-lbl">Benchmark</span>
          <div class="nx-card-bench-track nx-meter"><div class="nx-card-bench-fill nx-meter-fill" style="width:${scorePct}%"></div></div>
          <span class="nx-card-bench-val">${score.toFixed(2)}</span>
        </div>` : ""}
      <div class="status">
        <span class="nx-status ${status[0]}">${status[1]}</span>
        ${stars ? `<span class="nx-card-stars" title="GitHub stars">${STAR_GLYPH}${stars}</span>` : ""}
        <span class="badge-system">${escapeHtml((a.category || "").replace(/-/g, " "))}</span>
      </div>
      <div class="nx-card-actions">
        ${launchable ? `<button class="launch-btn nx-btn nx-btn-sm" type="button">${icon("play", 12)}Launch</button>`
          : st ? `<a class="nx-btn nx-btn-sm nx-btn-tinted" href="#/store/${encodeURIComponent(a.slug)}">${icon("download", 12)}Install</a>` : ""}
        <button class="compose-btn nx-btn nx-btn-sm nx-btn-ghost" type="button" title="Add to a Cortex launch">Compose</button>
        <button class="trust-btn nx-btn nx-btn-sm nx-btn-ghost" type="button" title="Open the trust sheet">Trust</button>
        ${a.source_github ? `<a class="src-link nx-icon-btn" href="https://github.com/${escapeHtml(a.source_github)}" target="_blank" rel="noopener noreferrer" title="Source on GitHub" aria-label="Source on GitHub">${icon("external-link", 14)}</a>` : ""}
      </div>
    </div>
  `;
}

// ── Main view: settings ───────────────────────────────────────────────────
async function renderSettings() {
  const main = document.getElementById("nx-main");
  main.innerHTML = `
    <div class="nx-main-inner">
      <header class="nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Configure</div>
          <h1 class="nx-page-title">Settings</h1>
          <p class="nx-page-sub">Local-first. Changes apply immediately and stay in your own data directory.</p>
        </div>
      </header>
      <div class="nx-settings-shell">
        <nav class="nx-settings-tabs nx-tabs nx-tabs-vertical" role="tablist" aria-label="Settings sections">
          <button class="nx-tab active" type="button" role="tab" aria-selected="true" data-tab="general">${icon("sliders", 16)}General</button>
          <button class="nx-tab" type="button" role="tab" aria-selected="false" data-tab="chat-history">${icon("message", 16)}Chat history</button>
          <button class="nx-tab" type="button" role="tab" aria-selected="false" data-tab="security">${icon("shield", 16)}Security</button>
          <button class="nx-tab" type="button" role="tab" aria-selected="false" data-tab="providers">${icon("cpu", 16)}Providers</button>
          <button class="nx-tab" type="button" role="tab" aria-selected="false" data-tab="federation">${icon("share", 16)}Federation</button>
          <button class="nx-tab" type="button" role="tab" aria-selected="false" data-tab="moods">${icon("contrast", 16)}Moods</button>
          <button class="nx-tab" type="button" role="tab" aria-selected="false" data-tab="about">${icon("info", 16)}About</button>
        </nav>
        <section class="nx-card nx-panel nx-settings-panel" id="nx-settings-panel" role="tabpanel"></section>
      </div>
    </div>
  `;
  const panel = document.getElementById("nx-settings-panel");
  const renderTab = async (tab) => {
    main.querySelectorAll(".nx-settings-tabs button").forEach(x => {
      x.classList.toggle("active", x.dataset.tab === tab);
      x.setAttribute("aria-selected", String(x.dataset.tab === tab));
    });
    // Stop chat-history's polling timer whenever we navigate away from it.
    stopChatHistoryRefresh();
    panel.innerHTML = SETTINGS_LOADING_HTML;
    if (tab === "chat-history") {
      await renderChatHistory(panel);
      return;
    }
    panel.innerHTML = await renderSettingsTab(tab);
    if (tab === "providers") {
      wireProvidersHandlers(panel);
    }
    // Wire any panel-specific handlers
    if (tab === "moods") {
      panel.querySelector("#nx-settings-mood-clear")?.addEventListener("click", () => {
        state.mood.override = null;
        if (state.mood.kernelMood) applyMood(state.mood.kernelMood);
        renderTab("moods");
      });
    }
    if (tab === "security") {
      const listEl = panel.querySelector("#nx-st-trust-list");
      const more = panel.querySelector("#nx-st-trust-more");
      const countEl = panel.querySelector("#nx-st-search-count");

      const wireRevokes = () => {
        listEl.querySelectorAll(".nx-st-revoke[data-module]").forEach(btn => {
          btn.addEventListener("click", async () => {
            const mod = btn.dataset.module;
            if (!confirm(`Reset ${mod}'s trust to 0.0 (revokes all grants)?`)) return;
            await fetch(`/api/trust/${encodeURIComponent(mod)}/adjust`, {
              method: "POST", headers: {"Content-Type":"application/json"},
              body: JSON.stringify({ delta: -1.0, reason: "user_revoke_settings" }),
            });
            renderTab("security");
          });
        });
      };
      wireRevokes();

      // Live filter — incrementally renders the matches
      const search = panel.querySelector("#nx-st-trust-search");
      search?.addEventListener("input", (e) => {
        const q = e.target.value.trim().toLowerCase();
        const all = state._securityModules || [];
        const matched = q
          ? all.filter(s => s.module.toLowerCase().includes(q))
          : all;
        // Cap rendering at 80 rows for perf
        const visible = matched.slice(0, 80);
        listEl.innerHTML = renderTrustRows(visible);
        if (countEl) countEl.textContent = matched.length;
        if (more) {
          more.style.display = matched.length > 80 ? "" : "none";
          more.textContent = matched.length > 80
            ? `Showing the first 80 of ${matched.length} matches. Narrow the search to see more.`
            : "";
        }
        wireRevokes();
      });
    }
  };
  main.querySelectorAll(".nx-settings-tabs button").forEach(b => {
    b.addEventListener("click", () => renderTab(b.dataset.tab));
  });
  renderTab("general");
}

const SETTINGS_LOADING_HTML = `<div aria-busy="true"><span class="nx-skeleton nx-skeleton-title"></span><span class="nx-skeleton nx-skeleton-short"></span><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-line"></span></div>`;

function renderTrustRows(rows) {
  if (!rows.length) return `<div class="nx-empty-line nx-st-nomatch">No modules match that search.</div>`;
  return rows.map(s => {
    const score = s.trust ?? 0;
    const tier = score >= 0.75 ? "EXECUTOR"
               : score >= 0.50 ? "MONITOR"
               : score >= 0.25 ? "ADVISOR" : "OBSERVER";
    return `
      <div class="nx-st-trust-row">
        <div class="nx-st-trust-name">${escapeHtml(s.module)}</div>
        <div class="nx-st-trust-bar nx-meter"><span class="nx-meter-fill" style="width:${(score * 100).toFixed(1)}%"></span></div>
        <div class="nx-st-trust-score">${score.toFixed(2)}</div>
        <div class="nx-st-trust-tier">${tier.charAt(0) + tier.slice(1).toLowerCase()}</div>
        <button class="nx-st-revoke nx-btn nx-btn-sm nx-btn-ghost" type="button" data-module="${escapeHtml(s.module)}">Revoke</button>
      </div>
    `;
  }).join("");
}

// ── Cortex launcher ──────────────────────────────────────────────────────
//
// Multi-agent dispatch surface. Type a prompt, pick one or more agents
// (Cortex pre-suggests its top picks), and the launcher fans the prompt
// to all selected agents in parallel. Each response renders as its own
// card with module name, latency, and a feedback affordance hooked into
// the same Aegis trust loop the home composer uses.
//
// Also reachable by typing "cortex <prompt>" into the home composer —
// sendMessage detects the keyword and routes here with the rest of the
// message pre-filled via ?prompt=...

const _cortexState = {
  prompt: "",
  candidates: null,         // { primary, top, all_modules, catalog_matches }
  selected: new Set(),      // agent slugs the user has ticked (built-in OR catalog)
  catalogSearch: "",        // live search text inside the picker
  catalogSearchResults: [], // chips fetched on demand via /api/cortex/agent-search
  catalogMeta: new Map(),   // slug → catalog entry metadata (for chip rendering)
  templates: [],            // curated swarm templates from /api/cortex/templates
  activeTemplate: null,     // id of the template the user last applied
  running: false,
  runs: null,
  lastError: null,          // { status, detail } — last failed dispatch, shown as role=alert banner
};

// Bespoke swarm-template glyphs — line-stroke, same language as icons.js.
const SWARM_TEMPLATE_ICONS = {
  research: icon("search", 16),
  build: icon("layers", 16),
  monitor: icon("activity", 16),
  negotiate: icon("flag", 16),
};

async function renderCortexLauncher(hash) {
  // Parse ?prompt= and ?agent= out of the hash.
  const qi = hash.indexOf("?");
  let prefill = "";
  let preselectAgent = "";
  if (qi >= 0) {
    const params = new URLSearchParams(hash.slice(qi + 1));
    prefill = params.get("prompt") || "";
    preselectAgent = params.get("agent") || "";
  }
  if (prefill && !_cortexState.prompt) {
    _cortexState.prompt = prefill;
  }
  // Pre-tick a single agent (from the sidebar's "resume this agent" click).
  // We need its metadata in catalogMeta so the chip renders even before
  // the prompt-driven candidates load — fetch the catalog entry if needed.
  if (preselectAgent) {
    _cortexState.selected.add(preselectAgent);
    if (!_cortexState.catalogMeta.has(preselectAgent)) {
      try {
        const r = await fetch(`/api/cortex/agent-search?q=${encodeURIComponent(preselectAgent)}&limit=5`);
        if (r.ok) {
          const data = await r.json();
          (data.matches || []).forEach(c => _cortexState.catalogMeta.set(c.slug, c));
        }
      } catch {}
    }
  }

  const main = document.getElementById("nx-main");
  main.innerHTML = `
    <div class="nx-main-inner">
      <header class="nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Cortex · multi-agent launcher</div>
          <h1 class="nx-page-title">Launch agents</h1>
          <p class="nx-page-sub">
            Write a prompt and pick one or many agents. Cortex suggests its top picks; tick the ones you want and dispatch them in parallel.
            You can also type <code class="nx-code-inline">cortex</code> followed by a prompt into the home composer to land here.
          </p>
        </div>
      </header>

      <section class="nx-swarm-templates" id="nx-swarm-templates" aria-label="Swarm templates"></section>

      <section class="nx-card nx-cortex-form" id="nx-cortex-form">
        <label class="nx-sr-only" for="nx-cortex-prompt">Prompt</label>
        <textarea
          id="nx-cortex-prompt"
          rows="3"
          class="nx-cortex-textarea"
          placeholder="What should the agents do?"
          autofocus>${escapeHtml(_cortexState.prompt)}</textarea>

        <div class="nx-cortex-pickers">
          <div class="nx-cortex-pickers-head">
            <div class="nx-section-label">Agents, pick one or many</div>
            <div class="nx-cortex-search nx-search-field">
              ${icon("search", 14)}
              <input id="nx-cortex-agent-search" type="search" class="nx-input"
                     placeholder="Search ${(state.catalogTotal || state.runnableCount || 0).toLocaleString()} catalog agents"
                     aria-label="Search catalog agents"
                     autocomplete="off" spellcheck="false">
            </div>
          </div>
          <div class="nx-eyebrow nx-cortex-sub-eyebrow">Built-in</div>
          <div class="nx-cortex-chips" id="nx-cortex-chips-builtin">
            <div class="nx-loading"><span class="nx-spinner" aria-hidden="true"></span>Loading agents</div>
          </div>
          <div id="nx-cortex-catalog-section" hidden>
            <div class="nx-eyebrow nx-cortex-sub-eyebrow" id="nx-cortex-catalog-heading">Catalog matches</div>
            <div class="nx-cortex-chips" id="nx-cortex-chips-catalog"></div>
          </div>
        </div>

        <div class="nx-cortex-actions">
          <button id="nx-cortex-run" class="nx-cortex-run nx-btn nx-btn-primary" type="button" disabled>
            <span class="nx-spinner" aria-hidden="true" hidden></span>
            <span class="nx-cortex-run-label">Pick agents to dispatch</span>
          </button>
          <button id="nx-cortex-top3" class="nx-cortex-pickbtn nx-btn nx-btn-ghost" type="button">${icon("sparkle", 14)}Pick top 3 for me</button>
          <button id="nx-cortex-all" class="nx-cortex-pickbtn nx-btn nx-btn-ghost" type="button">All built-ins</button>
          <button id="nx-cortex-clear" class="nx-cortex-pickbtn nx-btn nx-btn-ghost" type="button">Clear</button>
        </div>

        <div id="nx-cortex-error-slot"></div>
      </section>

      <section id="nx-cortex-results"></section>
    </div>
  `;

  const promptEl = document.getElementById("nx-cortex-prompt");
  const chipsEl = document.getElementById("nx-cortex-chips");
  const runBtn = document.getElementById("nx-cortex-run");
  const resultsEl = document.getElementById("nx-cortex-results");

  const refreshRunBtn = () => {
    const n = _cortexState.selected.size;
    runBtn.disabled = _cortexState.running || n === 0 || !(_cortexState.prompt.trim());
    const label = runBtn.querySelector(".nx-cortex-run-label");
    const spinner = runBtn.querySelector(".nx-spinner");
    if (spinner) spinner.hidden = !_cortexState.running;
    runBtn.classList.toggle("running", !!_cortexState.running);
    runBtn.setAttribute("aria-busy", String(!!_cortexState.running));
    if (_cortexState.running) {
      label.textContent = "Dispatching";
    } else if (n === 0) {
      label.textContent = "Pick agents to dispatch";
    } else if (!_cortexState.prompt.trim()) {
      label.textContent = "Write a prompt to dispatch";
    } else {
      label.textContent = `Dispatch to ${n} agent${n === 1 ? "" : "s"}`;
    }
  };

  // Prominent inline error banner — renders into the slot below the dispatch
  // actions whenever the LAST dispatch failed outright (HTTP error or network
  // failure). role="alert" so screen readers announce it immediately.
  const renderLauncherError = () => {
    const slot = document.getElementById("nx-cortex-error-slot");
    if (!slot) return;
    const err = _cortexState.lastError;
    if (!err) { slot.innerHTML = ""; return; }
    const text = err.status
      ? `HTTP ${err.status}: ${err.detail || "no detail"}`
      : (err.detail || "unknown error");
    slot.innerHTML = `
      <div class="nx-cortex-error nx-alert is-danger" role="alert">
        ${icon("alert-circle", 16)}
        <div class="nx-alert-body">
          <span class="nx-cortex-error-badge nx-alert-title">DISPATCH FAILED</span>
          <span class="nx-cortex-error-text">${escapeHtml(text)}</span>
        </div>
        <button type="button" class="nx-cortex-error-dismiss nx-icon-btn" aria-label="Dismiss error">${UI.close(14)}</button>
      </div>
    `;
    slot.querySelector(".nx-cortex-error-dismiss")?.addEventListener("click", () => {
      _cortexState.lastError = null;
      renderLauncherError();
    });
  };

  const renderChips = () => {
    const cands = _cortexState.candidates || { top: [], all_modules: [], primary: null, catalog_matches: [] };
    const topModules = new Set((cands.top || []).map(c => c.module));
    const all = cands.all_modules || [];
    const topMap = Object.fromEntries((cands.top || []).map(c => [c.module, c]));

    const builtinChips = all.map(slug => {
      const selected = _cortexState.selected.has(slug);
      const t = topMap[slug];
      const scoreText = t ? `${(t.score * 100).toFixed(0)}%` : "";
      const isPrimary = cands.primary === slug;
      const gradient = (typeof GRADIENTS !== "undefined" && GRADIENTS[slug]) || ["#9aa8ff", "#4d5bcf"];
      const disc = (typeof agentDisc === "function")
        ? agentDisc(slug, { size: 24 })
        : `<span style="display:inline-block;width:20px;height:20px;border-radius:50%;background:linear-gradient(135deg,${gradient[0]},${gradient[1]})"></span>`;
      return `
        <button type="button" class="nx-cortex-chip nx-chip ${selected ? "selected" : ""} ${topModules.has(slug) ? "top" : ""}" data-slug="${escapeHtml(slug)}" data-kind="builtin" aria-pressed="${selected}">
          <span class="nx-cortex-chip-icon">${disc}</span>
          <span class="nx-cortex-chip-name">${escapeHtml(slug)}</span>
          ${isPrimary ? `<span class="nx-cortex-chip-pill nx-pill nx-pill-accent">Primary</span>` : ""}
          ${scoreText ? `<span class="nx-cortex-chip-score">${escapeHtml(scoreText)}</span>` : ""}
        </button>
      `;
    }).join("") || `<div class="nx-empty-line">No agents are registered with Cortex yet.</div>`;
    document.getElementById("nx-cortex-chips-builtin").innerHTML = builtinChips;

    // Catalog chips: union of (candidates.catalog_matches from prompt) and
    // (catalogSearchResults from the search input). Cache metadata so the
    // dispatch payload includes whichever slugs the user ticked.
    const catalogSource = _cortexState.catalogSearch
      ? _cortexState.catalogSearchResults
      : (cands.catalog_matches || []);

    catalogSource.forEach(c => _cortexState.catalogMeta.set(c.slug, c));
    // Always include any ALREADY-SELECTED catalog chips even if they aren't in
    // the current visible source — otherwise selecting a chip then changing
    // the search would visually drop the selection.
    const selectedCatalog = [..._cortexState.selected]
      .filter(slug => !all.includes(slug))
      .map(slug => _cortexState.catalogMeta.get(slug))
      .filter(Boolean);
    const dedupMap = new Map();
    [...selectedCatalog, ...catalogSource].forEach(c => {
      if (!dedupMap.has(c.slug)) dedupMap.set(c.slug, c);
    });
    const catalogList = [...dedupMap.values()].slice(0, 24);

    const catalogSection = document.getElementById("nx-cortex-catalog-section");
    const catalogHeading = document.getElementById("nx-cortex-catalog-heading");
    const catalogEl = document.getElementById("nx-cortex-chips-catalog");

    if (catalogList.length === 0 && !_cortexState.catalogSearch) {
      catalogSection.hidden = true;
    } else {
      catalogSection.hidden = false;
      catalogHeading.textContent = _cortexState.catalogSearch
        ? `Catalog · ${catalogList.length} match${catalogList.length === 1 ? "" : "es"} for "${_cortexState.catalogSearch}"`
        : `Catalog · ${catalogList.length} prompt match${catalogList.length === 1 ? "" : "es"}`;
      catalogEl.innerHTML = catalogList.map(c => {
        const selected = _cortexState.selected.has(c.slug);
        return `
          <button type="button" class="nx-cortex-chip nx-chip catalog ${selected ? "selected" : ""}" data-slug="${escapeHtml(c.slug)}" data-kind="catalog" aria-pressed="${selected}" title="${escapeHtml(c.tagline || c.name)}">
            <span class="nx-cortex-chip-icon nx-cortex-chip-cat-icon">${icon("package", 13)}</span>
            <span class="nx-cortex-chip-name">${escapeHtml(c.name || c.slug)}</span>
            <span class="nx-cortex-chip-cat">${escapeHtml((c.category || "").replace(/-/g, " "))}</span>
          </button>
        `;
      }).join("") || `<div class="nx-empty-line">No catalog agents match.</div>`;
    }

    // Wire all chips (both lists)
    document.querySelectorAll(".nx-cortex-chip[data-slug]").forEach(c => {
      c.addEventListener("click", () => {
        const slug = c.dataset.slug;
        if (_cortexState.selected.has(slug)) _cortexState.selected.delete(slug);
        else _cortexState.selected.add(slug);
        renderChips();
        refreshRunBtn();
      });
    });
  };

  const renderRuns = () => {
    if (!_cortexState.runs) {
      resultsEl.innerHTML = "";
      return;
    }
    const { runs = [], succeeded = 0, failed = 0 } = _cortexState.runs;
    const anyPending = runs.some(r => r.pending);
    const summary = anyPending
      ? `<span class="running nx-status is-live">Dispatching to ${runs.length} agent${runs.length === 1 ? "" : "s"}</span>`
      : `<span class="ok nx-status is-ok">${succeeded} succeeded</span>
         ${failed > 0 ? `<span class="fail nx-status is-danger">${failed} failed</span>` : ""}`;
    resultsEl.innerHTML = `
      <header class="nx-cortex-results-head nx-section-head">
        <div class="nx-section-label">${anyPending ? "Dispatching, agents are working" : "Results, continue any card below"}</div>
        <div class="nx-cortex-summary">${summary}</div>
      </header>
      <div class="nx-cortex-runlist">
        ${runs.map((r, idx) => renderRunCard(r, idx)).join("")}
      </div>
    `;
    wireRunCards();
  };

  // Each turn in a card is rendered as a chat bubble. The "thread" is the
  // run's `_messages` array (built up across continue calls). When the
  // dispatch first lands `_messages` is initialized as
  // [{role:'user', content: original_prompt}, {role:'assistant', content: r.response}].
  const renderTurn = (m) => {
    if (m.role === "user") {
      return `
        <div class="nx-cortex-turn user">
          <span class="nx-cortex-turn-tag">You</span>
          <div class="nx-cortex-turn-body">${escapeHtml(m.content)}</div>
        </div>
      `;
    }
    return `
      <div class="nx-cortex-turn agent">
        <span class="nx-cortex-turn-tag">Agent</span>
        <div class="nx-cortex-turn-body nx-msg-md">${renderMarkdown(m.content)}</div>
      </div>
    `;
  };

  const renderRunCard = (r, idx) => {
    // In-flight: the dispatch has been sent but no result has landed yet.
    // Render as RUNNING (spinner + pulsing border), never as an error.
    if (r.pending) {
      return `
        <article class="nx-cortex-run-card pending" data-module="${escapeHtml(r.module)}" data-idx="${idx}" aria-busy="true">
          <header class="nx-cortex-run-head">
            ${agentDisc(r.module, { size: 24 })}
            <span class="nx-cortex-run-name">${escapeHtml(r.module)}</span>
            <span class="nx-cortex-run-meta">
              <span class="nx-spinner" aria-hidden="true"></span>
              <span class="nx-cortex-run-status running">Running</span>
            </span>
          </header>
          <div class="nx-cortex-run-body nx-dim">Dispatched. Waiting for ${escapeHtml(r.module)} to respond.</div>
          <div class="nx-progress is-indeterminate" aria-hidden="true"><div class="nx-progress-bar"></div></div>
        </article>
      `;
    }
    if (!r.success) {
      const secs = ((r.elapsed_ms || 0) / 1000).toFixed(1);
      return `
        <article class="nx-cortex-run-card fail" data-module="${escapeHtml(r.module)}" data-idx="${idx}">
          <header class="nx-cortex-run-head">
            ${agentDisc(r.module, { size: 24 })}
            <span class="nx-cortex-run-name">${escapeHtml(r.module)}</span>
            <span class="nx-cortex-run-meta">
              <span class="nx-cortex-run-status fail">Error</span>
              <span class="nx-dim">· failed after ${secs}s</span>
            </span>
          </header>
          <div class="nx-cortex-run-body">
            <span class="fail">${escapeHtml(r.error || "unknown error")}</span>
          </div>
        </article>
      `;
    }
    // Initialize _messages on first render so the very first response is part of the thread.
    if (!r._messages) {
      r._messages = [
        { role: "user", content: _cortexState.prompt },
        { role: "assistant", content: r.response || "" },
      ];
    }
    const handoffPill = r.suggested_handoff
      ? `<button class="nx-cortex-handoff-pill nx-btn nx-btn-sm nx-btn-tinted" type="button" data-handoff="${escapeHtml(r.suggested_handoff)}" title="The agent suggested handing the next turn to ${escapeHtml(r.suggested_handoff)}. Click to accept.">${icon("arrow-up-right", 12)}Hand off to ${escapeHtml(r.suggested_handoff)}</button>`
      : "";
    const turning = r._continuing
      ? `<div class="nx-cortex-turn agent typing"><span class="nx-cortex-turn-tag">${escapeHtml(r._next_agent || r.module)}</span><div class="nx-cortex-turn-body"><span class="nx-typing" aria-label="Thinking"><span></span><span></span><span></span></span></div></div>`
      : "";
    return `
      <article class="nx-cortex-run-card ok" data-module="${escapeHtml(r.module)}" data-idx="${idx}">
        <header class="nx-cortex-run-head">
          ${agentDisc(r.module, { size: 24 })}
          <span class="nx-cortex-run-name">${escapeHtml(r.module)}</span>
          <span class="nx-cortex-run-meta">
            <span class="nx-cortex-run-status ok">Done</span>
            <span class="nx-dim">· ${r.elapsed_ms}ms · ${r._messages.filter(m => m.role === "assistant").length} turn${r._messages.filter(m => m.role === "assistant").length === 1 ? "" : "s"}</span>
            ${r.llm_augmented ? `<span class="nx-cortex-llm-pill nx-pill nx-pill-accent" title="The agent's native handler returned a canned response, so Cortex re-asked the LLM to answer as this agent.">LLM</span>` : ""}
          </span>
        </header>
        <div class="nx-cortex-turns">
          ${r._messages.map(renderTurn).join("")}
          ${turning}
        </div>

        <footer class="nx-cortex-run-fb" data-fb-state="${r._feedback || ""}">
          <button type="button" class="nx-cortex-fb-btn nx-btn nx-btn-sm nx-btn-ghost ${r._feedback === "up" ? "active" : ""}" data-fb="up" aria-pressed="${r._feedback === "up"}" aria-label="Useful: +0.12 to ${escapeHtml(r.module)}'s trust">
            ${icon("thumbs-up", 14)}
            <span>Useful</span>
          </button>
          <button type="button" class="nx-cortex-fb-btn nx-btn nx-btn-sm nx-btn-ghost ${r._feedback === "down" ? "active down" : ""}" data-fb="down" aria-pressed="${r._feedback === "down"}" aria-label="Not useful: −0.22 from ${escapeHtml(r.module)}'s trust">
            ${icon("thumbs-down", 14)}
            <span>Wrong</span>
          </button>
          ${handoffPill}
          <button type="button" class="nx-cortex-handoff-btn nx-btn nx-btn-sm nx-btn-ghost" data-pick-handoff="${escapeHtml(r.module)}">${icon("repeat", 12)}Hand off</button>
          <span class="nx-cortex-fb-hint">${r._feedback === "up" ? "+0.12 applied, trust rose" : r._feedback === "down" ? "−0.22 applied, trust fell" : "Rating this response feeds Aegis trust"}</span>
        </footer>

        <form class="nx-cortex-followup" data-followup="${escapeHtml(r.module)}">
          <input class="nx-cortex-followup-input nx-input" type="text" placeholder="Ask a follow-up, or start with @agent to hand off" aria-label="Follow-up for ${escapeHtml(r.module)}" autocomplete="off">
          <button type="submit" class="nx-cortex-followup-send nx-btn" ${r._continuing ? "disabled" : ""}>${r._continuing ? `<span class="nx-spinner" aria-hidden="true"></span>Sending` : "Send"}</button>
        </form>

        ${r._handoffPickerOpen ? `
          <div class="nx-cortex-handoff-picker">
            <div class="nx-search-field">${icon("search", 14)}<input class="nx-cortex-handoff-search nx-input" type="search" placeholder="Search agents to hand off to" aria-label="Search agents to hand off to" autocomplete="off"></div>
            <div class="nx-cortex-handoff-results">
              ${renderHandoffOptions(r)}
            </div>
            <button type="button" class="nx-cortex-handoff-close nx-btn nx-btn-sm nx-btn-ghost" data-close-handoff="${escapeHtml(r.module)}">Close</button>
          </div>
        ` : ""}
      </article>
    `;
  };

  const renderHandoffOptions = (r) => {
    const cands = _cortexState.candidates || { all_modules: [] };
    const filter = (r._handoffSearch || "").toLowerCase();
    const builtins = (cands.all_modules || []).filter(s => !filter || s.includes(filter));
    const catalog = (r._handoffCatalogResults && r._handoffCatalogResults.length > 0)
      ? r._handoffCatalogResults
      : (cands.catalog_matches || []);
    return `
      <div class="nx-cortex-handoff-group">
        <div class="nx-eyebrow nx-cortex-handoff-eyebrow">Built-in</div>
        <div class="nx-cortex-handoff-chips">
          ${builtins.map(s => `<button type="button" class="nx-cortex-handoff-chip nx-chip" data-handoff-to="${escapeHtml(s)}">${agentDisc(s, { size: 20 })}${escapeHtml(s)}</button>`).join("")}
        </div>
      </div>
      ${catalog.length ? `
        <div class="nx-cortex-handoff-group">
          <div class="nx-eyebrow nx-cortex-handoff-eyebrow">Catalog</div>
          <div class="nx-cortex-handoff-chips">
            ${catalog.slice(0, 16).map(c => `<button type="button" class="nx-cortex-handoff-chip nx-chip catalog" data-handoff-to="${escapeHtml(c.slug)}" title="${escapeHtml(c.tagline || "")}">${icon("package", 13)}${escapeHtml(c.name || c.slug)}</button>`).join("")}
          </div>
        </div>
      ` : ""}
    `;
  };

  const continueOnCard = async (cardIdx, nextMessage, opts = {}) => {
    const r = _cortexState.runs.runs[cardIdx];
    if (!r) return;
    const targetModule = opts.targetModule || r.module;
    r._messages = r._messages || [];
    r._messages.push({ role: "user", content: nextMessage });
    r._continuing = true;
    r._next_agent = targetModule;
    renderRuns();
    try {
      const resp = await fetch("/api/cortex/continue", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          module: targetModule,
          history: r._messages.slice(0, -1),  // everything BEFORE the new user turn
          message: nextMessage,
          workspace_id: state.active || null,
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        // If we handed off, update the card's module so subsequent turns
        // continue with the new agent. History is preserved.
        if (targetModule !== r.module) {
          r.module = targetModule;
          r.llm_augmented = true;   // continue endpoint always uses LLM
        }
        r._messages.push({ role: "assistant", content: data.response || "" });
        r.suggested_handoff = data.suggested_handoff || null;
        r.elapsed_ms = data.elapsed_ms;
      } else {
        const detail = await resp.text();
        r._messages.push({ role: "assistant", content: `[error] ${resp.status}: ${detail}` });
      }
    } catch (err) {
      r._messages.push({ role: "assistant", content: `[network error] ${err.message}` });
    } finally {
      r._continuing = false;
      r._next_agent = null;
      renderRuns();
    }
  };

  const wireRunCards = () => {
    resultsEl.querySelectorAll(".nx-cortex-run-card[data-idx]").forEach(card => {
      const idx = parseInt(card.dataset.idx, 10);
      const moduleSlug = card.dataset.module;
      const runEntry = _cortexState.runs.runs[idx];
      if (!runEntry || runEntry.pending) return;  // in-flight cards have no affordances yet

      // Feedback buttons — same Aegis +0.12/−0.22 loop as the main composer
      card.querySelectorAll(".nx-cortex-fb-btn[data-fb]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const accepted = btn.dataset.fb === "up";
          if (runEntry) runEntry._feedback = accepted ? "up" : "down";
          renderRuns();
          try {
            await fetch("/api/messages/feedback", {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ module: moduleSlug, accepted }),
            });
            if (typeof loadTrust === "function") {
              await loadTrust();
              if (typeof renderCockpitRail === "function") renderCockpitRail();
            }
          } catch {
            if (runEntry) runEntry._feedback = "";
            renderRuns();
          }
        });
      });

      // Follow-up composer — sends next message to the SAME agent unless
      // the message starts with @<slug>, in which case we hand off.
      const form = card.querySelector(".nx-cortex-followup");
      if (form && !runEntry._continuing) {
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const input = form.querySelector(".nx-cortex-followup-input");
          const raw = (input?.value || "").trim();
          if (!raw) return;
          input.value = "";
          // Detect @<slug> hand-off prefix
          const handoffMatch = raw.match(/^@([a-z0-9][a-z0-9_.-]*)\s+(.*)$/i);
          if (handoffMatch) {
            const target = handoffMatch[1].toLowerCase();
            const remainder = handoffMatch[2];
            await continueOnCard(idx, remainder, { targetModule: target });
          } else {
            await continueOnCard(idx, raw);
          }
        });
      }

      // Inline accept of agent-suggested handoff
      card.querySelectorAll("[data-handoff]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const target = btn.dataset.handoff;
          if (!target) return;
          // Compose a tiny "continue" prompt that lets the new agent pick up
          await continueOnCard(idx, "(continuing from where the previous agent left off, please proceed)", { targetModule: target });
        });
      });

      // Explicit hand-off picker toggle
      card.querySelectorAll("[data-pick-handoff]").forEach(btn => {
        btn.addEventListener("click", () => {
          runEntry._handoffPickerOpen = !runEntry._handoffPickerOpen;
          runEntry._handoffSearch = "";
          renderRuns();
        });
      });
      card.querySelectorAll("[data-close-handoff]").forEach(btn => {
        btn.addEventListener("click", () => {
          runEntry._handoffPickerOpen = false;
          renderRuns();
        });
      });

      // Hand-off picker search + chip click
      const pickerSearch = card.querySelector(".nx-cortex-handoff-search");
      if (pickerSearch) {
        pickerSearch.value = runEntry._handoffSearch || "";
        pickerSearch.focus();
        const debSearch = debounceCortexInput(async (e) => {
          const q = (e?.target?.value || e || "").trim();
          runEntry._handoffSearch = q;
          if (q) {
            try {
              const r2 = await fetch(`/api/cortex/agent-search?q=${encodeURIComponent(q)}&limit=24`);
              if (r2.ok) {
                const data = await r2.json();
                runEntry._handoffCatalogResults = data.matches || [];
              }
            } catch {}
          } else {
            runEntry._handoffCatalogResults = [];
          }
          renderRuns();
        }, 220);
        pickerSearch.addEventListener("input", debSearch);
      }
      card.querySelectorAll("[data-handoff-to]").forEach(btn => {
        btn.addEventListener("click", async () => {
          const target = btn.dataset.handoffTo;
          runEntry._handoffPickerOpen = false;
          await continueOnCard(idx, "(handed off to you with full prior context, please continue)", { targetModule: target });
        });
      });
    });
  };

  // Fetch candidates. With an empty prompt we still hit the endpoint so
  // the picker always knows the built-in module list (otherwise the chip
  // area says "no agents registered" until the user types). The endpoint
  // returns an empty `top` and `catalog_matches` in that case but still
  // populates `all_modules` with the 10 built-ins.
  const loadCandidates = async (msg) => {
    try {
      const url = msg.trim()
        ? `/api/cortex/candidates?message=${encodeURIComponent(msg)}&catalog_limit=8`
        : `/api/cortex/candidates?message=hello&catalog_limit=0`;  // hello is throwaway; we only want all_modules
      const r = await fetch(url);
      if (r.ok) {
        const data = await r.json();
        // When there's no prompt yet, scrub the prompt-driven hints so
        // the UI doesn't pre-tick a "primary" that's just whatever the
        // classifier defaulted to for an empty query.
        if (!msg.trim()) {
          data.top = [];
          data.catalog_matches = [];
          data.primary = null;
        }
        _cortexState.candidates = data;
        (data.catalog_matches || []).forEach(c => _cortexState.catalogMeta.set(c.slug, c));
        renderChips();
      }
    } catch {}
  };

  // Live catalog search inside the picker — fetches /api/cortex/agent-search
  // and replaces the visible catalog chips with matches as the user types.
  const debouncedCatalogSearch = debounceCortexInput(async (q) => {
    _cortexState.catalogSearch = q;
    if (!q.trim()) {
      _cortexState.catalogSearchResults = [];
      renderChips();
      return;
    }
    try {
      const r = await fetch(`/api/cortex/agent-search?q=${encodeURIComponent(q)}&limit=24`);
      if (r.ok) {
        const data = await r.json();
        _cortexState.catalogSearchResults = data.matches || [];
        (data.matches || []).forEach(c => _cortexState.catalogMeta.set(c.slug, c));
      } else {
        _cortexState.catalogSearchResults = [];
      }
    } catch {
      _cortexState.catalogSearchResults = [];
    }
    renderChips();
  }, 200);

  // Wire prompt textarea
  promptEl.addEventListener("input", debounceCortexInput((e) => {
    _cortexState.prompt = e.target.value;
    loadCandidates(_cortexState.prompt);
    refreshRunBtn();
  }));
  promptEl.addEventListener("input", (e) => {
    _cortexState.prompt = e.target.value;
    refreshRunBtn();
  });

  // Wire catalog search input
  const catSearchEl = document.getElementById("nx-cortex-agent-search");
  catSearchEl?.addEventListener("input", (e) => {
    debouncedCatalogSearch(e.target.value);
  });

  // Pick-helper buttons
  document.getElementById("nx-cortex-top3").addEventListener("click", async () => {
    // Rank across BOTH built-ins (classifier score) and catalog (keyword-
    // search relevance). The classifier returns built-in modules in
    // .top with float scores; catalog_matches are already pre-ranked by
    // the candidates endpoint via keyword-search and tokenization. Both
    // populations contribute proportionally — if the catalog has very
    // strong matches for a domain-specific prompt (e.g. spreadsheet,
    // financial-modeling), they should be able to outrank the generic
    // built-ins instead of always losing to "council" because council
    // is the default primary.
    const cands = _cortexState.candidates || {};
    const scored = [];

    // Built-in classifier hits — keep their float score (0..1 ish).
    (cands.top || []).forEach(c => scored.push({ slug: c.module, score: c.score || 0.5 }));
    // Primary even when score=[] (the classifier's default pick).
    if (cands.primary && !scored.some(s => s.slug === cands.primary)) {
      scored.push({ slug: cands.primary, score: 0.45 });
    }
    // Catalog hits — ranked descending; give them tapered relevance scores
    // so the strongest catalog match can outrank a low-confidence built-in.
    (cands.catalog_matches || []).forEach((c, i) => {
      // Top catalog match gets ~0.7, then declines. Strong catalog
      // matches outrank built-in classifier defaults (~0.45) but the
      // best-scored built-in (e.g. council@0.8) still wins.
      scored.push({ slug: c.slug, score: Math.max(0.20, 0.72 - i * 0.07) });
    });

    // If we still need more options (sparse prompt), backfill with the
    // remaining registered built-ins at lower scores.
    (cands.all_modules || []).forEach(slug => {
      if (!scored.some(s => s.slug === slug)) {
        scored.push({ slug, score: 0.15 });
      }
    });

    // Pick top 3, distinct.
    scored.sort((a, b) => b.score - a.score);
    const picks = [];
    for (const s of scored) {
      if (!picks.includes(s.slug)) picks.push(s.slug);
      if (picks.length >= 3) break;
    }
    _cortexState.selected = new Set(picks);
    renderChips();
    refreshRunBtn();
  });
  document.getElementById("nx-cortex-all").addEventListener("click", () => {
    _cortexState.selected = new Set(_cortexState.candidates?.all_modules || []);
    renderChips();
    refreshRunBtn();
  });
  document.getElementById("nx-cortex-clear").addEventListener("click", () => {
    _cortexState.selected = new Set();
    renderChips();
    refreshRunBtn();
  });

  // Dispatch
  runBtn.addEventListener("click", async () => {
    if (_cortexState.running) return;
    const agents = [..._cortexState.selected];
    if (!agents.length || !_cortexState.prompt.trim()) return;
    const startedAt = Date.now();
    _cortexState.running = true;
    _cortexState.lastError = null;
    renderLauncherError();
    refreshRunBtn();
    // Show RUNNING cards immediately — spinner + pulsing border, not errors.
    _cortexState.runs = {
      runs: agents.map(slug => ({ module: slug, pending: true, success: false, response: "", error: null, elapsed_ms: 0 })),
      succeeded: 0, failed: 0,
    };
    renderRuns();
    // A failed dispatch must never look like a silent 0-second nothing:
    // every selected agent's card flips to a clear error with elapsed time,
    // and the launcher shows a prominent role="alert" banner.
    const failAll = (status, detail) => {
      const elapsed = Date.now() - startedAt;
      _cortexState.lastError = { status, detail };
      _cortexState.runs = {
        runs: agents.map(slug => ({
          module: slug, success: false, response: "",
          error: status ? `Dispatch failed. HTTP ${status}: ${detail}` : `Dispatch failed. ${detail}`,
          elapsed_ms: elapsed,
        })),
        succeeded: 0, failed: agents.length,
      };
    };
    try {
      const r = await fetch("/api/cortex/launch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: _cortexState.prompt.trim(),
          agents,
          workspace_id: state.active || null,
        }),
      });
      if (r.ok) {
        _cortexState.runs = await r.json();
      } else {
        let detail = await r.text();
        try { detail = JSON.parse(detail).detail || detail; } catch {}
        failAll(r.status, detail);
      }
    } catch (err) {
      failAll(null, `network error: ${err.message}`);
    } finally {
      _cortexState.running = false;
      renderRuns();
      refreshRunBtn();
      renderLauncherError();
    }
  });

  // ── Swarm templates — one-tap composition of a common swarm ───────────────
  // Tapping a template fills the task and pre-selects the swarm's agents, so
  // composing a run is "open the template, edit the brackets, dispatch".
  const applyTemplate = (tpl) => {
    _cortexState.prompt = tpl.prompt || "";
    promptEl.value = _cortexState.prompt;
    _cortexState.selected = new Set(tpl.agents || []);
    _cortexState.activeTemplate = tpl.id;
    loadCandidates(_cortexState.prompt).then(() => { renderChips(); refreshRunBtn(); });
    renderChips();
    refreshRunBtn();
    renderSwarmTemplates();
    // place the caret on the first <bracket> so the user can type the specifics
    promptEl.focus();
    const m = _cortexState.prompt.match(/<[^>]+>/);
    if (m) { const i = _cortexState.prompt.indexOf(m[0]); promptEl.setSelectionRange(i, i + m[0].length); }
  };

  const renderSwarmTemplates = () => {
    const el = document.getElementById("nx-swarm-templates");
    if (!el) return;
    const tpls = _cortexState.templates || [];
    if (!tpls.length) { el.innerHTML = ""; return; }
    el.innerHTML = `
      <div class="nx-section-head nx-swarm-eyebrow"><div class="nx-section-label">Swarm templates, compose a run in one tap</div></div>
      <div class="nx-swarm-grid">
        ${tpls.map(t => {
          const active = _cortexState.activeTemplate === t.id;
          const discs = (t.agents || []).slice(0, 5).map(a =>
            `<span class="nx-swarm-disc">${agentDisc(a, { size: 22 })}</span>`).join("");
          return `
            <button type="button" class="nx-swarm-card ${active ? "active" : ""}" data-tpl="${escapeHtml(t.id)}" aria-pressed="${active}">
              <span class="nx-swarm-card-icon">${SWARM_TEMPLATE_ICONS[t.id] || ""}</span>
              <span class="nx-swarm-card-name">${escapeHtml(t.name)}</span>
              <span class="nx-swarm-card-tag">${escapeHtml(t.tagline)}</span>
              <span class="nx-swarm-card-roster">${discs}<span class="nx-swarm-card-count">${(t.agents || []).length}</span></span>
            </button>`;
        }).join("")}
      </div>`;
    el.querySelectorAll(".nx-swarm-card[data-tpl]").forEach(card => {
      card.addEventListener("click", () => {
        const tpl = (_cortexState.templates || []).find(x => x.id === card.dataset.tpl);
        if (tpl) applyTemplate(tpl);
      });
    });
  };

  const loadSwarmTemplates = async () => {
    try {
      const r = await fetch("/api/cortex/templates");
      if (!r.ok) return;
      const body = await r.json();
      _cortexState.templates = body.templates || [];
      renderSwarmTemplates();
    } catch {}
  };

  // Initial paint — always loads the built-in module list so the picker
  // isn't blank on first entry, even when there's no prompt.
  await loadCandidates(_cortexState.prompt || "");
  renderChips();
  refreshRunBtn();
  renderRuns();
  loadSwarmTemplates();
}

// Tiny debounce — only refetches candidates after the user pauses typing.
function debounceCortexInput(fn, ms = 250) {
  let t = null;
  return (e) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(e), ms);
  };
}

// ── Providers tab (Settings) ──────────────────────────────────────────────
//
// Shows local providers (Ollama, llama.cpp) and lets the user add cloud
// providers (OpenAI, Anthropic) via an inline API-key input. Keys are
// POSTed to /api/providers/keys, persisted to ~/.local/share/nexus/
// provider_keys.json with 0600 perms, and never displayed back to the UI.
// The configured state surfaces only a tail-fingerprint like "sk-...1234".

const PROVIDER_DISPLAY = {
  ollama:    { label: "Ollama",    note: "local · runs offline", isLocal: true },
  "llama.cpp": { label: "llama.cpp", note: "local · llama.cpp HTTP server", isLocal: true },
  local:     { label: "llama.cpp", note: "local · llama.cpp HTTP server", isLocal: true },
  openai:    { label: "OpenAI",    note: "cloud · requires API key" },
  anthropic: { label: "Anthropic", note: "cloud · requires API key" },
};

const _providersState = { addingKey: null /* "openai" | "anthropic" | null */ };

async function renderProvidersTab() {
  let list = { providers: [] };
  let keys = { keys: {} };
  let models = { installed: [], active: null, recommended: [], pulls: {}, ollama_present: false };
  try {
    [list, keys, models] = await Promise.all([
      fetch("/api/providers").then(r => r.ok ? r.json() : { providers: [] }),
      fetch("/api/providers/keys").then(r => r.ok ? r.json() : { keys: {} }),
      fetch("/api/providers/ollama/models").then(r => r.ok ? r.json() : models),
    ]);
  } catch {}

  // Don't surface llama.cpp as "unavailable" when the user is on Ollama —
  // Ollama IS their local provider. Only show llama.cpp if it's actually
  // reachable (separate HTTP server at port 8384) so the panel doesn't
  // imply something is broken.
  const filteredProviders = (list.providers || []).filter(p => {
    const slug = (p.name || "").toLowerCase();
    if (slug === "local" || slug === "llama.cpp") {
      return !!p.healthy;
    }
    return true;
  });
  const rowsLive = filteredProviders.map(p => {
    const slug = (p.name || "").toLowerCase();
    const meta = PROVIDER_DISPLAY[slug] || { label: p.name, note: "" };
    const dotClass = p.healthy ? "ok" : "fail";
    const statusText = p.healthy ? "healthy" : "unavailable";
    return `
      <div class="nx-st-row">
        <dt>${escapeHtml(meta.label)} ${p.is_default ? '<span class="nx-st-pill nx-pill nx-pill-accent">Default</span>' : ""}</dt>
        <dd>
          <span class="nx-status ${p.healthy ? "is-ok" : "is-danger"}">${escapeHtml(statusText.charAt(0).toUpperCase() + statusText.slice(1))}</span>
          ${meta.note ? `<span class="nx-st-note">${escapeHtml(meta.note)}</span>` : ""}
        </dd>
      </div>
    `;
  }).join("");
  const hasLlamaCpp = filteredProviders.some(p => {
    const s = (p.name || "").toLowerCase();
    return s === "local" || s === "llama.cpp";
  });

  // Cloud rows (OpenAI / Anthropic) — separate UI element with add/configured/remove states
  const cloudRows = ["openai", "anthropic"].map(slug => renderCloudProviderRow(slug, keys.keys || {})).join("");

  return `
    <h3>LLM providers</h3>
    <p class="nx-panel-sub">
      Local providers (Ollama, llama.cpp) run offline with no API key.
      Add an OpenAI or Anthropic key below to enable cloud providers. Keys are stored locally with restricted file permissions and never shown again.
    </p>

    <div class="nx-st-group">
      <div class="nx-section-label">Local</div>
      <dl class="nx-st-rows">${rowsLive || `<div class="nx-empty-line">No providers are registered.</div>`}</dl>
      <div class="nx-ollama-controls">
        <button type="button" class="nx-st-keysave nx-btn nx-btn-sm" data-ollama-restart>${icon("refresh", 14)}Restart Ollama</button>
        <span class="nx-ollama-status" aria-live="polite"></span>
      </div>
      ${!hasLlamaCpp ? `
        <p class="nx-st-footnote">
          The llama.cpp HTTP server isn't running on port 8384, so Ollama covers local inference.
          To add llama.cpp too, start a server on <code class="nx-code-inline">localhost:8384</code> and it will appear here.
        </p>
      ` : ""}
    </div>

    <div class="nx-st-group">
      <div class="nx-section-label">Local model, the active brain</div>
      ${renderLocalModelSwitcher(models)}
    </div>

    <div class="nx-st-group">
      <div class="nx-section-label">Cloud</div>
      <dl class="nx-st-rows">${cloudRows}</dl>
    </div>
  `;
}

// The local-model switcher — pick which Ollama model is the kernel's active
// brain. Switching deactivates the previous one (it stays installed, switch
// back anytime). Recommended models can be added (pulled) in one click.
function renderLocalModelSwitcher(models) {
  const installed = models.installed || [];
  const active = models.active;
  const pulls = models.pulls || {};
  if (!models.ollama_present && !installed.length) {
    return `<div class="nx-model-empty nx-alert is-info">${icon("info", 16)}<div class="nx-alert-body">Ollama isn't installed. Get it from <code class="nx-code-inline">ollama.com</code> and your models will appear here.</div></div>`;
  }
  const installedChips = installed.length ? installed.map(m => `
    <button type="button" class="nx-model-chip nx-chip ${m === active ? "active selected" : ""}" aria-pressed="${m === active}" data-set-model="${escapeHtml(m)}">
      <span class="nx-model-dot nx-dot ${m === active ? "is-live" : ""}"></span>${escapeHtml(m)}${m === active ? ` <span class="nx-model-active-tag nx-pill nx-pill-accent">Active</span>` : ""}
    </button>`).join("") : `<div class="nx-empty-line">No models installed yet. Add one below.</div>`;

  const recRows = (models.recommended || []).map(r => {
    const p = pulls[r.name];
    const pulling = p && p.status === "pulling";
    const err = p && p.status === "error";
    let action;
    if (r.installed) {
      action = r.name === active
        ? `<span class="nx-model-active-tag nx-pill nx-pill-accent">Active</span>`
        : `<button type="button" class="nx-model-use nx-btn nx-btn-sm" data-set-model="${escapeHtml(r.name)}">Use</button>`;
    } else if (pulling) {
      action = `<span class="nx-model-pulling nx-status is-live">Pulling</span>`;
    } else {
      action = `<button type="button" class="nx-model-add nx-btn nx-btn-sm" data-pull-model="${escapeHtml(r.name)}">${icon("download", 14)}Add</button>`;
    }
    return `
      <div class="nx-model-rec">
        <div class="nx-model-rec-main">
          <span class="nx-model-rec-name">${escapeHtml(r.name)}${r.recommended ? ` <span class="nx-model-rec-badge nx-pill nx-pill-warn">Recommended</span>` : ""}</span>
          <span class="nx-model-rec-note">${escapeHtml(r.note || "")} · ${escapeHtml(r.size || "")}</span>
          ${pulling ? `<div class="nx-progress is-indeterminate" aria-hidden="true"><div class="nx-progress-bar"></div></div>` : ""}
          ${err ? `<span class="nx-model-rec-err">Pull failed: ${escapeHtml((p.detail||"").slice(0,120))}</span>` : ""}
        </div>
        <div class="nx-model-rec-action">${action}</div>
      </div>`;
  }).join("");

  return `
    <div class="nx-model-switcher">
      <div class="nx-model-active-line">Active brain: <b>${escapeHtml(active || "none selected")}</b></div>
      <div class="nx-model-chips">${installedChips}</div>
      <div class="nx-model-rec-label">Recommended for ONEXUS. Qwen2.5 leads on tool calling. Adding one pulls it and makes it active.</div>
      <div class="nx-model-rec-list nx-list nx-list-boxed">${recRows}</div>
    </div>`;
}

function renderCloudProviderRow(slug, keysMap) {
  const meta = PROVIDER_DISPLAY[slug];
  const info = keysMap[slug];                // { configured: bool, fingerprint: "...xxxx" }
  const isConfigured = !!(info && info.configured);
  const isAdding = _providersState.addingKey === slug;

  let dd;
  if (isAdding) {
    dd = `
      <form class="nx-st-keyform" data-add="${escapeHtml(slug)}">
        <input type="password" name="apiKey" class="nx-st-keyinput nx-input nx-input-mono"
               placeholder="${slug === "openai" ? "sk-..." : "sk-ant-..."}"
               aria-label="${escapeHtml(meta.label)} API key"
               autocomplete="off" spellcheck="false" autofocus>
        <button type="submit" class="nx-st-keysave nx-btn nx-btn-primary nx-btn-sm">Save</button>
        <button type="button" class="nx-st-keycancel nx-btn nx-btn-ghost nx-btn-sm" data-cancel="${escapeHtml(slug)}">Cancel</button>
      </form>
    `;
  } else if (isConfigured) {
    const fp = info.fingerprint || "configured";
    dd = `
      <span class="nx-status is-ok">Configured</span>
      <code class="nx-code-inline nx-st-fp">${escapeHtml(fp)}</code>
      <button type="button" class="nx-st-keyremove nx-btn nx-btn-sm nx-btn-danger" data-remove="${escapeHtml(slug)}">Remove</button>
    `;
  } else {
    dd = `
      <button type="button" class="nx-st-keyadd nx-btn nx-btn-sm" data-add="${escapeHtml(slug)}">${icon("key", 14)}Add ${escapeHtml(meta.label)} API key</button>
    `;
  }
  return `
    <div class="nx-st-row">
      <dt>${escapeHtml(meta.label)}</dt>
      <dd>${dd}</dd>
    </div>
  `;
}

// While a model pull is in flight, refresh the providers tab so the user sees
// progress and the auto-switch once it lands. Self-stops when no pull is active.
let _ollamaPollTimer = null;
function startOllamaPullPolling(panel) {
  if (_ollamaPollTimer) return;
  _ollamaPollTimer = setInterval(async () => {
    if (!document.body.contains(panel)) { clearInterval(_ollamaPollTimer); _ollamaPollTimer = null; return; }
    let models = null;
    try { models = await fetch("/api/providers/ollama/models").then(r => r.ok ? r.json() : null); } catch {}
    const anyPulling = models && Object.values(models.pulls || {}).some(p => p.status === "pulling");
    panel.innerHTML = await renderProvidersTab();
    wireProvidersHandlers(panel);
    if (!anyPulling) { clearInterval(_ollamaPollTimer); _ollamaPollTimer = null; }
  }, 3000);
}

// Wired by renderSettings after each providers-tab render. Re-renders the
// tab when the state changes so we don't have to manage in-place mutation.
function wireProvidersHandlers(panel) {
  const repaint = async () => {
    panel.innerHTML = await renderProvidersTab();
    wireProvidersHandlers(panel);
  };

  panel.querySelectorAll("[data-add]").forEach(el => {
    el.addEventListener("click", (e) => {
      // The form's submit is handled below; here we only handle the "+ add"
      // button that flips into edit mode.
      if (el.tagName === "BUTTON" && el.classList.contains("nx-st-keyadd")) {
        _providersState.addingKey = el.dataset.add;
        repaint();
      }
    });
  });

  panel.querySelectorAll("[data-cancel]").forEach(el => {
    el.addEventListener("click", () => {
      _providersState.addingKey = null;
      repaint();
    });
  });

  // Restart Ollama: spawn (or restart) the local Ollama server from inside the
  // app, so quitting Ollama doesn't mean leaving ONEXUS to bring it back.
  panel.querySelectorAll("[data-ollama-restart]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const status = panel.querySelector(".nx-ollama-status");
      const prev = btn.textContent;
      btn.disabled = true;
      btn.textContent = "Restarting";
      if (status) status.textContent = "";
      try {
        const r = await fetch("/api/providers/ollama/restart", { method: "POST" });
        const body = await r.json().catch(() => ({}));
        if (r.ok) {
          if (status) status.textContent = body.message || "Ollama started";
          // Give the server a moment to bind its port, then refresh health dots.
          setTimeout(repaint, 1500);
        } else {
          if (status) status.textContent = body.detail || `Failed (HTTP ${r.status})`;
          btn.disabled = false;
          btn.textContent = prev;
        }
      } catch (err) {
        if (status) status.textContent = `Network error: ${err}`;
        btn.disabled = false;
        btn.textContent = prev;
      }
    });
  });

  // Local-model switch — activate an installed model (deactivates the previous).
  panel.querySelectorAll("[data-set-model]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const model = btn.dataset.setModel;
      btn.disabled = true;
      try {
        const r = await fetch("/api/providers/ollama/model", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model }),
        });
        if (!r.ok) { const b = await r.json().catch(() => ({})); alert(b.detail || "switch failed"); btn.disabled = false; return; }
      } catch (err) { alert("network error: " + err); btn.disabled = false; return; }
      repaint();
    });
  });

  // Add (pull) a recommended model — it becomes active when the pull lands.
  panel.querySelectorAll("[data-pull-model]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const model = btn.dataset.pullModel;
      btn.disabled = true; btn.textContent = "Starting";
      try {
        const r = await fetch("/api/providers/ollama/pull", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ model, activate: true }),
        });
        if (!r.ok) { const b = await r.json().catch(() => ({})); alert(b.detail || "The pull failed to start."); btn.disabled = false; btn.textContent = "Add"; return; }
      } catch (err) { alert("Network error: " + err); btn.disabled = false; btn.textContent = "Add"; return; }
      repaint();
      startOllamaPullPolling(panel);
    });
  });

  panel.querySelectorAll("form.nx-st-keyform").forEach(form => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const slug = form.dataset.add;
      const input = form.querySelector("input[name=apiKey]");
      const key = (input?.value || "").trim();
      if (!key) return;
      const submitBtn = form.querySelector(".nx-st-keysave");
      if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = "Saving"; }
      try {
        const r = await fetch("/api/providers/keys", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ provider: slug, api_key: key }),
        });
        if (!r.ok) {
          const body = await r.json().catch(() => ({}));
          alert(`failed to save ${slug} key: ${body.detail || r.status}`);
          if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Save"; }
          return;
        }
        // Clear input immediately (so the key never lingers in DOM) and flip out of edit mode.
        if (input) input.value = "";
        _providersState.addingKey = null;
        repaint();
      } catch (err) {
        alert(`Network error: ${err}`);
        if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = "Save"; }
      }
    });
  });

  panel.querySelectorAll("[data-remove]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const slug = btn.dataset.remove;
      const meta = PROVIDER_DISPLAY[slug];
      if (!confirm(`Remove the ${meta?.label || slug} API key from this machine?`)) return;
      try {
        const r = await fetch(`/api/providers/keys/${encodeURIComponent(slug)}`, { method: "DELETE" });
        if (!r.ok) {
          alert(`failed to remove key: ${r.status}`);
          return;
        }
        repaint();
      } catch (err) {
        alert(`network error: ${err}`);
      }
    });
  });
}

// ── Chat history (settings tab) ───────────────────────────────────────────
// Three nested views: workspaces → agents → chats. The page polls every 5s
// while open so new exchanges appear without a manual refresh.

const chatHistoryState = {
  view: "workspaces",         // "workspaces" | "agents" | "chats"
  workspace_id: null,
  workspace_name: null,
  workspace_tone: null,
  module: null,
  offset: 0,
  pageSize: 50,
  refreshTimer: null,
  // Cached last-fetched payloads, so a poll re-render doesn't flash blank
  // while the fetch is in flight.
  _last: null,
};

function stopChatHistoryRefresh() {
  if (chatHistoryState.refreshTimer) {
    clearInterval(chatHistoryState.refreshTimer);
    chatHistoryState.refreshTimer = null;
  }
}

async function renderChatHistory(panel) {
  stopChatHistoryRefresh();
  await paintChatHistory(panel);
  // Poll for new chats every 5s. Stop if the panel was removed (user
  // navigated away to another route / closed settings entirely).
  chatHistoryState.refreshTimer = setInterval(() => {
    if (!document.body.contains(panel)) {
      stopChatHistoryRefresh();
      return;
    }
    paintChatHistory(panel, { silent: true }).catch(() => {});
  }, 5000);
}

async function paintChatHistory(panel, { silent = false } = {}) {
  if (!silent) {
    panel.innerHTML = SETTINGS_LOADING_HTML;
  }
  const view = chatHistoryState.view;
  let html;
  if (view === "workspaces") html = await renderChatHistoryWorkspaces();
  else if (view === "agents") html = await renderChatHistoryAgents();
  else html = await renderChatHistoryChats();
  panel.innerHTML = html;
  // Tone the chat-history surface to the workspace's color, so the rail on
  // each chat panel, the breadcrumb hover, and the agent tag pick up the
  // workspace's own gradient instead of the global mood primary.
  applyChatHistoryTone(panel);
  wireChatHistoryHandlers(panel);
}

function applyChatHistoryTone(panel) {
  const tone = (chatHistoryState.view === "workspaces")
    ? null
    : (chatHistoryState.workspace_tone || "indigo").toLowerCase();
  if (!tone) {
    panel.style.removeProperty("--ch-tone-a");
    panel.style.removeProperty("--ch-tone-b");
    panel.classList.remove("nx-ch-toned");
    return;
  }
  panel.style.setProperty("--ch-tone-a", `var(--nx-tone-${tone}-a)`);
  panel.style.setProperty("--ch-tone-b", `var(--nx-tone-${tone}-b)`);
  panel.classList.add("nx-ch-toned");
}

function chatHistoryRelative(ts) {
  if (!ts) return "never";
  const then = Date.parse(ts);
  if (!Number.isFinite(then)) return "unknown";
  const s = Math.floor((Date.now() - then) / 1000);
  if (s < 60) return s <= 1 ? "just now" : `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d ago`;
  const mo = Math.floor(d / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(mo / 12)}y ago`;
}

function chatHistoryFmtTime(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "";
  // e.g. "Jun 9 · 8:42 PM"
  const month = d.toLocaleString(undefined, { month: "short" });
  const day = d.getDate();
  const time = d.toLocaleString(undefined, { hour: "numeric", minute: "2-digit" });
  return `${month} ${day} · ${time}`;
}

async function renderChatHistoryWorkspaces() {
  let body;
  try {
    body = await fetch("/api/chat-history/workspaces").then(r => r.ok ? r.json() : { workspaces: [] });
  } catch {
    body = { workspaces: [] };
  }
  const ws = body.workspaces || [];
  chatHistoryState._last = body;

  const totalChats = ws.reduce((a, w) => a + (w.chat_count || 0), 0);
  const totalAgents = ws.reduce((a, w) => a + (w.agent_count || 0), 0);

  const cards = ws.map(w => {
    const tone = (w.tone || "indigo").toLowerCase();
    return `
      <button class="nx-ch-ws-card" type="button" data-workspace="${escapeHtml(w.workspace_id || "_unscoped")}" data-name="${escapeHtml(w.name)}" data-tone="${escapeHtml(tone)}" style="--tone:var(--nx-tone-${escapeHtml(tone)}-a, var(--nx-accent))">
        <div class="nx-ch-ws-swatch nx-tone-${escapeHtml(tone)}"></div>
        <div class="nx-ch-ws-body">
          <div class="nx-ch-ws-name">${escapeHtml(w.name)}</div>
          <div class="nx-ch-ws-meta">
            <span><b>${w.chat_count}</b> ${w.chat_count === 1 ? "chat" : "chats"}</span>
            <span class="nx-ch-sep">·</span>
            <span><b>${w.agent_count}</b> ${w.agent_count === 1 ? "agent" : "agents"}</span>
          </div>
          <div class="nx-ch-ws-last">Last active ${chatHistoryRelative(w.last_active_at)}</div>
        </div>
        <div class="nx-ch-chev" aria-hidden="true">${icon("chevron-right", 16)}</div>
      </button>
    `;
  }).join("");

  return `
    <div class="nx-ch-head">
      <h3>Chat history</h3>
      <div class="nx-ch-live nx-status is-live">Live</div>
    </div>
    <p class="nx-panel-sub">
      <b>${totalChats}</b> ${totalChats === 1 ? "chat" : "chats"}
      across <b>${ws.length}</b> ${ws.length === 1 ? "workspace" : "workspaces"}
      with <b>${totalAgents}</b> ${totalAgents === 1 ? "agent slot" : "agent slots"}.
      Open a workspace to see who you've been talking to.
    </p>
    ${ws.length === 0
      ? emptyStateHTML({ icon: "message", title: "No chats yet", body: "Send a message from a workspace and your history starts here." })
      : `<div class="nx-ch-ws-grid">${cards}</div>`}
  `;
}

async function renderChatHistoryAgents() {
  const wsId = chatHistoryState.workspace_id;
  let body;
  try {
    body = await fetch(`/api/chat-history/workspaces/${encodeURIComponent(wsId)}/agents`)
      .then(r => r.ok ? r.json() : { agents: [] });
  } catch {
    body = { agents: [] };
  }
  const agents = body.agents || [];
  chatHistoryState._last = body;

  const rows = agents.map(a => {
    const slug = a.module || "unknown";
    const gradient = (typeof GRADIENTS !== "undefined" && GRADIENTS[slug]) || ["#9aa8ff", "#4d5bcf"];
    const disc = (typeof agentDisc === "function")
      ? agentDisc(slug, { size: 32 })
      : `<div class="nx-ch-agent-fallback" style="background:linear-gradient(135deg,${gradient[0]},${gradient[1]})"></div>`;
    return `
      <button class="nx-ch-agent-row" type="button" data-module="${escapeHtml(slug)}">
        <div class="nx-ch-agent-icon">${disc}</div>
        <div class="nx-ch-agent-body">
          <div class="nx-ch-agent-name">${escapeHtml(slug)}</div>
          <div class="nx-ch-agent-preview">${escapeHtml(a.last_preview || "")}</div>
        </div>
        <div class="nx-ch-agent-stats">
          <div class="nx-ch-agent-count"><b>${a.chat_count}</b> ${a.chat_count === 1 ? "chat" : "chats"}</div>
          <div class="nx-ch-agent-last">${chatHistoryRelative(a.last_active_at)}</div>
        </div>
        <div class="nx-ch-chev" aria-hidden="true">${icon("chevron-right", 16)}</div>
      </button>
    `;
  }).join("");

  return `
    <div class="nx-ch-head">
      <h3>Chat history</h3>
      <div class="nx-ch-live nx-status is-live">Live</div>
    </div>
    <div class="nx-ch-crumbs">
      <button class="nx-ch-crumb-link" type="button" data-nav="workspaces">All workspaces</button>
      <span class="nx-ch-crumb-sep" aria-hidden="true">${icon("chevron-right", 12)}</span>
      <span class="nx-ch-crumb-here">${escapeHtml(chatHistoryState.workspace_name || wsId)}</span>
    </div>
    <p class="nx-panel-sub">
      <b>${agents.length}</b> ${agents.length === 1 ? "agent" : "agents"} you've spoken to in this workspace. Open one to read the full transcripts.
    </p>
    ${agents.length === 0
      ? emptyStateHTML({ icon: "message", title: "No chats in this workspace", body: "Chats you have here will be listed by agent." })
      : `<div class="nx-ch-agent-list">${rows}</div>`}
  `;
}

async function renderChatHistoryChats() {
  const wsId = chatHistoryState.workspace_id;
  const module = chatHistoryState.module;
  const offset = chatHistoryState.offset || 0;
  const limit = chatHistoryState.pageSize || 50;
  let body;
  try {
    const url = `/api/chat-history/workspaces/${encodeURIComponent(wsId)}/agents/${encodeURIComponent(module)}/chats?offset=${offset}&limit=${limit}`;
    body = await fetch(url).then(r => r.ok ? r.json() : { chats: [], total: 0 });
  } catch {
    body = { chats: [], total: 0 };
  }
  const chats = body.chats || [];
  const total = body.total || 0;
  chatHistoryState._last = body;

  const totalPages = Math.max(1, Math.ceil(total / limit));
  const currentPage = Math.floor(offset / limit) + 1;
  const showingFrom = total === 0 ? 0 : offset + 1;
  const showingTo = Math.min(offset + limit, total);

  const panels = chats.map(c => {
    const t = c.transcript || {};
    const truncatedHint = t.truncated
      ? `<div class="nx-ch-msg-truncated">The transcript memory was not found, so this is the Chronicle preview (${t.agent_response_chars || 0} character response).</div>`
      : "";
    return `
      <article class="nx-ch-chat">
        <header class="nx-ch-chat-head">
          <span class="nx-ch-chat-time">${escapeHtml(chatHistoryFmtTime(c.timestamp))}</span>
          <span class="nx-ch-chat-rel nx-dim">${chatHistoryRelative(c.timestamp)}</span>
        </header>
        <div class="nx-ch-msg nx-ch-msg-you">
          <span class="nx-ch-msg-tag">You</span>
          <div class="nx-ch-msg-text">${escapeHtml(t.user || "")}</div>
        </div>
        <div class="nx-ch-msg nx-ch-msg-agent">
          <span class="nx-ch-msg-tag">${escapeHtml(module)}</span>
          <div class="nx-ch-msg-text">${escapeHtml(t.agent || "")}</div>
        </div>
        ${truncatedHint}
      </article>
    `;
  }).join("");

  const prevDisabled = offset <= 0;
  const nextDisabled = !body.has_more;
  const pagination = total > limit ? `
    <nav class="nx-ch-pager">
      <button class="nx-ch-pager-btn nx-btn nx-btn-sm" type="button" data-pager="prev" ${prevDisabled ? "disabled" : ""}>${icon("chevron-left", 14)}Previous</button>
      <div class="nx-ch-pager-status">
        <span class="nx-ch-pager-page">${showingFrom}–${showingTo}</span>
        <span class="nx-dim">of</span>
        <span class="nx-ch-pager-total">${total}</span>
        <span class="nx-dim">·</span>
        <span class="nx-dim">page ${currentPage} / ${totalPages}</span>
      </div>
      <button class="nx-ch-pager-btn nx-btn nx-btn-sm" type="button" data-pager="next" ${nextDisabled ? "disabled" : ""}>Next${icon("chevron-right", 14)}</button>
    </nav>
  ` : "";

  return `
    <div class="nx-ch-head">
      <h3>Chat history</h3>
      <div class="nx-ch-live nx-status is-live">Live</div>
    </div>
    <div class="nx-ch-crumbs">
      <button class="nx-ch-crumb-link" type="button" data-nav="workspaces">All workspaces</button>
      <span class="nx-ch-crumb-sep" aria-hidden="true">${icon("chevron-right", 12)}</span>
      <button class="nx-ch-crumb-link" type="button" data-nav="agents">${escapeHtml(chatHistoryState.workspace_name || wsId)}</button>
      <span class="nx-ch-crumb-sep" aria-hidden="true">${icon("chevron-right", 12)}</span>
      <span class="nx-ch-crumb-here">${escapeHtml(module)}</span>
    </div>
    <p class="nx-panel-sub">
      ${total === 0
        ? "No chats with this agent yet."
        : `Showing <b>${showingFrom}–${showingTo}</b> of <b>${total}</b> ${total === 1 ? "chat" : "chats"}, newest first, 50 per page.`}
    </p>
    ${chats.length === 0
      ? emptyStateHTML({ icon: "inbox", title: "Nothing on this page", body: "Go back a page, or pick another agent." })
      : `<div class="nx-ch-chat-list">${panels}</div>`}
    ${pagination}
  `;
}

function wireChatHistoryHandlers(panel) {
  // Workspace cards → drill into agents
  panel.querySelectorAll(".nx-ch-ws-card").forEach(btn => {
    btn.addEventListener("click", () => {
      chatHistoryState.workspace_id = btn.dataset.workspace;
      chatHistoryState.workspace_name = btn.dataset.name;
      chatHistoryState.workspace_tone = btn.dataset.tone;
      chatHistoryState.module = null;
      chatHistoryState.offset = 0;
      chatHistoryState.view = "agents";
      paintChatHistory(panel);
    });
  });
  // Agent rows → drill into chats
  panel.querySelectorAll(".nx-ch-agent-row").forEach(btn => {
    btn.addEventListener("click", () => {
      chatHistoryState.module = btn.dataset.module;
      chatHistoryState.offset = 0;
      chatHistoryState.view = "chats";
      paintChatHistory(panel);
    });
  });
  // Breadcrumb nav
  panel.querySelectorAll(".nx-ch-crumb-link").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.dataset.nav;
      if (target === "workspaces") {
        chatHistoryState.view = "workspaces";
        chatHistoryState.workspace_id = null;
        chatHistoryState.workspace_name = null;
        chatHistoryState.module = null;
      } else if (target === "agents") {
        chatHistoryState.view = "agents";
        chatHistoryState.module = null;
      }
      chatHistoryState.offset = 0;
      paintChatHistory(panel);
    });
  });
  // Pagination
  panel.querySelectorAll(".nx-ch-pager-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const dir = btn.dataset.pager;
      const size = chatHistoryState.pageSize || 50;
      if (dir === "prev") chatHistoryState.offset = Math.max(0, (chatHistoryState.offset || 0) - size);
      else if (dir === "next") chatHistoryState.offset = (chatHistoryState.offset || 0) + size;
      paintChatHistory(panel);
    });
  });
}

async function renderSettingsTab(tab) {
  switch (tab) {
    case "general": {
      const sys = await fetch("/api/system/config").then(r => r.ok ? r.json() : {}).catch(() => ({}));
      return `
        <h3>General</h3>
        <p class="nx-panel-sub">Where ONEXUS keeps its data and how it runs.</p>
        <dl class="nx-st-rows">
          <div class="nx-st-row">
            <dt>Data directory</dt>
            <dd><code>${escapeHtml(sys.data_dir || "~/.nexus")}</code></dd>
          </div>
          <div class="nx-st-row">
            <dt>API port</dt>
            <dd><code>${escapeHtml(String(sys.port || location.port || "8000"))}</code></dd>
          </div>
          <div class="nx-st-row">
            <dt>Default provider</dt>
            <dd><code>${escapeHtml(sys.default_provider || "local")}</code></dd>
          </div>
          <div class="nx-st-row">
            <dt>Log level</dt>
            <dd><code>${escapeHtml(sys.log_level || "INFO")}</code></dd>
          </div>
          <div class="nx-st-row">
            <dt>Time of day</dt>
            <dd><code id="nx-st-clock">${escapeHtml(new Date().toString().slice(0, 24))}</code></dd>
          </div>
        </dl>
      `;
    }
    case "security": {
      const all = await fetch("/api/trust").then(r => r.ok ? r.json() : { scores: [] }).catch(() => ({scores:[]}));
      const sorted = (all.scores || []).slice().sort((a,b) => (b.trust ?? 0) - (a.trust ?? 0));
      // Cache full list for client-side filtering
      state._securityModules = sorted;
      return `
        <h3>Security and trust</h3>
        <p class="nx-panel-sub">
          <span id="nx-st-trust-count">${sorted.length}</span> module${sorted.length === 1 ? "" : "s"} registered with Aegis. Revoke resets a module's trust to 0 and collapses all of its grants.
        </p>
        <div class="nx-st-search nx-search-field">
          ${icon("search", 14)}
          <input id="nx-st-trust-search" type="search" class="nx-input"
                 placeholder="Filter modules and MCP agents"
                 aria-label="Filter modules">
          <span class="nx-st-search-count nx-pill nx-pill-mono" id="nx-st-search-count">${sorted.length}</span>
        </div>
        <div class="nx-st-trust-head" aria-hidden="true"><span>Module</span><span>Trust</span><span></span><span>Tier</span><span></span></div>
        <div class="nx-st-trust-list" id="nx-st-trust-list">
          ${renderTrustRows(sorted.slice(0, 60))}
        </div>
        ${sorted.length > 60 ? `<div class="nx-st-footnote" id="nx-st-trust-more">Showing the first 60 of ${sorted.length}. Use the filter to narrow.</div>` : ""}
      `;
    }
    case "providers": {
      return await renderProvidersTab();
    }
    case "federation": {
      let peers = { peers: [] };
      try { peers = await fetch("/api/federation/peers").then(r => r.ok ? r.json() : {peers:[]}); } catch {}
      return `
        <h3>Federation</h3>
        <p class="nx-panel-sub">
          Connect ONEXUS instances peer to peer. Set <code class="nx-code-inline">NEXUS_FEDERATION_ENABLED=1</code> to enable it on this instance.
        </p>
        <dl class="nx-st-rows">
          <div class="nx-st-row">
            <dt>Status</dt>
            <dd><span class="nx-status ${peers.peers ? "is-ok" : ""}">${peers.peers ? "Enabled" : "Disabled"}</span></dd>
          </div>
          <div class="nx-st-row">
            <dt>Peers</dt>
            <dd>${(peers.peers || []).length === 0 ? `<span class="nx-dim">None connected</span>` : (peers.peers || []).map(p => `<code>${escapeHtml(p.peer_id || p.id)}</code>`).join(", ")}</dd>
          </div>
        </dl>
      `;
    }
    case "moods": {
      const current = await fetch("/api/mood/current").then(r => r.ok ? r.json() : {}).catch(() => ({}));
      return `
        <h3>Moods</h3>
        <p class="nx-panel-sub">
          The MoodEngine watches CPU, Engram busy ratio, trust events, time of day and resident agents.
          Each of the eight moods sets the color of the whole shell: the light behind the content, the tint of every surface and edge, and the accent.
        </p>
        <div class="nx-st-mood-now">
          <span class="nx-st-mood-swatch nx-mood-preview-${escapeHtml((current.mood || state.mood.mood || "calm_focus").replace(/_/g, "-"))}" aria-hidden="true"></span>
          <div>
            <div class="nx-eyebrow">Right now</div>
            <div class="nx-st-mood-name">${escapeHtml((current.mood || state.mood.mood || "calm_focus").replace(/_/g, " "))}</div>
            <div class="nx-st-mood-reason">${escapeHtml(current.reason || "")}</div>
          </div>
          ${state.mood.override ? `
            <div class="nx-st-mood-override">
              <span class="nx-status is-warn">Manual override</span> <button class="nx-st-mood-clear-btn nx-btn nx-btn-sm" type="button" id="nx-settings-mood-clear">Return to auto</button>
            </div>
          ` : `<div class="nx-st-mood-auto nx-status is-ok">Auto, following the kernel</div>`}
        </div>
        <div class="nx-st-mood-grid">
          ${MOOD_OPTIONS.map(m => `
            <div class="nx-st-mood-card">
              <span class="nx-mp-swatch nx-mood-preview-${m.key.replace(/_/g, "-")}"></span>
              <div class="nx-st-mood-card-text">
                <div class="nx-st-mood-card-name">${escapeHtml(m.name)}</div>
                <div class="nx-st-mood-card-note">${escapeHtml(m.note)}</div>
              </div>
            </div>
          `).join("")}
        </div>
      `;
    }
    case "about": {
      // Live counts — never hardcoded.
      const [tests, all, runnable] = await Promise.all([
        fetch("/api/system/tests").then(r => r.ok ? r.json() : { total: null }).catch(() => ({total: null})),
        fetch("/api/agents?limit=1").then(r => r.ok ? r.json() : { total: null }).catch(() => ({total: null})),
        fetch("/api/agents?runnable_only=true&limit=1").then(r => r.ok ? r.json() : { total: null }).catch(() => ({total: null})),
      ]);
      const fmt = n => (n === null || n === undefined) ? "?" : Number(n).toLocaleString();
      return `
        <h3>About ONEXUS</h3>
        <p class="nx-panel-sub">
          An operating system for agents. Local-first, sovereign, gated by Aegis.
          The kernel never touches the network, and a static test proves it.
        </p>
        <dl class="nx-st-rows">
          <div class="nx-st-row">
            <dt>Version</dt>
            <dd><code>v1.0</code></dd>
          </div>
          <div class="nx-st-row">
            <dt>Tests</dt>
            <dd>
              <span class="ok">${fmt(tests.total)}</span> declared
              <span class="nx-st-note">Scanned live from <code class="nx-code-inline">tests/</code></span>
            </dd>
          </div>
          <div class="nx-st-row">
            <dt>Catalog</dt>
            <dd>
              ${fmt(all.total)} agents · ${fmt(runnable.total)} runnable
              <span class="nx-st-note">Runnable means an MCP adapter is present</span>
            </dd>
          </div>
          <div class="nx-st-row">
            <dt>Source</dt>
            <dd><a href="https://github.com/AllStreets/ONEXUS" target="_blank" rel="noopener" class="nx-st-link nx-link">github.com/AllStreets/ONEXUS ${icon("external-link", 12)}</a></dd>
          </div>
          <div class="nx-st-row">
            <dt>License</dt>
            <dd>Apache-2.0</dd>
          </div>
        </dl>
      `;
    }
  }
  return `<h3>${escapeHtml(tab)}</h3><p class="nx-panel-sub">This section doesn't exist.</p>`;
}

// ── Mood picker (click the mood pill) ─────────────────────────────────────
const MOOD_OPTIONS = [
  { key: "calm_focus",    name: "calm focus",    note: "teal · default · low load, eyes-down work" },
  { key: "deep_flow",     name: "deep flow",     note: "jade · long uninterrupted stretches" },
  { key: "routing",       name: "routing",       note: "rose · cortex dispatching, lots of small tasks" },
  { key: "deliberating",  name: "deliberating",  note: "amber · council weighing options" },
  { key: "creative",      name: "creative",      note: "periwinkle · open-ended generation, deep ideation" },
  { key: "reflective",    name: "reflective",    note: "orchid · review, summarise, look back" },
  { key: "watchful",      name: "watchful",      note: "sky · sentry on, scanning" },
  { key: "alert",         name: "alert",         note: "signal red · trust collapse, denied call, override" },
];

function openMoodPicker() {
  const existing = document.getElementById("nx-mood-picker");
  if (existing) { existing.remove(); return; }

  const pill = document.getElementById("nx-mood-pill");
  const rect = pill.getBoundingClientRect();
  const current = state.mood.mood || "calm_focus";
  const isAuto = !state.mood.override;

  const pop = document.createElement("div");
  pop.id = "nx-mood-picker";
  pop.className = "nx-mood-picker nx-popover";
  pop.setAttribute("role", "dialog");
  pop.setAttribute("aria-label", "Choose a mood");
  pop.style.top = (rect.bottom + 8) + "px";
  pop.style.right = (window.innerWidth - rect.right) + "px";
  pop.innerHTML = `
    <div class="nx-mp-head">
      <div class="nx-mp-eyebrow">Mood ${state.mood.override ? `· <span class="nx-mp-override">Override</span>` : `· Auto`}</div>
      <div class="nx-mp-hint">Sets the accent for the whole shell. The kernel senses ${escapeHtml((state.mood.kernelMood || state.mood.mood || "calm_focus").replace(/_/g, " "))} right now.</div>
    </div>
    <button class="nx-mp-auto ${isAuto ? "active" : ""}" type="button" data-action="auto" aria-pressed="${isAuto}">
      <span class="nx-mp-auto-icon">${icon("refresh", 14)}</span>
      <span class="nx-mp-auto-text">
        <span class="nx-mp-auto-name">Auto, follow the kernel</span>
        <span class="nx-mp-auto-note">Currently sensing ${escapeHtml((state.mood.kernelMood || "calm_focus").replace(/_/g, " "))}</span>
      </span>
    </button>
    <div class="nx-mp-grid">
      ${MOOD_OPTIONS.map(m => `
        <button class="nx-mp-cell ${m.key === current && !isAuto ? "active" : ""}" type="button" data-mood="${m.key}" title="${escapeHtml(m.note)}">
          <span class="nx-mp-swatch nx-mood-preview-${m.key.replace(/_/g, "-")}"></span>
          <span class="nx-mp-name">${escapeHtml(m.name)}</span>
          <span class="nx-mp-note">${escapeHtml(m.note)}</span>
        </button>
      `).join("")}
    </div>
    <div class="nx-mp-foot">
      A manual pick stays until you press Auto. The kernel keeps observing in the background.
    </div>
  `;
  document.body.appendChild(pop);

  const refreshActive = () => {
    pop.querySelectorAll(".nx-mp-cell").forEach(c => c.classList.toggle("active", !state.mood.override ? false : c.dataset.mood === state.mood.mood));
    pop.querySelector(".nx-mp-auto").classList.toggle("active", !state.mood.override);
    const eyebrow = pop.querySelector(".nx-mp-eyebrow");
    if (eyebrow) eyebrow.innerHTML = `Mood ${state.mood.override ? `· <span class="nx-mp-override">Override</span>` : `· Auto`}`;
  };

  // Auto button → clear override, snap back to kernel mood
  pop.querySelector(".nx-mp-auto").addEventListener("click", () => {
    state.mood.override = null;
    if (state.mood.kernelMood) {
      state.mood.mood = state.mood.kernelMood;
      applyMood(state.mood.kernelMood);
    }
    refreshActive();
    renderMoodCard();
  });

  pop.querySelectorAll(".nx-mp-cell[data-mood]").forEach(btn => {
    btn.addEventListener("click", async () => {
      const mood = btn.dataset.mood;
      state.mood.override = mood;   // <-- key fix: WS no longer overrides
      state.mood.mood = mood;
      applyMood(mood);              // applies instantly + holds (WS is gated on override)
      refreshActive();
      renderMoodCard();
    });
  });

  // Close on outside click / Esc
  const onClick = (e) => { if (!pop.contains(e.target) && e.target !== pill) closePicker(); };
  const onKey = (e) => { if (e.key === "Escape") closePicker(); };
  const closePicker = () => {
    pop.remove();
    document.removeEventListener("click", onClick);
    window.removeEventListener("keydown", onKey);
  };
  setTimeout(() => {
    document.addEventListener("click", onClick);
    window.addEventListener("keydown", onKey);
  }, 50);
}

// ── Guide (multi-page walkthrough) ────────────────────────────────────────
const GUIDE_PAGES = [
  {
    eyebrow: "PAGE 1 / 13",
    chapter: "WELCOME",
    title: "An operating system for agents.",
    body: "ONEXUS runs agents the way iOS runs apps: workspaces with their own memory, agents with their own trust, and every tool call gated by Aegis. This guide walks every surface in about eight minutes. Use the arrow keys to flip pages, click a number to jump, and press Esc to leave.",
    shot: "/aurora/static/guide/01-welcome.png",
    callouts: [
      { x: 8.3, y: 25.6, label: "1", note: "Sidebar: the tools, your workspaces and recent agents." },
      { x: 47.9, y: 58, label: "2", note: "Main canvas: the workspace home with agent prompts." },
      { x: 89.6, y: 18.4, label: "3", note: "Cockpit rail: trust, permissions, the live kernel and mood." },
    ],
    cta: { label: "Continue", action: null },
  },
  {
    eyebrow: "PAGE 2 / 13",
    chapter: "WORKSPACES",
    title: "Each workspace is its own room.",
    body: "Rooms have their own agents, memory, grants and home tone. Switch between them with ⌘K and create new ones with ⌘N. To delete one, hover its row and click the trash icon. Each room stays private: what's remembered here doesn't leak there.",
    shot: "/aurora/static/guide/09-sidebar.png",
    fullSidebar: true,
    callouts: [
      { x: 49.8, y: 37.5, label: "1", note: "Workspace rows: click to switch, click the active one again for its home." },
      { x: 87.9, y: 37.5, label: "2", note: "Hover any row to reveal the trash icon." },
      { x: 49.8, y: 47.1, label: "3", note: "New workspace, or press ⌘N." },
    ],
    cta: { label: "Try it with ⌘K", action: "switcher" },
  },
  {
    eyebrow: "PAGE 3 / 13",
    chapter: "CONVERSATION",
    title: "Talk to a room of agents at once.",
    body: "Send a message and Cortex routes it to whoever is best placed to answer. Mention an agent (@oracle, @council) to call it directly. Press ⌘⏎ to send. The composer stays pinned at the bottom and the thread scrolls above it.",
    shot: "/aurora/static/guide/02-conversation.png",
    callouts: [
      { x: 22.6, y: 24.4, label: "1", note: "Agent identity tile and module name." },
      { x: 49.4, y: 35.2, label: "2", note: "Inline permission card, shown on the first sensitive call." },
      { x: 47.9, y: 94.4, label: "3", note: "Composer: type, paste or drop files, then press ⌘⏎." },
    ],
    cta: { label: "Try it in a room", action: "compose" },
  },
  {
    eyebrow: "PAGE 4 / 13",
    chapter: "FILES",
    title: "Drag, drop, attach.",
    body: "Drop a file anywhere on the conversation to attach it; an outline in the mood color confirms the drop. Files are stored in <code>.onexus/uploads/</code> under the workspace root, hashed to avoid duplicates, registered with Engram so the agent can recall them, and logged to Chronicle. The paperclip in the composer does the same with a file picker.",
    shot: "/aurora/static/guide/02-conversation.png",
    callouts: [
      { x: 23.1, y: 94.4, label: "1", note: "The paperclip opens a file picker." },
      { x: 47.9, y: 31.2, label: "2", note: "Drag a file anywhere on the canvas to drop it in." },
      { x: 37.4, y: 91.6, label: "3", note: "Attached files appear as chips above the composer." },
    ],
    cta: { label: "Done", action: null },
  },
  {
    eyebrow: "PAGE 5 / 13",
    chapter: "SAFETY MODEL",
    title: "Every sensitive call asks first.",
    body: "Aegis classifies every capability as routine, notable, sensitive or privileged. Routine runs silently. Sensitive pauses the agent until you allow once, allow always in this workspace, or deny. The cockpit log keeps a record of every decision, marked by class.",
    shot: "/aurora/static/guide/02-conversation.png",
    callouts: [
      { x: 26.4, y: 35.2, label: "1", note: "The amber pulse marks a sensitive request." },
      { x: 62.6, y: 35.2, label: "2", note: "Three decisions: allow once, always in this workspace, or deny." },
      { x: 89.6, y: 36.3, label: "3", note: "The cockpit log records the decision." },
    ],
    cta: { label: "See it in action", action: "seed-permission" },
  },
  {
    eyebrow: "PAGE 6 / 13",
    chapter: "TRUST",
    title: "Trust is earned, asymmetrically.",
    body: "Click the thumbs up or thumbs down under any agent message to mark it useful or wrong. Useful adds 0.12 to that agent's Aegis trust; wrong takes away 0.22. Above 0.75 the agent auto-grants its notable capabilities. Below 0.50, every grant collapses at once. The cockpit's trust readout shows the rolling 60-minute change.",
    shot: "/aurora/static/guide/08-cockpit.png",
    cockpitOnly: true,
    callouts: [
      { x: 50.2, y: 3.5, label: "1", note: "Trust readout: rising in amber, falling in steel, collapse in red." },
      { x: 50.2, y: 8.4, label: "2", note: "Breakdown by permission class." },
    ],
    cta: { label: "Done", action: null },
  },
  {
    eyebrow: "PAGE 7 / 13",
    chapter: "COCKPIT",
    title: "Watch what the kernel sees.",
    body: "The right rail keeps trust, permissions, the live kernel, mood and the agent roster in view. Toggle it with the panel icon at the top right. Press ⌘0 for the expanded cockpit. Every panel refreshes as the kernel runs.",
    shot: "/aurora/static/guide/08-cockpit.png",
    cockpitOnly: true,
    callouts: [
      { x: 50.2, y: 4.7,  label: "1", note: "Trust over the last 60 minutes." },
      { x: 50.2, y: 18.8, label: "2", note: "Recent permissions log." },
      { x: 50.2, y: 71.8, label: "3", note: "Ambient mood, which sets the shell's accent." },
      { x: 23.5, y: 78.9, label: "4", note: "Built-in agents: click any tile for its capabilities." },
    ],
    cta: { label: "Open the cockpit with ⌘0", action: "cockpit" },
  },
  {
    eyebrow: "PAGE 8 / 13",
    chapter: "MOOD",
    title: "The shell shifts color with what's happening.",
    body: "Click the mood pill at the top right of the title bar to open the mood picker. Pick any of the eight moods (calm focus, deep flow, routing, deliberating, creative, reflective, watchful, alert) and the <em>whole shell</em> crossfades into it: the light behind the content, the tint of every surface and edge, the chrome band, and the accent on the active workspace, the composer, primary buttons and live dots. Press <code>Auto, follow the kernel</code> to go back to automatic, which picks based on CPU load, Engram activity, time of day and trust events.",
    shot: "/aurora/static/guide/10-mood-picker.png",
    callouts: [
      { x: 91.9, y: 2.6,  label: "1", note: "The mood pill: click to open the picker." },
      { x: 82.4, y: 17.5, label: "2", note: "Auto, follow the kernel: releases a manual pick." },
      { x: 82.4, y: 34.6, label: "3", note: "Eight moods: pick one to set the accent yourself." },
    ],
    cta: { label: "Try it and pick a mood", action: "moodpicker" },
  },
  {
    eyebrow: "PAGE 9 / 13",
    chapter: "AGENTS",
    title: "Ten built-in. Click any tile.",
    body: "Council deliberates. Specter red-teams. Oracle reads. Legacy remembers. Wraith forgets. Sentry watches. Autonomic automates. Echo mirrors. Consciousness regulates mood. The agents dispatcher routes to installed third-party agents. Click any tile to see its declared capabilities, trust floor and network reach.",
    shot: "/aurora/static/guide/03-capability-sheet.png",
    callouts: [
      { x: 30.7, y: 12.3, label: "1", note: "Identity tile and name." },
      { x: 50, y: 58.9, label: "2", note: "Tools declared, each with its permission class." },
      { x: 50, y: 32.3, label: "3", note: "Live trust, trust floor and network reach." },
    ],
    cta: { label: "Done", action: null },
  },
  {
    eyebrow: "PAGE 10 / 13",
    chapter: "WORKSHOP",
    title: "Code and a sandbox, without leaving.",
    body: "Open the Workshop from the sidebar or press ⌘E. Pick a runtime such as Python, JavaScript or shell, then press Run or ⌘⏎. Code runs in a subprocess sandbox with a stripped environment, an 8-second timeout, and captured stdout and stderr. Every run lands in Chronicle.",
    shot: "/aurora/static/guide/04-workshop.png",
    callouts: [
      { x: 25.3, y: 24.2, label: "1", note: "Language picker." },
      { x: 34.9, y: 43.7, label: "2", note: "Code editor in a monospaced well." },
      { x: 34.9, y: 76, label: "3", note: "Output: exit code, elapsed time, stdout and stderr." },
    ],
    cta: { label: "Open the Workshop with ⌘E", action: "workshop" },
  },
  {
    eyebrow: "PAGE 11 / 13",
    chapter: "WEB SEARCH",
    title: "Search the web without leaving.",
    body: "Press ⌘/ to open Search. Queries route through aegis.network() to DuckDuckGo's instant-answer API by default, with no tracking. Set NEXUS_BRAVE_KEY for organic results from Brave Search. Wikipedia is always a fallback, so you never see an empty page.",
    shot: "/aurora/static/guide/05-search.png",
    callouts: [
      { x: 47.9, y: 24.4, label: "1", note: "The search bar. Press ⌘/ from anywhere to get here." },
      { x: 47.9, y: 40, label: "2", note: "Results: title, URL, snippet and source." },
    ],
    cta: { label: "Open Search with ⌘/", action: "search" },
  },
  {
    eyebrow: "PAGE 12 / 13",
    chapter: "CATALOG",
    title: "6,745 agents · 571 runnable.",
    body: "ONEXUS ships with the AllStreets/ONEXUS-Agents catalog bundled. Browse it from the sidebar. Turn on Runnable only to see the 571 with MCP adapters that you can launch in one click. Each card links to its source repo.",
    shot: "/aurora/static/guide/06-catalog.png",
    callouts: [
      { x: 47.9, y: 23.3, label: "1", note: "Filters: search, category and Runnable only." },
      { x: 27.9, y: 53.3, label: "2", note: "Each card has Launch, Compose, Trust and a source link." },
    ],
    cta: { label: "Browse the catalog", action: "catalog" },
  },
  {
    eyebrow: "PAGE 13 / 13",
    chapter: "KEYBOARD",
    title: "Shortcuts you'll use every day.",
    body: "Master these and you barely touch the mouse.",
    shot: null,
    keys: [
      ["⌘K",   "Open the workspace switcher"],
      ["⌘N",   "New workspace"],
      ["⌘0",   "Expanded cockpit"],
      ["⌘L",   "Cortex launch"],
      ["⌘J",   "Kernel watch"],
      ["⌘Y",   "Memory replay"],
      ["⌘E",   "Open the Workshop"],
      ["⌘/",   "Web search"],
      ["⌘P",   "Settings"],
      ["⌘⏎",   "Send a message"],
      ["←  →",  "Flip guide pages"],
      ["Esc",  "Close any overlay or leave focus mode"],
    ],
    cta: { label: "Done, start using ONEXUS", action: "close" },
  },
];

function renderGuide(pageIndex) {
  const root = document.getElementById("nx-overlay-root");
  const p = GUIDE_PAGES[pageIndex];
  if (!p) return closeOverlay();
  const total = GUIDE_PAGES.length;

  // Numbered MARKERS land on the screenshot; the explanatory NOTES live
  // in a readable legend below the image. No more floating tooltips that
  // clip off the right edge.
  const markersHTML = (p.callouts || []).map(c => `
    <span class="nx-g-marker" style="left:${c.x}%;top:${c.y}%" data-i="${escapeHtml(c.label)}">${escapeHtml(c.label)}</span>
  `).join("");
  const legendHTML = (p.callouts || []).length ? `
    <ol class="nx-g-legend">
      ${p.callouts.map(c => `
        <li>
          <span class="num">${escapeHtml(c.label)}</span>
          <span class="text">${escapeHtml(c.note)}</span>
        </li>
      `).join("")}
    </ol>
  ` : "";

  const keysHTML = p.keys ? `
    <div class="nx-g-keys">
      ${p.keys.map(([k, v]) => `
        <div class="nx-g-key-row">
          <span class="nx-g-key-kbd nx-kbd">${escapeHtml(k)}</span>
          <span class="nx-g-key-desc">${escapeHtml(v)}</span>
        </div>
      `).join("")}
    </div>
    <div class="nx-g-dismiss-hint">
      Click anywhere, press <span class="nx-kbd">esc</span> or choose <span class="nx-kbd">Done</span> to close. The left arrow goes back.
    </div>
  ` : "";

  const dotsHTML = GUIDE_PAGES.map((_, i) =>
    `<button type="button" class="nx-g-dot ${i === pageIndex ? "active" : (i < pageIndex ? "done" : "")}" data-i="${i}" ${i === pageIndex ? 'aria-current="page"' : ""} aria-label="Page ${i+1}: ${escapeHtml(GUIDE_PAGES[i].chapter.toLowerCase())}" title="Page ${i+1} · ${escapeHtml(GUIDE_PAGES[i].chapter.toLowerCase())}">${i+1}</button>`
  ).join("");

  const showShot = p.shot && !p.keys;

  const html = `
    <div class="nx-guide-overlay" id="nx-guide-overlay" role="dialog" aria-modal="true" aria-label="Guide">
      <button class="nx-g-close-btn nx-btn nx-btn-sm nx-btn-ghost" type="button" id="nx-g-close" aria-label="Close guide">
        ${icon("x", 14)}
        <span>Close</span>
        <span class="nx-kbd">esc</span>
      </button>

      <div class="nx-guide-stage">
        <div class="nx-g-eyebrow nx-eyebrow">${escapeHtml(p.eyebrow.replace("PAGE", "Page"))} · ${escapeHtml(p.chapter.charAt(0) + p.chapter.slice(1).toLowerCase())}</div>
        <h2 class="nx-g-title">${escapeHtml(p.title)}</h2>
        <div class="nx-g-body">${p.body}</div>

        ${showShot ? `
          <div class="nx-g-shot-wrap ${p.fullSidebar ? "nx-g-shot-narrow" : ""} ${p.cockpitOnly ? "nx-g-shot-cockpit" : ""}">
            <img class="nx-g-shot" src="${escapeHtml(p.shot)}?v=${state._guideCacheBust}" alt="${escapeHtml(p.title)}">
            <div class="nx-g-shot-markers" aria-hidden="true">${markersHTML}</div>
          </div>
          ${legendHTML}
        ` : keysHTML}
      </div>

      <div class="nx-guide-nav">
        <button class="nx-g-arrow nx-btn nx-btn-icon" type="button" id="nx-g-prev" ${pageIndex === 0 ? "disabled" : ""} aria-label="Previous page" title="Previous page (←)">
          ${icon("arrow-left", 16)}
        </button>
        <div class="nx-g-dots">${dotsHTML}</div>
        <div class="nx-g-right">
          ${p.cta && p.cta.action ? `
            <button class="nx-g-cta nx-btn nx-btn-tinted" type="button" id="nx-g-next" title="${escapeHtml(p.cta.label)}">
              <span>${escapeHtml(p.cta.label)}</span>
            </button>
          ` : ""}
          <button class="nx-g-arrow nx-g-arrow-next nx-btn nx-btn-primary nx-btn-icon" type="button" id="nx-g-advance"
                  ${pageIndex === total - 1 ? "disabled" : ""}
                  aria-label="${pageIndex === total - 1 ? "Last page" : "Next page"}"
                  title="${pageIndex === total - 1 ? "Last page" : "Next page (→)"}">
            ${icon("arrow-right", 16)}
          </button>
        </div>
      </div>
    </div>
  `;

  withSmoothSwap(
    () => { root.innerHTML = html; },
    () => {
      const close = () => closeOverlay();
      const isLastPage = pageIndex === total - 1;

      // Advancing through the guide (arrow keys, → button) — strictly moves
      // to the next page. NEVER triggers a CTA action. On the LAST page,
      // advance is a no-op: the user has to click "Done", Esc, or outside.
      const advance = () => {
        if (pageIndex < total - 1) renderGuide(pageIndex + 1);
      };

      // The CTA button runs the page's specific action. On the last page
      // the CTA explicitly closes the guide ("Done — start using ONEXUS").
      const runCTA = () => {
        if (isLastPage) { close(); return; }
        const action = p.cta?.action;
        switch (action) {
          case "switcher":        close(); renderSwitcher(); return;
          case "compose":         close(); document.getElementById("nx-composer-input")?.focus(); return;
          case "seed-permission":
            fetch("/api/permissions/seed", {
              method: "POST", headers: {"Content-Type":"application/json"},
              body: JSON.stringify({ workspace_id: state.active, target: "src/test.py" }),
            });
            return;
          case "cockpit":         close(); toggleCockpitOverlay(); return;
          case "moodpicker":      close(); setTimeout(() => openMoodPicker(), 100); return;
          case "workshop":        close(); location.hash = "#/workshop"; return;
          case "search":          close(); location.hash = "#/search"; return;
          case "catalog":         close(); location.hash = "#/catalog"; return;
          default:                advance(); return;
        }
      };

      document.getElementById("nx-g-close").addEventListener("click", close);
      document.getElementById("nx-g-prev").addEventListener("click", () => pageIndex > 0 && renderGuide(pageIndex - 1));
      document.getElementById("nx-g-next")?.addEventListener("click", runCTA);
      document.getElementById("nx-g-advance")?.addEventListener("click", advance);

      if (isLastPage) {
        const overlay = document.getElementById("nx-guide-overlay");
        overlay.addEventListener("click", (e) => {
          const t = e.target;
          const isInteractive = t.closest("button, a, .nx-g-dot");
          if (!isInteractive) close();
        });
      }
      root.querySelectorAll(".nx-g-dot[data-i]").forEach(dot => {
        dot.addEventListener("click", () => renderGuide(Number(dot.dataset.i)));
      });
      const overlayEl = document.getElementById("nx-guide-overlay");
      const onKey = (e) => {
        if (!document.body.contains(overlayEl)) {
          window.removeEventListener("keydown", onKey);
          return;
        }
        if (e.key === "Escape") { close(); }
        else if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); advance(); }
        else if (e.key === "ArrowLeft")  { if (pageIndex > 0) renderGuide(pageIndex - 1); }
        else if (e.key >= "1" && e.key <= "9") {
          const i = Number(e.key) - 1;
          if (i < total) renderGuide(i);
        }
        else if (e.key === "0") { if (total > 9) renderGuide(9); }
      };
      window.addEventListener("keydown", onKey, { once: false });
      const observer = new MutationObserver(() => {
        if (!document.body.contains(overlayEl)) {
          window.removeEventListener("keydown", onKey);
          observer.disconnect();
        }
      });
      observer.observe(document.body, { childList: true, subtree: true });
    }
  );
}

// ── History helpers (workshop + search) ──────────────────────────────────
const HISTORY_LIMITS = { workshop: 30, search: 50 };

function loadHistory(kind) {
  try {
    const raw = localStorage.getItem(`nx-history-${kind}`);
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}
function saveHistoryEntry(kind, entry) {
  try {
    const items = loadHistory(kind);
    items.unshift({ ...entry, ts: Date.now() });
    const trimmed = items.slice(0, HISTORY_LIMITS[kind] || 30);
    localStorage.setItem(`nx-history-${kind}`, JSON.stringify(trimmed));
  } catch {}
}
function clearHistory(kind) {
  try { localStorage.removeItem(`nx-history-${kind}`); } catch {}
}
function fmtAgo(ts) {
  if (!ts) return "";
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

function openHistoryPopover(anchorEl, kind, onPick) {
  // Close existing
  document.getElementById("nx-history-popover")?.remove();
  const items = loadHistory(kind);
  const rect = anchorEl.getBoundingClientRect();

  const pop = document.createElement("div");
  pop.id = "nx-history-popover";
  pop.className = "nx-history-popover nx-popover";
  pop.style.top  = (rect.bottom + 8) + "px";
  pop.style.left = rect.left + "px";

  if (!items.length) {
    pop.innerHTML = `
      <div class="nx-hp-head"><span class="nx-section-label">${kind === "workshop" ? "Workshop" : "Search"} history</span></div>
      <div class="nx-hp-empty nx-empty-line">Nothing here yet. Runs and searches you make are kept on this machine.</div>
    `;
  } else {
    const rowsHTML = items.map((it, i) => {
      const preview = kind === "workshop"
        ? `<span class="hp-lang">${escapeHtml(it.language || "")}</span> <span class="hp-prev">${escapeHtml((it.code || "").split("\n")[0].slice(0, 64))}</span>`
        : `<span class="hp-prev">${escapeHtml(it.query || "")}</span>`;
      return `
        <button class="nx-hp-row" type="button" data-i="${i}">
          ${preview}
          <span class="hp-ago">${escapeHtml(fmtAgo(it.ts))}</span>
        </button>
      `;
    }).join("");
    pop.innerHTML = `
      <div class="nx-hp-head">
        <span class="nx-section-label">${kind === "workshop" ? "Workshop" : "Search"} history · ${items.length}</span>
        <button class="nx-hp-clear nx-btn nx-btn-sm nx-btn-danger" type="button" id="nx-hp-clear" title="Clear ${kind} history">Clear</button>
      </div>
      <div class="nx-hp-list">${rowsHTML}</div>
    `;
  }
  document.body.appendChild(pop);

  pop.querySelectorAll(".nx-hp-row[data-i]").forEach(btn => {
    btn.addEventListener("click", () => {
      const item = items[Number(btn.dataset.i)];
      pop.remove();
      onPick(item);
    });
  });
  pop.querySelector("#nx-hp-clear")?.addEventListener("click", () => {
    clearHistory(kind);
    pop.remove();
  });

  // Close on outside click / Esc
  const onClick = (e) => {
    if (!pop.contains(e.target) && !anchorEl.contains(e.target)) {
      pop.remove();
      document.removeEventListener("click", onClick);
      window.removeEventListener("keydown", onKey);
    }
  };
  const onKey = (e) => {
    if (e.key === "Escape") {
      pop.remove();
      document.removeEventListener("click", onClick);
      window.removeEventListener("keydown", onKey);
    }
  };
  setTimeout(() => {
    document.addEventListener("click", onClick);
    window.addEventListener("keydown", onKey);
  }, 50);
}

// ── Workshop (in-OS code editor + sandbox runtime) ────────────────────────
// Workshop chat thread — persists across runs in the same session.
// Sees current source + last run output + full prior conversation on every turn.
const _workshopThread = { messages: [], lastOutput: null };

// Render markup/style languages in a sandboxed iframe (they don't "run").
function renderWorkshopPreview(language, code, outEl) {
  const demo = `<h1>Heading</h1><p>A paragraph with <a href="#">a link</a>, <strong>bold</strong> and <em>italic</em>.</p>
    <button>Button</button> <input placeholder="input"/>
    <ul><li>list item one</li><li>list item two</li></ul>`;
  let doc;
  if (language === "html") {
    doc = code;
  } else if (language === "css") {
    doc = `<!doctype html><html><head><meta charset="utf-8"><style>${code}</style></head><body>${demo}</body></html>`;
  } else { // markdown
    doc = `<!doctype html><html><head><meta charset="utf-8"><style>body{font-family:-apple-system,system-ui,sans-serif;color:#1a1620;background:#fff;padding:22px;line-height:1.6;max-width:760px}pre,code{font-family:ui-monospace,monospace;background:#f0eef5;padding:2px 5px;border-radius:4px}pre{padding:12px;overflow:auto}</style></head><body>${renderMarkdown(code)}</body></html>`;
  }
  outEl.innerHTML = `<div class="nx-workshop-stats"><span class="ok nx-status is-ok">Preview</span><span class="nx-mono">${escapeHtml(language)}</span><span class="nx-dim">Rendered in a sandboxed frame</span></div>`;
  const frame = document.createElement("iframe");
  frame.className = "nx-workshop-preview";
  frame.setAttribute("sandbox", "allow-scripts");
  frame.setAttribute("title", `${language} preview`);

  frame.srcdoc = doc;
  outEl.appendChild(frame);
}

async function renderWorkshop() {
  const main = document.getElementById("nx-main");
  // Discover available runtimes from the server
  let langs = {};
  try {
    const r = await fetch("/api/workshop/languages");
    if (r.ok) langs = (await r.json()).languages || {};
  } catch {}
  const available = Object.keys(langs);
  const installedLangs = available.filter(l => langs[l]?.installed);
  const defaultLang = installedLangs[0] || available[0] || "python";
  const lastCode = state._workshopCode || "";
  const lastLang = state._workshopLang || defaultLang;

  main.innerHTML = `
    <div class="nx-main-inner">
      <header class="nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Workshop</div>
          <h1 class="nx-page-title">Code and sandbox</h1>
          <p class="nx-page-sub">${available.length} languages, ${installedLangs.length} installed. Every run is gated by Aegis and logged to Chronicle. The coder agent pairs with you on the right.</p>
        </div>
      </header>

      <div class="nx-workshop with-chat">
        <div class="nx-workshop-left">
          <div class="nx-workshop-controls">
            <input id="nx-workshop-lang" class="nx-input nx-input-mono nx-workshop-lang" list="nx-workshop-lang-list"
                   value="${escapeHtml(lastLang)}" placeholder="Language"
                   autocomplete="off" spellcheck="false" aria-label="Language (type to search)">
            <datalist id="nx-workshop-lang-list">
              ${available.map(l => `<option value="${escapeHtml(l)}">${escapeHtml(l)}${langs[l]?.installed ? "" : " (not installed)"}</option>`).join("")}
            </datalist>
            <button id="nx-workshop-run" class="nx-run-btn nx-btn nx-btn-primary" type="button">
              ${icon("play", 14)}
              <span>Run</span>
              <span class="run-kbd">⌘⏎</span>
            </button>
            <button id="nx-workshop-history" class="nx-history-btn nx-btn" type="button" title="Recent runs">
              ${icon("history", 14)}
              <span>History</span>
            </button>
          </div>
          <textarea id="nx-workshop-code" class="nx-workshop-code" spellcheck="false" aria-label="Code"
                    placeholder="# Write code here. It runs in a subprocess sandbox with no network access by default."
          >${escapeHtml(lastCode)}</textarea>
          <div class="nx-workshop-out" id="nx-workshop-out" aria-live="polite">
            <div class="nx-empty-line nx-workshop-hint">${icon("terminal", 14)}Run a snippet to see stdout and stderr here.</div>
          </div>
        </div>
        <aside class="nx-workshop-chat" id="nx-workshop-chat">
          <header class="nx-workshop-chat-head">
            <div class="nx-workshop-chat-title">${agentDisc("agents", { size: 24 })}<div><div class="nx-workshop-chat-name">Coder</div><div class="nx-workshop-chat-sub">Pair agent</div></div></div>
            <button class="nx-workshop-chat-clear nx-btn nx-btn-sm nx-btn-ghost" type="button" id="nx-workshop-chat-clear" title="Clear conversation">Clear</button>
          </header>
          <div class="nx-workshop-chat-thread" id="nx-workshop-chat-thread" aria-live="polite"></div>
          <form class="nx-workshop-chat-form" id="nx-workshop-chat-form">
            <input type="text" id="nx-workshop-chat-input" class="nx-workshop-chat-input nx-input"
                   placeholder="Ask the coder"
                   aria-label="Ask the coder"
                   autocomplete="off">
            <button type="submit" class="nx-workshop-chat-send nx-btn nx-btn-icon" aria-label="Send">${icon("arrow-up", 16)}</button>
          </form>
        </aside>
      </div>
    </div>
  `;

  const codeEl = document.getElementById("nx-workshop-code");
  const langEl = document.getElementById("nx-workshop-lang");
  const outEl = document.getElementById("nx-workshop-out");
  const runBtn = document.getElementById("nx-workshop-run");

  const run = async () => {
    const code = codeEl.value;
    const language = (langEl.value || "").trim().toLowerCase();
    state._workshopCode = code;
    state._workshopLang = language;
    // Markup/style languages render in a sandboxed iframe instead of running.
    if (langs[language]?.preview) { renderWorkshopPreview(language, code, outEl); return; }
    // The language field is a free-text search box; guide typos before we
    // bother the sandbox.
    if (!available.includes(language)) {
      outEl.innerHTML = `<div class="nx-alert is-warn" role="alert">${icon("alert-triangle", 16)}<div class="nx-alert-body">Unknown language <b class="nx-mono">${escapeHtml(language || "(blank)")}</b>. Pick one from the list, ${available.length} are available.</div></div>`;
      return;
    }
    runBtn.disabled = true;
    outEl.innerHTML = `<div class="nx-loading"><span class="nx-spinner" aria-hidden="true"></span>Running in the sandbox</div>`;
    try {
      const r = await fetch("/api/workshop/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ language, code, workspace_id: state.active }),
      });
      if (!r.ok) {
        const txt = await r.text();
        outEl.innerHTML = `<pre class="nx-workshop-err">${escapeHtml(txt)}</pre>`;
        return;
      }
      const body = await r.json();
      // Capture the run output so the coder chat sees it on the next turn.
      _workshopThread.lastOutput = {
        exit_code: body.exit_code,
        elapsed_ms: body.elapsed_ms,
        stdout: body.stdout || "",
        stderr: body.stderr || "",
      };
      outEl.innerHTML = `
        <div class="nx-workshop-stats">
          <span class="nx-status ${body.exit_code === 0 ? 'ok is-ok' : 'fail is-danger'}">Exit ${body.exit_code}</span>
          <span class="nx-mono">${body.elapsed_ms} ms</span>
          ${body.truncated ? `<span class="warn nx-status is-warn">Truncated</span>` : ""}
        </div>
        ${body.stdout ? `<div class="nx-workshop-block"><div class="nx-workshop-block-lbl nx-section-label">stdout</div><pre>${escapeHtml(body.stdout)}</pre></div>` : ""}
        ${body.stderr ? `<div class="nx-workshop-block err"><div class="nx-workshop-block-lbl nx-section-label">stderr</div><pre>${escapeHtml(body.stderr)}</pre></div>` : ""}
        ${!body.stdout && !body.stderr ? `<div class="nx-empty-line">The program finished without printing anything.</div>` : ""}
      `;
      // Save to history (only successful runs we can recall)
      if (code && code.trim()) {
        saveHistoryEntry("workshop", {
          language, code,
          exit_code: body.exit_code,
          elapsed_ms: body.elapsed_ms,
        });
      }
    } catch (e) {
      outEl.innerHTML = `<pre class="nx-workshop-err">${escapeHtml(e.message)}</pre>`;
    } finally {
      runBtn.disabled = false;
    }
  };
  runBtn.addEventListener("click", run);
  document.getElementById("nx-workshop-history").addEventListener("click", (e) => {
    e.stopPropagation();
    openHistoryPopover(e.currentTarget, "workshop", (item) => {
      codeEl.value = item.code;
      langEl.value = item.language;
      state._workshopCode = item.code;
      state._workshopLang = item.language;
      codeEl.focus();
    });
  });
  codeEl.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") { e.preventDefault(); run(); }
  });
  codeEl.addEventListener("input", () => { state._workshopCode = codeEl.value; });

  // ── Chat thread (coder pair-programmer) ────────────────────────────────
  const chatThreadEl = document.getElementById("nx-workshop-chat-thread");
  const chatForm = document.getElementById("nx-workshop-chat-form");
  const chatInput = document.getElementById("nx-workshop-chat-input");

  const repaintChat = () => {
    if (_workshopThread.messages.length === 0) {
      chatThreadEl.innerHTML = emptyStateHTML({ icon: "message", title: "Ask the coder", body: `It reads your code and the last run. Try “what's wrong?” or “make this faster”.`, compact: false });
      return;
    }
    chatThreadEl.innerHTML = _workshopThread.messages.map((m, i) => {
      const codeBlocks = m.role === "assistant" ? extractCodeBlocks(m.content) : [];
      const applyBtn = codeBlocks.length > 0
        ? `<button class="nx-workshop-chat-apply nx-btn nx-btn-sm nx-btn-tinted" type="button" data-apply-idx="${i}" data-block-idx="0">${icon("corner-down-left", 12)}Apply code</button>`
        : "";
      const renderedBody = m.role === "assistant"
        ? renderMarkdownLite(m.content)
        : escapeHtml(m.content);
      return `
        <div class="nx-workshop-chat-msg ${m.role}">
          <span class="nx-workshop-chat-tag">${m.role === "user" ? "You" : "Coder"}</span>
          <div class="nx-workshop-chat-body">${renderedBody}</div>
          ${applyBtn}
        </div>
      `;
    }).join("");
    chatThreadEl.scrollTop = chatThreadEl.scrollHeight;
    chatThreadEl.querySelectorAll("[data-apply-idx]").forEach(btn => {
      btn.addEventListener("click", () => {
        const mi = parseInt(btn.dataset.applyIdx, 10);
        const bi = parseInt(btn.dataset.blockIdx, 10);
        const blocks = extractCodeBlocks(_workshopThread.messages[mi].content);
        if (blocks[bi]) {
          codeEl.value = blocks[bi].code;
          state._workshopCode = blocks[bi].code;
          if (blocks[bi].lang && available.includes(blocks[bi].lang)) {
            langEl.value = blocks[bi].lang;
            state._workshopLang = blocks[bi].lang;
          }
          btn.innerHTML = `${UI.check(12)} Applied. Press ⌘⏎ to run`;
          btn.disabled = true;
        }
      });
    });
  };

  const sendChat = async (text) => {
    if (!text.trim()) return;
    // Build a contextual prompt that includes current code + last run output,
    // so the coder agent doesn't have to ask. Re-attached on every turn.
    const ctxParts = [];
    if (codeEl.value.trim()) {
      ctxParts.push(`Current code (${langEl.value}):\n\n\`\`\`${langEl.value}\n${codeEl.value}\n\`\`\``);
    }
    if (_workshopThread.lastOutput) {
      const o = _workshopThread.lastOutput;
      const stat = `exit=${o.exit_code} · ${o.elapsed_ms}ms`;
      ctxParts.push(`Last run: ${stat}${o.stdout ? `\n\nSTDOUT:\n${o.stdout}` : ""}${o.stderr ? `\n\nSTDERR:\n${o.stderr}` : ""}`);
    }
    const userContent = ctxParts.length
      ? `${text}\n\n— context —\n${ctxParts.join("\n\n")}`
      : text;

    _workshopThread.messages.push({ role: "user", content: text });
    repaintChat();
    // Pending placeholder
    _workshopThread.messages.push({ role: "assistant", content: "Thinking", _pending: true });
    repaintChat();

    try {
      const r = await fetch("/api/cortex/continue", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          module: "coder",
          history: _workshopThread.messages
            .slice(0, -2)   // drop placeholder + current user msg (sent as message)
            .filter(m => !m._pending)
            .map(m => ({ role: m.role, content: m.content })),
          message: userContent,
          workspace_id: state.active || null,
        }),
      });
      _workshopThread.messages.pop();   // drop the placeholder
      if (r.ok) {
        const data = await r.json();
        _workshopThread.messages.push({ role: "assistant", content: data.response || "" });
      } else {
        _workshopThread.messages.push({ role: "assistant", content: `[error] ${r.status}: ${await r.text()}` });
      }
    } catch (err) {
      _workshopThread.messages.pop();
      _workshopThread.messages.push({ role: "assistant", content: `[network error] ${err.message}` });
    }
    repaintChat();
  };

  chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = chatInput.value;
    chatInput.value = "";
    sendChat(text);
  });
  document.getElementById("nx-workshop-chat-clear").addEventListener("click", () => {
    if (_workshopThread.messages.length && !confirm("Clear the coder chat?")) return;
    _workshopThread.messages = [];
    repaintChat();
  });

  repaintChat();
}

// Extract fenced ```lang\n...\n``` code blocks from an LLM reply.
function extractCodeBlocks(text) {
  if (!text) return [];
  const re = /```(\w+)?\n([\s\S]*?)```/g;
  const out = [];
  let m;
  while ((m = re.exec(text))) {
    out.push({ lang: (m[1] || "").toLowerCase(), code: m[2] });
  }
  return out;
}

// Tiny markdown — bold, inline code, fenced code blocks. Enough for the
// coder agent's replies without bringing in a full markdown library.
function renderMarkdownLite(text) {
  if (!text) return "";
  let html = escapeHtml(text);
  // Fenced code blocks (rendered with proper styling)
  html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre class="nx-workshop-chat-code"><code>${code}</code></pre>`);
  // Inline code
  html = html.replace(/`([^`\n]+)`/g, '<code class="nx-md-code">$1</code>');
  // Bold
  html = html.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  // Newlines
  html = html.replace(/\n/g, "<br>");
  return html;
}

// ── Search (in-OS web search) ─────────────────────────────────────────────
// Web search keeps a continuous thread of queries during the session
// rather than blowing away prior results on each new search. Each query
// appends a new section to the thread; "ask cortex about this" routes
// the results into the Cortex launcher pre-filled.
const _searchThread = { entries: [] /* [{query, hits, ts, error}] */ };

async function renderSearch(hash) {
  const main = document.getElementById("nx-main");
  const qMatch = hash.match(/[?&]q=([^&]+)/);
  const initial = qMatch ? decodeURIComponent(qMatch[1]) : "";
  main.innerHTML = `
    <div class="nx-main-inner">
      <header class="nx-page-head">
        <div class="nx-page-head-text">
          <div class="nx-eyebrow nx-page-eyebrow">Search</div>
          <h1 class="nx-page-title">Search the web without leaving</h1>
          <p class="nx-page-sub">Routes through <code class="nx-code-inline">aegis.network()</code>. The default provider is DuckDuckGo, with no tracking. Earlier queries stay visible below.</p>
        </div>
      </header>
      <form class="nx-search-bar" id="nx-search-form" role="search">
        ${icon("search", 16)}
        <input id="nx-search-q" type="search" value="${escapeHtml(initial)}" autofocus
               aria-label="Search the web"
               placeholder="What do you need to know?">
        <button type="button" id="nx-search-history" class="nx-history-btn nx-btn nx-btn-ghost nx-btn-sm" title="Recent searches">
          ${icon("history", 14)}
          <span>History</span>
        </button>
        <button type="button" id="nx-search-clear" class="nx-history-btn nx-btn nx-btn-ghost nx-btn-sm" title="Clear this thread">
          <span>Clear thread</span>
        </button>
        <button type="submit" class="nx-run-btn nx-btn nx-btn-primary">Search</button>
      </form>
      <div class="nx-search-thread" id="nx-search-thread"></div>
    </div>
  `;

  const formEl = document.getElementById("nx-search-form");
  const qEl = document.getElementById("nx-search-q");
  const threadEl = document.getElementById("nx-search-thread");

  const repaint = () => {
    if (_searchThread.entries.length === 0) {
      threadEl.innerHTML = emptyStateHTML({ icon: "globe", title: "No searches yet", body: "Type a query above. Each new search stacks here, so you can compare results across queries." });
      return;
    }
    threadEl.innerHTML = _searchThread.entries.slice().reverse().map((e, revIdx) => {
      const idx = _searchThread.entries.length - 1 - revIdx;
      if (e.pending) {
        return `
          <section class="nx-search-section pending" data-idx="${idx}">
            <header class="nx-search-section-head">
              <div class="nx-eyebrow">Query · ${escapeHtml(chatHistoryRelative(e.ts))}</div>
              <div class="nx-search-section-q">${escapeHtml(e.query)}</div>
            </header>
            <div class="nx-search-results" aria-busy="true">${[0, 1, 2].map(() => `<div class="nx-search-hit"><span class="nx-skeleton nx-skeleton-title"></span><span class="nx-skeleton nx-skeleton-short"></span><span class="nx-skeleton nx-skeleton-line"></span></div>`).join("")}</div>
          </section>
        `;
      }
      if (e.error) {
        return `
          <section class="nx-search-section fail" data-idx="${idx}">
            <header class="nx-search-section-head">
              <div class="nx-eyebrow">Query · ${escapeHtml(chatHistoryRelative(e.ts))}</div>
              <div class="nx-search-section-q">${escapeHtml(e.query)}</div>
            </header>
            <div class="nx-alert is-danger" role="alert">${icon("alert-circle", 16)}<div class="nx-alert-body">${escapeHtml(e.error)}</div></div>
          </section>
        `;
      }
      const resultsHTML = e.hits.length === 0
        ? `<div class="nx-empty-line">No results for ${escapeHtml(e.query)}. Try different words.</div>`
        : e.hits.map((h, hi) => `
            <div class="nx-search-hit" data-open-reader="${idx}:${hi}" tabindex="0" role="button">
              <div class="hit-title">${escapeHtml(h.title || h.url)}</div>
              <div class="hit-url">${escapeHtml(h.url)}</div>
              ${h.snippet ? `<div class="hit-snippet">${escapeHtml(h.snippet)}</div>` : ""}
              <div class="hit-actions">
                ${h.source ? `<span class="hit-source">${escapeHtml(h.source)}</span>` : ""}
                <a class="hit-external nx-link" href="${escapeHtml(h.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">Open in browser ${icon("external-link", 12)}</a>
              </div>
            </div>
          `).join("");
      return `
        <section class="nx-search-section" data-idx="${idx}">
          <header class="nx-search-section-head">
            <div class="nx-search-section-meta">
              <div class="nx-eyebrow">Query · ${escapeHtml(chatHistoryRelative(e.ts))}</div>
              <div class="nx-search-section-q">${escapeHtml(e.query)}</div>
            </div>
            <div class="nx-search-section-actions">
              <span class="nx-search-count">${e.hits.length} ${e.hits.length === 1 ? "result" : "results"}</span>
              <button class="nx-search-ask-cortex nx-btn nx-btn-sm nx-btn-tinted" type="button" data-ask-cortex="${idx}">${icon("workflow", 12)}Ask Cortex about these</button>
            </div>
          </header>
          <div class="nx-search-results">${resultsHTML}</div>
        </section>
      `;
    }).join("");
    // Wire ask-cortex buttons
    threadEl.querySelectorAll("[data-ask-cortex]").forEach(btn => {
      btn.addEventListener("click", () => {
        const i = parseInt(btn.dataset.askCortex, 10);
        const e = _searchThread.entries[i];
        if (!e) return;
        const summary = e.hits.slice(0, 5).map((h, j) =>
          `${j + 1}. ${h.title || h.url}: ${h.url}${h.snippet ? `\n   ${h.snippet}` : ""}`
        ).join("\n");
        const prompt = `I searched the web for "${e.query}" and got these top results:\n\n${summary}\n\nWhat should I take away from this?`;
        location.hash = `#/cortex?prompt=${encodeURIComponent(prompt)}`;
      });
    });
    // Wire open-reader on each hit
    threadEl.querySelectorAll("[data-open-reader]").forEach(el => {
      const onOpen = () => {
        const [ei, hi] = el.dataset.openReader.split(":").map(Number);
        const entry = _searchThread.entries[ei];
        if (!entry) return;
        const hit = entry.hits[hi];
        if (!hit) return;
        openReaderPanel(hit);
      };
      el.addEventListener("click", onOpen);
      el.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(); }
      });
    });
  };

  // Reader panel — slides over the search thread, fetches the page via
  // /api/search/reader, shows clean text + LLM digest. No tab switching.
  async function openReaderPanel(hit) {
    let panel = document.getElementById("nx-reader-panel");
    if (!panel) {
      panel = document.createElement("aside");
      panel.id = "nx-reader-panel";
      panel.className = "nx-reader-panel";
      document.body.appendChild(panel);
    }
    panel.classList.add("open");
    panel.innerHTML = `
      <header class="nx-reader-head">
        <div class="nx-reader-meta">
          <div class="nx-eyebrow">Reader · in-app preview</div>
          <h2>${escapeHtml(hit.title || hit.url)}</h2>
          <a class="nx-reader-url" href="${escapeHtml(hit.url)}" target="_blank" rel="noopener">${escapeHtml(hit.url)} ${icon("external-link", 12)}</a>
        </div>
        <button class="nx-reader-close nx-icon-btn" type="button" aria-label="Close reader">${UI.close(16)}</button>
      </header>
      <section class="nx-reader-digest">
        <div class="nx-section-label">Digest, LLM summary</div>
        <div class="nx-reader-digest-body nx-dim"><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-short"></span></div>
      </section>
      <section class="nx-reader-text">
        <div class="nx-section-label">Clean text</div>
        <div class="nx-reader-text-body nx-dim"><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-line"></span><span class="nx-skeleton nx-skeleton-short"></span></div>
      </section>
      <footer class="nx-reader-actions">
        <button class="nx-reader-ask nx-btn nx-btn-primary nx-btn-block" type="button">${icon("workflow", 14)}Ask Cortex about this page</button>
      </footer>
    `;
    panel.querySelector(".nx-reader-close").addEventListener("click", () => {
      panel.classList.remove("open");
    });
    try {
      const r = await fetch(`/api/search/reader?url=${encodeURIComponent(hit.url)}&digest=true`);
      if (!r.ok) {
        panel.querySelector(".nx-reader-text-body").innerHTML = `<span class="fail">The reader could not load this page (HTTP ${r.status}).</span>`;
        panel.querySelector(".nx-reader-digest-body").innerHTML = "";
        return;
      }
      const data = await r.json();
      const digestBody = panel.querySelector(".nx-reader-digest-body");
      const textBody = panel.querySelector(".nx-reader-text-body");
      if (data.digest) {
        digestBody.classList.remove("nx-dim");
        digestBody.innerHTML = escapeHtml(data.digest).replace(/\n/g, "<br>");
      } else {
        digestBody.innerHTML = `<span class="nx-dim">${escapeHtml(data.error || "No digest available.")}</span>`;
      }
      if (data.text) {
        textBody.classList.remove("nx-dim");
        textBody.innerHTML = escapeHtml(data.text).replace(/\n/g, "<br>") + (data.truncated ? `<div class="nx-reader-trunc">Truncated. Open it in the browser for the full page.</div>` : "");
      } else {
        textBody.innerHTML = `<span class="nx-dim">${escapeHtml(data.error || "No text could be extracted.")}</span>`;
      }
      panel.querySelector(".nx-reader-ask").addEventListener("click", () => {
        const ctx = (data.digest || data.text || "").slice(0, 2000);
        const prompt = `I'm reading ${data.url} (${data.title || "untitled"}). Here's what it says:\n\n${ctx}\n\nHelp me reason about this.`;
        location.hash = `#/cortex?prompt=${encodeURIComponent(prompt)}`;
      });
    } catch (err) {
      panel.querySelector(".nx-reader-text-body").innerHTML = `<span class="fail">Network error: ${escapeHtml(err.message)}</span>`;
    }
  }

  const doSearch = async (q) => {
    if (!q) return;
    const entry = { query: q, hits: [], ts: new Date().toISOString(), pending: true };
    _searchThread.entries.push(entry);
    repaint();
    try {
      const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=12`);
      entry.pending = false;
      if (!r.ok) {
        entry.error = `Search failed: ${await r.text()}`;
        repaint();
        return;
      }
      const body = await r.json();
      entry.hits = body.hits || [];
      saveHistoryEntry("search", { query: q, hit_count: entry.hits.length });
      repaint();
    } catch (err) {
      entry.pending = false;
      entry.error = `Network error: ${err.message}`;
      repaint();
    }
    // Clear the input so the next query is fresh — keeps the thread feeling continuous.
    qEl.value = "";
    qEl.focus();
  };

  formEl.addEventListener("submit", (e) => { e.preventDefault(); doSearch(qEl.value.trim()); });
  document.getElementById("nx-search-history").addEventListener("click", (e) => {
    e.stopPropagation();
    openHistoryPopover(e.currentTarget, "search", (item) => {
      qEl.value = item.query;
      doSearch(item.query);
    });
  });
  document.getElementById("nx-search-clear").addEventListener("click", () => {
    if (_searchThread.entries.length && !confirm("Clear all queries from this thread?")) return;
    _searchThread.entries = [];
    repaint();
  });

  repaint();
  if (initial) doSearch(initial);
}

// ── Overlay: workspace switcher (⌘K) ──────────────────────────────────────
function renderSwitcher() {
  const root = document.getElementById("nx-overlay-root");
  const tiles = state.workspaces.map(w => {
    const tone = (w.tone || "indigo").toLowerCase();
    const isActive = w.workspace_id === state.active;
    return `
    <button type="button" class="nx-switch-row nx-row nx-row-interactive ${isActive ? "active is-selected" : ""}" role="option" aria-selected="${isActive}"
         data-id="${w.workspace_id}" style="--tone:var(--nx-tone-${escapeHtml(tone)}-a, var(--nx-accent))">
      <span class="ws-dot nx-switch-dot" aria-hidden="true"></span>
      <span class="nx-row-main">
        <span class="nx-row-title tile-name">${escapeHtml(w.name)}</span>
        <span class="nx-row-sub tile-eyebrow">${escapeHtml(tone)} · ${escapeHtml(w.workspace_id)}</span>
      </span>
      <span class="nx-row-trail">${isActive ? `<span class="nx-status is-live">Active</span>` : (w.last_active_at ? `Seen ${escapeHtml(chatHistoryRelative(w.last_active_at))}` : "")}</span>
    </button>
  `;
  }).join("");
  root.innerHTML = `
    <div class="nx-switcher-overlay nx-scrim nx-scrim-top" id="nx-switcher-overlay">
      <div class="nx-switcher nx-modal" role="dialog" aria-modal="true" aria-labelledby="nx-switcher-title">
        <div class="nx-modal-head">
          <div>
            <h3 class="nx-modal-title" id="nx-switcher-title">Switch workspace</h3>
            <p class="nx-modal-sub">${state.workspaces.length} workspace${state.workspaces.length === 1 ? "" : "s"} on this machine.</p>
          </div>
          <span class="nx-kbd">esc</span>
        </div>
        <div class="nx-modal-body nx-switcher-body">
          <div class="nx-switcher-grid nx-list" role="listbox" aria-label="Workspaces">
            ${tiles}
          </div>
        </div>
        <div class="nx-modal-foot">
          <button type="button" class="nx-btn" id="nx-new-workspace-overlay">${icon("plus", 14)}New workspace<span class="nx-kbd">⌘N</span></button>
        </div>
      </div>
    </div>
  `;
  root.querySelector(".nx-switch-row")?.focus();
  root.querySelectorAll(".nx-switch-row[data-id]").forEach(el => {
    el.addEventListener("click", async () => {
      await fetch(`/api/workspaces/${el.dataset.id}/switch`, { method: "POST" });
      await loadWorkspaces();
      renderSidebar();
      renderChromeContext();
      closeOverlay();
      location.hash = `#/conversation/${el.dataset.id}`;
    });
  });
  document.getElementById("nx-new-workspace-overlay").addEventListener("click", openNewWorkspaceForm);
  document.getElementById("nx-switcher-overlay").addEventListener("click", (e) => {
    if (e.target.id === "nx-switcher-overlay") closeOverlay();
  });
}

// ── Overlay: new workspace form (⌘N) ──────────────────────────────────────
const WORKSPACE_TONES = [
  "indigo", "violet", "lavender", "cobalt", "sky", "ocean", "teal",
  "mint", "sage", "emerald", "lime",
  "amber", "honey", "tangerine", "mocha",
  "coral", "rose", "crimson",
  "magenta", "fuchsia", "plum", "orchid",
  "slate", "graphite", "midnight",
];

function _toneSwatchHex(tone, part = "a") {
  const computed = getComputedStyle(document.documentElement);
  return computed.getPropertyValue(`--nx-tone-${tone}-${part}`).trim() || "#888";
}

// A workspace's emblem: a mark in its own tone with its initials.
function workspaceEmblem(w, size = 32) {
  const tone = (w.tone || "indigo").toLowerCase();
  return identityDisc({ size, slug: w.name || w.workspace_id, shape: "squircle", gradient: [_toneSwatchHex(tone, "a"), _toneSwatchHex(tone, "b")] });
}

function openNewWorkspaceForm() {
  const root = document.getElementById("nx-overlay-root");
  let selectedTone = "indigo";

  const toneSwatchHTML = WORKSPACE_TONES.map(t => `
    <button type="button" class="nx-ws-tone-swatch ${t === selectedTone ? "selected" : ""}" data-tone="${t}" title="${t}" aria-pressed="${t === selectedTone}" style="--tone:var(--nx-tone-${t}-a)">
      <span class="dot" aria-hidden="true"></span>
      <span class="label">${t}</span>
    </button>
  `).join("");

  root.innerHTML = `
    <div class="nx-switcher-overlay nx-scrim" id="nx-newws-overlay">
      <form class="nx-switcher nx-newws nx-modal" id="nx-newws-form" autocomplete="off" role="dialog" aria-modal="true" aria-labelledby="nx-newws-title">
        <div class="nx-modal-head">
          <div>
            <h3 class="nx-modal-title" id="nx-newws-title">New workspace</h3>
            <p class="nx-modal-sub">A room with its own agents, memory and grants.</p>
          </div>
        </div>
        <div class="nx-modal-body nx-newws-fields">
          <label class="nx-field">
            <span class="nx-field-label">Name</span>
            <input id="ws-name" class="nx-newws-input nx-input nx-input-lg" placeholder="Client work" required autofocus>
          </label>
          <label class="nx-field">
            <span class="nx-field-label">ID</span>
            <input id="ws-id" class="nx-newws-input nx-input nx-input-mono" placeholder="client-work" pattern="^[a-z][a-z0-9-]{0,63}$">
            <span class="nx-field-hint">Lowercase letters, numbers and hyphens. Filled in from the name.</span>
          </label>

          <div class="nx-field">
            <span class="nx-field-label nx-newws-tones-label">Tone</span>
            <div class="nx-newws-tones" id="ws-tones">
              ${toneSwatchHTML}
            </div>
          </div>
          <input type="hidden" id="ws-tone" value="${selectedTone}">

          <div id="ws-error" class="nx-newws-error nx-field-error" role="alert"></div>
        </div>
        <div class="nx-modal-foot nx-newws-actions">
          <button type="button" class="nx-newws-cancel nx-btn nx-btn-ghost" id="ws-cancel">Cancel</button>
          <button type="submit" class="nx-newws-create nx-btn nx-btn-primary" id="ws-create">Create workspace</button>
        </div>
      </form>
    </div>`;

  // Wire swatch selection
  root.querySelectorAll(".nx-ws-tone-swatch[data-tone]").forEach(btn => {
    btn.addEventListener("click", () => {
      root.querySelectorAll(".nx-ws-tone-swatch").forEach(b => { b.classList.remove("selected"); b.setAttribute("aria-pressed", "false"); });
      btn.classList.add("selected");
      btn.setAttribute("aria-pressed", "true");
      document.getElementById("ws-tone").value = btn.dataset.tone;
    });
  });

  const nameInput = document.getElementById("ws-name");
  const idInput = document.getElementById("ws-id");
  let userTypedSlug = false;
  idInput.addEventListener("input", () => { userTypedSlug = idInput.value.length > 0; });
  nameInput.addEventListener("input", () => {
    if (!userTypedSlug) {
      idInput.value = nameInput.value.toLowerCase().trim()
        .replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 64);
    }
  });

  document.getElementById("ws-cancel").addEventListener("click", (e) => {
    e.preventDefault();
    closeOverlay();
  });
  document.getElementById("nx-newws-overlay").addEventListener("click", (e) => {
    if (e.target.id === "nx-newws-overlay") closeOverlay();
  });
  document.getElementById("nx-newws-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = nameInput.value.trim();
    let id = idInput.value.trim();
    const tone = document.getElementById("ws-tone").value;
    const errEl = document.getElementById("ws-error");
    errEl.textContent = "";
    if (!name) { errEl.textContent = "Name is required."; return; }
    if (!id) {
      id = name.toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 64);
    }
    if (!/^[a-z][a-z0-9-]{0,63}$/.test(id)) {
      errEl.textContent = "The ID must start with a letter and use only lowercase letters, numbers and hyphens.";
      return;
    }
    try {
      const r = await fetch("/api/workspaces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ workspace_id: id, name, tone }),
      });
      if (r.ok) {
        await fetch(`/api/workspaces/${encodeURIComponent(id)}/switch`, { method: "POST" });
        await loadWorkspaces();
        renderSidebar();
        renderChromeContext();
        closeOverlay();
        location.hash = `#/conversation/${id}`;
      } else {
        const err = await r.json().catch(() => ({ detail: "The request failed." }));
        errEl.textContent = err.detail || "Could not create the workspace.";
      }
    } catch (err) {
      errEl.textContent = "Network error: " + err.message;
    }
  });
}

function closeOverlay() {
  // The expanded cockpit may host a live scene canvas; tear it down before the
  // overlay root is cleared so its rAF loop doesn't outlive the canvas.
  if (typeof unregisterScene === "function") unregisterScene("cockpit");
  document.getElementById("nx-overlay-root").innerHTML = "";
}

// ── Overlay: expanded cockpit (⌘0) ─────────────────────────────────────────
async function toggleCockpitOverlay() {
  const root = document.getElementById("nx-overlay-root");
  if (root.querySelector(".nx-cockpit-overlay")) { closeOverlay(); return; }
  root.innerHTML = `
    <div class="nx-cockpit-overlay nx-scrim" id="nx-cockpit-overlay">
      <div class="nx-cockpit nx-modal nx-modal-wide" role="dialog" aria-modal="true" aria-labelledby="nx-cockpit-title">
        <div class="nx-cockpit-scan" aria-hidden="true"></div>
        <div class="nx-cockpit-header nx-modal-head">
          <div>
            <div class="nx-eyebrow">Cockpit · ${escapeHtml((state.mood.mood || "calm_focus").replace(/_/g, " "))}</div>
            <h3 class="nx-cockpit-title nx-modal-title" id="nx-cockpit-title">Everything the kernel is doing</h3>
          </div>
          <button class="nx-cockpit-close nx-btn nx-btn-sm nx-btn-ghost" type="button" id="nx-cockpit-close">Close<span class="nx-kbd">esc</span></button>
        </div>
        <div class="nx-modal-body">
        <div class="nx-cockpit-grid">
          <!-- Row 1: Trust spans 2 cols on the left · Mood · Workspaces -->
          <div class="nx-cockpit-panel span2">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Trust · 60m</span>
              <span class="nx-cockpit-panel-badge">${state.trust.history.length} events</span>
            </div>
            <div class="nx-cockpit-stat">
              <span class="nx-stat-value">${state.trust.delta > 0 ? "+" : ""}${state.trust.delta.toFixed(2)}</span>
              <span class="nx-trust-state">${escapeHtml(state.trust.direction || "steady")}</span>
            </div>
            <svg class="nx-cockpit-spark" viewBox="0 0 320 92" preserveAspectRatio="none" aria-hidden="true">
              ${trustSparkSVG(state.trust.history.length ? state.trust.history : [], state.trust.direction)}
            </svg>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Ambient mood</span></div>
            <div class="nx-cockpit-mood"><span class="nx-mp-swatch nx-mood-preview-${escapeHtml((state.mood.mood || "calm_focus").replace(/_/g, "-"))}" aria-hidden="true"></span><span class="nx-cockpit-big">${escapeHtml((state.mood.mood || "calm_focus").replace(/_/g, " "))}</span></div>
            <div class="nx-cockpit-note">${escapeHtml(state.mood.reason || "")}</div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Workspaces</span>
              <span class="nx-cockpit-panel-badge">${state.workspaces.length}</span>
            </div>
            <div class="nx-cockpit-list">${state.workspaces.map(w => `<div><span class="nx-cockpit-dot" style="--tone:var(--nx-tone-${escapeHtml((w.tone || "indigo").toLowerCase())}-a)"></span>${escapeHtml(w.name)}</div>`).join("") || "<div class='nx-empty-line'>None yet.</div>"}</div>
          </div>

          <!-- Row 2: Recent permissions spans 3 cols · Pending tickets on the right -->
          <div class="nx-cockpit-panel span3">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Recent permissions</span>
              <span class="nx-cockpit-panel-badge">${state.perms.recent.length}</span>
            </div>
            <div class="nx-cockpit-list">
              ${(state.perms.recent.slice(0, 6).map(r =>
                `<div class="nx-cockpit-tail-row"><span class="nx-mono">${escapeHtml(r.capability || "")}</span><span class="nx-cockpit-target">${escapeHtml(r.target || "")}</span><span class="nx-perm-status s-${escapeHtml((r.status || "auto").toLowerCase())}">${escapeHtml(r.status || "")}</span></div>`
              )).join("") || "<div class='nx-empty-line'>No permission activity yet.</div>"}
            </div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Pending</span></div>
            <div class="nx-stat-value ${state.perms.pending.length ? "nx-cockpit-warn" : ""}">${state.perms.pending.length}</div>
            <div class="nx-cockpit-note">ticket${state.perms.pending.length === 1 ? "" : "s"} awaiting a decision</div>
          </div>

          <!-- Row 3: the live Kernel Scene spans all 4 cols -->
          <div class="nx-cockpit-panel span4">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Kernel scene · live</span>
              <span class="nx-cockpit-panel-badge">⌘J opens the full Watch view</span>
            </div>
            <div class="nx-cockpit-scene"><canvas id="nx-cockpit-scene-canvas"></canvas></div>
          </div>

          <!-- Row 4: legible kernel ledger + sigil radar -->
          <div class="nx-cockpit-panel span2">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Kernel · live</span>
              <span class="nx-cockpit-panel-badge">${state.kernelViz.routes.length + state.kernelViz.gates.length} events</span>
            </div>
            <div id="nx-cockpit-kernel-live">${kernelVizHTML()}</div>
          </div>
          <div class="nx-cockpit-panel span2">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Sigil radar</span>
              <span class="nx-cockpit-panel-badge">${state.kernelViz.detections.length} pings</span>
            </div>
            <div>${state.kernelViz.detections.map(radarPingHTML).join("") || "<div class='nx-empty-line'>Radar clear. No anomalies.</div>"}</div>
          </div>
        </div>
        </div>
      </div>
    </div>
  `;
  document.getElementById("nx-cockpit-close").addEventListener("click", closeOverlay);
  document.getElementById("nx-cockpit-overlay").addEventListener("click", (e) => {
    if (e.target.id === "nx-cockpit-overlay") closeOverlay();
  });
  const cpCanvas = document.getElementById("nx-cockpit-scene-canvas");
  if (cpCanvas) { registerScene("cockpit", cpCanvas, { compact: false }); if (!state.scene.modules.length) await loadKernelScene(); }
}

// ── Router ────────────────────────────────────────────────────────────────
async function route(hash) {
  await loadWorkspaces();
  renderSidebar();
  if (!hash || hash === "#" || hash === "#/") {
    if (state.active) {
      location.hash = `#/conversation/${state.active}`;
      return;
    }
    renderWorkspacesGrid();
    return;
  }
  // The full-screen Watch scene owns a canvas + rAF loop; tear it down whenever
  // we navigate anywhere else so it never animates a detached canvas.
  if (!hash.startsWith("#/watch")) unregisterScene("watch");
  if (!hash.startsWith("#/memory")) pauseReplay();
  if (hash.startsWith("#/watch")) { await renderWatch(); return; }
  if (hash.startsWith("#/memory")) { await renderMemory(); return; }
  if (hash === "#/workspaces") { renderWorkspacesGrid(); return; }
  if (hash.startsWith("#/store")) { renderStore(hash); return; }
  if (hash.startsWith("#/catalog")) { renderCatalog(); return; }
  if (hash === "#/settings") { renderSettings(); return; }
  if (hash.startsWith("#/cortex")) { renderCortexLauncher(hash); return; }
  if (hash === "#/workshop") { renderWorkshop(); return; }
  if (hash === "#/atlas") { await renderAtlasGraph(); return; }
  if (hash === "#/chronos") { await renderChronosTimeline(); return; }
  if (hash.startsWith("#/search")) { renderSearch(hash); return; }
  if (hash.startsWith("#/guide")) {
    const m = hash.match(/#\/guide\/(\d+)/);
    const pi = m ? Math.max(0, Math.min(GUIDE_PAGES.length - 1, Number(m[1]))) : 0;
    renderGuide(pi);
    // Keep the underlying view too — go to active conversation if there is one
    if (state.active && !document.getElementById("nx-main").innerHTML.trim()) {
      renderConversation(state.active);
    }
    return;
  }
  if (hash.startsWith("#/conversation/")) {
    const id = decodeURIComponent(hash.slice("#/conversation/".length));
    await renderConversation(id);
    return;
  }
  document.getElementById("nx-main").innerHTML = `<div class="nx-empty">unknown route: ${escapeHtml(hash)}</div>`;
}
window.addEventListener("hashchange", () => route(location.hash));

// ── Streams ───────────────────────────────────────────────────────────────
function subscribeStreams() {
  const wsProto = location.protocol === "https:" ? "wss:" : "ws:";
  // Mood — but skip the auto-apply while a manual override is active so a
  // deliberate pick doesn't get stomped 2s later by the next WS push.
  try {
    const w = new WebSocket(`${wsProto}//${location.host}/api/mood/ws`);
    w.onmessage = (e) => {
      try {
        const body = JSON.parse(e.data);
        // Always refresh the "current kernel mood" reason for the cockpit card
        state.mood.kernelMood = body.mood;
        state.mood.reason = body.reason || "";
        if (!state.mood.override) {
          state.mood.mood = body.mood;
          applyMood(body.mood);
        }
        renderMoodCard();
      } catch {}
    };
  } catch {}
  // Permissions — only re-render conversation when the pending SET actually
  // changes (otherwise the 2s WS push wipes focus + scroll + in-flight text).
  let lastPendingKey = "";
  try {
    const w = new WebSocket(`${wsProto}//${location.host}/api/permissions/ws`);
    w.onmessage = (e) => {
      try {
        const body = JSON.parse(e.data);
        const pending = body.pending || [];
        const newKey = pending.map(p => p.id).sort().join(",");
        if (newKey === lastPendingKey) return;  // no change, do nothing
        lastPendingKey = newKey;
        state.perms.pending = pending;
        renderCockpitRail();
        if (location.hash.startsWith("#/conversation/")) {
          const id = decodeURIComponent(location.hash.slice("#/conversation/".length));
          renderConversation(id);
        }
      } catch {}
    };
  } catch {}
  // Kernel events — kernel.route / kernel.gate / sigil.detection /
  // aegis.trust_change stream over the all-topics Pulse relay. No polling.
  try {
    const w = new WebSocket(`${wsProto}//${location.host}/api/events/ws`);
    w.onmessage = (e) => {
      try { handleKernelEvent(JSON.parse(e.data)); } catch {}
    };
  } catch {}
  // Trust + permission log: poll every 30s, only refresh cockpit (never the
  // conversation) so the user's typing isn't disrupted.
  setInterval(async () => {
    await Promise.allSettled([loadTrust(), loadPermissions()]);
    renderCockpitRail();
  }, 30000);
  // Keep the runnable-agents figure live (catalog count updates on rebuilds).
  setInterval(refreshRunnableCount, 60000);
  // Trust event temperature overlays — flash a brief gold/steel/crimson wash
  // on the body when a new trust_change event lands in chronicle.
  setInterval(pollTrustEvents, 2000);
}

// ── Trust event temperature overlays ──────────────────────────────────────
let _lastTrustEventId = null;
async function pollTrustEvents() {
  try {
    const r = await fetch("/api/chronicle?source=aegis&event_type=aegis.trust_change&limit=1");
    if (!r.ok) return;
    const body = await r.json();
    const events = body.entries || [];
    if (events.length === 0) return;
    const ev = events[0];
    if (ev.id === _lastTrustEventId) return;
    _lastTrustEventId = ev.id;

    const payload = ev.payload || {};
    let cls;
    if (typeof payload.new_score === "number" && payload.new_score < 0.50) {
      cls = "nx-trust-wash-collapse";
    } else if (typeof payload.new_score === "number" && typeof payload.old_score === "number"
               && payload.new_score > payload.old_score) {
      cls = "nx-trust-wash-rising";
    } else {
      cls = "nx-trust-wash-falling";
    }
    document.body.classList.add(cls);
    setTimeout(() => document.body.classList.remove(cls), 1500);
  } catch {}
}

// ── Keybinds ──────────────────────────────────────────────────────────────
// ── Clipboard shortcuts (⌘/Ctrl + C / X / V) ────────────────────────────────
// The Tauri WebView ships no Edit menu, so macOS never binds ⌘C/⌘V/⌘X to text
// inputs there. This capture-phase handler performs copy/cut/paste itself via
// the async Clipboard API, so the shortcuts work in the native app today
// (no rebuild) and remain correct in the browser.
function installClipboardShortcuts() {
  const editableEl = () => {
    const el = document.activeElement;
    if (!el) return null;
    if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") return el;
    if (el.isContentEditable) return el;
    return null;
  };
  const selectedText = (el) => {
    if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
      const s = el.selectionStart, e = el.selectionEnd;
      if (s != null && e != null && e > s) return el.value.slice(s, e);
      return "";
    }
    return window.getSelection ? String(window.getSelection() || "") : "";
  };
  document.addEventListener("keydown", async (e) => {
    const meta = e.metaKey || e.ctrlKey;
    if (!meta || e.altKey) return;
    const key = (e.key || "").toLowerCase();
    if (key !== "c" && key !== "x" && key !== "v") return;
    if (!navigator.clipboard) return;   // let the platform try if no API
    const el = editableEl();

    if (key === "c" || key === "x") {
      const text = selectedText(el);
      if (!text) return;                // nothing selected — leave default
      e.preventDefault(); e.stopPropagation();
      try { await navigator.clipboard.writeText(text); } catch { return; }
      if (key === "x" && el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA")) {
        const s = el.selectionStart, en = el.selectionEnd;
        el.setRangeText("", s, en, "end");
        el.dispatchEvent(new Event("input", { bubbles: true }));
      } else if (key === "x" && el && el.isContentEditable) {
        document.execCommand("delete");
      }
      return;
    }

    // paste — only into an editable target
    if (key === "v") {
      if (!el) return;
      e.preventDefault(); e.stopPropagation();
      let text = "";
      try { text = await navigator.clipboard.readText(); } catch { return; }
      if (!text) return;
      if (el.tagName === "INPUT" || el.tagName === "TEXTAREA") {
        const s = el.selectionStart ?? el.value.length;
        const en = el.selectionEnd ?? el.value.length;
        el.setRangeText(text, s, en, "end");
        el.dispatchEvent(new Event("input", { bubbles: true }));
      } else if (el.isContentEditable) {
        document.execCommand("insertText", false, text);
      }
    }
  }, true);  // capture phase — run before app keybinds
}

function attachKeybinds() {
  window.addEventListener("keydown", (e) => {
    const meta = e.metaKey || e.ctrlKey;
    if (meta && e.key === "k") { e.preventDefault(); loadWorkspaces().then(renderSwitcher); return; }
    if (meta && e.key === "n") { e.preventDefault(); openNewWorkspaceForm(); return; }
    if (meta && e.key === "0") { e.preventDefault(); toggleCockpitOverlay(); return; }
    if (meta && (e.key === "p" || e.key === "P")) { e.preventDefault(); location.hash = "#/settings"; return; }
    if (meta && e.key === "e") { e.preventDefault(); location.hash = "#/workshop"; return; }
    if (meta && (e.key === "l" || e.key === "L")) { e.preventDefault(); location.hash = "#/cortex"; return; }
    if (meta && (e.key === "j" || e.key === "J")) { e.preventDefault(); location.hash = "#/watch"; return; }
    if (meta && (e.key === "y" || e.key === "Y")) { e.preventDefault(); location.hash = "#/memory"; return; }
    if (meta && e.key === "/") { e.preventDefault(); location.hash = "#/search"; return; }
    if (e.key === "?" && document.activeElement === document.body) {
      e.preventDefault(); renderGuide(0); return;
    }
    if (e.key === "Escape") {
      // Esc: close any overlay AND exit focus mode if it was on
      if (document.body.classList.contains("nx-focus-mode")) {
        document.body.classList.remove("nx-focus-mode");
      }
      closeOverlay();
      return;
    }
    if (e.key === "/" && document.activeElement === document.body) {
      e.preventDefault();
      document.getElementById("nx-search-input").focus();
    }
  });
}

// ── Utilities ─────────────────────────────────────────────────────────────
// Inline custom properties that tint a card or header with an agent's own
// mark colors (see .nx-agent-tinted and .nx-agent-hero in app.css).
function agentTintStyle(slug) {
  const [a, b] = agentColors(slug);
  return `--mark-a:${a};--mark-b:${b}`;
}

// Shared empty state (components.css .nx-empty-state). `body` and `actions`
// are trusted HTML built by the caller; `title` is escaped here.
function emptyStateHTML({ icon: name = "inbox", title = "", body = "", actions = "", compact = false } = {}) {
  return `
    <div class="nx-empty-state${compact ? " nx-empty-state-compact" : ""}">
      <span class="nx-empty-state-icon">${icon(name, 20)}</span>
      ${title ? `<div class="nx-empty-state-title">${escapeHtml(title)}</div>` : ""}
      ${body ? `<div class="nx-empty-state-body">${body}</div>` : ""}
      ${actions ? `<div class="nx-empty-state-actions">${actions}</div>` : ""}
    </div>`;
}

function escapeHtml(s) {
  if (s == null) return "";
  const d = document.createElement("div");
  d.textContent = String(s);
  return d.innerHTML;
}
function truncate(s, n) {
  s = String(s);
  if (s.length <= n) return s;
  return s.slice(0, Math.max(1, n - 1)) + "…";
}
function formatTime(s) {
  if (!s) return "";
  try {
    const d = new Date(s);
    if (isNaN(d.getTime())) return "";
    const hh = String(d.getHours()).padStart(2, "0");
    const mm = String(d.getMinutes()).padStart(2, "0");
    return `${hh}:${mm}`;
  } catch { return ""; }
}

// ── Go ────────────────────────────────────────────────────────────────────
boot();
