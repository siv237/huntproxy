router.register('settings', (container) => {
  let config = {};

  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const card = ui.card(t('page.settings.title'));
    card.id = 'settings-card';
    card.style.flex = '1';
    card.style.minHeight = '0';
    card.style.overflow = 'auto';
    container.appendChild(card);

    const btns = ui.el('div', '', { style: 'display:flex;gap:8px;margin-top:16px' });
    const saveBtn = ui.el('button', 'btn btn-primary', { text: t('page.settings.saveSettings') });
    saveBtn.addEventListener('click', () => save());
    btns.appendChild(saveBtn);

    const reloadBtn = ui.el('button', 'btn btn-secondary', { text: t('page.settings.reload') });
    reloadBtn.addEventListener('click', () => load());
    btns.appendChild(reloadBtn);
    container.appendChild(btns);
  }

  build();

  async function load() {
    try {
      const data = await api.settings();
      config = data;
      render();
      app.toast('Settings loaded');
    } catch (e) {
      console.error('settings load', e);
      app.toast('Failed to load settings', 'error');
    }
  }

  function render() {
    const card = document.getElementById('settings-card');
    if (!card) return;
    card.innerHTML = '';
    const header = ui.el('div', 'card-header');
    header.appendChild(ui.el('div', 'card-title', { text: t('page.settings.title') }));
    card.appendChild(header);

    const grid = ui.el('div', 'grid grid-2');
    grid.appendChild(renderGroup('Server', [
      { key: 'server.web_listen', label: 'Web UI Listen', type: 'text' },
      { key: 'server.http_listen', label: 'HTTP Proxy Listen', type: 'text' },
      { key: 'server.socks5_listen', label: 'SOCKS5 Proxy Listen', type: 'text' },
      { key: 'server.transparent_listen', label: 'Transparent Proxy Listen', type: 'text' },
      { key: 'server.transparent_enabled', label: 'Transparent Enabled', type: 'checkbox' },
    ]));
    grid.appendChild(renderGroup('Hunt', [
      { key: 'hunt.parallel', label: 'Parallel Checks', type: 'number' },
      { key: 'hunt.timeout', label: 'Timeout (sec)', type: 'number' },
      { key: 'hunt.us_only', label: 'US Only', type: 'checkbox' },
      { key: 'hunt.health_interval', label: 'Health Interval (sec)', type: 'number' },
      { key: 'hunt.health_parallel', label: 'Health Parallel', type: 'number' },
    ]));
    grid.appendChild(renderGroup('Proxies', [
      { key: 'proxies.validate_interval', label: 'Validate Interval (sec)', type: 'number' },
      { key: 'proxies.validate_parallel', label: 'Validate Parallel', type: 'number' },
      { key: 'proxies.health_interval', label: 'Health Interval (sec)', type: 'number' },
      { key: 'proxies.health_parallel', label: 'Health Parallel', type: 'number' },
      { key: 'proxies.max_failures', label: 'Max Failures', type: 'number' },
      { key: 'proxies.cooldown', label: 'Cooldown (sec)', type: 'number' },
      { key: 'proxies.strategy', label: 'Strategy', type: 'select', options: ['round_robin', 'random'] },
    ]));
    grid.appendChild(renderGroup('Logging', [
      { key: 'logging.level', label: 'Log Level', type: 'select', options: ['DEBUG', 'INFO', 'WARN', 'ERROR'] },
      { key: 'logging.file', label: 'Log File', type: 'text' },
      { key: 'logging.max_size_mb', label: 'Max Size (MB)', type: 'number' },
      { key: 'logging.backup_count', label: 'Backup Count', type: 'number' },
    ]));
    card.appendChild(grid);
  }

  function renderGroup(title, fields) {
    const group = ui.el('div', 'card', { style: 'padding:16px' });
    group.appendChild(ui.el('div', '', { style: 'font-weight:600;margin-bottom:12px;font-size:14px', text: title }));
    fields.forEach(f => {
      const row = ui.el('div', '', { style: 'margin-bottom:10px' });
      row.appendChild(ui.el('label', '', { style: 'display:block;font-size:12px;color:var(--text-secondary);margin-bottom:4px', text: f.label }));
      const val = getValue(config, f.key);
      if (f.type === 'checkbox') {
        const wrap = ui.el('label', '', { style: 'display:flex;align-items:center;gap:6px;cursor:pointer' });
        const inp = ui.el('input', '', { type: 'checkbox', 'data-key': f.key });
        inp.checked = !!val;
        wrap.appendChild(inp);
        wrap.appendChild(ui.el('span', '', { style: 'font-size:13px', text: f.label }));
        row.appendChild(wrap);
      } else if (f.type === 'select') {
        const inp = ui.el('select', '', { 'data-key': f.key, style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px' });
        (f.options || []).forEach(o => {
          const opt = ui.el('option', '', { value: o, text: o });
          if (o === val) opt.selected = true;
          inp.appendChild(opt);
        });
        row.appendChild(inp);
      } else {
        const inp = ui.el('input', '', { type: f.type, 'data-key': f.key, value: val !== undefined && val !== null ? val : '', style: 'width:100%;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary);font-size:13px' });
        row.appendChild(inp);
      }
      group.appendChild(row);
    });
    return group;
  }

  function getValue(obj, key) {
    return key.split('.').reduce((o, k) => o && o[k], obj);
  }

  function setValue(obj, key, value) {
    const parts = key.split('.');
    const last = parts.pop();
    const target = parts.reduce((o, k) => {
      if (!o[k]) o[k] = {};
      return o[k];
    }, obj);
    target[last] = value;
  }

  async function save() {
    const newConfig = JSON.parse(JSON.stringify(config));
    document.querySelectorAll('#settings-card [data-key]').forEach(el => {
      const key = el.getAttribute('data-key');
      let val = el.type === 'checkbox' ? el.checked : el.value;
      if (el.type === 'number') val = parseFloat(val);
      setValue(newConfig, key, val);
    });
    try {
      await api.saveSettings(newConfig);
      app.toast('Settings saved');
    } catch (e) {
      app.toast('Error: ' + e.message, 'error');
    }
  }

  load();
});
