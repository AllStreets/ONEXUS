// ── NEXUS Dashboard Application ───────────────────────────────────────────
// Vanilla JS. No frameworks. No emojis.
// Trust scores are 0.0-1.0 floats. Tiers: OBSERVER/ADVISOR/MONITOR/EXECUTOR/AUTONOMOUS.

const API_BASE = window.location.origin;
const WS_BASE  = API_BASE.replace(/^http/, 'ws');

// ── Trust Utilities ──────────────────────────────────────────────────────

function trustColor(score) {
  if (score >= 1.0)  return 'var(--secondary)';
  if (score >= 0.75) return 'var(--success)';
  if (score >= 0.50) return 'var(--primary)';
  if (score >= 0.25) return 'var(--warning)';
  return 'var(--danger)';
}

function trustClass(score) {
  if (score >= 1.0)  return 'trust-purple';
  if (score >= 0.75) return 'trust-green';
  if (score >= 0.50) return 'trust-cyan';
  if (score >= 0.25) return 'trust-amber';
  return 'trust-red';
}

function trustTier(score) {
  if (score >= 1.0)  return 'AUTONOMOUS';
  if (score >= 0.75) return 'EXECUTOR';
  if (score >= 0.50) return 'MONITOR';
  if (score >= 0.25) return 'ADVISOR';
  return 'OBSERVER';
}

function glowClass(score) {
  if (score >= 1.0)  return 'glow-perfect';
  if (score >= 0.75) return 'glow-max';
  if (score >= 0.50) return 'glow-high';
  if (score >= 0.25) return 'glow-med';
  return 'glow-low';
}

function formatTrust(score) {
  return (score * 100).toFixed(0);
}

function formatTrustFull(score) {
  return score.toFixed(2);
}

// ── General Utilities ────────────────────────────────────────────────────

function topicClass(topic) {
  if (!topic) return '';
  const t = topic.toLowerCase();
  if (t.includes('trust'))     return 'topic-trust';
  if (t.includes('chronicle')) return 'topic-chronicle';
  if (t.includes('module'))    return 'topic-module';
  if (t.includes('system') || t.includes('error')) return 'topic-system';
  return '';
}

function formatTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  } catch { return ts || '--:--:--'; }
}

function formatTimeShort(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit' });
  } catch { return ''; }
}

function truncate(str, len) {
  if (!str) return '';
  const s = typeof str === 'string' ? str : JSON.stringify(str);
  return s.length > len ? s.slice(0, len) + '...' : s;
}

async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(API_BASE + path, {
      headers: { 'Content-Type': 'application/json', ...opts.headers },
      ...opts,
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return await res.json();
  } catch (err) {
    console.error(`API fetch ${path}:`, err);
    return null;
  }
}

function renderLoading() {
  return `<div class="loading-skeleton">
    <div class="skeleton-line" style="width:100%"></div>
    <div class="skeleton-line"></div>
    <div class="skeleton-line"></div>
  </div>`;
}

function renderEmpty(iconName, msg) {
  return `<div class="panel-empty">${icon(iconName, 36)}<span>${msg}</span></div>`;
}

// ── StatusBar ────────────────────────────────────────────────────────────

const StatusBar = {
  el: null,

  init() {
    this.el = document.getElementById('status-bar');
    this.fetch();
    setInterval(() => this.fetch(), 10000);
  },

  async fetch() {
    const health = await apiFetch('/api/system/health');
    const status = await apiFetch('/api/system/status');
    this.render(health, status);
  },

  render(health, status) {
    if (!this.el) return;

    const h = health || { status: 'unknown', db_accessible: false, llm_available: null };
    const s = status || {};

    const dbClass = h.db_accessible ? 'healthy' : 'unhealthy';
    const llmClass = h.llm_available === true ? 'healthy' : h.llm_available === false ? 'unhealthy' : 'unknown';
    const sysClass = h.status === 'healthy' ? 'healthy' : h.status === 'degraded' ? 'degraded' : 'unhealthy';

    this.el.innerHTML = `
      <div class="status-pill ${sysClass}">
        <span class="dot"></span>
        ${h.status || 'unknown'}
      </div>
      <div class="status-pill ${dbClass}">
        ${icon('database', 12)}
        DB
      </div>
      <div class="status-pill ${llmClass}">
        ${icon('cpu', 12)}
        LLM
      </div>
      ${s.modules_loaded != null ? `<div class="status-pill">
        ${icon('module', 12)}
        ${s.modules_loaded}
      </div>` : ''}
      ${s.version ? `<div class="status-pill">v${s.version}</div>` : ''}
    `;
  },
};

// ── Module List ──────────────────────────────────────────────────────────

