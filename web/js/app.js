const app = {
  _theme: 'light',
  _lastSeq: 0,
  _pollers: [],

  init() {
    this.loadTheme();
    router.resolve();
    this.startPollers();
    window.addEventListener('beforeunload', () => this.stopPollers());
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
    if (label) label.textContent = theme === 'dark' ? 'Dark' : 'Light';
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
    // Global events poller (shared across all pages)
    this._pollers.push(setInterval(() => this.pollEvents(), 2000));
  },

  stopPollers() {
    this._pollers.forEach(id => clearInterval(id));
    this._pollers = [];
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
