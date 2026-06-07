router.register('logs', (container) => {
  let state = {
    lines: [],
    filter: '',
    level: 'all',
  };

  function build() {
    container.innerHTML = '';

    const filterBar = ui.el('div', '', { style: 'display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:16px' });
    const search = ui.el('input', '', { type: 'text', placeholder: 'Filter logs...', value: state.filter, style: 'padding:6px 10px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px;min-width:220px' });
    search.addEventListener('input', (e) => {
      state.filter = e.target.value.toLowerCase();
      render();
    });
    filterBar.appendChild(search);

    const levels = ['All', 'INFO', 'WARN', 'ERROR'];
    levels.forEach(l => {
      const btn = ui.el('button', `btn btn-sm ${state.level === l.toLowerCase() || (l === 'All' && state.level === 'all') ? 'btn-primary' : 'btn-secondary'}`, { text: l });
      btn.addEventListener('click', () => {
        state.level = l === 'All' ? 'all' : l.toLowerCase();
        render();
      });
      filterBar.appendChild(btn);
    });

    filterBar.appendChild(ui.el('div', '', { style: 'flex:1' }));

    const liveBtn = ui.el('button', 'btn btn-secondary', { text: 'Live' });
    let liveInterval = null;
    liveBtn.addEventListener('click', () => {
      if (liveInterval) {
        clearInterval(liveInterval);
        liveInterval = null;
        liveBtn.textContent = 'Live';
        liveBtn.className = 'btn btn-secondary';
      } else {
        load();
        liveInterval = setInterval(load, 3000);
        liveBtn.textContent = 'Stop Live';
        liveBtn.className = 'btn btn-primary';
      }
    });
    filterBar.appendChild(liveBtn);

    const clearBtn = ui.el('button', 'btn btn-secondary', { text: 'Clear' });
    clearBtn.addEventListener('click', () => { state.lines = []; render(); });
    filterBar.appendChild(clearBtn);

    container.appendChild(filterBar);

    const card = ui.card('System Logs');
    card.id = 'logs-card';
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
    header.appendChild(ui.el('div', 'card-title', { text: 'System Logs' }));
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
      card.appendChild(ui.el('div', 'empty', { text: 'No matching logs' }));
      return;
    }

    const wrap = ui.el('div', '', { style: 'font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12px;line-height:1.6;max-height:500px;overflow-y:auto' });
    lines.forEach(line => {
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
  }

  load();
});
