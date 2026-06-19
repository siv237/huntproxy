router.register('logs', (container) => {
  let state = {
    events: [],
    filter: '',
    type: 'all',
    reverse: true,
    autoScroll: true,
  };

  const TYPE_FILTERS = [
    { label: 'page.logs.all', value: 'all' },
    { label: 'page.logs.typeInfo', value: 'info' },
    { label: 'page.logs.typeWarn', value: 'warn' },
    { label: 'page.logs.typeError', value: 'error' },
    { label: 'page.logs.typeOk', value: 'ok' },
    { label: 'page.logs.typeProgress', value: 'progress' },
    { label: 'page.logs.typeBlacklist', value: 'blacklist' },
    { label: 'page.logs.typePhase', value: 'phase' },
  ];

  const TYPE_COLORS = {
    info: 'var(--info)',
    warn: 'var(--warning)',
    error: 'var(--danger)',
    ok: 'var(--success)',
    progress: 'var(--text-secondary)',
    blacklist: 'var(--danger)',
    phase: 'var(--info)',
  };

  function fmtTime(ts) {
    const d = new Date(ts * 1000);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });
    const search = ui.el('input', '', { type: 'text', placeholder: t('page.logs.filterPlaceholder'), value: state.filter, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:220px' });
    search.addEventListener('input', (e) => {
      state.filter = e.target.value.toLowerCase();
      render();
    });
    filterBar.appendChild(search);

    TYPE_FILTERS.forEach(f => {
      const btn = ui.el('button', `btn btn-sm ${state.type === f.value ? 'btn-primary' : 'btn-secondary'}`, { text: t(f.label) });
      btn.addEventListener('click', () => {
        state.type = f.value;
        filterBar.querySelectorAll('button').forEach((b, i) => {
          if (i < TYPE_FILTERS.length) b.className = `btn btn-sm ${state.type === TYPE_FILTERS[i].value ? 'btn-primary' : 'btn-secondary'}`;
        });
        render();
      });
      filterBar.appendChild(btn);
    });

    const reverseBtn = ui.el('button', `btn btn-sm ${state.reverse ? 'btn-primary' : 'btn-secondary'}`, { text: t('page.logs.reverse') });
    reverseBtn.addEventListener('click', () => {
      state.reverse = !state.reverse;
      reverseBtn.className = `btn btn-sm ${state.reverse ? 'btn-primary' : 'btn-secondary'}`;
      render();
    });
    filterBar.appendChild(reverseBtn);

    const autoScrollBtn = ui.el('button', `btn btn-sm ${state.autoScroll ? 'btn-primary' : 'btn-secondary'}`, { text: t('page.logs.autoScroll') });
    autoScrollBtn.addEventListener('click', () => {
      state.autoScroll = !state.autoScroll;
      autoScrollBtn.className = `btn btn-sm ${state.autoScroll ? 'btn-primary' : 'btn-secondary'}`;
    });
    filterBar.appendChild(autoScrollBtn);

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const liveBtn = ui.el('button', 'btn btn-secondary', { text: t('page.logs.live') });
    let liveInterval = null;
    liveBtn.addEventListener('click', () => {
      if (liveInterval) {
        clearInterval(liveInterval);
        liveInterval = null;
        liveBtn.textContent = t('page.logs.live');
        liveBtn.className = 'btn btn-secondary';
      } else {
        load();
        liveInterval = setInterval(load, 3000);
        liveBtn.textContent = t('page.logs.stopLive');
        liveBtn.className = 'btn btn-primary';
      }
    });
    filterBar.appendChild(liveBtn);

    const clearBtn = ui.el('button', 'btn btn-secondary', { text: t('page.logs.clear') });
    clearBtn.addEventListener('click', () => { state.events = []; render(); });
    filterBar.appendChild(clearBtn);

    container.appendChild(filterBar);

    const card = ui.card(t('page.logs.systemLogs'));
    card.id = 'logs-card';
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
      const params = { limit: 500 };
      if (state.type !== 'all') params.type = state.type;
      const data = await api.logs(params);
      state.events = data.events || [];
      render();
    } catch (e) {
      console.error('logs load', e);
    }
  }

  function render() {
    const card = document.getElementById('logs-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.logs.systemLogs') }));
    const count = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: t('page.logs.lines', { count: state.events.length }) });
    header.appendChild(count);
    card.appendChild(header);

    let events = state.events;
    if (state.filter) {
      events = events.filter(e => e.msg.toLowerCase().includes(state.filter));
    }

    if (!events.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.logs.noMatching') }));
      return;
    }

    const display = state.reverse ? events : events.slice().reverse();
    const wrap = ui.el('div', '', { id: 'logs-lines-wrap', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:1.6;flex:1;min-height:0;overflow-y:auto' });
    display.forEach(ev => {
      const row = ui.el('div', '', { style: 'padding:2px 0;border-bottom:1px solid var(--border-subtle);white-space:pre-wrap;word-break:break-all;display:flex;gap:8px' });
      const timeEl = ui.el('span', '', { text: fmtTime(ev.ts), style: 'color:var(--text-muted);flex-shrink:0' });
      row.appendChild(timeEl);
      const typeEl = ui.el('span', '', { text: ev.type.toUpperCase(), style: `color:${TYPE_COLORS[ev.type] || 'var(--text-primary)'};flex-shrink:0;font-weight:600;min-width:70px` });
      row.appendChild(typeEl);
      const msgEl = ui.el('span', '', { text: ev.msg, style: `color:${TYPE_COLORS[ev.type] || 'var(--text-primary)'}` });
      row.appendChild(msgEl);
      wrap.appendChild(row);
    });
    card.appendChild(wrap);
    if (state.reverse && state.autoScroll) {
      requestAnimationFrame(() => { wrap.scrollTop = wrap.scrollHeight; });
    }
  }

  load();
});
