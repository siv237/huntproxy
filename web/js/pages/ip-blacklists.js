router.register('ip-blacklists', (container) => {
  let sources = [];
  let editingId = null;
  let _loading = false;

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
    const row = ui.el('div', 'grid grid-2 row-stretch');
    row.appendChild(buildSourcesCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);

    container.appendChild(buildMatchesCard());
  }

  function buildSourcesCard() {
    const card = ui.card(t('page.ipBlacklists.ipBlacklists'));
    card.id = 'card-ip-blacklists';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.ipBlacklists.newSource'), style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });

    const refreshBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.ipBlacklists.refresh'), style: 'margin-bottom:8px;margin-left:6px' });
    refreshBtn.addEventListener('click', () => {
      refreshBtn.disabled = true;
      refreshBtn.textContent = t('page.ipBlacklists.fetching');
      api.ipBlacklistFetch().then(r => {
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.ipBlacklists.refresh');
        if (r.ok) {
          app.toast(`Fetched ${r.total_entries || 0} IP blacklist entries`);
        } else {
          app.toast('Fetch error: ' + (r.error || 'unknown'), 'error');
        }
        load();
      }).catch(e => {
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.ipBlacklists.refresh');
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });

    card.appendChild(addBtn);
    card.appendChild(refreshBtn);

    const statusEl = ui.el('div', '', { id: 'ip-bl-fetch-status', style: 'display:none;padding:6px 8px;margin-bottom:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;line-height:1.5' });
    card.appendChild(statusEl);

    const tblWrap = ui.el('div', '', { id: 'ip-blacklists-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noSources')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.ipBlacklists.sourceEditor'));
    card.id = 'card-ip-bl-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'ip-bl-editor-body' });
    body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.selectToEdit')}</div>`;
    card.appendChild(body);

    return card;
  }

  function buildMatchesCard() {
    const card = ui.card(t('page.ipBlacklists.matches'));
    card.id = 'card-ip-bl-matches';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';

    const info = ui.el('div', '', { id: 'ip-bl-matches-info', style: 'font-size:12px;color:var(--text-secondary);margin-bottom:8px' });
    card.appendChild(info);

    const tblWrap = ui.el('div', '', { id: 'ip-bl-matches-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noMatches')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function showEditor(src) {
    const body = document.getElementById('ip-bl-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = src ? src.id : null;

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.ipBlacklists.nameLabel') }));
    const nameInput = ui.el('input', '', { id: 'ip-bl-name', type: 'text', value: src ? src.name : '', placeholder: 'e.g. Tor Exit Nodes', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.ipBlacklists.idLabel') }));
    const idInput = ui.el('input', '', { id: 'ip-bl-id', type: 'text', value: src ? src.id : '', placeholder: 'auto-generated', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);' + (src ? 'opacity:0.6' : '') });
    if (src) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const urlRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    urlRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.ipBlacklists.urlLabel') }));
    const urlInput = ui.el('input', '', { id: 'ip-bl-url', type: 'text', value: src ? src.url : '', placeholder: 'https://example.com/ips.txt', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    urlRow.appendChild(urlInput);
    body.appendChild(urlRow);

    if (src && src.last_fetched_at) {
      const statsHtml = `
        <div style="padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;margin-bottom:12px">
          <div style="margin-bottom:4px;color:var(--text-secondary)">${t('page.ipBlacklists.sourceStats')}</div>
          <div>${t('page.ipBlacklists.lastFetched')}: <b>${ui.ago(src.last_fetched_at)}</b></div>
          <div>${t('page.ipBlacklists.lastStatus')}: <b style="color:${src.last_fetch_status === 'ok' ? 'var(--success)' : 'var(--danger)'}">${src.last_fetch_status || '—'}</b></div>
          ${src.last_fetch_error ? `<div>${t('common.error', {message: ui.escHtml(src.last_fetch_error)})}</div>` : ''}
          <div style="margin-top:6px">
            <span>${t('page.ipBlacklists.fetched')}: ${src.last_fetch_count}</span>
          </div>
          <div style="margin-top:2px">
            <span style="color:var(--text-muted)">${t('page.ipBlacklists.cumulative')}: ${src.total_fetched}</span>
          </div>
        </div>`;
      body.appendChild(ui.el('div', '', { html: statsHtml }));
    }

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: src ? t('page.ipBlacklists.saveChanges') : t('page.ipBlacklists.addSource') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('ip-bl-name').value.trim();
      let sourceId = document.getElementById('ip-bl-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!sourceId) sourceId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const url = document.getElementById('ip-bl-url').value.trim();

      if (!name) { app.toast(t('common.nameRequired'), 'error'); return; }
      if (!url) { app.toast(t('common.urlRequired'), 'error'); return; }

      const data = { id: sourceId, name, url };

      if (editingId) {
        api.ipBlacklistUpdate(editingId, data).then(() => {
          app.toast(t('page.ipBlacklists.sourceUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
      } else {
        api.ipBlacklistCreate(data).then(() => {
          app.toast(t('page.ipBlacklists.sourceAdded'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (src) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
      cancelBtn.addEventListener('click', () => {
        editingId = null;
        resetEditor();
      });
      btnRow.appendChild(cancelBtn);
    }

    body.appendChild(btnRow);
  }

  function resetEditor() {
    const body = document.getElementById('ip-bl-editor-body');
    if (body) body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.selectToEdit')}</div>`;
  }

  function statusBadge(src) {
    if (!src.last_fetched_at) return `<span style="color:var(--text-muted);font-size:11px">${t('page.ipBlacklists.never')}</span>`;
    if (src.last_fetch_status === 'ok') return `<span style="color:var(--success);font-size:11px">OK</span>`;
    return `<span style="color:var(--danger);font-size:11px" title="${ui.escHtml(src.last_fetch_error || '')}">ERR</span>`;
  }

  function updateSourcesCard(list) {
    const wrap = document.getElementById('ip-blacklists-tbl');
    if (!wrap) return;
    sources = list || [];

    if (!list || !list.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noSources')}</div>`;
      return;
    }

    const headers = [
      { label: 'Source', width: '160px' },
      { label: 'Status', width: '40px', align: 'center' },
      { label: 'Last', width: '60px' },
      { label: 'Entries', width: '60px', align: 'center' },
      { label: 'On/Off', width: '40px', align: 'center' },
      { label: 'Actions', width: '80px', align: 'center' },
    ];

    const rows = list.map(s => {
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer;font-size:12px';
      nameSpan.textContent = s.name || s.id;
      nameSpan.dataset.sourceId = s.id;
      nameSpan.dataset.action = 'edit';

      const linkBtn = document.createElement('a');
      linkBtn.href = s.url || '#';
      linkBtn.target = '_blank';
      linkBtn.rel = 'noopener';
      linkBtn.style.cssText = 'display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;font-size:10px;color:var(--text-muted);text-decoration:none;border:1px solid var(--border);border-radius:3px;margin-left:4px;vertical-align:middle;flex-shrink:0';
      linkBtn.textContent = '↗';
      linkBtn.title = t('page.ipBlacklists.openSourceUrl');

      const nameCell = document.createElement('span');
      nameCell.style.cssText = 'display:inline-flex;align-items:center;gap:0';
      nameCell.appendChild(nameSpan);
      nameCell.appendChild(linkBtn);

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = t('common.edit');
      editBtn.dataset.sourceId = s.id;
      editBtn.dataset.action = 'edit';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = t('common.delete');
      delBtn.dataset.sourceId = s.id;
      delBtn.dataset.action = 'delete';

      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'btn btn-xs ' + (s.enabled ? 'btn-primary' : 'btn-ghost');
      toggleBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      toggleBtn.textContent = s.enabled ? t('common.on') : t('common.off');
      toggleBtn.dataset.sourceId = s.id;
      toggleBtn.dataset.action = 'toggle';

      return [
        nameCell.outerHTML,
        statusBadge(s),
        ui.ago(s.last_fetched_at),
        s.current_entries ?? s.last_fetch_count ?? '0',
        toggleBtn.outerHTML,
        editBtn.outerHTML + delBtn.outerHTML,
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        const sourceId = el.dataset.sourceId;
        const action = el.dataset.action;
        if (action === 'edit') editSource(sourceId);
        else if (action === 'delete') deleteSource(sourceId);
        else if (action === 'toggle') toggleSource(sourceId);
      });
    });
  }

  function renderMatches(matches) {
    const info = document.getElementById('ip-bl-matches-info');
    if (info) info.textContent = t('page.ipBlacklists.matchesInfo', {count: matches.length});

    const wrap = document.getElementById('ip-bl-matches-tbl');
    if (!wrap) return;

    if (!matches || !matches.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.ipBlacklists.noMatches')}</div>`;
      return;
    }

    const headers = [
      { label: 'Proxy', width: '160px' },
      { label: 'Egress IP', width: '120px' },
      { label: 'Country', width: '100px' },
      { label: 'Reason', width: '200px' },
      { label: 'Score', width: '60px', align: 'right' },
    ];

    const rows = matches.map(m => [
      `<span class="addr proxy-address-link" data-card-addr="${ui.escHtml(m.address)}" style="cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${m.address}</span>`,
      ui.escHtml(m.egress_ip || '—'),
      `${ui.flag(m.country_code)} ${ui.escHtml(m.country || '—')}`,
      `<span style="color:var(--danger)">${ui.escHtml(m.reason || '—')}</span>`,
      Math.round(m.score || 0),
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

  function editSource(id) {
    api.ipBlacklistGet(id).then(src => {
      if (src) showEditor(src);
      else app.toast(t('page.ipBlacklists.sourceNotFound'), 'error');
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function deleteSource(id) {
    if (!confirm(t('common.confirmDelete', {item: 'IP blacklist source'}))) return;
    api.ipBlacklistDelete(id).then(() => {
      app.toast(t('page.ipBlacklists.sourceDeleted'));
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function toggleSource(id) {
    api.ipBlacklistToggle(id).then(() => {
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      let result = [];
      try { result = await api.ipBlacklistSources(); } catch (e) { console.error('ipBlacklistSources', e); }
      const list = result.sources || result || [];
      sources = list;
      updateSourcesCard(list);

      let matches = [];
      try { matches = (await api.ipBlacklistMatches()).matches || []; } catch (e) { console.error('ipBlacklistMatches', e); }
      renderMatches(matches);
    } catch (e) {
      console.error('ip-blacklists load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
