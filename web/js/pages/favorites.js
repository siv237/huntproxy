router.register('favorites', (container) => {
  let state = {
    favorites: [],
    search: '',
    sortKey: 'score',
    sortDir: -1,
  };

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });
    const search = ui.el('input', '', { type: 'text', placeholder: t('page.favorites.searchPlaceholder'), value: state.search, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:200px' });
    search.addEventListener('input', (e) => {
      state.search = e.target.value.toLowerCase();
      renderTable();
    });
    filterBar.appendChild(search);

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const count = ui.el('div', '', { id: 'fav-count', style: 'font-size:12px;color:var(--text-secondary)' });
    filterBar.appendChild(count);

    const refreshBtn = ui.el('button', 'btn btn-secondary', { text: t('common.refresh') });
    refreshBtn.addEventListener('click', () => load());
    filterBar.appendChild(refreshBtn);

    container.appendChild(filterBar);

    const card = ui.card(t('page.favorites.title'));
    card.id = 'favorites-table-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'hidden';
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    container.appendChild(card);
  }

  build();

  async function load() {
    try {
      const data = await api.favorites();
      state.favorites = data || [];
      renderTable();
    } catch (e) {
      console.error('favorites load', e);
      app.toast(t('common.error', {message: e.message}), 'error');
    }
  }

  function setSort(key) {
    if (state.sortKey === key) state.sortDir *= -1;
    else { state.sortKey = key; state.sortDir = 1; }
    renderTable();
  }

  function renderTable() {
    const card = document.getElementById('favorites-table-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.favorites.title') }));
    card.appendChild(header);

    let rows = state.favorites;
    if (state.search) {
      rows = rows.filter(p =>
        (p.address || '').toLowerCase().includes(state.search) ||
        (p.country || '').toLowerCase().includes(state.search)
      );
    }

    const count = document.getElementById('fav-count');
    if (count) count.textContent = t('page.favorites.count', {count: rows.length});

    rows = rows.slice().sort((a, b) => ui.sortValue(a, b, state.sortKey, state.sortDir));

    if (!rows.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.favorites.empty') }));
      return;
    }

    const h = (label, key, width, align) => ({ label: label + (key ? ui.sortArrow(key, state.sortKey, state.sortDir) : ''), width, align, sortKey: key, onSort: key ? () => setSort(key) : undefined });
    const headers = [
      h('Proxy', 'address', null, 'left'),
      h('Country', 'country', '110px', 'left'),
      h('Proto', null, '50px', 'center'),
      h('Lat', 'last_latency', '50px', 'right'),
      h('Speed', 'speed_avg', '55px', 'right'),
      h('Succ', 'success_rate', '40px', 'right'),
      h('Score', 'score', '40px', 'right'),
      h('Status', null, '50px', 'center'),
      h('Last', 'last_check', '55px', 'right'),
      h('', null, '28px', 'center'),
    ];
    const bodyRows = rows.map(p => {
      const statusColor = p.in_blacklist ? 'var(--danger)' : p.last_status === 'ok' ? 'var(--success)' : 'var(--danger)';
      const statusText = p.in_blacklist ? 'BL' : p.last_status === 'ok' ? 'OK' : 'FAIL';
      const proto = (p.protocol || 'http').toUpperCase();
      const lat = p.last_latency != null ? (p.last_latency < 1 ? (p.last_latency * 1000).toFixed(0) + 'ms' : p.last_latency.toFixed(2) + 's') : '—';
      const speed = p.speed_avg ? p.speed_avg.toFixed(0) + 'KB/s' : '—';
      const succ = p.success_rate != null ? (p.success_rate * 100).toFixed(0) + '%' : '—';
      const score = Math.round(p.score || 0);
      const flag = ui.flag(p.country_code);
      return [
        `<span class="proxy-address-link" data-card-addr="${ui.escHtml(p.address)}" style="font-size:12px;font-family:monospace;color:var(--text-primary);cursor:pointer;text-decoration:underline dotted;text-underline-offset:2px">${ui.escHtml(p.address)}</span>`,
        `<span style="font-size:12px">${flag} ${ui.escHtml(p.country || '—')}</span>`,
        `<span style="font-size:11px;color:var(--text-muted)">${proto}</span>`,
        `<span style="font-size:11px">${lat}</span>`,
        `<span style="font-size:11px">${speed}</span>`,
        `<span style="font-size:11px">${succ}</span>`,
        `<span style="font-size:11px;font-weight:600">${score}</span>`,
        `<span style="color:${statusColor};font-weight:600;font-size:11px">${statusText}</span>`,
        `<span style="font-size:11px;color:var(--text-muted)">${ui.ago(p.last_check)}</span>`,
        `<button class="btn btn-xs btn-secondary" data-fav-remove="${ui.escHtml(p.address)}" style="padding:1px 4px;font-size:9px;color:var(--warning)" title="${t('proxyCard.removedFromFavorites')}"><svg width="12" height="12"><use href="#icon-star"/></svg></button>`,
      ];
    });
    const tblWrap = ui.el('div', 'table-wrap', { style: 'flex:1;min-height:0;overflow-y:auto' });
    tblWrap.appendChild(ui.table(headers, bodyRows));
    card.appendChild(tblWrap);

    tblWrap.querySelectorAll('[data-card-addr]').forEach(el => {
      el.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = el.dataset.cardAddr;
        if (addr && window.proxyCard) window.proxyCard.show(addr);
      });
    });
    tblWrap.querySelectorAll('[data-fav-remove]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const addr = btn.dataset.favRemove;
        api.favRemove(addr).then(() => {
          app.toast(t('proxyCard.removedFromFavorites'));
          load();
        }).catch(err => app.toast(t('common.error', {message: err.message}), 'error'));
      });
    });
  }

  load();
  const id = setInterval(load, 10000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
