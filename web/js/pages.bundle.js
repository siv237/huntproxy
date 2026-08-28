/* ==== js/pages/about.js ==== */
router.register('about', (container) => {
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '18px';
  container.style.minHeight = '0';
  container.style.flex = '1';
  container.style.overflow = 'auto';
  container.style.padding = '8px 4px';

  const logoWrap = ui.el('div', '', { style: 'text-align:center' });
  const logo = ui.el('img', 'about-logo', {
    src: '/assets/biglogo.png',
    alt: 'huntproxy',
    style: 'max-width:760px;width:100%;height:auto',
  });
  logoWrap.appendChild(logo);
  container.appendChild(logoWrap);

  const sectionStyle =
    'font-size:15px;font-weight:600;color:var(--text-primary);margin-top:6px';
  const bodyStyle =
    'font-size:14px;line-height:1.7;color:var(--text-secondary)';

  const descTitle = ui.el('div', '', { style: sectionStyle, text: t('page.about.about') });
  container.appendChild(descTitle);
  const desc = ui.el('div', '', { style: bodyStyle, html: t('page.about.description') });
  container.appendChild(desc);

  const techTitle = ui.el('div', '', { style: sectionStyle, text: t('page.about.technology') });
  container.appendChild(techTitle);
  const tech = ui.el('div', '', { style: bodyStyle, html: t('page.about.techStack') });
  container.appendChild(tech);
});


/* ==== js/pages/actions.js ==== */
router.register('actions', (container) => {
  let entries = [];
  let filter = '';

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const bar = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center;flex-shrink:0;flex-wrap:wrap' });
    const search = ui.el('input', '', {
      type: 'text',
      placeholder: t('page.actions.filterPlaceholder') || 'Filter actions...',
      value: filter,
      style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:220px'
    });
    search.addEventListener('input', (e) => { filter = e.target.value.toLowerCase(); render(); });
    bar.appendChild(search);

    bar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const refreshBtn = ui.el('button', 'btn btn-secondary', { text: t('page.actions.refresh') || 'Refresh' });
    refreshBtn.addEventListener('click', load);
    bar.appendChild(refreshBtn);

    const liveBtn = ui.el('button', 'btn btn-secondary', { text: t('page.actions.live') || 'Live' });
    let liveInterval = null;
    liveBtn.addEventListener('click', () => {
      if (liveInterval) {
        clearInterval(liveInterval);
        liveInterval = null;
        liveBtn.textContent = t('page.actions.live') || 'Live';
        liveBtn.className = 'btn btn-secondary';
      } else {
        load();
        liveInterval = setInterval(load, 3000);
        liveBtn.textContent = t('page.actions.stopLive') || 'Stop live';
        liveBtn.className = 'btn btn-primary';
      }
    });
    bar.appendChild(liveBtn);

    container.appendChild(bar);

    const card = ui.card(t('page.actions.title') || 'Action Log');
    card.id = 'actions-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    container.appendChild(card);
  }

  build();

  async function load() {
    try {
      entries = await api.actions(200);
      render();
    } catch (e) {
      console.error('actions load', e);
    }
  }

  function render() {
    const card = document.getElementById('actions-card');
    if (!card) return;
    card.innerHTML = '';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.actions.title') || 'Action Log' }));
    header.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: `${entries.length}` }));
    card.appendChild(header);

    let rows = entries;
    if (filter) {
      rows = rows.filter(e =>
        (e.action + ' ' + e.detail).toLowerCase().includes(filter));
    }

    if (!rows.length) {
      card.appendChild(ui.emptyState(t('page.actions.empty') || 'No actions recorded yet.'));
      return;
    }

    const wrap = ui.el('div', '', { style: 'flex:1;min-height:0;overflow-y:auto' });
    rows.forEach(e => {
      const snap = e.snapshot || {};
      const total = snap.checking_total || 0;
      const checked = snap.checked || 0;
      const desync = total > 0 && checked > total;
      const row = ui.el('div', '', {
        style: 'padding:6px 8px;border-bottom:1px solid var(--border-subtle);font-size:12px;display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap' +
          (desync ? ';background:rgba(207,34,46,0.08)' : '')
      });
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);font-family:ui-monospace,monospace;white-space:nowrap', text: ui.fmtTime(e.ts) }));
      row.appendChild(ui.el('span', '', { style: 'color:var(--accent);font-weight:600;white-space:nowrap', text: e.action }));
      if (e.detail) row.appendChild(ui.el('span', '', { style: 'color:var(--text-primary)', text: e.detail }));
      const meta = ui.el('span', '', {
        style: 'color:var(--text-muted);font-family:ui-monospace,monospace;white-space:nowrap',
        text: `phase=${snap.phase || '—'} paused=${snap.paused ? 1 : 0} ${checked}/${total} w=${snap.working || 0} f=${snap.failed || 0}` +
          (desync ? ` ⚠ ${Math.round(100 * checked / total)}%` : '')
      });
      if (desync) meta.style.color = 'var(--danger)';
      row.appendChild(meta);
      wrap.appendChild(row);
    });
    card.appendChild(wrap);
  }

  load();
});


/* ==== js/pages/analytics.js ==== */
router.register('analytics', (container) => {
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';

  function makeChartCard(title, id) {
    const card = ui.card(title);
    card.id = id;
    card.style.minHeight = '0';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.overflow = 'hidden';
    return card;
  }

  // Row 0: Full-width heatmap
  const heatmapCard = ui.card(t('page.analytics.proxyHeatmap'));
  heatmapCard.id = 'analytics-heatmap';
  heatmapCard.style.flex = '1';
  heatmapCard.style.minHeight = '0';
  heatmapCard.style.display = 'flex';
  heatmapCard.style.flexDirection = 'column';
  heatmapCard.style.overflow = 'hidden';
  container.appendChild(heatmapCard);

  // Rows 1-3: existing charts (compact)
  const row1 = ui.el('div', 'grid grid-3 row-stretch');
  row1.appendChild(makeChartCard(t('page.analytics.poolSizeOverTime'), 'analytics-pool'));
  row1.appendChild(makeChartCard(t('page.analytics.trafficVolume'), 'analytics-traffic'));
  row1.appendChild(makeChartCard(t('page.analytics.bandwidth24h'), 'analytics-bandwidth'));
  container.appendChild(row1);

  const row2 = ui.el('div', 'grid grid-3 row-stretch');
  row2.appendChild(makeChartCard(t('page.analytics.avgResponseTime'), 'analytics-latency'));
  row2.appendChild(makeChartCard(t('page.analytics.errorTrend'), 'analytics-errors'));
  row2.appendChild(makeChartCard(t('page.analytics.eventHistory'), 'analytics-events'));
  container.appendChild(row2);

  function renderChartCard(id, inner) {
    const card = document.getElementById(id);
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: card.dataset.title || card.titleCache || '' }));
    card.appendChild(header);
    const body = ui.el('div', '', { style: 'flex:1;min-height:0;position:relative;display:flex' });
    body.innerHTML = inner;
    card.appendChild(body);
  }

  function setTitle(id, title) {
    const card = document.getElementById(id);
    if (card) card.titleCache = title;
  }

  setTitle('analytics-pool', t('page.analytics.poolSizeOverTime'));
  setTitle('analytics-traffic', t('page.analytics.trafficVolume'));
  setTitle('analytics-bandwidth', t('page.analytics.bandwidth24h'));
  setTitle('analytics-latency', t('page.analytics.avgResponseTime'));
  setTitle('analytics-errors', t('page.analytics.errorTrend'));
  setTitle('analytics-events', t('page.analytics.eventHistory'));

  let _heatmapPolling = null;
  let _heatmapRows = {};      // address -> { lastCell, initialLastVal, wasActive }
  let _heatmapSegs = 72;
  let _rechecking = false;

  function setCellState(cell, state) {
    cell.classList.remove('ok', 'err', 'none', 'dimmed', 'checking');
    if (state === 'ok') cell.classList.add('ok');
    else if (state === 'err') cell.classList.add('err');
    else if (state === 'checking') cell.classList.add('checking');
    else cell.classList.add('none');
  }

  function renderHeatmap() {
    const card = document.getElementById('analytics-heatmap');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.analytics.proxyHeatmap') }));
    const headerRight = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px' });
    const legend = ui.el('div', 'proxy-heatmap-legend');
    legend.innerHTML = `<span><span class="proxy-heatmap-legend-dot ok"></span>${ui.escHtml(t('page.analytics.heatmapOk'))}</span><span><span class="proxy-heatmap-legend-dot err"></span>${ui.escHtml(t('page.analytics.heatmapErr'))}</span><span><span class="proxy-heatmap-legend-dot none"></span>${ui.escHtml(t('page.analytics.heatmapNone'))}</span><span><span class="proxy-heatmap-legend-dot checking"></span>${ui.escHtml(t('page.analytics.heatmapChecking'))}</span>`;
    headerRight.appendChild(legend);
    const recheckBtn = ui.el('button', 'btn btn-xs btn-secondary', { text: t('page.analytics.recheckAll') });
    recheckBtn.id = 'heatmap-recheck-btn';
    recheckBtn.addEventListener('click', () => {
      if (_rechecking) abortRecheck(recheckBtn);
      else startRecheck(recheckBtn);
    });
    headerRight.appendChild(recheckBtn);
    header.appendChild(headerRight);
    card.appendChild(header);

    const body = ui.el('div', 'proxy-heatmap');
    card.appendChild(body);

    drawHeatmapBody(body);

    if (_heatmapPolling) {
      const btn = document.getElementById('heatmap-recheck-btn');
      if (btn) { btn.textContent = t('page.analytics.abortRecheck'); }
    }
  }

  function drawHeatmapBody(body) {
    _heatmapRows = {};
    api.proxyHeatmap(72).then(data => {
      const proxies = data.proxies || [];
      body.innerHTML = '';
      if (!proxies.length) {
        body.appendChild(ui.el('div', 'empty', { text: t('page.analytics.heatmapEmpty'), style: 'padding:16px' }));
        return;
      }
      const segs = data.segments || 72;
      _heatmapSegs = segs;
      const lastIdx = segs - 1;

      const scroll = ui.el('div', 'proxy-heatmap-scroll');

      proxies.forEach(p => {
        const row = ui.el('div', 'proxy-heatmap-row');
        row.style.cursor = 'pointer';
        row.addEventListener('click', () => { if (window.proxyCard) window.proxyCard.show(p.address); });
        const label = ui.el('span', 'proxy-heatmap-label');
        const favStar = p.is_favorite ? '<svg width="10" height="10" style="vertical-align:-1px;color:var(--warning);flex-shrink:0;width:10px;height:10px"><use href="#icon-star"/></svg>' : '<span style="width:10px;flex-shrink:0"></span>';
        const proto = (p.protocol || 'http').toLowerCase();
        let prefix = 'http://';
        if (proto === 'socks5') prefix = 'socks5://';
        else if (proto === 'socks4') prefix = 'socks4://';
        else if (proto === 'tor' || p.address.includes('.onion')) prefix = 'tor://';
        else if (p.ssl_supported) prefix = 'https://';
        const speed = p.speed_avg ? `<span class="speed">${p.speed_avg.toFixed(0)}KB/s</span>` : '<span class="speed"></span>';
        const score = `<span class="score">${(p.score || 0).toFixed(0)}</span>`;
        label.innerHTML = `${favStar}<span class="flag">${ui.flag(p.country_code)}</span><span class="addr" title="${ui.escHtml(prefix + p.address)}">${prefix}${ui.escHtml(p.address)}</span>${speed}${score}`;
        row.appendChild(label);

        const bar = ui.el('div', 'proxy-heatmap-bar');

        // Find first actual check index
        let firstCheck = -1;
        for (let i = 0; i < segs; i++) {
          if ((p.buckets[i] || 0) !== 0) { firstCheck = i; break; }
        }

        // Walk left-to-right: carry last known state forward for gaps
        let runningState = 0;
        let lastCell = null;
        for (let i = 0; i < segs; i++) {
          const v = p.buckets[i] || 0;
          let cls, dimmed = false;
          if (v !== 0) {
            cls = v === 1 ? 'ok' : 'err';
            runningState = v;
          } else if (i < firstCheck || firstCheck < 0) {
            cls = 'none';
          } else {
            cls = runningState === 1 ? 'ok' : 'err';
            dimmed = true;
          }
          const cell = ui.el('div', `proxy-heatmap-cell ${cls}` + (dimmed ? ' dimmed' : ''));
          const cellLabel = cls === 'ok' ? (dimmed ? t('page.analytics.heatmapOkDimmed') : t('page.analytics.heatmapOk')) : cls === 'err' ? (dimmed ? t('page.analytics.heatmapErrDimmed') : t('page.analytics.heatmapErr')) : t('page.analytics.heatmapNone');
          cell.title = `${p.address} — ${cellLabel}`;
          if (i === lastIdx) lastCell = cell;
          bar.appendChild(cell);
        }
        row.appendChild(bar);
        scroll.appendChild(row);

        _heatmapRows[p.address] = {
          lastCell,
          initialLastVal: p.buckets[lastIdx] || 0,
          wasActive: false,
        };
      });

      body.appendChild(scroll);

      const axis = ui.el('div', 'proxy-heatmap-axis');
      axis.appendChild(ui.el('span', '', { text: t('proxyCard.h72ago') }));
      axis.appendChild(ui.el('span', '', { text: t('proxyCard.h36ago') }));
      axis.appendChild(ui.el('span', '', { text: t('ago.now') }));
      body.appendChild(axis);
    }).catch(e => {
      body.innerHTML = '';
      body.appendChild(ui.el('div', 'empty', { text: t('page.analytics.heatmapEmpty'), style: 'padding:16px' }));
    });
  }

  function startRecheck(btn) {
    if (btn.disabled) return;
    if (!Object.keys(_heatmapRows).length) return;
    btn.disabled = true;
    btn.textContent = t('common.testing');
    api.healthStart().then(() => {
      app.toast(t('common.recheckStarted'));
      _rechecking = true;
      btn.disabled = false;
      btn.textContent = t('page.analytics.abortRecheck');
      const lastIdx = _heatmapSegs - 1;
      _heatmapPolling = setInterval(async () => {
        const body = document.querySelector('#analytics-heatmap .proxy-heatmap');
        const [snap, hm] = await Promise.all([
          api.snapshot().catch(() => null),
          api.proxyHeatmap(72).catch(() => null),
        ]);
        const activeAddrs = new Set();
        if (snap && snap.progress && Array.isArray(snap.progress.active_checks)) {
          for (const c of snap.progress.active_checks) if (c && c.addr) activeAddrs.add(c.addr);
        }
        const hmMap = new Map();
        if (hm && Array.isArray(hm.proxies)) {
          for (const p of hm.proxies) hmMap.set(p.address, p.buckets || []);
        }

        for (const addr in _heatmapRows) {
          const r = _heatmapRows[addr];
          if (!r.lastCell) continue;
          const inActive = activeAddrs.has(addr);

          if (inActive) {
            r.wasActive = true;
            setCellState(r.lastCell, 'checking');
            r.lastCell.title = `${addr} — ${t('page.analytics.heatmapChecking')}`;
            continue;
          }
          // Need heatmap data to determine a result; skip until next poll if it failed.
          if (hm === null) continue;

          const buckets = hmMap.get(addr);
          const inHm = !!buckets;
          const curBucket = inHm ? (buckets[lastIdx] || 0) : null;

          if (r.wasActive) {
            // Just finished checking — assign final colour
            let result;
            if (!inHm) result = 'err';
            else if (curBucket === 2) result = 'err';
            else result = 'ok';
            setCellState(r.lastCell, result);
            r.lastCell.title = `${addr} — ${result === 'ok' ? t('page.analytics.heatmapOk') : t('page.analytics.heatmapErr')}`;
          } else if (curBucket !== null && curBucket !== r.initialLastVal && curBucket !== 0) {
            // Finished between polls (never seen active) — colour by bucket
            const result = curBucket === 1 ? 'ok' : 'err';
            setCellState(r.lastCell, result);
            r.wasActive = true;
            r.lastCell.title = `${addr} — ${result === 'ok' ? t('page.analytics.heatmapOk') : t('page.analytics.heatmapErr')}`;
          } else if (!inHm && r.initialLastVal !== 0) {
            // Dropped out of the alive list without being seen active → failed
            setCellState(r.lastCell, 'err');
            r.lastCell.title = `${addr} — ${t('page.analytics.heatmapErr')}`;
          }
        }

        // null = snapshot fetch failed → keep polling; true/false = actual run state
        const stillRunning = snap === null ? null : (snap.running && snap.phase === 'health');
        if (stillRunning === false) {
          finishRecheck(btn, body);
        }
      }, 500);
      if (window._pageIntervals) window._pageIntervals.push(_heatmapPolling);
    }).catch(e => {
      btn.disabled = false;
      btn.textContent = t('page.analytics.recheckAll');
      if (e.message && e.message.includes('already_running')) {
        app.toast(t('common.recheckAlreadyRunning'), 'warn');
      } else {
        app.toast(t('common.error', { message: e.message }), 'error');
      }
    });
  }

  function finishRecheck(btn, body) {
    if (_heatmapPolling) {
      clearInterval(_heatmapPolling);
      _heatmapPolling = null;
    }
    _rechecking = false;
    if (btn) {
      btn.disabled = false;
      btn.textContent = t('page.analytics.recheckAll');
    }
    if (body) drawHeatmapBody(body);
  }

  function abortRecheck(btn) {
    btn.disabled = true;
    api.healthStop().then(() => {
      // The polling loop will detect phase != health and call finishRecheck.
    }).catch(e => {
      if (e.message && e.message.includes('not_running')) {
        // Already stopped — the polling loop / finishRecheck handles the button.
        if (_rechecking) { btn.disabled = false; btn.textContent = t('page.analytics.abortRecheck'); }
      } else {
        if (_rechecking) { btn.disabled = false; btn.textContent = t('page.analytics.abortRecheck'); }
        app.toast(t('common.error', { message: e.message }), 'error');
      }
    });
  }

  async function load() {
    const [h24, h6h] = await Promise.all([
      api.history('24h').catch(e => { console.error('history 24h', e); return []; }),
      api.history('6h').catch(e => { console.error('history 6h', e); return []; }),
    ]);
    const pts = h24.length >= 2 ? h24 : h6h;

    const labels = pts.map(p => {
      const d = new Date(p.ts * 1000);
      return `${d.getHours()}:${d.getMinutes().toString().padStart(2, '0')}`;
    });

    if (pts.length >= 2) {
      const alive = pts.map(p => p.alive || 0);
      const dead = pts.map(p => p.dead || 0);
      renderChartCard('analytics-pool', charts.multiLineChart([
        { data: alive, color: 'var(--success)', label: t('page.analytics.alive'), fillArea: true },
        { data: dead, color: 'var(--danger)', label: t('page.analytics.dead'), fillArea: true },
      ], { width: 600, height: 220, labels, responsive: true }));

      const reqData = pts.map(p => p.requests || 0);
      renderChartCard('analytics-traffic', charts.lineChart(reqData, {
        width: 600, height: 220, color: 'var(--accent)', fillArea: true, labels, responsive: true
      }));

      const bwIn = pts.map(p => (p.bandwidth_in || 0) / 1024);
      const bwOut = pts.map(p => (p.bandwidth_out || 0) / 1024);
      renderChartCard('analytics-bandwidth', charts.multiLineChart([
        { data: bwIn, color: 'var(--info)', label: t('page.analytics.inKB'), fillArea: true },
        { data: bwOut, color: 'var(--warning)', label: t('page.analytics.outKB'), fillArea: true },
      ], { width: 600, height: 220, labels, responsive: true }));

      const latData = pts.map(p => (p.avg_latency || 0) * 1000);
      renderChartCard('analytics-latency', charts.lineChart(latData, {
        width: 600, height: 220, color: 'var(--warning)', fillArea: true, labels, responsive: true
      }));

      const failData = pts.map(p => p.connections_failed || 0);
      renderChartCard('analytics-errors', charts.lineChart(failData, {
        width: 600, height: 220, color: 'var(--danger)', fillArea: true, labels, responsive: true
      }));
    } else {
      ['analytics-pool', 'analytics-traffic', 'analytics-bandwidth', 'analytics-latency', 'analytics-errors'].forEach(id => {
        const card = document.getElementById(id);
        if (card) {
          card.innerHTML = '';
          const header = ui.el('div', 'card-header', { html: `<div class="card-title">${card.titleCache || ''}</div>` });
          card.appendChild(header);
          card.appendChild(ui.el('div', 'empty', { text: t('page.analytics.notEnoughData'), style: 'padding:16px' }));
        }
      });
    }

    const eventsEl = document.getElementById('analytics-events');
    if (eventsEl) {
      eventsEl.innerHTML = '';
      const header = ui.el('div', 'card-header', { html: `<div class="card-title">${eventsEl.titleCache || t('page.analytics.eventHistory')}</div>` });
      eventsEl.appendChild(header);
      try {
        const activity = await api.activity(20);
        if (activity && activity.length) {
          const headers = [
            { label: 'Time', width: '80px' },
            { label: 'Type', width: '60px', align: 'center' },
            { label: 'Message', width: null, align: 'left' },
          ];
          const rows = activity.map(e => [
            ui.ago(e.ts),
            `<span style="color:${e.type === 'ok' ? 'var(--success)' : e.type === 'error' ? 'var(--danger)' : e.type === 'warn' ? 'var(--warning)' : 'var(--text-secondary)'};font-weight:600">${e.type}</span>`,
            e.msg,
          ]);
          const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
          tblWrap.appendChild(ui.table(headers, rows));
          eventsEl.appendChild(tblWrap);
        } else {
          eventsEl.appendChild(ui.el('div', 'empty', { text: t('page.analytics.noEventsYet') }));
        }
      } catch (e) {
        eventsEl.appendChild(ui.el('div', 'empty', { text: t('page.analytics.couldNotLoadEvents') }));
      }
    }
  }

  renderHeatmap();
  load();
});


/* ==== js/pages/api-docs.js ==== */
router.register('api', (container) => {
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';
  const card = ui.card(t('page.api.apiDocumentation'));
  card.style.flex = '1';
  card.appendChild(ui.el('div', 'empty', { text: t('page.api.comingSoon') }));
  container.appendChild(card);
});


/* ==== js/pages/blacklist.js ==== */
router.register('blacklist', (container) => {
  let state = {
    page: 1,
    limit: 20,
    blacklist: [],
    total: 0,
    search: '',
    sortKey: 'address',
    sortDir: 1,
  };

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });
    const search = ui.el('input', '', { type: 'text', placeholder: t('page.blacklist.searchPlaceholder'), value: state.search, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:200px' });
    search.addEventListener('input', (e) => {
      state.search = e.target.value.toLowerCase();
      state.page = 1;
      load();
    });
    filterBar.appendChild(search);

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const refreshBtn = ui.el('button', 'btn btn-secondary', { text: t('common.refresh') });
    refreshBtn.addEventListener('click', () => load());
    filterBar.appendChild(refreshBtn);

    const addBtn = ui.el('button', 'btn btn-primary', { html: '<svg width="14" height="14"><use href="#icon-plus"/></svg> ' + t('common.add') });
    addBtn.addEventListener('click', () => {
      const addr = prompt(t('page.blacklist.proxyAddress'));
      if (addr) blAdd(addr, prompt(t('page.blacklist.reasonOptional')) || 'manual');
    });
    filterBar.appendChild(addBtn);

    container.appendChild(filterBar);

    const card = ui.card(t('page.blacklist.title'));
    card.id = 'blacklist-table-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    container.appendChild(card);

    const pagWrap = ui.el('div', '', { style: 'display:flex;justify-content:space-between;align-items:center;flex-shrink:0' });
    const left = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)' });
    left.id = 'bl-pag-info';
    pagWrap.appendChild(left);

    const right = ui.el('div', '', { style: 'display:flex;gap:4px' });
    const prev = ui.el('button', 'btn btn-sm btn-secondary', { text: t('common.previous') });
    prev.addEventListener('click', () => { if (state.page > 1) { state.page--; load(); } });
    right.appendChild(prev);

    const pages = ui.el('div', '', { style: 'display:flex;gap:4px', id: 'bl-page-btns' });
    right.appendChild(pages);

    const next = ui.el('button', 'btn btn-sm btn-secondary', { text: t('common.next') });
    next.addEventListener('click', () => { state.page++; load(); });
    right.appendChild(next);
    pagWrap.appendChild(right);
    container.appendChild(pagWrap);
  }

  build();

  async function load() {
    try {
      const params = { page: state.page, limit: state.limit };
      const data = await api.blacklist(params);
      state.blacklist = data.blacklist || [];
      state.total = data.total || 0;
      renderTable();
      renderPagination();
    } catch (e) {
      console.error('blacklist load', e);
      app.toast(t('page.blacklist.failedToLoad'), 'error');
    }
  }

  function setSort(key) {
    if (state.sortKey === key) state.sortDir *= -1;
    else { state.sortKey = key; state.sortDir = 1; }
    renderTable();
  }

  function renderTable() {
    const card = document.getElementById('blacklist-table-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.blacklist.title') }));
    card.appendChild(header);

    let rows = state.blacklist;
    if (state.search) {
      rows = rows.filter(r =>
        (r.address || '').toLowerCase().includes(state.search) ||
        (r.reason || '').toLowerCase().includes(state.search)
      );
    }

    rows = rows.slice().sort((a, b) => ui.sortValue(a, b, state.sortKey, state.sortDir));

    if (!rows.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.blacklist.noBlacklisted') }));
      return;
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.sortKey, state.sortDir) : ''), width, align, sortKey: key, onSort: key ? () => setSort(key) : undefined });
    const headers = [
      h('Proxy', 'address', null, 'left'),
      h('Country', 'country', '120px', 'left'),
      h('Reason', 'reason', '150px', 'left'),
      h('Score', 'score', '60px', 'right'),
      h('', null, '80px', 'center'),
    ];
    const bodyRows = rows.map(b => [
      `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(b.address)}" style="cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${b.address}</span>`,
      `${ui.escHtml(b.country || '—')}`,
      `<span style="color:var(--danger)">${b.reason || '—'}</span>`,
      Math.round(b.score || 0),
      `<button class="btn btn-xs btn-secondary" onclick="blRemove('${b.address}')">${t('common.remove')}</button>`,
    ]);
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, bodyRows));
    card.appendChild(tblWrap);

    tblWrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
  }

  function renderPagination() {
    const info = document.getElementById('bl-pag-info');
      if (info) info.textContent = t('page.blacklist.showing', {from: (state.page - 1) * state.limit + 1, to: Math.min(state.page * state.limit, state.total), total: state.total});

    const btns = document.getElementById('bl-page-btns');
    if (!btns) return;
    btns.innerHTML = '';
    const totalPages = Math.ceil(state.total / state.limit) || 1;
    const start = Math.max(1, state.page - 2);
    const end = Math.min(totalPages, start + 4);
    for (let i = start; i <= end; i++) {
      const b = ui.el('button', `btn btn-sm ${i === state.page ? 'btn-primary' : 'btn-secondary'}`, { text: i.toString() });
      b.addEventListener('click', () => { state.page = i; load(); });
      btns.appendChild(b);
    }
  }

  async function blAdd(addr, reason) {
    try {
      await api.blAdd(addr, reason);
      app.toast(t('page.blacklist.addedToBlacklist'));
      load();
    } catch (e) {
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  async function blRemove(addr) {
    try {
      await api.blRemove(addr);
      app.toast(t('page.blacklist.removedFromBlacklist'));
      load();
    } catch (e) {
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  load();
  const id = setInterval(load, 10000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});

window.blAdd = async function(addr, reason) {
  try {
    await api.blAdd(addr, reason || 'manual');
    app.toast(t('page.blacklist.addedToBlacklist'));
    if (router.current === 'blacklist') router.resolve();
    else if (router.current === 'proxies') router.resolve();
  } catch (e) {
    app.toast(t('common.error', {message: e.message}), 'error');
  }
};

window.blRemove = async function(addr) {
  try {
    await api.blRemove(addr);
    app.toast(t('page.blacklist.removedFromBlacklist'));
  } catch (e) {
    app.toast(t('common.error', {message: e.message}), 'error');
  }
};


/* ==== js/pages/blocklists.js ==== */
router.register('blocklists', (container) => {
  let sources = [];
  let editingId = null;
  let _loading = false;
  let fetchProgress = {};
  let progressPoller = null;

  function fmtBytes(n) {
    if (!n) return '0B';
    if (n >= 1048576) return (n / 1048576).toFixed(1) + 'MB';
    if (n >= 1024) return (n / 1024).toFixed(0) + 'KB';
    return n + 'B';
  }

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
    const row = ui.el('div', 'grid grid-2 row-stretch');
    row.appendChild(buildSourcesCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);
  }

  function buildSourcesCard() {
    const card = ui.card(t('page.blocklists.sources'));
    card.id = 'card-blocklists';
    card.style.overflow = 'hidden';

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap' });

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.blocklists.newSource') });
    addBtn.addEventListener('click', () => { editingId = null; showEditor(null); });
    btnRow.appendChild(addBtn);

    const refreshBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.blocklists.refresh') });
    function startFetch() {
      refreshBtn.disabled = true;
      refreshBtn.textContent = t('page.blocklists.fetching');
      fetchProgress = {};
      progressPoller = setInterval(() => {
        api.blocklistProgress().then(r => {
          if (r && r.progress) {
            fetchProgress = r.progress;
            updateSourcesCard(sources);
          }
        }).catch(() => {});
      }, 2000);
      api.blocklistFetch().then(r => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.blocklists.refresh');
        fetchProgress = {};
        if (r.ok) {
          app.toast(t('page.blocklists.fetchDone', { count: r.total_entries || 0 }));
        } else {
          app.toast(t('common.error', { message: r.error || 'unknown' }), 'error');
        }
        load();
      }).catch(e => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.blocklists.refresh');
        fetchProgress = {};
        app.toast(t('common.error', { message: e.message }), 'error');
      });
    }
    refreshBtn.addEventListener('click', startFetch);
    btnRow.appendChild(refreshBtn);

    card.appendChild(btnRow);

    const tblWrap = ui.el('div', '', { id: 'blocklists-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.noSources')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.blocklists.editor'));
    card.id = 'card-bl-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'bl-editor-body' });
    body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.selectToEdit')}</div>`;
    card.appendChild(body);

    return card;
  }

  function dirLabel(d) {
    if (d === 'outside') return t('page.blocklists.directionOutside');
    if (d === 'domestic') return t('page.blocklists.directionDomestic');
    return t('page.blocklists.directionInside');
  }

  function classLabel(c) {
    if (c === 'white') return t('page.blocklists.classWhite');
    return t('page.blocklists.classBlock');
  }

  function typeLabel(ty) {
    if (ty === 'domain') return t('page.blocklists.typeDomain');
    return t('page.blocklists.typeIp');
  }

  function showEditor(src) {
    const body = document.getElementById('bl-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = src ? src.id : null;

    const mkField = (id, label, value, placeholder, opts = {}) => {
      const row = ui.el('div', '', { style: 'margin-bottom:10px' });
      row.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: label }));
      const input = ui.el('input', '', { id, type: 'text', value, placeholder, style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' + (opts.disabled ? ';opacity:0.6' : '') });
      if (opts.disabled) input.disabled = true;
      row.appendChild(input);
      return row;
    };

    const mkSelect = (id, label, options, selected) => {
      const row = ui.el('div', '', { style: 'margin-bottom:10px' });
      row.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: label }));
      const sel = ui.el('select', '', { id, style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
      options.forEach(o => {
        const opt = ui.el('option', '', { value: o.value, text: o.label });
        if (o.value === selected) opt.selected = true;
        sel.appendChild(opt);
      });
      row.appendChild(sel);
      return row;
    };

    body.appendChild(mkField('bl-name', t('page.blocklists.nameLabel'), src ? src.name : '', 'e.g. Russia RKN IPs'));
    body.appendChild(mkField('bl-id', t('page.blocklists.idLabel'), src ? src.id : '', 'auto-generated', { disabled: !!src }));

    const nameInput = document.getElementById('bl-name');
    const idInput = document.getElementById('bl-id');
    if (!src) {
      nameInput.addEventListener('input', () => {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      });
    }

    body.appendChild(mkField('bl-country', t('page.blocklists.countryLabel'), src ? src.country : '', 'RU, US, CN...'));
    body.appendChild(mkSelect('bl-direction', t('page.blocklists.directionLabel'), [
      { value: 'inside', label: t('page.blocklists.directionInside') },
      { value: 'outside', label: t('page.blocklists.directionOutside') },
      { value: 'domestic', label: t('page.blocklists.directionDomestic') },
    ], src ? src.direction : 'inside'));
    body.appendChild(mkSelect('bl-list-type', t('page.blocklists.typeLabel'), [
      { value: 'ip', label: t('page.blocklists.typeIp') },
      { value: 'domain', label: t('page.blocklists.typeDomain') },
    ], src ? src.list_type : 'ip'));
    body.appendChild(mkSelect('bl-class', t('page.blocklists.classLabel'), [
      { value: 'block', label: t('page.blocklists.classBlock') },
      { value: 'white', label: t('page.blocklists.classWhite') },
    ], src ? (src.class || 'block') : 'block'));
    body.appendChild(mkField('bl-route', t('page.blocklists.routeLabel'), src ? (src.route || '') : '', 'direct / pool / custom:id / proxy:addr'));
    body.appendChild(mkField('bl-url', t('page.blocklists.urlLabel'), src ? src.url : '', 'https://example.com/list.txt'));
    body.appendChild(mkField('bl-proxy', t('page.blocklists.proxyLabel'), src ? (src.download_proxy || '') : '', 'http://127.0.0.1:17277 or empty'));

    if (src && src.last_fetched_at) {
      const stats = ui.el('div', '', { style: 'padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;margin-bottom:12px' });
      stats.innerHTML = `
        <div style="margin-bottom:4px;color:var(--text-secondary)">${t('page.blocklists.sourceStats')}</div>
        <div>${t('page.blocklists.lastFetched')}: <b>${ui.ago(src.last_fetched_at)}</b></div>
        <div>${t('page.blocklists.lastStatus')}: <b style="color:${src.last_fetch_status === 'ok' ? 'var(--success)' : 'var(--danger)'}">${src.last_fetch_status || '—'}</b></div>
        ${src.last_fetch_error ? `<div style="color:var(--danger)">${ui.escHtml(src.last_fetch_error)}</div>` : ''}
        <div style="margin-top:6px">${t('page.blocklists.fetched')}: ${src.last_fetch_count}</div>
        <div style="margin-top:2px;color:var(--text-muted)">${t('page.blocklists.cumulative')}: ${src.total_fetched}</div>`;
      body.appendChild(stats);
    }

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: src ? t('page.blocklists.saveChanges') : t('page.blocklists.addSource') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('bl-name').value.trim();
      let sourceId = document.getElementById('bl-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!sourceId) sourceId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const url = document.getElementById('bl-url').value.trim();
      if (!name) { app.toast(t('common.nameRequired'), 'error'); return; }
      if (!url) { app.toast(t('common.urlRequired'), 'error'); return; }
      const data = {
        id: sourceId, name, url,
        country: document.getElementById('bl-country').value.trim().toUpperCase(),
        direction: document.getElementById('bl-direction').value,
        list_type: document.getElementById('bl-list-type').value,
        class: document.getElementById('bl-class').value,
        route: document.getElementById('bl-route').value.trim(),
        download_proxy: document.getElementById('bl-proxy').value.trim(),
      };
      if (editingId) {
        api.blocklistUpdate(editingId, data).then(() => {
          app.toast(t('page.blocklists.sourceUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      } else {
        api.blocklistCreate(data).then(() => {
          app.toast(t('page.blocklists.sourceAdded'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (src) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
      cancelBtn.addEventListener('click', () => { editingId = null; resetEditor(); });
      btnRow.appendChild(cancelBtn);
    }
    body.appendChild(btnRow);
  }

  function resetEditor() {
    const body = document.getElementById('bl-editor-body');
    if (body) body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.selectToEdit')}</div>`;
  }

  function statusBadge(s) {
    const p = fetchProgress[s.id];
    if (p) {
      if (p.status === 'downloading') return `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
      if (p.status === 'connecting') return `<span style="color:var(--info);font-size:11px">…</span>`;
      if (p.status === 'parsing') return `<span style="color:var(--warning);font-size:11px">⏳</span>`;
      if (p.status === 'done') return `<span style="color:var(--success);font-size:11px">✓ ${p.count || 0}</span>`;
      if (p.status === 'error') return `<span style="color:var(--danger);font-size:11px">ERR</span>`;
    }
    if (!s.last_fetched_at) return `<span style="color:var(--text-muted);font-size:11px">${t('page.blocklists.never')}</span>`;
    if (s.last_fetch_status === 'ok') return `<span style="color:var(--success);font-size:11px">OK</span>`;
    return `<span style="color:var(--danger);font-size:11px" title="${ui.escHtml(s.last_fetch_error || '')}">ERR</span>`;
  }

  function countryFlag(cc) {
    if (!cc) return '';
    return ui.flag(cc) + ' ';
  }

  function updateSourcesCard(list) {
    const wrap = document.getElementById('blocklists-tbl');
    if (!wrap) return;
    sources = list || [];

    if (!list || !list.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.noSources')}</div>`;
      return;
    }

    const grouped = {};
    list.forEach(s => {
      const key = `${s.country || '??'}|${s.direction || 'inside'}`;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(s);
    });

    wrap.innerHTML = '';
    Object.keys(grouped).sort().forEach(key => {
      const [country, direction] = key.split('|');
      const items = grouped[key];

      const grp = ui.el('div', '', { style: 'margin-bottom:12px' });
      const hdr = ui.el('div', '', { style: 'font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:4px;padding:2px 0;text-transform:uppercase;letter-spacing:0.5px' });
      hdr.textContent = `${countryFlag(country)}${country || '??'} — ${dirLabel(direction)}`;
      grp.appendChild(hdr);

      const headers = [
        { label: t('page.blocklists.colSource'), width: '160px' },
        { label: t('page.blocklists.colType'), width: '60px', align: 'center' },
        { label: t('page.blocklists.colStatus'), width: '40px', align: 'center' },
        { label: t('page.blocklists.colEntries'), width: '60px', align: 'right' },
        { label: t('page.blocklists.colProxy'), width: '70px' },
        { label: '', width: '40px', align: 'center' },
        { label: '', width: '70px', align: 'center' },
      ];

      const rows = items.map(s => {
        const nameSpan = document.createElement('span');
        nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer;font-size:12px';
        nameSpan.textContent = s.name || s.id;
        nameSpan.dataset.sourceId = s.id;
        nameSpan.dataset.action = 'edit';

        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'btn btn-xs ' + (s.enabled ? 'btn-primary' : 'btn-ghost');
        toggleBtn.style.cssText = 'padding:1px 4px;font-size:9px';
        toggleBtn.textContent = s.enabled ? t('common.on') : t('common.off');
        toggleBtn.dataset.sourceId = s.id;
        toggleBtn.dataset.action = 'toggle';

        const editBtn = document.createElement('button');
        editBtn.className = 'btn btn-xs btn-secondary';
        editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
        editBtn.textContent = t('common.edit');
        editBtn.dataset.sourceId = s.id;
        editBtn.dataset.action = 'edit';

        const delBtn = document.createElement('button');
        delBtn.className = 'btn btn-xs btn-danger';
        delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
        delBtn.textContent = t('common.delete');
        delBtn.dataset.sourceId = s.id;
        delBtn.dataset.action = 'delete';

        const clsBadge = s.class === 'white'
          ? `<span style="font-size:8px;font-weight:700;color:#fff;background:var(--success);border-radius:3px;padding:1px 3px;margin-right:4px;vertical-align:middle" title="${ui.escHtml(classLabel('white'))}">W</span>`
          : '';
        const p = fetchProgress[s.id];
        let entryCell;
        if (p) {
          if (p.status === 'downloading') entryCell = `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
          else if (p.status === 'parsing') entryCell = `<span style="color:var(--warning);font-size:11px">⏳ parse</span>`;
          else if (p.status === 'done' && p.count != null) entryCell = `<span style="color:var(--success);font-size:11px">✓ ${p.count}</span>`;
          else entryCell = s.entry_count ?? s.last_fetch_count ?? 0;
        } else {
          entryCell = s.entry_count ?? s.last_fetch_count ?? 0;
        }

         return [
          clsBadge + nameSpan.outerHTML,
          `<span style="font-size:10px;color:var(--text-muted)">${typeLabel(s.list_type)}</span>`,
          statusBadge(s),
          entryCell,
          s.download_proxy ? `<span style="font-size:9px;color:var(--text-muted)">via proxy</span>` : `<span style="font-size:9px;color:var(--text-muted)">direct</span>`,
          toggleBtn.outerHTML,
          editBtn.outerHTML + delBtn.outerHTML,
        ];
      });

      const tbl = ui.table(headers, rows);
      grp.appendChild(tbl);
      grp.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', () => {
          const sid = el.dataset.sourceId;
          const action = el.dataset.action;
          if (action === 'edit') editSource(sid);
          else if (action === 'delete') deleteSource(sid);
          else if (action === 'toggle') toggleSource(sid);
        });
      });
      wrap.appendChild(grp);
    });
  }

  function editSource(id) {
    api.blocklistGet(id).then(src => {
      if (src) showEditor(src);
      else app.toast(t('page.blocklists.sourceNotFound'), 'error');
    }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  function deleteSource(id) {
    if (!confirm(t('common.confirmDelete', { item: 'blocklist source' }))) return;
    api.blocklistDelete(id).then(() => {
      app.toast(t('page.blocklists.sourceDeleted'));
      if (editingId === id) { editingId = null; resetEditor(); }
      load();
    }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  function toggleSource(id) {
    api.blocklistToggle(id).then(() => load()).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    if (progressPoller) return;
    _loading = true;
    try {
      const result = await api.blocklists();
      sources = result.sources || [];
      updateSourcesCard(sources);
    } catch (e) {
      console.error('blocklists load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 5000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/client-card.js ==== */
const clientCard = {
  _timer: null,

  async show(client, hours = 24) {
    this.close();
    const overlay = ui.el('div', 'client-card-overlay');
    const modal = ui.el('div', 'client-card');
    modal.innerHTML = `<div style="padding:48px;text-align:center;color:var(--text-muted)">${t('common.loading')}</div>`;
    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) this.close(); });
    document.body.appendChild(overlay);
    this._onKey = (e) => { if (e.key === 'Escape') this.close(); };
    document.addEventListener('keydown', this._onKey);
    await this._load(modal, client, hours);
    this._timer = setInterval(() => {
      if (!document.body.contains(modal)) { this.close(); return; }
      this._load(modal, client, this._hours, true);
    }, 5000);
  },

  close() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
    if (this._onKey) { document.removeEventListener('keydown', this._onKey); this._onKey = null; }
    const overlay = document.querySelector('.client-card-overlay');
    if (overlay) overlay.remove();
  },

  async _load(modal, client, hours, silent = false) {
    this._hours = hours;
    try {
      const [data, alive] = await Promise.all([
        api.clientDetail(client, hours),
        api.proxyAlive().catch(() => []),
      ]);
      if (!document.body.contains(modal)) return;
      this._geo = {};
      (alive || []).forEach(p => { if (p && p.address) this._geo[p.address] = p; });
      const content = modal.querySelector('.client-card-content');
      const list = modal.querySelector('.cc-hist-list');
      this._uiState = {
        contentScroll: content ? content.scrollTop : 0,
        listScroll: list ? list.scrollTop : 0,
        open: new Set(Array.from(modal.querySelectorAll('.cc-hist-item.open') || [], el => el.dataset.key || '')),
      };
      this._render(modal, data, hours);
    } catch (e) {
      if (!silent) modal.innerHTML = `<div style="padding:48px;color:var(--danger)">${t('common.error', { message: ui.escHtml(e.message) })}</div>`;
    }
  },

  _render(modal, data, hours) {
    const s = data.summary || {};
    modal.innerHTML = '';
    modal.appendChild(this._header(modal, s, hours));
    const content = ui.el('div', 'client-card-content');
    modal.appendChild(content);

    content.appendChild(this._kpiRow(s, data));
    content.appendChild(this._activity(data.hourly || []));

    const cols = ui.el('div', 'client-card-cols');
    cols.appendChild(this._history(data.recent || []));
    cols.appendChild(this._sidePanel(s, data));
    content.appendChild(cols);

    const st = this._uiState || {};
    if (st.open && st.open.size) {
      content.querySelectorAll('.cc-hist-item').forEach(item => {
        if (st.open.has(item.dataset.key)) {
          item.classList.add('open');
          const d = item.querySelector('.cc-hist-details');
          if (d) d.style.display = '';
        }
      });
    }
    const newList = content.querySelector('.cc-hist-list');
    if (newList && st.listScroll) newList.scrollTop = st.listScroll;
    content.scrollTop = st.contentScroll || 0;
    this._uiState = null;
  },

  _header(modal, s, hours) {
    const bar = ui.el('div', 'client-card-header');
    const left = ui.el('div', 'client-card-id');
    left.appendChild(ui.el('div', 'client-card-ava', { html: this._svg('user') }));
    const idText = ui.el('div', 'client-card-idtext');
    const nameRow = ui.el('div', 'client-card-namerow');
    nameRow.appendChild(ui.el('div', 'client-card-name', { text: s.client || '—' }));
    if (s.hostname) nameRow.appendChild(ui.el('span', 'client-card-dns', { text: `(${s.hostname})`, title: s.hostname }));
    const online = (Date.now() / 1000 - (s.last_seen || 0)) < 300;
    nameRow.appendChild(ui.el('span', 'client-card-state' + (online ? ' on' : ''), {
      html: `<span class="pulse${online ? '' : ' off'}"></span>${online ? t('clientCard.online') : t('clientCard.offline')}`,
    }));
    idText.appendChild(nameRow);
    const subParts = [];
    if (s.client === '127.0.0.1' || s.client === '::1' || s.client === 'localhost') subParts.push(t('clientCard.local'));
    subParts.push(t('clientCard.subtitle', { last: ui.ago(s.last_seen || 0) }));
    idText.appendChild(ui.el('div', 'client-card-sub', { text: subParts.join(' · ') }));
    left.appendChild(idText);
    bar.appendChild(left);

    const right = ui.el('div', 'client-card-headright');
    const tabs = ui.el('div', 'client-card-tabs');
    [['24h', 24, t('clientCard.period24h')], ['7d', 168, t('clientCard.period7d')], ['30d', 720, t('clientCard.period30d')]].forEach(([, h, label]) => {
      const tab = ui.el('button', 'client-card-tab' + (h === hours ? ' active' : ''), { text: label });
      tab.addEventListener('click', () => this._load(modal, s.client, h, true));
      tabs.appendChild(tab);
    });
    right.appendChild(tabs);
    const closeBtn = ui.el('button', 'client-card-close', { html: this._svg('x') });
    closeBtn.addEventListener('click', () => this.close());
    right.appendChild(closeBtn);
    bar.appendChild(right);
    return bar;
  },

  _kpiRow(s, data) {
    const grid = ui.el('div', 'client-card-kpis');
    const tiles = [
      { icon: 'zap', color: 'var(--accent)', value: (s.requests || 0).toLocaleString(), label: t('clientCard.kpiRequests'), sub: '≈ ' + ui.fmtBytes(s.total_bytes || 0) },
      { icon: 'download', color: 'var(--info)', value: ui.fmtBytes(s.total_bytes || 0), label: t('clientCard.kpiTraffic'), sub: `↓ ${ui.fmtBytes(s.bytes_out || 0)} · ↑ ${ui.fmtBytes(s.bytes_in || 0)}` },
      { icon: 'clock', color: 'var(--warning)', value: s.avg_duration ? ui.fmtLatency(s.avg_duration) : '—', label: t('clientCard.kpiAvgTime'), sub: t('clientCard.kpiAvgTimeSub') },
      { icon: 'route', color: '#8a2be2', value: String((data.routes || []).length), label: t('clientCard.kpiRoutes'), sub: t('clientCard.kpiRoutesSub') },
      { icon: 'globe', color: 'var(--success)', value: String((data.domains || []).length), label: t('clientCard.kpiDomains'), sub: t('clientCard.kpiDomainsSub') },
    ];
    tiles.forEach(tl => {
      const tile = ui.el('div', 'cc-tile');
      tile.innerHTML = `<div class="cc-tile-icon" style="color:${tl.color};background:color-mix(in srgb, ${tl.color} 12%, transparent)">${this._svg(tl.icon)}</div>` +
        `<div class="cc-tile-body"><div class="cc-tile-value">${ui.escHtml(tl.value)}</div><div class="cc-tile-label">${ui.escHtml(tl.label)}</div><div class="cc-tile-sub">${ui.escHtml(tl.sub)}</div></div>`;
      grid.appendChild(tile);
    });
    return grid;
  },

  _activity(hourly) {
    const card = ui.el('div', 'client-card-section');
    const head = ui.el('div', 'cc-sec-head');
    head.appendChild(ui.el('div', 'cc-sec-title', { text: t('clientCard.activity') }));
    const legend = ui.el('div', 'cc-legend');
    legend.innerHTML = `<span class="cc-legend-item"><span class="cc-legend-dot" style="background:var(--accent)"></span>${t('clientCard.legendRequests')}</span>` +
      `<span class="cc-legend-item"><span class="cc-legend-dot" style="background:var(--warning)"></span>${t('clientCard.legendTraffic')}</span>`;
    head.appendChild(legend);
    card.appendChild(head);

    const wrap = ui.el('div', 'cc-bars');
    const maxReq = Math.max(...hourly.map(h => h.requests || 0), 1);
    const maxBytes = Math.max(...hourly.map(h => h.bytes || 0), 1);
    hourly.forEach(h => {
      const d = new Date(h.ts * 1000);
      const col = ui.el('div', 'cc-bar-col');
      const reqH = Math.round((h.requests || 0) / maxReq * 64);
      const byH = Math.round((h.bytes || 0) / maxBytes * 64);
      const title = `${d.getHours()}:00 — ${h.requests} ${t('page.proxyControl.requests')} · ${ui.fmtBytes(h.bytes)}`;
      col.appendChild(ui.el('div', 'cc-bar cc-bar-bytes', { style: `height:${Math.max(byH, h.bytes ? 2 : 0)}px`, title }));
      col.appendChild(ui.el('div', 'cc-bar cc-bar-reqs', { style: `height:${Math.max(reqH, h.requests ? 2 : 0)}px`, title }));
      col.appendChild(ui.el('div', 'cc-bar-label', { text: d.getHours().toString().padStart(2, '0') }));
      wrap.appendChild(col);
    });
    card.appendChild(wrap);
    return card;
  },

  _history(recent) {
    const card = ui.el('div', 'client-card-section client-card-hist');
    const head = ui.el('div', 'cc-sec-head');
    head.appendChild(ui.el('div', 'cc-sec-title', { text: t('clientCard.history') }));
    const searchWrap = ui.el('div', 'cc-search');
    searchWrap.innerHTML = this._svg('search');
    const input = ui.el('input', 'cc-search-input', { type: 'text', placeholder: t('page.proxyControl.filterHistory'), spellcheck: 'false' });
    input.value = this._histFilter || '';
    let debounce = null;
    input.addEventListener('input', () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        this._histFilter = input.value.toLowerCase().trim();
        let visible = 0;
        card.querySelectorAll('.cc-hist-item').forEach(item => {
          const show = !this._histFilter || (item.dataset.search || '').includes(this._histFilter);
          item.style.display = show ? '' : 'none';
          if (show) visible++;
        });
        const empty = card.querySelector('.cc-filter-empty');
        if (empty) empty.style.display = visible ? 'none' : '';
      }, 120);
    });
    searchWrap.appendChild(input);
    head.appendChild(searchWrap);
    card.appendChild(head);
    if (!recent.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noRecentRequests') }));
      return card;
    }
    const list = ui.el('div', 'cc-hist-list');
    let visible = 0;
    recent.forEach(r => {
      const host = ui.hostOf(r.target);
      const item = ui.el('div', 'cc-hist-item');
      item.dataset.key = (r.ts || 0) + '|' + (r.target || '');
      item.dataset.search = [r.target, host, r.upstream, r.status, r.via].join(' ').toLowerCase();
      if (this._histFilter && !item.dataset.search.includes(this._histFilter)) item.style.display = 'none';
      else visible++;
      const row = ui.el('div', 'cc-hist-row');
      row.innerHTML = ui.hostAvatar(host, 30) +
        `<div class="cc-hist-main"><div class="cc-hist-host">${ui.escHtml(host || '—')}</div>` +
        `<div class="cc-hist-path" title="${ui.escHtml(r.target)}">${ui.escHtml(r.target.length > 70 ? r.target.slice(0, 68) + '…' : r.target)}</div></div>` +
        `<div class="cc-hist-meta"><span class="cc-hist-time">${ui.fmtTime(r.ts).split(' ')[0]}</span>` +
        `<span class="cc-hist-size">${ui.fmtBytes((r.bytes_in || 0) + (r.bytes_out || 0))}</span>` +
        `<span class="cc-hist-dur">${r.duration != null ? r.duration.toFixed(2) + 's' : '—'}</span>` +
        ui.viaBadge(r.via) + ui.statusPill(r.status) + ui.routeBadge(r.upstream, this._geo) +
        `<span class="cc-hist-chevron">${this._svg('chevron')}</span></div>`;
      const details = ui.el('div', 'cc-hist-details');
      details.innerHTML = `<div class="cc-hist-detail"><span>${t('page.proxyControl.via')}</span><b>${ui.viaBadge(r.via)}</b></div>` +
        `<div class="cc-hist-detail"><span>${t('page.proxyControl.route')}</span><b>${ui.routeBadge(r.upstream, this._geo)}</b></div>` +
        `<div class="cc-hist-detail"><span>${t('page.proxyControl.download')} / ${t('page.proxyControl.upload')}</span><b>↓ ${ui.fmtBytes(r.bytes_out)} · ↑ ${ui.fmtBytes(r.bytes_in)}</b></div>` +
        `<div class="cc-hist-detail"><span>${t('page.proxyControl.duration')}</span><b>${r.duration != null ? r.duration.toFixed(3) + 's' : '—'}</b></div>` +
        `<div class="cc-hist-detail"><span>${t('page.proxyControl.time')}</span><b>${ui.fmtDateTime(r.ts)}</b></div>`;
      details.style.display = 'none';
      row.addEventListener('click', () => {
        const open = details.style.display !== 'none';
        details.style.display = open ? 'none' : '';
        item.classList.toggle('open', !open);
      });
      item.appendChild(row);
      item.appendChild(details);
      list.appendChild(item);
    });
    card.appendChild(list);
    const emptyMsg = ui.el('div', 'pc-empty cc-filter-empty', { text: t('page.proxyControl.filterEmpty') });
    if (visible) emptyMsg.style.display = 'none';
    card.appendChild(emptyMsg);
    return card;
  },

  _sidePanel(s, data) {
    const panel = ui.el('div', 'client-card-side');

    const info = ui.el('div', 'client-card-section');
    info.appendChild(ui.el('div', 'cc-sec-title', { text: t('clientCard.info') }));
    const rows = [
      [t('clientCard.ip'), s.client || '—'],
      [t('clientCard.firstSeen'), s.first_seen ? ui.fmtDateTime(s.first_seen) : '—'],
      [t('clientCard.lastSeen'), s.last_seen ? ui.fmtDateTime(s.last_seen) : '—'],
      [t('page.proxyControl.successRate'), (s.success_rate || 0) + '%'],
      [t('clientCard.kpiAvgTime'), s.avg_duration ? ui.fmtLatency(s.avg_duration) : '—'],
    ];
    const infoList = ui.el('div', 'cc-info-list');
    rows.forEach(([k, v]) => {
      infoList.appendChild(ui.el('div', 'cc-info-row', { html: `<span>${ui.escHtml(k)}</span><b>${ui.escHtml(v)}</b>` }));
    });
    info.appendChild(infoList);
    panel.appendChild(info);

    const routes = data.routes || [];
    const routesCard = ui.el('div', 'client-card-section');
    routesCard.appendChild(ui.el('div', 'cc-sec-title', { text: t('clientCard.routes') }));
    if (!routes.length) {
      routesCard.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noRouteData') }));
    } else {
      const donutWrap = ui.el('div', 'cc-donut-wrap');
      const donutData = routes.slice(0, 4).map(r => ({
        value: r.requests,
        color: { direct: 'var(--success)', proxy: 'var(--info)', pool: '#8a2be2', custom: 'var(--warning)', other: 'var(--text-muted)' }[r.type] || 'var(--text-muted)',
      }));
      if (routes.length > 4) donutData.push({ value: routes.slice(4).reduce((a, r) => a + r.requests, 0), color: 'var(--border)' });
      donutWrap.innerHTML = charts.donutChart(donutData, { size: 108, strokeWidth: 16, centerText: (s.requests || 0).toLocaleString(), centerLabel: t('page.proxyControl.requests') });
      const legend = ui.el('div', 'cc-donut-legend');
      routes.slice(0, 5).forEach(r => {
        const color = { direct: 'var(--success)', proxy: 'var(--info)', pool: '#8a2be2', custom: 'var(--warning)', other: 'var(--text-muted)' }[r.type] || 'var(--text-muted)';
        let upLabel = r.top_upstream || '';
        upLabel = upLabel.replace(/^(proxy|pool|custom):/, '');
        legend.appendChild(ui.el('div', 'cc-donut-row', {
          html: `<span class="cc-donut-dot" style="background:${color}"></span><span class="cc-donut-name">${r.type.toUpperCase()}${upLabel && upLabel !== r.type ? ` <i title="${ui.escHtml(r.top_upstream)}">${ui.escHtml(upLabel.length > 22 ? upLabel.slice(0, 20) + '…' : upLabel)}</i>` : ''}</span><b>${r.pct}%</b>`,
        }));
      });
      donutWrap.appendChild(legend);
      routesCard.appendChild(donutWrap);
    }
    panel.appendChild(routesCard);

    const domains = data.domains || [];
    const domCard = ui.el('div', 'client-card-section');
    domCard.appendChild(ui.el('div', 'cc-sec-title', { text: t('clientCard.topDomains') }));
    if (!domains.length) {
      domCard.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noDomainData') }));
    } else {
      const list = ui.el('div', 'cc-dom-list');
      const maxReq = Math.max(...domains.map(d => d.requests || 0), 1);
      domains.slice(0, 6).forEach(d => {
        const row = ui.el('div', 'cc-dom-row');
        row.innerHTML = ui.hostAvatar(d.domain, 24) +
          `<div class="cc-dom-main"><div class="cc-dom-name">${ui.escHtml(d.domain)}</div>` +
          `<div class="cc-dom-bar"><div style="width:${(d.requests / maxReq * 100).toFixed(0)}%"></div></div></div>` +
          `<b class="cc-dom-pct">${d.pct}%</b>`;
        list.appendChild(row);
      });
      domCard.appendChild(list);
    }
    panel.appendChild(domCard);

    return panel;
  },

  _svg(name) {
    const icons = {
      user: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
      x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
      zap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
      download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
      clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
      route: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="19" r="3"/><path d="M9 19h8.5a3.5 3.5 0 0 0 0-7h-11a3.5 3.5 0 0 1 0-7H15"/><circle cx="18" cy="5" r="3"/></svg>',
      globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
      chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>',
      search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    };
    return icons[name] || '';
  },
};

window.clientCard = clientCard;


/* ==== js/pages/connectivity.js ==== */
router.register('connectivity', (container) => {
  let canaryData = null;
  let history = [];
  let _loading = false;
  let lastAlive = null;
  let lastIp = null;
  let eventLog = [];
  let eventInterval = null;
  let aliveProxies = [];
  let customProxies = [];
  let channelRoute = '';

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
    topRow.style.gridTemplateColumns = '1fr 1fr';
    topRow.style.gap = '10px';
    topRow.appendChild(buildStatusCard());
    topRow.appendChild(buildChannelCard());
    container.appendChild(topRow);

    const directRow = ui.el('div', '');
    directRow.style.display = 'grid';
    directRow.style.gridTemplateColumns = '1fr 2fr';
    directRow.style.gap = '10px';
    directRow.appendChild(buildDirectInfoCard());
    directRow.appendChild(buildHostsCard());
    container.appendChild(directRow);

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

  function buildChannelCard() {
    const card = ui.card(t('page.connectivity.channel'));
    card.id = 'card-channel';

    const desc = ui.el('div', '', { style: 'font-size:11px;color:var(--text-secondary);margin-bottom:8px;line-height:1.5', text: t('page.connectivity.channelDesc') });
    card.appendChild(desc);

    const sel = ui.el('select', '', { id: 'channel-select', style: 'width:100%;padding:6px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);margin-bottom:8px' });
    sel.addEventListener('change', () => {
      const route = sel.value;
      api.channelSelect(route).then(() => {
        app.toast(route ? t('page.connectivity.channelSet', { route }) : t('page.connectivity.channelCleared'));
      }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
    });
    card.appendChild(sel);

    const info = ui.el('div', '', { id: 'channel-info', style: 'font-size:12px;line-height:1.6' });
    card.appendChild(info);
    return card;
  }

  function populateChannelSelect(currentRoute) {
    const sel = document.getElementById('channel-select');
    if (!sel) return;
    const prev = currentRoute !== undefined ? currentRoute : sel.value;
    sel.innerHTML = '';

    sel.appendChild(ui.el('option', '', { value: '', text: t('page.connectivity.channelDirect') }));

    if (customProxies.length) {
      const grp = ui.el('optgroup', '', { label: t('page.connectivity.channelCustom') + ' (' + customProxies.length + ')' });
      customProxies.forEach(cp => {
        const addr = cp.host + ':' + cp.port;
        const st = cp.last_check_status === 'ok' ? '✓' : cp.last_check_status === 'fail' ? '✗' : '?';
        const lat = cp.last_check_latency >= 0 ? cp.last_check_latency + 'ms' : '';
        grp.appendChild(ui.el('option', '', { value: 'custom:' + cp.id, text: st + ' ' + (cp.name || addr) + '  ' + addr + (lat ? ' ' + lat : '') }));
      });
      sel.appendChild(grp);
    }

    const filtered = (aliveProxies || []).slice()
      .filter(p => p.last_status === 'ok' && !p.in_blacklist && (p.supports_connect || (p.protocol || '').startsWith('socks')))
      .sort((a, b) => (b.score || 0) - (a.score || 0))
      .slice(0, 100);

    if (filtered.length) {
      const grp = ui.el('optgroup', '', { label: t('page.connectivity.channelPool') + ' (' + filtered.length + ')' });
      filtered.forEach(p => {
        const flag = ui.flag(p.egress_country_code || p.country_code) || '';
        const lat = p.last_latency ? p.last_latency.toFixed(2) + 's' : '—';
        grp.appendChild(ui.el('option', '', { value: 'proxy:' + p.address, text: flag + ' ' + p.address + '  ' + lat }));
      });
      sel.appendChild(grp);
    }

    sel.value = prev || '';
  }

  function updateChannelCard(channel) {
    const info = document.getElementById('channel-info');
    if (!info) return;
    const route = channel && channel.channel_route ? channel.channel_route : '';
    channelRoute = route;
    const proxy = channel && channel.proxy ? channel.proxy : null;
    if (!proxy) {
      info.innerHTML = '<span class="route-badge route-direct">DIRECT</span>'
        + '<div style="font-size:11px;color:var(--text-secondary);margin-top:6px">' + t('page.connectivity.channelDirect') + '</div>';
      return;
    }
    const proto = (proxy.protocol || 'http').toUpperCase();
    const badgeCls = route.startsWith('custom:') ? 'route-custom' : 'route-proxy';
    const label = route.startsWith('custom:') ? 'CUSTOM' : 'PROXY';
    info.innerHTML = '<span class="route-badge ' + badgeCls + '">' + label + '</span>'
      + '<div style="font-family:monospace;font-size:13px;font-weight:600;color:var(--accent);margin-top:6px">' + ui.escHtml(proxy.host + ':' + proxy.port) + '</div>'
      + '<div style="font-size:11px;color:var(--text-secondary);margin-top:4px">' + proto + (proxy.has_auth ? ' · auth' : '') + '</div>';
  }

  function buildDirectInfoCard() {
    const card = ui.card(t('page.connectivity.directConnection'));
    card.id = 'card-direct-info';

    const viaBadge = ui.el('div', '', { id: 'direct-via-badge', style: 'font-size:10px;margin-bottom:6px;display:none' });
    card.appendChild(viaBadge);

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
    const via = document.getElementById('direct-via-badge');
    if (via) {
      const route = (data.channel && data.channel.channel_route) || '';
      if (route && route !== 'direct') {
        via.style.display = 'block';
        via.innerHTML = '<span class="route-badge route-custom" style="font-size:9px">' + ui.escHtml(t('page.connectivity.viaChannel')) + '</span>';
      } else {
        via.style.display = 'none';
      }
    }
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
    const colorBorder = getComputedStyle(document.documentElement).getPropertyValue('--border').trim() || '#d0d7de';

    const pad = { top: 18, right: 4, bottom: 24, left: 4 };
    const chartW = W - pad.left - pad.right;
    const chartH = H - pad.top - pad.bottom;

    if (!hist || !hist.length) {
      ctx.fillStyle = colorMuted; ctx.font = '12px sans-serif'; ctx.textAlign = 'center';
      ctx.fillText(t('page.connectivity.noDataYet'), W / 2, H / 2); return;
    }

    const now = Date.now();
    const start = now - 24 * 3600 * 1000;
    const bucketMs = 10 * 60 * 1000;
    const bucketCount = 24 * 6; // 144 buckets of 10 min
    const buckets = Array.from({ length: bucketCount }, (_, i) => ({
      start: start + i * bucketMs,
      end: start + (i + 1) * bucketMs,
      up: 0,
      down: 0,
    }));

    let totalUp = 0, totalDown = 0;
    hist.forEach(e => {
      const ts = e.ts * 1000;
      if (ts < start || ts > now) return;
      const idx = Math.min(bucketCount - 1, Math.floor((ts - start) / bucketMs));
      if (buckets[idx]) {
        if (e.alive) { buckets[idx].up++; totalUp++; }
        else { buckets[idx].down++; totalDown++; }
      }
    });

    const barW = chartW / bucketCount;
    for (let i = 0; i < bucketCount; i++) {
      const b = buckets[i];
      const x = pad.left + i * barW;
      if (b.up + b.down === 0) {
        ctx.fillStyle = colorBorder;
        ctx.fillRect(x + 1, pad.top + chartH - 2, barW - 2, 2);
      } else if (b.down > 0) {
        ctx.fillStyle = colorFail;
        ctx.fillRect(x + 1, pad.top, barW - 2, chartH);
      } else {
        ctx.fillStyle = colorOk;
        ctx.fillRect(x + 1, pad.top, barW - 2, chartH);
      }
    }

    // Grid lines
    ctx.strokeStyle = colorBorder;
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    for (let i = 1; i <= 3; i++) {
      const y = pad.top + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(pad.left, y);
      ctx.lineTo(W - pad.right, y);
      ctx.stroke();
    }
    ctx.setLineDash([]);

    // Time labels every 4 hours
    ctx.fillStyle = colorMuted;
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'center';
    for (let h = 0; h <= 24; h += 4) {
      const idx = h * 6;
      if (idx >= bucketCount) continue;
      const x = pad.left + idx * barW + (barW / 2);
      const d = new Date(start + h * 3600 * 1000);
      ctx.fillText(`${d.getHours().toString().padStart(2, '0')}:00`, x, H - 8);
    }

    // Uptime summary
    const total = totalUp + totalDown;
    const uptime = total ? Math.round(totalUp / total * 100) : 0;
    ctx.fillStyle = colorMuted;
    ctx.font = '11px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(t('page.connectivity.uptime24h', { pct: uptime }), pad.left, 12);
    ctx.textAlign = 'right';
    ctx.fillText(t('page.connectivity.okFail', { up: totalUp, down: totalDown }), W - pad.right, 12);
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
        if (data.channel) {
          populateChannelSelect(data.channel.channel_route);
          updateChannelCard(data.channel);
        }
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

  async function loadProxies() {
    try {
      const [alive, custom] = await Promise.all([
        api.proxyAlive().catch(() => []),
        api.customProxies().catch(() => ({ proxies: [] })),
      ]);
      aliveProxies = alive || [];
      customProxies = (custom && custom.proxies) || [];
      populateChannelSelect(channelRoute);
    } catch (e) { /* ignore */ }
  }
  loadProxies();

  const id = setInterval(load, 10000);
  const eventId = setInterval(loadEvents, 10000);
  const idProxy = setInterval(loadProxies, 15000);
  if (window._pageIntervals) {
    window._pageIntervals.push(id, eventId, idProxy);
  } else {
    window._pageIntervals = [id, eventId, idProxy];
  }
});


/* ==== js/pages/custom-proxies.js ==== */
router.register('custom-proxies', (container) => {
  let customProxies = [];
  let editingId = null;
  let _loading = false;

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

    const row = ui.el('div', 'grid grid-2 row-stretch');
    row.appendChild(buildListCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);
  }

  function buildListCard() {
    const card = ui.card(t('page.customProxies.customProxies'));
    card.id = 'card-custom-proxies';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+ New Proxy', id: 'btn-add-proxy', style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });
    card.appendChild(addBtn);

    const tblWrap = ui.el('div', '', { id: 'custom-proxies-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No custom proxies</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.customProxies.proxyEditor'));
    card.id = 'card-proxy-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'proxy-editor-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a proxy to edit or create a new one</div>';
    card.appendChild(body);

    return card;
  }

  function inputStyle() {
    return 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)';
  }

  function labelStyle() {
    return 'font-size:12px;color:var(--text-secondary);margin-bottom:4px';
  }

  function showEditor(p) {
    const body = document.getElementById('proxy-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = p ? p.id : null;

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Name:' }));
    const nameInput = ui.el('input', '', { id: 'pe-name', type: 'text', value: p ? p.name : '', placeholder: 'e.g. Corporate, Tor, Anti-ban', style: inputStyle() });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'ID (auto-generated from name):' }));
    const idInput = ui.el('input', '', { id: 'pe-id', type: 'text', value: p ? p.id : '', placeholder: 'auto-generated from name', style: inputStyle() + (p ? 'opacity:0.6' : '') });
    if (p) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const protoRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    protoRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Protocol:' }));
    const protoSelect = ui.el('select', '', { id: 'pe-protocol', style: inputStyle() });
    ['socks5', 'http', 'https'].forEach(v => {
      const o = ui.el('option', '', { value: v, text: v.toUpperCase() });
      if (p && p.protocol === v) o.selected = true;
      protoSelect.appendChild(o);
    });
    protoRow.appendChild(protoSelect);
    body.appendChild(protoRow);

    const addrRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-bottom:10px' });
    const hostCol = ui.el('div', '', { style: 'flex:3' });
    hostCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Host:' }));
    hostCol.appendChild(ui.el('input', '', { id: 'pe-host', type: 'text', value: p ? p.host : '', placeholder: 'proxy.example.com or 127.0.0.1', style: inputStyle() }));
    addrRow.appendChild(hostCol);
    const portCol = ui.el('div', '', { style: 'flex:1' });
    portCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Port:' }));
    portCol.appendChild(ui.el('input', '', { id: 'pe-port', type: 'number', value: p ? p.port : '', placeholder: '1080', style: inputStyle() }));
    addrRow.appendChild(portCol);
    body.appendChild(addrRow);

    const authRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-bottom:10px' });
    const userCol = ui.el('div', '', { style: 'flex:1' });
    userCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Username:' }));
    userCol.appendChild(ui.el('input', '', { id: 'pe-username', type: 'text', value: p ? p.username : '', placeholder: '(optional)', style: inputStyle() }));
    authRow.appendChild(userCol);
    const passCol = ui.el('div', '', { style: 'flex:1' });
    passCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Password:' }));
    const passWrap = ui.el('div', '', { style: 'display:flex;gap:4px' });
    const passInput = ui.el('input', '', { id: 'pe-password', type: 'password', value: '', placeholder: p && p.password ? '**** (unchanged)' : '(optional)', style: inputStyle() + 'flex:1' });
    passWrap.appendChild(passInput);
    const eyeBtn = ui.el('button', 'btn btn-xs btn-ghost', { style: 'padding:4px 6px;font-size:11px;line-height:1' });
    eyeBtn.textContent = '\u{1F441}';
    let passVisible = false;
    eyeBtn.addEventListener('click', () => {
      passVisible = !passVisible;
      passInput.type = passVisible ? 'text' : 'password';
    });
    passWrap.appendChild(eyeBtn);
    passCol.appendChild(passWrap);
    authRow.appendChild(passCol);
    body.appendChild(authRow);

    const testRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    testRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Test URL (used to verify proxy works):' }));
    testRow.appendChild(ui.el('input', '', { id: 'pe-test-url', type: 'text', value: p ? p.test_url : '', placeholder: 'http://check.torproject.org or http://intranet.corp/', style: inputStyle() }));
    body.appendChild(testRow);

    const hints = ui.el('div', '', { style: 'font-size:10px;color:var(--text-muted);line-height:1.5;margin-bottom:12px;padding:6px 8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
    hints.innerHTML = '<b>Protocol hints:</b><br>SOCKS5 — Tor (127.0.0.1:9050), local SOCKS proxies<br>HTTP — corporate proxies (often with auth)<br>HTTPS — TLS-wrapped proxies (anti-ban services)';
    body.appendChild(hints);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center' });
    const testBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.customProxies.testConnection') });
    testBtn.addEventListener('click', () => {
      const host = document.getElementById('pe-host').value.trim();
      const port = parseInt(document.getElementById('pe-port').value) || 0;
      if (!host || !port) { app.toast('Fill host and port first', 'error'); return; }
      testBtn.disabled = true;
      testBtn.textContent = 'Testing...';
      const testData = {
        host,
        port,
        protocol: document.getElementById('pe-protocol').value,
        username: document.getElementById('pe-username').value.trim(),
        password: document.getElementById('pe-password').value || (p && p.password === '****' ? '' : ''),
        test_url: document.getElementById('pe-test-url').value.trim(),
      };
      api.customProxyTestDirect(testData).then(result => {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
        if (result.status === 'ok') {
          app.toast(`OK — HTTP ${result.http_code} in ${result.latency_ms}ms`);
        } else {
          app.toast(`${result.status}: ${result.error || 'HTTP ' + result.http_code}`, 'error');
        }
      }).catch(e => {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
        app.toast('Error: ' + e.message, 'error');
      });
    });
    btnRow.appendChild(testBtn);

    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: p ? 'Save Changes' : 'Create Proxy' });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('pe-name').value.trim();
      let proxyId = document.getElementById('pe-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!proxyId) proxyId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const protocol = document.getElementById('pe-protocol').value;
      const host = document.getElementById('pe-host').value.trim();
      const port = parseInt(document.getElementById('pe-port').value) || 0;
      const username = document.getElementById('pe-username').value.trim();
      const passwordVal = document.getElementById('pe-password').value;
      const test_url = document.getElementById('pe-test-url').value.trim();

      if (!name) { app.toast('Name is required', 'error'); return; }
      if (!host) { app.toast('Host is required', 'error'); return; }
      if (!port) { app.toast('Port is required', 'error'); return; }

      const existingP = editingId ? customProxies.find(x => x.id === editingId) : null;
      const data = {
        id: proxyId,
        name,
        protocol,
        host,
        port,
        username,
        password: passwordVal || (existingP ? '****' : ''),
        test_url,
        enabled: existingP ? existingP.enabled : true,
      };

      if (editingId) {
        api.customProxyUpdate(editingId, data).then(() => {
          app.toast('Proxy updated');
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.customProxyCreate(data).then(() => {
          app.toast('Proxy created');
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (p) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
      cancelBtn.addEventListener('click', () => {
        editingId = null;
        resetEditor();
      });
      btnRow.appendChild(cancelBtn);
    }

    body.appendChild(btnRow);
  }

  function resetEditor() {
    const body = document.getElementById('proxy-editor-body');
    if (body) body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a proxy to edit or create a new one</div>';
  }

  function statusBadge(p) {
    const s = p.last_check_status;
    if (!s) return '<span style="color:var(--text-muted);font-size:11px">—</span>';
    if (s === 'ok') return '<span style="color:var(--success);font-weight:600;font-size:11px">OK</span>';
    if (s === 'timeout') return '<span style="color:var(--warning);font-weight:600;font-size:11px">Timeout</span>';
    if (s === 'auth_fail') return '<span style="color:var(--danger);font-weight:600;font-size:11px">Auth Fail</span>';
    return '<span style="color:var(--danger);font-weight:600;font-size:11px">Fail</span>';
  }

  function latencyText(p) {
    if (p.last_check_latency < 0) return '<span style="color:var(--text-muted)">—</span>';
    return `<span style="font-size:11px">${p.last_check_latency}ms</span>`;
  }

  function updateListCard(proxies) {
    const wrap = document.getElementById('custom-proxies-tbl');
    if (!wrap) return;
    customProxies = proxies || [];

    if (!proxies || !proxies.length) {
      wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No custom proxies. Add one for specialized routing (corporate, Tor, anti-ban).</div>';
      return;
    }

    const headers = [
      { label: 'Name', width: '120px' },
      { label: 'Protocol', width: '60px', align: 'center' },
      { label: 'Address', width: '130px' },
      { label: 'Test URL', width: '100px' },
      { label: 'Status', width: '60px', align: 'center' },
      { label: 'Latency', width: '50px', align: 'center' },
      { label: 'Enabled', width: '50px', align: 'center' },
      { label: 'Actions', width: '120px', align: 'center' },
    ];

    const rows = proxies.map(p => {
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer';
      nameSpan.textContent = p.name || p.id;
      nameSpan.dataset.proxyId = p.id;
      nameSpan.dataset.action = 'edit';

      const protoSpan = `<span style="font-size:11px;text-transform:uppercase;color:var(--info)">${ui.escHtml(p.protocol)}</span>`;

      const addrSpan = `<span style="font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px">${ui.escHtml(p.host)}:${p.port}</span>`;

      const testUrlSpan = document.createElement('span');
      testUrlSpan.style.cssText = 'font-size:10px;color:var(--text-muted);max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block';
      testUrlSpan.textContent = p.test_url || '—';

      const enabledHtml = p.enabled
        ? '<span style="color:var(--success)">✓</span>'
        : '<span style="color:var(--text-muted)">✗</span>';

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = 'Edit';
      editBtn.dataset.proxyId = p.id;
      editBtn.dataset.action = 'edit';

      const testBtn = document.createElement('button');
      testBtn.className = 'btn btn-xs btn-secondary';
      testBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      testBtn.textContent = 'Test';
      testBtn.dataset.proxyId = p.id;
      testBtn.dataset.action = 'test';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = 'Delete';
      delBtn.dataset.proxyId = p.id;
      delBtn.dataset.action = 'delete';

      return [
        nameSpan.outerHTML,
        protoSpan,
        addrSpan,
        testUrlSpan.outerHTML,
        statusBadge(p),
        latencyText(p),
        enabledHtml,
        editBtn.outerHTML + testBtn.outerHTML + delBtn.outerHTML,
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        const proxyId = el.dataset.proxyId;
        const action = el.dataset.action;
        if (action === 'edit') editProxy(proxyId);
        else if (action === 'test') testProxy(proxyId);
        else if (action === 'delete') deleteProxy(proxyId);
      });
    });
  }

  function editProxy(id) {
    const p = customProxies.find(x => x.id === id);
    if (p) showEditor(p);
    else app.toast('Proxy not found', 'error');
  }

  function testProxy(id) {
    app.toast('Testing proxy...', 'info');
    api.customProxyTest(id).then(result => {
      if (result.status === 'ok') {
        app.toast(`Proxy OK — ${result.http_code} in ${result.latency_ms}ms`);
      } else {
        app.toast(`Proxy ${result.status}: ${result.error || 'HTTP ' + result.http_code}`, 'error');
      }
      load();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function deleteProxy(id) {
    if (!confirm(t('common.confirmDelete', { item: 'proxy' }))) return;
    api.customProxyDelete(id).then(() => {
      app.toast('Proxy deleted');
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      let result = [];
      try { result = await api.customProxies(); } catch (e) { console.error('customProxies', e); }
      const proxies = result.proxies || result || [];
      customProxies = proxies;
      updateListCard(proxies);
    } catch (e) {
      console.error('custom-proxies load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 5000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/domain-lists.js ==== */
router.register('domain-lists', (container) => {
  let domainLists = [];
  let editingId = null;
  let _loading = false;

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

    const row = ui.el('div', 'grid grid-2 row-stretch');
    row.appendChild(buildListsCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);
  }

  function buildListsCard() {
    const card = ui.card(t('page.domainLists.domainLists'));
    card.id = 'card-domain-lists';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+ New List', id: 'btn-add-list', style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });
    card.appendChild(addBtn);

    const tblWrap = ui.el('div', '', { id: 'domain-lists-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No domain lists</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.domainLists.listEditor'));
    card.id = 'card-domain-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'editor-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a list to edit or create a new one</div>';
    card.appendChild(body);

    return card;
  }

  function showEditor(dl) {
    const body = document.getElementById('editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = dl ? dl.id : null;

    const currentSource = dl ? (dl.source || 'manual') : 'manual';

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.listName') }));
    const nameInput = ui.el('input', '', { id: 'editor-name', type: 'text', value: dl ? dl.name : '', placeholder: 'e.g. Social Media, Blocked Sites', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.listId') }));
    const idInput = ui.el('input', '', { id: 'editor-id', type: 'text', value: dl ? dl.id : '', placeholder: 'auto-generated from name', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);' + (dl ? 'opacity:0.6' : '') });
    if (dl) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const sourceRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    sourceRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.source') }));
    const sourceSelect = ui.el('select', '', { id: 'editor-source', style: 'width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    sourceRow.appendChild(sourceSelect);
    body.appendChild(sourceRow);

    const domainsRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    domainsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.domainsOnePerLine') }));
    const domainsArea = ui.el('textarea', '', { id: 'editor-domains', rows: '10', placeholder: 'example.com\n.facebook.com\nexact:twitter.com\n*.google.com', style: 'width:100%;padding:8px 10px;font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);resize:vertical' });
    domainsArea.value = dl && dl.domains ? dl.domains.join('\n') : '';
    domainsRow.appendChild(domainsArea);

    const hints = ui.el('div', '', { style: 'font-size:10px;color:var(--text-muted);line-height:1.5;margin-bottom:12px;padding:6px 8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
    hints.innerHTML = '<b>Patterns:</b><br>example.com — exact + subdomains (*.example.com)<br>.example.com — subdomains only<br>exact:example.com — strict match (no subdomains)<br>*.example.com — same as .example.com';
    domainsRow.appendChild(hints);
    body.appendChild(domainsRow);

    const routeRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    routeRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.routeLabel') }));
    const routeSelect = ui.el('select', '', { id: 'editor-route', style: 'width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    routeRow.appendChild(routeSelect);
    body.appendChild(routeRow);

    function populateRouteSelect(selected) {
      routeSelect.innerHTML = '';
      const opts = [
        { value: 'direct', text: t('route.directNoProxy') },
        { value: 'pool_selected', text: t('route.poolSelected') },
        { value: 'pool', text: t('route.poolBest') },
      ];
      opts.forEach(o => {
        const el = ui.el('option', '', { value: o.value, text: o.text });
        if (o.value === selected) el.selected = true;
        routeSelect.appendChild(el);
      });
      api.customProxies().then(r => {
        const cps = (r && r.proxies) || [];
        const enabled = cps.filter(p => p.enabled);
        if (enabled.length) {
          const grp = ui.el('optgroup', '', { label: t('page.domainLists.customProxies') });
          enabled.forEach(p => {
            const label = p.name + ' (' + (p.protocol || 'socks5').toUpperCase() + ' ' + p.host + ':' + p.port + ')';
            const o = ui.el('option', '', { value: 'custom:' + p.id, text: label });
            if (('custom:' + p.id) === selected) o.selected = true;
            grp.appendChild(o);
          });
          routeSelect.appendChild(grp);
        }
      }).catch(() => {});
      api.proxies({ status: 'ok', limit: 200 }).then(r => {
        const proxies = (r && r.proxies) || r || [];
        const alive = Array.isArray(proxies) ? proxies.filter(p => p.last_status === 'ok' || p.alive) : [];
        if (alive.length) {
          const grp = ui.el('optgroup', '', { label: t('page.domainLists.workingProxies') });
          alive.slice(0, 200).forEach(p => {
            const addr = p.address || (p.host + ':' + p.port);
            const label = addr + ' (' + (p.protocol || '').toUpperCase() + ' ' + (p.country || '?') + ')';
            const o = ui.el('option', '', { value: 'proxy:' + addr, text: label });
            if (('proxy:' + addr) === selected) o.selected = true;
            grp.appendChild(o);
          });
          routeSelect.appendChild(grp);
        }
      }).catch(() => {});
    }

    populateRouteSelect(dl ? (dl.route || '') : 'pool');

    const searchRow = ui.el('div', '', { id: 'search-row', style: 'margin-bottom:10px;display:none' });
    const searchBox = ui.el('input', '', { id: 'bl-search', type: 'text', placeholder: t('page.domainLists.searchPlaceholder'), style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    searchRow.appendChild(searchBox);
    const searchInfo = ui.el('div', '', { id: 'bl-info', style: 'font-size:11px;color:var(--text-secondary);margin-top:4px' });
    searchRow.appendChild(searchInfo);
    body.appendChild(searchRow);

    let allDomains = [];
    let showCount = 200;
    let filteredCount = 0;

    function applySearch() {
      const q = (document.getElementById('bl-search').value || '').trim().toLowerCase();
      if (!q) {
        domainsArea.value = allDomains.join('\n');
        filteredCount = allDomains.length;
      } else {
        const filtered = allDomains.filter(d => d.includes(q));
        filteredCount = filtered.length;
        domainsArea.value = filtered.slice(0, 5000).join('\n');
      }
      const info = document.getElementById('bl-info');
      if (info) {
        let txt = `${filteredCount} / ${allDomains.length}`;
        if (q && filteredCount > 5000) txt += ' (showing first 5000)';
        info.textContent = txt;
      }
    }

    function setManualMode() {
      domainsArea.disabled = false;
      domainsArea.style.opacity = '1';
      searchRow.style.display = 'none';
      hints.style.display = '';
    }

    function setBlocklistMode(blId) {
      domainsArea.disabled = true;
      domainsArea.style.opacity = '0.6';
      hints.style.display = 'none';
      searchRow.style.display = '';
      domainsArea.value = 'Loading...';
      api.domainListGet(blId).then(d => {
        allDomains = (d && d.domains) || [];
        showCount = 200;
        applySearch();
      }).catch(e => {
        domainsArea.value = '';
        app.toast(t('common.error', { message: e.message }), 'error');
      });
    }

    let blocklistSources = [];
    sourceSelect.appendChild(ui.el('option', '', { value: 'manual', text: t('page.domainLists.manual') }));
    api.blocklists().then(r => {
      const sources = (r && r.sources) || [];
      blocklistSources = sources.filter(s => s.list_type === 'domain');
      blocklistSources.forEach(s => {
        const opt = ui.el('option', '', { value: s.id, text: `${s.name} (${s.entry_count || 0})` });
        sourceSelect.appendChild(opt);
      });
      if (currentSource === 'blocklist' && dl) {
        sourceSelect.value = dl.id;
        setBlocklistMode(dl.id);
      } else {
        sourceSelect.value = 'manual';
        setManualMode();
      }
    }).catch(() => {
      sourceSelect.value = 'manual';
      setManualMode();
    });

    if (currentSource === 'blocklist' && dl) {
      allDomains = dl.domains || [];
      sourceSelect.value = dl.id;
      setBlocklistMode(dl.id);
    } else {
      sourceSelect.value = 'manual';
      setManualMode();
    }

    sourceSelect.addEventListener('change', () => {
      const val = sourceSelect.value;
      if (val === 'manual') {
        setManualMode();
      } else {
        setBlocklistMode(val);
      }
    });

    searchBox.addEventListener('input', () => { applySearch(); });

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: dl ? t('page.domainLists.saveChanges') : t('page.domainLists.createList') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('editor-name').value.trim();
      let listId = document.getElementById('editor-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!listId) listId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const domainsText = document.getElementById('editor-domains').value;
      const domains = domainsText.split('\n').map(d => d.trim()).filter(d => d);

      if (!name) { app.toast('Name is required', 'error'); return; }

      const sourceVal = sourceSelect.value;
      const existingDl = editingId ? domainLists.find(l => l.id === editingId) : null;
      const data = {
        id: listId,
        name,
        domains,
        source: sourceVal === 'manual' ? 'manual' : 'blocklist',
        route: document.getElementById('editor-route').value || 'pool',
        enabled: existingDl ? existingDl.enabled : true,
      };

      if (editingId) {
        api.domainListUpdate(editingId, data).then(() => {
          app.toast(t('page.domainLists.listUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      } else {
        api.domainListCreate(data).then(() => {
          app.toast(t('page.domainLists.listCreated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (dl) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
      cancelBtn.addEventListener('click', () => {
        editingId = null;
        resetEditor();
      });
      btnRow.appendChild(cancelBtn);
    }

    body.appendChild(btnRow);
  }

  function resetEditor() {
    const body = document.getElementById('editor-body');
    if (body) body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a list to edit or create a new one</div>';
  }

  function updateListsCard(lists) {
    const wrap = document.getElementById('domain-lists-tbl');
    if (!wrap) return;
    domainLists = lists || [];

    if (!lists || !lists.length) {
      wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No domain lists. Create one to group domains for routing.</div>';
      return;
    }

    const headers = [
      { label: 'Name', width: '140px' },
      { label: 'Domains', width: '60px', align: 'center' },
      { label: 'Source', width: '60px', align: 'center' },
      { label: 'Route', width: '80px' },
      { label: 'Actions', width: '100px', align: 'center' },
    ];

    const sourceLabel = (source) => {
      if (source === 'blocklist') return '<span style="color:var(--success);font-size:11px">Blocklist</span>';
      if (source === 'url') return '<span style="color:var(--info);font-size:11px">URL</span>';
      return '<span style="color:var(--text-muted);font-size:11px">Manual</span>';
    };

    const rows = lists.map(l => {
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer';
      nameSpan.textContent = l.name || l.id;
      nameSpan.dataset.listId = l.id;
      nameSpan.dataset.action = 'edit';

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = 'Edit';
      editBtn.dataset.listId = l.id;
      editBtn.dataset.action = 'edit';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = 'Delete';
      delBtn.dataset.listId = l.id;
      delBtn.dataset.action = 'delete';

      return [
        nameSpan.outerHTML,
        (l.domain_count || 0),
        sourceLabel(l.source || 'manual'),
        ui.formatRouteLabel(l.route),
        editBtn.outerHTML + delBtn.outerHTML,
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        const listId = el.dataset.listId;
        const action = el.dataset.action;
        if (action === 'edit') editList(listId);
        else if (action === 'delete') deleteList(listId);
      });
    });
  }

  function editList(id) {
    api.domainListGet(id).then(dl => {
      if (dl) showEditor(dl);
      else app.toast('List not found', 'error');
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function deleteList(id) {
    if (!confirm(t('common.confirmDelete', { item: 'list' }))) return;
    api.domainListDelete(id).then(() => {
      app.toast('List deleted');
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      let result = [];
      try { result = await api.domainLists(); } catch (e) { console.error('domainLists', e); }
      const lists = result.lists || result || [];
      domainLists = lists;
      updateListsCard(lists);
    } catch (e) {
      console.error('domain-lists load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/downloads.js ==== */
router.register('downloads', (container) => {
  let counts = {};
  let backupGroups = [];

  async function loadCounts() {
    try { counts = await api.downloadCounts(); } catch (e) { counts = {}; }
    renderDownloads();
  }

  async function loadBackupGroups() {
    try {
      const data = await api.backupGroups();
      backupGroups = data.groups || [];
    } catch (e) { backupGroups = []; }
    renderBackup();
  }

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';
    container.style.overflow = 'hidden';

    const card = ui.card(t('page.downloads.downloads'));
    card.id = 'downloads-card';
    container.appendChild(card);

    const files = [
      { name: 'working.txt', desc: t('page.downloads.workingTxt'), icon: '📄' },
      { name: 'blacklist.txt', desc: t('page.downloads.blacklistTxt'), icon: '🚫' },
      { name: 'ip_blacklist.txt', desc: t('page.downloads.ipBlacklistTxt'), icon: '🛡️' },
      { name: 'ratings.json', desc: t('page.downloads.ratingsJson'), icon: '📊' },
      { name: 'config.yaml', desc: t('page.downloads.configYaml'), icon: '⚙️' },
    ];

    const grid = ui.el('div', 'grid grid-2');
    grid.id = 'downloads-grid';
    files.forEach(f => {
      const item = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;padding:16px;background:var(--surface-raised);border-radius:var(--radius-xs);border:1px solid var(--border)' });
      item.appendChild(ui.el('div', '', { style: 'font-size:24px', text: f.icon }));
      const info = ui.el('div', '', { style: 'flex:1;min-width:0' });
      info.appendChild(ui.el('div', '', { style: 'font-weight:600;font-size:13px;margin-bottom:2px', text: f.name }));
      info.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: f.desc }));
      item.appendChild(info);
      const countSpan = ui.el('span', 'badge', { text: '…', style: 'font-size:11px;min-width:32px;text-align:center' });
      countSpan.dataset.file = f.name;
      item.appendChild(countSpan);
      const dl = ui.el('a', 'btn btn-sm btn-primary', { text: t('page.downloads.download'), href: `/api/download/${f.name}`, download: f.name });
      item.appendChild(dl);
      grid.appendChild(item);
    });
    card.appendChild(grid);

    const importCard = ui.card(t('page.downloads.importProxies'));
    importCard.id = 'import-card';
    container.appendChild(importCard);

    const impWrap = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:8px' });
    impWrap.id = 'import-wrap';
    importCard.appendChild(impWrap);

    const impDesc = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: t('page.overview.importDesc') });
    impWrap.appendChild(impDesc);

    const favLabel = ui.el('label', '', { style: 'display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer' });
    const favCb = ui.el('input', '', { type: 'checkbox', checked: true });
    favLabel.appendChild(favCb);
    favLabel.appendChild(ui.el('span', '', { text: t('page.overview.importAsFavorite') }));
    impWrap.appendChild(favLabel);

    const impBtnRow = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center' });
    const impBtn = ui.el('button', 'btn btn-primary', { text: t('page.overview.chooseFile') });
    const impInput = ui.el('input', '', { type: 'file', accept: '.txt', style: 'display:none' });
    impBtnRow.appendChild(impBtn);
    impBtnRow.appendChild(impInput);
    impWrap.appendChild(impBtnRow);

    const impStatus = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);min-height:16px' });
    impWrap.appendChild(impStatus);

    impBtn.addEventListener('click', () => impInput.click());
    impInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      impBtn.disabled = true;
      impStatus.textContent = '...';
      try {
        const text = await file.text();
        const lines = text.split('\n');
        const result = await api.importProxies({ proxies: lines, favorite: favCb.checked });
        const msg = (result.added || 0) + (result.favorited != null ? ' ⭐' + result.favorited : '');
        impStatus.textContent = msg;
      } catch (err) {
        impStatus.textContent = String(err.message || err);
      } finally {
        impBtn.disabled = false;
        impInput.value = '';
        loadCounts();
      }
    });

    const backupCard = ui.card(t('page.downloads.backupRestore'));
    backupCard.id = 'backup-card';
    backupCard.style.display = 'flex';
    backupCard.style.flexDirection = 'column';
    backupCard.style.flex = '1';
    backupCard.style.minHeight = '0';
    container.appendChild(backupCard);

    const brWrap = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:8px;flex:1;min-height:0' });
    brWrap.id = 'backup-wrap';
    backupCard.appendChild(brWrap);
  }

  function renderDownloads() {
    document.querySelectorAll('[data-file]').forEach(el => {
      const n = counts[el.dataset.file];
      el.textContent = n !== undefined ? n : '…';
    });
  }

  function renderBackup() {
    const wrap = document.getElementById('backup-wrap');
    if (!wrap) return;
    wrap.innerHTML = '';

    const allBar = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:11px;color:var(--text-secondary)' });
    const allCb = ui.el('input', '', { type: 'checkbox', id: 'bk-all', checked: true });
    allBar.appendChild(allCb);
    allBar.appendChild(ui.el('label', '', { text: t('page.downloads.selectAll'), for: 'bk-all', style: 'cursor:pointer' }));
    wrap.appendChild(allBar);

    const list = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:2px;flex:1;min-height:0;overflow-y:auto;margin-bottom:8px' });
    backupGroups.forEach(g => {
      const row = ui.el('label', '', { style: 'display:flex;align-items:center;gap:8px;padding:4px 6px;cursor:pointer;font-size:12px' });
      const cb = ui.el('input', 'bk-grp', { type: 'checkbox', value: g.key, checked: true });
      row.appendChild(cb);
      row.appendChild(ui.el('span', '', { text: g.label, style: 'flex:1;min-width:0' }));
      row.appendChild(ui.el('span', 'badge', { text: String(g.total), style: 'font-size:10px' }));
      list.appendChild(row);
    });
    wrap.appendChild(list);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center' });
    const bkBtn = ui.el('button', 'btn btn-primary', { text: t('page.downloads.createBackup') });
    const fileInput = ui.el('input', '', { type: 'file', accept: '.json', style: 'display:none' });
    const rsBtn = ui.el('button', 'btn btn-secondary', { text: t('page.downloads.restoreBackup') });
    btnRow.appendChild(bkBtn);
    btnRow.appendChild(rsBtn);
    btnRow.appendChild(fileInput);
    wrap.appendChild(btnRow);

    const statusEl = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);min-height:16px;margin-top:6px' });
    wrap.appendChild(statusEl);

    allCb.addEventListener('change', () => {
      document.querySelectorAll('.bk-grp').forEach(c => { c.checked = allCb.checked; });
    });

    bkBtn.addEventListener('click', async () => {
      const selected = [...document.querySelectorAll('.bk-grp:checked')].map(c => c.value);
      if (!selected.length) { statusEl.textContent = t('page.downloads.selectAtLeastOne'); return; }
      statusEl.textContent = t('page.downloads.creating');
      bkBtn.disabled = true;
      try {
        const blob = await api.createBackup(selected);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `huntproxy_backup_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'')}.json`;
        a.click();
        URL.revokeObjectURL(url);
        statusEl.textContent = t('page.downloads.backupCreated');
      } catch (e) {
        statusEl.textContent = String(e.message || e);
      } finally {
        bkBtn.disabled = false;
      }
    });

    rsBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const selected = [...document.querySelectorAll('.bk-grp:checked')].map(c => c.value);
      if (!selected.length) { statusEl.textContent = t('page.downloads.selectAtLeastOne'); return; }
      statusEl.textContent = t('page.downloads.restoring');
      rsBtn.disabled = true;
      try {
        const text = await file.text();
        const result = await api.restoreBackup(selected, text);
        if (result.ok) {
          const counts = Object.entries(result.restored).map(([k,v]) => `${k}: ${v}`).join(', ');
          statusEl.textContent = t('page.downloads.restoreDone') + ' (' + counts + ')';
          loadBackupGroups();
        } else {
          statusEl.textContent = result.error || t('page.downloads.restoreFailed');
        }
      } catch (e) {
        statusEl.textContent = String(e.message || e);
      } finally {
        rsBtn.disabled = false;
        fileInput.value = '';
      }
    });
  }

  build();
  loadCounts();
  loadBackupGroups();
});


/* ==== js/pages/favorites.js ==== */
router.register('favorites', (container) => {
  let state = {
    favorites: [],
    search: '',
    sortKey: 'score',
    sortDir: -1,
  };

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });
    const search = ui.el('input', '', { type: 'text', placeholder: t('page.favorites.searchPlaceholder'), value: state.search, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:200px' });
    search.addEventListener('input', (e) => {
      state.search = e.target.value.toLowerCase();
      renderTable();
    });
    filterBar.appendChild(search);

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const count = ui.el('div', '', { id: 'fav-count', style: 'font-size:12px;color:var(--text-secondary)' });
    filterBar.appendChild(count);

    const refreshBtn = ui.el('button', 'btn btn-secondary', { text: t('common.refresh') });
    refreshBtn.addEventListener('click', () => load());
    filterBar.appendChild(refreshBtn);

    container.appendChild(filterBar);

    const card = ui.card(t('page.favorites.title'));
    card.id = 'favorites-table-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    container.appendChild(card);
  }

  build();

  async function load() {
    try {
      const data = await api.favorites();
      state.favorites = data || [];
      renderTable();
    } catch (e) {
      console.error('favorites load', e);
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  function setSort(key) {
    if (state.sortKey === key) state.sortDir *= -1;
    else { state.sortKey = key; state.sortDir = 1; }
    renderTable();
  }

  function renderTable() {
    const card = document.getElementById('favorites-table-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.favorites.title') }));
    card.appendChild(header);

    let rows = state.favorites;
    if (state.search) {
      rows = rows.filter(p =>
        (p.address || '').toLowerCase().includes(state.search) ||
        (p.country || '').toLowerCase().includes(state.search)
      );
    }

    const count = document.getElementById('fav-count');
    if (count) count.textContent = t('page.favorites.count', {count: rows.length});

    rows = rows.slice().sort((a, b) => ui.sortValue(a, b, state.sortKey, state.sortDir));

    if (!rows.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.favorites.empty') }));
      return;
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.sortKey, state.sortDir) : ''), width, align, sortKey: key, onSort: key ? () => setSort(key) : undefined });
    const headers = [
      h('Proxy', 'address', null, 'left'),
      h('Country', 'country', '110px', 'left'),
      h('Proto', null, '50px', 'center'),
      h('Lat', 'last_latency', '50px', 'right'),
      h('Speed', 'speed_avg', '55px', 'right'),
      h('Succ', 'success_rate', '40px', 'right'),
      h('Score', 'score', '40px', 'right'),
      h('Status', null, '50px', 'center'),
      h('Last', 'last_check', '55px', 'right'),
      h('', null, '28px', 'center'),
    ];
    const bodyRows = rows.map(p => {
      const statusColor = p.in_blacklist ? 'var(--danger)' : p.last_status === 'ok' ? 'var(--success)' : 'var(--danger)';
      const statusText = p.in_blacklist ? 'BL' : p.last_status === 'ok' ? 'OK' : 'FAIL';
      const proto = (p.protocol || 'http').toUpperCase();
      const lat = p.last_latency != null ? (p.last_latency < 1 ? (p.last_latency * 1000).toFixed(0) + 'ms' : p.last_latency.toFixed(2) + 's') : '—';
      const speed = p.speed_avg ? p.speed_avg.toFixed(0) + 'KB/s' : '—';
      const succ = p.success_rate != null ? (p.success_rate * 100).toFixed(0) + '%' : '—';
      const score = Math.round(p.score || 0);
      const flag = ui.flag(p.country_code);
      return [
        `<span class="proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="font-size:12px;font-family:monospace;color:var(--text-primary);cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${ui.escHtml(p.address)}</span>`,
        `<span style="font-size:12px">${flag} ${ui.escHtml(p.country || '—')}</span>`,
        `<span style="font-size:11px;color:var(--text-muted)">${proto}</span>`,
        `<span style="font-size:11px">${lat}</span>`,
        `<span style="font-size:11px">${speed}</span>`,
        `<span style="font-size:11px">${succ}</span>`,
        `<span style="font-size:11px;font-weight:600">${score}</span>`,
        `<span style="color:${statusColor};font-weight:600;font-size:11px">${statusText}</span>`,
        `<span style="font-size:11px;color:var(--text-muted)">${ui.ago(p.last_check)}</span>`,
        `<button class="btn btn-xs btn-secondary" data-fav-remove="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px;color:var(--warning)" title="${t('proxyCard.removedFromFavorites')}"><svg width="12" height="12"><use href="#icon-star"/></svg></button>`,
      ];
    });
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, bodyRows));
    card.appendChild(tblWrap);

    tblWrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
    tblWrap.querySelectorAll('[data-fav-remove]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.favRemove;
        api.favRemove(addr).then(() => {
          app.toast(t('proxyCard.removedFromFavorites'));
          load();
        }).catch(err => app.toast(t('common.error', {message: err.message}), 'error'));
      });
    });
  }

  load();
  const id = setInterval(load, 10000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/hunt.js ==== */
router.register('hunt', (container) => {
  const els = {};
  let topSortKey = 'score', topSortDir = -1;
  let blSortKey = 'address', blSortDir = 1;

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    // Top: Pipeline stepper strip (full width, thin)
    container.appendChild(buildPipelineStrip());

    // Main: Left conveyor + Right panels
    const main = ui.el('div', '', { style: 'display:flex;gap:10px;flex:1;min-height:0' });

    const leftCol = ui.el('div', '', { style: 'flex:0 0 45%;display:flex;flex-direction:column;min-height:0' });
    leftCol.appendChild(buildConveyorCard());
    main.appendChild(leftCol);

    const rightCol = ui.el('div', '', { style: 'flex:1;display:flex;flex-direction:column;gap:10px;min-height:0;min-width:0' });
    const row1 = ui.el('div', 'grid grid-2 row-stretch');
    row1.appendChild(buildProgressCard());
    row1.appendChild(buildResultsCard());
    rightCol.appendChild(row1);

    const row2 = ui.el('div', 'grid grid-2 row-stretch');
    row2.appendChild(buildTopProxiesCard());
    row2.appendChild(buildLogCard());
    rightCol.appendChild(row2);

    main.appendChild(rightCol);
    container.appendChild(main);
  }

  const PIPELINE_PHASES = ['download', 'blacklist', 'validate', 'health'];
  const PIPELINE_PHASE_I18N = { download: 'page.hunt.phase_download', blacklist: 'page.hunt.phase_blacklist', validate: 'page.hunt.phase_validate', health: 'page.hunt.phase_health' };
  const PIPELINE_PHASE_ICON = { download: '⬇', blacklist: '🛡', validate: '🔍', health: '❤' };

  function buildPipelineStrip() {
    const card = ui.el('div', 'card pipeline-strip');
    card.id = 'pipeline-strip';
    card.style.padding = '6px 10px';
    card.style.flex = '0 0 auto';

    const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0' });
    PIPELINE_PHASES.forEach((ph, i) => {
      const step = ui.el('div', 'pipe-step');
      step.id = 'pipe-step-' + ph;
      const dot = ui.el('div', 'pipe-step-dot', { text: PIPELINE_PHASE_ICON[ph] });
      step.appendChild(dot);
      const body = ui.el('div', 'pipe-step-body');
      body.appendChild(ui.el('div', 'pipe-step-title', { id: 'pipe-title-' + ph, text: t(PIPELINE_PHASE_I18N[ph]) }));
      body.appendChild(ui.el('div', 'pipe-step-detail', { id: 'pipe-detail-' + ph, text: '—' }));
      step.appendChild(body);
      row.appendChild(step);
      if (i < PIPELINE_PHASES.length - 1) {
        row.appendChild(ui.el('div', 'pipe-step-arrow'));
      }
    });
    card.appendChild(row);
    return card;
  }

  const CONVEYOR_PHASES = ['queued', 'connect', 'speed_wait', 'speed'];
  const CONVEYOR_PHASE_I18N = { queued: 'page.hunt.conv_queued', connect: 'page.hunt.conv_connect', speed_wait: 'page.hunt.conv_speed_wait', speed: 'page.hunt.conv_speed' };
  const CONVEYOR_PHASE_ICON = { queued: '⏳', connect: '🔗', speed_wait: '⏱', speed: '⚡' };

  function buildConveyorCard() {
    const card = ui.el('div', 'card conveyor-board');
    card.id = 'conveyor-card';
    card.style.padding = '8px 10px';
    card.style.flex = '1';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.minHeight = '0';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.conveyor') }));
    const liveTag = ui.el('span', 'pipeline-live', { id: 'pipeline-live', text: '—' });
    header.appendChild(liveTag);
    card.appendChild(header);

    const lanes = ui.el('div', 'conveyor-vlanes');
    lanes.id = 'conveyor-lanes';

    CONVEYOR_PHASES.forEach(ph => {
      const lane = ui.el('div', 'conveyor-vlane');
      lane.id = 'conveyor-vlane-' + ph;
      const label = ui.el('div', 'conveyor-vlane-header', {}, [
        ui.el('span', 'conveyor-vlane-icon', { text: CONVEYOR_PHASE_ICON[ph] }),
        ui.el('span', '', { text: t(CONVEYOR_PHASE_I18N[ph]) }),
        ui.el('span', 'conveyor-vlane-count', { id: 'conveyor-vcount-' + ph, text: '0' }),
      ]);
      lane.appendChild(label);
      const items = ui.el('div', 'conveyor-vlane-items', { id: 'conveyor-vitems-' + ph });
      lane.appendChild(items);
      lanes.appendChild(lane);
    });

    card.appendChild(lanes);
    return card;
  }

  function buildControlCard() {
    const card = ui.el('div', 'card');
    card.id = 'control-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.huntControl'), style: 'margin-bottom:8px' }));

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap' });
    const startBtn = ui.el('button', 'btn btn-primary', { text: t('page.hunt.startHunt') });
    startBtn.id = 'btn-hunt-start';
    startBtn.addEventListener('click', () => api.huntStart().then(r => app.toast(r.ok ? t('page.hunt.huntStarted') : r.error)));
    btnRow.appendChild(startBtn);

    const pauseBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.pause') });
    pauseBtn.id = 'btn-hunt-pause';
    pauseBtn.addEventListener('click', () => api.huntPause().then(r => app.toast(r.ok ? t('page.hunt.pausedMsg') : r.error)));
    btnRow.appendChild(pauseBtn);

    const resumeBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.resume') });
    resumeBtn.id = 'btn-hunt-resume';
    resumeBtn.addEventListener('click', () => api.huntResume().then(r => app.toast(r.ok ? t('page.hunt.resumed') : r.error)));
    btnRow.appendChild(resumeBtn);

    const stopBtn = ui.el('button', 'btn btn-danger', { text: t('page.hunt.stop') });
    stopBtn.id = 'btn-hunt-stop';
    stopBtn.addEventListener('click', () => api.huntStop().then(() => app.toast(t('page.hunt.huntStopped'))));
    btnRow.appendChild(stopBtn);
    card.appendChild(btnRow);

    const sel = ui.el('select', '', { id: 'country-filter', style: 'width:100%;padding:4px 6px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    ['ALL','US','RU','GB','DE','FR','NL','CA','JP','BR','IN','UA','PL'].forEach(c => {
      const opt = ui.el('option', '', { value: c === 'ALL' ? '' : c, text: c });
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => api.setCountry(sel.value).then(() => app.toast('Country: ' + (sel.value || 'ALL'))));
    card.appendChild(sel);
    return card;
  }

  function buildProgressCard() {
    const card = ui.el('div', 'card');
    card.id = 'progress-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.poolProgress') }));
    const btnRow = ui.el('div', '', { style: 'display:flex;gap:4px;flex-wrap:wrap' });
    const startBtn = ui.el('button', 'btn btn-primary', { text: t('page.hunt.startHunt') });
    startBtn.id = 'btn-hunt-start';
    startBtn.style.fontSize = '10px';
    startBtn.style.padding = '2px 8px';
    startBtn.addEventListener('click', () => api.huntStart().then(r => app.toast(r.ok ? t('page.hunt.huntStarted') : r.error)));
    btnRow.appendChild(startBtn);

    const pauseBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.pause') });
    pauseBtn.id = 'btn-hunt-pause';
    pauseBtn.style.fontSize = '10px';
    pauseBtn.style.padding = '2px 8px';
    pauseBtn.addEventListener('click', () => api.huntPause().then(r => app.toast(r.ok ? t('page.hunt.pausedMsg') : r.error)));
    btnRow.appendChild(pauseBtn);

    const resumeBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.resume') });
    resumeBtn.id = 'btn-hunt-resume';
    resumeBtn.style.fontSize = '10px';
    resumeBtn.style.padding = '2px 8px';
    resumeBtn.addEventListener('click', () => api.huntResume().then(r => app.toast(r.ok ? t('page.hunt.resumed') : r.error)));
    btnRow.appendChild(resumeBtn);

    const stopBtn = ui.el('button', 'btn btn-danger', { text: t('page.hunt.stop') });
    stopBtn.id = 'btn-hunt-stop';
    stopBtn.style.fontSize = '10px';
    stopBtn.style.padding = '2px 8px';
    stopBtn.addEventListener('click', () => api.huntStop().then(() => app.toast(t('page.hunt.huntStopped'))));
    btnRow.appendChild(stopBtn);

    const skipBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.skip') });
    skipBtn.id = 'btn-hunt-skip';
    skipBtn.style.fontSize = '10px';
    skipBtn.style.padding = '2px 8px';
    skipBtn.style.display = 'none';
    skipBtn.addEventListener('click', () => api.huntSkip().then(r => app.toast(r.ok ? t('page.hunt.skipped') : r.error)).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
    btnRow.appendChild(skipBtn);

    header.appendChild(btnRow);
    card.appendChild(header);

    const top = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:6px' });
    top.appendChild(ui.el('div', '', { id: 'phase-badge', style: 'display:inline-flex;align-items:center;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;text-transform:uppercase;background:var(--surface-raised);color:var(--text-secondary)', text: t('page.hunt.idle') }));
    top.appendChild(ui.el('div', '', { id: 'last-event', style: 'font-size:11px;color:var(--text-secondary);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: t('common.ready') }));
    top.appendChild(ui.el('span', '', { id: 'live-dot', style: 'width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0' }));
    card.appendChild(top);

    card.appendChild(ui.el('div', 'progress-bar', { id: 'progress-bar', style: 'margin-bottom:4px' }, [ui.el('div', '', { id: 'progress-fill', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease' })]));

    card.appendChild(ui.el('div', '', {
      id: 'progress-text',
      style: 'display:flex;justify-content:space-between;font-size:11px;color:var(--text-secondary)',
      html: `<span>${t('page.hunt.checked')} <b id="p-checked">0</b> / <b id="p-total">0</b></span><span>${t('page.hunt.newWorking')} <b id="p-new-working" style="color:var(--info)">0</b></span><span>${t('page.hunt.confirmedWorking')} <b id="p-confirmed-working" style="color:var(--success)">0</b></span>`
    }));

    const lp = ui.el('div', '', { id: 'last-proxy-row', style: 'margin-top:4px;font-size:11px;color:var(--text-secondary);display:flex;align-items:center;gap:4px;visibility:hidden' });
    lp.innerHTML = '<span id="last-flag"></span><span id="last-addr" style="font-family:monospace;color:var(--accent)"></span><span id="last-country-name"></span>';
    card.appendChild(lp);

    const sel = ui.el('select', '', { id: 'country-filter', style: 'width:100%;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);margin-top:6px' });
    ['ALL','US','RU','GB','DE','FR','NL','CA','JP','BR','IN','UA','PL'].forEach(c => {
      const opt = ui.el('option', '', { value: c === 'ALL' ? '' : c, text: c });
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => api.setCountry(sel.value).then(() => app.toast('Country: ' + (sel.value || 'ALL'))));
    card.appendChild(sel);

    return card;
  }

  function buildResultsCard() {
    const card = ui.el('div', 'card conveyor-board');
    card.id = 'results-card';
    card.style.padding = '8px 10px';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.results') }));
    const resultsCount = ui.el('span', 'pipeline-live', { id: 'results-count', text: '0' });
    header.appendChild(resultsCount);
    card.appendChild(header);

    const lanes = ui.el('div', 'conveyor-vlanes');

    // Alive lane
    const aliveLane = ui.el('div', 'conveyor-vlane conveyor-vlane-alive');
    const aliveHeader = ui.el('div', 'conveyor-vlane-header', {}, [
      ui.el('span', 'conveyor-vlane-icon', { text: '✓' }),
      ui.el('span', '', { text: t('page.hunt.conv_alive') }),
      ui.el('span', 'conveyor-vlane-count', { id: 'results-alive-count', text: '0' }),
    ]);
    aliveLane.appendChild(aliveHeader);
    const aliveItems = ui.el('div', 'conveyor-vlane-items', { id: 'results-alive-items' });
    aliveLane.appendChild(aliveItems);
    lanes.appendChild(aliveLane);

    // Dead lane
    const deadLane = ui.el('div', 'conveyor-vlane conveyor-vlane-dead');
    const deadHeader = ui.el('div', 'conveyor-vlane-header', {}, [
      ui.el('span', 'conveyor-vlane-icon', { text: '✗' }),
      ui.el('span', '', { text: t('page.hunt.conv_dead') }),
      ui.el('span', 'conveyor-vlane-count', { id: 'results-dead-count', text: '0' }),
    ]);
    deadLane.appendChild(deadHeader);
    const deadItems = ui.el('div', 'conveyor-vlane-items', { id: 'results-dead-items' });
    deadLane.appendChild(deadItems);
    lanes.appendChild(deadLane);

    card.appendChild(lanes);
    return card;
  }

  function buildTopProxiesCard() {
    const card = ui.el('div', 'card');
    card.id = 'top-proxies-card';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.topRatedAlive') }));
    const count = ui.el('div', '', { id: 'top-count', style: 'font-size:11px;color:var(--text-secondary)', text: '0' });
    header.appendChild(count);
    card.appendChild(header);

    const wrap = ui.el('div', 'table-wrap');
    wrap.id = 'top-tbl-wrap';
    card.appendChild(wrap);
    return card;
  }

  function buildLogCard() {
    const card = ui.el('div', 'card');
    card.id = 'log-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.huntLog'), style: 'margin-bottom:8px' }));
    const log = ui.el('div', '', { id: 'hunt-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow-y:auto;flex:1;min-height:0;color:var(--text-primary)' });
    card.appendChild(log);
    return card;
  }

  build();

  // --- Updaters ---

  const PHASE_MAP = { 'downloading': 'download', 'blacklists': 'blacklist', 'validating': 'validate', 'health': 'health', 'done': null, 'idle': null, 'paused': null };

  function updatePipelineStrip(s) {
    const p = s.progress || {};
    const phase = s.phase;
    const phaseKey = PHASE_MAP[phase] ?? null;
    const parallel = (s.settings && s.settings.parallel) || 30;

    const setStep = (id, cls) => { const el = document.getElementById('pipe-step-' + id); if (el) el.className = 'pipe-step' + (cls ? ' ' + cls : ''); };
    const setDetail = (id, txt) => { const el = document.getElementById('pipe-detail-' + id); if (el) el.textContent = txt; };

    PIPELINE_PHASES.forEach(ph => { setStep(ph, 'waiting'); setDetail(ph, '—'); });

    // Download
    {
      const srcs = p.source_results || [];
      const okN = srcs.filter(r => r.status === 'ok').length;
      const errN = srcs.filter(r => r.status === 'error').length;
      const total = srcs.length || p.sources_total || 0;
      const done = p.sources_done || okN + errN;
      setDetail('download', total > 0 ? `${done}/${total} · ${okN}ok ${errN}err` : '—');
    }
    // Blacklist
    {
      const bls = p.bl_source_results || [];
      const okN = bls.filter(r => r.status === 'ok').length;
      const errN = bls.filter(r => r.status === 'error').length;
      const total = bls.length || p.bl_sources_total || 0;
      const done = p.bl_sources_done || okN + errN;
      setDetail('blacklist', total > 0 ? `${done}/${total} · ${okN}ok ${errN}err` : '—');
    }
    // Validate
    {
      const total = p.checking_total || p.downloaded || 0;
      const checked = p.checked || 0;
      const pct = total > 0 ? Math.round(checked / total * 100) : 0;
      setDetail('validate', total > 0 ? `${checked}/${total} ${pct}% · ⚡${parallel} ✓${p.working || 0} ✗${p.failed || 0}` : '—');
    }
    // Health
    {
      const alive = (s.counts && s.counts.alive) || 0;
      setDetail('health', alive > 0 ? `${alive} alive · ${Math.round((s.settings || {}).health_interval || 300)}s` : '—');
    }

    // Mark done/active
    const currentIdx = phaseKey ? PIPELINE_PHASES.indexOf(phaseKey) : -1;
    PIPELINE_PHASES.forEach((ph, i) => {
      if (currentIdx < 0) return;
      if (i < currentIdx) setStep(ph, 'done');
      else if (i === currentIdx) setStep(ph, s.paused ? 'paused' : 'active');
    });
    if (phase === 'done') PIPELINE_PHASES.forEach(ph => setStep(ph, 'done'));
  }

  function updateConveyor(s) {
    const p = s.progress || {};
    const active = p.active_checks || [];
    const now = Date.now() / 1000;
    const protoColors = { socks5: 'var(--accent)', socks4: 'var(--info)', http: 'var(--text-secondary)', https: 'var(--success)' };

    const byPhase = {};
    CONVEYOR_PHASES.forEach(ph => byPhase[ph] = []);

    active.forEach(c => {
      const ph = CONVEYOR_PHASES.includes(c.step) ? c.step : 'queued';
      byPhase[ph].push(c);
    });

    CONVEYOR_PHASES.forEach(ph => {
      const items = document.getElementById('conveyor-vitems-' + ph);
      const count = document.getElementById('conveyor-vcount-' + ph);
      const lane = document.getElementById('conveyor-vlane-' + ph);
      if (!items) return;

      if (count) count.textContent = String(byPhase[ph].length);
      if (lane) lane.classList.toggle('conveyor-vlane-active', byPhase[ph].length > 0);

      items.innerHTML = '';
      byPhase[ph].sort((a, b) => (a.started || 0) - (b.started || 0)).forEach(c => {
        const card = ui.el('div', 'conveyor-vcard conveyor-vcard-' + ph);
        const protoEl = ui.el('span', 'conveyor-proto', { text: (c.protocol || 'http').toUpperCase() });
        protoEl.style.color = protoColors[c.protocol] || protoColors.http;
        card.appendChild(protoEl);

        const addrEl = ui.el('span', 'conveyor-addr', { text: c.addr || '—' });
        card.appendChild(addrEl);

        const elapsed = Math.max(0, now - (c.started || now));
        const elapsedEl = ui.el('span', 'conveyor-elapsed', { text: elapsed.toFixed(1) + 's' });
        card.appendChild(elapsedEl);

        if (c.cc) {
          const flagEl = ui.el('span', 'conveyor-flag', { text: ui.flag(c.cc) || '' });
          card.appendChild(flagEl);
        }

        items.appendChild(card);
      });
    });

    const live = document.getElementById('pipeline-live');
    if (live) {
      if (s.paused) { live.textContent = t('page.hunt.paused'); live.className = 'pipeline-live paused'; }
      else if (s.running) { live.textContent = active.length + ' ' + t('page.hunt.conv_active'); live.className = 'pipeline-live active'; }
      else { live.textContent = t('page.hunt.idle'); live.className = 'pipeline-live'; }
    }
  }

  function updateResults(s) {
    const counts = s.counts || {};
    const alive = s.top_proxies || [];
    const dead = s.recent_dead || [];
    const protoColors = { socks5: 'var(--accent)', socks4: 'var(--info)', http: 'var(--text-secondary)', https: 'var(--success)' };

    const aliveEl = document.getElementById('results-alive-items');
    const deadEl = document.getElementById('results-dead-items');
    const aliveCount = document.getElementById('results-alive-count');
    const deadCount = document.getElementById('results-dead-count');
    const totalCount = document.getElementById('results-count');
    if (aliveCount) aliveCount.textContent = String(counts.alive || 0);
    if (deadCount) deadCount.textContent = String(counts.dead || 0);
    if (totalCount) totalCount.textContent = (counts.alive || 0) + ' / ' + (counts.dead || 0);

    const renderCard = (p, cls) => {
      const card = ui.el('div', 'conveyor-vcard ' + cls);
      const protoEl = ui.el('span', 'conveyor-proto', { text: (p.protocol || 'http').toUpperCase() });
      protoEl.style.color = protoColors[p.protocol] || protoColors.http;
      card.appendChild(protoEl);
      const addrEl = ui.el('span', 'conveyor-addr', { text: p.address });
      addrEl.classList.add('proxy-address-link');
      addrEl.dataset.cardAddr = p.address;
      card.appendChild(addrEl);
      if (p.country_code) {
        const flagEl = ui.el('span', 'conveyor-flag', { text: ui.flag(p.country_code) || '' });
        card.appendChild(flagEl);
      }
      if (p.speed_avg) {
        const speedEl = ui.el('span', 'conveyor-elapsed', { text: Math.round(p.speed_avg) + 'KB/s' });
        card.appendChild(speedEl);
      }
      return card;
    };

    if (aliveEl) {
      aliveEl.innerHTML = '';
      alive.slice(0, 50).forEach(p => aliveEl.appendChild(renderCard(p, 'conveyor-vcard-alive')));
    }
    if (deadEl) {
      deadEl.innerHTML = '';
      dead.slice(0, 50).forEach(p => deadEl.appendChild(renderCard(p, 'conveyor-vcard-dead')));
    }

    [aliveEl, deadEl].forEach(el => {
      if (!el) return;
      el.querySelectorAll('[data-card-addr]').forEach(link => {
        link.addEventListener('click', (e) => {
          e.stopPropagation();
          const addr = link.dataset.cardAddr;
          if (addr && window.proxyCard) window.proxyCard.show(addr);
        });
      });
    });
  }

  function updateStats(s) {
    const c = s.counts || {};
    const el = id => document.getElementById(id);
    const paused = s.paused || false;
    const manual = s.manual_pause || false;
    if (el('btn-hunt-start')) el('btn-hunt-start').disabled = s.running && !paused;
    if (el('btn-hunt-pause')) el('btn-hunt-pause').disabled = !s.running || paused;
    if (el('btn-hunt-resume')) el('btn-hunt-resume').disabled = !paused;
    if (el('btn-hunt-stop')) el('btn-hunt-stop').disabled = !s.running && !paused;

    const skipBtn = el('btn-hunt-skip');
    if (skipBtn) {
      const skippable = s.running && !paused && (s.phase === 'downloading' || s.phase === 'blacklists' || s.phase === 'validating');
      skipBtn.style.display = skippable ? '' : 'none';
    }

    if (el('phase-badge')) {
      const badge = el('phase-badge');
      if (paused) {
        badge.textContent = manual ? t('page.hunt.paused') : t('page.hunt.pausedNoInet');
        badge.style.color = 'var(--warning,#9a6700)';
        badge.style.background = 'rgba(154,103,0,0.12)';
      } else {
        badge.textContent = s.phase || t('page.hunt.idle');
        badge.style.color = s.running ? 'var(--accent)' : 'var(--text-secondary)';
        badge.style.background = s.running ? 'var(--accent-light)' : 'var(--surface-raised)';
      }
    }
    if (el('last-event')) el('last-event').textContent = s.last_event || t('common.ready');
    if (el('live-dot')) el('live-dot').style.background = paused ? 'var(--warning,#9a6700)' : s.running ? 'var(--accent)' : 'var(--text-muted)';
  }

  function updateProgress(s) {
    const p = s.progress || {};
    const total = p.checking_total || p.downloaded || 0;
    const c = p.checked || 0;
    const pct = total > 0 ? Math.round((c / total) * 100) : 0;
    const el = id => document.getElementById(id);
    if (el('progress-fill')) el('progress-fill').style.width = pct + '%';
    if (el('p-checked')) el('p-checked').textContent = c;
    if (el('p-total')) el('p-total').textContent = total;
    if (el('p-new-working')) el('p-new-working').textContent = p.new_working || 0;
    if (el('p-confirmed-working')) el('p-confirmed-working').textContent = p.confirmed_working || 0;

    if (el('last-proxy-row')) {
      if (p.last_proxy) {
        el('last-proxy-row').style.visibility = 'visible';
        const det = s.last_proxy_details || {};
        if (el('last-flag')) el('last-flag').textContent = ui.flag(det.country_code || '');
        if (el('last-addr')) el('last-addr').textContent = p.last_proxy;
        if (el('last-country-name')) el('last-country-name').textContent = p.last_country || '';
      } else {
        el('last-proxy-row').style.visibility = 'hidden';
      }
    }
  }

  function setTopSort(key) {
    if (topSortKey === key) topSortDir *= -1;
    else { topSortKey = key; topSortDir = -1; }
    poll();
  }

  function updateTopProxies(proxies) {
    const wrap = document.getElementById('top-tbl-wrap');
    if (!wrap) return;
    const el = id => document.getElementById(id);
    if (el('top-count')) el('top-count').textContent = t('page.hunt.alive', { count: (proxies || []).length });

    const sorted = (proxies || []).slice().sort((a, b) => ui.sortValue(a, b, topSortKey, topSortDir));

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, topSortKey, topSortDir) : ''), width, align, sortKey: key, onSort: key ? () => setTopSort(key) : undefined });
    const headers = [
      h('#', null, '24px', 'center'),
      h('Proxy', 'address', null, 'left'),
      h('Ctry', 'country', '40px', 'center'),
      h('Lat', 'last_latency', '50px', 'right'),
      h('Avg', 'latency_avg', '50px', 'right'),
      h('KB/s', 'speed_avg', '40px', 'right'),
      h('Succ', 'success_rate', '40px', 'right'),
      h('Chk', 'checks_total', '40px', 'right'),
      h('Score', 'score', '40px', 'right'),
      h('Flags', null, '50px', 'center'),
      h('Ok', 'last_ok', '36px', 'right'),
      h('', null, '30px', 'center'),
    ];
    const rows = sorted.slice(0, 10).map((p, i) => {
      const sc = Math.min(100, Math.max(0, p.score || 0));
      const flags = [];
      if (p.ssl_supported || p.protocol === 'https') flags.push('<span style="color:var(--success);font-weight:600">HTTPS</span>');
      else flags.push('<span style="color:var(--text-muted)">HTTP</span>');
      if (p.mitm_suspect) flags.push('<span style="color:var(--danger);font-weight:600">MITM!</span>');
      const proto = p.protocol || 'http';
      const favStar = p.is_favorite ? '<svg width="11" height="11" style="vertical-align:-2px;color:var(--warning);flex-shrink:0;width:11px;height:11px;margin-right:2px"><use href="#icon-star"/></svg>' : '<span style="width:13px;flex-shrink:0;display:inline-block"></span>';
      return [
        `<span style="color:var(--text-muted)">${i+1}</span>`,
        `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="font-size:10px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${favStar}${p.address}</span>`,
        ui.flag(p.country_code) || '—',
        p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
        p.latency_avg ? p.latency_avg.toFixed(2) + 's' : '—',
        (p.speed_avg || 0).toFixed(0),
        (p.success_rate * 100).toFixed(0) + '%',
        `${p.checks_ok}/${p.checks_total}`,
        `<div style="display:inline-block;width:30px;height:4px;background:var(--surface-raised);border-radius:2px;vertical-align:middle;overflow:hidden"><div style="width:${sc}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--info));transition:width 0.4s"></div></div>`,
        `<span style="color:var(--text-muted);font-size:10px">${proto}</span> ${flags.join(' ')}`,
        ui.ago(p.last_ok),
        `<button class="btn btn-xs btn-danger" onclick="blAdd('${p.address}','manual')" style="padding:1px 4px;font-size:9px">bl</button>`,
      ];
    });
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
  }

  function setBlSort(key) {
    if (blSortKey === key) blSortDir *= -1;
    else { blSortKey = key; blSortDir = 1; }
    poll();
  }

  function updateBlacklist(bl) {
    const wrap = document.getElementById('bl-tbl-wrap');
    if (!wrap) return;
    const sorted = (bl || []).slice().sort((a, b) => ui.sortValue(a, b, blSortKey, blSortDir));
    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, blSortKey, blSortDir) : ''), width, align, sortKey: key, onSort: key ? () => setBlSort(key) : undefined });
    const headers = [
      h('Proxy', 'address', null, 'left'),
      h('Reason', 'reason', '80px', 'left'),
      h('Ctry', 'country', '40px', 'center'),
      h('', null, '30px', 'center'),
    ];
    const rows = sorted.slice(0, 8).map(b => [
      `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(b.address)}" style="font-size:10px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${b.address}</span>`,
      `<span style="color:var(--danger);font-size:10px">${b.reason || '—'}</span>`,
      b.country || '—',
      `<button class="btn btn-xs btn-secondary" onclick="blRemove('${b.address}')" style="padding:1px 4px;font-size:9px">×</button>`,
    ]);
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
  }

  let huntLogLines = [];
  function updateLog(events) {
    const log = document.getElementById('hunt-log');
    if (!log || !events || !events.length) return;
    events.forEach(e => {
      huntLogLines.unshift(`<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> ${e.msg}`);
      if (huntLogLines.length > 100) huntLogLines.length = 100;
    });
    log.innerHTML = huntLogLines.join('<br>');
  }

  // --- Polling ---
  let lastEventSeq = 0;
  async function poll() {
    try {
      const [s, ev] = await Promise.all([
        api.snapshot().catch(e => { console.error('snapshot', e); return {}; }),
        api.events(lastEventSeq).catch(e => { console.error('events', e); return []; }),
      ]);

      updateStats(s);
      updatePipelineStrip(s);
      updateConveyor(s);
      updateProgress(s);
      updateResults(s);
      updateTopProxies(s.top_proxies);
      if (ev && ev.length) {
        lastEventSeq = Math.max(...ev.map(e => e.seq), lastEventSeq);
        updateLog(ev);
      }
    } catch (e) {
      console.error('hunt poll', e);
    }
  }

  poll();
  const id = setInterval(poll, 1000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/interception.js ==== */
router.register('interception', (container) => {
  // Last port reported by the backend; the input is synced only when the
  // SERVER-side value changes so the 2s poll never clobbers user edits.
  let lastTpPort = null;
  container.innerHTML = '';
  container.classList.add('interception-page');
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';

  // ── Card 1: whole-machine transparent interception (copy-paste) ──
  const card = ui.el('div', 'card');
  card.id = 'interception-card';
  card.appendChild(ui.el('div', 'card-title', { text: t('page.interception.localTitle'), style: 'margin-bottom:8px' }));
  card.appendChild(ui.el('div', '', {
    style: 'font-size:12px;color:var(--text-secondary);margin-bottom:10px;line-height:1.4',
    text: t('page.interception.wholeMachineDesc'),
  }));

  const status = ui.el('div', '', {
    id: 'interception-status',
    style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:10px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)',
  });
  card.appendChild(status);

  const info = ui.el('div', '', { id: 'interception-info', style: 'font-size:12px;color:var(--text-secondary);margin-bottom:10px' });
  card.appendChild(info);

  // ── Readiness checklist + one-click toggle ──
  const readinessEl = ui.el('div', '', {
    id: 'interception-readiness',
    style: 'font-size:12px;line-height:1.6;margin-bottom:10px;padding:8px 10px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-xs)',
  });
  card.appendChild(readinessEl);

  const toggleBtn = ui.el('button', 'btn btn-primary', {
    id: 'btn-intercept-toggle',
    style: 'margin-bottom:10px',
    text: t('page.interception.enable'),
  });
  toggleBtn.addEventListener('click', async () => {
    const wasActive = toggleBtn.dataset.active === '1';
    toggleBtn.disabled = true;
    try {
      if (wasActive) {
        await api.interceptionStop();
      } else {
        toggleBtn.textContent = t('page.interception.applying');
        await api.interceptionApply();
      }
      load();
    } catch (e) {
      app.toast(t('common.error', { message: e.message }), 'error');
      toggleBtn.disabled = false;
    }
  });
  card.appendChild(toggleBtn);

  function buildCmdBlock(labelKey, codeId, btnId) {
    const wrap = ui.el('div', '', { style: 'margin-top:10px' });
    wrap.appendChild(ui.el('div', '', {
      style: 'font-size:11px;color:var(--text-secondary);font-weight:600;margin-bottom:4px',
      text: t(labelKey),
    }));
    const code = ui.el('code', '', {
      id: codeId,
      style: 'display:block;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-xs);padding:8px 10px;color:var(--text-primary);white-space:pre-wrap;word-break:break-all',
    });
    wrap.appendChild(code);
    const btn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.interception.copy'), id: btnId, style: 'margin-top:6px' });
    btn.addEventListener('click', () => copyText(code.textContent, btn));
    wrap.appendChild(btn);
    return wrap;
  }

  card.appendChild(buildCmdBlock('page.interception.applyCmd', 'interception-apply', 'btn-apply-copy'));
  card.appendChild(buildCmdBlock('page.interception.revertCmd', 'interception-revert', 'btn-revert-copy'));

  card.appendChild(ui.el('div', '', {
    style: 'margin-top:12px;font-size:11px;color:var(--text-muted);line-height:1.5',
    text: t('page.interception.localNetNote'),
  }));
  card.appendChild(ui.el('div', '', {
    style: 'margin-top:6px;font-size:11px;color:var(--text-muted);line-height:1.5',
    text: t('page.interception.runHint'),
  }));
  container.appendChild(card);

  // ── Card 2: transparent proxy control (reuses existing endpoints) ──
  const tpCard = ui.el('div', 'card');
  tpCard.id = 'interception-tp-card';
  tpCard.appendChild(ui.el('div', 'card-title', { text: t('page.server.transparent'), style: 'margin-bottom:8px' }));

  const tpStatus = ui.el('div', '', {
    id: 'tp-status-bar',
    style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:8px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)',
  });
  tpStatus.innerHTML = `<span id="tp-dot" style="width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0"></span><span id="tp-status-text">${t('page.server.stopped')}</span>`;
  tpCard.appendChild(tpStatus);

  const tpRow = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px' });
  tpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:52px;flex-shrink:0', text: t('page.server.port') }));
  const tpPortInp = ui.el('input', '', { id: 'interception-tp-port', type: 'number', value: '17477', min: '1024', max: '65535', style: 'width:72px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
  tpRow.appendChild(tpPortInp);
  const tpStartBtn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.server.start'), id: 'btn-tp-start' });
  tpStartBtn.addEventListener('click', () => api.transparentStart(tpPortInp.value).then(() => app.toast(t('page.server.transparentStarted'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
  tpRow.appendChild(tpStartBtn);
  const tpStopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.server.stop'), id: 'btn-tp-stop' });
  tpStopBtn.addEventListener('click', () => api.transparentStop().then(() => app.toast(t('page.server.transparentStopped'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
  tpRow.appendChild(tpStopBtn);
  tpCard.appendChild(tpRow);

  const tpConnRow = ui.el('div', '', { style: 'display:flex;gap:12px;align-items:baseline' });
  const connEl = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
  connEl.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.transparent') }));
  connEl.appendChild(ui.el('span', '', { id: 'interception-tp-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
  tpConnRow.appendChild(connEl);
  tpCard.appendChild(tpConnRow);
  container.appendChild(tpCard);

  // ── Card 3: live intercepted connections (transparent log) ──
  const logCard = ui.el('div', 'card');
  logCard.id = 'interception-tp-log-card';
  logCard.style.display = 'flex';
  logCard.style.flexDirection = 'column';
  logCard.style.overflow = 'hidden';
  logCard.appendChild(ui.el('div', 'card-title', { text: t('page.server.clientLog'), style: 'margin-bottom:8px' }));
  const tpLog = ui.el('div', '', { id: 'interception-tp-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow-y:auto;flex:1;min-height:0;color:var(--text-primary)' });
  tpLog.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.server.proxyNotStarted')}</div>`;
  logCard.appendChild(tpLog);
  container.appendChild(logCard);

  function renderReadiness(r) {
    const el = document.getElementById('interception-readiness');
    if (!el) return;
    if (!r) { el.innerHTML = ''; return; }
    const checks = [
      [r.is_root, t('page.interception.readinessIsRoot')],
      [r.iptables, t('page.interception.readinessIptables')],
      [r.cgroup_v2, t('page.interception.readinessCgroup')],
      [r.script_present, t('page.interception.readinessScript')],
      [r.transparent_running, t('page.interception.readinessTransparentRunning')],
      [r.transparent_listening, t('page.interception.readinessTransparentListening', { port: r.transparent_port })],
    ];
    let html = '<div style="font-weight:600;margin-bottom:4px">' + t('page.interception.readinessTitle') + '</div>';
    for (const pair of checks) {
      const ok = pair[0];
      const label = pair[1];
      const color = ok ? 'var(--success)' : '#f85149';
      const mark = ok ? '✓' : '✗';
      html += '<div><span style="color:' + color + ';font-weight:700">' + mark + '</span> ' + label + '</div>';
    }
    if (!r.ready) {
      html += '<div style="margin-top:4px;color:#f85149">' + t('page.interception.notReady') + '</div>';
      for (const b of (r.blockers || [])) html += '<div style="color:#f85149">• ' + b + '</div>';
    } else {
      html += '<div style="margin-top:4px;color:var(--success)">' + t('page.interception.readyHint') + '</div>';
    }
    el.innerHTML = html;
  }

  function updateToggleBtn(d) {
    const btn = document.getElementById('btn-intercept-toggle');
    if (!btn) return;
    const active = !!(d.status && d.status.active);
    btn.dataset.active = active ? '1' : '0';
    if (active) {
      btn.textContent = t('page.interception.disable');
      btn.disabled = false;
    } else if (d.readiness && d.readiness.ready) {
      btn.textContent = t('page.interception.enable');
      btn.disabled = false;
    } else {
      btn.textContent = t('page.interception.enable');
      btn.disabled = true;
      btn.title = t('page.interception.notReady');
    }
  }

  function copyText(txt, btn) {
    navigator.clipboard.writeText(txt).then(() => {
      const old = btn.textContent;
      btn.textContent = '✓';
      setTimeout(() => { btn.textContent = old; }, 1200);
    }).catch(() => app.toast(t('common.error', { message: txt }), 'error'));
  }

  function renderInterceptStatus(st) {
    const el = document.getElementById('interception-status');
    if (!el) return;
    const active = !!(st && st.active);
    el.style.background = active ? 'var(--success-bg)' : 'var(--surface-raised)';
    el.style.borderColor = active ? 'var(--success)' : 'var(--border)';
    el.style.color = active ? 'var(--success)' : 'var(--text-secondary)';
    let label = active ? t('page.interception.active') : t('page.interception.inactive');
    if (active && st.applied_at) {
      label += ' · ' + t('page.interception.appliedAt') + ' ' + st.applied_at;
    }
    el.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:${active ? 'var(--success)' : 'var(--text-muted)'};flex-shrink:0"></span><span>${label}</span>`;
  }

  function updateTpControl(ts) {
    const bar = document.getElementById('tp-status-bar');
    const dot = document.getElementById('tp-dot');
    const txt = document.getElementById('tp-status-text');
    const running = !!(ts && ts.running);
    if (bar) { bar.style.background = running ? 'var(--success-bg)' : 'var(--surface-raised)'; bar.style.borderColor = running ? 'var(--success)' : 'var(--border)'; bar.style.color = running ? 'var(--success)' : 'var(--text-secondary)'; }
    if (dot) dot.style.background = running ? 'var(--success)' : 'var(--text-muted)';
    if (txt) txt.textContent = running ? t('page.server.running') + ' ' + (ts.port || 17477) : t('page.server.stopped');
    const startBtn = document.getElementById('btn-tp-start');
    const stopBtn = document.getElementById('btn-tp-stop');
    if (startBtn) startBtn.disabled = running;
    if (stopBtn) stopBtn.disabled = !running;
    if (ts && ts.port && ts.port !== lastTpPort) {
      lastTpPort = ts.port;
      const inp = document.getElementById('interception-tp-port');
      if (inp) inp.value = ts.port;
    }
    const conn = document.getElementById('interception-tp-connections');
    if (conn) conn.textContent = ts ? (ts.connections || 0) : 0;
  }

  function updateTpLog(ts) {
    const log = document.getElementById('interception-tp-log');
    if (!log) return;
    const entries = (ts && ts.log) || [];
    if (!entries.length) {
      log.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.server.proxyNotStarted')}</div>`;
      return;
    }
    const fmtTarget = tgt => {
      if (!tgt || tgt === '?') return '?';
      const m = tgt.match(/^(https?:\/\/)?([^\/:]+)(.*)/);
      if (!m) return tgt;
      return (m[1] || '') + '<b>' + m[2] + '</b>' + (m[3] || '');
    };
    log.innerHTML = entries.map(e => `<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> ${e.client || '?'} → ${fmtTarget(e.target)} [${e.status || ''}] <span style="color:var(--info)">via ${ui.escHtml(e.upstream || 'direct')}</span>`).join('<br>');
  }

  async function load() {
    try {
      const d = await api.interception();
      if (document.getElementById('interception-apply')) document.getElementById('interception-apply').textContent = d.apply_command || '';
      if (document.getElementById('interception-revert')) document.getElementById('interception-revert').textContent = d.revert_command || '';
      const ipText = (d.own_ips && d.own_ips.length) ? d.own_ips.join(', ') : '—';
      const infoEl = document.getElementById('interception-info');
      if (infoEl) {
        infoEl.innerHTML =
          `<div><b>${t('page.interception.detectedIp')}:</b> ${ipText}</div>` +
          `<div><b>${t('page.interception.proxyPid')}:</b> ${d.proxy_pid != null ? d.proxy_pid : '—'}</div>`;
      }
      renderInterceptStatus(d.status);
      renderReadiness(d.readiness);
      updateToggleBtn(d);
    } catch (e) {
      console.error('interception load', e);
    }
    try {
      const ts = await api.transparentStatus();
      updateTpControl(ts);
      updateTpLog(ts);
    } catch (e) {
      console.error('transparent status', e);
    }
  }

  load();
  const id = setInterval(load, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/ip-blacklists.js ==== */
router.register('ip-blacklists', (container) => {
  let sources = [];
  let editingId = null;
  let _loading = false;
  let fetchProgress = {};
  let progressPoller = null;

  function fmtBytes(n) {
    if (!n) return '0B';
    if (n >= 1048576) return (n / 1048576).toFixed(1) + 'MB';
    if (n >= 1024) return (n / 1024).toFixed(0) + 'KB';
    return n + 'B';
  }

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
    const row = ui.el('div', 'grid grid-2 row-stretch');
    row.appendChild(buildSourcesCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);

    container.appendChild(buildMatchesCard());
  }

  function buildSourcesCard() {
    const card = ui.card(t('page.ipBlacklists.ipBlacklists'));
    card.id = 'card-ip-blacklists';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.ipBlacklists.newSource'), style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });

    const refreshBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.ipBlacklists.refresh'), style: 'margin-bottom:8px;margin-left:6px' });
    function startFetch() {
      refreshBtn.disabled = true;
      refreshBtn.textContent = t('page.ipBlacklists.fetching');
      fetchProgress = {};
      progressPoller = setInterval(() => {
        api.ipBlacklistProgress().then(r => {
          if (r && r.progress) { fetchProgress = r.progress; updateSourcesCard(sources); }
        }).catch(() => {});
      }, 2000);
      api.ipBlacklistFetch().then(r => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.ipBlacklists.refresh');
        fetchProgress = {};
        if (r.ok) {
          app.toast(`Fetched ${r.total_entries || 0} IP blacklist entries`);
        } else {
          app.toast('Fetch error: ' + (r.error || 'unknown'), 'error');
        }
        load();
      }).catch(e => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.ipBlacklists.refresh');
        fetchProgress = {};
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    }
    refreshBtn.addEventListener('click', startFetch);

    card.appendChild(addBtn);
    card.appendChild(refreshBtn);

    const statusEl = ui.el('div', '', { id: 'ip-bl-fetch-status', style: 'display:none;padding:6px 8px;margin-bottom:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;line-height:1.5' });
    card.appendChild(statusEl);

    const tblWrap = ui.el('div', '', { id: 'ip-blacklists-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noSources')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.ipBlacklists.sourceEditor'));
    card.id = 'card-ip-bl-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'ip-bl-editor-body' });
    body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.selectToEdit')}</div>`;
    card.appendChild(body);

    return card;
  }

  function buildMatchesCard() {
    const card = ui.card(t('page.ipBlacklists.matches'));
    card.id = 'card-ip-bl-matches';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';

    const info = ui.el('div', '', { id: 'ip-bl-matches-info', style: 'font-size:12px;color:var(--text-secondary);margin-bottom:8px' });
    card.appendChild(info);

    const tblWrap = ui.el('div', '', { id: 'ip-bl-matches-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noMatches')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function showEditor(src) {
    const body = document.getElementById('ip-bl-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = src ? src.id : null;

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.ipBlacklists.nameLabel') }));
    const nameInput = ui.el('input', '', { id: 'ip-bl-name', type: 'text', value: src ? src.name : '', placeholder: 'e.g. Tor Exit Nodes', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.ipBlacklists.idLabel') }));
    const idInput = ui.el('input', '', { id: 'ip-bl-id', type: 'text', value: src ? src.id : '', placeholder: 'auto-generated', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);' + (src ? 'opacity:0.6' : '') });
    if (src) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const urlRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    urlRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.ipBlacklists.urlLabel') }));
    const urlInput = ui.el('input', '', { id: 'ip-bl-url', type: 'text', value: src ? src.url : '', placeholder: 'https://example.com/ips.txt', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    urlRow.appendChild(urlInput);
    body.appendChild(urlRow);

    if (src && src.last_fetched_at) {
      const statsHtml = `
        <div style="padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;margin-bottom:12px">
          <div style="margin-bottom:4px;color:var(--text-secondary)">${t('page.ipBlacklists.sourceStats')}</div>
          <div>${t('page.ipBlacklists.lastFetched')}: <b>${ui.ago(src.last_fetched_at)}</b></div>
          <div>${t('page.ipBlacklists.lastStatus')}: <b style="color:${src.last_fetch_status === 'ok' ? 'var(--success)' : 'var(--danger)'}">${src.last_fetch_status || '—'}</b></div>
          ${src.last_fetch_error ? `<div>${t('common.error', {message: ui.escHtml(src.last_fetch_error)})}</div>` : ''}
          <div style="margin-top:6px">
            <span>${t('page.ipBlacklists.fetched')}: ${src.last_fetch_count}</span>
          </div>
          <div style="margin-top:2px">
            <span style="color:var(--text-muted)">${t('page.ipBlacklists.cumulative')}: ${src.total_fetched}</span>
          </div>
        </div>`;
      body.appendChild(ui.el('div', '', { html: statsHtml }));
    }

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: src ? t('page.ipBlacklists.saveChanges') : t('page.ipBlacklists.addSource') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('ip-bl-name').value.trim();
      let sourceId = document.getElementById('ip-bl-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!sourceId) sourceId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const url = document.getElementById('ip-bl-url').value.trim();

      if (!name) { app.toast(t('common.nameRequired'), 'error'); return; }
      if (!url) { app.toast(t('common.urlRequired'), 'error'); return; }

      const data = { id: sourceId, name, url };

      if (editingId) {
        api.ipBlacklistUpdate(editingId, data).then(() => {
          app.toast(t('page.ipBlacklists.sourceUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
      } else {
        api.ipBlacklistCreate(data).then(() => {
          app.toast(t('page.ipBlacklists.sourceAdded'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (src) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
      cancelBtn.addEventListener('click', () => {
        editingId = null;
        resetEditor();
      });
      btnRow.appendChild(cancelBtn);
    }

    body.appendChild(btnRow);
  }

  function resetEditor() {
    const body = document.getElementById('ip-bl-editor-body');
    if (body) body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.selectToEdit')}</div>`;
  }

  function statusBadge(src) {
    const p = fetchProgress[src.id];
    if (p) {
      if (p.status === 'downloading') return `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
      if (p.status === 'connecting') return `<span style="color:var(--info);font-size:11px">…</span>`;
      if (p.status === 'done') return `<span style="color:var(--success);font-size:11px">✓ ${p.count || 0}</span>`;
      if (p.status === 'error') return `<span style="color:var(--danger);font-size:11px">ERR</span>`;
    }
    if (!src.last_fetched_at) return `<span style="color:var(--text-muted);font-size:11px">${t('page.ipBlacklists.never')}</span>`;
    if (src.last_fetch_status === 'ok') return `<span style="color:var(--success);font-size:11px">OK</span>`;
    return `<span style="color:var(--danger);font-size:11px" title="${ui.escHtml(src.last_fetch_error || '')}">ERR</span>`;
  }

  function updateSourcesCard(list) {
    const wrap = document.getElementById('ip-blacklists-tbl');
    if (!wrap) return;
    sources = list || [];

    if (!list || !list.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noSources')}</div>`;
      return;
    }

    const headers = [
      { label: 'Source', width: '160px' },
      { label: 'Status', width: '40px', align: 'center' },
      { label: 'Last', width: '60px' },
      { label: 'Entries', width: '60px', align: 'center' },
      { label: 'On/Off', width: '40px', align: 'center' },
      { label: 'Actions', width: '80px', align: 'center' },
    ];

    const rows = list.map(s => {
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer;font-size:12px';
      nameSpan.textContent = s.name || s.id;
      nameSpan.dataset.sourceId = s.id;
      nameSpan.dataset.action = 'edit';

      const linkBtn = document.createElement('a');
      linkBtn.href = s.url || '#';
      linkBtn.target = '_blank';
      linkBtn.rel = 'noopener';
      linkBtn.style.cssText = 'display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;font-size:10px;color:var(--text-muted);text-decoration:none;border:1px solid var(--border);border-radius:3px;margin-left:4px;vertical-align:middle;flex-shrink:0';
      linkBtn.textContent = '↗';
      linkBtn.title = t('page.ipBlacklists.openSourceUrl');

      const nameCell = document.createElement('span');
      nameCell.style.cssText = 'display:inline-flex;align-items:center;gap:0';
      nameCell.appendChild(nameSpan);
      nameCell.appendChild(linkBtn);

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = t('common.edit');
      editBtn.dataset.sourceId = s.id;
      editBtn.dataset.action = 'edit';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = t('common.delete');
      delBtn.dataset.sourceId = s.id;
      delBtn.dataset.action = 'delete';

      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'btn btn-xs ' + (s.enabled ? 'btn-primary' : 'btn-ghost');
      toggleBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      toggleBtn.textContent = s.enabled ? t('common.on') : t('common.off');
      toggleBtn.dataset.sourceId = s.id;
      toggleBtn.dataset.action = 'toggle';

        const p = fetchProgress[s.id];
        let entryCell;
        if (p) {
          if (p.status === 'downloading') entryCell = `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
          else if (p.status === 'done' && p.count != null) entryCell = `<span style="color:var(--success)">${p.count}</span>`;
          else entryCell = s.current_entries ?? s.last_fetch_count ?? '0';
        } else {
          entryCell = s.current_entries ?? s.last_fetch_count ?? '0';
        }

        return [
          nameCell.outerHTML,
          statusBadge(s),
          ui.ago(s.last_fetched_at),
          entryCell,
        toggleBtn.outerHTML,
        editBtn.outerHTML + delBtn.outerHTML,
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        const sourceId = el.dataset.sourceId;
        const action = el.dataset.action;
        if (action === 'edit') editSource(sourceId);
        else if (action === 'delete') deleteSource(sourceId);
        else if (action === 'toggle') toggleSource(sourceId);
      });
    });
  }

  function renderMatches(matches) {
    const info = document.getElementById('ip-bl-matches-info');
    if (info) info.textContent = t('page.ipBlacklists.matchesInfo', {count: matches.length});

    const wrap = document.getElementById('ip-bl-matches-tbl');
    if (!wrap) return;

    if (!matches || !matches.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noMatches')}</div>`;
      return;
    }

    const headers = [
      { label: 'Proxy', width: '160px' },
      { label: 'Egress IP', width: '120px' },
      { label: 'Country', width: '100px' },
      { label: 'Reason', width: '200px' },
      { label: 'Score', width: '60px', align: 'right' },
    ];

    const rows = matches.map(m => [
      `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(m.address)}" style="cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${m.address}</span>`,
      ui.escHtml(m.egress_ip || '—'),
      `${ui.flag(m.country_code)} ${ui.escHtml(m.country || '—')}`,
      `<span style="color:var(--danger)">${ui.escHtml(m.reason || '—')}</span>`,
      Math.round(m.score || 0),
    ]);

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
  }

  function editSource(id) {
    api.ipBlacklistGet(id).then(src => {
      if (src) showEditor(src);
      else app.toast(t('page.ipBlacklists.sourceNotFound'), 'error');
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function deleteSource(id) {
    if (!confirm(t('common.confirmDelete', {item: 'IP blacklist source'}))) return;
    api.ipBlacklistDelete(id).then(() => {
      app.toast(t('page.ipBlacklists.sourceDeleted'));
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function toggleSource(id) {
    api.ipBlacklistToggle(id).then(() => {
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    if (progressPoller) return;
    _loading = true;
    try {
      let result = [];
      try { result = await api.ipBlacklistSources(); } catch (e) { console.error('ipBlacklistSources', e); }
      const list = result.sources || result || [];
      sources = list;
      updateSourcesCard(list);

      let matches = [];
      try { matches = (await api.ipBlacklistMatches()).matches || []; } catch (e) { console.error('ipBlacklistMatches', e); }
      renderMatches(matches);
    } catch (e) {
      console.error('ip-blacklists load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/logs.js ==== */
router.register('logs', (container) => {
  let state = {
    events: [],
    filter: '',
    types: [],
    reverse: false,
    autoScroll: true,
  };

  const TYPE_FILTERS = [
    { label: 'page.logs.all', value: 'all' },
    { label: 'page.logs.typeInfo', value: 'info' },
    { label: 'page.logs.typeWarn', value: 'warn' },
    { label: 'page.logs.typeError', value: 'error' },
    { label: 'page.logs.typeOk', value: 'ok' },
    { label: 'page.logs.typeProgress', value: 'progress' },
    { label: 'page.logs.typeBlacklist', value: 'blacklist' },
    { label: 'page.logs.typePhase', value: 'phase' },
  ];

  const TYPE_COLORS = {
    info: 'var(--info)',
    warn: 'var(--warning)',
    error: 'var(--danger)',
    ok: 'var(--success)',
    progress: 'var(--text-secondary)',
    blacklist: 'var(--danger)',
    phase: 'var(--info)',
  };

  function fmtTime(ts) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  const typeBtns = {};

  function syncTypeBtns() {
    TYPE_FILTERS.forEach(f => {
      const btn = typeBtns[f.value];
      if (!btn) return;
      const active = f.value === 'all' ? state.types.length === 0 : state.types.includes(f.value);
      btn.className = `btn btn-sm ${active ? 'btn-primary' : 'btn-secondary'}`;
    });
  }

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });
    const search = ui.el('input', '', { type: 'text', placeholder: t('page.logs.filterPlaceholder'), value: state.filter, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:220px' });
    search.addEventListener('input', (e) => {
      state.filter = e.target.value.toLowerCase();
      render();
    });
    filterBar.appendChild(search);

    TYPE_FILTERS.forEach(f => {
      const btn = ui.el('button', 'btn btn-sm btn-secondary', { text: t(f.label) });
      btn.addEventListener('click', () => {
        if (f.value === 'all') {
          state.types = [];
        } else {
          const idx = state.types.indexOf(f.value);
          if (idx >= 0) state.types.splice(idx, 1);
          else state.types.push(f.value);
        }
        syncTypeBtns();
        render();
      });
      typeBtns[f.value] = btn;
      filterBar.appendChild(btn);
    });
    syncTypeBtns();

    const reverseBtn = ui.el('button', `btn btn-sm ${state.reverse ? 'btn-primary' : 'btn-secondary'}`, { text: t('page.logs.reverse') });
    reverseBtn.addEventListener('click', () => {
      state.reverse = !state.reverse;
      reverseBtn.className = `btn btn-sm ${state.reverse ? 'btn-primary' : 'btn-secondary'}`;
      render();
    });
    filterBar.appendChild(reverseBtn);

    const autoScrollBtn = ui.el('button', `btn btn-sm ${state.autoScroll ? 'btn-primary' : 'btn-secondary'}`, { text: t('page.logs.autoScroll') });
    autoScrollBtn.addEventListener('click', () => {
      state.autoScroll = !state.autoScroll;
      autoScrollBtn.className = `btn btn-sm ${state.autoScroll ? 'btn-primary' : 'btn-secondary'}`;
    });
    filterBar.appendChild(autoScrollBtn);

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const liveBtn = ui.el('button', 'btn btn-secondary', { text: t('page.logs.live') });
    let liveInterval = null;
    liveBtn.addEventListener('click', () => {
      if (liveInterval) {
        clearInterval(liveInterval);
        liveInterval = null;
        liveBtn.textContent = t('page.logs.live');
        liveBtn.className = 'btn btn-secondary';
      } else {
        load();
        liveInterval = setInterval(load, 3000);
        liveBtn.textContent = t('page.logs.stopLive');
        liveBtn.className = 'btn btn-primary';
      }
    });
    filterBar.appendChild(liveBtn);

    const clearBtn = ui.el('button', 'btn btn-secondary', { text: t('page.logs.clear') });
    clearBtn.addEventListener('click', () => { state.events = []; render(); });
    filterBar.appendChild(clearBtn);

    container.appendChild(filterBar);

    const card = ui.card(t('page.logs.systemLogs'));
    card.id = 'logs-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    container.appendChild(card);
  }

  build();

  async function load() {
    try {
      const data = await api.logs({ limit: 500 });
      state.events = data.events || [];
      render();
    } catch (e) {
      console.error('logs load', e);
    }
  }

  function render() {
    const card = document.getElementById('logs-card');
    if (!card) return;
    const oldWrap = document.getElementById('logs-lines-wrap');
    const wasAtBottom = oldWrap ? (oldWrap.scrollHeight - oldWrap.scrollTop - oldWrap.clientHeight < 30) : true;
    const oldScrollTop = oldWrap ? oldWrap.scrollTop : 0;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.logs.systemLogs') }));
    let events = state.events;
    if (state.types.length) {
      events = events.filter(e => state.types.includes(e.type));
    }
    if (state.filter) {
      events = events.filter(e => e.msg.toLowerCase().includes(state.filter));
    }
    const count = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: t('page.logs.lines', { count: events.length }) });
    header.appendChild(count);
    card.appendChild(header);

    if (!events.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.logs.noMatching') }));
      return;
    }

    const display = state.reverse ? events : events.slice().reverse();
    const wrap = ui.el('div', '', { id: 'logs-lines-wrap', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:1.6;flex:1;min-height:0;overflow-y:auto' });
    display.forEach(ev => {
      const row = ui.el('div', '', { style: 'padding:2px 0;border-bottom:1px solid var(--border-subtle);white-space:pre-wrap;word-break:break-all;display:flex;gap:8px' });
      const timeEl = ui.el('span', '', { text: fmtTime(ev.ts), style: 'color:var(--text-muted);flex-shrink:0' });
      row.appendChild(timeEl);
      const typeEl = ui.el('span', '', { text: ev.type.toUpperCase(), style: `color:${TYPE_COLORS[ev.type] || 'var(--text-primary)'};flex-shrink:0;font-weight:600;min-width:70px` });
      row.appendChild(typeEl);
      const msgEl = ui.el('span', '', { text: ev.msg, style: `color:${TYPE_COLORS[ev.type] || 'var(--text-primary)'}` });
      row.appendChild(msgEl);
      wrap.appendChild(row);
    });
    card.appendChild(wrap);
    if (state.autoScroll && wasAtBottom) {
      requestAnimationFrame(() => { wrap.scrollTop = wrap.scrollHeight; });
    } else {
      wrap.scrollTop = oldScrollTop;
    }
  }

  load();
});


/* ==== js/pages/overview.js ==== */
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
    const row3 = ui.el('div', 'grid row-stretch', { style: 'grid-template-columns:2.5fr 1.2fr 1fr' });
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
    const card = ui.el('div', 'card pool-progress-card');
    card.id = 'pool-progress-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.overflow = 'hidden';
    card.style.minWidth = '0';

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
    const skipBtn = ui.el('button', '', { id: 'pool-skip-btn', style: bstyle + ';color:var(--warning,#9a6700);display:none' });
    skipBtn.textContent = '⏭';
    skipBtn.title = t('page.overview.skipPhase');
    btns.appendChild(skipBtn);
    header.appendChild(btns);
    card.appendChild(header);

    const body = ui.el('div', '', { style: 'display:flex;align-items:center;gap:20px;flex-wrap:wrap;min-width:0' });

    const circle = ui.el('div', 'circle-progress', { id: 'pool-circle' });
    circle.innerHTML = `
      <svg width="80" height="80" viewBox="0 0 80 80" style="transform:rotate(-90deg)">
        <circle class="track" cx="40" cy="40" r="34"/>
        <circle class="fill-err" id="pool-circle-err" cx="40" cy="40" r="34" stroke-dasharray="213.6" stroke-dashoffset="213.6" style="stroke:var(--danger);fill:none;stroke-width:6;stroke-linecap:round;transition:stroke-dashoffset 0.4s ease"/>
        <circle class="fill" id="pool-circle-fill" cx="40" cy="40" r="34" stroke-dasharray="213.6" stroke-dashoffset="213.6" style="stroke:var(--success);fill:none;stroke-width:6;stroke-linecap:round;transition:stroke-dashoffset 0.4s ease"/>
      </svg>
      <div class="text">
        <span class="value" id="pool-pct">0%</span>
      </div>`;
    body.appendChild(circle);

    const details = ui.el('div', '', { style: 'flex:1;min-width:0;overflow:hidden' });
    details.appendChild(ui.el('div', '', { id: 'pool-phase', style: 'font-size:13px;font-weight:600;color:var(--text-primary);margin-bottom:8px', text: t('page.overview.validatingProxies') }));

    const bar = ui.el('div', 'progress-bar', { style: 'height:8px;margin-bottom:6px' });
    bar.appendChild(ui.el('div', '', { id: 'pool-bar-fill', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease;border-radius:4px' }));
    details.appendChild(bar);

    const stats = ui.el('div', '', { style: 'display:flex;justify-content:space-between;font-size:12px;color:var(--text-secondary);gap:8px;min-width:0' });
    stats.innerHTML = `<span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t('page.overview.checked')} <b id="pool-checked" style="color:var(--text-primary)">0</b> / <b id="pool-total" style="color:var(--text-primary)">0</b></span><span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t('page.overview.newWorking')} <b id="pool-new-working" style="color:var(--info)">0</b></span><span style="min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${t('page.overview.confirmedWorking')} <b id="pool-confirmed-working" style="color:var(--success)">0</b></span>`;
    details.appendChild(stats);
    body.appendChild(details);
    card.appendChild(body);

    const currentProxy = ui.el('div', '', { id: 'pool-current-proxy', style: 'margin-top:10px;font-size:12px;color:var(--text-secondary);flex:1;min-width:0;overflow:hidden' });
    currentProxy.innerHTML = `<span style="color:var(--text-muted)">${t('common.ready')}</span>`;
    card.appendChild(currentProxy);

    const sourceList = ui.el('div', '', { id: 'pool-source-list', style: 'margin-top:8px;max-height:120px;overflow-y:auto;display:none' });
    card.appendChild(sourceList);

    const poolStats = ui.el('div', '', { id: 'pool-stats-row', style: 'display:grid;grid-template-columns:repeat(4, minmax(0, 1fr));gap:0.3em;margin-top:auto;min-width:0' });
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

    const mode = (det.ssl_supported || det.protocol === 'https') ? 'HTTPS' : (det.protocol || 'HTTP').toUpperCase();
    const ok = det.last_status === 'ok';
    const addrRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.4em;min-width:0' });
    const addrLink = ui.el('span', '', { style: 'font-family:monospace;font-weight:700;color:var(--accent);font-size:12px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%', text: det.address });
    addrLink.addEventListener('click', () => { if (window.proxyCard) window.proxyCard.show(det.address); });
    addrRow.appendChild(addrLink);
    if (det.is_favorite) addrRow.appendChild(ui.el('span', '', { style: 'color:var(--warning);font-size:12px;margin-left:2px', html: '<svg width="12" height="12"><use href="#icon-star"/></svg>' }));
    addrRow.appendChild(ui.el('span', '', { style: 'color:var(--accent);font-weight:600;font-size:11px', text: mode }));
    if (det.ssl_supported) addrRow.appendChild(ui.el('span', '', { style: 'color:#06b6d4;font-weight:600;font-size:10px;border:1px solid #06b6d4;border-radius:3px;padding:0 3px', text: 'SSL' }));
    addrRow.appendChild(ui.el('span', '', { style: `color:${ok ? 'var(--success)' : 'var(--danger)'};font-size:14px`, text: ok ? '●' : '○' }));
    wrap.appendChild(addrRow);

    const hasListen = !!(det.listen_country || det.listen_city);
    const hasEgress = !!(det.egress_country || det.egress_city);
    const diffCountry = hasListen && hasEgress && (det.listen_country || '') !== (det.egress_country || '');

    if (diffCountry) {
      const cols = ui.el('div', '', { style: 'display:grid;grid-template-columns:1fr auto 1fr;gap:0 0.5em;margin-bottom:0.3em;font-size:11px;min-width:0' });

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
      const single = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.2em;font-size:11px;min-width:0' });
      single.appendChild(ui.el('span', 'flag', { text: ui.flag(det.country_code || ''), style: 'flex-shrink:0' }));
      single.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: (det.listen_country || det.egress_country || det.country || '') + (det.listen_city || det.egress_city ? ', ' + (det.listen_city || det.egress_city) : '') }));
      wrap.appendChild(single);
      const details = ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);line-height:1.3;margin-bottom:0.2em;overflow-wrap:break-word' });
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
        const cell = ui.el('div', '', { style: 'text-align:center;padding:0.25em 0.15em;background:var(--surface-raised);border-radius:0.25em;min-width:0;overflow:hidden' });
        cell.appendChild(ui.el('div', '', { style: 'font-size:0.6em;color:var(--text-muted);text-transform:uppercase;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: it.l }));
        cell.appendChild(ui.el('div', '', { style: 'font-weight:600;color:var(--text-primary);font-size:clamp(0.65em, 2.5cqw, 0.8em);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: it.v }));
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
      row.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-primary);min-width:0;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:140px', text: name }));
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
    const recheckBtn = ui.el('button', 'card-action', { text: t('page.overview.recheck') });
    recheckBtn.addEventListener('click', () => {
      recheckBtn.disabled = true;
      recheckBtn.textContent = t('common.testing');
      api.healthStart().then(() => {
        app.toast(t('common.recheckStarted'));
        const wait = setInterval(async () => {
          try {
            const s = await api.snapshot();
            if (!s.running || s.phase !== 'health') {
              clearInterval(wait);
              recheckBtn.disabled = false;
              recheckBtn.textContent = t('page.overview.recheck');
            }
          } catch (e) { /* keep waiting */ }
        }, 2000);
        if (window._pageIntervals) window._pageIntervals.push(wait);
      }).catch(e => {
        recheckBtn.disabled = false;
        recheckBtn.textContent = t('page.overview.recheck');
        if (e.message && e.message.includes('already_running')) {
          app.toast(t('common.recheckAlreadyRunning'), 'warn');
        } else {
          app.toast(t('common.error', {message: e.message}), 'error');
        }
      });
    });
    header.appendChild(recheckBtn);
    const viewAllBtn = ui.el('button', 'card-action', { text: t('page.overview.viewAllProxies') });
    viewAllBtn.addEventListener('click', () => router.navigate('proxies'));
    header.appendChild(viewAllBtn);
    card.appendChild(header);

    const wrap = ui.el('div', '', { id: 'top-rated-tbl-wrap', style: 'flex:1;overflow-y:auto;min-height:0' });
    card.appendChild(wrap);

    return card;
  }

  function blacklistBadge(p) {
    const hits = p.ip_blacklist_hits || 0;
    if (!p.in_blacklist && hits === 0) return '';
    if (hits > 0) {
      return `<span style="display:inline-flex;align-items:center;justify-content:center;min-width:20px;padding:1px 4px;border-radius:var(--radius-xs);background:var(--danger-bg);color:var(--danger);font-weight:700;font-size:9px">BL×${hits}</span>`;
    }
    return `<span style="display:inline-flex;align-items:center;justify-content:center;min-width:16px;padding:1px 4px;border-radius:var(--radius-xs);background:var(--danger-bg);color:var(--danger);font-weight:700;font-size:9px">BL</span>`;
  }

  function proxyMarkers(p) {
    const markers = [];
    const proto = (p.protocol || 'http').toUpperCase();
    const hasHttpsMarker = p.supports_connect;
    if (!(hasHttpsMarker && proto === 'HTTP')) {
      markers.push(`<span style="color:var(--text-muted);font-weight:600;font-size:9px">${proto}</span>`);
    }
    if (p.ssl_supported) markers.push('<span style="color:#06b6d4;font-weight:600;font-size:9px">SSL</span>');
    if (p.supports_connect) markers.push('<span style="color:var(--success);font-weight:600;font-size:9px">HTTPS</span>');
    const fs = typeof p.fraud_score === 'number' ? p.fraud_score : null;
    const fv = p.fraud_verdict || 'FAILCHECK';
    const flags = `hosting ${p.fraud_hosting ? 'yes' : 'no'} · proxy ${p.fraud_proxy ? 'yes' : 'no'} · mobile ${p.fraud_mobile ? 'yes' : 'no'}`;
    if (p.fraud_failcheck || fs === null) {
      markers.push(`<span title="FAILCHECK — no fresh measurement (${flags})" style="display:inline-flex;align-items:center;padding:1px 4px;border-radius:var(--radius-xs);background:rgba(107,114,128,.15);color:var(--text-muted);font-weight:700;font-size:9px">FC</span>`);
    } else {
      const fColor = fv === 'CLEAN' ? 'var(--success)' : fv === 'MOBILE' ? '#3b82f6' : fv === 'DC' ? 'var(--warning)' : 'var(--danger)';
      const fBg = fv === 'CLEAN' ? 'rgba(34,197,94,.12)' : fv === 'MOBILE' ? 'rgba(59,130,246,.12)' : fv === 'DC' ? 'rgba(245,158,11,.12)' : 'rgba(239,68,68,.12)';
      markers.push(`<span title="${fv}: risk ${fs}/100 · ${flags}" style="display:inline-flex;align-items:center;padding:1px 4px;border-radius:var(--radius-xs);background:${fBg};color:${fColor};font-weight:700;font-size:9px">F:${fs}</span>`);
    }
    if (p.mitm_suspect) markers.push('<span style="color:var(--danger);font-weight:700;font-size:9px">MITM!</span>');
    if (p.in_grace) markers.push('<span style="color:var(--warning);font-weight:600;font-size:9px">GRACE</span>');
    const bl = blacklistBadge(p);
    if (bl) markers.push(bl);
    return markers.join(' ');
  }

  function renderTopRated(proxies, ps) {
    const wrap = document.getElementById('top-rated-tbl-wrap');
    if (!wrap) return;

    const activeAddr = ps && ps.active_proxy ? ps.active_proxy.address : null;
    const running = ps && ps.running;
    const port = ps && ps.port ? ps.port : 17277;

    const headers = [
      { label: '#', width: '28px', align: 'center' },
      { label: 'Country', width: null, align: 'left' },
      { label: 'Proxy', width: null, align: 'left' },
      { label: 'Markers', width: null, align: 'left' },
      { label: 'Lat', width: '46px', align: 'right' },
      { label: 'Speed', width: '50px', align: 'right' },
      { label: 'Score', width: '44px', align: 'right' },
      { label: 'Up', width: '44px', align: 'center' },
      { label: 'Last', width: '50px', align: 'right' },
      { label: '', width: '46px', align: 'center' },
    ];
    const agoShort = (ts) => {
      if (!ts) return '—';
      const d = Math.floor(Date.now() / 1000 - ts);
      if (d < 0) return t('ago.now');
      if (d < 60) return d + 's';
      if (d < 3600) return Math.floor(d / 60) + 'm';
      if (d < 86400) return Math.floor(d / 3600) + 'h';
      return Math.floor(d / 86400) + 'd';
    };
    const rows = (proxies || []).map((p, i) => {
      const isSel = activeAddr === p.address;
      const favStar = p.is_favorite ? '<svg width="11" height="11" style="vertical-align:-2px;color:var(--warning);flex-shrink:0;width:11px;height:11px;margin-right:2px"><use href="#icon-star"/></svg>' : '<span style="width:13px;flex-shrink:0;display:inline-block"></span>';
      return [
        `<span style="color:var(--text-muted);font-size:11px">${i + 1}</span>`,
        `<span class="flag">${ui.flag(p.country_code)}</span> <span style="font-size:11px">${ui.escHtml(p.country || '')}</span>`,
        `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${favStar}${ui.escHtml(p.address)}</span>`,
        `<span style="display:inline-flex;gap:3px;flex-wrap:wrap">${proxyMarkers(p)}</span>`,
        p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
        p.speed_avg ? p.speed_avg.toFixed(0) + 'KB/s' : '—',
        (p.score || 0).toFixed(0),
        `${p.checks_ok || 0}/${p.checks_total || 0}`,
        agoShort(p.last_check),
        `<button class="btn btn-xs ${isSel ? 'btn-primary' : 'btn-secondary'}" data-select-addr="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px">${isSel ? t('page.proxyPool.active') : t('page.proxyPool.select')}</button>`,
      ];
    });
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-select-addr]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.selectAddr;
        if (!addr) return;
        api.proxySelect(addr).then(() => {
          app.toast(t('page.proxyPool.selected', { addr }));
          if (!running) {
            return api.proxyStart(port).then(() => app.toast(t('page.overview.proxyStarted')));
          }
        }).catch(er => app.toast(t('common.error', { message: er.message }), 'error'));
      });
    });

    wrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
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
      { icon: 'download', label: t('page.overview.export'), desc: t('page.overview.exportDesc'), action: () => api.exportProxies().then(r => { const blob = new Blob([r.data], {type: 'text/plain'}); const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'export.txt'; a.click(); URL.revokeObjectURL(a.href); app.toast(t('page.overview.export')); }).catch(e => app.toast(t('common.error', {message: e.message}), 'error')), color: 'var(--info)', bg: 'rgba(59,130,246,0.1)' },
      { icon: 'upload', label: t('page.overview.import'), desc: t('page.overview.importDesc'), action: () => { const dlg = ui.el('div', '', { style: 'position:fixed;inset:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999' }); const box = ui.el('div', 'card', { style: 'padding:20px;max-width:380px;width:90%;display:flex;flex-direction:column;gap:12px' }); box.appendChild(ui.el('div', '', { style: 'font-weight:600;font-size:14px', text: t('page.overview.import') })); const cbWrap = ui.el('label', '', { style: 'display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer' }); const favCb = ui.el('input', '', { type: 'checkbox', checked: true }); cbWrap.appendChild(favCb); cbWrap.appendChild(ui.el('span', '', { text: t('page.overview.importAsFavorite') })); box.appendChild(cbWrap); const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;justify-content:flex-end' }); const cancelBtn = ui.el('button', 'btn btn-secondary', { text: t('common.cancel') }); cancelBtn.addEventListener('click', () => dlg.remove()); const pickBtn = ui.el('button', 'btn btn-primary', { text: t('page.overview.chooseFile') }); pickBtn.addEventListener('click', () => { const inp = document.createElement('input'); inp.type = 'file'; inp.accept = '.txt'; inp.onchange = () => { const f = inp.files[0]; if (!f) return; const reader = new FileReader(); reader.onload = () => { const lines = reader.result.split('\n'); api.importProxies({ proxies: lines, favorite: favCb.checked }).then(r => { const msg = t('page.overview.import') + ': ' + (r.added || 0) + (r.favorited != null ? ' ⭐' + r.favorited : ''); app.toast(msg); dlg.remove(); }).catch(e => { app.toast(t('common.error', {message: e.message}), 'error'); dlg.remove(); }); }; reader.readAsText(f); }; inp.click(); }); btnRow.appendChild(cancelBtn); btnRow.appendChild(pickBtn); box.appendChild(btnRow); dlg.appendChild(box); dlg.addEventListener('click', (e) => { if (e.target === dlg) dlg.remove(); }); document.body.appendChild(dlg); }, color: 'var(--warning)', bg: 'rgba(245,158,11,0.1)' },
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
    const card = ui.el('div', 'card current-proxy-card');
    card.id = 'current-proxy-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.overflow = 'hidden';
    card.style.minWidth = '0';

    const header = ui.el('div', 'card-header');
    const titleRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;min-width:0;flex:1' });
    titleRow.appendChild(ui.el('div', 'card-title', { id: 'proxy-card-title', text: t('page.overview.localProxy') }));
    const poolBtn = ui.el('button', 'card-action', { text: t('page.overview.proxyPool') });
    poolBtn.addEventListener('click', () => router.navigate('proxy-pool'));
    titleRow.appendChild(poolBtn);
    header.appendChild(titleRow);
    card.appendChild(header);

    const main = ui.el('div', '', { id: 'current-proxy-main', style: 'flex:1;min-width:0;overflow:hidden;display:grid;grid-template-columns:1fr 1fr;gap:8px' });

    const body = ui.el('div', '', { id: 'current-proxy-body', style: 'min-width:0;overflow-y:auto;display:flex;flex-direction:column' });
    body.innerHTML = `<div class="empty" style="font-size:12px;padding:16px">${t('page.overview.noUpstreamSelected')}</div>`;
    main.appendChild(body);

    const history = ui.el('div', '', { id: 'proxy-switch-history-mini', style: 'min-width:0;font-size:11px;display:flex;flex-direction:column' });
    main.appendChild(history);

    card.appendChild(main);

    const statsRow = ui.el('div', '', { id: 'proxy-stats-row', style: 'display:grid;grid-template-columns:repeat(auto-fit, minmax(0, 1fr));gap:0.3em;margin-top:8px;min-width:0;flex-shrink:0' });
    card.appendChild(statsRow);

    return card;
  }

  function renderCurrentProxy(ps, ss) {
    const body = document.getElementById('current-proxy-body');
    const statsWrap = document.getElementById('proxy-stats-row');
    const card = document.getElementById('current-proxy-card');
    const titleEl = document.getElementById('proxy-card-title');
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
    renderSwitchHistoryMini(ps);

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

    if (!ap) {
      const nextBtn = ui.el('button', '', { style: 'padding:0.4em 1em;border:1px solid var(--border);border-radius:0.3em;background:var(--surface-raised);color:var(--accent);cursor:pointer', text: t('page.overview.selectBestProxy') });
      nextBtn.addEventListener('click', () => api.proxyNext().then(() => app.toast(t('page.overview.proxySelected'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
      body.appendChild(nextBtn);
      return;
    }

    const mode = (ap.ssl_supported || ap.protocol === 'https') ? 'HTTPS' : (ap.protocol || 'HTTP').toUpperCase();
    const ok = ap.last_status === 'ok';
    const metaRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.3em;min-width:0' });
    metaRow.appendChild(ui.el('span', '', { style: 'color:var(--accent);font-weight:600;font-size:11px', text: mode }));
    if (ap.ssl_supported) metaRow.appendChild(ui.el('span', '', { style: 'color:#06b6d4;font-weight:600;font-size:10px;border:1px solid #06b6d4;border-radius:3px;padding:0 3px', text: 'SSL' }));
    metaRow.appendChild(ui.el('span', '', { style: `color:${ok ? 'var(--success)' : 'var(--danger)'};font-size:14px`, text: ok ? '●' : '○' }));
    const actionBtns = ui.el('div', '', { style: 'display:flex;gap:4px;margin-left:auto' });
    actionBtns.appendChild(mkBtn('»', t('page.overview.nextProxy'), 'var(--accent)', () => api.proxyNext().then(() => app.toast(t('page.overview.switchedToNext'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error'))));
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
    actionBtns.appendChild(recheckBtn);
    metaRow.appendChild(actionBtns);
    if (!document.getElementById('recheck-spin-style')) {
      const s = document.createElement('style');
      s.id = 'recheck-spin-style';
      s.textContent = '@keyframes recheckSpin{from{transform:rotate(0deg)}to{transform:rotate(360deg)}}';
      document.head.appendChild(s);
    }
    body.appendChild(metaRow);

    const hasListen = !!(ap.listen_country || ap.listen_city);
    const hasEgress = !!(ap.egress_country || ap.egress_city);
    const diffCountry = hasListen && hasEgress && (ap.listen_country || '') !== (ap.egress_country || '');

    if (diffCountry) {
      const cols = ui.el('div', '', { style: 'display:grid;grid-template-columns:1fr auto 1fr;gap:0 0.5em;margin-bottom:0.3em;font-size:11px;min-width:0' });

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
      const single = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0.4em;flex-wrap:wrap;margin-bottom:0.2em;font-size:11px;min-width:0' });
      single.appendChild(ui.el('span', 'flag', { text: ui.flag(ap.country_code || ''), style: 'flex-shrink:0' }));
      single.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: (ap.listen_country || ap.egress_country || ap.country || '') + (ap.listen_city || ap.egress_city ? ', ' + (ap.listen_city || ap.egress_city) : '') }));
      body.appendChild(single);
      const details = ui.el('div', '', { style: 'font-size:0.7em;color:var(--text-muted);line-height:1.3;margin-bottom:0.2em;overflow-wrap:break-word' });
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
        const cell = ui.el('div', '', { style: 'text-align:center;padding:0.25em 0.15em;background:var(--surface-raised);border-radius:0.25em;min-width:0;overflow:hidden' });
        cell.appendChild(ui.el('div', '', { style: 'font-size:0.6em;color:var(--text-muted);text-transform:uppercase;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: it.l }));
        cell.appendChild(ui.el('div', '', { style: 'font-weight:600;color:var(--text-primary);font-size:clamp(0.65em, 2.5cqw, 0.8em);overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: it.v }));
        statsWrap.appendChild(cell);
      });
    }

  }

  function renderSwitchHistoryMini(ps) {
    const wrap = document.getElementById('proxy-switch-history-mini');
    if (!wrap) return;
    const history = (ps && ps.switch_history) || [];
    wrap.innerHTML = '';

    const header = ui.el('div', '', { style: 'display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;flex-shrink:0' });
    header.appendChild(ui.el('div', '', { style: 'font-size:10px;font-weight:600;color:var(--text-secondary);text-transform:uppercase', text: t('page.overview.recentSwitches') }));
    header.appendChild(ui.el('div', '', { style: 'font-size:9px;color:var(--text-muted)', text: t('page.overview.switchHistoryHint') }));
    wrap.appendChild(header);

    if (!history.length) {
      wrap.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);padding:8px 0', text: t('page.overview.noSwitches') }));
      return;
    }

    const fmtDuration = (sec) => {
      if (!sec || sec <= 0) return '0s';
      if (sec < 60) return Math.round(sec) + 's';
      if (sec < 3600) return Math.floor(sec / 60) + 'm' + Math.round(sec % 60) + 's';
      return Math.floor(sec / 3600) + 'h' + Math.floor((sec % 3600) / 60) + 'm';
    };

    const list = ui.el('div', 'switch-history-mini');
    history.slice(0, 6).forEach((e, i) => {
      const row = ui.el('div', 'sh-item' + (i === 0 ? ' current' : ''));

      const top = ui.el('div', 'sh-top');
      if (!e.address) {
        top.appendChild(ui.el('span', '', { style: 'font-size:10px;color:var(--text-muted)', text: e.action === 'direct' ? t('page.proxyPool.directModeOn') : t('page.proxyPool.cleared') }));
      } else {
        const flag = e.egress_country_code ? ui.flag(e.egress_country_code) : '';
        top.appendChild(ui.el('span', 'flag', { text: flag }));
        const addr = ui.el('span', 'sh-addr', { text: e.address, title: e.address });
        addr.addEventListener('click', () => { if (window.proxyCard) window.proxyCard.show(e.address); });
        top.appendChild(addr);
        if (e.is_favorite) {
          top.appendChild(ui.el('span', 'sh-fav', { html: '<svg width="10" height="10"><use href="#icon-star"/></svg>' }));
        }
      }
      row.appendChild(top);

      const meta = ui.el('div', 'sh-meta');
      const bytes = e.bytes || 0;
      meta.appendChild(ui.el('span', 'traffic', { text: '↓↑ ' + ui.fmtBytes(bytes) }));
      meta.appendChild(ui.el('span', 'duration', { text: '●' + fmtDuration(e.duration_sec) }));
      meta.appendChild(ui.el('span', 'when', { text: ui.ago(e.ts) }));
      row.appendChild(meta);

      list.appendChild(row);
    });
    wrap.appendChild(list);
  }

  build();

  // --- Polling ---
  let lastEventSeq = 0;
  let trafficThrottle = 0;
  let lastTrafficItems = [];

  async function poll() {
    try {
      // Parallel fetch: serial awaits made first data appear only after the
      // SUM of endpoint latencies instead of the max.
      const [ps, ss, s, ev] = await Promise.all([
        api.proxyStatus().catch(e => { console.error('proxyStatus', e); return {}; }),
        api.socks5Status().catch(e => { console.error('socks5Status', e); return {}; }),
        api.snapshot().catch(e => { console.error('snapshot', e); return {}; }),
        api.events(lastEventSeq).catch(e => { console.error('events', e); return []; }),
      ]);

      // Update stat cards
      const c = s.counts || {};
      try { localStorage.setItem('overview.counts', JSON.stringify({ t: Date.now(), c })); } catch (e) {}
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
      const isDownloading = s.phase === 'downloading' || s.phase === 'blacklists';
      const isHealthCheck = s.phase === 'health';
      const isBlacklists = s.phase === 'blacklists';
      const poolTotal = isDownloading ? (isBlacklists ? (p.bl_sources_total || 0) : (p.sources_total || 0)) : (p.checking_total || p.downloaded || 0);
      const checked = isDownloading ? (isBlacklists ? (p.bl_sources_done || 0) : (p.sources_done || 0)) : (p.checked || 0);
      const pct = poolTotal > 0 ? Math.round((checked / poolTotal) * 100) : 0;
      if (el('pool-pct')) el('pool-pct').textContent = pct + '%';
      if (el('pool-checked')) el('pool-checked').textContent = checked;
      if (el('pool-total')) el('pool-total').textContent = poolTotal;
      if (el('pool-new-working')) el('pool-new-working').textContent = p.new_working || 0;
      if (el('pool-confirmed-working')) el('pool-confirmed-working').textContent = p.confirmed_working || 0;
      if (el('pool-bar-fill')) el('pool-bar-fill').style.width = pct + '%';
      if (el('pool-circle-fill')) {
        const circumference = 2 * Math.PI * 34;
        let okPct, errPct;
        if (isDownloading) {
          const results = isBlacklists ? (p.bl_source_results || []) : (p.source_results || []);
          const total = results.length || poolTotal || 1;
          const okN = results.filter(r => r.status === 'ok').length;
          const errN = results.filter(r => r.status === 'error').length;
          okPct = okN / total;
          errPct = errN / total;
        } else {
          okPct = poolTotal > 0 ? (p.working || 0) / poolTotal : 0;
          errPct = poolTotal > 0 ? (p.failed || 0) / poolTotal : 0;
        }
        const errEl = el('pool-circle-err');
        if (errEl) {
          errEl.style.strokeDashoffset = circumference - (errPct * circumference);
          errEl.style.transformBox = 'fill-box';
          errEl.style.transformOrigin = 'center';
          errEl.style.transform = `rotate(${okPct * 360}deg)`;
        }
        el('pool-circle-fill').style.strokeDashoffset = circumference - (okPct * circumference);
      }
      // Source download details (downloading phase)
      const srcList = document.getElementById('pool-source-list');
      if (srcList) {
        const results = isBlacklists ? (p.bl_source_results || []) : (p.source_results || []);
        if (isDownloading && results.length) {
          srcList.style.display = '';
          srcList.innerHTML = '';
          const okCount = results.filter(r => r.status === 'ok').length;
          const errCount = results.filter(r => r.status === 'error').length;
          const pendingCount = results.length - okCount - errCount;
          const summary = ui.el('div', '', { style: 'font-size:10px;color:var(--text-muted);margin-bottom:4px' });
          summary.innerHTML = `<span style="color:var(--success)">${okCount} OK</span> / <span style="color:var(--danger)">${errCount} ERR</span> / <span style="color:var(--text-muted)">${pendingCount} pending</span>`;
          srcList.appendChild(summary);
          results.forEach(r => {
            const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:4px;font-size:10px;padding:1px 0' });
            const dot = ui.el('span', '', { style: 'width:6px;height:6px;border-radius:50%;flex-shrink:0' });
            dot.style.background = r.status === 'ok' ? 'var(--success)' : r.status === 'error' ? 'var(--danger)' : 'var(--text-muted)';
            row.appendChild(dot);
            const name = ui.el('span', '', { style: 'flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: r.name });
            row.appendChild(name);
            const cnt = ui.el('span', '', { style: 'color:var(--text-muted);flex-shrink:0', text: r.count > 0 ? r.count : (r.status === 'ok' ? '0' : '—') });
            row.appendChild(cnt);
            srcList.appendChild(row);
          });
        } else {
          srcList.style.display = 'none';
        }
      }
      if (el('pool-phase')) {
        const phaseLabels = {
          'downloading': t('page.overview.phaseDownloading'),
          'blacklists': t('page.overview.phaseBlacklists'),
          'validating': t('page.overview.validatingProxies'),
          'health': s.health_manual ? t('page.overview.phaseRecheck') : t('page.overview.phaseHealthCheck'),
          'done': t('page.overview.phaseDone'),
          'idle': t('page.hunt.idle'),
          'paused': t('page.hunt.pausedMsg'),
        };
        el('pool-phase').textContent = phaseLabels[s.phase] || (s.running ? t('page.overview.validatingProxies') : t('page.hunt.idle'));
      }
      if (el('pool-current-proxy')) {
        el('pool-current-proxy').style.display = isDownloading ? 'none' : '';
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
        const skip = el('pool-skip-btn');
        if (skip) {
          const skippable = s.running && !s.paused && (s.phase === 'downloading' || s.phase === 'blacklists' || s.phase === 'validating');
          skip.style.display = skippable ? '' : 'none';
          skip.onclick = () => api.huntSkip().then(r => app.toast(r.ok ? t('page.overview.phaseSkipped') : r.error)).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
        }
      }
      if (el('pool-title')) {
        const p = s.paused || false, m = s.manual_pause || false;
        const phaseTitles = {
          'downloading': t('page.overview.phaseDownloading'),
          'blacklists': t('page.overview.phaseBlacklists'),
          'validating': t('page.overview.validatingProxies'),
          'health': s.health_manual ? t('page.overview.phaseRecheck') : t('page.overview.phaseHealthCheck'),
          'done': t('page.overview.phaseDone'),
        };
        const phaseTitle = phaseTitles[s.phase] || t('page.overview.running');
        el('pool-title').textContent = p ? (m ? t('page.overview.poolProgress') + ' — ' + t('page.hunt.pausedMsg') : t('page.overview.poolProgress') + ' — No Internet') : (s.running ? t('page.overview.poolProgress') + ' — ' + phaseTitle : t('page.overview.poolProgress'));
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
      renderTopRated(s.top_proxies, ps);

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

  // Stale-while-revalidate: paint the last known counters immediately so
  // the cards are never empty while the first poll is in flight.
  try {
    const cached = JSON.parse(localStorage.getItem('overview.counts') || 'null');
    if (cached && Date.now() - cached.t < 300000) {
      const cc = cached.c || {};
      const el0 = id => document.getElementById(id);
      if (el0('stat-val-total')) el0('stat-val-total').textContent = (cc.ratings || 0).toLocaleString();
      if (el0('stat-val-alive')) el0('stat-val-alive').textContent = (cc.alive || 0).toLocaleString();
      if (el0('stat-val-dead')) el0('stat-val-dead').textContent = (cc.dead || 0).toLocaleString();
      if (el0('stat-val-blacklisted')) el0('stat-val-blacklisted').textContent = (cc.blacklist || 0).toLocaleString();
    }
  } catch (e) {}

  poll();
  const id = setInterval(poll, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/pac.js ==== */
router.register('pac', (container) => {
  let cfg = { enabled: false, proxy_host: '', proxy_port: 17277, direct_hosts: [], internal_nets: [], url: '', preview: '' };
  let _loading = false;

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
    const row = ui.el('div', '', { style: 'display:flex;gap:10px;align-items:stretch;flex-wrap:wrap' });
    const settingsCard = buildSettingsCard();
    settingsCard.style.flex = '1';
    settingsCard.style.minWidth = '280px';
    row.appendChild(settingsCard);
    const urlCard = buildUrlCard();
    urlCard.style.flex = '1';
    urlCard.style.minWidth = '280px';
    row.appendChild(urlCard);
    container.appendChild(row);

    const exRow = ui.el('div', '', { style: 'display:flex;gap:10px;align-items:stretch;flex-wrap:wrap' });
    const domainsCard = buildDomainsCard();
    domainsCard.style.flex = '1';
    domainsCard.style.minWidth = '300px';
    exRow.appendChild(domainsCard);
    const netsCard = buildNetsCard();
    netsCard.style.flex = '1';
    netsCard.style.minWidth = '300px';
    exRow.appendChild(netsCard);
    container.appendChild(exRow);

    container.appendChild(buildPreviewCard());
  }

  function buildSettingsCard() {
    const card = ui.card(t('page.pac.serverSettings'));
    card.id = 'card-pac-settings';

    const toggleRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:12px' });
    const label = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;font-weight:600' });
    const cb = ui.el('input', '', { id: 'pac-enabled', type: 'checkbox' });
    cb.addEventListener('change', () => {
      updateStatusBadge();
      persist(true);
    });
    label.appendChild(cb);
    label.appendChild(ui.el('span', '', { text: t('page.pac.enable') }));
    toggleRow.appendChild(label);
    const badge = ui.el('span', '', { id: 'pac-status-badge', style: 'font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600' });
    toggleRow.appendChild(badge);
    card.appendChild(toggleRow);

    const hostRow = fieldRow(t('page.pac.proxyHost'), 'pac-proxy-host');
    card.appendChild(hostRow);

    const portRow = fieldRow(t('page.pac.proxyPort'), 'pac-proxy-port');
    card.appendChild(portRow);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-top:10px;flex-wrap:wrap' });
    const detectBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.pac.detectIp') });
    detectBtn.addEventListener('click', () => {
      const existing = document.getElementById('pac-ip-select-wrap');
      if (existing) { existing.remove(); return; }
      api.pacIps().then(r => {
        const ips = r.ips || [];
        if (!ips.length) return;
        const wrap = ui.el('div', '', { id: 'pac-ip-select-wrap', style: 'display:flex;gap:6px;align-items:center;margin-top:8px' });
        const select = ui.el('select', '', { id: 'pac-ip-select', style: 'flex:1;padding:4px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
        ips.forEach(ip => {
          const o = ui.el('option', '', { value: ip, text: ip });
          if (ip === cfg.proxy_host) o.selected = true;
          select.appendChild(o);
        });
        select.addEventListener('change', () => {
          applySelectedIp(select.value);
          wrap.remove();
        });
        wrap.appendChild(select);
        const useBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.pac.useIp') });
        useBtn.addEventListener('click', () => {
          applySelectedIp(select.value);
          wrap.remove();
        });
        wrap.appendChild(useBtn);
        const hostRow = document.querySelector('#card-pac-settings');
        hostRow.appendChild(wrap);
      }).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    btnRow.appendChild(detectBtn);

    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.pac.save') });
    saveBtn.addEventListener('click', () => save());
    btnRow.appendChild(saveBtn);

    const saveStatus = ui.el('span', '', { id: 'pac-save-status', style: 'font-size:11px;color:var(--text-muted);align-self:center' });
    btnRow.appendChild(saveStatus);
    card.appendChild(btnRow);

    return card;
  }

  function fieldRow(labelText, id) {
    const row = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:4px;margin-bottom:8px' });
    row.appendChild(ui.el('label', '', { style: 'font-size:12px;color:var(--text-secondary)', text: labelText }));
    row.appendChild(ui.el('input', '', {
      id, type: 'text', style: 'padding:5px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)',
    }));
    return row;
  }

  function buildUrlCard() {
    const card = ui.card(t('page.pac.autoconfigUrl'));
    card.id = 'card-pac-url';

    const urlInput = ui.el('input', '', {
      id: 'pac-url', type: 'text', readonly: true, style: 'width:100%;padding:6px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);box-sizing:border-box',
    });
    card.appendChild(urlInput);
    card.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin:6px 0 10px', text: t('page.pac.urlHint') }));

    const copyBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.pac.copyUrl') });
    copyBtn.addEventListener('click', () => {
      const url = document.getElementById('pac-url');
      if (!url || !url.value) return;
      navigator.clipboard.writeText(url.value).then(() => {
        app.toast(t('page.pac.copied'));
      }).catch(() => app.toast('Error', 'error'));
    });
    card.appendChild(copyBtn);
    return card;
  }

  function buildDomainsCard() {
    const card = ui.card(t('page.pac.domains'));
    card.id = 'card-pac-domains';
    card.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-bottom:8px', text: t('page.pac.domainsHint') }));

    const addRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px' });
    const input = ui.el('input', '', { id: 'pac-domain-input', type: 'text', placeholder: '*.example.com', style: 'flex:1;min-width:100px;padding:5px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    addRow.appendChild(input);
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+' });
    addBtn.addEventListener('click', () => {
      const v = input.value.trim();
      if (v && !cfg.direct_hosts.includes(v)) cfg.direct_hosts.push(v);
      input.value = '';
      renderDomainList();
      persist(false);
    });
    addRow.appendChild(addBtn);
    card.appendChild(addRow);

    const list = ui.el('div', '', { id: 'pac-domain-list' });
    card.appendChild(list);
    return card;
  }

  function renderDomainList() {
    const list = document.getElementById('pac-domain-list');
    if (!list) return;
    list.innerHTML = '';
    if (!cfg.direct_hosts.length) {
      list.appendChild(ui.el('div', 'empty', { style: 'padding:8px;font-size:12px', text: t('page.pac.noDomains') }));
      return;
    }
    cfg.direct_hosts.forEach((d, i) => {
      const row = ui.el('div', '', { style: 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 8px;border-bottom:1px solid var(--border);font-size:12px' });
      row.appendChild(ui.el('span', '', { text: d }));
      const del = ui.el('button', '', { style: 'background:none;border:none;cursor:pointer;color:var(--danger);font-size:13px', text: '✕', title: t('common.delete') });
      del.addEventListener('click', () => { cfg.direct_hosts.splice(i, 1); renderDomainList(); persist(false); });
      row.appendChild(del);
      list.appendChild(row);
    });
  }

  function buildNetsCard() {
    const card = ui.card(t('page.pac.subnets'));
    card.id = 'card-pac-nets';
    card.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-bottom:8px', text: t('page.pac.subnetsHint') }));

    const addRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px' });
    const netInput = ui.el('input', '', { id: 'pac-net-input', type: 'text', placeholder: '10.0.0.0', style: 'flex:1;min-width:80px;padding:5px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    addRow.appendChild(netInput);
    const maskInput = ui.el('input', '', { id: 'pac-mask-input', type: 'text', placeholder: '255.0.0.0', style: 'flex:1;min-width:80px;padding:5px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    addRow.appendChild(maskInput);
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+' });
    addBtn.addEventListener('click', () => {
      const network = netInput.value.trim();
      const mask = maskInput.value.trim();
      if (network && mask) cfg.internal_nets.push({ network, mask });
      netInput.value = '';
      maskInput.value = '';
      renderNetList();
      persist(false);
    });
    addRow.appendChild(addBtn);
    card.appendChild(addRow);

    const list = ui.el('div', '', { id: 'pac-net-list' });
    card.appendChild(list);
    return card;
  }

  function renderNetList() {
    const list = document.getElementById('pac-net-list');
    if (!list) return;
    list.innerHTML = '';
    if (!cfg.internal_nets.length) {
      list.appendChild(ui.el('div', 'empty', { style: 'padding:8px;font-size:12px', text: t('page.pac.noSubnets') }));
      return;
    }
    cfg.internal_nets.forEach((n, i) => {
      const row = ui.el('div', '', { style: 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 8px;border-bottom:1px solid var(--border);font-size:12px' });
      row.appendChild(ui.el('span', '', { text: n.network + ' / ' + n.mask }));
      const del = ui.el('button', '', { style: 'background:none;border:none;cursor:pointer;color:var(--danger);font-size:13px', text: '✕', title: t('common.delete') });
      del.addEventListener('click', () => { cfg.internal_nets.splice(i, 1); renderNetList(); persist(false); });
      row.appendChild(del);
      list.appendChild(row);
    });
  }

  function buildPreviewCard() {
    const card = ui.card(t('page.pac.preview'));
    card.id = 'card-pac-preview';
    card.appendChild(ui.el('pre', '', {
      id: 'pac-preview', style: 'background:var(--surface-raised);padding:10px;border-radius:var(--radius-xs);font-size:11px;line-height:1.5;overflow:auto;max-height:360px;white-space:pre-wrap;word-break:break-all;color:var(--text-primary)',
    }));
    return card;
  }

  function collectFromInputs() {
    const host = document.getElementById('pac-proxy-host');
    const port = document.getElementById('pac-port') || document.getElementById('pac-proxy-port');
    const cb = document.getElementById('pac-enabled');
    if (host) cfg.proxy_host = host.value.trim();
    if (port) {
      const p = parseInt(port.value, 10);
      if (!isNaN(p)) cfg.proxy_port = p;
    }
    if (cb) cfg.enabled = cb.checked;
  }

  function applySelectedIp(ip) {
    const host = document.getElementById('pac-proxy-host');
    if (host && ip) host.value = ip;
    persist(true);
  }

  function updateStatusBadge() {
    const badge = document.getElementById('pac-status-badge');
    const cb = document.getElementById('pac-enabled');
    if (!badge) return;
    if (cb && cb.checked) {
      badge.textContent = 'ON';
      badge.style.background = 'var(--success-bg)';
      badge.style.color = 'var(--success)';
    } else {
      badge.textContent = 'OFF';
      badge.style.background = 'var(--surface-raised)';
      badge.style.color = 'var(--text-muted)';
    }
  }

  function persist(showToast) {
    collectFromInputs();
    api.pacSave({
      enabled: cfg.enabled,
      proxy_host: cfg.proxy_host,
      proxy_port: cfg.proxy_port,
      direct_hosts: cfg.direct_hosts,
      internal_nets: cfg.internal_nets,
    }).then(res => {
      cfg = res;
      applyToDom(cfg);
      if (showToast) {
        const status = document.getElementById('pac-save-status');
        if (status) status.textContent = t('page.pac.saved');
        app.toast(t('page.pac.saved'));
      }
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function save() {
    persist(true);
  }

  function applyToDom(c) {
    const host = document.getElementById('pac-proxy-host');
    const port = document.getElementById('pac-proxy-port');
    const cb = document.getElementById('pac-enabled');
    const url = document.getElementById('pac-url');
    const preview = document.getElementById('pac-preview');
    if (host) host.value = c.proxy_host;
    if (port) port.value = c.proxy_port;
    if (cb) cb.checked = !!c.enabled;
    if (url) url.value = c.url || '';
    if (preview) preview.textContent = c.preview || '';
    renderDomainList();
    renderNetList();
    updateStatusBadge();
  }

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      cfg = await api.pacConfig();
      applyToDom(cfg);
    } catch (e) {
      console.error('pac load', e);
    } finally {
      _loading = false;
    }
  }

  build();
  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/proxies.js ==== */
router.register('proxies', (container) => {
  let groupBy = 'country';
  let statusFilter = 'alive';
  let search = '';
  let groups = [];
  let totalCount = 0;
  let _loading = false;
  let expandedKeys = {};
  let loadedKeys = {};

  let _built = false;

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '8px';
    container.style.minHeight = '0';
    container.style.flex = '1';
    container.style.overflow = 'hidden';

    const toolbar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });

    const groupTabs = ui.el('div', '', { id: 'group-tabs', style: 'display:flex;gap:0;border:1px solid var(--border);border-radius:var(--radius-xs);overflow:hidden' });
    const gBtn = (label, mode) => {
      const b = ui.el('button', '', { text: label, 'data-mode': mode, style: `padding:5px 12px;font-size:12px;border:none;cursor:pointer` });
      b.addEventListener('click', () => { groupBy = mode; expandedKeys = {}; loadedKeys = {}; _built = false; updateTabs(); load(); });
      return b;
    };
    groupTabs.appendChild(gBtn(t('page.proxies.byCountry'), 'country'));
    groupTabs.appendChild(gBtn(t('page.proxies.bySource'), 'source'));
    groupTabs.appendChild(gBtn(t('page.proxies.byProtocol'), 'protocol'));
    toolbar.appendChild(groupTabs);

    const statusTabs = ui.el('div', '', { id: 'status-tabs', style: 'display:flex;gap:0;border:1px solid var(--border);border-radius:var(--radius-xs);overflow:hidden' });
    const sBtn = (label, val) => {
      const b = ui.el('button', '', { text: label, 'data-val': val, style: `padding:5px 10px;font-size:12px;border:none;cursor:pointer` });
      b.addEventListener('click', () => { statusFilter = val; expandedKeys = {}; loadedKeys = {}; _built = false; updateTabs(); load(); });
      return b;
    };
    statusTabs.appendChild(sBtn(t('page.proxies.all'), ''));
    statusTabs.appendChild(sBtn(t('page.proxies.alive'), 'alive'));
    statusTabs.appendChild(sBtn(t('page.proxies.dead'), 'dead'));
    toolbar.appendChild(statusTabs);

    const searchInput = ui.el('input', '', { type: 'text', placeholder: t('page.proxies.searchPlaceholder'), value: search, style: 'padding:5px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:200px;flex:1' });
    searchInput.addEventListener('input', (e) => { search = e.target.value.toLowerCase(); renderGroups(); });
    toolbar.appendChild(searchInput);

    toolbar.appendChild(ui.el('div', '', { style: 'flex:1' }));
    const totalLabel = ui.el('div', '', { id: 'proxies-total-label', style: 'font-size:12px;color:var(--text-secondary)' });
    toolbar.appendChild(totalLabel);

    container.appendChild(toolbar);

    const listWrap = ui.el('div', '', { id: 'proxies-group-list', style: 'flex:1;min-height:0;overflow-y:auto;padding-right:4px' });
    container.appendChild(listWrap);
  }

  build();
  updateTabs();

  function updateTabs() {
    const gt = document.getElementById('group-tabs');
    if (gt) gt.querySelectorAll('button').forEach(b => {
      const active = b.dataset.mode === groupBy;
      b.style.background = active ? 'var(--accent)' : 'var(--surface)';
      b.style.color = active ? 'var(--bg)' : 'var(--text-primary)';
    });
    const st = document.getElementById('status-tabs');
    if (st) st.querySelectorAll('button').forEach(b => {
      const active = b.dataset.val === statusFilter;
      b.style.background = active ? 'var(--accent)' : 'var(--surface)';
      b.style.color = active ? 'var(--bg)' : 'var(--text-primary)';
    });
  }

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      const data = await api.proxies({ mode: 'grouped', group_by: groupBy, status: statusFilter });
      groups = data.groups || [];
      totalCount = data.total || 0;
      renderGroups();
    } catch (e) {
      console.error('proxies load', e);
    } finally {
      _loading = false;
    }
  }

  async function loadGroupProxies(key) {
    const body = document.getElementById('spoiler-body-' + key);
    if (!body) return;
    body.innerHTML = `<div style="padding:12px;color:var(--text-muted);font-size:12px">${t('common.loading')}</div>`;
    try {
      const data = await api.proxies({ mode: 'group-proxies', group_by: groupBy, group_key: key, status: statusFilter });
      const proxies = data.proxies || [];
      loadedKeys[key] = proxies;
      renderGroupBody(key, proxies);
    } catch (e) {
      body.innerHTML = `<div style="padding:12px;color:var(--danger);font-size:12px">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    }
  }

  function toggleGroup(key) {
    expandedKeys[key] = !expandedKeys[key];
    const body = document.getElementById('spoiler-body-' + key);
    const chevron = document.getElementById('spoiler-chevron-' + key);
    if (expandedKeys[key]) {
      if (body) body.style.display = 'block';
      if (chevron) chevron.textContent = '▼';
      if (!loadedKeys[key]) {
        loadGroupProxies(key);
      }
    } else {
      if (body) body.style.display = 'none';
      if (chevron) chevron.textContent = '▶';
    }
  }

  function pctBar(pct) {
    const color = pct >= 50 ? 'var(--success)' : pct >= 20 ? 'var(--warning)' : 'var(--danger)';
    return `<div style="display:inline-block;width:40px;height:6px;background:var(--border);border-radius:3px;vertical-align:middle;margin-left:6px"><div style="width:${pct}%;height:100%;background:${color};border-radius:3px"></div></div>`;
  }

  function renderProxyRow(p) {
    const statusColor = p.in_blacklist ? 'var(--danger)' : p.last_status === 'ok' ? 'var(--success)' : 'var(--danger)';
    const statusText = p.in_blacklist ? 'BL' : p.last_status === 'ok' ? 'OK' : 'FAIL';
    const proto = (p.protocol || 'http').toUpperCase();
    const ssl = p.ssl_supported ? '<span style="color:#06b6d4;font-weight:600;font-size:10px">SSL</span>' : '<span style="color:var(--text-muted);font-size:10px">—</span>';
    const lat = p.last_latency != null ? (p.last_latency < 1 ? (p.last_latency * 1000).toFixed(0) + 'ms' : p.last_latency.toFixed(2) + 's') : '—';
    const avg = p.latency_avg != null ? (p.latency_avg < 1 ? (p.latency_avg * 1000).toFixed(0) + 'ms' : p.latency_avg.toFixed(2) + 's') : '—';
    const speed = p.speed_avg ? p.speed_avg.toFixed(0) + 'KB/s' : '—';
    const succ = p.success_rate != null ? (p.success_rate * 100).toFixed(0) + '%' : '—';
    const up = (p.checks_ok || 0) + '/' + (p.checks_total || 0);
    const score = Math.round(p.score || 0);
    const flag = ui.flag(p.country_code);
    const favStar = p.is_favorite ? '<svg width="12" height="12" style="vertical-align:-2px;color:var(--warning);flex-shrink:0;width:12px;height:12px;margin-right:2px"><use href="#icon-star"/></svg>' : '<span style="width:14px;flex-shrink:0;display:inline-block"></span>';

    return [
      `<span class="proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="font-size:12px;font-family:monospace;color:var(--text-primary);cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${favStar}${ui.escHtml(p.address)}</span>`,
      `<span style="font-size:12px">${flag} ${ui.escHtml(p.country || '—')}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${proto}</span>`,
      ssl,
      `<span style="font-size:11px">${lat}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${avg}</span>`,
      `<span style="font-size:11px">${speed}</span>`,
      `<span style="font-size:11px">${succ}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${up}</span>`,
      `<span style="font-size:11px;font-weight:600">${score}</span>`,
      `<span style="color:${statusColor};font-weight:600;font-size:11px">${statusText}</span>`,
      `<span style="font-size:11px;color:var(--text-muted)">${ui.ago(p.last_check)}</span>`,
      `<button class="btn btn-xs btn-secondary" data-select-addr="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px" title="Use as upstream">Sel</button>`,
      `<button class="btn btn-xs btn-info" data-recheck-addr="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px;color:var(--info);border-color:var(--info)" title="Recheck proxy">↻</button>`,
      `<button class="btn btn-xs btn-danger" data-bl-addr="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px">BL</button>`,
    ];
  }

  function renderGroupBody(key, proxies) {
    const body = document.getElementById('spoiler-body-' + key);
    if (!body) return;
    body.innerHTML = '';

    let filtered = proxies;
    if (search) {
      filtered = proxies.filter(p =>
        (p.address || '').toLowerCase().includes(search) ||
        (p.country || '').toLowerCase().includes(search) ||
        (p.protocol || '').toLowerCase().includes(search) ||
        (p.ssl_supported ? 'ssl' : '').includes(search)
      );
    }

    if (!filtered.length) {
      body.innerHTML = `<div style="padding:8px;color:var(--text-muted);font-size:12px">${t('page.proxies.noMatching')}</div>`;
      return;
    }

    const sorted = filtered.slice().sort((a, b) => (b.score || 0) - (a.score || 0));
    const tblWrap = ui.el('div', 'table-wrap', { style: 'max-height:400px;overflow-y:auto' });
    const headers = [
      { label: 'Proxy', width: null },
      { label: 'Country', width: '110px' },
      { label: 'Proto', width: '50px', align: 'center' },
      { label: 'SSL', width: '36px', align: 'center' },
      { label: 'Lat', width: '50px', align: 'right' },
      { label: 'Avg', width: '50px', align: 'right' },
      { label: 'Speed', width: '55px', align: 'right' },
      { label: 'Succ', width: '40px', align: 'right' },
      { label: 'Up', width: '45px', align: 'right' },
      { label: 'Score', width: '40px', align: 'right' },
      { label: 'Status', width: '45px', align: 'center' },
      { label: 'Last', width: '55px', align: 'right' },
      { label: '', width: '28px', align: 'center' },
      { label: '', width: '28px', align: 'center' },
      { label: '', width: '28px', align: 'center' },
    ];
    const rows = sorted.map(p => renderProxyRow(p));
    tblWrap.appendChild(ui.table(headers, rows));
    body.appendChild(tblWrap);

    body.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });

    body.querySelectorAll('[data-bl-addr]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.blAddr;
        if (addr) blAdd(addr);
      });
    });

    body.querySelectorAll('[data-select-addr]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.selectAddr;
        if (!addr) return;
        btn.disabled = true;
        btn.textContent = '...';
        api.proxySelect(addr).then(async () => {
          app.toast(t('page.proxyPool.selected', {addr: addr}));
          try {
            const ps = await api.proxyStatus();
            if (!ps || !ps.running) {
              const port = ps && ps.port ? ps.port : 8080;
              await api.proxyStart(port);
              app.toast(t('page.overview.proxyStarted'));
            }
          } catch (startErr) {
            console.error('proxy start', startErr);
          }
          btn.disabled = false;
          btn.textContent = 'Sel';
        }).catch(er => {
          btn.disabled = false;
          btn.textContent = 'Sel';
          app.toast(t('common.error', {message: er.message}), 'error');
        });
      });
    });

    body.querySelectorAll('[data-recheck-addr]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.recheckAddr;
        if (!addr) return;
        btn.disabled = true;
        btn.textContent = '...';
        api.proxyRecheck(addr).then(() => {
          btn.disabled = false;
          btn.textContent = '↻';
          app.toast(t('page.proxies.recheckComplete'));
          loadGroupProxies(key);
        }).catch(er => {
          btn.disabled = false;
          btn.textContent = '↻';
          app.toast(t('common.error', {message: er.message}), 'error');
        });
      });
    });
  }

  function renderGroups() {
    const totalLabel = document.getElementById('proxies-total-label');
    if (totalLabel) totalLabel.textContent = t('page.proxies.totalProxies', {count: totalCount});

    const listWrap = document.getElementById('proxies-group-list');
    if (!listWrap) return;

    let filtered = groups;
    if (search) {
      filtered = groups.filter(g => g.label.toLowerCase().includes(search));
    }

    if (!filtered.length) {
      listWrap.innerHTML = '';
      listWrap.appendChild(ui.el('div', 'empty', { text: t('page.proxies.noProxiesFound') }));
      _built = false;
      return;
    }

    const existingKeys = new Set();
    listWrap.querySelectorAll('[data-group-key]').forEach(el => existingKeys.add(el.dataset.groupKey));

    const filteredKeys = new Set(filtered.map(g => g.key));

    if (_built && existingKeys.size === filteredKeys.size && filtered.every(g => existingKeys.has(g.key))) {
      filtered.forEach(g => updateGroupHeader(g));
      return;
    }

    _built = true;
    listWrap.innerHTML = '';

    filtered.forEach(g => {
      const isExpanded = !!expandedKeys[g.key];
      const spoiler = ui.el('div', '', { style: 'border:1px solid var(--border);border-radius:var(--radius-xs);overflow:hidden;margin-bottom:6px', 'data-group-key': g.key });

      const header = ui.el('div', '', {
        id: 'spoiler-header-' + g.key,
        style: `display:flex;align-items:center;gap:8px;padding:8px 12px;cursor:pointer;background:var(--surface);user-select:none;transition:background 0.15s`
      });
      header.addEventListener('mouseenter', () => header.style.background = 'var(--surface-raised)');
      header.addEventListener('mouseleave', () => header.style.background = 'var(--surface)');
      header.addEventListener('click', () => toggleGroup(g.key));

      const chevron = ui.el('span', '', { id: 'spoiler-chevron-' + g.key, text: isExpanded ? '▼' : '▶', style: 'font-size:10px;color:var(--text-muted);width:14px;flex-shrink:0' });
      header.appendChild(chevron);

      const label = ui.el('span', '', { html: g.label, style: 'font-size:13px;font-weight:500;color:var(--text-primary);flex-shrink:0;max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap' });
      header.appendChild(label);

      const countBadge = ui.el('span', '', { id: 'spoiler-count-' + g.key, html: countHtml(g), style: 'font-size:12px;flex-shrink:0' });
      header.appendChild(countBadge);

      const pctLabel = ui.el('span', '', { id: 'spoiler-pct-' + g.key, html: pctHtml(g), style: 'flex-shrink:0' });
      header.appendChild(pctLabel);

      header.appendChild(ui.el('div', '', { style: 'flex:1' }));

      const deadLabel = ui.el('span', '', { id: 'spoiler-dead-' + g.key, html: deadHtml(g), style: 'flex-shrink:0' });
      header.appendChild(deadLabel);

      spoiler.appendChild(header);

      const body = ui.el('div', '', {
        id: 'spoiler-body-' + g.key,
        style: `display:${isExpanded ? 'block' : 'none'};border-top:1px solid var(--border)`
      });

      if (isExpanded && loadedKeys[g.key]) {
        renderGroupBody(g.key, loadedKeys[g.key]);
      } else if (isExpanded) {
        body.innerHTML = `<div style="padding:12px;color:var(--text-muted);font-size:12px">${t('common.loading')}</div>`;
      }

      spoiler.appendChild(body);
      listWrap.appendChild(spoiler);
    });
  }

  function countHtml(g) {
    return `<span style="color:var(--success);font-weight:600">${g.alive}</span><span style="color:var(--text-muted)">/</span><span style="color:var(--text-primary)">${g.total}</span>`;
  }

  function pctHtml(g) {
    const color = g.alive_pct >= 50 ? 'var(--success)' : g.alive_pct >= 20 ? 'var(--warning)' : 'var(--danger)';
    return `<span style="color:${color};font-weight:600;font-size:12px">${g.alive_pct}%</span>${pctBar(g.alive_pct)}`;
  }

  function deadHtml(g) {
    return `<span style="color:var(--danger);font-size:11px">${t('page.proxies.deadCount', {count: g.dead})}</span>`;
  }

  function updateGroupHeader(g) {
    const count = document.getElementById('spoiler-count-' + g.key);
    const pct = document.getElementById('spoiler-pct-' + g.key);
    const dead = document.getElementById('spoiler-dead-' + g.key);
    if (count) count.innerHTML = countHtml(g);
    if (pct) pct.innerHTML = pctHtml(g);
    if (dead) dead.innerHTML = deadHtml(g);
  }

  async function blAdd(addr) {
    try {
      await api.blAdd(addr, 'manual');
      app.toast(t('page.proxies.addedToBlacklist'));
    } catch (e) {
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  load();
  const id = setInterval(load, 15000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/proxy-card.js ==== */
const proxyCard = {
  async show(addr) {
    const overlay = ui.el('div', 'proxy-card-overlay', {
      style: 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center;overflow:auto;'
    });
    const modal = ui.el('div', 'proxy-card');
    modal.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t('common.loading')}</div>`;
    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);

    try {
      const p = await api.proxyDetail(addr);
      let checksData = null;
      try { checksData = await api.proxyChecks(addr, 30); } catch (e) { checksData = { checks: [], p95: 0, max_speed: 0, errors: 0, count: 0 }; }
      this._render(modal, p, checksData, overlay);
      const fs = typeof p.fraud_score === 'number' ? p.fraud_score : -1;
      if (fs < 0) setTimeout(() => this._fraudCheck(addr), 500);
    } catch (e) {
      modal.innerHTML = `<div style="padding:40px;color:var(--danger)">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    }
  },

  _render(modal, p, checksData, overlay) {
    modal.innerHTML = '';
    this._modal = modal;
    this._overlay = overlay;

    modal.appendChild(this._topBar(p, overlay));

    const content = ui.el('div', 'content');
    modal.appendChild(content);

    content.appendChild(this._hero(p));
    content.appendChild(this._securityBadges(p));

    const midGrid = ui.el('div', 'proxy-card-grid-3');
    midGrid.appendChild(this._performance(p, checksData));
    midGrid.appendChild(this._security(p));
    midGrid.appendChild(this._network(p));
    content.appendChild(midGrid);

    const bottomGrid = ui.el('div', 'proxy-card-grid-2');
    bottomGrid.appendChild(this._timeline(p));
    bottomGrid.appendChild(this._suitability(p));
    content.appendChild(bottomGrid);

    content.appendChild(this._scoreBreakdown(p));

    modal.appendChild(this._actions(p, overlay));
  },

  _refresh(modal, addr, overlay) {
    modal.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t('common.loading')}</div>`;
    Promise.all([
      api.proxyDetail(addr),
      api.proxyChecks(addr, 30).catch(() => ({ checks: [], p95: 0, max_speed: 0, errors: 0, count: 0 })),
    ]).then(([p, checksData]) => {
      this._render(modal, p, checksData, overlay);
    }).catch(e => {
      modal.innerHTML = `<div style="padding:40px;color:var(--danger)">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    });
  },

  _topBar(p, overlay) {
    const bar = ui.el('div', 'topbar');
    bar.appendChild(ui.el('div', 'topbar-title', { text: t('proxyCard.title') }));
    const closeBtn = ui.el('button', 'btn btn-sm btn-ghost', { html: '×', style: 'font-size:22px;line-height:1;padding:0 6px' });
    closeBtn.addEventListener('click', () => overlay.remove());
    bar.appendChild(closeBtn);
    return bar;
  },

  _hero(p) {
    const score = Math.round(p.score || 0);
    const scoreColor = score >= 60 ? 'var(--success)' : score >= 30 ? 'var(--warning)' : 'var(--danger)';
    const status = this._status(p);
    const flag = ui.flag(p.country_code);
    const location = [p.country, p.city].filter(Boolean).join(', ') || '—';
    const isp = p.isp || p.listen_isp || p.egress_isp || '';
    const asn = p.asn || '';

    const wrap = ui.el('div', 'proxy-card-hero');

    const main = ui.el('div', 'proxy-card-hero-main');

    const statusRow = ui.el('div', 'proxy-card-hero-status-row');
    statusRow.appendChild(ui.el('div', `proxy-card-status ${status.cls}`, { text: status.label }));
    main.appendChild(statusRow);

    const addrRow = ui.el('div', 'proxy-card-hero-addr-row');
    addrRow.appendChild(ui.el('div', 'proxy-card-address', { text: p.address }));
    const copyBtn = ui.el('button', 'proxy-card-copy-btn', { html: this._svg('copy') });
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(p.address).then(() => app.toast(t('proxyCard.copied'))).catch(() => {});
    });
    addrRow.appendChild(copyBtn);
    main.appendChild(addrRow);

    const meta = ui.el('div', 'proxy-card-hero-meta');
    if (flag) meta.appendChild(ui.el('span', 'flag', { text: flag }));
    meta.appendChild(ui.el('span', '', { text: location }));
    if (asn) {
      meta.appendChild(ui.el('span', 'dot', { text: '•' }));
      meta.appendChild(ui.el('span', '', { text: asn }));
    }
    if (isp) {
      meta.appendChild(ui.el('span', 'dot', { text: '•' }));
      meta.appendChild(ui.el('span', '', { text: isp }));
    }
    if (p.protocol === 'http' && !p.ssl_supported) {
      meta.appendChild(ui.el('span', 'proxy-card-type-badge', { text: t('proxyCard.publicProxy') }));
    }
    main.appendChild(meta);

    const checkRow = ui.el('div', 'proxy-card-hero-check-row');
    if (p.last_check) {
      checkRow.appendChild(ui.el('span', '', { html: `${this._svg('check-circle')} ${t('proxyCard.checkedAgo')} ${ui.ago(p.last_check)}` }));
    }
    main.appendChild(checkRow);

    wrap.appendChild(main);

    const rating = ui.el('div', 'proxy-card-rating');
    rating.appendChild(ui.el('div', 'proxy-card-rating-label', { text: t('proxyCard.rating') }));
    const valWrap = ui.el('div', 'proxy-card-rating-value-wrap');
    valWrap.appendChild(ui.el('div', 'proxy-card-rating-value', { text: String(score), style: `color:${scoreColor}` }));
    valWrap.appendChild(ui.el('div', 'proxy-card-rating-max', { text: '/100' }));
    rating.appendChild(valWrap);
    const desc = score >= 60 ? t('proxyCard.ratingGood') : score >= 30 ? t('proxyCard.ratingAvg') : t('proxyCard.ratingBad');
    rating.appendChild(ui.el('div', 'proxy-card-rating-desc', { text: desc }));
    const bar = ui.el('div', 'proxy-card-rating-bar');
    const segments = 10;
    for (let i = 0; i < segments; i++) {
      const seg = ui.el('div', 'proxy-card-rating-segment');
      if (score >= (i + 1) * 10) {
        seg.style.background = scoreColor;
      }
      bar.appendChild(seg);
    }
    rating.appendChild(bar);
    wrap.appendChild(rating);

    return wrap;
  },

  _securityBadges(p) {
    const row = ui.el('div', 'proxy-card-security-badges');

    const httpsBadge = ui.el('div', `proxy-card-sec-badge ${p.ssl_supported ? 'good' : 'bad'}`);
    httpsBadge.innerHTML = `${this._svg('lock')} HTTPS`;
    row.appendChild(httpsBadge);

    if (p.ssl_supported) {
      const sslBadge = ui.el('div', 'proxy-card-sec-badge good');
      sslBadge.innerHTML = `${this._svg('lock')} SSL`;
      row.appendChild(sslBadge);
    }

    const connectBadge = ui.el('div', `proxy-card-sec-badge ${p.supports_connect ? 'good' : 'bad'}`);
    connectBadge.innerHTML = `${this._svg('link')} CONNECT`;
    row.appendChild(connectBadge);

    const mitmBadge = ui.el('div', `proxy-card-sec-badge ${!p.mitm_suspect ? 'good' : 'bad'}`);
    mitmBadge.innerHTML = `${this._svg('shield-check')} MITM ${!p.mitm_suspect ? t('proxyCard.notDetected') : t('proxyCard.suspected')}`;
    row.appendChild(mitmBadge);

    return row;
  },

  _status(p) {
    if (p.in_blacklist) return { cls: 'bad', label: t('proxyCard.status.blocked') };
    if (p.last_status !== 'ok') return { cls: 'bad', label: t('proxyCard.status.unstable') };
    if (p.mitm_suspect) return { cls: 'warn', label: t('proxyCard.status.degraded') };
    if ((p.success_rate || 0) < 0.8) return { cls: 'warn', label: t('proxyCard.status.degraded') };
    return { cls: 'good', label: t('proxyCard.status.ready') };
  },

  _performance(p, checksData) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.performance'), this._svg('bar-chart')));

    const grid = ui.el('div', 'proxy-card-kpi-grid');

    const checks = checksData || { checks: [], p95: 0, max_speed: 0, avg_speed: 0, avg_latency: 0, success_rate: 0, errors: 0, count: 0 };
    const checkList = checks.checks || [];

    const avgLat = checks.avg_latency || p.latency_avg || 0;
    const lastLat = p.last_latency || 0;
    const latValue = avgLat ? ui.fmtLatency(avgLat) : ui.fmtLatency(lastLat);
    grid.appendChild(this._kpiWithSpark(latValue, t('proxyCard.avgLatency'), 's',
      this._sparklinePoints(checkList, 'latency'), 'var(--success)',
      `${t('proxyCard.p95')} ${checks.p95 ? ui.fmtLatency(checks.p95) : '—'}`));

    const speed = checks.avg_speed || p.speed_avg || 0;
    const speedValue = speed ? speed.toFixed(0) : t('proxyCard.notMeasured');
    grid.appendChild(this._kpiWithSpark(speedValue, t('proxyCard.avgSpeed'), speed ? 'KB/s' : '',
      this._sparklinePoints(checkList, 'speed'), 'var(--accent)',
      `${t('proxyCard.maxSpeed')} ${checks.max_speed ? checks.max_speed.toFixed(0) + ' KB/s' : '—'}`,
      speed ? 'var(--text-primary)' : 'var(--danger)'));

    const sr = checks.success_rate || p.success_rate || 0;
    const srPct = Math.round(sr * 100);
    grid.appendChild(this._kpiWithSpark(srPct + '%', t('proxyCard.successRate'), '',
      this._sparklineSuccessPoints(checkList), 'var(--success)',
      `${t('proxyCard.lastChecks', { count: checks.count || 0 })}`));

    const totalChecks = (p.checks_total || 0);
    const checksOk = (p.checks_ok || 0);
    grid.appendChild(this._kpiWithSpark(`${checksOk}/${totalChecks}`, t('proxyCard.checks'), '',
      this._sparklineOkPoints(checkList), 'var(--success)',
      `${t('proxyCard.errors')} ${checks.errors || 0}`));

    section.appendChild(grid);

    if (checkList.length >= 1) {
      section.appendChild(this._checkHistory24h(checkList));
    }

    return section;
  },

  _checkHistory24h(checkList) {
    const now = Date.now() / 1000;
    const hours = 72;
    const cutoff = now - hours * 3600;
    const segments = 72;
    const segDur = (hours * 3600) / segments;
    const buckets = new Array(segments).fill(null);

    for (const c of checkList) {
      if (c.ts < cutoff) continue;
      const idx = Math.floor((c.ts - cutoff) / segDur);
      if (idx >= 0 && idx < segments) {
        if (buckets[idx] === null) {
          buckets[idx] = c.ok ? 'ok' : 'err';
        } else if (buckets[idx] === 'ok' && !c.ok) {
          buckets[idx] = 'err';
        }
      }
    }

    const wrap = ui.el('div', 'proxy-card-checkhist');

    const bar = ui.el('div', 'proxy-card-checkhist-bar');
    for (let i = 0; i < segments; i++) {
      const seg = ui.el('div', `proxy-card-checkhist-seg ${buckets[i] || 'none'}`);
      bar.appendChild(seg);
    }
    wrap.appendChild(bar);

    const legend = ui.el('div', 'proxy-card-checkhist-legend');
    legend.appendChild(this._legendDot('ok', t('proxyCard.legendOk')));
    legend.appendChild(this._legendDot('none', t('proxyCard.legendNone')));
    legend.appendChild(this._legendDot('err', t('proxyCard.legendErr')));
    wrap.appendChild(legend);

    const axis = ui.el('div', 'proxy-card-checkhist-axis');
    axis.appendChild(ui.el('span', '', { text: t('proxyCard.h72ago') }));
    axis.appendChild(ui.el('span', '', { text: t('proxyCard.h36ago') }));
    axis.appendChild(ui.el('span', '', { text: t('proxyCard.now') }));
    wrap.appendChild(axis);

    return wrap;
  },

  _legendDot(cls, label) {
    const item = ui.el('div', 'proxy-card-checkhist-legend-item');
    item.appendChild(ui.el('span', `proxy-card-checkhist-dot ${cls}`));
    item.appendChild(ui.el('span', '', { text: label }));
    return item;
  },

  _sparklinePoints(checks, field) {
    return checks.map(c => c[field] || 0).filter(v => v > 0);
  },

  _sparklineSuccessPoints(checks) {
    if (!checks.length) return [];
    const result = [];
    for (let i = 0; i < checks.length; i++) {
      const ok = checks[i].ok ? 1 : 0;
      const win = checks.slice(Math.max(0, i - 4), i + 1);
      result.push(win.reduce((a, c) => a + (c.ok ? 1 : 0), 0) / win.length);
    }
    return result;
  },

  _sparklineOkPoints(checks) {
    return checks.map(c => c.ok ? 1 : 0);
  },

  _kpiWithSpark(value, label, unit, points, color, sub, valueColor) {
    const kpi = ui.el('div', 'proxy-card-kpi');
    const valStyle = valueColor ? `style="color:${valueColor}"` : '';
    const val = ui.el('div', 'proxy-card-kpi-value', { html: `${ui.escHtml(String(value))}${unit ? `<small>${ui.escHtml(unit)}</small>` : ''}`, style: valStyle || undefined });
    kpi.appendChild(val);
    kpi.appendChild(ui.el('div', 'proxy-card-kpi-label', { text: label }));
    if (points && points.length >= 2) {
      kpi.appendChild(this._sparklineSvg(points, color));
    }
    if (sub) {
      kpi.appendChild(ui.el('div', 'proxy-card-kpi-sub', { text: sub }));
    }
    return kpi;
  },

  _sparklineSvg(points, color) {
    const w = 100, h = 28;
    const min = Math.min(...points, 0);
    const max = Math.max(...points, 0.001);
    const range = max - min || 1;
    const n = points.length;
    const stepX = w / (n - 1);
    const coords = points.map((v, i) => {
      const x = i * stepX;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
    const linePath = `M${coords.join(' L')}`;
    const areaPath = `M0,${h} L${coords.join(' L')} L${w},${h} Z`;
    const svg = `<svg class="proxy-card-sparkline" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><path class="area" d="${areaPath}" style="fill:${color}"/><path d="${linePath}" style="stroke:${color}"/></svg>`;
    const wrap = ui.el('div', 'proxy-card-sparkline-wrap', { html: svg });
    return wrap;
  },

  _kpi(value, label, unit = '') {
    const kpi = ui.el('div', 'proxy-card-kpi');
    const val = ui.el('div', 'proxy-card-kpi-value', { html: `${ui.escHtml(String(value))}${unit ? `<small>${ui.escHtml(unit)}</small>` : ''}` });
    kpi.appendChild(val);
    kpi.appendChild(ui.el('div', 'proxy-card-kpi-label', { text: label }));
    return kpi;
  },

  _security(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.security'), this._svg('shield')));

    const list = ui.el('div', 'proxy-card-checklist');
    list.appendChild(this._checkRow('HTTPS (TLS)', p.ssl_supported, p.ssl_supported ? t('proxyCard.supported') : t('proxyCard.notSupported'), p.ssl_supported ? 'good' : 'bad'));
    list.appendChild(this._checkRow(t('proxyCard.sslPassthrough'), p.ssl_supported, p.ssl_supported ? t('common.yes') : t('common.no'), p.ssl_supported ? 'good' : 'muted'));
    list.appendChild(this._checkRow('CONNECT', p.supports_connect, p.supports_connect ? t('common.yes') : t('common.no'), p.supports_connect ? 'good' : 'muted'));
    list.appendChild(this._checkRow('MITM', !p.mitm_suspect, p.mitm_suspect ? t('proxyCard.suspected') : t('proxyCard.notDetected'), p.mitm_suspect ? 'bad' : 'good'));

    section.appendChild(list);
    return section;
  },

  _checkRow(label, ok, valueText, cls) {
    const row = ui.el('div', `proxy-card-check ${cls}`);
    const icon = cls === 'good' ? this._svg('check') : cls === 'bad' ? this._svg('x') : cls === 'warn' ? this._svg('alert') : this._svg('minus');
    const labelEl = ui.el('div', 'proxy-card-check-label', { html: `${icon} <span>${label}</span>` });
    row.appendChild(labelEl);
    row.appendChild(ui.el('div', `proxy-card-check-value ${cls}`, { text: valueText }));
    return row;
  },

  _network(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.route'), this._svg('map-pin')));

    const route = ui.el('div', 'proxy-card-route-vertical');

    const listenCountry = p.listen_country || p.country || '';
    const listenCity = p.listen_city || p.city || '';
    const listenIp = p.address ? p.address.split(':')[0] : '—';
    const egressCountry = p.egress_country || p.country || '';
    const egressCity = p.egress_city || p.city || '';
    const egressIp = p.egress_ip || listenIp;

    const listenPoint = ui.el('div', 'proxy-card-route-vpoint');
    listenPoint.appendChild(ui.el('div', 'proxy-card-route-vdot good'));
    const listenContent = ui.el('div', 'proxy-card-route-vcontent');
    listenContent.appendChild(ui.el('div', 'proxy-card-route-vlabel', { text: t('proxyCard.listen') }));
    const listenLoc = ui.el('div', 'proxy-card-route-vlocation');
    if (p.listen_country_code || p.country_code) listenLoc.appendChild(ui.el('span', 'flag', { text: ui.flag(p.listen_country_code || p.country_code) }));
    listenLoc.appendChild(ui.el('span', '', { text: [listenCountry, listenCity].filter(Boolean).join(', ') || '—' }));
    listenContent.appendChild(listenLoc);
    listenContent.appendChild(ui.el('div', 'proxy-card-route-vip', { text: listenIp }));
    listenPoint.appendChild(listenContent);
    route.appendChild(listenPoint);

    const arrow = ui.el('div', 'proxy-card-route-varrow');
    route.appendChild(arrow);

    const egressPoint = ui.el('div', 'proxy-card-route-vpoint');
    egressPoint.appendChild(ui.el('div', 'proxy-card-route-vdot good'));
    const egressContent = ui.el('div', 'proxy-card-route-vcontent');
    egressContent.appendChild(ui.el('div', 'proxy-card-route-vlabel', { text: t('proxyCard.egress') }));
    const egressLoc = ui.el('div', 'proxy-card-route-vlocation');
    if (p.egress_country_code || p.country_code) egressLoc.appendChild(ui.el('span', 'flag', { text: ui.flag(p.egress_country_code || p.country_code) }));
    egressLoc.appendChild(ui.el('span', '', { text: [egressCountry, egressCity].filter(Boolean).join(', ') || '—' }));
    egressContent.appendChild(egressLoc);
    egressContent.appendChild(ui.el('div', 'proxy-card-route-vip', { text: egressIp }));
    egressPoint.appendChild(egressContent);
    route.appendChild(egressPoint);

    section.appendChild(route);

    const details = ui.el('div', 'proxy-card-route-details');
    const isp = p.listen_isp || p.egress_isp || p.isp || '';
    const asn = p.asn || '';
    if (asn) {
      details.appendChild(this._routeDetail('ASN', asn + (isp ? ' ' + isp : '')));
    } else if (isp) {
      details.appendChild(this._routeDetail(t('proxyCard.isp'), isp));
    }
    const fv = p.fraud_verdict || 'FAILCHECK';
    const fs = typeof p.fraud_score === 'number' ? p.fraud_score : null;
    const fraudRow = ui.el('div', 'proxy-card-route-detail');
    fraudRow.appendChild(ui.el('div', 'proxy-card-route-detail-key', { text: 'Fraud' }));
    const valWrap = ui.el('div', 'proxy-card-route-detail-val');
    valWrap.style.cssText = 'display:flex;align-items:center;justify-content:flex-end;gap:6px;min-width:0';
    {
      const flags = `hosting ${p.fraud_hosting ? 'yes' : 'no'} · proxy ${p.fraud_proxy ? 'yes' : 'no'} · mobile ${p.fraud_mobile ? 'yes' : 'no'}`;
      if (p.fraud_failcheck || fs === null) {
        const badge = ui.el('span', '', { text: 'FAILCHECK' });
        badge.style.cssText = 'color:var(--text-muted);font-weight:700;white-space:nowrap';
        badge.title = `no fresh proxycheck measurement — worst case assumed (${flags})`;
        valWrap.appendChild(badge);
      } else {
        const fColor = fv === 'CLEAN' ? '#22c55e' : fv === 'MOBILE' ? '#3b82f6' : fv === 'DC' ? '#f59e0b' : '#ef4444';
        const badge = ui.el('span', '', { text: `${fs}/100` });
        badge.style.cssText = `color:${fColor};font-weight:700;white-space:nowrap`;
        const pc = (typeof p.fraud_score_raw === 'number' && p.fraud_score_raw >= 0) ? ` · proxycheck ${p.fraud_score_raw}` : '';
        badge.title = `${fv}: ${fs}/100 · ${flags}${pc}`;
        valWrap.appendChild(badge);
      }
      if (p.fraud_checked_ts) {
        valWrap.appendChild(ui.el('span', '', { text: ui.ago(p.fraud_checked_ts), style: 'color:var(--text-muted);font-size:9px;white-space:nowrap' }));
      }
      details.appendChild(fraudRow);
      details.appendChild(this._routeDetail('Fraud flags', `hosting ${p.fraud_hosting ? 'yes' : 'no'} · proxy ${p.fraud_proxy ? 'yes' : 'no'} · mobile ${p.fraud_mobile ? 'yes' : 'no'}`));
    }
    const btn = ui.el('button', 'btn btn-xs btn-secondary', { text: '↻ Re-check' });
    btn.style.cssText = 'padding:1px 6px;font-size:9px;flex:none';
    btn.addEventListener('click', () => this._fraudCheck(p.address, true));
    valWrap.appendChild(btn);
    fraudRow.appendChild(valWrap);
    section.appendChild(details);

    return section;
  },

  _routeDetail(key, value) {
    const row = ui.el('div', 'proxy-card-route-detail');
    row.appendChild(ui.el('div', 'proxy-card-route-detail-key', { text: key }));
    row.appendChild(ui.el('div', 'proxy-card-route-detail-val', { text: value }));
    return row;
  },

  async _fraudCheck(addr, force = false) {
    try {
      await api.proxyFraud(addr, force);
    } catch (e) {
      app.toast(t('common.error', { message: e.message }), 'error');
    }
    if (this._modal) this._refresh(this._modal, addr, this._overlay);
  },

  _timeline(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.timeline'), this._svg('clock')));

    const list = ui.el('div', 'proxy-card-timeline');
    list.appendChild(this._timelineItem(t('proxyCard.discovered'), p.first_seen, 'accent'));
    list.appendChild(this._timelineItem(t('proxyCard.lastCheck'), p.last_check, p.last_status === 'ok' ? 'ok' : 'bad'));
    list.appendChild(this._timelineItem(t('proxyCard.lastOk'), p.last_ok, 'ok'));
    section.appendChild(list);
    return section;
  },

  _timelineItem(label, ts, dotCls) {
    const item = ui.el('div', 'proxy-card-timeline-item');
    item.appendChild(ui.el('div', `proxy-card-timeline-dot ${dotCls}`));
    const text = ui.el('div', 'proxy-card-timeline-text');
    text.appendChild(ui.el('div', 'proxy-card-timeline-label', { text: label }));
    text.appendChild(ui.el('div', 'proxy-card-timeline-time', { text: ts ? ui.ago(ts) : '—' }));
    item.appendChild(text);
    return item;
  },

  _suitability(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.sourcesTitle'), this._svg('layers')));

    const sourceIds = p.source_ids || [];
    const sourcesTotal = p.sources_total || 0;
    const found = sourceIds.length;
    const foundPct = sourcesTotal ? Math.round((found / sourcesTotal) * 100) : 0;
    const foundColor = found >= 5 ? 'var(--success)' : found >= 2 ? 'var(--warning)' : 'var(--danger)';

    const blHits = p.ip_blacklist_hits || 0;
    const blTotal = p.ip_blacklist_sources_total || 0;
    const blPct = blTotal ? Math.round((blHits / blTotal) * 100) : 0;
    const blColor = blHits === 0 ? 'var(--success)' : blHits <= 2 ? 'var(--warning)' : 'var(--danger)';

    const wrap = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:clamp(10px,1.5cqi,16px)' });

    const foundRow = this._sourceBar(t('proxyCard.foundInSources', { found, total: sourcesTotal }), `${found}/${sourcesTotal}`, foundPct, foundColor, t('proxyCard.moreIsBetter'));
    wrap.appendChild(foundRow);

    const blRow = this._sourceBar(t('proxyCard.ipBlHits', { hits: blHits, total: blTotal }), `${blHits}/${blTotal}`, blPct, blColor, t('proxyCard.lessIsBetter'));
    wrap.appendChild(blRow);

    section.appendChild(wrap);
    return section;
  },

  _sourceBar(label, value, pct, color, hint) {
    const item = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:clamp(3px,0.4cqi,6px);min-width:0' });
    const header = ui.el('div', '', { style: 'display:flex;justify-content:space-between;align-items:center;gap:8px;min-width:0' });
    header.appendChild(ui.el('div', '', { style: 'font-size:clamp(10px,1.1cqi,12px);color:var(--text-secondary);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: label }));
    header.appendChild(ui.el('div', '', { style: `font-size:clamp(12px,1.4cqi,15px);font-weight:700;color:${color};flex-shrink:0`, text: value }));
    item.appendChild(header);
    const bar = ui.el('div', '', { style: 'height:clamp(4px,0.6cqi,6px);background:var(--surface);border-radius:3px;overflow:hidden' });
    bar.appendChild(ui.el('div', '', { style: `width:${pct}%;height:100%;background:${color};border-radius:3px;transition:width 0.4s ease` }));
    item.appendChild(bar);
    item.appendChild(ui.el('div', '', { style: 'font-size:clamp(8px,0.9cqi,10px);color:var(--text-muted)', text: hint }));
    return item;
  },

  _scoreBreakdown(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.scoreBreakdown'), this._svg('bar-chart')));

    const bd = p.score_breakdown;
    if (!bd || !Array.isArray(bd.base)) {
      section.appendChild(ui.el('div', 'proxy-card-rating-hint', { text: t('proxyCard.ratingHint') }));
      return section;
    }
    const LABELS = {
      reliability: t('proxyCard.reliabilityScore'),
      latency: t('proxyCard.latencyScore'),
      speed: t('proxyCard.speedScore'),
      ssl: 'SSL', connect: 'CONNECT', socks: 'SOCKS',
      fraud: t('proxyCard.fraudFactor'),
      mitm: 'MITM',
      ipbl: t('proxyCard.ipblFactor'),
      grace: 'GRACE',
    };

    const grid = ui.el('div', 'proxy-card-score-hgrid');
    bd.base.forEach(c => {
      const pct = Math.max(0, Math.min(100, (c.value / c.max) * 100));
      const item = ui.el('div', 'proxy-card-score-hitem');
      const header = ui.el('div', 'proxy-card-score-hheader');
      header.appendChild(ui.el('div', 'proxy-card-score-hlabel', { text: LABELS[c.key] || c.key }));
      header.appendChild(ui.el('div', 'proxy-card-score-hvalue', { text: `${c.value > 0 ? '+' : ''}${c.value.toFixed(1)}`, style: `color:${c.value > 0 ? 'var(--success)' : 'var(--text-muted)'}` }));
      item.appendChild(header);
      const bar = ui.el('div', 'proxy-card-score-hbar');
      bar.appendChild(ui.el('div', '', { style: `width:${pct}%;background:${c.value > 0 ? 'var(--success)' : 'var(--text-muted)'}` }));
      item.appendChild(bar);
      item.appendChild(ui.el('div', 'proxy-card-score-hmax', { text: `${c.value.toFixed(1)} / ${c.max}` }));
      grid.appendChild(item);
    });
    section.appendChild(grid);

    const mults = Array.isArray(bd.multipliers) ? bd.multipliers : [];
    const modRow = ui.el('div', 'proxy-card-score-hgrid');
    mults.forEach(m => {
      const item = ui.el('div', 'proxy-card-score-hitem');
      const header = ui.el('div', 'proxy-card-score-hheader');
      header.appendChild(ui.el('div', 'proxy-card-score-hlabel', { text: LABELS[m.key] || m.key }));
      const dim = m.factor === 1 && !m.note;
      const color = dim ? 'var(--text-muted)' : (m.factor < 1 ? 'var(--danger)' : m.factor > 1 ? 'var(--success)' : 'var(--text-muted)');
      header.appendChild(ui.el('div', 'proxy-card-score-hvalue', { text: `×${Number(m.factor).toFixed(2)}`, style: `color:${color}` }));
      item.appendChild(header);
      if (m.note) item.appendChild(ui.el('div', 'proxy-card-score-hmax', { text: m.note }));
      modRow.appendChild(item);
    });
    section.appendChild(modRow);

    const parts = bd.base.map(c => c.value.toFixed(1));
    const multParts = mults.map(m => `×${Number(m.factor).toFixed(2)}`);
    const formula = `(${parts.join(' + ')}) ${multParts.join(' ')} = ${Number(bd.final).toFixed(1)}`;
    section.appendChild(ui.el('div', 'proxy-card-score-formula', { text: formula }));

    const total = Math.round(bd.final || 0);
    const totalRow = ui.el('div', 'proxy-card-score-total');
    totalRow.appendChild(ui.el('div', 'proxy-card-score-total-label', { text: t('proxyCard.totalScore') }));
    const totalVal = ui.el('div', 'proxy-card-score-total-value', { html: `${total}<small>/100</small>`, style: `color:${total >= 60 ? 'var(--success)' : total >= 30 ? 'var(--warning)' : 'var(--danger)'}` });
    totalRow.appendChild(totalVal);
    section.appendChild(totalRow);

    section.appendChild(ui.el('div', 'proxy-card-rating-hint', { text: t('proxyCard.ratingHint') }));

    return section;
  },

  _actions(p, overlay) {
    const footer = ui.el('div', 'proxy-card-footer');

    const left = ui.el('div', 'proxy-card-actions');

    const favBtn = ui.el('button', `btn btn-sm ${p.is_favorite ? 'btn-primary' : 'btn-secondary'}`, { html: `${this._svg('star')} ${p.is_favorite ? t('proxyCard.favorited') : t('proxyCard.favorite')}` });
    if (p.is_favorite) favBtn.classList.add('active');
    favBtn.addEventListener('click', () => {
      favBtn.disabled = true;
      const promise = p.is_favorite ? api.favRemove(p.address) : api.favAdd(p.address);
      promise.then(() => {
        app.toast(p.is_favorite ? t('proxyCard.removedFromFavorites') : t('proxyCard.addedToFavorites'));
        p.is_favorite = !p.is_favorite;
        this._refresh(overlay.querySelector('.proxy-card'), p.address, overlay);
      }).catch(e => {
        favBtn.disabled = false;
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    left.appendChild(favBtn);

    const selectBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('proxyCard.select') });
    selectBtn.addEventListener('click', () => {
      selectBtn.disabled = true;
      selectBtn.textContent = t('common.loading');
      api.proxySelect(p.address).then(async () => {
        app.toast(t('page.proxyPool.selected', {addr: p.address}));
        try {
          const ps = await api.proxyStatus();
          if (!ps || !ps.running) {
            const port = ps && ps.port ? ps.port : 8080;
            await api.proxyStart(port);
            app.toast(t('page.overview.proxyStarted'));
          }
        } catch (e) { console.error('proxy start', e); }
        overlay.remove();
      }).catch(e => {
        selectBtn.disabled = false;
        selectBtn.textContent = t('proxyCard.select');
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    left.appendChild(selectBtn);

    const recheckBtn = ui.el('button', 'btn btn-sm btn-secondary', { html: `${this._svg('refresh')} ${t('proxyCard.recheck')}` });
    recheckBtn.addEventListener('click', () => {
      recheckBtn.disabled = true;
      recheckBtn.innerHTML = `${this._svg('refresh')} ${t('common.loading')}`;
      api.proxyRecheck(p.address).then(() => {
        app.toast(t('page.proxies.recheckComplete'));
        this._refresh(overlay.querySelector('.proxy-card'), p.address, overlay);
      }).catch(e => {
        recheckBtn.disabled = false;
        recheckBtn.innerHTML = `${this._svg('refresh')} ${t('proxyCard.recheck')}`;
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    left.appendChild(recheckBtn);

    const copyWrap = ui.el('div', 'proxy-card-copy-wrap');
    const copyBtn = ui.el('button', 'btn btn-sm btn-secondary', { html: `${this._svg('copy')} ${t('proxyCard.copy')}` });
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(p.address).then(() => app.toast(t('proxyCard.copied'))).catch(() => {});
    });
    copyWrap.appendChild(copyBtn);
    left.appendChild(copyWrap);

    const right = ui.el('div', 'proxy-card-actions');
    const blBtn = ui.el('button', 'btn btn-sm btn-danger', { html: `${this._svg('x-circle')} ${p.in_blacklist ? t('proxyCard.removeFromBlacklist') : t('proxyCard.addToBlacklist')}` });
    blBtn.addEventListener('click', () => {
      blBtn.disabled = true;
      const promise = p.in_blacklist ? api.blRemove(p.address) : api.blAdd(p.address, 'manual');
      promise.then(() => {
        app.toast(p.in_blacklist ? t('page.blacklist.removedFromBlacklist') : t('page.proxies.addedToBlacklist'));
        overlay.remove();
      }).catch(e => {
        blBtn.disabled = false;
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    right.appendChild(blBtn);

    footer.appendChild(left);
    footer.appendChild(right);
    return footer;
  },

  _sectionTitle(text, icon) {
    return ui.el('div', 'proxy-card-section-title', { html: `${icon} ${ui.escHtml(text)}` });
  },

  _svg(name) {
    const icons = {
      'bar-chart': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
      shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
      'map-pin': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
      clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
      'thumbs-up': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>',
      check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
      x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
      alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
      minus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="5" y1="12" x2="19" y2="12"/></svg>',
      copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>',
      lock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>',
      link: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
      'shield-check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><polyline points="9 12 11 14 15 10"/></svg>',
      'check-circle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
      refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
      tag: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>',
      star: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
      'x-circle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
      globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>',
      code: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
      users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
      search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
      download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>',
      play: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg>',
      gamepad: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="6" y1="12" x2="10" y2="12"/><line x1="8" y1="10" x2="8" y2="14"/><line x1="15" y1="13" x2="15.01" y2="13"/><line x1="18" y1="11" x2="18.01" y2="11"/><rect x="2" y="6" width="20" height="12" rx="2"/></svg>',
      'credit-card': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/></svg>',
      layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
    };
    return icons[name] || '';
  }
};

window.proxyCard = proxyCard;


/* ==== js/pages/proxy-control.js ==== */
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
        if (filter.length >= 2) {
          runSearch();
        } else {
          searchActive = false;
          if (lastStreamData) updateStream(lastStreamData);
          if (lastRequestsData) updateDomains(lastRequestsData);
          if (lastClientsData) updateClients(lastClientsData);
        }
      }, 250);
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
        if (searchActive) runSearch();
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
  let searchActive = false;
  let searchSeq = 0;

  async function runSearch() {
    if (filter.length < 2) { searchActive = false; return; }
    searchActive = true;
    const seq = ++searchSeq;
    try {
      const minutes = (RANGES.find(r => r[0] === range) || [null, 1440])[1];
    const res = await api.trafficSearch(filter, minutes);
      if (!searchActive || seq !== searchSeq) return;
      updateStream({ requests: res.requests || [], searchTotal: res.total || 0 });
      updateDomains({ searchDomains: res.domains || [] });
      updateClients({ searchClients: res.clients || [] });
    } catch (e) {
      console.error('traffic search', e);
    }
  }
  function buildGeoMap(alive, ps) {
    geoMap = {};
    (alive || []).forEach(p => { if (p && p.address) geoMap[p.address] = p; });
    const ap = ps && ps.active_proxy;
    if (ap && ap.address) geoMap[ap.address] = Object.assign({}, geoMap[ap.address], ap);
  }

  function updateStream(requests) {
    if (requests) lastStreamData = requests;
    const body = els.streamBody;
    const searched = !!(lastStreamData && lastStreamData.searchTotal !== undefined);
    const all = lastStreamData && lastStreamData.requests ? lastStreamData.requests : [];
    const list = searched ? all : (filter ? all.filter(rowMatches) : all);
    const prevWrap = body.querySelector('.pc-stream-wrap');
    const prevScroll = prevWrap ? prevWrap.scrollTop : 0;
    body.innerHTML = '';
    if (!list.length) {
      body.appendChild(ui.el('div', 'pc-empty', { text: (filter || searched) ? t('page.proxyControl.filterEmpty') : t('page.proxyControl.noRecentRequests') }));
      return;
    }

    const newIds = new Set();
    list.forEach(r => { newIds.add(r.ts + '|' + r.client + '|' + r.target); });

    const limit = searched ? (showAllStream ? 50 : 8) : (showAllStream ? 40 : 8);
    const shown = searched ? list.slice(0, limit) : list.slice(0, limit);
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
      (searched
        ? (lastStreamData.searchTotal > list.length
          ? `<div class="pc-stream-more">${t('page.proxyControl.foundTotal', { count: lastStreamData.searchTotal.toLocaleString() })}</div>`
          : '')
        : (list.length > limit
          ? `<div class="pc-stream-more">${t('page.proxyControl.showingNofM', { shown: limit, total: list.length })}</div>`
          : ''));

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
    const searchDomains = lastRequestsData && lastRequestsData.searchDomains;
    els.domains.innerHTML = '';
    if (searchDomains) {
      if (!searchDomains.length) {
        els.domains.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.filterEmpty') }));
        return;
      }
      const maxReq = searchDomains[0].requests || 1;
      const sTotal = searchDomains.reduce((s, d) => s + d.requests, 0) || 1;
      searchDomains.slice(0, 6).forEach(d => {
        const row = ui.el('div', 'pc-top-row');
        row.innerHTML = ui.hostAvatar(d.domain, 26) +
          `<div class="pc-top-main">` +
            `<div class="pc-top-namerow"><span class="pc-top-name" title="${ui.escHtml(d.domain)}">${ui.escHtml(d.domain)}</span><span class="pc-top-pct">${(d.requests / sTotal * 100).toFixed(1)}%</span></div>` +
            `<div class="pc-top-bar"><span style="width:${(d.requests / maxReq * 100).toFixed(0)}%;background:var(--accent)"></span></div>` +
          `</div>` +
          `<div class="pc-top-right"><b>${d.requests.toLocaleString()}</b><span>${fmtBytes(d.bytes)}</span></div>`;
        els.domains.appendChild(row);
      });
      return;
    }
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
    const searchClients = lastClientsData && lastClientsData.searchClients;
    clientHostnameMap = {};
    (list || []).forEach(c => { if (c.hostname) clientHostnameMap[c.client] = c.hostname; });
    els.clients.innerHTML = '';
    if (searchClients) {
      if (!searchClients.length) {
        els.clients.appendChild(ui.el('div', 'pc-empty', { text: t('page.proxyControl.filterEmpty') }));
        return;
      }
      searchClients.forEach(c => { if (c.hostname) clientHostnameMap[c.client] = c.hostname; });
      const sMax = searchClients[0].requests || 1;
      const sTotal = searchClients.reduce((s, c) => s + c.requests, 0) || 1;
      const nowSec2 = Date.now() / 1000;
      searchClients.slice(0, 6).forEach(c => {
        const online = (nowSec2 - (c.last_seen || 0)) < 600;
        const row = ui.el('div', 'pc-top-row');
        row.style.cursor = 'pointer';
        const title2 = c.hostname ? `${c.client} (${c.hostname})` : c.client;
        row.innerHTML = ui.personAvatar(c.client, 26) +
          `<div class="pc-top-main">` +
            `<div class="pc-top-namerow"><span class="pc-top-name pc-mono" title="${ui.escHtml(title2)}">${ui.escHtml(c.client)}${c.hostname ? ` <span class="pc-hostname">(${ui.escHtml(c.hostname)})</span>` : ''}</span><span class="pc-top-pct">${(c.requests / sTotal * 100).toFixed(1)}%</span></div>` +
            `<div class="pc-top-bar"><span style="width:${(c.requests / sMax * 100).toFixed(0)}%;background:#8a2be2"></span></div>` +
          `</div>` +
          `<div class="pc-top-right"><b>${c.requests.toLocaleString()}</b><span class="${online ? 'pc-online' : ''}">${ui.ago(c.last_seen)}</span></div>`;
        row.addEventListener('click', () => window.clientCard.show(c.client));
        els.clients.appendChild(row);
      });
      return;
    }
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
      if (searchActive) {
        await runSearch();
        try { updateRoutes(routes); } catch (e) { console.error('routes', e); }
        try { updateUpstream(ps); } catch (e) { console.error('upstream', e); }
        try { updateConsumer(summary); } catch (e) { console.error('consumer', e); }
        try { updateBandwidth(bw); } catch (e) { console.error('bandwidth', e); }
        lastUpdate = Date.now();
        updateFooter();
        return;
      }
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


/* ==== js/pages/proxy-pool.js ==== */
router.register('proxy-pool', (container) => {
  let state = {
    proxies: [],
    selected: null,
    proxySortKey: 'score',
    proxySortDir: -1,
    hideNoHttps: true,
    hideNoSsl: false,
    hideMitm: true,
    hideBlacklisted: true,
    hideFraud: false,
    groupByProtocol: true,
  };

  function setProxySort(key) {
    if (state.proxySortKey === key) state.proxySortDir *= -1;
    else { state.proxySortKey = key; state.proxySortDir = -1; }
    load();
  }

  function fmtDuration(sec) {
    if (!sec || sec <=0) return '—';
    const s = Math.round(sec % 60);
    const m = Math.floor((sec % 3600) / 60);
    const hh = Math.floor(sec / 3600);
    const dd = Math.floor(sec / 86400);
    const mo = Math.floor(dd / 30);
    const y = Math.floor(dd / 365);
    if (sec >= 94608000) return y + ' ' + t('time.year');
    if (sec >= 7776000) return mo + ' ' + t('time.month');
    if (sec >= 259200) return dd + ' ' + t('time.day');
    if (sec >= 10800) return hh + ' ' + t('time.hour');
    if (sec >= 180) return (hh ? hh + ' ' + t('time.hour') + ' ' : '') + m + ' ' + t('time.minute');
    if (m) return m + ' ' + t('time.minute') + ' ' + s + ' ' + t('time.second');
    return s + ' ' + t('time.second');
  }

  function fmtFullTime(ts) {
    if (!ts) return '—';
    const d = new Date(ts * 1000);
    const pad = (n) => String(n).padStart(2, '0');
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }

  function fmtAgo(ts) {
    if (!ts) return '—';
    const d = Math.floor(Date.now() / 1000 - ts);
    if (d < 0) return t('ago.now');
    const s = Math.round(d % 60);
    const m = Math.floor((d % 3600) / 60);
    const hh = Math.floor(d / 3600);
    const days = Math.floor(d / 86400);
    const mo = Math.floor(days / 30);
    const y = Math.floor(days / 365);
    if (d >= 94608000) return y + ' ' + t('time.year') + ' ' + t('time.ago');
    if (d >= 7776000) return mo + ' ' + t('time.month') + ' ' + t('time.ago');
    if (d >= 259200) return days + ' ' + t('time.day') + ' ' + t('time.ago');
    if (d >= 10800) return hh + ' ' + t('time.hour') + ' ' + t('time.ago');
    if (d >= 180) return (hh ? hh + ' ' + t('time.hour') + ' ' : '') + m + ' ' + t('time.minute') + ' ' + t('time.ago');
    if (m) return m + ' ' + t('time.minute') + ' ' + s + ' ' + t('time.second') + ' ' + t('time.ago');
    return s + ' ' + t('time.second') + ' ' + t('time.ago');
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
    row1.appendChild(buildSelectedProxyCard());
    row1.appendChild(buildSwitchHistoryCard());
    container.appendChild(row1);

    const row2 = ui.el('div', 'grid grid-1 row-stretch');
    row2.style.flex = '2';
    row2.appendChild(buildSelectProxyCard());
    container.appendChild(row2);
  }

  function buildSelectedProxyCard() {
    const card = ui.el('div', 'card');
    card.id = 'selected-proxy-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.proxyPool.selectedUpstream'), style: 'margin-bottom:8px' }));

    const body = ui.el('div', '', { id: 'sel-proxy-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No upstream selected</div>';
    card.appendChild(body);
    return card;
  }

  function buildSwitchHistoryCard() {
    const card = ui.el('div', 'card');
    card.id = 'switch-history-card';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.minHeight = '0';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.proxyPool.switchHistory') }));
    header.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.proxyPool.switchHistoryHint') }));
    card.appendChild(header);
    const body = ui.el('div', '', { id: 'switch-history-body', style: 'flex:1;overflow-y:auto;min-height:0;font-size:11px' });
    body.innerHTML = `<div class="empty" style="padding:8px">${t('page.proxyPool.noSwitches')}</div>`;
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
    const recheckAllBtn = ui.el('button', 'card-action', { text: t('page.proxyPool.recheckAll') });
    recheckAllBtn.addEventListener('click', () => {
      recheckAllBtn.disabled = true;
      recheckAllBtn.textContent = t('common.testing');
      api.healthStart().then(() => {
        app.toast(t('common.recheckStarted'));
        const wait = setInterval(async () => {
          try {
            const s = await api.snapshot();
            if (!s.running || s.phase !== 'health') {
              clearInterval(wait);
              recheckAllBtn.disabled = false;
              recheckAllBtn.textContent = t('page.proxyPool.recheckAll');
              load();
            }
          } catch (e) { /* keep waiting */ }
        }, 2000);
        if (window._pageIntervals) window._pageIntervals.push(wait);
      }).catch(e => {
        recheckAllBtn.disabled = false;
        recheckAllBtn.textContent = t('page.proxyPool.recheckAll');
        if (e.message && e.message.includes('already_running')) {
          app.toast(t('common.recheckAlreadyRunning'), 'warn');
        } else {
          app.toast(t('common.error', {message: e.message}), 'error');
        }
      });
    });
    header.appendChild(recheckAllBtn);
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
    const fraudLbl = ui.el('label', '', { style: 'display:flex;align-items:center;gap:4px;cursor:pointer;font-size:11px' });
    const fraudCb = ui.el('input', '', { id: 'hide-fraud', type: 'checkbox' });
    fraudCb.addEventListener('change', () => { state.hideFraud = fraudCb.checked; updateSelectProxy(state.proxies); });
    fraudLbl.appendChild(fraudCb);
    fraudLbl.appendChild(ui.el('span', '', { text: 'fraud-CLEAN only' }));
    filterRow.appendChild(fraudLbl);
    card.appendChild(filterRow);

    const wrap = ui.el('div', '', { id: 'select-proxy-tbl', style: 'flex:1;overflow-y:auto;min-height:0' });
    wrap.addEventListener('click', (e) => {
      const el = e.target.closest('[data-card-addr]');
      if (!el) return;
      e.stopPropagation();
      const addr = el.dataset.cardAddr;
      if (addr && window.proxyCard) window.proxyCard.show(addr);
    });
    card.appendChild(wrap);
    return card;
  }

  build();

  // --- Updaters ---
  function updateSelectedProxy(ps) {
    const body = document.getElementById('sel-proxy-body');
    if (!body) return;
    const ap = ps && ps.active_proxy;
    if (!ap || (ps && ps.direct_mode)) {
      body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxyPool.noUpstreamSelected')}</div>`;
      return;
    }

    const top = ui.el('div', '', { style: 'font-family:monospace;font-size:13px;font-weight:700;color:var(--accent);margin-bottom:4px;word-break:break-all;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px' });
    top.textContent = proxyUrl(ap);
    top.addEventListener('click', () => { if (window.proxyCard) window.proxyCard.show(ap.address); });
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

  function updateSwitchHistory(ps) {
    const body = document.getElementById('switch-history-body');
    if (!body) return;
    const history = (ps && ps.switch_history) || [];
    if (!history.length) {
      body.innerHTML = `<div class="empty" style="padding:8px">${t('page.proxyPool.noSwitches')}</div>`;
      return;
    }
    const headers = [
      t('page.proxyPool.colAddress'),
      t('page.proxyPool.colCountry'),
      t('page.proxyPool.colEgress'),
      t('page.proxyPool.colEgressIp'),
      'SSL',
      t('page.proxyPool.colTraffic'),
      t('page.proxyPool.colActive'),
      t('page.proxyPool.colWhen'),
    ];
    const rows = history.map((e) => {
      if (!e.address) {
        const label = e.action === 'direct' ? t('page.proxyPool.directModeOn') : t('page.proxyPool.cleared');
        return [label, '', '', '', '', '', '', `<span style="color:var(--text-muted)" title="${ui.escHtml(fmtFullTime(e.ts))}">${fmtAgo(e.ts)}</span>`];
      }
      const flag = e.egress_country_code ? (ui.flag(e.egress_country_code) || '') + ' ' + ui.escHtml(e.egress_country_code) : '—';
      const exitLoc = [e.egress_city, e.egress_isp].filter(Boolean).map(ui.escHtml).join(' · ') || '—';
      const egressIp = e.egress_ip ? `<span style="font-family:monospace;color:var(--text-muted)">${e.egress_country_code ? (ui.flag(e.egress_country_code) || '') + ' ' : ''}${ui.escHtml(e.egress_ip)}</span>` : '—';
      const ssl = e.ssl_supported
        ? '<span style="color:#06b6d4;font-weight:600">✓</span>'
        : '<span style="color:var(--text-muted)">✗</span>';
      const bytes = e.bytes || 0;
      const traffic = `<span class="badge badge-blue" style="font-size:9px">↓↑ ${ui.fmtBytes(bytes)}</span>`;
      const active = `<span class="badge badge-gray" style="font-size:9px">${fmtDuration(e.duration_sec)}</span>`;
      const when = `<span style="color:var(--text-muted)" title="${ui.escHtml(fmtFullTime(e.ts))}">${fmtAgo(e.ts)}</span>`;
      const favStar = e.is_favorite ? '<svg width="10" height="10" style="vertical-align:-1px;color:var(--warning);flex-shrink:0;width:10px;height:10px;margin-right:2px"><use href="#icon-star"/></svg>' : '<span style="width:12px;flex-shrink:0;display:inline-block"></span>';
      const addr = `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(e.address)}" style="font-family:monospace;font-size:10px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${favStar}${ui.escHtml(e.address)}</span>`;
      return [addr, flag, exitLoc, egressIp, ssl, traffic, active, when];
    });
    body.innerHTML = '';
    const tbl = ui.table(headers, rows);
    tbl.classList.add('switch-history-table');
    const tbody = tbl.querySelector('tbody');
    if (tbody && history.length && history[0].address) {
      const firstTr = tbody.querySelector('tr');
      if (firstTr) firstTr.style.background = 'var(--accent-light)';
    }
    body.appendChild(tbl);
    body.querySelectorAll('.proxy-address-link').forEach(el => {
      el.addEventListener('click', (ev) => { ev.stopPropagation(); if (window.proxyCard) window.proxyCard.show(el.getAttribute('data-card-addr')); });
    });
  }

  function proxyProtoGroup(p) {
    const proto = (p.protocol || 'http').toLowerCase();
    if (proto === 'socks5') return 'SOCKS5';
    if (proto === 'socks4') return 'SOCKS4';
    if (proto === 'tor' || p.address.includes('.onion')) return 'TOR';
    if (p.supports_connect || p.ssl_supported) return 'HTTPS';
    return 'HTTP';
  }

  function proxyUrl(p) {
    const proto = (p.protocol || 'http').toLowerCase();
    if (proto === 'socks5') return `socks5://${p.address}`;
    if (proto === 'socks4') return `socks4://${p.address}`;
    if (proto === 'tor' || p.address.includes('.onion')) return `tor://${p.address}`;
    if (p.supports_connect || p.ssl_supported) return `https://${p.address}`;
    return `http://${p.address}`;
  }

  const PROTO_GROUP_ORDER = ['HTTP', 'HTTPS', 'SOCKS4', 'SOCKS5', 'TOR'];
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
      .filter(p => (!state.hideNoHttps || p.supports_connect) && (!state.hideNoSsl || p.ssl_supported) && (!state.hideMitm || !p.mitm_suspect) && (!state.hideBlacklisted || !(p.in_blacklist || (p.ip_blacklist_hits || 0) > 0)) && (!state.hideFraud || p.fraud_verdict === 'CLEAN'))
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
      if (state.hideFraud) tags.push('fraud-CLEAN');
      count.textContent = sorted.length + (tags.length ? ' ' + tags.join('+') : ' alive');
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.proxySortKey, state.proxySortDir) : ''), width, align, sortKey: key, onSort: key ? () => setProxySort(key) : undefined });

    function fraudBadge(p) {
      const fc = p.fraud_failcheck;
      const s = typeof p.fraud_score === 'number' ? p.fraud_score : null;
      const v = p.fraud_verdict || 'FAILCHECK';
      const flags = `hosting ${p.fraud_hosting ? 'yes' : 'no'} · proxy ${p.fraud_proxy ? 'yes' : 'no'} · mobile ${p.fraud_mobile ? 'yes' : 'no'}`;
      if (fc || s === null) {
        return `<span title="FAILCHECK — no fresh measurement (${flags})" style="display:inline-flex;align-items:center;justify-content:center;min-width:40px;padding:1px 4px;border-radius:var(--radius-xs);background:rgba(107,114,128,.15);color:var(--text-muted);font-weight:700;font-size:9px">FC</span>`;
      }
      const color = v === 'CLEAN' ? 'var(--success)' : v === 'MOBILE' ? '#3b82f6' : v === 'DC' ? 'var(--warning)' : 'var(--danger)';
      const bg = v === 'CLEAN' ? 'rgba(34,197,94,.12)' : v === 'MOBILE' ? 'rgba(59,130,246,.12)' : v === 'DC' ? 'rgba(245,158,11,.12)' : 'rgba(239,68,68,.12)';
      return `<span title="${v}: risk ${s}/100 · ${flags}" style="display:inline-flex;align-items:center;justify-content:center;min-width:40px;padding:1px 4px;border-radius:var(--radius-xs);background:${bg};color:${color};font-weight:700;font-size:9px">${s}</span>`;
    }

    function blacklistBadge(p) {
      const hits = p.ip_blacklist_hits || 0;
      const total = p.ip_blacklist_sources_total || 0;
      if (!p.in_blacklist && hits === 0) return '';
      if (hits > 0 && total > 0) {
        return `<span style="display:inline-flex;align-items:center;justify-content:center;min-width:20px;padding:1px 4px;border-radius:var(--radius-xs);background:var(--danger-bg);color:var(--danger);font-weight:700;font-size:9px;margin-left:4px">${hits}/${total}</span>`;
      }
      if (p.in_blacklist) {
        return `<span style="display:inline-flex;align-items:center;justify-content:center;min-width:16px;padding:1px 4px;border-radius:var(--radius-xs);background:var(--danger-bg);color:var(--danger);font-weight:700;font-size:9px;margin-left:4px">BL</span>`;
      }
      return '';
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
          h('BL', 'ip_blacklist_hits', '36px', 'center'),
          h('Fraud', 'fraud_score', '52px', 'center'),
          h('Ok', 'last_ok', '36px', 'right'),
          h('', null, '40px', 'center'),
        ];
        const rows = list.map((p, i) => {
          const sc = Math.min(100, Math.max(0, p.score || 0));
          const isSel = state.selected === p.address;
          const hasDiff = p.listen_country && p.egress_country && p.listen_country !== p.egress_country;
          const srvFlag = ui.flag(p.listen_country_code || p.country_code) || '—';
          const exitFlag = hasDiff ? (ui.flag(p.egress_country_code || p.country_code) || '') : '';
          const favStar = p.is_favorite ? '<svg width="11" height="11" style="vertical-align:-2px;color:var(--warning);flex-shrink:0;width:11px;height:11px;margin-right:2px"><use href="#icon-star"/></svg>' : '<span style="width:13px;flex-shrink:0;display:inline-block"></span>';
          return [
            `<span style="color:var(--text-muted)">${i+1}</span>`,
            `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="font-size:10px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${favStar}${proxyUrl(p)}</span>`,
            srvFlag,
            exitFlag,
            p.ssl_supported ? '<span style="color:#06b6d4;font-weight:600;font-size:10px">✓</span>' : '<span style="color:var(--text-muted)">—</span>',
            p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
            (p.speed_avg || 0).toFixed(0),
            (p.success_rate * 100).toFixed(0) + '%',
            `<div style="display:inline-block;width:30px;height:4px;background:var(--surface-raised);border-radius:2px;vertical-align:middle;overflow:hidden"><div style="width:${sc}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--info));transition:width 0.4s"></div></div>`,
            blacklistBadge(p),
            fraudBadge(p),
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
        h('BL', 'ip_blacklist_hits', '36px', 'center'),
        h('Fraud', 'fraud_score', '52px', 'center'),
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
        const favStar = p.is_favorite ? '<svg width="11" height="11" style="vertical-align:-2px;color:var(--warning);flex-shrink:0;width:11px;height:11px;margin-right:2px"><use href="#icon-star"/></svg>' : '<span style="width:13px;flex-shrink:0;display:inline-block"></span>';
        return [
          `<span style="color:var(--text-muted)">${i+1}</span>`,
          `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="font-size:10px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${favStar}${proxyUrl(p)}</span>`,
          srvFlag,
          exitFlag,
          p.ssl_supported ? '<span style="color:#06b6d4;font-weight:600;font-size:10px">✓</span>' : '<span style="color:var(--text-muted)">—</span>',
          p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
          (p.speed_avg || 0).toFixed(0),
          (p.success_rate * 100).toFixed(0) + '%',
          `<div style="display:inline-block;width:30px;height:4px;background:var(--surface-raised);border-radius:2px;vertical-align:middle;overflow:hidden"><div style="width:${sc}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--info));transition:width 0.4s"></div></div>`,
          blacklistBadge(p),
          fraudBadge(p),
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
      const [ps, proxies] = await Promise.all([
        api.proxyStatus().catch(e => { console.error('proxyStatus', e); return {}; }),
        api.proxyAlive().catch(e => { console.error('proxyAlive', e); return []; }),
      ]);
      state.selected = ps && ps.active_proxy ? ps.active_proxy.address : null;
      state.proxies = proxies;
      updateSelectedProxy(ps);
      updateSwitchHistory(ps);
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


/* ==== js/pages/proxy-sources.js ==== */
router.register('proxy-sources', (container) => {
  let sources = [];
  let editingId = null;
  let _loading = false;
  let fetchProgress = {};
  let progressPoller = null;

  function fmtBytes(n) {
    if (!n) return '0B';
    if (n >= 1048576) return (n / 1048576).toFixed(1) + 'MB';
    if (n >= 1024) return (n / 1024).toFixed(0) + 'KB';
    return n + 'B';
  }

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
    const row = ui.el('div', 'grid grid-2 row-stretch');
    row.appendChild(buildSourcesCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);
  }

  function buildSourcesCard() {
    const card = ui.card(t('page.proxySources.proxySources'));
    card.id = 'card-proxy-sources';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.proxySources.newSource'), style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });

    const refreshBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.proxySources.refresh'), style: 'margin-bottom:8px;margin-left:6px' });
    function startFetch() {
      refreshBtn.disabled = true;
      refreshBtn.textContent = t('page.proxySources.fetching');
      fetchProgress = {};
      progressPoller = setInterval(() => {
        api.proxySourceProgress().then(r => {
          if (r && r.progress) { fetchProgress = r.progress; updateSourcesCard(sources); }
        }).catch(() => {});
      }, 2000);
      api.proxySourcesFetch().then(r => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.proxySources.refresh');
        fetchProgress = {};
        if (r.ok) {
          const parts = [];
          if (r.sources) {
            r.sources.forEach(s => {
              const icon = s.status === 'ok' ? '✓' : '✗';
              const color = s.status === 'ok' ? 'var(--success)' : 'var(--danger)';
              parts.push(`<span style="color:${color}">${icon} ${ui.escHtml(s.name)}: ${s.count}</span>`);
            });
          }
          const total = r.total_addresses || 0;
          const statusHtml = parts.length
            ? parts.join(' &nbsp;·&nbsp; ') + `<br><span style="color:var(--text-muted)">${t('page.proxySources.uniqueAddresses', {count: total})}</span>`
            : `<span style="color:var(--text-muted)">${t('page.proxySources.noEnabledSources')}</span>`;
          const statusEl = document.getElementById('fetch-status');
          if (statusEl) {
            statusEl.innerHTML = statusHtml;
            statusEl.style.display = '';
            clearTimeout(statusEl._hideTimer);
            statusEl._hideTimer = setTimeout(() => { statusEl.style.display = 'none'; }, 8000);
          }
          app.toast(`Fetched ${total} addresses from ${r.sources ? r.sources.length : 0} sources`);
        } else {
          app.toast('Fetch error: ' + (r.error || 'unknown'), 'error');
        }
        load();
      }).catch(e => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.proxySources.refresh');
        fetchProgress = {};
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    }
    refreshBtn.addEventListener('click', startFetch);

    card.appendChild(addBtn);
    card.appendChild(refreshBtn);

    const fetchStatus = ui.el('div', '', { id: 'fetch-status', style: 'display:none;padding:6px 8px;margin-bottom:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;line-height:1.5' });
    card.appendChild(fetchStatus);

    const tblWrap = ui.el('div', '', { id: 'proxy-sources-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.noSources')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.proxySources.sourceEditor'));
    card.id = 'card-source-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'source-editor-body' });
    body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.selectToEdit')}</div>`;
    card.appendChild(body);

    return card;
  }

  function showEditor(src) {
    const body = document.getElementById('source-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = src ? src.id : null;

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.nameLabel') }));
    const nameInput = ui.el('input', '', { id: 'src-name', type: 'text', value: src ? src.name : '', placeholder: 'e.g. monosans/socks5', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.idLabel') }));
    const idInput = ui.el('input', '', { id: 'src-id', type: 'text', value: src ? src.id : '', placeholder: 'auto-generated', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);' + (src ? 'opacity:0.6' : '') });
    if (src) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const urlRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    urlRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.urlLabel') }));
    const urlInput = ui.el('input', '', { id: 'src-url', type: 'text', value: src ? src.url : '', placeholder: 'https://example.com/proxies.txt', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    urlRow.appendChild(urlInput);
    body.appendChild(urlRow);

    const protoRow = ui.el('div', '', { style: 'margin-bottom:12px' });
    protoRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.protocolLabel') }));
    const protoSelect = ui.el('select', '', { id: 'src-protocol', style: 'width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    ['mixed', 'http', 'https', 'socks4', 'socks5'].forEach(p => {
      const opt = ui.el('option', '', { value: p, text: p.toUpperCase() });
      if (src && src.protocol === p) opt.selected = true;
      if (!src && p === 'mixed') opt.selected = true;
      protoSelect.appendChild(opt);
    });
    protoRow.appendChild(protoSelect);
    body.appendChild(protoRow);

    if (src && src.last_fetched_at) {
      const statsHtml = `
        <div style="padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;margin-bottom:12px">
          <div style="margin-bottom:4px;color:var(--text-secondary)">${t('page.proxySources.sourceStats')}</div>
          <div>${t('page.proxySources.lastFetched')}: <b>${ui.ago(src.last_fetched_at)}</b></div>
          <div>${t('page.proxySources.lastStatus')}: <b style="color:${src.last_fetch_status === 'ok' ? 'var(--success)' : 'var(--danger)'}">${src.last_fetch_status || '—'}</b></div>
          ${src.last_fetch_error ? `<div>${t('common.error', {message: ui.escHtml(src.last_fetch_error)})}</div>` : ''}
          <div style="margin-top:6px">
            <span style="color:var(--success)">Last: ${src.last_working} ${t('page.proxySources.working')}</span> /
            <span style="color:var(--danger)">${src.last_dead} ${t('page.proxySources.dead')}</span>
            (${t('page.proxySources.fetched')} ${src.last_fetch_count})
          </div>
          <div style="margin-top:2px">
            <span style="color:var(--text-muted)">${t('page.proxySources.currentAddresses')}: ${src.current_entries ?? src.last_fetch_count ?? '0'}</span>
          </div>
          <div style="margin-top:2px">
            <span style="color:var(--text-muted)">${t('page.proxySources.cumulative')}: ${src.total_working} ${t('page.proxySources.working')} / ${src.total_dead} ${t('page.proxySources.dead')} / ${src.total_fetched} ${t('page.proxySources.fetched')}</span>
          </div>
        </div>`;
      body.appendChild(ui.el('div', '', { html: statsHtml }));
    }

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: src ? t('page.proxySources.saveChanges') : t('page.proxySources.addSource') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('src-name').value.trim();
      let sourceId = document.getElementById('src-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!sourceId) sourceId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const url = document.getElementById('src-url').value.trim();
      const protocol = document.getElementById('src-protocol').value;

      if (!name) { app.toast(t('common.nameRequired'), 'error'); return; }
      if (!url) { app.toast(t('common.urlRequired'), 'error'); return; }

      const data = { id: sourceId, name, url, protocol };

      if (editingId) {
        api.proxySourceUpdate(editingId, data).then(() => {
          app.toast(t('page.proxySources.sourceUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
      } else {
        api.proxySourceCreate(data).then(() => {
          app.toast(t('page.proxySources.sourceAdded'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (src) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
      cancelBtn.addEventListener('click', () => {
        editingId = null;
        resetEditor();
      });
      btnRow.appendChild(cancelBtn);
    }

    body.appendChild(btnRow);
  }

  function resetEditor() {
    const body = document.getElementById('source-editor-body');
    if (body) body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.selectToEdit')}</div>`;
  }

  function qualityPct(working, dead) {
    const total = working + dead;
    if (!total) return 0;
    return Math.round(working / total * 100);
  }

  function qualityBadge(working, dead) {
    const pct = qualityPct(working, dead);
    if (pct >= 50) return `<span style="color:var(--success);font-weight:600">${pct}%</span>`;
    if (pct >= 20) return `<span style="color:var(--warning);font-weight:600">${pct}%</span>`;
    if (pct > 0) return `<span style="color:var(--danger);font-weight:600">${pct}%</span>`;
    return `<span style="color:var(--text-muted)">—</span>`;
  }

  function protocolBadge(protocol) {
    const colors = { http: 'var(--info)', https: '#8b5cf6', socks4: 'var(--accent)', socks5: 'var(--success)', mixed: 'var(--text-muted)' };
    const color = colors[protocol] || colors.mixed;
    return `<span style="color:${color};font-size:11px;font-weight:600">${(protocol || 'mixed').toUpperCase()}</span>`;
  }

  function statusBadge(src) {
    const p = fetchProgress[src.id];
    if (p) {
      if (p.status === 'downloading') return `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
      if (p.status === 'connecting') return `<span style="color:var(--info);font-size:11px">…</span>`;
      if (p.status === 'done') return `<span style="color:var(--success);font-size:11px">✓ ${p.count || 0}</span>`;
      if (p.status === 'error') return `<span style="color:var(--danger);font-size:11px">ERR</span>`;
    }
    if (!src.last_fetched_at) return `<span style="color:var(--text-muted);font-size:11px">${t('page.proxySources.never')}</span>`;
    if (src.last_fetch_status === 'ok') return `<span style="color:var(--success);font-size:11px">OK</span>`;
    return `<span style="color:var(--danger);font-size:11px" title="${ui.escHtml(src.last_fetch_error || '')}">ERR</span>`;
  }

  function updateSourcesCard(list) {
    const wrap = document.getElementById('proxy-sources-tbl');
    if (!wrap) return;
    sources = list || [];

    if (!list || !list.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.noSources')}</div>`;
      return;
    }

    const headers = [
      { label: 'Source', width: '140px' },
      { label: 'Proto', width: '50px', align: 'center' },
      { label: 'Status', width: '40px', align: 'center' },
      { label: 'Last', width: '60px' },
      { label: 'Quality', width: '50px', align: 'center' },
      { label: 'Addresses', width: '60px', align: 'center' },
      { label: 'Working', width: '50px', align: 'center' },
      { label: 'Dead', width: '50px', align: 'center' },
      { label: 'On/Off', width: '40px', align: 'center' },
      { label: 'Actions', width: '80px', align: 'center' },
    ];

    const rows = list.map(s => {
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer;font-size:12px';
      nameSpan.textContent = s.name || s.id;
      nameSpan.dataset.sourceId = s.id;
      nameSpan.dataset.action = 'edit';

      const linkBtn = document.createElement('a');
      linkBtn.href = s.url || '#';
      linkBtn.target = '_blank';
      linkBtn.rel = 'noopener';
      linkBtn.style.cssText = 'display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;font-size:10px;color:var(--text-muted);text-decoration:none;border:1px solid var(--border);border-radius:3px;margin-left:4px;vertical-align:middle;flex-shrink:0';
      linkBtn.textContent = '↗';
      linkBtn.title = t('page.proxySources.openSourceUrl');

      const nameCell = document.createElement('span');
      nameCell.style.cssText = 'display:inline-flex;align-items:center;gap:0';
      nameCell.appendChild(nameSpan);
      nameCell.appendChild(linkBtn);

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = t('common.edit');
      editBtn.dataset.sourceId = s.id;
      editBtn.dataset.action = 'edit';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = t('common.delete');
      delBtn.dataset.sourceId = s.id;
      delBtn.dataset.action = 'delete';

      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'btn btn-xs ' + (s.enabled ? 'btn-primary' : 'btn-ghost');
      toggleBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      toggleBtn.textContent = s.enabled ? t('common.on') : t('common.off');
      toggleBtn.dataset.sourceId = s.id;
      toggleBtn.dataset.action = 'toggle';

        const p = fetchProgress[s.id];
        let addrCell;
        if (p) {
          if (p.status === 'downloading') addrCell = `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
          else if (p.status === 'done' && p.count != null) addrCell = `<span style="color:var(--success)">${p.count}</span>`;
          else addrCell = `<span style="color:var(--text-secondary)">${s.current_entries ?? s.last_fetch_count ?? '0'}</span>`;
        } else {
          addrCell = `<span style="color:var(--text-secondary)">${s.current_entries ?? s.last_fetch_count ?? '0'}</span>`;
        }

        return [
          nameCell.outerHTML,
          protocolBadge(s.protocol),
          statusBadge(s),
          ui.ago(s.last_fetched_at),
          qualityBadge(s.last_working, s.last_dead),
          addrCell,
        `<span style="color:var(--success)">${s.last_working}</span>`,
        `<span style="color:var(--danger)">${s.last_dead}</span>`,
        toggleBtn.outerHTML,
        editBtn.outerHTML + delBtn.outerHTML,
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        const sourceId = el.dataset.sourceId;
        const action = el.dataset.action;
        if (action === 'edit') editSource(sourceId);
        else if (action === 'delete') deleteSource(sourceId);
        else if (action === 'toggle') toggleSource(sourceId);
      });
    });
  }

  function editSource(id) {
    api.proxySourceGet(id).then(src => {
      if (src) showEditor(src);
      else app.toast(t('page.proxySources.sourceNotFound'), 'error');
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function deleteSource(id) {
    if (!confirm(t('common.confirmDelete', {item: 'proxy source'}))) return;
    api.proxySourceDelete(id).then(() => {
      app.toast(t('page.proxySources.sourceDeleted'));
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function toggleSource(id) {
    api.proxySourceToggle(id).then(() => {
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    if (progressPoller) return;
    _loading = true;
    try {
      let result = [];
      try { result = await api.proxySources(); } catch (e) { console.error('proxySources', e); }
      const list = result.sources || result || [];
      sources = list;
      updateSourcesCard(list);
    } catch (e) {
      console.error('proxy-sources load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/routes.js ==== */
router.register('routes', (container) => {
  let routingStatus = null;
  let domainLists = [];
  let customProxies = [];
  let _loading = false;

  const ROUTE_OPTIONS = [
    { value: 'direct', labelKey: 'route.directNoProxy' },
    { value: 'pool_selected', labelKey: 'route.poolSelected' },
    { value: 'pool', labelKey: 'route.poolBest' },
  ];

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

    container.appendChild(buildTopRow());
    container.appendChild(buildRulesCard());
  }

  function buildTopRow() {
    const row = ui.el('div', '', { style: 'display:flex;gap:10px;flex-shrink:0' });
    const modeCard = buildModeCard();
    modeCard.style.flex = '1';
    const testCard = buildTestCard();
    testCard.style.flex = '1';
    row.appendChild(modeCard);
    row.appendChild(testCard);
    return row;
  }

  function buildModeCard() {
    const card = ui.card(t('page.routes.routingMode'));
    card.id = 'card-routing-mode';

    const toggleRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:10px' });
    const toggleLabel = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;font-weight:600' });
    const toggleCb = ui.el('input', '', { id: 'routing-toggle', type: 'checkbox' });
    toggleCb.addEventListener('change', () => {
      if (toggleCb.checked) {
        api.routingEnable().then(() => { app.toast(t('page.routes.routingEnabled')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.routingDisable().then(() => { app.toast(t('page.routes.routingDisabled')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    toggleLabel.appendChild(toggleCb);
    toggleLabel.appendChild(ui.el('span', '', { text: t('page.routes.domainBasedRouting') }));
    toggleRow.appendChild(toggleLabel);

    const statusBadge = ui.el('span', '', { id: 'routing-status-badge', style: 'font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600' });
    toggleRow.appendChild(statusBadge);
    card.appendChild(toggleRow);

    const defaultRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:4px' });
    defaultRow.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-secondary)', text: t('page.routes.defaultRouteUnmatched') }));
    const routeSelect = ui.el('select', '', { id: 'default-route-select', style: 'padding:3px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    populateRouteSelect(routeSelect);
    routeSelect.addEventListener('change', () => {
      api.routingSetDefault(routeSelect.value).then(() => app.toast('Default route updated')).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    defaultRow.appendChild(routeSelect);
    card.appendChild(defaultRow);

    const fbRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin:8px 0 2px' });
    const fbCb = ui.el('input', '', { id: 'routing-fallback-toggle', type: 'checkbox' });
    fbCb.addEventListener('change', () => {
      api.routingFallback(fbCb.checked).then(() => {
        app.toast(fbCb.checked ? t('page.routes.fallbackOn') : t('page.routes.fallbackOff'));
      }).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    fbRow.appendChild(fbCb);
    const fbText = ui.el('span', '', { style: 'font-size:12px;color:var(--text-secondary)', text: t('page.routes.fallbackPool') });
    fbText.title = t('page.routes.fallbackPoolHint');
    fbRow.appendChild(fbText);
    card.appendChild(fbRow);

    const hint = ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-top:4px', text: t('page.routes.routingOffHint') });
    card.appendChild(hint);

    return card;
  }

  function buildRulesCard() {
    const card = ui.card(t('page.routes.activeRoutes'));
    card.id = 'card-routing-rules';
    card.style.flex = '1';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.minHeight = '0';

    const headerRow = ui.el('div', '', { style: 'display:flex;align-items:center;justify-content:space-between;margin-bottom:10px' });
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.routes.addRoute') });
    addBtn.addEventListener('click', () => showAddRouteModal());
    headerRow.appendChild(addBtn);
    const countBadge = ui.el('span', 'badge badge-gray', { id: 'route-count-badge', style: 'font-size:10px' });
    headerRow.appendChild(countBadge);
    card.appendChild(headerRow);

    const tblWrap = ui.el('div', '', { id: 'routes-table-wrap', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:12px;font-size:12px">' + t('page.routes.noRoutesAdd') + '</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildTestCard() {
    const card = ui.card(t('page.routes.testRoute'));
    card.id = 'card-route-test';

    const row = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center;flex-wrap:wrap' });
    const input = ui.el('input', '', { id: 'route-test-input', type: 'text', placeholder: t('page.routes.testPlaceholder'), style: 'flex:1;min-width:120px;padding:5px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    row.appendChild(input);

    const testBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('common.test') });
    testBtn.addEventListener('click', () => {
      const domain = input.value.trim();
      if (!domain) return;
      testBtn.disabled = true;
      testBtn.textContent = '...';
      api.routingTest(domain).then(result => {
        testBtn.disabled = false;
        testBtn.textContent = t('common.test');
        const resultEl = document.getElementById('route-test-result');
        if (resultEl) {
          const route = result.route || 'unknown';
          const matchedList = result.matched_list || null;
          resultEl.innerHTML = ui.formatRouteLabel(route);
          const viaSpan = document.createElement('span');
          viaSpan.style.color = 'var(--text-secondary)';
          viaSpan.style.marginLeft = '6px';
          viaSpan.textContent = matchedList ? t('route.viaList', { name: matchedList }) : t('route.defaultRoute');
          resultEl.appendChild(viaSpan);
        }
      }).catch(e => {
        testBtn.disabled = false;
        testBtn.textContent = t('common.test');
        app.toast('Error: ' + e.message, 'error');
      });
    });
    row.appendChild(testBtn);

    const result = ui.el('span', '', { id: 'route-test-result', style: 'font-size:12px;min-height:18px;display:flex;align-items:center;gap:4px;flex-shrink:0' });
    row.appendChild(result);
    card.appendChild(row);

    return card;
  }

  function showAddRouteModal() {
    const unassigned = domainLists.filter(l => !l.route);
    if (!unassigned.length) {
      app.toast(t('page.routes.createDomainListFirst'), 'error');
      return;
    }

    const overlay = ui.el('div', '', { style: 'position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center' });
    const modal = ui.el('div', 'card', { style: 'width:400px;padding:20px' });
    modal.appendChild(ui.el('div', 'card-title', { text: t('page.routes.addRouteTitle'), style: 'margin-bottom:12px' }));

    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.routes.domainList') }));
    const listSelect = ui.el('select', '', { id: 'modal-list-select', style: 'width:100%;padding:6px 8px;margin-bottom:12px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    unassigned.forEach(dl => {
      const o = ui.el('option', '', { value: dl.id, text: dl.name + ' (' + (dl.domain_count || 0) + ' domains)' });
      listSelect.appendChild(o);
    });
    modal.appendChild(listSelect);

    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.routes.route') }));
    const routeSelect = ui.el('select', '', { id: 'modal-route-select', style: 'width:100%;padding:6px 8px;margin-bottom:16px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    populateRouteSelect(routeSelect);
    modal.appendChild(routeSelect);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;justify-content:flex-end' });
    const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('page.routes.cancel') });
    cancelBtn.addEventListener('click', () => overlay.remove());
    btnRow.appendChild(cancelBtn);

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.routes.addRoute') });
    addBtn.addEventListener('click', () => {
      const listId = listSelect.value;
      const route = routeSelect.value;
      if (!listId) return;
      const dl = domainLists.find(d => d.id === listId);
      if (dl) {
        const payload = { ...dl, route, enabled: true };
        api.domainListUpdate(dl.id, payload).then(() => {
          overlay.remove();
          app.toast(t('page.routes.routeAdded'));
          load();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    btnRow.appendChild(addBtn);
    modal.appendChild(btnRow);

    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  }

  function updateModeCard(status) {
    const toggle = document.getElementById('routing-toggle');
    const badge = document.getElementById('routing-status-badge');
    const select = document.getElementById('default-route-select');
    const fb = document.getElementById('routing-fallback-toggle');

    if (toggle && status) toggle.checked = !!status.enabled;
    if (fb && status) fb.checked = status.fallback_pool !== false;
    if (badge && status) {
      if (status.enabled) {
        badge.textContent = 'ON';
        badge.style.background = 'var(--success-bg)';
        badge.style.color = 'var(--success)';
      } else {
        badge.textContent = 'OFF';
        badge.style.background = 'var(--surface-raised)';
        badge.style.color = 'var(--text-muted)';
      }
    }
    if (select && status) {
      populateRouteSelect(select, status.default_route || 'direct');
    }
  }

  function routeTypeOf(route) {
    if (!route) return 'unknown';
    if (route === 'direct') return 'direct';
    if (route === 'pool' || route === 'pool_selected') return 'pool';
    if (route.startsWith('custom:')) return 'custom';
    if (route.startsWith('proxy:')) return 'proxy';
    return 'unknown';
  }

  function routeIconHtml(type) {
    if (type === 'direct') return '◆';
    if (type === 'pool') return '◈';
    if (type === 'custom') return '◉';
    if (type === 'proxy') return '◉';
    return '•';
  }

  function routeLabelHtml(route) {
    const type = routeTypeOf(route);
    if (type === 'direct') return '<span class="route-label direct">' + t('route.direct') + '</span>';
    if (type === 'pool') {
      if (route === 'pool_selected') return '<span class="route-label pool">' + t('route.poolSelected') + '</span>';
      return '<span class="route-label pool">' + t('route.pool') + '</span>';
    }
    if (type === 'custom') {
      const name = route.slice(7);
      return '<span class="route-label custom">' + t('route.custom', { name: ui.escHtml(name) }) + '</span>';
    }
    if (type === 'proxy') return '<span class="route-label custom">' + ui.escHtml(route) + '</span>';
    return '<span class="route-label">' + ui.escHtml(route || '—') + '</span>';
  }

  function updateRulesCard(status, lists) {
    const wrap = document.getElementById('routes-table-wrap');
    const countBadge = document.getElementById('route-count-badge');
    if (!wrap) return;

    const routedLists = (lists || []).filter(l => l.route);
    if (countBadge) countBadge.textContent = routedLists.length;

    if (!routedLists.length) {
      wrap.innerHTML = '<div class="empty" style="padding:12px;font-size:12px">' + t('page.routes.noRoutesAdd') + '</div>';
      return;
    }

    wrap.innerHTML = '';
    const listEl = ui.el('div', 'route-list');

    routedLists.forEach((l, i) => {
      const type = routeTypeOf(l.route);
      const enabled = !!l.enabled;

      const row = ui.el('div', 'route-row' + (enabled ? '' : ' disabled'));
      row.dataset.type = type;
      row.dataset.listId = l.id;

      // Priority badge
      const prioClass = i === 0 ? 'p1' : i === 1 ? 'p2' : i === 2 ? 'p3' : 'p4-plus';
      const prio = ui.el('div', 'route-priority ' + prioClass, { text: String(i + 1) });
      row.appendChild(prio);

      // Type icon
      const icon = ui.el('div', 'route-type-icon ' + type, { text: routeIconHtml(type) });
      row.appendChild(icon);

      // Body: name + meta
      const body = ui.el('div', 'route-body');
      const nameLink = document.createElement('a');
      nameLink.href = '#/domain-lists';
      nameLink.textContent = l.name || l.id;
      const nameDiv = ui.el('div', 'route-name');
      nameDiv.appendChild(nameLink);
      body.appendChild(nameDiv);

      const meta = ui.el('div', 'route-meta');
      const countPill = ui.el('span', 'route-domain-count', { text: ui.fmtNum(l.domain_count || 0) + ' ' + t('common.domains') });
      meta.appendChild(countPill);
      if (l.source === 'manual') {
        const srcBadge = ui.el('span', 'badge badge-gray', { text: 'manual', style: 'font-size:9px' });
        meta.appendChild(srcBadge);
      }
      body.appendChild(meta);
      row.appendChild(body);

      // Route label
      const labelWrap = ui.el('div', '', { html: routeLabelHtml(l.route) });
      row.appendChild(labelWrap);

      // Toggle switch
      const toggle = ui.el('div', 'route-toggle' + (enabled ? ' on' : ''));
      toggle.title = enabled ? t('common.disable') : t('common.enable');
      toggle.addEventListener('click', () => toggleRouteList(l.id));
      row.appendChild(toggle);

      // Reorder arrows
      const reorder = ui.el('div', 'route-reorder');
      const upBtn = ui.el('button', 'route-arrow', { html: '▲', title: t('common.moveUp') });
      upBtn.disabled = (i === 0);
      upBtn.addEventListener('click', () => moveRouteUpAnimated(l.id, row, 'up'));
      reorder.appendChild(upBtn);

      const downBtn = ui.el('button', 'route-arrow', { html: '▼', title: t('common.moveDown') });
      downBtn.disabled = (i === routedLists.length - 1);
      downBtn.addEventListener('click', () => moveRouteUpAnimated(l.id, row, 'down'));
      reorder.appendChild(downBtn);
      row.appendChild(reorder);

      // Delete
      const delBtn = ui.el('button', 'route-delete', { html: '✕', title: t('common.delete') });
      delBtn.addEventListener('click', () => removeRoute(l.id));
      row.appendChild(delBtn);

      // Drag handle
      const dragHandle = ui.el('div', 'route-drag-handle', { text: '⋮⋮', title: t('common.moveUp') });
      row.appendChild(dragHandle);

      attachDragHandlers(row, listEl);

      listEl.appendChild(row);
    });

    wrap.appendChild(listEl);

    listEl.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    });
    listEl.addEventListener('drop', (e) => {
      e.preventDefault();
      if (!_draggedRow) return;
      if (e.target === _placeholder) {
        const nextRow = _placeholder.nextElementSibling;
        const prevRow = _placeholder.previousElementSibling;
        if (nextRow && nextRow.classList.contains('route-row')) {
          performDrop(listEl, _draggedRow, nextRow, true);
        } else if (prevRow && prevRow.classList.contains('route-row')) {
          performDrop(listEl, _draggedRow, prevRow, false);
        }
        return;
      }
      if (e.target === listEl) {
        const rows = Array.from(listEl.querySelectorAll('.route-row'));
        const lastRow = rows[rows.length - 1];
        if (lastRow) performDrop(listEl, _draggedRow, lastRow, false);
      }
    });
  }

  let _draggedRow = null;
  let _placeholder = null;
  let _dropTimer = null;

  function ensurePlaceholder(listEl) {
    if (!_placeholder || !_placeholder.parentNode) {
      _placeholder = ui.el('div', 'route-drop-placeholder');
      _placeholder.addEventListener('dragover', (e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
      });
    }
    if (_placeholder.parentNode !== listEl) {
      listEl.appendChild(_placeholder);
    }
    return _placeholder;
  }

  function attachDragHandlers(row, listEl) {
    const handle = row.querySelector('.route-drag-handle');
    if (!handle) return;

    row.draggable = false;

    handle.addEventListener('mousedown', () => { row.draggable = true; });
    row.addEventListener('dragend', () => { row.draggable = false; });

    row.addEventListener('dragstart', (e) => {
      _draggedRow = row;
      row.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', row.dataset.listId);
      const ghost = document.createElement('div');
      ghost.style.cssText = 'position:absolute;top:-9999px;width:1px;height:1px';
      document.body.appendChild(ghost);
      e.dataTransfer.setDragImage(ghost, 0, 0);
      setTimeout(() => ghost.remove(), 0);
      hidePlaceholder();
    });

    row.addEventListener('dragend', () => {
      row.classList.remove('dragging');
      row.draggable = false;
      _draggedRow = null;
      hidePlaceholder();
    });

    row.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (!_draggedRow || _draggedRow === row) return;

      const rect = row.getBoundingClientRect();
      const midpoint = rect.top + rect.height / 2;
      const insertBefore = e.clientY < midpoint;

      movePlaceholder(listEl, row, insertBefore);
    });

    row.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!_draggedRow || _draggedRow === row) return;
      const rect = row.getBoundingClientRect();
      const midpoint = rect.top + rect.height / 2;
      const insertBefore = e.clientY < midpoint;
      performDrop(listEl, _draggedRow, row, insertBefore);
    });
  }

  function hidePlaceholder() {
    if (!_placeholder) return;
    _placeholder.classList.remove('active');
    if (_placeholder.parentNode) _placeholder.parentNode.removeChild(_placeholder);
  }

  function movePlaceholder(listEl, refRow, insertBefore) {
    const ph = ensurePlaceholder(listEl);

    // already in the right spot?
    const prev = insertBefore ? refRow.previousSibling : (refRow.nextSibling && refRow.nextSibling !== ph ? refRow.nextSibling : null);
    if (ph === refRow.previousSibling && insertBefore) return;
    if (ph === refRow.nextSibling && !insertBefore) return;

    if (insertBefore) {
      listEl.insertBefore(ph, refRow);
    } else {
      const next = refRow.nextSibling;
      if (next && next !== ph) listEl.insertBefore(ph, next);
      else if (next === ph) { /* already after */ }
      else listEl.appendChild(ph);
    }

    requestAnimationFrame(() => ph.classList.add('active'));
  }

  function performDrop(listEl, draggedRow, refRow, insertBefore) {
    const rows = Array.from(listEl.querySelectorAll('.route-row'));
    const currentOrder = rows.map(r => r.dataset.listId);

    const draggedId = draggedRow.dataset.listId;
    const refId = refRow.dataset.listId;

    const order = currentOrder.filter(id => id !== draggedId);
    const refIdx = order.indexOf(refId);
    if (refIdx < 0) { hidePlaceholder(); return; }

    if (insertBefore) {
      order.splice(refIdx, 0, draggedId);
    } else {
      order.splice(refIdx + 1, 0, draggedId);
    }

    hidePlaceholder();
    if (insertBefore) {
      listEl.insertBefore(draggedRow, refRow);
    } else {
      const refNext = refRow.nextSibling;
      if (refNext) listEl.insertBefore(draggedRow, refNext);
      else listEl.appendChild(draggedRow);
    }
    api.routingReorder(order).then(() => { app.toast(t('page.routes.reordered')); load(); }).catch(e => { app.toast('Error: ' + e.message, 'error'); load(); });
  }

  function toggleRouteList(id) {
    api.domainListToggle(id).then(() => { app.toast(t('page.routes.toggled')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function getRoutedOrder() {
    if (!routingStatus || !Array.isArray(routingStatus.lists)) return [];
    return routingStatus.lists.filter(l => l.route).map(l => l.id);
  }

  function moveRouteUpAnimated(id, rowEl, dir) {
    const order = getRoutedOrder();
    const idx = order.indexOf(id);
    if (dir === 'up') {
      if (idx <= 0) return;
      [order[idx - 1], order[idx]] = [order[idx], order[idx - 1]];
    } else {
      if (idx < 0 || idx >= order.length - 1) return;
      [order[idx], order[idx + 1]] = [order[idx + 1], order[idx]];
    }
    const animClass = dir === 'up' ? 'moving-up' : 'moving-down';
    if (rowEl) rowEl.classList.add(animClass);
    const delay = rowEl ? 250 : 0;
    setTimeout(() => {
      api.routingReorder(order).then(() => { app.toast(t('page.routes.reordered')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
    }, delay);
  }

  function moveRouteUp(id) {
    moveRouteUpAnimated(id, null, 'up');
  }

  function moveRouteDown(id) {
    moveRouteUpAnimated(id, null, 'down');
  }

  function removeRoute(id) {
    const dl = domainLists.find(l => l.id === id);
    if (dl) {
      const payload = { ...dl, route: '', enabled: false };
      api.domainListUpdate(id, payload).then(() => { app.toast(t('page.routes.routeRemoved')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
    }
  }

  function populateRouteSelect(selectEl, selectedValue) {
    selectEl.innerHTML = '';
    ROUTE_OPTIONS.forEach(opt => {
      const o = ui.el('option', '', { value: opt.value, text: t(opt.labelKey) });
      if (opt.value === selectedValue) o.selected = true;
      selectEl.appendChild(o);
    });
    if (customProxies.length) {
      const grp = ui.el('optgroup', '', { label: t('route.customProxies') });
      customProxies.filter(p => p.enabled).forEach(p => {
        const label = p.name + ' (' + p.protocol.toUpperCase() + ' ' + p.host + ':' + p.port + ')';
        const o = ui.el('option', '', { value: 'custom:' + p.id, text: label });
        if (('custom:' + p.id) === selectedValue) o.selected = true;
        grp.appendChild(o);
      });
      selectEl.appendChild(grp);
    }
  }

  build();

  async function load() {
    if (_loading) return;
    if (_draggedRow) return;
    _loading = true;
    try {
      let status = {}, lists = [], cpResult = [];
      try { status = await api.routingStatus(); } catch (e) { console.error('routingStatus', e); }
      try { lists = await api.domainLists(); } catch (e) { console.error('domainLists', e); }
      try { cpResult = await api.customProxies(); } catch (e) { console.error('customProxies', e); }
      routingStatus = status;
      domainLists = lists.lists || lists || [];
      customProxies = cpResult.proxies || cpResult || [];
      updateModeCard(status);
      updateRulesCard(status, domainLists);
      const defSelect = document.getElementById('default-route-select');
      if (defSelect) {
        populateRouteSelect(defSelect, status.default_route || 'direct');
      }
    } catch (e) {
      console.error('routes load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});


/* ==== js/pages/schedules.js ==== */
router.register('schedules', (container) => {
  let schedules = [];
  let schedulerStatus = { running: false, paused: false, running_tasks: [] };
  let _loading = false;

  const TASK_TYPE_KEYS = {
    proxy_check: 'page.schedules.taskProxyCheck',
    source_refresh: 'page.schedules.taskSourceRefresh',
    ip_blacklist: 'page.schedules.taskIpBlacklist',
    blocklist: 'page.schedules.taskBlocklist',
    health_check: 'page.schedules.taskHealthCheck',
    history: 'page.schedules.taskHistory',
    clear_dead: 'page.schedules.taskClearDead',
    backup: 'page.schedules.taskBackup',
  };

  const STATUS_VARIANTS = {
    ok: 'green',
    failed: 'red',
    running: 'blue',
    queued: 'yellow',
    skipped: 'gray',
    never: 'gray',
  };

  const STATUS_KEYS = {
    ok: 'page.schedules.statusOk',
    failed: 'page.schedules.statusFailed',
    running: 'page.schedules.statusRunning',
    queued: 'page.schedules.statusQueued',
    skipped: 'page.schedules.statusSkipped',
    never: 'page.schedules.statusNever',
  };

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
    const topRow = ui.el('div', 'grid grid-2 row-stretch', { style: 'flex-shrink:0' });
    topRow.appendChild(buildStatusCard());
    topRow.appendChild(buildLogCard());
    container.appendChild(topRow);
    container.appendChild(buildSchedulesCard());
  }

  function buildStatusCard() {
    const card = ui.card('', '');
    card.id = 'card-scheduler-status';
    card.style.padding = '14px 16px';

    const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;flex-wrap:wrap' });

    const dot = ui.el('span', '', { id: 'sched-status-dot', style: 'width:10px;height:10px;border-radius:50%;background:var(--success);flex-shrink:0' });
    row.appendChild(dot);

    const label = ui.el('span', '', { id: 'sched-status-label', style: 'font-weight:600;font-size:14px', text: t('page.schedules.schedulerRunning') });
    row.appendChild(label);

    const spacer = ui.el('div', '', { style: 'flex:1' });
    row.appendChild(spacer);

    const pauseBtn = ui.el('button', 'btn btn-sm btn-secondary', { id: 'sched-pause-btn', text: t('page.schedules.pauseAll') });
    pauseBtn.addEventListener('click', () => {
      if (schedulerStatus.paused) {
        api.schedulesResume().then(() => { app.toast(t('page.schedules.schedulerRunning')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.schedulesPause().then(() => { app.toast(t('page.schedules.schedulerPaused')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    row.appendChild(pauseBtn);

    card.appendChild(row);

    // Stats row
    const statsRow = ui.el('div', '', { id: 'sched-stats-row', style: 'display:flex;gap:20px;margin-top:12px;flex-wrap:wrap' });
    statsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', html: `<span id="sched-stat-enabled"></span>` }));
    statsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', html: `<span id="sched-stat-running"></span>` }));
    statsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', html: `<span id="sched-stat-next"></span>` }));
    card.appendChild(statsRow);

    return card;
  }

  function buildLogCard() {
    const card = ui.card(t('page.schedules.schedulerLog'), '');
    card.id = 'card-scheduler-log';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', {
      id: 'sched-log-body',
      style: 'overflow-y:auto;flex:1;font-family:monospace;font-size:11px;line-height:1.6;padding:4px 0;min-height:120px;max-height:220px',
    });
    card.appendChild(body);
    return card;
  }

  function buildSchedulesCard() {
    const card = ui.card(t('page.schedules.title'), '');
    card.id = 'card-schedules';
    card.style.overflow = 'auto';

    const header = card.querySelector('.card-header') || card;
    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-bottom:8px' });
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.schedules.newSchedule') });
    addBtn.addEventListener('click', () => showEditor(null));
    btnRow.appendChild(addBtn);
    const restoreBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.schedules.restoreDefaults') });
    restoreBtn.addEventListener('click', () => {
      api.schedulesRestoreDefaults().then((d) => {
        const n = (d.added || []).length;
        app.toast(n ? t('page.schedules.defaultsRestored').replace('{n}', n) : t('page.schedules.defaultsUpToDate'));
        load();
      }).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    btnRow.appendChild(restoreBtn);
    card.insertBefore(btnRow, card.firstChild.nextSibling || card.firstChild);

    const body = ui.el('div', '', { id: 'schedules-body' });
    card.appendChild(body);
    return card;
  }

  function formatInterval(sec) {
    if (!sec || sec <= 0) return '—';
    if (sec < 60) return sec + ' ' + t('units.secondsShort');
    if (sec < 3600) return Math.round(sec / 60) + ' ' + t('units.minutesShort');
    if (sec < 86400) return (sec / 3600).toFixed(sec % 3600 === 0 ? 0 : 1) + ' ' + t('units.hoursShort');
    return (sec / 86400).toFixed(sec % 86400 === 0 ? 0 : 1) + ' ' + t('units.daysShort');
  }

  function formatDuration(sec) {
    if (!sec || sec <= 0) return '—';
    if (sec < 60) return sec.toFixed(sec < 10 ? 1 : 0) + 's';
    const m = Math.floor(sec / 60);
    const s = Math.round(sec % 60);
    if (sec < 3600) return m + 'm' + (s ? ' ' + s + 's' : '');
    const h = Math.floor(sec / 3600);
    const mm = Math.round((sec % 3600) / 60);
    return h + 'h' + (mm ? ' ' + mm + 'm' : '');
  }

  function formatCountdown(s) {
    if (!s.enabled || s.interval_sec <= 0) return '—';
    if (s.countdown === -1) return t('page.schedules.runningNow');
    if (s.countdown === 0 || s.queued) return t('page.schedules.queuedNow');
    const c = s.countdown;
    if (c <= 0) return t('page.schedules.overdue');
    if (c < 60) return c + 's';
    if (c < 3600) return Math.floor(c / 60) + 'm ' + (c % 60) + 's';
    if (c < 86400) return Math.floor(c / 3600) + 'h ' + Math.floor((c % 3600) / 60) + 'm';
    return Math.floor(c / 86400) + 'd ' + Math.floor((c % 86400) / 3600) + 'h';
  }

  function renderSchedules() {
    const body = document.getElementById('schedules-body');
    if (!body) return;
    body.innerHTML = '';

    if (!schedules.length) {
      body.appendChild(ui.emptyState(t('page.schedules.noSchedules')));
      return;
    }

    const table = ui.table(
      [
        { label: t('page.schedules.taskName'), sortKey: 'name' },
        { label: t('page.schedules.interval'), sortKey: 'interval' },
        { label: t('page.schedules.enabled') },
        { label: t('page.schedules.lastRun') },
        { label: t('page.schedules.lastOk') },
        { label: t('page.schedules.duration') },
        { label: t('page.schedules.countdown') },
        { label: t('page.schedules.status') },
        { label: t('page.schedules.actions') },
      ],
      schedules.map(s => [
        ui.escHtml(s.name) + '<br><span style="font-size:11px;color:var(--text-secondary)">' + ui.escHtml(s.id) + '</span>',
        formatInterval(s.interval_sec),
        renderToggle(s),
        s.last_run > 0 ? ui.fmtDateTime(s.last_run) : '—',
        s.last_ok > 0 ? ui.fmtDateTime(s.last_ok) : '—',
        formatDuration(s.last_duration_s),
        '<span class="sched-countdown" data-id="' + ui.escHtml(s.id) + '">' + formatCountdown(s) + '</span>',
        renderStatusBadge(s.last_status),
        renderActions(s),
      ])
    );
    body.appendChild(table);
    tickCountdowns();
  }

  function renderToggle(s) {
    const checked = s.enabled ? 'checked' : '';
    return `<label style="display:inline-flex;align-items:center;cursor:pointer">
      <input type="checkbox" ${checked} onchange="window._schedToggle('${ui.escHtml(s.id)}')" style="cursor:pointer">
    </label>`;
  }

  function tickCountdowns() {
    const cells = document.querySelectorAll('.sched-countdown');
    cells.forEach(cell => {
      const id = cell.getAttribute('data-id');
      const s = schedules.find(x => x.id === id);
      if (!s) return;
      if (s.countdown === -1 || s.countdown === 0 || s.queued) {
        cell.textContent = formatCountdown(s);
        return;
      }
      // Decrement the countdown locally for a smooth realtime feel.
      if (typeof s._liveCountdown !== 'number') s._liveCountdown = s.countdown;
      s._liveCountdown = Math.max(0, s._liveCountdown - 1);
      const live = Object.assign({}, s, { countdown: s._liveCountdown });
      cell.textContent = formatCountdown(live);
    });
    // Sync run/stop buttons with live status between full reloads.
    document.querySelectorAll('.sched-action-run').forEach(btn => {
      const id = btn.getAttribute('data-id');
      const s = schedules.find(x => x.id === id);
      if (!s) return;
      const isRunning = s.last_status === 'running' || s.queued;
      const wasRunning = btn.getAttribute('data-running') === '1';
      if (isRunning !== wasRunning) {
        // Status changed — re-render the actions cell via full reload.
        load();
      }
    });
  }

  function renderStatusBadge(status) {
    const variant = STATUS_VARIANTS[status] || 'gray';
    const label = t(STATUS_KEYS[status] || 'page.schedules.statusNever');
    if (status === 'running') {
      return `<span class="badge badge-${variant}" style="animation:pulse 1.5s infinite">${ui.escHtml(label)}</span>`;
    }
    return `<span class="badge badge-${variant}">${ui.escHtml(label)}</span>`;
  }

  function renderActions(s) {
    const actStyle = 'min-width:32px;height:32px;font-size:15px;padding:4px 8px';
    const isRunning = s.last_status === 'running' || s.queued;
    const runBtn = isRunning
      ? `<button class="btn btn-ghost sched-action-run" data-id="${ui.escHtml(s.id)}" data-running="1" style="${actStyle};color:var(--danger,#dc3545)" onclick="window._schedStop('${ui.escHtml(s.id)}')" title="${t('common.stop') || 'Stop'}">■</button>`
      : `<button class="btn btn-ghost sched-action-run" data-id="${ui.escHtml(s.id)}" data-running="0" style="${actStyle}" onclick="window._schedRun('${ui.escHtml(s.id)}')" title="${t('page.schedules.runNow')}">▶</button>`;
    const editBtn = `<button class="btn btn-ghost" style="${actStyle}" onclick="window._schedEdit('${ui.escHtml(s.id)}')" title="${t('page.schedules.edit')}">✎</button>`;
    const delBtn = `<button class="btn btn-ghost" style="${actStyle}" onclick="window._schedDelete('${ui.escHtml(s.id)}')" title="${t('page.schedules.delete')}">🗑</button>`;
    return `<div style="display:flex;gap:6px">${runBtn}${editBtn}${delBtn}</div>`;
  }

  function updateHeader() {
    const dot = document.getElementById('sched-status-dot');
    const label = document.getElementById('sched-status-label');
    const btn = document.getElementById('sched-pause-btn');
    if (!dot || !label || !btn) return;
    if (schedulerStatus.paused) {
      dot.style.background = 'var(--warning, #f0ad4e)';
      label.textContent = t('page.schedules.schedulerPaused');
      btn.textContent = t('page.schedules.resumeAll');
    } else if (schedulerStatus.running) {
      dot.style.background = 'var(--success, #28a745)';
      label.textContent = t('page.schedules.schedulerRunning');
      btn.textContent = t('page.schedules.pauseAll');
    } else {
      dot.style.background = 'var(--text-secondary, #888)';
      label.textContent = t('page.schedules.schedulerStopped') || t('page.schedules.schedulerPaused');
      btn.textContent = t('page.schedules.resumeAll');
    }
    // Stats
    const enabledEl = document.getElementById('sched-stat-enabled');
    const runningEl = document.getElementById('sched-stat-running');
    const nextEl = document.getElementById('sched-stat-next');
    if (enabledEl) {
      const enabledCount = schedules.filter(s => s.enabled).length;
      enabledEl.textContent = t('page.schedules.enabled') + ': ' + enabledCount + '/' + schedules.length;
    }
    if (runningEl) {
      const runningCount = (schedulerStatus.running_tasks || []).length;
      const queuedCount = (schedulerStatus.queued || []).length;
      runningEl.textContent = t('page.schedules.statusRunning') + ': ' + runningCount +
        (queuedCount ? ' / ' + t('page.schedules.statusQueued') + ': ' + queuedCount : '');
    }
    if (nextEl) {
      const due = schedules.filter(s => s.enabled && s.countdown !== null && s.countdown > 0);
      if (due.length) {
        const next = due.reduce((a, b) => a.countdown < b.countdown ? a : b);
        nextEl.textContent = t('page.schedules.nextRun') + ': ' + formatCountdown(next) + ' (' + next.name + ')';
      } else {
        nextEl.textContent = t('page.schedules.nextRun') + ': —';
      }
    }
  }

  function renderLog(entries) {
    const body = document.getElementById('sched-log-body');
    if (!body) return;
    const wasScrolled = body.scrollTop + body.clientHeight >= body.scrollHeight - 20;
    body.innerHTML = '';
    if (!entries.length) {
      body.appendChild(ui.el('div', '', { style: 'color:var(--text-secondary);padding:8px', text: t('page.schedules.noLogEntries') }));
      return;
    }
    const typeColors = {
      ok: 'var(--success)',
      info: 'var(--text-secondary)',
      warn: 'var(--warning, #f0ad4e)',
      error: 'var(--danger, #dc3545)',
      action: 'var(--accent, #007bff)',
    };
    for (const e of entries) {
      const ts = new Date(e.ts * 1000);
      const timeStr = ts.toLocaleTimeString();
      const color = typeColors[e.type] || typeColors.info;
      const line = ui.el('div', '', {
        style: `padding:1px 0;color:${color};white-space:pre-wrap;word-break:break-all`,
        html: `<span style="color:var(--text-secondary)">${timeStr}</span>  ${ui.escHtml(e.msg)}`,
      });
      body.appendChild(line);
    }
    if (wasScrolled) body.scrollTop = body.scrollHeight;
  }

  async function loadLog() {
    try {
      const data = await api.schedulesLog(50);
      renderLog(data.entries || []);
    } catch (e) {
      // ignore
    }
  }

  function showEditor(existing) {
    const overlay = ui.el('div', '', {
      style: 'position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center'
    });
    const modal = ui.el('div', 'card', { style: 'width:420px;padding:20px' });
    modal.appendChild(ui.el('div', 'card-title', { text: existing ? t('page.schedules.editSchedule') : t('page.schedules.newSchedule'), style: 'margin-bottom:14px' }));

    const isDefault = existing && ['history', 'ip_blacklist_refresh', 'blocklist_refresh', 'health_check', 'hunt_cycle'].includes(existing.id);

    // Name field
    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.schedules.taskName') }));
    const nameInput = ui.el('input', '', {
      style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box',
      value: existing ? existing.name : '',
    });
    modal.appendChild(nameInput);

    // ID field (only for new)
    if (!existing) {
      modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'ID' }));
      const idInput = ui.el('input', '', {
        id: 'sched-edit-id',
        style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box',
      });
      modal.appendChild(idInput);
    }

    // Task type select
    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.schedules.taskType') }));
    const typeSelect = ui.el('select', '', {
      style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box',
    });
    if (existing) typeSelect.disabled = true;
    for (const [ttype, key] of Object.entries(TASK_TYPE_KEYS)) {
      const opt = ui.el('option', '', { value: ttype, text: t(key) });
      if (existing && existing.task_type === ttype) opt.selected = true;
      typeSelect.appendChild(opt);
    }
    modal.appendChild(typeSelect);

    // Interval field
    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.schedules.interval') }));
    const intervalRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-bottom:10px' });
    let currentSec = existing ? existing.interval_sec : 3600;
    let unit = 'seconds';
    let val = currentSec;
    if (currentSec >= 86400 && currentSec % 86400 === 0) { unit = 'days'; val = currentSec / 86400; }
    else if (currentSec >= 3600 && currentSec % 3600 === 0) { unit = 'hours'; val = currentSec / 3600; }
    else if (currentSec >= 60 && currentSec % 60 === 0) { unit = 'minutes'; val = currentSec / 60; }
    const numInput = ui.el('input', '', {
      type: 'number', value: val, min: 0,
      style: 'flex:1;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;box-sizing:border-box',
    });
    const unitSelect = ui.el('select', '', {
      style: 'width:120px;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;box-sizing:border-box',
    });
    const unitOpts = [
      { v: 'seconds', k: 'page.schedules.unitSeconds' },
      { v: 'minutes', k: 'page.schedules.unitMinutes' },
      { v: 'hours', k: 'page.schedules.unitHours' },
      { v: 'days', k: 'page.schedules.unitDays' },
    ];
    for (const u of unitOpts) {
      const opt = ui.el('option', '', { value: u.v, text: t(u.k) });
      if (u.v === unit) opt.selected = true;
      unitSelect.appendChild(opt);
    }
    intervalRow.appendChild(numInput);
    intervalRow.appendChild(unitSelect);
    modal.appendChild(intervalRow);

    // Enabled checkbox
    const enRow = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer;margin-bottom:14px;font-size:13px' });
    const enCb = ui.el('input', '', { type: 'checkbox' });
    if (existing ? existing.enabled : true) enCb.checked = true;
    enRow.appendChild(enCb);
    enRow.appendChild(ui.el('span', '', { text: t('page.schedules.enabled') }));
    modal.appendChild(enRow);

    // Buttons
    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;justify-content:flex-end' });
    const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
    cancelBtn.addEventListener('click', () => overlay.remove());
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('common.save') });
    saveBtn.addEventListener('click', () => {
      const num = parseInt(numInput.value, 10) || 0;
      const multipliers = { seconds: 1, minutes: 60, hours: 3600, days: 86400 };
      const interval_sec = num * multipliers[unitSelect.value];
      const data = {
        name: nameInput.value.trim() || 'Untitled',
        task_type: typeSelect.value,
        interval_sec,
        enabled: enCb.checked,
      };
      if (!existing) {
        const idEl = document.getElementById('sched-edit-id');
        data.id = (idEl ? idEl.value.trim() : '').replace(/[^a-zA-Z0-9_-]/g, '_');
        if (!data.id) { app.toast('ID required', 'error'); return; }
        api.scheduleCreate(data).then(() => {
          app.toast(t('page.schedules.scheduleCreated') || t('common.saved'));
          overlay.remove();
          load();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.scheduleUpdate(existing.id, data).then(() => {
          app.toast(t('common.saved'));
          overlay.remove();
          load();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(saveBtn);
    modal.appendChild(btnRow);

    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  }

  // Global handlers for inline onclick
  window._schedToggle = (id) => {
    api.scheduleToggle(id).then(() => load()).catch(e => app.toast('Error: ' + e.message, 'error'));
  };
  window._schedRun = (id) => {
    api.scheduleRun(id).then(() => { app.toast(t('page.schedules.runStarted') || 'Started'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  };
  window._schedStop = (id) => {
    api.scheduleStop(id).then(() => { app.toast(t('common.stopped') || 'Stopped'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  };
  window._schedEdit = (id) => {
    const s = schedules.find(x => x.id === id);
    if (s) showEditor(s);
  };
  window._schedDelete = (id) => {
    if (!confirm(t('page.schedules.deleteConfirm'))) return;
    api.scheduleDelete(id).then(() => { app.toast(t('common.deleted') || 'Deleted'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  };

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      const data = await api.schedules();
      schedules = data.schedules || [];
      schedules.forEach(s => { s._liveCountdown = undefined; });
      schedulerStatus = data.status || { running: false, paused: false, running_tasks: [] };
      renderSchedules();
      updateHeader();
    } catch (e) {
      // ignore
    } finally {
      _loading = false;
    }
  }

  build();
  load();
  loadLog();
  const pollId = setInterval(load, 3000);
  const logPollId = setInterval(loadLog, 2000);
  const tickId = setInterval(tickCountdowns, 1000);
  if (window._pageIntervals) window._pageIntervals.push(pollId, logPollId, tickId);
  else window._pageIntervals = [pollId, logPollId, tickId];
});


/* ==== js/pages/server.js ==== */
router.register('server', (container) => {
  let aliveProxies = [];
  let customProxies = [];
  let filters = { hideNoHttps: true, hideNoSsl: false, hideMitm: true, hideBlacklisted: true };
  // Last port values reported by the backend. Port inputs are synced only
  // when the SERVER-side value actually changes, so user edits (typing or
  // spinner clicks, which may not focus the input) are never clobbered by
  // the 2s status poll.
  const lastPorts = { http: null, s5: null, tp: null };

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
    httpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:74px;flex-shrink:0', text: t('page.server.http') }));
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
    s5Row.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:74px;flex-shrink:0', text: t('page.server.socks5') }));
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

    const tpRow = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px;padding-top:6px;border-top:1px solid var(--border-subtle)' });
    tpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:74px;flex-shrink:0', text: t('page.server.transparent') }));
    tpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.port') }));
    const tpPortInp = ui.el('input', '', { id: 'transparent-port', type: 'number', value: '17477', min: '1024', max: '65535', style: 'width:72px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    tpRow.appendChild(tpPortInp);
    const tpStartBtn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.server.start'), id: 'btn-transparent-start' });
    tpStartBtn.addEventListener('click', () => api.transparentStart(tpPortInp.value).then(() => app.toast(t('page.server.transparentStarted'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    tpRow.appendChild(tpStartBtn);
    const tpStopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.server.stop'), id: 'btn-transparent-stop' });
    tpStopBtn.addEventListener('click', () => api.transparentStop().then(() => app.toast(t('page.server.transparentStopped'))).catch(e => app.toast(t('common.error', {message: e.message}), 'error')));
    tpRow.appendChild(tpStopBtn);
    card.appendChild(tpRow);

    const connRow = ui.el('div', '', { style: 'display:flex;gap:18px;align-items:baseline;margin-top:2px' });
    const httpConn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
    httpConn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.http') }));
    httpConn.appendChild(ui.el('span', '', { id: 'proxy-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
    connRow.appendChild(httpConn);
    const s5Conn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
    s5Conn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.socks5') }));
    s5Conn.appendChild(ui.el('span', '', { id: 'socks5-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
    connRow.appendChild(s5Conn);
    const tpConn = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
    tpConn.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.transparent') }));
    tpConn.appendChild(ui.el('span', '', { id: 'transparent-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
    connRow.appendChild(tpConn);
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

    const statusRow = ui.el('div', '', { id: 'mode-status-row', style: 'margin-top:8px;font-size:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap' });
    card.appendChild(statusRow);

    const channelRow = ui.el('div', '', { id: 'channel-status-row', style: 'margin-top:6px;font-size:12px;display:flex;align-items:center;gap:6px;flex-wrap:wrap' });
    card.appendChild(channelRow);
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

  function updateProxyControl(ps, ss, ts) {
    const el = id => document.getElementById(id);
    const bar = el('proxy-status-bar');
    const dot = el('proxy-dot');
    const txt = el('proxy-status-text');
    const httpRunning = ps && ps.running;
    const s5Running = ss && ss.running;
    const tpRunning = ts && ts.running;
    const anyRunning = httpRunning || s5Running || tpRunning;

    if (anyRunning) {
      if (bar) { bar.style.background = 'var(--success-bg)'; bar.style.borderColor = 'var(--success)'; bar.style.color = 'var(--success)'; }
      if (dot) dot.style.background = 'var(--success)';
      const parts = [];
      if (httpRunning) parts.push('HTTP:' + (ps.port || 17277));
      if (s5Running) parts.push('SOCKS5:' + (ss.port || 17278));
      if (tpRunning) parts.push('TP:' + (ts.port || 17477));
      if (txt) txt.textContent = t('page.server.running') + ' ' + parts.join(', ');
    } else {
      if (bar) { bar.style.background = 'var(--surface-raised)'; bar.style.borderColor = 'var(--border)'; bar.style.color = 'var(--text-secondary)'; }
      if (dot) dot.style.background = 'var(--text-muted)';
      if (txt) txt.textContent = t('page.server.stopped');
    }
    if (el('btn-proxy-start')) el('btn-proxy-start').disabled = httpRunning;
    if (el('btn-proxy-stop')) el('btn-proxy-stop').disabled = !httpRunning;
    const syncPort = (id, port, key) => {
      if (!port || port === lastPorts[key]) return;
      lastPorts[key] = port;
      const inp = el(id);
      if (inp) inp.value = port;
    };
    syncPort('proxy-port', ps && ps.port, 'http');
    if (el('btn-socks5-start')) el('btn-socks5-start').disabled = s5Running;
    if (el('btn-socks5-stop')) el('btn-socks5-stop').disabled = !s5Running;
    syncPort('socks5-port', ss && ss.port, 's5');
    if (el('btn-transparent-start')) el('btn-transparent-start').disabled = tpRunning;
    if (el('btn-transparent-stop')) el('btn-transparent-stop').disabled = !tpRunning;
    syncPort('transparent-port', ts && ts.port, 'tp');
    const httpConn = ps ? (ps.connections || 0) : 0;
    const s5Conn = ss ? (ss.connections || 0) : 0;
    const tpConn = ts ? (ts.connections || 0) : 0;
    if (el('proxy-connections')) el('proxy-connections').textContent = httpConn;
    if (el('socks5-connections')) el('socks5-connections').textContent = s5Conn;
    if (el('transparent-connections')) el('transparent-connections').textContent = tpConn;
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

  function updateProxyLog(ps, ss, ts) {
    const log = document.getElementById('proxy-log');
    if (!log) return;
    const httpLog = (ps && ps.log) || [];
    const s5Log = (ss && ss.log) || [];
    const tpLog = (ts && ts.log) || [];
    const all = [...httpLog.map(e => ({...e, type: 'HTTP'})), ...s5Log.map(e => ({...e, type: 'SOCKS5'})), ...tpLog.map(e => ({...e, type: 'TP'}))]
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

  function updateChannelStatus(ch) {
    const row = document.getElementById('channel-status-row');
    if (!row) return;
    row.innerHTML = '';
    const route = (ch && ch.channel_route) || '';
    const label = ui.el('span', '', { style: 'color:var(--text-secondary);font-weight:600', text: t('page.server.channel') + ':' });
    row.appendChild(label);
    if (!route || route === 'direct') {
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-muted)', text: t('page.server.channelDirect') }));
      return;
    }
    const p = ch && ch.proxy;
    if (p && ch.available) {
      row.appendChild(ui.el('span', '', { style: 'color:var(--info);font-weight:600', text: t('page.server.channelVia', { addr: p.host + ':' + p.port }) }));
    } else {
      row.appendChild(ui.el('span', '', { style: 'color:var(--danger);font-weight:600', text: t('page.server.channelUnavailable') }));
    }
    const link = ui.el('a', '', { style: 'color:var(--info);text-decoration:underline;cursor:pointer;font-size:11px', text: '→ ' + t('page.server.channelManage') });
    link.addEventListener('click', () => router.navigate('connectivity'));
    row.appendChild(link);
  }

  async function load() {
    try {
      const [ps, ss, ts, rs, ch] = await Promise.all([
        api.proxyStatus().catch(e => { console.error('proxyStatus', e); return {}; }),
        api.socks5Status().catch(e => { console.error('socks5Status', e); return {}; }),
        api.transparentStatus().catch(e => { console.error('transparentStatus', e); return {}; }),
        api.routingStatus().catch(e => { console.error('routingStatus', e); return {}; }),
        api.channelStatus().catch(e => { console.error('channelStatus', e); return {}; }),
      ]);
      updateProxyControl(ps, ss, ts);
      updateModeStatus(ps, !!(rs && rs.enabled));
      updateChannelStatus(ch);
      updateProxyLog(ps, ss, ts);
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


/* ==== js/pages/settings.js ==== */
router.register('settings', (container) => {
  let config = {};

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const card = ui.card(t('page.settings.title'));
    card.id = 'settings-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'auto';
    container.appendChild(card);

    const btns = ui.el('div', '', { style: 'display:flex;gap:8px;margin-top:16px' });
    const saveBtn = ui.el('button', 'btn btn-primary', { text: t('page.settings.saveSettings') });
    saveBtn.addEventListener('click', () => save());
    btns.appendChild(saveBtn);

    const reloadBtn = ui.el('button', 'btn btn-secondary', { text: t('page.settings.reload') });
    reloadBtn.addEventListener('click', () => load());
    btns.appendChild(reloadBtn);
    container.appendChild(btns);
  }

  build();

  async function load() {
    try {
      const data = await api.settings();
      config = data;
      render();
      app.toast('Settings loaded');
    } catch (e) {
      console.error('settings load', e);
      app.toast('Failed to load settings', 'error');
    }
  }

  function render() {
    const card = document.getElementById('settings-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.settings.title') }));
    card.appendChild(header);

    const grid = ui.el('div', 'grid grid-2');
    grid.appendChild(renderGroup('Server', [
      { key: 'server.web_listen', label: 'Web UI Listen', type: 'text' },
      { key: 'server.http_listen', label: 'HTTP Proxy Listen', type: 'text' },
      { key: 'server.socks5_listen', label: 'SOCKS5 Proxy Listen', type: 'text' },
      { key: 'server.transparent_listen', label: 'Transparent Proxy Listen', type: 'text' },
      { key: 'server.transparent_enabled', label: 'Transparent Enabled', type: 'checkbox' },
    ]));
    grid.appendChild(renderGroup('Hunt', [
      { key: 'hunt.parallel', label: 'Parallel Checks', type: 'number' },
      { key: 'hunt.timeout', label: 'Timeout (sec)', type: 'number' },
      { key: 'hunt.us_only', label: 'US Only', type: 'checkbox' },
      { key: 'hunt.health_interval', label: 'Health Interval (sec)', type: 'number' },
      { key: 'hunt.health_parallel', label: 'Health Parallel', type: 'number' },
    ]));
    grid.appendChild(renderGroup('Proxies', [
      { key: 'proxies.validate_interval', label: 'Validate Interval (sec)', type: 'number' },
      { key: 'proxies.validate_parallel', label: 'Validate Parallel', type: 'number' },
      { key: 'proxies.health_interval', label: 'Health Interval (sec)', type: 'number' },
      { key: 'proxies.health_parallel', label: 'Health Parallel', type: 'number' },
      { key: 'proxies.max_failures', label: 'Max Failures', type: 'number' },
      { key: 'proxies.cooldown', label: 'Cooldown (sec)', type: 'number' },
      { key: 'proxies.strategy', label: 'Strategy', type: 'select', options: ['round_robin', 'random'] },
    ]));
    grid.appendChild(renderGroup('Logging', [
      { key: 'logging.level', label: 'Log Level', type: 'select', options: ['DEBUG', 'INFO', 'WARN', 'ERROR'] },
      { key: 'logging.file', label: 'Log File', type: 'text' },
      { key: 'logging.max_size_mb', label: 'Max Size (MB)', type: 'number' },
      { key: 'logging.backup_count', label: 'Backup Count', type: 'number' },
    ]));
    card.appendChild(grid);
  }

  function renderGroup(title, fields) {
    const group = ui.el('div', 'card', { style: 'padding:16px' });
    group.appendChild(ui.el('div', '', { style: 'font-weight:600;margin-bottom:12px;font-size:14px', text: title }));
    fields.forEach(f => {
      const row = ui.el('div', '', { style: 'margin-bottom:10px' });
      row.appendChild(ui.el('label', '', { style: 'display:block;font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: f.label }));
      const val = getValue(config, f.key);
      if (f.type === 'checkbox') {
        const wrap = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer' });
        const inp = ui.el('input', '', { type: 'checkbox', 'data-key': f.key });
        inp.checked = !!val;
        wrap.appendChild(inp);
        wrap.appendChild(ui.el('span', '', { style: 'font-size:13px', text: f.label }));
        row.appendChild(wrap);
      } else if (f.type === 'select') {
        const inp = ui.el('select', '', { 'data-key': f.key, style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px' });
        (f.options || []).forEach(o => {
          const opt = ui.el('option', '', { value: o, text: o });
          if (o === val) opt.selected = true;
          inp.appendChild(opt);
        });
        row.appendChild(inp);
      } else {
        const inp = ui.el('input', '', { type: f.type, 'data-key': f.key, value: val !== undefined && val !== null ? val : '', style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px' });
        row.appendChild(inp);
      }
      group.appendChild(row);
    });
    return group;
  }

  function getValue(obj, key) {
    return key.split('.').reduce((o, k) => o && o[k], obj);
  }

  function setValue(obj, key, value) {
    const parts = key.split('.');
    const last = parts.pop();
    const target = parts.reduce((o, k) => {
      if (!o[k]) o[k] = {};
      return o[k];
    }, obj);
    target[last] = value;
  }

  async function save() {
    const newConfig = JSON.parse(JSON.stringify(config));
    document.querySelectorAll('#settings-card [data-key]').forEach(el => {
      const key = el.getAttribute('data-key');
      let val = el.type === 'checkbox' ? el.checked : el.value;
      if (el.type === 'number') val = parseFloat(val);
      setValue(newConfig, key, val);
    });
    try {
      await api.saveSettings(newConfig);
      app.toast('Settings saved');
    } catch (e) {
      app.toast('Error: ' + e.message, 'error');
    }
  }

  load();
});


/* ==== js/pages/traffic-flow.js ==== */
router.register('traffic-flow', (container) => {
  let routingStatus = null;
  let proxyStatus = null;
  let channelStatus = null;
  let domainLists = [];
  let customProxies = [];
  let traceResult = null;
  let _loading = false;
  let zoom = 1;

  const ZOOM_MIN = 0.4;
  const ZOOM_MAX = 3;
  const ZOOM_STEP = 0.15;
  const BASE_W = 820;

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

    const flowCard = ui.card(t('page.trafficFlow.title'));
    flowCard.id = 'card-traffic-flow';
    flowCard.style.flex = '1';
    flowCard.style.display = 'flex';
    flowCard.style.flexDirection = 'column';
    flowCard.style.minHeight = '0';

    const controls = ui.el('div', 'flow-controls');

    const statusBadge = ui.el('span', '', { id: 'flow-routing-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600' });
    controls.appendChild(statusBadge);

    const serverBadge = ui.el('span', '', { id: 'flow-server-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600' });
    controls.appendChild(serverBadge);

    const channelBadge = ui.el('span', '', { id: 'flow-channel-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600;display:none' });
    controls.appendChild(channelBadge);

    const legend = ui.el('div', 'flow-legend');
    legend.appendChild(legendItem('var(--success)', t('page.trafficFlow.activePath')));
    legend.appendChild(legendItem('var(--border)', t('page.trafficFlow.inactivePath')));
    legend.appendChild(legendItem('var(--accent)', t('page.trafficFlow.decision')));
    controls.appendChild(legend);

    const spacer = ui.el('div', '', { style: 'flex:1' });
    controls.appendChild(spacer);

    const zoomGroup = ui.el('div', 'flow-zoom');
    const zOut = ui.el('button', 'btn btn-sm btn-ghost', { text: '\u2212' });
    zOut.addEventListener('click', () => setZoom(zoom - ZOOM_STEP));
    zoomGroup.appendChild(zOut);

    const zLabel = ui.el('span', 'flow-zoom-label', { id: 'flow-zoom-label', text: '100%' });
    zoomGroup.appendChild(zLabel);

    const zIn = ui.el('button', 'btn btn-sm btn-ghost', { text: '+' });
    zIn.addEventListener('click', () => setZoom(zoom + ZOOM_STEP));
    zoomGroup.appendChild(zIn);

    const zReset = ui.el('button', 'btn btn-sm btn-ghost', { text: '1:1' });
    zReset.addEventListener('click', () => setZoom(1));
    zoomGroup.appendChild(zReset);
    controls.appendChild(zoomGroup);

    const input = ui.el('input', '', { id: 'flow-trace-input', type: 'text', placeholder: t('page.trafficFlow.tracePlaceholder'), style: 'width:200px;padding:5px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    controls.appendChild(input);

    const traceBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.trafficFlow.trace') });
    traceBtn.addEventListener('click', () => doTrace(input.value.trim()));
    controls.appendChild(traceBtn);

    const clearBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.clear') });
    clearBtn.addEventListener('click', () => { input.value = ''; traceResult = null; renderFlow(); });
    controls.appendChild(clearBtn);

    flowCard.appendChild(controls);

    const wrap = ui.el('div', 'flow-wrap', { id: 'flow-wrap' });
    wrap.addEventListener('wheel', (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setZoom(zoom + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
    }, { passive: false });
    flowCard.appendChild(wrap);

    container.appendChild(flowCard);
  }

  function setZoom(v) {
    zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.round(v * 100) / 100));
    const label = document.getElementById('flow-zoom-label');
    if (label) label.textContent = Math.round(zoom * 100) + '%';
    const svg = document.querySelector('#flow-wrap .flow-svg');
    if (svg) {
      svg.style.width = (BASE_W * zoom) + 'px';
    }
  }

  function legendItem(color, label) {
    const item = ui.el('div', 'flow-legend-item');
    item.appendChild(ui.el('span', 'flow-legend-dot', { style: 'background:' + color }));
    item.appendChild(ui.el('span', '', { text: label }));
    return item;
  }

  function doTrace(domain) {
    if (!domain) return;
    api.routingTest(domain).then(result => {
      traceResult = result;
      renderFlow();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function routeTypeOf(route) {
    if (!route) return 'unknown';
    if (route === 'direct') return 'direct';
    if (route === 'pool') return 'pool';
    if (route === 'pool_selected') return 'pool_selected';
    if (route.startsWith('custom:')) return 'custom';
    if (route.startsWith('proxy:')) return 'proxy';
    return 'unknown';
  }

  function routeLabel(route) {
    if (route === 'direct') return t('route.direct');
    if (route === 'pool') return t('route.pool');
    if (route === 'pool_selected') return t('route.poolSelected');
    if (route.startsWith('custom:')) {
      const cp = customProxies.find(p => ('custom:' + p.id) === route);
      return cp ? cp.name : route.slice(7);
    }
    if (route.startsWith('proxy:')) return route.slice(6);
    return route || '\u2014';
  }

  function renderFlow() {
    const wrap = document.getElementById('flow-wrap');
    if (!wrap) return;
    wrap.innerHTML = '';

    const enabled = !!(routingStatus && routingStatus.enabled);
    const running = !!(proxyStatus && proxyStatus.running);
    const directMode = !!(proxyStatus && proxyStatus.direct_mode);
    const activeProxy = proxyStatus && proxyStatus.active_proxy ? proxyStatus.active_proxy.address : null;
    const port = proxyStatus ? proxyStatus.port : '\u2014';

    const routedLists = (domainLists || []).filter(l => l.route && l.enabled);
    const defaultRoute = routingStatus ? (routingStatus.default_route || 'direct') : 'direct';
    const tracedRoute = traceResult ? traceResult.route : null;
    const hasMatch = !!(traceResult && traceResult.matched_list);

    const reachable = new Set();
    routedLists.forEach(l => reachable.add(routeTypeOf(l.route)));
    reachable.add(routeTypeOf(defaultRoute));
    if (!enabled) {
      if (directMode) reachable.add('direct');
      if (activeProxy) reachable.add('proxy');
    }
    if (customProxies && customProxies.length) {
      routedLists.forEach(l => { if (routeTypeOf(l.route) === 'custom') reachable.add('custom'); });
    } else {
      reachable.delete('custom');
    }

    const destOrder = ['direct', 'pool', 'pool_selected', 'custom', 'proxy'];
    const destMeta = {
      direct: { label: t('route.direct'), sub: t('page.trafficFlow.directExit') },
      pool: { label: t('route.pool'), sub: t('page.trafficFlow.bestProxy') },
      pool_selected: { label: t('route.poolSelected'), sub: t('page.trafficFlow.selectedProxy') },
      custom: { label: t('route.custom', { name: '' }).replace(/[: ]*$/, ''), sub: '' },
      proxy: { label: t('route.proxy'), sub: activeProxy || '' },
    };
    const destNodes = destOrder.filter(rt => reachable.has(rt)).map(rt => ({
      id: 'dest-' + rt, routeType: rt, label: destMeta[rt].label, sub: destMeta[rt].sub, kind: 'dest',
      active: isDestActive(rt, enabled, running, directMode, activeProxy, tracedRoute, hasMatch, defaultRoute),
    }));

    const W = BASE_W;
    const cx = W / 2;
    const nodeW = 180;
    const nodeH = 48;
    const dW = 140;
    const dH = 58;

    const offX = cx - 190;
    const onX = cx + 190;

    const nodes = {};
    nodes.client = { id: 'client', label: t('page.trafficFlow.client'), kind: 'io', x: cx, y: 38, w: nodeW, h: nodeH, active: running };
    nodes.server = { id: 'server', label: t('page.trafficFlow.proxyServer'), sub: running ? ('127.0.0.1:' + port) : t('page.trafficFlow.stopped'), kind: 'engine', x: cx, y: 122, w: nodeW, h: nodeH, active: running };
    nodes.routing = { id: 'routing', label: t('page.trafficFlow.routingEngine'), sub: enabled ? 'ON' : 'OFF', kind: 'decision', x: cx, y: 206, w: nodeW, h: nodeH, active: running };

    nodes.off = { id: 'off', label: t('page.trafficFlow.routingOff'), sub: t('page.trafficFlow.proxyControl'), kind: 'branch', x: offX, y: 296, w: nodeW, h: nodeH, active: running && !enabled };
    if (directMode) nodes.off.sub2 = t('page.trafficFlow.directExit');
    else if (activeProxy) nodes.off.sub2 = activeProxy;
    else nodes.off.sub2 = t('page.trafficFlow.noUpstream');

    nodes.on = { id: 'on', label: t('page.trafficFlow.routingOn'), kind: 'branch', x: onX, y: 296, w: nodeW, h: nodeH, active: running && enabled };
    nodes.rules = { id: 'rules', label: t('page.trafficFlow.domainRules'), sub: routedLists.length + ' ' + t('common.routes'), kind: 'list', x: onX, y: 378, w: nodeW, h: nodeH, active: running && enabled };
    nodes.match = { id: 'match', label: t('page.trafficFlow.matchDecision'), sub: hasMatch ? (traceResult.matched_list || '') : (traceResult ? t('page.trafficFlow.noMatch') : ''), kind: 'decision', x: onX, y: 460, w: nodeW, h: nodeH, active: running && enabled };
    nodes.default = { id: 'default', label: t('page.trafficFlow.defaultRoute'), sub: routeLabel(defaultRoute), kind: 'branch', x: onX, y: 542, w: nodeW, h: nodeH, active: running && enabled && !hasMatch };

    const destY = 648;
    const n = destNodes.length;
    const dMargin = 70;
    const dArea = W - 2 * dMargin;
    destNodes.forEach((d, i) => {
      d.x = n === 1 ? cx : dMargin + i * dArea / (n - 1);
      d.y = destY;
      d.w = dW; d.h = dH;
      nodes[d.id] = d;
    });

    const channelRoute = channelStatus ? (channelStatus.channel_route || '') : '';
    const channelActive = !!(channelRoute && channelRoute !== 'direct' && channelStatus.proxy);
    const channelY = 758;
    let internetY = 758;
    if (channelActive) {
      const cp = channelStatus.proxy;
      nodes.channel = {
        id: 'channel', label: t('page.trafficFlow.channel'),
        sub: cp ? (cp.host + ':' + cp.port) : '',
        kind: 'engine', x: cx, y: channelY, w: nodeW, h: nodeH,
        active: running && channelStatus.available,
      };
      internetY = 850;
    }

    nodes.internet = { id: 'internet', label: t('page.trafficFlow.internet'), sub: traceResult ? traceResult.domain : '', kind: 'io', x: cx, y: internetY, w: nodeW, h: nodeH, active: running };

    const totalH = internetY + nodeH / 2 + 24;

    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgEl.setAttribute('viewBox', `0 0 ${W} ${totalH}`);
    svgEl.setAttribute('preserveAspectRatio', 'xMidYMin meet');
    svgEl.classList.add('flow-svg');
    svgEl.style.width = (BASE_W * zoom) + 'px';
    svgEl.style.maxWidth = 'none';
    svgEl.style.maxHeight = 'none';

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    ['active', 'inactive'].forEach(kind => {
      const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
      marker.setAttribute('id', 'arrow-' + kind);
      marker.setAttribute('viewBox', '0 0 10 10');
      marker.setAttribute('refX', '8');
      marker.setAttribute('refY', '5');
      marker.setAttribute('markerWidth', '7');
      marker.setAttribute('markerHeight', '7');
      marker.setAttribute('orient', 'auto');
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M0,0 L10,5 L0,10 z');
      path.setAttribute('fill', kind === 'active' ? 'var(--success)' : 'var(--border)');
      marker.appendChild(path);
      defs.appendChild(marker);
    });
    svgEl.appendChild(defs);

    const onActive = running && enabled;
    const offActive = running && !enabled;

    const edges = [
      { from: 'client', to: 'server', active: running },
      { from: 'server', to: 'routing', active: running },
      { from: 'routing', to: 'off', active: offActive, curve: true },
      { from: 'routing', to: 'on', active: onActive, curve: true },
      { from: 'on', to: 'rules', active: onActive },
      { from: 'rules', to: 'match', active: onActive },
    ];

    const defaultActive = onActive && !hasMatch;
    edges.push({ from: 'match', to: 'default', active: defaultActive });

    const matchedDest = hasMatch ? destNodes.find(d => d.routeType === routeTypeOf(tracedRoute)) : null;
    if (matchedDest) {
      edges.push({ from: 'match', to: matchedDest.id, active: onActive && hasMatch, curve: true, dashed: true });
    }

    const defaultDest = destNodes.find(d => d.routeType === routeTypeOf(defaultRoute));
    if (defaultDest) {
      edges.push({ from: 'default', to: defaultDest.id, active: defaultActive, curve: true, dashed: true });
    }

    destNodes.forEach(d => {
      if (offActive) {
        edges.push({ from: 'off', to: d.id, active: d.active, curve: true, dashed: true });
      }
    });

    if (channelActive) {
      destNodes.forEach(d => {
        edges.push({ from: d.id, to: 'channel', active: d.active, curve: true });
      });
      edges.push({ from: 'channel', to: 'internet', active: running && channelStatus.available });
    } else {
      destNodes.forEach(d => {
        edges.push({ from: d.id, to: 'internet', active: d.active, curve: true });
      });
    }

    edges.forEach(e => drawEdge(svgEl, nodes[e.from], nodes[e.to], e.active, e.curve, e.dashed, e.thin));

    Object.values(nodes).forEach(n => drawNode(svgEl, n, n.active));

    wrap.appendChild(svgEl);

    updateBadges(enabled, running, directMode);
  }

  function isDestActive(rt, enabled, running, directMode, activeProxy, tracedRoute, hasMatch, defaultRoute) {
    if (!running) return false;
    if (!enabled) {
      return (rt === 'direct' && directMode) || (rt === 'proxy' && !!activeProxy);
    }
    if (hasMatch) return routeTypeOf(tracedRoute) === rt;
    return routeTypeOf(defaultRoute) === rt;
  }

  function drawEdge(svg, from, to, active, curve, dashed, thin) {
    if (!from || !to) return;
    const x1 = from.x, y1 = from.y + from.h / 2;
    const x2 = to.x, y2 = to.y - to.h / 2;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    let d;
    if (curve) {
      const my = (y1 + y2) / 2;
      d = `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`;
    } else {
      d = `M${x1},${y1} L${x2},${y2}`;
    }
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', active ? 'var(--success)' : 'var(--border)');
    path.setAttribute('stroke-width', thin ? '1.4' : '2');
    if (dashed) path.setAttribute('stroke-dasharray', '5 4');
    path.setAttribute('marker-end', `url(#arrow-${active ? 'active' : 'inactive'})`);
    if (active) {
      path.classList.add('flow-edge-active');
      const dash = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
      dash.setAttribute('attributeName', 'stroke-dashoffset');
      dash.setAttribute('from', '20');
      dash.setAttribute('to', '0');
      dash.setAttribute('dur', '0.8s');
      dash.setAttribute('repeatCount', 'indefinite');
      if (!dashed) path.setAttribute('stroke-dasharray', '8 4');
      path.appendChild(dash);
    }
    svg.appendChild(path);
  }

  function nodeColor(kind, active) {
    if (kind === 'decision') return { fill: 'var(--accent-light)', stroke: 'var(--accent)' };
    if (kind === 'io') return { fill: active ? 'var(--success-bg)' : 'var(--surface-raised)', stroke: active ? 'var(--success)' : 'var(--border)' };
    if (kind === 'engine') return { fill: 'var(--info-bg)', stroke: 'var(--info)' };
    if (kind === 'dest') return { fill: active ? 'var(--success-bg)' : 'var(--surface-raised)', stroke: active ? 'var(--success)' : 'var(--border)' };
    if (kind === 'list') return { fill: 'var(--surface-raised)', stroke: 'var(--border)' };
    return { fill: 'var(--surface-raised)', stroke: active ? 'var(--success)' : 'var(--border)' };
  }

  function drawNode(svg, node, active) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const w = node.w, h = node.h;
    const x = node.x - w / 2, y = node.y - h / 2;
    const col = nodeColor(node.kind, active);

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', x);
    rect.setAttribute('y', y);
    rect.setAttribute('width', w);
    rect.setAttribute('height', h);
    rect.setAttribute('rx', 8);
    rect.setAttribute('fill', col.fill);
    rect.setAttribute('stroke', col.stroke);
    rect.setAttribute('stroke-width', active ? '2.5' : '1.5');
    g.appendChild(rect);

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', node.x);
    label.setAttribute('y', y + (node.sub || node.sub2 ? 20 : h / 2 + 5));
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('font-size', '12');
    label.setAttribute('font-weight', '600');
    label.setAttribute('fill', 'var(--text-primary)');
    label.textContent = node.label;
    g.appendChild(label);

    let subY = y + 36;
    if (node.sub) {
      const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      sub.setAttribute('x', node.x);
      sub.setAttribute('y', subY);
      sub.setAttribute('text-anchor', 'middle');
      sub.setAttribute('font-size', '10');
      sub.setAttribute('fill', active ? 'var(--success)' : 'var(--text-secondary)');
      sub.textContent = node.sub;
      g.appendChild(sub);
      subY += 13;
    }
    if (node.sub2) {
      const sub2 = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      sub2.setAttribute('x', node.x);
      sub2.setAttribute('y', subY);
      sub2.setAttribute('text-anchor', 'middle');
      sub2.setAttribute('font-size', '10');
      sub2.setAttribute('fill', 'var(--text-muted)');
      sub2.textContent = node.sub2;
      g.appendChild(sub2);
    }

    svg.appendChild(g);
  }

  function updateBadges(enabled, running, directMode) {
    const rb = document.getElementById('flow-routing-badge');
    if (rb) {
      rb.textContent = enabled ? t('page.trafficFlow.routingOn') : t('page.trafficFlow.routingOff');
      rb.style.background = enabled ? 'var(--success-bg)' : 'var(--surface-raised)';
      rb.style.color = enabled ? 'var(--success)' : 'var(--text-muted)';
    }
    const sb = document.getElementById('flow-server-badge');
    if (sb) {
      if (running) {
        sb.textContent = t('page.trafficFlow.serverRunning') + (directMode ? ' \u00b7 ' + t('page.trafficFlow.directMode') : '');
        sb.style.background = 'var(--success-bg)';
        sb.style.color = 'var(--success)';
      } else {
        sb.textContent = t('page.trafficFlow.stopped');
        sb.style.background = 'var(--surface-raised)';
        sb.style.color = 'var(--text-muted)';
      }
    }
    const cb = document.getElementById('flow-channel-badge');
    if (cb) {
      const route = channelStatus ? (channelStatus.channel_route || '') : '';
      if (route && route !== 'direct' && channelStatus.proxy) {
        cb.style.display = '';
        const ok = channelStatus.available;
        cb.textContent = t('page.trafficFlow.channel') + ': ' + channelStatus.proxy.host + ':' + channelStatus.proxy.port;
        cb.style.background = ok ? 'var(--info-bg)' : 'var(--danger-bg)';
        cb.style.color = ok ? 'var(--info)' : 'var(--danger)';
      } else {
        cb.style.display = 'none';
      }
    }
  }

  build();
  renderFlow();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      const [status, ps, dl, cp, ch] = await Promise.all([
        api.routingStatus().catch(e => { console.error('routingStatus', e); return {}; }),
        api.proxyStatus().catch(e => { console.error('proxyStatus', e); return {}; }),
        api.domainLists().catch(e => { console.error('domainLists', e); return { lists: [] }; }),
        api.customProxies().catch(e => { console.error('customProxies', e); return { proxies: [] }; }),
        api.channelStatus().catch(e => { console.error('channelStatus', e); return {}; }),
      ]);
      routingStatus = status;
      proxyStatus = ps;
      domainLists = dl.lists || dl || [];
      customProxies = cp.proxies || cp || [];
      channelStatus = ch;
      renderFlow();
    } catch (e) {
      console.error('traffic-flow load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});

