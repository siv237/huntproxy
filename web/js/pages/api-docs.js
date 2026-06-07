router.register('api', (container) => {
  const card = ui.card('API Documentation');
  card.appendChild(ui.el('div', 'empty', { text: 'API endpoints documentation will appear here' }));
  container.appendChild(card);
});
