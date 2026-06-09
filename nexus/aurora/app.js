/* ───────────────────────────────────────────────────────────────────────────
 * ONEXUS Aurora — application bootstrap and renderers.
 * Layout: persistent window shell with sidebar + main + cockpit rail.
 * Overlays for ⌘K switcher / ⌘N new workspace / ⌘0 cockpit / ⌘P settings.
 * ─────────────────────────────────────────────────────────────────────────── */

import { KERNEL_MARK, agentDisc, identityDisc, GRADIENTS, GLYPHS, UI, BUILTIN_CAPABILITIES } from "/aurora/static/icons.js";

// ── State ──────────────────────────────────────────────────────────────────
const state = {
  workspaces: [],
  active: null,
  thread: new Map(),       // workspace_id -> array of message records
  attachments: new Map(),  // workspace_id -> array of pending file uploads
  agents: [],              // catalog/runtime metadata
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
  mood: {
    mood: "calm_focus",
    tone: null,
    reason: "",
  },
  user: { initials: "you", name: "you" },
};

// ── Boot ──────────────────────────────────────────────────────────────────
async function boot() {
  document.getElementById("nx-kernel-mark").innerHTML = KERNEL_MARK(16);
  startClock();
  attachShellHandlers();
  attachKeybinds();
  await loadAll();
  renderSidebar();
  renderCockpitRail();
  subscribeStreams();
  await route(location.hash);
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
    body: "ONEXUS runs agents the way iOS runs apps. A short tour — eight scenes, sixty seconds, skip whenever.",
    diagram: () => sceneWelcome(),
  },
  {
    eyebrow: "01 · WORKSPACES",
    title: "Each room is its own world.",
    body: "A workspace owns its agents, its memory, its grants, and its home tone. Switch between them with ⌘K. Each one stays private to itself.",
    diagram: () => sceneWorkspaces(),
  },
  {
    eyebrow: "02 · CONVERSATION",
    title: "Talk to a room of agents at once.",
    body: "Send a message — Cortex routes it to whoever is best placed to answer. Mention an agent by name with @ to call them directly.",
    diagram: () => sceneConversation(),
  },
  {
    eyebrow: "03 · SAFETY MODEL",
    title: "Every sensitive tool call asks first.",
    body: "Aegis classifies every capability — routine, notable, sensitive, privileged. Sensitive calls pause until you allow once, always-in-workspace, or deny.",
    diagram: () => sceneSafety(),
  },
  {
    eyebrow: "04 · TRUST",
    title: "Trust is earned, asymmetrically.",
    body: "Outcomes nudge an agent's trust score. Above 0.75 it earns auto-grants on notable calls. Below 0.50, every grant collapses — instantly.",
    diagram: () => sceneTrust(),
  },
  {
    eyebrow: "05 · COCKPIT",
    title: "See what the kernel sees.",
    body: "The right rail keeps trust, permissions, mood, and the agent roster live in view. Press ⌘0 for the expanded six-panel cockpit.",
    diagram: () => sceneCockpit(),
  },
  {
    eyebrow: "06 · AGENTS",
    title: "Ten built-in. Seven thousand more in the catalog.",
    body: "Council deliberates, Specter red-teams, Oracle reads, Legacy remembers, Wraith forgets, Sentry watches. Install third-party agents like apps.",
    diagram: () => sceneAgents(),
  },
  {
    eyebrow: "READY",
    title: "Your turn.",
    body: "⌘K switch · ⌘N new workspace · ⌘0 cockpit · ⌘P settings · click the trash on any workspace to delete it. Have fun.",
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
    `<span class="nx-tour-dot ${i === index ? "active" : (i < index ? "done" : "")}" data-i="${i}"></span>`
  ).join("");
  const html = `
    <div class="nx-tour-overlay" id="nx-tour-overlay" role="dialog" aria-modal="true" aria-label="Tour">
      <button class="nx-tour-skip" id="nx-tour-skip" aria-label="Skip tour">Skip · esc</button>
      <div class="nx-tour-stage">
        <div class="nx-tour-diagram" id="nx-tour-diagram" aria-hidden="true">${scene.diagram()}</div>
        <div class="nx-tour-eyebrow">${escapeHtml(scene.eyebrow)}</div>
        <h2 class="nx-tour-title">${escapeHtml(scene.title)}</h2>
        <p class="nx-tour-body">${escapeHtml(scene.body)}</p>
      </div>
      <div class="nx-tour-nav">
        <button class="nx-tour-prev" id="nx-tour-prev" ${index === 0 ? "disabled" : ""} aria-label="Previous scene">←</button>
        <div class="nx-tour-dots">${dots}</div>
        <button class="nx-tour-next" id="nx-tour-next" aria-label="${index === total - 1 ? "Begin" : "Next scene"}">
          ${index === total - 1 ? "Begin →" : "Next →"}
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

// Tour scenes — each returns SVG with boomerang (alternate-infinite) motion.
// Animations use animation-direction: alternate so motion springs forward
// then back, like an Instagram boomerang.

function sceneWelcome() {
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <defs>
        <radialGradient id="t-orb" cx="40%" cy="35%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="25%" stop-color="#f0e6ff"/>
          <stop offset="60%" stop-color="#c9b8ff"/>
          <stop offset="100%" stop-color="#5a4ac4" stop-opacity="0.3"/>
        </radialGradient>
      </defs>
      <g transform="translate(160 110)">
        <circle r="80" fill="url(#t-orb)" opacity="0.30" class="nx-tour-anim-corona"/>
        <circle r="56" fill="url(#t-orb)" class="nx-tour-anim-orb"/>
        <circle r="20" fill="#ffffff" opacity="0.7" class="nx-tour-anim-core"/>
      </g>
    </svg>
  `;
}

function sceneWorkspaces() {
  // 4 workspace tiles in a 2×2 grid around a central orb. The whole group
  // gently breathes via a CSS scale animation, so we need extra padding
  // inside the viewBox to keep nothing clipping at the larger end of the
  // breath cycle. Positions are absolute (no SVG-attribute transform), so
  // the CSS transform doesn't double-apply with an SVG translate.
  const cx = 200, cy = 145;   // viewBox centre
  const tones = [
    { x: cx - 70, y: cy - 36, c1: "#5a6cd0", c2: "#2c3a78" },
    { x: cx + 70, y: cy - 36, c1: "#88a888", c2: "#3e5840" },
    { x: cx - 70, y: cy + 36, c1: "#c060a0", c2: "#5e2050" },
    { x: cx + 70, y: cy + 36, c1: "#e8a06c", c2: "#844820" },
  ];
  return `
    <svg viewBox="0 0 400 290" width="100%" height="100%" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
      <defs>
        ${tones.map(t => `
          <linearGradient id="g-${t.c1.replace('#','')}" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="${t.c1}"/>
            <stop offset="100%" stop-color="${t.c2}"/>
          </linearGradient>
        `).join("")}
      </defs>
      <g class="nx-tour-anim-rooms" style="transform-origin:${cx}px ${cy}px">
        ${tones.map(t => `
          <g>
            <rect x="${t.x - 46}" y="${t.y - 26}" width="92" height="52" rx="9"
                  fill="url(#g-${t.c1.replace('#','')})" opacity="0.95"/>
            <circle cx="${t.x - 32}" cy="${t.y - 14}" r="3" fill="#ffffff" opacity="0.8"/>
          </g>
        `).join("")}
        <circle cx="${cx}" cy="${cy}" r="14" fill="url(#t-orb)"/>
      </g>
    </svg>
  `;
}

function sceneConversation() {
  // Two message bubbles trade back and forth
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <defs>
        <radialGradient id="ag-disc" cx="35%" cy="30%" r="70%">
          <stop offset="0%" stop-color="#a8e8ff"/>
          <stop offset="100%" stop-color="#346b9c"/>
        </radialGradient>
      </defs>
      <g transform="translate(40 70)">
        <circle cx="14" cy="14" r="14" fill="url(#ag-disc)" class="nx-tour-anim-disc"/>
        <rect x="36" y="4" width="170" height="22" rx="11" fill="rgba(232,222,252,0.08)" class="nx-tour-anim-bubble-a"/>
        <rect x="36" y="32" width="120" height="14" rx="7" fill="rgba(232,222,252,0.05)" class="nx-tour-anim-bubble-a"/>
      </g>
      <g transform="translate(80 130)" class="nx-tour-anim-bubble-b">
        <rect x="0" y="0" width="200" height="26" rx="13" fill="rgba(168,180,255,0.18)"/>
        <text x="14" y="17" font-family="ui-sans-serif,sans-serif" font-size="11" fill="#e2e6ff">summarize the kernel runtime</text>
      </g>
    </svg>
  `;
}

function sceneSafety() {
  // Permission prompt — two-row layout so the class label, target path,
  // and the three decision pills each get their own line and don't
  // overlap. The card pulses gently; the pills slide in from the left.
  return `
    <svg viewBox="0 0 400 290" width="100%" height="100%" aria-hidden="true" preserveAspectRatio="xMidYMid meet">
      <g transform="translate(200 145)">
        <!-- Card (300 × 116, two rows tall) -->
        <rect x="-150" y="-58" width="300" height="116" rx="14"
              fill="rgba(248,196,96,0.08)"
              stroke="rgba(248,196,96,0.40)" stroke-width="1.2"
              class="nx-tour-anim-card"/>

        <!-- Row 1: pulse + class label + path -->
        <circle cx="-126" cy="-28" r="6" fill="#f8c460" class="nx-tour-anim-pulse-dot"/>
        <circle cx="-126" cy="-28" r="11" fill="none" stroke="rgba(248,196,96,0.55)" stroke-width="1.2"
                class="nx-tour-anim-ping"/>
        <text x="-110" y="-32" font-family="ui-monospace,monospace" font-size="11"
              letter-spacing="2.4" fill="#f8c460" font-weight="700">FS.WRITE</text>
        <text x="-110" y="-18" font-family="ui-monospace,monospace" font-size="9"
              letter-spacing="2" fill="rgba(248,196,96,0.78)">SENSITIVE</text>

        <text x="-110" y="6" font-family="ui-sans-serif,sans-serif" font-size="11"
              fill="#e8defc">oracle → src/kernel/cortex.py</text>

        <!-- Row 2: three decision pills, evenly spaced, with slide-in motion -->
        <g class="nx-tour-anim-pills" transform="translate(0 34)">
          <rect x="-126" y="-12" width="68" height="24" rx="12"
                fill="rgba(154,255,182,0.16)" stroke="rgba(154,255,182,0.50)"/>
          <text x="-92" y="4" font-family="ui-sans-serif,sans-serif" font-size="11"
                font-weight="600" fill="#a8f4c0" text-anchor="middle">allow</text>

          <rect x="-50" y="-12" width="88" height="24" rx="12"
                fill="rgba(168,124,232,0.20)" stroke="rgba(168,124,232,0.55)"/>
          <text x="-6" y="4" font-family="ui-sans-serif,sans-serif" font-size="11"
                font-weight="600" fill="#e0d0ff" text-anchor="middle">always</text>

          <rect x="46" y="-12" width="62" height="24" rx="12"
                fill="rgba(248,96,120,0.12)" stroke="rgba(248,96,120,0.40)"/>
          <text x="77" y="4" font-family="ui-sans-serif,sans-serif" font-size="11"
                font-weight="600" fill="#f8a0b0" text-anchor="middle">deny</text>
        </g>
      </g>
    </svg>
  `;
}

function sceneTrust() {
  // Sparkline that draws itself going up, mirrors to baseline (boomerang)
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <defs>
        <linearGradient id="t-fill" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="#ffd680" stop-opacity="0.55"/>
          <stop offset="100%" stop-color="#ffd680" stop-opacity="0"/>
        </linearGradient>
        <linearGradient id="t-line" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#ffb878"/>
          <stop offset="100%" stop-color="#ffe09a"/>
        </linearGradient>
      </defs>
      <g transform="translate(30 30)">
        <path d="M0 160 L0 130 L30 125 L60 122 L90 110 L120 100 L150 95 L180 80 L210 70 L240 56 L260 50 L260 160 Z"
              fill="url(#t-fill)" class="nx-tour-anim-area"/>
        <path d="M0 130 L30 125 L60 122 L90 110 L120 100 L150 95 L180 80 L210 70 L240 56 L260 50"
              fill="none" stroke="url(#t-line)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
              class="nx-tour-anim-line"/>
        <circle cx="260" cy="50" r="4" fill="#ffe09a" class="nx-tour-anim-dot"/>
        <text x="0" y="20" font-family="ui-monospace,monospace" font-size="18" font-weight="700" fill="#ffe09a">+0.14</text>
        <text x="60" y="20" font-family="ui-monospace,monospace" font-size="10" letter-spacing="2" fill="#f8c460">RISING</text>
      </g>
    </svg>
  `;
}

