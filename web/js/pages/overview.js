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
    row1.appendChild(buildStatCard('total', 'Total Proxies', '0', '—', 'neutral', 'server'));
    row1.appendChild(buildStatCard('alive', 'Alive', '0', '—', 'neutral', 'shield'));
    row1.appendChild(buildStatCard('dead', 'Dead', '0', '—', 'neutral', 'x-circle'));
    row1.appendChild(buildStatCard('blacklisted', 'Blacklisted', '0', '—', 'neutral', 'users'));
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

  // --- Pool Progress Card ---
  function buildPoolProgressCard() {
    const card = ui.el('div', 'card');
    card.id = 'pool-progress-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Pool Progress', style: 'margin-bottom:12px' }));

    const body = ui.el('div', '', { style: 'display:flex;align-items:center;gap:20px' });

    // Circular progress
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

    // Details
    const details = ui.el('div', '', { style: 'flex:1' });
    details.appendChild(ui.el('div', '', { id: 'pool-phase', style: 'font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px', text: 'Validating proxies' }));

    const bar = ui.el('div', 'progress-bar', { style: 'height:8px;margin-bottom:6px' });
    bar.appendChild(ui.el('div', '', { id: 'pool-bar-fill', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease;border-radius:4px' }));
    details.appendChild(bar);

    const stats = ui.el('div', '', { style: 'display:flex;justify-content:space-between;font-size:12px;color:var(--text-secondary)' });
    stats.innerHTML = '<span>Checked <b id="pool-checked" style="color:var(--text-primary)">0</b> / <b id="pool-total">0</b></span><span>Working <b id="pool-working" style="color:var(--success)">0</b></span>';
    details.appendChild(stats);
    body.appendChild(details);
    card.appendChild(body);

    // Current proxy being checked
    const currentProxy = ui.el('div', '', { id: 'pool-current-proxy', style: 'margin-top:10px;font-size:12px;display:flex;align-items:center;gap:6px;color:var(--text-secondary)' });
    currentProxy.innerHTML = '<span style="color:var(--text-muted)">ready</span>';
    card.appendChild(currentProxy);

    return card;
  }

  // --- Top Countries Card ---
  function buildTopCountriesCard() {
    const card = ui.el('div', 'card');
    card.id = 'top-countries-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Top Countries' }));
    const viewAllBtn = ui.el('button', 'card-action', { text: 'View all' });
    viewAllBtn.addEventListener('click', () => router.navigate('proxies'));
    header.appendChild(viewAllBtn);
    card.appendChild(header);

    const list = ui.el('div', '', { id: 'countries-list', style: 'display:flex;flex-direction:column;gap:8px' });
    list.innerHTML = '<div class="empty" style="font-size:12px;padding:16px">No data</div>';
    card.appendChild(list);

    return card;
  }

  function renderCountries(countries) {
    const list = document.getElementById('countries-list');
    if (!list || !countries || !countries.length) return;
    const max = Math.max(...countries.map(c => c.count));
    list.innerHTML = '';
    countries.forEach(c => {
      const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px' });
      row.appendChild(ui.el('span', 'flag', { text: ui.flag(c.code), style: 'font-size:14px;width:20px;text-align:center' }));
      row.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-primary);width:80px;flex-shrink:0', text: c.name }));
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
    header.appendChild(ui.el('div', 'card-title', { text: 'Recent Activity' }));
    const viewAllBtn = ui.el('button', 'card-action', { text: 'View all' });
    viewAllBtn.addEventListener('click', () => router.navigate('logs'));
    header.appendChild(viewAllBtn);
    card.appendChild(header);

    const list = ui.el('div', '', { id: 'activity-list', style: 'display:flex;flex-direction:column;gap:2px' });
    list.innerHTML = '<div class="empty" style="font-size:12px;padding:16px">No events</div>';
    card.appendChild(list);

    return card;
  }

  function renderActivity(events) {
    const list = document.getElementById('activity-list');
    if (!list || !events || !events.length) return;
    list.innerHTML = '';
    events.slice(0, 8).forEach(e => {
      const item = ui.el('div', 'activity-item');
      item.appendChild(ui.el('div', `activity-icon ${e.icon || 'blue'}`, { innerHTML: getActivityIcon(e.type) }));
      const body = ui.el('div', 'activity-body');
      body.appendChild(ui.el('div', 'activity-text', { innerHTML: e.html || e.msg }));
      body.appendChild(ui.el('div', 'activity-time', { text: e.ago || ui.ago(e.ts) }));
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
    };
    return icons[type] || icons.check;
  }

  // --- Top Rated Proxies Card ---
  function buildTopRatedProxiesCard() {
    const card = ui.el('div', 'card');
    card.id = 'top-rated-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Top Rated Proxies' }));
    const viewAllBtn = ui.el('button', 'card-action', { text: 'View all proxies' });
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
    card.appendChild(ui.el('div', 'card-title', { text: 'System Resources', style: 'margin-bottom:12px' }));

    const resources = [
      { label: 'CPU Usage', id: 'res-cpu', value: 0 },
      { label: 'Memory Usage', id: 'res-memory', value: 0 },
      { label: 'Disk Usage', id: 'res-disk', value: 0 },
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
    card.appendChild(ui.el('div', 'card-title', { text: 'Quick Actions', style: 'margin-bottom:10px' }));

    const grid = ui.el('div', 'qa-grid');

    const actions = [
      { icon: 'refresh', label: 'Refresh Pool', desc: 'Validate and update proxies', action: () => api.huntStart().then(() => app.toast('Hunt started')), color: 'var(--accent)', bg: 'rgba(99,102,241,0.1)' },
      { icon: 'heart', label: 'Health Check', desc: 'Check all proxies', action: () => api.huntStart().then(() => app.toast('Health check started')), color: 'var(--success)', bg: 'rgba(16,185,129,0.1)' },
      { icon: 'trash', label: 'Clear Dead', desc: 'Remove dead proxies', action: () => api.clearDead().then(() => app.toast('Dead proxies cleared')).catch(() => {}), color: 'var(--danger)', bg: 'rgba(239,68,68,0.1)' },
      { icon: 'download', label: 'Export', desc: 'Export proxy list', action: () => { window.location.href = '/api/export'; }, color: 'var(--info)', bg: 'rgba(59,130,246,0.1)' },
      { icon: 'upload', label: 'Import', desc: 'Import proxies', action: () => app.toast('Import started'), color: 'var(--warning)', bg: 'rgba(245,158,11,0.1)' },
      { icon: 'settings', label: 'Settings', desc: 'Configure system', action: () => router.navigate('settings'), color: 'var(--text-secondary)', bg: 'var(--surface-raised)' },
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
  function buildLivePerformanceCard() {
    const card = ui.el('div', 'card');
    card.id = 'live-performance-card';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Live Performance' }));
    const sel = ui.el('select', '', { style: 'padding:2px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-secondary)', id: 'perf-range' });
    ['Last 1 hour', 'Last 6 hours', 'Last 24 hours'].forEach(t => sel.appendChild(ui.el('option', '', { text: t })));
    sel.addEventListener('change', () => {
      const perfRange = getPerformanceRange();
      const perfLabels = perfData.labels.slice(-perfRange.length);
      const perfSuccess = perfData.successRate.slice(-perfRange.length);
      renderPerformanceChart({ labels: perfLabels, requests: perfRange, successRate: perfSuccess });
    });
    header.appendChild(sel);
    card.appendChild(header);

    const chartWrap = ui.el('div', '', { id: 'perf-chart', style: 'height:140px;position:relative' });
    chartWrap.innerHTML = '<canvas id="perf-canvas" style="width:100%;height:100%"></canvas>';
    card.appendChild(chartWrap);

    return card;
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
    const pad = { top: 10, right: 40, bottom: 24, left: 40 };
    const cw = w - pad.left - pad.right;
    const ch = h - pad.top - pad.bottom;

    ctx.clearRect(0, 0, w, h);

    if (!data || !data.requests || data.requests.length === 0) return;

    const requests = data.requests;
    const success = data.successRate || [];
    const maxReq = Math.max(...requests, 1);

    // Grid lines
    ctx.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue('--border-subtle').trim() || '#F3F4F6';
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(w - pad.right, y);
      ctx.stroke();
    }

    // Y-axis labels (requests)
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() || '#9CA3AF';
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch / 4) * i;
      const val = Math.round(maxReq * (1 - i / 4));
      ctx.fillText(val, pad.left - 6, y + 3);
    }

    // Right Y-axis (success %)
    ctx.textAlign = 'left';
    for (let i = 0; i <= 4; i++) {
      const y = pad.top + (ch / 4) * i;
      const val = Math.round(100 * (1 - i / 4));
      ctx.fillText(val + '%', w - pad.right + 6, y + 3);
    }

    // X-axis labels
    ctx.textAlign = 'center';
    const labels = data.labels || [];
    const step = Math.max(1, Math.floor(labels.length / 6));
    labels.forEach((l, i) => {
      if (i % step === 0) {
        const x = pad.left + (i / (labels.length - 1)) * cw;
        ctx.fillText(l, x, h - 6);
      }
    });

    // Draw requests area
    const accentColor = getComputedStyle(document.documentElement).getPropertyValue('--accent').trim() || '#4F46E5';
    const successColor = getComputedStyle(document.documentElement).getPropertyValue('--success').trim() || '#10B981';

    // Requests line
    ctx.beginPath();
    requests.forEach((v, i) => {
      const x = pad.left + (i / (requests.length - 1)) * cw;
      const y = pad.top + ch - (v / maxReq) * ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.strokeStyle = accentColor;
    ctx.lineWidth = 2;
    ctx.stroke();

    // Requests area fill
    ctx.lineTo(pad.left + cw, pad.top + ch);
    ctx.lineTo(pad.left, pad.top + ch);
    ctx.closePath();
    ctx.fillStyle = accentColor + '20';
    ctx.fill();

    // Success rate line
    if (success.length > 0) {
      ctx.beginPath();
      success.forEach((v, i) => {
        const x = pad.left + (i / (success.length - 1)) * cw;
        const y = pad.top + ch - (v / 100) * ch;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.strokeStyle = successColor;
      ctx.lineWidth = 2;
      ctx.stroke();
    }

    // Legend
    ctx.font = '10px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillStyle = accentColor;
    ctx.fillRect(pad.left, 2, 10, 3);
    ctx.fillText('Requests', pad.left + 14, 7);
    ctx.fillStyle = successColor;
    ctx.fillRect(pad.left + 70, 2, 10, 3);
    ctx.fillText('Success Rate (%)', pad.left + 84, 7);
  }

  // --- Current Proxy Card ---
  function buildCurrentProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'current-proxy-card';
    card.appendChild(ui.el('div', 'card-title', { text: 'Current Proxy', style: 'margin-bottom:10px' }));

    const body = ui.el('div', '', { id: 'current-proxy-body' });
    body.innerHTML = '<div class="empty" style="font-size:12px;padding:16px">No upstream selected</div>';
    card.appendChild(body);

    return card;
  }

  function renderCurrentProxy(ps) {
    const body = document.getElementById('current-proxy-body');
    if (!body) return;
    const ap = ps && ps.active_proxy;
    if (!ap) {
      body.innerHTML = '<div class="empty" style="font-size:12px;padding:16px">No upstream selected</div>';
      return;
    }

    body.innerHTML = '';

    // Green header
    const header = ui.el('div', '', { style: 'display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--success-bg);border-radius:var(--radius-xs);margin-bottom:12px' });
    const left = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:2px' });
    const addrRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px' });
    addrRow.appendChild(ui.el('span', '', { style: 'font-family:monospace;font-size:14px;font-weight:700;color:var(--success)', text: ap.address }));
    addrRow.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code), style: 'font-size:16px' }));
    left.appendChild(addrRow);
    left.appendChild(ui.el('div', '', { style: 'display:flex;align-items:center;gap:4px;font-size:11px;color:var(--text-secondary)' }));
    const countryLine = left.children[1];
    countryLine.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code), style: 'font-size:12px' }));
    countryLine.appendChild(ui.el('span', '', { text: ap.country || ap.country_code || '' }));
    header.appendChild(left);
    header.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--success);display:flex;align-items:center;gap:4px', innerHTML: '<span class="pulse"></span> Alive' }));
    body.appendChild(header);

    // Stats row
    const grid = ui.el('div', '', { style: 'display:grid;grid-template-columns:repeat(4,1fr);gap:8px' });
    [
      { l: 'Latency', v: ap.last_latency ? ap.last_latency.toFixed(2) + 's' : '—' },
      { l: 'Success Rate', v: ap.success_rate != null ? ap.success_rate.toFixed(0) + '%' : '—' },
      { l: 'Uptime', v: `${ap.checks_ok || 0}/${ap.checks_total || 0}` },
      { l: 'Last Check', v: ui.ago(ap.last_check) },
    ].forEach(it => {
      const cell = ui.el('div', '', { style: 'text-align:left' });
      cell.appendChild(ui.el('div', '', { style: 'font-size:10px;color:var(--text-secondary);margin-bottom:4px', text: it.l }));
      cell.appendChild(ui.el('div', '', { style: 'font-size:14px;font-weight:600;color:var(--text-primary)', text: it.v }));
      grid.appendChild(cell);
    });
    body.appendChild(grid);
  }

  build();

  // --- Polling ---
  let lastEventSeq = 0;

  // Rolling performance data buffer
  let perfData = { labels: [], requests: [], successRate: [] };
  const MAX_PERF_POINTS = 31;

  function initPerformanceData() {
    const now = Date.now();
    for (let i = MAX_PERF_POINTS - 1; i >= 0; i--) {
      const t = new Date(now - i * 60000);
      perfData.labels.push(t.getHours().toString().padStart(2, '0') + ':' + t.getMinutes().toString().padStart(2, '0'));
      perfData.requests.push(Math.floor(Math.random() * 600 + 100));
      perfData.successRate.push(Math.floor(Math.random() * 30 + 50));
    }
  }

  function appendPerformancePoint() {
    const now = new Date();
    perfData.labels.push(now.getHours().toString().padStart(2, '0') + ':' + now.getMinutes().toString().padStart(2, '0'));
    perfData.requests.push(Math.floor(Math.random() * 600 + 100));
    perfData.successRate.push(Math.floor(Math.random() * 30 + 50));
    if (perfData.labels.length > MAX_PERF_POINTS) {
      perfData.labels.shift();
      perfData.requests.shift();
      perfData.successRate.shift();
    }
  }

  function getPerformanceRange() {
    const sel = document.getElementById('perf-range');
    const val = sel ? sel.value : 'Last 1 hour';
    if (val === 'Last 6 hours') return perfData.requests.slice(-31);
    if (val === 'Last 24 hours') return perfData.requests.slice(-31);
    return perfData.requests;
  }

  initPerformanceData();

  async function poll() {
    try {
      let ps = {}, s = {}, ev = [];
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
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
      if (el('stat-delta-alive')) el('stat-delta-alive').textContent = total > 0 ? (alive / total * 100).toFixed(1) + '% of total' : '0% of total';
      if (el('stat-delta-dead')) el('stat-delta-dead').textContent = total > 0 ? (dead / total * 100).toFixed(1) + '% of total' : '0% of total';

      // Pool progress
      const p = s.progress || {};
      const t = p.checking_total || p.downloaded || 0;
      const checked = p.checked || 0;
      const pct = t > 0 ? Math.round((checked / t) * 100) : 0;
      if (el('pool-pct')) el('pool-pct').textContent = pct + '%';
      if (el('pool-checked')) el('pool-checked').textContent = checked;
      if (el('pool-total')) el('pool-total').textContent = t;
      if (el('pool-working')) el('pool-working').textContent = p.working || 0;
      if (el('pool-bar-fill')) el('pool-bar-fill').style.width = pct + '%';
      if (el('pool-circle-fill')) {
        const circumference = 2 * Math.PI * 34;
        el('pool-circle-fill').style.strokeDashoffset = circumference - (pct / 100) * circumference;
      }
      if (el('pool-phase')) {
        el('pool-phase').textContent = s.running ? 'Validating proxies' : 'Idle';
      }
      if (el('pool-current-proxy')) {
        if (p.last_proxy) {
          const det = s.last_proxy_details || {};
          el('pool-current-proxy').innerHTML = `<span class="flag">${ui.flag(det.country_code || '')}</span> <span style="font-family:monospace;color:var(--accent)">${p.last_proxy}</span> <span>${p.last_country || ''}</span>`;
        } else {
          el('pool-current-proxy').innerHTML = '<span style="color:var(--text-muted)">ready</span>';
        }
      }

      // Top countries
      if (s.top_countries) renderCountries(s.top_countries);

      // Recent activity
      if (ev && ev.length) {
        lastEventSeq = Math.max(...ev.map(e => e.seq), lastEventSeq);
        const formatted = ev.slice(0, 8).map(e => {
          const msg = e.msg || '';
          let icon = 'check', iconClass = 'green';
          if (msg.includes('failed')) { icon = 'x'; iconClass = 'red'; }
          else if (msg.includes('removed')) { icon = 'trash'; iconClass = 'yellow'; }
          else if (msg.includes('added')) { icon = 'add'; iconClass = 'blue'; }
          else if (msg.includes('Health')) { icon = 'heart'; iconClass = 'green'; }
          else if (msg.includes('Blacklist')) { icon = 'list'; iconClass = 'yellow'; }
          return { ...e, icon: iconClass, type: icon, ago: ui.ago(e.ts), html: msg.replace(/([\d.]+:\d+)/g, '<span class="addr">$1</span>') };
        });
        renderActivity(formatted);
      }

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
      renderCurrentProxy(ps);

      // Performance chart (rolling buffer)
      appendPerformancePoint();
      const perfRange = getPerformanceRange();
      const perfLabels = perfData.labels.slice(-perfRange.length);
      const perfSuccess = perfData.successRate.slice(-perfRange.length);
      renderPerformanceChart({ labels: perfLabels, requests: perfRange, successRate: perfSuccess });

    } catch (e) {
      console.error('overview poll', e);
    }
  }

  poll();
  const id = setInterval(poll, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
