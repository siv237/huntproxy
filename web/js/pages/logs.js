router.register('logs', (container) => {
  let state = {
    lines: [],
    filter: '',
    level: 'all',
  };

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    state.reverse = state.reverse !== false;
    state.autoScroll = state.autoScroll !== false;

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;flex-shrink:0' });
    const search = ui.el('input', '', { type: 'text', placeholder: t('page.logs.filterPlaceholder'), value: state.filter, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:220px' });
    search.addEventListener('input', (e) => {
      state.filter = e.target.value.toLowerCase();
      render();
    });
    filterBar.appendChild(search);

     const levels = [{label: t('page.logs.all'), value: 'all'}, {label: 'INFO', value: 'info'}, {label: 'WARN', value: 'warn'}, {label: 'ERROR', value: 'error'}];
     levels.forEach(l => {
       const btn = ui.el('button', `btn btn-sm ${state.level === l.value ? 'btn-primary' : 'btn-secondary'}`, { text: l.label });
       btn.addEventListener('click', () => {
         state.level = l.value;
         render();
       });
       filterBar.appendChild(btn);
     });

    const reverseBtn = ui.el('button', `btn btn-sm ${state.reverse ? 'btn-primary' : 'btn-secondary'}`, { text: t('page.logs.reverse') || 'Newest first' });
    reverseBtn.addEventListener('click', () => {
      state.reverse = !state.reverse;
      reverseBtn.className = `btn btn-sm ${state.reverse ? 'btn-primary' : 'btn-secondary'}`;
      render();
    });
    filterBar.appendChild(reverseBtn);

    const autoScrollBtn = ui.el('button', `btn btn-sm ${state.autoScroll ? 'btn-primary' : 'btn-secondary'}`, { text: t('page.logs.autoScroll') || 'Auto-scroll' });
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
    clearBtn.addEventListener('click', () => { state.lines = []; render(); });
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
      const data = await api.logs({ limit: 200 });
      state.lines = data.lines || [];
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
    const count = ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: `${state.lines.length} lines` });
    header.appendChild(count);
    card.appendChild(header);

    let lines = state.lines;
    if (state.filter) {
      lines = lines.filter(l => l.toLowerCase().includes(state.filter));
    }
    if (state.level !== 'all') {
      lines = lines.filter(l => l.toLowerCase().includes(state.level));
    }

    if (!lines.length) {
      card.appendChild(ui.el('div', 'empty', { text: t('page.logs.noMatching') }));
      return;
    }

    const displayLines = state.reverse ? lines.slice().reverse() : lines.slice();
    const wrap = ui.el('div', '', { id: 'logs-lines-wrap', style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:1.6;flex:1;min-height:0;overflow-y:auto' });
    displayLines.forEach(line => {
      const row = ui.el('div', '', { style: 'padding:2px 0;border-bottom:1px solid var(--border-subtle);white-space:pre-wrap;word-break:break-all' });
      let color = 'var(--text-primary)';
      if (line.includes('ERROR')) color = 'var(--danger)';
      else if (line.includes('WARN')) color = 'var(--warning)';
      else if (line.includes('INFO')) color = 'var(--info)';
      row.style.color = color;
      row.textContent = line;
      wrap.appendChild(row);
    });
    card.appendChild(wrap);
    if (state.reverse && state.autoScroll) {
      requestAnimationFrame(() => { wrap.scrollTop = wrap.scrollHeight; });
    }
  }

  load();
});