const ModuleList = {
  el: null,
  bodyEl: null,
  modules: [],
  filter: '',
  sort: 'trust',
  categoryFilter: null,
  selected: null,

  init() {
    this.el = document.getElementById('module-list');
    this.bodyEl = this.el.querySelector('.panel-body');

    const searchInput = this.el.querySelector('.module-search input');
    searchInput.addEventListener('input', (e) => {
      this.filter = e.target.value.toLowerCase();
      this.render();
    });

    this.el.querySelector('[data-sort="trust"]').addEventListener('click', () => this.setSort('trust'));
    this.el.querySelector('[data-sort="alpha"]').addEventListener('click', () => this.setSort('alpha'));
    this.el.querySelectorAll('[data-category]').forEach((btn) => {
      btn.addEventListener('click', () => {
        const cat = btn.dataset.category;
        this.categoryFilter = this.categoryFilter === cat ? null : cat;
        this.el.querySelectorAll('[data-category]').forEach(b => b.classList.remove('active'));
        if (this.categoryFilter) btn.classList.add('active');
        this.render();
      });
    });

    this.bodyEl.innerHTML = renderLoading();
    this.fetch();
    setInterval(() => this.fetch(), 5000);
  },

  setSort(s) {
    this.sort = s;
    this.el.querySelectorAll('[data-sort]').forEach(b => b.classList.toggle('active', b.dataset.sort === s));
    this.render();
  },

  async fetch() {
    const data = await apiFetch('/api/modules');
    if (data && data.modules) {
      this.modules = data.modules;
      this.render();
    }
  },

  getFiltered() {
    let list = [...this.modules];

    if (this.filter) {
      list = list.filter(m =>
        m.name.toLowerCase().includes(this.filter) ||
        (m.description || '').toLowerCase().includes(this.filter)
      );
    }

    if (this.categoryFilter) {
      list = list.filter(m => this.guessCategory(m) === this.categoryFilter);
    }

    if (this.sort === 'trust') {
      list.sort((a, b) => b.trust - a.trust);
    } else {
      list.sort((a, b) => a.name.localeCompare(b.name));
    }

    return list;
  },

  guessCategory(m) {
    const n = m.name.toLowerCase();
    if (n.includes('agent') || n.includes('bot'))   return 'agent';
    if (n.includes('kernel') || n.includes('core') || n.includes('cortex') || n.includes('engram') || n.includes('aegis') || n.includes('pulse') || n.includes('chronicle')) return 'kernel';
    return 'intelligence';
  },

  render() {
    const list = this.getFiltered();
    if (list.length === 0) {
      this.bodyEl.innerHTML = renderEmpty('module', 'No modules found');
      return;
    }

    this.bodyEl.innerHTML = list.map(m => {
      const sel = this.selected === m.name ? ' selected' : '';
      const displayTrust = formatTrust(m.trust);
      return `<div class="module-item fade-enter${sel}" data-name="${m.name}">
        <span class="module-status-dot ${m.allowed ? 'allowed' : 'denied'}"></span>
        <div class="module-info">
          <div class="module-name">${m.name}</div>
          <div class="module-desc">${truncate(m.description, 40)}</div>
        </div>
        <span class="module-trust-badge ${trustClass(m.trust)}">${displayTrust}</span>
      </div>`;
    }).join('');

    this.bodyEl.querySelectorAll('.module-item').forEach(el => {
      el.addEventListener('click', () => {
        const name = el.dataset.name;
        this.selected = this.selected === name ? null : name;
        TrustGauges.highlight(this.selected);
        this.render();
      });
    });
  },
};

// ── Trust Gauges ─────────────────────────────────────────────────────────

