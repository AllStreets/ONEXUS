import { KERNEL_MARK, agentDisc, UI } from "/aurora/static/icons.js";

document.getElementById("nx-kernel-mark").innerHTML = KERNEL_MARK(14);

// ── State ────────────────────────────────────────────────────────────────
const state = {
  workspaces: [],
  active: null,
};

async function loadWorkspaces() {
  try {
    const r = await fetch("/api/workspaces");
    if (r.ok) {
      const body = await r.json();
      state.workspaces = body.workspaces;
      state.active = body.active;
      // Update header active workspace label
      const label = document.getElementById("nx-active-workspace");
      if (label) {
        if (state.active) {
          const cfg = state.workspaces.find(w => w.workspace_id === state.active);
          label.textContent = cfg ? cfg.name : state.active;
        } else {
          label.textContent = "No workspace";
        }
      }
    }
  } catch {}
}

// ── Switcher overlay ─────────────────────────────────────────────────────
function renderSwitcher() {
  const root = document.getElementById("nx-overlay-root");
  const tiles = state.workspaces.map(w => `
    <div class="nx-ws-tile nx-tone-${w.tone} ${w.workspace_id === state.active ? "active" : ""}"
         data-id="${w.workspace_id}">
      <div class="tile-eyebrow">${w.tone.toUpperCase()}</div>
      <div class="tile-name">${escapeHtml(w.name)}</div>
      <div class="tile-footer">
        <div class="disc-stack">
          ${w.resident_agents.slice(0, 3).map(a =>
            agentDisc(a, { size: 22 })
          ).join("")}
        </div>
        <span class="nx-mono" style="opacity:0.8">
          ${w.workspace_id === state.active ? "active" : (w.last_active_at ? "seen" : "—")}
        </span>
      </div>
    </div>
  `).join("");
  root.innerHTML = `
    <div class="nx-switcher-overlay" id="nx-switcher-overlay">
      <div class="nx-card nx-switcher">
        <h3>Workspaces</h3>
        <div class="nx-switcher-grid">
          ${tiles}
          <div class="nx-ws-tile new" id="nx-new-workspace">
            ${UI.plus(22)}
            <div style="font-size:13px;margin-top:6px">New workspace</div>
          </div>
        </div>
      </div>
    </div>`;

  // Click handlers
  root.querySelectorAll(".nx-ws-tile[data-id]").forEach(el => {
    el.addEventListener("click", async () => {
      await fetch(`/api/workspaces/${el.dataset.id}/switch`, { method: "POST" });
      await loadWorkspaces();
      closeOverlay();
      location.hash = `#/conversation/${el.dataset.id}`;
    });
  });
  document.getElementById("nx-new-workspace").addEventListener("click", openNewWorkspaceForm);
  document.getElementById("nx-switcher-overlay").addEventListener("click", (e) => {
    if (e.target.id === "nx-switcher-overlay") closeOverlay();
  });
}

function openNewWorkspaceForm() {
  const root = document.getElementById("nx-overlay-root");
  root.innerHTML = `
    <div class="nx-switcher-overlay">
      <div class="nx-card nx-switcher" style="max-width:480px">
        <h3>New workspace</h3>
        <div style="display:flex;flex-direction:column;gap:10px">
          <input id="ws-name" class="nx-card" style="padding:10px 12px;border:1px solid var(--nx-card-border);background:transparent;color:inherit" placeholder="Name (e.g. Client work)">
          <input id="ws-id" class="nx-card" style="padding:10px 12px;border:1px solid var(--nx-card-border);background:transparent;color:inherit" placeholder="workspace-id (kebab-case)">
          <select id="ws-tone" class="nx-card" style="padding:10px 12px;border:1px solid var(--nx-card-border);background:transparent;color:inherit">
            <option value="indigo">indigo</option>
            <option value="magenta">magenta</option>
            <option value="sage">sage</option>
            <option value="plum">plum</option>
            <option value="amber">amber</option>
          </select>
          <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:8px">
            <button class="nx-pill" id="ws-cancel">Cancel</button>
            <button class="nx-pill" id="ws-create" style="background:rgba(168,180,255,0.18);border:1px solid rgba(168,180,255,0.34)">Create</button>
          </div>
        </div>
      </div>
    </div>`;
  document.getElementById("ws-cancel").addEventListener("click", closeOverlay);
  document.getElementById("ws-create").addEventListener("click", async () => {
    const name = document.getElementById("ws-name").value.trim();
    const id = document.getElementById("ws-id").value.trim();
    const tone = document.getElementById("ws-tone").value;
    if (!name || !id) return;
    const r = await fetch("/api/workspaces", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ workspace_id: id, name, tone }),
    });
    if (r.ok) {
      await loadWorkspaces();
      renderSwitcher();
    } else {
      const err = await r.json();
      alert(err.detail || "failed");
    }
  });
}

