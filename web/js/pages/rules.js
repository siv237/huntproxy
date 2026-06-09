router.register('rules', (container) => {
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';
  const card = ui.card('Rules');
  card.style.flex = '1';
  card.appendChild(ui.el('div', 'empty', { text: 'Transparent proxy rules and iptables configuration will appear here' }));
  container.appendChild(card);
});
