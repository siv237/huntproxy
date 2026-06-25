router.register('schedules', (container) => {
  let schedules = [];
  let schedulerStatus = { running: false, paused: false, running_tasks: [] };
  let _loading = false;

  const TASK_TYPE_KEYS = {
    hunt_cycle: 'page.schedules.taskHuntCycle',
    ip_blacklist: 'page.schedules.taskIpBlacklist',
    blocklist: 'page.schedules.taskBlocklist',
    health_check: 'page.schedules.taskHealthCheck',
    history: 'page.schedules.taskHistory',
    clear_dead: 'page.schedules.taskClearDead',
    backup: 'page.schedules.taskBackup',
  };

  const STATUS_VARIANTS = {
    ok: 'green',
    failed: 'red',
    running: 'blue',
    skipped: 'yellow',
    never: 'gray',
  };

  const STATUS_KEYS = {
    ok: 'page.schedules.statusOk',
    failed: 'page.schedules.statusFailed',
    running: 'page.schedules.statusRunning',
    skipped: 'page.schedules.statusSkipped',
    never: 'page.schedules.statusNever',
  };

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
    const topRow = ui.el('div', 'grid grid-2 row-stretch', { style: 'flex-shrink:0' });
    topRow.appendChild(buildStatusCard());
    topRow.appendChild(buildLogCard());
    container.appendChild(topRow);
    container.appendChild(buildSchedulesCard());
  }

  function buildStatusCard() {
    const card = ui.card('', '');
    card.id = 'card-scheduler-status';
    card.style.padding = '14px 16px';

    const row = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;flex-wrap:wrap' });

    const dot = ui.el('span', '', { id: 'sched-status-dot', style: 'width:10px;height:10px;border-radius:50%;background:var(--success);flex-shrink:0' });
    row.appendChild(dot);

    const label = ui.el('span', '', { id: 'sched-status-label', style: 'font-weight:600;font-size:14px', text: t('page.schedules.schedulerRunning') });
    row.appendChild(label);

    const spacer = ui.el('div', '', { style: 'flex:1' });
    row.appendChild(spacer);

    const pauseBtn = ui.el('button', 'btn btn-sm btn-secondary', { id: 'sched-pause-btn', text: t('page.schedules.pauseAll') });
    pauseBtn.addEventListener('click', () => {
      if (schedulerStatus.paused) {
        api.schedulesResume().then(() => { app.toast(t('page.schedules.schedulerRunning')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.schedulesPause().then(() => { app.toast(t('page.schedules.schedulerPaused')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    row.appendChild(pauseBtn);

    card.appendChild(row);

    // Stats row
    const statsRow = ui.el('div', '', { id: 'sched-stats-row', style: 'display:flex;gap:20px;margin-top:12px;flex-wrap:wrap' });
    statsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', html: `<span id="sched-stat-enabled"></span>` }));
    statsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', html: `<span id="sched-stat-running"></span>` }));
    statsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', html: `<span id="sched-stat-next"></span>` }));
    card.appendChild(statsRow);

    return card;
  }

  function buildLogCard() {
    const card = ui.card(t('page.schedules.schedulerLog'), '');
    card.id = 'card-scheduler-log';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', {
      id: 'sched-log-body',
      style: 'overflow-y:auto;flex:1;font-family:monospace;font-size:11px;line-height:1.6;padding:4px 0;min-height:120px;max-height:220px',
    });
    card.appendChild(body);
    return card;
  }

  function buildSchedulesCard() {
    const card = ui.card(t('page.schedules.title'), '');
    card.id = 'card-schedules';
    card.style.overflow = 'auto';

    const header = card.querySelector('.card-header') || card;
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.schedules.newSchedule'), style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => showEditor(null));
    card.insertBefore(addBtn, card.firstChild.nextSibling || card.firstChild);

    const body = ui.el('div', '', { id: 'schedules-body' });
    card.appendChild(body);
    return card;
  }

  function formatInterval(sec) {
    if (!sec || sec <= 0) return '—';
    if (sec < 60) return sec + ' ' + t('units.secondsShort');
    if (sec < 3600) return Math.round(sec / 60) + ' ' + t('units.minutesShort');
    if (sec < 86400) return (sec / 3600).toFixed(sec % 3600 === 0 ? 0 : 1) + ' ' + t('units.hoursShort');
    return (sec / 86400).toFixed(sec % 86400 === 0 ? 0 : 1) + ' ' + t('units.daysShort');
  }

  function renderSchedules() {
    const body = document.getElementById('schedules-body');
    if (!body) return;
    body.innerHTML = '';

    if (!schedules.length) {
      body.appendChild(ui.emptyState(t('page.schedules.noSchedules')));
      return;
    }

    const table = ui.table(
      [
        { label: t('page.schedules.taskName'), sortKey: 'name' },
        { label: t('page.schedules.interval'), sortKey: 'interval' },
        { label: t('page.schedules.enabled') },
        { label: t('page.schedules.lastRun') },
        { label: t('page.schedules.nextRun') },
        { label: t('page.schedules.status') },
        { label: t('page.schedules.actions') },
      ],
      schedules.map(s => [
        ui.escHtml(s.name) + '<br><span style="font-size:11px;color:var(--text-secondary)">' + ui.escHtml(s.id) + '</span>',
        formatInterval(s.interval_sec),
        renderToggle(s),
        s.last_run > 0 ? ui.ago(s.last_run) : '—',
        s.enabled && s.next_run > 0 ? ui.ago(s.next_run) : '—',
        renderStatusBadge(s.last_status),
        renderActions(s),
      ])
    );
    body.appendChild(table);
  }

  function renderToggle(s) {
    const checked = s.enabled ? 'checked' : '';
    return `<label style="display:inline-flex;align-items:center;cursor:pointer">
      <input type="checkbox" ${checked} onchange="window._schedToggle('${ui.escHtml(s.id)}')" style="cursor:pointer">
    </label>`;
  }

  function renderStatusBadge(status) {
    const variant = STATUS_VARIANTS[status] || 'gray';
    const label = t(STATUS_KEYS[status] || 'page.schedules.statusNever');
    if (status === 'running') {
      return `<span class="badge badge-${variant}" style="animation:pulse 1.5s infinite">${ui.escHtml(label)}</span>`;
    }
    return `<span class="badge badge-${variant}">${ui.escHtml(label)}</span>`;
  }

  function renderActions(s) {
    const actStyle = 'min-width:32px;height:32px;font-size:15px;padding:4px 8px';
    const runBtn = `<button class="btn btn-ghost" style="${actStyle}" onclick="window._schedRun('${ui.escHtml(s.id)}')" title="${t('page.schedules.runNow')}">▶</button>`;
    const editBtn = `<button class="btn btn-ghost" style="${actStyle}" onclick="window._schedEdit('${ui.escHtml(s.id)}')" title="${t('page.schedules.edit')}">✎</button>`;
    const delBtn = `<button class="btn btn-ghost" style="${actStyle}" onclick="window._schedDelete('${ui.escHtml(s.id)}')" title="${t('page.schedules.delete')}">🗑</button>`;
    return `<div style="display:flex;gap:6px">${runBtn}${editBtn}${delBtn}</div>`;
  }

  function updateHeader() {
    const dot = document.getElementById('sched-status-dot');
    const label = document.getElementById('sched-status-label');
    const btn = document.getElementById('sched-pause-btn');
    if (!dot || !label || !btn) return;
    if (schedulerStatus.paused) {
      dot.style.background = 'var(--warning, #f0ad4e)';
      label.textContent = t('page.schedules.schedulerPaused');
      btn.textContent = t('page.schedules.resumeAll');
    } else if (schedulerStatus.running) {
      dot.style.background = 'var(--success, #28a745)';
      label.textContent = t('page.schedules.schedulerRunning');
      btn.textContent = t('page.schedules.pauseAll');
    } else {
      dot.style.background = 'var(--text-secondary, #888)';
      label.textContent = t('page.schedules.schedulerStopped') || t('page.schedules.schedulerPaused');
      btn.textContent = t('page.schedules.resumeAll');
    }
    // Stats
    const enabledEl = document.getElementById('sched-stat-enabled');
    const runningEl = document.getElementById('sched-stat-running');
    const nextEl = document.getElementById('sched-stat-next');
    if (enabledEl) {
      const enabledCount = schedules.filter(s => s.enabled).length;
      enabledEl.textContent = t('page.schedules.enabled') + ': ' + enabledCount + '/' + schedules.length;
    }
    if (runningEl) {
      const runningCount = (schedulerStatus.running_tasks || []).length;
      runningEl.textContent = t('page.schedules.statusRunning') + ': ' + runningCount;
    }
    if (nextEl) {
      const now = Date.now() / 1000;
      const nextSched = schedules
        .filter(s => s.enabled && s.next_run > 0)
        .map(s => s.next_run)
        .sort((a, b) => a - b)[0];
      if (nextSched) {
        const delta = nextSched - now;
        nextEl.textContent = t('page.schedules.nextRun') + ': ' + (delta > 0 ? ui.ago(nextSched) : t('page.schedules.statusRunning'));
      } else {
        nextEl.textContent = t('page.schedules.nextRun') + ': —';
      }
    }
  }

  function renderLog(entries) {
    const body = document.getElementById('sched-log-body');
    if (!body) return;
    const wasScrolled = body.scrollTop + body.clientHeight >= body.scrollHeight - 20;
    body.innerHTML = '';
    if (!entries.length) {
      body.appendChild(ui.el('div', '', { style: 'color:var(--text-secondary);padding:8px', text: t('page.schedules.noLogEntries') }));
      return;
    }
    const typeColors = {
      ok: 'var(--success)',
      info: 'var(--text-secondary)',
      warn: 'var(--warning, #f0ad4e)',
      error: 'var(--danger, #dc3545)',
      action: 'var(--accent, #007bff)',
    };
    for (const e of entries) {
      const ts = new Date(e.ts * 1000);
      const timeStr = ts.toLocaleTimeString();
      const color = typeColors[e.type] || typeColors.info;
      const line = ui.el('div', '', {
        style: `padding:1px 0;color:${color};white-space:pre-wrap;word-break:break-all`,
        html: `<span style="color:var(--text-secondary)">${timeStr}</span>  ${ui.escHtml(e.msg)}`,
      });
      body.appendChild(line);
    }
    if (wasScrolled) body.scrollTop = body.scrollHeight;
  }

  async function loadLog() {
    try {
      const data = await api.schedulesLog(50);
      renderLog(data.entries || []);
    } catch (e) {
      // ignore
    }
  }

  function showEditor(existing) {
    const overlay = ui.el('div', '', {
      style: 'position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center'
    });
    const modal = ui.el('div', 'card', { style: 'width:420px;padding:20px' });
    modal.appendChild(ui.el('div', 'card-title', { text: existing ? t('page.schedules.editSchedule') : t('page.schedules.newSchedule'), style: 'margin-bottom:14px' }));

    const isDefault = existing && ['history', 'ip_blacklist_refresh', 'blocklist_refresh', 'health_check', 'hunt_cycle'].includes(existing.id);

    // Name field
    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.schedules.taskName') }));
    const nameInput = ui.el('input', '', {
      style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box',
      value: existing ? existing.name : '',
    });
    modal.appendChild(nameInput);

    // ID field (only for new)
    if (!existing) {
      modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'ID' }));
      const idInput = ui.el('input', '', {
        id: 'sched-edit-id',
        style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box',
      });
      modal.appendChild(idInput);
    }

    // Task type select
    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.schedules.taskType') }));
    const typeSelect = ui.el('select', '', {
      style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;margin-bottom:10px;box-sizing:border-box',
    });
    if (existing) typeSelect.disabled = true;
    for (const [ttype, key] of Object.entries(TASK_TYPE_KEYS)) {
      const opt = ui.el('option', '', { value: ttype, text: t(key) });
      if (existing && existing.task_type === ttype) opt.selected = true;
      typeSelect.appendChild(opt);
    }
    modal.appendChild(typeSelect);

    // Interval field
    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.schedules.interval') }));
    const intervalRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-bottom:10px' });
    let currentSec = existing ? existing.interval_sec : 3600;
    let unit = 'seconds';
    let val = currentSec;
    if (currentSec >= 86400 && currentSec % 86400 === 0) { unit = 'days'; val = currentSec / 86400; }
    else if (currentSec >= 3600 && currentSec % 3600 === 0) { unit = 'hours'; val = currentSec / 3600; }
    else if (currentSec >= 60 && currentSec % 60 === 0) { unit = 'minutes'; val = currentSec / 60; }
    const numInput = ui.el('input', '', {
      type: 'number', value: val, min: 0,
      style: 'flex:1;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;box-sizing:border-box',
    });
    const unitSelect = ui.el('select', '', {
      style: 'width:120px;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;box-sizing:border-box',
    });
    const unitOpts = [
      { v: 'seconds', k: 'page.schedules.unitSeconds' },
      { v: 'minutes', k: 'page.schedules.unitMinutes' },
      { v: 'hours', k: 'page.schedules.unitHours' },
      { v: 'days', k: 'page.schedules.unitDays' },
    ];
    for (const u of unitOpts) {
      const opt = ui.el('option', '', { value: u.v, text: t(u.k) });
      if (u.v === unit) opt.selected = true;
      unitSelect.appendChild(opt);
    }
    intervalRow.appendChild(numInput);
    intervalRow.appendChild(unitSelect);
    modal.appendChild(intervalRow);

    // Enabled checkbox
    const enRow = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer;margin-bottom:14px;font-size:13px' });
    const enCb = ui.el('input', '', { type: 'checkbox' });
    if (existing ? existing.enabled : true) enCb.checked = true;
    enRow.appendChild(enCb);
    enRow.appendChild(ui.el('span', '', { text: t('page.schedules.enabled') }));
    modal.appendChild(enRow);

    // Buttons
    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;justify-content:flex-end' });
    const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
    cancelBtn.addEventListener('click', () => overlay.remove());
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('common.save') });
    saveBtn.addEventListener('click', () => {
      const num = parseInt(numInput.value, 10) || 0;
      const multipliers = { seconds: 1, minutes: 60, hours: 3600, days: 86400 };
      const interval_sec = num * multipliers[unitSelect.value];
      const data = {
        name: nameInput.value.trim() || 'Untitled',
        task_type: typeSelect.value,
        interval_sec,
        enabled: enCb.checked,
      };
      if (!existing) {
        const idEl = document.getElementById('sched-edit-id');
        data.id = (idEl ? idEl.value.trim() : '').replace(/[^a-zA-Z0-9_-]/g, '_');
        if (!data.id) { app.toast('ID required', 'error'); return; }
        api.scheduleCreate(data).then(() => {
          app.toast(t('page.schedules.scheduleCreated') || t('common.saved'));
          overlay.remove();
          load();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.scheduleUpdate(existing.id, data).then(() => {
          app.toast(t('common.saved'));
          overlay.remove();
          load();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    btnRow.appendChild(cancelBtn);
    btnRow.appendChild(saveBtn);
    modal.appendChild(btnRow);

    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  }

  // Global handlers for inline onclick
  window._schedToggle = (id) => {
    api.scheduleToggle(id).then(() => load()).catch(e => app.toast('Error: ' + e.message, 'error'));
  };
  window._schedRun = (id) => {
    api.scheduleRun(id).then(() => { app.toast(t('page.schedules.runStarted') || 'Started'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  };
  window._schedEdit = (id) => {
    const s = schedules.find(x => x.id === id);
    if (s) showEditor(s);
  };
  window._schedDelete = (id) => {
    if (!confirm(t('page.schedules.deleteConfirm'))) return;
    api.scheduleDelete(id).then(() => { app.toast(t('common.deleted') || 'Deleted'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  };

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      const data = await api.schedules();
      schedules = data.schedules || [];
      schedulerStatus = data.status || { running: false, paused: false, running_tasks: [] };
      renderSchedules();
      updateHeader();
    } catch (e) {
      // ignore
    } finally {
      _loading = false;
    }
  }

  build();
  load();
  loadLog();
  const pollId = setInterval(load, 3000);
  const logPollId = setInterval(loadLog, 2000);
  if (window._pageIntervals) window._pageIntervals.push(pollId, logPollId);
  else window._pageIntervals = [pollId, logPollId];
});
