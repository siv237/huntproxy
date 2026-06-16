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
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.overflow = 'hidden';
    return card;
  }

  const row1 = ui.el('div', 'grid grid-2 row-stretch');
  row1.appendChild(makeChartCard(t('page.analytics.poolSizeOverTime'), 'analytics-pool'));
  row1.appendChild(makeChartCard(t('page.analytics.trafficVolume'), 'analytics-traffic'));
  container.appendChild(row1);

  const row2 = ui.el('div', 'grid grid-2 row-stretch');
  row2.appendChild(makeChartCard(t('page.analytics.bandwidth24h'), 'analytics-bandwidth'));
  row2.appendChild(makeChartCard(t('page.analytics.avgResponseTime'), 'analytics-latency'));
  container.appendChild(row2);

  const row3 = ui.el('div', 'grid grid-2 row-stretch');
  row3.appendChild(makeChartCard(t('page.analytics.errorTrend'), 'analytics-errors'));
  row3.appendChild(makeChartCard(t('page.analytics.eventHistory'), 'analytics-events'));
  container.appendChild(row3);

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

  load();
});