const TrustGauges = {
  el: null,
  bodyEl: null,
  scores: [],
  highlighted: null,

  init() {
    this.el = document.getElementById('trust-gauges');
    this.bodyEl = this.el.querySelector('.panel-body');
    this.bodyEl.innerHTML = renderLoading();
    this.fetch();
    setInterval(() => this.fetch(), 5000);
  },

  async fetch() {
    const data = await apiFetch('/api/trust');
    if (data && data.scores) {
      this.scores = data.scores;
      this.render();
    }
  },

  highlight(name) {
    this.highlighted = name;
    this.render();
  },

  buildGaugeSVG(score, color) {
    const r = 38;
    const circumference = 2 * Math.PI * r;
    const sweepFraction = 0.75;
    const totalArc = circumference * sweepFraction;
    const filledArc = totalArc * score; // score is already 0.0-1.0
    const dashOffset = totalArc - filledArc;
    const startAngle = 135;
    const displayVal = formatTrust(score);
    const tier = trustTier(score);

    return `<svg class="gauge-svg" viewBox="0 0 100 100">
      <circle class="gauge-bg" cx="50" cy="50" r="${r}"
        stroke-dasharray="${totalArc} ${circumference}"
        stroke-dashoffset="0"
        transform="rotate(${startAngle} 50 50)"
        stroke-linecap="round" />
      <circle class="gauge-fill" cx="50" cy="50" r="${r}"
        stroke="${color}"
        stroke-dasharray="${totalArc} ${circumference}"
        stroke-dashoffset="${dashOffset}"
        transform="rotate(${startAngle} 50 50)" />
      <text class="gauge-value" x="50" y="46">${displayVal}</text>
      <text class="gauge-tier" x="50" y="60">${tier}</text>
    </svg>`;
  },

  render() {
    const active = this.scores.filter(s => s.trust > 0 || s.allowed);
    if (active.length === 0) {
      this.bodyEl.innerHTML = renderEmpty('trust', 'No active trust scores');
      return;
    }

    this.bodyEl.innerHTML = `<div class="trust-gauges-grid">${active.map(s => {
      const color = trustColor(s.trust);
      const hl = this.highlighted === s.module ? ' highlighted' : '';
      const glow = glowClass(s.trust);
      return `<div class="gauge-card ${glow}${hl}" data-module="${s.module}">
        ${this.buildGaugeSVG(s.trust, color)}
        <div class="gauge-label">${s.module}</div>
      </div>`;
    }).join('')}</div>`;

    this.bodyEl.querySelectorAll('.gauge-card').forEach(el => {
      el.addEventListener('click', () => {
        const name = el.dataset.module;
        ModuleList.selected = ModuleList.selected === name ? null : name;
        this.highlighted = ModuleList.selected;
        ModuleList.render();
        this.render();
      });
    });
  },
};

// ── Pulse Event Stream ───────────────────────────────────────────────────

const PulseStream = {
  el: null,
  bodyEl: null,
  statusEl: null,
  events: [],
  ws: null,
  reconnectDelay: 1000,
  maxReconnectDelay: 30000,
  maxEvents: 200,

  init() {
    this.el = document.getElementById('pulse-stream');
    this.bodyEl = this.el.querySelector('.panel-body');
    this.statusEl = this.el.querySelector('.pulse-connection');
    this.bodyEl.innerHTML = renderEmpty('pulse', 'Waiting for events...');
    this.connect();
  },

  connect() {
    if (this.ws && (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)) return;

    try {
      this.ws = new WebSocket(WS_BASE + '/api/events/ws');
    } catch (err) {
      this.setStatus(false);
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.setStatus(true);
      this.reconnectDelay = 1000;
    };

    this.ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        data._receivedAt = new Date().toISOString();
        this.addEvent(data);
      } catch (e) {
        console.error('Pulse parse error:', e);
      }
    };

    this.ws.onclose = () => {
      this.setStatus(false);
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      this.setStatus(false);
    };
  },

  scheduleReconnect() {
    setTimeout(() => this.connect(), this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  },

  setStatus(connected) {
    if (!this.statusEl) return;
    this.statusEl.className = 'pulse-connection ' + (connected ? 'connected' : 'disconnected');
    this.statusEl.innerHTML = `<span class="dot"></span>${connected ? 'live' : 'offline'}`;
  },

  addEvent(data) {
    this.events.push(data);
    if (this.events.length > this.maxEvents) {
      this.events = this.events.slice(-this.maxEvents);
    }
    this.renderLatest(data);
  },

  renderLatest(data) {
    const empty = this.bodyEl.querySelector('.panel-empty');
    if (empty) this.bodyEl.innerHTML = '';

    const el = document.createElement('div');
    el.className = 'pulse-event';
    const tc = topicClass(data.topic);
    const payload = data.payload ? truncate(JSON.stringify(data.payload), 80) : '';

    el.innerHTML = `
      <div class="pulse-event-header">
        <span class="pulse-topic ${tc}">${data.topic || 'unknown'}</span>
        <span class="pulse-time">${formatTime(data._receivedAt)}</span>
      </div>
      <div class="pulse-source">from: ${data.source || '--'}</div>
      ${payload ? `<div class="pulse-payload">${payload}</div>` : ''}
    `;

    this.bodyEl.appendChild(el);
    this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
  },
};

// ── Chronicle Timeline ───────────────────────────────────────────────────

