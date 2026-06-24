router.register('server', (container) => {
  let aliveProxies = [];
  let customProxies = [];
  let filters = { hideNoHttps: true, hideNoSsl: false, hideMitm: true, hideBlacklisted: true };

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const row1 = ui.el('div', 'grid grid-2 row-stretch');
    row1.style.flex = '0 0 auto';
    row1.appendChild(buildServerControlCard());
    row1.appendChild(buildModeCard());
    container.appendChild(row1);

    const row2 = ui.el('div', 'grid grid-1 row-stretch');
    row2.style.flex = '1';
    row2.appendChild(buildClientLogCard());
    container.appendChild(row2);
  }

  function buildServerControlCard() {
    const card = ui.el('div', 'card');
    card.id = 'server-control-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.server.proxyServer'), style: 'margin-bottom:8px' }));

    const status = ui.el('div', '', { id: 'proxy-status-bar', style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:8px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)' });
    status.innerHTML = `<span id="proxy-dot" style="width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0"></span><span id="proxy-status-text">${t('page.server.stopped')}</span>`;
    card.appendChild(status);

    const httpRow = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px' });
    httpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:52px;flex-shrink:0', text: t('page.server.http') }));
    httpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.port') }));
    const portInp = ui.el('input', '', { id: 'proxy-port', type: 'number', value: '17277', min: '1024', max: '65535', style: 'width:72px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    httpRow.appendChild(portInp);
    const startBtn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.server.start'), id: 'btn-proxy-start' });
    startBtn.addEventListener('click', () => api.proxyStart(portInp.value).then(() => app.toast(t('page.server.proxyStarted'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    httpRow.appendChild(startBtn);
    const stopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.server.stop'), id: 'btn-proxy-stop' });
    stopBtn.addEventListener('click', () => api.proxyStop().then(() => app.toast(t('page.server.proxyStopped'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    httpRow.appendChild(stopBtn);
    card.appendChild(httpRow);

    const s5Row = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px;padding-top:6px;border-top:1px solid var(--border-subtle)' });
    s5Row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:52px;flex-shrink:0', text: t('page.server.socks5') }));
    s5Row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.port') }));
    const s5PortInp = ui.el('input', '', { id: 'socks5-port', type: 'number', value: '17278', min: '1024', max: '65535', style: 'width:72px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    s5Row.appendChild(s5PortInp);
    const s5StartBtn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.server.start'), id: 'btn-socks5-start' });
    s5StartBtn.addEventListener('click', () => api.socks5Start(s5PortInp.value).then(() => app.toast(t('page.server.socks5Started'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    s5Row.appendChild(s5StartBtn);
    const s5StopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.server.stop'), id: 'btn-socks5-stop' });
    s5StopBtn.addEventListener('click', () => api.socks5Stop().then(() => app.toast(t('page.server.socks5Stopped'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    s5Row.appendChild(s5StopBtn);
    card.appendChild(s5Row);

    const connRow = ui.el('div', '', { style: 'display:flex;gap:12px;align-items:baseline' });
    const httpConn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
    httpConn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.http') }));
    httpConn.appendChild(ui.el('span', '', { id: 'proxy-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
    connRow.appendChild(httpConn);
    const s5Conn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
    s5Conn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.socks5') }));
    s5Conn.appendChild(ui.el('span', '', { id: 'socks5-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
    connRow.appendChild(s5Conn);
    card.appendChild(connRow);
    return card;
  }

  function buildModeCard() {
    const card = ui.el('div', 'card');
    card.id = 'mode-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.server.mode'), style: 'margin-bottom:8px' }));

    const sel = ui.el('select', '', { id: 'mode-select', style: 'width:100%;padding:6px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    sel.addEventListener('change', () => {
      const val = sel.value;
      if (val === 'direct') {
        api.routingDisable().then(() => api.toggleDirect(true)).then(() => app.toast(t('page.server.directModeOn')));
      } else if (val === 'routing') {
        api.routingEnable().then(() => api.toggleDirect(false)).then(() => app.toast(t('page.server.routingModeOn')));
      } else if (val === 'cascade-pool') {
        api.routingDisable().then(() => api.toggleDirect(false)).then(() => api.proxySelect('')).then(() => app.toast(t('page.server.cascadePoolOn')));
      } else if (val.startsWith('proxy:')) {
        const addr = val.slice(6);
        api.routingDisable().then(() => api.toggleDirect(false)).then(() => api.proxySelect(addr)).then(() => app.toast(t('page.server.cascadeSelected', {addr})));
      }
    });
    card.appendChild(sel);

    const filterRow = ui.el('div', '', { id: 'mode-filters', style: 'display:flex;align-items:center;gap:6px;margin-top:6px;flex-wrap:wrap' });
    function makeFilter(id, label, key, checked) {
      const lbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:3px;cursor:pointer;font-size:10px' });
      const cb = ui.el('input', '', { id, type: 'checkbox', ...(checked ? { checked: 'checked' } : {}) });
      cb.addEventListener('change', () => { filters[key] = cb.checked; populateModeSelect(); });
      lbl.appendChild(cb);
      lbl.appendChild(ui.el('span', '', { text: label }));
      return lbl;
    }
    filterRow.appendChild(makeFilter('srv-hide-https', t('page.proxyPool.hideNoHttps'), 'hideNoHttps', true));
    filterRow.appendChild(makeFilter('srv-hide-ssl', 'SSL', 'hideNoSsl', false));
    filterRow.appendChild(makeFilter('srv-hide-mitm', t('page.proxyPool.hideMitm'), 'hideMitm', true));
    filterRow.appendChild(makeFilter('srv-hide-bl', t('page.proxyPool.hideBlacklisted'), 'hideBlacklisted', true));
    card.appendChild(filterRow);

    const statusRow = ui.el('div', '', { id: 'mode-status-row', style: 'margin-top:8px;font-size:12px;display:flex;align-items:center;gap:6px' });
    card.appendChild(statusRow);
    return card;
  }

  function populateModeSelect() {
    const sel = document.getElementById('mode-select');
    if (!sel) return;
    const prevVal = sel.value;
    sel.innerHTML = '';

    sel.appendChild(ui.el('option', '', { value: 'direct', text: t('page.server.directMode') + ' — ' + t('page.server.directDesc') }));
    sel.appendChild(ui.el('option', '', { value: 'routing', text: t('page.server.routingMode') + ' — ' + t('page.server.routingDesc') }));

    const cascadeAuto = ui.el('optgroup', '', { label: t('page.server.cascadeMode') + ': ' + t('page.server.cascadePool') });
    cascadeAuto.appendChild(ui.el('option', '', { value: 'cascade-pool', text: t('page.server.poolCurrent') }));
    sel.appendChild(cascadeAuto);

    if (customProxies.length) {
      const grp = ui.el('optgroup', '', { label: t('page.server.cascadeMode') + ': ' + t('page.server.cascadeCustom') + ' (' + customProxies.length + ')' });
      customProxies.forEach(cp => {
        const addr = cp.host + ':' + cp.port;
        const st = cp.last_check_status === 'ok' ? '✓' : cp.last_check_status === 'fail' ? '✗' : '?';
        const lat = cp.last_check_latency ? cp.last_check_latency.toFixed(2) + 's' : '';
        grp.appendChild(ui.el('option', '', { value: 'proxy:' + addr, text: st + ' ' + (cp.name || addr) + '  ' + addr + (lat ? ' ' + lat : '') }));
      });
      sel.appendChild(grp);
    }

    const filtered = (aliveProxies || []).slice()
      .filter(p => (!filters.hideNoHttps || p.supports_connect) && (!filters.hideNoSsl || p.ssl_supported) && (!filters.hideMitm || !p.mitm_suspect) && (!filters.hideBlacklisted || !(p.in_blacklist || (p.ip_blacklist_hits || 0) > 0)))
      .sort((a, b) => (b.score || 0) - (a.score || 0));

    if (filtered.length) {
      const grp = ui.el('optgroup', '', { label: t('page.server.cascadeMode') + ': ' + t('page.server.cascadeWorking') + ' (' + filtered.length + ')' });
      filtered.slice(0, 200).forEach(p => {
        const flag = ui.flag(p.egress_country_code || p.country_code) || '';
        const lat = p.last_latency ? p.last_latency.toFixed(2) + 's' : '—';
        const speed = (p.speed_avg || 0).toFixed(0) + 'KB/s';
        const succ = (p.success_rate * 100).toFixed(0) + '%';
        grp.appendChild(ui.el('option', '', { value: 'proxy:' + p.address, text: flag + ' ' + p.address + '  ' + lat + ' ' + speed + ' ' + succ }));
      });
      sel.appendChild(grp);
    }

    sel.value = prevVal;
  }

  function buildClientLogCard() {
    const card = ui.el('div', 'card');
    card.id = 'client-log-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.overflow = 'hidden';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.server.clientLog'), style: 'margin-bottom:8px' }));

    const log = ui.el('div', '', { id: 'proxy-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow-y:auto;flex:1;min-height:0;color:var(--text-primary)' });
    log.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.server.proxyNotStarted')}</div>`;
    card.appendChild(log);
    return card;
  }

  build();

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
      if (txt) txt.textContent = t('page.server.running') + ' ' + parts.join(', ');
    } else {
      if (bar) { bar.style.background = 'var(--surface-raised)'; bar.style.borderColor = 'var(--border)'; bar.style.color = 'var(--text-secondary)'; }
      if (dot) dot.style.background = 'var(--text-muted)';
      if (txt) txt.textContent = t('page.server.stopped');
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
  }

  function updateModeStatus(ps, routingEnabled) {
    const el = id => document.getElementById(id);
    const isDirect = !!(ps && ps.direct_mode);
    const hasActive = !!(ps && ps.active_proxy);
    const addr = hasActive ? ps.active_proxy.address : null;

    const sel = el('mode-select');
    if (sel) {
      if (routingEnabled) {
        sel.value = 'routing';
      } else if (isDirect) {
        sel.value = 'direct';
      } else if (addr) {
        const opt = Array.from(sel.options).find(o => o.value === 'proxy:' + addr);
        sel.value = opt ? opt.value : 'cascade-pool';
      } else {
        sel.value = 'cascade-pool';
      }
    }

    const stRow = el('mode-status-row');
    if (stRow) {
      stRow.innerHTML = '';
      if (routingEnabled) {
        const txt = ui.el('span', '', { style: 'color:var(--accent);font-weight:600', text: t('page.server.routingMode') });
        stRow.appendChild(txt);
        const link = ui.el('a', '', { style: 'color:var(--info);text-decoration:underline;cursor:pointer;font-size:11px', text: '→ ' + t('page.server.configureRoutes') });
        link.addEventListener('click', () => router.navigate('routes'));
        stRow.appendChild(link);
      } else if (isDirect) {
        stRow.appendChild(ui.el('span', '', { style: 'color:var(--warning)', text: t('page.server.directMode') + ' — ' + t('page.server.directDesc') }));
      } else {
        const isPoolMode = sel && sel.value === 'cascade-pool';
        if (isPoolMode) {
          stRow.appendChild(ui.el('span', '', { style: 'color:var(--success);font-weight:600', text: t('page.server.cascadeMode') + ': ' + t('page.server.cascadePool') }));
          if (addr) {
            stRow.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);font-family:monospace;font-size:11px', text: '→ ' + addr }));
          }
          const link = ui.el('a', '', { style: 'color:var(--info);text-decoration:underline;cursor:pointer;font-size:11px', text: '→ ' + t('page.server.poolManage') });
          link.addEventListener('click', () => router.navigate('proxy-pool'));
          stRow.appendChild(link);
        } else if (addr) {
          stRow.appendChild(ui.el('span', '', { style: 'color:var(--info);font-weight:600', text: t('page.server.cascadeMode') + ': → ' + addr }));
        } else {
          stRow.appendChild(ui.el('span', '', { style: 'color:var(--text-muted)', text: '—' }));
        }
      }
    }
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
      log.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.server.proxyNotStarted')}</div>`;
      return;
    }
    const fmtTarget = t => {
      if (!t || t === '?') return '?';
      const m = t.match(/^(https?:\/\/)?([^\/:]+)(.*)/);
      if (!m) return t;
      return (m[1] || '') + '<b>' + m[2] + '</b>' + (m[3] || '');
    };
    const fmtChain = upstream => {
      if (!upstream || upstream === '?') return 'direct';
      return ui.escHtml(upstream);
    };
    log.innerHTML = all.map(e => `<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> <span style="color:var(--accent);font-size:10px">${e.type}</span> ${e.client || '?'} → ${fmtTarget(e.target)} [${e.status || ''}] <span style="color:var(--info)">via ${fmtChain(e.upstream)}</span>`).join('<br>');
  }

  async function load() {
    try {
      let ps = {}, ss = {}, rs = {};
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { ss = await api.socks5Status(); } catch (e) { console.error('socks5Status', e); }
      try { rs = await api.routingStatus(); } catch (e) { console.error('routingStatus', e); }
      updateProxyControl(ps, ss);
      updateModeStatus(ps, !!(rs && rs.enabled));
      updateProxyLog(ps, ss);
    } catch (e) {
      console.error('server poll', e);
    }
  }

  async function loadProxies() {
    try {
      const [alive, custom] = await Promise.all([
        api.proxyAlive().catch(() => []),
        api.customProxies().catch(() => ({proxies: []})),
      ]);
      aliveProxies = alive || [];
      customProxies = (custom && custom.proxies) || [];
      populateModeSelect();
    } catch (e) { /* ignore */ }
  }

  load();
  loadProxies();
  const id = setInterval(load, 2000);
  const idProxy = setInterval(loadProxies, 5000);
  if (window._pageIntervals) window._pageIntervals.push(id, idProxy);
  else window._pageIntervals = [id, idProxy];
});
