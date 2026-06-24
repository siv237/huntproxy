router.register('domain-lists', (container) => {
  let domainLists = [];
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
    row.appendChild(buildListsCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);
  }

  function buildListsCard() {
    const card = ui.card(t('page.domainLists.domainLists'));
    card.id = 'card-domain-lists';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+ New List', id: 'btn-add-list', style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });
    card.appendChild(addBtn);

    const tblWrap = ui.el('div', '', { id: 'domain-lists-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No domain lists</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.domainLists.listEditor'));
    card.id = 'card-domain-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'editor-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a list to edit or create a new one</div>';
    card.appendChild(body);

    return card;
  }

  function showEditor(dl) {
    const body = document.getElementById('editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = dl ? dl.id : null;

    const currentSource = dl ? (dl.source || 'manual') : 'manual';

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.listName') }));
    const nameInput = ui.el('input', '', { id: 'editor-name', type: 'text', value: dl ? dl.name : '', placeholder: 'e.g. Social Media, Blocked Sites', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.listId') }));
    const idInput = ui.el('input', '', { id: 'editor-id', type: 'text', value: dl ? dl.id : '', placeholder: 'auto-generated from name', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);' + (dl ? 'opacity:0.6' : '') });
    if (dl) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const sourceRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    sourceRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.source') }));
    const sourceSelect = ui.el('select', '', { id: 'editor-source', style: 'width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    sourceRow.appendChild(sourceSelect);
    body.appendChild(sourceRow);

    const domainsRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    domainsRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.domainsOnePerLine') }));
    const domainsArea = ui.el('textarea', '', { id: 'editor-domains', rows: '10', placeholder: 'example.com\n.facebook.com\nexact:twitter.com\n*.google.com', style: 'width:100%;padding:8px 10px;font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);resize:vertical' });
    domainsArea.value = dl && dl.domains ? dl.domains.join('\n') : '';
    domainsRow.appendChild(domainsArea);

    const hints = ui.el('div', '', { style: 'font-size:10px;color:var(--text-muted);line-height:1.5;margin-bottom:12px;padding:6px 8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
    hints.innerHTML = '<b>Patterns:</b><br>example.com — exact + subdomains (*.example.com)<br>.example.com — subdomains only<br>exact:example.com — strict match (no subdomains)<br>*.example.com — same as .example.com';
    domainsRow.appendChild(hints);
    body.appendChild(domainsRow);

    const routeRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    routeRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.domainLists.routeLabel') }));
    const routeSelect = ui.el('select', '', { id: 'editor-route', style: 'width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    routeRow.appendChild(routeSelect);
    body.appendChild(routeRow);

    function populateRouteSelect(selected) {
      routeSelect.innerHTML = '';
      const opts = [
        { value: 'direct', text: t('route.directNoProxy') },
        { value: 'pool', text: t('route.poolBest') },
      ];
      opts.forEach(o => {
        const el = ui.el('option', '', { value: o.value, text: o.text });
        if (o.value === selected) el.selected = true;
        routeSelect.appendChild(el);
      });
      api.customProxies().then(r => {
        const cps = (r && r.proxies) || [];
        const enabled = cps.filter(p => p.enabled);
        if (enabled.length) {
          const grp = ui.el('optgroup', '', { label: t('page.domainLists.customProxies') });
          enabled.forEach(p => {
            const label = p.name + ' (' + (p.protocol || 'socks5').toUpperCase() + ' ' + p.host + ':' + p.port + ')';
            const o = ui.el('option', '', { value: 'custom:' + p.id, text: label });
            if (('custom:' + p.id) === selected) o.selected = true;
            grp.appendChild(o);
          });
          routeSelect.appendChild(grp);
        }
      }).catch(() => {});
      api.proxies({ status: 'ok', limit: 200 }).then(r => {
        const proxies = (r && r.proxies) || r || [];
        const alive = Array.isArray(proxies) ? proxies.filter(p => p.last_status === 'ok' || p.alive) : [];
        if (alive.length) {
          const grp = ui.el('optgroup', '', { label: t('page.domainLists.workingProxies') });
          alive.slice(0, 200).forEach(p => {
            const addr = p.address || (p.host + ':' + p.port);
            const label = addr + ' (' + (p.protocol || '').toUpperCase() + ' ' + (p.country || '?') + ')';
            const o = ui.el('option', '', { value: 'proxy:' + addr, text: label });
            if (('proxy:' + addr) === selected) o.selected = true;
            grp.appendChild(o);
          });
          routeSelect.appendChild(grp);
        }
      }).catch(() => {});
    }

    populateRouteSelect(dl ? (dl.route || '') : 'pool');

    const searchRow = ui.el('div', '', { id: 'search-row', style: 'margin-bottom:10px;display:none' });
    const searchBox = ui.el('input', '', { id: 'bl-search', type: 'text', placeholder: t('page.domainLists.searchPlaceholder'), style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    searchRow.appendChild(searchBox);
    const searchInfo = ui.el('div', '', { id: 'bl-info', style: 'font-size:11px;color:var(--text-secondary);margin-top:4px' });
    searchRow.appendChild(searchInfo);
    body.appendChild(searchRow);

    let allDomains = [];
    let showCount = 200;
    let filteredCount = 0;

    function applySearch() {
      const q = (document.getElementById('bl-search').value || '').trim().toLowerCase();
      if (!q) {
        domainsArea.value = allDomains.join('\n');
        filteredCount = allDomains.length;
      } else {
        const filtered = allDomains.filter(d => d.includes(q));
        filteredCount = filtered.length;
        domainsArea.value = filtered.slice(0, 5000).join('\n');
      }
      const info = document.getElementById('bl-info');
      if (info) {
        let txt = `${filteredCount} / ${allDomains.length}`;
        if (q && filteredCount > 5000) txt += ' (showing first 5000)';
        info.textContent = txt;
      }
    }

    function setManualMode() {
      domainsArea.disabled = false;
      domainsArea.style.opacity = '1';
      searchRow.style.display = 'none';
      hints.style.display = '';
    }

    function setBlocklistMode(blId) {
      domainsArea.disabled = true;
      domainsArea.style.opacity = '0.6';
      hints.style.display = 'none';
      searchRow.style.display = '';
      domainsArea.value = 'Loading...';
      api.domainListGet(blId).then(d => {
        allDomains = (d && d.domains) || [];
        showCount = 200;
        applySearch();
      }).catch(e => {
        domainsArea.value = '';
        app.toast(t('common.error', { message: e.message }), 'error');
      });
    }

    let blocklistSources = [];
    sourceSelect.appendChild(ui.el('option', '', { value: 'manual', text: t('page.domainLists.manual') }));
    api.blocklists().then(r => {
      const sources = (r && r.sources) || [];
      blocklistSources = sources.filter(s => s.list_type === 'domain');
      blocklistSources.forEach(s => {
        const opt = ui.el('option', '', { value: s.id, text: `${s.name} (${s.entry_count || 0})` });
        sourceSelect.appendChild(opt);
      });
      if (currentSource === 'blocklist' && dl) {
        sourceSelect.value = dl.id;
        setBlocklistMode(dl.id);
      } else {
        sourceSelect.value = 'manual';
        setManualMode();
      }
    }).catch(() => {
      sourceSelect.value = 'manual';
      setManualMode();
    });

    if (currentSource === 'blocklist' && dl) {
      allDomains = dl.domains || [];
      sourceSelect.value = dl.id;
      setBlocklistMode(dl.id);
    } else {
      sourceSelect.value = 'manual';
      setManualMode();
    }

    sourceSelect.addEventListener('change', () => {
      const val = sourceSelect.value;
      if (val === 'manual') {
        setManualMode();
      } else {
        setBlocklistMode(val);
      }
    });

    searchBox.addEventListener('input', () => { applySearch(); });

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: dl ? t('page.domainLists.saveChanges') : t('page.domainLists.createList') });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('editor-name').value.trim();
      let listId = document.getElementById('editor-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!listId) listId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const domainsText = document.getElementById('editor-domains').value;
      const domains = domainsText.split('\n').map(d => d.trim()).filter(d => d);

      if (!name) { app.toast('Name is required', 'error'); return; }

      const sourceVal = sourceSelect.value;
      const existingDl = editingId ? domainLists.find(l => l.id === editingId) : null;
      const data = {
        id: listId,
        name,
        domains,
        source: sourceVal === 'manual' ? 'manual' : 'blocklist',
        route: document.getElementById('editor-route').value || 'pool',
        enabled: existingDl ? existingDl.enabled : true,
      };

      if (editingId) {
        api.domainListUpdate(editingId, data).then(() => {
          app.toast(t('page.domainLists.listUpdated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      } else {
        api.domainListCreate(data).then(() => {
          app.toast(t('page.domainLists.listCreated'));
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast(t('common.error', { message: e.message }), 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (dl) {
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
    const body = document.getElementById('editor-body');
    if (body) body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a list to edit or create a new one</div>';
  }

  function updateListsCard(lists) {
    const wrap = document.getElementById('domain-lists-tbl');
    if (!wrap) return;
    domainLists = lists || [];

    if (!lists || !lists.length) {
      wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No domain lists. Create one to group domains for routing.</div>';
      return;
    }

    const headers = [
      { label: 'Name', width: '140px' },
      { label: 'Domains', width: '60px', align: 'center' },
      { label: 'Source', width: '60px', align: 'center' },
      { label: 'Route', width: '80px' },
      { label: 'Actions', width: '100px', align: 'center' },
    ];

    const sourceLabel = (source) => {
      if (source === 'blocklist') return '<span style="color:var(--success);font-size:11px">Blocklist</span>';
      if (source === 'url') return '<span style="color:var(--info);font-size:11px">URL</span>';
      return '<span style="color:var(--text-muted);font-size:11px">Manual</span>';
    };

    const rows = lists.map(l => {
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer';
      nameSpan.textContent = l.name || l.id;
      nameSpan.dataset.listId = l.id;
      nameSpan.dataset.action = 'edit';

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = 'Edit';
      editBtn.dataset.listId = l.id;
      editBtn.dataset.action = 'edit';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = 'Delete';
      delBtn.dataset.listId = l.id;
      delBtn.dataset.action = 'delete';

      return [
        nameSpan.outerHTML,
        (l.domain_count || 0),
        sourceLabel(l.source || 'manual'),
        ui.formatRouteLabel(l.route),
        editBtn.outerHTML + delBtn.outerHTML,
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        const listId = el.dataset.listId;
        const action = el.dataset.action;
        if (action === 'edit') editList(listId);
        else if (action === 'delete') deleteList(listId);
      });
    });
  }

  function editList(id) {
    api.domainListGet(id).then(dl => {
      if (dl) showEditor(dl);
      else app.toast('List not found', 'error');
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function deleteList(id) {
    if (!confirm(t('common.confirmDelete', { item: 'list' }))) return;
    api.domainListDelete(id).then(() => {
      app.toast('List deleted');
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      let result = [];
      try { result = await api.domainLists(); } catch (e) { console.error('domainLists', e); }
      const lists = result.lists || result || [];
      domainLists = lists;
      updateListsCard(lists);
    } catch (e) {
      console.error('domain-lists load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
