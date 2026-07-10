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

    // Top: Pipeline stepper strip (full width, thin)
    container.appendChild(buildPipelineStrip());

    // Main: Left conveyor + Right panels
    const main = ui.el('div', '', { style: 'display:flex;gap:10px;flex:1;min-height:0' });

    const leftCol = ui.el('div', '', { style: 'flex:0 0 45%;display:flex;flex-direction:column;min-height:0' });
    leftCol.appendChild(buildConveyorCard());
    main.appendChild(leftCol);

    const rightCol = ui.el('div', '', { style: 'flex:1;display:flex;flex-direction:column;gap:10px;min-height:0;min-width:0' });
    const row1 = ui.el('div', 'grid grid-2 row-stretch');
    row1.appendChild(buildProgressCard());
    row1.appendChild(buildResultsCard());
    rightCol.appendChild(row1);

    const row2 = ui.el('div', 'grid grid-2 row-stretch');
    row2.appendChild(buildTopProxiesCard());
    row2.appendChild(buildLogCard());
    rightCol.appendChild(row2);

    main.appendChild(rightCol);
    container.appendChild(main);
  }

  const PIPELINE_PHASES = ['download', 'blacklist', 'validate', 'health'];
  const PIPELINE_PHASE_I18N = { download: 'page.hunt.phase_download', blacklist: 'page.hunt.phase_blacklist', validate: 'page.hunt.phase_validate', health: 'page.hunt.phase_health' };
  const PIPELINE_PHASE_ICON = { download: '⬇', blacklist: '🛡', validate: '🔍', health: '❤' };

  function buildPipelineStrip() {
    const card = ui.el('div', 'card pipeline-strip');
    card.id = 'pipeline-strip';
    card.style.padding = '6px 10px';
    card.style.flex = '0 0 auto';

    const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:0' });
    PIPELINE_PHASES.forEach((ph, i) => {
      const step = ui.el('div', 'pipe-step');
      step.id = 'pipe-step-' + ph;
      const dot = ui.el('div', 'pipe-step-dot', { text: PIPELINE_PHASE_ICON[ph] });
      step.appendChild(dot);
      const body = ui.el('div', 'pipe-step-body');
      body.appendChild(ui.el('div', 'pipe-step-title', { id: 'pipe-title-' + ph, text: t(PIPELINE_PHASE_I18N[ph]) }));
      body.appendChild(ui.el('div', 'pipe-step-detail', { id: 'pipe-detail-' + ph, text: '—' }));
      step.appendChild(body);
      row.appendChild(step);
      if (i < PIPELINE_PHASES.length - 1) {
        row.appendChild(ui.el('div', 'pipe-step-arrow'));
      }
    });
    card.appendChild(row);
    return card;
  }

  const CONVEYOR_PHASES = ['queued', 'connect', 'speed_wait', 'speed'];
  const CONVEYOR_PHASE_I18N = { queued: 'page.hunt.conv_queued', connect: 'page.hunt.conv_connect', speed_wait: 'page.hunt.conv_speed_wait', speed: 'page.hunt.conv_speed' };
  const CONVEYOR_PHASE_ICON = { queued: '⏳', connect: '🔗', speed_wait: '⏱', speed: '⚡' };

  function buildConveyorCard() {
    const card = ui.el('div', 'card conveyor-board');
    card.id = 'conveyor-card';
    card.style.padding = '8px 10px';
    card.style.flex = '1';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.minHeight = '0';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.conveyor') }));
    const liveTag = ui.el('span', 'pipeline-live', { id: 'pipeline-live', text: '—' });
    header.appendChild(liveTag);
    card.appendChild(header);

    const lanes = ui.el('div', 'conveyor-vlanes');
    lanes.id = 'conveyor-lanes';

    CONVEYOR_PHASES.forEach(ph => {
      const lane = ui.el('div', 'conveyor-vlane');
      lane.id = 'conveyor-vlane-' + ph;
      const label = ui.el('div', 'conveyor-vlane-header', {}, [
        ui.el('span', 'conveyor-vlane-icon', { text: CONVEYOR_PHASE_ICON[ph] }),
        ui.el('span', '', { text: t(CONVEYOR_PHASE_I18N[ph]) }),
        ui.el('span', 'conveyor-vlane-count', { id: 'conveyor-vcount-' + ph, text: '0' }),
      ]);
      lane.appendChild(label);
      const items = ui.el('div', 'conveyor-vlane-items', { id: 'conveyor-vitems-' + ph });
      lane.appendChild(items);
      lanes.appendChild(lane);
    });

    card.appendChild(lanes);
    return card;
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
    card.style.display = 'flex';
    card.style.flexDirection = 'column';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.poolProgress') }));
    const btnRow = ui.el('div', '', { style: 'display:flex;gap:4px;flex-wrap:wrap' });
    const startBtn = ui.el('button', 'btn btn-primary', { text: t('page.hunt.startHunt') });
    startBtn.id = 'btn-hunt-start';
    startBtn.style.fontSize = '10px';
    startBtn.style.padding = '2px 8px';
    startBtn.addEventListener('click', () => api.huntStart().then(r => app.toast(r.ok ? t('page.hunt.huntStarted') : r.error)));
    btnRow.appendChild(startBtn);

    const pauseBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.pause') });
    pauseBtn.id = 'btn-hunt-pause';
    pauseBtn.style.fontSize = '10px';
    pauseBtn.style.padding = '2px 8px';
    pauseBtn.addEventListener('click', () => api.huntPause().then(r => app.toast(r.ok ? t('page.hunt.pausedMsg') : r.error)));
    btnRow.appendChild(pauseBtn);

    const resumeBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.resume') });
    resumeBtn.id = 'btn-hunt-resume';
    resumeBtn.style.fontSize = '10px';
    resumeBtn.style.padding = '2px 8px';
    resumeBtn.addEventListener('click', () => api.huntResume().then(r => app.toast(r.ok ? t('page.hunt.resumed') : r.error)));
    btnRow.appendChild(resumeBtn);

    const stopBtn = ui.el('button', 'btn btn-danger', { text: t('page.hunt.stop') });
    stopBtn.id = 'btn-hunt-stop';
    stopBtn.style.fontSize = '10px';
    stopBtn.style.padding = '2px 8px';
    stopBtn.addEventListener('click', () => api.huntStop().then(() => app.toast(t('page.hunt.huntStopped'))));
    btnRow.appendChild(stopBtn);

    const skipBtn = ui.el('button', 'btn btn-secondary', { text: t('page.hunt.skip') });
    skipBtn.id = 'btn-hunt-skip';
    skipBtn.style.fontSize = '10px';
    skipBtn.style.padding = '2px 8px';
    skipBtn.style.display = 'none';
    skipBtn.addEventListener('click', () => api.huntSkip().then(r => app.toast(r.ok ? t('page.hunt.skipped') : r.error)).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
    btnRow.appendChild(skipBtn);

    header.appendChild(btnRow);
    card.appendChild(header);

    const top = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:6px' });
    top.appendChild(ui.el('div', '', { id: 'phase-badge', style: 'display:inline-flex;align-items:center;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;text-transform:uppercase;background:var(--surface-raised);color:var(--text-secondary)', text: t('page.hunt.idle') }));
    top.appendChild(ui.el('div', '', { id: 'last-event', style: 'font-size:11px;color:var(--text-secondary);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap', text: t('common.ready') }));
    top.appendChild(ui.el('span', '', { id: 'live-dot', style: 'width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0' }));
    card.appendChild(top);

    card.appendChild(ui.el('div', 'progress-bar', { id: 'progress-bar', style: 'margin-bottom:4px' }, [ui.el('div', '', { id: 'progress-fill', style: 'width:0%;height:100%;background:var(--accent);transition:width 0.4s ease' })]));

    card.appendChild(ui.el('div', '', {
      id: 'progress-text',
      style: 'display:flex;justify-content:space-between;font-size:11px;color:var(--text-secondary)',
      html: `<span>${t('page.hunt.checked')} <b id="p-checked">0</b> / <b id="p-total">0</b></span><span>${t('page.hunt.newWorking')} <b id="p-new-working" style="color:var(--info)">0</b></span><span>${t('page.hunt.confirmedWorking')} <b id="p-confirmed-working" style="color:var(--success)">0</b></span>`
    }));

    const lp = ui.el('div', '', { id: 'last-proxy-row', style: 'margin-top:4px;font-size:11px;color:var(--text-secondary);display:flex;align-items:center;gap:4px;visibility:hidden' });
    lp.innerHTML = '<span id="last-flag"></span><span id="last-addr" style="font-family:monospace;color:var(--accent)"></span><span id="last-country-name"></span>';
    card.appendChild(lp);

    const sel = ui.el('select', '', { id: 'country-filter', style: 'width:100%;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);margin-top:6px' });
    ['ALL','US','RU','GB','DE','FR','NL','CA','JP','BR','IN','UA','PL'].forEach(c => {
      const opt = ui.el('option', '', { value: c === 'ALL' ? '' : c, text: c });
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => api.setCountry(sel.value).then(() => app.toast('Country: ' + (sel.value || 'ALL'))));
    card.appendChild(sel);

    return card;
  }

  function buildResultsCard() {
    const card = ui.el('div', 'card conveyor-board');
    card.id = 'results-card';
    card.style.padding = '8px 10px';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.hunt.results') }));
    const resultsCount = ui.el('span', 'pipeline-live', { id: 'results-count', text: '0' });
    header.appendChild(resultsCount);
    card.appendChild(header);

    const lanes = ui.el('div', 'conveyor-vlanes');

    // Alive lane
    const aliveLane = ui.el('div', 'conveyor-vlane conveyor-vlane-alive');
    const aliveHeader = ui.el('div', 'conveyor-vlane-header', {}, [
      ui.el('span', 'conveyor-vlane-icon', { text: '✓' }),
      ui.el('span', '', { text: t('page.hunt.conv_alive') }),
      ui.el('span', 'conveyor-vlane-count', { id: 'results-alive-count', text: '0' }),
    ]);
    aliveLane.appendChild(aliveHeader);
    const aliveItems = ui.el('div', 'conveyor-vlane-items', { id: 'results-alive-items' });
    aliveLane.appendChild(aliveItems);
    lanes.appendChild(aliveLane);

    // Dead lane
    const deadLane = ui.el('div', 'conveyor-vlane conveyor-vlane-dead');
    const deadHeader = ui.el('div', 'conveyor-vlane-header', {}, [
      ui.el('span', 'conveyor-vlane-icon', { text: '✗' }),
      ui.el('span', '', { text: t('page.hunt.conv_dead') }),
      ui.el('span', 'conveyor-vlane-count', { id: 'results-dead-count', text: '0' }),
    ]);
    deadLane.appendChild(deadHeader);
    const deadItems = ui.el('div', 'conveyor-vlane-items', { id: 'results-dead-items' });
    deadLane.appendChild(deadItems);
    lanes.appendChild(deadLane);

    card.appendChild(lanes);
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

  const PHASE_MAP = { 'downloading': 'download', 'blacklists': 'blacklist', 'validating': 'validate', 'health': 'health', 'done': null, 'idle': null, 'paused': null };

  function updatePipelineStrip(s) {
    const p = s.progress || {};
    const phase = s.phase;
    const phaseKey = PHASE_MAP[phase] ?? null;
    const parallel = (s.settings && s.settings.parallel) || 30;

    const setStep = (id, cls) => { const el = document.getElementById('pipe-step-' + id); if (el) el.className = 'pipe-step' + (cls ? ' ' + cls : ''); };
    const setDetail = (id, txt) => { const el = document.getElementById('pipe-detail-' + id); if (el) el.textContent = txt; };

    PIPELINE_PHASES.forEach(ph => { setStep(ph, 'waiting'); setDetail(ph, '—'); });

    // Download
    {
      const srcs = p.source_results || [];
      const okN = srcs.filter(r => r.status === 'ok').length;
      const errN = srcs.filter(r => r.status === 'error').length;
      const total = srcs.length || p.sources_total || 0;
      const done = p.sources_done || okN + errN;
      setDetail('download', total > 0 ? `${done}/${total} · ${okN}ok ${errN}err` : '—');
    }
    // Blacklist
    {
      const bls = p.bl_source_results || [];
      const okN = bls.filter(r => r.status === 'ok').length;
      const errN = bls.filter(r => r.status === 'error').length;
      const total = bls.length || p.bl_sources_total || 0;
      const done = p.bl_sources_done || okN + errN;
      setDetail('blacklist', total > 0 ? `${done}/${total} · ${okN}ok ${errN}err` : '—');
    }
    // Validate
    {
      const total = p.checking_total || p.downloaded || 0;
      const checked = p.checked || 0;
      const pct = total > 0 ? Math.round(checked / total * 100) : 0;
      setDetail('validate', total > 0 ? `${checked}/${total} ${pct}% · ⚡${parallel} ✓${p.working || 0} ✗${p.failed || 0}` : '—');
    }
    // Health
    {
      const alive = (s.counts && s.counts.alive) || 0;
      setDetail('health', alive > 0 ? `${alive} alive · ${Math.round((s.settings || {}).health_interval || 300)}s` : '—');
    }

    // Mark done/active
    const currentIdx = phaseKey ? PIPELINE_PHASES.indexOf(phaseKey) : -1;
    PIPELINE_PHASES.forEach((ph, i) => {
      if (currentIdx < 0) return;
      if (i < currentIdx) setStep(ph, 'done');
      else if (i === currentIdx) setStep(ph, s.paused ? 'paused' : 'active');
    });
    if (phase === 'done') PIPELINE_PHASES.forEach(ph => setStep(ph, 'done'));
  }

  function updateConveyor(s) {
    const p = s.progress || {};
    const active = p.active_checks || [];
    const now = Date.now() / 1000;
    const protoColors = { socks5: 'var(--accent)', socks4: 'var(--info)', http: 'var(--text-secondary)', https: 'var(--success)' };

    const byPhase = {};
    CONVEYOR_PHASES.forEach(ph => byPhase[ph] = []);

    active.forEach(c => {
      const ph = CONVEYOR_PHASES.includes(c.step) ? c.step : 'queued';
      byPhase[ph].push(c);
    });

    CONVEYOR_PHASES.forEach(ph => {
      const items = document.getElementById('conveyor-vitems-' + ph);
      const count = document.getElementById('conveyor-vcount-' + ph);
      const lane = document.getElementById('conveyor-vlane-' + ph);
      if (!items) return;

      if (count) count.textContent = String(byPhase[ph].length);
      if (lane) lane.classList.toggle('conveyor-vlane-active', byPhase[ph].length > 0);

      items.innerHTML = '';
      byPhase[ph].sort((a, b) => (a.started || 0) - (b.started || 0)).forEach(c => {
        const card = ui.el('div', 'conveyor-vcard conveyor-vcard-' + ph);
        const protoEl = ui.el('span', 'conveyor-proto', { text: (c.protocol || 'http').toUpperCase() });
        protoEl.style.color = protoColors[c.protocol] || protoColors.http;
        card.appendChild(protoEl);

        const addrEl = ui.el('span', 'conveyor-addr', { text: c.addr || '—' });
        card.appendChild(addrEl);

        const elapsed = Math.max(0, now - (c.started || now));
        const elapsedEl = ui.el('span', 'conveyor-elapsed', { text: elapsed.toFixed(1) + 's' });
        card.appendChild(elapsedEl);

        if (c.cc) {
          const flagEl = ui.el('span', 'conveyor-flag', { text: ui.flag(c.cc) || '' });
          card.appendChild(flagEl);
        }

        items.appendChild(card);
      });
    });

    const live = document.getElementById('pipeline-live');
    if (live) {
      if (s.paused) { live.textContent = t('page.hunt.paused'); live.className = 'pipeline-live paused'; }
      else if (s.running) { live.textContent = active.length + ' ' + t('page.hunt.conv_active'); live.className = 'pipeline-live active'; }
      else { live.textContent = t('page.hunt.idle'); live.className = 'pipeline-live'; }
    }
  }

  function updateResults(s) {
    const counts = s.counts || {};
    const alive = s.top_proxies || [];
    const dead = s.recent_dead || [];
    const protoColors = { socks5: 'var(--accent)', socks4: 'var(--info)', http: 'var(--text-secondary)', https: 'var(--success)' };

    const aliveEl = document.getElementById('results-alive-items');
    const deadEl = document.getElementById('results-dead-items');
    const aliveCount = document.getElementById('results-alive-count');
    const deadCount = document.getElementById('results-dead-count');
    const totalCount = document.getElementById('results-count');
    if (aliveCount) aliveCount.textContent = String(counts.alive || 0);
    if (deadCount) deadCount.textContent = String(counts.dead || 0);
    if (totalCount) totalCount.textContent = (counts.alive || 0) + ' / ' + (counts.dead || 0);

    const renderCard = (p, cls) => {
      const card = ui.el('div', 'conveyor-vcard ' + cls);
      const protoEl = ui.el('span', 'conveyor-proto', { text: (p.protocol || 'http').toUpperCase() });
      protoEl.style.color = protoColors[p.protocol] || protoColors.http;
      card.appendChild(protoEl);
      const addrEl = ui.el('span', 'conveyor-addr', { text: p.address });
      addrEl.classList.add('proxy-address-link');
      addrEl.dataset.cardAddr = p.address;
      card.appendChild(addrEl);
      if (p.country_code) {
        const flagEl = ui.el('span', 'conveyor-flag', { text: ui.flag(p.country_code) || '' });
        card.appendChild(flagEl);
      }
      if (p.speed_avg) {
        const speedEl = ui.el('span', 'conveyor-elapsed', { text: Math.round(p.speed_avg) + 'KB/s' });
        card.appendChild(speedEl);
      }
      return card;
    };

    if (aliveEl) {
      aliveEl.innerHTML = '';
      alive.slice(0, 50).forEach(p => aliveEl.appendChild(renderCard(p, 'conveyor-vcard-alive')));
    }
    if (deadEl) {
      deadEl.innerHTML = '';
      dead.slice(0, 50).forEach(p => deadEl.appendChild(renderCard(p, 'conveyor-vcard-dead')));
    }

    [aliveEl, deadEl].forEach(el => {
      if (!el) return;
      el.querySelectorAll('[data-card-addr]').forEach(link => {
        link.addEventListener('click', (e) => {
          e.stopPropagation();
          const addr = link.dataset.cardAddr;
          if (addr && window.proxyCard) window.proxyCard.show(addr);
        });
      });
    });
  }

  function updateStats(s) {
    const c = s.counts || {};
    const el = id => document.getElementById(id);
    const paused = s.paused || false;
    const manual = s.manual_pause || false;
    if (el('btn-hunt-start')) el('btn-hunt-start').disabled = s.running && !paused;
    if (el('btn-hunt-pause')) el('btn-hunt-pause').disabled = !s.running || paused;
    if (el('btn-hunt-resume')) el('btn-hunt-resume').disabled = !paused;
    if (el('btn-hunt-stop')) el('btn-hunt-stop').disabled = !s.running && !paused;

    const skipBtn = el('btn-hunt-skip');
    if (skipBtn) {
      const skippable = s.running && !paused && (s.phase === 'downloading' || s.phase === 'blacklists' || s.phase === 'validating');
      skipBtn.style.display = skippable ? '' : 'none';
    }

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
    if (el('p-new-working')) el('p-new-working').textContent = p.new_working || 0;
    if (el('p-confirmed-working')) el('p-confirmed-working').textContent = p.confirmed_working || 0;

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
      if (p.ssl_supported || p.protocol === 'https') flags.push('<span style="color:var(--success);font-weight:600">HTTPS</span>');
      else flags.push('<span style="color:var(--text-muted)">HTTP</span>');
      if (p.mitm_suspect) flags.push('<span style="color:var(--danger);font-weight:600">MITM!</span>');
      const proto = p.protocol || 'http';
      const favStar = p.is_favorite ? '<svg width="11" height="11" style="vertical-align:-2px;color:var(--warning);flex-shrink:0;width:11px;height:11px;margin-right:2px"><use href="#icon-star"/></svg>' : '<span style="width:13px;flex-shrink:0;display:inline-block"></span>';
      return [
        `<span style="color:var(--text-muted)">${i+1}</span>`,
        `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="font-size:10px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${favStar}${p.address}</span>`,
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

    wrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
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
      `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(b.address)}" style="font-size:10px;cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${b.address}</span>`,
      `<span style="color:var(--danger);font-size:10px">${b.reason || '—'}</span>`,
      b.country || '—',
      `<button class="btn btn-xs btn-secondary" onclick="blRemove('${b.address}')" style="padding:1px 4px;font-size:9px">×</button>`,
    ]);
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
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
      updatePipelineStrip(s);
      updateConveyor(s);
      updateProgress(s);
      updateResults(s);
      updateTopProxies(s.top_proxies);
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
