router.register('routes', (container) => {
  let routingStatus = null;
  let domainLists = [];
  let customProxies = [];
  let _loading = false;

  const ROUTE_OPTIONS = [
    { value: 'direct', labelKey: 'route.directNoProxy' },
    { value: 'pool', labelKey: 'route.poolBest' },
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

    container.appendChild(buildTopRow());
    container.appendChild(buildRulesCard());
  }

  function buildTopRow() {
    const row = ui.el('div', '', { style: 'display:flex;gap:10px;flex-shrink:0' });
    const modeCard = buildModeCard();
    modeCard.style.flex = '1';
    const testCard = buildTestCard();
    testCard.style.flex = '1';
    row.appendChild(modeCard);
    row.appendChild(testCard);
    return row;
  }

  function buildModeCard() {
    const card = ui.card(t('page.routes.routingMode'));
    card.id = 'card-routing-mode';

    const toggleRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;margin-bottom:10px' });
    const toggleLabel = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer;font-size:13px;font-weight:600' });
    const toggleCb = ui.el('input', '', { id: 'routing-toggle', type: 'checkbox' });
    toggleCb.addEventListener('change', () => {
      if (toggleCb.checked) {
        api.routingEnable().then(() => { app.toast(t('page.routes.routingEnabled')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      } else {
        api.routingDisable().then(() => { app.toast(t('page.routes.routingDisabled')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
      }
    });
    toggleLabel.appendChild(toggleCb);
    toggleLabel.appendChild(ui.el('span', '', { text: t('page.routes.domainBasedRouting') }));
    toggleRow.appendChild(toggleLabel);

    const statusBadge = ui.el('span', '', { id: 'routing-status-badge', style: 'font-size:11px;padding:2px 8px;border-radius:10px;font-weight:600' });
    toggleRow.appendChild(statusBadge);
    card.appendChild(toggleRow);

    const defaultRow = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;margin-bottom:4px' });
    defaultRow.appendChild(ui.el('span', '', { style: 'font-size:12px;color:var(--text-secondary)', text: t('page.routes.defaultRouteUnmatched') }));
    const routeSelect = ui.el('select', '', { id: 'default-route-select', style: 'padding:3px 8px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    populateRouteSelect(routeSelect);
    routeSelect.addEventListener('change', () => {
      api.routingSetDefault(routeSelect.value).then(() => app.toast('Default route updated')).catch(e => app.toast('Error: ' + e.message, 'error'));
    });
    defaultRow.appendChild(routeSelect);
    card.appendChild(defaultRow);

    const hint = ui.el('div', '', { style: 'font-size:11px;color:var(--text-muted);margin-top:4px', text: t('page.routes.routingOffHint') });
    card.appendChild(hint);

    return card;
  }

  function buildRulesCard() {
    const card = ui.card(t('page.routes.activeRoutes'));
    card.id = 'card-routing-rules';
    card.style.flex = '1';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.minHeight = '0';

    const headerRow = ui.el('div', '', { style: 'display:flex;align-items:center;justify-content:space-between;margin-bottom:10px' });
    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.routes.addRoute') });
    addBtn.addEventListener('click', () => showAddRouteModal());
    headerRow.appendChild(addBtn);
    const countBadge = ui.el('span', 'badge badge-gray', { id: 'route-count-badge', style: 'font-size:10px' });
    headerRow.appendChild(countBadge);
    card.appendChild(headerRow);

    const tblWrap = ui.el('div', '', { id: 'routes-table-wrap', style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.innerHTML = '<div class="empty" style="padding:12px;font-size:12px">' + t('page.routes.noRoutesAdd') + '</div>';
    card.appendChild(tblWrap);

    return card;
  }

  function buildTestCard() {
    const card = ui.card(t('page.routes.testRoute'));
    card.id = 'card-route-test';

    const row = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center;flex-wrap:wrap' });
    const input = ui.el('input', '', { id: 'route-test-input', type: 'text', placeholder: t('page.routes.testPlaceholder'), style: 'flex:1;min-width:120px;padding:5px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    row.appendChild(input);

    const testBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('common.test') });
    testBtn.addEventListener('click', () => {
      const domain = input.value.trim();
      if (!domain) return;
      testBtn.disabled = true;
      testBtn.textContent = '...';
      api.routingTest(domain).then(result => {
        testBtn.disabled = false;
        testBtn.textContent = t('common.test');
        const resultEl = document.getElementById('route-test-result');
        if (resultEl) {
          const route = result.route || 'unknown';
          const matchedList = result.matched_list || null;
          resultEl.innerHTML = ui.formatRouteLabel(route);
          const viaSpan = document.createElement('span');
          viaSpan.style.color = 'var(--text-secondary)';
          viaSpan.style.marginLeft = '6px';
          viaSpan.textContent = matchedList ? t('route.viaList', { name: matchedList }) : t('route.defaultRoute');
          resultEl.appendChild(viaSpan);
        }
      }).catch(e => {
        testBtn.disabled = false;
        testBtn.textContent = t('common.test');
        app.toast('Error: ' + e.message, 'error');
      });
    });
    row.appendChild(testBtn);

    const result = ui.el('span', '', { id: 'route-test-result', style: 'font-size:12px;min-height:18px;display:flex;align-items:center;gap:4px;flex-shrink:0' });
    row.appendChild(result);
    card.appendChild(row);

    return card;
  }

  function showAddRouteModal() {
    const unassigned = domainLists.filter(l => !l.route);
    if (!unassigned.length) {
      app.toast(t('page.routes.createDomainListFirst'), 'error');
      return;
    }

    const overlay = ui.el('div', '', { style: 'position:fixed;inset:0;background:rgba(0,0,0,0.4);z-index:1000;display:flex;align-items:center;justify-content:center' });
    const modal = ui.el('div', 'card', { style: 'width:400px;padding:20px' });
    modal.appendChild(ui.el('div', 'card-title', { text: t('page.routes.addRouteTitle'), style: 'margin-bottom:12px' }));

    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.routes.domainList') }));
    const listSelect = ui.el('select', '', { id: 'modal-list-select', style: 'width:100%;padding:6px 8px;margin-bottom:12px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    unassigned.forEach(dl => {
      const o = ui.el('option', '', { value: dl.id, text: dl.name + ' (' + (dl.domain_count || 0) + ' domains)' });
      listSelect.appendChild(o);
    });
    modal.appendChild(listSelect);

    modal.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: t('page.routes.route') }));
    const routeSelect = ui.el('select', '', { id: 'modal-route-select', style: 'width:100%;padding:6px 8px;margin-bottom:16px;font-size:13px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    populateRouteSelect(routeSelect);
    modal.appendChild(routeSelect);

    const btnRow = ui.el('div', '', { style: 'display:flex;gap:8px;justify-content:flex-end' });
    const cancelBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('page.routes.cancel') });
    cancelBtn.addEventListener('click', () => overlay.remove());
    btnRow.appendChild(cancelBtn);

    const addBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.routes.addRoute') });
    addBtn.addEventListener('click', () => {
      const listId = listSelect.value;
      const route = routeSelect.value;
      if (!listId) return;
      const dl = domainLists.find(d => d.id === listId);
      if (dl) {
        const payload = { ...dl, route, enabled: true };
        api.domainListUpdate(dl.id, payload).then(() => {
          overlay.remove();
          app.toast(t('page.routes.routeAdded'));
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

  function routeTypeOf(route) {
    if (!route) return 'unknown';
    if (route === 'direct') return 'direct';
    if (route === 'pool') return 'pool';
    if (route.startsWith('custom:')) return 'custom';
    if (route.startsWith('proxy:')) return 'proxy';
    return 'unknown';
  }

  function routeIconHtml(type) {
    if (type === 'direct') return '◆';
    if (type === 'pool') return '◈';
    if (type === 'custom') return '◉';
    if (type === 'proxy') return '◉';
    return '•';
  }

  function routeLabelHtml(route) {
    const type = routeTypeOf(route);
    if (type === 'direct') return '<span class="route-label direct">' + t('route.direct') + '</span>';
    if (type === 'pool') return '<span class="route-label pool">' + t('route.pool') + '</span>';
    if (type === 'custom') {
      const name = route.slice(7);
      return '<span class="route-label custom">' + t('route.custom', { name: ui.escHtml(name) }) + '</span>';
    }
    if (type === 'proxy') return '<span class="route-label custom">' + ui.escHtml(route) + '</span>';
    return '<span class="route-label">' + ui.escHtml(route || '—') + '</span>';
  }

  function updateRulesCard(status, lists) {
    const wrap = document.getElementById('routes-table-wrap');
    const countBadge = document.getElementById('route-count-badge');
    if (!wrap) return;

    const routedLists = (lists || []).filter(l => l.route);
    if (countBadge) countBadge.textContent = routedLists.length;

    if (!routedLists.length) {
      wrap.innerHTML = '<div class="empty" style="padding:12px;font-size:12px">' + t('page.routes.noRoutesAdd') + '</div>';
      return;
    }

    wrap.innerHTML = '';
    const listEl = ui.el('div', 'route-list');

    routedLists.forEach((l, i) => {
      const type = routeTypeOf(l.route);
      const enabled = !!l.enabled;

      const row = ui.el('div', 'route-row' + (enabled ? '' : ' disabled'));
      row.dataset.type = type;
      row.dataset.listId = l.id;

      // Priority badge
      const prioClass = i === 0 ? 'p1' : i === 1 ? 'p2' : i === 2 ? 'p3' : 'p4-plus';
      const prio = ui.el('div', 'route-priority ' + prioClass, { text: String(i + 1) });
      row.appendChild(prio);

      // Type icon
      const icon = ui.el('div', 'route-type-icon ' + type, { text: routeIconHtml(type) });
      row.appendChild(icon);

      // Body: name + meta
      const body = ui.el('div', 'route-body');
      const nameLink = document.createElement('a');
      nameLink.href = '#/domain-lists';
      nameLink.textContent = l.name || l.id;
      const nameDiv = ui.el('div', 'route-name');
      nameDiv.appendChild(nameLink);
      body.appendChild(nameDiv);

      const meta = ui.el('div', 'route-meta');
      const countPill = ui.el('span', 'route-domain-count', { text: ui.fmtNum(l.domain_count || 0) + ' ' + t('common.domains') });
      meta.appendChild(countPill);
      if (l.source === 'manual') {
        const srcBadge = ui.el('span', 'badge badge-gray', { text: 'manual', style: 'font-size:9px' });
        meta.appendChild(srcBadge);
      }
      body.appendChild(meta);
      row.appendChild(body);

      // Route label
      const labelWrap = ui.el('div', '', { html: routeLabelHtml(l.route) });
      row.appendChild(labelWrap);

      // Toggle switch
      const toggle = ui.el('div', 'route-toggle' + (enabled ? ' on' : ''));
      toggle.title = enabled ? t('common.disable') : t('common.enable');
      toggle.addEventListener('click', () => toggleRouteList(l.id));
      row.appendChild(toggle);

      // Reorder arrows
      const reorder = ui.el('div', 'route-reorder');
      const upBtn = ui.el('button', 'route-arrow', { html: '▲', title: t('common.moveUp') });
      upBtn.disabled = (i === 0);
      upBtn.addEventListener('click', () => moveRouteUpAnimated(l.id, row, 'up'));
      reorder.appendChild(upBtn);

      const downBtn = ui.el('button', 'route-arrow', { html: '▼', title: t('common.moveDown') });
      downBtn.disabled = (i === routedLists.length - 1);
      downBtn.addEventListener('click', () => moveRouteUpAnimated(l.id, row, 'down'));
      reorder.appendChild(downBtn);
      row.appendChild(reorder);

      // Delete
      const delBtn = ui.el('button', 'route-delete', { html: '✕', title: t('common.delete') });
      delBtn.addEventListener('click', () => removeRoute(l.id));
      row.appendChild(delBtn);

      // Drag handle
      const dragHandle = ui.el('div', 'route-drag-handle', { text: '⋮⋮', title: t('common.moveUp') });
      row.appendChild(dragHandle);

      attachDragHandlers(row, listEl);

      listEl.appendChild(row);
    });

    wrap.appendChild(listEl);

    listEl.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
    });
    listEl.addEventListener('drop', (e) => {
      e.preventDefault();
      if (!_draggedRow) return;
      // dropped on empty area of the list (not on a row)
      if (e.target === listEl) {
        const rows = Array.from(listEl.querySelectorAll('.route-row'));
        const lastRow = rows[rows.length - 1];
        if (lastRow) performDrop(listEl, _draggedRow, lastRow, false);
      }
    });
  }

  let _draggedRow = null;
  let _placeholder = null;
  let _dropTimer = null;

  function ensurePlaceholder(listEl) {
    if (!_placeholder || !_placeholder.parentNode) {
      _placeholder = ui.el('div', 'route-drop-placeholder');
    }
    if (_placeholder.parentNode !== listEl) {
      listEl.appendChild(_placeholder);
    }
    return _placeholder;
  }

  function attachDragHandlers(row, listEl) {
    const handle = row.querySelector('.route-drag-handle');
    if (!handle) return;

    row.draggable = false;

    handle.addEventListener('mousedown', () => { row.draggable = true; });
    row.addEventListener('dragend', () => { row.draggable = false; });

    row.addEventListener('dragstart', (e) => {
      _draggedRow = row;
      row.classList.add('dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', row.dataset.listId);
      const ghost = document.createElement('div');
      ghost.style.cssText = 'position:absolute;top:-9999px;width:1px;height:1px';
      document.body.appendChild(ghost);
      e.dataTransfer.setDragImage(ghost, 0, 0);
      setTimeout(() => ghost.remove(), 0);
      hidePlaceholder();
    });

    row.addEventListener('dragend', () => {
      row.classList.remove('dragging');
      row.draggable = false;
      _draggedRow = null;
      hidePlaceholder();
    });

    row.addEventListener('dragover', (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      if (!_draggedRow || _draggedRow === row) return;

      const rect = row.getBoundingClientRect();
      const midpoint = rect.top + rect.height / 2;
      const insertBefore = e.clientY < midpoint;

      movePlaceholder(listEl, row, insertBefore);
    });

    row.addEventListener('drop', (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (!_draggedRow || _draggedRow === row) return;
      const rect = row.getBoundingClientRect();
      const midpoint = rect.top + rect.height / 2;
      const insertBefore = e.clientY < midpoint;
      performDrop(listEl, _draggedRow, row, insertBefore);
    });
  }

  function hidePlaceholder() {
    if (!_placeholder) return;
    _placeholder.classList.remove('active');
    if (_placeholder.parentNode) _placeholder.parentNode.removeChild(_placeholder);
  }

  function movePlaceholder(listEl, refRow, insertBefore) {
    const ph = ensurePlaceholder(listEl);

    // already in the right spot?
    const prev = insertBefore ? refRow.previousSibling : (refRow.nextSibling && refRow.nextSibling !== ph ? refRow.nextSibling : null);
    if (ph === refRow.previousSibling && insertBefore) return;
    if (ph === refRow.nextSibling && !insertBefore) return;

    if (insertBefore) {
      listEl.insertBefore(ph, refRow);
    } else {
      const next = refRow.nextSibling;
      if (next && next !== ph) listEl.insertBefore(ph, next);
      else if (next === ph) { /* already after */ }
      else listEl.appendChild(ph);
    }

    requestAnimationFrame(() => ph.classList.add('active'));
  }

  function performDrop(listEl, draggedRow, refRow, insertBefore) {
    const rows = Array.from(listEl.querySelectorAll('.route-row'));
    const currentOrder = rows.map(r => r.dataset.listId);

    const draggedId = draggedRow.dataset.listId;
    const refId = refRow.dataset.listId;

    const order = currentOrder.filter(id => id !== draggedId);
    const refIdx = order.indexOf(refId);
    if (refIdx < 0) { hidePlaceholder(); return; }

    if (insertBefore) {
      order.splice(refIdx, 0, draggedId);
    } else {
      order.splice(refIdx + 1, 0, draggedId);
    }

    hidePlaceholder();
    api.routingReorder(order).then(() => { app.toast(t('page.routes.reordered')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function toggleRouteList(id) {
    api.domainListToggle(id).then(() => { app.toast(t('page.routes.toggled')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function getRoutedOrder() {
    if (!routingStatus || !Array.isArray(routingStatus.lists)) return [];
    return routingStatus.lists.filter(l => l.route).map(l => l.id);
  }

  function moveRouteUpAnimated(id, rowEl, dir) {
    const order = getRoutedOrder();
    const idx = order.indexOf(id);
    if (dir === 'up') {
      if (idx <= 0) return;
      [order[idx - 1], order[idx]] = [order[idx], order[idx - 1]];
    } else {
      if (idx < 0 || idx >= order.length - 1) return;
      [order[idx], order[idx + 1]] = [order[idx + 1], order[idx]];
    }
    const animClass = dir === 'up' ? 'moving-up' : 'moving-down';
    if (rowEl) rowEl.classList.add(animClass);
    const delay = rowEl ? 250 : 0;
    setTimeout(() => {
      api.routingReorder(order).then(() => { app.toast(t('page.routes.reordered')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
    }, delay);
  }

  function moveRouteUp(id) {
    moveRouteUpAnimated(id, null, 'up');
  }

  function moveRouteDown(id) {
    moveRouteUpAnimated(id, null, 'down');
  }

  function removeRoute(id) {
    const dl = domainLists.find(l => l.id === id);
    if (dl) {
      const payload = { ...dl, route: '', enabled: false };
      api.domainListUpdate(id, payload).then(() => { app.toast(t('page.routes.routeRemoved')); load(); }).catch(e => app.toast('Error: ' + e.message, 'error'));
    }
  }

  function populateRouteSelect(selectEl, selectedValue) {
    selectEl.innerHTML = '';
    ROUTE_OPTIONS.forEach(opt => {
      const o = ui.el('option', '', { value: opt.value, text: t(opt.labelKey) });
      if (opt.value === selectedValue) o.selected = true;
      selectEl.appendChild(o);
    });
    if (customProxies.length) {
      const grp = ui.el('optgroup', '', { label: t('route.customProxies') });
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
