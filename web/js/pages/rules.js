router.register('rules', (container) => {
  const card = ui.card('Rules');
  card.appendChild(ui.el('div', 'empty', { text: 'Transparent proxy rules and iptables configuration will appear here' }));
  container.appendChild(card);
});
