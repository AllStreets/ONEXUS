/* NEXUS Aurora — the Kernel Scene (N1 "Sigil" live visualization)
 *
 * The headline watch experience: the kernel's cognition rendered as a living
 * constellation. Cortex routing travels as luminous beads from the core to the
 * module it picked; Aegis verdicts burst as coloured flares; trust changes warm
 * or cool each module's ring; Engram writes settle as sediment into memory
 * strata; Sigil anomalies sweep the whole surface in alert red.
 *
 * Canvas 2D, no build step, no third-party library — sovereign and local by
 * construction, like everything else in Aurora. Driven entirely by the same
 * `/api/events/ws` Pulse relay the cockpit already consumes.
 *
 * Public API (all no-ops until setModules() has run):
 *   const scene = new KernelScene(canvas, { compact: false });
 *   scene.setModules([{ name, colorA, colorB, trust, tier }]);
 *   scene.setMood("#a8b4ff");
 *   scene.route({ target, signals });
 *   scene.gate({ agent, verdict, permission_class, capability });
 *   scene.trust({ module, old_score, new_score });
 *   scene.memory({ tier, source });
 *   scene.detection(det);  scene.emergency(payload);
 *   scene.start();  scene.stop();  scene.destroy();
 */

const TAU = Math.PI * 2;
const GOLDEN = 2.399963229728653; // golden angle (rad)

// memory tiers, top→bottom, deepest tier sinks lowest (semantic/atlas = bedrock)
const STRATA = [
  { key: "working",  label: "WORKING",  tint: "#9affb6" },
  { key: "episodic", label: "EPISODIC", tint: "#a8b4ff" },
  { key: "semantic", label: "SEMANTIC", tint: "#c8a0ff" },
  { key: "atlas",    label: "ATLAS",    tint: "#7ee8b2" },
];

const VERDICT_COLOR = {
  allow:  "#9affb6",
  prompt: "#f8c460",
  deny:   "#f8643c",
};