const ChronicleTimeline = {
  el: null,
  trackEl: null,
  entries: [],
  filter: null,

  init() {
    this.el = document.getElementById('chronicle');
    this.trackEl = this.el.querySelector('.timeline-track');

    this.el.querySelectorAll('.chronicle-filters button').forEach(btn => {
      btn.addEventListener('click', () => {
        const f = btn.dataset.filter;
        if (f === 'all') {
          this.filter = null;
        } else {
          this.filter = this.filter === f ? null : f;
        }
        this.el.querySelectorAll('.chronicle-filters button').forEach(b => b.classList.remove('active'));
        if (this.filter) {
          btn.classList.add('active');
        } else {
          this.el.querySelector('[data-filter="all"]').classList.add('active');
        }
        this.render();
      });
    });

    this.fetch();
    setInterval(() => this.fetch(), 10000);
  },

  async fetch() {
    const data = await apiFetch('/api/chronicle?limit=50');
    if (data && data.entries) {
      this.entries = data.entries;
      this.render();
    }
  },

  getFiltered() {
    if (!this.filter) return this.entries;
    return this.entries.filter(e => e.action === this.filter);
  },

  render() {
    const entries = this.getFiltered();
    if (entries.length === 0) {
      this.trackEl.innerHTML = '<div class="timeline-line"></div>';
      return;
    }

    const sorted = [...entries].sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    this.trackEl.innerHTML = `<div class="timeline-line"></div>${sorted.map(e => {
      const dotClass = 'type-' + (e.action || '').replace(/\s+/g, '_');
      const payloadStr = e.payload ? truncate(JSON.stringify(e.payload), 60) : '';
      return `<div class="timeline-node">
        <div class="timeline-tooltip">
          <div class="timeline-tooltip-source">${e.source}</div>
          <div class="timeline-tooltip-action">${e.action}</div>
          ${payloadStr ? `<div class="timeline-tooltip-detail">${payloadStr}</div>` : ''}
          <div class="timeline-tooltip-time">${formatTime(e.timestamp)}</div>
        </div>
        <div class="timeline-dot ${dotClass}"></div>
        <span class="timeline-time">${formatTimeShort(e.timestamp)}</span>
      </div>`;
    }).join('')}`;
  },
};

// ── Message Console ──────────────────────────────────────────────────────

const MessageConsole = {
  el: null,
  outputEl: null,
  inputEl: null,
  sendBtn: null,
  history: [],
  historyIndex: -1,
  sending: false,

  init() {
    this.el = document.getElementById('console');
    this.outputEl = this.el.querySelector('.console-output');
    this.inputEl = this.el.querySelector('.console-input-row input');
    this.sendBtn = this.el.querySelector('.console-send-btn');

    this.addSystemLine('NEXUS Console ready. Type a message to route through Cortex.');

    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.send();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        this.navigateHistory(-1);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        this.navigateHistory(1);
      }
    });

    this.sendBtn.addEventListener('click', () => this.send());
  },

  navigateHistory(dir) {
    if (this.history.length === 0) return;
    this.historyIndex += dir;
    if (this.historyIndex < 0) this.historyIndex = 0;
    if (this.historyIndex >= this.history.length) {
      this.historyIndex = this.history.length;
      this.inputEl.value = '';
      return;
    }
    this.inputEl.value = this.history[this.historyIndex];
  },

  addSystemLine(text) {
    const div = document.createElement('div');
    div.className = 'console-line system';
    div.textContent = text;
    this.outputEl.appendChild(div);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
  },

  addInputLine(text) {
    const div = document.createElement('div');
    div.className = 'console-line input';
    div.textContent = text;
    this.outputEl.appendChild(div);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
  },

  addOutputLine(text, module) {
    const div = document.createElement('div');
    div.className = 'console-line output';
    div.innerHTML = (module ? `<span class="module-tag">[${module}]</span>` : '') + text;
    this.outputEl.appendChild(div);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
  },

  addErrorLine(text) {
    const div = document.createElement('div');
    div.className = 'console-line error';
    div.textContent = text;
    this.outputEl.appendChild(div);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
  },

  showTyping() {
    const div = document.createElement('div');
    div.className = 'console-typing';
    div.id = 'typing-indicator';
    div.innerHTML = 'processing<span class="typing-dots"></span>';
    this.outputEl.appendChild(div);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
  },

  hideTyping() {
    const el = document.getElementById('typing-indicator');
    if (el) el.remove();
  },

  async send() {
    const msg = this.inputEl.value.trim();
    if (!msg || this.sending) return;

    this.history.push(msg);
    this.historyIndex = this.history.length;
    this.inputEl.value = '';
    this.addInputLine(msg);
    this.sending = true;
    this.sendBtn.disabled = true;
    this.showTyping();

    try {
      const data = await apiFetch('/api/messages', {
        method: 'POST',
        body: JSON.stringify({ message: msg }),
      });

      this.hideTyping();

      if (data) {
        this.addOutputLine(data.response || '(empty response)', data.module);
      } else {
        this.addErrorLine('Failed to get response from NEXUS');
      }
    } catch (err) {
      this.hideTyping();
      this.addErrorLine('Error: ' + err.message);
    } finally {
      this.sending = false;
      this.sendBtn.disabled = false;
      this.inputEl.focus();
    }
  },
};

// ── Initialize ───────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  StatusBar.init();
  ModuleList.init();
  TrustGauges.init();
  PulseStream.init();
  ChronicleTimeline.init();
  MessageConsole.init();
});
