const app = {
  _theme: 'light',
  _lastSeq: 0,
  _pollers: [],

  init() {
    this.loadTheme();
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

  toggleLang() {
    const langs = i18n.getSupportedLangs();
    const codes = langs.map(l => l.code);
    const idx = codes.indexOf(i18n.lang);
    const next = codes[(idx + 1) % codes.length];
    i18n.setLang(next).then(() => {
      this.updateLangLabel();
      this.applyI18n();
      router.resolve();
    });
  },

  updateLangLabel() {
    const label = document.getElementById('lang-label');
    if (label) label.textContent = i18n.lang.toUpperCase();
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
    this.pollCanary();
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
};

document.addEventListener('DOMContentLoaded', () => app.init());
