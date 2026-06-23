const router = {
  routes: {},
  current: '',
  titles: {
    overview: ['page.overview.title', 'page.overview.subtitle'],
    hunt: ['page.hunt.title', 'page.hunt.subtitle'],
    'proxy-sources': ['page.proxySources.title', 'page.proxySources.subtitle'],
    proxies: ['page.proxies.title', 'page.proxies.subtitle'],
    'proxy-control': ['page.proxyControl.title', 'page.proxyControl.subtitle'],
    'proxy-pool': ['page.proxyPool.title', 'page.proxyPool.subtitle'],
    blacklist: ['page.blacklist.title', 'page.blacklist.subtitle'],
    favorites: ['page.favorites.title', 'page.favorites.subtitle'],
    'ip-blacklists': ['page.ipBlacklists.title', 'page.ipBlacklists.subtitle'],
    'blocklists': ['page.blocklists.title', 'page.blocklists.subtitle'],
    analytics: ['page.analytics.title', 'page.analytics.subtitle'],
    logs: ['page.logs.title', 'page.logs.subtitle'],
    actions: ['page.actions.title', 'page.actions.subtitle'],
    settings: ['page.settings.title', 'page.settings.subtitle'],
    routes: ['page.routes.title', 'page.routes.subtitle'],
    'domain-lists': ['page.domainLists.title', 'page.domainLists.subtitle'],
    'custom-proxies': ['page.customProxies.title', 'page.customProxies.subtitle'],
    'connectivity': ['page.connectivity.title', 'page.connectivity.subtitle'],
    downloads: ['page.downloads.title', 'page.downloads.subtitle'],
    api: ['page.api.title', 'page.api.subtitle'],
    about: ['page.about.title', 'page.about.subtitle'],
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
    if (window.app) app.expandActiveSection(page);
    // Title
    const [titleKey, subKey] = this.titles[page] || [page, ''];
    const title = t(titleKey);
    const sub = t(subKey);
    const tEl = document.getElementById('page-title');
    const sEl = document.getElementById('page-subtitle');
    if (tEl) tEl.textContent = title;
    if (sEl) sEl.textContent = sub;
    // Close mobile sidebar
    document.body.classList.remove('sidebar-open');
  },
};

window.addEventListener('hashchange', () => router.resolve());
