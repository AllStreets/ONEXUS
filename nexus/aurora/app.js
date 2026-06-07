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

// ── Router ───────────────────────────────────────────────────────────────
async function route(hash) {
  await loadWorkspaces();
  const v = document.getElementById("nx-view");
  if (!hash || hash === "#" || hash === "#/" || hash === "#/workspaces") {
    renderSwitcher();
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
