const router = {
  routes: {},
  current: '',
  titles: {
    overview: ['Overview', 'Dashboard — key metrics from all systems'],
    hunt: ['Hunt', 'Pool harvesting, validation and progress'],
    proxies: ['Proxies', 'Manage and monitor your proxy pool'],
    'proxy-control': ['Proxy Control', 'Monitor and control internal proxy performance and traffic'],
    'proxy-pool': ['Proxy Pool', 'Browse and select upstream proxies'],
    blacklist: ['Blacklist', 'Manage blacklisted proxies'],
    analytics: ['Analytics', 'Proxy performance analytics and trends'],
    logs: ['Logs', 'System logs and activity'],
    settings: ['Settings', 'Configure huntproxy settings'],
    rules: ['Rules', 'Transparent proxy rules and iptables configuration'],
    downloads: ['Downloads', 'Export data files'],
    api: ['API', 'API documentation and endpoints'],
  },

  register(page, renderFn) {
    this.routes[page] = renderFn;
  },

  navigate(page) {
    window.location.hash = `#/${page}`;
  },

  resolve() {
    // Clear previous page intervals
    if (window._pageIntervals) {
      window._pageIntervals.forEach(clearInterval);
    }
    window._pageIntervals = [];

    const raw = window.location.hash.replace(/^#\//, '').replace(/^#/, '');
    const page = raw || 'overview';
    this.current = page;
    const container = document.getElementById('router-view');
    if (!container) return;
    container.innerHTML = '';
    const fn = this.routes[page];
    if (fn) {
      try { fn(container); } catch (e) { console.error(e); container.innerHTML = `<div class="empty" style="color:var(--danger)">Error rendering page: ${e.message}</div>`; }
    } else {
      container.innerHTML = `<div class="empty">Page not found: <b>${page}</b></div>`;
    }
    // Sidebar active state
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.page === page);
    });
    // Title
    const [title, sub] = this.titles[page] || [page, ''];
    const tEl = document.getElementById('page-title');
    const sEl = document.getElementById('page-subtitle');
    if (tEl) tEl.textContent = title;
    if (sEl) sEl.textContent = sub;
    // Close mobile sidebar
    document.body.classList.remove('sidebar-open');
  },
};

window.addEventListener('hashchange', () => router.resolve());
window.addEventListener('DOMContentLoaded', () => router.resolve());
