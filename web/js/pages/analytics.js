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

  function renderHeatmap() {
    const card = document.getElementById('analytics-heatmap');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.analytics.proxyHeatmap') }));
    const headerRight = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px' });
    const legend = ui.el('div', 'proxy-heatmap-legend');
    legend.innerHTML = `<span><span class="proxy-heatmap-legend-dot ok"></span>${ui.escHtml(t('page.analytics.heatmapOk'))}</span><span><span class="proxy-heatmap-legend-dot err"></span>${ui.escHtml(t('page.analytics.heatmapErr'))}</span><span><span class="proxy-heatmap-legend-dot none"></span>${ui.escHtml(t('page.analytics.heatmapNone'))}</span>`;
    headerRight.appendChild(legend);
    const recheckBtn = ui.el('button', 'btn btn-xs btn-secondary', { text: t('page.analytics.recheckAll') });
    recheckBtn.id = 'heatmap-recheck-btn';
    recheckBtn.addEventListener('click', () => startRecheck(recheckBtn));
    headerRight.appendChild(recheckBtn);
    header.appendChild(headerRight);
    card.appendChild(header);

    const body = ui.el('div', 'proxy-heatmap');
    card.appendChild(body);

    drawHeatmapBody(body);

    if (_heatmapPolling) {
      const btn = document.getElementById('heatmap-recheck-btn');
      if (btn) { btn.disabled = true; btn.textContent = t('common.testing'); }
    }
  }

  function drawHeatmapBody(body) {
    api.proxyHeatmap(72).then(data => {
      const proxies = data.proxies || [];
      if (!proxies.length) {
        body.appendChild(ui.el('div', 'empty', { text: t('page.analytics.heatmapEmpty'), style: 'padding:16px' }));
        card.appendChild(body);
        return;
      }
      const segs = data.segments || 72;

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
          const label = cls === 'ok' ? (dimmed ? t('page.analytics.heatmapOkDimmed') : t('page.analytics.heatmapOk')) : cls === 'err' ? (dimmed ? t('page.analytics.heatmapErrDimmed') : t('page.analytics.heatmapErr')) : t('page.analytics.heatmapNone');
          cell.title = `${p.address} — ${label}`;
          bar.appendChild(cell);
        }
        row.appendChild(bar);
        scroll.appendChild(row);
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
    btn.disabled = true;
    btn.textContent = t('common.testing');
    api.healthStart().then(() => {
      app.toast(t('common.recheckStarted'));
      _heatmapPolling = setInterval(async () => {
        const body = document.querySelector('#analytics-heatmap .proxy-heatmap');
        if (body) drawHeatmapBody(body);
        try {
          const s = await api.snapshot();
          if (!s.running || s.phase !== 'health') {
            clearInterval(_heatmapPolling);
            _heatmapPolling = null;
            btn.disabled = false;
            btn.textContent = t('page.analytics.recheckAll');
            if (body) drawHeatmapBody(body);
          }
        } catch (e) { /* keep polling */ }
      }, 2000);
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

  async function load() {
    let h24 = [], h6h = [];
    try { h24 = await api.history('24h'); } catch (e) { console.error('history 24h', e); }
    try { h6h = await api.history('6h'); } catch (e) { console.error('history 6h', e); }
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
