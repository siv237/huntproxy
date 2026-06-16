router.register('proxy-control', (container) => {
  const els = {};

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    // Row 1: KPI Cards (6)
    const row1 = ui.el('div', 'grid grid-6');
    const kpiDefs = [
      { id: 'kpi-active', label: t('page.proxyControl.activeProxy'), sub: t('page.proxyControl.status'), color: 'var(--success)' },
      { id: 'kpi-type', label: t('page.proxyControl.proxyType'), sub: 'CONNECT', color: 'var(--accent)' },
      { id: 'kpi-uptime', label: t('page.proxyControl.uptime'), sub: t('page.proxyControl.sinceStart'), color: 'var(--text-secondary)' },
      { id: 'kpi-req', label: t('page.proxyControl.requests24h'), sub: t('common.vsYesterday'), color: 'var(--info)' },
      { id: 'kpi-sr', label: t('page.proxyControl.successRate'), sub: t('common.vsYesterday'), color: 'var(--success)' },
      { id: 'kpi-rt', label: t('page.proxyControl.avgResponseTime'), sub: t('common.vsYesterday'), color: 'var(--warning)' },
    ];
    kpiDefs.forEach(k => {
      const card = ui.statCard(k.label, '—', null, [10,15,12,18,20,16,22]);
      card.id = k.id;
      els[k.id] = card;
      row1.appendChild(card);
    });
    container.appendChild(row1);

    // Row 2: Traffic Overview + Current Proxy + Connected Clients
    const row2 = ui.el('div', 'grid grid-3 row-stretch');
    const trafficCard = ui.card(t('page.proxyControl.trafficOverview'));
    trafficCard.id = 'card-traffic';
    trafficCard.style.gridColumn = 'span 2';
    trafficCard.style.overflow = 'hidden';
    els.traffic = trafficCard;
    row2.appendChild(trafficCard);

    const rightCol = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:10px;min-height:0;overflow:hidden' });
    const curCard = ui.card(t('page.proxyControl.currentProxy'));
    curCard.id = 'card-cur-proxy';
    curCard.style.flex = '1';
    curCard.style.minHeight = '0';
    curCard.style.overflow = 'hidden';
    els.curProxy = curCard;
    rightCol.appendChild(curCard);

    const clientsCard = ui.card(t('page.proxyControl.connectedClients'), t('common.viewAll'));
    clientsCard.id = 'card-clients';
    clientsCard.style.flex = '1';
    clientsCard.style.minHeight = '0';
    clientsCard.style.overflow = 'hidden';
    els.clients = clientsCard;
    rightCol.appendChild(clientsCard);
    row2.appendChild(rightCol);
    container.appendChild(row2);

    // Row 3: Top Domains + Error Breakdown + Bandwidth
    const row3 = ui.el('div', 'grid grid-3 row-stretch');
    const domainsCard = ui.card(t('page.proxyControl.topDomains'));
    domainsCard.id = 'card-domains';
    domainsCard.style.overflow = 'hidden';
    els.domains = domainsCard;
    row3.appendChild(domainsCard);

    const errCard = ui.card(t('page.proxyControl.errorBreakdown'), t('common.viewAll'));
    errCard.id = 'card-errors';
    errCard.style.overflow = 'hidden';
    els.errors = errCard;
    row3.appendChild(errCard);

    const bwCard = ui.card(t('page.proxyControl.bandwidthUsage'));
    bwCard.id = 'card-bandwidth';
    bwCard.style.overflow = 'hidden';
    els.bandwidth = bwCard;
    row3.appendChild(bwCard);
    container.appendChild(row3);

    // Row 4: Recent Requests + Proxy Health
    const row4 = ui.el('div', 'grid grid-2 row-stretch');
    const reqCard = ui.card(t('page.proxyControl.recentRequests'));
    reqCard.id = 'card-recent-req';
    reqCard.style.overflow = 'hidden';
    els.recentReq = reqCard;
    row4.appendChild(reqCard);

    const healthCard = ui.card(t('page.proxyControl.proxyHealth'));
    healthCard.id = 'card-proxy-health';
    healthCard.style.overflow = 'hidden';
    els.proxyHealth = healthCard;
    row4.appendChild(healthCard);
    container.appendChild(row4);
  }

  build();

  // --- Updaters ---
  function updateKPIs(ps, traffic, requests) {
    const ap = ps && ps.active_proxy;
    const totalReq = requests && requests.requests ? requests.requests.length : 0;
    const successCount = requests && requests.requests ? requests.requests.filter(r => {
      const st = (r.status || '').toString();
      return st.startsWith('2') || st.startsWith('ok') || st === '200';
    }).length : 0;
    const sr = totalReq ? (successCount / totalReq * 100) : 0;

    const kpiMap = {
      'kpi-active': { value: ap ? ap.address.split(':')[0] : t('page.proxyControl.none'), sub: ap ? (ap.last_status === 'ok' ? t('page.proxyControl.healthy') : t('page.proxyControl.unhealthy')) : '—' },
      'kpi-type': { value: ap ? (ap.protocol || 'HTTP').toUpperCase() : '—', sub: 'CONNECT' },
      'kpi-uptime': { value: '—', sub: t('page.proxyControl.sinceStart') },
      'kpi-req': { value: totalReq.toLocaleString(), sub: '—' },
      'kpi-sr': { value: sr.toFixed(1) + '%', sub: '—' },
      'kpi-rt': { value: '—', sub: '—' },
    };
    Object.entries(kpiMap).forEach(([id, data]) => {
      const card = document.getElementById(id);
      if (!card) return;
      const val = card.querySelector('.stat-value');
      if (val) val.textContent = data.value;
      const sub = card.querySelector('.stat-delta');
      if (sub) {
        sub.style.display = 'block';
        sub.textContent = data.sub;
      }
    });
  }

  function updateTraffic(card, traffic) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.trafficOverview') }));
    const tabs = ui.tabs(['Requests', 'Bandwidth', 'Response Time', 'Errors'], (name) => {
      // For MVP, all tabs show same Requests graph
      renderTrafficGraph(card, traffic);
    });
    header.appendChild(tabs);
    card.appendChild(header);
    renderTrafficGraph(card, traffic);
  }

  function renderTrafficGraph(card, traffic) {
    const existing = card.querySelector('.traffic-body');
    if (existing) existing.remove();

    const body = ui.el('div', 'traffic-body', { style: 'display:flex;gap:16px;flex:1;min-height:0;overflow:hidden' });
    const left = ui.el('div', '', { style: 'flex:1;min-width:0;min-height:0;display:flex;overflow:hidden' });
    const pts = traffic && traffic.points ? traffic.points.slice(-48) : [];
    if (pts.length >= 2) {
      const data = pts.map(p => p.requests || 0);
      const labels = pts.map(p => {
        const d = new Date(p.ts * 1000);
        return `${d.getHours()}:${d.getMinutes().toString().padStart(2,'0')}`;
      });
      left.innerHTML = charts.lineChart(data, { width: 500, height: 200, labels, color: 'var(--accent)', fillArea: true, responsive: true });
    } else {
      left.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noTrafficData') }));
    }
    body.appendChild(left);

    const right = ui.el('div', '', { style: 'width:160px;flex-shrink:0;display:flex;flex-direction:column;gap:6px;overflow:hidden' });
    const last = pts.length ? pts[pts.length-1] : null;
    const totalReq = pts.reduce((s, p) => s + (p.requests || 0), 0);
    const totalOk = pts.reduce((s, p) => s + (p.connections_ok || 0), 0);
    const totalFailed = pts.reduce((s, p) => s + (p.connections_failed || 0), 0);
    const totalBwIn = pts.reduce((s, p) => s + (p.bandwidth_in || 0), 0);
    const totalBwOut = pts.reduce((s, p) => s + (p.bandwidth_out || 0), 0);
    const fmtBytes = b => {
      if (b >= 1024*1024*1024) return (b/(1024*1024*1024)).toFixed(2) + ' GB';
      if (b >= 1024*1024) return (b/(1024*1024)).toFixed(1) + ' MB';
      if (b >= 1024) return (b/1024).toFixed(1) + ' KB';
      return b + ' B';
    };
    const items = [
      { label: t('page.proxyControl.totalRequests'), value: totalReq.toLocaleString(), color: 'var(--text-primary)' },
      { label: t('page.proxyControl.successful'), value: totalOk.toLocaleString(), color: 'var(--success)' },
      { label: t('page.proxyControl.failed'), value: totalFailed.toLocaleString(), color: 'var(--danger)' },
      { label: t('page.proxyControl.bandwidthIn'), value: fmtBytes(totalBwIn), color: 'var(--text-secondary)' },
      { label: t('page.proxyControl.bandwidthOut'), value: fmtBytes(totalBwOut), color: 'var(--text-secondary)' },
    ];
    items.forEach(item => {
      const row = ui.el('div', '', { style: 'display:flex;justify-content:space-between;align-items:center;font-size:12px;padding:4px 0;border-bottom:1px solid var(--border-subtle)' });
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary)', text: item.label }));
      row.appendChild(ui.el('span', '', { style: `font-weight:700;color:${item.color}`, text: item.value }));
      right.appendChild(row);
    });
    body.appendChild(right);
    card.appendChild(body);
  }

  function updateCurProxy(card, ps) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.currentProxy') }));
    const btn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.proxyControl.changeProxy') });
    btn.addEventListener('click', () => router.navigate('proxy-pool'));
    header.appendChild(btn);
    card.appendChild(header);

    const ap = ps && ps.active_proxy;
    if (!ap) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noActiveProxy') }));
      return;
    }

    const top = ui.el('div', '', { style: 'display:flex;align-items:center;gap:10px;margin-bottom:12px' });
    top.appendChild(ui.el('div', '', { style: 'font-size:16px;font-weight:700;font-family:monospace;color:var(--accent)', text: ap.address }));
    top.appendChild(ui.badge(ap.last_status === 'ok' ? t('page.proxyControl.healthy') : t('page.proxyControl.unhealthy'), ap.last_status === 'ok' ? 'green' : 'red'));
    top.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code) }));
    card.appendChild(top);

    const grid = ui.el('div', 'grid grid-2');
    const items = [
      { label: t('page.proxyControl.status'), value: ap.last_status === 'ok' ? t('page.proxyControl.healthy') : t('page.proxyControl.unhealthy') },
      { label: t('page.proxyControl.latency'), value: ui.fmtLatency(ap.last_latency) },
      { label: t('page.proxyControl.responseTimeAvg'), value: '—' },
      { label: t('page.proxyControl.successRate'), value: ui.fmtPct(ap.success_rate) },
      { label: t('page.proxyControl.lastCheck'), value: ui.ago(ap.last_check) },
      { label: t('page.proxyControl.fails'), value: (ap.checks_total - ap.checks_ok) + ' / ' + ap.checks_total },
      { label: t('page.proxyControl.speed'), value: ap.speed_avg ? ap.speed_avg.toFixed(0) + ' KB/s' : '—' },
      { label: t('page.proxyControl.protocol'), value: (ap.protocol || 'HTTP').toUpperCase() },
    ];
    items.forEach(item => {
      const cell = ui.el('div', '', { style: 'text-align:center;padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
      cell.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-secondary)', text: item.label }));
      cell.appendChild(ui.el('div', '', { style: 'font-size:14px;font-weight:600', text: item.value }));
      grid.appendChild(cell);
    });
    card.appendChild(grid);
  }

  function updateClients(card, clients) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.connectedClients') }));
    const live = ui.el('div', '', { style: 'display:flex;align-items:center;gap:6px;font-size:12px;color:var(--success)' });
    live.innerHTML = '<span class="pulse" style="width:8px;height:8px"></span> ' + t('page.proxyControl.live');
    header.appendChild(live);
    const va = ui.el('button', 'card-action', { text: t('common.viewAll') });
    va.addEventListener('click', () => router.navigate('logs'));
    header.appendChild(va);
    card.appendChild(header);

    const list = clients && clients.clients ? clients.clients : [];
    const total = list.reduce((s, c) => s + (c.requests || 0), 0);
    const totalEl = ui.el('div', '', { style: 'font-size:24px;font-weight:700;margin-bottom:8px', text: total.toLocaleString() });
    card.appendChild(totalEl);
    const subEl = ui.el('div', '', { style: 'font-size:11px;color:var(--text-secondary);margin-bottom:12px', text: t('page.proxyControl.totalConnections') });
    card.appendChild(subEl);

    if (!list.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noClients') }));
      return;
    }

    const headers = [
      { label: 'IP Address', width: '120px' },
      { label: 'Country', width: '80px' },
      { label: 'Requests', width: '70px', align: 'right' },
      { label: 'Last Seen', width: '80px', align: 'right' },
    ];
    const rows = list.slice(0, 8).map(c => [
      c.client || '—',
      '—', // Country not available in proxy log
      (c.requests || 0).toLocaleString(),
      ui.ago(c.last_seen),
    ]);
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, rows));
    card.appendChild(tblWrap);
  }

  function updateDomains(card, domains) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.topDomains') }));
    card.appendChild(header);

    const list = domains && domains.domains ? domains.domains : [];
    if (!list.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noDomainData') }));
      return;
    }

    const headers = [
      { label: 'Domain', width: '160px' },
      { label: 'Requests', width: '70px', align: 'right' },
      { label: '% of Total', width: '70px', align: 'right' },
      { label: 'Avg Response', width: '90px', align: 'right' },
      { label: 'Status', width: '60px', align: 'center' },
    ];
    const total = list.reduce((s, d) => s + (d.requests || 0), 0) || 1;
    const rows = list.slice(0, 10).map(d => [
      d.domain || '—',
      (d.requests || 0).toLocaleString(),
      ((d.requests || 0) / total * 100).toFixed(1) + '%',
      '—', // Avg response placeholder
      '<span style="color:var(--success)">200</span>', // Placeholder status
    ]);
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, rows));
    card.appendChild(tblWrap);
  }

  function updateErrors(card, errors) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.errorBreakdown') }));
    const va = ui.el('button', 'card-action', { text: t('common.viewAll') });
    va.addEventListener('click', () => router.navigate('logs'));
    header.appendChild(va);
    card.appendChild(header);

    const list = errors && errors.errors ? errors.errors : [];
    const total = errors && errors.total ? errors.total : 0;

    const wrap = ui.el('div', '', { style: 'display:flex;align-items:center;gap:20px;flex-wrap:wrap' });
    const donutWrap = ui.el('div', '', { style: 'flex-shrink:0' });
    donutWrap.innerHTML = charts.donutChart(list.map((e, i) => ({
      label: e.type,
      value: e.count,
      color: ['var(--danger)', 'var(--warning)', 'var(--info)', 'var(--accent)'][i % 4],
    })), { size: 120, centerText: total.toString(),       centerLabel: t('page.proxyControl.totalErrors') });
    wrap.appendChild(donutWrap);

    const legend = ui.el('div', '', { style: 'flex:1;min-width:120px;display:flex;flex-direction:column;gap:8px' });
    if (!list.length) {
      legend.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noErrors') }));
    } else {
      list.forEach((e, i) => {
        const col = ['var(--danger)', 'var(--warning)', 'var(--info)', 'var(--accent)'][i % 4];
        const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;font-size:12px' });
        row.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:${col};flex-shrink:0"></span><span style="flex:1">${e.type}</span><span style="font-weight:600">${e.count}</span><span style="color:var(--text-muted)">(${e.pct || 0}%)</span>`;
        legend.appendChild(row);
      });
    }
    wrap.appendChild(legend);
    card.appendChild(wrap);
  }

  function updateBandwidth(card, bw) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.bandwidth24h') }));
    card.appendChild(header);

    const fmtBytes = b => {
      if (b >= 1024*1024*1024) return (b/(1024*1024*1024)).toFixed(2) + ' GB';
      if (b >= 1024*1024) return (b/(1024*1024)).toFixed(1) + ' MB';
      if (b >= 1024) return (b/1024).toFixed(1) + ' KB';
      return b + ' B';
    };
    const incoming = bw ? (bw.incoming || 0) : 0;
    const outgoing = bw ? (bw.outgoing || 0) : 0;

    const wrap = ui.el('div', 'grid grid-2');
    const incomingEl = ui.el('div', '', { style: 'text-align:center;padding:12px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
    incomingEl.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxyControl.incoming') }));
    incomingEl.appendChild(ui.el('div', '', { style: 'font-size:20px;font-weight:700', text: incoming ? fmtBytes(incoming) : '—' }));
    incomingEl.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--success)', text: incoming ? (bw.incoming_gb || 0).toFixed(3) + ' GB' : '↑ —%' }));
    wrap.appendChild(incomingEl);

    const outgoingEl = ui.el('div', '', { style: 'text-align:center;padding:12px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
    outgoingEl.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxyControl.outgoing') }));
    outgoingEl.appendChild(ui.el('div', '', { style: 'font-size:20px;font-weight:700', text: outgoing ? fmtBytes(outgoing) : '—' }));
    outgoingEl.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--success)', text: outgoing ? (bw.outgoing_gb || 0).toFixed(3) + ' GB' : '↑ —%' }));
    wrap.appendChild(outgoingEl);
    card.appendChild(wrap);
  }

  function updateRecentRequests(card, requests) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.recentRequests') }));
    card.appendChild(header);

    const list = requests && requests.requests ? requests.requests : [];
    if (!list.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noRecentRequests') }));
      return;
    }

    const fmtBytes = b => {
      if (!b) return '—';
      if (b >= 1024*1024) return (b/(1024*1024)).toFixed(1) + ' MB';
      if (b >= 1024) return (b/1024).toFixed(1) + ' KB';
      return b + ' B';
    };

    const headers = [
      { label: 'Time', width: '60px' },
      { label: 'Client IP', width: '100px' },
      { label: 'Target', width: '180px' },
      { label: 'Status', width: '50px', align: 'center' },
      { label: 'Duration', width: '70px', align: 'right' },
      { label: 'Size In', width: '60px', align: 'right' },
      { label: 'Size Out', width: '60px', align: 'right' },
      { label: 'Proxy', width: '120px' },
    ];
    const rows = list.slice(0, 10).map(r => {
      const st = (r.status || '').toString();
      const isOk = st === 'ok' || st === '200';
      const dur = r.duration ? r.duration.toFixed(3) + 's' : '—';
      const upstream = r.upstream && r.upstream !== '?' ? r.upstream : 'direct';
      return [
        ui.fmtTime(r.ts || 0).split(' ')[0],
        r.client || '—',
        `<span style="max-width:160px;overflow:hidden;text-overflow:ellipsis;display:inline-block;white-space:nowrap">${r.target || '—'}</span>`,
        `<span style="color:${isOk ? 'var(--success)' : 'var(--danger)'}">${st || '—'}</span>`,
        dur,
        fmtBytes(r.bytes_in),
        fmtBytes(r.bytes_out),
        `<span style="color:var(--info)">${ui.escHtml(upstream)}</span>`,
      ];
    });
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, rows));
    card.appendChild(tblWrap);
  }

  function updateProxyHealth(card, ps, history) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.proxyHealth') }));
    card.appendChild(header);

    const pts = history && history.length ? history.slice(-48) : [];
    if (pts.length >= 2) {
      const data = pts.map(p => p.traffic_success_rate != null ? p.traffic_success_rate : (p.success_rate || 0));
      const labels = pts.map(p => {
        const d = new Date(p.ts * 1000);
        return `${d.getHours()}:${d.getMinutes().toString().padStart(2,'0')}`;
      });
      card.appendChild(ui.el('div', '', { style: 'flex:1;min-height:0;display:flex',
        html: charts.lineChart(data, { width: 400, height: 120, labels, color: 'var(--success)', fillArea: true, responsive: true })
      }));
    } else {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noHealthData') }));
    }

    const ap = ps && ps.active_proxy;
    const grid = ui.el('div', 'grid grid-4', { style: 'margin-top:auto;flex-shrink:0' });
    const healthScore = ap ? Math.round(ap.score) : 0;
    const failures = ap ? (ap.checks_total - ap.checks_ok) : 0;
    const avgLat = ap ? ap.last_latency : 0;
    const checks = ap ? ap.checks_total : 0;
    const avgResp = pts.length ? (pts.reduce((s,p) => s + (p.avg_latency || 0), 0) / pts.length).toFixed(3) + 's' : '—';
    const items = [
      { label: t('page.proxyControl.healthScore'), value: healthScore + '%', color: 'var(--success)' },
      { label: t('page.proxyControl.failures'), value: failures.toString(), color: 'var(--danger)' },
      { label: t('page.proxyControl.avgResponse'), value: avgResp, color: 'var(--text-primary)' },
      { label: t('page.proxyControl.checks'), value: checks.toLocaleString(), color: 'var(--text-primary)' },
    ];
    items.forEach(item => {
      const cell = ui.el('div', '', { style: 'text-align:center;padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
      cell.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-secondary)', text: item.label }));
      cell.appendChild(ui.el('div', '', { style: `font-size:16px;font-weight:600;color:${item.color}`, text: item.value }));
      grid.appendChild(cell);
    });
    card.appendChild(grid);
  }

  // --- Polling ---
  async function poll() {
    try {
      let ps = {}, traffic = {}, requests = {}, clients = {}, domains = {}, errors = {}, bw = {}, history = [];
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { traffic = await api.traffic(); } catch (e) { console.error('traffic', e); }
      try { requests = await api.requests(); } catch (e) { console.error('requests', e); }
      try { clients = await api.clients(); } catch (e) { console.error('clients', e); }
      try { domains = await api.domains(); } catch (e) { console.error('domains', e); }
      try { errors = await api.errors(); } catch (e) { console.error('errors', e); }
      try { bw = await api.bandwidth(); } catch (e) { console.error('bandwidth', e); }
      try { history = await api.history('24h'); } catch (e) { console.error('history', e); }

      try { updateKPIs(ps, traffic, requests); } catch (e) { console.error('kpi update', e); }
      try { updateTraffic(els.traffic, traffic); } catch (e) { console.error('traffic update', e); }
      try { updateCurProxy(els.curProxy, ps); } catch (e) { console.error('curProxy update', e); }
      try { updateClients(els.clients, clients); } catch (e) { console.error('clients update', e); }
      try { updateDomains(els.domains, domains); } catch (e) { console.error('domains update', e); }
      try { updateErrors(els.errors, errors); } catch (e) { console.error('errors update', e); }
      try { updateBandwidth(els.bandwidth, bw); } catch (e) { console.error('bandwidth update', e); }
      try { updateRecentRequests(els.recentReq, requests); } catch (e) { console.error('recentReq update', e); }
      try { updateProxyHealth(els.proxyHealth, ps, history); } catch (e) { console.error('proxyHealth update', e); }
    } catch (e) {
      console.error('proxy-control poll', e);
    }
  }

  poll();
  const id = setInterval(poll, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
