router.register('proxies', (container) => {
  let groupBy = 'country';
  let statusFilter = 'alive';
  let search = '';
  let groups = [];
  let totalCount = 0;
  let _loading = false;
  let expandedKeys = {};
  let loadedKeys = {};

  let _built = false;

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '8px';
    container.style.minHeight = '0';
    container.style.flex = '1';
    container.style.overflow = 'hidden';

    const toolbar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });

    const groupTabs = ui.el('div', '', { id: 'group-tabs', style: 'display:flex;gap:0;border:1px solid var(--border);border-radius:var(--radius-xs);overflow:hidden' });
    const gBtn = (label, mode) => {
      const b = ui.el('button', '', { text: label, 'data-mode': mode, style: `padding:5px 12px;font-size:12px;border:none;cursor:pointer` });
      b.addEventListener('click', () => { groupBy = mode; expandedKeys = {}; loadedKeys = {}; _built = false; updateTabs(); load(); });
      return b;
    };
    groupTabs.appendChild(gBtn(t('page.proxies.byCountry'), 'country'));
    groupTabs.appendChild(gBtn(t('page.proxies.bySource'), 'source'));
    groupTabs.appendChild(gBtn(t('page.proxies.byProtocol'), 'protocol'));
    toolbar.appendChild(groupTabs);

    const statusTabs = ui.el('div', '', { id: 'status-tabs', style: 'display:flex;gap:0;border:1px solid var(--border);border-radius:var(--radius-xs);overflow:hidden' });
    const sBtn = (label, val) => {
      const b = ui.el('button', '', { text: label, 'data-val': val, style: `padding:5px 10px;font-size:12px;border:none;cursor:pointer` });
      b.addEventListener('click', () => { statusFilter = val; expandedKeys = {}; loadedKeys = {}; _built = false; updateTabs(); load(); });
      return b;
    };
    statusTabs.appendChild(sBtn(t('page.proxies.all'), ''));
    statusTabs.appendChild(sBtn(t('page.proxies.alive'), 'alive'));
    statusTabs.appendChild(sBtn(t('page.proxies.dead'), 'dead'));
    toolbar.appendChild(statusTabs);

    const searchInput = ui.el('input', '', { type: 'text', placeholder: t('page.proxies.searchPlaceholder'), value: search, style: 'padding:5px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:200px;flex:1' });
    searchInput.addEventListener('input', (e) => { search = e.target.value.toLowerCase(); renderGroups(); });
    toolbar.appendChild(searchInput);

    toolbar.appendChild(ui.el('div', '', { style: 'flex:1' }));
    const totalLabel = ui.el('div', '', { id: 'proxies-total-label', style: 'font-size:12px;color:var(--text-secondary)' });
    toolbar.appendChild(totalLabel);

    container.appendChild(toolbar);

    const listWrap = ui.el('div', '', { id: 'proxies-group-list', style: 'flex:1;min-height:0;overflow-y:auto;padding-right:4px' });
    container.appendChild(listWrap);
  }

  build();
  updateTabs();

  function updateTabs() {
    const gt = document.getElementById('group-tabs');
    if (gt) gt.querySelectorAll('button').forEach(b => {
      const active = b.dataset.mode === groupBy;
      b.style.background = active ? 'var(--accent)' : 'var(--surface)';
      b.style.color = active ? 'var(--bg)' : 'var(--text-primary)';
    });
    const st = document.getElementById('status-tabs');
    if (st) st.querySelectorAll('button').forEach(b => {
      const active = b.dataset.val === statusFilter;
      b.style.background = active ? 'var(--accent)' : 'var(--surface)';
      b.style.color = active ? 'var(--bg)' : 'var(--text-primary)';
    });
  }

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      const data = await api.proxies({ mode: 'grouped', group_by: groupBy, status: statusFilter });
      groups = data.groups || [];
      totalCount = data.total || 0;
      renderGroups();
    } catch (e) {
      console.error('proxies load', e);
    } finally {
      _loading = false;
    }
  }

  async function loadGroupProxies(key) {
    const body = document.getElementById('spoiler-body-' + key);
    if (!body) return;
    body.innerHTML = `<div style="padding:12px;color:var(--text-muted);font-size:12px">${t('common.loading')}</div>`;
    try {
      const data = await api.proxies({ mode: 'group-proxies', group_by: groupBy, group_key: key, status: statusFilter });
      const proxies = data.proxies || [];
      loadedKeys[key] = proxies;
      renderGroupBody(key, proxies);
    } catch (e) {
      body.innerHTML = `<div style="padding:12px;color:var(--danger);font-size:12px">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    }
  }

  function toggleGroup(key) {
    expandedKeys[key] = !expandedKeys[key];
    const body = document.getElementById('spoiler-body-' + key);
    const chevron = document.getElementById('spoiler-chevron-' + key);
    if (expandedKeys[key]) {
      if (body) body.style.display = 'block';
      if (chevron) chevron.textContent = '▼';
      if (!loadedKeys[key]) {
        loadGroupProxies(key);
      }
    } else {
      if (body) body.style.display = 'none';
      if (chevron) chevron.textContent = '▶';
    }
  }

  function pctBar(pct) {
    const color = pct >= 50 ? 'var(--success)' : pct >= 20 ? 'var(--warning)' : 'var(--danger)';
    return `<div style="display:inline-block;width:40px;height:6px;background:var(--border);border-radius:3px;vertical-align:middle;margin-left:6px"><div style="width:${pct}%;height:100%;background:${color};border-radius:3px"></div></div>`;
  }

  function renderProxyRow(p) {
    const statusColor = p.in_blacklist ? 'var(--danger)' : p.last_status === 'ok' ? 'var(--success)' : 'var(--danger)';
    const statusText = p.in_blacklist ? 'BL' : p.last_status === 'ok' ? 'OK' : 'FAIL';
    const proto = (p.protocol || 'http').toUpperCase();
    const lat = p.last_latency != null ? (p.last_latency < 1 ? (p.last_latency * 1000).toFixed(0) + 'ms' : p.last_latency.toFixed(2) + 's') : '—';
    const avg = p.latency_avg != null ? (p.latency_avg < 1 ? (p.latency_avg * 1000).toFixed(0) + 'ms' : p.latency_avg.toFixed(2) + 's') : '—';
    const speed = p.speed_avg ? p.speed_avg.toFixed(0) + 'KB/s' : '—';
    const succ = p.success_rate != null ? (p.success_rate * 100).toFixed(0) + '%' : '—';
    const up = (p.checks_ok || 0) + '/' + (p.checks_total || 0);
    const score = Math.round(p.score || 0);
    const flag = ui.flag(p.country_code);

    return [
      `<span style="font-size:12px;font-family:monospace;color:var(--text-primary)">${ui.escHtml(p.address)}</span>`,
      `<span style="font-size:12px">${flag} ${ui.escHtml(p.country || '—')}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${proto}</span>`,
      `<span style="font-size:11px">${lat}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${avg}</span>`,
      `<span style="font-size:11px">${speed}</span>`,
      `<span style="font-size:11px">${succ}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${up}</span>`,
      `<span style="font-size:11px;font-weight:600">${score}</span>`,
      `<span style="color:${statusColor};font-weight:600;font-size:11px">${statusText}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${ui.ago(p.last_check)}</span>`,
      `<button class="btn btn-xs btn-secondary" data-select-addr="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px" title="Use as upstream">Sel</button>`,
      `<button class="btn btn-xs btn-info" data-recheck-addr="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px;color:var(--info);border-color:var(--info)" title="Recheck proxy">↻</button>`,
      `<button class="btn btn-xs btn-danger" data-bl-addr="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px">BL</button>`,
    ];
  }

  function renderGroupBody(key, proxies) {
    const body = document.getElementById('spoiler-body-' + key);
    if (!body) return;
    body.innerHTML = '';

    let filtered = proxies;
    if (search) {
      filtered = proxies.filter(p =>
        (p.address || '').toLowerCase().includes(search) ||
        (p.country || '').toLowerCase().includes(search) ||
        (p.protocol || '').toLowerCase().includes(search)
      );
    }

    if (!filtered.length) {
      body.innerHTML = `<div style="padding:8px;color:var(--text-muted);font-size:12px">${t('page.proxies.noMatching')}</div>`;
      return;
    }

    const sorted = filtered.slice().sort((a, b) => (b.score || 0) - (a.score || 0));
    const tblWrap = ui.el('div', 'table-wrap', { style: 'max-height:400px;overflow-y:auto' });
    const headers = [
      { label: 'Proxy', width: null },
      { label: 'Country', width: '110px' },
      { label: 'Proto', width: '50px', align: 'center' },
      { label: 'Lat', width: '50px', align: 'right' },
      { label: 'Avg', width: '50px', align: 'right' },
      { label: 'Speed', width: '55px', align: 'right' },
      { label: 'Succ', width: '40px', align: 'right' },
      { label: 'Up', width: '45px', align: 'right' },
      { label: 'Score', width: '40px', align: 'right' },
      { label: 'Status', width: '45px', align: 'center' },
      { label: 'Last', width: '55px', align: 'right' },
      { label: '', width: '28px', align: 'center' },
      { label: '', width: '28px', align: 'center' },
      { label: '', width: '28px', align: 'center' },
    ];
    const rows = sorted.map(p => renderProxyRow(p));
    tblWrap.appendChild(ui.table(headers, rows));
    body.appendChild(tblWrap);

    body.querySelectorAll('[data-bl-addr]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.blAddr;
        if (addr) blAdd(addr);
      });
    });

    body.querySelectorAll('[data-select-addr]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.selectAddr;
        if (addr) api.proxySelect(addr).then(() => app.toast(t('page.proxyPool.selected', {addr: addr}))).catch(er => app.toast(t('common.error', {message: er.message}), 'error'));
      });
    });

    body.querySelectorAll('[data-recheck-addr]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.recheckAddr;
        if (!addr) return;
        btn.disabled = true;
        btn.textContent = '...';
        api.proxyRecheck(addr).then(() => {
          btn.disabled = false;
          btn.textContent = '↻';
          app.toast(t('page.proxies.recheckComplete'));
          loadGroupProxies(key);
        }).catch(er => {
          btn.disabled = false;
          btn.textContent = '↻';
          app.toast(t('common.error', {message: er.message}), 'error');
        });
      });
    });
  }

  function renderGroups() {
    const totalLabel = document.getElementById('proxies-total-label');
    if (totalLabel) totalLabel.textContent = t('page.proxies.totalProxies', {count: totalCount});

    const listWrap = document.getElementById('proxies-group-list');
    if (!listWrap) return;

    let filtered = groups;
    if (search) {
      filtered = groups.filter(g => g.label.toLowerCase().includes(search));
    }

    if (!filtered.length) {
      listWrap.innerHTML = '';
      listWrap.appendChild(ui.el('div', 'empty', { text: t('page.proxies.noProxiesFound') }));
      _built = false;
      return;
    }

    const existingKeys = new Set();
    listWrap.querySelectorAll('[data-group-key]').forEach(el => existingKeys.add(el.dataset.groupKey));

    const filteredKeys = new Set(filtered.map(g => g.key));

    if (_built && existingKeys.size === filteredKeys.size && filtered.every(g => existingKeys.has(g.key))) {
      filtered.forEach(g => updateGroupHeader(g));
      return;
    }

    _built = true;
    listWrap.innerHTML = '';

    filtered.forEach(g => {
      const isExpanded = !!expandedKeys[g.key];
      const spoiler = ui.el('div', '', { style: 'border:1px solid var(--border);border-radius:var(--radius-xs);overflow:hidden;margin-bottom:6px', 'data-group-key': g.key });

      const header = ui.el('div', '', {
        id: 'spoiler-header-' + g.key,
        style: `display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;background:var(--surface);user-select:none;transition:background 0.15s`
      });
      header.addEventListener('mouseenter', () => header.style.background = 'var(--surface-raised)');
      header.addEventListener('mouseleave', () => header.style.background = 'var(--surface)');
      header.addEventListener('click', () => toggleGroup(g.key));

      const chevron = ui.el('span', '', { id: 'spoiler-chevron-' + g.key, text: isExpanded ? '▼' : '▶', style: 'font-size:10px;color:var(--text-muted);width:14px;flex-shrink:0' });
      header.appendChild(chevron);

      const label = ui.el('span', '', { html: g.label, style: 'font-size:13px;font-weight:500;color:var(--text-primary);flex-shrink:0;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' });
      header.appendChild(label);

      const countBadge = ui.el('span', '', { id: 'spoiler-count-' + g.key, html: countHtml(g), style: 'font-size:12px;flex-shrink:0' });
      header.appendChild(countBadge);

      const pctLabel = ui.el('span', '', { id: 'spoiler-pct-' + g.key, html: pctHtml(g), style: 'flex-shrink:0' });
      header.appendChild(pctLabel);

      header.appendChild(ui.el('div', '', { style: 'flex:1' }));

      const deadLabel = ui.el('span', '', { id: 'spoiler-dead-' + g.key, html: deadHtml(g), style: 'flex-shrink:0' });
      header.appendChild(deadLabel);

      spoiler.appendChild(header);

      const body = ui.el('div', '', {
        id: 'spoiler-body-' + g.key,
        style: `display:${isExpanded ? 'block' : 'none'};border-top:1px solid var(--border)`
      });

      if (isExpanded && loadedKeys[g.key]) {
        renderGroupBody(g.key, loadedKeys[g.key]);
      } else if (isExpanded) {
        body.innerHTML = `<div style="padding:12px;color:var(--text-muted);font-size:12px">${t('common.loading')}</div>`;
      }

      spoiler.appendChild(body);
      listWrap.appendChild(spoiler);
    });
  }

  function countHtml(g) {
    return `<span style="color:var(--success);font-weight:600">${g.alive}</span><span style="color:var(--text-muted)">/</span><span style="color:var(--text-primary)">${g.total}</span>`;
  }

  function pctHtml(g) {
    const color = g.alive_pct >= 50 ? 'var(--success)' : g.alive_pct >= 20 ? 'var(--warning)' : 'var(--danger)';
    return `<span style="color:${color};font-weight:600;font-size:12px">${g.alive_pct}%</span>${pctBar(g.alive_pct)}`;
  }

  function deadHtml(g) {
    return `<span style="color:var(--danger);font-size:11px">${t('page.proxies.deadCount', {count: g.dead})}</span>`;
  }

  function updateGroupHeader(g) {
    const count = document.getElementById('spoiler-count-' + g.key);
    const pct = document.getElementById('spoiler-pct-' + g.key);
    const dead = document.getElementById('spoiler-dead-' + g.key);
    if (count) count.innerHTML = countHtml(g);
    if (pct) pct.innerHTML = pctHtml(g);
    if (dead) dead.innerHTML = deadHtml(g);
  }

  async function blAdd(addr) {
    try {
      await api.blAdd(addr, 'manual');
      app.toast(t('page.proxies.addedToBlacklist'));
    } catch (e) {
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  load();
  const id = setInterval(load, 15000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
