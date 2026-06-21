router.register('about', (container) => {
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.gap = '18px';
  container.style.minHeight = '0';
  container.style.flex = '1';
  container.style.overflow = 'auto';
  container.style.padding = '8px 4px';

  const logoWrap = ui.el('div', '', { style: 'text-align:center' });
  const logo = ui.el('img', 'about-logo', {
    src: '/assets/biglogo.png',
    alt: 'huntproxy',
    style: 'max-width:760px;width:100%;height:auto',
  });
  logoWrap.appendChild(logo);
  container.appendChild(logoWrap);

  const sectionStyle =
    'font-size:15px;font-weight:600;color:var(--text-primary);margin-top:6px';
  const bodyStyle =
    'font-size:14px;line-height:1.7;color:var(--text-secondary)';

  const descTitle = ui.el('div', '', { style: sectionStyle, text: t('page.about.about') });
  container.appendChild(descTitle);
  const desc = ui.el('div', '', { style: bodyStyle, html: t('page.about.description') });
  container.appendChild(desc);

  const techTitle = ui.el('div', '', { style: sectionStyle, text: t('page.about.technology') });
  container.appendChild(techTitle);
  const tech = ui.el('div', '', { style: bodyStyle, html: t('page.about.techStack') });
  container.appendChild(tech);
});
