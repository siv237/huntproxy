router.register('interception', (container) => {
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';

  // ── Card 1: whole-machine transparent interception (copy-paste) ──
  const card = ui.el('div', 'card');
  card.id = 'interception-card';
  card.appendChild(ui.el('div', 'card-title', { text: t('page.interception.localTitle'), style: 'margin-bottom:8px' }));
  card.appendChild(ui.el('div', '', {
    style: 'font-size:12px;color:var(--text-secondary);margin-bottom:10px;line-height:1.4',
    text: t('page.interception.wholeMachineDesc'),
  }));

  const status = ui.el('div', '', {
    id: 'interception-status',
    style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:10px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)',
  });
  card.appendChild(status);

  const info = ui.el('div', '', { id: 'interception-info', style: 'font-size:12px;color:var(--text-secondary);margin-bottom:10px' });
  card.appendChild(info);

  function buildCmdBlock(labelKey, codeId, btnId) {
    const wrap = ui.el('div', '', { style: 'margin-top:10px' });
    wrap.appendChild(ui.el('div', '', {
      style: 'font-size:11px;color:var(--text-secondary);font-weight:600;margin-bottom:4px',
      text: t(labelKey),
    }));
    const code = ui.el('code', '', {
      id: codeId,
      style: 'display:block;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-xs);padding:8px 10px;color:var(--text-primary);white-space:pre-wrap;word-break:break-all',
    });
    wrap.appendChild(code);
    const btn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.interception.copy'), id: btnId, style: 'margin-top:6px' });
    btn.addEventListener('click', () => copyText(code.textContent, btn));
    wrap.appendChild(btn);
    return wrap;
  }

  card.appendChild(buildCmdBlock('page.interception.applyCmd', 'interception-apply', 'btn-apply-copy'));
  card.appendChild(buildCmdBlock('page.interception.revertCmd', 'interception-revert', 'btn-revert-copy'));

  card.appendChild(ui.el('div', '', {
    style: 'margin-top:12px;font-size:11px;color:var(--text-muted);line-height:1.5',
    text: t('page.interception.localNetNote'),
  }));
  card.appendChild(ui.el('div', '', {
    style: 'margin-top:6px;font-size:11px;color:var(--text-muted);line-height:1.5',
    text: t('page.interception.runHint'),
  }));
  container.appendChild(card);

  // ── Card 2: transparent proxy control (reuses existing endpoints) ──
  const tpCard = ui.el('div', 'card');
  tpCard.id = 'interception-tp-card';
  tpCard.appendChild(ui.el('div', 'card-title', { text: t('page.server.transparent'), style: 'margin-bottom:8px' }));

  const tpStatus = ui.el('div', '', {
    id: 'tp-status-bar',
    style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:8px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)',
  });
  tpStatus.innerHTML = `<span id="tp-dot" style="width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0"></span><span id="tp-status-text">${t('page.server.stopped')}</span>`;
  tpCard.appendChild(tpStatus);

  const tpRow = ui.el('div', '', { style: 'display:flex;gap:4px;align-items:center;margin-bottom:6px' });
  tpRow.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary);font-weight:600;width:52px;flex-shrink:0', text: t('page.server.port') }));
  const tpPortInp = ui.el('input', '', { id: 'interception-tp-port', type: 'number', value: '17477', min: '1024', max: '65535', style: 'width:72px;padding:3px 6px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
  tpRow.appendChild(tpPortInp);
  const tpStartBtn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.server.start'), id: 'btn-tp-start' });
  tpStartBtn.addEventListener('click', () => api.transparentStart(tpPortInp.value).then(() => app.toast(t('page.server.transparentStarted'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
  tpRow.appendChild(tpStartBtn);
  const tpStopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.server.stop'), id: 'btn-tp-stop' });
  tpStopBtn.addEventListener('click', () => api.transparentStop().then(() => app.toast(t('page.server.transparentStopped'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
  tpRow.appendChild(tpStopBtn);
  tpCard.appendChild(tpRow);

  const tpConnRow = ui.el('div', '', { style: 'display:flex;gap:12px;align-items:baseline' });
  const connEl = ui.el('div', '', { style: 'display:flex;align-items:baseline;gap:4px' });
  connEl.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.server.transparent') }));
  connEl.appendChild(ui.el('span', '', { id: 'interception-tp-connections', style: 'font-size:16px;font-weight:700;color:var(--accent)', text: '0' }));
  tpConnRow.appendChild(connEl);
  tpCard.appendChild(tpConnRow);
  container.appendChild(tpCard);

  // ── Card 3: live intercepted connections (transparent log) ──
  const logCard = ui.el('div', 'card');
  logCard.id = 'interception-tp-log-card';
  logCard.style.display = 'flex';
  logCard.style.flexDirection = 'column';
  logCard.style.overflow = 'hidden';
  logCard.appendChild(ui.el('div', 'card-title', { text: t('page.server.clientLog'), style: 'margin-bottom:8px' }));
  const tpLog = ui.el('div', '', { id: 'interception-tp-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow-y:auto;flex:1;min-height:0;color:var(--text-primary)' });
  tpLog.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.server.proxyNotStarted')}</div>`;
  logCard.appendChild(tpLog);
  container.appendChild(logCard);

  function copyText(txt, btn) {
    navigator.clipboard.writeText(txt).then(() => {
      const old = btn.textContent;
      btn.textContent = '✓';
      setTimeout(() => { btn.textContent = old; }, 1200);
    }).catch(() => app.toast(t('common.error', { message: txt }), 'error'));
  }

  function renderInterceptStatus(st) {
    const el = document.getElementById('interception-status');
    if (!el) return;
    const active = !!(st && st.active);
    el.style.background = active ? 'var(--success-bg)' : 'var(--surface-raised)';
    el.style.borderColor = active ? 'var(--success)' : 'var(--border)';
    el.style.color = active ? 'var(--success)' : 'var(--text-secondary)';
    let label = active ? t('page.interception.active') : t('page.interception.inactive');
    if (active && st.applied_at) {
      label += ' · ' + t('page.interception.appliedAt') + ' ' + st.applied_at;
    }
    el.innerHTML = `<span style="width:8px;height:8px;border-radius:50%;background:${active ? 'var(--success)' : 'var(--text-muted)'};flex-shrink:0"></span><span>${label}</span>`;
  }

  function updateTpControl(ts) {
    const bar = document.getElementById('tp-status-bar');
    const dot = document.getElementById('tp-dot');
    const txt = document.getElementById('tp-status-text');
    const running = !!(ts && ts.running);
    if (bar) { bar.style.background = running ? 'var(--success-bg)' : 'var(--surface-raised)'; bar.style.borderColor = running ? 'var(--success)' : 'var(--border)'; bar.style.color = running ? 'var(--success)' : 'var(--text-secondary)'; }
    if (dot) dot.style.background = running ? 'var(--success)' : 'var(--text-muted)';
    if (txt) txt.textContent = running ? t('page.server.running') + ' ' + (ts.port || 17477) : t('page.server.stopped');
    const startBtn = document.getElementById('btn-tp-start');
    const stopBtn = document.getElementById('btn-tp-stop');
    if (startBtn) startBtn.disabled = running;
    if (stopBtn) stopBtn.disabled = !running;
    if (document.getElementById('interception-tp-port') && ts && ts.port) document.getElementById('interception-tp-port').value = ts.port;
    const conn = document.getElementById('interception-tp-connections');
    if (conn) conn.textContent = ts ? (ts.connections || 0) : 0;
  }

  function updateTpLog(ts) {
    const log = document.getElementById('interception-tp-log');
    if (!log) return;
    const entries = (ts && ts.log) || [];
    if (!entries.length) {
      log.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.server.proxyNotStarted')}</div>`;
      return;
    }
    const fmtTarget = tgt => {
      if (!tgt || tgt === '?') return '?';
      const m = tgt.match(/^(https?:\/\/)?([^\/:]+)(.*)/);
      if (!m) return tgt;
      return (m[1] || '') + '<b>' + m[2] + '</b>' + (m[3] || '');
    };
    log.innerHTML = entries.map(e => `<span style="color:var(--text-muted)">${ui.fmtTime(e.ts)}</span> ${e.client || '?'} → ${fmtTarget(e.target)} [${e.status || ''}] <span style="color:var(--info)">via ${ui.escHtml(e.upstream || 'direct')}</span>`).join('<br>');
  }

  async function load() {
    try {
      const d = await api.interception();
      if (document.getElementById('interception-apply')) document.getElementById('interception-apply').textContent = d.apply_command || '';
      if (document.getElementById('interception-revert')) document.getElementById('interception-revert').textContent = d.revert_command || '';
      const ipText = (d.own_ips && d.own_ips.length) ? d.own_ips.join(', ') : '—';
      const infoEl = document.getElementById('interception-info');
      if (infoEl) {
        infoEl.innerHTML =
          `<div><b>${t('page.interception.detectedIp')}:</b> ${ipText}</div>` +
          `<div><b>${t('page.interception.proxyPid')}:</b> ${d.proxy_pid != null ? d.proxy_pid : '—'}</div>`;
      }
      renderInterceptStatus(d.status);
    } catch (e) {
      console.error('interception load', e);
    }
    try {
      const ts = await api.transparentStatus();
      updateTpControl(ts);
      updateTpLog(ts);
    } catch (e) {
      console.error('transparent status', e);
    }
  }

  load();
  const id = setInterval(load, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
