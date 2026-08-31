const app = {
  _theme: 'light',
  _lastSeq: 0,
  _pollers: [],
  _sectionOf: {
    server: 'engine', 'proxy-control': 'engine', connectivity: 'engine', routes: 'engine',
    'traffic-flow': 'engine', pac: 'engine',
    'proxy-pool': 'proxies', hunt: 'proxies', proxies: 'proxies', favorites: 'proxies',
    analytics: 'proxies', 'custom-proxies': 'proxies',
    'proxy-sources': 'lists', blacklist: 'lists', 'ip-blacklists': 'lists', blocklists: 'lists', 'domain-lists': 'lists',
    logs: 'insights', actions: 'insights',
    settings: 'system', schedules: 'system', downloads: 'system', api: 'system', about: 'system',
  },

  init() {
    this.loadTheme();
    this.initSections();
    i18n.init().then(() => {
      this.updateLangLabel();
      this.applyI18n();
      router.resolve();
      this.startPollers();
      window.addEventListener('beforeunload', () => this.stopPollers());
    });
  },

  loadTheme() {
    const saved = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
    this._theme = saved;
    this.updateThemeIcon(saved);
  },

  toggleTheme() {
    const next = this._theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    this._theme = next;
    this.updateThemeIcon(next);
  },

  updateThemeIcon(theme) {
    const sun = document.getElementById('theme-icon-sun');
    const moon = document.getElementById('theme-icon-moon');
    const label = document.getElementById('theme-label');
    if (sun && moon) {
      sun.style.display = theme === 'dark' ? 'none' : 'inline';
      moon.style.display = theme === 'dark' ? 'inline' : 'none';
    }
    if (label) label.textContent = theme === 'dark' ? t('sidebar.dark') : t('sidebar.light');
  },

  updateLangLabel() {
    const bar = document.getElementById('lang-bar');
    if (!bar) return;
    bar.innerHTML = '';
    const langs = i18n.getSupportedLangs();
    langs.forEach(l => {
      const btn = ui.el('button', 'lang-btn' + (l.code === i18n.lang ? ' active' : ''), { text: l.code.toUpperCase() });
      btn.addEventListener('click', () => {
        if (l.code === i18n.lang) return;
        i18n.setLang(l.code).then(() => {
          bar.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');
          this.applyI18n();
          router.resolve();
        });
      });
      bar.appendChild(btn);
    });
  },

  applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      el.textContent = t(key);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      el.placeholder = t(key);
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
      const key = el.getAttribute('data-i18n-title');
      el.title = t(key);
    });
  },

  toggleSidebar() {
    document.body.classList.toggle('sidebar-open');
  },

  initSections() {
    const saved = localStorage.getItem('sidebar-collapsed');
    let collapsed = null;
    if (saved !== null) {
      try {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed)) collapsed = parsed;
      } catch (e) {}
    }
    document.querySelectorAll('.nav-section').forEach(sec => {
      const name = sec.dataset.section;
      if (collapsed === null || collapsed.includes(name)) {
        sec.classList.add('collapsed');
      }
    });
  },

  toggleSection(name) {
    const sec = document.querySelector(`.nav-section[data-section="${name}"]`);
    if (!sec) return;
    let collapsed = [];
    try { collapsed = JSON.parse(localStorage.getItem('sidebar-collapsed') || '[]'); } catch (e) {}
    if (sec.classList.contains('collapsed')) {
      sec.classList.remove('collapsed');
      collapsed = collapsed.filter(s => s !== name);
    } else {
      sec.classList.add('collapsed');
      collapsed.push(name);
    }
    localStorage.setItem('sidebar-collapsed', JSON.stringify(collapsed));
  },

  expandActiveSection(page) {
    const name = this._sectionOf[page];
    document.querySelectorAll('.nav-section').forEach(sec => {
      sec.classList.toggle('nav-section-has-active', sec.dataset.section === name);
    });
    if (!name) return;
    const sec = document.querySelector(`.nav-section[data-section="${name}"]`);
    if (sec && sec.classList.contains('collapsed')) {
      sec.classList.remove('collapsed');
      let collapsed = [];
      try { collapsed = JSON.parse(localStorage.getItem('sidebar-collapsed') || '[]'); } catch (e) {}
      collapsed = collapsed.filter(s => s !== name);
      localStorage.setItem('sidebar-collapsed', JSON.stringify(collapsed));
    }
  },

  toast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => { if (el.parentNode) el.parentNode.removeChild(el); }, 4000);
  },

  startPollers() {
    this._pollers.push(setInterval(() => this.pollEvents(), 2000));
    this._pollers.push(setInterval(() => this.pollCanary(), 30000));
    this._pollers.push(setInterval(() => this.pollTraffic(), 2000));
    this._pollers.push(setInterval(() => this.pollPing(), 1000));
    this._pollers.push(setInterval(() => this.pollDirectMode(), 3000));
    this._pollers.push(setInterval(() => this.pollChannel(), 3000));
    this._pollers.push(setInterval(() => this.pollVersion(), 60000));
    this.pollCanary();
    this.pollVersion();
    this.pollTraffic();
    this.pollPing();
    this.pollDirectMode();
    this.pollChannel();
  },

  stopPollers() {
    this._pollers.forEach(id => clearInterval(id));
    this._pollers = [];
  },

  async pollCanary() {
    try {
      const result = await api.canaryStatus();
      const dot = document.getElementById('canary-dot');
      const text = document.getElementById('canary-text');
      if (dot && text) {
        if (result.alive) {
          dot.className = 'status-dot online';
          text.textContent = t('sidebar.internetOK');
        } else {
          dot.className = 'status-dot offline';
          text.textContent = t('sidebar.internetDown');
        }
      }
    } catch (e) {
      const dot = document.getElementById('canary-dot');
      const text = document.getElementById('canary-text');
      if (dot) dot.className = 'status-dot offline';
      if (text) text.textContent = t('sidebar.internetUnknown');
    }
  },

  async pollVersion() {
    try {
      const v = await api.version();
      const el = document.getElementById('sys-version');
      if (!el || !v) return;
      el.textContent = v.display || v.commit || '';
      el.href = v.url || '#';
    } catch (e) {
      const el = document.getElementById('sys-version');
      if (el) { el.textContent = 'unknown'; el.href = '#'; }
    }
  },

  async pollTraffic() {
    try {
      const t = await api.trafficLive();
      const now = Date.now();
      const inB = t.in_bytes || 0;   // bytes_in = client→upstream = upload
      const outB = t.out_bytes || 0; // bytes_out = upstream→client = download
      const totalB = t.total_bytes || 0;

      let inRate = 0;
      let outRate = 0;
      if (this._lastTraffic && now > this._lastTraffic.ts) {
        const delta = (now - this._lastTraffic.ts) / 1000;
        inRate = Math.max(0, (inB - this._lastTraffic.inBytes) / delta);
        outRate = Math.max(0, (outB - this._lastTraffic.outBytes) / delta);
      }
      this._lastTraffic = { ts: now, inBytes: inB, outBytes: outB, totalBytes: totalB };

      const inEl = document.getElementById('traffic-in');   // ↓ In = download = out_bytes
      const outEl = document.getElementById('traffic-out'); // ↑ Out = upload = in_bytes
      const totalEl = document.getElementById('traffic-total');
      if (inEl) inEl.textContent = ui.fmtBytes(outRate) + '/s';
      if (outEl) outEl.textContent = ui.fmtBytes(inRate) + '/s';
      if (totalEl) totalEl.textContent = ui.fmtBytes(totalB);
    } catch (e) {
      console.error('pollTraffic', e);
      const inEl = document.getElementById('traffic-in');
      const outEl = document.getElementById('traffic-out');
      const totalEl = document.getElementById('traffic-total');
      if (inEl) inEl.textContent = '—';
      if (outEl) outEl.textContent = '—';
      if (totalEl) totalEl.textContent = '—';
    }
  },

  async pollEvents() {
    try {
      const ev = await api.events(this._lastSeq);
      if (ev && ev.length) {
        this._lastSeq = Math.max(...ev.map(e => e.seq), this._lastSeq);
        // Pages can hook into this by dispatching a custom event
        window.dispatchEvent(new CustomEvent('hunt-events', { detail: ev }));
      }
    } catch (e) {
      // Silently ignore network errors during polling
    }
  },

  async pollChannel() {
    try {
      const ch = await api.channelStatus().catch(() => null);
      const badge = document.getElementById('channel-badge');
      if (!badge || !ch) return;
      const span = document.getElementById('channel-badge-text');
      const route = ch.channel_route || '';
      if (route && route !== 'direct') {
        badge.style.display = '';
        const p = ch.proxy;
        if (p) {
          const ok = ch.available;
          badge.style.borderColor = ok ? 'var(--info)' : 'var(--danger)';
          badge.style.background = ok ? 'var(--info-bg)' : 'var(--danger-bg)';
          badge.style.color = ok ? 'var(--info)' : 'var(--danger)';
          if (span) span.textContent = t('topbar.channelText') + ': ' + p.host + ':' + p.port;
        } else {
          badge.style.borderColor = 'var(--danger)';
          badge.style.background = 'var(--danger-bg)';
          badge.style.color = 'var(--danger)';
          if (span) span.textContent = t('topbar.channelText') + ': ' + t('topbar.channelUnavailable');
        }
      } else {
        badge.style.display = 'none';
      }
    } catch (e) { /* ignore */ }
  },

  async pollPing() {
    try {
      const p = await api.proxyPing();
      const badge = document.getElementById('ping-badge');
      const valueEl = document.getElementById('ping-value');
      const proxyEl = document.getElementById('ping-proxy');
      const geoEl = document.getElementById('ping-geo');
      const line = document.getElementById('ping-spark-line');
      if (!badge || !valueEl) return;
      const last = p.last || {};
      const ok = last.ok === true;
      const lat = ok ? (last.latency || 0) : -1;
      const color = !ok ? 'var(--danger)' : lat < 100 ? 'var(--success)' : lat < 300 ? 'var(--warning, #f0ad4e)' : 'var(--danger)';
      valueEl.style.color = color;
      valueEl.textContent = ok ? lat + 'ms' : '✗';
      if (line) {
        const samples = p.samples || [];
        if (samples.length >= 1) {
          const n = samples.length;
          const pts = samples.map((s, i) => {
            const x = (n === 1 ? 23 : (i / (n - 1) * 44)).toFixed(1);
            const y = (16 - Math.min(Math.max(s.latency, 0), 500) / 500 * 13).toFixed(1);
            return `${x},${y}`;
          }).join(' ');
          line.setAttribute('points', pts);
          line.setAttribute('stroke', color);
          line.style.display = '';
        } else {
          line.style.display = 'none';
        }
      }
      const src = p.source || 'none';
      if (src === 'none' && !ok) {
        badge.style.display = 'none';
        return;
      }
      badge.style.display = '';
      // Clicking the badge opens the standard proxy card for the proxy it
      // pings through (pool proxy or channel pool-proxy); custom channels
      // and direct mode fall back to the connectivity page.
      if (badge && !badge._pingClickBound) {
        badge._pingClickBound = true;
        badge.style.cursor = 'pointer';
        badge.addEventListener('click', () => {
          const addr = badge.dataset.pingAddr;
          if (addr && window.proxyCard) window.proxyCard.show(addr);
          else router.navigate('connectivity');
        });
      }
      const clickable = src === 'pool' ||
        (src === 'channel' && (p.route || '').startsWith('proxy:'));
      badge.dataset.pingAddr = clickable ? (p.proxy_addr || '') : '';
      badge.style.cursor = clickable ? 'pointer' : 'default';
      const srcLabel = src === 'direct' ? '↔' : src === 'channel' ? '◈' : '⬢';
      if (proxyEl) {
        proxyEl.textContent = src === 'direct'
          ? (srcLabel + ' ' + t('topbar.pingDirect'))
          : (srcLabel + ' ' + (p.proxy_addr || '') + (ok ? '' : ' — ' + (last.error || t('topbar.pingFail'))));
        proxyEl.title = proxyEl.textContent;
      }
      if (geoEl) {
        const g = p.geo || {};
        const flag = ui.flag((g.country_code || '').toUpperCase());
        const parts = [];
        const country = g.country || g.country_code || '';
        if (country) parts.push(country);
        if (g.city) parts.push(g.city);
        const isp = g.isp || '';
        if (isp) parts.push(isp);
        geoEl.textContent = ((flag ? flag + ' ' : '') + parts.join(' · ')) || '—';
        geoEl.title = parts.join(' · ');
      }
    } catch (e) {
      const badge = document.getElementById('ping-badge');
      if (badge) badge.style.display = 'none';
    }
  },

  async pollDirectMode() {
    try {
      const [ps, rs] = await Promise.all([
        api.proxyStatus().catch(() => null),
        api.routingStatus().catch(() => null),
      ]);
      const badge = document.getElementById('direct-mode-badge');
      if (!badge) return;
      const span = badge.querySelector('span');
      if (rs && rs.enabled) {
        badge.style.display = '';
        badge.style.borderColor = 'var(--accent)';
        badge.style.background = 'var(--accent-bg)';
        badge.style.color = 'var(--accent)';
        if (span) span.textContent = t('topbar.routingModeText');
      } else if (ps && ps.direct_mode) {
        badge.style.display = '';
        badge.style.borderColor = 'var(--warning)';
        badge.style.background = 'var(--warning-bg)';
        badge.style.color = 'var(--warning)';
        if (span) span.textContent = t('topbar.directModeText');
      } else if (ps && ps.active_proxy) {
        badge.style.display = '';
        badge.style.borderColor = 'var(--info)';
        badge.style.background = 'var(--info-bg)';
        badge.style.color = 'var(--info)';
        if (span) span.textContent = t('topbar.cascadeModeText') + ': ' + (ps.active_proxy.address || '');
      } else {
        badge.style.display = 'none';
      }
    } catch (e) { /* ignore */ }
  },
};

document.addEventListener('DOMContentLoaded', () => app.init());
