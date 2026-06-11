router.register('downloads', (container) => {
  function build() {
    container.innerHTML = '';
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';

    const card = ui.card(t('page.downloads.downloads'));
    card.id = 'downloads-card';
    container.appendChild(card);

    const files = [
      { name: 'working.txt', desc: t('page.downloads.workingTxt'), icon: '📄' },
      { name: 'blacklist.txt', desc: t('page.downloads.blacklistTxt'), icon: '🚫' },
      { name: 'ratings.json', desc: t('page.downloads.ratingsJson'), icon: '📊' },
      { name: 'config.yaml', desc: t('page.downloads.configYaml'), icon: '⚙️' },
    ];

    const grid = ui.el('div', 'grid grid-2');
    files.forEach(f => {
      const item = ui.el('div', '', { style: 'display:flex;align-items:center;gap:12px;padding:16px;background:var(--surface-raised);border-radius:var(--radius-xs);border:1px solid var(--border)' });
      item.appendChild(ui.el('div', '', { style: 'font-size:24px', text: f.icon }));
      const info = ui.el('div', '', { style: 'flex:1;min-width:0' });
      info.appendChild(ui.el('div', '', { style: 'font-weight:600;font-size:13px;margin-bottom:2px', text: f.name }));
      info.appendChild(ui.el('div', '', { style: 'font-size:12px;color:var(--text-secondary)', text: f.desc }));
      item.appendChild(info);
      const dl = ui.el('a', 'btn btn-sm btn-primary', { text: t('page.downloads.download'), href: `/api/download/${f.name}`, download: f.name });
      item.appendChild(dl);
      grid.appendChild(item);
    });

    const cardEl = document.getElementById('downloads-card');
    if (cardEl) cardEl.appendChild(grid);
  }

  build();
});