function closeOverlay() {
  document.getElementById("nx-overlay-root").innerHTML = "";
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

// ── Conversation surface ─────────────────────────────────────────────────
async function renderConversation(workspaceId) {
  const v = document.getElementById("nx-view");
  // Fetch workspace details
  let ws = state.workspaces.find(w => w.workspace_id === workspaceId);
  if (!ws) {
    const r = await fetch(`/api/workspaces/${encodeURIComponent(workspaceId)}`);
    if (r.ok) ws = await r.json();
  }
  if (!ws) {
    v.innerHTML = `<div class="nx-empty nx-dim">workspace not found: ${workspaceId}</div>`;
    return;
  }
  v.innerHTML = `
    <div class="nx-conv-grid">
      <aside class="nx-conv-left">
        <div class="nx-eyebrow" style="margin-bottom:10px">Workspaces</div>
        <div id="nx-conv-ws-list"></div>
        <div class="nx-eyebrow" style="margin:24px 0 10px">Roster</div>
        <div id="nx-conv-roster"></div>
      </aside>
      <section class="nx-conv-center">
        <header class="nx-conv-header">
          <div class="nx-display" style="font-size:24px">${escapeHtml(ws.name)}</div>
          <div class="nx-dim" style="font-size:12.5px;margin-top:4px">${ws.routing_pins ? ws.routing_pins.length : (ws.pins ? ws.pins.length : 0)} pins · ${ws.resident_agents.length} agents resident</div>
        </header>
        <div id="nx-conv-thread" class="nx-conv-thread"></div>
        <form id="nx-conv-input" class="nx-conv-input">
          <span class="nx-conv-kernel">${KERNEL_MARK(14)}</span>
          <input id="nx-conv-text" placeholder="Ask anything, or @ to call a specific agent…">
          <span class="nx-mono nx-softer">⌘K</span>
        </form>
      </section>
      <aside class="nx-conv-right">
        <div class="nx-eyebrow" style="margin-bottom:10px">Ambient</div>
        <div class="nx-card" id="nx-conv-mood" style="padding:14px;margin-bottom:12px"></div>
        <div class="nx-eyebrow" style="margin-bottom:10px">Recent</div>
        <div id="nx-conv-recent" style="font-size:12px;line-height:1.6"></div>
      </aside>
    </div>`;

  // Workspaces mini-list (left)
  document.getElementById("nx-conv-ws-list").innerHTML = state.workspaces.map(w => `
    <div class="nx-conv-ws ${w.workspace_id === workspaceId ? "active" : ""}"
         data-id="${w.workspace_id}">${escapeHtml(w.name)}</div>
  `).join("");
  document.querySelectorAll(".nx-conv-ws").forEach(el => {
    el.addEventListener("click", () => {
      location.hash = `#/conversation/${el.dataset.id}`;
    });
  });

  // Roster (left)
  const roster = ws.resident_agents.map(slug => `
    <div class="nx-conv-roster-row">
      ${agentDisc(slug, { size: 22 })}
      <span style="margin-left:8px">${slug}</span>
    </div>
  `).join("");
  document.getElementById("nx-conv-roster").innerHTML = roster || `<span class="nx-softer">no agents resident</span>`;

  // Mood card (right)
  await refreshMoodCard();

  // Recent chronicle (right)
  await refreshRecent();

  // Input
  document.getElementById("nx-conv-input").addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("nx-conv-text");
    const message = input.value.trim();
    if (!message) return;
    appendMessage("you", message);
    input.value = "";
    try {
      const r = await fetch("/api/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message }),
      });
      if (r.ok) {
        const body = await r.json();
        appendMessage(body.module || "nexus", body.response, body);
        await refreshRecent();
      } else {
        appendMessage("nexus", `(error ${r.status})`);
      }
    } catch (err) {
      appendMessage("nexus", `(error: ${err.message})`);
    }
  });
}

