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
    groupByProtocol: true,
  };

  function setProxySort(key) {
    if (state.proxySortKey === key) state.proxySortDir *= -1;
    else { state.proxySortKey = key; state.proxySortDir = -1; }
    load();
  }

  function fmtDuration(sec) {
    if (!sec || sec <= 0) return '—';
    const s = Math.round(sec % 60);
    const m = Math.floor((sec % 3600) / 60);
    const hh = Math.floor(sec / 3600);
    const dd = Math.floor(sec / 86400);
    const mo = Math.floor(dd / 30);
    const y = Math.floor(dd / 365);
    if (sec >= 94608000) return y + 'г';
    if (sec >= 7776000) return mo + 'мес';
    if (sec >= 259200) return dd + 'д';
    if (sec >= 10800) return hh + 'ч';
    if (sec >= 180) return (hh ? hh + 'ч ' : '') + m + 'м';
    if (m) return m + 'м ' + s + 'с';
    return s + 'с';
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
    if (d >= 94608000) return y + 'г назад';
    if (d >= 7776000) return mo + 'мес назад';
    if (d >= 259200) return days + 'д назад';
    if (d >= 10800) return hh + 'ч назад';
    if (d >= 180) return (hh ? hh + 'ч ' : '') + m + 'м назад';
    if (m) return m + 'м ' + s + 'с назад';
    return s + 'с назад';
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
      .filter(p => (!state.hideNoHttps || p.supports_connect) && (!state.hideNoSsl || p.ssl_supported) && (!state.hideMitm || !p.mitm_suspect) && (!state.hideBlacklisted || !(p.in_blacklist || (p.ip_blacklist_hits || 0) > 0)))
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
      count.textContent = sorted.length + (tags.length ? ' ' + tags.join('+') : ' alive');
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.proxySortKey, state.proxySortDir) : ''), width, align, sortKey: key, onSort: key ? () => setProxySort(key) : undefined });

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
      let ps = {}, proxies = [];
      try { ps = await api.proxyStatus(); } catch (e) { console.error('proxyStatus', e); }
      try { proxies = await api.proxyAlive(); } catch (e) { console.error('proxyAlive', e); }
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
