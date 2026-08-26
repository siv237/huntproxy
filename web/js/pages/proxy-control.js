router.register('proxy-control', (container) => {
  const els = {};
  let lastReqIds = new Set();
  let autoRefresh = true;
  let lastUpdate = 0;
  let range = '1h';
  let showAllStream = false;
  let historyCache = [];
  let filter = '';
  let lastRequestsData = null;
  let lastClientsData = null;

  // Substring match across everything the row can show: client, its DNS
  // name, target, upstream chain + geo (country/ISP), ingress type, status.
  function rowMatches(r) {
    if (!filter) return true;
    const hay = [
      r.client, clientHostnameMap[r.client], r.target, r.status, r.via,
      r.upstream,
    ];
    const ups = (r.upstream || '').split(' → ');
    ups.forEach(p => {
      const m = p.match(/^(?:proxy|pool|custom):([^\s(]+)/);
      if (m) {
        const g = geoMap[m[1]];
        if (g) hay.push(g.egress_country, g.egress_country_code, g.egress_isp, g.country, g.country_code, g.isp);
      }
    });
    return hay.some(v => v && String(v).toLowerCase().includes(filter));
  }

  const RANGES = [
    ['5m', 5, 'page.proxyControl.r5m'],
    ['15m', 15, 'page.proxyControl.r15m'],
    ['1h', 60, 'page.proxyControl.r1h'],
    ['6h', 360, 'page.proxyControl.r6h'],
    ['24h', 1440, 'page.proxyControl.r24h'],
  ];

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '14px';
    container.style.minHeight = '0';
    container.style.flex = '1';
    container.style.overflowY = 'auto';
    container.style.padding = '14px 16px 10px';

    buildHeader();
    buildKpis();
    buildStreamAndRoutes();
    buildTopsRow();
    buildBottomRow();
    buildFooter();
  }

  // ── Page header: period tabs + filter + auto-refresh + refresh ──
  function buildHeader() {
    const head = ui.el('div', 'pc-head');
    const right = ui.el('div', 'pc-head-right');

    const searchWrap = ui.el('div', 'pc-search');
    const searchIcon = ui.el('span', 'pc-search-icon', { html: pcSvg('search') });
    const input = ui.el('input', 'pc-search-input', { type: 'text', placeholder: t('page.proxyControl.filterHint'), spellcheck: 'false' });
    let debounce = null;
    input.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        filter = input.value.toLowerCase().trim();
        if (lastStreamData) updateStream(null);
        if (lastRequestsData) updateDomains(lastRequestsData);
        if (lastClientsData) updateClients(lastClientsData);
      }, 120);
    });
    searchWrap.appendChild(searchIcon);
    searchWrap.appendChild(input);
    right.appendChild(searchWrap);

    const tabs = ui.el('div', 'pc-range');
    RANGES.forEach(([key, , locKey]) => {
      const tab = ui.el('button', 'pc-range-btn' + (key === range ? ' active' : ''), { text: t(locKey) });
      tab.addEventListener('click', () => {
        range = key;
        tabs.querySelectorAll('.pc-range-btn').forEach(b => b.classList.remove('active'));
        tab.classList.add('active');
        updateTimeChart();
      });
      tabs.appendChild(tab);
    });
    right.appendChild(tabs);

    const auto = ui.el('button', 'pc-auto-pill on');
    auto.innerHTML = `<span class="pulse"></span><span class="pc-auto-text">${t('page.proxyControl.autoOn')}</span>`;
    auto.addEventListener('click', () => {
      autoRefresh = !autoRefresh;
      auto.classList.toggle('on', autoRefresh);
      auto.querySelector('.pulse').classList.toggle('off', !autoRefresh);
      auto.querySelector('.pc-auto-text').textContent = autoRefresh ? t('page.proxyControl.autoOn') : t('page.proxyControl.autoOff');
    });
    right.appendChild(auto);

    const refresh = ui.el('button', 'pc-icon-btn', { html: pcSvg('refresh'), title: t('common.refresh') });
    refresh.addEventListener('click', () => poll());
    right.appendChild(refresh);

    head.appendChild(right);
    container.appendChild(head);
  }

  // ── KPI row: 6 tiles ──
  function buildKpis() {
    const row = ui.el('div', 'pc-kpis');
    const tiles = [
      { id: 'tile-clients', icon: 'users', color: 'var(--accent)' },
      { id: 'tile-req', icon: 'zap', color: 'var(--info)', spark: true },
      { id: 'tile-dl', icon: 'download', color: 'var(--info)', spark: true },
      { id: 'tile-ul', icon: 'upload', color: 'var(--warning)', spark: true },
      { id: 'tile-rt', icon: 'clock', color: '#8a2be2', spark: true },
      { id: 'tile-sr', icon: 'check', color: 'var(--success)' },
    ];
    tiles.forEach(ti => {
      const card = ui.el('div', 'card pc-kpi');
      card.id = ti.id;
      card.innerHTML =
        `<div class="pc-kpi-icon" style="color:${ti.color};background:color-mix(in srgb, ${ti.color} 10%, transparent)">${pcSvg(ti.icon)}</div>` +
        `<div class="pc-kpi-body">` +
          `<div class="pc-kpi-label"></div>` +
          `<div class="pc-kpi-value">—</div>` +
          `<div class="pc-kpi-sub"></div>` +
        `</div>` +
        (ti.spark ? `<div class="pc-kpi-spark" id="spark-${ti.id}"></div>` : '');
      row.appendChild(card);
    });
    container.appendChild(row);
  }

  // ── Live stream (2/3) + Route distribution donut (1/3) ──
  function buildStreamAndRoutes() {
    const row = ui.el('div', 'pc-row pc-row-stream');

    const streamCard = ui.el('div', 'card pc-card');
    streamCard.id = 'card-stream';
    const sh = ui.el('div', 'pc-card-head');
    sh.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.liveStream') }));
    const showAll = ui.el('button', 'pc-link', { text: t('common.viewAll') });
    showAll.addEventListener('click', () => {
      showAllStream = !showAllStream;
      showAll.textContent = showAllStream ? t('page.proxyControl.showLess') : t('common.viewAll');
      updateStream(lastStreamData);
    });
    sh.appendChild(showAll);
    const pulseEl = ui.el('div', 'tm-live-pulse');
    pulseEl.innerHTML = '<span class="pulse"></span> ' + t('page.proxyControl.live');
    sh.appendChild(pulseEl);
    streamCard.appendChild(sh);
    const streamBody = ui.el('div', 'pc-stream-body');
    streamCard.appendChild(streamBody);
    els.streamBody = streamBody;
    row.appendChild(streamCard);

    const routeCard = ui.el('div', 'card pc-card');
    routeCard.id = 'card-routes';
    const rh = ui.el('div', 'pc-card-head');
    rh.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.routeDistribution') }));
    routeCard.appendChild(rh);
    const donutBody = ui.el('div', 'pc-donut-body');
    routeCard.appendChild(donutBody);
    els.donutBody = donutBody;
    row.appendChild(routeCard);

    container.appendChild(row);
  }

  // ── Tops row: destinations / clients / time chart ──
  function buildTopsRow() {
    const row = ui.el('div', 'pc-row pc-row-3');

    const domCard = ui.el('div', 'card pc-card');
    const dh = ui.el('div', 'pc-card-head');
    dh.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.topDestinations') }));
    domCard.appendChild(dh);
    els.domains = ui.el('div', 'pc-list');
    domCard.appendChild(els.domains);
    row.appendChild(domCard);

    const clCard = ui.el('div', 'card pc-card');
    const ch = ui.el('div', 'pc-card-head');
    ch.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.topClients') }));
    clCard.appendChild(ch);
    els.clients = ui.el('div', 'pc-list');
    clCard.appendChild(els.clients);
    row.appendChild(clCard);

    const timeCard = ui.el('div', 'card pc-card');
    const th = ui.el('div', 'pc-card-head');
    th.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.trafficOverTime') }));
    const legend = ui.el('div', 'pc-chart-legend');
    legend.innerHTML = `<span><span class="pc-dot" style="background:var(--info)"></span>${t('page.proxyControl.download')}</span>` +
      `<span><span class="pc-dot" style="background:var(--warning)"></span>${t('page.proxyControl.upload')}</span>`;
    th.appendChild(legend);
    timeCard.appendChild(th);
    els.timeBody = ui.el('div', 'pc-time-body');
    timeCard.appendChild(els.timeBody);
    row.appendChild(timeCard);

    container.appendChild(row);
  }

  // ── Bottom row: upstream / consumer / bandwidth 24h ──
  function buildBottomRow() {
    const row = ui.el('div', 'pc-row pc-row-3');

    const upCard = ui.el('div', 'card pc-card');
    const uh = ui.el('div', 'pc-card-head');
    uh.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.currentUpstream') }));
    const btn = ui.el('button', 'pc-link', { text: t('page.proxyControl.changeProxy') });
    btn.addEventListener('click', () => router.navigate('proxy-pool'));
    uh.appendChild(btn);
    upCard.appendChild(uh);
    els.upstream = ui.el('div', 'pc-list');
    upCard.appendChild(els.upstream);
    row.appendChild(upCard);

    const consumerCard = ui.el('div', 'card pc-card');
    const ch2 = ui.el('div', 'pc-card-head');
    ch2.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.trafficConsumer') }));
    const periodTabs = ui.el('div', 'pc-mini-tabs');
    const periodLabels = { day: t('page.proxyControl.period_day'), week: t('page.proxyControl.period_week'), month: t('page.proxyControl.period_month') };
    ['day', 'week', 'month'].forEach((p, i) => {
      const tab = ui.el('button', 'pc-mini-tab' + (i === 0 ? ' active' : ''), { text: periodLabels[p] });
      tab.addEventListener('click', () => {
        consumerCard.querySelectorAll('.pc-mini-tab').forEach(b => b.classList.remove('active'));
        tab.classList.add('active');
        els._consumerPeriod = p;
        if (lastSummaryData) updateConsumer(lastSummaryData);
      });
      periodTabs.appendChild(tab);
    });
    ch2.appendChild(periodTabs);
    consumerCard.appendChild(ch2);
    els.consumer = ui.el('div', 'pc-list');
    consumerCard.appendChild(els.consumer);
    row.appendChild(consumerCard);

    const bwCard = ui.el('div', 'card pc-card');
    const bh = ui.el('div', 'pc-card-head');
    bh.appendChild(ui.el('div', 'pc-card-title', { text: t('page.proxyControl.bandwidth24h') }));
    bwCard.appendChild(bh);
    els.bandwidth = ui.el('div', 'pc-list');
    bwCard.appendChild(els.bandwidth);
    row.appendChild(bwCard);

    container.appendChild(row);
  }

  // ── Footer status bar ──
  function buildFooter() {
    const footer = ui.el('div', 'pc-footer');
    footer.innerHTML =
      `<span class="pc-foot-item"><span class="pulse"></span><span id="pcf-update"></span></span>` +
      `<span class="pc-foot-item"><span class="pulse" id="pcf-dot"></span><span id="pcf-auto"></span></span>` +
      `<span class="pc-foot-right">` +
        `<span id="pcf-clients"></span><span class="pc-foot-sep"></span>` +
        `<span id="pcf-routes"></span>` +
      `</span>`;
    container.appendChild(footer);
  }

  function pcSvg(name) {
    const icons = {
      search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
      users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
      zap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
      check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
      download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
      upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
      clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
      refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
    };
    return icons[name] || '';
  }

  function fmtBytes(b) {
    if (!b || b === 0) return '0 B';
    if (b >= 1024 * 1024 * 1024) return (b / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    if (b >= 1024 * 1024) return (b / (1024 * 1024)).toFixed(1) + ' MB';
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KB';
    return b + ' B';
  }

  function routeTypeLabel(type) {
    const map = {
      direct: t('route.direct'),
      proxy: t('route.proxy'),
      pool: t('route.pool'),
      custom: t('route.custom', { name: '' }).replace(/[: ]*$/, ''),
      other: t('page.proxyControl.other'),
    };
    return map[type] || type;
  }

  // ── Updaters ──
  function updateKpis(reqs, clients, bw, history) {
    const list = reqs ? reqs.requests || [] : [];
    const totalReq = list.length;
    const okCount = list.filter(r => (r.status || '') === 'ok').length;
    const sr = totalReq ? (okCount / totalReq * 100) : null;
    const durations = list.filter(r => r.duration != null).map(r => r.duration);
    const avgDur = durations.length ? durations.reduce((a, b) => a + b, 0) / durations.length : null;
    const nowSec = Date.now() / 1000;
    const activeClients = clients ? clients.filter(c => (nowSec - (c.last_seen || 0)) < 600).length : 0;
    const totalClients = clients ? clients.length : 0;
    const download = bw ? (bw.download || 0) : 0;
    const upload = bw ? (bw.upload || 0) : 0;

    const set = (id, label, value, sub, valueColor) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.querySelector('.pc-kpi-label').textContent = label;
      const v = el.querySelector('.pc-kpi-value');
      v.textContent = value;
      v.style.color = valueColor || 'var(--text-primary)';
      el.querySelector('.pc-kpi-sub').textContent = sub || '';
    };

    set('tile-clients', t('page.proxyControl.kpiClients'), activeClients.toLocaleString(), t('page.proxyControl.kpiOfTotal', { total: totalClients }));
    set('tile-req', t('page.proxyControl.req24h'), totalReq.toLocaleString(), `${okCount.toLocaleString()} ✓`);
    set('tile-dl', t('page.proxyControl.download'), fmtBytes(download), '↓ 24h');
    set('tile-ul', t('page.proxyControl.upload'), fmtBytes(upload), '↑ 24h');
    set('tile-rt', t('page.proxyControl.kpiAvgResponse'), avgDur != null ? ui.fmtLatency(avgDur) : '—', '');
    set('tile-sr', t('page.proxyControl.successRate'),
      sr === null ? '—' : sr.toFixed(1) + '%',
      totalReq ? `${okCount}/${totalReq}` : '',
      sr === null ? 'var(--text-primary)' : sr >= 80 ? 'var(--success)' : sr >= 50 ? 'var(--warning)' : 'var(--danger)');

    const pts = history && history.length ? history.slice(-60) : [];
    const spark = (id, data, color) => {
      const el = document.getElementById(id);
      if (!el) return;
      el.innerHTML = data && data.length >= 2 ? charts.sparkline(data, color, 88, 38) : '';
    };
    spark('spark-tile-req', pts.map(p => p.requests || 0), 'var(--info)');
    spark('spark-tile-dl', pts.map(p => p.bandwidth_out || 0), 'var(--info)');
    spark('spark-tile-ul', pts.map(p => p.bandwidth_in || 0), 'var(--warning)');
    spark('spark-tile-rt', pts.filter(p => p.avg_latency > 0).map(p => p.avg_latency), '#8a2be2');
  }

  let lastStreamData = null;
  let geoMap = {};
  let clientHostnameMap = {};
  function buildGeoMap(alive, ps) {
    geoMap = {};
    (alive || []).forEach(p => { if (p && p.address) geoMap[p.address] = p; });
    const ap = ps && ps.active_proxy;
    if (ap && ap.address) geoMap[ap.address] = Object.assign({}, geoMap[ap.address], ap);
  }

  function updateStream(requests) {
    if (requests) lastStreamData = requests;
    const body = els.streamBody;
    const all = lastStreamData && lastStreamData.requests ? lastStreamData.requests : [];
    const list = filter ? all.filter(rowMatches) : all;
    const prevWrap = body.querySelector('.pc-stream-wrap');
    const prevScroll = prevWrap ? prevWrap.scrollTop : 0;
    body.innerHTML = '';
    if (!list.length) {
      body.appendChild(ui.el('div', 'pc-empty', { text: filter ? t('page.proxyControl.filterEmpty') : t('page.proxyControl.noRecentRequests') }));
      return;
    }

    const newIds = new Set();
    list.forEach(r => { newIds.add(r.ts + '|' + r.client + '|' + r.target); });

    const limit = showAllStream ? 40 : 8;
    const shown = list.slice(0, limit);
    const rows = shown.map(r => {
      const id = r.ts + '|' + r.client + '|' + r.target;
      const isNew = !lastReqIds.has(id) ? ' tm-row-new' : '';
      const dur = r.duration != null ? r.duration.toFixed(2) + 's' : '—';
      const sz = fmtBytes((r.bytes_in || 0) + (r.bytes_out || 0));
      const target = r.target || '—';
      const host = ui.hostOf(target);
      const targetShort = target.length > 34 ? target.slice(0, 32) + '…' : target;
      const client = r.client || '—';
      const hostName = clientHostnameMap[client] || '';
      return `<tr${isNew ? ' class="tm-row-new"' : ''}>` +
        `<td class="pc-td-time">${ui.fmtTime(r.ts || 0).split(' ')[0]}</td>` +
        `<td><span class="pc-client" data-client="${ui.escHtml(client)}" title="${ui.escHtml(hostName ? client + ' (' + hostName + ')' : client)}">${ui.personAvatar(client, 22)}<span class="pc-client-addr">${ui.escHtml(client)}</span></span></td>` +
        `<td>${ui.viaBadge(r.via)}</td>` +
        `<td><span class="pc-target">${ui.hostAvatar(host, 22)}<span title="${ui.escHtml(target)}">${ui.escHtml(targetShort)}</span></span></td>` +
        `<td>${ui.routeBadge(r.upstream, geoMap)}</td>` +
        `<td style="text-align:center">${ui.statusPill(r.status)}</td>` +
        `<td class="pc-td-num">${dur}</td>` +
        `<td class="pc-td-num">${sz}</td>` +
      `</tr>`;
    }).join('');

    body.innerHTML =
      `<div class="table-wrap pc-stream-wrap"><table class="table pc-stream">` +
        `<thead><tr>` +
          `<th>${t('page.proxyControl.time')}</th>` +
          `<th>${t('page.proxyControl.client')}</th>` +
          `<th>${t('page.proxyControl.via')}</th>` +
          `<th>${t('page.proxyControl.target')}</th>` +
          `<th>${t('page.proxyControl.route')}</th>` +
          `<th style="text-align:center">${t('page.proxyControl.status')}</th>` +
          `<th style="text-align:right">${t('page.proxyControl.duration')}</th>` +
          `<th style="text-align:right">${t('page.proxyControl.size')}</th>` +
        `</tr></thead>` +
        `<tbody>${rows}</tbody>` +
      `</table></div>` +
      (list.length > limit ? `<div class="pc-stream-more">${t('page.proxyControl.showingNofM', { shown: limit, total: list.length })}</div>` : '');

    body.querySelectorAll('.pc-client').forEach(el => {
      el.addEventListener('click', () => window.clientCard.show(el.dataset.client));
    });
    const newWrap = body.querySelector('.pc-stream-wrap');
    if (newWrap) newWrap.scrollTop = prevScroll;
    lastReqIds = newIds;
  }

  function updateRoutes(routes) {
    const body = els.donutBody;
    const list = routes && routes.routes ? routes.routes : [];
    body.innerHTML = '';
    if (!list.length) {
      body.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.noRouteData') }));
      return;
    }
    const totalReq = list.reduce((s, r) => s + (r.requests || 0), 0) || 1;
    const palette = { direct: 'var(--success)', proxy: 'var(--info)', pool: '#8a2be2', custom: 'var(--warning)', other: '#9CA3AF' };

    const donutData = list.slice(0, 4).map(r => ({ value: r.requests, color: palette[r.type] || palette.other }));
    if (list.length > 4) donutData.push({ value: list.slice(4).reduce((a, r) => a + r.requests, 0), color: 'var(--border)' });
    const donut = ui.el('div', 'pc-donut', {
      html: charts.donutChart(donutData, { size: 150, strokeWidth: 22, centerText: totalReq.toLocaleString(), centerLabel: t('page.proxyControl.requests') }),
    });
    body.appendChild(donut);

    const legend = ui.el('div', 'pc-donut-legend');
    list.slice(0, 5).forEach(r => {
      const pct = (r.requests / totalReq * 100);
      const color = palette[r.type] || palette.other;
      const row = ui.el('div', 'pc-donut-row');
      row.innerHTML = `<span class="pc-dot" style="background:${color}"></span>` +
        `<span class="pc-donut-name" title="${ui.escHtml(routeTypeLabel(r.type))}">${ui.escHtml(routeTypeLabel(r.type))}</span>` +
        `<b class="pc-donut-pct">${pct.toFixed(1)}%</b>` +
        `<span class="pc-donut-count">(${r.requests.toLocaleString()})</span>`;
      legend.appendChild(row);
    });
    if (list.length > 5) {
      const restPct = list.slice(5).reduce((a, r) => a + r.requests, 0) / totalReq * 100;
      legend.appendChild(ui.el('div', 'pc-donut-row', {
        html: `<span class="pc-dot" style="background:var(--border)"></span><span class="pc-donut-name">${t('page.proxyControl.other')}</span><b class="pc-donut-pct">${restPct.toFixed(1)}%</b><span class="pc-donut-count"></span>`,
      }));
    }
    body.appendChild(legend);
  }

  function updateDomains(requests) {
    if (requests) lastRequestsData = requests;
    const list = lastRequestsData && lastRequestsData.requests ? lastRequestsData.requests : [];
    els.domains.innerHTML = '';
    if (!list.length) {
      els.domains.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.noDomainData') }));
      return;
    }
    const domains = {};
    list.forEach(r => {
      const target = r.target || '';
      if (!target || target === '?') return;
      const h = ui.hostOf(target);
      if (!h) return;
      if (!domains[h]) domains[h] = { domain: h, requests: 0, bytes: 0 };
      domains[h].requests++;
      domains[h].bytes += (r.bytes_in || 0) + (r.bytes_out || 0);
    });
    const top = Object.values(domains)
      .filter(d => !filter || d.domain.toLowerCase().includes(filter))
      .sort((a, b) => b.requests - a.requests).slice(0, 6);
    if (!top.length) {
      els.domains.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.filterEmpty') }));
      return;
    }
    const total = top.reduce((s, d) => s + d.requests, 0) || 1;
    const maxReq = top[0].requests || 1;

    top.forEach(d => {
      const row = ui.el('div', 'pc-top-row');
      row.innerHTML = ui.hostAvatar(d.domain, 26) +
        `<div class="pc-top-main">` +
          `<div class="pc-top-namerow"><span class="pc-top-name" title="${ui.escHtml(d.domain)}">${ui.escHtml(d.domain)}</span><span class="pc-top-pct">${(d.requests / total * 100).toFixed(1)}%</span></div>` +
          `<div class="pc-top-bar"><span style="width:${(d.requests / maxReq * 100).toFixed(0)}%;background:var(--accent)"></span></div>` +
        `</div>` +
        `<div class="pc-top-right"><b>${d.requests.toLocaleString()}</b><span>${fmtBytes(d.bytes)}</span></div>`;
      els.domains.appendChild(row);
    });
  }

  function updateClients(clients) {
    if (clients) lastClientsData = clients;
    const list = lastClientsData && lastClientsData.clients ? lastClientsData.clients : [];
    clientHostnameMap = {};
    (list || []).forEach(c => { if (c.hostname) clientHostnameMap[c.client] = c.hostname; });
    els.clients.innerHTML = '';
    if (!list.length) {
      els.clients.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.noClientData') }));
      return;
    }
    const top = list.filter(c => !filter ||
      c.client.toLowerCase().includes(filter) ||
      (c.hostname || '').toLowerCase().includes(filter)).slice(0, 6);
    if (!top.length) {
      els.clients.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.filterEmpty') }));
      return;
    }
    const maxReq = top[0].requests || 1;
    const total = top.reduce((s, c) => s + c.requests, 0) || 1;
    const nowSec = Date.now() / 1000;

    top.forEach(c => {
      const online = (nowSec - (c.last_seen || 0)) < 600;
      const row = ui.el('div', 'pc-top-row');
      row.style.cursor = 'pointer';
      const title = c.hostname ? `${c.client} (${c.hostname})` : c.client;
      row.innerHTML = ui.personAvatar(c.client, 26) +
        `<div class="pc-top-main">` +
          `<div class="pc-top-namerow"><span class="pc-top-name pc-mono" title="${ui.escHtml(title)}">${ui.escHtml(c.client)}${c.hostname ? ` <span class="pc-hostname">(${ui.escHtml(c.hostname)})</span>` : ''}</span><span class="pc-top-pct">${(c.requests / total * 100).toFixed(1)}%</span></div>` +
          `<div class="pc-top-bar"><span style="width:${(c.requests / maxReq * 100).toFixed(0)}%;background:#8a2be2"></span></div>` +
        `</div>` +
        `<div class="pc-top-right"><b>${c.requests.toLocaleString()}</b><span class="${online ? 'pc-online' : ''}">${ui.ago(c.last_seen)}</span></div>`;
      row.addEventListener('click', () => window.clientCard.show(c.client));
      els.clients.appendChild(row);
    });
  }

  function updateTimeChart() {
    const minutes = (RANGES.find(r => r[0] === range) || [null, 60])[1];
    const pts = historyCache.slice(-minutes);
    els.timeBody.innerHTML = '';
    if (pts.length < 2) {
      els.timeBody.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.noTrafficData') }));
      return;
    }
    const labels = pts.map(p => {
      const d = new Date(p.ts * 1000);
      return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
    });
    const toMb = v => (v || 0) / (1024 * 1024);
    els.timeBody.innerHTML = charts.multiLineChart([
      { data: pts.map(p => toMb(p.bandwidth_out)), color: 'var(--info)', label: t('page.proxyControl.download'), fillArea: true },
      { data: pts.map(p => toMb(p.bandwidth_in)), color: 'var(--warning)', label: t('page.proxyControl.upload'), fillArea: true },
    ], { width: 460, height: 210, labels, responsive: true });
  }

  function updateUpstream(ps) {
    els.upstream.innerHTML = '';
    const ap = ps && ps.active_proxy;
    const directMode = ps && ps.direct_mode;

    if (directMode) {
      els.upstream.innerHTML = '<div class="pc-upstream-mode"><span class="route-badge route-direct">DIRECT MODE</span><div class="pc-upstream-note">' + t('page.proxyControl.directModeDesc') + '</div></div>';
      return;
    }
    if (!ap) {
      els.upstream.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.noActiveProxy') }));
      return;
    }

    const top = ui.el('div', 'pc-upstream-top');
    const addr = ui.el('span', 'pc-upstream-addr', { text: ap.address, title: t('proxyCard.title') });
    addr.addEventListener('click', () => { if (window.proxyCard) window.proxyCard.show(ap.address); });
    top.appendChild(addr);
    top.appendChild(ui.badge(ap.last_status === 'ok' ? t('page.proxyControl.healthy') : t('page.proxyControl.unhealthy'), ap.last_status === 'ok' ? 'green' : 'red'));
    if (ap.country_code) top.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code) }));
    els.upstream.appendChild(top);

    const grid = ui.el('div', 'pc-stat-grid');
    const items = [
      { label: t('page.proxyControl.latency'), value: ui.fmtLatency(ap.last_latency) },
      { label: t('page.proxyControl.successRate'), value: ui.fmtPct(ap.success_rate), color: 'var(--success)' },
      { label: t('page.proxyControl.speed'), value: ap.speed_avg ? ap.speed_avg.toFixed(0) + ' KB/s' : '—', color: 'var(--info)' },
      { label: t('page.proxyControl.protocol'), value: (ap.protocol || 'HTTP').toUpperCase() },
    ];
    items.forEach(item => {
      const cell = ui.el('div', 'pc-stat-cell');
      cell.appendChild(ui.el('div', 'pc-stat-label', { text: item.label }));
      const v = ui.el('div', 'pc-stat-value', { text: item.value });
      if (item.color) v.style.color = item.color;
      cell.appendChild(v);
      grid.appendChild(cell);
    });
    els.upstream.appendChild(grid);
  }

  function updateBandwidth(bw) {
    els.bandwidth.innerHTML = '';
    const download = bw ? (bw.download || 0) : 0;
    const upload = bw ? (bw.upload || 0) : 0;

    const boxes = ui.el('div', 'pc-bw-boxes');
    const dl = ui.el('div', 'pc-bw-box');
    dl.innerHTML = `<div class="pc-bw-label">↓ ${t('page.proxyControl.download')}</div><div class="pc-bw-value">${fmtBytes(download)}</div>`;
    boxes.appendChild(dl);
    const up = ui.el('div', 'pc-bw-box');
    up.innerHTML = `<div class="pc-bw-label">↑ ${t('page.proxyControl.upload')}</div><div class="pc-bw-value">${fmtBytes(upload)}</div>`;
    boxes.appendChild(up);
    els.bandwidth.appendChild(boxes);

    const pts = historyCache.slice(-48);
    if (pts.length >= 2) {
      const data = pts.map(p => ((p.bandwidth_in || 0) + (p.bandwidth_out || 0)) / (1024 * 1024));
      const labels = pts.map(p => {
        const d = new Date(p.ts * 1000);
        return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
      });
      const wrap = ui.el('div', 'pc-bw-chart', { html: charts.lineChart(data, { width: 440, height: 160, labels, color: 'var(--accent)', fillArea: true, responsive: true }) });
      els.bandwidth.appendChild(wrap);
    } else {
      els.bandwidth.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.noTrafficData') }));
    }
  }

  let lastSummaryData = null;
  function updateConsumer(summary) {
    if (summary) lastSummaryData = summary;
    const period = els._consumerPeriod || 'day';
    const data = lastSummaryData && lastSummaryData[period] ? lastSummaryData[period] : null;
    els.consumer.innerHTML = '';

    if (!data || (data.requests || 0) === 0) {
      els.consumer.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.noTrafficData') }));
      return;
    }

    const total = data.total || 0;
    const download = data.download || 0;
    const upload = data.upload || 0;
    const dlPct = total ? (download / total * 100) : 0;
    const sr = data.success_rate || 0;

    const head = ui.el('div', 'pc-consumer-head');
    head.innerHTML = `<div class="pc-consumer-total"><span class="pc-consumer-value">${fmtBytes(total)}</span><span class="pc-consumer-label">${t('page.proxyControl.totalTraffic')}</span></div>` +
      `<div class="pc-consumer-reqs"><span>${data.requests.toLocaleString()} ${t('page.proxyControl.requests')}</span><span style="color:${sr >= 80 ? 'var(--success)' : sr >= 50 ? 'var(--warning)' : 'var(--danger)'};font-weight:600">${sr}%</span></div>`;
    els.consumer.appendChild(head);

    const split = ui.el('div', 'pc-split');
    split.innerHTML = `<div class="pc-split-bar"><span class="pc-split-dl" style="width:${dlPct}%"></span><span class="pc-split-ul" style="width:${100 - dlPct}%"></span></div>` +
      `<div class="pc-split-labels"><span style="color:var(--success)">↓ ${fmtBytes(download)} · ${dlPct.toFixed(0)}%</span><span style="color:var(--accent)">↑ ${fmtBytes(upload)} · ${(100 - dlPct).toFixed(0)}%</span></div>`;
    els.consumer.appendChild(split);

    if (data.top_routes && data.top_routes.length) {
      const maxBytes = Math.max(...data.top_routes.map(r => r.bytes), 1);
      data.top_routes.slice(0, 4).forEach(r => {
        const row = ui.el('div', 'pc-top-row pc-top-row-sm');
        row.innerHTML = `<div class="pc-top-main">` +
            `<div class="pc-top-namerow"><span class="route-badge-sm ${ui.routeTypeClass(r.type)}">${routeTypeLabel(r.type)}</span><span class="pc-top-pct">${fmtBytes(r.bytes)}</span></div>` +
            `<div class="pc-top-bar"><span style="width:${(r.bytes / maxBytes * 100).toFixed(0)}%;background:var(--accent)"></span></div>` +
          `</div><div class="pc-top-right"><b>${r.requests.toLocaleString()}</b></div>`;
        els.consumer.appendChild(row);
      });
    }
  }

  function updateFooter() {
    const upd = document.getElementById('pcf-update');
    if (upd) upd.textContent = t('page.proxyControl.lastUpdate', { time: lastUpdate ? new Date(lastUpdate).toLocaleTimeString() : '—' });
    const auto = document.getElementById('pcf-auto');
    if (auto) auto.textContent = autoRefresh ? t('page.proxyControl.autoOn') : t('page.proxyControl.autoOff');
    const dot = document.getElementById('pcf-dot');
    if (dot) dot.classList.toggle('off', !autoRefresh);
  }

  // ── Polling ──
  async function poll() {
    try {
      const [ps, requests, routes, bw, summary, history, clients, alive] = await Promise.all([
        api.proxyStatus().catch(() => ({})),
        api.requests().catch(() => ({})),
        api.trafficRoutes().catch(() => ({})),
        api.bandwidth().catch(() => ({})),
        api.trafficSummary().catch(() => ({})),
        api.history('24h').catch(() => []),
        api.clients().catch(() => ({})),
        api.proxyAlive().catch(() => []),
      ]);

      buildGeoMap(alive, ps);

      historyCache = history || [];
      try { updateKpis(requests.requests || [], clients.clients || [], bw, historyCache); } catch (e) { console.error('tiles', e); }
      try { updateStream(requests); } catch (e) { console.error('stream', e); }
      try { updateRoutes(routes); } catch (e) { console.error('routes', e); }
      try { updateDomains(requests); } catch (e) { console.error('domains', e); }
      try { updateClients(clients); } catch (e) { console.error('clients', e); }
      try { updateTimeChart(); } catch (e) { console.error('time', e); }
      try { updateUpstream(ps); } catch (e) { console.error('upstream', e); }
      try { updateConsumer(summary); } catch (e) { console.error('consumer', e); }
      try { updateBandwidth(bw); } catch (e) { console.error('bandwidth', e); }

      lastUpdate = Date.now();
      const cl = document.getElementById('pcf-clients');
      if (cl) cl.textContent = t('page.proxyControl.footerClients', { count: (clients.clients || []).length });
      const rt = document.getElementById('pcf-routes');
      if (rt) rt.textContent = t('page.proxyControl.footerRoutes', { count: (routes.routes || []).length });
      updateFooter();
    } catch (e) {
      console.error('proxy-control poll', e);
    }
  }

  build();
  poll();
  const id = setInterval(() => { if (autoRefresh) poll(); }, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