function sceneCockpit() {
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(40 40)">
        <rect x="0"   y="0"   width="60" height="40" rx="6" fill="rgba(255,214,128,0.10)" stroke="rgba(255,214,128,0.30)" class="nx-tour-anim-panel" style="animation-delay:0s"/>
        <rect x="72"  y="0"   width="76" height="40" rx="6" fill="rgba(168,180,255,0.08)" stroke="rgba(168,180,255,0.28)" class="nx-tour-anim-panel" style="animation-delay:0.2s"/>
        <rect x="160" y="0"   width="80" height="40" rx="6" fill="rgba(168,124,232,0.08)" stroke="rgba(168,124,232,0.28)" class="nx-tour-anim-panel" style="animation-delay:0.4s"/>
        <rect x="0"   y="52"  width="100" height="48" rx="6" fill="rgba(154,255,182,0.07)" stroke="rgba(154,255,182,0.26)" class="nx-tour-anim-panel" style="animation-delay:0.6s"/>
        <rect x="112" y="52"  width="128" height="48" rx="6" fill="rgba(140,184,212,0.07)" stroke="rgba(140,184,212,0.24)" class="nx-tour-anim-panel" style="animation-delay:0.8s"/>
        <rect x="0"   y="112" width="240" height="32" rx="6" fill="rgba(248,196,96,0.06)" stroke="rgba(248,196,96,0.24)" class="nx-tour-anim-panel" style="animation-delay:1.0s"/>
      </g>
    </svg>
  `;
}

function sceneAgents() {
  const SLUGS = ["council", "oracle", "specter", "wraith", "echo", "autonomic", "legacy", "consciousness"];
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(160 110)" class="nx-tour-anim-discs">
        ${SLUGS.map((s, i) => {
          const angle = (i / SLUGS.length) * Math.PI * 2 - Math.PI / 2;
          const r = 70;
          const x = Math.cos(angle) * r;
          const y = Math.sin(angle) * r;
          const grads = {
            council:["#ffd2a0","#c47a32"], oracle:["#a8e8ff","#346b9c"],
            specter:["#ff9eb8","#8c2e54"], wraith:["#9affc8","#2a6a4e"],
            echo:["#a8e8ff","#346b9c"], autonomic:["#c8a0ff","#5e3a9c"],
            legacy:["#ffd680","#9c6a1a"], consciousness:["#e0c8ff","#5a3a8c"],
          };
          const g = grads[s] || ["#c8c8ff","#3a3a8c"];
          const gid = `td-${s}`;
          return `
            <defs>
              <radialGradient id="${gid}" cx="35%" cy="30%" r="70%">
                <stop offset="0%" stop-color="${g[0]}"/>
                <stop offset="100%" stop-color="${g[1]}"/>
              </radialGradient>
            </defs>
            <circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="16" fill="url(#${gid})" class="nx-tour-anim-disc-pop" style="animation-delay:${(i * 0.1).toFixed(2)}s"/>
          `;
        }).join("")}
        <circle r="22" fill="url(#t-orb)"/>
      </g>
    </svg>
  `;
}

function sceneReady() {
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <defs>
        <radialGradient id="r-orb" cx="40%" cy="35%">
          <stop offset="0%" stop-color="#ffffff"/>
          <stop offset="25%" stop-color="#f0e6ff"/>
          <stop offset="60%" stop-color="#c9b8ff"/>
          <stop offset="100%" stop-color="#5a4ac4" stop-opacity="0.3"/>
        </radialGradient>
      </defs>
      <g transform="translate(160 110)">
        <circle r="48" fill="url(#r-orb)" class="nx-tour-anim-core"/>
        <circle r="60" fill="none" stroke="rgba(201,184,255,0.30)" stroke-width="1" class="nx-tour-anim-ring1"/>
        <circle r="80" fill="none" stroke="rgba(201,184,255,0.20)" stroke-width="1" class="nx-tour-anim-ring2"/>
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
}

async function loadAgents() {
  try {
    // Pull built-in / system agents first (these are the resident set).
    const r = await fetch("/api/agents?category=system&limit=20");
    if (r.ok) {
      const body = await r.json();
      state.agents = body.agents || [];
    }
  } catch {}
  // Recent = running agents first, then top of system catalog
  try {
    const r = await fetch("/api/agents/running");
    if (r.ok) {
      const running = await r.json();
      const runningSet = new Set(running.map(a => a.slug));
      state.recentAgents = [
        ...running.map(a => ({ ...a, is_running: true })),
        ...state.agents.filter(a => !runningSet.has(a.slug)),
      ].slice(0, 3);
      return;
    }
  } catch {}
  state.recentAgents = state.agents.slice(0, 3);
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
    const anyCollapse = recent.some(e => e.new_score < 0.50);
    state.trust.direction = anyCollapse
      ? "collapse"
      : state.trust.delta < -0.01 ? "falling" : "rising";
  } catch {}
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
  // Breakdown count
  state.trust.breakdown = state.perms.recent.reduce((acc, e) => {
    const k = (e.permission_class || "routine").toLowerCase();
    acc[k] = (acc[k] || 0) + 1;
    if (e.status === "denied") acc.denied = (acc.denied || 0) + 1;
    return acc;
  }, { routine: 0, notable: 0, sensitive: 0, privileged: 0, denied: 0 });
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
  document.getElementById("nx-open-settings").addEventListener("click", () => location.hash = "#/settings");
  document.getElementById("nx-open-workshop").addEventListener("click", () => location.hash = "#/workshop");
  document.getElementById("nx-open-search").addEventListener("click", () => location.hash = "#/search");
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
    list.innerHTML = `<div class="nx-empty" style="opacity:0.5;padding:14px 4px;font-size:11.5px">no workspaces yet · ⌘N to create one</div>`;
  } else {
    list.innerHTML = state.workspaces.map(w => {
      const tone = w.tone || "indigo";
      const colorMap = {
        indigo: "#a8b4ff",  amber: "#f8c460",  sage: "#9affb6",
        plum: "#c8a0ff",    magenta: "#f86078", "calm-focus": "#a87af5",
      };
      const dotColor = colorMap[(tone || "").toLowerCase()] || "#a87af5";
      const meta = w.workspace_id === state.active
        ? `${w.resident_agents?.length || 0} agents · active`
        : `${w.resident_agents?.length || 0} agents`;
      return `
        <div class="nx-ws-row ${w.workspace_id === state.active ? "active" : ""}" data-id="${w.workspace_id}">
          <button class="nx-ws-pill" data-id="${w.workspace_id}" aria-label="Open workspace ${escapeHtml(w.name)}">
            <span class="ws-dot" style="background:${dotColor};color:${dotColor}"></span>
            <span class="ws-name">${escapeHtml(w.name || w.workspace_id)}</span>
            <span></span>
            <span class="ws-meta">${escapeHtml(meta)}</span>
          </button>
          <button class="nx-ws-trash" data-id="${w.workspace_id}" data-name="${escapeHtml(w.name)}"
                  aria-label="Delete workspace ${escapeHtml(w.name)}" title="Delete workspace">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M2.5 3.5h9"/>
              <path d="M5 3.5V2.2c0-.4.3-.7.7-.7h2.6c.4 0 .7.3.7.7v1.3"/>
              <path d="M3.5 3.5l.6 8.4c0 .3.3.6.6.6h4.6c.3 0 .6-.3.6-.6l.6-8.4"/>
              <path d="M6 6v4M8 6v4"/>
            </svg>
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
        if (!confirm(`Delete workspace "${name}"? This is permanent — its memory and grants will be removed.`)) return;
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

  // Recent agents
  const recentEl = document.getElementById("nx-recent-agents");
  if (!state.recentAgents.length) {
    recentEl.innerHTML = `<div class="nx-empty" style="opacity:0.45;padding:8px 4px;font-size:11px">no installed agents yet</div>`;
  } else {
    recentEl.innerHTML = state.recentAgents.map(a => {
      const floor = typeof a.trust_floor === "number" ? a.trust_floor : null;
      const trustLabel = a.is_running ? "running"
        : floor == null ? "—"
        : floor >= 0.75 ? "trusted"
        : floor >= 0.50 ? "executor"
        : "probationary";
      return `
        <div class="nx-agent-row" data-slug="${a.slug}">
          ${agentDisc(a.slug, { size: 28, trust: floor })}
          <div>
            <div class="ag-name">${escapeHtml(a.slug)}</div>
            <div class="ag-sub">${escapeHtml(a.category || "")}</div>
          </div>
          <div class="ag-status">${escapeHtml(trustLabel)}</div>
        </div>
      `;
    }).join("");
    recentEl.querySelectorAll(".nx-agent-row").forEach(row => {
      row.addEventListener("click", () => location.hash = `#/catalog?focus=${encodeURIComponent(row.dataset.slug)}`);
    });
  }

  // User footer initials
  const initialsEl = document.getElementById("nx-user-initials");
  initialsEl.textContent = state.user.initials;
}

function renderChromeContext() {
  const el = document.getElementById("nx-chrome-context");
  if (!el) return;
  if (!state.active) { el.textContent = "no workspace"; return; }
  const w = state.workspaces.find(ws => ws.workspace_id === state.active);
  const name = w ? w.name : state.active;
  const count = w?.resident_agents?.length || 0;
  el.textContent = `— ${name.toLowerCase()} · ${count} agent${count === 1 ? "" : "s"} on duty`;
}

