const api = {
  async request(path, method = 'GET', body = null) {
    const opts = { method, headers: {} };
    if (body) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    try {
      const res = await fetch(path, opts);
      if (!res.ok) {
        const text = await res.text().catch(() => '');
        throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
      }
      return res.json();
    } catch (err) {
      console.error('API error', path, err);
      throw err;
    }
  },

  snapshot() { return this.request('/api/snapshot'); },
  events(since = 0) { return this.request(`/api/events?since=${since}`); },
  proxyStatus() { return this.request('/api/proxy/status'); },
  proxyAlive() { return this.request('/api/proxy/alive'); },
  huntStart() { return this.request('/api/hunt/start', 'POST'); },
  huntStop() { return this.request('/api/hunt/stop', 'POST'); },
  huntPause() { return this.request('/api/hunt/pause', 'POST'); },
  huntResume() { return this.request('/api/hunt/resume', 'POST'); },
  proxyStart(port) { return this.request(`/api/proxy/start?port=${port}`, 'POST'); },
  proxyStop() { return this.request('/api/proxy/stop', 'POST'); },
  proxySelect(addr) { return this.request(`/api/proxy/select?address=${encodeURIComponent(addr || '')}`, 'POST'); },
  proxyNext() { return this.request('/api/proxy/next', 'POST'); },
  proxyRecheck(addr) { return this.request(`/api/proxy/recheck?address=${encodeURIComponent(addr)}`, 'POST'); },
  toggleDirect(on) { return this.request(`/api/proxy/direct?on=${on}`, 'POST'); },
  socks5Status() { return this.request('/api/socks5/status'); },
  socks5Start(port) { return this.request(`/api/socks5/start?port=${port}`, 'POST'); },
  socks5Stop() { return this.request('/api/socks5/stop', 'POST'); },
  blAdd(addr, reason) { return this.request('/api/blacklist/add', 'POST', { address: addr, reason }); },
  blRemove(addr) { return this.request('/api/blacklist/remove', 'POST', { address: addr }); },
  setCountry(code) { return this.request(`/api/settings/country_filter?code=${encodeURIComponent(code)}`, 'POST'); },

  // New endpoints (Phase 1+)
  countries() { return this.request('/api/countries'); },
  system() { return this.request('/api/system'); },
  activity(limit = 10) { return this.request(`/api/activity?limit=${limit}`); },
  actions(limit = 100) { return this.request(`/api/actions?limit=${limit}`); },
  history(last = '1h') { return this.request(`/api/history?last=${last}`); },
  proxies(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/api/proxies?${q}`);
  },
  proxyDetail(addr) { return this.request(`/api/proxy/${encodeURIComponent(addr)}`); },
  blacklist(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/api/blacklist?${q}`);
  },
  settings() { return this.request('/api/settings'); },
  saveSettings(body) { return this.request('/api/settings', 'POST', body); },
  logs(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/api/logs?${q}`);
  },
  clearDead() { return this.request('/api/clear_dead', 'POST'); },
  exportProxies() { return this.request('/api/export', 'POST'); },
  importProxies(body) { return this.request('/api/import', 'POST', body); },
  healthStart() { return this.request('/api/health/start', 'POST'); },
  traffic() { return this.request('/api/traffic'); },
  trafficLive() { return this.request('/api/traffic/live'); },
  requests() { return this.request('/api/requests'); },
  clients() { return this.request('/api/clients'); },
  domains() { return this.request('/api/domains'); },
  errors() { return this.request('/api/errors'); },
  bandwidth() { return this.request('/api/bandwidth'); },

  // Routing & Domain Lists
  routingStatus() { return this.request('/api/routing/status'); },
  routingEnable() { return this.request('/api/routing/enable', 'POST'); },
  routingDisable() { return this.request('/api/routing/disable', 'POST'); },
  routingSetDefault(route) { return this.request('/api/routing/default', 'POST', { default_route: route }); },
  routingReorder(listIds) { return this.request('/api/routing/reorder', 'POST', { order: listIds }); },
  routingTest(domain) { return this.request('/api/routing/test', 'POST', { domain }); },

  domainLists() { return this.request('/api/domain-lists'); },
  domainListGet(id) { return this.request(`/api/domain-lists/${encodeURIComponent(id)}`); },
  domainListCreate(data) { return this.request('/api/domain-lists', 'POST', data); },
  domainListUpdate(id, data) { return this.request(`/api/domain-lists/${encodeURIComponent(id)}`, 'POST', data); },
  domainListDelete(id) { return this.request(`/api/domain-lists/${encodeURIComponent(id)}`, 'DELETE'); },
  domainListToggle(id) { return this.request(`/api/domain-lists/${encodeURIComponent(id)}/toggle`, 'POST'); },

  // Proxy Sources
  proxySources() { return this.request('/api/proxy-sources'); },
  proxySourceGet(id) { return this.request(`/api/proxy-sources/${encodeURIComponent(id)}`); },
  proxySourceCreate(data) { return this.request('/api/proxy-sources', 'POST', data); },
  proxySourceUpdate(id, data) { return this.request(`/api/proxy-sources/${encodeURIComponent(id)}`, 'POST', data); },
  proxySourceDelete(id) { return this.request(`/api/proxy-sources/${encodeURIComponent(id)}`, 'DELETE'); },
  proxySourceToggle(id) { return this.request(`/api/proxy-sources/${encodeURIComponent(id)}/toggle`, 'POST'); },
  proxySourcesFetch() { return this.request('/api/proxy-sources/fetch', 'POST'); },

  // IP Blacklist Sources
  ipBlacklistSources() { return this.request('/api/ip-blacklists'); },
  ipBlacklistGet(id) { return this.request(`/api/ip-blacklists/${encodeURIComponent(id)}`); },
  ipBlacklistCreate(data) { return this.request('/api/ip-blacklists', 'POST', data); },
  ipBlacklistUpdate(id, data) { return this.request(`/api/ip-blacklists/${encodeURIComponent(id)}`, 'POST', data); },
  ipBlacklistDelete(id) { return this.request(`/api/ip-blacklists/${encodeURIComponent(id)}`, 'DELETE'); },
  ipBlacklistToggle(id) { return this.request(`/api/ip-blacklists/${encodeURIComponent(id)}/toggle`, 'POST'); },
  ipBlacklistFetch() { return this.request('/api/ip-blacklists/fetch', 'POST'); },
  ipBlacklistEntries(params = {}) {
    const q = new URLSearchParams(params).toString();
    return this.request(`/api/ip-blacklist/entries?${q}`);
  },
  ipBlacklistMatches() { return this.request('/api/ip-blacklist/matches'); },

  // Custom Proxies
  customProxies() { return this.request('/api/custom-proxies'); },
  customProxyGet(id) { return this.request(`/api/custom-proxies/${encodeURIComponent(id)}`); },
  customProxyCreate(data) { return this.request('/api/custom-proxies', 'POST', data); },
  customProxyUpdate(id, data) { return this.request(`/api/custom-proxies/${encodeURIComponent(id)}`, 'POST', data); },
  customProxyDelete(id) { return this.request(`/api/custom-proxies/${encodeURIComponent(id)}`, 'DELETE'); },
  customProxyToggle(id) { return this.request(`/api/custom-proxies/${encodeURIComponent(id)}/toggle`, 'POST'); },
  customProxyTest(id) { return this.request(`/api/custom-proxies/${encodeURIComponent(id)}/test`, 'POST'); },
  customProxyTestDirect(data) { return this.request('/api/custom-proxies/test-direct', 'POST', data); },

  // Canary / Internet Connectivity
  canaryStatus() { return this.request('/api/canary/status'); },
  canaryHistory(hours = 24) { return this.request(`/api/canary/history?hours=${hours}`); },
  canarySetHosts(hosts) { return this.request('/api/canary/hosts', 'POST', { canary_hosts: hosts }); },

  // Downloads & Backup
  downloadCounts() { return this.request('/api/downloads/count'); },
  backupGroups() { return this.request('/api/backup/groups'); },
  async createBackup(groups) {
    const res = await fetch('/api/backup', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ groups }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.blob();
  },
  restoreBackup(groups, data) { return this.request('/api/restore', 'POST', { groups, data }); },
};
