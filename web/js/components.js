const ui = {
  el(tag, classes = '', attrs = {}, children = []) {
    const e = document.createElement(tag);
    if (classes) e.className = classes;
    Object.entries(attrs).forEach(([k, v]) => {
      if (k === 'text') e.textContent = v;
      else if (k === 'html') e.innerHTML = v;
      else e.setAttribute(k, v);
    });
    children.forEach(c => {
      if (typeof c === 'string') e.appendChild(document.createTextNode(c));
      else if (c) e.appendChild(c);
    });
    return e;
  },

  sortArrow(key, currentKey, currentDir) {
    if (key !== currentKey) return '<span style="color:var(--text-muted);font-size:10px;margin-left:2px">⇅</span>';
    return currentDir < 0 ? '<span style="color:var(--accent);font-size:10px;margin-left:2px">▼</span>' : '<span style="color:var(--accent);font-size:10px;margin-left:2px">▲</span>';
  },

  sortValue(a, b, key, dir) {
    const va = a[key], vb = b[key];
    if (va === undefined || va === null) return dir;
    if (vb === undefined || vb === null) return -dir;
    if (typeof va === 'string') return dir * va.localeCompare(vb);
    if (typeof va === 'boolean') return dir * (va === vb ? 0 : (va ? -1 : 1));
    return dir * (va - vb);
  },

  card(title = '', actions = '') {
    const header = ui.el('div', 'card-header');
    if (title) header.appendChild(ui.el('div', 'card-title', { text: title }));
    if (actions) {
      const a = typeof actions === 'string' ? ui.el('button', 'card-action', { html: actions }) : actions;
      header.appendChild(a);
    }
    const card = ui.el('div', 'card');
    if (title || actions) card.appendChild(header);
    return card;
  },

  badge(text, variant = 'gray') {
    return ui.el('span', `badge badge-${variant}`, { text });
  },

  progress(value, max = 100, variant = '') {
    const pct = Math.min(100, Math.max(0, (value / max) * 100));
    const bar = ui.el('div', 'progress-bar');
    const fill = ui.el('div', `fill ${variant}`, { style: `width:${pct}%` });
    bar.appendChild(fill);
    return bar;
  },

  circleProgress(value, label = '') {
    const r = 50;
    const c = 2 * Math.PI * r;
    const offset = c - (Math.min(100, Math.max(0, value)) / 100) * c;
    const wrap = ui.el('div', 'circle-progress');
    wrap.innerHTML = `
      <svg viewBox="0 0 120 120" width="120" height="120">
        <circle class="track" cx="60" cy="60" r="${r}"/>
        <circle class="fill" cx="60" cy="60" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${offset}"/>
      </svg>
      <div class="text"><div class="value">${Math.round(value)}%</div>${label ? `<div class="label">${label}</div>` : ''}</div>
    `;
    return wrap;
  },

  statCard(label, value, delta = null, sparkData = null) {
    const card = ui.card();
    card.classList.add('stat-card');
    card.appendChild(ui.el('div', 'stat-label', { text: label }));
    card.appendChild(ui.el('div', 'stat-value', { text: value }));
    if (delta !== null && delta !== undefined) {
      const isUp = delta > 0;
      const d = ui.el('div', `stat-delta ${isUp ? 'up' : 'down'}`, {
        html: `${isUp ? '↑' : '↓'} ${Math.abs(delta)} ${t('common.vsYesterday')}`
      });
      card.appendChild(d);
    }
    if (sparkData && sparkData.length) {
      const box = ui.el('div', 'stat-sparkline');
      box.innerHTML = charts.sparkline(sparkData, undefined, undefined, 40);
      card.appendChild(box);
    }
    return card;
  },

  table(headers, rows) {
    const wrap = ui.el('div', 'table-wrap');
    const table = ui.el('table', 'table');
    const thead = ui.el('thead');
    const trh = ui.el('tr');
    headers.forEach(h => {
      const label = typeof h === 'string' ? h : h.label;
      const th = ui.el('th', '', { html: label });
      if (typeof h === 'object' && h.width) {
        th.style.minWidth = h.width;
        th.style.width = 'auto';
      }
      if (typeof h === 'object' && h.align) th.style.textAlign = h.align;
      if (typeof h === 'object' && h.sortKey) {
        th.style.cursor = 'pointer';
        th.style.userSelect = 'none';
        th.addEventListener('click', h.onSort || (() => {}));
      }
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    table.appendChild(thead);
    const tbody = ui.el('tbody');
    if (rows.length === 0) {
      const tr = ui.el('tr');
      const td = ui.el('td', 'muted', { colSpan: headers.length, text: t('common.noData') });
      td.style.textAlign = 'center';
      tr.appendChild(td);
      tbody.appendChild(tr);
    } else {
      rows.forEach(row => {
        const tr = ui.el('tr');
        row.forEach((cell, i) => {
          const td = ui.el('td', '', { html: cell });
          const align = typeof headers[i] === 'object' ? headers[i].align : '';
          if (align) td.style.textAlign = align;
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
    }
    table.appendChild(tbody);
    wrap.appendChild(table);
    return wrap;
  },

  qaGrid(actions) {
    const grid = ui.el('div', 'qa-grid');
    actions.forEach(a => {
      const item = ui.el('button', 'qa-item');
      const icon = ui.el('div', 'qa-icon', { html: a.icon || '' });
      const text = ui.el('div', 'qa-text');
      text.appendChild(ui.el('div', 'qa-title', { text: a.title }));
      text.appendChild(ui.el('div', 'qa-desc', { text: a.desc || '' }));
      item.appendChild(icon);
      item.appendChild(text);
      if (a.onClick) item.addEventListener('click', a.onClick);
      grid.appendChild(item);
    });
    return grid;
  },

  activityItem(iconHtml, textHtml, timeStr, variant = 'gray') {
    const item = ui.el('div', 'activity-item');
    const icon = ui.el('div', `activity-icon ${variant}`, { html: iconHtml });
    const body = ui.el('div', 'activity-body');
    body.appendChild(ui.el('div', 'activity-text', { html: textHtml }));
    body.appendChild(ui.el('div', 'activity-time', { text: timeStr }));
    item.appendChild(icon);
    item.appendChild(body);
    return item;
  },

  tabs(names, onChange, activeIndex = 0) {
    const wrap = ui.el('div', 'card-tabs');
    names.forEach((name, i) => {
      const btn = ui.el('button', `card-tab ${i === activeIndex ? 'active' : ''}`, { text: name });
      btn.addEventListener('click', () => {
        wrap.querySelectorAll('.card-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        if (onChange) onChange(name, i);
      });
      wrap.appendChild(btn);
    });
    return wrap;
  },

  emptyState(text) {
    return ui.el('div', 'empty', { text: text || t('common.noData') });
  },

  flag(code) {
    if (!code || code.length !== 2) return '';
    const b = 0x1F1E6 - 65;
    return String.fromCodePoint(b + code.charCodeAt(0), b + code.charCodeAt(1));
  },

  ago(ts) {
    if (!ts) return '—';
    const d = Math.floor(Date.now() / 1000 - ts);
    if (d < 0) return t('ago.now');
    if (d < 60) return t('ago.seconds', { count: d });
    if (d < 3600) return t('ago.minutes', { count: Math.floor(d / 60) });
    if (d < 86400) return t('ago.hours', { count: Math.floor(d / 3600) });
    return t('ago.days', { count: Math.floor(d / 86400) });
  },

  fmtTime(ts) {
    return new Date(ts * 1000).toLocaleTimeString();
  },

  fmtDate(ts) {
    return new Date(ts * 1000).toLocaleDateString();
  },

  fmtDateTime(ts) {
    if (!ts) return '—';
    const d = new Date(ts * 1000);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString();
  },

  fmtNum(n) {
    if (n === undefined || n === null) return '—';
    return n.toLocaleString();
  },

  fmtPct(n) {
    if (n === undefined || n === null) return '—';
    return (n * 100).toFixed(1) + '%';
  },

  fmtLatency(s) {
    if (s === undefined || s === null) return '—';
    if (s < 1) return (s * 1000).toFixed(0) + 'ms';
    return s.toFixed(2) + 's';
  },

  fmtBytes(bytes) {
    if (!bytes) return '0 B';
    const units = [t('units.b'),t('units.kb'),t('units.mb'),t('units.gb'),t('units.tb')];
    let i = 0;
    let b = bytes;
    while (b >= 1024 && i < units.length - 1) { b /= 1024; i++; }
    return b.toFixed(2) + ' ' + units[i];
  },

  escHtml(str) {
    if (str == null) return '';
    return String(str).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
  },

  formatRouteLabel(route) {
    if (!route) return '<span style="color:var(--text-muted)">—</span>';
    if (route === 'direct') return '<span style="color:var(--success);font-weight:600">' + t('route.direct') + '</span>';
    if (route === 'pool') return '<span style="color:var(--accent);font-weight:600">' + t('route.pool') + '</span>';
    if (route === 'pool_selected') return '<span style="color:var(--accent);font-weight:600">' + t('route.poolSelected') + '</span>';
    if (route.startsWith('custom:')) {
      const name = route.slice(7);
      return '<span style="color:var(--info);font-weight:600">' + t('route.custom', { name: ui.escHtml(name) }) + '</span>';
    }
    if (route.startsWith('proxy:')) return '<span style="color:var(--info);font-weight:600">' + ui.escHtml(route) + '</span>';
    return '<span style="color:var(--text-muted)">' + ui.escHtml(route) + '</span>';
  },

  hostOf(target) {
    if (!target) return '';
    try {
      return target.startsWith('http') ? new URL(target).hostname : target.split(':')[0].split('/')[0];
    } catch (e) {
      return target;
    }
  },

  hostColor(str) {
    let h = 0;
    const s = String(str || '');
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return `hsl(${h % 360}, 62%, 52%)`;
  },

  hostAvatar(host, size = 28) {
    const ch = (host || '?').replace(/^www\./, '').charAt(0).toUpperCase();
    const color = ui.hostColor(host);
    return `<span class="obj-ava" style="width:${size}px;height:${size}px;background:color-mix(in srgb, ${color} 15%, transparent);color:${color};font-size:${Math.round(size * 0.45)}px">${ui.escHtml(ch)}</span>`;
  },

  personAvatar(str, size = 26) {
    const color = ui.hostColor(str);
    const svg = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width:60%;height:60%"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>';
    return `<span class="obj-ava" style="width:${size}px;height:${size}px;background:color-mix(in srgb, ${color} 15%, transparent);color:${color}">${svg}</span>`;
  },

  routeTypeOf(upstream) {
    if (!upstream || upstream === '?' || upstream === 'unknown') return 'other';
    if (upstream === 'direct' || upstream.startsWith('direct')) return 'direct';
    if (upstream.startsWith('proxy:')) return 'proxy';
    if (upstream.startsWith('pool:')) return 'pool';
    if (upstream.startsWith('custom:')) return 'custom';
    return 'other';
  },

  routeTypeClass(type) {
    return { direct: 'route-direct', proxy: 'route-proxy', pool: 'route-pool', custom: 'route-custom', other: 'route-unknown' }[type] || 'route-unknown';
  },

  routeBadge(upstream, geo) {
    if (!upstream || upstream === '?' || upstream === 'unknown') {
      return `<span class="route-badge route-unknown" title="${ui.escHtml(t('page.proxyControl.routeUnknown'))}">${ui.escHtml(t('page.proxyControl.routeUnknown'))}</span>`;
    }
    const parts = upstream.split(' → ');
    return parts.map(p => {
      if (p === 'direct') return '<span class="route-badge route-direct">DIRECT</span>';
      const m = p.match(/^(proxy|pool|custom):([^\s(]+)/);
      if (m) {
        const type = m[1];
        const addr = m[2];
        const label = type.toUpperCase();
        const isFallback = p.includes('(fallback');
        const g = geo ? geo[addr] : null;
        const fbTag = isFallback ? ` <span class="route-fallback" title="${ui.escHtml(t('page.proxyControl.fallbackNote'))}">↯</span>` : '';
        if (g) {
          const cc = g.egress_country_code || g.country_code || '';
          const country = g.egress_country || g.country || '';
          const isp = g.egress_isp || '';
          const flag = ui.flag(cc);
          const short = [cc, isp ? isp.slice(0, 16) : ''].filter(Boolean).join(' · ');
          const title = [addr, country, isp, isFallback ? t('page.proxyControl.fallbackNote') : ''].filter(Boolean).join(' · ');
          return `<span class="route-badge route-${type} route-clickable${isFallback ? ' route-fell-back' : ''}" data-addr="${ui.escHtml(addr)}" title="${ui.escHtml(title)}">${label}` +
            (flag ? ` <span class="route-flag">${flag}</span>` : '') +
            (short ? ` <span class="route-geo">${ui.escHtml(short)}</span>` : ` <span class="route-addr">${ui.escHtml(addr)}</span>`) +
            fbTag +
            `</span>`;
        }
        if (type === 'custom') {
          const name = p.slice(7);
          return `<span class="route-badge route-custom" title="${ui.escHtml(name)}">CUSTOM <span class="route-addr">${ui.escHtml(name)}</span></span>`;
        }
        return `<span class="route-badge route-${type} route-clickable${isFallback ? ' route-fell-back' : ''}" data-addr="${ui.escHtml(addr)}" title="${ui.escHtml(addr + (isFallback ? ' · ' + t('page.proxyControl.fallbackNote') : ''))}">${label} <span class="route-addr">${ui.escHtml(addr)}</span>${fbTag}</span>`;
      }
      if (p.startsWith('custom:')) {
        const name = p.slice(7);
        return `<span class="route-badge route-custom" title="${ui.escHtml(name)}">CUSTOM <span class="route-addr">${ui.escHtml(name)}</span></span>`;
      }
      return `<span class="route-badge route-unknown">${ui.escHtml(p)}</span>`;
    }).join('<span class="route-arrow">→</span>');
  },

  statusPill(status) {
    const st = (status || '').toString();
    const isOk = st === 'ok' || st === '200';
    const is502 = st.startsWith('502');
    const code = isOk ? '200' : is502 ? '502' : (st || 'ERR').slice(0, 8);
    const cls = isOk ? 'ok' : is502 ? 'warn' : 'err';
    const title = isOk ? t('page.proxyControl.statusOk') : is502 ? t('page.proxyControl.statusBadGateway') : t('page.proxyControl.statusFailed');
    return `<span class="st-pill ${cls}" title="${ui.escHtml(title)}"><span class="st-pill-dot"></span>${ui.escHtml(code)}</span>`;
  },

  viaBadge(via) {
    const v = (via || '').toString().toLowerCase();
    if (!v) return '<span class="via-badge via-unknown" title="?">—</span>';
    if (v === 'http') return `<span class="via-badge via-http" title="${ui.escHtml(t('page.proxyControl.viaHttp'))}">HTTP</span>`;
    if (v === 'socks5' || v === 'socks4') return `<span class="via-badge via-socks" title="${ui.escHtml(t('page.proxyControl.viaSocks'))}">SOCKS</span>`;
    if (v === 'transparent' || v === 'tp') return `<span class="via-badge via-trans" title="${ui.escHtml(t('page.proxyControl.viaTrans'))}">TP</span>`;
    return `<span class="via-badge via-unknown" title="${ui.escHtml(v)}">${ui.escHtml(v.slice(0, 6).toUpperCase())}</span>`;
  },
};

// Click on a proxy/pool route badge opens the standard proxy card.
// Capture phase + stopPropagation so container handlers (e.g. the expandable
// history rows in the client card) don't also fire.
document.addEventListener('click', (e) => {
  const badge = e.target && e.target.closest ? e.target.closest('.route-badge[data-addr]') : null;
  if (!badge) return;
  e.stopPropagation();
  if (window.proxyCard) window.proxyCard.show(badge.dataset.addr);
}, true);
