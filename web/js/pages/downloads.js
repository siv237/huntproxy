router.register('downloads', (container) => {
  let counts = {};
  let backupGroups = [];

  async function loadCounts() {
    try { counts = await api.downloadCounts(); } catch (e) { counts = {}; }
    renderDownloads();
  }

  async function loadBackupGroups() {
    try {
      const data = await api.backupGroups();
      backupGroups = data.groups || [];
    } catch (e) { backupGroups = []; }
    renderBackup();
  }

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';
    container.style.overflow = 'hidden';

    const card = ui.card(t('page.downloads.downloads'));
    card.id = 'downloads-card';
    container.appendChild(card);

    const files = [
      { name: 'working.txt', desc: t('page.downloads.workingTxt'), icon: '📄' },
      { name: 'blacklist.txt', desc: t('page.downloads.blacklistTxt'), icon: '🚫' },
      { name: 'ip_blacklist.txt', desc: t('page.downloads.ipBlacklistTxt'), icon: '🛡️' },
      { name: 'ratings.json', desc: t('page.downloads.ratingsJson'), icon: '📊' },
      { name: 'config.yaml', desc: t('page.downloads.configYaml'), icon: '⚙️' },
    ];

    const grid = ui.el('div', 'grid grid-2');
    grid.id = 'downloads-grid';
    files.forEach(f => {
      const item = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;padding:16px;background:var(--surface-raised);border-radius:var(--radius-xs);border:1px solid var(--border)' });
      item.appendChild(ui.el('div', '', { style: 'font-size:24px', text: f.icon }));
      const info = ui.el('div', '', { style: 'flex:1;min-width:0' });
      info.appendChild(ui.el('div', '', { style: 'font-weight:600;font-size:13px;margin-bottom:2px', text: f.name }));
      info.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: f.desc }));
      item.appendChild(info);
      const countSpan = ui.el('span', 'badge', { text: '…', style: 'font-size:11px;min-width:32px;text-align:center' });
      countSpan.dataset.file = f.name;
      item.appendChild(countSpan);
      const dl = ui.el('a', 'btn btn-sm btn-primary', { text: t('page.downloads.download'), href: `/api/download/${f.name}`, download: f.name });
      item.appendChild(dl);
      grid.appendChild(item);
    });
    card.appendChild(grid);

    const importCard = ui.card(t('page.downloads.importProxies'));
    importCard.id = 'import-card';
    container.appendChild(importCard);

    const impWrap = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:8px' });
    impWrap.id = 'import-wrap';
    importCard.appendChild(impWrap);

    const impDesc = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: t('page.overview.importDesc') });
    impWrap.appendChild(impDesc);

    const favLabel = ui.el('label', '', { style: 'display:flex;align-items:center;gap:8px;font-size:12px;cursor:pointer' });
    const favCb = ui.el('input', '', { type: 'checkbox', checked: true });
    favLabel.appendChild(favCb);
    favLabel.appendChild(ui.el('span', '', { text: t('page.overview.importAsFavorite') }));
    impWrap.appendChild(favLabel);

    const impBtnRow = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center' });
    const impBtn = ui.el('button', 'btn btn-primary', { text: t('page.overview.chooseFile') });
    const impInput = ui.el('input', '', { type: 'file', accept: '.txt', style: 'display:none' });
    impBtnRow.appendChild(impBtn);
    impBtnRow.appendChild(impInput);
    impWrap.appendChild(impBtnRow);

    const impStatus = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);min-height:16px' });
    impWrap.appendChild(impStatus);

    impBtn.addEventListener('click', () => impInput.click());
    impInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      impBtn.disabled = true;
      impStatus.textContent = '...';
      try {
        const text = await file.text();
        const lines = text.split('\n');
        const result = await api.importProxies({ proxies: lines, favorite: favCb.checked });
        const msg = (result.added || 0) + (result.favorited != null ? ' ⭐' + result.favorited : '');
        impStatus.textContent = msg;
      } catch (err) {
        impStatus.textContent = String(err.message || err);
      } finally {
        impBtn.disabled = false;
        impInput.value = '';
        loadCounts();
      }
    });

    const backupCard = ui.card(t('page.downloads.backupRestore'));
    backupCard.id = 'backup-card';
    backupCard.style.display = 'flex';
    backupCard.style.flexDirection = 'column';
    backupCard.style.flex = '1';
    backupCard.style.minHeight = '0';
    container.appendChild(backupCard);

    const brWrap = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:8px;flex:1;min-height:0' });
    brWrap.id = 'backup-wrap';
    backupCard.appendChild(brWrap);
  }

  function renderDownloads() {
    document.querySelectorAll('[data-file]').forEach(el => {
      const n = counts[el.dataset.file];
      el.textContent = n !== undefined ? n : '…';
    });
  }

  function renderBackup() {
    const wrap = document.getElementById('backup-wrap');
    if (!wrap) return;
    wrap.innerHTML = '';

    const allBar = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:8px;font-size:11px;color:var(--text-secondary)' });
    const allCb = ui.el('input', '', { type: 'checkbox', id: 'bk-all', checked: true });
    allBar.appendChild(allCb);
    allBar.appendChild(ui.el('label', '', { text: t('page.downloads.selectAll'), for: 'bk-all', style: 'cursor:pointer' }));
    wrap.appendChild(allBar);

    const list = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:2px;flex:1;min-height:0;overflow-y:auto;margin-bottom:8px' });
    backupGroups.forEach(g => {
      const row = ui.el('label', '', { style: 'display:flex;align-items:center;gap:8px;padding:4px 6px;cursor:pointer;font-size:12px' });
      const cb = ui.el('input', 'bk-grp', { type: 'checkbox', value: g.key, checked: true });
      row.appendChild(cb);
      row.appendChild(ui.el('span', '', { text: g.label, style: 'flex:1;min-width:0' }));
      row.appendChild(ui.el('span', 'badge', { text: String(g.total), style: 'font-size:10px' }));
      list.appendChild(row);
    });
    wrap.appendChild(list);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center' });
    const bkBtn = ui.el('button', 'btn btn-primary', { text: t('page.downloads.createBackup') });
    const fileInput = ui.el('input', '', { type: 'file', accept: '.json', style: 'display:none' });
    const rsBtn = ui.el('button', 'btn btn-secondary', { text: t('page.downloads.restoreBackup') });
    btnRow.appendChild(bkBtn);
    btnRow.appendChild(rsBtn);
    btnRow.appendChild(fileInput);
    wrap.appendChild(btnRow);

    const statusEl = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);min-height:16px;margin-top:6px' });
    wrap.appendChild(statusEl);

    allCb.addEventListener('change', () => {
      document.querySelectorAll('.bk-grp').forEach(c => { c.checked = allCb.checked; });
    });

    bkBtn.addEventListener('click', async () => {
      const selected = [...document.querySelectorAll('.bk-grp:checked')].map(c => c.value);
      if (!selected.length) { statusEl.textContent = t('page.downloads.selectAtLeastOne'); return; }
      statusEl.textContent = t('page.downloads.creating');
      bkBtn.disabled = true;
      try {
        const blob = await api.createBackup(selected);
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `huntproxy_backup_${new Date().toISOString().slice(0,19).replace(/[:T]/g,'')}.json`;
        a.click();
        URL.revokeObjectURL(url);
        statusEl.textContent = t('page.downloads.backupCreated');
      } catch (e) {
        statusEl.textContent = String(e.message || e);
      } finally {
        bkBtn.disabled = false;
      }
    });

    rsBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const selected = [...document.querySelectorAll('.bk-grp:checked')].map(c => c.value);
      if (!selected.length) { statusEl.textContent = t('page.downloads.selectAtLeastOne'); return; }
      statusEl.textContent = t('page.downloads.restoring');
      rsBtn.disabled = true;
      try {
        const text = await file.text();
        const result = await api.restoreBackup(selected, text);
        if (result.ok) {
          const counts = Object.entries(result.restored).map(([k,v]) => `${k}: ${v}`).join(', ');
          statusEl.textContent = t('page.downloads.restoreDone') + ' (' + counts + ')';
          loadBackupGroups();
        } else {
          statusEl.textContent = result.error || t('page.downloads.restoreFailed');
        }
      } catch (e) {
        statusEl.textContent = String(e.message || e);
      } finally {
        rsBtn.disabled = false;
        fileInput.value = '';
      }
    });
  }

  build();
  loadCounts();
  loadBackupGroups();
});
