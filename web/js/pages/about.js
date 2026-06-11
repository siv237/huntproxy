router.register('about', (container) => {
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '10px';
  container.style.minHeight = '0';
  container.style.flex = '1';
  container.style.overflow = 'auto';

  const logoWrap = ui.el('div', '', { style: 'text-align:center' });
  const logo = ui.el('img', '', {
    src: '/assets/biglogo.png',
    alt: 'huntproxy',
    style: 'max-width:320px;width:100%;height:auto;border-radius:12px',
  });
  logoWrap.appendChild(logo);
  container.appendChild(logoWrap);

  const title = ui.el('div', '', {
    style: 'font-size:28px;font-weight:700;color:var(--text-primary);text-align:center',
    text: 'huntproxy',
  });
  container.appendChild(title);

  const version = ui.el('div', '', {
    style: 'font-size:13px;color:var(--text-secondary);text-align:center;margin-top:-8px',
    text: 'v1.0.0',
  });
  container.appendChild(version);

  const descCard = ui.card(t('page.about.about'));
  const desc = ui.el('div', '', {
    style: 'font-size:14px;line-height:1.7;color:var(--text-secondary)',
    html: t('page.about.description'),
  });
  descCard.appendChild(desc);
  container.appendChild(descCard);

  const techCard = ui.card(t('page.about.technology'));
  const tech = ui.el('div', '', {
    style: 'font-size:13px;line-height:1.7;color:var(--text-secondary)',
    html: t('page.about.techStack'),
  });
  techCard.appendChild(tech);
  container.appendChild(techCard);
});
