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

// ── Router ───────────────────────────────────────────────────────────────
async function route(hash) {
  await loadWorkspaces();
  const v = document.getElementById("nx-view");
  if (!hash || hash === "#" || hash === "#/" || hash === "#/workspaces") {
    renderSwitcher();
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

// ── Header buttons ───────────────────────────────────────────────────────
document.getElementById("nx-workspaces-btn").addEventListener("click", () => {
  loadWorkspaces().then(renderSwitcher);
});

// ── Keybinds ─────────────────────────────────────────────────────────────
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); loadWorkspaces().then(renderSwitcher); }
  if ((e.metaKey || e.ctrlKey) && e.key === "`") { e.preventDefault(); document.getElementById("nx-cockpit-btn").click(); }
  if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); document.getElementById("nx-settings-btn").click(); }
  if (e.key === "Escape") closeOverlay();
});

// ── Mood polling (from T3) ───────────────────────────────────────────────
async function pollMood() {
  try {
    const r = await fetch("/api/mood/current");
    if (r.ok) {
      const body = await r.json();
      const cls = "nx-mood-" + body.mood.replace(/_/g, "-");
      const current = [...document.body.classList].find(c => c.startsWith("nx-mood-"));
      if (current && current !== cls) document.body.classList.remove(current);
      if (!document.body.classList.contains(cls)) document.body.classList.add(cls);
      document.body.dataset.mood = body.mood;
    }
  } catch {}
}
setInterval(pollMood, 2000);
pollMood();
