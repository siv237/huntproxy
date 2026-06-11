router.register('proxy-sources', (container) => {
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
  }

  function buildSourcesCard() {
    const card = ui.card('Proxy Sources');
    card.id = 'card-proxy-sources';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+ New Source', style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });
    card.appendChild(addBtn);

    const tblWrap = ui.el('div', '', { id: 'proxy-sources-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No proxy sources</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card('Source Editor');
    card.id = 'card-source-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'source-editor-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a source to edit or add a new one</div>';
    card.appendChild(body);

    return card;
  }

  function showEditor(src) {
    const body = document.getElementById('source-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = src ? src.id : null;

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'Name:' }));
    const nameInput = ui.el('input', '', { id: 'src-name', type: 'text', value: src ? src.name : '', placeholder: 'e.g. monosans/socks5', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'ID (auto from name):' }));
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
    urlRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'URL (plain text ip:port list):' }));
    const urlInput = ui.el('input', '', { id: 'src-url', type: 'text', value: src ? src.url : '', placeholder: 'https://example.com/proxies.txt', style: 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    urlRow.appendChild(urlInput);
    body.appendChild(urlRow);

    const protoRow = ui.el('div', '', { style: 'margin-bottom:12px' });
    protoRow.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'Protocol:' }));
    const protoSelect = ui.el('select', '', { id: 'src-protocol', style: 'width:100%;padding:6px 8px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    ['mixed', 'http', 'socks4', 'socks5'].forEach(p => {
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
          <div style="margin-bottom:4px;color:var(--text-secondary)">Source Stats</div>
          <div>Last fetched: <b>${ui.ago(src.last_fetched_at)}</b></div>
          <div>Last status: <b style="color:${src.last_fetch_status === 'ok' ? 'var(--success)' : 'var(--danger)'}">${src.last_fetch_status || '—'}</b></div>
          ${src.last_fetch_error ? `<div>Error: <span style="color:var(--danger)">${ui.escHtml(src.last_fetch_error)}</span></div>` : ''}
          <div style="margin-top:6px">
            <span style="color:var(--success)">Last: ${src.last_working} working</span> /
            <span style="color:var(--danger)">${src.last_dead} dead</span>
            (fetched ${src.last_fetch_count})
          </div>
          <div style="margin-top:2px">
            <span style="color:var(--text-muted)">Cumulative: ${src.total_working} working / ${src.total_dead} dead / ${src.total_fetched} fetched</span>
          </div>
        </div>`;
      body.appendChild(ui.el('div', '', { html: statsHtml }));
    }

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px' });
    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: src ? 'Save Changes' : 'Add Source' });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('src-name').value.trim();
      let sourceId = document.getElementById('src-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!sourceId) sourceId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const url = document.getElementById('src-url').value.trim();
      const protocol = document.getElementById('src-protocol').value;

      if (!name) { app.toast('Name is required', 'error'); return; }
      if (!url) { app.toast('URL is required', 'error'); return; }

      const data = { id: sourceId, name, url, protocol };

      if (editingId) {
        api.proxySourceUpdate(editingId, data).then(() => {
          app.toast('Source updated');
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.proxySourceCreate(data).then(() => {
          app.toast('Source added');
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (src) {
      const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: 'Cancel' });
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
    if (body) body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a source to edit or add a new one</div>';
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
    const colors = { http: 'var(--info)', socks4: 'var(--accent)', socks5: 'var(--success)', mixed: 'var(--text-muted)' };
    const color = colors[protocol] || colors.mixed;
    return `<span style="color:${color};font-size:11px;font-weight:600">${(protocol || 'mixed').toUpperCase()}</span>`;
  }

  function statusBadge(src) {
    if (!src.last_fetched_at) return '<span style="color:var(--text-muted);font-size:11px">Never</span>';
    if (src.last_fetch_status === 'ok') return `<span style="color:var(--success);font-size:11px">OK</span>`;
    return `<span style="color:var(--danger);font-size:11px" title="${ui.escHtml(src.last_fetch_error || '')}">ERR</span>`;
  }

  function updateSourcesCard(list) {
    const wrap = document.getElementById('proxy-sources-tbl');
    if (!wrap) return;
    sources = list || [];

    if (!list || !list.length) {
      wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No proxy sources. Add one to harvest proxies.</div>';
      return;
    }

    const headers = [
      { label: 'Source', width: '140px' },
      { label: 'Proto', width: '50px', align: 'center' },
      { label: 'Status', width: '40px', align: 'center' },
      { label: 'Last', width: '60px' },
      { label: 'Quality', width: '50px', align: 'center' },
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

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = 'Edit';
      editBtn.dataset.sourceId = s.id;
      editBtn.dataset.action = 'edit';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = 'Del';
      delBtn.dataset.sourceId = s.id;
      delBtn.dataset.action = 'delete';

      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'btn btn-xs ' + (s.enabled ? 'btn-primary' : 'btn-ghost');
      toggleBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      toggleBtn.textContent = s.enabled ? 'ON' : 'OFF';
      toggleBtn.dataset.sourceId = s.id;
      toggleBtn.dataset.action = 'toggle';

      return [
        nameSpan.outerHTML,
        protocolBadge(s.protocol),
        statusBadge(s),
        ui.ago(s.last_fetched_at),
        qualityBadge(s.last_working, s.last_dead),
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
      else app.toast('Source not found', 'error');
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function deleteSource(id) {
    if (!confirm('Delete this proxy source?')) return;
    api.proxySourceDelete(id).then(() => {
      app.toast('Source deleted');
      if (editingId === id) {
        editingId = null;
        resetEditor();
      }
      load();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function toggleSource(id) {
    api.proxySourceToggle(id).then(() => {
      load();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  build();

  async function load() {
    if (_loading) return;
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
