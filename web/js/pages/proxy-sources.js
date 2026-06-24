router.register('proxy-sources', (container) => {
  let sources = [];
  let editingId = null;
  let _loading = false;
  let fetchProgress = {};
  let progressPoller = null;

  function fmtBytes(n) {
    if (!n) return '0B';
    if (n >= 1048576) return (n / 1048576).toFixed(1) + 'MB';
    if (n >= 1024) return (n / 1024).toFixed(0) + 'KB';
    return n + 'B';
  }

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
  }

  function buildSourcesCard() {
    const card = ui.card(t('page.proxySources.proxySources'));
    card.id = 'card-proxy-sources';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.proxySources.newSource'), style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });

    const refreshBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.proxySources.refresh'), style: 'margin-bottom:8px;margin-left:6px' });
    function startFetch() {
      refreshBtn.disabled = true;
      refreshBtn.textContent = t('page.proxySources.fetching');
      fetchProgress = {};
      progressPoller = setInterval(() => {
        api.proxySourceProgress().then(r => {
          if (r && r.progress) { fetchProgress = r.progress; updateSourcesCard(sources); }
        }).catch(() => {});
      }, 2000);
      api.proxySourcesFetch().then(r => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.proxySources.refresh');
        fetchProgress = {};
        if (r.ok) {
          const parts = [];
          if (r.sources) {
            r.sources.forEach(s => {
              const icon = s.status === 'ok' ? '✓' : '✗';
              const color = s.status === 'ok' ? 'var(--success)' : 'var(--danger)';
              parts.push(`<span style="color:${color}">${icon} ${ui.escHtml(s.name)}: ${s.count}</span>`);
            });
          }
          const total = r.total_addresses || 0;
          const statusHtml = parts.length
            ? parts.join(' &nbsp;·&nbsp; ') + `<br><span style="color:var(--text-muted)">${t('page.proxySources.uniqueAddresses', {count: total})}</span>`
            : `<span style="color:var(--text-muted)">${t('page.proxySources.noEnabledSources')}</span>`;
          const statusEl = document.getElementById('fetch-status');
          if (statusEl) {
            statusEl.innerHTML = statusHtml;
            statusEl.style.display = '';
            clearTimeout(statusEl._hideTimer);
            statusEl._hideTimer = setTimeout(() => { statusEl.style.display = 'none'; }, 8000);
          }
          app.toast(`Fetched ${total} addresses from ${r.sources ? r.sources.length : 0} sources`);
        } else {
          app.toast('Fetch error: ' + (r.error || 'unknown'), 'error');
        }
        load();
      }).catch(e => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.proxySources.refresh');
        fetchProgress = {};
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    }
    refreshBtn.addEventListener('click', startFetch);

    card.appendChild(addBtn);
    card.appendChild(refreshBtn);

    const fetchStatus = ui.el('div', '', { id: 'fetch-status', style: 'display:none;padding:6px 8px;margin-bottom:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;line-height:1.5' });
    card.appendChild(fetchStatus);

    const tblWrap = ui.el('div', '', { id: 'proxy-sources-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.noSources')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.proxySources.sourceEditor'));
    card.id = 'card-source-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'source-editor-body' });
    body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.selectToEdit')}</div>`;
    card.appendChild(body);

    return card;
  }

  function showEditor(src) {
    const body = document.getElementById('source-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = src ? src.id : null;

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.nameLabel') }));
    const nameInput = ui.el('input', '', { id: 'src-name', type: 'text', value: src ? src.name : '', placeholder: 'e.g. monosans/socks5', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.idLabel') }));
    const idInput = ui.el('input', '', { id: 'src-id', type: 'text', value: src ? src.id : '', placeholder: 'auto-generated', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);' + (src ? 'opacity:0.6' : '') });
    if (src) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const urlRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    urlRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.urlLabel') }));
    const urlInput = ui.el('input', '', { id: 'src-url', type: 'text', value: src ? src.url : '', placeholder: 'https://example.com/proxies.txt', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    urlRow.appendChild(urlInput);
    body.appendChild(urlRow);

    const protoRow = ui.el('div', '', { style: 'margin-bottom:12px' });
    protoRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.proxySources.protocolLabel') }));
    const protoSelect = ui.el('select', '', { id: 'src-protocol', style: 'width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    ['mixed', 'http', 'https', 'socks4', 'socks5'].forEach(p => {
      const opt = ui.el('option', '', { value: p, text: p.toUpperCase() });
      if (src && src.protocol === p) opt.selected = true;
      if (!src && p === 'mixed') opt.selected = true;
      protoSelect.appendChild(opt);
    });
    protoRow.appendChild(protoSelect);
    body.appendChild(protoRow);

    if (src && src.last_fetched_at) {
      const statsHtml = `
        <div style="padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;margin-bottom:12px">
          <div style="margin-bottom:4px;color:var(--text-secondary)">${t('page.proxySources.sourceStats')}</div>
          <div>${t('page.proxySources.lastFetched')}: <b>${ui.ago(src.last_fetched_at)}</b></div>
          <div>${t('page.proxySources.lastStatus')}: <b style="color:${src.last_fetch_status === 'ok' ? 'var(--success)' : 'var(--danger)'}">${src.last_fetch_status || '—'}</b></div>
          ${src.last_fetch_error ? `<div>${t('common.error', {message: ui.escHtml(src.last_fetch_error)})}</div>` : ''}
          <div style="margin-top:6px">
            <span style="color:var(--success)">Last: ${src.last_working} ${t('page.proxySources.working')}</span> /
            <span style="color:var(--danger)">${src.last_dead} ${t('page.proxySources.dead')}</span>
            (${t('page.proxySources.fetched')} ${src.last_fetch_count})
          </div>
          <div style="margin-top:2px">
            <span style="color:var(--text-muted)">${t('page.proxySources.currentAddresses')}: ${src.current_entries ?? src.last_fetch_count ?? '0'}</span>
          </div>
          <div style="margin-top:2px">
            <span style="color:var(--text-muted)">${t('page.proxySources.cumulative')}: ${src.total_working} ${t('page.proxySources.working')} / ${src.total_dead} ${t('page.proxySources.dead')} / ${src.total_fetched} ${t('page.proxySources.fetched')}</span>
          </div>
        </div>`;
      body.appendChild(ui.el('div', '', { html: statsHtml }));
    }

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: src ? t('page.proxySources.saveChanges') : t('page.proxySources.addSource') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('src-name').value.trim();
      let sourceId = document.getElementById('src-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!sourceId) sourceId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const url = document.getElementById('src-url').value.trim();
      const protocol = document.getElementById('src-protocol').value;

      if (!name) { app.toast(t('common.nameRequired'), 'error'); return; }
      if (!url) { app.toast(t('common.urlRequired'), 'error'); return; }

      const data = { id: sourceId, name, url, protocol };

      if (editingId) {
        api.proxySourceUpdate(editingId, data).then(() => {
          app.toast(t('page.proxySources.sourceUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
      } else {
        api.proxySourceCreate(data).then(() => {
          app.toast(t('page.proxySources.sourceAdded'));
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
    const body = document.getElementById('source-editor-body');
    if (body) body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.selectToEdit')}</div>`;
  }

  function qualityPct(working, dead) {
    const total = working + dead;
    if (!total) return 0;
    return Math.round(working / total * 100);
  }

  function qualityBadge(working, dead) {
    const pct = qualityPct(working, dead);
    if (pct >= 50) return `<span style="color:var(--success);font-weight:600">${pct}%</span>`;
    if (pct >= 20) return `<span style="color:var(--warning);font-weight:600">${pct}%</span>`;
    if (pct > 0) return `<span style="color:var(--danger);font-weight:600">${pct}%</span>`;
    return `<span style="color:var(--text-muted)">—</span>`;
  }

  function protocolBadge(protocol) {
    const colors = { http: 'var(--info)', https: '#8b5cf6', socks4: 'var(--accent)', socks5: 'var(--success)', mixed: 'var(--text-muted)' };
    const color = colors[protocol] || colors.mixed;
    return `<span style="color:${color};font-size:11px;font-weight:600">${(protocol || 'mixed').toUpperCase()}</span>`;
  }

  function statusBadge(src) {
    const p = fetchProgress[src.id];
    if (p) {
      if (p.status === 'downloading') return `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
      if (p.status === 'connecting') return `<span style="color:var(--info);font-size:11px">…</span>`;
      if (p.status === 'done') return `<span style="color:var(--success);font-size:11px">✓ ${p.count || 0}</span>`;
      if (p.status === 'error') return `<span style="color:var(--danger);font-size:11px">ERR</span>`;
    }
    if (!src.last_fetched_at) return `<span style="color:var(--text-muted);font-size:11px">${t('page.proxySources.never')}</span>`;
    if (src.last_fetch_status === 'ok') return `<span style="color:var(--success);font-size:11px">OK</span>`;
    return `<span style="color:var(--danger);font-size:11px" title="${ui.escHtml(src.last_fetch_error || '')}">ERR</span>`;
  }

  function updateSourcesCard(list) {
    const wrap = document.getElementById('proxy-sources-tbl');
    if (!wrap) return;
    sources = list || [];

    if (!list || !list.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.proxySources.noSources')}</div>`;
      return;
    }

    const headers = [
      { label: 'Source', width: '140px' },
      { label: 'Proto', width: '50px', align: 'center' },
      { label: 'Status', width: '40px', align: 'center' },
      { label: 'Last', width: '60px' },
      { label: 'Quality', width: '50px', align: 'center' },
      { label: 'Addresses', width: '60px', align: 'center' },
      { label: 'Working', width: '50px', align: 'center' },
      { label: 'Dead', width: '50px', align: 'center' },
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
      linkBtn.title = t('page.proxySources.openSourceUrl');

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

        const p = fetchProgress[s.id];
        let addrCell;
        if (p) {
          if (p.status === 'downloading') addrCell = `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
          else if (p.status === 'done' && p.count != null) addrCell = `<span style="color:var(--success)">${p.count}</span>`;
          else addrCell = `<span style="color:var(--text-secondary)">${s.current_entries ?? s.last_fetch_count ?? '0'}</span>`;
        } else {
          addrCell = `<span style="color:var(--text-secondary)">${s.current_entries ?? s.last_fetch_count ?? '0'}</span>`;
        }

        return [
          nameCell.outerHTML,
          protocolBadge(s.protocol),
          statusBadge(s),
          ui.ago(s.last_fetched_at),
          qualityBadge(s.last_working, s.last_dead),
          addrCell,
        `<span style="color:var(--success)">${s.last_working}</span>`,
        `<span style="color:var(--danger)">${s.last_dead}</span>`,
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

  function editSource(id) {
    api.proxySourceGet(id).then(src => {
      if (src) showEditor(src);
      else app.toast(t('page.proxySources.sourceNotFound'), 'error');
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function deleteSource(id) {
    if (!confirm(t('common.confirmDelete', {item: 'proxy source'}))) return;
    api.proxySourceDelete(id).then(() => {
      app.toast(t('page.proxySources.sourceDeleted'));
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  function toggleSource(id) {
    api.proxySourceToggle(id).then(() => {
      load();
    }).catch(e => app.toast(t('common.error', {message: e.message}), 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    if (progressPoller) return;
    _loading = true;
    try {
      let result = [];
      try { result = await api.proxySources(); } catch (e) { console.error('proxySources', e); }
      const list = result.sources || result || [];
      sources = list;
      updateSourcesCard(list);
    } catch (e) {
      console.error('proxy-sources load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
