/* ───────────────────────────────────────────────────────────────────────────
 * ONEXUS Aurora — application bootstrap and renderers.
 * Layout: persistent window shell with sidebar + main + cockpit rail.
 * Overlays for ⌘K switcher / ⌘N new workspace / ⌘` cockpit / ⌘, settings.
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
    body: "The right rail keeps trust, permissions, mood, and the agent roster live in view. Press ⌘\` for the expanded six-panel cockpit.",
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
    body: "⌘K switch · ⌘N new workspace · ⌘\` cockpit · ⌘, settings · click the trash on any workspace to delete it. Have fun.",
    diagram: () => sceneReady(),
  },
];

function renderTour(index) {
  const root = document.getElementById("nx-overlay-root");
  const scene = TOUR_SCENES[index];
  const total = TOUR_SCENES.length;
  const dots = TOUR_SCENES.map((_, i) =>
    `<span class="nx-tour-dot ${i === index ? "active" : (i < index ? "done" : "")}" data-i="${i}"></span>`
  ).join("");
  root.innerHTML = `
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
  // Esc closes
  const onKey = (e) => {
    if (e.key === "Escape") { close(); window.removeEventListener("keydown", onKey); }
    if (e.key === "ArrowRight") { if (index < total - 1) renderTour(index + 1); }
    if (e.key === "ArrowLeft")  { if (index > 0) renderTour(index - 1); }
  };
  window.addEventListener("keydown", onKey, { once: false });
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
  // 4 workspace tiles that drift apart and back together (boomerang)
  const tones = [
    { x: -70, y: -30, c1: "#5a6cd0", c2: "#2c3a78" },
    { x:  70, y: -30, c1: "#88a888", c2: "#3e5840" },
    { x: -70, y:  40, c1: "#c060a0", c2: "#5e2050" },
    { x:  70, y:  40, c1: "#e8a06c", c2: "#844820" },
  ];
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(160 110)" class="nx-tour-anim-rooms">
        ${tones.map(t => `
          <g transform="translate(${t.x} ${t.y})">
            <rect x="-46" y="-26" width="92" height="52" rx="9"
                  fill="url(#g-${t.c1.replace('#','')})" opacity="0.95"/>
            <defs>
              <linearGradient id="g-${t.c1.replace('#','')}" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="${t.c1}"/>
                <stop offset="100%" stop-color="${t.c2}"/>
              </linearGradient>
            </defs>
            <circle cx="-32" cy="-14" r="3" fill="#ffffff" opacity="0.8"/>
          </g>
        `).join("")}
        <circle r="14" fill="url(#t-orb)"/>
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
  // Amber permission prompt that pulses + pills slide in
  return `
    <svg viewBox="0 0 320 220" width="100%" height="100%" aria-hidden="true">
      <g transform="translate(160 110)">
        <rect x="-130" y="-32" width="260" height="64" rx="12"
              fill="rgba(248,196,96,0.08)" stroke="rgba(248,196,96,0.35)" stroke-width="1"
              class="nx-tour-anim-card"/>
        <circle cx="-110" cy="0" r="6" fill="#f8c460" class="nx-tour-anim-pulse-dot"/>
        <circle cx="-110" cy="0" r="11" fill="none" stroke="rgba(248,196,96,0.50)" class="nx-tour-anim-ping"/>
        <text x="-92" y="-6" font-family="ui-monospace,monospace" font-size="9" letter-spacing="2" fill="#f8c460">FS.WRITE · SENSITIVE</text>
        <text x="-92" y="10" font-family="ui-sans-serif,sans-serif" font-size="10" fill="#e8defc">oracle → src/kernel/cortex.py</text>
        <g class="nx-tour-anim-pills">
          <rect x="22" y="-12" width="40" height="22" rx="11" fill="rgba(154,255,182,0.14)" stroke="rgba(154,255,182,0.40)"/>
          <text x="42" y="2" font-family="ui-sans-serif,sans-serif" font-size="8.5" font-weight="600" fill="#a8f4c0" text-anchor="middle">allow</text>
          <rect x="66" y="-12" width="48" height="22" rx="11" fill="rgba(168,124,232,0.18)" stroke="rgba(168,124,232,0.50)"/>
          <text x="90" y="2" font-family="ui-sans-serif,sans-serif" font-size="8.5" font-weight="600" fill="#e0d0ff" text-anchor="middle">always</text>
          <rect x="118" y="-12" width="32" height="22" rx="11" fill="rgba(248,96,120,0.10)" stroke="rgba(248,96,120,0.36)"/>
          <text x="134" y="2" font-family="ui-sans-serif,sans-serif" font-size="8.5" font-weight="600" fill="#f8a0b0" text-anchor="middle">deny</text>
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
  document.getElementById("nx-mood-pill").addEventListener("click", toggleCockpitOverlay);
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
  // Click the workspace name in the chrome → return to that workspace's home
  // (clears the active thread and shows the welcome state + prompt cards).
  document.getElementById("nx-chrome-context").addEventListener("click", () => {
    if (!state.active) return;
    state.thread.set(state.active, []);
    location.hash = `#/conversation/${state.active}`;
    renderConversation(state.active);
  });

  // Chrome traffic lights — wired so they aren't decorative
  document.getElementById("nx-tl-close").addEventListener("click", () => {
    // window.close() only works if the tab was opened by script. If not, give
    // the user a clean "are you sure" path via a confirm dialog.
    if (window.opener) { window.close(); return; }
    if (confirm("Close ONEXUS in this tab?")) {
      try { window.close(); } catch {}
      // Fallback: navigate to about:blank
      setTimeout(() => { location.href = "about:blank"; }, 50);
    }
  });
  document.getElementById("nx-tl-focus").addEventListener("click", () => {
    document.body.classList.toggle("nx-focus-mode");
  });
  document.getElementById("nx-cockpit-toggle").addEventListener("click", () => {
    document.body.classList.toggle("nx-cockpit-hidden");
  });
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
  const composerHTML = `
    <form class="nx-composer" id="nx-composer" autocomplete="off">
      <button type="button" class="nx-attach-btn" id="nx-attach-btn" title="Attach file (or drag-and-drop)">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M9.8 5.5 5.8 9.5a2 2 0 1 1-2.8-2.8L8 1.7a3 3 0 0 1 4.2 4.2L7.2 11a4 4 0 0 1-5.7-5.6"/>
        </svg>
      </button>
      <input id="nx-composer-input"
             placeholder="${attachedFiles.length ? `message + ${attachedFiles.length} file${attachedFiles.length===1?'':'s'}…` : 'message agents in this workspace…'}"
             aria-label="Compose a message"
             autofocus>
      <input type="file" id="nx-file-input" multiple style="display:none">
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

  // File attach + drag-and-drop
  const fileInput = document.getElementById("nx-file-input");
  const attachBtn = document.getElementById("nx-attach-btn");
  attachBtn?.addEventListener("click", () => fileInput?.click());
  fileInput?.addEventListener("change", async (e) => {
    for (const f of e.target.files) await uploadFile(workspaceId, f);
    e.target.value = "";
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
  // Drop anywhere on the main canvas
  main.ondragover = (e) => { e.preventDefault(); main.classList.add("nx-dragover"); };
  main.ondragleave = (e) => { if (e.target === main) main.classList.remove("nx-dragover"); };
  main.ondrop = async (e) => {
    e.preventDefault();
    main.classList.remove("nx-dragover");
    for (const item of e.dataTransfer?.files || []) await uploadFile(workspaceId, item);
  };

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
      <button class="nx-tour-link" id="nx-tour-link" data-workspace="${escapeHtml(ws.workspace_id)}">
        See the safety model in action — fire a sample permission prompt
      </button>
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
        ${a.source_github ? `<a class="src-link" href="${escapeHtml(a.source_github)}" target="_blank" rel="noopener">source ↗</a>` : ""}
      </div>
    </div>
  `;
}

// ── Main view: settings ───────────────────────────────────────────────────
async function renderSettings() {
  const main = document.getElementById("nx-main");
  main.innerHTML = `
    <div class="nx-main-inner">
      <div class="nx-settings-shell">
        <nav class="nx-settings-tabs">
          <button class="active" data-tab="general">General</button>
          <button data-tab="security">Security</button>
          <button data-tab="providers">Providers</button>
          <button data-tab="federation">Federation</button>
          <button data-tab="moods">Moods</button>
          <button data-tab="about">About</button>
        </nav>
        <section class="nx-card nx-settings-panel" id="nx-settings-panel">
          <h3>General</h3>
          <p class="nx-dim" style="font-size:13px">Workspace defaults, autosave, and locale.</p>
        </section>
      </div>
    </div>
  `;
  main.querySelectorAll(".nx-settings-tabs button").forEach(b => {
    b.addEventListener("click", () => {
      main.querySelectorAll(".nx-settings-tabs button").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      const tab = b.dataset.tab;
      const panel = document.getElementById("nx-settings-panel");
      const heading = tab[0].toUpperCase() + tab.slice(1);
      panel.innerHTML = `<h3>${heading}</h3><p class="nx-dim" style="font-size:13px">— stub —</p>`;
    });
  });
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
    } catch (e) {
      outEl.innerHTML = `<pre class="nx-workshop-err">${escapeHtml(e.message)}</pre>`;
    } finally {
      runBtn.disabled = false;
    }
  };
  runBtn.addEventListener("click", run);
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
function openNewWorkspaceForm() {
  const root = document.getElementById("nx-overlay-root");
  root.innerHTML = `
    <div class="nx-switcher-overlay" id="nx-newws-overlay">
      <form class="nx-switcher" id="nx-newws-form" style="max-width:480px" autocomplete="off">
        <h3>New workspace</h3>
        <div style="display:flex;flex-direction:column;gap:10px">
          <input id="ws-name" placeholder="Name (e.g. Client work)" required autofocus
                 style="padding:10px 12px;border:1px solid var(--nx-card-border);background:rgba(232,222,252,0.04);color:inherit;border-radius:8px;font:inherit">
          <input id="ws-id" placeholder="workspace-id (kebab-case)" pattern="^[a-z][a-z0-9-]{0,63}$"
                 style="padding:10px 12px;border:1px solid var(--nx-card-border);background:rgba(232,222,252,0.04);color:inherit;border-radius:8px;font:inherit">
          <select id="ws-tone" style="padding:10px 12px;border:1px solid var(--nx-card-border);background:rgba(232,222,252,0.04);color:inherit;border-radius:8px;font:inherit">
            <option value="indigo">indigo</option>
            <option value="magenta">magenta</option>
            <option value="sage">sage</option>
            <option value="plum">plum</option>
            <option value="amber">amber</option>
          </select>
          <div id="ws-error" class="nx-dim" style="font-size:12px;color:#ffb8c0;min-height:16px"></div>
          <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:4px">
            <button type="button" class="nx-pill" id="ws-cancel">Cancel</button>
            <button type="submit" id="ws-create" style="padding:6px 14px;font-size:12px;background:rgba(168,124,232,0.18);border:1px solid rgba(168,124,232,0.40);border-radius:999px;color:#e0d0ff;font-weight:600;cursor:pointer">Create</button>
          </div>
        </div>
      </form>
    </div>`;

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

// ── Overlay: expanded cockpit (⌘`) ─────────────────────────────────────────
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
          <div class="nx-cockpit-panel span2 row2">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Trust · 60m</span>
              <span class="nx-cockpit-panel-badge">${state.trust.history.length} events</span>
            </div>
            <svg viewBox="0 0 320 160" preserveAspectRatio="none" style="width:100%;height:160px">
              ${trustSparkSVG(state.trust.history.length ? state.trust.history : [], state.trust.direction)
                  .replace('viewBox="0 0 320 92"', '')}
            </svg>
            <div style="margin-top:8px;font-size:11px;opacity:0.7">
              ${state.trust.delta > 0 ? "+" : ""}${state.trust.delta.toFixed(2)} · ${state.trust.direction}
            </div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Mood</span></div>
            <div style="font-family:var(--nx-font-display);font-size:18px;color:#f3ecff;margin-bottom:4px">${escapeHtml((state.mood.mood || "calm_focus").replace(/_/g, " "))}</div>
            <div class="nx-dim" style="font-size:11px">${escapeHtml(state.mood.reason || "")}</div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Workspaces</span></div>
            <div style="font-size:11px;line-height:1.7">${state.workspaces.map(w => `<div>· ${escapeHtml(w.name)}</div>`).join("") || "<div class='nx-dim'>none</div>"}</div>
          </div>
          <div class="nx-cockpit-panel span2">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Recent permissions</span></div>
            <div style="font-size:11px;line-height:1.7">
              ${(state.perms.recent.slice(0, 6).map(r =>
                `<div class="nx-cockpit-tail-row">${escapeHtml(r.capability || "")} → ${escapeHtml(r.target || "—")} <span style="float:right;opacity:0.55">${escapeHtml(r.status || "")}</span></div>`
              )).join("") || "<div class='nx-dim'>no activity</div>"}
            </div>
          </div>
          <div class="nx-cockpit-panel">
            <div class="nx-cockpit-panel-header"><span class="nx-cockpit-panel-label">Pending</span></div>
            <div style="font-size:11px">${state.perms.pending.length} ticket${state.perms.pending.length === 1 ? "" : "s"}</div>
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
  // Mood
  try {
    const w = new WebSocket(`${wsProto}//${location.host}/api/mood/ws`);
    w.onmessage = (e) => {
      try {
        const body = JSON.parse(e.data);
        state.mood.mood = body.mood;
        state.mood.reason = body.reason || "";
        applyMood(body.mood);
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
    if (meta && e.key === "`") { e.preventDefault(); toggleCockpitOverlay(); return; }
    if (meta && e.key === ",") { e.preventDefault(); location.hash = "#/settings"; return; }
    if (meta && e.key === "e") { e.preventDefault(); location.hash = "#/workshop"; return; }
    if (meta && e.key === "/") { e.preventDefault(); location.hash = "#/search"; return; }
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
