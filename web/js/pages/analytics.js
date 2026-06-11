router.register('analytics', (container) => {
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';

  const row1 = ui.el('div', 'grid grid-2 row-stretch');
  const poolCard = ui.card(t('page.analytics.poolSizeOverTime'));
  poolCard.id = 'analytics-pool';
  row1.appendChild(poolCard);

  const trafficCard = ui.card(t('page.analytics.trafficVolume'));
  trafficCard.id = 'analytics-traffic';
  row1.appendChild(trafficCard);

  container.appendChild(row1);

  const row2 = ui.el('div', 'grid grid-2 row-stretch');
  const bwCard = ui.card(t('page.analytics.bandwidth24h'));
  bwCard.id = 'analytics-bandwidth';
  row2.appendChild(bwCard);

  const latCard = ui.card(t('page.analytics.avgResponseTime'));
  latCard.id = 'analytics-latency';
  row2.appendChild(latCard);

  container.appendChild(row2);

  const row3 = ui.el('div', 'grid grid-2 row-stretch');
  const errTrendCard = ui.card(t('page.analytics.errorTrend'));
  errTrendCard.id = 'analytics-errors';
  row3.appendChild(errTrendCard);

  const eventsCard = ui.card(t('page.analytics.eventHistory'));
  eventsCard.id = 'analytics-events';
  row3.appendChild(eventsCard);

  container.appendChild(row3);

  function responsiveSvg(innerSvg, viewBoxW, viewBoxH) {
    return `<div style="flex:1;min-height:0;display:flex"><svg width="100%" height="100%" viewBox="0 0 ${viewBoxW} ${viewBoxH}" preserveAspectRatio="xMidYMid meet">${innerSvg}</svg></div>`;
  }

  async function load() {
    let h24 = [], h6h = [];
    try { h24 = await api.history('24h'); } catch (e) {}
    try { h6h = await api.history('6h'); } catch (e) {}
    const pts = h24.length ? h24 : h6h;

    if (pts.length >= 2) {
      const labels = pts.map(p => {
        const d = new Date(p.ts * 1000);
        return `${d.getHours()}:${d.getMinutes().toString().padStart(2,'0')}`;
      });

      // Pool size
      const poolEl = document.getElementById('analytics-pool');
      if (poolEl) {
        const alive = pts.map(p => p.alive || 0);
        const dead = pts.map(p => p.dead || 0);
        poolEl.innerHTML = '';
        poolEl.appendChild(ui.el('div', 'card-header', { html: `<div class="card-title">${t('page.analytics.poolSizeOverTime')}</div>` }));
        const VB_W = 500, VB_H = 200;
        const pad = { top: 10, right: 10, bottom: 30, left: 40 };
        const cw = VB_W - pad.left - pad.right;
        const ch = VB_H - pad.top - pad.bottom;
        const allData = [...alive, ...dead];
        const min = Math.min(...allData); const max = Math.max(...allData); const range = max - min || 1;
        const mkPath = data => data.map((v, i) => {
          const x = pad.left + (i / (data.length - 1)) * cw;
          const y = pad.top + ch - ((v - min) / range) * ch;
          return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
        }).join(' ');
        const mkArea = (data, pathD) => pathD + ` L${(pad.left + cw).toFixed(1)},${pad.top + ch} L${pad.left},${pad.top + ch} Z`;
        let gridLines = '';
        for (let i = 0; i <= 4; i++) {
          const y = pad.top + (ch / 4) * i;
          gridLines += `<line x1="${pad.left}" y1="${y}" x2="${pad.left + cw}" y2="${y}" stroke="var(--border)" stroke-dasharray="2,2"/>`;
        }
        const alivePath = mkPath(alive);
        const deadPath = mkPath(dead);
        const innerSvg = `
          ${gridLines}
          <path d="${alivePath}" fill="none" stroke="var(--success)" stroke-width="2"/>
          <path d="${mkArea(alive, alivePath)}" fill="var(--success)" opacity="0.15"/>
          <path d="${deadPath}" fill="none" stroke="var(--danger)" stroke-width="2"/>
          <path d="${mkArea(dead, deadPath)}" fill="var(--danger)" opacity="0.1"/>
          <text x="${pad.left + 10}" y="${pad.top + 2}" fill="var(--success)" font-size="10">${t('page.analytics.alive')}</text>
          <text x="${pad.left + 60}" y="${pad.top + 2}" fill="var(--danger)" font-size="10">${t('page.analytics.dead')}</text>
          ${[min, (min + max) / 2, max].map((v, i) => {
            const y = pad.top + ch - (i / 2) * ch;
            return `<text x="${pad.left - 6}" y="${y + 4}" text-anchor="end" fill="var(--text-muted)" font-size="10">${v.toFixed(0)}</text>`;
          }).join('')}
        `;
        poolEl.appendChild(ui.el('div', '', { html: responsiveSvg(innerSvg, VB_W, VB_H) }));
      }

      // Traffic volume
      const trafficEl = document.getElementById('analytics-traffic');
      if (trafficEl) {
        trafficEl.innerHTML = '';
        trafficEl.appendChild(ui.el('div', 'card-header', { html: `<div class="card-title">${t('page.analytics.trafficVolume')}</div>` }));
        const reqData = pts.map(p => p.requests || 0);
        const chartWrap = ui.el('div', '', { style: 'flex:1;min-height:0;display:flex' });
        chartWrap.innerHTML = charts.lineChart(reqData, { width: 500, height: 200, labels, color: 'var(--accent)', fillArea: true, responsive: true });
        trafficEl.appendChild(chartWrap);
      }

      // Bandwidth
      const bwEl = document.getElementById('analytics-bandwidth');
      if (bwEl) {
        bwEl.innerHTML = '';
        bwEl.appendChild(ui.el('div', 'card-header', { html: `<div class="card-title">${t('page.analytics.bandwidth24h')}</div>` }));
        const VB_W = 500, VB_H = 200;
        const pad = { top: 10, right: 10, bottom: 30, left: 40 };
        const cw = VB_W - pad.left - pad.right;
        const ch = VB_H - pad.top - pad.bottom;
        const bwIn = pts.map(p => (p.bandwidth_in || 0) / 1024);
        const bwOut = pts.map(p => (p.bandwidth_out || 0) / 1024);
        const all = [...bwIn, ...bwOut];
        const min = Math.min(...all); const max = Math.max(...all); const range = max - min || 1;
        const mkPath = data => data.map((v, i) => {
          const x = pad.left + (i / (data.length - 1)) * cw;
          const y = pad.top + ch - ((v - min) / range) * ch;
          return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
        }).join(' ');
        let gridLines = '';
        for (let i = 0; i <= 4; i++) {
          const y = pad.top + (ch / 4) * i;
          gridLines += `<line x1="${pad.left}" y1="${y}" x2="${pad.left + cw}" y2="${y}" stroke="var(--border)" stroke-dasharray="2,2"/>`;
        }
        const inPath = mkPath(bwIn);
        const outPath = mkPath(bwOut);
        const innerSvg = `
          ${gridLines}
          <path d="${inPath}" fill="none" stroke="var(--info)" stroke-width="2"/>
          <path d="${inPath} L${(pad.left + cw).toFixed(1)},${pad.top + ch} L${pad.left},${pad.top + ch} Z" fill="var(--info)" opacity="0.1"/>
          <path d="${outPath}" fill="none" stroke="var(--warning)" stroke-width="2"/>
          <text x="${pad.left + 10}" y="${pad.top + 2}" fill="var(--info)" font-size="10">${t('page.analytics.inKB')}</text>
          <text x="${pad.left + 80}" y="${pad.top + 2}" fill="var(--warning)" font-size="10">${t('page.analytics.outKB')}</text>
          ${[min, (min + max) / 2, max].map((v, i) => {
            const y = pad.top + ch - (i / 2) * ch;
            return `<text x="${pad.left - 6}" y="${y + 4}" text-anchor="end" fill="var(--text-muted)" font-size="10">${v.toFixed(1)}</text>`;
          }).join('')}
        `;
        bwEl.appendChild(ui.el('div', '', { html: responsiveSvg(innerSvg, VB_W, VB_H) }));
      }

      // Avg response time
      const latEl = document.getElementById('analytics-latency');
      if (latEl) {
        latEl.innerHTML = '';
        latEl.appendChild(ui.el('div', 'card-header', { html: `<div class="card-title">${t('page.analytics.avgResponseTime')}</div>` }));
        const latData = pts.map(p => (p.avg_latency || 0) * 1000);
        const chartWrap = ui.el('div', '', { style: 'flex:1;min-height:0;display:flex' });
        chartWrap.innerHTML = charts.lineChart(latData, { width: 500, height: 200, labels, color: 'var(--warning)', fillArea: true, responsive: true });
        latEl.appendChild(chartWrap);
      }

      // Error trend
      const errEl = document.getElementById('analytics-errors');
      if (errEl) {
        errEl.innerHTML = '';
        errEl.appendChild(ui.el('div', 'card-header', { html: `<div class="card-title">${t('page.analytics.errorTrend')}</div>` }));
        const failData = pts.map(p => p.connections_failed || 0);
        const chartWrap = ui.el('div', '', { style: 'flex:1;min-height:0;display:flex' });
        chartWrap.innerHTML = charts.lineChart(failData, { width: 500, height: 200, labels, color: 'var(--danger)', fillArea: true, responsive: true });
        errEl.appendChild(chartWrap);
      }
    } else {
      ['analytics-pool', 'analytics-traffic', 'analytics-bandwidth', 'analytics-latency', 'analytics-errors'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.appendChild(ui.el('div', 'empty', { text: t('page.analytics.notEnoughData'), style: 'padding:16px' }));
      });
    }

    // Event history
    const eventsEl = document.getElementById('analytics-events');
    if (eventsEl) {
      eventsEl.innerHTML = '';
      eventsEl.appendChild(ui.el('div', 'card-header', { html: `<div class="card-title">${t('page.analytics.eventHistory')}</div>` }));
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
