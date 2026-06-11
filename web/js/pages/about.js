router.register('about', (container) => {
  container.innerHTML = '';
  container.style.display = 'flex';
  container.style.flexDirection = 'column';
  container.style.alignItems = 'center';
  container.style.gap = '20px';
  container.style.padding = '24px';
  container.style.flex = '1';
  container.style.minHeight = '0';
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
    style: 'font-size:13px;color:var(--text-secondary);margin-top:-14px',
    text: 'v1.0.0',
  });
  container.appendChild(version);

  const descCard = ui.card('About');
  descCard.style.width = '100%';
  const desc = ui.el('div', '', {
    style: 'font-size:14px;line-height:1.7;color:var(--text-secondary);overflow-wrap:break-word',
    html:
      '<b>huntproxy</b> — proxy discovery, validation, and pool management tool with a built-in Web UI.<br><br>' +
      '<b>How it works:</b><br>' +
      '• Downloads proxy lists from open sources (GitHub, etc.)<br>' +
      '• Validates each proxy for availability, speed, and geolocation<br>' +
      '• Filters by country, detects MITM-suspect nodes<br>' +
      '• Maintains ratings and a blacklist automatically<br>' +
      '• Provides HTTP/SOCKS5/transparent proxy with round-robin balancing<br>' +
      '• Supports domain-based traffic routing<br><br>' +
      '<b>Key features:</b><br>' +
      '• Automated proxy discovery and validation (SOCKS4/SOCKS5/HTTP/HTTPS)<br>' +
      '• Health-checking with auto-pause on internet loss<br>' +
      '• Detailed analytics: latency, speed, success rate, geography<br>' +
      '• Flexible routing: domain lists, custom proxies, direct/pool<br>' +
      '• Transparent proxy mode via iptables (no app configuration needed)<br>' +
      '• Canary-based internet connectivity monitoring',
  });
  descCard.appendChild(desc);
  container.appendChild(descCard);

  const techCard = ui.card('Technology');
  techCard.style.width = '100%';
  const tech = ui.el('div', '', {
    style: 'font-size:13px;line-height:1.7;color:var(--text-secondary);overflow-wrap:break-word',
    html:
      '<b>Stack:</b> Python 3, asyncio, SQLite<br>' +
      '<b>Web UI:</b> Vanilla JS, CSS custom properties, Chart.js<br>' +
      '<b>Protocols:</b> HTTP CONNECT, SOCKS4, SOCKS5, Transparent proxy<br>' +
      '<b>Data:</b> GeoIP (ip-api.com), speed test, MITM detection',
  });
  techCard.appendChild(tech);
  container.appendChild(techCard);
});
