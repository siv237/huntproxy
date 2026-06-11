router.register('custom-proxies', (container) => {
  let customProxies = [];
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
    row.appendChild(buildListCard());
    row.appendChild(buildEditorCard());
    container.appendChild(row);
  }

  function buildListCard() {
    const card = ui.card(t('page.customProxies.customProxies'));
    card.id = 'card-custom-proxies';
    card.style.overflow = 'hidden';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+ New Proxy', id: 'btn-add-proxy', style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => {
      editingId = null;
      showEditor(null);
    });
    card.appendChild(addBtn);

    const tblWrap = ui.el('div', '', { id: 'custom-proxies-tbl', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No custom proxies</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildEditorCard() {
    const card = ui.card(t('page.customProxies.proxyEditor'));
    card.id = 'card-proxy-editor';
    card.style.overflow = 'hidden';

    const body = ui.el('div', '', { id: 'proxy-editor-body' });
    body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a proxy to edit or create a new one</div>';
    card.appendChild(body);

    return card;
  }

  function inputStyle() {
    return 'width:100%;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)';
  }

  function labelStyle() {
    return 'font-size:12px;color:var(--text-secondary);margin-bottom:4px';
  }

  function showEditor(p) {
    const body = document.getElementById('proxy-editor-body');
    if (!body) return;
    body.innerHTML = '';
    editingId = p ? p.id : null;

    const nameRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    nameRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Name:' }));
    const nameInput = ui.el('input', '', { id: 'pe-name', type: 'text', value: p ? p.name : '', placeholder: 'e.g. Corporate, Tor, Anti-ban', style: inputStyle() });
    nameRow.appendChild(nameInput);
    body.appendChild(nameRow);

    const idRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    idRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'ID (auto-generated from name):' }));
    const idInput = ui.el('input', '', { id: 'pe-id', type: 'text', value: p ? p.id : '', placeholder: 'auto-generated from name', style: inputStyle() + (p ? 'opacity:0.6' : '') });
    if (p) idInput.disabled = true;
    idRow.appendChild(idInput);
    body.appendChild(idRow);

    nameInput.addEventListener('input', () => {
      if (!editingId) {
        idInput.value = nameInput.value.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      }
    });

    const protoRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    protoRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Protocol:' }));
    const protoSelect = ui.el('select', '', { id: 'pe-protocol', style: inputStyle() });
    ['socks5', 'http', 'https'].forEach(v => {
      const o = ui.el('option', '', { value: v, text: v.toUpperCase() });
      if (p && p.protocol === v) o.selected = true;
      protoSelect.appendChild(o);
    });
    protoRow.appendChild(protoSelect);
    body.appendChild(protoRow);

    const addrRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-bottom:10px' });
    const hostCol = ui.el('div', '', { style: 'flex:3' });
    hostCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Host:' }));
    hostCol.appendChild(ui.el('input', '', { id: 'pe-host', type: 'text', value: p ? p.host : '', placeholder: 'proxy.example.com or 127.0.0.1', style: inputStyle() }));
    addrRow.appendChild(hostCol);
    const portCol = ui.el('div', '', { style: 'flex:1' });
    portCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Port:' }));
    portCol.appendChild(ui.el('input', '', { id: 'pe-port', type: 'number', value: p ? p.port : '', placeholder: '1080', style: inputStyle() }));
    addrRow.appendChild(portCol);
    body.appendChild(addrRow);

    const authRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-bottom:10px' });
    const userCol = ui.el('div', '', { style: 'flex:1' });
    userCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Username:' }));
    userCol.appendChild(ui.el('input', '', { id: 'pe-username', type: 'text', value: p ? p.username : '', placeholder: '(optional)', style: inputStyle() }));
    authRow.appendChild(userCol);
    const passCol = ui.el('div', '', { style: 'flex:1' });
    passCol.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Password:' }));
    const passWrap = ui.el('div', '', { style: 'display:flex;gap:4px' });
    const passInput = ui.el('input', '', { id: 'pe-password', type: 'password', value: '', placeholder: p && p.password ? '**** (unchanged)' : '(optional)', style: inputStyle() + 'flex:1' });
    passWrap.appendChild(passInput);
    const eyeBtn = ui.el('button', 'btn btn-xs btn-ghost', { style: 'padding:4px 6px;font-size:11px;line-height:1' });
    eyeBtn.textContent = '\u{1F441}';
    let passVisible = false;
    eyeBtn.addEventListener('click', () => {
      passVisible = !passVisible;
      passInput.type = passVisible ? 'text' : 'password';
    });
    passWrap.appendChild(eyeBtn);
    passCol.appendChild(passWrap);
    authRow.appendChild(passCol);
    body.appendChild(authRow);

    const testRow = ui.el('div', '', { style: 'margin-bottom:10px' });
    testRow.appendChild(ui.el('div', '', { style: labelStyle(), text: 'Test URL (used to verify proxy works):' }));
    testRow.appendChild(ui.el('input', '', { id: 'pe-test-url', type: 'text', value: p ? p.test_url : '', placeholder: 'http://check.torproject.org or http://intranet.corp/', style: inputStyle() }));
    body.appendChild(testRow);

    const hints = ui.el('div', '', { style: 'font-size:10px;color:var(--text-muted);line-height:1.5;margin-bottom:12px;padding:6px 8px;background:var(--surface-raised);border-radius:var(--radius-xs)' });
    hints.innerHTML = '<b>Protocol hints:</b><br>SOCKS5 — Tor (127.0.0.1:9050), local SOCKS proxies<br>HTTP — corporate proxies (often with auth)<br>HTTPS — TLS-wrapped proxies (anti-ban services)';
    body.appendChild(hints);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center' });
    const testBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.customProxies.testConnection') });
    testBtn.addEventListener('click', () => {
      const host = document.getElementById('pe-host').value.trim();
      const port = parseInt(document.getElementById('pe-port').value) || 0;
      if (!host || !port) { app.toast('Fill host and port first', 'error'); return; }
      testBtn.disabled = true;
      testBtn.textContent = 'Testing...';
      const testData = {
        host,
        port,
        protocol: document.getElementById('pe-protocol').value,
        username: document.getElementById('pe-username').value.trim(),
        password: document.getElementById('pe-password').value || (p && p.password === '****' ? '' : ''),
        test_url: document.getElementById('pe-test-url').value.trim(),
      };
      api.customProxyTestDirect(testData).then(result => {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
        if (result.status === 'ok') {
          app.toast(`OK — HTTP ${result.http_code} in ${result.latency_ms}ms`);
        } else {
          app.toast(`${result.status}: ${result.error || 'HTTP ' + result.http_code}`, 'error');
        }
      }).catch(e => {
        testBtn.disabled = false;
        testBtn.textContent = 'Test Connection';
        app.toast('Error: ' + e.message, 'error');
      });
    });
    btnRow.appendChild(testBtn);

    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: p ? 'Save Changes' : 'Create Proxy' });
    saveBtn.addEventListener('click', () => {
      const name = document.getElementById('pe-name').value.trim();
      let proxyId = document.getElementById('pe-id').value.trim().replace(/[^a-z0-9-_]/gi, '-').toLowerCase();
      if (!proxyId) proxyId = name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
      const protocol = document.getElementById('pe-protocol').value;
      const host = document.getElementById('pe-host').value.trim();
      const port = parseInt(document.getElementById('pe-port').value) || 0;
      const username = document.getElementById('pe-username').value.trim();
      const passwordVal = document.getElementById('pe-password').value;
      const test_url = document.getElementById('pe-test-url').value.trim();

      if (!name) { app.toast('Name is required', 'error'); return; }
      if (!host) { app.toast('Host is required', 'error'); return; }
      if (!port) { app.toast('Port is required', 'error'); return; }

      const existingP = editingId ? customProxies.find(x => x.id === editingId) : null;
      const data = {
        id: proxyId,
        name,
        protocol,
        host,
        port,
        username,
        password: passwordVal || (existingP ? '****' : ''),
        test_url,
        enabled: existingP ? existingP.enabled : true,
      };

      if (editingId) {
        api.customProxyUpdate(editingId, data).then(() => {
          app.toast('Proxy updated');
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.customProxyCreate(data).then(() => {
          app.toast('Proxy created');
          editingId = null;
          load();
          resetEditor();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    btnRow.appendChild(saveBtn);

    if (p) {
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
    const body = document.getElementById('proxy-editor-body');
    if (body) body.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">Select a proxy to edit or create a new one</div>';
  }

  function statusBadge(p) {
    const s = p.last_check_status;
    if (!s) return '<span style="color:var(--text-muted);font-size:11px">—</span>';
    if (s === 'ok') return '<span style="color:var(--success);font-weight:600;font-size:11px">OK</span>';
    if (s === 'timeout') return '<span style="color:var(--warning);font-weight:600;font-size:11px">Timeout</span>';
    if (s === 'auth_fail') return '<span style="color:var(--danger);font-weight:600;font-size:11px">Auth Fail</span>';
    return '<span style="color:var(--danger);font-weight:600;font-size:11px">Fail</span>';
  }

  function latencyText(p) {
    if (p.last_check_latency < 0) return '<span style="color:var(--text-muted)">—</span>';
    return `<span style="font-size:11px">${p.last_check_latency}ms</span>`;
  }

  function updateListCard(proxies) {
    const wrap = document.getElementById('custom-proxies-tbl');
    if (!wrap) return;
    customProxies = proxies || [];

    if (!proxies || !proxies.length) {
      wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No custom proxies. Add one for specialized routing (corporate, Tor, anti-ban).</div>';
      return;
    }

    const headers = [
      { label: 'Name', width: '120px' },
      { label: 'Protocol', width: '60px', align: 'center' },
      { label: 'Address', width: '130px' },
      { label: 'Test URL', width: '100px' },
      { label: 'Status', width: '60px', align: 'center' },
      { label: 'Latency', width: '50px', align: 'center' },
      { label: 'Enabled', width: '50px', align: 'center' },
      { label: 'Actions', width: '120px', align: 'center' },
    ];

    const rows = proxies.map(p => {
      const nameSpan = document.createElement('span');
      nameSpan.style.cssText = 'color:var(--text-primary);font-weight:500;cursor:pointer';
      nameSpan.textContent = p.name || p.id;
      nameSpan.dataset.proxyId = p.id;
      nameSpan.dataset.action = 'edit';

      const protoSpan = `<span style="font-size:11px;text-transform:uppercase;color:var(--info)">${ui.escHtml(p.protocol)}</span>`;

      const addrSpan = `<span style="font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:11px">${ui.escHtml(p.host)}:${p.port}</span>`;

      const testUrlSpan = document.createElement('span');
      testUrlSpan.style.cssText = 'font-size:10px;color:var(--text-muted);max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block';
      testUrlSpan.textContent = p.test_url || '—';

      const enabledHtml = p.enabled
        ? '<span style="color:var(--success)">✓</span>'
        : '<span style="color:var(--text-muted)">✗</span>';

      const editBtn = document.createElement('button');
      editBtn.className = 'btn btn-xs btn-secondary';
      editBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      editBtn.textContent = 'Edit';
      editBtn.dataset.proxyId = p.id;
      editBtn.dataset.action = 'edit';

      const testBtn = document.createElement('button');
      testBtn.className = 'btn btn-xs btn-secondary';
      testBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      testBtn.textContent = 'Test';
      testBtn.dataset.proxyId = p.id;
      testBtn.dataset.action = 'test';

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = 'Delete';
      delBtn.dataset.proxyId = p.id;
      delBtn.dataset.action = 'delete';

      return [
        nameSpan.outerHTML,
        protoSpan,
        addrSpan,
        testUrlSpan.outerHTML,
        statusBadge(p),
        latencyText(p),
        enabledHtml,
        editBtn.outerHTML + testBtn.outerHTML + delBtn.outerHTML,
      ];
    });

    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(el => {
      el.addEventListener('click', () => {
        const proxyId = el.dataset.proxyId;
        const action = el.dataset.action;
        if (action === 'edit') editProxy(proxyId);
        else if (action === 'test') testProxy(proxyId);
        else if (action === 'delete') deleteProxy(proxyId);
      });
    });
  }

  function editProxy(id) {
    const p = customProxies.find(x => x.id === id);
    if (p) showEditor(p);
    else app.toast('Proxy not found', 'error');
  }

  function testProxy(id) {
    app.toast('Testing proxy...', 'info');
    api.customProxyTest(id).then(result => {
      if (result.status === 'ok') {
        app.toast(`Proxy OK — ${result.http_code} in ${result.latency_ms}ms`);
      } else {
        app.toast(`Proxy ${result.status}: ${result.error || 'HTTP ' + result.http_code}`, 'error');
      }
      load();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function deleteProxy(id) {
    if (!confirm(t('common.confirmDelete', { item: 'proxy' }))) return;
    api.customProxyDelete(id).then(() => {
      app.toast('Proxy deleted');
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
      try { result = await api.customProxies(); } catch (e) { console.error('customProxies', e); }
      const proxies = result.proxies || result || [];
      customProxies = proxies;
      updateListCard(proxies);
    } catch (e) {
      console.error('custom-proxies load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 5000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
