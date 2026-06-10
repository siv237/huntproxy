router.register('connectivity', (container) => {
  let canaryData = null;
  let history = [];
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
    container.appendChild(buildStatusCard());
    container.appendChild(buildDirectInfoCard());
    container.appendChild(buildHostsCard());
    container.appendChild(buildGraphCard());
  }

  function buildStatusCard() {
    const card = ui.card('Internet Connectivity');
    card.id = 'card-canary-status';

    const indicator = ui.el('div', '', { id: 'canary-big-indicator', style: 'display:flex;align-items:center;gap:16px;margin-bottom:12px' });
    const dot = ui.el('div', '', { id: 'canary-big-dot', style: 'width:48px;height:48px;border-radius:50%;background:var(--text-muted);flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:22px;transition:background .3s' });
    dot.textContent = '?';
    indicator.appendChild(dot);

    const info = ui.el('div', '', { style: 'flex:1' });
    info.innerHTML = '<div id="canary-big-text" style="font-size:18px;font-weight:700;color:var(--text-muted)">Checking...</div>'
      + '<div id="canary-big-sub" style="font-size:12px;color:var(--text-secondary);margin-top:4px"></div>';
    indicator.appendChild(info);

    card.appendChild(indicator);
    return card;
  }

  function buildDirectInfoCard() {
    const card = ui.card('Direct Connection');
    card.id = 'card-direct-info';

    const grid = ui.el('div', '', { id: 'direct-info-grid', style: 'display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:8px' });
    const fields = [
      { id: 'di-ip', label: 'IP Address', value: '—' },
      { id: 'di-country', label: 'Country', value: '—' },
      { id: 'di-city', label: 'City', value: '—' },
      { id: 'di-isp', label: 'ISP', value: '—' },
    ];
    fields.forEach(f => {
      const item = ui.el('div', '', { style: 'padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
      item.appendChild(ui.el('div', '', { style: 'font-size:10px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.5px', text: f.label }));
      item.appendChild(ui.el('div', '', { id: f.id, style: 'font-size:14px;font-weight:600;margin-top:2px', text: '—' }));
      grid.appendChild(item);
    });
    card.appendChild(grid);
    return card;
  }

  function buildHostsCard() {
    const card = ui.card('Canary Hosts');
    card.id = 'card-canary-hosts';

    const tblWrap = ui.el('div', '', { id: 'canary-hosts-tbl', style: 'margin-bottom:12px' });
    card.appendChild(tblWrap);

    const editor = ui.el('div', '', { id: 'canary-hosts-editor', style: 'display:flex;gap:8px;align-items:center' });
    editor.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-secondary)', text: 'Hosts (one per line):' }));
    const textarea = ui.el('textarea', '', { id: 'canary-hosts-input', rows: '2', placeholder: 'ya.ru\ngoogle.com\n2ip.ru', style: 'flex:1;padding:6px 10px;font-size:12px;font-family:ui-monospace,monospace;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);resize:vertical' });
    editor.appendChild(textarea);
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: 'Save' });
    saveBtn.addEventListener('click', () => {
      const text = document.getElementById('canary-hosts-input').value;
      const hosts = text.split('\n').map(h => h.trim()).filter(h => h);
      if (!hosts.length) { app.toast('Add at least one host', 'error'); return; }
      api.canarySetHosts(hosts).then(() => {
        app.toast('Canary hosts updated');
        load();
      }).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    editor.appendChild(saveBtn);
    card.appendChild(editor);

    return card;
  }

  function buildGraphCard() {
    const card = ui.card('Availability (last 24h)');
    card.id = 'card-canary-graph';

    const canvas = ui.el('canvas', '', { id: 'canary-canvas', style: 'width:100%;height:120px' });
    card.appendChild(canvas);

    const legend = ui.el('div', '', { style: 'display:flex;gap:16px;font-size:11px;margin-top:6px' });
    legend.innerHTML = '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:2px;background:var(--success)"></span> Online</span>'
      + '<span style="display:flex;align-items:center;gap:4px"><span style="width:10px;height:10px;border-radius:2px;background:var(--danger)"></span> Offline</span>';
    card.appendChild(legend);

    return card;
  }

  function updateStatusCard(data) {
    if (!data) return;
    const dot = document.getElementById('canary-big-dot');
    const text = document.getElementById('canary-big-text');
    const sub = document.getElementById('canary-big-sub');
    if (!dot || !text) return;

    if (data.alive) {
      dot.style.background = 'var(--success)';
      dot.textContent = '✓';
      text.style.color = 'var(--success)';
      text.textContent = 'Internet: Online';
    } else {
      dot.style.background = 'var(--danger)';
      dot.textContent = '✗';
      text.style.color = 'var(--danger)';
      dot.style.animation = 'blink 1s infinite';
      text.textContent = 'Internet: Offline';
    }
    if (sub) {
      const pct = data.total > 0 ? Math.round(data.alive_count / data.total * 100) : 0;
      sub.textContent = `${data.alive_count}/${data.total} hosts reachable (${pct}%)`;
    }
  }

  function updateDirectInfo(data) {
    if (!data) return;
    const setEl = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val || '—';
    };
    setEl('di-ip', data.direct_ip);
    setEl('di-country', data.direct_country);
    setEl('di-city', data.direct_city);
    setEl('di-isp', data.direct_isp);
  }

  function updateHostsCard(data) {
    if (!data) return;
    const wrap = document.getElementById('canary-hosts-tbl');
    const input = document.getElementById('canary-hosts-input');
    if (!wrap) return;

    if (input && !input.dataset.loaded) {
      input.value = (data.canary_hosts || []).join('\n');
      input.dataset.loaded = '1';
    }

    const hosts = data.hosts || {};
    const entries = Object.entries(hosts);
    if (!entries.length) {
      wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No canary hosts</div>';
      return;
    }

    const headers = [
      { label: 'Host', width: '200px' },
      { label: 'Status', width: '80px', align: 'center' },
      { label: 'Response', width: '80px', align: 'center' },
    ];

    const rows = entries.map(([host, ok]) => [
      `<span style="font-family:ui-monospace,monospace;font-size:12px">${ui.escHtml(host)}</span>`,
      ok
        ? '<span style="color:var(--success);font-weight:600">Reachable</span>'
        : '<span style="color:var(--danger);font-weight:600">Unreachable</span>',
      ok
        ? '<span style="color:var(--success);font-size:11px">TCP 443 OK</span>'
        : '<span style="color:var(--danger);font-size:11px">Timeout / Refused</span>',
    ]);

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  function updateGraph(hist) {
    const canvas = document.getElementById('canary-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    canvas.width = rect.width * (window.devicePixelRatio || 1);
    canvas.height = rect.height * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    const W = rect.width;
    const H = rect.height;

    ctx.clearRect(0, 0, W, H);

    if (!hist || !hist.length) {
      ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted') || '#888';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('No data yet', W / 2, H / 2);
      return;
    }

    const barW = Math.max(2, Math.min(6, W / hist.length));
    const gap = 1;
    const totalW = hist.length * (barW + gap);
    const startX = Math.max(0, (W - totalW) / 2);
    const barH = H - 20;

    for (let i = 0; i < hist.length; i++) {
      const entry = hist[i];
      const x = startX + i * (barW + gap);
      const alive = entry.alive;
      ctx.fillStyle = alive
        ? (getComputedStyle(document.documentElement).getPropertyValue('--success') || '#1a7f37')
        : (getComputedStyle(document.documentElement).getPropertyValue('--danger') || '#cf222e');
      ctx.fillRect(x, 10, barW, barH);
    }

    const ts0 = hist[0].ts;
    const ts1 = hist[hist.length - 1].ts;
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--text-muted') || '#888';
    ctx.font = '9px sans-serif';
    ctx.textAlign = 'left';
    ctx.fillText(new Date(ts0 * 1000).toLocaleTimeString(), 0, H - 2);
    ctx.textAlign = 'right';
    ctx.fillText(new Date(ts1 * 1000).toLocaleTimeString(), W, H - 2);
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
      }
      updateGraph(hist);

      // Update sidebar indicator
      const dot = document.getElementById('canary-dot');
      const text = document.getElementById('canary-text');
      if (dot && text && data) {
        if (data.alive) {
          dot.className = 'status-dot online';
          text.textContent = 'Internet: OK';
        } else {
          dot.className = 'status-dot offline';
          text.textContent = 'Internet: DOWN';
        }
      }
    } catch (e) {
      console.error('connectivity load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 10000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
