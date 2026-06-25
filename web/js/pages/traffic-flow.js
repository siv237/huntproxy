router.register('traffic-flow', (container) => {
  let routingStatus = null;
  let proxyStatus = null;
  let domainLists = [];
  let customProxies = [];
  let traceResult = null;
  let _loading = false;

  function setContainerStyle() {
    container.style.display = 'flex';
    container.style.flexDirection = 'column';
    container.style.gap = '10px';
    container.style.minHeight = '0';
    container.style.flex = '1';
  }

  function build() {
    container.innerHTML = '';
    setContainerStyle();
    container.appendChild(buildTopCard());
    const flowCard = ui.card(t('page.trafficFlow.diagram'));
    flowCard.id = 'card-traffic-flow';
    flowCard.style.flex = '1';
    flowCard.style.display = 'flex';
    flowCard.style.flexDirection = 'column';
    flowCard.style.minHeight = '0';
    const wrap = ui.el('div', 'flow-wrap', { id: 'flow-wrap' });
    flowCard.appendChild(wrap);
    container.appendChild(flowCard);
  }

  function buildTopCard() {
    const card = ui.card(t('page.trafficFlow.title'));
    card.id = 'card-flow-top';

    const row = ui.el('div', '', { style: 'display:flex;gap:8px;align-items:center;flex-wrap:wrap' });

    const statusBadge = ui.el('span', '', { id: 'flow-routing-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600' });
    row.appendChild(statusBadge);

    const serverBadge = ui.el('span', '', { id: 'flow-server-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600' });
    row.appendChild(serverBadge);

    const spacer = ui.el('div', '', { style: 'flex:1' });
    row.appendChild(spacer);

    const input = ui.el('input', '', { id: 'flow-trace-input', type: 'text', placeholder: t('page.trafficFlow.tracePlaceholder'), style: 'width:200px;padding:5px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    row.appendChild(input);

    const traceBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.trafficFlow.trace') });
    traceBtn.addEventListener('click', () => doTrace(input.value.trim()));
    row.appendChild(traceBtn);

    const clearBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.clear') });
    clearBtn.addEventListener('click', () => { input.value = ''; traceResult = null; renderFlow(); });
    row.appendChild(clearBtn);

    card.appendChild(row);

    const legend = ui.el('div', 'flow-legend');
    legend.appendChild(legendItem('var(--success)', t('page.trafficFlow.activePath')));
    legend.appendChild(legendItem('var(--border)', t('page.trafficFlow.inactivePath')));
    legend.appendChild(legendItem('var(--accent)', t('page.trafficFlow.decision')));
    card.appendChild(legend);

    return card;
  }

  function legendItem(color, label) {
    const item = ui.el('div', 'flow-legend-item');
    item.appendChild(ui.el('span', 'flow-legend-dot', { style: 'background:' + color }));
    item.appendChild(ui.el('span', '', { text: label }));
    return item;
  }

  function doTrace(domain) {
    if (!domain) return;
    api.routingTest(domain).then(result => {
      traceResult = result;
      renderFlow();
    }).catch(e => app.toast('Error: ' + e.message, 'error'));
  }

  function routeTypeOf(route) {
    if (!route) return 'unknown';
    if (route === 'direct') return 'direct';
    if (route === 'pool') return 'pool';
    if (route.startsWith('custom:')) return 'custom';
    if (route.startsWith('proxy:')) return 'proxy';
    return 'unknown';
  }

  function routeLabel(route) {
    if (route === 'direct') return t('route.direct');
    if (route === 'pool') return t('route.pool');
    if (route.startsWith('custom:')) {
      const cp = customProxies.find(p => ('custom:' + p.id) === route);
      return cp ? cp.name : route.slice(7);
    }
    if (route.startsWith('proxy:')) return route.slice(6);
    return route || '—';
  }

  function currentActiveRoute() {
    if (traceResult && traceResult.route) return traceResult.route;
    if (routingStatus && routingStatus.enabled) return routingStatus.default_route || 'direct';
    if (proxyStatus && proxyStatus.direct_mode) return 'direct';
    if (proxyStatus && proxyStatus.active_proxy) return 'proxy:' + (proxyStatus.active_proxy.address || '');
    return 'pool';
  }

  function renderFlow() {
    const wrap = document.getElementById('flow-wrap');
    if (!wrap) return;
    wrap.innerHTML = '';

    const enabled = !!(routingStatus && routingStatus.enabled);
    const running = !!(proxyStatus && proxyStatus.running);
    const directMode = !!(proxyStatus && proxyStatus.direct_mode);
    const activeProxy = proxyStatus && proxyStatus.active_proxy ? proxyStatus.active_proxy.address : null;
    const port = proxyStatus ? proxyStatus.port : '—';
    const activeRoute = currentActiveRoute();
    const activeType = routeTypeOf(activeRoute);

    const routedLists = (domainLists || []).filter(l => l.route && l.enabled);
    const defaultRoute = routingStatus ? (routingStatus.default_route || 'direct') : 'direct';

    const W = 760;
    const nodeW = 170;
    const nodeH = 50;
    const cx = W / 2;

    const layers = [];
    layers.push({ id: 'client', label: t('page.trafficFlow.client'), sub: '', kind: 'io', x: cx, active: running });
    layers.push({ id: 'server', label: t('page.trafficFlow.proxyServer'), sub: running ? ('127.0.0.1:' + port) : t('page.trafficFlow.stopped'), kind: 'engine', x: cx, active: running });
    layers.push({ id: 'routing', label: t('page.trafficFlow.routingEngine'), sub: enabled ? 'ON' : 'OFF', kind: 'decision', x: cx, active: running });

    const offNode = { id: 'off', label: t('page.trafficFlow.routingOff'), sub: t('page.trafficFlow.proxyControl'), kind: 'branch', x: 150, active: running && !enabled };
    if (directMode) offNode.sub2 = t('page.trafficFlow.directExit');
    else if (activeProxy) offNode.sub2 = activeProxy;
    else offNode.sub2 = t('page.trafficFlow.noUpstream');
    layers.push(offNode);

    const onNode = { id: 'on', label: t('page.trafficFlow.routingOn'), sub: routedLists.length + ' ' + t('common.routes'), kind: 'branch', x: cx + 220, active: running && enabled };

    const listNodes = [];
    routedLists.slice(0, 4).forEach((l, i) => {
      listNodes.push({ id: 'list-' + l.id, label: l.name, sub: routeLabel(l.route), kind: 'list', x: cx + 220, prio: i + 1, routeType: routeTypeOf(l.route), active: running && enabled });
    });

    const matchNode = { id: 'match', label: t('page.trafficFlow.matchDecision'), sub: traceResult ? (traceResult.matched_list || t('page.trafficFlow.noMatch')) : '', kind: 'decision', x: cx + 220, active: running && enabled };

    const defaultNode = { id: 'default', label: t('page.trafficFlow.defaultRoute'), sub: routeLabel(defaultRoute), kind: 'branch', x: cx + 220, active: running && enabled && (!traceResult || !traceResult.matched_list) };

    layers.push(onNode);
    layers.push(matchNode);
    layers.push(defaultNode);

    const destNodes = [
      { id: 'dest-direct', label: t('route.direct'), sub: t('page.trafficFlow.directExit'), kind: 'dest', x: 90, routeType: 'direct', active: activeType === 'direct' && running },
      { id: 'dest-pool', label: t('route.pool'), sub: t('page.trafficFlow.bestProxy'), kind: 'dest', x: 300, routeType: 'pool', active: activeType === 'pool' && running },
      { id: 'dest-custom', label: t('route.custom', { name: '' }).replace(/[: ]*$/, ''), sub: '', kind: 'dest', x: 510, routeType: 'custom', active: activeType === 'custom' && running },
      { id: 'dest-proxy', label: t('route.proxy'), sub: activeType === 'proxy' ? activeRoute.slice(6) : '', kind: 'dest', x: 680, routeType: 'proxy', active: activeType === 'proxy' && running },
    ];

    layers.push({ id: 'destinations', destNodes: destNodes, kind: 'destrow' });
    layers.push({ id: 'internet', label: t('page.trafficFlow.internet'), sub: traceResult ? traceResult.domain : '', kind: 'io', x: cx, active: running });

    const yStart = 40;
    const yStep = 90;
    const positions = {};
    let y = yStart;
    const renderedLayers = [];
    layers.forEach(layer => {
      if (layer.kind === 'destrow') {
        y += 30;
        destNodes.forEach(d => { positions[d.id] = { x: d.x, y: y, w: 130, h: 60 }; });
        renderedLayers.push({ y: y, kind: 'destrow', nodes: destNodes });
        y += 60;
      } else {
        positions[layer.id] = { x: layer.x, y: y, w: nodeW, h: nodeH };
        renderedLayers.push({ y: y, kind: 'single', node: layer });
        y += yStep;
      }
    });

    if (listNodes.length) {
      const matchPos = positions['match'];
      let ly = matchPos.y - (listNodes.length * 52) - 20;
      listNodes.forEach(n => { positions[n.id] = { x: n.x, y: ly, w: 170, h: 44 }; ly += 52; });
    }

    const totalH = y + 40;
    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgEl.setAttribute('viewBox', `0 0 ${W} ${totalH}`);
    svgEl.setAttribute('preserveAspectRatio', 'xMidYMin meet');
    svgEl.classList.add('flow-svg');

    const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
    ['active', 'inactive'].forEach(kind => {
      const marker = document.createElementNS('http://www.w3.org/2000/svg', 'marker');
      marker.setAttribute('id', 'arrow-' + kind);
      marker.setAttribute('viewBox', '0 0 10 10');
      marker.setAttribute('refX', '8');
      marker.setAttribute('refY', '5');
      marker.setAttribute('markerWidth', '7');
      marker.setAttribute('markerHeight', '7');
      marker.setAttribute('orient', 'auto');
      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', 'M0,0 L10,5 L0,10 z');
      path.setAttribute('fill', kind === 'active' ? 'var(--success)' : 'var(--border)');
      marker.appendChild(path);
      defs.appendChild(marker);
    });
    svgEl.appendChild(defs);

    const edges = [
      { from: 'client', to: 'server', active: running },
      { from: 'server', to: 'routing', active: running },
      { from: 'routing', to: 'off', active: running && !enabled, curve: true },
      { from: 'routing', to: 'on', active: running && enabled, curve: true },
    ];

    if (listNodes.length) {
      edges.push({ from: 'on', to: listNodes[0].id, active: running && enabled });
      for (let i = 0; i < listNodes.length - 1; i++) {
        edges.push({ from: listNodes[i].id, to: listNodes[i + 1].id, active: running && enabled });
      }
      edges.push({ from: listNodes[listNodes.length - 1].id, to: 'match', active: running && enabled });
    } else {
      edges.push({ from: 'on', to: 'match', active: running && enabled });
    }
    edges.push({ from: 'match', to: 'default', active: running && enabled && (!traceResult || !traceResult.matched_list) });

    const tracedRoute = traceResult ? traceResult.route : null;
    destNodes.forEach(d => {
      const destActive = running && (
        (enabled && (tracedRoute === d.routeType || (!traceResult && defaultRoute === d.routeType))) ||
        (!enabled && ((d.routeType === 'direct' && directMode) || (d.routeType === 'proxy' && activeProxy)))
      );
      if (d.routeType === 'custom' && !(customProxies && customProxies.length)) return;
      edges.push({ from: 'off', to: d.id, active: destActive && !enabled, curve: true, dashed: true });
      edges.push({ from: 'default', to: d.id, active: destActive && enabled, curve: true, dashed: true });
      if (listNodes.length) {
        listNodes.forEach(ln => {
          if (ln.routeType === d.routeType) {
            edges.push({ from: ln.id, to: d.id, active: running && enabled && traceResult && traceResult.matched_list && tracedRoute === d.routeType, curve: true, dashed: true, thin: true });
          }
        });
      }
    });

    const internetPos = positions['internet'];
    destNodes.forEach(d => {
      if (d.routeType === 'custom' && !(customProxies && customProxies.length)) return;
      edges.push({ from: d.id, to: 'internet', active: d.active, curve: true });
    });

    edges.forEach(e => drawEdge(svgEl, positions[e.from], positions[e.to], e.active, e.curve, e.dashed, e.thin));

    renderedLayers.forEach(layer => {
      if (layer.kind === 'destrow') {
        layer.nodes.forEach(d => {
          if (d.routeType === 'custom' && !(customProxies && customProxies.length)) return;
          drawNode(svgEl, d, positions[d.id], d.active, d.routeType);
        });
      } else if (layer.kind === 'single') {
        const n = layer.node;
        drawNode(svgEl, n, positions[n.id], n.active, n.routeType);
      }
    });
    listNodes.forEach(n => drawNode(svgEl, n, positions[n.id], n.active, n.routeType, n.prio));

    wrap.appendChild(svgEl);

    updateBadges(enabled, running, directMode);
  }

  function drawEdge(svg, from, to, active, curve, dashed, thin) {
    if (!from || !to) return;
    const x1 = from.x, y1 = from.y + from.h / 2;
    const x2 = to.x, y2 = to.y - to.h / 2;
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    let d;
    if (curve) {
      const my = (y1 + y2) / 2;
      d = `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`;
    } else {
      d = `M${x1},${y1} L${x2},${y2}`;
    }
    path.setAttribute('d', d);
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', active ? 'var(--success)' : 'var(--border)');
    path.setAttribute('stroke-width', thin ? '1.4' : '2');
    if (dashed) path.setAttribute('stroke-dasharray', '5 4');
    path.setAttribute('marker-end', `url(#arrow-${active ? 'active' : 'inactive'})`);
    if (active) {
      path.classList.add('flow-edge-active');
      const dash = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
      dash.setAttribute('attributeName', 'stroke-dashoffset');
      dash.setAttribute('from', '20');
      dash.setAttribute('to', '0');
      dash.setAttribute('dur', '0.8s');
      dash.setAttribute('repeatCount', 'indefinite');
      if (!dashed) path.setAttribute('stroke-dasharray', '8 4');
      path.appendChild(dash);
    }
    svg.appendChild(path);
  }

  function nodeColor(kind, active) {
    if (kind === 'decision') return { fill: 'var(--accent-light)', stroke: 'var(--accent)' };
    if (kind === 'io') return { fill: active ? 'var(--success-bg)' : 'var(--surface-raised)', stroke: active ? 'var(--success)' : 'var(--border)' };
    if (kind === 'engine') return { fill: 'var(--info-bg)', stroke: 'var(--info)' };
    if (kind === 'dest') return { fill: active ? 'var(--success-bg)' : 'var(--surface-raised)', stroke: active ? 'var(--success)' : 'var(--border)' };
    if (kind === 'list') return { fill: 'var(--surface-raised)', stroke: 'var(--border)' };
    return { fill: 'var(--surface-raised)', stroke: active ? 'var(--success)' : 'var(--border)' };
  }

  function drawNode(svg, node, pos, active, routeType, prio) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const w = pos.w, h = pos.h;
    const x = pos.x - w / 2, y = pos.y - h / 2;
    const col = nodeColor(node.kind, active);

    const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    rect.setAttribute('x', x);
    rect.setAttribute('y', y);
    rect.setAttribute('width', w);
    rect.setAttribute('height', h);
    rect.setAttribute('rx', 8);
    rect.setAttribute('fill', col.fill);
    rect.setAttribute('stroke', col.stroke);
    rect.setAttribute('stroke-width', active ? '2.5' : '1.5');
    g.appendChild(rect);

    if (prio) {
      const badge = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      badge.setAttribute('cx', x + 12);
      badge.setAttribute('cy', y + 12);
      badge.setAttribute('r', 9);
      badge.setAttribute('fill', 'var(--accent)');
      g.appendChild(badge);
      const bt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      bt.setAttribute('x', x + 12);
      bt.setAttribute('y', y + 16);
      bt.setAttribute('text-anchor', 'middle');
      bt.setAttribute('font-size', '10');
      bt.setAttribute('fill', '#fff');
      bt.setAttribute('font-weight', '700');
      bt.textContent = prio;
      g.appendChild(bt);
    }

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', pos.x + (prio ? 8 : 0));
    label.setAttribute('y', y + (node.sub || node.sub2 ? 20 : h / 2 + 5));
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('font-size', '12');
    label.setAttribute('font-weight', '600');
    label.setAttribute('fill', 'var(--text-primary)');
    label.textContent = node.label;
    g.appendChild(label);

    let subY = y + 36;
    if (node.sub) {
      const sub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      sub.setAttribute('x', pos.x + (prio ? 8 : 0));
      sub.setAttribute('y', subY);
      sub.setAttribute('text-anchor', 'middle');
      sub.setAttribute('font-size', '10');
      sub.setAttribute('fill', active ? 'var(--success)' : 'var(--text-secondary)');
      sub.textContent = node.sub;
      g.appendChild(sub);
      subY += 13;
    }
    if (node.sub2) {
      const sub2 = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      sub2.setAttribute('x', pos.x + (prio ? 8 : 0));
      sub2.setAttribute('y', subY);
      sub2.setAttribute('text-anchor', 'middle');
      sub2.setAttribute('font-size', '10');
      sub2.setAttribute('fill', 'var(--text-muted)');
      sub2.textContent = node.sub2;
      g.appendChild(sub2);
    }

    svg.appendChild(g);
  }

  function updateBadges(enabled, running, directMode) {
    const rb = document.getElementById('flow-routing-badge');
    if (rb) {
      rb.textContent = enabled ? t('page.trafficFlow.routingOn') : t('page.trafficFlow.routingOff');
      rb.style.background = enabled ? 'var(--success-bg)' : 'var(--surface-raised)';
      rb.style.color = enabled ? 'var(--success)' : 'var(--text-muted)';
    }
    const sb = document.getElementById('flow-server-badge');
    if (sb) {
      if (running) {
        sb.textContent = t('page.trafficFlow.serverRunning') + (directMode ? ' · ' + t('page.trafficFlow.directMode') : '');
        sb.style.background = 'var(--success-bg)';
        sb.style.color = 'var(--success)';
      } else {
        sb.textContent = t('page.trafficFlow.stopped');
        sb.style.background = 'var(--surface-raised)';
        sb.style.color = 'var(--text-muted)';
      }
    }
  }

  build();
  renderFlow();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      const [status, ps, dl, cp] = await Promise.all([
        api.routingStatus().catch(e => { console.error('routingStatus', e); return {}; }),
        api.proxyStatus().catch(e => { console.error('proxyStatus', e); return {}; }),
        api.domainLists().catch(e => { console.error('domainLists', e); return { lists: [] }; }),
        api.customProxies().catch(e => { console.error('customProxies', e); return { proxies: [] }; }),
      ]);
      routingStatus = status;
      proxyStatus = ps;
      domainLists = dl.lists || dl || [];
      customProxies = cp.proxies || cp || [];
      renderFlow();
    } catch (e) {
      console.error('traffic-flow load', e);
    } finally {
      _loading = false;
    }
  }

  load();
  const id = setInterval(load, 3000);
  if (window._pageIntervals) window._pageIntervals.push(id);
  else window._pageIntervals = [id];
});