function appendMessage(speaker, text, meta = null) {
  const thread = document.getElementById("nx-conv-thread");
  if (!thread) return;
  if (speaker === "you") {
    thread.insertAdjacentHTML("beforeend", `
      <div class="nx-conv-turn nx-conv-user">
        <div class="nx-eyebrow">You</div>
        <div>${escapeHtml(text)}</div>
      </div>`);
  } else {
    const trust = meta && meta.trust ? `· ${(meta.trust).toFixed(2)} trust` : "";
    const score = meta && meta.score ? `· ${(meta.score).toFixed(2)} match` : "";
    thread.insertAdjacentHTML("beforeend", `
      <div class="nx-conv-turn nx-conv-agent">
        <div class="nx-card" style="padding:14px 16px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
            ${agentDisc(speaker, { size: 28 })}
            <div style="font-weight:500">${escapeHtml(speaker)}</div>
            <div class="nx-mono nx-softer" style="font-size:10.5px">picked by cortex ${score} ${trust}</div>
          </div>
          <div style="font-size:13.5px;line-height:1.6">${escapeHtml(text)}</div>
        </div>
      </div>`);
  }
  thread.scrollTop = thread.scrollHeight;
}

async function refreshMoodCard() {
  const el = document.getElementById("nx-conv-mood");
  if (!el) return;
  try {
    const r = await fetch("/api/mood/current");
    if (r.ok) {
      const m = await r.json();
      el.innerHTML = `
        <div class="nx-eyebrow" style="margin-bottom:4px">Workspace mood</div>
        <div class="nx-display" style="font-size:18px">${m.mood.replace(/_/g, " ")}</div>
        <div class="nx-dim" style="font-size:11.5px;margin-top:6px">${escapeHtml(m.reason || "")}</div>`;
    }
  } catch {}
}

async function refreshRecent() {
  const el = document.getElementById("nx-conv-recent");
  if (!el) return;
  try {
    const r = await fetch("/api/chronicle/recent?source=cortex&action=route&limit=5");
    if (r.ok) {
      const body = await r.json();
      const rows = (body.events || []).slice(0, 5).map(ev => {
        const target = (ev.payload || {}).target || "—";
        const ts = (ev.timestamp || "").slice(11, 16);
        return `<div style="display:flex;gap:8px"><span class="nx-softer nx-mono" style="width:48px;flex:none">${ts}</span><span>routed to <strong>${escapeHtml(target)}</strong></span></div>`;
      }).join("");
      el.innerHTML = rows || `<span class="nx-softer">no recent routes</span>`;
    }
  } catch {}
}

// ── Spatial catalog grid ─────────────────────────────────────────────────

async function renderSpatial() {
  const v = document.getElementById("nx-view");
  v.innerHTML = `<div class="nx-empty nx-dim">Loading agents…</div>`;
  let body;
  try {
    const r = await fetch("/api/spatial/agents");
    body = await r.json();
  } catch {
    v.innerHTML = `<div class="nx-empty nx-dim">Failed to load agents.</div>`;
    return;
  }
  const agents = body.agents || [];
  v.innerHTML = `
    <header class="nx-spatial-header">
      <div>
        <div class="nx-eyebrow" style="margin-bottom:6px">Catalog</div>
        <div class="nx-display" style="font-size:30px">Agents</div>
        <div class="nx-dim" style="font-size:13px;margin-top:4px">${agents.length} known</div>
      </div>
    </header>
    <div class="nx-spatial" id="nx-spatial-grid">
      ${agents.map(a => renderSpatialCard(a)).join("") || `<div class="nx-empty nx-dim">no agents registered yet</div>`}
    </div>`;
}

function renderSpatialCard(a) {
  const trust = a.trust != null ? a.trust.toFixed(2) : "—";
  const tier = a.tier || "OBSERVER";
  const dotClass = tier === "OBSERVER" ? "sleeping" : "";
  return `
    <div class="nx-spatial-card" data-slug="${a.slug}">
      ${agentDisc(a.slug, { size: 48, trust: a.trust })}
      <div class="name">${escapeHtml(a.name)} ${a.system ? `<span class="badge-system">system</span>` : ""}</div>
      <div class="tagline">${escapeHtml(a.tagline || "")}</div>
      <div class="status">
        <span class="status-dot ${dotClass}"></span>
        ${tier.toLowerCase()} · ${trust}
      </div>
    </div>`;
}

