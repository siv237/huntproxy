router.register('connectivity', (container) => {
  let canaryData = null;
  let history = [];
  let _loading = false;
  let lastAlive = null;
  let lastIp = null;
  let eventLog = [];
  let eventInterval = null;

  function setContainerStyle() {
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';
  }

  function build() {
    container.innerHTML = '';
    setContainerStyle();

    const topRow = ui.el('div', '');
    topRow.style.display = 'grid';
    topRow.style.gridTemplateColumns = '1fr 2fr';
    topRow.style.gap = '10px';
    topRow.appendChild(buildStatusCard());
    topRow.appendChild(buildDirectInfoCard());
    container.appendChild(topRow);

    container.appendChild(buildHostsCard());
    container.appendChild(buildGraphCard());
    container.appendChild(buildEventLogCard());
  }

  function buildStatusCard() {
    const card = ui.card(t('page.connectivity.internetConnectivity'));
    card.id = 'card-canary-status';

    const indicator = ui.el('div', '', { style: 'display:flex;align-items:center;gap:14px' });
    const dotWrap = ui.el('div', '', { style: 'position:relative;width:44px;height:44px;flex-shrink:0' });
    const dot = ui.el('div', '', { id: 'canary-big-dot', style: 'width:44px;height:44px;border-radius:50%;background:var(--text-muted);display:flex;align-items:center;justify-content:center;font-size:20px;transition:background .3s' });
    dot.textContent = '?';
    const pulse = ui.el('div', '', { id: 'canary-pulse', style: 'position:absolute;inset:0;border-radius:50%;opacity:0;transition:opacity .3s' });
    pulse.style.background = 'var(--success)';
    dotWrap.appendChild(pulse);
    dotWrap.appendChild(dot);
    indicator.appendChild(dotWrap);

    const info = ui.el('div', '', { style: 'flex:1' });
    info.innerHTML = '<div id="canary-big-text" style="font-size:16px;font-weight:700;color:var(--text-muted)">' + t('page.connectivity.checking') + '</div>'
      + '<div id="canary-big-sub" style="font-size:11px;color:var(--text-secondary);margin-top:2px"></div>';
    indicator.appendChild(info);

    card.appendChild(indicator);
    return card;
  }

  function buildDirectInfoCard() {
    const card = ui.card(t('page.connectivity.directConnection'));
    card.id = 'card-direct-info';

    const grid = ui.el('div', '', { id: 'direct-info-grid', style: 'display:grid;grid-template-columns:repeat(4,1fr);gap:8px' });
    const fields = [
      { id: 'di-ip', label: t('page.connectivity.ipAddress') },
      { id: 'di-country', label: t('page.connectivity.country') },
      { id: 'di-city', label: t('page.connectivity.city') },
      { id: 'di-isp', label: t('page.connectivity.isp') },
    ];
    fields.forEach(f => {
      const item = ui.el('div', '', { style: 'padding:6px 8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
      item.appendChild(ui.el('div', '', { style: 'font-size:9px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.5px', text: f.label }));
      item.appendChild(ui.el('div', '', { id: f.id, style: 'font-size:13px;font-weight:600;margin-top:1px', text: '—' }));
      grid.appendChild(item);
    });
    card.appendChild(grid);
    return card;
  }

  function buildHostsCard() {
    const card = ui.card(t('page.connectivity.canaryHosts'));
    card.id = 'card-canary-hosts';

    const tblWrap = ui.el('div', '', { id: 'canary-hosts-tbl', style: 'margin-bottom:10px' });
    card.appendChild(tblWrap);

    const editor = ui.el('div', '', { id: 'canary-hosts-editor', style: 'margin-bottom:6px' });
    const chips = ui.el('div', '', { id: 'canary-chips', style: 'display:flex;flex-wrap:wrap;gap:6px;margin-bottom:8px' });
    editor.appendChild(chips);

    const inputRow = ui.el('div', '', { style: 'display:flex;gap:6px;align-items:center' });
    const input = ui.el('input', '', { id: 'canary-host-input', type: 'text', placeholder: 'e.g. ya.ru, google.com', style: 'flex:1;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    inputRow.appendChild(input);
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.connectivity.addHost'), style: 'flex-shrink:0' });
    addBtn.addEventListener('click', () => addHost());
    inputRow.appendChild(addBtn);
    editor.appendChild(inputRow);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); addHost(); } });

    card.appendChild(editor);
    return card;
  }

  function addHost() {
    const input = document.getElementById('canary-host-input');
    if (!input) return;
    const host = input.value.trim().toLowerCase().replace(/[^a-z0-9.\-_]/g, '');
    if (!host) return;
    const chips = document.getElementById('canary-chips');
    if (chips && chips.querySelector('[data-host="' + CSS.escape(host) + '"]')) { app.toast(t('page.connectivity.hostAlreadyAdded'), 'error'); return; }
    const hosts = getChipHosts();
    hosts.push(host);
    api.canarySetHosts(hosts).then(() => { input.value = ''; app.toast(t('page.connectivity.hostAdded')); load(); }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  function getChipHosts() {
    const chips = document.getElementById('canary-chips');
    if (!chips) return [];
    return Array.from(chips.querySelectorAll('[data-host]')).map(el => el.dataset.host);
  }

  function removeChip(host) {
    const hosts = getChipHosts().filter(h => h !== host);
    api.canarySetHosts(hosts).then(() => { app.toast(t('page.connectivity.hostRemoved')); load(); }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  function renderChips(hosts) {
    const chips = document.getElementById('canary-chips');
    if (!chips) return;
    chips.innerHTML = '';
    (hosts || []).forEach(h => {
      const chip = ui.el('div', '', { 'data-host': h, style: 'display:inline-flex;align-items:center;gap:4px;padding:4px 10px;background:var(--surface-raised);border:1px solid var(--border);border-radius:16px;font-size:12px;font-family:ui-monospace,monospace' });
      chip.appendChild(ui.el('span', '', { text: h }));
      const x = ui.el('span', '', { style: 'cursor:pointer;color:var(--text-muted);font-size:10px;font-weight:700', text: '\u2715' });
      x.addEventListener('click', () => removeChip(h));
      chip.appendChild(x);
      chips.appendChild(chip);
    });
  }

  function buildGraphCard() {
    const card = ui.card(t('page.connectivity.availability24h'));
    card.id = 'card-canary-graph';
    const canvas = ui.el('canvas', '', { id: 'canary-canvas', style: 'width:100%;height:160px' });
    card.appendChild(canvas);
    const legend = ui.el('div', '', { style: 'display:flex;gap:16px;font-size:11px;margin-top:6px' });
    legend.innerHTML = '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:2px;background:var(--success)"></span> ' + t('page.connectivity.onlineLegend') + '</span>'
      + '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:2px;background:var(--danger)"></span> ' + t('page.connectivity.offlineLegend') + '</span>';
    card.appendChild(legend);
    return card;
  }

  function buildEventLogCard() {
    const card = ui.card(t('page.connectivity.eventLog'));
    card.id = 'card-canary-log';
    const logWrap = ui.el('div', '', { id: 'canary-log-wrap', style: 'max-height:200px;overflow-y:auto;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.6' });
    logWrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">' + t('page.connectivity.waitingForEvents') + '</div>';
    card.appendChild(logWrap);
    return card;
  }

  function updateStatusCard(data) {
    if (!data) return;
    const dot = document.getElementById('canary-big-dot');
    const pulse = document.getElementById('canary-pulse');
    const text = document.getElementById('canary-big-text');
    const sub = document.getElementById('canary-big-sub');
    if (!dot || !text) return;

    const wasAlive = lastAlive;
    const isAlive = data.alive;

    if (isAlive) {
      dot.style.background = 'var(--success)';
      dot.textContent = '\u2713';
      text.style.color = 'var(--success)';
      text.textContent = t('page.connectivity.online');
      dot.style.animation = '';
      if (pulse) { pulse.style.background = 'var(--success)'; triggerPulse(pulse); }
    } else {
      dot.style.background = 'var(--danger)';
      dot.textContent = '\u2717';
      text.style.color = 'var(--danger)';
      dot.style.animation = 'blink 1s infinite';
      text.textContent = t('page.connectivity.offline');
      if (pulse) { pulse.style.background = 'var(--danger)'; triggerPulse(pulse); }
    }

    if (sub) {
      const pct = data.total > 0 ? Math.round(data.alive_count / data.total * 100) : 0;
      const latencies = data.latencies || {};
      const latParts = Object.entries(latencies).map(([h, ms]) => ms >= 0 ? h + ':' + ms + 'ms' : h + ':fail');
      sub.textContent = pct + '% reachable | ' + latParts.join(' | ');
    }

    if (isAlive && data.direct_ip) {
      if (lastIp && data.direct_ip !== lastIp) {
        // IP change is logged as an event by the backend; frontend just keeps state.
      }
      lastIp = data.direct_ip;
    }
    lastAlive = isAlive;
  }

  function triggerPulse(el) {
    el.style.opacity = '0.6';
    el.style.transform = 'scale(1)';
    el.style.transition = 'none';
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        el.style.transition = 'opacity 0.8s, transform 0.8s';
        el.style.opacity = '0';
        el.style.transform = 'scale(2)';
      });
    });
  }

  function addEvent(type, msg, variant) {
    const ts = new Date().toLocaleTimeString();
    eventLog.unshift({ ts, type, msg, variant });
    if (eventLog.length > 100) eventLog.length = 100;
    renderEventLog();
  }

  function renderEventLog() {
    const wrap = document.getElementById('canary-log-wrap');
    if (!wrap) return;
    wrap.innerHTML = '';
    eventLog.forEach(ev => {
      const line = ui.el('div', '', { style: 'padding:2px 0;border-bottom:1px solid var(--border)' });
      const tsSpan = ui.el('span', '', { style: 'color:var(--text-muted);margin-right:8px', text: ev.ts });
      const typeColor = ev.variant === 'ok' ? 'var(--success)' : ev.variant === 'error' ? 'var(--danger)' : ev.variant === 'warn' ? 'var(--warning,#9a6700)' : 'var(--text-secondary)';
      const typeSpan = ui.el('span', '', { style: 'color:' + typeColor + ';font-weight:700;margin-right:8px;min-width:60px;display:inline-block', text: ev.type });
      const msgSpan = ui.el('span', '', { text: ev.msg });
      line.appendChild(tsSpan);
      line.appendChild(typeSpan);
      line.appendChild(msgSpan);
      wrap.appendChild(line);
    });
  }

  function updateDirectInfo(data) {
    if (!data) return;
    const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val || '\u2014'; };
    setEl('di-ip', data.direct_ip);
    setEl('di-country', data.direct_country);
    setEl('di-city', data.direct_city);
    setEl('di-isp', data.direct_isp);
  }

  function updateHostsCard(data) {
    if (!data) return;
    const wrap = document.getElementById('canary-hosts-tbl');
    if (!wrap) return;
    renderChips(data.canary_hosts || []);
    const hosts = data.hosts || {};
    const latencies = data.latencies || {};
    const entries = Object.entries(hosts);
    if (!entries.length) { wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">' + t('page.connectivity.noCanaryHosts') + '</div>'; return; }

    const headers = [
      { label: 'Host', width: '180px' },
      { label: 'Status', width: '80px', align: 'center' },
      { label: 'Latency', width: '70px', align: 'center' },
    ];

    const rows = entries.map(([host, ok]) => {
      const ms = latencies[host];
      return [
        '<span style="font-family:ui-monospace,monospace;font-size:12px">' + ui.escHtml(host) + '</span>',
        ok ? '<span style="color:var(--success);font-weight:600">OK</span>' : '<span style="color:var(--danger);font-weight:600">FAIL</span>',
        ms >= 0 ? '<span style="color:' + (ms < 50 ? 'var(--success)' : ms < 200 ? 'var(--warning,#9a6700)' : 'var(--danger)') + ';font-weight:600">' + ms + 'ms</span>' : '<span style="color:var(--text-muted)">\u2014</span>',
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  function updateGraph(hist) {
    const canvas = document.getElementById('canary-canvas');
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 10 || rect.height < 10) return;
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    const W = rect.width;
    const H = rect.height;
    ctx.clearRect(0, 0, W, H);
    const colorOk = getComputedStyle(document.documentElement).getPropertyValue('--success').trim() || '#1a7f37';
    const colorFail = getComputedStyle(document.documentElement).getPropertyValue('--danger').trim() || '#cf222e';
    const colorMuted = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#888';
    if (!hist || !hist.length) {
      ctx.fillStyle = colorMuted; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText(t('page.connectivity.noDataYet'), W / 2, H / 2); return;
    }
    const pad = 4;
    const barH = H - 24;
    const barW = Math.max(2, (W - pad * 2) / hist.length - 1);
    for (let i = 0; i < hist.length; i++) {
      const x = pad + i * (barW + 1);
      ctx.fillStyle = hist[i].alive ? colorOk : colorFail;
      ctx.fillRect(x, 10, barW, barH);
    }
    ctx.fillStyle = colorMuted; ctx.font = '9px sans-serif';
    ctx.textAlign = 'left'; ctx.fillText(new Date(hist[0].ts * 1000).toLocaleTimeString(), pad, H - 2);
    ctx.textAlign = 'right'; ctx.fillText(new Date(hist[hist.length - 1].ts * 1000).toLocaleTimeString(), W - pad, H - 2);
  }

  build();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      let data = null;
      let hist = [];
      try { data = await api.canaryStatus(); } catch (e) { console.error('canaryStatus', e); }
      try { hist = await api.canaryHistory(24); } catch (e) { console.error('canaryHistory', e); }
      canaryData = data;
      history = hist;
      if (data) {
        updateStatusCard(data);
        updateDirectInfo(data);
        updateHostsCard(data);
      }
      updateGraph(hist);
      const dot = document.getElementById('canary-dot');
      const text = document.getElementById('canary-text');
      if (dot && text && data) {
        if (data.alive) { dot.className = 'status-dot online'; text.textContent = t('sidebar.internetOK'); }
        else { dot.className = 'status-dot offline'; text.textContent = t('sidebar.internetDown'); }
      }
    } catch (e) {
      console.error('connectivity load', e);
    } finally {
      _loading = false;
    }
  }

  async function loadEvents() {
    try {
      const activity = await api.activity(200);
      const connectivityTypes = ['ok', 'error', 'warn'];
      eventLog = (activity || []).filter(e => {
        const msg = (e.msg || '').toLowerCase();
        return msg.includes('internet') || msg.includes('isp changed') || msg.includes('canary');
      }).map(e => ({
        ts: new Date(e.ts * 1000).toLocaleTimeString(),
        type: e.type === 'ok' ? 'UP' : e.type === 'error' ? 'DOWN' : e.type === 'warn' ? 'CHANGE' : String(e.type).toUpperCase(),
        msg: e.msg,
        variant: e.type === 'ok' ? 'ok' : e.type === 'error' ? 'error' : e.type === 'warn' ? 'warn' : 'info',
      })).slice(0, 100);
      renderEventLog();
    } catch (e) {
      console.error('connectivity events load', e);
    }
  }

  load();
  loadEvents();
  const id = setInterval(load, 10000);
  const eventId = setInterval(loadEvents, 10000);
  if (window._pageIntervals) {
    window._pageIntervals.push(id, eventId);
  } else {
    window._pageIntervals = [id, eventId];
  }
});
