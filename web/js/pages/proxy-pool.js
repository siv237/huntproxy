router.register('proxy-pool', (container) => {
  let state = {
    proxies: [],
    selected: null,
    proxySortKey: 'score',
    proxySortDir: -1,
    hideNoHttps: true,
    hideMitm: true,
  };

  function setProxySort(key) {
    if (state.proxySortKey === key) state.proxySortDir *= -1;
    else { state.proxySortKey = key; state.proxySortDir = -1; }
    load();
  }

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const row1 = ui.el('div', 'grid grid-2 row-stretch');
    row1.appendChild(buildProxyControlCard());
    row1.appendChild(buildSelectedProxyCard());
    container.appendChild(row1);

    const row2 = ui.el('div', 'grid grid-2 row-stretch');
    row2.appendChild(buildSelectProxyCard());
    row2.appendChild(buildClientLogCard());
    container.appendChild(row2);
  }

  function buildProxyControlCard() {
    const card = ui.el('div', 'card');
    card.id = 'proxy-control-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Proxy Server', style: 'margin-bottom:8px' }));

    // Status bar
    const status = ui.el('div', '', { id: 'proxy-status-bar', style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:8px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)' });
    status.innerHTML = '<span id="proxy-dot" style="width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0"></span><span id="proxy-status-text">stopped</span>';
    card.appendChild(status);

    // Port + Start/Stop
    const row = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px' });
    row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: 'Port:' }));
    const portInp = ui.el('input', '', { id: 'proxy-port', type: 'number', value: '17277', min: '1024', max: '65535', style: 'width:60px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    row.appendChild(portInp);

    const startBtn = ui.el('button', 'btn btn-xs btn-primary', { text: 'Start', id: 'btn-proxy-start' });
    startBtn.addEventListener('click', () => api.proxyStart(portInp.value).then(() => app.toast('Proxy started')).catch(e => app.toast('Error: ' + e.message, 'error')));
    row.appendChild(startBtn);

    const stopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: 'Stop', id: 'btn-proxy-stop' });
    stopBtn.addEventListener('click', () => api.proxyStop().then(() => app.toast('Proxy stopped')).catch(e => app.toast('Error: ' + e.message, 'error')));
    row.appendChild(stopBtn);
    card.appendChild(row);

    // Direct mode
    const dm = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px;margin-bottom:6px' });
    const dmCb = ui.el('input', '', { id: 'direct-toggle', type: 'checkbox' });
    dmCb.addEventListener('change', () => api.toggleDirect(dmCb.checked).then(() => app.toast(dmCb.checked ? 'Direct mode ON' : 'Direct mode OFF')));
    dm.appendChild(dmCb);
    dm.appendChild(ui.el('span', '', { style: 'font-weight:600', text: 'Direct mode' }));
    dm.appendChild(ui.el('span', '', { style: 'color:var(--text-muted)', text: ' (no upstream)' }));
    card.appendChild(dm);

    // Connections
    const conn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:6px' });
    conn.appendChild(ui.el('span', '', { id: 'proxy-connections', style: 'font-size:18px;font-weight:700;color:var(--accent)', text: '0' }));
    conn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: 'connections' }));
    card.appendChild(conn);
    return card;
  }

  function buildSelectedProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'selected-proxy-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Selected Upstream', style: 'margin-bottom:8px' }));

    const body = ui.el('div', '', { id: 'sel-proxy-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No upstream selected</div>';
    card.appendChild(body);
    return card;
  }

  function buildSelectProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'select-proxy-card';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Select Upstream Proxy' }));
    const count = ui.el('div', '', { id: 'select-count', style: 'font-size:11px;color:var(--text-secondary)', text: '0' });
    header.appendChild(count);
    card.appendChild(header);

    const filterRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-shrink:0' });
    const httpsLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const httpsCb = ui.el('input', '', { id: 'hide-no-https', type: 'checkbox', checked: 'checked' });
    httpsCb.addEventListener('change', () => { state.hideNoHttps = httpsCb.checked; updateSelectProxy(state.proxies); });
    httpsLbl.appendChild(httpsCb);
    httpsLbl.appendChild(ui.el('span', '', { text: 'Hide without HTTPS' }));
    filterRow.appendChild(httpsLbl);
    const mitmLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const mitmCb = ui.el('input', '', { id: 'hide-mitm', type: 'checkbox', checked: 'checked' });
    mitmCb.addEventListener('change', () => { state.hideMitm = mitmCb.checked; updateSelectProxy(state.proxies); });
    mitmLbl.appendChild(mitmCb);
    mitmLbl.appendChild(ui.el('span', '', { text: 'Hide MITM suspects' }));
    filterRow.appendChild(mitmLbl);
    card.appendChild(filterRow);

    const wrap = ui.el('div', '', { id: 'select-proxy-tbl', style: 'flex:1;overflow-y:auto;min-height:0' });
    card.appendChild(wrap);
    return card;
  }

  function buildClientLogCard() {
    const card = ui.el('div', 'card');
    card.id = 'client-log-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Client Log', style: 'margin-bottom:8px' }));

    const log = ui.el('div', '', { id: 'proxy-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow-y:auto;flex:1;min-height:0;color:var(--text-primary)' });
    log.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">proxy not started</div>';
    card.appendChild(log);
    return card;
  }

  build();

  // --- Updaters ---
  function updateProxyControl(ps) {
    const el = id => document.getElementById(id);
    const bar = el('proxy-status-bar');
    const dot = el('proxy-dot');
    const txt = el('proxy-status-text');
    if (ps && ps.running) {
      if (bar) { bar.style.background = 'var(--success-bg)'; bar.style.borderColor = 'var(--success)'; bar.style.color = 'var(--success)'; }
      if (dot) dot.style.background = 'var(--success)';
      if (txt) txt.textContent = 'running on :' + (ps.port || 17277);
    } else {
      if (bar) { bar.style.background = 'var(--surface-raised)'; bar.style.borderColor = 'var(--border)'; bar.style.color = 'var(--text-secondary)'; }
      if (dot) dot.style.background = 'var(--text-muted)';
      if (txt) txt.textContent = 'stopped';
    }
    if (el('btn-proxy-start')) el('btn-proxy-start').disabled = ps && ps.running;
    if (el('btn-proxy-stop')) el('btn-proxy-stop').disabled = !(ps && ps.running);
    if (el('proxy-connections')) el('proxy-connections').textContent = ps ? (ps.connections || 0) : 0;
    if (el('direct-toggle')) el('direct-toggle').checked = !!(ps && ps.direct_mode);
  }

  function updateSelectedProxy(ps) {
    const body = document.getElementById('sel-proxy-body');
    if (!body) return;
    const ap = ps && ps.active_proxy;
    if (!ap || (ps && ps.direct_mode)) {
      body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No upstream selected</div>';
      return;
    }

    const top = ui.el('div', '', { style: 'font-family:monospace;font-size:13px;font-weight:700;color:var(--accent);margin-bottom:4px;word-break:break-all' });
    top.textContent = ap.address;
    body.innerHTML = '';
    body.appendChild(top);

    const badges = ui.el('div', '', { style: 'display:flex;gap:4px;flex-wrap:wrap;margin-bottom:4px' });

    const hasListen = !!(ap.listen_country || ap.listen_city);
    const hasEgress = !!(ap.egress_country || ap.egress_city);
    const diffCountry = hasListen && hasEgress && (ap.listen_country || '') !== (ap.egress_country || '');

    if (diffCountry) {
      badges.appendChild(ui.badge((ui.flag(ap.listen_country_code || ap.country_code) || '') + ' ' + (ap.listen_country || ''), 'blue'));
      badges.appendChild(ui.el('span', '', { style: 'color:var(--accent);font-weight:700', text: '→' }));
      badges.appendChild(ui.badge((ui.flag(ap.egress_country_code || ap.country_code) || '') + ' ' + (ap.egress_country || ''), 'green'));
    } else {
      badges.appendChild(ui.badge((ui.flag(ap.listen_country_code || ap.country_code) || '') + ' ' + (ap.egress_country || ap.country || 'Unknown'), 'blue'));
    }
    badges.appendChild(ui.badge(ap.protocol || 'http', 'gray'));
    body.appendChild(badges);

    const geo = ui.el('div', '', { style: 'font-size:10px;color:var(--text-secondary);line-height:1.5;margin-bottom:6px' });
    let geoHtml = '';
    if (diffCountry) {
      geoHtml += 'server: ' + (ap.listen_country || '') + (ap.listen_city ? ', ' + ap.listen_city : '') + (ap.listen_isp ? ', ' + ap.listen_isp : '') + '<br>';
      geoHtml += 'exit: ' + (ap.egress_country || '') + (ap.egress_city ? ', ' + ap.egress_city : '') + (ap.egress_isp ? ', ' + ap.egress_isp : '') + '<br>';
    } else {
      if (ap.listen_isp) geoHtml += 'isp: ' + ap.listen_isp + '<br>';
    }
    if (ap.egress_ip) geoHtml += 'exit ip: ' + ap.egress_ip;
    geo.innerHTML = geoHtml || '—';
    body.appendChild(geo);

    const stats = ui.el('div', '', { style: 'display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:6px' });
    const items = [
      { l: 'score', v: ap.score ? ap.score.toFixed(0) : '-' },
      { l: 'latency', v: (ap.last_latency || 0).toFixed(2) + 's' },
      { l: 'KB/s', v: (ap.speed_avg || 0).toFixed(0) },
      { l: 'success', v: (ap.success_rate * 100).toFixed(0) + '%' },
      { l: 'checks', v: (ap.checks_ok || 0) + '/' + (ap.checks_total || 0) },
    ];
    items.forEach(item => {
      const cell = ui.el('div', '', { style: 'text-align:center;padding:4px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
      cell.appendChild(ui.el('div', '', { style: 'font-size:10px;color:var(--text-secondary)', text: item.l }));
      cell.appendChild(ui.el('div', '', { style: 'font-size:13px;font-weight:600', text: item.v }));
      stats.appendChild(cell);
    });
    body.appendChild(stats);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:4px' });
    const recheckBtn = ui.el('button', 'btn btn-xs btn-secondary', { text: 'recheck' });
    recheckBtn.addEventListener('click', () => {
      recheckBtn.disabled = true; recheckBtn.textContent = 'checking...';
      api.proxyRecheck(ap.address).then(() => {
        recheckBtn.disabled = false; recheckBtn.textContent = 'recheck';
        app.toast('Recheck complete'); load();
      }).catch(e => { recheckBtn.disabled = false; recheckBtn.textContent = 'recheck'; app.toast('Error: ' + e.message, 'error'); });
    });
    btnRow.appendChild(recheckBtn);

    const clearBtn = ui.el('button', 'btn btn-xs btn-ghost', { text: 'clear selection' });
    clearBtn.addEventListener('click', () => api.proxySelect('').then(() => app.toast('Cleared')).catch(e => app.toast('Error: ' + e.message, 'error')));
    btnRow.appendChild(clearBtn);
    body.appendChild(btnRow);
  }

  function updateProxyLog(ps) {
    const log = document.getElementById('proxy-log');
    if (!log) return;
    if (!ps || !ps.log || !ps.log.length) {
      log.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">proxy not started</div>';
      return;
    }
    log.innerHTML = ps.log.map(e => `<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> ${e.client || '?'} → ${e.target || '?'} [${e.status || ''}]` + (e.upstream && e.upstream !== 'direct' && e.upstream !== '?' ? ` <span style="color:var(--accent)">via ${e.upstream}</span>` : '')).join('<br>');
  }

  function updateSelectProxy(proxies) {
    const wrap = document.getElementById('select-proxy-tbl');
    const count = document.getElementById('select-count');
    if (!wrap) return;

    const sorted = (proxies || []).slice()
      .map(p => { p._diff = (p.listen_country && p.egress_country && p.listen_country !== p.egress_country) ? 1 : 0; p._exit_code = p.egress_country ? ui.flag(p.egress_country.slice(0,2).toUpperCase().replace(/[^A-Z]/g,'')) : ''; return p; })
      .filter(p => (!state.hideNoHttps || p.supports_connect) && (!state.hideMitm || !p.mitm_suspect))
      .sort((a, b) => {
        const key = state.proxySortKey;
        const dir = state.proxySortDir;
        if (key === '_exit') return dir * (a._diff - b._diff || (a.egress_country || '').localeCompare(b.egress_country || ''));
        return ui.sortValue(a, b, key, dir);
      });

    if (count) {
      const tags = [];
      if (state.hideNoHttps) tags.push('HTTPS');
      if (state.hideMitm) tags.push('no-MITM');
      count.textContent = sorted.length + (tags.length ? ' ' + tags.join('+') : ' alive');
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.proxySortKey, state.proxySortDir) : ''), width, align, sortKey: key, onSort: key ? () => setProxySort(key) : undefined });
    const headers = [
      h('#', null, '24px', 'center'),
      h('Proxy', 'address', null, 'left'),
      h('Srv', 'country', '30px', 'center'),
      h('Exit', '_exit', '30px', 'center'),
      h('Lat', 'last_latency', '46px', 'right'),
      h('KB/s', 'speed_avg', '40px', 'right'),
      h('Succ', 'success_rate', '40px', 'right'),
      h('Score', 'score', '40px', 'right'),
      h('Flags', 'supports_connect', '50px', 'center'),
      h('Ok', 'last_ok', '36px', 'right'),
      h('', null, '40px', 'center'),
    ];
    const rows = sorted.map((p, i) => {
      const sc = Math.min(100, Math.max(0, p.score || 0));
      const flags = [];
      if (p.supports_connect) flags.push('<span style="color:var(--success);font-weight:600">HTTPS</span>');
      else flags.push('<span style="color:var(--text-muted)">HTTP</span>');
      if (p.mitm_suspect) flags.push('<span style="color:var(--danger);font-weight:600">MITM!</span>');
      const proto = p.protocol || 'http';
      const isSel = state.selected === p.address;
      const hasDiff = p.listen_country && p.egress_country && p.listen_country !== p.egress_country;
      const srvFlag = ui.flag(p.listen_country_code || p.country_code) || '—';
      const exitFlag = hasDiff ? (ui.flag(p.egress_country_code || p.country_code) || '') : '';
      return [
        `<span style="color:var(--text-muted)">${i+1}</span>`,
        `<span class="addr" style="font-size:10px">${p.address}</span>`,
        srvFlag,
        exitFlag,
        p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
        (p.speed_avg || 0).toFixed(0),
        (p.success_rate * 100).toFixed(0) + '%',
        `<div style="display:inline-block;width:30px;height:4px;background:var(--surface-raised);border-radius:2px;vertical-align:middle;overflow:hidden"><div style="width:${sc}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--info));transition:width 0.4s"></div></div>`,
        `<span style="color:var(--text-muted);font-size:10px">${proto}</span> ${flags.join(' ')}`,
        ui.ago(p.last_ok),
        `<button class="btn btn-xs ${isSel ? 'btn-primary' : 'btn-secondary'}" onclick="selectProxy('${p.address}')" style="padding:1px 4px;font-size:9px">${isSel ? 'Active' : 'Select'}</button>`,
      ];
    });
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  // --- Polling ---
  async function load() {
    try {
      let ps = {}, proxies = [];
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { proxies = await api.proxyAlive(); } catch (e) { console.error('proxyAlive', e); }
      state.selected = ps && ps.active_proxy ? ps.active_proxy.address : null;
      state.proxies = proxies;
      updateProxyControl(ps);
      updateSelectedProxy(ps);
      updateProxyLog(ps);
      updateSelectProxy(proxies);
    } catch (e) {
      console.error('proxy-pool poll', e);
    }
  }

  window.selectProxy = async function(addr) {
    try {
      await api.proxySelect(addr);
      app.toast(addr ? `Selected ${addr}` : 'Direct mode');
      state.selected = addr || null;
      load();
    } catch (e) {
      app.toast('Error: ' + e.message, 'error');
    }
  };

  load();
  const id = setInterval(load, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