// ── Settings surface ─────────────────────────────────────────────────────

async function renderSettings() {
  const v = document.getElementById("nx-view");
  v.innerHTML = `
    <div class="nx-settings-shell">
      <nav class="nx-settings-tabs" id="nx-settings-tabs">
        <button data-tab="general" class="active">General</button>
        <button data-tab="workspaces">Workspaces</button>
        <button data-tab="agents">Agents</button>
        <button data-tab="security">Security</button>
        <button data-tab="providers">Providers</button>
        <button data-tab="about">About</button>
      </nav>
      <section class="nx-settings-panel nx-card" id="nx-settings-panel"></section>
    </div>`;
  selectSettingsTab("general");
  document.querySelectorAll("#nx-settings-tabs button").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("#nx-settings-tabs button").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      selectSettingsTab(btn.dataset.tab);
    });
  });
}

function selectSettingsTab(tab) {
  const panel = document.getElementById("nx-settings-panel");
  if (!panel) return;
  if (tab === "general") {
    panel.innerHTML = `
      <h3>General</h3>
      <div class="nx-dim">Theme, mood preferences, accessibility toggles — v2.</div>
      <div style="margin-top:14px">
        <label style="display:flex;gap:10px;align-items:center;font-size:13px">
          <input type="checkbox" id="nx-reduce-motion-toggle">
          Reduce motion (also respects OS setting)
        </label>
      </div>`;
  } else if (tab === "agents") {
    panel.innerHTML = `
      <h3>Agents</h3>
      <button class="nx-pill" id="nx-install-from-file">Install from manifest…</button>
      <div id="nx-installed-list" style="margin-top:18px"></div>`;
    document.getElementById("nx-install-from-file").addEventListener("click", openInstallReview);
    fetch("/api/spatial/agents").then(r => r.json()).then(b => {
      const installed = b.agents.filter(a => !a.system);
      document.getElementById("nx-installed-list").innerHTML = installed.length
        ? installed.map(a => `<div style="padding:8px 0;border-bottom:1px solid var(--nx-hairline)">${escapeHtml(a.name)} <span class="nx-dim">v${a.version}</span></div>`).join("")
        : `<div class="nx-dim">No installed agents yet.</div>`;
    });
  } else if (tab === "security") {
    panel.innerHTML = `<h3>Security</h3><div class="nx-dim">Permission grants and trust history — v2.</div>`;
  } else if (tab === "workspaces") {
    panel.innerHTML = `<h3>Workspaces</h3><div class="nx-dim">Use ⌘K to manage workspaces.</div>`;
  } else if (tab === "providers") {
    panel.innerHTML = `<h3>Providers</h3><div class="nx-dim">LLM provider configuration — v2.</div>`;
  } else if (tab === "about") {
    panel.innerHTML = `<h3>About</h3>
      <div class="nx-dim">NEXUS · the agent OS.</div>
      <div class="nx-mono nx-softer" style="margin-top:10px">Aurora · Phase 5</div>`;
  }
}

// ── Install review modal ──────────────────────────────────────────────────

