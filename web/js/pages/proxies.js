router.register('proxies', (container) => {
  let state = {
    status: '', // all, alive, dead, blacklisted
    page: 1,
    limit: 20,
    proxies: [],
    total: 0,
    search: '',
    sortKey: 'score',
    sortDir: -1,
  };

  function build() {
    container.innerHTML = '';

    // Filter bar
    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px' });
    const tabs = ['All', 'Alive', 'Dead', 'Blacklisted'];
    tabs.forEach(t => {
      const btn = ui.el('button', `btn ${state.status === t.toLowerCase() || (t === 'All' && !state.status) ? 'btn-primary' : 'btn-secondary'}`, { text: t });
      btn.addEventListener('click', () => {
        state.status = t === 'All' ? '' : t.toLowerCase();
        state.page = 1;
        load();
      });
      filterBar.appendChild(btn);
    });

    const search = ui.el('input', '', { type: 'text', placeholder: 'Search proxy...', value: state.search, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:180px' });
    search.addEventListener('input', (e) => {
      state.search = e.target.value.toLowerCase();
      state.page = 1;
      load();
    });
    filterBar.appendChild(search);

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));
    const refreshBtn = ui.el('button', 'btn btn-secondary', { html: '<svg width="14" height="14"><use href="#icon-proxies"/></svg> Refresh' });
    refreshBtn.addEventListener('click', () => load());
    filterBar.appendChild(refreshBtn);

    const exportBtn = ui.el('button', 'btn btn-secondary', { html: '<svg width="14" height="14"><use href="#icon-downloads"/></svg> Export' });
    exportBtn.addEventListener('click', () => api.exportProxies().then(() => app.toast('Exported')));
    filterBar.appendChild(exportBtn);

    container.appendChild(filterBar);

    // Table card
    const card = ui.card('Proxies');
    card.id = 'proxies-table-card';
    container.appendChild(card);

    // Pagination
    const pagWrap = ui.el('div', '', { style: 'display:flex;justify-content:space-between;align-items:center;margin-top:12px' });
    const left = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)' });
    left.id = 'proxies-pag-info';
    pagWrap.appendChild(left);

    const right = ui.el('div', '', { style: 'display:flex;gap:4px' });
    const prev = ui.el('button', 'btn btn-sm btn-secondary', { text: 'Previous' });
    prev.addEventListener('click', () => { if (state.page > 1) { state.page--; load(); } });
    right.appendChild(prev);

    const pages = ui.el('div', '', { style: 'display:flex;gap:4px', id: 'proxies-page-btns' });
    right.appendChild(pages);

    const next = ui.el('button', 'btn btn-sm btn-secondary', { text: 'Next' });
    next.addEventListener('click', () => { state.page++; load(); });
    right.appendChild(next);
    pagWrap.appendChild(right);
    container.appendChild(pagWrap);
  }

  build();

  async function load() {
    try {
      const params = { status: state.status, page: state.page, limit: state.limit };
      const data = await api.proxies(params);
      state.proxies = data.proxies || [];
      state.total = data.total || 0;
      renderTable();
      renderPagination();
    } catch (e) {
      console.error('proxies load', e);
      app.toast('Failed to load proxies', 'error');
    }
  }

  function setSort(key) {
    if (state.sortKey === key) state.sortDir *= -1;
    else { state.sortKey = key; state.sortDir = -1; }
    renderTable();
  }

  function renderTable() {
    const card = document.getElementById('proxies-table-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: 'Proxies' }));
    card.appendChild(header);

    let rows = state.proxies;
    if (state.search) {
      rows = rows.filter(r =>
        (r.address || '').toLowerCase().includes(state.search) ||
        (r.country || '').toLowerCase().includes(state.search)
      );
    }

    rows = rows.slice().sort((a, b) => ui.sortValue(a, b, state.sortKey, state.sortDir));

    if (!rows.length) {
      card.appendChild(ui.el('div', 'empty', { text: 'No proxies found' }));
      return;
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.sortKey, state.sortDir) : ''), width, align, sortKey: key, onSort: key ? () => setSort(key) : undefined });
    const headers = [
      h('#', null, '30px', 'center'),
      h('Proxy', 'address', null, 'left'),
      h('Country', 'country', '120px', 'left'),
      h('Type', 'protocol', '60px', 'center'),
      h('Latency', 'last_latency', '70px', 'right'),
      h('Score', 'score', '50px', 'right'),
      h('Status', 'last_status', '70px', 'center'),
      h('Last Check', 'last_check', '80px', 'right'),
      h('', null, '60px', 'center'),
    ];
    const bodyRows = rows.map((p, i) => {
      const idx = (state.page - 1) * state.limit + i + 1;
      const statusBadge = p.in_blacklist ? ui.badge('Blacklisted', 'red') :
        p.last_status === 'ok' ? ui.badge('Alive', 'green') : ui.badge('Dead', 'red');
      return [
        `<span style="color:var(--text-muted)">${idx}</span>`,
        `<span class="addr" onclick="router.navigate('proxy-detail/${encodeURIComponent(p.address)}')">${p.address}</span>`,
        `${ui.flag(p.country_code)} ${p.country || 'Unknown'}`,
        (p.protocol || 'http').toUpperCase(),
        ui.fmtLatency(p.last_latency),
        Math.round(p.score),
        statusBadge.outerHTML,
        ui.ago(p.last_check),
        `<button class="btn btn-xs btn-danger" onclick="blAdd('${p.address}')">BL</button>`,
      ];
    });
    card.appendChild(ui.table(headers, bodyRows));
  }

  function renderPagination() {
    const info = document.getElementById('proxies-pag-info');
    if (info) info.textContent = `Showing ${(state.page - 1) * state.limit + 1} to ${Math.min(state.page * state.limit, state.total)} of ${state.total} proxies`;

    const btns = document.getElementById('proxies-page-btns');
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

  async function blAdd(addr) {
    try {
      await api.blAdd(addr, 'manual');
      app.toast('Added to blacklist');
      load();
    } catch (e) {
      app.toast('Error: ' + e.message, 'error');
    }
  }

  load();
  const id = setInterval(load, 10000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
