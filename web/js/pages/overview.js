router.register('overview', (container) => {
  const els = {};

  function build() {
    container.innerHTML = '';

    // Row 1: Proxy Server + Hunt Progress
    const row1 = ui.el('div', 'grid grid-2');
    row1.appendChild(buildProxyCard());
    row1.appendChild(buildHuntCard());
    container.appendChild(row1);

    // Row 2: Pool Stats + Current Proxy + Recent Activity
    const row2 = ui.el('div', 'grid grid-3');
    row2.appendChild(buildPoolStatsCard());
    row2.appendChild(buildCurrentProxyCard());
    row2.appendChild(buildActivityCard());
    container.appendChild(row2);

    // Row 3: Top 5 + Blacklist mini
    const row3 = ui.el('div', 'grid grid-2');
    row3.appendChild(buildTopProxiesCard());
    row3.appendChild(buildBlacklistMiniCard());
    container.appendChild(row3);
  }

  function buildProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'proxy-server-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'HTTP Proxy Server' }));
    const conn = ui.el('span', '', { id: 'proxy-conn', style: 'font-size:12px;color:var(--text-secondary)', text: '0 connections' });
    header.appendChild(conn);
    card.appendChild(header);

    const statusRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:10px;margin-bottom:10px' });
    const dot = ui.el('span', '', { id: 'proxy-dot', style: 'width:10px;height:10px;border-radius:50%;background:var(--text-muted);flex-shrink:0' });
    const statusText = ui.el('span', '', { id: 'proxy-status-text', style: 'font-size:14px;font-weight:600', text: 'Stopped' });
    statusRow.appendChild(dot);
    statusRow.appendChild(statusText);
    card.appendChild(statusRow);

    const upstream = ui.el('div', '', { id: 'proxy-upstream', style: 'padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs);border:1px solid var(--border);font-size:13px;min-height:60px' });
    upstream.innerHTML = '<div class="empty" style="font-size:12px">No active upstream</div>';
    card.appendChild(upstream);

    const ctrl = ui.el('div', '', { style: 'display:flex;gap:6px;margin-top:8px;align-items:center' });
    const portInp = ui.el('input', '', { id: 'proxy-port', type: 'number', value: '17277', min: '1024', max: '65535', style: 'width:70px;padding:4px 6px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    const startBtn = ui.el('button', 'btn btn-sm btn-primary', { text: 'Start', id: 'btn-proxy-start' });
    startBtn.addEventListener('click', () => api.proxyStart(portInp.value).then(() => app.toast('Proxy started')).catch(e => app.toast('Error: ' + e.message, 'error')));
    const stopBtn = ui.el('button', 'btn btn-sm btn-danger', { text: 'Stop', id: 'btn-proxy-stop' });
    stopBtn.addEventListener('click', () => api.proxyStop().then(() => app.toast('Proxy stopped')).catch(e => app.toast('Error: ' + e.message, 'error')));
    const poolBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: 'Change Proxy' });
    poolBtn.addEventListener('click', () => router.navigate('proxy-pool'));
    ctrl.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-secondary)', text: 'Port:' }));
    ctrl.appendChild(portInp);
    ctrl.appendChild(startBtn);
    ctrl.appendChild(stopBtn);
    ctrl.appendChild(poolBtn);
    card.appendChild(ctrl);

    return card;
  }

  function buildHuntCard() {
    const card = ui.el('div', 'card');
    card.id = 'hunt-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Hunt Progress' }));
    const phase = ui.el('span', '', { id: 'hunt-phase', style: 'font-size:11px;font-weight:600;text-transform:uppercase;padding:2px 8px;border-radius:10px;background:var(--surface-raised);color:var(--text-secondary)', text: 'idle' });
    header.appendChild(phase);
    card.appendChild(header);

    const progressWrap = ui.el('div', '', { style: 'margin-bottom:6px' });
    progressWrap.appendChild(ui.el('div', 'progress-bar', { id: 'hunt-progress-bar', style: 'height:8px' }, [
      ui.el('div', '', { id: 'hunt-progress-fill', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease;border-radius:4px' })
    ]));
    card.appendChild(progressWrap);

    const stats = ui.el('div', '', { style: 'display:flex;justify-content:space-between;font-size:12px;color:var(--text-secondary);margin-bottom:6px' });
    stats.innerHTML = '<span>Checked <b id="hunt-checked" style="color:var(--text-primary)">0</b> / <b id="hunt-total">0</b></span><span>Working <b id="hunt-working" style="color:var(--success)">0</b></span>';
    card.appendChild(stats);

    const last = ui.el('div', '', { id: 'hunt-last', style: 'font-size:11px;color:var(--text-secondary);display:flex;align-items:center;gap:4px;min-height:20px' });
    last.innerHTML = '<span style="color:var(--text-muted)">ready</span>';
    card.appendChild(last);

    const ctrl = ui.el('div', '', { style: 'display:flex;gap:6px;margin-top:8px' });
    const startBtn = ui.el('button', 'btn btn-sm btn-primary', { text: 'Start', id: 'btn-hunt-start' });
    startBtn.addEventListener('click', () => api.huntStart().then(() => app.toast('Hunt started')));
    const stopBtn = ui.el('button', 'btn btn-sm btn-danger', { text: 'Stop', id: 'btn-hunt-stop' });
    stopBtn.addEventListener('click', () => api.huntStop().then(() => app.toast('Hunt stopped')));
    const sel = ui.el('select', '', { id: 'hunt-country', style: 'padding:4px 6px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);max-width:80px' });
    ['ALL','US','RU','GB','DE','FR','NL','CA','JP','BR','IN','UA','PL'].forEach(c => {
      sel.appendChild(ui.el('option', '', { value: c === 'ALL' ? '' : c, text: c }));
    });
    sel.addEventListener('change', () => api.setCountry(sel.value).then(() => app.toast('Country: ' + (sel.value || 'ALL'))));
    ctrl.appendChild(startBtn);
    ctrl.appendChild(stopBtn);
    ctrl.appendChild(sel);
    card.appendChild(ctrl);

    return card;
  }

  function buildPoolStatsCard() {
    const card = ui.el('div', 'card');
    card.id = 'pool-stats-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Pool', style: 'margin-bottom:8px' }));
    const grid = ui.el('div', '', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:10px' });
    grid.appendChild(statBox('Alive', '0', 'stat-alive', 'var(--success)'));
    grid.appendChild(statBox('Dead', '0', 'stat-dead', 'var(--danger)'));
    grid.appendChild(statBox('BL', '0', 'stat-bl', 'var(--warning)'));
    grid.appendChild(statBox('Total', '0', 'stat-total', 'var(--text-primary)'));
    card.appendChild(grid);
    return card;
  }

  function statBox(label, value, id, color) {
    const box = ui.el('div', '', { style: 'text-align:center' });
    box.appendChild(ui.el('div', '', { id, style: `font-size:22px;font-weight:700;color:${color}`, text: value }));
    box.appendChild(ui.el('div', '', { style: 'font-size:10px;color:var(--text-secondary);text-transform:uppercase', text: label }));
    return box;
  }

  function buildCurrentProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'current-proxy-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Current Upstream', style: 'margin-bottom:8px' }));

    const body = ui.el('div', '', { id: 'current-proxy-body', style: 'font-size:12px' });
    body.innerHTML = '<div class="empty" style="font-size:12px">No upstream selected</div>';
    card.appendChild(body);
    return card;
  }

  function buildActivityCard() {
    const card = ui.el('div', 'card');
    card.id = 'activity-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Recent Activity', style: 'margin-bottom:8px' }));
    const list = ui.el('div', '', { id: 'activity-list', style: 'font-size:11px;line-height:1.6;max-height:110px;overflow-y:auto' });
    list.innerHTML = '<div class="empty" style="font-size:11px">No events</div>';
    card.appendChild(list);
    return card;
  }

  function buildTopProxiesCard() {
    const card = ui.el('div', 'card');
    card.id = 'top-proxies-card';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Top Alive' }));
    const count = ui.el('div', '', { id: 'top-count', style: 'font-size:11px;color:var(--text-secondary)', text: '0' });
    header.appendChild(count);
    card.appendChild(header);

    const wrap = ui.el('div', 'table-wrap');
    wrap.id = 'top-tbl-wrap';
    card.appendChild(wrap);
    return card;
  }

  function buildBlacklistMiniCard() {
    const card = ui.el('div', 'card');
    card.id = 'bl-card';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Blacklist' }));
    const count = ui.el('div', '', { id: 'bl-count', style: 'font-size:11px;color:var(--text-secondary)', text: '0' });
    header.appendChild(count);
    card.appendChild(header);

    const wrap = ui.el('div', 'table-wrap');
    wrap.id = 'bl-tbl-wrap';
    card.appendChild(wrap);
    return card;
  }

  build();

  // --- Updaters ---

  function updateProxyCard(ps) {
    const dot = document.getElementById('proxy-dot');
    const txt = document.getElementById('proxy-status-text');
    const conn = document.getElementById('proxy-conn');
    const wrap = document.getElementById('proxy-upstream');
    if (!dot || !txt || !wrap) return;

    const running = ps && ps.running;
    dot.style.background = running ? 'var(--success)' : 'var(--danger)';
    txt.textContent = running ? 'Running on port ' + (ps.port || 17277) : 'Stopped';
    txt.style.color = running ? 'var(--success)' : 'var(--danger)';
    if (conn) conn.textContent = (ps.connections || 0) + ' connections';

    if (document.getElementById('btn-proxy-start')) document.getElementById('btn-proxy-start').disabled = running;
    if (document.getElementById('btn-proxy-stop')) document.getElementById('btn-proxy-stop').disabled = !running;

    const ap = ps && ps.active_proxy;
    if (!ap) {
      wrap.innerHTML = '<div class="empty" style="font-size:12px">No active upstream. Server is ' + (running ? 'running in direct mode' : 'stopped') + '.</div>';
      return;
    }
    const top = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap' });
    top.appendChild(ui.el('div', '', { style: 'font-family:monospace;font-size:14px;font-weight:700;color:var(--accent)', text: ap.address }));
    top.appendChild(ui.badge(ap.last_status === 'ok' ? 'Healthy' : 'Unhealthy', ap.last_status === 'ok' ? 'green' : 'red'));
    top.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code) }));
    wrap.innerHTML = '';
    wrap.appendChild(top);

    const grid = ui.el('div', '', { style: 'display:grid;grid-template-columns:1fr 1fr 1fr;gap:4px;font-size:11px' });
    [
      { l: 'Latency', v: ui.fmtLatency(ap.last_latency) },
      { l: 'Success', v: ui.fmtPct(ap.success_rate) },
      { l: 'Last', v: ui.ago(ap.last_check) },
    ].forEach(it => {
      const cell = ui.el('div', '', { style: 'text-align:center;padding:4px;background:var(--bg);border-radius:var(--radius-xs);border:1px solid var(--border)' });
      cell.appendChild(ui.el('div', '', { style: 'font-size:10px;color:var(--text-secondary)', text: it.l }));
      cell.appendChild(ui.el('div', '', { style: 'font-size:12px;font-weight:600', text: it.v }));
      grid.appendChild(cell);
    });
    wrap.appendChild(grid);
  }

  function updateHuntCard(s) {
    const p = s.progress || {};
    const t = p.checking_total || p.downloaded || 0;
    const c = p.checked || 0;
    const pct = t > 0 ? Math.round((c / t) * 100) : 0;
    const el = id => document.getElementById(id);
    if (el('hunt-progress-fill')) el('hunt-progress-fill').style.width = pct + '%';
    if (el('hunt-checked')) el('hunt-checked').textContent = c;
    if (el('hunt-total')) el('hunt-total').textContent = t;
    if (el('hunt-working')) el('hunt-working').textContent = p.working || 0;

    if (el('hunt-phase')) {
      el('hunt-phase').textContent = s.phase || 'idle';
      el('hunt-phase').style.color = s.running ? 'var(--accent)' : 'var(--text-secondary)';
      el('hunt-phase').style.background = s.running ? 'var(--accent-light)' : 'var(--surface-raised)';
    }

    if (el('hunt-last')) {
      if (p.last_proxy) {
        const det = s.last_proxy_details || {};
        el('hunt-last').innerHTML = `<span>${ui.flag(det.country_code || '')}</span> <span style="font-family:monospace;color:var(--accent)">${p.last_proxy}</span> <span>${p.last_country || ''}</span>`;
      } else {
        el('hunt-last').innerHTML = '<span style="color:var(--text-muted)">' + (s.last_event || 'ready') + '</span>';
      }
    }

    if (el('btn-hunt-start')) el('btn-hunt-start').disabled = s.running;
    if (el('btn-hunt-stop')) el('btn-hunt-stop').disabled = !s.running;
  }

  function updatePoolStats(s) {
    const c = s.counts || {};
    const el = id => document.getElementById(id);
    if (el('stat-alive')) el('stat-alive').textContent = c.alive || 0;
    if (el('stat-dead')) el('stat-dead').textContent = c.dead || 0;
    if (el('stat-bl')) el('stat-bl').textContent = c.blacklist || 0;
    if (el('stat-total')) el('stat-total').textContent = c.ratings || 0;
  }

  function updateCurrentProxy(ps) {
    const body = document.getElementById('current-proxy-body');
    if (!body) return;
    const ap = ps && ps.active_proxy;
    if (!ap) {
      body.innerHTML = '<div class="empty" style="font-size:12px">No upstream selected</div>';
      return;
    }
    const grid = ui.el('div', '', { style: 'display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:11px' });
    [
      { l: 'Latency', v: ui.fmtLatency(ap.last_latency) },
      { l: 'Success', v: ui.fmtPct(ap.success_rate) },
      { l: 'Score', v: (ap.score || 0).toFixed(0) },
      { l: 'Checks', v: `${ap.checks_ok}/${ap.checks_total}` },
      { l: 'Speed', v: ap.speed_avg ? ap.speed_avg.toFixed(0) + ' KB/s' : '—' },
      { l: 'Protocol', v: (ap.protocol || 'HTTP').toUpperCase() },
    ].forEach(it => {
      const cell = ui.el('div', '', { style: 'text-align:center;padding:4px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
      cell.appendChild(ui.el('div', '', { style: 'font-size:10px;color:var(--text-secondary)', text: it.l }));
      cell.appendChild(ui.el('div', '', { style: 'font-size:12px;font-weight:600', text: it.v }));
      grid.appendChild(cell);
    });
    body.innerHTML = '';
    body.appendChild(grid);
  }

  let activityLines = [];
  function updateActivity(events) {
    const list = document.getElementById('activity-list');
    if (!list || !events || !events.length) return;
    events.forEach(e => {
      activityLines.unshift(`<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> ${e.msg}`);
      if (activityLines.length > 20) activityLines.length = 20;
    });
    list.innerHTML = activityLines.join('<br>');
  }

  function updateTopProxies(proxies) {
    const wrap = document.getElementById('top-tbl-wrap');
    if (!wrap) return;
    const el = id => document.getElementById(id);
    if (el('top-count')) el('top-count').textContent = (proxies || []).length + ' alive';

    const headers = [
      { label: 'Proxy', width: null, align: 'left' },
      { label: 'Ctry', width: '40px', align: 'center' },
      { label: 'Latency', width: '60px', align: 'right' },
      { label: 'Score', width: '50px', align: 'right' },
    ];
    const rows = (proxies || []).slice(0, 5).map(p => [
      `<span style="font-family:monospace;font-size:12px">${p.address}</span>`,
      ui.flag(p.country_code) || '—',
      p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
      (p.score || 0).toFixed(0),
    ]);
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  function updateBlacklistMini(bl) {
    const wrap = document.getElementById('bl-tbl-wrap');
    const count = document.getElementById('bl-count');
    if (count) count.textContent = (bl || []).length + ' total';
    if (!wrap) return;

    const headers = [
      { label: 'Proxy', width: null, align: 'left' },
      { label: 'Reason', width: '60px', align: 'left' },
      { label: '', width: '24px', align: 'center' },
    ];
    const rows = (bl || []).slice(0, 3).map(b => [
      `<span style="font-family:monospace;font-size:11px">${b.address}</span>`,
      `<span style="font-size:10px;color:var(--danger)">${b.reason || '—'}</span>`,
      `<button class="btn btn-xs btn-secondary" onclick="window.blRemove('${b.address}')" style="padding:1px 4px;font-size:9px">×</button>`,
    ]);
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  // --- Polling ---
  let lastEventSeq = 0;
  async function poll() {
    try {
      let ps = {}, s = {}, ev = [];
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { s = await api.snapshot(); } catch (e) { console.error('snapshot', e); }
      try { ev = await api.events(lastEventSeq); } catch (e) { console.error('events', e); }

      updateProxyCard(ps);
      updateHuntCard(s);
      updatePoolStats(s);
      updateCurrentProxy(ps);
      updateTopProxies(s.top_proxies);
      updateBlacklistMini(s.blacklist);
      if (ev && ev.length) {
        lastEventSeq = Math.max(...ev.map(e => e.seq), lastEventSeq);
        updateActivity(ev);
      }
    } catch (e) {
      console.error('overview poll', e);
    }
  }

  poll();
  const id = setInterval(poll, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