function openInstallReview() {
  const root = document.getElementById("nx-overlay-root");
  root.innerHTML = `
    <div class="nx-install-overlay" id="nx-install-overlay">
      <div class="nx-card" style="max-width:560px;width:90%;padding:22px 24px">
        <h3 style="margin:0 0 12px">Install agent</h3>
        <p class="nx-dim" style="font-size:12px">Paste a manifest.json to review the install plan.</p>
        <textarea id="nx-install-text" class="nx-card" rows="10"
          style="width:100%;padding:10px;font-family:var(--nx-font-mono);font-size:11px;color:inherit;background:transparent;border:1px solid var(--nx-card-border)"></textarea>
        <div id="nx-install-plan" style="margin-top:14px"></div>
        <div style="margin-top:16px;display:flex;gap:8px;justify-content:flex-end">
          <button class="nx-pill" id="nx-install-cancel">Cancel</button>
          <button class="nx-pill" id="nx-install-review-btn">Review plan</button>
          <button class="nx-pill" id="nx-install-confirm" style="background:rgba(168,180,255,0.18);border-color:rgba(168,180,255,0.34);display:none">Install</button>
        </div>
      </div>
    </div>`;
  let lastManifest = null;
  document.getElementById("nx-install-cancel").addEventListener("click", () => { root.innerHTML = ""; });
  document.getElementById("nx-install-review-btn").addEventListener("click", async () => {
    try {
      lastManifest = JSON.parse(document.getElementById("nx-install-text").value);
    } catch (err) {
      document.getElementById("nx-install-plan").innerHTML = `<div style="color:var(--nx-privileged)">Invalid JSON: ${escapeHtml(err.message)}</div>`;
      return;
    }
    const r = await fetch("/api/agents/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manifest: lastManifest, confirm: false }),
    });
    if (!r.ok) {
      const err = await r.json();
      document.getElementById("nx-install-plan").innerHTML = `<div style="color:var(--nx-privileged)">${escapeHtml(JSON.stringify(err))}</div>`;
      return;
    }
    const body = await r.json();
    document.getElementById("nx-install-plan").innerHTML = renderInstallPlan(body.plan);
    document.getElementById("nx-install-confirm").style.display = "";
  });
  document.getElementById("nx-install-confirm").addEventListener("click", async () => {
    if (!lastManifest) return;
    const r = await fetch("/api/agents/install", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ manifest: lastManifest, confirm: true }),
    });
    if (r.ok) {
      root.innerHTML = `<div class="nx-install-overlay"><div class="nx-card" style="padding:20px 24px">Installed.</div></div>`;
      setTimeout(() => { root.innerHTML = ""; }, 1200);
    }
  });
}

function renderInstallPlan(plan) {
  const accent = { Routine: "var(--nx-routine)", Notable: "var(--nx-notable)", Sensitive: "var(--nx-sensitive)", Privileged: "var(--nx-privileged)" };
  return `
    <div style="font-size:13px;line-height:1.6">
      <div><strong>${escapeHtml(plan.name)} v${plan.version}</strong> by ${escapeHtml(plan.publisher)} · ${escapeHtml(plan.license)}</div>
      <div class="nx-dim" style="margin-top:4px">${escapeHtml(plan.tagline || "")}</div>
      <div style="margin-top:12px">
        ${plan.groups.filter(g => g.capabilities.length).map(g => `
          <div style="margin-top:8px">
            <span style="color:${accent[g.permission_class]||"#fff"};font-family:var(--nx-font-mono);font-size:11px">${g.permission_class}</span>
            <span class="nx-dim" style="font-family:var(--nx-font-mono);font-size:11.5px">${g.capabilities.join(", ")}</span>
          </div>`).join("")}
      </div>
    </div>`;
}

// ── First-use prompt polling ──────────────────────────────────────────────
const _shownTickets = new Set();
async function pollPermissions() {
  try {
    const r = await fetch("/api/permissions/pending");
    if (!r.ok) return;
    const body = await r.json();
    const pending = body.pending || [];
    if (pending.length === 0) {
      _shownTickets.clear();
      return;
    }
    const ticket = pending[0];
    if (_shownTickets.has(ticket.id)) return;
    _shownTickets.add(ticket.id);
    renderPermissionPrompt(ticket);
  } catch {}
}
setInterval(pollPermissions, 1500);

