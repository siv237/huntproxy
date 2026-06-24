router.register('server', (container) => {
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
    row1.appendChild(buildDirectModeCard());
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

  function buildDirectModeCard() {
    const card = ui.el('div', 'card');
    card.id = 'direct-mode-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.server.directMode'), style: 'margin-bottom:8px' }));

    const dm = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px;margin-bottom:6px' });
    const dmCb = ui.el('input', '', { id: 'direct-toggle', type: 'checkbox' });
    dmCb.addEventListener('change', () => api.toggleDirect(dmCb.checked).then(() => app.toast(dmCb.checked ? t('page.server.directModeOn') : t('page.server.directModeOff'))));
    dm.appendChild(dmCb);
    dm.appendChild(ui.el('span', '', { style: 'font-weight:600', text: t('page.server.directMode') }));
    dm.appendChild(ui.el('span', '', { style: 'color:var(--text-muted)', text: t('page.server.noUpstream') }));
    card.appendChild(dm);

    const body = ui.el('div', '', { id: 'server-active-proxy', style: 'font-family:monospace;font-size:12px;color:var(--text-secondary);margin-top:4px' });
    body.textContent = '—';
    card.appendChild(body);
    return card;
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
    if (el('direct-toggle')) el('direct-toggle').checked = !!(ps && ps.direct_mode);

    const apEl = el('server-active-proxy');
    if (apEl) {
      const ap = ps && ps.active_proxy;
      if (ap && !(ps && ps.direct_mode)) {
        const proto = (ap.protocol || 'http').toLowerCase();
        const prefix = proto === 'socks5' ? 'socks5://' : proto === 'socks4' ? 'socks4://' : proto === 'tor' || (ap.address || '').includes('.onion') ? 'tor://' : (ap.supports_connect || ap.ssl_supported) ? 'https://' : 'http://';
        apEl.textContent = prefix + ap.address;
        apEl.style.color = 'var(--accent)';
        apEl.style.fontWeight = '600';
      } else {
        apEl.textContent = '—';
        apEl.style.color = 'var(--text-muted)';
        apEl.style.fontWeight = '400';
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
      let ps = {}, ss = {};
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { ss = await api.socks5Status(); } catch (e) { console.error('socks5Status', e); }
      updateProxyControl(ps, ss);
      updateProxyLog(ps, ss);
    } catch (e) {
      console.error('server poll', e);
    }
  }

  load();
  const id = setInterval(load, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
