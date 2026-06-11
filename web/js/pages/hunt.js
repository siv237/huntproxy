router.register('hunt', (container) => {
  const els = {};
  let topSortKey = 'score', topSortDir = -1;
  let blSortKey = 'address', blSortDir = 1;

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    // Row 1: Controls + Progress + Blacklist mini
    const row1 = ui.el('div', 'grid grid-3 row-stretch');
    row1.appendChild(buildControlCard());
    row1.appendChild(buildProgressCard());
    row1.appendChild(buildBlacklistCard());
    container.appendChild(row1);

    // Row 2: Top Proxies + Hunt Log
    const row2 = ui.el('div', 'grid grid-2 row-stretch');
    row2.appendChild(buildTopProxiesCard());
    row2.appendChild(buildLogCard());
    container.appendChild(row2);
  }

  function buildControlCard() {
    const card = ui.el('div', 'card');
    card.id = 'control-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.huntControl'), style: 'margin-bottom:8px' }));

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap' });
    const startBtn = ui.el('button', 'btn btn-primary', { text: t('page.hunt.startHunt') });
    startBtn.id = 'btn-hunt-start';
    startBtn.addEventListener('click', () => api.huntStart().then(r => app.toast(r.ok ? t('page.hunt.huntStarted') : r.error)));
    btnRow.appendChild(startBtn);

    const pauseBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.pause') });
    pauseBtn.id = 'btn-hunt-pause';
    pauseBtn.addEventListener('click', () => api.huntPause().then(r => app.toast(r.ok ? t('page.hunt.pausedMsg') : r.error)));
    btnRow.appendChild(pauseBtn);

    const resumeBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.resume') });
    resumeBtn.id = 'btn-hunt-resume';
    resumeBtn.addEventListener('click', () => api.huntResume().then(r => app.toast(r.ok ? t('page.hunt.resumed') : r.error)));
    btnRow.appendChild(resumeBtn);

    const stopBtn = ui.el('button', 'btn btn-danger', { text: t('page.hunt.stop') });
    stopBtn.id = 'btn-hunt-stop';
    stopBtn.addEventListener('click', () => api.huntStop().then(() => app.toast(t('page.hunt.huntStopped'))));
    btnRow.appendChild(stopBtn);
    card.appendChild(btnRow);

    const sel = ui.el('select', '', { id: 'country-filter', style: 'width:100%;padding:4px 6px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    ['ALL','US','RU','GB','DE','FR','NL','CA','JP','BR','IN','UA','PL'].forEach(c => {
      const opt = ui.el('option', '', { value: c === 'ALL' ? '' : c, text: c });
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => api.setCountry(sel.value).then(() => app.toast('Country: ' + (sel.value || 'ALL'))));
    card.appendChild(sel);
    return card;
  }

  function buildProgressCard() {
    const card = ui.el('div', 'card');
    card.id = 'progress-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.poolProgress'), style: 'margin-bottom:8px' }));

    const top = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:6px' });
    top.appendChild(ui.el('div', '', { id: 'phase-badge', style: 'display:inline-flex;align-items:center;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;text-transform:uppercase;background:var(--surface-raised);color:var(--text-secondary)', text: t('page.hunt.idle') }));
    top.appendChild(ui.el('div', '', { id: 'last-event', style: 'font-size:11px;color:var(--text-secondary);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: t('common.ready') }));
    top.appendChild(ui.el('span', '', { id: 'live-dot', style: 'width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0' }));
    card.appendChild(top);

    card.appendChild(ui.el('div', 'progress-bar', { id: 'progress-bar', style: 'margin-bottom:4px' }, [ui.el('div', '', { id: 'progress-fill', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease' })]));

    card.appendChild(ui.el('div', '', {
      id: 'progress-text',
      style: 'display:flex;justify-content:space-between;font-size:11px;color:var(--text-secondary)',
      html: `<span>${t('page.hunt.checked')} <b id="p-checked">0</b> / <b id="p-total">0</b></span><span>${t('page.hunt.working')} <b id="p-working" style="color:var(--success)">0</b></span>`
    }));

    const lp = ui.el('div', '', { id: 'last-proxy-row', style: 'margin-top:4px;font-size:11px;color:var(--text-secondary);display:flex;align-items:center;gap:4px;visibility:hidden' });
    lp.innerHTML = '<span id="last-flag"></span><span id="last-addr" style="font-family:monospace;color:var(--accent)"></span><span id="last-country-name"></span>';
    card.appendChild(lp);
    return card;
  }

  function buildBlacklistCard() {
    const card = ui.el('div', 'card');
    card.id = 'blacklist-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.blacklist'), style: 'margin-bottom:8px' }));

    const form = ui.el('div', '', { style: 'display:flex;gap:4px;margin-bottom:6px' });
    const addrInp = ui.el('input', '', { id: 'bl-input', type: 'text', placeholder: t('page.blacklist.proxyAddress'), style: 'flex:1;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    const reasonInp = ui.el('input', '', { id: 'bl-reason', type: 'text', placeholder: t('common.reason'), style: 'flex:1;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    const addBtn = ui.el('button', 'btn btn-xs btn-primary', { text: '+' });
    addBtn.addEventListener('click', () => {
      const a = addrInp.value.trim(), r = reasonInp.value.trim();
      if (!a) return;
      api.blAdd(a, r).then(() => { addrInp.value = ''; reasonInp.value = ''; app.toast(t('page.hunt.addedToBlacklist')); poll(); });
    });
    form.appendChild(addrInp);
    form.appendChild(reasonInp);
    form.appendChild(addBtn);
    card.appendChild(form);

    const tbl = ui.el('div', 'table-wrap');
    tbl.id = 'bl-tbl-wrap';
    card.appendChild(tbl);
    return card;
  }

  function buildTopProxiesCard() {
    const card = ui.el('div', 'card');
    card.id = 'top-proxies-card';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.topRatedAlive') }));
    const count = ui.el('div', '', { id: 'top-count', style: 'font-size:11px;color:var(--text-secondary)', text: '0' });
    header.appendChild(count);
    card.appendChild(header);

    const wrap = ui.el('div', 'table-wrap');
    wrap.id = 'top-tbl-wrap';
    card.appendChild(wrap);
    return card;
  }

  function buildLogCard() {
    const card = ui.el('div', 'card');
    card.id = 'log-card';
    card.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.huntLog'), style: 'margin-bottom:8px' }));
    const log = ui.el('div', '', { id: 'hunt-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow-y:auto;flex:1;min-height:0;color:var(--text-primary)' });
    card.appendChild(log);
    return card;
  }

  build();

  // --- Updaters ---
  function updateStats(s) {
    const c = s.counts || {};
    const el = id => document.getElementById(id);
    const paused = s.paused || false;
    const manual = s.manual_pause || false;
    if (el('btn-hunt-start')) el('btn-hunt-start').disabled = s.running && !paused;
    if (el('btn-hunt-pause')) el('btn-hunt-pause').disabled = !s.running || paused;
    if (el('btn-hunt-resume')) el('btn-hunt-resume').disabled = !paused;
    if (el('btn-hunt-stop')) el('btn-hunt-stop').disabled = !s.running && !paused;

    if (el('phase-badge')) {
      const badge = el('phase-badge');
      if (paused) {
        badge.textContent = manual ? t('page.hunt.paused') : t('page.hunt.pausedNoInet');
        badge.style.color = 'var(--warning,#9a6700)';
        badge.style.background = 'rgba(154,103,0,0.12)';
      } else {
        badge.textContent = s.phase || t('page.hunt.idle');
        badge.style.color = s.running ? 'var(--accent)' : 'var(--text-secondary)';
        badge.style.background = s.running ? 'var(--accent-light)' : 'var(--surface-raised)';
      }
    }
    if (el('last-event')) el('last-event').textContent = s.last_event || t('common.ready');
    if (el('live-dot')) el('live-dot').style.background = paused ? 'var(--warning,#9a6700)' : s.running ? 'var(--accent)' : 'var(--text-muted)';
  }

  function updateProgress(s) {
    const p = s.progress || {};
    const total = p.checking_total || p.downloaded || 0;
    const c = p.checked || 0;
    const pct = total > 0 ? Math.round((c / total) * 100) : 0;
    const el = id => document.getElementById(id);
    if (el('progress-fill')) el('progress-fill').style.width = pct + '%';
    if (el('p-checked')) el('p-checked').textContent = c;
    if (el('p-total')) el('p-total').textContent = total;
    if (el('p-working')) el('p-working').textContent = p.working || 0;

    if (el('last-proxy-row')) {
      if (p.last_proxy) {
        el('last-proxy-row').style.visibility = 'visible';
        const det = s.last_proxy_details || {};
        if (el('last-flag')) el('last-flag').textContent = ui.flag(det.country_code || '');
        if (el('last-addr')) el('last-addr').textContent = p.last_proxy;
        if (el('last-country-name')) el('last-country-name').textContent = p.last_country || '';
      } else {
        el('last-proxy-row').style.visibility = 'hidden';
      }
    }
  }

  function setTopSort(key) {
    if (topSortKey === key) topSortDir *= -1;
    else { topSortKey = key; topSortDir = -1; }
    poll();
  }

  function updateTopProxies(proxies) {
    const wrap = document.getElementById('top-tbl-wrap');
    if (!wrap) return;
    const el = id => document.getElementById(id);
    if (el('top-count')) el('top-count').textContent = t('page.hunt.alive', { count: (proxies || []).length });

    const sorted = (proxies || []).slice().sort((a, b) => ui.sortValue(a, b, topSortKey, topSortDir));

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, topSortKey, topSortDir) : ''), width, align, sortKey: key, onSort: key ? () => setTopSort(key) : undefined });
    const headers = [
      h('#', null, '24px', 'center'),
      h('Proxy', 'address', null, 'left'),
      h('Ctry', 'country', '40px', 'center'),
      h('Lat', 'last_latency', '50px', 'right'),
      h('Avg', 'latency_avg', '50px', 'right'),
      h('KB/s', 'speed_avg', '40px', 'right'),
      h('Succ', 'success_rate', '40px', 'right'),
      h('Chk', 'checks_total', '40px', 'right'),
      h('Score', 'score', '40px', 'right'),
      h('Flags', null, '50px', 'center'),
      h('Ok', 'last_ok', '36px', 'right'),
      h('', null, '30px', 'center'),
    ];
    const rows = sorted.slice(0, 10).map((p, i) => {
      const sc = Math.min(100, Math.max(0, p.score || 0));
      const flags = [];
      if (p.supports_connect) flags.push('<span style="color:var(--success);font-weight:600">HTTPS</span>');
      else flags.push('<span style="color:var(--text-muted)">HTTP</span>');
      if (p.mitm_suspect) flags.push('<span style="color:var(--danger);font-weight:600">MITM!</span>');
      const proto = p.protocol || 'http';
      return [
        `<span style="color:var(--text-muted)">${i+1}</span>`,
        `<span class="addr" style="font-size:10px;cursor:pointer" onclick="window._proxySelect='${p.address}';router.navigate('proxy-pool')">${p.address}</span>`,
        ui.flag(p.country_code) || '—',
        p.last_latency ? p.last_latency.toFixed(2) + 's' : '—',
        p.latency_avg ? p.latency_avg.toFixed(2) + 's' : '—',
        (p.speed_avg || 0).toFixed(0),
        (p.success_rate * 100).toFixed(0) + '%',
        `${p.checks_ok}/${p.checks_total}`,
        `<div style="display:inline-block;width:30px;height:4px;background:var(--surface-raised);border-radius:2px;vertical-align:middle;overflow:hidden"><div style="width:${sc}%;height:100%;background:linear-gradient(90deg,var(--accent),var(--info));transition:width 0.4s"></div></div>`,
        `<span style="color:var(--text-muted);font-size:10px">${proto}</span> ${flags.join(' ')}`,
        ui.ago(p.last_ok),
        `<button class="btn btn-xs btn-danger" onclick="blAdd('${p.address}','manual')" style="padding:1px 4px;font-size:9px">bl</button>`,
      ];
    });
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  function setBlSort(key) {
    if (blSortKey === key) blSortDir *= -1;
    else { blSortKey = key; blSortDir = 1; }
    poll();
  }

  function updateBlacklist(bl) {
    const wrap = document.getElementById('bl-tbl-wrap');
    if (!wrap) return;
    const sorted = (bl || []).slice().sort((a, b) => ui.sortValue(a, b, blSortKey, blSortDir));
    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, blSortKey, blSortDir) : ''), width, align, sortKey: key, onSort: key ? () => setBlSort(key) : undefined });
    const headers = [
      h('Proxy', 'address', null, 'left'),
      h('Reason', 'reason', '80px', 'left'),
      h('Ctry', 'country', '40px', 'center'),
      h('', null, '30px', 'center'),
    ];
    const rows = sorted.slice(0, 8).map(b => [
      `<span class="addr" style="font-size:10px">${b.address}</span>`,
      `<span style="color:var(--danger);font-size:10px">${b.reason || '—'}</span>`,
      b.country || '—',
      `<button class="btn btn-xs btn-secondary" onclick="blRemove('${b.address}')" style="padding:1px 4px;font-size:9px">×</button>`,
    ]);
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));
  }

  let huntLogLines = [];
  function updateLog(events) {
    const log = document.getElementById('hunt-log');
    if (!log || !events || !events.length) return;
    events.forEach(e => {
      huntLogLines.unshift(`<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> ${e.msg}`);
      if (huntLogLines.length > 100) huntLogLines.length = 100;
    });
    log.innerHTML = huntLogLines.join('<br>');
  }

  // --- Polling ---
  let lastEventSeq = 0;
  async function poll() {
    try {
      let s = {}, ev = [];
      try { s = await api.snapshot(); } catch (e) { console.error('snapshot', e); }
      try { ev = await api.events(lastEventSeq); } catch (e) { console.error('events', e); }

      updateStats(s);
      updateProgress(s);
      updateTopProxies(s.top_proxies);
      updateBlacklist(s.blacklist);
      if (ev && ev.length) {
        lastEventSeq = Math.max(...ev.map(e => e.seq), lastEventSeq);
        updateLog(ev);
      }
    } catch (e) {
      console.error('hunt poll', e);
    }
  }

  poll();
  const id = setInterval(poll, 1000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
