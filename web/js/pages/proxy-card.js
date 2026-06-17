const proxyCard = {
  async show(addr) {
    const overlay = ui.el('div', 'proxy-card-overlay', {
      style: 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:1000;display:flex;align-items:center;justify-content:center;padding:20px'
    });
    const modal = ui.el('div', 'card proxy-card', {
      style: 'width:900px;max-width:95vw;max-height:90vh;overflow:hidden;display:flex;flex-direction:column'
    });

    modal.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t('common.loading')}</div>`;
    overlay.appendChild(modal);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
    document.body.appendChild(overlay);

    try {
      const p = await api.proxyDetail(addr);
      this._render(modal, p, overlay);
    } catch (e) {
      modal.innerHTML = `<div style="padding:40px;color:var(--danger)">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    }
  },

  _render(modal, p, overlay) {
    modal.innerHTML = '';
    modal.style.padding = '0';

    const topBar = ui.el('div', '', {
      style: 'display:flex;justify-content:space-between;align-items:center;padding:12px 24px;border-bottom:1px solid var(--border);background:var(--surface);flex-shrink:0'
    });
    topBar.appendChild(ui.el('div', '', { style: 'font-size:16px;font-weight:600;color:var(--text-primary)', text: t('proxyCard.title') }));
    const closeBtn = ui.el('button', 'btn btn-sm btn-ghost', { html: '×', style: 'font-size:22px;line-height:1;padding:0 6px' });
    closeBtn.addEventListener('click', () => overlay.remove());
    topBar.appendChild(closeBtn);
    modal.appendChild(topBar);

    const content = ui.el('div', '', {
      style: 'overflow-y:auto;padding:24px;min-height:0;flex:1'
    });
    modal.appendChild(content);

    content.appendChild(this._header(p));
    content.appendChild(this._grid(p));
    content.appendChild(this._scoreBreakdown(p));

    const footer = ui.el('div', '', {
      style: 'display:flex;gap:8px;justify-content:flex-end;padding:16px 24px;border-top:1px solid var(--border);background:var(--surface)'
    });
    modal.appendChild(footer);
    this._actions(modal, footer, p, overlay);
  },

  _refresh(modal, addr, overlay) {
    modal.innerHTML = `<div style="padding:40px;text-align:center;color:var(--text-muted)">${t('common.loading')}</div>`;
    api.proxyDetail(addr).then(p => {
      this._render(modal, p, overlay);
    }).catch(e => {
      modal.innerHTML = `<div style="padding:40px;color:var(--danger)">${t('common.error', {message: ui.escHtml(e.message)})}</div>`;
    });
  },

  _header(p) {
    const statusColor = p.in_blacklist ? 'var(--danger)' : p.last_status === 'ok' ? 'var(--success)' : 'var(--danger)';
    const statusText = p.in_blacklist ? t('proxyCard.blacklisted') : p.last_status === 'ok' ? 'OK' : 'FAIL';
    const score = Math.round(p.score || 0);
    const scoreColor = score >= 60 ? 'var(--success)' : score >= 30 ? 'var(--warning)' : 'var(--danger)';
    const flag = ui.flag(p.country_code);
    const proto = (p.protocol || 'http').toUpperCase();

    const wrap = ui.el('div', '', {
      style: 'display:flex;align-items:flex-start;gap:16px;margin-bottom:20px'
    });

    const left = ui.el('div', '', { style: 'flex:1;min-width:0' });
    left.appendChild(ui.el('div', '', {
      style: 'font-family:monospace;font-size:18px;font-weight:600;color:var(--text-primary);margin-bottom:6px',
      text: p.address
    }));
    const meta = ui.el('div', '', { style: 'display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:13px;color:var(--text-secondary)' });
    if (p.country) {
      meta.appendChild(ui.el('span', '', { text: `${flag} ${p.country}` }));
    }
    if (p.city) {
      meta.appendChild(ui.el('span', '', { text: p.city }));
    }
    if (p.isp) {
      meta.appendChild(ui.el('span', '', { text: p.isp }));
    }
    left.appendChild(meta);
    wrap.appendChild(left);

    const right = ui.el('div', '', { style: 'display:flex;align-items:center;gap:10px;flex-shrink:0;flex-wrap:wrap;justify-content:flex-end' });
    right.appendChild(ui.badge(proto, 'gray'));
    right.appendChild(ui.badge(statusText, p.in_blacklist ? 'red' : p.last_status === 'ok' ? 'green' : 'red'));
    if (p.ssl_supported) right.appendChild(ui.badge('SSL', 'cyan'));
    if (p.supports_connect) right.appendChild(ui.badge('CONNECT', 'blue'));
    if (p.mitm_suspect) right.appendChild(ui.badge('MITM', 'red'));
    right.appendChild(ui.el('div', '', {
      style: `font-size:28px;font-weight:700;color:${scoreColor};line-height:1`,
      text: String(score)
    }));
    wrap.appendChild(right);

    return wrap;
  },

  _grid(p) {
    const grid = ui.el('div', '', {
      style: 'display:grid;grid-template-columns:repeat(3, 1fr);gap:12px;margin-bottom:20px'
    });

    grid.appendChild(this._sectionCard(t('proxyCard.performance'), [
      [t('proxyCard.lastLatency'), ui.fmtLatency(p.last_latency)],
      [t('proxyCard.avgLatency'), ui.fmtLatency(p.latency_avg)],
      [t('proxyCard.lastSpeed'), p.last_speed ? p.last_speed.toFixed(0) + ' KB/s' : '—'],
      [t('proxyCard.avgSpeed'), p.speed_avg ? p.speed_avg.toFixed(0) + ' KB/s' : '—'],
      [t('proxyCard.successRate'), ui.fmtPct(p.success_rate)],
      [t('proxyCard.checks'), `${p.checks_ok || 0}/${p.checks_total || 0}`],
    ]));

    grid.appendChild(this._sectionCard(t('proxyCard.security'), [
      [t('proxyCard.ssl'), p.ssl_supported ? t('common.yes') : t('common.no')],
      [t('proxyCard.connect'), p.supports_connect ? t('common.yes') : t('common.no')],
      [t('proxyCard.mitm'), p.mitm_suspect ? t('proxyCard.mitmYes') : t('common.no')],
      [t('proxyCard.manualBlacklist'), p.in_blacklist ? t('common.yes') : t('common.no')],
      [t('proxyCard.ipBlacklist'), p.ip_blacklist_hits ? `${p.ip_blacklist_hits} ${t('proxyCard.hits')}` : t('common.no')],
    ]));

    grid.appendChild(this._sectionCard(t('proxyCard.network'), [
      [t('proxyCard.egressIp'), p.egress_ip || '—'],
      [t('proxyCard.egress'), [p.egress_country, p.egress_city, p.egress_isp].filter(Boolean).join(', ') || '—'],
      [t('proxyCard.listenIp'), p.address ? p.address.split(':')[0] : '—'],
      [t('proxyCard.listen'), [p.listen_country, p.listen_city, p.listen_isp].filter(Boolean).join(', ') || '—'],
      [t('proxyCard.sources'), (p.source_ids || []).join(', ') || '—'],
    ]));

    grid.appendChild(this._sectionCard(t('proxyCard.timeline'), [
      [t('proxyCard.firstSeen'), p.first_seen ? ui.ago(p.first_seen) : '—'],
      [t('proxyCard.lastCheck'), p.last_check ? ui.ago(p.last_check) : '—'],
      [t('proxyCard.lastOk'), p.last_ok ? ui.ago(p.last_ok) : '—'],
      [t('proxyCard.speedFails'), String(p.speed_fails || 0)],
    ]));

    return grid;
  },

  _sectionCard(title, rows) {
    const card = ui.card(title);
    card.style.padding = '12px';
    const list = ui.el('div', '', { style: 'display:flex;flex-direction:column;gap:6px' });
    rows.forEach(([label, value]) => {
      const row = ui.el('div', '', { style: 'display:flex;justify-content:space-between;gap:12px;font-size:12px' });
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary);flex-shrink:0', text: label }));
      const val = typeof value === 'string' ? value : String(value || '—');
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-primary);text-align:right;word-break:break-word', text: val }));
      list.appendChild(row);
    });
    card.appendChild(list);
    return card;
  },

  _scoreBreakdown(p) {
    const card = ui.card(t('proxyCard.scoreBreakdown'));
    card.style.padding = '12px';
    card.style.marginBottom = '0';

    const sr = p.success_rate || 0;
    const base = sr * 50;
    const lat = p.latency_avg || 0;
    const latScore = Math.max(0, 100 - lat * 10) * 0.5;
    const sslBonus = p.ssl_supported ? 10 : 0;
    const connectBonus = p.supports_connect ? 5 : 0;
    const mitmPenalty = p.mitm_suspect ? -30 : 0;
    const speedBonus = p.speed_avg ? Math.min(20, p.speed_avg / 50) : 0;
    const speedFailPenalty = (p.speed_fails || 0) >= 3 ? -40 : 0;
    let total = base + latScore + sslBonus + connectBonus + mitmPenalty + speedBonus + speedFailPenalty;
    const hits = p.ip_blacklist_hits || 0;
    const ipMultiplier = hits ? Math.max(0.2, Math.pow(0.75, hits)) : 1;
    const beforeIp = total;
    if (hits) total *= ipMultiplier;
    if (p.in_blacklist) total = 0;
    total = Math.max(0, total);

    const rows = [
      [t('proxyCard.successRate'), '+' + base.toFixed(1)],
      [t('proxyCard.latencyScore'), '+' + latScore.toFixed(1)],
      [t('proxyCard.sslBonus'), '+' + sslBonus.toFixed(0)],
      [t('proxyCard.connectBonus'), '+' + connectBonus.toFixed(0)],
      [t('proxyCard.speedBonus'), '+' + speedBonus.toFixed(1)],
      [t('proxyCard.mitmPenalty'), mitmPenalty ? mitmPenalty.toFixed(0) : '0'],
      [t('proxyCard.speedFailPenalty'), speedFailPenalty ? speedFailPenalty.toFixed(0) : '0'],
    ];
    if (hits) {
      rows.push([t('proxyCard.ipBlacklistMultiplier'), `×${ipMultiplier.toFixed(3)}`]);
    }
    if (p.in_blacklist) {
      rows.push([t('proxyCard.manualBlacklist'), '0']);
    }

    const list = ui.el('div', '', { style: 'display:grid;grid-template-columns:repeat(4, 1fr);gap:8px 12px' });
    rows.forEach(([label, value]) => {
      const row = ui.el('div', '', { style: 'display:flex;justify-content:space-between;gap:8px;font-size:12px;padding:4px 0;border-bottom:1px solid var(--border)' });
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-secondary)', text: label }));
      row.appendChild(ui.el('span', '', { style: 'color:var(--text-primary);font-weight:500', text: value }));
      list.appendChild(row);
    });

    const sumRow = ui.el('div', '', { style: 'display:flex;justify-content:space-between;gap:8px;font-size:14px;font-weight:600;padding:8px 0 0;margin-top:4px' });
    sumRow.appendChild(ui.el('span', '', { text: t('proxyCard.totalScore') }));
    sumRow.appendChild(ui.el('span', '', { style: 'color:var(--accent)', text: Math.round(total) }));
    list.appendChild(sumRow);

    card.appendChild(list);
    return card;
  },

  _actions(modal, footer, p, overlay) {
    const selectBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('proxyCard.select') });
    selectBtn.addEventListener('click', () => {
      selectBtn.disabled = true;
      selectBtn.textContent = t('common.loading');
      api.proxySelect(p.address).then(async () => {
        app.toast(t('page.proxyPool.selected', {addr: p.address}));
        try {
          const ps = await api.proxyStatus();
          if (!ps || !ps.running) {
            const port = ps && ps.port ? ps.port : 8080;
            await api.proxyStart(port);
            app.toast(t('page.overview.proxyStarted'));
          }
        } catch (e) { console.error('proxy start', e); }
        overlay.remove();
      }).catch(e => {
        selectBtn.disabled = false;
        selectBtn.textContent = t('proxyCard.select');
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    footer.appendChild(selectBtn);

    const recheckBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('proxyCard.recheck') });
    recheckBtn.addEventListener('click', () => {
      recheckBtn.disabled = true;
      recheckBtn.textContent = t('common.loading');
      api.proxyRecheck(p.address).then(() => {
        app.toast(t('page.proxies.recheckComplete'));
        this._refresh(modal, p.address, overlay);
      }).catch(e => {
        recheckBtn.disabled = false;
        recheckBtn.textContent = t('proxyCard.recheck');
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    footer.appendChild(recheckBtn);

    const blBtn = ui.el('button', p.in_blacklist ? 'btn btn-sm btn-danger' : 'btn btn-sm btn-danger', { text: p.in_blacklist ? t('proxyCard.removeFromBlacklist') : t('proxyCard.addToBlacklist') });
    blBtn.addEventListener('click', () => {
      blBtn.disabled = true;
      const promise = p.in_blacklist ? api.blRemove(p.address) : api.blAdd(p.address, 'manual');
      promise.then(() => {
        app.toast(p.in_blacklist ? t('page.blacklist.removedFromBlacklist') : t('page.proxies.addedToBlacklist'));
        overlay.remove();
      }).catch(e => {
        blBtn.disabled = false;
        app.toast(t('common.error', {message: e.message}), 'error');
      });
    });
    footer.appendChild(blBtn);

    const copyBtn = ui.el('button', 'btn btn-sm btn-secondary', { text: t('proxyCard.copy') });
    copyBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(p.address).then(() => app.toast(t('proxyCard.copied'))).catch(() => {});
    });
    footer.appendChild(copyBtn);

    const closeBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.cancel') });
    closeBtn.addEventListener('click', () => overlay.remove());
    footer.appendChild(closeBtn);
  }
};

window.proxyCard = proxyCard;
