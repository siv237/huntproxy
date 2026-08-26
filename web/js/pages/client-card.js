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
    card.appendChild(ui.el('div', 'cc-sec-title', { text: t('clientCard.history') }));
    if (!recent.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.proxyControl.noRecentRequests') }));
      return card;
    }
    const list = ui.el('div', 'cc-hist-list');
    recent.forEach(r => {
      const host = ui.hostOf(r.target);
      const item = ui.el('div', 'cc-hist-item');
      item.dataset.key = (r.ts || 0) + '|' + (r.target || '');
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
    };
    return icons[name] || '';
  },
};

window.clientCard = clientCard;
