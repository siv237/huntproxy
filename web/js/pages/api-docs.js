router.register('api', (container) => {
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';
  const card = ui.card(t('page.api.apiDocumentation'));
  card.style.flex = '1';
  card.appendChild(ui.el('div', 'empty', { text: t('page.api.comingSoon') }));
  container.appendChild(card);
});
