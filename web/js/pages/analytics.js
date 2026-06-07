router.register('analytics', (container) => {
  const card = ui.card('Analytics');
  card.appendChild(ui.el('div', 'empty', { text: 'Analytics charts and trends will appear here' }));
  container.appendChild(card);
});
