router.register('actions', (container) => {
  let entries = [];
  let filter = '';

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const bar = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center;flex-shrink:0;flex-wrap:wrap' });
    const search = ui.el('input', '', {
      type: 'text',
      placeholder: t('page.actions.filterPlaceholder') || 'Filter actions...',
      value: filter,
      style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:220px'
    });
    search.addEventListener('input', (e) => { filter = e.target.value.toLowerCase(); render(); });
    bar.appendChild(search);

    bar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const refreshBtn = ui.el('button', 'btn btn-secondary', { text: t('page.actions.refresh') || 'Refresh' });
    refreshBtn.addEventListener('click', load);
    bar.appendChild(refreshBtn);

    const liveBtn = ui.el('button', 'btn btn-secondary', { text: t('page.actions.live') || 'Live' });
    let liveInterval = null;
    liveBtn.addEventListener('click', () => {
      if (liveInterval) {
        clearInterval(liveInterval);
        liveInterval = null;
        liveBtn.textContent = t('page.actions.live') || 'Live';
        liveBtn.className = 'btn btn-secondary';
      } else {
        load();
        liveInterval = setInterval(load, 3000);
        liveBtn.textContent = t('page.actions.stopLive') || 'Stop live';
        liveBtn.className = 'btn btn-primary';
      }
    });
    bar.appendChild(liveBtn);

    container.appendChild(bar);

    const card = ui.card(t('page.actions.title') || 'Action Log');
    card.id = 'actions-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    container.appendChild(card);
  }

  build();

  async function load() {
    try {
      entries = await api.actions(200);
      render();
    } catch (e) {
      console.error('actions load', e);
    }
  }

  function render() {
    const card = document.getElementById('actions-card');
    if (!card) return;
    card.innerHTML = '';

    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.actions.title') || 'Action Log' }));
    header.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: `${entries.length}` }));
    card.appendChild(header);

    let rows = entries;
    if (filter) {
      rows = rows.filter(e =>
        (e.action + ' ' + e.detail).toLowerCase().includes(filter));
    }

    if (!rows.length) {
      card.appendChild(ui.emptyState(t('page.actions.empty') || 'No actions recorded yet.'));
      return;
    }

    const wrap = ui.el('div', '', { style: 'flex:1;min-height:0;overflow-y:auto' });
    rows.forEach(e => {
      const snap = e.snapshot || {};
      const total = snap.checking_total || 0;
      const checked = snap.checked || 0;
      const desync = total > 0 && checked > total;
      const row = ui.el('div', '', {
        style: 'padding:6px 8px;border-bottom:1px solid var(--border-subtle);font-size:12px;display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap' +
          (desync ? ';background:rgba(207,34,46,0.08)' : '')
      });
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);font-family:ui-monospace,monospace;white-space:nowrap', text: ui.fmtTime(e.ts) }));
      row.appendChild(ui.el('span', '', { style: 'color:var(--accent);font-weight:600;white-space:nowrap', text: e.action }));
      if (e.detail) row.appendChild(ui.el('span', '', { style: 'color:var(--text-primary)', text: e.detail }));
      const meta = ui.el('span', '', {
        style: 'color:var(--text-muted);font-family:ui-monospace,monospace;white-space:nowrap',
        text: `phase=${snap.phase || '—'} paused=${snap.paused ? 1 : 0} ${checked}/${total} w=${snap.working || 0} f=${snap.failed || 0}` +
          (desync ? ` ⚠ ${Math.round(100 * checked / total)}%` : '')
      });
      if (desync) meta.style.color = 'var(--danger)';
      row.appendChild(meta);
      wrap.appendChild(row);
    });
    card.appendChild(wrap);
  }

  load();
});
