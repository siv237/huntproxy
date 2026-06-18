const proxyCard = {
  async show(addr) {
    const overlay = ui.el('div', 'proxy-card-overlay', {
      style: 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px'
    });
    const modal = ui.el('div', 'proxy-card');
    modal.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t('common.loading')}</div>`;
    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);

    try {
      const p = await api.proxyDetail(addr);
      this._render(modal, p, overlay);
    } catch (e) {
      modal.innerHTML = `<div style="padding:40px;color:var(--danger)">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    }
  },

  _render(modal, p, overlay) {
    modal.innerHTML = '';

    modal.appendChild(this._topBar(p, overlay));

    const content = ui.el('div', 'content');
    modal.appendChild(content);

    content.appendChild(this._hero(p));

    const midGrid = ui.el('div', 'proxy-card-grid-3');
    midGrid.appendChild(this._performance(p));
    midGrid.appendChild(this._security(p));
    midGrid.appendChild(this._network(p));
    content.appendChild(midGrid);

    const bottomGrid = ui.el('div', 'proxy-card-grid');
    bottomGrid.appendChild(this._timeline(p));
    bottomGrid.appendChild(this._scoreBreakdown(p));
    content.appendChild(bottomGrid);

    content.appendChild(this._suitability(p));

    modal.appendChild(this._actions(p, overlay));
  },

  _refresh(modal, addr, overlay) {
    modal.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t('common.loading')}</div>`;
    api.proxyDetail(addr).then(p => {
      this._render(modal, p, overlay);
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
    const isp = p.isp || '';

    const wrap = ui.el('div', 'proxy-card-hero');

    const main = ui.el('div', 'proxy-card-hero-main');
    main.appendChild(ui.el('div', `proxy-card-status ${status.cls}`, { text: status.label }));
    main.appendChild(ui.el('div', 'proxy-card-address', { text: p.address }));

    const meta = ui.el('div', 'proxy-card-meta');
    if (flag) meta.appendChild(ui.el('span', 'flag', { text: flag, style: 'font-size:14px' }));
    meta.appendChild(ui.el('span', '', { text: location }));
    if (isp) {
      meta.appendChild(ui.el('span', 'dot', { text: '•' }));
      meta.appendChild(ui.el('span', '', { text: isp }));
    }
    if (p.last_check) {
      meta.appendChild(ui.el('span', 'dot', { text: '•' }));
      meta.appendChild(ui.el('span', '', { text: t('proxyCard.lastCheck') + ' ' + ui.ago(p.last_check) }));
    }
    main.appendChild(meta);

    const badges = ui.el('div', 'proxy-card-badges');
    const proto = (p.protocol || 'http').toUpperCase();
    badges.appendChild(ui.badge(proto, 'gray'));
    if (p.ssl_supported) badges.appendChild(ui.badge('SSL', 'cyan'));
    if (p.supports_connect) badges.appendChild(ui.badge('CONNECT', 'blue'));
    if (p.mitm_suspect) badges.appendChild(ui.badge('MITM', 'red'));
    main.appendChild(badges);
    wrap.appendChild(main);

    const rating = ui.el('div', 'proxy-card-rating');
    rating.appendChild(ui.el('div', 'proxy-card-rating-label', { text: t('proxyCard.rating') }));
    const val = ui.el('div', 'proxy-card-rating-value', { text: String(score), style: `color:${scoreColor}` });
    rating.appendChild(val);
    const bar = ui.el('div', 'proxy-card-rating-bar');
    bar.appendChild(ui.el('div', '', { style: `width:${score}%;background:${scoreColor}` }));
    rating.appendChild(bar);
    wrap.appendChild(rating);

    return wrap;
  },

  _status(p) {
    if (p.in_blacklist) return { cls: 'bad', label: t('proxyCard.status.blocked') };
    if (p.last_status !== 'ok') return { cls: 'bad', label: t('proxyCard.status.unstable') };
    if (p.mitm_suspect) return { cls: 'warn', label: t('proxyCard.status.degraded') };
    if ((p.success_rate || 0) < 0.8) return { cls: 'warn', label: t('proxyCard.status.degraded') };
    return { cls: 'good', label: t('proxyCard.status.ready') };
  },

  _performance(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.performance'), this._svg('activity')));

    const grid = ui.el('div', 'proxy-card-kpi-grid');

    const avgLat = p.latency_avg || 0;
    const lastLat = p.last_latency || 0;
    const latValue = avgLat ? ui.fmtLatency(avgLat) : ui.fmtLatency(lastLat);
    const latGood = avgLat ? avgLat < 1 : lastLat < 1;
    const latColor = latGood ? 'var(--success)' : (avgLat || lastLat) < 3 ? 'var(--warning)' : 'var(--danger)';
    const latPct = Math.max(0, Math.min(100, 100 - ((avgLat || lastLat) * 40)));
    grid.appendChild(this._kpi(latValue, t('proxyCard.avgLatency'), latPct, latColor));

    const speed = p.speed_avg || 0;
    const speedValue = speed ? speed.toFixed(0) : '—';
    const speedUnit = speed ? 'KB/s' : '';
    const speedPct = Math.max(0, Math.min(100, (speed / 300) * 100));
    const speedColor = speed > 100 ? 'var(--success)' : speed > 30 ? 'var(--warning)' : 'var(--danger)';
    grid.appendChild(this._kpi(speedValue, t('proxyCard.avgSpeed'), speedPct, speedColor, speedUnit));

    const sr = p.success_rate || 0;
    const srPct = Math.round(sr * 100);
    const srColor = sr >= 0.95 ? 'var(--success)' : sr >= 0.8 ? 'var(--warning)' : 'var(--danger)';
    grid.appendChild(this._kpi(srPct + '%', t('proxyCard.successRate'), srPct, srColor));

    const checks = (p.checks_total || 0);
    const checksOk = (p.checks_ok || 0);
    const checksPct = checks ? Math.round((checksOk / checks) * 100) : 0;
    grid.appendChild(this._kpi(`${checksOk}/${checks}`, t('proxyCard.checks'), checksPct, 'var(--accent)'));

    section.appendChild(grid);
    return section;
  },

  _kpi(value, label, pct, color, unit = '') {
    const kpi = ui.el('div', 'proxy-card-kpi');
    const val = ui.el('div', 'proxy-card-kpi-value', { html: `${ui.escHtml(String(value))}${unit ? `<small>${ui.escHtml(unit)}</small>` : ''}` });
    kpi.appendChild(val);
    kpi.appendChild(ui.el('div', 'proxy-card-kpi-label', { text: label }));
    const bar = ui.el('div', 'proxy-card-kpi-bar');
    bar.appendChild(ui.el('div', '', { style: `width:${pct}%;background:${color}` }));
    kpi.appendChild(bar);
    return kpi;
  },

  _security(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.security'), this._svg('shield')));

    const list = ui.el('div', 'proxy-card-checklist');
    list.appendChild(this._check('HTTPS', p.ssl_supported, t('common.yes'), t('common.no')));
    list.appendChild(this._check('CONNECT', p.supports_connect, t('common.yes'), t('common.no')));
    list.appendChild(this._check('MITM', !p.mitm_suspect, t('proxyCard.notDetected'), t('proxyCard.suspected')));
    list.appendChild(this._check(t('proxyCard.manualBlacklist'), !p.in_blacklist, t('common.no'), t('common.yes')));
    list.appendChild(this._check(t('proxyCard.ipBlacklist'), !(p.ip_blacklist_hits > 0), p.ip_blacklist_hits ? `${p.ip_blacklist_hits} ${t('proxyCard.hits')}` : t('common.no')));

    section.appendChild(list);
    return section;
  },

  _check(label, ok, yesText, noText) {
    const cls = ok ? 'good' : 'bad';
    const value = ok ? yesText : noText;
    const icon = ok ? this._svg('check') : this._svg('x');
    const row = ui.el('div', `proxy-card-check ${cls}`);
    const labelEl = ui.el('div', 'proxy-card-check-label', { html: `${icon} <span>${label}</span>` });
    row.appendChild(labelEl);
    row.appendChild(ui.el('div', 'proxy-card-check-value', { text: value }));
    return row;
  },

  _network(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.network'), this._svg('map-pin')));

    const hasListen = !!(p.listen_country || p.listen_city);
    const hasEgress = !!(p.egress_country || p.egress_city);
    const listenCountry = p.listen_country || p.country || '';
    const listenCity = p.listen_city || p.city || '';
    const egressCountry = p.egress_country || p.country || '';
    const egressCity = p.egress_city || p.city || '';
    const listenIp = p.address ? p.address.split(':')[0] : '—';
    const egressIp = p.egress_ip || '—';

    const route = ui.el('div', 'proxy-card-route');
    route.appendChild(this._routePoint(t('proxyCard.listen'), p.listen_country_code || p.country_code, listenCountry, listenCity, listenIp));
    route.appendChild(ui.el('div', 'proxy-card-route-arrow', { text: '→' }));
    route.appendChild(this._routePoint(t('proxyCard.egress'), p.egress_country_code || p.country_code, egressCountry, egressCity, egressIp));
    section.appendChild(route);

    const details = ui.el('div', 'proxy-card-route-details');
    const isp = p.listen_isp || p.egress_isp || p.isp || '';
    if (isp) {
      details.appendChild(this._routeDetail(t('proxyCard.isp'), isp));
    }
    if (p.asn) {
      details.appendChild(this._routeDetail('ASN', p.asn));
    }
    details.appendChild(this._routeDetail(t('proxyCard.sources'), (p.source_ids || []).join(', ') || '—'));
    section.appendChild(details);

    return section;
  },

  _routePoint(label, code, country, city, ip) {
    const point = ui.el('div', 'proxy-card-route-point');
    point.appendChild(ui.el('div', 'proxy-card-route-label', { text: label }));
    const location = ui.el('div', 'proxy-card-route-location');
    if (code) location.appendChild(ui.el('span', 'flag', { text: ui.flag(code) }));
    location.appendChild(ui.el('span', '', { text: [country, city].filter(Boolean).join(', ') || '—' }));
    point.appendChild(location);
    point.appendChild(ui.el('div', 'proxy-card-route-ip', { text: ip }));
    return point;
  },

  _routeDetail(key, value) {
    const row = ui.el('div', 'proxy-card-route-detail');
    row.appendChild(ui.el('div', 'proxy-card-route-detail-key', { text: key }));
    row.appendChild(ui.el('div', 'proxy-card-route-detail-val', { text: value }));
    return row;
  },

  _timeline(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.timeline'), this._svg('clock')));

    const list = ui.el('div', 'proxy-card-timeline');
    list.appendChild(this._timelineItem(t('proxyCard.firstSeen'), p.first_seen, 'accent'));
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
    section.appendChild(this._sectionTitle(t('proxyCard.suitability'), this._svg('thumbs-up')));

    const sr = p.success_rate || 0;
    const lat = p.latency_avg || p.last_latency || 0;
    const speed = p.speed_avg || 0;
    const good = sr >= 0.9 && lat < 2 && !p.in_blacklist && !p.mitm_suspect;
    const ok = sr >= 0.8 && lat < 4 && !p.in_blacklist && !p.mitm_suspect;

    const items = [
      { key: 'web', label: t('proxyCard.use.web'), cls: good ? 'good' : ok ? 'warn' : 'bad' },
      { key: 'api', label: t('proxyCard.use.api'), cls: (good && p.ssl_supported && p.supports_connect) ? 'good' : (ok && p.ssl_supported) ? 'warn' : 'bad' },
      { key: 'parsing', label: t('proxyCard.use.parsing'), cls: (sr >= 0.95 && !p.mitm_suspect && !p.in_blacklist) ? 'good' : (sr >= 0.85 && !p.in_blacklist) ? 'warn' : 'bad' },
      { key: 'download', label: t('proxyCard.use.download'), cls: speed > 100 ? 'good' : speed > 30 ? 'warn' : 'bad' },
      { key: 'streaming', label: t('proxyCard.use.streaming'), cls: (speed > 200 && lat < 1 && !p.mitm_suspect) ? 'good' : (speed > 80 && lat < 2) ? 'warn' : 'bad' },
      { key: 'games', label: t('proxyCard.use.games'), cls: (lat < 0.1 && !p.mitm_suspect) ? 'good' : 'bad' },
    ];

    const tags = ui.el('div', 'proxy-card-tags');
    items.forEach(it => {
      const icon = it.cls === 'good' ? this._svg('check') : it.cls === 'warn' ? this._svg('alert') : this._svg('x');
      tags.appendChild(ui.el('div', `proxy-card-tag ${it.cls}`, { html: `${icon} ${it.label}` }));
    });
    section.appendChild(tags);
    return section;
  },

  _scoreBreakdown(p) {
    const section = ui.el('div', 'proxy-card-section');
    section.appendChild(this._sectionTitle(t('proxyCard.scoreBreakdown'), this._svg('bar-chart')));

    const sr = p.success_rate || 0;
    const base = sr * 40;
    const lat = p.latency_avg || 0;
    const latScore = Math.max(0, 100 - lat * 10) * 0.2;
    const sslBonus = p.ssl_supported ? 10 : 0;
    const connectBonus = p.supports_connect ? 5 : 0;
    const mitmPenalty = p.mitm_suspect ? -30 : 0;
    const speedBonus = p.speed_avg ? Math.min(50, p.speed_avg / 20) : 0;
    const speedFailPenalty = -Math.min(45, (p.speed_fails || 0) * 15);
    let total = base + latScore + sslBonus + connectBonus + mitmPenalty + speedBonus + speedFailPenalty;
    const hits = p.ip_blacklist_hits || 0;
    const ipMultiplier = hits ? Math.max(0.2, Math.pow(0.75, hits)) : 1;
    if (hits) total *= ipMultiplier;
    if (p.in_blacklist) total = 0;
    total = Math.max(0, Math.min(100, total));

    const rows = [
      [t('proxyCard.successRate'), base, 40, 'var(--accent)'],
      [t('proxyCard.latencyScore'), latScore, 20, 'var(--accent)'],
      [t('proxyCard.sslConnectBonus'), sslBonus + connectBonus, 15, 'var(--success)'],
      [t('proxyCard.speedBonus'), speedBonus, 50, 'var(--accent)'],
      [t('proxyCard.penalties'), Math.abs(mitmPenalty) + Math.abs(speedFailPenalty), 75, 'var(--danger)', mitmPenalty < 0 || speedFailPenalty < 0],
    ];
    if (hits) {
      rows.push([t('proxyCard.ipBlacklistMultiplier'), ipMultiplier * 100, 100, 'var(--warning)']);
    }

    const grid = ui.el('div', 'proxy-card-score-grid');
    rows.forEach(([label, value, max, color, negative]) => {
      const pct = Math.max(0, Math.min(100, (value / max) * 100));
      const row = ui.el('div', 'proxy-card-score-row');
      const header = ui.el('div', 'proxy-card-score-header');
      header.appendChild(ui.el('div', 'proxy-card-score-label', { text: label }));
      const sign = negative ? '-' : '+';
      const displayValue = negative ? value.toFixed(1) : value.toFixed(1);
      header.appendChild(ui.el('div', 'proxy-card-score-value', { text: `${sign}${displayValue}`, style: `color:${color}` }));
      row.appendChild(header);
      const bar = ui.el('div', 'proxy-card-score-bar');
      bar.appendChild(ui.el('div', '', { style: `width:${pct}%;background:${color}` }));
      row.appendChild(bar);
      grid.appendChild(row);
    });
    section.appendChild(grid);

    const totalRow = ui.el('div', 'proxy-card-score-total');
    totalRow.appendChild(ui.el('div', 'proxy-card-score-total-label', { text: t('proxyCard.totalScore') }));
    const totalVal = ui.el('div', 'proxy-card-score-total-value', { html: `${Math.round(total)}<small>/100</small>` });
    totalRow.appendChild(totalVal);
    section.appendChild(totalRow);

    section.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-top:10px;line-height:1.4', text: t('proxyCard.ratingHint') }));

    return section;
  },

  _actions(p, overlay) {
    const footer = ui.el('div', 'proxy-card-footer');

    const left = ui.el('div', 'proxy-card-actions');
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

    const recheckBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('proxyCard.recheck') });
    recheckBtn.addEventListener('click', () => {
      recheckBtn.disabled = true;
      recheckBtn.textContent = t('common.loading');
      api.proxyRecheck(p.address).then(() => {
        app.toast(t('page.proxies.recheckComplete'));
        this._refresh(overlay.querySelector('.proxy-card'), p.address, overlay);
      }).catch(e => {
        recheckBtn.disabled = false;
        recheckBtn.textContent = t('proxyCard.recheck');
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    left.appendChild(recheckBtn);

    const copyBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('proxyCard.copy') });
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(p.address).then(() => app.toast(t('proxyCard.copied'))).catch(() => {});
    });
    left.appendChild(copyBtn);

    const right = ui.el('div', 'proxy-card-actions');
    const blBtn = ui.el('button', 'btn btn-sm btn-danger', { text: p.in_blacklist ? t('proxyCard.removeFromBlacklist') : t('proxyCard.addToBlacklist') });
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
      activity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
      shield: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>',
      'map-pin': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
      clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
      'thumbs-up': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>',
      'bar-chart': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/></svg>',
      check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
      x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
      alert: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
    };
    return icons[name] || '';
  }
};

window.proxyCard = proxyCard;