function renderPermissionPrompt(t) {
  const root = document.getElementById("nx-overlay-root");
  // Don't replace install overlay if visible
  if (document.getElementById("nx-install-overlay")) return;
  const ws = t.workspace_id || "—";
  root.insertAdjacentHTML("beforeend", `
    <div class="nx-prompt-overlay" id="nx-prompt-${t.id}">
      <div class="nx-prompt-card nx-card">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
          ${agentDisc(t.agent_slug, { size: 28 })}
          <div>
            <div style="font-size:13px;font-weight:500">${escapeHtml(t.agent_slug)} wants <span class="nx-mono" style="font-size:12px">${escapeHtml(t.capability)}</span></div>
            <div class="nx-dim" style="font-size:11px;margin-top:2px">workspace · ${escapeHtml(ws)}</div>
          </div>
          <span class="nx-pc nx-pc-${t.permission_class.toLowerCase()}" style="margin-left:auto">${t.permission_class}</span>
        </div>
        <div class="nx-dim" style="font-size:12px;margin-bottom:12px">${escapeHtml(t.preview || "")}</div>
        <div style="display:flex;flex-direction:column;gap:6px">
          <button class="nx-pill" data-decision="allow_once">Allow once</button>
          <button class="nx-pill" data-decision="allow_always_in_workspace">Always in <strong>${escapeHtml(ws)}</strong></button>
          <button class="nx-pill" data-decision="allow_always_everywhere">Always for ${escapeHtml(t.agent_slug)}, everywhere</button>
          <button class="nx-pill" data-decision="deny" style="background:rgba(248,100,120,0.12);border-color:rgba(248,100,120,0.34);color:#ffd0d4">Don't allow</button>
        </div>
      </div>
    </div>`);
  const el = document.getElementById(`nx-prompt-${t.id}`);
  el.querySelectorAll("button[data-decision]").forEach(btn => {
    btn.addEventListener("click", async () => {
      await fetch("/api/permissions/decide", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket_id: t.id, decision: btn.dataset.decision }),
      });
      el.remove();
    });
  });
}

// ── Router ───────────────────────────────────────────────────────────────
async function route(hash) {
  await loadWorkspaces();
  const v = document.getElementById("nx-view");
  if (!hash || hash === "#" || hash === "#/" || hash === "#/workspaces") {
    renderSwitcher();
    return;
  }
  if (hash === "#/spatial") {
    renderSpatial();
    return;
  }
  if (hash === "#/settings") {
    renderSettings();
    return;
  }
  if (hash.startsWith("#/conversation/")) {
    const ws = hash.slice("#/conversation/".length);
    renderConversation(ws);
    return;
  }
  v.innerHTML = `<div class="nx-empty nx-dim">surfaces in progress: ${escapeHtml(hash)}</div>`;
}
window.addEventListener("hashchange", () => route(location.hash));
route(location.hash);

// ── Cockpit overlay ──────────────────────────────────────────────────────

/**
 * toggleCockpit — open or close the Cockpit observability overlay (Cmd-`).
 * Six panels: Pulse waveform · Residents · Trust gradient · Last route ·
 * Chronicle tail · Network / Engram stats.
 */
async function toggleCockpit() {
  const root = document.getElementById("nx-overlay-root");
  // If already open, close it.
  if (root.querySelector(".nx-cockpit-overlay")) {
    closeOverlay();
    return;
  }

  // Render loading shell immediately.
  root.innerHTML = `
    <div class="nx-cockpit-overlay" id="nx-cockpit-overlay">
      <div class="nx-cockpit">
        <div class="nx-cockpit-scan"></div>
        <div class="nx-cockpit-header">
          <span class="nx-cockpit-title">COCKPIT</span>
          <button class="nx-cockpit-close" id="nx-cockpit-close">ESC</button>
        </div>
        <div class="nx-cockpit-grid" id="nx-cockpit-grid">
          <div class="nx-cockpit-panel span2 row2" id="cp-pulse">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Pulse waveform</span>
              <span class="nx-cockpit-panel-badge">60s</span>
            </div>
            <svg width="100%" height="80" id="cp-pulse-svg" viewBox="0 0 240 80" preserveAspectRatio="none"></svg>
          </div>
          <div class="nx-cockpit-panel" id="cp-residents">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Residents</span>
            </div>
            <div id="cp-residents-body" class="nx-dim" style="font-size:11px">loading…</div>
          </div>
          <div class="nx-cockpit-panel" id="cp-trust">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Trust gradient</span>
            </div>
            <div id="cp-trust-body">loading…</div>
          </div>
          <div class="nx-cockpit-panel" id="cp-last-route">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Last route</span>
            </div>
            <div id="cp-last-route-body" class="nx-dim">—</div>
          </div>
          <div class="nx-cockpit-panel span2" id="cp-chronicle">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Chronicle tail</span>
            </div>
            <div id="cp-chronicle-body" class="nx-dim">loading…</div>
          </div>
          <div class="nx-cockpit-panel" id="cp-network">
            <div class="nx-cockpit-panel-header">
              <span class="nx-cockpit-panel-label">Network · Engram</span>
            </div>
            <div id="cp-network-body" class="nx-dim">loading…</div>
          </div>
        </div>
      </div>
    </div>`;

  document.getElementById("nx-cockpit-close").addEventListener("click", closeOverlay);
  document.getElementById("nx-cockpit-overlay").addEventListener("click", (e) => {
    if (e.target.id === "nx-cockpit-overlay") closeOverlay();
  });

  // Fetch both in parallel.
  const [snapRes, pulseRes] = await Promise.all([
    fetch("/api/cockpit/snapshot").catch(() => null),
    fetch("/api/cockpit/pulse-rate").catch(() => null),
  ]);

  const snap = snapRes && snapRes.ok ? await snapRes.json() : null;
  const pulseData = pulseRes && pulseRes.ok ? await pulseRes.json() : null;

  _renderPulse(pulseData);
  _renderResidents(snap);
  _renderTrust(snap);
  _renderLastRoute(snap);
  _renderChronicle(snap);
  _renderNetwork(snap);
}

