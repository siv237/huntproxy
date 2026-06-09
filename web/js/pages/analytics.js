router.register('analytics', (container) => {
  container.innerHTML = '';

  const row1 = ui.el('div', 'grid grid-2');

  const poolCard = ui.card('Pool Size Over Time');
  poolCard.id = 'analytics-pool';
  row1.appendChild(poolCard);

  const trafficCard = ui.card('Traffic Volume');
  trafficCard.id = 'analytics-traffic';
  row1.appendChild(trafficCard);

  container.appendChild(row1);

  const row2 = ui.el('div', 'grid grid-2');

  const bwCard = ui.card('Bandwidth (24h)');
  bwCard.id = 'analytics-bandwidth';
  row2.appendChild(bwCard);

  const latCard = ui.card('Avg Response Time');
  latCard.id = 'analytics-latency';
  row2.appendChild(latCard);

  container.appendChild(row2);

  const row3 = ui.el('div', 'grid grid-2');

  const errTrendCard = ui.card('Error Trend');
  errTrendCard.id = 'analytics-errors';
  row3.appendChild(errTrendCard);

  const eventsCard = ui.card('Event History');
  eventsCard.id = 'analytics-events';
  row3.appendChild(eventsCard);

  container.appendChild(row3);

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
        const total = pts.map(p => p.total || 0);
        poolEl.innerHTML = '';
        poolEl.appendChild(ui.el('div', 'card-header', { html: '<div class="card-title">Pool Size Over Time</div>' }));
        const svg = `<svg width="500" height="200" viewBox="0 0 500 200">
          ${[alive, dead].map((data, idx) => {
            const min = Math.min(...data); const max = Math.max(...data); const range = max - min || 1;
            const color = idx === 0 ? 'var(--success)' : 'var(--danger)';
            const opacity = idx === 0 ? '0.15' : '0.1';
            const pathD = data.map((v, i) => {
              const x = 40 + (i / (data.length - 1)) * 440;
              const y = 10 + 160 - ((v - min) / range) * 160;
              return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
            }).join(' ');
            return `<path d="${pathD}" fill="none" stroke="${color}" stroke-width="2"/><path d="${pathD} L${(40 + 440).toFixed(1)},170 L40,170 Z" fill="${color}" opacity="${opacity}"/>`;
          }).join('')}
          <text x="50" y="12" fill="var(--success)" font-size="10">Alive</text>
          <text x="100" y="12" fill="var(--danger)" font-size="10">Dead</text>
        </svg>`;
        poolEl.appendChild(ui.el('div', '', { html: svg }));
      }

      // Traffic volume
      const trafficEl = document.getElementById('analytics-traffic');
      if (trafficEl) {
        trafficEl.innerHTML = '';
        trafficEl.appendChild(ui.el('div', 'card-header', { html: '<div class="card-title">Traffic Volume</div>' }));
        const reqData = pts.map(p => p.requests || 0);
        trafficEl.appendChild(ui.el('div', '', {
          html: charts.lineChart(reqData, { width: 500, height: 200, labels, color: 'var(--accent)', fillArea: true })
        }));
      }

      // Bandwidth
      const bwEl = document.getElementById('analytics-bandwidth');
      if (bwEl) {
        bwEl.innerHTML = '';
        bwEl.appendChild(ui.el('div', 'card-header', { html: '<div class="card-title">Bandwidth (24h)</div>' }));
        const bwIn = pts.map(p => (p.bandwidth_in || 0) / 1024);
        const bwOut = pts.map(p => (p.bandwidth_out || 0) / 1024);
        const all = [...bwIn, ...bwOut];
        const min = Math.min(...all); const max = Math.max(...all); const range = max - min || 1;
        const mkPath = data => data.map((v, i) => {
          const x = 40 + (i / (data.length - 1)) * 440;
          const y = 10 + 160 - ((v - min) / range) * 160;
          return (i === 0 ? 'M' : 'L') + x.toFixed(1) + ',' + y.toFixed(1);
        }).join(' ');
        const svg = `<svg width="500" height="200" viewBox="0 0 500 200">
          <path d="${mkPath(bwIn)}" fill="none" stroke="var(--info)" stroke-width="2"/>
          <path d="${mkPath(bwIn)} L${(40+440).toFixed(1)},170 L40,170 Z" fill="var(--info)" opacity="0.1"/>
          <path d="${mkPath(bwOut)}" fill="none" stroke="var(--warning)" stroke-width="2"/>
          <text x="50" y="12" fill="var(--info)" font-size="10">In (KB)</text>
          <text x="120" y="12" fill="var(--warning)" font-size="10">Out (KB)</text>
        </svg>`;
        bwEl.appendChild(ui.el('div', '', { html: svg }));
      }

      // Avg response time
      const latEl = document.getElementById('analytics-latency');
      if (latEl) {
        latEl.innerHTML = '';
        latEl.appendChild(ui.el('div', 'card-header', { html: '<div class="card-title">Avg Response Time</div>' }));
        const latData = pts.map(p => (p.avg_latency || 0) * 1000);
        latEl.appendChild(ui.el('div', '', {
          html: charts.lineChart(latData, { width: 500, height: 200, labels, color: 'var(--warning)', fillArea: true })
        }));
      }

      // Error trend
      const errEl = document.getElementById('analytics-errors');
      if (errEl) {
        errEl.innerHTML = '';
        errEl.appendChild(ui.el('div', 'card-header', { html: '<div class="card-title">Error Trend</div>' }));
        const failData = pts.map(p => p.connections_failed || 0);
        errEl.appendChild(ui.el('div', '', {
          html: charts.lineChart(failData, { width: 500, height: 200, labels, color: 'var(--danger)', fillArea: true })
        }));
      }
    } else {
      ['analytics-pool', 'analytics-traffic', 'analytics-bandwidth', 'analytics-latency', 'analytics-errors'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.appendChild(ui.el('div', 'empty', { text: 'Not enough data yet — keep the proxy running', style: 'padding:16px' }));
      });
    }

    // Event history
    const eventsEl = document.getElementById('analytics-events');
    if (eventsEl) {
      eventsEl.innerHTML = '';
      eventsEl.appendChild(ui.el('div', 'card-header', { html: '<div class="card-title">Event History</div>' }));
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
          eventsEl.appendChild(ui.table(headers, rows));
        } else {
          eventsEl.appendChild(ui.el('div', 'empty', { text: 'No events yet' }));
        }
      } catch (e) {
        eventsEl.appendChild(ui.el('div', 'empty', { text: 'Could not load events' }));
      }
    }
  }

  load();
});