// ── Cockpit rail ──────────────────────────────────────────────────────────
function renderCockpitRail() {
  renderTrustCard();
  renderPermLog();
  renderMoodCard();
  renderAgentDiscs();
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
    <svg class="nx-trust-spark" viewBox="0 0 320 92" preserveAspectRatio="none" aria-hidden="true">
      ${trustSparkSVG(state.trust.history, dir)}
    </svg>
    <div class="nx-trust-head">
      <span class="nx-trust-delta">${dStr}</span>
      <span class="nx-trust-state">${dir.toUpperCase()}</span>
    </div>
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
    return `<line x1="0" y1="${h * 0.7}" x2="${w}" y2="${h * 0.7}" stroke="rgba(255,224,154,0.3)" stroke-width="1"/>`;
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
  const colorLine = direction === "collapse" ? "#ff8868"
                  : direction === "falling"  ? "#b0d4ec"
                                              : "#ffe09a";
  const colorArea = direction === "collapse" ? "rgba(248,100,60,0.30)"
                  : direction === "falling"  ? "rgba(140,184,212,0.22)"
                                              : "rgba(255,214,128,0.32)";
  const last = points[points.length - 1];
  return `
    <defs>
      <linearGradient id="ts-area" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="${colorArea}"/>
        <stop offset="100%" stop-color="${colorArea}" stop-opacity="0"/>
      </linearGradient>
    </defs>
    <path d="M ${pts} L ${w},${h} L 0,${h} Z" fill="url(#ts-area)"/>
    <path d="M ${pts}" fill="none" stroke="${colorLine}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="${last.x.toFixed(1)}" cy="${y(last.acc).toFixed(1)}" r="3.5" fill="${colorLine}"/>
    <circle cx="${last.x.toFixed(1)}" cy="${y(last.acc).toFixed(1)}" r="8" fill="none" stroke="${colorLine}" stroke-opacity="0.4"/>
  `;
}

