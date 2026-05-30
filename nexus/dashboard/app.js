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
      <div class="status-pill ${dbClass} llm-clickable" id="db-pill" title="View database info">
        <span class="dot"></span>
        ${icon('database', 12)}
        DB
      </div>
      <div class="status-pill ${llmClass} llm-clickable" id="llm-pill" title="Manage LLM providers">
        <span class="dot"></span>
        ${icon('llm', 12)}
        LLM
      </div>
      ${s.modules_loaded != null ? `<div class="status-pill healthy">
        <span class="dot"></span>
        ${s.modules_loaded}
      </div>` : ''}
      ${s.version ? `<div class="status-pill">v${s.version}</div>` : ''}
    `;

    // Wire pill clicks
    const dbPill = document.getElementById('db-pill');
    if (dbPill) {
      dbPill.addEventListener('click', () => DatabaseManager.open());
    }
    const llmPill = document.getElementById('llm-pill');
    if (llmPill) {
      llmPill.addEventListener('click', () => ProviderManager.open());
    }
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
    const kernelNames = ['cortex', 'engram', 'aegis', 'pulse', 'chronicle'];
    if (kernelNames.includes(n)) return 'kernel';
    if (n.startsWith('agent.')) return 'agent';
    if (n.includes('agent') || n.includes('bot')) return 'agent';
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
      const displayName = m.name.startsWith('agent.') ? m.name.slice(6) : m.name;
      const isAgent = m.name.startsWith('agent.');
      return `<div class="module-item fade-enter${sel}" data-name="${m.name}">
        <span class="module-status-dot ${m.allowed ? 'allowed' : 'denied'}"></span>
        <div class="module-info">
          <div class="module-name">${displayName}${isAgent ? ' <span class="mcp-tag">MCP</span>' : ''}</div>
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
      const isAgent = s.module.startsWith('agent.');
      const label = isAgent ? s.module.slice(6) : s.module;
      const builtin = isAgent ? '' : ' builtin';
      return `<div class="gauge-card ${glow}${hl}${builtin}" data-module="${s.module}">
        ${this.buildGaugeSVG(s.trust, color)}
        <div class="gauge-label">${label}</div>
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
    el.style.cursor = 'pointer';
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

    el.addEventListener('click', () => this.showDetail(data));

    this.bodyEl.appendChild(el);
    this.bodyEl.scrollTop = this.bodyEl.scrollHeight;
  },

  showDetail(data) {
    // Remove existing popup if any
    const existing = document.getElementById('pulse-detail-popup');
    if (existing) existing.remove();

    const payloadStr = data.payload
      ? JSON.stringify(data.payload, null, 2)
      : 'No payload';

    const popup = document.createElement('div');
    popup.id = 'pulse-detail-popup';
    popup.className = 'pulse-detail-overlay';
    popup.innerHTML = `
      <div class="pulse-detail-modal">
        <div class="pulse-detail-header">
          <span class="pulse-topic ${topicClass(data.topic)}">${data.topic || 'unknown'}</span>
          <button class="modal-close" id="pulse-detail-close">${icon('x', 18)}</button>
        </div>
        <div class="pulse-detail-rows">
          <div class="pulse-detail-row"><span class="pulse-detail-label">source</span><span>${data.source || '--'}</span></div>
          <div class="pulse-detail-row"><span class="pulse-detail-label">time</span><span>${data._receivedAt ? new Date(data._receivedAt).toLocaleString() : '--'}</span></div>
          ${data.id ? `<div class="pulse-detail-row"><span class="pulse-detail-label">id</span><span>${data.id}</span></div>` : ''}
        </div>
        <div class="pulse-detail-payload-label">payload</div>
        <pre class="pulse-detail-payload">${payloadStr}</pre>
      </div>
    `;

    popup.addEventListener('click', (e) => {
      if (e.target === popup) popup.remove();
    });
    popup.querySelector('#pulse-detail-close').addEventListener('click', () => popup.remove());

    document.getElementById('app').appendChild(popup);
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

  _categoryMap: {
    start:  ['server_start', 'provider_registered', 'agent_launched'],
    stop:   ['server_stop', 'provider_removed', 'agent_stopped'],
    trust:  ['trust_adjusted', 'user_feedback', 'aegis.trust_change'],
    allow:  ['module_allowed', 'route', 'response'],
    deny:   ['module_denied', 'permission_denied', 'network_denied'],
    msg:    ['route', 'response', 'module_error', 'user_feedback'],
  },

  getFiltered() {
    if (!this.filter) return this.entries;
    const actions = this._categoryMap[this.filter] || [this.filter];
    return this.entries.filter(e => actions.includes(e.action));
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
      const payload = e.payload || {};
      const hasPayload = Object.keys(payload).length > 0;
      // Build a human-readable detail line from payload
      let detail = '';
      if (hasPayload) {
        if (payload.module) detail = payload.module;
        else if (payload.target) detail = payload.target;
        else if (payload.provider) detail = payload.provider;
        if (payload.message_preview) detail += ': ' + truncate(payload.message_preview, 40);
        else if (payload.reason) detail += ': ' + truncate(payload.reason, 40);
        else if (payload.response_preview) detail += ': ' + truncate(payload.response_preview, 40);
        if (!detail) detail = truncate(JSON.stringify(payload), 50);
      }
      return `<div class="timeline-node">
        <div class="timeline-tooltip">
          <div class="timeline-tooltip-source">${e.source}</div>
          <div class="timeline-tooltip-action">${e.action}</div>
          ${detail ? `<div class="timeline-tooltip-detail">${detail}</div>` : ''}
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

  _scrollToLatest(div) {
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
    requestAnimationFrame(() => {
      const rect = div.getBoundingClientRect();
      const viewportH = window.innerHeight || document.documentElement.clientHeight;
      if (rect.bottom > viewportH || rect.top < 0) {
        div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    });
  },

  addSystemLine(text) {
    const div = document.createElement('div');
    div.className = 'console-line system';
    div.textContent = text;
    this.outputEl.appendChild(div);
    this._scrollToLatest(div);
  },

  addInputLine(text) {
    const div = document.createElement('div');
    div.className = 'console-line input';
    div.textContent = text;
    this.outputEl.appendChild(div);
    this._scrollToLatest(div);
  },

  addOutputLine(text, module) {
    const div = document.createElement('div');
    div.className = 'console-line output';

    const content = (module ? `<span class="module-tag">[${module}]</span>` : '') + text;

    if (module) {
      // Check current trust to decide whether to show feedback dots
      const trust = this._getModuleTrust(module);
      const showFeedback = trust < 1.0;

      div.innerHTML = `
        <div class="console-response-content">${content}</div>
        ${showFeedback ? `<div class="console-feedback" data-module="${module}">
          <button class="feedback-dot accept" title="+0.12 trust"></button>
          <button class="feedback-dot reject" title="-0.22 trust"></button>
        </div>` : ''}
      `;

      if (showFeedback) {
        const acceptBtn = div.querySelector('.feedback-dot.accept');
        const rejectBtn = div.querySelector('.feedback-dot.reject');
        const feedbackEl = div.querySelector('.console-feedback');

        acceptBtn.addEventListener('click', () => {
          this.sendFeedback(module, true);
          feedbackEl.innerHTML = '<span class="feedback-done accepted">+0.12</span>';
        });

        rejectBtn.addEventListener('click', () => {
          this.sendFeedback(module, false);
          feedbackEl.innerHTML = '<span class="feedback-done rejected">-0.22</span>';
        });
      }
    } else {
      div.innerHTML = content;
    }

    this.outputEl.appendChild(div);
    this._scrollToLatest(div);
  },

  _getModuleTrust(moduleName) {
    // Pull from TrustGauges cached data if available
    if (TrustGauges.scores) {
      const entry = TrustGauges.scores.find(s => s.module === moduleName);
      if (entry) return entry.trust;
    }
    return 0.3; // default
  },

  async sendFeedback(module, accepted) {
    const data = await apiFetch('/api/messages/feedback', {
      method: 'POST',
      body: JSON.stringify({ module, accepted }),
    });
    // Refresh trust gauges after feedback
    if (data) TrustGauges.fetch();
  },

  addErrorLine(text) {
    const div = document.createElement('div');
    div.className = 'console-line error';
    div.textContent = text;
    this.outputEl.appendChild(div);
    this._scrollToLatest(div);
  },

  showTyping() {
    const div = document.createElement('div');
    div.className = 'console-typing';
    div.id = 'typing-indicator';
    div.innerHTML = 'processing<span class="typing-dots"></span>';
    this.outputEl.appendChild(div);
    this._scrollToLatest(div);
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

    // Handle local commands
    const revokeMatch = msg.match(/^revoke\s+trust:\s*(.+)$/i);
    if (revokeMatch) {
      const moduleName = revokeMatch[1].trim().toLowerCase();
      await this.revokeTrust(moduleName);
      return;
    }

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

  async revokeTrust(moduleName) {
    // Get current trust to calculate delta needed to reach 0.30
    const trustData = await apiFetch('/api/trust');
    if (!trustData) {
      this.addErrorLine('Failed to fetch trust data');
      return;
    }
    const entry = trustData.scores.find(s => s.module === moduleName);
    if (!entry) {
      this.addErrorLine(`Module '${moduleName}' not found`);
      return;
    }

    const currentTrust = entry.trust;
    const targetTrust = 0.30;
    if (currentTrust <= targetTrust) {
      this.addSystemLine(`[aegis] ${moduleName} trust is already at ${currentTrust.toFixed(2)} (at or below 0.30)`);
      return;
    }

    const delta = targetTrust - currentTrust;
    const data = await apiFetch(`/api/trust/${moduleName}/adjust`, {
      method: 'POST',
      body: JSON.stringify({ delta, reason: 'trust revoked by operator' }),
    });

    if (data) {
      this.addSystemLine(`[aegis] ${moduleName} trust revoked: ${currentTrust.toFixed(2)} -> ${data.new_trust.toFixed(2)} (ADVISOR tier)`);
      TrustGauges.fetch();
    } else {
      this.addErrorLine(`Failed to revoke trust for ${moduleName}`);
    }
  },
};

// ── Database Manager ────────────────────────────────────────────────────

const DatabaseManager = {
  modalEl: null,
  infoEl: null,

  init() {
    this.modalEl = document.getElementById('db-modal');
    this.infoEl = document.getElementById('db-info');

    document.getElementById('db-modal-close').addEventListener('click', () => this.close());
    this.modalEl.addEventListener('click', (e) => {
      if (e.target === this.modalEl) this.close();
    });
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.modalEl.classList.contains('open')) this.close();
    });
  },

  open() {
    this.modalEl.classList.add('open');
    this.infoEl.innerHTML = '<div class="provider-status loading">Loading database info...</div>';
    this.fetch();
  },

  close() {
    this.modalEl.classList.remove('open');
  },

  async fetch() {
    const data = await apiFetch('/api/system/db');
    if (!data) {
      this.infoEl.innerHTML = '<div class="provider-status error">Failed to load database info</div>';
      return;
    }
    this.render(data);
  },

  formatSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  },

  render(data) {
    const tables = data.tables || {};
    const tableNames = Object.keys(tables);
    const totalRows = Object.values(tables).reduce((a, b) => a + (b > 0 ? b : 0), 0);

    let html = `
      <div class="db-stats">
        <div class="db-stat-card">
          <div class="db-stat-value">${tableNames.length}</div>
          <div class="db-stat-label">tables</div>
        </div>
        <div class="db-stat-card">
          <div class="db-stat-value">${totalRows.toLocaleString()}</div>
          <div class="db-stat-label">rows</div>
        </div>
        <div class="db-stat-card">
          <div class="db-stat-value">${this.formatSize(data.size_bytes || 0)}</div>
          <div class="db-stat-label">size</div>
        </div>
      </div>
      <div class="db-path">${data.path || 'unknown'}</div>
      <div class="provider-list-title" style="margin-top:18px">Tables</div>
    `;

    for (const [name, count] of Object.entries(tables)) {
      html += `<div class="provider-card">
        <span class="provider-dot healthy"></span>
        <div class="provider-card-info">
          <div class="provider-card-name">${name}</div>
        </div>
        <span class="module-trust-badge trust-cyan">${count >= 0 ? count.toLocaleString() : '?'}</span>
      </div>`;
    }

    this.infoEl.innerHTML = html;
  },
};

