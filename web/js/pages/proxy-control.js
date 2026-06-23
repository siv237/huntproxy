router.register('proxy-control', (container) => {
  const els = {};
  let lastReqIds = new Set();
  let pulseOn = false;

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    // Row 1: Summary tiles (4)
    const row1 = ui.el('div', 'grid grid-4');
    const tiles = [
      { id: 'tile-req', label: t('page.proxyControl.req24h'), icon: '↻', color: 'var(--accent)' },
      { id: 'tile-sr', label: t('page.proxyControl.successRate'), icon: '✓', color: 'var(--success)' },
      { id: 'tile-bw', label: t('page.proxyControl.bandwidth24h'), icon: '↕', color: 'var(--info)' },
      { id: 'tile-routes', label: t('page.proxyControl.activeRoutes'), icon: '⇄', color: 'var(--warning)' },
    ];
    tiles.forEach(ti => {
      const card = ui.el('div', 'card tm-tile');
      card.id = ti.id;
      card.innerHTML = `<div class="tm-tile-icon" style="color:${ti.color}">${ti.icon}</div>` +
        `<div class="tm-tile-body"><div class="tm-tile-value">—</div><div class="tm-tile-label">${ti.label}</div></div>`;
      els[ti.id] = card;
      row1.appendChild(card);
    });
    container.appendChild(row1);

    // Row 2: Live Traffic Stream (full width, tall — the star)
    const streamCard = ui.card(t('page.proxyControl.liveStream'));
    streamCard.id = 'card-stream';
    streamCard.style.flex = '1';
    streamCard.style.minHeight = '0';
    streamCard.style.display = 'flex';
    streamCard.style.flexDirection = 'column';
    streamCard.style.overflow = 'hidden';
    const pulseEl = ui.el('div', 'tm-live-pulse');
    pulseEl.innerHTML = '<span class="pulse"></span> ' + t('page.proxyControl.live');
    const streamHeader = streamCard.querySelector('.card-header');
    if (streamHeader) streamHeader.appendChild(pulseEl);
    els.stream = streamCard;
    container.appendChild(streamCard);

    // Row 3: Route Distribution + Top Destinations
    const row3 = ui.el('div', 'grid grid-2 row-stretch');
    const routeCard = ui.card(t('page.proxyControl.routeDistribution'));
    routeCard.id = 'card-routes';
    routeCard.style.overflow = 'hidden';
    routeCard.style.display = 'flex';
    routeCard.style.flexDirection = 'column';
    els.routes = routeCard;
    row3.appendChild(routeCard);

    const domCard = ui.card(t('page.proxyControl.topDestinations'));
    domCard.id = 'card-domains';
    domCard.style.overflow = 'hidden';
    domCard.style.display = 'flex';
    domCard.style.flexDirection = 'column';
    els.domains = domCard;
    row3.appendChild(domCard);
    container.appendChild(row3);

    // Row 4: Current Upstream + Bandwidth
    const row4 = ui.el('div', 'grid grid-2 row-stretch');
    const upCard = ui.card(t('page.proxyControl.currentUpstream'), t('page.proxyControl.changeProxy'));
    upCard.id = 'card-upstream';
    upCard.style.overflow = 'hidden';
    const upAction = upCard.querySelector('.card-action');
    if (upAction) upAction.addEventListener('click', () => router.navigate('proxy-pool'));
    els.upstream = upCard;
    row4.appendChild(upCard);

    const bwCard = ui.card(t('page.proxyControl.bandwidth24h'));
    bwCard.id = 'card-bandwidth';
    bwCard.style.overflow = 'hidden';
    bwCard.style.display = 'flex';
    bwCard.style.flexDirection = 'column';
    els.bandwidth = bwCard;
    row4.appendChild(bwCard);
    container.appendChild(row4);
  }

  build();

  // --- Helpers ---
  function routeBadge(upstream) {
    if (!upstream || upstream === '?') {
      return '<span class="route-badge route-unknown">?</span>';
    }
    const parts = upstream.split(' → ');
    return parts.map(p => {
      if (p === 'direct') return '<span class="route-badge route-direct">DIRECT</span>';
      if (p.startsWith('pool:')) {
        const addr = p.slice(5);
        return `<span class="route-badge route-pool" title="${ui.escHtml(addr)}">POOL <span class="route-addr">${ui.escHtml(addr)}</span></span>`;
      }
      if (p.startsWith('proxy:')) {
        const addr = p.slice(6);
        return `<span class="route-badge route-proxy" title="${ui.escHtml(addr)}">PROXY <span class="route-addr">${ui.escHtml(addr)}</span></span>`;
      }
      if (p.startsWith('custom:')) {
        const name = p.slice(7);
        return `<span class="route-badge route-custom" title="${ui.escHtml(name)}">CUSTOM <span class="route-addr">${ui.escHtml(name)}</span></span>`;
      }
      if (p.includes('(disabled)')) return `<span class="route-badge route-unknown">${ui.escHtml(p)}</span>`;
      return `<span class="route-badge route-unknown">${ui.escHtml(p)}</span>`;
    }).join('<span class="route-arrow">→</span>');
  }

  function routeTypeLabel(type) {
    const map = { direct: t('route.direct'), proxy: t('route.proxy'), pool: t('route.pool'), custom: t('route.custom'), other: t('page.proxyControl.other') };
    return map[type] || type;
  }

  function routeTypeClass(type) {
    return { direct: 'route-direct', proxy: 'route-proxy', pool: 'route-pool', custom: 'route-custom', other: 'route-unknown' }[type] || 'route-unknown';
  }

  function fmtBytes(b) {
    if (!b || b === 0) return '0 B';
    if (b >= 1024 * 1024 * 1024) return (b / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
    if (b >= 1024 * 1024) return (b / (1024 * 1024)).toFixed(1) + ' MB';
    if (b >= 1024) return (b / 1024).toFixed(1) + ' KB';
    return b + ' B';
  }

  // --- Updaters ---
  function updateTiles(reqs, routes, bw) {
    const totalReq = reqs ? reqs.length : 0;
    const okCount = reqs ? reqs.filter(r => (r.status || '') === 'ok').length : 0;
    const sr = totalReq ? (okCount / totalReq * 100).toFixed(1) + '%' : '—';
    const totalBw = bw ? (bw.incoming || 0) + (bw.outgoing || 0) : 0;
    const routeCount = routes ? routes.length : 0;

    const setVal = (id, v) => {
      const el = document.getElementById(id);
      if (el) {
        const val = el.querySelector('.tm-tile-value');
        if (val) val.textContent = v;
      }
    };
    setVal('tile-req', totalReq.toLocaleString());
    setVal('tile-sr', sr);
    setVal('tile-bw', fmtBytes(totalBw));
    setVal('tile-routes', routeCount.toString());
  }

  function updateStream(card, requests) {
    const list = requests && requests.requests ? requests.requests : [];
    if (!list.length) {
      const body = card.querySelector('.tm-stream-body');
      if (body) body.remove();
      if (!card.querySelector('.empty')) {
        card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noRecentRequests'), style: 'flex:1;display:flex;align-items:center;justify-content:center' }));
      }
      return;
    }

    let body = card.querySelector('.tm-stream-body');
    if (!body) {
      body = ui.el('div', 'tm-stream-body');
      card.appendChild(body);
    }

    // Detect new requests for flash animation
    const newIds = new Set();
    list.forEach(r => { newIds.add(r.ts + '|' + r.client + '|' + r.target); });

    body.innerHTML = '';
    const headers = [
      { label: t('page.proxyControl.time'), width: '55px' },
      { label: t('page.proxyControl.client'), width: '110px' },
      { label: t('page.proxyControl.target'), width: 'auto' },
      { label: t('page.proxyControl.route'), width: 'auto' },
      { label: t('page.proxyControl.status'), width: '50px', align: 'center' },
      { label: t('page.proxyControl.duration'), width: '65px', align: 'right' },
      { label: t('page.proxyControl.size'), width: '80px', align: 'right' },
    ];
    const rows = list.slice(0, 40).map(r => {
      const st = (r.status || '').toString();
      const isOk = st === 'ok' || st === '200';
      const is502 = st.startsWith('502');
      const dur = r.duration != null ? r.duration.toFixed(2) + 's' : '—';
      const sz = fmtBytes((r.bytes_in || 0) + (r.bytes_out || 0));
      const id = r.ts + '|' + r.client + '|' + r.target;
      const isNew = !lastReqIds.has(id);
      const cls = isNew ? 'tm-row-new' : '';
      const target = r.target || '—';
      const targetShort = target.length > 40 ? target.slice(0, 38) + '…' : target;
      return [
        `<span class="${cls}">${ui.fmtTime(r.ts || 0).split(' ')[0]}</span>`,
        `<span class="${cls}" style="font-family:monospace;font-size:11px">${ui.escHtml(r.client || '—')}</span>`,
        `<span class="${cls}" style="font-family:monospace;font-size:12px;color:var(--text-primary)" title="${ui.escHtml(target)}">${ui.escHtml(targetShort)}</span>`,
        `<span class="${cls}">${routeBadge(r.upstream)}</span>`,
        `<span class="${cls}" style="color:${isOk ? 'var(--success)' : is502 ? 'var(--warning)' : 'var(--danger)'};font-weight:600">${isOk ? '✓' : is502 ? '502' : '✗'}</span>`,
        `<span class="${cls}" style="font-size:11px;color:var(--text-secondary)">${dur}</span>`,
        `<span class="${cls}" style="font-size:11px;color:var(--text-secondary)">${sz}</span>`,
      ];
    });
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, rows));
    body.appendChild(tblWrap);

    lastReqIds = newIds;
  }

  function updateRoutes(card, routes) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.routeDistribution') }));
    card.appendChild(header);

    const list = routes && routes.routes ? routes.routes : [];
    if (!list.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noRouteData'), style: 'flex:1;display:flex;align-items:center;justify-content:center' }));
      return;
    }

    const totalReq = list.reduce((s, r) => s + (r.requests || 0), 0) || 1;

    const wrap = ui.el('div', '', { style: 'flex:1;min-height:0;overflow-y:auto;padding:4px 0' });
    list.forEach(r => {
      const pct = (r.requests / totalReq * 100);
      const row = ui.el('div', 'tm-route-row');
      const top = ui.el('div', 'tm-route-top');
      const badge = ui.el('span', `route-badge ${routeTypeClass(r.type)}`, { text: routeTypeLabel(r.type).toUpperCase() });
      top.appendChild(badge);
      top.appendChild(ui.el('span', 'tm-route-count', { text: r.requests.toLocaleString() }));
      top.appendChild(ui.el('span', 'tm-route-pct', { text: pct.toFixed(1) + '%' }));
      top.appendChild(ui.el('span', 'tm-route-sr', { text: r.success_rate + '% OK', style: `color:${r.success_rate >= 80 ? 'var(--success)' : r.success_rate >= 50 ? 'var(--warning)' : 'var(--danger)'};font-size:11px;font-weight:600` }));
      row.appendChild(top);

      const bar = ui.el('div', 'tm-route-bar');
      bar.appendChild(ui.el('div', '', { style: `width:${pct}%;height:100%;background:var(--${routeTypeClass(r.type).replace('route-', '')});border-radius:2px;transition:width .3s` }));
      row.appendChild(bar);

      const meta = ui.el('div', 'tm-route-meta');
      meta.appendChild(ui.el('span', '', { text: '↓ ' + fmtBytes(r.bytes_out), style: 'color:var(--text-secondary)' }));
      meta.appendChild(ui.el('span', '', { text: '↑ ' + fmtBytes(r.bytes_in), style: 'color:var(--text-secondary)' }));
      meta.appendChild(ui.el('span', '', { text: r.avg_duration + 's avg', style: 'color:var(--text-secondary)' }));
      row.appendChild(meta);

      if (r.upstreams && r.upstreams.length > 1) {
        const ups = ui.el('div', 'tm-route-ups');
        r.upstreams.slice(0, 3).forEach(u => {
          ups.appendChild(ui.el('span', 'tm-route-up', { text: u.upstream, title: u.upstream }));
        });
        if (r.upstreams.length > 3) {
          ups.appendChild(ui.el('span', 'tm-route-up', { text: '+' + (r.upstreams.length - 3) }));
        }
        row.appendChild(ups);
      }

      wrap.appendChild(row);
    });
    card.appendChild(wrap);
  }

  function updateDomains(card, requests) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.topDestinations') }));
    card.appendChild(header);

    const list = requests && requests.requests ? requests.requests : [];
    if (!list.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noDomainData'), style: 'flex:1;display:flex;align-items:center;justify-content:center' }));
      return;
    }

    const domains = {};
    list.forEach(r => {
      const target = r.target || '';
      if (!target || target === '?') return;
      let h;
      try { h = target.startsWith('http') ? new URL(target).hostname : target.split(':')[0]; } catch (e) { h = target; }
      if (!h) return;
      if (!domains[h]) domains[h] = { domain: h, requests: 0, bytes: 0, routes: {} };
      domains[h].requests++;
      domains[h].bytes += (r.bytes_in || 0) + (r.bytes_out || 0);
      const up = r.upstream || 'unknown';
      const upType = up === 'direct' ? 'direct' : up.startsWith('proxy:') ? 'proxy' : up.startsWith('pool:') ? 'pool' : up.startsWith('custom:') ? 'custom' : 'other';
      domains[h].routes[upType] = (domains[h].routes[upType] || 0) + 1;
    });

    const top = Object.values(domains).sort((a, b) => b.requests - a.requests).slice(0, 12);
    const total = top.reduce((s, d) => s + d.requests, 0) || 1;

    const wrap = ui.el('div', '', { style: 'flex:1;min-height:0;overflow-y:auto' });
    top.forEach(d => {
      const row = ui.el('div', 'tm-domain-row');
      const left = ui.el('div', 'tm-domain-left');
      left.appendChild(ui.el('div', 'tm-domain-name', { text: d.domain, title: d.domain }));
      const bar = ui.el('div', 'tm-domain-bar');
      bar.appendChild(ui.el('div', '', { style: `width:${(d.requests / total * 100)}%;height:100%;background:var(--accent);border-radius:2px` }));
      left.appendChild(bar);
      row.appendChild(left);

      const right = ui.el('div', 'tm-domain-right');
      right.appendChild(ui.el('span', '', { text: d.requests + ' req', style: 'font-weight:600;font-size:12px' }));
      right.appendChild(ui.el('span', '', { text: fmtBytes(d.bytes), style: 'font-size:11px;color:var(--text-secondary)' }));

      const routeTypes = Object.entries(d.routes).sort((a, b) => b[1] - a[1]);
      const badges = ui.el('div', 'tm-domain-routes');
      routeTypes.forEach(([type, count]) => {
        badges.appendChild(ui.el('span', `route-badge-sm ${routeTypeClass(type)}`, { text: routeTypeLabel(type), title: count + ' requests' }));
      });
      right.appendChild(badges);
      row.appendChild(right);

      wrap.appendChild(row);
    });
    card.appendChild(wrap);
  }

  function updateUpstream(card, ps) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.currentUpstream') }));
    const btn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.proxyControl.changeProxy') });
    btn.addEventListener('click', () => router.navigate('proxy-pool'));
    header.appendChild(btn);
    card.appendChild(header);

    const ap = ps && ps.active_proxy;
    const directMode = ps && ps.direct_mode;

    if (directMode) {
      const direct = ui.el('div', 'tm-upstream-mode');
      direct.innerHTML = '<span class="route-badge route-direct">DIRECT MODE</span><div style="font-size:12px;color:var(--text-secondary);margin-top:8px">' + t('page.proxyControl.directModeDesc') + '</div>';
      card.appendChild(direct);
      return;
    }

    if (!ap) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noActiveProxy'), style: 'flex:1;display:flex;align-items:center;justify-content:center' }));
      return;
    }

    const top = ui.el('div', 'tm-upstream-top');
    const addrLink = ui.el('div', 'tm-upstream-addr');
    addrLink.innerHTML = `<span style="font-family:monospace;font-size:15px;font-weight:700;color:var(--accent);cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${ui.escHtml(ap.address)}</span>`;
    addrLink.querySelector('span').addEventListener('click', () => { if (window.proxyCard) window.proxyCard.show(ap.address); });
    top.appendChild(addrLink);
    top.appendChild(ui.badge(ap.last_status === 'ok' ? t('page.proxyControl.healthy') : t('page.proxyControl.unhealthy'), ap.last_status === 'ok' ? 'green' : 'red'));
    if (ap.country_code) top.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code) }));
    card.appendChild(top);

    const grid = ui.el('div', 'grid grid-4');
    const items = [
      { label: t('page.proxyControl.latency'), value: ui.fmtLatency(ap.last_latency), color: 'var(--text-primary)' },
      { label: t('page.proxyControl.successRate'), value: ui.fmtPct(ap.success_rate), color: 'var(--success)' },
      { label: t('page.proxyControl.speed'), value: ap.speed_avg ? ap.speed_avg.toFixed(0) + ' KB/s' : '—', color: 'var(--info)' },
      { label: t('page.proxyControl.protocol'), value: (ap.protocol || 'HTTP').toUpperCase(), color: 'var(--text-secondary)' },
    ];
    items.forEach(item => {
      const cell = ui.el('div', 'tm-stat-cell');
      cell.appendChild(ui.el('div', 'tm-stat-label', { text: item.label }));
      cell.appendChild(ui.el('div', 'tm-stat-value', { text: item.value, style: `color:${item.color}` }));
      grid.appendChild(cell);
    });
    card.appendChild(grid);
  }

  function updateBandwidth(card, bw, history) {
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyControl.bandwidth24h') }));
    card.appendChild(header);

    const incoming = bw ? (bw.incoming || 0) : 0;
    const outgoing = bw ? (bw.outgoing || 0) : 0;

    const stats = ui.el('div', 'grid grid-2', { style: 'flex-shrink:0;margin-bottom:8px' });
    const inCell = ui.el('div', 'tm-bw-cell');
    inCell.innerHTML = `<div class="tm-bw-label">↓ ${t('page.proxyControl.incoming')}</div><div class="tm-bw-value">${fmtBytes(incoming)}</div>`;
    stats.appendChild(inCell);
    const outCell = ui.el('div', 'tm-bw-cell');
    outCell.innerHTML = `<div class="tm-bw-label">↑ ${t('page.proxyControl.outgoing')}</div><div class="tm-bw-value">${fmtBytes(outgoing)}</div>`;
    stats.appendChild(outCell);
    card.appendChild(stats);

    const pts = history && history.length ? history.slice(-48) : [];
    if (pts.length >= 2) {
      const data = pts.map(p => (p.bandwidth_in || 0) + (p.bandwidth_out || 0));
      const labels = pts.map(p => {
        const d = new Date(p.ts * 1000);
        return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
      });
      const chartWrap = ui.el('div', '', { style: 'flex:1;min-height:0;display:flex', html: charts.lineChart(data, { width: 400, height: 120, labels, color: 'var(--accent)', fillArea: true, responsive: true }) });
      card.appendChild(chartWrap);
    } else {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noTrafficData'), style: 'flex:1;display:flex;align-items:center;justify-content:center' }));
    }
  }

  // --- Polling ---
  async function poll() {
    try {
      let ps = {}, requests = {}, routes = {}, bw = {}, history = [];
      try { ps = await api.proxyStatus(); } catch (e) {}
      try { requests = await api.requests(); } catch (e) {}
      try { routes = await api.trafficRoutes(); } catch (e) {}
      try { bw = await api.bandwidth(); } catch (e) {}
      try { history = await api.history('24h'); } catch (e) {}

      try { updateTiles(requests.requests || [], routes.routes || [], bw); } catch (e) { console.error('tiles', e); }
      try { updateStream(els.stream, requests); } catch (e) { console.error('stream', e); }
      try { updateRoutes(els.routes, routes); } catch (e) { console.error('routes', e); }
      try { updateDomains(els.domains, requests); } catch (e) { console.error('domains', e); }
      try { updateUpstream(els.upstream, ps); } catch (e) { console.error('upstream', e); }
      try { updateBandwidth(els.bandwidth, bw, history); } catch (e) { console.error('bandwidth', e); }
    } catch (e) {
      console.error('proxy-control poll', e);
    }
  }

  poll();
  const id = setInterval(poll, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