function _renderPulse(data) {
  const svg = document.getElementById("cp-pulse-svg");
  if (!svg || !data || !data.points || data.points.length === 0) return;
  const pts = data.points;
  const n = pts.length;
  const W = 240, H = 80;
  const maxChron = Math.max(1, ...pts.map(p => p.chronicle));
  const maxCortex = Math.max(1, ...pts.map(p => p.cortex_route));
  const maxAegis  = Math.max(1, ...pts.map(p => p.aegis_check));

  function toPath(vals, maxVal) {
    const step = W / (n - 1 || 1);
    return vals.map((v, i) => {
      const x = i * step;
      const y = H - 8 - (v / maxVal) * (H - 16);
      return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  }

  svg.innerHTML = `
    <path class="nx-cockpit-trace cyan"   d="${toPath(pts.map(p => p.chronicle),    maxChron)}"/>
    <path class="nx-cockpit-trace violet" d="${toPath(pts.map(p => p.cortex_route), maxCortex)}"/>
    <path class="nx-cockpit-trace amber"  d="${toPath(pts.map(p => p.aegis_check),  maxAegis)}"/>`;
}

function _renderResidents(snap) {
  const el = document.getElementById("cp-residents-body");
  if (!el) return;
  const modules = snap && snap.residents ? snap.residents : [];
  if (modules.length === 0) {
    el.textContent = "(no data)";
    return;
  }
  el.innerHTML = modules.map(m =>
    `<div style="padding:2px 0;opacity:0.8">${escapeHtml(String(m))}</div>`
  ).join("");
}

function _renderTrust(snap) {
  const el = document.getElementById("cp-trust-body");
  if (!el) return;
  const policies = snap && snap.trust_gradient ? snap.trust_gradient : [];
  if (policies.length === 0) {
    el.innerHTML = `<span class="nx-dim">(no data)</span>`;
    return;
  }
  const top = policies.slice(0, 6);
  el.innerHTML = top.map(p => {
    const trust = typeof p.trust_score === "number" ? p.trust_score : (p.trust || 0);
    const pct = Math.round(trust * 100);
    return `<div class="nx-cockpit-bar-row">
      <span class="nx-cockpit-bar-label" title="${escapeHtml(p.module)}">${escapeHtml(p.module)}</span>
      <div class="nx-cockpit-bar-track">
        <div class="nx-cockpit-bar-fill" style="width:${pct}%"></div>
      </div>
      <span style="opacity:0.5;font-size:10px;width:28px;text-align:right">${pct}</span>
    </div>`;
  }).join("");
}

function _renderLastRoute(snap) {
  const el = document.getElementById("cp-last-route-body");
  if (!el) return;
  const route = snap && snap.last_route;
  if (!route) {
    el.textContent = "(no recent route)";
    return;
  }
  const target = (route.payload || {}).target || "—";
  const ts = (route.timestamp || "").slice(11, 19);
  el.innerHTML = `
    <div style="opacity:0.5;font-size:10px;margin-bottom:4px">${escapeHtml(ts)}</div>
    <div style="color:#88d4ff">${escapeHtml(target)}</div>
    <div style="opacity:0.5;font-size:10px;margin-top:4px">${escapeHtml(route.source || "")} · ${escapeHtml(route.action || "")}</div>`;
}

function _renderChronicle(snap) {
  const el = document.getElementById("cp-chronicle-body");
  if (!el) return;
  const tail = snap && snap.chronicle_tail ? snap.chronicle_tail : [];
  if (tail.length === 0) {
    el.textContent = "(no data)";
    return;
  }
  el.innerHTML = tail.slice(0, 8).map(ev => {
    const ts = (ev.timestamp || "").slice(11, 19);
    return `<div class="nx-cockpit-tail-row">
      <span style="opacity:0.4;margin-right:8px">${escapeHtml(ts)}</span>
      <span style="color:#c8a8ff">${escapeHtml(ev.source || "")}</span>
      <span style="opacity:0.5;margin:0 4px">·</span>
      <span>${escapeHtml(ev.action || "")}</span>
    </div>`;
  }).join("");
}

function _renderNetwork(snap) {
  const el = document.getElementById("cp-network-body");
  if (!el) return;
  const stats = snap && snap.engram_stats ? snap.engram_stats : {};
  const network = snap && snap.network ? snap.network : [];
  el.innerHTML = `
    <div class="nx-cockpit-stat-row">
      <span>network gates</span>
      <span class="nx-cockpit-stat-val">${network.length > 0 ? network.length : "—"}</span>
    </div>
    <div class="nx-cockpit-stat-row">
      <span>engram partitions</span>
      <span class="nx-cockpit-stat-val">${Object.keys(stats).length > 0 ? Object.keys(stats).length : "—"}</span>
    </div>`;
}

// ── Header buttons ───────────────────────────────────────────────────────
document.getElementById("nx-workspaces-btn").addEventListener("click", () => {
  loadWorkspaces().then(renderSwitcher);
});
document.getElementById("nx-cockpit-btn").addEventListener("click", toggleCockpit);
document.getElementById("nx-spatial-btn").addEventListener("click", () => {
  location.hash = "#/spatial";
});
document.getElementById("nx-settings-btn").addEventListener("click", () => {
  location.hash = "#/settings";
});

// ── Keybinds ─────────────────────────────────────────────────────────────
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); loadWorkspaces().then(renderSwitcher); }
  if ((e.metaKey || e.ctrlKey) && e.key === "`") { e.preventDefault(); document.getElementById("nx-cockpit-btn").click(); }
  if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); document.getElementById("nx-settings-btn").click(); }
  if (e.key === "Escape") closeOverlay();
});