// ── Provider Manager ────────────────────────────────────────────────────

const ProviderManager = {
  modalEl: null,
  listEl: null,
  statusEl: null,
  submitBtn: null,
  selectedType: 'anthropic',
  providers: [],

  init() {
    this.modalEl = document.getElementById('provider-modal');
    this.listEl = document.getElementById('provider-list');
    this.statusEl = document.getElementById('provider-status');
    this.submitBtn = document.getElementById('provider-submit');

    // Close button
    document.getElementById('provider-modal-close').addEventListener('click', () => this.close());

    // Overlay click to close
    this.modalEl.addEventListener('click', (e) => {
      if (e.target === this.modalEl) this.close();
    });

    // Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && this.modalEl.classList.contains('open')) this.close();
    });

    // Type selector
    this.modalEl.querySelectorAll('.provider-type-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        this.selectedType = btn.dataset.type;
        this.modalEl.querySelectorAll('.provider-type-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.updateFormFields();
      });
    });

    // Submit
    this.submitBtn.addEventListener('click', () => this.submit());

    // Enter key in inputs
    this.modalEl.querySelectorAll('.provider-fields input[type="text"], .provider-fields input[type="password"]').forEach(inp => {
      inp.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') this.submit();
      });
    });

    this.updateFormFields();
  },

  open() {
    this.modalEl.classList.add('open');
    this.statusEl.textContent = '';
    this.statusEl.className = 'provider-status';
    this.fetchProviders();
    // Focus API key field
    setTimeout(() => {
      const keyInput = document.getElementById('provider-api-key');
      if (keyInput && keyInput.offsetParent !== null) keyInput.focus();
    }, 100);
  },

  close() {
    this.modalEl.classList.remove('open');
  },

  updateFormFields() {
    const apiKeyField = document.getElementById('field-api-key');
    const modelField = document.getElementById('field-model');
    const baseUrlField = document.getElementById('field-base-url');
    const modelInput = document.getElementById('provider-model');

    if (this.selectedType === 'local') {
      apiKeyField.style.display = 'none';
      baseUrlField.style.display = '';
      modelInput.placeholder = 'model name (optional)';
    } else {
      apiKeyField.style.display = '';
      baseUrlField.style.display = 'none';
      if (this.selectedType === 'anthropic') {
        modelInput.placeholder = 'claude-sonnet-4-20250514';
      } else {
        modelInput.placeholder = 'gpt-4o-mini';
      }
    }
  },

  async fetchProviders() {
    const data = await apiFetch('/api/providers');
    if (data && data.providers) {
      this.providers = data.providers;
      this.renderList(data.default);
    }
  },

  renderList(defaultName) {
    if (!this.providers.length) {
      this.listEl.innerHTML = '';
      return;
    }

    const html = `<div class="provider-list-title">Registered Providers</div>` +
      this.providers.map(p => {
        const dotClass = p.healthy ? 'healthy' : 'unhealthy';
        const isDefault = p.is_default;
        return `<div class="provider-card" data-name="${p.name}">
          <span class="provider-dot ${dotClass}"></span>
          <div class="provider-card-info">
            <div class="provider-card-name">${p.name}</div>
            <div class="provider-card-meta">${p.healthy ? 'connected' : 'unreachable'}</div>
          </div>
          ${isDefault ? `<span class="provider-default-badge">default</span>` : `
            <button class="provider-action-btn set-default" data-name="${p.name}" title="Set as default">${icon('star', 15)}</button>
          `}
          <button class="provider-action-btn remove" data-name="${p.name}" title="Remove">${icon('trash', 15)}</button>
        </div>`;
      }).join('');

    this.listEl.innerHTML = html;

    // Bind actions
    this.listEl.querySelectorAll('.set-default').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.setDefault(btn.dataset.name);
      });
    });

    this.listEl.querySelectorAll('.remove').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        this.removeProvider(btn.dataset.name);
      });
    });
  },

  async submit() {
    const apiKey = document.getElementById('provider-api-key').value.trim();
    const model = document.getElementById('provider-model').value.trim();
    const baseUrl = document.getElementById('provider-base-url').value.trim();
    const setDefault = document.getElementById('provider-set-default').checked;

    if (this.selectedType !== 'local' && !apiKey) {
      this.setStatus('API key is required', 'error');
      return;
    }

    this.submitBtn.disabled = true;
    this.setStatus('Connecting...', 'loading');

    const body = {
      provider: this.selectedType,
      set_default: setDefault,
    };
    if (apiKey) body.api_key = apiKey;
    if (model) body.model = model;
    if (baseUrl) body.base_url = baseUrl;

    try {
      const res = await fetch(API_BASE + '/api/providers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      const data = await res.json();

      if (!res.ok) {
        this.setStatus(data.detail || 'Registration failed', 'error');
        return;
      }

      this.setStatus(data.message || 'Provider connected', 'success');
      document.getElementById('provider-api-key').value = '';
      document.getElementById('provider-model').value = '';
      document.getElementById('provider-base-url').value = '';

      // Refresh provider list and status bar
      this.fetchProviders();
      StatusBar.fetch();
    } catch (err) {
      this.setStatus('Connection error: ' + err.message, 'error');
    } finally {
      this.submitBtn.disabled = false;
    }
  },

  async setDefault(name) {
    const res = await fetch(API_BASE + `/api/providers/default/${name}`, { method: 'POST' });
    if (res.ok) {
      this.fetchProviders();
      StatusBar.fetch();
    }
  },

  async removeProvider(name) {
    const res = await fetch(API_BASE + `/api/providers/${name}`, { method: 'DELETE' });
    if (res.ok) {
      this.fetchProviders();
      StatusBar.fetch();
    }
  },

  setStatus(msg, cls) {
    this.statusEl.textContent = msg;
    this.statusEl.className = 'provider-status ' + (cls || '');
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
  DatabaseManager.init();
  ProviderManager.init();
});