function renderPermLog() {
  const el = document.getElementById("nx-perm-log");
  if (!el) return;
  const rows = state.perms.recent.slice(0, 6);
  if (!rows.length) {
    el.innerHTML = `<div class="nx-empty" style="opacity:0.5;padding:14px 4px;font-size:11px">no recent activity</div>`;
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
          <span class="nx-perm-status s-${status}">${status.toUpperCase()}</span>
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
  el.innerHTML = `
    <div class="nx-mood-mesh"></div>
    <div class="nx-mood-caption">
      <div class="nx-mood-caption-name">${escapeHtml(name)}</div>
      <div class="nx-mood-caption-sub">${escapeHtml(reason.toLowerCase())}</div>
    </div>
  `;
  // reasons block
  const r = document.getElementById("nx-mood-reasons");
  r.innerHTML = `
    <div>↳ mood: ${escapeHtml(name)}</div>
    <div>↳ ${escapeHtml(reason || "ambient")}</div>
    <div>↳ ${state.workspaces.length} workspace${state.workspaces.length === 1 ? "" : "s"} · ${state.perms.pending.length} pending</div>
  `;
}

function renderAgentDiscs() {
  const el = document.getElementById("nx-agent-discs");
  if (!el) return;
  const BUILTINS = ["oracle", "council", "wraith", "echo", "specter", "autonomic"];
  const totalBuiltin = state.agents.filter(a => a.is_builtin).length || 10;
  document.getElementById("nx-agents-label").textContent =
    `${totalBuiltin} BUILT-IN · ${state.agents.length || 0} INSTALLED`;
  const overflow = Math.max(0, totalBuiltin - BUILTINS.length);
  el.innerHTML = BUILTINS.map(slug => `<button class="nx-disc-btn" data-slug="${slug}" title="${escapeHtml(BUILTIN_CAPABILITIES[slug]?.tagline || slug)}">${agentDisc(slug, { size: 28 })}</button>`).join("") +
    (overflow > 0 ? `<button class="nx-agent-overflow" title="Browse catalog">+${overflow}</button>` : "");
  const overEl = el.querySelector(".nx-agent-overflow");
  if (overEl) overEl.addEventListener("click", () => location.hash = "#/catalog");
  // Click any built-in disc → show its capability sheet
  el.querySelectorAll(".nx-disc-btn[data-slug]").forEach(btn => {
    btn.addEventListener("click", () => openCapabilitySheet(btn.dataset.slug));
  });
}

function openCapabilitySheet(slug) {
  const caps = BUILTIN_CAPABILITIES[slug];
  if (!caps) return;
  const root = document.getElementById("nx-overlay-root");
  const gradient = GRADIENTS[slug] || ["#a87af5", "#5a4ac4"];
  root.innerHTML = `
    <div class="nx-cap-overlay" id="nx-cap-overlay" role="dialog" aria-modal="true">
      <div class="nx-cap-sheet" style="--cap-grad-a:${gradient[0]};--cap-grad-b:${gradient[1]}">
        <button class="nx-cap-close" id="nx-cap-close" aria-label="Close">×</button>
        <div class="nx-cap-head">
          ${agentDisc(slug, { size: 64 })}
          <div>
            <div class="nx-cap-eyebrow">BUILT-IN AGENT</div>
            <div class="nx-cap-name">${escapeHtml(slug)}</div>
            <div class="nx-cap-tag">${escapeHtml(caps.tagline)}</div>
          </div>
        </div>
        <p class="nx-cap-desc">${escapeHtml(caps.description)}</p>

        <div class="nx-cap-grid">
          <div class="nx-cap-section">
            <div class="nx-cap-label">INTENTS</div>
            <div class="nx-cap-chips">${caps.intents.map(i => `<span class="cap-chip">${escapeHtml(i)}</span>`).join("")}</div>
          </div>

          <div class="nx-cap-section">
            <div class="nx-cap-label">PERMISSION CLASSES</div>
            <div class="nx-cap-chips">${caps.permission_classes.map(c => `
              <span class="cap-chip class-${c.toLowerCase()}">${escapeHtml(c)}</span>
            `).join("")}</div>
          </div>

          <div class="nx-cap-section nx-cap-section-tools">
            <div class="nx-cap-label">TOOLS DECLARED</div>
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
            <div class="nx-cap-label">TRUST FLOOR</div>
            <div class="nx-cap-tf">${caps.trust_floor.toFixed(2)} <span style="color:#6b6080;font-size:11px;letter-spacing:0.10em">/ 1.00</span></div>
          </div>

          <div class="nx-cap-section">
            <div class="nx-cap-label">NETWORK</div>
            <div class="nx-cap-net ${caps.network ? 'on' : 'off'}">${caps.network ? "REACHES NETWORK" : "LOCAL-ONLY"}</div>
          </div>
        </div>

        <div class="nx-cap-actions">
          <button class="nx-cap-mention" data-slug="${slug}">@${slug} — start a message</button>
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
    if (!location.hash.startsWith("#/conversation/")) {
      location.hash = `#/conversation/${state.active}`;
    }
    setTimeout(() => {
      const ci = document.getElementById("nx-composer-input");
      if (ci) { ci.value = `@${slug} `; ci.focus(); }
    }, 200);
  });
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
    main.innerHTML = `<div class="nx-empty">workspace not found: ${escapeHtml(workspaceId)}</div>`;
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
    ? `started by you · ${onDuty} on duty${(ws.resident_agents || []).length > 1 ? ` · ${(ws.resident_agents || [])[1]} listening` : ""}`
    : `started by you · council routing`;

  const attachedFiles = state.attachments?.get(workspaceId) || [];
  // Use a <label for="..."> wrapping the paperclip — clicking a label for a
  // file input is a native browser primitive and opens the picker without any
  // JS click chain. Works in every browser, including Safari which is picky
  // about programmatic .click() on hidden inputs.
  const composerHTML = `
    <form class="nx-composer" id="nx-composer" autocomplete="off">
      <label class="nx-attach-btn" id="nx-attach-btn" for="nx-file-input" title="Attach file (or drag-and-drop)">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9.8 5.5 5.8 9.5a2 2 0 1 1-2.8-2.8L8 1.7a3 3 0 0 1 4.2 4.2L7.2 11a4 4 0 0 1-5.7-5.6"/>
        </svg>
      </label>
      <input type="file" id="nx-file-input" multiple aria-hidden="true" class="nx-file-input-vis">
      <input id="nx-composer-input"
             placeholder="${attachedFiles.length ? `message + ${attachedFiles.length} file${attachedFiles.length===1?'':'s'}…` : 'message agents in this workspace…'}"
             aria-label="Compose a message"
             autofocus>
      <div class="nx-composer-kbd">
        <span class="kbd">⌘</span><span class="kbd">⏎</span><span class="hint">send</span>
      </div>
    </form>
    ${attachedFiles.length ? `
      <div class="nx-attached-strip">
        ${attachedFiles.map(f => `
          <span class="nx-attached-chip" data-id="${escapeHtml(f.id)}" title="${escapeHtml(f.name)} · ${(f.size/1024).toFixed(1)} KB">
            <svg width="11" height="11" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" aria-hidden="true">
              <path d="M2 0h6l4 4v10H2z"/>
              <path d="M8 0v4h4"/>
            </svg>
            <span class="chip-name">${escapeHtml(truncate(f.name, 24))}</span>
            <button type="button" class="chip-x" data-id="${escapeHtml(f.id)}" aria-label="Remove">×</button>
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
              <button class="crumb-link" id="nx-crumb-home" data-id="${escapeHtml(ws.workspace_id)}">
                <span class="crumb-dim">workspace /</span>
                <span class="crumb-strong">${escapeHtml((ws.name || ws.workspace_id).toLowerCase())}</span>
              </button>
              <span class="crumb-dim">— today, ${stamp}</span>
            </div>
            <div class="nx-conv-head-actions">
              <button class="nx-conv-action" id="nx-new-thread" title="Start a new thread in this workspace">
                <span class="nx-plus" aria-hidden="true"></span>
                <span>new thread</span>
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

  // Wire prompt suggestion cards (empty state)
  main.querySelectorAll(".nx-prompt-card[data-prompt]").forEach(card => {
    card.addEventListener("click", async () => {
      const input = document.getElementById("nx-composer-input");
      if (input) input.value = card.dataset.prompt;
      await sendMessage(workspaceId);
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
        body: "Refactor the kernel runtime — three candidates, smallest blast radius first.",
        ts: minus(140),
      });
      t.push({
        role: "agent", agent: "oracle", ts: minus(120),
        body: "I traced the dependency graph across 47 files in src/kernel/. Three refactor candidates match your scope — diffs below, ordered by smallest blast radius:",
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
            preview: "Apply candidate #2 — replaces the inline router fallback with explicit dispatch.",
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
  const SUGGESTIONS = [
    { glyph: "council",       label: "Convene the council",  hint: "Get a 3-round deliberation across the cognitive modules.", prompt: "Council: I'm refactoring my kernel runtime — what should I be careful about?" },
    { glyph: "oracle",        label: "Ask the oracle",        hint: "A first read across whatever is in this workspace.",      prompt: "Oracle: read this repo and summarise its architecture in 5 bullets." },
    { glyph: "specter",       label: "Red-team a plan",       hint: "Counter-arguments and dissenting views, no flattery.",     prompt: "Specter: red-team my decision to switch from postgres to sqlite." },
    { glyph: "legacy",        label: "Pull from memory",      hint: "Recall what was decided last time, with citations.",       prompt: "Legacy: what have I tried for this problem before?" },
  ];
  return `
    <div class="nx-welcome">
      <div class="nx-welcome-orb">${KERNEL_MARK(72)}</div>
      <h1>${escapeHtml(ws.name)}</h1>
      <p>A workspace is a room with its own agents, memory, and grants. Send a
         message to start — or pick a thread below. Every tool call passes
         through <span class="nx-mono" style="color:#c9b8ff">Aegis</span>, every event lands in
         <span class="nx-mono" style="color:#c9b8ff">Chronicle</span>.</p>
      <div class="nx-prompt-grid" id="nx-prompt-grid">
        ${SUGGESTIONS.map(s => `
          <button class="nx-prompt-card" data-prompt="${escapeHtml(s.prompt)}">
            <div class="nx-prompt-glyph">${agentDisc(s.glyph, { size: 32 })}</div>
            <div class="nx-prompt-text">
              <div class="nx-prompt-label">${escapeHtml(s.label)}</div>
              <div class="nx-prompt-hint">${escapeHtml(s.hint)}</div>
            </div>
            <div class="nx-prompt-arrow">↩</div>
          </button>
        `).join("")}
      </div>
      <div class="nx-welcome-links">
        <button class="nx-tour-link" id="nx-tour-link" data-workspace="${escapeHtml(ws.workspace_id)}">
          See the safety model in action — fire a sample permission prompt
        </button>
        <button class="nx-tour-link" id="nx-welcome-guide" style="border-color:rgba(168,124,232,0.32);color:#c9b8ff">
          Open the guide · ${GUIDE_PAGES.length} pages · ?
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
            <svg width="10" height="10" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" aria-hidden="true">
              <path d="M2 0h6l4 4v10H2z"/>
              <path d="M8 0v4h4"/>
            </svg>
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
      <div class="nx-msg-agent">
        ${agentDisc(slug, { size: 40 })}
        <div class="nx-msg-col">
          <div class="nx-msg-head">
            <span class="nx-msg-name">routing…</span>
            <span class="nx-msg-meta">cortex is picking a module</span>
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
          <span class="nx-diff-icon" aria-hidden="true"></span>
          <span class="nx-diff-path">${escapeHtml(d.path)}</span>
          <span class="nx-diff-adds">+${d.adds || 0}</span>
          <span class="nx-diff-dels">−${d.dels || 0}</span>
          <span class="nx-diff-trail" aria-hidden="true"></span>
        </div>
      `).join("")}
    </div>
  ` : "";
  const fb = m.feedback;  // null | 'up' | 'down'
  return `
    <div class="nx-msg-agent" data-message-id="${escapeHtml(m.id || "")}" data-module="${escapeHtml(slug)}">
      ${agentDisc(slug, { size: 40 })}
      <div class="nx-msg-col">
        <div class="nx-msg-head">
          <span class="nx-msg-name">${escapeHtml(slug)}</span>
          <span class="nx-msg-meta">${escapeHtml(time)}</span>
          ${m.memory_id ? `<span class="nx-msg-memory" title="Stored in Engram: ${escapeHtml(m.memory_id)}">remembered</span>` : ""}
        </div>
        <div class="nx-msg-body" style="white-space:pre-wrap">${m.html || escapeHtml(m.body)}</div>
        ${diffHTML}
        <div class="nx-msg-footer">
          <button class="nx-fb-btn ${fb === 'up' ? 'on' : ''}" data-fb="up" title="Mark this response as useful (raises ${escapeHtml(slug)}'s trust)">
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M3 6V10H1.5V6z"/>
              <path d="M3 6h5.5l1.5-2.5c.3-.6 0-1.5-.8-1.5H7l.4-1.3c.1-.5-.3-1-.8-1H6L4 4 3 5"/>
            </svg>
          </button>
          <button class="nx-fb-btn ${fb === 'down' ? 'on down' : ''}" data-fb="down" title="Mark this response as unhelpful (lowers ${escapeHtml(slug)}'s trust)">
            <svg width="11" height="11" viewBox="0 0 11 11" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="transform:rotate(180deg)">
              <path d="M3 6V10H1.5V6z"/>
              <path d="M3 6h5.5l1.5-2.5c.3-.6 0-1.5-.8-1.5H7l.4-1.3c.1-.5-.3-1-.8-1H6L4 4 3 5"/>
            </svg>
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
      ${agentDisc(slug, { size: 40 })}
      <div>
        <div class="nx-msg-head">
          <span class="nx-msg-name">${escapeHtml(slug)}</span>
          <span class="nx-msg-meta">requesting access</span>
        </div>
        <div class="nx-msg-body">
          Needs <span class="nx-cap">${escapeHtml(p.capability)}</span>${p.target ? ` on <span class="nx-code">${escapeHtml(p.target)}</span>` : ""}.
          ${p.preview ? ` ${escapeHtml(p.preview)}` : ""} How should Aegis remember this?
        </div>
        <div class="nx-perm-prompt class-${pc}" data-ticket="${escapeHtml(p.id)}">
          <span class="nx-perm-pulse" aria-hidden="true"></span>
          <div class="nx-perm-info">
            <div class="nx-perm-eyebrow">${escapeHtml((p.capability || "").toUpperCase())} · ${pc.toUpperCase()}</div>
            <div class="nx-perm-body">${escapeHtml(slug)} → <span class="nx-code">${escapeHtml(p.target || "—")}</span></div>
          </div>
          <div class="nx-perm-actions">
            <button class="nx-perm-btn allow"  data-decision="allow_once">allow once</button>
            <button class="nx-perm-btn always" data-decision="allow_always_in_workspace">always · here</button>
            <button class="nx-perm-btn deny"   data-decision="deny">deny</button>
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

async function sendMessage(workspaceId) {
  const input = document.getElementById("nx-composer-input");
  const body = input.value.trim();
  const files = state.attachments.get(workspaceId) || [];
  if (!body && files.length === 0) return;
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

// ── Main view: workspaces grid (no active workspace) ──────────────────────
function renderWorkspacesGrid() {
  const main = document.getElementById("nx-main");
  if (!state.workspaces.length) {
    main.innerHTML = `
      <div class="nx-main-inner">
        <div class="nx-welcome">
          <div class="nx-welcome-orb">${KERNEL_MARK(96)}</div>
          <h1>Welcome to ONEXUS</h1>
          <p>An operating system for agents. Each room — a workspace — has its own
             agents, memory, and grants. Create your first one to get started.</p>
          <button class="nx-welcome-cta" id="nx-welcome-create">Create your first workspace · ⌘N</button>
        </div>
      </div>
    `;
    document.getElementById("nx-welcome-create").addEventListener("click", openNewWorkspaceForm);
    return;
  }
  const tiles = state.workspaces.map(w => `
    <div class="nx-ws-tile nx-tone-${w.tone || "indigo"} ${w.workspace_id === state.active ? "active" : ""}"
         data-id="${w.workspace_id}">
      <div class="tile-eyebrow">${escapeHtml((w.tone || "indigo").toUpperCase())}</div>
      <div class="tile-name">${escapeHtml(w.name)}</div>
      <div class="tile-footer">
        <div class="disc-stack">
          ${(w.resident_agents || []).slice(0, 3).map(a => agentDisc(a, { size: 22 })).join("")}
        </div>
        <span class="nx-mono" style="opacity:0.8">
          ${w.workspace_id === state.active ? "active" : (w.last_active_at ? "seen" : "—")}
        </span>
      </div>
    </div>
  `).join("");
  main.innerHTML = `
    <div class="nx-main-inner">
      <header style="display:flex;align-items:end;justify-content:space-between;margin-bottom:24px">
        <div>
          <div class="nx-eyebrow" style="margin-bottom:6px">Rooms</div>
          <div class="nx-display" style="font-size:28px;color:#f3ecff;font-weight:700">Workspaces</div>
          <div class="nx-dim" style="font-size:13px;margin-top:4px">
            ${state.workspaces.length} workspace${state.workspaces.length === 1 ? "" : "s"} · ⌘K to switch · ⌘N for new
          </div>
        </div>
      </header>
      <div class="nx-ws-grid">
        ${tiles}
        <div class="nx-ws-tile new" id="nx-inline-new-workspace">
          ${UI.plus(22)}
          <div style="font-size:13px;margin-top:6px">New workspace</div>
        </div>
      </div>
    </div>
  `;
  main.querySelectorAll(".nx-ws-tile[data-id]").forEach(el => {
    el.addEventListener("click", async () => {
      await fetch(`/api/workspaces/${el.dataset.id}/switch`, { method: "POST" });
      await loadWorkspaces();
      renderSidebar();
      location.hash = `#/conversation/${el.dataset.id}`;
    });
  });
  document.getElementById("nx-inline-new-workspace").addEventListener("click", openNewWorkspaceForm);
}