// ── Trust event temperature overlays ────────────────────────────────────
let _lastTrustEventId = null;

async function pollTrustEvents() {
  try {
    const r = await fetch("/api/chronicle/recent?source=aegis&action=trust_change&limit=1");
    if (!r.ok) return;
    const body = await r.json();
    const events = body.events || [];
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
setInterval(pollTrustEvents, 2000);

// ── Mood push (WS preferred, polling fallback) ──────────────────────────
function _applyMoodBody(body) {
  const cls = "nx-mood-" + body.mood.replace(/_/g, "-");
  const current = [...document.body.classList].find(c => c.startsWith("nx-mood-"));
  if (current && current !== cls) document.body.classList.remove(current);
  if (!document.body.classList.contains(cls)) document.body.classList.add(cls);
  document.body.dataset.mood = body.mood;
}

(function initMoodStream() {
  const wsProto = location.protocol === "https:" ? "wss:" : "ws:";
  let ws = null;
  let pollInterval = null;

  function startPolling() {
    if (pollInterval) return;
    pollInterval = setInterval(async () => {
      try {
        const r = await fetch("/api/mood/current");
        if (r.ok) _applyMoodBody(await r.json());
      } catch {}
    }, 2000);
    // Run immediately
    fetch("/api/mood/current").then(r => r.ok ? r.json() : null).then(b => b && _applyMoodBody(b)).catch(() => {});
  }

  function connectWs() {
    try {
      ws = new WebSocket(`${wsProto}//${location.host}/api/mood/ws`);
      ws.onmessage = (e) => { try { _applyMoodBody(JSON.parse(e.data)); } catch {} };
      ws.onerror = () => { ws = null; startPolling(); };
      ws.onclose = () => { ws = null; startPolling(); };
    } catch {
      startPolling();
    }
  }

  if (typeof WebSocket !== "undefined") {
    connectWs();
  } else {
    startPolling();
  }
})();
