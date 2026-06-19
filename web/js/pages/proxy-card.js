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
    } catch (e) {
      modal.innerHTML = `<div style="padding:40px;color:var(--danger)">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    }
  },

  _render(modal, p, checksData, overlay) {
    modal.innerHTML = '';

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
    section.appendChild(details);

    return section;
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

    const components = [
      { label: t('proxyCard.successRate'), value: base, max: 40, color: 'var(--success)' },
      { label: t('proxyCard.latencyScore'), value: latScore, max: 25, color: 'var(--success)' },
      { label: 'SSL', value: sslBonus, max: 10, color: 'var(--success)' },
      { label: 'CONNECT', value: connectBonus, max: 5, color: 'var(--success)' },
      { label: t('proxyCard.speedBonus'), value: speedBonus, max: 10, color: 'var(--success)' },
      { label: t('proxyCard.mitmPenalty'), value: Math.abs(mitmPenalty), max: 10, color: 'var(--danger)', negative: true },
      { label: t('proxyCard.speedFailPenalty'), value: Math.abs(speedFailPenalty), max: 10, color: 'var(--danger)', negative: true },
    ];

    const grid = ui.el('div', 'proxy-card-score-hgrid');
    components.forEach(c => {
      const pct = Math.max(0, Math.min(100, (c.value / c.max) * 100));
      const item = ui.el('div', 'proxy-card-score-hitem');
      const header = ui.el('div', 'proxy-card-score-hheader');
      header.appendChild(ui.el('div', 'proxy-card-score-hlabel', { text: c.label }));
      let sign = '';
      if (c.negative) sign = '-';
      else if (c.value > 0) sign = '+';
      header.appendChild(ui.el('div', 'proxy-card-score-hvalue', { text: `${sign}${c.value.toFixed(1)}`, style: `color:${c.color}` }));
      item.appendChild(header);
      const bar = ui.el('div', 'proxy-card-score-hbar');
      bar.appendChild(ui.el('div', '', { style: `width:${pct}%;background:${c.color}` }));
      item.appendChild(bar);
      item.appendChild(ui.el('div', 'proxy-card-score-hmax', { text: `${c.value.toFixed(1)} / ${c.max}` }));
      grid.appendChild(item);
    });
    section.appendChild(grid);

    const totalRow = ui.el('div', 'proxy-card-score-total');
    totalRow.appendChild(ui.el('div', 'proxy-card-score-total-label', { text: t('proxyCard.totalScore') }));
    const totalVal = ui.el('div', 'proxy-card-score-total-value', { html: `${Math.round(total)}<small>/100</small>`, style: `color:${total >= 60 ? 'var(--success)' : total >= 30 ? 'var(--warning)' : 'var(--danger)'}` });
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
