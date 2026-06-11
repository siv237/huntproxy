router.register('blacklist', (container) => {
  let state = {
    page: 1,
    limit: 20,
    blacklist: [],
    total: 0,
    search: '',
    sortKey: 'address',
    sortDir: 1,
  };

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });
    const search = ui.el('input', '', { type: 'text', placeholder: t('page.blacklist.searchPlaceholder'), value: state.search, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:200px' });
    search.addEventListener('input', (e) => {
      state.search = e.target.value.toLowerCase();
      state.page = 1;
      load();
    });
    filterBar.appendChild(search);

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const refreshBtn = ui.el('button', 'btn btn-secondary', { text: t('common.refresh') });
    refreshBtn.addEventListener('click', () => load());
    filterBar.appendChild(refreshBtn);

    const addBtn = ui.el('button', 'btn btn-primary', { html: '<svg width="14" height="14"><use href="#icon-plus"/></svg> ' + t('common.add') });
    addBtn.addEventListener('click', () => {
      const addr = prompt(t('page.blacklist.proxyAddress'));
      if (addr) blAdd(addr, prompt(t('page.blacklist.reasonOptional')) || 'manual');
    });
    filterBar.appendChild(addBtn);

    container.appendChild(filterBar);

    const card = ui.card(t('page.blacklist.title'));
    card.id = 'blacklist-table-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    container.appendChild(card);

    const pagWrap = ui.el('div', '', { style: 'display:flex;justify-content:space-between;align-items:center;flex-shrink:0' });
    const left = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)' });
    left.id = 'bl-pag-info';
    pagWrap.appendChild(left);

    const right = ui.el('div', '', { style: 'display:flex;gap:4px' });
    const prev = ui.el('button', 'btn btn-sm btn-secondary', { text: t('common.previous') });
    prev.addEventListener('click', () => { if (state.page > 1) { state.page--; load(); } });
    right.appendChild(prev);

    const pages = ui.el('div', '', { style: 'display:flex;gap:4px', id: 'bl-page-btns' });
    right.appendChild(pages);

    const next = ui.el('button', 'btn btn-sm btn-secondary', { text: t('common.next') });
    next.addEventListener('click', () => { state.page++; load(); });
    right.appendChild(next);
    pagWrap.appendChild(right);
    container.appendChild(pagWrap);
  }

  build();

  async function load() {
    try {
      const params = { page: state.page, limit: state.limit };
      const data = await api.blacklist(params);
      state.blacklist = data.blacklist || [];
      state.total = data.total || 0;
      renderTable();
      renderPagination();
    } catch (e) {
      console.error('blacklist load', e);
      app.toast(t('page.blacklist.failedToLoad'), 'error');
    }
  }

  function setSort(key) {
    if (state.sortKey === key) state.sortDir *= -1;
    else { state.sortKey = key; state.sortDir = 1; }
    renderTable();
  }

  function renderTable() {
    const card = document.getElementById('blacklist-table-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.blacklist.title') }));
    card.appendChild(header);

    let rows = state.blacklist;
    if (state.search) {
      rows = rows.filter(r =>
        (r.address || '').toLowerCase().includes(state.search) ||
        (r.reason || '').toLowerCase().includes(state.search)
      );
    }

    rows = rows.slice().sort((a, b) => ui.sortValue(a, b, state.sortKey, state.sortDir));

    if (!rows.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.blacklist.noBlacklisted') }));
      return;
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.sortKey, state.sortDir) : ''), width, align, sortKey: key, onSort: key ? () => setSort(key) : undefined });
    const headers = [
      h('Proxy', 'address', null, 'left'),
      h('Country', 'country', '120px', 'left'),
      h('Reason', 'reason', '150px', 'left'),
      h('Score', 'score', '60px', 'right'),
      h('', null, '80px', 'center'),
    ];
    const bodyRows = rows.map(b => [
      `<span class="addr">${b.address}</span>`,
      `${ui.escHtml(b.country || '—')}`,
      `<span style="color:var(--danger)">${b.reason || '—'}</span>`,
      Math.round(b.score || 0),
      `<button class="btn btn-xs btn-secondary" onclick="blRemove('${b.address}')">${t('common.remove')}</button>`,
    ]);
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, bodyRows));
    card.appendChild(tblWrap);
  }

  function renderPagination() {
    const info = document.getElementById('bl-pag-info');
      if (info) info.textContent = t('page.blacklist.showing', {from: (state.page - 1) * state.limit + 1, to: Math.min(state.page * state.limit, state.total), total: state.total});

    const btns = document.getElementById('bl-page-btns');
    if (!btns) return;
    btns.innerHTML = '';
    const totalPages = Math.ceil(state.total / state.limit) || 1;
    const start = Math.max(1, state.page - 2);
    const end = Math.min(totalPages, start + 4);
    for (let i = start; i <= end; i++) {
      const b = ui.el('button', `btn btn-sm ${i === state.page ? 'btn-primary' : 'btn-secondary'}`, { text: i.toString() });
      b.addEventListener('click', () => { state.page = i; load(); });
      btns.appendChild(b);
    }
  }

  async function blAdd(addr, reason) {
    try {
      await api.blAdd(addr, reason);
      app.toast(t('page.blacklist.addedToBlacklist'));
      load();
    } catch (e) {
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  async function blRemove(addr) {
    try {
      await api.blRemove(addr);
      app.toast(t('page.blacklist.removedFromBlacklist'));
      load();
    } catch (e) {
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  load();
  const id = setInterval(load, 10000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});

window.blAdd = async function(addr, reason) {
  try {
    await api.blAdd(addr, reason || 'manual');
    app.toast(t('page.blacklist.addedToBlacklist'));
    if (router.current === 'blacklist') router.resolve();
    else if (router.current === 'proxies') router.resolve();
  } catch (e) {
    app.toast(t('common.error', {message: e.message}), 'error');
  }
};

window.blRemove = async function(addr) {
  try {
    await api.blRemove(addr);
    app.toast(t('page.blacklist.removedFromBlacklist'));
  } catch (e) {
    app.toast(t('common.error', {message: e.message}), 'error');
  }
};
