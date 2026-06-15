router.register('proxy-pool', (container) => {
  let state = {
    proxies: [],
    selected: null,
    proxySortKey: 'score',
    proxySortDir: -1,
    hideNoHttps: true,
    hideNoSsl: false,
    hideMitm: true,
    hideBlacklisted: false,
    groupByProtocol: true,
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
    row1.style.flex = '1';
    row1.appendChild(buildProxyControlCard());
    row1.appendChild(buildSelectedProxyCard());
    container.appendChild(row1);

    const row2 = ui.el('div', 'grid grid-2 row-stretch');
    row2.style.flex = '2';
    row2.appendChild(buildSelectProxyCard());
    row2.appendChild(buildClientLogCard());
    container.appendChild(row2);
  }

  function buildProxyControlCard() {
    const card = ui.el('div', 'card');
    card.id = 'proxy-control-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.proxyPool.proxyServer'), style: 'margin-bottom:8px' }));

    const status = ui.el('div', '', { id: 'proxy-status-bar', style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:8px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)' });
    status.innerHTML = `<span id="proxy-dot" style="width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0"></span><span id="proxy-status-text">${t('page.proxyPool.stopped')}</span>`;
    card.appendChild(status);

    // HTTP row
    const httpRow = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px' });
    httpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:52px;flex-shrink:0', text: t('page.proxyPool.http') }));
    httpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.proxyPool.port') }));
    const portInp = ui.el('input', '', { id: 'proxy-port', type: 'number', value: '17277', min: '1024', max: '65535', style: 'width:72px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    httpRow.appendChild(portInp);
    const startBtn = ui.el('button', 'btn btn-xs btn-primary', { text: 'Start', id: 'btn-proxy-start' });
    startBtn.addEventListener('click', () => api.proxyStart(portInp.value).then(() => app.toast(t('page.proxyPool.proxyStarted'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    httpRow.appendChild(startBtn);
    const stopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.proxyPool.stop'), id: 'btn-proxy-stop' });
    stopBtn.addEventListener('click', () => api.proxyStop().then(() => app.toast(t('page.proxyPool.proxyStopped'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    httpRow.appendChild(stopBtn);
    card.appendChild(httpRow);

    // SOCKS5 row
    const s5Row = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px;padding-top:6px;border-top:1px solid var(--border-subtle)' });
    s5Row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:52px;flex-shrink:0', text: t('page.proxyPool.socks5') }));
    s5Row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.proxyPool.port') }));
    const s5PortInp = ui.el('input', '', { id: 'socks5-port', type: 'number', value: '17278', min: '1024', max: '65535', style: 'width:72px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    s5Row.appendChild(s5PortInp);
    const s5StartBtn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.proxyPool.start'), id: 'btn-socks5-start' });
    s5StartBtn.addEventListener('click', () => api.socks5Start(s5PortInp.value).then(() => app.toast(t('page.proxyPool.socks5Started'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    s5Row.appendChild(s5StartBtn);
    const s5StopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.proxyPool.stop'), id: 'btn-socks5-stop' });
    s5StopBtn.addEventListener('click', () => api.socks5Stop().then(() => app.toast(t('page.proxyPool.socks5Stopped'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    s5Row.appendChild(s5StopBtn);
    card.appendChild(s5Row);

    // Connections per protocol
    const connRow = ui.el('div', '', { style: 'display:flex;gap:12px;align-items:baseline' });
    const httpConn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
    httpConn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.proxyPool.http') }));
    httpConn.appendChild(ui.el('span', '', { id: 'proxy-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
    connRow.appendChild(httpConn);
    const s5Conn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
    s5Conn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.proxyPool.socks5') }));
    s5Conn.appendChild(ui.el('span', '', { id: 'socks5-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
    connRow.appendChild(s5Conn);
    card.appendChild(connRow);
    return card;
  }

  function buildSelectedProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'selected-proxy-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.proxyPool.selectedUpstream'), style: 'margin-bottom:8px' }));

    const dm = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px;margin-bottom:6px' });
    const dmCb = ui.el('input', '', { id: 'direct-toggle', type: 'checkbox' });
    dmCb.addEventListener('change', () => api.toggleDirect(dmCb.checked).then(() => app.toast(dmCb.checked ? t('page.proxyPool.directModeOn') : t('page.proxyPool.directModeOff'))));
    dm.appendChild(dmCb);
    dm.appendChild(ui.el('span', '', { style: 'font-weight:600', text: t('page.proxyPool.directMode') }));
    dm.appendChild(ui.el('span', '', { style: 'color:var(--text-muted)', text: t('page.proxyPool.noUpstream') }));
    card.appendChild(dm);

    const body = ui.el('div', '', { id: 'sel-proxy-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No upstream selected</div>';
    card.appendChild(body);
    return card;
  }

  function buildSelectProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'select-proxy-card';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyPool.selectUpstreamProxy') }));
    const count = ui.el('div', '', { id: 'select-count', style: 'font-size:11px;color:var(--text-secondary)', text: '0' });
    header.appendChild(count);
    card.appendChild(header);

    const filterRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-shrink:0;flex-wrap:wrap' });
    const httpsLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const httpsCb = ui.el('input', '', { id: 'hide-no-https', type: 'checkbox', checked: 'checked' });
    httpsCb.addEventListener('change', () => { state.hideNoHttps = httpsCb.checked; updateSelectProxy(state.proxies); });
    httpsLbl.appendChild(httpsCb);
    httpsLbl.appendChild(ui.el('span', '', { text: t('page.proxyPool.hideNoHttps') }));
    filterRow.appendChild(httpsLbl);
    const sslLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const sslCb = ui.el('input', '', { id: 'hide-no-ssl', type: 'checkbox' });
    sslCb.addEventListener('change', () => { state.hideNoSsl = sslCb.checked; updateSelectProxy(state.proxies); });
    sslLbl.appendChild(sslCb);
    sslLbl.appendChild(ui.el('span', '', { text: 'SSL only' }));
    filterRow.appendChild(sslLbl);
    const mitmLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const mitmCb = ui.el('input', '', { id: 'hide-mitm', type: 'checkbox', checked: 'checked' });
    mitmCb.addEventListener('change', () => { state.hideMitm = mitmCb.checked; updateSelectProxy(state.proxies); });
    mitmLbl.appendChild(mitmCb);
    mitmLbl.appendChild(ui.el('span', '', { text: t('page.proxyPool.hideMitm') }));
    filterRow.appendChild(mitmLbl);
    const grpLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const grpCb = ui.el('input', '', { id: 'group-by-proto', type: 'checkbox', checked: 'checked' });
    grpCb.addEventListener('change', () => { state.groupByProtocol = grpCb.checked; updateSelectProxy(state.proxies); });
    grpLbl.appendChild(grpCb);
    grpLbl.appendChild(ui.el('span', '', { text: t('page.proxyPool.groupByProtocol') }));
    filterRow.appendChild(grpLbl);
    const blLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const blCb = ui.el('input', '', { id: 'hide-blacklisted', type: 'checkbox', checked: 'checked' });
    blCb.addEventListener('change', () => { state.hideBlacklisted = blCb.checked; updateSelectProxy(state.proxies); });
    blLbl.appendChild(blCb);
    blLbl.appendChild(ui.el('span', '', { text: t('page.proxyPool.hideBlacklisted') }));
    filterRow.appendChild(blLbl);
    card.appendChild(filterRow);

    const wrap = ui.el('div', '', { id: 'select-proxy-tbl', style: 'flex:1;overflow-y:auto;min-height:0' });
    card.appendChild(wrap);
    return card;
  }

  function buildClientLogCard() {
    const card = ui.el('div', 'card');
    card.id = 'client-log-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.proxyPool.clientLog'), style: 'margin-bottom:8px' }));

    const log = ui.el('div', '', { id: 'proxy-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow-y:auto;flex:1;min-height:0;color:var(--text-primary)' });
    log.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxyPool.proxyNotStarted')}</div>`;
    card.appendChild(log);
    return card;
  }

  build();

  // --- Updaters ---
  function updateProxyControl(ps, ss) {
    const el = id => document.getElementById(id);
    const bar = el('proxy-status-bar');
    const dot = el('proxy-dot');
    const txt = el('proxy-status-text');
    const httpRunning = ps && ps.running;
    const s5Running = ss && ss.running;
    const anyRunning = httpRunning || s5Running;

    if (anyRunning) {
      if (bar) { bar.style.background = 'var(--success-bg)'; bar.style.borderColor = 'var(--success)'; bar.style.color = 'var(--success)'; }
      if (dot) dot.style.background = 'var(--success)';
      const parts = [];
      if (httpRunning) parts.push('HTTP:' + (ps.port || 17277));
      if (s5Running) parts.push('SOCKS5:' + (ss.port || 17278));
      if (txt) txt.textContent = t('page.proxyPool.running') + ' ' + parts.join(', ');
    } else {
      if (bar) { bar.style.background = 'var(--surface-raised)'; bar.style.borderColor = 'var(--border)'; bar.style.color = 'var(--text-secondary)'; }
      if (dot) dot.style.background = 'var(--text-muted)';
      if (txt) txt.textContent = t('page.proxyPool.stopped');
    }
    if (el('btn-proxy-start')) el('btn-proxy-start').disabled = httpRunning;
    if (el('btn-proxy-stop')) el('btn-proxy-stop').disabled = !httpRunning;
    if (el('proxy-port') && ps && ps.port) el('proxy-port').value = ps.port;
    if (el('btn-socks5-start')) el('btn-socks5-start').disabled = s5Running;
    if (el('btn-socks5-stop')) el('btn-socks5-stop').disabled = !s5Running;
    if (el('socks5-port') && ss && ss.port) el('socks5-port').value = ss.port;
    const httpConn = ps ? (ps.connections || 0) : 0;
    const s5Conn = ss ? (ss.connections || 0) : 0;
    if (el('proxy-connections')) el('proxy-connections').textContent = httpConn;
    if (el('socks5-connections')) el('socks5-connections').textContent = s5Conn;
    if (el('direct-toggle')) el('direct-toggle').checked = !!(ps && ps.direct_mode);
  }

  function updateSelectedProxy(ps) {
    const body = document.getElementById('sel-proxy-body');
    if (!body) return;
    const ap = ps && ps.active_proxy;
    if (!ap || (ps && ps.direct_mode)) {
      body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxyPool.noUpstreamSelected')}</div>`;
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
      badges.appendChild(ui.badge((ui.flag(ap.listen_country_code || ap.country_code) || '') + ' ' + (ap.egress_country || ap.country || t('page.proxyPool.unknown')), 'blue'));
    }
    badges.appendChild(ui.badge(ap.protocol || 'http', 'gray'));
    if (ap.ssl_supported) badges.appendChild(ui.badge('SSL', 'cyan'));
    if (ap.in_blacklist) {
      const hits = ap.ip_blacklist_hits > 0 ? `×${ap.ip_blacklist_hits}` : '';
      badges.appendChild(ui.badge(`BL${hits}`, 'red'));
    }
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
    const recheckBtn = ui.el('button', 'btn btn-xs btn-secondary', { text: t('page.proxyPool.recheck') });
    recheckBtn.addEventListener('click', () => {
      recheckBtn.disabled = true; recheckBtn.textContent = t('page.proxyPool.checking');
      api.proxyRecheck(ap.address).then(() => {
        recheckBtn.disabled = false; recheckBtn.textContent = t('page.proxyPool.recheck');
        app.toast(t('page.proxyPool.recheckComplete')); load();
      }).catch(e => { recheckBtn.disabled = false; recheckBtn.textContent = t('page.proxyPool.recheck'); app.toast(t('common.error', {message: e.message}), 'error'); });
    });
    btnRow.appendChild(recheckBtn);

    const clearBtn = ui.el('button', 'btn btn-xs btn-ghost', { text: t('page.proxyPool.clearSelection') });
    clearBtn.addEventListener('click', () => api.proxySelect('').then(() => app.toast(t('page.proxyPool.cleared'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    btnRow.appendChild(clearBtn);
    body.appendChild(btnRow);
  }

  function updateProxyLog(ps, ss) {
    const log = document.getElementById('proxy-log');
    if (!log) return;
    const httpLog = (ps && ps.log) || [];
    const s5Log = (ss && ss.log) || [];
    const all = [...httpLog.map(e => ({...e, type: 'HTTP'})), ...s5Log.map(e => ({...e, type: 'SOCKS5'}))]
      .sort((a, b) => (b.ts || 0) - (a.ts || 0))
      .slice(0, 50);
    if (!all.length) {
      log.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxyPool.proxyNotStarted')}</div>`;
      return;
    }
    const fmtTarget = t => {
      if (!t || t === '?') return '?';
      const m = t.match(/^(https?:\/\/)?([^\/:]+)(.*)/);
      if (!m) return t;
      return (m[1] || '') + '<b>' + m[2] + '</b>' + (m[3] || '');
    };
    log.innerHTML = all.map(e => `<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> <span style="color:var(--accent);font-size:10px">${e.type}</span> ${e.client || '?'} → ${fmtTarget(e.target)} [${e.status || ''}]` + (e.upstream && e.upstream !== 'direct' && e.upstream !== '?' ? ` <span style="color:var(--accent)">via ${e.upstream}</span>` : '')).join('<br>');
  }

  function proxyProtoGroup(p) {
    const proto = (p.protocol || 'http').toLowerCase();
    if (proto === 'socks5') return 'SOCKS5';
    if (proto === 'socks4') return 'SOCKS4';
    if (p.supports_connect) return 'HTTPS';
    return 'HTTP';
  }

  const PROTO_GROUP_ORDER = ['HTTP', 'HTTPS', 'SOCKS4', 'SOCKS5'];
  const PROTO_GROUP_COLORS = {
    HTTP: 'var(--info)',
    HTTPS: '#8b5cf6',
    SOCKS4: 'var(--accent)',
    SOCKS5: 'var(--success)',
  };

  function updateSelectProxy(proxies) {
    const wrap = document.getElementById('select-proxy-tbl');
    const count = document.getElementById('select-count');
    if (!wrap) return;

    const sorted = (proxies || []).slice()
      .map(p => { p._diff = (p.listen_country && p.egress_country && p.listen_country !== p.egress_country) ? 1 : 0; p._exit_code = p.egress_country ? ui.flag(p.egress_country.slice(0,2).toUpperCase().replace(/[^A-Z]/g,'')) : ''; p._protoGroup = proxyProtoGroup(p); return p; })
      .filter(p => (!state.hideNoHttps || p.supports_connect) && (!state.hideNoSsl || p.ssl_supported) && (!state.hideMitm || !p.mitm_suspect) && (!state.hideBlacklisted || !p.in_blacklist))
      .sort((a, b) => {
        const key = state.proxySortKey;
        const dir = state.proxySortDir;
        if (key === '_exit') return dir * (a._diff - b._diff || (a.egress_country || '').localeCompare(b.egress_country || ''));
        return ui.sortValue(a, b, key, dir);
      });

    if (count) {
      const tags = [];
      if (state.hideNoHttps) tags.push('HTTPS');
      if (state.hideNoSsl) tags.push('SSL');
      if (state.hideMitm) tags.push('no-MITM');
      if (state.hideBlacklisted) tags.push('no-BL');
      count.textContent = sorted.length + (tags.length ? ' ' + tags.join('+') : ' alive');
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.proxySortKey, state.proxySortDir) : ''), width, align, sortKey: key, onSort: key ? () => setProxySort(key) : undefined });

    function blacklistBadge(p) {
      if (!p.in_blacklist) return '';
      const hits = p.ip_blacklist_hits > 0 ? `×${p.ip_blacklist_hits}` : '';
      return `<span style="display:inline-flex;align-items:center;justify-content:center;min-width:16px;padding:1px 4px;border-radius:var(--radius-xs);background:var(--danger-bg);color:var(--danger);font-weight:700;font-size:9px;margin-left:4px">BL${hits}</span>`;
    }

    if (state.groupByProtocol) {
      const groups = {};
      sorted.forEach(p => {
        const g = p._protoGroup;
        if (!groups[g]) groups[g] = [];
        groups[g].push(p);
      });
      wrap.innerHTML = '';
      PROTO_GROUP_ORDER.forEach(g => {
        const list = groups[g];
        if (!list) return;
        const hdr = ui.el('div', '', { style: `display:flex;align-items:center;gap:6px;padding:4px 8px;margin:4px 0 2px;background:var(--surface-raised);border-radius:var(--radius-xs);cursor:pointer;user-select:none` });
        const color = PROTO_GROUP_COLORS[g] || 'var(--text-muted)';
        const arrow = ui.el('span', '', { style: 'font-size:10px;color:var(--text-muted)', text: '▾' });
        const label = ui.el('span', '', { style: `color:${color};font-weight:700;font-size:11px`, text: g });
        const cnt = ui.el('span', '', { style: 'color:var(--text-muted);font-size:11px', text: `${list.length}` });
        hdr.appendChild(arrow);
        hdr.appendChild(label);
        hdr.appendChild(cnt);

        const headers = [
          h('#', null, '24px', 'center'),
          h('Proxy', 'address', null, 'left'),
          h('Srv', 'country', '30px', 'center'),
          h('Exit', '_exit', '30px', 'center'),
          h('SSL', 'ssl_supported', '28px', 'center'),
          h('Lat', 'last_latency', '46px', 'right'),
          h('KB/s', 'speed_avg', '40px', 'right'),
          h('Succ', 'success_rate', '40px', 'right'),
          h('Score', 'score', '40px', 'right'),
          h('BL', 'ip_blacklist_hits', '28px', 'center'),
          h('Ok', 'last_ok', '36px', 'right'),
          h('', null, '40px', 'center'),
        ];
        const rows = list.map((p, i) => {
          const sc = Math.min(100, Math.max(0, p.score || 0));
          const isSel = state.selected === p.address;
          const hasDiff = p.listen_country && p.egress_country && p.listen_country !== p.egress_country;
          const srvFlag = ui.flag(p.listen_country_code || p.country_code) || '—';
          const exitFlag = hasDiff ? (ui.flag(p.egress_country_code || p.country_code) || '') : '';
          return [
            `<span style="color:var(--text-muted)">${i+1}</span>`,
            `<span class="addr" style="font-size:10px">${p.address}</span>`,
            srvFlag,
            exitFlag,
            p.ssl_supported ? '<span style="color:#06b6d4;font-weight:600;font-size:10px">✓</span>' : '<span style="color:var(--text-muted)">—</span>',
            p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
            (p.speed_avg || 0).toFixed(0),
            (p.success_rate * 100).toFixed(0) + '%',
            `<div style="display:inline-block;width:30px;height:4px;background:var(--surface-raised);border-radius:2px;vertical-align:middle;overflow:hidden"><div style="width:${sc}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--info));transition:width 0.4s"></div></div>`,
            blacklistBadge(p),
            ui.ago(p.last_ok),
            `<button class="btn btn-xs ${isSel ? 'btn-primary' : 'btn-secondary'}" onclick="selectProxy('${p.address}')" style="padding:1px 4px;font-size:9px">${isSel ? t('page.proxyPool.active') : t('page.proxyPool.select')}</button>`,
          ];
        });
        const tbl = ui.table(headers, rows);
        let collapsed = false;
        tbl.style.display = '';
        hdr.addEventListener('click', () => {
          collapsed = !collapsed;
          tbl.style.display = collapsed ? 'none' : '';
          arrow.textContent = collapsed ? '▸' : '▾';
        });
        wrap.appendChild(hdr);
        wrap.appendChild(tbl);
      });
    } else {
      const headers = [
        h('#', null, '24px', 'center'),
        h('Proxy', 'address', null, 'left'),
        h('Srv', 'country', '30px', 'center'),
        h('Exit', '_exit', '30px', 'center'),
        h('SSL', 'ssl_supported', '28px', 'center'),
        h('Lat', 'last_latency', '46px', 'right'),
        h('KB/s', 'speed_avg', '40px', 'right'),
        h('Succ', 'success_rate', '40px', 'right'),
        h('Score', 'score', '40px', 'right'),
        h('BL', 'ip_blacklist_hits', '28px', 'center'),
        h('Flags', 'supports_connect', '50px', 'center'),
        h('Ok', 'last_ok', '36px', 'right'),
        h('', null, '40px', 'center'),
      ];
      const rows = sorted.map((p, i) => {
        const sc = Math.min(100, Math.max(0, p.score || 0));
        const flags = [];
        if (p.supports_connect) flags.push('<span style="color:var(--success);font-weight:600">HTTPS</span>');
        else flags.push('<span style="color:var(--text-muted)">HTTP</span>');
        if (p.ssl_supported) flags.push('<span style="color:#06b6d4;font-weight:600">SSL</span>');
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
          p.ssl_supported ? '<span style="color:#06b6d4;font-weight:600;font-size:10px">✓</span>' : '<span style="color:var(--text-muted)">—</span>',
          p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
          (p.speed_avg || 0).toFixed(0),
          (p.success_rate * 100).toFixed(0) + '%',
          `<div style="display:inline-block;width:30px;height:4px;background:var(--surface-raised);border-radius:2px;vertical-align:middle;overflow:hidden"><div style="width:${sc}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--info));transition:width 0.4s"></div></div>`,
          blacklistBadge(p),
          `<span style="color:var(--text-muted);font-size:10px">${proto}</span> ${flags.join(' ')}`,
          ui.ago(p.last_ok),
          `<button class="btn btn-xs ${isSel ? 'btn-primary' : 'btn-secondary'}" onclick="selectProxy('${p.address}')" style="padding:1px 4px;font-size:9px">${isSel ? t('page.proxyPool.active') : t('page.proxyPool.select')}</button>`,
        ];
      });
      wrap.innerHTML = '';
      wrap.appendChild(ui.table(headers, rows));
    }
  }

  // --- Polling ---
  async function load() {
    try {
      let ps = {}, ss = {}, proxies = [];
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { ss = await api.socks5Status(); } catch (e) { console.error('socks5Status', e); }
      try { proxies = await api.proxyAlive(); } catch (e) { console.error('proxyAlive', e); }
      state.selected = ps && ps.active_proxy ? ps.active_proxy.address : null;
      state.proxies = proxies;
      updateProxyControl(ps, ss);
      updateSelectedProxy(ps);
      updateProxyLog(ps, ss);
      updateSelectProxy(proxies);
    } catch (e) {
      console.error('proxy-pool poll', e);
    }
  }

  window.selectProxy = async function(addr) {
    try {
      await api.proxySelect(addr);
      app.toast(addr ? t('page.proxyPool.selected', {addr: addr}) : t('page.proxyPool.directMode'));
      state.selected = addr || null;
      load();
    } catch (e) {
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  };

  load();
  const id = setInterval(load, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
