router.register('pac', (container) => {
  let cfg = { enabled: false, proxy_host: '', proxy_port: 17277, direct_hosts: [], internal_nets: [], url: '', preview: '' };
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
    const row = ui.el('div', '', { style: 'display:flex;gap:10px;align-items:stretch;flex-wrap:wrap' });
    const settingsCard = buildSettingsCard();
    settingsCard.style.flex = '1';
    settingsCard.style.minWidth = '280px';
    row.appendChild(settingsCard);
    const urlCard = buildUrlCard();
    urlCard.style.flex = '1';
    urlCard.style.minWidth = '280px';
    row.appendChild(urlCard);
    container.appendChild(row);

    const exRow = ui.el('div', '', { style: 'display:flex;gap:10px;align-items:stretch;flex-wrap:wrap' });
    const domainsCard = buildDomainsCard();
    domainsCard.style.flex = '1';
    domainsCard.style.minWidth = '300px';
    exRow.appendChild(domainsCard);
    const netsCard = buildNetsCard();
    netsCard.style.flex = '1';
    netsCard.style.minWidth = '300px';
    exRow.appendChild(netsCard);
    container.appendChild(exRow);

    container.appendChild(buildPreviewCard());
  }

  function buildSettingsCard() {
    const card = ui.card(t('page.pac.serverSettings'));
    card.id = 'card-pac-settings';

    const toggleRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:12px' });
    const label = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;font-weight:600' });
    const cb = ui.el('input', '', { id: 'pac-enabled', type: 'checkbox' });
    cb.addEventListener('change', () => {
      updateStatusBadge();
      persist(true);
    });
    label.appendChild(cb);
    label.appendChild(ui.el('span', '', { text: t('page.pac.enable') }));
    toggleRow.appendChild(label);
    const badge = ui.el('span', '', { id: 'pac-status-badge', style: 'font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600' });
    toggleRow.appendChild(badge);
    card.appendChild(toggleRow);

    const hostRow = fieldRow(t('page.pac.proxyHost'), 'pac-proxy-host');
    card.appendChild(hostRow);

    const portRow = fieldRow(t('page.pac.proxyPort'), 'pac-proxy-port');
    card.appendChild(portRow);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;margin-top:10px;flex-wrap:wrap' });
    const detectBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.pac.detectIp') });
    detectBtn.addEventListener('click', () => {
      api.pacDetectIp().then(r => {
        const host = document.getElementById('pac-proxy-host');
        if (host && r.ip) host.value = r.ip;
        app.toast(t('page.pac.ipDetected'));
      }).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    btnRow.appendChild(detectBtn);

    const saveBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.pac.save') });
    saveBtn.addEventListener('click', () => save());
    btnRow.appendChild(saveBtn);

    const saveStatus = ui.el('span', '', { id: 'pac-save-status', style: 'font-size:11px;color:var(--text-muted);align-self:center' });
    btnRow.appendChild(saveStatus);
    card.appendChild(btnRow);

    return card;
  }

  function fieldRow(labelText, id) {
    const row = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:4px;margin-bottom:8px' });
    row.appendChild(ui.el('label', '', { style: 'font-size:12px;color:var(--text-secondary)', text: labelText }));
    row.appendChild(ui.el('input', '', {
      id, type: 'text', style: 'padding:5px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)',
    }));
    return row;
  }

  function buildUrlCard() {
    const card = ui.card(t('page.pac.autoconfigUrl'));
    card.id = 'card-pac-url';

    const urlInput = ui.el('input', '', {
      id: 'pac-url', type: 'text', readonly: true, style: 'width:100%;padding:6px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);box-sizing:border-box',
    });
    card.appendChild(urlInput);
    card.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin:6px 0 10px', text: t('page.pac.urlHint') }));

    const copyBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('page.pac.copyUrl') });
    copyBtn.addEventListener('click', () => {
      const url = document.getElementById('pac-url');
      if (!url || !url.value) return;
      navigator.clipboard.writeText(url.value).then(() => {
        app.toast(t('page.pac.copied'));
      }).catch(() => app.toast('Error', 'error'));
    });
    card.appendChild(copyBtn);
    return card;
  }

  function buildDomainsCard() {
    const card = ui.card(t('page.pac.domains'));
    card.id = 'card-pac-domains';
    card.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-bottom:8px', text: t('page.pac.domainsHint') }));

    const addRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px' });
    const input = ui.el('input', '', { id: 'pac-domain-input', type: 'text', placeholder: '*.example.com', style: 'flex:1;min-width:100px;padding:5px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    addRow.appendChild(input);
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+' });
    addBtn.addEventListener('click', () => {
      const v = input.value.trim();
      if (v && !cfg.direct_hosts.includes(v)) cfg.direct_hosts.push(v);
      input.value = '';
      renderDomainList();
      persist(false);
    });
    addRow.appendChild(addBtn);
    card.appendChild(addRow);

    const list = ui.el('div', '', { id: 'pac-domain-list' });
    card.appendChild(list);
    return card;
  }

  function renderDomainList() {
    const list = document.getElementById('pac-domain-list');
    if (!list) return;
    list.innerHTML = '';
    if (!cfg.direct_hosts.length) {
      list.appendChild(ui.el('div', 'empty', { style: 'padding:8px;font-size:12px', text: t('page.pac.noDomains') }));
      return;
    }
    cfg.direct_hosts.forEach((d, i) => {
      const row = ui.el('div', '', { style: 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 8px;border-bottom:1px solid var(--border);font-size:12px' });
      row.appendChild(ui.el('span', '', { text: d }));
      const del = ui.el('button', '', { style: 'background:none;border:none;cursor:pointer;color:var(--danger);font-size:13px', text: '✕', title: t('common.delete') });
      del.addEventListener('click', () => { cfg.direct_hosts.splice(i, 1); renderDomainList(); persist(false); });
      row.appendChild(del);
      list.appendChild(row);
    });
  }

  function buildNetsCard() {
    const card = ui.card(t('page.pac.subnets'));
    card.id = 'card-pac-nets';
    card.appendChild(ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-bottom:8px', text: t('page.pac.subnetsHint') }));

    const addRow = ui.el('div', '', { style: 'display:flex;gap:6px;margin-bottom:8px' });
    const netInput = ui.el('input', '', { id: 'pac-net-input', type: 'text', placeholder: '10.0.0.0', style: 'flex:1;min-width:80px;padding:5px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    addRow.appendChild(netInput);
    const maskInput = ui.el('input', '', { id: 'pac-mask-input', type: 'text', placeholder: '255.0.0.0', style: 'flex:1;min-width:80px;padding:5px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    addRow.appendChild(maskInput);
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+' });
    addBtn.addEventListener('click', () => {
      const network = netInput.value.trim();
      const mask = maskInput.value.trim();
      if (network && mask) cfg.internal_nets.push({ network, mask });
      netInput.value = '';
      maskInput.value = '';
      renderNetList();
      persist(false);
    });
    addRow.appendChild(addBtn);
    card.appendChild(addRow);

    const list = ui.el('div', '', { id: 'pac-net-list' });
    card.appendChild(list);
    return card;
  }

  function renderNetList() {
    const list = document.getElementById('pac-net-list');
    if (!list) return;
    list.innerHTML = '';
    if (!cfg.internal_nets.length) {
      list.appendChild(ui.el('div', 'empty', { style: 'padding:8px;font-size:12px', text: t('page.pac.noSubnets') }));
      return;
    }
    cfg.internal_nets.forEach((n, i) => {
      const row = ui.el('div', '', { style: 'display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 8px;border-bottom:1px solid var(--border);font-size:12px' });
      row.appendChild(ui.el('span', '', { text: n.network + ' / ' + n.mask }));
      const del = ui.el('button', '', { style: 'background:none;border:none;cursor:pointer;color:var(--danger);font-size:13px', text: '✕', title: t('common.delete') });
      del.addEventListener('click', () => { cfg.internal_nets.splice(i, 1); renderNetList(); persist(false); });
      row.appendChild(del);
      list.appendChild(row);
    });
  }

  function buildPreviewCard() {
    const card = ui.card(t('page.pac.preview'));
    card.id = 'card-pac-preview';
    card.appendChild(ui.el('pre', '', {
      id: 'pac-preview', style: 'background:var(--surface-raised);padding:10px;border-radius:var(--radius-xs);font-size:11px;line-height:1.5;overflow:auto;max-height:360px;white-space:pre-wrap;word-break:break-all;color:var(--text-primary)',
    }));
    return card;
  }

  function collectFromInputs() {
    const host = document.getElementById('pac-proxy-host');
    const port = document.getElementById('pac-port') || document.getElementById('pac-proxy-port');
    const cb = document.getElementById('pac-enabled');
    if (host) cfg.proxy_host = host.value.trim();
    if (port) {
      const p = parseInt(port.value, 10);
      if (!isNaN(p)) cfg.proxy_port = p;
    }
    if (cb) cfg.enabled = cb.checked;
  }

  function updateStatusBadge() {
    const badge = document.getElementById('pac-status-badge');
    const cb = document.getElementById('pac-enabled');
    if (!badge) return;
    if (cb && cb.checked) {
      badge.textContent = 'ON';
      badge.style.background = 'var(--success-bg)';
      badge.style.color = 'var(--success)';
    } else {
      badge.textContent = 'OFF';
      badge.style.background = 'var(--surface-raised)';
      badge.style.color = 'var(--text-muted)';
    }
  }

  function persist(showToast) {
    collectFromInputs();
    api.pacSave({
      enabled: cfg.enabled,
      proxy_host: cfg.proxy_host,
      proxy_port: cfg.proxy_port,
      direct_hosts: cfg.direct_hosts,
      internal_nets: cfg.internal_nets,
    }).then(res => {
      cfg = res;
      applyToDom(cfg);
      if (showToast) {
        const status = document.getElementById('pac-save-status');
        if (status) status.textContent = t('page.pac.saved');
        app.toast(t('page.pac.saved'));
      }
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function save() {
    persist(true);
  }

  function applyToDom(c) {
    const host = document.getElementById('pac-proxy-host');
    const port = document.getElementById('pac-proxy-port');
    const cb = document.getElementById('pac-enabled');
    const url = document.getElementById('pac-url');
    const preview = document.getElementById('pac-preview');
    if (host) host.value = c.proxy_host;
    if (port) port.value = c.proxy_port;
    if (cb) cb.checked = !!c.enabled;
    if (url) url.value = c.url || '';
    if (preview) preview.textContent = c.preview || '';
    renderDomainList();
    renderNetList();
    updateStatusBadge();
  }

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      cfg = await api.pacConfig();
      applyToDom(cfg);
    } catch (e) {
      console.error('pac load', e);
    } finally {
      _loading = false;
    }
  }

  build();
  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