// ── Main view: catalog (spatial grid) ─────────────────────────────────────
async function renderCatalog() {
  const main = document.getElementById("nx-main");
  main.innerHTML = `<div class="nx-main-inner"><div class="nx-empty">loading catalog…</div></div>`;
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
    const r = await fetch(endpoint);
    if (!r.ok) throw new Error("catalog fetch failed");
    const body = await r.json();
    const agents = body.agents || [];
    const cats = body.categories || [];
    main.innerHTML = `
      <div class="nx-main-inner">
        <div class="nx-spatial-header">
          <div>
            <div class="nx-eyebrow" style="margin-bottom:6px">Catalog</div>
            <div class="nx-display" style="font-size:26px;color:#f3ecff;font-weight:700">Browse agents</div>
            <div class="nx-dim" style="font-size:13px;margin-top:4px">${agents.length} of ${body.total} · ${runnableOnly ? "runnable (MCP adapter)" : "all"} · vendored from ONEXUS-Agents</div>
          </div>
          <form class="nx-cat-filters" id="nx-cat-filters">
            <input type="search" id="nx-cat-q" value="${escapeHtml(search)}" placeholder="search the catalog…">
            <select id="nx-cat-cat">
              <option value="">all categories</option>
              ${cats.map(c => `<option value="${escapeHtml(c)}" ${c===category?"selected":""}>${escapeHtml(c)}</option>`).join("")}
            </select>
            <label class="nx-cat-toggle">
              <input type="checkbox" id="nx-cat-runnable" ${runnableOnly?"checked":""}>
              runnable only
            </label>
          </form>
        </div>
        <div class="nx-spatial">
          ${agents.map(renderCatalogCard).join("")}
        </div>
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
    // Wire card actions
    main.querySelectorAll(".nx-spatial-card[data-slug]").forEach(card => {
      const slug = card.dataset.slug;
      card.querySelector(".launch-btn")?.addEventListener("click", async (e) => {
        e.stopPropagation();
        const btn = e.currentTarget;
        btn.disabled = true;
        btn.textContent = "launching…";
        try {
          const r = await fetch(`/api/agents/${encodeURIComponent(slug)}/launch`, { method: "POST" });
          const body = await r.json().catch(() => ({}));
          btn.textContent = r.ok ? "running" : (body.detail || body.message || "failed");
          if (r.ok) btn.classList.add("on");
        } catch (e) {
          btn.textContent = "error";
        } finally {
          setTimeout(() => { btn.disabled = false; }, 1200);
        }
      });
    });
  } catch (e) {
    main.innerHTML = `<div class="nx-main-inner"><div class="nx-empty">could not load catalog: ${escapeHtml(e.message)}</div></div>`;
  }
}

function renderCatalogCard(a) {
  const runnable = a.runnable || a.is_builtin;
  return `
    <div class="nx-spatial-card" data-slug="${escapeHtml(a.slug)}">
      ${agentDisc(a.slug, { size: 36, trust: a.trust_floor ?? null })}
      <div class="name">${escapeHtml(a.name || a.slug)}</div>
      <div class="tagline">${escapeHtml(a.tagline || a.description || "")}</div>
      <div class="status">
        <span class="status-dot ${runnable ? "" : "sleeping"}"></span>
        ${runnable ? "runnable" : "manifest-only"}
        <span class="badge-system">${escapeHtml(a.category || "")}</span>
      </div>
      <div class="nx-card-actions">
        ${runnable ? `<button class="launch-btn" type="button">Launch</button>` : ""}
        ${a.source_github ? `<a class="src-link" href="https://github.com/${escapeHtml(a.source_github)}" target="_blank" rel="noopener noreferrer">source ↗</a>` : ""}
      </div>
    </div>
  `;
}

// ── Main view: settings ───────────────────────────────────────────────────
async function renderSettings() {
  const main = document.getElementById("nx-main");
  main.innerHTML = `
    <div class="nx-main-inner">
      <header style="margin-bottom:18px">
        <div class="nx-eyebrow" style="margin-bottom:6px">Configure</div>
        <div class="nx-display" style="font-size:26px;color:#f3ecff;font-weight:700">Settings</div>
        <div class="nx-dim" style="font-size:13px;margin-top:4px">Local-first · changes apply immediately · sovereign data dir</div>
      </header>
      <div class="nx-settings-shell">
        <nav class="nx-settings-tabs">
          <button class="active" data-tab="general">General</button>
          <button data-tab="security">Security</button>
          <button data-tab="providers">Providers</button>
          <button data-tab="federation">Federation</button>
          <button data-tab="moods">Moods</button>
          <button data-tab="about">About</button>
        </nav>
        <section class="nx-card nx-settings-panel" id="nx-settings-panel"></section>
      </div>
    </div>
  `;
  const panel = document.getElementById("nx-settings-panel");
  const renderTab = async (tab) => {
    main.querySelectorAll(".nx-settings-tabs button").forEach(x => x.classList.toggle("active", x.dataset.tab === tab));
    panel.innerHTML = `<div class="nx-empty" style="opacity:0.5;font-size:12px;padding:18px">loading…</div>`;
    panel.innerHTML = await renderSettingsTab(tab);
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
            ? `showing first 80 of ${matched.length} matches · narrow further`
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

function renderTrustRows(rows) {
  if (!rows.length) return `<div class="nx-empty" style="opacity:0.55;padding:18px;font-size:12px">no matches</div>`;
  return rows.map(s => {
    const score = s.trust ?? 0;
    const tier = score >= 0.75 ? "EXECUTOR"
               : score >= 0.50 ? "MONITOR"
               : score >= 0.25 ? "ADVISOR" : "OBSERVER";
    return `
      <div class="nx-st-trust-row">
        <div class="nx-st-trust-name">${escapeHtml(s.module)}</div>
        <div class="nx-st-trust-bar"><span style="width:${(score * 100).toFixed(1)}%"></span></div>
        <div class="nx-st-trust-score">${score.toFixed(2)}</div>
        <div class="nx-st-trust-tier">${tier}</div>
        <button class="nx-st-revoke" data-module="${escapeHtml(s.module)}">revoke</button>
      </div>
    `;
  }).join("");
}

async function renderSettingsTab(tab) {
  switch (tab) {
    case "general": {
      const sys = await fetch("/api/system/config").then(r => r.ok ? r.json() : {}).catch(() => ({}));
      return `
        <h3>General</h3>
        <p class="nx-dim" style="font-size:13px;margin-bottom:18px">Where ONEXUS keeps its data, how it runs.</p>
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
        <h3>Security · Trust</h3>
        <p class="nx-dim" style="font-size:13px;margin-bottom:14px">
          <span id="nx-st-trust-count">${sorted.length}</span> module${sorted.length === 1 ? "" : "s"} registered with Aegis. Click revoke to reset a module's trust to 0 — all its grants collapse.
        </p>
        <div class="nx-st-search">
          <span class="nx-st-search-icon" aria-hidden="true"></span>
          <input id="nx-st-trust-search" type="search"
                 placeholder="search modules · 590 MCP agents · type to filter"
                 aria-label="Search modules">
          <span class="nx-st-search-count" id="nx-st-search-count">${sorted.length}</span>
        </div>
        <div class="nx-st-trust-list" id="nx-st-trust-list">
          ${renderTrustRows(sorted.slice(0, 60))}
        </div>
        ${sorted.length > 60 ? `<div class="nx-dim" id="nx-st-trust-more" style="font-size:12px;margin-top:10px">showing first 60 of ${sorted.length} · use the search to narrow</div>` : ""}
      `;
    }
    case "providers": {
      const list = await fetch("/api/providers").then(r => r.ok ? r.json() : {providers:[]}).catch(() => ({providers:[]}));
      const rows = (list.providers || []).map(p => `
        <div class="nx-st-row">
          <dt>${escapeHtml(p.name)} ${p.is_default ? '<span class="nx-st-pill">DEFAULT</span>' : ""}</dt>
          <dd><code>${escapeHtml(p.model || p.kind || "")}</code> · status: <span class="${p.healthy ? "ok":"fail"}">${escapeHtml(p.healthy ? "healthy" : "unavailable")}</span></dd>
        </div>
      `).join("");
      return `
        <h3>LLM providers</h3>
        <p class="nx-dim" style="font-size:13px;margin-bottom:18px">Local llama.cpp / Ollama runs offline. Set NEXUS_OPENAI_KEY / NEXUS_ANTHROPIC_KEY env vars to add cloud providers.</p>
        <dl class="nx-st-rows">${rows || `<div class="nx-empty">no providers registered</div>`}</dl>
      `;
    }
    case "federation": {
      let peers = { peers: [] };
      try { peers = await fetch("/api/federation/peers").then(r => r.ok ? r.json() : {peers:[]}); } catch {}
      return `
        <h3>Federation</h3>
        <p class="nx-dim" style="font-size:13px;margin-bottom:18px">
          Connect ONEXUS instances peer-to-peer. Set <code>NEXUS_FEDERATION_ENABLED=1</code> to enable on this instance.
        </p>
        <dl class="nx-st-rows">
          <div class="nx-st-row">
            <dt>Status</dt>
            <dd><code>${peers.peers ? "enabled" : "disabled"}</code></dd>
          </div>
          <div class="nx-st-row">
            <dt>Peers</dt>
            <dd>${(peers.peers || []).length === 0 ? `<span class="nx-dim">none connected</span>` : (peers.peers || []).map(p => `<code>${escapeHtml(p.peer_id || p.id)}</code>`).join(", ")}</dd>
          </div>
        </dl>
      `;
    }
    case "moods": {
      const current = await fetch("/api/mood/current").then(r => r.ok ? r.json() : {}).catch(() => ({}));
      return `
        <h3>Moods</h3>
        <p class="nx-dim" style="font-size:13px;margin-bottom:18px">
          The MoodEngine watches CPU, engram busy-ratio, trust events, time-of-day, and resident agents.
          Eight palettes shift the whole shell.
        </p>
        <div class="nx-st-mood-now">
          <div class="nx-eyebrow">RIGHT NOW</div>
          <div class="nx-st-mood-name">${escapeHtml((current.mood || state.mood.mood || "calm_focus").replace(/_/g, " "))}</div>
          <div class="nx-st-mood-reason">${escapeHtml(current.reason || "")}</div>
          ${state.mood.override ? `
            <div class="nx-st-mood-override">
              manual override active · <button class="nx-st-mood-clear-btn" id="nx-settings-mood-clear">return to auto</button>
            </div>
          ` : `<div class="nx-st-mood-auto">auto · following the kernel</div>`}
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
        <p class="nx-dim" style="font-size:13px;line-height:1.6">
          An operating system for agents. Local-first, sovereign, gated by Aegis.
          The kernel never touches the network — there's a static test that proves it.
        </p>
        <dl class="nx-st-rows" style="margin-top:18px">
          <div class="nx-st-row">
            <dt>Version</dt>
            <dd><code>v1.0</code></dd>
          </div>
          <div class="nx-st-row">
            <dt>Tests</dt>
            <dd>
              <span class="ok">${fmt(tests.total)}</span> declared
              <span class="nx-dim" style="font-size:11px;margin-left:8px">scanned live from <code>tests/</code></span>
            </dd>
          </div>
          <div class="nx-st-row">
            <dt>Catalog</dt>
            <dd>
              ${fmt(all.total)} agents · ${fmt(runnable.total)} runnable
              <span class="nx-dim" style="font-size:11px;margin-left:8px">(MCP adapter present)</span>
            </dd>
          </div>
          <div class="nx-st-row">
            <dt>Source</dt>
            <dd><a href="https://github.com/AllStreets/ONEXUS" target="_blank" rel="noopener" class="nx-st-link">github.com/AllStreets/ONEXUS ↗</a></dd>
          </div>
          <div class="nx-st-row">
            <dt>License</dt>
            <dd>Apache-2.0</dd>
          </div>
        </dl>
      `;
    }
  }
  return `<h3>${tab}</h3><p class="nx-dim">unknown tab</p>`;
}

// ── Mood picker (click the mood pill) ─────────────────────────────────────
const MOOD_OPTIONS = [
  { key: "calm_focus",    name: "calm focus",    note: "violet · default · low load, eyes-down work" },
  { key: "deep_flow",     name: "deep flow",     note: "jewel green · long uninterrupted stretches" },
  { key: "routing",       name: "routing",       note: "magenta + cyan · cortex dispatching, lots of small tasks" },
  { key: "deliberating",  name: "deliberating",  note: "amber + teal + magenta · council weighing options" },
  { key: "creative",      name: "creative",      note: "vivid navy · open-ended generation, deep ideation" },
  { key: "reflective",    name: "reflective",    note: "plum + rose · review, summarise, look back" },
  { key: "watchful",      name: "watchful",      note: "teal + ember + violet · sentry on, scanning" },
  { key: "alert",         name: "alert",         note: "crimson · trust collapse, denied call, override" },
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
  pop.className = "nx-mood-picker";
  pop.style.top = (rect.bottom + 8) + "px";
  pop.style.right = (window.innerWidth - rect.right) + "px";
  pop.innerHTML = `
    <div class="nx-mp-head">
      <div class="nx-mp-eyebrow">CHOOSE MOOD ${state.mood.override ? `· <span style="color:var(--nx-mood-primary)">OVERRIDE</span>` : `· AUTO`}</div>
      <div class="nx-mp-hint">drives the whole shell · the kernel sees ${escapeHtml(state.mood.kernelMood || state.mood.mood || "calm_focus")} right now</div>
    </div>
    <button class="nx-mp-auto ${isAuto ? "active" : ""}" data-action="auto">
      <span class="nx-mp-auto-icon">∞</span>
      <span class="nx-mp-auto-text">
        <span class="nx-mp-auto-name">Auto · follow the kernel</span>
        <span class="nx-mp-auto-note">currently sensing ${escapeHtml((state.mood.kernelMood || "calm_focus").replace(/_/g, " "))}</span>
      </span>
    </button>
    <div class="nx-mp-grid">
      ${MOOD_OPTIONS.map(m => `
        <button class="nx-mp-cell ${m.key === current && !isAuto ? "active" : ""}" data-mood="${m.key}" title="${escapeHtml(m.note)}">
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
    if (eyebrow) eyebrow.innerHTML = `CHOOSE MOOD ${state.mood.override ? `· <span style="color:var(--nx-mood-primary)">OVERRIDE</span>` : `· AUTO`}`;
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
      applyMood(mood);
      // Best-effort: nudge the engine so a future Auto-mode sees aligned signals
      try {
        const map = {
          calm_focus:    { kernel_cpu: 0.2, engram_busy_ratio: 0.2 },
          deep_flow:     { kernel_cpu: 0.5, engram_busy_ratio: 0.7 },
          routing:       { kernel_cpu: 0.8, engram_busy_ratio: 0.6 },
          deliberating:  { engram_busy_ratio: 0.4, trust_sliding: 0.0 },
          creative:      { kernel_cpu: 0.4, engram_busy_ratio: 0.5 },
          reflective:    { kernel_cpu: 0.15, engram_busy_ratio: 0.3 },
          watchful:      { trust_sliding: -0.05 },
          alert:         { trust_sliding: -0.30 },
        };
        await fetch("/api/mood/observe", {
          method: "POST", headers: {"Content-Type":"application/json"},
          body: JSON.stringify(map[mood] || {}),
        });
      } catch {}
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
    body: "ONEXUS runs agents the way iOS runs apps — workspaces with their own memory, agents with their own trust, and every tool call gated by Aegis. This guide walks every surface in eight minutes. Use ← → to flip pages, click any dot to jump, press Esc to leave.",
    shot: "/aurora/static/guide/01-welcome.png",
    callouts: [
      { x: 10, y: 30, label: "1", note: "Sidebar — workspaces, recent agents, in-OS tools." },
      { x: 50, y: 50, label: "2", note: "Main canvas — workspace home with agent prompts." },
      { x: 89, y: 18, label: "3", note: "Cockpit rail — trust meter, permissions, mood." },
    ],
    cta: { label: "Continue →", action: null },
  },
  {
    eyebrow: "PAGE 2 / 13",
    chapter: "WORKSPACES",
    title: "Each workspace is its own room.",
    body: "Rooms have their own agents, memory, grants, and home tone. Switch between them with ⌘K. Create new ones with ⌘N. Delete by hovering the row and clicking the neon-red trash icon. Each room stays private to itself — what's remembered here doesn't leak there.",
    shot: "/aurora/static/guide/09-sidebar.png",
    fullSidebar: true,
    callouts: [
      { x: 50, y: 13, label: "1", note: "Workspace pills — click to switch, click active again for home." },
      { x: 78, y: 28, label: "2", note: "Hover any row to reveal the delete trash." },
      { x: 50, y: 40, label: "3", note: "+ new workspace · ⌘N." },
    ],
    cta: { label: "Try it · ⌘K", action: "switcher" },
  },
  {
    eyebrow: "PAGE 3 / 13",
    chapter: "CONVERSATION",
    title: "Talk to a room of agents at once.",
    body: "Send a message and Cortex routes it to whoever is best placed to answer. @ mention an agent (@oracle, @council) to call them directly. Press ⌘⏎ to send. The composer stays pinned at the bottom; the thread scrolls above it.",
    shot: "/aurora/static/guide/02-conversation.png",
    callouts: [
      { x: 24, y: 16, label: "1", note: "Agent identity disc + module name." },
      { x: 52, y: 23, label: "2", note: "Inline permission prompt — fires on first sensitive call." },
      { x: 50, y: 93, label: "3", note: "Composer · type, paste, drop files, hit ⌘⏎." },
    ],
    cta: { label: "Try it · type to a room", action: "compose" },
  },
  {
    eyebrow: "PAGE 4 / 13",
    chapter: "FILES",
    title: "Drag, drop, attach.",
    body: "Drop any file anywhere on the conversation surface to attach it. The blue glow overlay confirms drop. Files are stored in <code>.onexus/uploads/</code> under the workspace root, hashed for dedup, registered with Engram so the agent can recall them, and logged to Chronicle. The composer's + button does the same with a file picker.",
    shot: "/aurora/static/guide/02-conversation.png",
    callouts: [
      { x: 35, y: 93, label: "1", note: "The + button opens a file picker." },
      { x: 50, y: 55, label: "2", note: "Drag a file anywhere on the canvas — the overlay glows mood-color." },
      { x: 60, y: 87, label: "3", note: "Attached files appear as chips above the composer." },
    ],
    cta: { label: "Done", action: null },
  },
  {
    eyebrow: "PAGE 5 / 13",
    chapter: "SAFETY MODEL",
    title: "Every sensitive call asks first.",
    body: "Aegis classifies every capability — routine / notable / sensitive / privileged. Routine runs silently. Sensitive pauses the agent until you allow once, allow always for this workspace, or deny. The cockpit log keeps a record of every decision with a colored class dot.",
    shot: "/aurora/static/guide/02-conversation.png",
    callouts: [
      { x: 32, y: 22, label: "1", note: "Amber pulse — sensitive permission requested." },
      { x: 52, y: 23, label: "2", note: "Three pill buttons: allow once · always · here · deny." },
      { x: 89, y: 32, label: "3", note: "Cockpit log records the decision." },
    ],
    cta: { label: "See it in action", action: "seed-permission" },
  },
  {
    eyebrow: "PAGE 6 / 13",
    chapter: "TRUST",
    title: "Trust is earned, asymmetrically.",
    body: "Click the thumb-up or thumb-down icon under any agent message to mark it useful or wrong. Useful = +0.12 to that agent's Aegis trust. Wrong = −0.22. Above 0.75 the agent auto-grants its Notable capabilities. Below 0.50, every grant collapses instantly. The cockpit's trust meter shows the rolling 60-minute delta.",
    shot: "/aurora/static/guide/08-cockpit.png",
    cockpitOnly: true,
    callouts: [
      { x: 28, y: 8, label: "1", note: "Trust meter — gold rising / steel falling / crimson collapse." },
      { x: 28, y: 13, label: "2", note: "Class breakdown by colored dot." },
    ],
    cta: { label: "Done", action: null },
  },
  {
    eyebrow: "PAGE 7 / 13",
    chapter: "COCKPIT",
    title: "Watch what the kernel sees.",
    body: "The right rail keeps trust, permissions, mood, and the agent roster live in view. Toggle it with the chrome icon (top-right). Press ⌘0 for the expanded six-panel cockpit. Every panel auto-refreshes as the kernel runs.",
    shot: "/aurora/static/guide/08-cockpit.png",
    cockpitOnly: true,
    callouts: [
      { x: 28, y: 8,  label: "1", note: "TRUST · last 60 minutes." },
      { x: 28, y: 22, label: "2", note: "RECENT PERMISSIONS log." },
      { x: 28, y: 40, label: "3", note: "AMBIENT MOOD — drives the whole shell." },
      { x: 12, y: 62, label: "4", note: "Built-in agents — click any disc for capabilities." },
    ],
    cta: { label: "Open the expanded cockpit · ⌘0", action: "cockpit" },
  },
  {
    eyebrow: "PAGE 8 / 13",
    chapter: "MOOD · ATMOSPHERE",
    title: "The shell shifts color with what's happening.",
    body: "Click the mood pill (top-right of the title bar) to open a color switcher. Pick any of the 8 atmospheres — Calm focus, Deep flow, Routing, Deliberating, Creative, Reflective, Watchful, Alert — and the <em>whole shell</em> crossfades: ambient mesh, workspace pills, composer focus ring, buttons, capability sheet edge, all of it. Press <code>Auto · follow the kernel</code> at the top to release back to automatic, which picks based on CPU load, engram activity, time of day, and trust events.",
    shot: "/aurora/static/guide/10-mood-picker.png",
    callouts: [
      { x: 73, y: 7,  label: "1", note: "The mood pill — click to open the switcher." },
      { x: 78, y: 16, label: "2", note: "Auto · follow the kernel — releases manual override." },
      { x: 78, y: 38, label: "3", note: "8 swatches — pick one to override the whole atmosphere." },
    ],
    cta: { label: "Try it · pick a mood", action: "moodpicker" },
  },
  {
    eyebrow: "PAGE 9 / 13",
    chapter: "AGENTS",
    title: "Ten built-in. Click any disc.",
    body: "Council deliberates. Specter red-teams. Oracle reads. Legacy remembers. Wraith forgets. Sentry watches. Autonomic automates. Echo mirrors. Consciousness regulates mood. Agents-dispatcher routes to installed third-parties. Click any disc to see its declared capabilities + trust floor + network reach.",
    shot: "/aurora/static/guide/03-capability-sheet.png",
    callouts: [
      { x: 40, y: 27, label: "1", note: "Identity disc + name." },
      { x: 50, y: 65, label: "2", note: "Tools declared + class color." },
      { x: 50, y: 82, label: "3", note: "Trust floor + network reach." },
    ],
    cta: { label: "Done", action: null },
  },
  {
    eyebrow: "PAGE 10 / 13",
    chapter: "WORKSHOP",
    title: "Code + sandbox — without leaving.",
    body: "Open the Workshop from the sidebar (or press ⌘E). Pick a runtime: Python, JavaScript, or shell. Hit Run (or ⌘⏎). Code executes in a subprocess sandbox with a stripped env, an 8-second timeout, and captured stdout/stderr. Every run lands in Chronicle.",
    shot: "/aurora/static/guide/04-workshop.png",
    callouts: [
      { x: 28, y: 14, label: "1", note: "Language selector." },
      { x: 50, y: 35, label: "2", note: "Code editor — JetBrains Mono, 12.5px." },
      { x: 50, y: 78, label: "3", note: "Output panel — exit code, elapsed ms, stdout + stderr." },
    ],
    cta: { label: "Open Workshop · ⌘E", action: "workshop" },
  },
  {
    eyebrow: "PAGE 11 / 13",
    chapter: "WEB SEARCH",
    title: "Search the web — without leaving.",
    body: "Press ⌘/ to open Search. Queries route through aegis.network() to DuckDuckGo's instant-answer API by default — no tracking. Set NEXUS_BRAVE_KEY for organic results via Brave Search. Wikipedia is always a fallback so you never see an empty page.",
    shot: "/aurora/static/guide/05-search.png",
    callouts: [
      { x: 45, y: 13, label: "1", note: "Search input — ⌘/ to focus from anywhere." },
      { x: 45, y: 30, label: "2", note: "Hits — title + URL + snippet + source." },
    ],
    cta: { label: "Open Search · ⌘/", action: "search" },
  },
  {
    eyebrow: "PAGE 12 / 13",
    chapter: "CATALOG",
    title: "6,745 agents · 571 runnable.",
    body: "ONEXUS ships with the AllStreets/ONEXUS-Agents catalog bundled. Browse it from the sidebar (or press ⌘? — not yet). Filter by runnable-only to see the 571 with MCP adapters that you can launch with one click. Each card links to its source repo.",
    shot: "/aurora/static/guide/06-catalog.png",
    callouts: [
      { x: 55, y: 13, label: "1", note: "Filters: search · category · runnable-only." },
      { x: 35, y: 35, label: "2", note: "Each card has Launch + source link." },
    ],
    cta: { label: "Browse catalog →", action: "catalog" },
  },
  {
    eyebrow: "PAGE 13 / 13",
    chapter: "KEYBOARD",
    title: "Shortcuts you'll use every day.",
    body: "Master these and you barely touch the mouse.",
    shot: null,
    keys: [
      ["⌘K",   "open workspace switcher"],
      ["⌘N",   "new workspace"],
      ["⌘0",   "expanded cockpit"],
      ["⌘E",   "open workshop"],
      ["⌘/",   "web search"],
      ["⌘P",   "settings"],
      ["⌘⏎",   "send message"],
      ["←  →",  "flip guide pages"],
      ["Esc",  "close any overlay / exit focus mode"],
    ],
    cta: { label: "Done — start using ONEXUS", action: "close" },
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
          <span class="nx-g-key-kbd">${escapeHtml(k)}</span>
          <span class="nx-g-key-desc">${escapeHtml(v)}</span>
        </div>
      `).join("")}
    </div>
    <div class="nx-g-dismiss-hint">
      click anywhere · press <span class="kbd">esc</span> · or click <span class="kbd">Done</span> · arrow-left to go back
    </div>
  ` : "";

  const dotsHTML = GUIDE_PAGES.map((_, i) =>
    `<button class="nx-g-dot ${i === pageIndex ? "active" : (i < pageIndex ? "done" : "")}" data-i="${i}" aria-label="Page ${i+1}: ${escapeHtml(GUIDE_PAGES[i].chapter)}" title="Page ${i+1} · ${escapeHtml(GUIDE_PAGES[i].chapter)}">${i+1}</button>`
  ).join("");

  const showShot = p.shot && !p.keys;

  const html = `
    <div class="nx-guide-overlay" id="nx-guide-overlay" role="dialog" aria-modal="true">
      <button class="nx-g-close-btn" id="nx-g-close" aria-label="Close guide">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"><path d="M3.5 3.5l7 7M10.5 3.5l-7 7"/></svg>
        <span>Close</span>
        <span class="kbd">esc</span>
      </button>

      <div class="nx-guide-stage">
        <div class="nx-g-eyebrow">${escapeHtml(p.eyebrow)} · ${escapeHtml(p.chapter)}</div>
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
        <button class="nx-g-arrow" id="nx-g-prev" ${pageIndex === 0 ? "disabled" : ""} aria-label="Previous page" title="Previous page (←)">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4 6 9l5 5"/></svg>
        </button>
        <div class="nx-g-dots">${dotsHTML}</div>
        <div class="nx-g-right">
          ${p.cta && p.cta.action ? `
            <button class="nx-g-cta" id="nx-g-next" title="${escapeHtml(p.cta.label)}">
              <span>${escapeHtml(p.cta.label)}</span>
            </button>
          ` : ""}
          <button class="nx-g-arrow nx-g-arrow-next" id="nx-g-advance"
                  ${pageIndex === total - 1 ? "disabled" : ""}
                  aria-label="${pageIndex === total - 1 ? "Last page" : "Next page"}"
                  title="${pageIndex === total - 1 ? "Done — close the guide" : "Next page (→)"}">
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4l5 5-5 5"/></svg>
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
  pop.className = "nx-history-popover";
  pop.style.top  = (rect.bottom + 8) + "px";
  pop.style.left = rect.left + "px";

  if (!items.length) {
    pop.innerHTML = `
      <div class="nx-hp-head">${kind} history</div>
      <div class="nx-hp-empty">no history yet</div>
    `;
  } else {
    const rowsHTML = items.map((it, i) => {
      const preview = kind === "workshop"
        ? `<span class="hp-lang">${escapeHtml(it.language || "")}</span> <span class="hp-prev">${escapeHtml((it.code || "").split("\n")[0].slice(0, 64))}</span>`
        : `<span class="hp-prev">${escapeHtml(it.query || "")}</span>`;
      return `
        <button class="nx-hp-row" data-i="${i}">
          ${preview}
          <span class="hp-ago">${escapeHtml(fmtAgo(it.ts))}</span>
        </button>
      `;
    }).join("");
    pop.innerHTML = `
      <div class="nx-hp-head">
        <span>${kind} history · ${items.length}</span>
        <button class="nx-hp-clear" id="nx-hp-clear" title="Clear ${kind} history">clear</button>
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
async function renderWorkshop() {
  const main = document.getElementById("nx-main");
  // Discover available runtimes from the server
  let langs = {};
  try {
    const r = await fetch("/api/workshop/languages");
    if (r.ok) langs = (await r.json()).languages || {};
  } catch {}
  const available = Object.keys(langs);
  const defaultLang = available[0] || "python";
  const lastCode = state._workshopCode || "";
  const lastLang = state._workshopLang || defaultLang;

  main.innerHTML = `
    <div class="nx-main-inner">
      <header style="display:flex;align-items:end;justify-content:space-between;margin-bottom:18px">
        <div>
          <div class="nx-eyebrow" style="margin-bottom:6px">Workshop</div>
          <div class="nx-display" style="font-size:26px;color:#f3ecff;font-weight:700">Code &amp; sandbox</div>
          <div class="nx-dim" style="font-size:13px;margin-top:4px">${available.length} runtime${available.length===1?"":"s"} available · gated by Aegis · logged to Chronicle</div>
        </div>
      </header>

      <div class="nx-workshop">
        <div class="nx-workshop-controls">
          <select id="nx-workshop-lang" class="nx-input">
            ${available.map(l => `<option value="${escapeHtml(l)}" ${l===lastLang?"selected":""}>${escapeHtml(l)}</option>`).join("")}
          </select>
          <button id="nx-workshop-run" class="nx-run-btn">
            <span>Run</span>
            <span class="run-kbd">⌘⏎</span>
          </button>
          <button id="nx-workshop-history" class="nx-history-btn" title="Recent runs (clearable)">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="6" cy="6" r="4.5"/>
              <path d="M6 3.5V6l1.8 1.2"/>
            </svg>
            <span>History</span>
          </button>
        </div>
        <textarea id="nx-workshop-code" class="nx-workshop-code" spellcheck="false"
                  placeholder="# write code — runs in a subprocess sandbox, no network access by default"
        >${escapeHtml(lastCode)}</textarea>
        <div class="nx-workshop-out" id="nx-workshop-out">
          <div class="nx-empty" style="opacity:0.45;padding:18px;font-size:11.5px">Run a snippet to see stdout / stderr here.</div>
        </div>
      </div>
    </div>
  `;

  const codeEl = document.getElementById("nx-workshop-code");
  const langEl = document.getElementById("nx-workshop-lang");
  const outEl = document.getElementById("nx-workshop-out");
  const runBtn = document.getElementById("nx-workshop-run");

  const run = async () => {
    runBtn.disabled = true;
    const code = codeEl.value;
    const language = langEl.value;
    state._workshopCode = code;
    state._workshopLang = language;
    outEl.innerHTML = `<div class="nx-empty" style="opacity:0.55;padding:14px;font-size:11.5px">Running…</div>`;
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
      outEl.innerHTML = `
        <div class="nx-workshop-stats">
          <span class="${body.exit_code === 0 ? 'ok' : 'fail'}">exit ${body.exit_code}</span>
          <span>${body.elapsed_ms} ms</span>
          ${body.truncated ? `<span class="warn">truncated</span>` : ""}
        </div>
        ${body.stdout ? `<div class="nx-workshop-block"><div class="nx-workshop-block-lbl">STDOUT</div><pre>${escapeHtml(body.stdout)}</pre></div>` : ""}
        ${body.stderr ? `<div class="nx-workshop-block err"><div class="nx-workshop-block-lbl">STDERR</div><pre>${escapeHtml(body.stderr)}</pre></div>` : ""}
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
}

// ── Search (in-OS web search) ─────────────────────────────────────────────
async function renderSearch(hash) {
  const main = document.getElementById("nx-main");
  const qMatch = hash.match(/[?&]q=([^&]+)/);
  const initial = qMatch ? decodeURIComponent(qMatch[1]) : "";
  main.innerHTML = `
    <div class="nx-main-inner">
      <header style="margin-bottom:18px">
        <div class="nx-eyebrow" style="margin-bottom:6px">Search</div>
        <div class="nx-display" style="font-size:26px;color:#f3ecff;font-weight:700">Search the web — without leaving</div>
        <div class="nx-dim" style="font-size:13px;margin-top:4px">Routes through aegis.network() · default provider: DuckDuckGo · no tracking</div>
      </header>
      <form class="nx-composer" id="nx-search-form" style="margin:0 0 18px">
        <input id="nx-search-q" type="search" value="${escapeHtml(initial)}" autofocus
               placeholder="what do you need to know?" style="flex:1;background:transparent;border:0;outline:0;color:inherit;font:inherit;font-size:14px">
        <button type="button" id="nx-search-history" class="nx-history-btn" title="Recent searches (clearable)">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="6" cy="6" r="4.5"/>
            <path d="M6 3.5V6l1.8 1.2"/>
          </svg>
          <span>History</span>
        </button>
        <button type="submit" class="nx-run-btn">Search</button>
      </form>
      <div class="nx-search-results" id="nx-search-results"></div>
    </div>
  `;

  const formEl = document.getElementById("nx-search-form");
  const qEl = document.getElementById("nx-search-q");
  const resultsEl = document.getElementById("nx-search-results");

  const doSearch = async (q) => {
    if (!q) return;
    resultsEl.innerHTML = `<div class="nx-empty" style="opacity:0.55;padding:18px">Searching…</div>`;
    try {
      const r = await fetch(`/api/search?q=${encodeURIComponent(q)}&limit=12`);
      if (!r.ok) {
        const txt = await r.text();
        resultsEl.innerHTML = `<div class="nx-empty">Search failed: ${escapeHtml(txt)}</div>`;
        return;
      }
      const body = await r.json();
      // Save to history regardless of result count
      saveHistoryEntry("search", { query: q, hit_count: body.hits?.length || 0 });
      if (!body.hits.length) {
        resultsEl.innerHTML = `<div class="nx-empty">No results for ${escapeHtml(q)}.</div>`;
        return;
      }
      resultsEl.innerHTML = body.hits.map(h => `
        <a class="nx-search-hit" href="${escapeHtml(h.url)}" target="_blank" rel="noopener">
          <div class="hit-title">${escapeHtml(h.title || h.url)}</div>
          <div class="hit-url">${escapeHtml(h.url)}</div>
          ${h.snippet ? `<div class="hit-snippet">${escapeHtml(h.snippet)}</div>` : ""}
          ${h.source ? `<div class="hit-source">${escapeHtml(h.source)}</div>` : ""}
        </a>
      `).join("");
    } catch (e) {
      resultsEl.innerHTML = `<div class="nx-empty">Network error: ${escapeHtml(e.message)}</div>`;
    }
  };

  formEl.addEventListener("submit", (e) => { e.preventDefault(); doSearch(qEl.value.trim()); });
  document.getElementById("nx-search-history").addEventListener("click", (e) => {
    e.stopPropagation();
    openHistoryPopover(e.currentTarget, "search", (item) => {
      qEl.value = item.query;
      doSearch(item.query);
    });
  });
  if (initial) doSearch(initial);
}

// ── Overlay: workspace switcher (⌘K) ──────────────────────────────────────
function renderSwitcher() {
  const root = document.getElementById("nx-overlay-root");
  const tiles = state.workspaces.map(w => `
    <div class="nx-ws-tile nx-tone-${w.tone || "indigo"} ${w.workspace_id === state.active ? "active" : ""}"
         data-id="${w.workspace_id}">
      <div class="tile-eyebrow">${escapeHtml((w.tone || "indigo").toUpperCase())}</div>
      <div class="tile-name">${escapeHtml(w.name)}</div>
      <div class="tile-footer">
        <div class="disc-stack">
          ${(w.resident_agents || []).slice(0, 3).map(a => agentDisc(a, { size: 22 })).join("")}
        </div>
        <span class="nx-mono" style="opacity:0.8">${w.workspace_id === state.active ? "active" : (w.last_active_at ? "seen" : "—")}</span>
      </div>
    </div>
  `).join("");
  root.innerHTML = `
    <div class="nx-switcher-overlay" id="nx-switcher-overlay">
      <div class="nx-switcher">
        <h3>Workspaces</h3>
        <div class="nx-switcher-grid">
          ${tiles}
          <div class="nx-ws-tile new" id="nx-new-workspace-overlay">
            ${UI.plus(22)}
            <div style="font-size:13px;margin-top:6px">New workspace</div>
          </div>
        </div>
      </div>
    </div>
  `;
  root.querySelectorAll(".nx-ws-tile[data-id]").forEach(el => {
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
  "slate", "graphite",
];

function _toneSwatchHex(tone) {
  const computed = getComputedStyle(document.documentElement);
  return computed.getPropertyValue(`--nx-tone-${tone}-a`).trim() || "#888";
}

function openNewWorkspaceForm() {
  const root = document.getElementById("nx-overlay-root");
  let selectedTone = "indigo";

  const toneSwatchHTML = WORKSPACE_TONES.map(t => `
    <button type="button" class="nx-ws-tone-swatch ${t === selectedTone ? "selected" : ""}" data-tone="${t}" title="${t}">
      <span class="dot" style="background:linear-gradient(135deg, var(--nx-tone-${t}-a), var(--nx-tone-${t}-b))"></span>
      <span class="label">${t}</span>
    </button>
  `).join("");

  root.innerHTML = `
    <div class="nx-switcher-overlay" id="nx-newws-overlay">
      <form class="nx-switcher nx-newws" id="nx-newws-form" style="max-width:560px" autocomplete="off">
        <h3>New workspace</h3>
        <div class="nx-newws-fields">
          <input id="ws-name" class="nx-newws-input" placeholder="Name (e.g. Client work)" required autofocus>
          <input id="ws-id" class="nx-newws-input" placeholder="workspace-id (kebab-case — auto-derived from name)" pattern="^[a-z][a-z0-9-]{0,63}$">

          <div class="nx-newws-tones-label">Color · pick a home tone</div>
          <div class="nx-newws-tones" id="ws-tones">
            ${toneSwatchHTML}
          </div>
          <input type="hidden" id="ws-tone" value="${selectedTone}">

          <div id="ws-error" class="nx-newws-error"></div>
        </div>
        <div class="nx-newws-actions">
          <button type="button" class="nx-newws-cancel" id="ws-cancel">Cancel</button>
          <button type="submit" class="nx-newws-create" id="ws-create">Create workspace</button>
        </div>
      </form>
    </div>`;

  // Wire swatch selection
  root.querySelectorAll(".nx-ws-tone-swatch[data-tone]").forEach(btn => {
    btn.addEventListener("click", () => {
      root.querySelectorAll(".nx-ws-tone-swatch").forEach(b => b.classList.remove("selected"));
      btn.classList.add("selected");
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
      errEl.textContent = "ID must be kebab-case (a-z, 0-9, hyphens), starting with a letter.";
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
        const err = await r.json().catch(() => ({ detail: "request failed" }));
        errEl.textContent = err.detail || "failed";
      }
    } catch (err) {
      errEl.textContent = "Network error: " + err.message;
    }
  });
}

function closeOverlay() {
  document.getElementById("nx-overlay-root").innerHTML = "";
}

// ── Overlay: expanded cockpit (⌘0) ─────────────────────────────────────────
async function toggleCockpitOverlay() {
  const root = document.getElementById("nx-overlay-root");
  if (root.querySelector(".nx-cockpit-overlay")) { closeOverlay(); return; }
  root.innerHTML = `
    <div class="nx-cockpit-overlay" id="nx-cockpit-overlay">
      <div class="nx-cockpit">
        <div class="nx-cockpit-scan"></div>
        <div class="nx-cockpit-header">
          <span class="nx-cockpit-title">COCKPIT — ${escapeHtml(state.mood.mood)}</span>
          <button class="nx-cockpit-close" id="nx-cockpit-close">ESC</button>
        </div>
        <div class="nx-cockpit-grid">
          <!-- Row 1: Trust spans 2 cols on the left · Mood · Workspaces -->
          <div class="nx-cockpit-panel span2">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Trust · 60m</span>
              <span class="nx-cockpit-panel-badge">${state.trust.history.length} events</span>
            </div>
            <svg viewBox="0 0 320 110" preserveAspectRatio="none" style="width:100%;height:110px">
              ${trustSparkSVG(state.trust.history.length ? state.trust.history : [], state.trust.direction)
                  .replace('viewBox="0 0 320 92"', '')}
            </svg>
            <div style="margin-top:10px;font-family:var(--nx-font-display);font-size:22px;color:#f3ecff;">
              ${state.trust.delta > 0 ? "+" : ""}${state.trust.delta.toFixed(2)}
              <span style="font-family:var(--nx-font-mono);font-size:11px;opacity:0.7;letter-spacing:0.16em;margin-left:8px;text-transform:uppercase">${escapeHtml(state.trust.direction || "—")}</span>
            </div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Ambient mood</span></div>
            <div style="font-family:var(--nx-font-display);font-size:20px;color:#f3ecff;margin-bottom:6px">${escapeHtml((state.mood.mood || "calm_focus").replace(/_/g, " "))}</div>
            <div class="nx-dim" style="font-size:11px;line-height:1.4">${escapeHtml(state.mood.reason || "")}</div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Workspaces</span>
              <span class="nx-cockpit-panel-badge">${state.workspaces.length}</span>
            </div>
            <div style="font-size:12px;line-height:1.8">${state.workspaces.map(w => `<div>· ${escapeHtml(w.name)}</div>`).join("") || "<div class='nx-dim'>none</div>"}</div>
          </div>

          <!-- Row 2: Recent permissions spans 3 cols · Pending tickets on the right -->
          <div class="nx-cockpit-panel span3">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Recent permissions</span>
              <span class="nx-cockpit-panel-badge">${state.perms.recent.length}</span>
            </div>
            <div style="font-size:11.5px;line-height:1.7">
              ${(state.perms.recent.slice(0, 6).map(r =>
                `<div class="nx-cockpit-tail-row">${escapeHtml(r.capability || "")} → ${escapeHtml(r.target || "—")} <span style="float:right;opacity:0.55">${escapeHtml(r.status || "")}</span></div>`
              )).join("") || "<div class='nx-dim'>no activity</div>"}
            </div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Pending</span></div>
            <div style="font-family:var(--nx-font-display);font-size:26px;color:#f3ecff">
              ${state.perms.pending.length}
            </div>
            <div class="nx-dim" style="font-size:11px;margin-top:4px">ticket${state.perms.pending.length === 1 ? "" : "s"} awaiting decision</div>
          </div>
        </div>
      </div>
    </div>
  `;
  document.getElementById("nx-cockpit-close").addEventListener("click", closeOverlay);
  document.getElementById("nx-cockpit-overlay").addEventListener("click", (e) => {
    if (e.target.id === "nx-cockpit-overlay") closeOverlay();
  });
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
  if (hash === "#/workspaces") { renderWorkspacesGrid(); return; }
  if (hash.startsWith("#/catalog")) { renderCatalog(); return; }
  if (hash === "#/settings") { renderSettings(); return; }
  if (hash === "#/workshop") { renderWorkshop(); return; }
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
  // Trust + permission log: poll every 30s, only refresh cockpit (never the
  // conversation) so the user's typing isn't disrupted.
  setInterval(async () => {
    await Promise.allSettled([loadTrust(), loadPermissions()]);
    renderCockpitRail();
  }, 30000);
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
function attachKeybinds() {
  window.addEventListener("keydown", (e) => {
    const meta = e.metaKey || e.ctrlKey;
    if (meta && e.key === "k") { e.preventDefault(); loadWorkspaces().then(renderSwitcher); return; }
    if (meta && e.key === "n") { e.preventDefault(); openNewWorkspaceForm(); return; }
    if (meta && e.key === "0") { e.preventDefault(); toggleCockpitOverlay(); return; }
    if (meta && (e.key === "p" || e.key === "P")) { e.preventDefault(); location.hash = "#/settings"; return; }
    if (meta && e.key === "e") { e.preventDefault(); location.hash = "#/workshop"; return; }
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