// ── small helpers ───────────────────────────────────────────────────────────
function hash01(str) {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) { h ^= str.charCodeAt(i); h = Math.imul(h, 16777619); }
  return ((h >>> 0) % 100000) / 100000;
}
function hexToRgb(hex) {
  const h = (hex || "#888").replace("#", "");
  const n = h.length === 3
    ? h.split("").map((c) => parseInt(c + c, 16))
    : [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  return n.map((v) => (Number.isFinite(v) ? v : 136));
}
function rgba(hex, a) { const [r, g, b] = hexToRgb(hex); return `rgba(${r},${g},${b},${a})`; }
function mix(a, b, t) { const A = hexToRgb(a), B = hexToRgb(b); return `rgb(${Math.round(A[0]+(B[0]-A[0])*t)},${Math.round(A[1]+(B[1]-A[1])*t)},${Math.round(A[2]+(B[2]-A[2])*t)})`; }
function ease(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; }
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// cached soft-dot sprites (radial gradient) keyed by colour — additive glow
const _sprites = new Map();
function glowSprite(color) {
  if (_sprites.has(color)) return _sprites.get(color);
  const s = 64, c = document.createElement("canvas"); c.width = c.height = s;
  const g = c.getContext("2d");
  const grd = g.createRadialGradient(s / 2, s / 2, 0, s / 2, s / 2, s / 2);
  grd.addColorStop(0, rgba(color, 1)); grd.addColorStop(0.4, rgba(color, 0.55)); grd.addColorStop(1, rgba(color, 0));
  g.fillStyle = grd; g.fillRect(0, 0, s, s);
  _sprites.set(color, c); return c;
}

export class KernelScene {
  constructor(canvas, opts = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.compact = !!opts.compact;            // mini variant for the cockpit
    this.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.dpr = Math.min(window.devicePixelRatio || 1, 2);
    this.W = 0; this.H = 0;
    this.nodes = new Map();
    this.order = [];                          // node names in layout order
    this.beads = [];                          // routing pulses
    this.flares = [];                         // gate / trust bursts
    this.motes = [];                          // memory particles
    this.ripples = [];                        // radar / detection rings
    this.strata = STRATA.map((s) => ({ ...s, level: 0, flash: 0 }));
    this.accent = "#a8b4ff";
    this.veil = 0;                            // emergency veil intensity 0..1
    this.energy = 0;                          // recent kernel activity 0..1
    this.t = 0; this.last = 0; this.raf = null; this.running = false;
    this.onPick = opts.onPick || null;       // (moduleName) => void, on node click
    this._loop = this._loop.bind(this);
    this._onResize = () => this._resize();
    this._ro = new ResizeObserver(this._onResize);
    this._ro.observe(canvas.parentElement || canvas);
    // Pointer interaction — the modules are characters you can watch AND direct.
    if (this.onPick) {
      this._onClick = (e) => { const n = this._pickAt(e.offsetX, e.offsetY); if (n) this.onPick(n); };
      this._onMove = (e) => { this.canvas.style.cursor = this._pickAt(e.offsetX, e.offsetY) ? "pointer" : "default"; };
      canvas.addEventListener("click", this._onClick);
      canvas.addEventListener("mousemove", this._onMove);
    }
    this._resize();
  }

  // hit-test a screen point against the live node positions (logical px)
  _pickAt(mx, my) {
    for (const node of this.nodes.values()) {
      const hit = (node.r || 8) + 8 + node.activity * 6;
      const dx = mx - node.x, dy = my - node.y;
      if (dx * dx + dy * dy <= hit * hit) return node.name;
    }
    return null;
  }

  // ── layout ────────────────────────────────────────────────────────────────
  _resize() {
    const host = this.canvas.parentElement || this.canvas;
    const w = host.clientWidth || 800, h = host.clientHeight || 480;
    if (!w || !h) return;
    this.W = w; this.H = h;
    this.canvas.width = Math.round(w * this.dpr);
    this.canvas.height = Math.round(h * this.dpr);
    this.canvas.style.width = w + "px"; this.canvas.style.height = h + "px";
    this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    this._layout();
  }

  _layout() {
    const w = this.W, h = this.H;
    const strataH = this.compact ? 0 : Math.max(64, h * 0.18);
    // Non-compact (full Watch view) reserves a top band so the constellation
    // never rides up under the "Watch it think" title block.
    const topBand = this.compact ? 8 : 150;
    this.field = { top: topBand, bottom: h - strataH - (this.compact ? 8 : 14) };
    const cy = this.field.top + (this.field.bottom - this.field.top) * (this.compact ? 0.5 : 0.5);
    this.core = this.core || { pulse: 0 };
    this.core.x = w * 0.5; this.core.y = cy;
    const rx = w * (this.compact ? 0.36 : 0.34);
    const ry = (this.field.bottom - this.field.top) * (this.compact ? 0.4 : 0.42);
    const n = this.order.length || 1;
    this.order.forEach((name, i) => {
      const node = this.nodes.get(name); if (!node) return;
      // golden-angle spiral so the roster reads as a scattered constellation,
      // not a clock face; deterministic jitter keeps every kernel's sky stable.
      const ang = node.baseAngle;
      const rf = 0.62 + node.radiusFactor * 0.38;
      node.hx = this.core.x + Math.cos(ang) * rx * rf;
      node.hy = this.core.y + Math.sin(ang) * ry * rf;
    });
    // strata bands
    if (!this.compact) {
      this.strata.forEach((s, i) => {
        s.y = (h - strataH) + (i + 0.5) * (strataH / this.strata.length);
        s.h = strataH / this.strata.length;
      });
    }
  }

  setModules(mods) {
    const keep = new Set();
    const total = mods.length || 1;
    mods.forEach((m, i) => {
      keep.add(m.name);
      let node = this.nodes.get(m.name);
      if (!node) {
        const j = hash01(m.name);
        node = {
          name: m.name,
          baseAngle: i * GOLDEN + j * 0.6,
          radiusFactor: j,
          trust: clamp(m.trust ?? 0.5, 0, 1),
          targetTrust: clamp(m.trust ?? 0.5, 0, 1),
          activity: 0, label: 1, temp: null, tempT: 0,
          colorA: m.colorA || "#a8b4ff", colorB: m.colorB || "#4d5bcf",
          tier: m.tier || "",
          r: this.compact ? 5.5 : 8.5,
          hx: this.core ? this.core.x : 0, hy: this.core ? this.core.y : 0,
          x: this.core ? this.core.x : 0, y: this.core ? this.core.y : 0,
          seed: j,
        };
        this.nodes.set(m.name, node);
      } else {
        node.targetTrust = clamp(m.trust ?? node.trust, 0, 1);
        node.colorA = m.colorA || node.colorA; node.colorB = m.colorB || node.colorB;
        node.tier = m.tier || node.tier;
      }
    });
    for (const k of [...this.nodes.keys()]) if (!keep.has(k)) this.nodes.delete(k);
    this.order = mods.map((m) => m.name);
    this._layout();
  }

  setMood(accent) { if (accent) this.accent = accent; }

  _node(name) {
    if (!name) return null;
    const key = String(name).toLowerCase();
    return this.nodes.get(key) || this.nodes.get(name) || null;
  }

  // ── events → motion ─────────────────────────────────────────────────────────
  route({ target, signals } = {}) {
    const node = this._node(target);
    this.energy = Math.min(1, this.energy + 0.34);
    if (!node) return;
    node.activity = 1; node.label = 1;
    // a perpendicular-bowed bezier so beads arc rather than fire straight
    const dx = node.hx - this.core.x, dy = node.hy - this.core.y;
    const bow = (hash01(target + (this.beads.length)) - 0.5) * 0.5;
    const cx = this.core.x + dx * 0.5 - dy * bow;
    const cy = this.core.y + dy * 0.5 + dx * bow;
    this.beads.push({
      x0: this.core.x, y0: this.core.y, cx, cy, x1: node.hx, y1: node.hy,
      t: 0, dur: this.reduced ? 0.01 : 0.62 + hash01(target) * 0.25,
      color: node.colorA, trail: [], target,
    });
  }

  gate({ agent, verdict, permission_class, capability } = {}) {
    const v = String(verdict || "").toLowerCase();
    const color = VERDICT_COLOR[v] || "#a8b4ff";
    const node = this._node(agent) || this._node(permission_class);
    const x = node ? node.hx : this.core.x, y = node ? node.hy : this.core.y;
    if (node) node.activity = 1;
    this.flares.push({ x, y, color, t: 0, dur: this.reduced ? 0.01 : 0.8, r0: node ? node.r + 3 : 10, r1: node ? 34 : 46, sym: v });
    if (v === "deny") this.energy = Math.min(1, this.energy + 0.22);
  }

  trust({ module, old_score, new_score } = {}) {
    const node = this._node(module); if (!node) return;
    if (typeof new_score === "number") node.targetTrust = clamp(new_score, 0, 1);
    const rising = (new_score ?? 0) >= (old_score ?? new_score ?? 0);
    const collapse = typeof new_score === "number" && new_score < 0.5 && !rising;
    node.temp = collapse ? "#f8643c" : rising ? "#f8c460" : "#8cb8d4";
    node.tempT = this.reduced ? 0.01 : 1;
    node.activity = Math.max(node.activity, 0.7);
    this.flares.push({ x: node.hx, y: node.hy, color: node.temp, t: 0, dur: 0.7, r0: node.r + 2, r1: 26, sym: "" });
  }

  memory({ tier, source } = {}) {
    const key = (tier || "episodic").toLowerCase();
    const band = this.strata.find((s) => s.key === key) || this.strata[1];
    if (!band || this.compact) { if (band) band.flash = 1; return; }
    const x = this.core.x + (hash01((source || "") + this.motes.length) - 0.5) * this.W * 0.4;
    this.motes.push({ x0: this.core.x, y0: this.core.y, x, y0b: band.y, t: 0, dur: this.reduced ? 0.01 : 1.0 + hash01(source || "x") * 0.5, band, tint: band.tint });
    this.energy = Math.min(1, this.energy + 0.1);
  }

  detection(det = {}) {
    const node = this._node(det.module) || this._node("sigil");
    const x = node ? node.hx : this.core.x, y = node ? node.hy : this.core.y;
    this.ripples.push({ x, y, t: 0, dur: this.reduced ? 0.2 : 1.6, color: "#f8643c", max: Math.max(this.W, this.H) * 0.5 });
    this.energy = Math.min(1, this.energy + 0.4);
  }

  emergency() {
    this.veil = 1;
    this.detection({ module: "sigil" });
  }

  // ── loop ────────────────────────────────────────────────────────────────────
  start() { if (this.running) return; this.running = true; this.last = performance.now(); this.raf = requestAnimationFrame(this._loop); }
  stop() { this.running = false; if (this.raf) cancelAnimationFrame(this.raf); this.raf = null; }
  destroy() {
    this.stop();
    try { this._ro.disconnect(); } catch {}
    if (this._onClick) this.canvas.removeEventListener("click", this._onClick);
    if (this._onMove) this.canvas.removeEventListener("mousemove", this._onMove);
  }

  _loop(now) {
    if (!this.running) return;
    let dt = (now - this.last) / 1000; this.last = now;
    dt = clamp(dt, 0, 0.05);
    this.t += dt;
    this._update(dt);
    this._draw();
    this.raf = requestAnimationFrame(this._loop);
  }

  _update(dt) {
    this.energy = Math.max(0, this.energy - dt * 0.55);
    this.veil = Math.max(0, this.veil - dt * 0.45);
    this.core.pulse = (this.core.pulse + dt * (0.4 + this.energy)) % TAU;
    // nodes: parallax drift, trust easing, decays
    const drift = this.reduced ? 0 : 1;
    for (const node of this.nodes.values()) {
      const sway = Math.sin(this.t * 0.5 + node.seed * TAU) * (this.compact ? 1.5 : 3.2) * drift;
      const sway2 = Math.cos(this.t * 0.37 + node.seed * TAU) * (this.compact ? 1.2 : 2.6) * drift;
      node.x = node.hx + sway; node.y = node.hy + sway2;
      node.trust += (node.targetTrust - node.trust) * Math.min(1, dt * 4);
      node.activity = Math.max(0, node.activity - dt * 1.3);
      node.tempT = Math.max(0, node.tempT - dt * 1.4);
      node.label = Math.max(this.compact ? 0 : 0.32, node.label - dt * 0.5);
    }
    for (const s of this.strata) { s.flash = Math.max(0, s.flash - dt * 1.5); s.level = Math.max(0, s.level - dt * 0.04); }
    this._advance(this.beads, dt, (b) => {
      const node = this._node(b.target);
      if (node) { node.activity = 1; node.label = 1; }
    });
    this._advance(this.flares, dt);
    this._advance(this.ripples, dt);
    this._advance(this.motes, dt, (m) => { m.band.flash = 1; m.band.level = Math.min(1, m.band.level + 0.16); });
  }

  _advance(arr, dt, onDone) {
    for (let i = arr.length - 1; i >= 0; i--) {
      const p = arr[i]; p.t += dt / p.dur;
      if (p.trail) { p.trail.push(this._bezAt(p, Math.min(1, p.t))); if (p.trail.length > 14) p.trail.shift(); }
      if (p.t >= 1) { if (onDone) onDone(p); arr.splice(i, 1); }
    }
  }
  _bezAt(b, t) {
    const u = 1 - t;
    return { x: u * u * b.x0 + 2 * u * t * b.cx + t * t * b.x1, y: u * u * b.y0 + 2 * u * t * b.cy + t * t * b.y1 };
  }

  // ── draw ────────────────────────────────────────────────────────────────────
  _draw() {
    const c = this.ctx, w = this.W, h = this.H;
    c.clearRect(0, 0, w, h);
    // atmosphere — mood-tinted radial wash behind everything
    const bg = c.createRadialGradient(this.core.x, this.core.y, 0, this.core.x, this.core.y, Math.max(w, h) * 0.7);
    bg.addColorStop(0, rgba(this.accent, 0.10 + this.energy * 0.06));
    bg.addColorStop(0.5, rgba(this.accent, 0.03));
    bg.addColorStop(1, "rgba(0,0,0,0)");
    c.fillStyle = bg; c.fillRect(0, 0, w, h);

    if (!this.compact) this._drawStrata();
    this._drawConstellationLines();
    this._drawMotes();
    this._drawBeads();
    this._drawNodes();
    this._drawCore();
    this._drawFlares();
    this._drawRipples();
    if (this.veil > 0.001) this._drawVeil();
  }

  _drawConstellationLines() {
    const c = this.ctx;
    c.lineWidth = 1;
    for (const node of this.nodes.values()) {
      const a = 0.05 + node.activity * 0.35;
      const grd = c.createLinearGradient(this.core.x, this.core.y, node.x, node.y);
      grd.addColorStop(0, rgba(this.accent, a * 0.5));
      grd.addColorStop(1, rgba(node.colorA, a));
      c.strokeStyle = grd;
      c.beginPath(); c.moveTo(this.core.x, this.core.y); c.lineTo(node.x, node.y); c.stroke();
    }
  }

  _drawBeads() {
    const c = this.ctx; c.globalCompositeOperation = "lighter";
    for (const b of this.beads) {
      const p = this._bezAt(b, ease(Math.min(1, b.t)));
      // trail
      for (let i = 0; i < b.trail.length; i++) {
        const pt = b.trail[i], a = (i / b.trail.length) * 0.5;
        const r = 2 + i * 0.5;
        c.globalAlpha = a;
        c.drawImage(glowSprite(b.color), pt.x - r, pt.y - r, r * 2, r * 2);
      }
      c.globalAlpha = 1;
      const r = this.compact ? 7 : 11;
      c.drawImage(glowSprite("#fbf7ff"), p.x - r, p.y - r, r * 2, r * 2);
      const r2 = this.compact ? 4 : 6;
      c.drawImage(glowSprite(b.color), p.x - r2, p.y - r2, r2 * 2, r2 * 2);
    }
    c.globalCompositeOperation = "source-over"; c.globalAlpha = 1;
  }

  _drawNodes() {
    const c = this.ctx;
    for (const node of this.nodes.values()) {
      const baseR = node.r * (1 + node.activity * 0.45 + Math.sin(this.t * 1.2 + node.seed * TAU) * 0.05);
      // glow halo
      c.globalCompositeOperation = "lighter";
      const halo = baseR * (3 + node.activity * 2);
      c.globalAlpha = 0.35 + node.activity * 0.5;
      c.drawImage(glowSprite(node.colorA), node.x - halo, node.y - halo, halo * 2, halo * 2);
      c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
      // body
      const grd = c.createRadialGradient(node.x - baseR * 0.3, node.y - baseR * 0.3, 0, node.x, node.y, baseR);
      grd.addColorStop(0, node.colorA); grd.addColorStop(1, node.colorB);
      c.beginPath(); c.arc(node.x, node.y, baseR, 0, TAU); c.fillStyle = grd; c.fill();
      // trust ring
      const ringR = baseR + 4;
      c.beginPath(); c.arc(node.x, node.y, ringR, 0, TAU);
      c.strokeStyle = "rgba(255,255,255,0.10)"; c.lineWidth = 2; c.stroke();
      c.beginPath(); c.arc(node.x, node.y, ringR, -Math.PI / 2, -Math.PI / 2 + TAU * node.trust);
      c.strokeStyle = node.tempT > 0 ? node.temp : "rgba(255,255,255,0.6)"; c.lineWidth = 2; c.lineCap = "round"; c.stroke();
      // label
      if (node.label > 0.01 && !this.compact) {
        c.globalAlpha = node.label * 0.9;
        c.fillStyle = "#e8e4f0"; c.font = "500 10px 'IBM Plex Mono', ui-monospace, monospace";
        c.textAlign = "center";
        c.fillText(node.name, node.x, node.y + ringR + 13);
        c.globalAlpha = 1;
      }
    }
    c.lineCap = "butt";
  }

  _drawCore() {
    const c = this.ctx, x = this.core.x, y = this.core.y;
    const beat = 1 + Math.sin(this.core.pulse) * 0.06 + this.energy * 0.18;
    const R = (this.compact ? 13 : 22) * beat;
    c.globalCompositeOperation = "lighter";
    const halo = R * 3.4; c.globalAlpha = 0.5 + this.energy * 0.4;
    c.drawImage(glowSprite("#c9b8ff"), x - halo, y - halo, halo * 2, halo * 2);
    c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
    const grd = c.createRadialGradient(x - R * 0.35, y - R * 0.4, 0, x, y, R);
    grd.addColorStop(0, "#fbf7ff"); grd.addColorStop(0.4, "#c9b8ff"); grd.addColorStop(1, "#5a4ac4");
    c.beginPath(); c.arc(x, y, R, 0, TAU); c.fillStyle = grd; c.fill();
    c.beginPath(); c.arc(x, y, R * 0.32, 0, TAU); c.fillStyle = "rgba(255,255,255,0.85)"; c.fill();
  }

  _drawFlares() {
    const c = this.ctx; c.globalCompositeOperation = "lighter";
    for (const f of this.flares) {
      const t = ease(Math.min(1, f.t)); const r = f.r0 + (f.r1 - f.r0) * t;
      c.globalAlpha = (1 - t) * 0.9; c.lineWidth = 2;
      c.strokeStyle = f.color; c.beginPath(); c.arc(f.x, f.y, r, 0, TAU); c.stroke();
    }
    c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
  }

  _drawRipples() {
    const c = this.ctx; c.globalCompositeOperation = "lighter";
    for (const p of this.ripples) {
      const t = Math.min(1, p.t);
      for (let k = 0; k < 3; k++) {
        const tt = t - k * 0.12; if (tt < 0) continue;
        const r = p.max * ease(tt);
        c.globalAlpha = (1 - tt) * 0.5;
        c.strokeStyle = p.color; c.lineWidth = 1.5;
        c.beginPath(); c.arc(p.x, p.y, r, 0, TAU); c.stroke();
      }
    }
    c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
  }

  _drawMotes() {
    const c = this.ctx; c.globalCompositeOperation = "lighter";
    for (const m of this.motes) {
      const t = ease(Math.min(1, m.t));
      const x = m.x0 + (m.x - m.x0) * t;
      const y = m.y0 + (m.y0b - m.y0) * t + Math.sin(t * Math.PI) * -10;
      const r = 5 * (1 - t * 0.4);
      c.globalAlpha = 0.8 * (1 - t * 0.3);
      c.drawImage(glowSprite(m.tint), x - r, y - r, r * 2, r * 2);
    }
    c.globalAlpha = 1; c.globalCompositeOperation = "source-over";
  }

  _drawStrata() {
    const c = this.ctx, w = this.W;
    for (const s of this.strata) {
      // band base
      c.fillStyle = rgba(s.tint, 0.03 + s.level * 0.07);
      c.fillRect(0, s.y - s.h / 2, w, s.h);
      // sediment line — brightens as memories land
      const a = 0.14 + s.flash * 0.6 + s.level * 0.2;
      const grd = c.createLinearGradient(0, 0, w, 0);
      grd.addColorStop(0, rgba(s.tint, 0)); grd.addColorStop(0.5, rgba(s.tint, a)); grd.addColorStop(1, rgba(s.tint, 0));
      c.fillStyle = grd; c.fillRect(0, s.y + s.h / 2 - 1.5, w, 1.5);
      // label
      c.globalAlpha = 0.4 + s.flash * 0.4;
      c.fillStyle = s.tint; c.font = "500 8.5px 'IBM Plex Mono', ui-monospace, monospace";
      c.textAlign = "left"; c.fillText(s.label, 12, s.y + 3);
      c.textAlign = "right";
      c.fillStyle = "rgba(232,228,240,0.4)";
      c.fillText(Math.round(s.level * 100) + "%", w - 12, s.y + 3);
      c.globalAlpha = 1;
    }
  }

  _drawVeil() {
    const c = this.ctx, w = this.W, h = this.H;
    const grd = c.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.7);
    const a = this.veil * 0.5;
    grd.addColorStop(0, `rgba(248,100,60,0)`);
    grd.addColorStop(0.7, `rgba(248,100,60,${a * 0.3})`);
    grd.addColorStop(1, `rgba(248,100,60,${a})`);
    c.fillStyle = grd; c.fillRect(0, 0, w, h);
  }
}
