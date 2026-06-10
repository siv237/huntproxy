router.register('routes', (container) => {
  let routingStatus = null;
  let domainLists = [];
  let customProxies = [];
  let _loading = false;

  const ROUTE_OPTIONS = [
    { value: 'direct', label: 'Direct (no proxy)' },
    { value: 'pool', label: 'Pool (best available)' },
  ];

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

    container.appendChild(buildModeCard());
    container.appendChild(buildRulesCard());
    container.appendChild(buildTestCard());
  }

  function buildModeCard() {
    const card = ui.card('Routing Mode');
    card.id = 'card-routing-mode';

    const toggleRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:10px' });
    const toggleLabel = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;font-weight:600' });
    const toggleCb = ui.el('input', '', { id: 'routing-toggle', type: 'checkbox' });
    toggleCb.addEventListener('change', () => {
      if (toggleCb.checked) {
        api.routingEnable().then(() => { app.toast('Routing enabled'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.routingDisable().then(() => { app.toast('Routing disabled'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    toggleLabel.appendChild(toggleCb);
    toggleLabel.appendChild(ui.el('span', '', { text: 'Domain-based routing' }));
    toggleRow.appendChild(toggleLabel);

    const statusBadge = ui.el('span', '', { id: 'routing-status-badge', style: 'font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600' });
    toggleRow.appendChild(statusBadge);
    card.appendChild(toggleRow);

    const defaultRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:4px' });
    defaultRow.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-secondary)', text: 'Default route for unmatched domains:' }));
    const routeSelect = ui.el('select', '', { id: 'default-route-select', style: 'padding:3px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    populateRouteSelect(routeSelect);
    routeSelect.addEventListener('change', () => {
      api.routingSetDefault(routeSelect.value).then(() => app.toast('Default route updated')).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    defaultRow.appendChild(routeSelect);
    card.appendChild(defaultRow);

    const hint = ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-top:4px', text: 'When routing is OFF, all traffic follows the Proxy Control settings (direct mode or selected upstream).' });
    card.appendChild(hint);

    return card;
  }

  function buildRulesCard() {
    const card = ui.card('Active Routes');
    card.id = 'card-routing-rules';

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: '+ Add Route', style: 'margin-bottom:8px' });
    addBtn.addEventListener('click', () => showAddRouteModal());
    card.appendChild(addBtn);

    const tblWrap = ui.el('div', '', { id: 'routes-table-wrap', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No routes configured</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildTestCard() {
    const card = ui.card('Test Route');
    card.id = 'card-route-test';

    const row = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center' });
    const input = ui.el('input', '', { id: 'route-test-input', type: 'text', placeholder: 'e.g. twitter.com', style: 'flex:1;padding:6px 10px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    row.appendChild(input);

    const testBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: 'Test' });
    testBtn.addEventListener('click', () => {
      const domain = input.value.trim();
      if (!domain) return;
      testBtn.disabled = true;
      testBtn.textContent = 'Testing...';
      api.routingTest(domain).then(result => {
        testBtn.disabled = false;
        testBtn.textContent = 'Test';
        const resultEl = document.getElementById('route-test-result');
        if (resultEl) {
          const route = result.route || 'unknown';
          const matchedList = result.matched_list || null;
          resultEl.innerHTML = '';
          resultEl.innerHTML = ui.formatRouteLabel(route);
          const viaSpan = document.createElement('span');
          viaSpan.style.color = 'var(--text-secondary)';
          viaSpan.style.marginLeft = '6px';
          viaSpan.textContent = matchedList ? `(via list: ${matchedList})` : '(default route)';
          resultEl.appendChild(viaSpan);
        }
      }).catch(e => {
        testBtn.disabled = false;
        testBtn.textContent = 'Test';
        app.toast('Error: ' + e.message, 'error');
      });
    });
    row.appendChild(testBtn);
    card.appendChild(row);

    const result = ui.el('div', '', { id: 'route-test-result', style: 'margin-top:8px;font-size:13px;min-height:20px' });
    card.appendChild(result);

    return card;
  }

  function showAddRouteModal() {
    const unassigned = domainLists.filter(l => !l.route);
    if (!unassigned.length) {
      app.toast('Create a domain list first (Domain Lists page)', 'error');
      return;
    }

    const overlay = ui.el('div', '', { style: 'position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center' });
    const modal = ui.el('div', 'card', { style: 'width:400px;padding:20px' });
    modal.appendChild(ui.el('div', 'card-title', { text: 'Add Route', style: 'margin-bottom:12px' }));

    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'Domain List:' }));
    const listSelect = ui.el('select', '', { id: 'modal-list-select', style: 'width:100%;padding:6px 8px;margin-bottom:12px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    unassigned.forEach(dl => {
      const o = ui.el('option', '', { value: dl.id, text: dl.name + ' (' + (dl.domain_count || 0) + ' domains)' });
      listSelect.appendChild(o);
    });
    modal.appendChild(listSelect);

    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: 'Route:' }));
    const routeSelect = ui.el('select', '', { id: 'modal-route-select', style: 'width:100%;padding:6px 8px;margin-bottom:16px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    populateRouteSelect(routeSelect);
    modal.appendChild(routeSelect);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;justify-content:flex-end' });
    const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: 'Cancel' });
    cancelBtn.addEventListener('click', () => overlay.remove());
    btnRow.appendChild(cancelBtn);

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: 'Add Route' });
    addBtn.addEventListener('click', () => {
      const listId = listSelect.value;
      const route = routeSelect.value;
      if (!listId) return;
      const dl = domainLists.find(d => d.id === listId);
      if (dl) {
        const payload = { ...dl, route, enabled: true };
        api.domainListUpdate(dl.id, payload).then(() => {
          overlay.remove();
          app.toast('Route added');
          load();
        }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    btnRow.appendChild(addBtn);
    modal.appendChild(btnRow);

    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);
  }

  function updateModeCard(status) {
    const toggle = document.getElementById('routing-toggle');
    const badge = document.getElementById('routing-status-badge');
    const select = document.getElementById('default-route-select');

    if (toggle && status) toggle.checked = !!status.enabled;
    if (badge && status) {
      if (status.enabled) {
        badge.textContent = 'ON';
        badge.style.background = 'var(--success-bg)';
        badge.style.color = 'var(--success)';
      } else {
        badge.textContent = 'OFF';
        badge.style.background = 'var(--surface-raised)';
        badge.style.color = 'var(--text-muted)';
      }
    }
    if (select && status) {
      populateRouteSelect(select, status.default_route || 'direct');
    }
  }

  function updateRulesCard(status, lists) {
    const wrap = document.getElementById('routes-table-wrap');
    if (!wrap) return;

    const routedLists = (lists || []).filter(l => l.route);
    if (!routedLists.length) {
      wrap.innerHTML = '<div class="empty" style="padding:8px;font-size:11px">No routes configured. Add a route to assign domain lists to proxy routes.</div>';
      return;
    }

    const headers = [
      { label: '#', width: '30px', align: 'center' },
      { label: 'Domain List', width: '160px' },
      { label: 'Domains', width: '80px', align: 'center' },
      { label: 'Route', width: '120px' },
      { label: 'Enabled', width: '60px', align: 'center' },
      { label: '', width: '120px', align: 'center' },
    ];

    const rows = routedLists.map((l, i) => {
      const nameLink = document.createElement('a');
      nameLink.href = '#/domain-lists';
      nameLink.style.cssText = 'color:var(--accent);cursor:pointer;text-decoration:none';
      nameLink.textContent = l.name || l.id;
      const nameHtml = nameLink.outerHTML;

      const enabledHtml = l.enabled
        ? '<span style="color:var(--success)">✓</span>'
        : '<span style="color:var(--text-muted)">✗</span>';

      const actions = [];
      const toggleBtn = document.createElement('button');
      toggleBtn.className = 'btn btn-xs btn-ghost';
      toggleBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      toggleBtn.textContent = l.enabled ? 'Disable' : 'Enable';
      toggleBtn.dataset.listId = l.id;
      toggleBtn.dataset.action = 'toggle';
      actions.push(toggleBtn.outerHTML);

      if (i > 0) {
        const upBtn = document.createElement('button');
        upBtn.className = 'btn btn-xs btn-ghost';
        upBtn.style.cssText = 'padding:1px 4px;font-size:9px';
        upBtn.textContent = '↑';
        upBtn.dataset.listId = l.id;
        upBtn.dataset.action = 'move-up';
        actions.push(upBtn.outerHTML);
      }
      if (i < routedLists.length - 1) {
        const downBtn = document.createElement('button');
        downBtn.className = 'btn btn-xs btn-ghost';
        downBtn.style.cssText = 'padding:1px 4px;font-size:9px';
        downBtn.textContent = '↓';
        downBtn.dataset.listId = l.id;
        downBtn.dataset.action = 'move-down';
        actions.push(downBtn.outerHTML);
      }

      const delBtn = document.createElement('button');
      delBtn.className = 'btn btn-xs btn-danger';
      delBtn.style.cssText = 'padding:1px 4px;font-size:9px';
      delBtn.textContent = '✕';
      delBtn.dataset.listId = l.id;
      delBtn.dataset.action = 'remove';
      actions.push(delBtn.outerHTML);

      return [
        `<span style="color:var(--text-muted)">${i + 1}</span>`,
        nameHtml,
        (l.domain_count || 0),
        ui.formatRouteLabel(l.route),
        enabledHtml,
        actions.join(''),
      ];
    });
    wrap.innerHTML = '';
    wrap.appendChild(ui.table(headers, rows));

    wrap.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.listId;
        const action = btn.dataset.action;
        if (action === 'toggle') toggleRouteList(id);
        else if (action === 'move-up') moveRouteUp(id);
        else if (action === 'move-down') moveRouteDown(id);
        else if (action === 'remove') removeRoute(id);
      });
    });
  }

  function toggleRouteList(id) {
    api.domainListToggle(id).then(() => { app.toast('Toggled'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function moveRouteUp(id) {
    if (!routingStatus || !Array.isArray(routingStatus.lists)) return;
    const order = routingStatus.lists.filter(l => l.route).map(l => l.id);
    const idx = order.indexOf(id);
    if (idx <= 0) return;
    [order[idx - 1], order[idx]] = [order[idx], order[idx - 1]];
    api.routingReorder(order).then(() => { app.toast('Reordered'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function moveRouteDown(id) {
    if (!routingStatus || !Array.isArray(routingStatus.lists)) return;
    const order = routingStatus.lists.filter(l => l.route).map(l => l.id);
    const idx = order.indexOf(id);
    if (idx < 0 || idx >= order.length - 1) return;
    [order[idx], order[idx + 1]] = [order[idx + 1], order[idx]];
    api.routingReorder(order).then(() => { app.toast('Reordered'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function removeRoute(id) {
    const dl = domainLists.find(l => l.id === id);
    if (dl) {
      const payload = { ...dl, route: '', enabled: false };
      api.domainListUpdate(id, payload).then(() => { app.toast('Route removed'); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
    }
  }

  function populateRouteSelect(selectEl, selectedValue) {
    selectEl.innerHTML = '';
    ROUTE_OPTIONS.forEach(opt => {
      const o = ui.el('option', '', { value: opt.value, text: opt.label });
      if (opt.value === selectedValue) o.selected = true;
      selectEl.appendChild(o);
    });
    if (customProxies.length) {
      const grp = ui.el('optgroup', '', { label: 'Custom Proxies' });
      customProxies.filter(p => p.enabled).forEach(p => {
        const label = p.name + ' (' + p.protocol.toUpperCase() + ' ' + p.host + ':' + p.port + ')';
        const o = ui.el('option', '', { value: 'custom:' + p.id, text: label });
        if (('custom:' + p.id) === selectedValue) o.selected = true;
        grp.appendChild(o);
      });
      selectEl.appendChild(grp);
    }
  }

  build();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      let status = {}, lists = [], cpResult = [];
      try { status = await api.routingStatus(); } catch (e) { console.error('routingStatus', e); }
      try { lists = await api.domainLists(); } catch (e) { console.error('domainLists', e); }
      try { cpResult = await api.customProxies(); } catch (e) { console.error('customProxies', e); }
      routingStatus = status;
      domainLists = lists.lists || lists || [];
      customProxies = cpResult.proxies || cpResult || [];
      updateModeCard(status);
      updateRulesCard(status, domainLists);
      const defSelect = document.getElementById('default-route-select');
      if (defSelect) {
        populateRouteSelect(defSelect, status.default_route || 'direct');
      }
    } catch (e) {
      console.error('routes load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
