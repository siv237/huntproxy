router.register('blocklists', (container) => {
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
    const card = ui.card(t('page.blocklists.sources'));
    card.id = 'card-blocklists';
    card.style.overflow = 'hidden';

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px;flex-wrap:wrap' });

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.blocklists.newSource') });
    addBtn.addEventListener('click', () => { editingId = null; showEditor(null); });
    btnRow.appendChild(addBtn);

    const refreshBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.blocklists.refresh') });
    function startFetch() {
      refreshBtn.disabled = true;
      refreshBtn.textContent = t('page.blocklists.fetching');
      fetchProgress = {};
      progressPoller = setInterval(() => {
        api.blocklistProgress().then(r => {
          if (r && r.progress) {
            fetchProgress = r.progress;
            updateSourcesCard(sources);
          }
        }).catch(() => {});
      }, 2000);
      api.blocklistFetch().then(r => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.blocklists.refresh');
        fetchProgress = {};
        if (r.ok) {
          app.toast(t('page.blocklists.fetchDone', { count: r.total_entries || 0 }));
        } else {
          app.toast(t('common.error', { message: r.error || 'unknown' }), 'error');
        }
        load();
      }).catch(e => {
        clearInterval(progressPoller);
        progressPoller = null;
        refreshBtn.disabled = false;
        refreshBtn.textContent = t('page.blocklists.refresh');
        fetchProgress = {};
        app.toast(t('common.error', { message: e.message }), 'error');
      });
    }
    refreshBtn.addEventListener('click', startFetch);
    btnRow.appendChild(refreshBtn);

    card.appendChild(btnRow);

    const tblWrap = ui.el('div', '', { id: 'blocklists-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.noSources')}</div>`;
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.blocklists.editor'));
    card.id = 'card-bl-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'bl-editor-body' });
    body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.selectToEdit')}</div>`;
    card.appendChild(body);

    return card;
  }

  function dirLabel(d) {
    if (d === 'outside') return t('page.blocklists.directionOutside');
    return t('page.blocklists.directionInside');
  }

  function typeLabel(ty) {
    if (ty === 'domain') return t('page.blocklists.typeDomain');
    return t('page.blocklists.typeIp');
  }

  function showEditor(src) {
    const body = document.getElementById('bl-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = src ? src.id : null;

    const mkField = (id, label, value, placeholder, opts = {}) => {
      const row = ui.el('div', '', { style: 'margin-bottom:10px' });
      row.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: label }));
      const input = ui.el('input', '', { id, type: 'text', value, placeholder, style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' + (opts.disabled ? ';opacity:0.6' : '') });
      if (opts.disabled) input.disabled = true;
      row.appendChild(input);
      return row;
    };

    const mkSelect = (id, label, options, selected) => {
      const row = ui.el('div', '', { style: 'margin-bottom:10px' });
      row.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: label }));
      const sel = ui.el('select', '', { id, style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
      options.forEach(o => {
        const opt = ui.el('option', '', { value: o.value, text: o.label });
        if (o.value === selected) opt.selected = true;
        sel.appendChild(opt);
      });
      row.appendChild(sel);
      return row;
    };

    body.appendChild(mkField('bl-name', t('page.blocklists.nameLabel'), src ? src.name : '', 'e.g. Russia RKN IPs'));
    body.appendChild(mkField('bl-id', t('page.blocklists.idLabel'), src ? src.id : '', 'auto-generated', { disabled: !!src }));

    const nameInput = document.getElementById('bl-name');
    const idInput = document.getElementById('bl-id');
    if (!src) {
      nameInput.addEventListener('input', () => {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      });
    }

    body.appendChild(mkField('bl-country', t('page.blocklists.countryLabel'), src ? src.country : '', 'RU, US, CN...'));
    body.appendChild(mkSelect('bl-direction', t('page.blocklists.directionLabel'), [
      { value: 'inside', label: t('page.blocklists.directionInside') },
      { value: 'outside', label: t('page.blocklists.directionOutside') },
    ], src ? src.direction : 'inside'));
    body.appendChild(mkSelect('bl-list-type', t('page.blocklists.typeLabel'), [
      { value: 'ip', label: t('page.blocklists.typeIp') },
      { value: 'domain', label: t('page.blocklists.typeDomain') },
    ], src ? src.list_type : 'ip'));
    body.appendChild(mkField('bl-url', t('page.blocklists.urlLabel'), src ? src.url : '', 'https://example.com/list.txt'));
    body.appendChild(mkField('bl-proxy', t('page.blocklists.proxyLabel'), src ? (src.download_proxy || '') : '', 'http://127.0.0.1:17277 or empty'));

    if (src && src.last_fetched_at) {
      const stats = ui.el('div', '', { style: 'padding:8px;background:var(--surface-raised);border-radius:var(--radius-xs);font-size:11px;margin-bottom:12px' });
      stats.innerHTML = `
        <div style="margin-bottom:4px;color:var(--text-secondary)">${t('page.blocklists.sourceStats')}</div>
        <div>${t('page.blocklists.lastFetched')}: <b>${ui.ago(src.last_fetched_at)}</b></div>
        <div>${t('page.blocklists.lastStatus')}: <b style="color:${src.last_fetch_status === 'ok' ? 'var(--success)' : 'var(--danger)'}">${src.last_fetch_status || '—'}</b></div>
        ${src.last_fetch_error ? `<div style="color:var(--danger)">${ui.escHtml(src.last_fetch_error)}</div>` : ''}
        <div style="margin-top:6px">${t('page.blocklists.fetched')}: ${src.last_fetch_count}</div>
        <div style="margin-top:2px;color:var(--text-muted)">${t('page.blocklists.cumulative')}: ${src.total_fetched}</div>`;
      body.appendChild(stats);
    }

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: src ? t('page.blocklists.saveChanges') : t('page.blocklists.addSource') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('bl-name').value.trim();
      let sourceId = document.getElementById('bl-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!sourceId) sourceId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const url = document.getElementById('bl-url').value.trim();
      if (!name) { app.toast(t('common.nameRequired'), 'error'); return; }
      if (!url) { app.toast(t('common.urlRequired'), 'error'); return; }
      const data = {
        id: sourceId, name, url,
        country: document.getElementById('bl-country').value.trim().toUpperCase(),
        direction: document.getElementById('bl-direction').value,
        list_type: document.getElementById('bl-list-type').value,
        download_proxy: document.getElementById('bl-proxy').value.trim(),
      };
      if (editingId) {
        api.blocklistUpdate(editingId, data).then(() => {
          app.toast(t('page.blocklists.sourceUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      } else {
        api.blocklistCreate(data).then(() => {
          app.toast(t('page.blocklists.sourceAdded'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (src) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
      cancelBtn.addEventListener('click', () => { editingId = null; resetEditor(); });
      btnRow.appendChild(cancelBtn);
    }
    body.appendChild(btnRow);
  }

  function resetEditor() {
    const body = document.getElementById('bl-editor-body');
    if (body) body.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.selectToEdit')}</div>`;
  }

  function statusBadge(s) {
    const p = fetchProgress[s.id];
    if (p) {
      if (p.status === 'downloading') return `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
      if (p.status === 'connecting') return `<span style="color:var(--info);font-size:11px">…</span>`;
      if (p.status === 'parsing') return `<span style="color:var(--warning);font-size:11px">⏳</span>`;
      if (p.status === 'done') return `<span style="color:var(--success);font-size:11px">✓ ${p.count || 0}</span>`;
      if (p.status === 'error') return `<span style="color:var(--danger);font-size:11px">ERR</span>`;
    }
    if (!s.last_fetched_at) return `<span style="color:var(--text-muted);font-size:11px">${t('page.blocklists.never')}</span>`;
    if (s.last_fetch_status === 'ok') return `<span style="color:var(--success);font-size:11px">OK</span>`;
    return `<span style="color:var(--danger);font-size:11px" title="${ui.escHtml(s.last_fetch_error || '')}">ERR</span>`;
  }

  function countryFlag(cc) {
    if (!cc) return '';
    return ui.flag(cc) + ' ';
  }

  function updateSourcesCard(list) {
    const wrap = document.getElementById('blocklists-tbl');
    if (!wrap) return;
    sources = list || [];

    if (!list || !list.length) {
      wrap.innerHTML = `<div class="empty" style="padding:8px;font-size:11px">${t('page.blocklists.noSources')}</div>`;
      return;
    }

    const grouped = {};
    list.forEach(s => {
      const key = `${s.country || '??'}|${s.direction || 'inside'}`;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(s);
    });

    wrap.innerHTML = '';
    Object.keys(grouped).sort().forEach(key => {
      const [country, direction] = key.split('|');
      const items = grouped[key];

      const grp = ui.el('div', '', { style: 'margin-bottom:12px' });
      const hdr = ui.el('div', '', { style: 'font-size:11px;font-weight:600;color:var(--text-secondary);margin-bottom:4px;padding:2px 0;text-transform:uppercase;letter-spacing:0.5px' });
      hdr.textContent = `${countryFlag(country)}${country || '??'} — ${dirLabel(direction)}`;
      grp.appendChild(hdr);

      const headers = [
        { label: t('page.blocklists.colSource'), width: '160px' },
        { label: t('page.blocklists.colType'), width: '60px', align: 'center' },
        { label: t('page.blocklists.colStatus'), width: '40px', align: 'center' },
        { label: t('page.blocklists.colEntries'), width: '60px', align: 'right' },
        { label: t('page.blocklists.colProxy'), width: '70px' },
        { label: '', width: '40px', align: 'center' },
        { label: '', width: '70px', align: 'center' },
      ];

      const rows = items.map(s => {
        const nameSpan = document.createElement('span');
        nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer;font-size:12px';
        nameSpan.textContent = s.name || s.id;
        nameSpan.dataset.sourceId = s.id;
        nameSpan.dataset.action = 'edit';

        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'btn btn-xs ' + (s.enabled ? 'btn-primary' : 'btn-ghost');
        toggleBtn.style.cssText = 'padding:1px 4px;font-size:9px';
        toggleBtn.textContent = s.enabled ? t('common.on') : t('common.off');
        toggleBtn.dataset.sourceId = s.id;
        toggleBtn.dataset.action = 'toggle';

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

        const p = fetchProgress[s.id];
        let entryCell;
        if (p) {
          if (p.status === 'downloading') entryCell = `<span style="color:var(--info);font-size:11px">↓ ${fmtBytes(p.downloaded)}</span>`;
          else if (p.status === 'parsing') entryCell = `<span style="color:var(--warning);font-size:11px">⏳ parse</span>`;
          else if (p.status === 'done' && p.count != null) entryCell = `<span style="color:var(--success);font-size:11px">✓ ${p.count}</span>`;
          else entryCell = s.entry_count ?? s.last_fetch_count ?? 0;
        } else {
          entryCell = s.entry_count ?? s.last_fetch_count ?? 0;
        }

        return [
          nameSpan.outerHTML,
          `<span style="font-size:10px;color:var(--text-muted)">${typeLabel(s.list_type)}</span>`,
          statusBadge(s),
          entryCell,
          s.download_proxy ? `<span style="font-size:9px;color:var(--text-muted)">via proxy</span>` : `<span style="font-size:9px;color:var(--text-muted)">direct</span>`,
          toggleBtn.outerHTML,
          editBtn.outerHTML + delBtn.outerHTML,
        ];
      });

      const tbl = ui.table(headers, rows);
      grp.appendChild(tbl);
      grp.querySelectorAll('[data-action]').forEach(el => {
        el.addEventListener('click', () => {
          const sid = el.dataset.sourceId;
          const action = el.dataset.action;
          if (action === 'edit') editSource(sid);
          else if (action === 'delete') deleteSource(sid);
          else if (action === 'toggle') toggleSource(sid);
        });
      });
      wrap.appendChild(grp);
    });
  }

  function editSource(id) {
    api.blocklistGet(id).then(src => {
      if (src) showEditor(src);
      else app.toast(t('page.blocklists.sourceNotFound'), 'error');
    }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  function deleteSource(id) {
    if (!confirm(t('common.confirmDelete', { item: 'blocklist source' }))) return;
    api.blocklistDelete(id).then(() => {
      app.toast(t('page.blocklists.sourceDeleted'));
      if (editingId === id) { editingId = null; resetEditor(); }
      load();
    }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  function toggleSource(id) {
    api.blocklistToggle(id).then(() => load()).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    if (progressPoller) return;
    _loading = true;
    try {
      const result = await api.blocklists();
      sources = result.sources || [];
      updateSourcesCard(sources);
    } catch (e) {
      console.error('blocklists load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 5000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
