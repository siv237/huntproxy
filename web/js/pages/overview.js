router.register('overview', (container) => {
  const els = {};

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    // Row 1: 4 stat cards
    const row1 = ui.el('div', 'grid grid-4');
    row1.appendChild(buildStatCard('total', t('page.overview.totalProxies'), '0', '—', 'neutral', 'server'));
    row1.appendChild(buildStatCard('alive', t('page.overview.alive'), '0', '—', 'neutral', 'shield'));
    row1.appendChild(buildStatCard('dead', t('page.overview.dead'), '0', '—', 'neutral', 'x-circle'));
    row1.appendChild(buildStatCard('blacklisted', t('page.overview.blacklisted'), '0', '—', 'neutral', 'users'));
    container.appendChild(row1);

    // Row 2: Pool Progress + Top Countries + Right sidebar (Activity)
    const row2 = ui.el('div', 'grid row-stretch', { style: 'grid-template-columns:2fr 1.5fr 1fr' });
    row2.appendChild(buildPoolProgressCard());
    row2.appendChild(buildTopCountriesCard());
    row2.appendChild(buildRecentActivityCard());
    container.appendChild(row2);

    // Row 3: Top Rated Proxies + System Resources + Right sidebar (Quick Actions)
    const row3 = ui.el('div', 'grid row-stretch', { style: 'grid-template-columns:2fr 1.5fr 1fr' });
    row3.appendChild(buildTopRatedProxiesCard());
    row3.appendChild(buildSystemResourcesCard());
    row3.appendChild(buildQuickActionsCard());
    container.appendChild(row3);

    // Row 4: Live Performance + Right sidebar (Current Proxy)
    const row4 = ui.el('div', 'grid row-stretch', { style: 'grid-template-columns:2fr 1fr' });
    row4.appendChild(buildLivePerformanceCard());
    row4.appendChild(buildCurrentProxyCard());
    container.appendChild(row4);
  }

  // --- Stat Card ---
  // Sparkline data buffer (updated from real stats during poll)
  let sparklineBuffers = { total: [], alive: [], dead: [], blacklisted: [] };
  let sparklinePrev = { total: null, alive: null, dead: null, blacklisted: null };
  const MAX_SPARK_POINTS = 9;

  function buildStatCard(id, label, value, delta, deltaDir, icon) {
    const card = ui.el('div', 'stat-card');
    card.id = 'stat-' + id;

    const body = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px' });

    // Left: icon
    const iconWrap = ui.el('div', 'stat-icon-wrap');
    iconWrap.style.background = id === 'total' ? 'rgba(99,102,241,0.1)' : id === 'alive' ? 'rgba(16,185,129,0.1)' : id === 'dead' ? 'rgba(239,68,68,0.1)' : 'rgba(139,92,246,0.1)';
    iconWrap.style.color = id === 'total' ? 'var(--accent)' : id === 'alive' ? 'var(--success)' : id === 'dead' ? 'var(--danger)' : '#8B5CF6';
    iconWrap.innerHTML = getStatIconSvg(icon);
    body.appendChild(iconWrap);

    // Center: label + value + delta
    const info = ui.el('div', '', { style: 'flex:1;min-width:0' });
    info.appendChild(ui.el('div', 'stat-label', { text: label }));
    const valRow = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:8px;margin-top:2px' });
    valRow.appendChild(ui.el('div', 'stat-value', { id: 'stat-val-' + id, text: value }));
    valRow.appendChild(ui.el('div', 'stat-delta ' + deltaDir, {
      id: 'stat-delta-' + id,
      text: delta,
      style: 'display:flex;align-items:center;gap:2px'
    }));
    info.appendChild(valRow);
    body.appendChild(info);

    // Right: sparkline
    const spark = ui.el('div', 'stat-sparkline');
    spark.innerHTML = buildSparkline(id);
    body.appendChild(spark);

    card.appendChild(body);
    return card;
  }

  function getStatIconSvg(name) {
    const icons = {
      server: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/><circle cx="6" cy="6" r="1"/><circle cx="6" cy="18" r="1"/></svg>',
      shield: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
      'x-circle': '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      users: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    };
    return icons[name] || '';
  }

  function buildSparkline(id) {
    const colors = {
      total: { stroke: '#4F46E5', fill: '#4F46E5' },
      alive: { stroke: '#10B981', fill: '#10B981' },
      dead: { stroke: '#EF4444', fill: '#EF4444' },
      blacklisted: { stroke: '#8B5CF6', fill: '#8B5CF6' },
    };
    const c = colors[id] || colors.total;
    const points = generateSparklineData(id);
    const w = 80, h = 32;
    const min = Math.min(...points), max = Math.max(...points);
    const range = max - min || 1;
    const pathD = points.map((p, i) => {
      const x = (i / (points.length - 1)) * w;
      const y = h - ((p - min) / range) * (h - 6) - 3;
      return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
    }).join(' ');
    const areaD = pathD + ` L${w},${h} L0,${h} Z`;
    return `<svg class="sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path class="area" d="${areaD}" fill="${c.fill}" opacity="0.15"/><path d="${pathD}" stroke="${c.stroke}" stroke-width="2" fill="none" stroke-linecap="round"/></svg>`;
  }

  function generateSparklineData(id) {
    const buf = sparklineBuffers[id];
    if (buf && buf.length > 1) return buf;
    return [0, 0, 0, 0, 0, 0, 0, 0, 0];
  }

  function updateSparklineBuffers(counts) {
    ['total', 'alive', 'dead', 'blacklisted'].forEach(key => {
      const mapKey = key === 'total' ? 'ratings' : key === 'blacklisted' ? 'blacklist' : key;
      const val = counts[mapKey] || 0;
      if (!sparklineBuffers[key]) sparklineBuffers[key] = [];
      sparklineBuffers[key].push(val);
      if (sparklineBuffers[key].length > MAX_SPARK_POINTS) sparklineBuffers[key].shift();
    });
  }

  function renderSparklines() {
    ['total', 'alive', 'dead', 'blacklisted'].forEach(key => {
      const sparkEl = document.querySelector('#stat-' + key + ' .stat-sparkline');
      if (sparkEl) sparkEl.innerHTML = buildSparkline(key);
    });
  }

  function updateDelta(id, current) {
    const el = document.getElementById('stat-delta-' + id);
    if (!el) return;
    const prev = sparklinePrev[id];
    if (prev === null) {
      el.textContent = '—';
      el.className = 'stat-delta neutral';
      return;
    }
    const diff = current - prev;
    if (diff === 0) {
      el.textContent = '±0';
      el.className = 'stat-delta neutral';
    } else if (diff > 0) {
      el.textContent = '↑' + diff;
      el.className = id === 'dead' || id === 'blacklisted' ? 'stat-delta negative' : 'stat-delta positive';
    } else {
      el.textContent = '↓' + Math.abs(diff);
      el.className = id === 'dead' || id === 'blacklisted' ? 'stat-delta positive' : 'stat-delta negative';
    }
    sparklinePrev[id] = current;
  }

  // --- Pool Progress Card ---
  function buildPoolProgressCard() {
    const card = ui.el('div', 'card');
    card.id = 'pool-progress-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { id: 'pool-title', text: t('page.overview.poolProgress') }));
    const btns = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center' });
    const bstyle = 'font-size:11px;padding:2px 6px;border:1px solid var(--border);border-radius:3px;background:var(--surface-raised);cursor:pointer;line-height:1';
    const huntBtn = ui.el('button', '', { id: 'pool-hunt-btn', style: bstyle + ';color:var(--success)' });
    huntBtn.textContent = '▶';
    huntBtn.title = t('page.overview.startHunt');
    btns.appendChild(huntBtn);
    const stopBtn = ui.el('button', '', { id: 'pool-stop-btn', style: bstyle + ';color:var(--danger);display:none' });
    stopBtn.textContent = '■';
    stopBtn.title = t('page.overview.stopHunt');
    btns.appendChild(stopBtn);
    header.appendChild(btns);
    card.appendChild(header);

    const body = ui.el('div', '', { style: 'display:flex;align-items:center;gap:20px;flex-wrap:wrap' });

    const circle = ui.el('div', 'circle-progress', { id: 'pool-circle' });
    circle.innerHTML = `
      <svg width="80" height="80" viewBox="0 0 80 80">
        <circle class="track" cx="40" cy="40" r="34"/>
        <circle class="fill" id="pool-circle-fill" cx="40" cy="40" r="34" stroke-dasharray="213.6" stroke-dashoffset="213.6"/>
      </svg>
      <div class="text">
        <span class="value" id="pool-pct">0%</span>
      </div>`;
    body.appendChild(circle);

    const details = ui.el('div', '', { style: 'flex:1;min-width:180px' });
    details.appendChild(ui.el('div', '', { id: 'pool-phase', style: 'font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px', text: t('page.overview.validatingProxies') }));

    const bar = ui.el('div', 'progress-bar', { style: 'height:8px;margin-bottom:6px' });
    bar.appendChild(ui.el('div', '', { id: 'pool-bar-fill', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease;border-radius:4px' }));
    details.appendChild(bar);

    const stats = ui.el('div', '', { style: 'display:flex;justify-content:space-between;font-size:12px;color:var(--text-secondary)' });
    stats.innerHTML = `<span>${t('page.overview.checked')} <b id="pool-checked" style="color:var(--text-primary)">0</b> / <b id="pool-total">0</b></span><span>${t('page.overview.working')} <b id="pool-working" style="color:var(--success)">0</b></span>`;
    details.appendChild(stats);
    body.appendChild(details);
    card.appendChild(body);

    const currentProxy = ui.el('div', '', { id: 'pool-current-proxy', style: 'margin-top:10px;font-size:12px;color:var(--text-secondary);flex:1' });
    currentProxy.innerHTML = `<span style="color:var(--text-muted)">${t('common.ready')}</span>`;
    card.appendChild(currentProxy);

    const poolStats = ui.el('div', '', { id: 'pool-stats-row', style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(60px,1fr));gap:0.3em;margin-top:auto' });
    card.appendChild(poolStats);

    return card;
  }

  function renderPoolProxyInfo(det) {
    const wrap = document.getElementById('pool-current-proxy');
    const statsWrap = document.getElementById('pool-stats-row');
    if (!wrap) return;
    if (!det || !det.address) {
      wrap.innerHTML = `<span style="color:var(--text-muted)">${t('common.ready')}</span>`;
      if (statsWrap) statsWrap.innerHTML = '';
      return;
    }
    wrap.innerHTML = '';

    const mode = det.supports_connect ? 'HTTPS' : (det.protocol || 'HTTP').toUpperCase();
    const ok = det.last_status === 'ok';
    const addrRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.4em' });
    addrRow.appendChild(ui.el('span', '', { style: 'font-family:monospace;font-weight:700;color:var(--accent);font-size:12px', text: det.address }));
    addrRow.appendChild(ui.el('span', '', { style: 'color:var(--accent);font-weight:600;font-size:11px', text: mode }));
    addrRow.appendChild(ui.el('span', '', { style: `color:${ok ? 'var(--success)' : 'var(--danger)'};font-size:14px`, text: ok ? '●' : '○' }));
    wrap.appendChild(addrRow);

    const hasListen = !!(det.listen_country || det.listen_city);
    const hasEgress = !!(det.egress_country || det.egress_city);
    const diffCountry = hasListen && hasEgress && (det.listen_country || '') !== (det.egress_country || '');

    if (diffCountry) {
      const cols = ui.el('div', '', { style: 'display:grid;grid-template-columns:1fr auto 1fr;gap:0 0.5em;margin-bottom:0.3em;font-size:11px' });

      const lc = ui.el('div', '', { style: 'min-width:0' });
      lc.appendChild(ui.el('div', '', { style: 'font-size:0.65em;color:var(--text-muted);text-transform:uppercase;margin-bottom:2px', text: t('page.overview.server') }));
      const lr = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.3em' });
      lr.appendChild(ui.el('span', 'flag', { text: ui.flag(det.listen_country_code || det.country_code || ''), style: 'flex-shrink:0' }));
      lr.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: (det.listen_country || '') + (det.listen_city ? ', ' + det.listen_city : '') }));
      lc.appendChild(lr);
      if (det.listen_isp) lc.appendChild(ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: det.listen_isp }));
      cols.appendChild(lc);

      const arrow = ui.el('div', '', { style: 'display:flex;align-items:center;color:var(--accent);font-weight:700;font-size:13px;padding-top:0.8em', text: '→' });
      cols.appendChild(arrow);

      const rc = ui.el('div', '', { style: 'min-width:0' });
      rc.appendChild(ui.el('div', '', { style: 'font-size:0.65em;color:var(--text-muted);text-transform:uppercase;margin-bottom:2px', text: t('page.overview.exit') }));
      const rr = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.3em' });
      rr.appendChild(ui.el('span', 'flag', { text: ui.flag(det.egress_country_code || det.country_code || ''), style: 'flex-shrink:0' }));      rr.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: (det.egress_country || '') + (det.egress_city ? ', ' + det.egress_city : '') }));
      rc.appendChild(rr);
      if (det.egress_isp) rc.appendChild(ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: det.egress_isp }));
      if (det.egress_ip) rc.appendChild(ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted)', text: 'ip: ' + det.egress_ip }));
      cols.appendChild(rc);

      wrap.appendChild(cols);
    } else {
      const single = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.2em;font-size:11px' });
      single.appendChild(ui.el('span', 'flag', { text: ui.flag(det.country_code || ''), style: 'flex-shrink:0' }));
      single.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary)', text: (det.listen_country || det.egress_country || det.country || '') + (det.listen_city || det.egress_city ? ', ' + (det.listen_city || det.egress_city) : '') }));
      wrap.appendChild(single);
      const details = ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);line-height:1.3;margin-bottom:0.2em' });
      let d = '';
      if (det.listen_isp) d += det.listen_isp;
      if (det.egress_ip) d += (d ? ' · ' : '') + 'exit ' + det.egress_ip;
      details.textContent = d;
      if (d) wrap.appendChild(details);
    }

    if (statsWrap) {
      statsWrap.innerHTML = '';
      const stats = [
        { l: 'Lat', v: det.last_latency ? det.last_latency.toFixed(2) + 's' : '–' },
        { l: 'Speed', v: det.speed_avg ? det.speed_avg.toFixed(0) + 'KB/s' : '–' },
        { l: 'Succ', v: det.success_rate != null ? Math.round(det.success_rate * 100) + '%' : '–' },
        { l: 'Up', v: (det.checks_ok || 0) + '/' + (det.checks_total || 0) },
      ];
      stats.forEach(it => {
        const cell = ui.el('div', '', { style: 'text-align:center;padding:0.25em 0.15em;background:var(--surface-raised);border-radius:0.25em;min-width:0' });
        cell.appendChild(ui.el('div', '', { style: 'font-size:0.6em;color:var(--text-muted);text-transform:uppercase', text: it.l }));
        cell.appendChild(ui.el('div', '', { style: 'font-weight:600;color:var(--text-primary);font-size:0.8em', text: it.v }));
        statsWrap.appendChild(cell);
      });
    }
  }

  // --- Top Countries Card ---
  function buildTopCountriesCard() {
    const card = ui.el('div', 'card');
    card.id = 'top-countries-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.overview.topCountries') }));
    const viewAllBtn = ui.el('button', 'card-action', { text: t('common.viewAll') });
    viewAllBtn.addEventListener('click', () => router.navigate('proxies'));
    header.appendChild(viewAllBtn);
    card.appendChild(header);

    const list = ui.el('div', '', { id: 'countries-list', style: 'display:flex;flex-direction:column;gap:8px' });
    list.innerHTML = `<div class="empty" style="font-size:12px;padding:16px">${t('common.noData')}</div>`;
    card.appendChild(list);

    return card;
  }

  function renderCountries(countries) {
    const list = document.getElementById('countries-list');
    if (!list || !countries || !countries.length) return;
    const max = Math.max(...countries.map(c => c.count));
    list.innerHTML = '';
    countries.forEach(c => {
      const code = c.country_code || c.code || '';
      const name = c.country || c.name || code;
      const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px' });
      row.appendChild(ui.el('span', 'flag', { text: ui.flag(code), style: 'font-size:14px;width:20px;text-align:center' }));
      row.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-primary);width:80px;flex-shrink:0', text: name }));
      const barWrap = ui.el('div', '', { style: 'flex:1;height:6px;background:var(--surface-raised);border-radius:3px;overflow:hidden' });
      barWrap.appendChild(ui.el('div', '', { style: `width:${(c.count / max) * 100}%;height:100%;background:var(--accent);border-radius:3px;transition:width 0.4s ease` }));
      row.appendChild(barWrap);
      row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);width:30px;text-align:right;flex-shrink:0', text: c.count }));
      row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-muted);width:40px;text-align:right;flex-shrink:0', text: c.pct + '%' }));
      list.appendChild(row);
    });
  }

  // --- Recent Activity Card ---
  function buildRecentActivityCard() {
    const card = ui.el('div', 'card');
    card.id = 'recent-activity-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.overview.recentActivity') }));
    const viewAllBtn = ui.el('button', 'card-action', { text: t('common.viewAll') });
    viewAllBtn.addEventListener('click', () => router.navigate('logs'));
    header.appendChild(viewAllBtn);
    card.appendChild(header);

    const list = ui.el('div', '', { id: 'activity-list', style: 'display:flex;flex-direction:column;gap:2px' });
    list.innerHTML = `<div class="empty" style="font-size:12px;padding:16px">${t('page.overview.noEvents')}</div>`;
    card.appendChild(list);

    return card;
  }

  function renderActivity(events) {
    const list = document.getElementById('activity-list');
    if (!list || !events || !events.length) return;
    list.innerHTML = '';
    events.slice(0, 8).forEach(e => {
      const item = ui.el('div', 'activity-item');
      item.appendChild(ui.el('div', `activity-icon ${e.icon || 'blue'}`, { html: getActivityIcon(e.type) }));
      const body = ui.el('div', 'activity-body');
      body.appendChild(ui.el('div', 'activity-text', { html: e.html || e.msg }));
      const meta = ui.el('div', 'activity-time');
      meta.textContent = e.ago || ui.ago(e.ts);
      body.appendChild(meta);
      item.appendChild(body);
      list.appendChild(item);
    });
  }

  function getActivityIcon(type) {
    const icons = {
      check: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
      add: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
      heart: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
      trash: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
      list: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1"/><circle cx="4" cy="12" r="1"/><circle cx="4" cy="18" r="1"/></svg>',
      x: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
      link: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
    };
    return icons[type] || icons.check;
  }

  // --- Top Rated Proxies Card ---
  function buildTopRatedProxiesCard() {
    const card = ui.el('div', 'card');
    card.id = 'top-rated-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.overview.topRatedProxies') }));
    const viewAllBtn = ui.el('button', 'card-action', { text: t('page.overview.viewAllProxies') });
    viewAllBtn.addEventListener('click', () => router.navigate('proxies'));
    header.appendChild(viewAllBtn);
    card.appendChild(header);

    const wrap = ui.el('div', 'table-wrap');
    wrap.id = 'top-rated-tbl-wrap';
    card.appendChild(wrap);

    return card;
  }

  function renderTopRated(proxies) {
    const wrap = document.getElementById('top-rated-tbl-wrap');
    if (!wrap) return;

    const headers = [
      { label: '#', width: '30px', align: 'center' },
      { label: 'Proxy', width: null, align: 'left' },
      { label: 'Country', width: '80px', align: 'left' },
      { label: 'Latency', width: '60px', align: 'right' },
      { label: 'Score', width: '50px', align: 'right' },
      { label: 'Uptime', width: '50px', align: 'center' },
      { label: 'Last Check', width: '70px', align: 'right' },
    ];
    const rows = (proxies || []).slice(0, 5).map((p, i) => [
      `<span style="color:var(--text-muted);font-size:11px">${i + 1}</span>`,
      `<span class="addr">${p.address}</span>`,
      `<span class="flag">${ui.flag(p.country_code)}</span> <span style="font-size:11px">${p.country || ''}</span>`,
      p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
      (p.score || 0).toFixed(0) + '%',
      `${p.checks_ok || 0}/${p.checks_total || 0}`,
      ui.ago(p.last_check),
    ]);
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  // --- System Resources Card ---
  function buildSystemResourcesCard() {
    const card = ui.el('div', 'card');
    card.id = 'system-resources-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.overview.systemResources'), style: 'margin-bottom:12px' }));

    const resources = [
      { label: t('page.overview.cpuUsage'), id: 'res-cpu', value: 0 },
      { label: t('page.overview.memoryUsage'), id: 'res-memory', value: 0 },
      { label: t('page.overview.diskUsage'), id: 'res-disk', value: 0 },
    ];

    resources.forEach(r => {
      const row = ui.el('div', '', { style: 'margin-bottom:10px' });
      const labelRow = ui.el('div', '', { style: 'display:flex;justify-content:space-between;margin-bottom:4px' });
      labelRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: r.label }));
      labelRow.appendChild(ui.el('span', '', { id: r.id + '-val', style: 'font-size:11px;font-weight:600;color:var(--text-primary)', text: '0%' }));
      row.appendChild(labelRow);
      const bar = ui.el('div', 'progress-bar', { style: 'height:6px' });
      bar.appendChild(ui.el('div', '', { id: r.id + '-bar', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease;border-radius:3px' }));
      row.appendChild(bar);
      card.appendChild(row);
    });

    return card;
  }

  // --- Quick Actions Card ---
  function buildQuickActionsCard() {
    const card = ui.el('div', 'card');
    card.id = 'quick-actions-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.overview.quickActions'), style: 'margin-bottom:10px' }));

    const grid = ui.el('div', 'qa-grid');

    const actions = [
      { icon: 'refresh', label: t('page.overview.refreshPool'), desc: t('page.overview.refreshPoolDesc'), action: () => api.huntStart().then(() => app.toast(t('page.overview.huntStarted'))), color: 'var(--accent)', bg: 'rgba(99,102,241,0.1)' },
      { icon: 'heart', label: t('page.overview.healthCheck'), desc: t('page.overview.healthCheckDesc'), action: () => api.huntStart().then(() => app.toast(t('page.overview.healthCheckStarted'))), color: 'var(--success)', bg: 'rgba(16,185,129,0.1)' },
      { icon: 'trash', label: t('page.overview.clearDead'), desc: t('page.overview.clearDeadDesc'), action: () => api.clearDead().then(() => app.toast(t('page.overview.deadCleared'))).catch(() => {}), color: 'var(--danger)', bg: 'rgba(239,68,68,0.1)' },
      { icon: 'download', label: t('page.overview.export'), desc: t('page.overview.exportDesc'), action: () => { window.location.href = '/api/export'; }, color: 'var(--info)', bg: 'rgba(59,130,246,0.1)' },
      { icon: 'upload', label: t('page.overview.import'), desc: t('page.overview.importDesc'), action: () => app.toast('Import started'), color: 'var(--warning)', bg: 'rgba(245,158,11,0.1)' },
      { icon: 'settings', label: t('page.overview.settingsAction'), desc: t('page.overview.settingsDesc'), action: () => router.navigate('settings'), color: 'var(--text-secondary)', bg: 'var(--surface-raised)' },
    ];

    actions.forEach(a => {
      const item = ui.el('button', 'qa-item');
      item.addEventListener('click', a.action);
      const iconWrap = ui.el('div', 'qa-icon');
      iconWrap.style.color = a.color;
      iconWrap.style.background = a.bg;
      iconWrap.innerHTML = getQAIcon(a.icon);
      item.appendChild(iconWrap);
      const text = ui.el('div', 'qa-text');
      text.appendChild(ui.el('div', 'qa-title', { text: a.label }));
      text.appendChild(ui.el('div', 'qa-desc', { text: a.desc }));
      item.appendChild(text);
      grid.appendChild(item);
    });

    card.appendChild(grid);
    return card;
  }

  function getQAIcon(name) {
    const icons = {
      refresh: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
      heart: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
      trash: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>',
      download: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
      upload: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>',
      settings: '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
    };
    return icons[name] || '';
  }

  // --- Live Performance Card ---
  let perfCache = { '1h': [], '6h': [], '24h': [] };
  let perfCurrentRange = '1h';

  function buildLivePerformanceCard() {
    const card = ui.el('div', 'card');
    card.id = 'live-performance-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.overview.livePerformance') }));
    const sel = ui.el('select', '', { style: 'padding:2px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-secondary)', id: 'perf-range' });
    ['1h', '6h', '24h'].forEach(r => sel.appendChild(ui.el('option', '', { text: t(r === '1h' ? 'page.overview.last1hour' : r === '6h' ? 'page.overview.last6hours' : 'page.overview.last24hours'), value: r })));
    sel.addEventListener('change', () => {
      perfCurrentRange = sel.value;
      renderPerformanceFromCache();
    });
    header.appendChild(sel);
    card.appendChild(header);

    const chartWrap = ui.el('div', '', { id: 'perf-chart', style: 'height:140px;position:relative' });
    chartWrap.innerHTML = '<canvas id="perf-canvas" style="width:100%;height:100%"></canvas>';
    card.appendChild(chartWrap);

    return card;
  }

  function fmtTimeLabel(ts, range) {
    const d = new Date(ts * 1000);
    const hh = d.getHours().toString().padStart(2, '0');
    const mm = d.getMinutes().toString().padStart(2, '0');
    if (range === '24h') return hh + ':' + mm;
    return hh + ':' + mm;
  }

  function renderPerformanceFromCache() {
    const pts = perfCache[perfCurrentRange] || [];
    if (!pts.length) {
      renderPerformanceChart({ points: [], range: perfCurrentRange });
      return;
    }
    renderPerformanceChart({ points: pts, range: perfCurrentRange });
  }

  function renderPerformanceChart(data) {
    const canvas = document.getElementById('perf-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    ctx.scale(dpr, dpr);

    const w = rect.width, h = rect.height;
    const pad = { top: 10, right: 10, bottom: 24, left: 40 };
    const cw = w - pad.left - pad.right;
    const ch = h - pad.top - pad.bottom;

    ctx.clearRect(0, 0, w, h);

    const pts = data.points || [];
    if (pts.length < 2) {
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#9CA3AF';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(t('page.overview.noDataYet'), w / 2, h / 2);
      return;
    }

    const okData = pts.map(p => p.connections_ok || 0);
    const failData = pts.map(p => p.connections_failed || 0);
    const maxVal = Math.max(...okData, ...failData, 1);
    const hasTraffic = okData.some(v => v > 0) || failData.some(v => v > 0);

    if (!hasTraffic) {
      ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border-subtle').trim() || '#F3F4F6';
      ctx.lineWidth = 0.5;
      for (let i = 0; i <= 4; i++) {
        const y = pad.top + (ch / 4) * i;
        ctx.beginPath();
        ctx.moveTo(pad.left, y);
        ctx.lineTo(w - pad.right, y);
        ctx.stroke();
      }
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#9CA3AF';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(t('page.overview.noProxyTraffic'), w / 2, h / 2);

      ctx.font = '10px sans-serif';
      const minTs = pts[0].ts;
      const maxTs = pts[pts.length - 1].ts;
      const tsRange = maxTs - minTs || 1;
      const xOfTs = ts => pad.left + ((ts - minTs) / tsRange) * cw;
      const range = data.range || '1h';
      const labelInterval = range === '24h' ? 3600 : range === '6h' ? 1800 : 600;
      const startTs = Math.ceil(minTs / labelInterval) * labelInterval;
      ctx.textAlign = 'center';
      for (let ts = startTs; ts <= maxTs; ts += labelInterval) {
        const x = xOfTs(ts);
        if (x >= pad.left && x <= w - pad.right) {
          ctx.fillText(fmtTimeLabel(ts, range), x, h - 6);
        }
      }

      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--success').trim() || '#10B981';
      ctx.fillRect(pad.left, 2, 10, 3);
      ctx.fillText('OK', pad.left + 14, 7);
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--danger').trim() || '#EF4444';
      ctx.fillRect(pad.left + 40, 2, 10, 3);
      ctx.fillText('Failed', pad.left + 54, 7);
      return;
    }

    const minTs = pts[0].ts;
    const maxTs = pts[pts.length - 1].ts;
    const tsRange = maxTs - minTs || 1;
    const xOfTs = ts => pad.left + ((ts - minTs) / tsRange) * cw;

    const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4F46E5';
    const successColor = getComputedStyle(document.documentElement).getPropertyValue('--success').trim() || '#10B981';
    const dangerColor = getComputedStyle(document.documentElement).getPropertyValue('--danger').trim() || '#EF4444';

    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border-subtle').trim() || '#F3F4F6';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
    }

    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#9CA3AF';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch / 4) * i;
      const val = Math.round(maxVal * (1 - i / 4));
      ctx.fillText(val, pad.left - 6, y + 3);
    }

    ctx.textAlign = 'center';
    const range = data.range || '1h';
    const labelInterval = range === '24h' ? 3600 : range === '6h' ? 1800 : 600;
    const startTs = Math.ceil(minTs / labelInterval) * labelInterval;
    for (let ts = startTs; ts <= maxTs; ts += labelInterval) {
      const x = xOfTs(ts);
      if (x >= pad.left && x <= w - pad.right) {
        ctx.fillText(fmtTimeLabel(ts, range), x, h - 6);
      }
    }

    ctx.beginPath();
    pts.forEach((p, i) => {
      const x = xOfTs(p.ts);
      const y = pad.top + ch - ((p.connections_ok || 0) / maxVal) * ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = successColor;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineTo(xOfTs(maxTs), pad.top + ch);
    ctx.lineTo(xOfTs(minTs), pad.top + ch);
    ctx.closePath();
    ctx.fillStyle = successColor + '15';
    ctx.fill();

    ctx.beginPath();
    pts.forEach((p, i) => {
      const x = xOfTs(p.ts);
      const y = pad.top + ch - ((p.connections_failed || 0) / maxVal) * ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = dangerColor;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.lineTo(xOfTs(maxTs), pad.top + ch);
    ctx.lineTo(xOfTs(minTs), pad.top + ch);
    ctx.closePath();
    ctx.fillStyle = dangerColor + '10';
    ctx.fill();

    ctx.font = '10px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillStyle = successColor;
    ctx.fillRect(pad.left, 2, 10, 3);
    ctx.fillText('OK', pad.left + 14, 7);
    ctx.fillStyle = dangerColor;
    ctx.fillRect(pad.left + 40, 2, 10, 3);
    ctx.fillText('Failed', pad.left + 54, 7);
  }

  // --- Current Proxy Card ---
  function buildCurrentProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'current-proxy-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';

    const header = ui.el('div', 'card-header');
    const titleRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px' });
    titleRow.appendChild(ui.el('div', 'card-title', { id: 'proxy-card-title', text: t('page.overview.localProxy') }));
    const upstreamBtns = ui.el('div', '', { id: 'upstream-btns', style: 'display:flex;gap:4px' });
    titleRow.appendChild(upstreamBtns);
    header.appendChild(titleRow);
    const poolBtn = ui.el('button', 'card-action', { text: t('page.overview.proxyPool') });
    poolBtn.addEventListener('click', () => router.navigate('proxy-pool'));
    header.appendChild(poolBtn);
    card.appendChild(header);

    const body = ui.el('div', '', { id: 'current-proxy-body', style: 'flex:1' });
    body.innerHTML = `<div class="empty" style="font-size:12px;padding:16px">${t('page.overview.noUpstreamSelected')}</div>`;
    card.appendChild(body);

    const statsRow = ui.el('div', '', { id: 'proxy-stats-row', style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(60px,1fr));gap:0.3em;margin-top:auto' });
    card.appendChild(statsRow);

    return card;
  }

  function renderCurrentProxy(ps, ss) {
    const body = document.getElementById('current-proxy-body');
    const statsWrap = document.getElementById('proxy-stats-row');
    const card = document.getElementById('current-proxy-card');
    const titleEl = document.getElementById('proxy-card-title');
    const btnsEl = document.getElementById('upstream-btns');
    if (!body) return;

    const running = ps && ps.running;
    const s5running = ss && ss.running;
    const anyRunning = running || s5running;

    if (card) {
      card.style.background = anyRunning ? '' : 'rgba(239,68,68,0.06)';
      card.style.borderColor = anyRunning ? '' : 'rgba(239,68,68,0.25)';
    }
    if (titleEl) {
      titleEl.textContent = anyRunning ? t('page.overview.localProxy') : t('page.overview.localProxyStopped');
      titleEl.style.color = anyRunning ? '' : 'var(--danger)';
    }

    body.innerHTML = '';
    if (statsWrap) statsWrap.innerHTML = '';

    const port = ps ? (ps.port || 17277) : 17277;
    const s5port = ss ? (ss.port || 17278) : 17278;
    const bindHost = ps ? (ps.bind_host || '127.0.0.1') : '127.0.0.1';
    const ap = ps && ps.active_proxy;

    const srvColor = anyRunning ? 'var(--success)' : 'var(--danger)';

    const mkBtn = (char, title, color, fn) => {
      const b = ui.el('button', '', { style: `font-size:1.4em;padding:0.1em 0.35em;border:1px solid var(--border);border-radius:0.25em;background:var(--surface-raised);color:${color};cursor:pointer;line-height:1` });
      b.textContent = char; b.title = title;
      b.addEventListener('click', fn);
      return b;
    };

    // HTTP row
    const httpRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;margin-bottom:0.2em' });
    httpRow.appendChild(ui.el('span', '', { style: 'color:var(--text-muted);font-weight:600;font-size:10px;text-transform:uppercase;width:44px;flex-shrink:0', text: 'HTTP' }));
    httpRow.appendChild(ui.el('span', '', { style: `font-family:monospace;font-weight:700;color:${running ? 'var(--success)' : 'var(--text-muted)'};font-size:12px`, text: String(port) }));
    if (running) {
      httpRow.appendChild(mkBtn('■', 'Stop HTTP', 'var(--danger)', () => api.proxyStop().then(() => app.toast(t('page.overview.proxyStopped'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error'))));
      httpRow.appendChild(ui.el('span', '', { style: 'color:var(--success);font-weight:600;font-size:11px', text: '✓' + (ps.connections_ok || 0) }));
      httpRow.appendChild(ui.el('span', '', { style: 'color:var(--danger);font-weight:600;font-size:11px', text: '✗' + (ps.connections_failed || 0) }));
    } else {
      httpRow.appendChild(mkBtn('▶', 'Start HTTP', 'var(--success)', () => api.proxyStart(port).then(() => app.toast(t('page.overview.proxyStarted'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error'))));
    }
    body.appendChild(httpRow);

    // SOCKS5 row
    const s5Row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;margin-bottom:0.4em' });
    s5Row.appendChild(ui.el('span', '', { style: 'color:var(--text-muted);font-weight:600;font-size:10px;text-transform:uppercase;width:44px;flex-shrink:0', text: 'SOCKS5' }));
    s5Row.appendChild(ui.el('span', '', { style: `font-family:monospace;font-weight:700;color:${s5running ? 'var(--success)' : 'var(--text-muted)'};font-size:12px`, text: String(s5port) }));
    if (s5running) {
      s5Row.appendChild(mkBtn('■', 'Stop SOCKS5', 'var(--danger)', () => api.socks5Stop().then(() => app.toast(t('page.overview.socks5Stopped'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error'))));
      s5Row.appendChild(ui.el('span', '', { style: 'color:var(--success);font-weight:600;font-size:11px', text: '✓' + (ss.connections_ok || 0) }));
      s5Row.appendChild(ui.el('span', '', { style: 'color:var(--danger);font-weight:600;font-size:11px', text: '✗' + (ss.connections_failed || 0) }));
    } else {
      s5Row.appendChild(mkBtn('▶', 'Start SOCKS5', 'var(--success)', () => api.socks5Start(s5port).then(() => app.toast(t('page.overview.socks5Started'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error'))));
    }
    body.appendChild(s5Row);

    // Upstream buttons in header
    if (btnsEl) {
      btnsEl.innerHTML = '';
      if (ap) {
        btnsEl.appendChild(mkBtn('»', t('page.overview.nextProxy'), 'var(--accent)', () => api.proxyNext().then(() => app.toast(t('page.overview.switchedToNext'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error'))));
        const recheckBtn = mkBtn('↻', t('page.overview.recheck'), 'var(--info)', () => {
          recheckBtn.disabled = true;
          recheckBtn.style.color = 'var(--text-muted)';
          const icon = recheckBtn.querySelector('span');
          if (icon) icon.style.animation = 'recheckSpin 0.8s linear infinite';
          api.proxyRecheck(ap.address).then(() => poll()).then(() => {
            recheckBtn.disabled = false;
            recheckBtn.style.color = 'var(--info)';
            if (icon) icon.style.animation = '';
          }).catch(e => {
            recheckBtn.disabled = false;
            recheckBtn.style.color = 'var(--info)';
            if (icon) icon.style.animation = '';
            app.toast(t('common.error', { message: e.message }), 'error');
          });
        });
        const recheckIcon = ui.el('span', '', { style: 'display:inline-block' });
        recheckIcon.textContent = '↻';
        recheckBtn.textContent = '';
        recheckBtn.appendChild(recheckIcon);
        btnsEl.appendChild(recheckBtn);
        if (!document.getElementById('recheck-spin-style')) {
          const s = document.createElement('style');
          s.id = 'recheck-spin-style';
          s.textContent = '@keyframes recheckSpin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}';
          document.head.appendChild(s);
        }
      }
    }

    if (!ap) {
      const nextBtn = ui.el('button', '', { style: 'padding:0.4em 1em;border:1px solid var(--border);border-radius:0.3em;background:var(--surface-raised);color:var(--accent);cursor:pointer', text: t('page.overview.selectBestProxy') });
      nextBtn.addEventListener('click', () => api.proxyNext().then(() => app.toast(t('page.overview.proxySelected'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
      body.appendChild(nextBtn);
      return;
    }

    const mode = ap.supports_connect ? 'HTTPS' : (ap.protocol || 'HTTP').toUpperCase();
    const ok = ap.last_status === 'ok';
    const metaRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.3em' });
    metaRow.appendChild(ui.el('span', '', { style: 'color:var(--accent);font-weight:600;font-size:11px', text: mode }));
    metaRow.appendChild(ui.el('span', '', { style: `color:${ok ? 'var(--success)' : 'var(--danger)'};font-size:14px`, text: ok ? '●' : '○' }));
    body.appendChild(metaRow);

    const hasListen = !!(ap.listen_country || ap.listen_city);
    const hasEgress = !!(ap.egress_country || ap.egress_city);
    const diffCountry = hasListen && hasEgress && (ap.listen_country || '') !== (ap.egress_country || '');

    if (diffCountry) {
      const cols = ui.el('div', '', { style: 'display:grid;grid-template-columns:1fr auto 1fr;gap:0 0.5em;margin-bottom:0.3em;font-size:11px' });

      const lc = ui.el('div', '', { style: 'min-width:0' });
      lc.appendChild(ui.el('div', '', { style: 'font-size:0.65em;color:var(--text-muted);text-transform:uppercase;margin-bottom:2px', text: t('page.overview.server') }));
      const lr = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.3em' });
      lr.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.listen_country_code || ap.country_code || ''), style: 'flex-shrink:0' }));
      lr.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: (ap.listen_country || '') + (ap.listen_city ? ', ' + ap.listen_city : '') }));
      lc.appendChild(lr);
      if (ap.listen_isp) lc.appendChild(ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: ap.listen_isp }));
      cols.appendChild(lc);

      const arrow = ui.el('div', '', { style: 'display:flex;align-items:center;color:var(--accent);font-weight:700;font-size:13px;padding-top:0.8em', text: '→' });
      cols.appendChild(arrow);

      const rc = ui.el('div', '', { style: 'min-width:0' });
      rc.appendChild(ui.el('div', '', { style: 'font-size:0.65em;color:var(--text-muted);text-transform:uppercase;margin-bottom:2px', text: t('page.overview.exit') }));
      const rr = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.3em' });
      rr.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.egress_country_code || ap.country_code || ''), style: 'flex-shrink:0' }));
      rr.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: (ap.egress_country || '') + (ap.egress_city ? ', ' + ap.egress_city : '') }));
      rc.appendChild(rr);
      if (ap.egress_isp) rc.appendChild(ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: ap.egress_isp }));
      if (ap.egress_ip) rc.appendChild(ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted)', text: 'ip: ' + ap.egress_ip }));
      cols.appendChild(rc);

      body.appendChild(cols);
    } else {
      const single = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.2em;font-size:11px' });
      single.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code || ''), style: 'flex-shrink:0' }));
      single.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary)', text: (ap.listen_country || ap.egress_country || ap.country || '') + (ap.listen_city || ap.egress_city ? ', ' + (ap.listen_city || ap.egress_city) : '') }));
      body.appendChild(single);
      const details = ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);line-height:1.3;margin-bottom:0.2em' });
      let d = '';
      if (ap.listen_isp) d += ap.listen_isp;
      if (ap.egress_ip) d += (d ? ' · ' : '') + 'exit ' + ap.egress_ip;
      details.textContent = d;
      if (d) body.appendChild(details);
    }

    if (statsWrap) {
      const stats = [
        { l: 'Lat', v: ap.last_latency ? ap.last_latency.toFixed(2) + 's' : '–' },
        { l: 'Avg', v: ap.latency_avg ? ap.latency_avg.toFixed(2) + 's' : '–' },
        { l: 'Speed', v: ap.speed_avg ? ap.speed_avg.toFixed(0) + 'KB/s' : '–' },
        { l: 'Succ', v: ap.success_rate != null ? Math.round(ap.success_rate * 100) + '%' : '–' },
        { l: 'Up', v: (ap.checks_ok || 0) + '/' + (ap.checks_total || 0) },
        { l: 'Last', v: ui.ago(ap.last_check) },
      ];
      stats.forEach(it => {
        const cell = ui.el('div', '', { style: 'text-align:center;padding:0.25em 0.15em;background:var(--surface-raised);border-radius:0.25em;min-width:0' });
        cell.appendChild(ui.el('div', '', { style: 'font-size:0.6em;color:var(--text-muted);text-transform:uppercase', text: it.l }));
        cell.appendChild(ui.el('div', '', { style: 'font-weight:600;color:var(--text-primary);font-size:0.8em', text: it.v }));
        statsWrap.appendChild(cell);
      });
    }

  }

  build();

  // --- Polling ---
  let lastEventSeq = 0;
  let trafficThrottle = 0;
  let lastTrafficItems = [];

  async function poll() {
    try {
      let ps = {}, ss = {}, s = {}, ev = {};
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { ss = await api.socks5Status(); } catch (e) { console.error('socks5Status', e); }
      try { s = await api.snapshot(); } catch (e) { console.error('snapshot', e); }
      try { ev = await api.events(lastEventSeq); } catch (e) { console.error('events', e); }

      // Update stat cards
      const c = s.counts || {};
      updateSparklineBuffers(c);
      const total = c.ratings || 0;
      const alive = c.alive || 0;
      const dead = c.dead || 0;
      const bl = c.blacklist || 0;
      const el = id => document.getElementById(id);
      if (el('stat-val-total')) el('stat-val-total').textContent = total.toLocaleString();
      if (el('stat-val-alive')) el('stat-val-alive').textContent = alive.toLocaleString();
      if (el('stat-val-dead')) el('stat-val-dead').textContent = dead.toLocaleString();
      if (el('stat-val-blacklisted')) el('stat-val-blacklisted').textContent = bl.toLocaleString();
      updateDelta('total', total);
      updateDelta('alive', alive);
      updateDelta('dead', dead);
      updateDelta('blacklisted', bl);
      renderSparklines();

      // Pool progress
      const p = s.progress || {};
      const poolTotal = p.checking_total || p.downloaded || 0;
      const checked = p.checked || 0;
      const pct = poolTotal > 0 ? Math.round((checked / poolTotal) * 100) : 0;
      if (el('pool-pct')) el('pool-pct').textContent = pct + '%';
      if (el('pool-checked')) el('pool-checked').textContent = checked;
      if (el('pool-total')) el('pool-total').textContent = poolTotal;
      if (el('pool-working')) el('pool-working').textContent = p.working || 0;
      if (el('pool-bar-fill')) el('pool-bar-fill').style.width = pct + '%';
      if (el('pool-circle-fill')) {
        const circumference = 2 * Math.PI * 34;
        el('pool-circle-fill').style.strokeDashoffset = circumference - (pct / 100) * circumference;
      }
      if (el('pool-phase')) {
        el('pool-phase').textContent = s.running ? t('page.overview.validatingProxies') : t('page.hunt.idle');
      }
      if (el('pool-current-proxy')) {
        renderPoolProxyInfo(s.last_proxy_details);
      }
      if (el('pool-hunt-btn')) {
        const btn = el('pool-hunt-btn');
        const stop = el('pool-stop-btn');
        if (s.paused) {
          btn.textContent = '▶';
          btn.title = t('page.hunt.resume');
          btn.style.color = 'var(--warning,#9a6700)';
          btn.onclick = () => api.huntResume().then(r => app.toast(r.ok ? t('page.hunt.resumed') : r.error)).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
        } else if (s.running) {
          btn.textContent = '⏸';
          btn.title = t('page.hunt.pause');
          btn.style.color = 'var(--warning,#9a6700)';
          btn.onclick = () => api.huntPause().then(r => app.toast(r.ok ? t('page.hunt.pausedMsg') : r.error)).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
        } else {
          btn.textContent = '▶';
          btn.title = t('page.hunt.startHunt');
          btn.style.color = 'var(--success)';
          btn.onclick = () => api.huntStart().then(r => app.toast(r.ok ? t('page.hunt.huntStarted') : r.error)).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
        }
        if (stop) {
          stop.style.display = (s.running || s.paused) ? '' : 'none';
          stop.style.color = 'var(--danger)';
          stop.onclick = () => api.huntStop().then(() => app.toast(t('page.hunt.huntStopped'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
        }
      }
      if (el('pool-title')) {
        const p = s.paused || false, m = s.manual_pause || false;
        el('pool-title').textContent = p ? (m ? t('page.overview.poolProgress') + ' — ' + t('page.hunt.pausedMsg') : t('page.overview.poolProgress') + ' — No Internet') : (s.running ? t('page.overview.poolProgress') + ' — Running' : t('page.overview.poolProgress'));
      }

      // Top countries
      if (s.top_countries) renderCountries(s.top_countries);

      // Recent activity — merge system events with traffic log
      if (ev && ev.length) {
        lastEventSeq = Math.max(...ev.map(e => e.seq), lastEventSeq);
      }

      let trafficItems = [];
      try {
        if (!trafficThrottle || trafficThrottle <= 0) {
          const reqs = await api.requests();
          const reqList = (reqs && reqs.requests) || [];
          const esc = s => (s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
          trafficItems = reqList.slice(0, 20).map(r => {
            const client = r.client || '?';
            const target = r.target || '?';
            const upstream = r.upstream || '';
            const ok = (r.status || '').toString().startsWith('ok') || (r.status || '').toString().startsWith('2');
            const clientHost = client.replace(/:\d+$/, '');
            const targetShort = target.replace(/^https?:\/\//, '').replace(/:\d+$/, '');
            const html = `<span class="addr">${esc(clientHost)}</span> <span style="color:var(--text-muted)">→</span> <span class="addr">${esc(targetShort)}</span>${upstream && upstream !== 'direct' ? ` <span style="color:var(--text-muted)">via</span> <span style="color:var(--accent);font-size:10px">${esc(upstream)}</span>` : ''}`;
            return {
              ts: r.ts,
              icon: ok ? 'green' : 'red',
              type: 'link',
              ago: ui.ago(r.ts),
              html,
              _sortTs: r.ts,
            };
          });
          lastTrafficItems = trafficItems;
          trafficThrottle = 3;
        } else {
          trafficThrottle--;
          trafficItems = lastTrafficItems;
        }
      } catch (e) { /* ignore */ }

      const eventItems = (ev || []).map(e => {
        const msg = e.msg || '';
        let icon = 'check', iconClass = 'green';
        if (msg.includes('failed')) { icon = 'x'; iconClass = 'red'; }
        else if (msg.includes('removed')) { icon = 'trash'; iconClass = 'yellow'; }
        else if (msg.includes('added')) { icon = 'add'; iconClass = 'blue'; }
        else if (msg.includes('Health')) { icon = 'heart'; iconClass = 'green'; }
        else if (msg.includes('Blacklist')) { icon = 'list'; iconClass = 'yellow'; }
        return { ...e, icon: iconClass, type: icon, ago: ui.ago(e.ts), html: msg.replace(/([\d.]+:\d+)/g, '<span class="addr">$1</span>'), _sortTs: e.ts };
      });

      const merged = [...trafficItems, ...eventItems]
        .sort((a, b) => (b._sortTs || 0) - (a._sortTs || 0))
        .slice(0, 8);
      if (merged.length) renderActivity(merged);

      // Top rated proxies
      renderTopRated(s.top_proxies);

      // System resources (mock for now, can be replaced with real data)
      if (s.resources) {
        if (el('res-cpu-val')) el('res-cpu-val').textContent = s.resources.cpu + '%';
        if (el('res-cpu-bar')) el('res-cpu-bar').style.width = s.resources.cpu + '%';
        if (el('res-memory-val')) el('res-memory-val').textContent = s.resources.memory + '%';
        if (el('res-memory-bar')) el('res-memory-bar').style.width = s.resources.memory + '%';
        if (el('res-disk-val')) el('res-disk-val').textContent = s.resources.disk + '%';
        if (el('res-disk-bar')) el('res-disk-bar').style.width = s.resources.disk + '%';
      }

      // Current proxy
      renderCurrentProxy(ps, ss);

      // Performance chart — load history for all ranges
      try {
        const [h1, h6, h24] = await Promise.all([
          api.history('1h'),
          api.history('6h'),
          api.history('24h'),
        ]);
        perfCache['1h'] = h1 || [];
        perfCache['6h'] = h6 || [];
        perfCache['24h'] = h24 || [];

        if (sparklineBuffers.total.length < 2 && h1 && h1.length) {
          const recent = h1.slice(-MAX_SPARK_POINTS);
          sparklineBuffers.total = recent.map(p => p.total || 0);
          sparklineBuffers.alive = recent.map(p => p.alive || 0);
          sparklineBuffers.dead = recent.map(p => p.dead || 0);
          sparklineBuffers.blacklisted = recent.map(p => Math.max(0, p.total - p.alive - p.dead));
          if (recent.length >= 2) {
            sparklinePrev.total = recent[recent.length - 2].total || 0;
            sparklinePrev.alive = recent[recent.length - 2].alive || 0;
            sparklinePrev.dead = recent[recent.length - 2].dead || 0;
            sparklinePrev.blacklisted = Math.max(0, recent[recent.length - 2].total - recent[recent.length - 2].alive - recent[recent.length - 2].dead);
          }
          renderSparklines();
        }

        renderPerformanceFromCache();
      } catch (e) { console.error('history', e); }

    } catch (e) {
      console.error('overview poll', e);
    }
  }

  poll();
  const id = setInterval(poll, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
