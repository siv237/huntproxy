router.register('interception', (container) => {
  // Last port reported by the backend; the input is synced only when the
  // SERVER-side value changes so the 2s poll never clobbers user edits.
  let lastTpPort = null;
  let currentTab = 0;
  let selCfgLoaded = false;
  let editingId = null;
  let lastTpLog = [];
  let logRuleFilter = '';
  let logResFilter = '';
  container.innerHTML = '';
  container.classList.add('interception-page');
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';

  const panelStyle = 'display:flex;flex-direction:column;gap:10px;min-height:0;flex:1';

  const tabBar = ui.tabs(
    [t('page.interception.tabGeneral'), t('page.interception.tabSelective'),
     t('page.interception.tabLog'), t('page.interception.actualRules')],
    (_name, i) => { currentTab = i; applyTab(); }
  );
  container.appendChild(tabBar);

  const sharedPanel = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:10px;flex:0 0 auto' });
  container.appendChild(sharedPanel);

  const generalPanel = ui.el('div', '', { style: panelStyle });
  const selectivePanel = ui.el('div', '', { style: panelStyle + ';display:none' });
  const logPanel = ui.el('div', '', { style: panelStyle + ';display:none' });
  const rulesPanel = ui.el('div', '', { style: panelStyle + ';display:none' });
  container.appendChild(generalPanel);
  container.appendChild(selectivePanel);
  container.appendChild(logPanel);
  container.appendChild(rulesPanel);

  function applyTab() {
    generalPanel.style.display = currentTab === 0 ? 'flex' : 'none';
    selectivePanel.style.display = currentTab === 1 ? 'flex' : 'none';
    logPanel.style.display = currentTab === 2 ? 'flex' : 'none';
    rulesPanel.style.display = currentTab === 3 ? 'flex' : 'none';
    if (currentTab === 3) loadRules();
  }
  applyTab();

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

  // ── Readiness checklist + one-click toggle ──
  const readinessEl = ui.el('div', '', {
    id: 'interception-readiness',
    style: 'font-size:12px;line-height:1.6;margin-bottom:10px;padding:8px 10px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-xs)',
  });
  card.appendChild(readinessEl);

  const toggleBtn = ui.el('button', 'btn btn-primary', {
    id: 'btn-intercept-toggle',
    style: 'margin-bottom:10px',
    text: t('page.interception.enable'),
  });
  toggleBtn.addEventListener('click', async () => {
    const wasActive = toggleBtn.dataset.active === '1';
    toggleBtn.disabled = true;
    try {
      if (wasActive) {
        await api.interceptionStop();
      } else {
        toggleBtn.textContent = t('page.interception.applying');
        await api.interceptionApply();
      }
      load();
    } catch (e) {
      app.toast(t('common.error', { message: e.message }), 'error');
      toggleBtn.disabled = false;
    }
  });
  card.appendChild(toggleBtn);

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
  generalPanel.appendChild(card);

  // ── Shared: compact one-line transparent-proxy control ──
  const tpCard = ui.el('div', '', {
    id: 'tp-status-bar',
    style: 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:3px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--surface-raised);color:var(--text-secondary)',
  });
  const tpDot = ui.el('span', '', { id: 'tp-dot', style: 'width:8px;height:8px;border-radius:50%;background:var(--text-muted);flex-shrink:0' });
  const tpLabel = ui.el('span', '', { style: 'font-weight:600;color:var(--text-primary)', text: t('page.server.transparent') });
  const tpText = ui.el('span', '', { id: 'tp-status-text', text: t('page.server.stopped') });
  const tpPortInp = ui.el('input', '', { id: 'interception-tp-port', type: 'number', value: '17477', min: '1024', max: '65535', style: 'width:62px;padding:1px 5px;font-size:11px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
  const tpStartBtn = ui.el('button', 'btn btn-xs btn-primary', { text: t('page.server.start'), id: 'btn-tp-start' });
  tpStartBtn.addEventListener('click', () => api.transparentStart(tpPortInp.value).then(() => app.toast(t('page.server.transparentStarted'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
  const tpStopBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.server.stop'), id: 'btn-tp-stop' });
  tpStopBtn.addEventListener('click', () => api.transparentStop().then(() => app.toast(t('page.server.transparentStopped'))).catch(e => app.toast(t('common.error', { message: e.message }), 'error')));
  const tpConn = ui.el('span', '', { id: 'interception-tp-connections', style: 'color:var(--text-muted)', text: '· 0' });
  tpCard.append(tpDot, tpLabel, tpText, tpPortInp, tpStartBtn, tpStopBtn, tpConn);
  sharedPanel.appendChild(tpCard);

  // ── Tab: the real interception rules currently in the kernel ──
  const rulesCard = ui.el('div', 'card', { style: 'display:flex;flex-direction:column;min-height:0;flex:1' });
  const rulesHead = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:8px' });
  rulesHead.appendChild(ui.el('div', 'card-title', { text: t('page.interception.actualRules'), style: 'margin:0' }));
  const rulesRefresh = ui.el('button', 'btn btn-xs', { id: 'btn-rules-refresh', text: t('common.refresh') });
  rulesHead.appendChild(rulesRefresh);
  rulesCard.appendChild(rulesHead);
  const rulesPre = ui.el('pre', '', {
    id: 'rules-dump',
    style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;white-space:pre-wrap;word-break:break-all;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-xs);padding:8px 10px;margin:0;overflow:auto;min-height:0;flex:1;color:var(--text-primary)',
  });
  rulesCard.appendChild(rulesPre);
  rulesPanel.appendChild(rulesCard);

  async function loadRules() {
    try {
      const r = await api.interceptionSelectiveRules();
      const lines = (r && r.lines) || [];
      if (!lines.length) {
        rulesPre.textContent = t('page.interception.rulesOff');
        return;
      }
      rulesPre.innerHTML = lines.map(pair => {
        const [text, ours] = pair;
        const safe = ui.escHtml(text);
        return ours ? `<span style="color:var(--accent);font-weight:600">${safe}</span>` : safe;
      }).join('\n');
    } catch (e) {
      rulesPre.textContent = t('common.error', { message: e.message });
    }
  }
  rulesRefresh.addEventListener('click', loadRules);

  // ── Card 3: live intercepted connections (own tab, filtered) ──
  const logCard = ui.el('div', 'card');
  logCard.id = 'interception-tp-log-card';
  logCard.style.display = 'flex';
  logCard.style.flexDirection = 'column';
  logCard.style.overflow = 'hidden';
  logCard.style.minHeight = '0';
  logCard.style.flex = '0 0 auto';
  const logHead = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:8px;flex-wrap:wrap' });
  logHead.appendChild(ui.el('div', 'card-title', { text: t('page.server.clientLog'), style: 'margin:0' }));
  logHead.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.interception.colStatus') }));
  const logRuleSel = ui.el('select', '', { id: 'log-rule-sel', style: 'font-size:11px;padding:2px 6px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
  logHead.appendChild(logRuleSel);
  logHead.appendChild(ui.el('span', '', { style: 'font-size:11px;color:var(--text-secondary)', text: t('page.interception.logResource') }));
  const logResSel = ui.el('select', '', { id: 'log-res-sel', style: 'font-size:11px;padding:2px 6px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
  logHead.appendChild(logResSel);
  logCard.appendChild(logHead);
  const tpLog = ui.el('div', '', { id: 'interception-tp-log', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px;line-height:1.5;overflow:auto;max-height:55vh;color:var(--text-primary)' });
  tpLog.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.server.proxyNotStarted')}</div>`;
  logCard.appendChild(tpLog);
  logPanel.appendChild(logCard);

  logRuleSel.addEventListener('change', () => { logRuleFilter = logRuleSel.value; renderLog(); });
  logResSel.addEventListener('change', () => { logResFilter = logResSel.value; renderLog(); });

  function renderReadiness(r) {
    const el = document.getElementById('interception-readiness');
    if (!el) return;
    if (!r) { el.innerHTML = ''; return; }
    const checks = [
      [r.is_root, t('page.interception.readinessIsRoot')],
      [r.iptables, t('page.interception.readinessIptables')],
      [r.cgroup_v2, t('page.interception.readinessCgroup')],
      [r.script_present, t('page.interception.readinessScript')],
      [r.transparent_running, t('page.interception.readinessTransparentRunning')],
      [r.transparent_listening, t('page.interception.readinessTransparentListening', { port: r.transparent_port })],
    ];
    let html = '<div style="font-weight:600;margin-bottom:4px">' + t('page.interception.readinessTitle') + '</div>';
    for (const pair of checks) {
      const ok = pair[0];
      const label = pair[1];
      const color = ok ? 'var(--success)' : '#f85149';
      const mark = ok ? '✓' : '✗';
      html += '<div><span style="color:' + color + ';font-weight:700">' + mark + '</span> ' + label + '</div>';
    }
    if (!r.ready) {
      html += '<div style="margin-top:4px;color:#f85149">' + t('page.interception.notReady') + '</div>';
      for (const b of (r.blockers || [])) html += '<div style="color:#f85149">• ' + b + '</div>';
    } else {
      html += '<div style="margin-top:4px;color:var(--success)">' + t('page.interception.readyHint') + '</div>';
    }
    el.innerHTML = html;
  }

  function applyModeVisibility(d) {
    const wholeOn = !!(d.status && d.status.active);
    const selTab = tabBar.children[1];
    if (!selTab) return;
    selTab.style.display = wholeOn ? 'none' : '';
    if (wholeOn && currentTab === 1 && tabBar.children[0]) tabBar.children[0].click();
  }

  function updateToggleBtn(d) {
    const btn = document.getElementById('btn-intercept-toggle');
    if (!btn) return;
    const active = !!(d.status && d.status.active);
    btn.dataset.active = active ? '1' : '0';
    if (active) {
      btn.textContent = t('page.interception.disable');
      btn.disabled = false;
    } else if (d.readiness && d.readiness.ready) {
      btn.textContent = t('page.interception.enable');
      btn.disabled = false;
    } else {
      btn.textContent = t('page.interception.enable');
      btn.disabled = true;
      btn.title = t('page.interception.notReady');
    }
  }

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
    if (ts && ts.port && ts.port !== lastTpPort) {
      lastTpPort = ts.port;
      const inp = document.getElementById('interception-tp-port');
      if (inp) inp.value = ts.port;
    }
    const conn = document.getElementById('interception-tp-connections');
    if (conn) conn.textContent = '· ' + (ts ? (ts.connections || 0) : 0);
  }

  function refreshLogSelects() {
    const ruleSel = document.getElementById('log-rule-sel');
    if (ruleSel) {
      const statuses = [...new Set(lastTpLog.map(e => e.status || '—'))].sort();
      ruleSel.innerHTML = `<option value="">${t('page.interception.logAll')}</option>`
        + statuses.map(s => `<option value="${ui.escHtml(s)}">${ui.escHtml(s)}</option>`).join('');
      ruleSel.value = statuses.includes(logRuleFilter) ? logRuleFilter : '';
      logRuleFilter = ruleSel.value;
    }
    const resSel = document.getElementById('log-res-sel');
    if (resSel) {
      const resources = (selectiveData && selectiveData.resources) || [];
      resSel.innerHTML = `<option value="">${t('page.interception.logAll')}</option>`
        + resources.map(r => `<option value="${ui.escHtml(r.id)}">${ui.escHtml(r.name)}</option>`).join('');
      resSel.value = resources.some(r => r.id === logResFilter) ? logResFilter : '';
      logResFilter = resSel.value;
    }
  }

  function resourceNameForTarget(tgt) {
    const host = String(tgt || '').split(':')[0];
    const res = ((selectiveData && selectiveData.resources) || []).find(r => (r.ips || []).includes(host));
    return res ? res.name : '';
  }

  function renderLog() {
    const log = document.getElementById('interception-tp-log');
    if (!log) return;
    let entries = lastTpLog;
    if (logRuleFilter) entries = entries.filter(e => (e.status || '—') === logRuleFilter);
    if (logResFilter) {
      const res = ((selectiveData && selectiveData.resources) || []).find(r => r.id === logResFilter);
      const ips = res ? res.ips : [];
      entries = entries.filter(e => ips.some(ip => {
        const tgt = String(e.target || '');
        return tgt === ip || tgt.startsWith(ip + ':');
      }));
    }
    const cell = (extra = '') => `padding:2px 8px;border-bottom:1px solid var(--border);white-space:nowrap;${extra}`;
    const headers = [
      t('page.interception.colTime'), t('page.interception.colClient'),
      t('page.interception.logResource'), t('page.interception.colRule'),
      t('page.interception.colTarget'), t('page.interception.colStatus'),
      t('page.interception.colVia'), t('page.interception.colTraffic'),
    ];
    const head = '<thead><tr style="text-align:left;color:var(--text-secondary)">'
      + headers.map(h => `<th style="${cell('font-weight:600')}">${ui.escHtml(h)}</th>`).join('')
      + '</tr></thead>';
    if (!entries.length) {
      log.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.interception.logEmpty')}</div>`;
      return;
    }
    const rows = entries.map(e => {
      const st = e.status || '';
      const ok = st === 'ok';
      const bad = /502|^err|no original|empty|self-target|dropped/.test(st);
      const stColor = ok ? 'var(--success)' : (bad ? '#f85149' : 'var(--text-muted)');
      const via = e.upstream || 'direct';
      const viaProxy = via.includes('proxy') || via.includes('pool');
      const resName = e.resource || resourceNameForTarget(e.target);
      const rule = e.rule || '';
      return '<tr>'
        + `<td style="${cell('color:var(--text-muted)')}">${ui.fmtTime(e.ts)}</td>`
        + `<td style="${cell('color:var(--text-secondary)')}">${ui.escHtml(e.client || '?')}</td>`
        + `<td style="${cell(resName ? 'color:var(--accent);font-weight:600' : 'color:var(--text-muted)')}">${ui.escHtml(resName || '—')}</td>`
        + `<td style="${cell('color:var(--text-secondary)')}">${ui.escHtml(rule || '—')}</td>`
        + `<td style="${cell('color:var(--text-primary)')}">${ui.escHtml(e.target || '?')}</td>`
        + `<td style="${cell('color:' + stColor + ';font-weight:600')}">${ui.escHtml(st)}</td>`
        + `<td style="${cell('color:' + (viaProxy ? 'var(--info)' : 'var(--text-muted)') + '')}">${ui.escHtml(via)}</td>`
        + `<td style="${cell('color:var(--text-muted)')}">${e.bytes_in || 0}↑ ${e.bytes_out || 0}↓ · ${e.duration != null ? e.duration + 's' : ''}</td>`
        + '</tr>';
    }).join('');
    log.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:11px">'
      + head + '<tbody>' + rows + '</tbody></table>';
  }

  function updateTpLog(ts) {
    lastTpLog = (ts && ts.log) || [];
    refreshLogSelects();
    renderLog();
    if (selectiveData && !editingId) renderResources(selectiveData.resources);
  }

  // ── Selective tab ────────────────────────────────────────────────────

  const selStatus = ui.el('div', '', {
    id: 'sel-status',
    style: 'display:flex;align-items:center;gap:6px;padding:4px 8px;border-radius:var(--radius-xs);margin-bottom:8px;font-size:12px;font-weight:500;background:var(--surface-raised);border:1px solid var(--border);color:var(--text-secondary)',
  });
  selectivePanel.appendChild(selStatus);

  const selMismatch = ui.el('div', '', {
    id: 'sel-mismatch',
    style: 'display:none;font-size:12px;line-height:1.5;margin-bottom:8px;padding:8px 10px;border-radius:var(--radius-xs);background:var(--bg);border:1px solid #f85149;color:#f85149',
  });
  selectivePanel.appendChild(selMismatch);

  const selBtns = ui.el('div', '', { style: 'display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:10px' });
  const masterWrap = ui.el('label', '', {
    style: 'display:inline-flex;align-items:center;gap:8px;font-size:13px;font-weight:600;cursor:pointer;padding:4px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--surface-raised)',
    id: 'sel-master-wrap',
  });
  const selMaster = ui.el('input', '', { id: 'sel-master', type: 'checkbox', style: 'width:16px;height:16px;flex-shrink:0' });
  masterWrap.appendChild(selMaster);
  const masterText = ui.el('span', '', { id: 'sel-master-text', text: '' });
  masterWrap.appendChild(masterText);
  selMaster.addEventListener('change', async () => {
    selMaster.disabled = true;
    const wantOn = selMaster.checked;
    try {
      await (wantOn ? api.interceptionSelectiveApply() : api.interceptionSelectiveStop());
      app.toast(wantOn ? t('page.interception.masterOnLabel') : t('page.interception.masterOffLabel'));
    } catch (e) {
      app.toast(t('common.error', { message: e.message }), 'error');
    } finally {
      selMaster.disabled = false;
      reloadSelective();
    }
  });
  selBtns.append(masterWrap);
  selectivePanel.appendChild(selBtns);

  function selAct(fn) {
    fn().then(() => reloadSelective())
      .catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  const LBL = 'font-size:11px;color:var(--text-secondary);font-weight:600';
  const INP = 'padding:6px 9px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)';
  function field(label, el, extra = '') {
    const w = ui.el('label', '', { style: `display:flex;flex-direction:column;gap:4px;min-width:0;${extra}` });
    w.appendChild(ui.el('span', '', { style: LBL, text: label }));
    w.appendChild(el);
    return w;
  }
  function check(label, input) {
    const w = ui.el('label', '', { style: 'display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer;padding:3px 0' });
    w.appendChild(input);
    w.appendChild(ui.el('span', '', { text: label }));
    return w;
  }
  const actionsRow = () => ui.el('div', '', { style: 'display:flex;justify-content:flex-end;margin-top:auto;padding-top:12px' });

  // Two tiles side by side, equal height.
  const formsRow = ui.el('div', '', {
    style: 'display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:10px;align-items:stretch',
  });

  // Tile 1: parameters
  const cfgCard = ui.el('div', 'card', { style: 'display:flex;flex-direction:column' });
  cfgCard.appendChild(ui.el('div', 'card-title', { text: t('page.interception.selectiveTitle') }));
  cfgCard.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin:4px 0 12px;line-height:1.4', text: t('page.interception.selectiveDesc') }));
  const selInterval = ui.el('input', '', { id: 'sel-interval', type: 'number', min: '30', style: INP + ';width:100px' });
  const selIface = ui.el('input', '', { id: 'sel-iface', type: 'text', placeholder: 'auto', style: INP + ';width:140px' });
  const cfgFields = ui.el('div', '', { style: 'display:flex;gap:16px;flex-wrap:wrap;margin-bottom:8px' });
  cfgFields.append(
    field(t('page.interception.resolveInterval'), selInterval),
    field(t('page.interception.iface'), selIface),
  );
  cfgCard.appendChild(cfgFields);
  const selQuic = ui.el('input', '', { id: 'sel-quic', type: 'checkbox' });
  const selFallback = ui.el('input', '', { id: 'sel-fallback', type: 'checkbox' });
  cfgCard.appendChild(check(t('page.interception.dropQuic'), selQuic));
  cfgCard.appendChild(check(t('page.interception.fallbackDirect'), selFallback));
  const cfgActions = actionsRow();
  const selSaveBtn = ui.el('button', 'btn btn-primary', { id: 'btn-sel-save', text: t('page.interception.save') });
  selSaveBtn.addEventListener('click', () => selAct(() => api.interceptionSelectiveConfig({
    iface: selIface.value,
    resolve_interval_sec: parseInt(selInterval.value, 10) || 300,
    drop_quic: selQuic.checked,
    fallback_direct: selFallback.checked,
  })));
  cfgActions.appendChild(selSaveBtn);
  cfgCard.appendChild(cfgActions);

  // Tile 2: add resource
  const addCard = ui.el('div', 'card', { style: 'display:flex;flex-direction:column' });
  addCard.appendChild(ui.el('div', 'card-title', { text: t('page.interception.addResource') }));
  const addTop = ui.el('div', '', { style: 'display:flex;gap:16px;align-items:flex-start;flex-wrap:wrap;margin-top:4px' });
  const selName = ui.el('input', '', { id: 'sel-name', type: 'text', placeholder: 'youtube', style: INP + ';width:100%' });
  const selAddresses = ui.el('textarea', '', { id: 'sel-addresses', rows: '4', placeholder: t('page.interception.addressesPlaceholder'), style: INP + ';width:100%;min-height:70px;resize:vertical;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace' });
  addTop.append(
    field(t('page.interception.resourceName'), selName, 'flex:0 1 180px'),
    field(t('page.interception.addressesLabel'), selAddresses, 'flex:1;min-width:220px'),
  );
  addCard.appendChild(addTop);
  addCard.appendChild(ui.el('div', '', { style: 'margin-top:6px;font-size:11px;color:var(--text-muted)', text: t('page.interception.addressesHint') }));
  const addBottom = ui.el('div', '', { style: 'display:flex;gap:20px;align-items:center;flex-wrap:wrap;margin-top:10px' });
  const addAuto = ui.el('input', '', { id: 'add-auto', type: 'checkbox' });
  addAuto.checked = true;
  const addPorts = ui.el('input', '', { id: 'add-ports', type: 'text', placeholder: '443,8080', style: INP + ';width:150px' });
  const addHint = ui.el('span', '', { style: 'font-size:11px;color:var(--text-muted)' });
  const syncAddPorts = () => {
    if (addAuto.checked) {
      addPorts.setAttribute('disabled', 'disabled');
      addPorts.value = '';
      addPorts.style.opacity = '0.5';
      addHint.textContent = '';
    } else {
      addPorts.removeAttribute('disabled');
      addPorts.style.opacity = '1';
      addHint.textContent = t('page.interception.manualHint');
    }
  };
  addAuto.addEventListener('change', syncAddPorts);
  syncAddPorts();
  addBottom.append(check(t('page.interception.autoAll'), addAuto),
                   field(t('page.interception.portsShort'), addPorts), addHint);
  addCard.appendChild(addBottom);
  const addActions = actionsRow();
  const selAddBtn = ui.el('button', 'btn btn-primary', { id: 'btn-sel-add', text: t('page.interception.add') });
  selAddBtn.addEventListener('click', () => {
    const name = selName.value.trim();
    const addresses = selAddresses.value.split('\n').map(s => s.trim()).filter(Boolean);
    if (!name) { app.toast(t('page.interception.resourceName'), 'error'); return; }
    selAct(() => api.interceptionResourceCreate({ name, addresses, auto: addAuto.checked, ports: addPorts.value }));
    selName.value = '';
    selAddresses.value = '';
  });
  addActions.appendChild(selAddBtn);
  addCard.appendChild(addActions);
  formsRow.append(cfgCard, addCard);
  selectivePanel.appendChild(formsRow);

  // Resources list
  const listCard = ui.el('div', 'card');
  listCard.style.display = 'flex';
  listCard.style.flexDirection = 'column';
  listCard.style.minHeight = '0';
  const listHead = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:8px' });
  listHead.appendChild(ui.el('div', 'card-title', { text: t('page.interception.tabSelective'), style: 'margin:0' }));
  const selResolveAll = ui.el('button', 'btn btn-xs', { id: 'btn-sel-resolve-all', text: t('page.interception.resolveAll') });
  selResolveAll.addEventListener('click', async () => {
    if (!selectiveData) return;
    for (const res of selectiveData.resources) {
      try { await api.interceptionResourceResolve(res.id); } catch (e) { console.error(e); }
    }
    reloadSelective();
  });
  listHead.appendChild(selResolveAll);
  listCard.appendChild(listHead);
  const selList = ui.el('div', '', { id: 'sel-resources', style: 'overflow-y:auto;min-height:0' });
  listCard.appendChild(selList);
  selectivePanel.appendChild(listCard);

  let selectiveData = null;

  function renderSelective(d) {
    selectiveData = d;
    const cfg = d.config || {};
    if (!selCfgLoaded) {
      selCfgLoaded = true;
      selInterval.value = cfg.resolve_interval_sec || 300;
      selQuic.checked = !!cfg.drop_quic;
      selIface.value = cfg.iface || '';
      selFallback.checked = cfg.fallback_direct !== false;
    }
    const on = !!d.applied;
    const ready = !!(d.readiness && d.readiness.ready);
    selMaster.checked = on;
    selMaster.disabled = !ready && !on;
    const masterLabel = on ? t('page.interception.masterOnLabel') : t('page.interception.masterOffLabel');
    masterText.textContent = masterLabel;
    const masterWrapEl = document.getElementById('sel-master-wrap');
    if (masterWrapEl) {
      masterWrapEl.style.borderColor = on ? 'var(--success)' : 'var(--border)';
      masterWrapEl.style.background = on ? 'var(--success-bg)' : 'var(--surface-raised)';
      masterWrapEl.style.color = on ? 'var(--success)' : 'var(--text-secondary)';
    }
    selStatus.style.background = on ? 'var(--success-bg)' : 'var(--surface-raised)';
    selStatus.style.borderColor = on ? 'var(--success)' : 'var(--border)';
    selStatus.style.color = on ? 'var(--success)' : 'var(--text-secondary)';
    const actual = d.actual || {};
    let rulesLabel;
    if (!actual.available) rulesLabel = t('page.interception.rulesUnknown');
    else rulesLabel = actual.selective_jump ? t('page.interception.rulesOn') : t('page.interception.rulesOff');
    const dotColor = on ? 'var(--success)' : 'var(--text-muted)';
    selStatus.innerHTML =
      `<span style="width:8px;height:8px;border-radius:50%;background:${dotColor};flex-shrink:0"></span>` +
      `<span>${masterLabel}` +
      ` · ${d.enabled_resources} ${t('page.interception.resourcesEnabled')}` +
      ` · ${d.ip_count} ${t('page.interception.addressCount')}` +
      (on ? ` · ${t('page.interception.actualRules')}: ${rulesLabel}` : '') +
      `</span>`;
    // Off = inactive look, but the list stays editable.
    listCard.style.opacity = on ? '1' : '0.55';

    let mismatchText = '';
    let mismatchColor = '#f85149';
    if (d.mismatch === 'leftover') {
      mismatchText = t('page.interception.mismatchLeftover');
    } else if (d.mismatch === 'pending') {
      mismatchText = t('page.interception.mismatchPending');
    } else if (!ready && !on) {
      mismatchText = t('page.interception.needTransparent');
      mismatchColor = 'var(--info)';
    }
    if (mismatchText) {
      selMismatch.textContent = mismatchText;
      selMismatch.style.borderColor = mismatchColor;
      selMismatch.style.color = mismatchColor;
      selMismatch.style.display = 'block';
    } else {
      selMismatch.style.display = 'none';
    }
    renderResources(d.resources || []);
    refreshLogSelects();
    renderLog();
  }

  function resourceView(res) {
    const enabled = !!res.enabled;
    const ips = res.ips || [];
    const row = ui.el('div', '', {
      style: `display:flex;align-items:center;gap:8px;flex-wrap:wrap;padding:4px 0;border-bottom:1px solid var(--border);font-size:12px;opacity:${enabled ? '1' : '0.55'}`,
    });
    row.appendChild(ui.el('span', '', {
      style: 'font-size:10px;font-weight:700;padding:1px 6px;border-radius:8px;flex-shrink:0;' +
        (enabled ? 'background:var(--success-bg);color:var(--success)' : 'background:var(--surface-raised);color:var(--text-muted)'),
      text: enabled ? t('page.interception.stateOn') : t('page.interception.stateOff'),
    }));
    row.appendChild(ui.el('b', '', { style: `font-size:13px;${enabled ? '' : 'color:var(--text-muted)'}`, text: res.name }));
    row.appendChild(ui.el('span', '', {
      style: 'font-size:10px;color:var(--text-secondary);border:1px solid var(--border);border-radius:8px;padding:1px 6px;flex-shrink:0',
      text: res.auto ? t('page.interception.autoBadge') : `${t('page.interception.portsShort')}: ${res.ports || '—'}`,
    }));
    row.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary)', text: `${ips.length} IP` }));
    const e0 = (res.entries || [])[0];
    if (e0) {
      const ecolor = e0.status === 'ok' ? 'var(--success)' : (e0.status === 'error' ? '#f85149' : 'var(--text-muted)');
      row.appendChild(ui.el('span', '', { style: `color:${ecolor}`, text: e0.status }));
      row.appendChild(ui.el('code', '', { style: 'color:var(--text-primary);font-family:ui-monospace,Menlo,Consolas,monospace', text: e0.address }));
      const extra = (res.entries.length - 1);
      if (extra > 0) row.appendChild(ui.el('span', '', { style: 'color:var(--text-muted)', text: `+${extra}` }));
      if (e0.ips && e0.ips.length) row.appendChild(ui.el('span', '', { style: 'color:var(--text-muted)', text: e0.ips.join(', ') }));
    }
    const targetMatches = tgt => ips.some(ip => { const s = String(tgt || ''); return s === ip || s.startsWith(ip + ':'); });
    const last = lastTpLog.find(e => targetMatches(e.target));
    if (last) {
      const fresh = (Date.now() / 1000 - last.ts) < 60;
      const color = last.status === 'ok' ? 'var(--success)' : '#f85149';
      row.appendChild(ui.el('span', '', {
        style: `color:${color};flex-shrink:0`,
        text: `· ${last.status} ${ui.ago(last.ts)}${fresh ? ' ●' : ''}`,
      }));
    }
    row.appendChild(ui.el('span', '', { style: 'flex:1' }));
    const toggleBtn = ui.el('button', `btn btn-xs ${enabled ? '' : 'btn-primary'}`, { text: enabled ? t('page.interception.disableRes') : t('page.interception.enableRes') });
    toggleBtn.addEventListener('click', () => selAct(() => api.interceptionResourceToggle(res.id)));
    row.appendChild(toggleBtn);
    const logBtn = ui.el('button', 'btn btn-xs', { text: t('page.interception.viewLog') });
    logBtn.addEventListener('click', () => {
      logResFilter = res.id;
      logRuleFilter = '';
      refreshLogSelects();
      const tabsEls = tabBar.querySelectorAll('.card-tab');
      if (tabsEls[2]) tabsEls[2].click();
      renderLog();
    });
    row.appendChild(logBtn);
    const resolveBtn = ui.el('button', 'btn btn-xs', { text: t('page.interception.resolve') });
    resolveBtn.addEventListener('click', () => selAct(() => api.interceptionResourceResolve(res.id)));
    row.appendChild(resolveBtn);
    const editBtn = ui.el('button', 'btn btn-xs', { text: t('page.interception.edit') });
    editBtn.addEventListener('click', () => { editingId = res.id; renderResources(selectiveData.resources); });
    row.appendChild(editBtn);
    const delBtn = ui.el('button', 'btn btn-xs btn-danger', { text: t('page.interception.delete') });
    delBtn.addEventListener('click', () => {
      if (!window.confirm(t('page.interception.confirmDelete', { name: res.name }))) return;
      editingId = null;
      selAct(() => api.interceptionResourceDelete(res.id));
    });
    row.appendChild(delBtn);
    return row;
  }

  function resourceEdit(res) {
    const wrap = ui.el('div', '', { style: 'padding:8px 0;border-bottom:1px solid var(--border);display:flex;flex-direction:column;gap:10px' });
    const nameInp = ui.el('input', '', { type: 'text', value: res.name, style: INP + ';width:240px' });
    const addr = ui.el('textarea', '', { rows: '4', style: INP + ';min-height:70px;resize:vertical;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace' });
    addr.value = (res.entries || []).map(e => e.address).join('\n');
    const top = ui.el('div', '', { style: 'display:flex;gap:12px;align-items:flex-start;flex-wrap:wrap' });
    top.append(
      field(t('page.interception.resourceName'), nameInp),
      field(t('page.interception.addressesLabel'), addr, 'flex:1;min-width:260px'),
    );
    const edAuto = ui.el('input', '', { type: 'checkbox' });
    edAuto.checked = !!res.auto;
    const edPorts = ui.el('input', '', { type: 'text', placeholder: '443,8080', style: INP + ';width:150px' });
    edPorts.value = res.ports || '';
    const syncEdPorts = () => {
      if (edAuto.checked) { edPorts.setAttribute('disabled', 'disabled'); edPorts.style.opacity = '0.5'; }
      else { edPorts.removeAttribute('disabled'); edPorts.style.opacity = '1'; }
    };
    edAuto.addEventListener('change', syncEdPorts);
    syncEdPorts();
    const edPolicy = ui.el('div', '', { style: 'display:flex;gap:16px;align-items:center;flex-wrap:wrap' });
    edPolicy.append(check(t('page.interception.autoAll'), edAuto),
                   field(t('page.interception.portsShort'), edPorts));
    const row = ui.el('div', '', { style: 'display:flex;gap:8px;justify-content:flex-end' });
    const save = ui.el('button', 'btn btn-primary', { text: t('page.interception.save') });
    save.addEventListener('click', () => {
      const addresses = addr.value.split('\n').map(s => s.trim()).filter(Boolean);
      editingId = null;
      selAct(() => api.interceptionResourceUpdate(res.id, {
        name: nameInp.value.trim(), addresses, auto: edAuto.checked, ports: edPorts.value,
      }));
    });
    const cancel = ui.el('button', 'btn btn-secondary', { text: t('page.interception.cancel') });
    cancel.addEventListener('click', () => { editingId = null; renderResources(selectiveData.resources); });
    row.append(save, cancel);
    wrap.append(top, edPolicy, row);
    return wrap;
  }

  function renderResources(resources) {
    selList.innerHTML = '';
    if (!resources.length) {
      selList.appendChild(ui.el('div', 'empty', { text: t('page.interception.noResources'), style: 'padding:8px;font-size:12px' }));
      return;
    }
    for (const res of resources) {
      selList.appendChild(res.id === editingId ? resourceEdit(res) : resourceView(res));
    }
  }

  async function reloadSelective() {
    try {
      const d = await api.interceptionSelective();
      renderSelective(d);
    } catch (e) {
      console.error('selective load', e);
    }
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
      renderReadiness(d.readiness);
      updateToggleBtn(d);
      applyModeVisibility(d);
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
    if ((currentTab === 1 || currentTab === 2) && !editingId) await reloadSelective();
  }

  load();
  const id = setInterval(load, 2000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
