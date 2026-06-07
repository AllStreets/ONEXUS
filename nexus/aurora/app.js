import { KERNEL_MARK } from "/aurora/static/icons.js";

/* —— bootstrap —— */
document.getElementById("nx-kernel-mark").innerHTML = KERNEL_MARK(14);

/* —— router (Phase 5 placeholder; surfaces filled in later tasks) —— */
function route(hash) {
  const v = document.getElementById("nx-view");
  if (!hash || hash === "#" || hash === "#/") {
    v.innerHTML = `<div class="nx-empty"><div class="nx-display" style="font-size:22px">NEXUS Aurora</div>
                   <p class="nx-dim">surfaces will land in subsequent Phase 5 tasks.</p></div>`;
    return;
  }
  v.innerHTML = `<div class="nx-empty nx-dim">unknown route: ${hash}</div>`;
}
window.addEventListener("hashchange", () => route(location.hash));
route(location.hash);

/* —— keybindings (Phase 5 stubs; actual handlers added by later tasks) —— */
window.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "k") { e.preventDefault(); document.getElementById("nx-workspaces-btn").click(); }
  if ((e.metaKey || e.ctrlKey) && e.key === "`") { e.preventDefault(); document.getElementById("nx-cockpit-btn").click(); }
  if ((e.metaKey || e.ctrlKey) && e.key === ",") { e.preventDefault(); document.getElementById("nx-settings-btn").click(); }
});

/* polling for mood — keeps the body class in sync */
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
