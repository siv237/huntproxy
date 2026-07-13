router.register('traffic-flow', (container) => {
  let routingStatus = null;
  let proxyStatus = null;
  let channelStatus = null;
  let domainLists = [];
  let customProxies = [];
  let traceResult = null;
  let _loading = false;
  let zoom = 1;

  const ZOOM_MIN = 0.4;
  const ZOOM_MAX = 3;
  const ZOOM_STEP = 0.15;
  const BASE_W = 820;

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

    const flowCard = ui.card(t('page.trafficFlow.title'));
    flowCard.id = 'card-traffic-flow';
    flowCard.style.flex = '1';
    flowCard.style.display = 'flex';
    flowCard.style.flexDirection = 'column';
    flowCard.style.minHeight = '0';

    const controls = ui.el('div', 'flow-controls');

    const statusBadge = ui.el('span', '', { id: 'flow-routing-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600' });
    controls.appendChild(statusBadge);

    const serverBadge = ui.el('span', '', { id: 'flow-server-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600' });
    controls.appendChild(serverBadge);

    const channelBadge = ui.el('span', '', { id: 'flow-channel-badge', style: 'font-size:11px;padding:3px 10px;border-radius:10px;font-weight:600;display:none' });
    controls.appendChild(channelBadge);

    const legend = ui.el('div', 'flow-legend');
    legend.appendChild(legendItem('var(--success)', t('page.trafficFlow.activePath')));
    legend.appendChild(legendItem('var(--border)', t('page.trafficFlow.inactivePath')));
    legend.appendChild(legendItem('var(--accent)', t('page.trafficFlow.decision')));
    controls.appendChild(legend);

    const spacer = ui.el('div', '', { style: 'flex:1' });
    controls.appendChild(spacer);

    const zoomGroup = ui.el('div', 'flow-zoom');
    const zOut = ui.el('button', 'btn btn-sm btn-ghost', { text: '\u2212' });
    zOut.addEventListener('click', () => setZoom(zoom - ZOOM_STEP));
    zoomGroup.appendChild(zOut);

    const zLabel = ui.el('span', 'flow-zoom-label', { id: 'flow-zoom-label', text: '100%' });
    zoomGroup.appendChild(zLabel);

    const zIn = ui.el('button', 'btn btn-sm btn-ghost', { text: '+' });
    zIn.addEventListener('click', () => setZoom(zoom + ZOOM_STEP));
    zoomGroup.appendChild(zIn);

    const zReset = ui.el('button', 'btn btn-sm btn-ghost', { text: '1:1' });
    zReset.addEventListener('click', () => setZoom(1));
    zoomGroup.appendChild(zReset);
    controls.appendChild(zoomGroup);

    const input = ui.el('input', '', { id: 'flow-trace-input', type: 'text', placeholder: t('page.trafficFlow.tracePlaceholder'), style: 'width:200px;padding:5px 10px;font-size:12px;border:1px solid var(--border);border-radius:var(--radius-xs);background:var(--bg);color:var(--text-primary)' });
    controls.appendChild(input);

    const traceBtn = ui.el('button', 'btn btn-sm btn-primary', { text: t('page.trafficFlow.trace') });
    traceBtn.addEventListener('click', () => doTrace(input.value.trim()));
    controls.appendChild(traceBtn);

    const clearBtn = ui.el('button', 'btn btn-sm btn-ghost', { text: t('common.clear') });
    clearBtn.addEventListener('click', () => { input.value = ''; traceResult = null; renderFlow(); });
    controls.appendChild(clearBtn);

    flowCard.appendChild(controls);

    const wrap = ui.el('div', 'flow-wrap', { id: 'flow-wrap' });
    wrap.addEventListener('wheel', (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      setZoom(zoom + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP));
    }, { passive: false });
    flowCard.appendChild(wrap);

    container.appendChild(flowCard);
  }

  function setZoom(v) {
    zoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, Math.round(v * 100) / 100));
    const label = document.getElementById('flow-zoom-label');
    if (label) label.textContent = Math.round(zoom * 100) + '%';
    const svg = document.querySelector('#flow-wrap .flow-svg');
    if (svg) {
      svg.style.width = (BASE_W * zoom) + 'px';
    }
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
    if (route === 'pool_selected') return 'pool_selected';
    if (route.startsWith('custom:')) return 'custom';
    if (route.startsWith('proxy:')) return 'proxy';
    return 'unknown';
  }

  function routeLabel(route) {
    if (route === 'direct') return t('route.direct');
    if (route === 'pool') return t('route.pool');
    if (route === 'pool_selected') return t('route.poolSelected');
    if (route.startsWith('custom:')) {
      const cp = customProxies.find(p => ('custom:' + p.id) === route);
      return cp ? cp.name : route.slice(7);
    }
    if (route.startsWith('proxy:')) return route.slice(6);
    return route || '\u2014';
  }

  function renderFlow() {
    const wrap = document.getElementById('flow-wrap');
    if (!wrap) return;
    wrap.innerHTML = '';

    const enabled = !!(routingStatus && routingStatus.enabled);
    const running = !!(proxyStatus && proxyStatus.running);
    const directMode = !!(proxyStatus && proxyStatus.direct_mode);
    const activeProxy = proxyStatus && proxyStatus.active_proxy ? proxyStatus.active_proxy.address : null;
    const port = proxyStatus ? proxyStatus.port : '\u2014';

    const routedLists = (domainLists || []).filter(l => l.route && l.enabled);
    const defaultRoute = routingStatus ? (routingStatus.default_route || 'direct') : 'direct';
    const tracedRoute = traceResult ? traceResult.route : null;
    const hasMatch = !!(traceResult && traceResult.matched_list);

    const reachable = new Set();
    routedLists.forEach(l => reachable.add(routeTypeOf(l.route)));
    reachable.add(routeTypeOf(defaultRoute));
    if (!enabled) {
      if (directMode) reachable.add('direct');
      if (activeProxy) reachable.add('proxy');
    }
    if (customProxies && customProxies.length) {
      routedLists.forEach(l => { if (routeTypeOf(l.route) === 'custom') reachable.add('custom'); });
    } else {
      reachable.delete('custom');
    }

    const destOrder = ['direct', 'pool', 'pool_selected', 'custom', 'proxy'];
    const destMeta = {
      direct: { label: t('route.direct'), sub: t('page.trafficFlow.directExit') },
      pool: { label: t('route.pool'), sub: t('page.trafficFlow.bestProxy') },
      pool_selected: { label: t('route.poolSelected'), sub: t('page.trafficFlow.selectedProxy') },
      custom: { label: t('route.custom', { name: '' }).replace(/[: ]*$/, ''), sub: '' },
      proxy: { label: t('route.proxy'), sub: activeProxy || '' },
    };
    const destNodes = destOrder.filter(rt => reachable.has(rt)).map(rt => ({
      id: 'dest-' + rt, routeType: rt, label: destMeta[rt].label, sub: destMeta[rt].sub, kind: 'dest',
      active: isDestActive(rt, enabled, running, directMode, activeProxy, tracedRoute, hasMatch, defaultRoute),
    }));

    const W = BASE_W;
    const cx = W / 2;
    const nodeW = 180;
    const nodeH = 48;
    const dW = 140;
    const dH = 58;

    const offX = cx - 190;
    const onX = cx + 190;

    const nodes = {};
    nodes.client = { id: 'client', label: t('page.trafficFlow.client'), kind: 'io', x: cx, y: 38, w: nodeW, h: nodeH, active: running };
    nodes.server = { id: 'server', label: t('page.trafficFlow.proxyServer'), sub: running ? ('127.0.0.1:' + port) : t('page.trafficFlow.stopped'), kind: 'engine', x: cx, y: 122, w: nodeW, h: nodeH, active: running };
    nodes.routing = { id: 'routing', label: t('page.trafficFlow.routingEngine'), sub: enabled ? 'ON' : 'OFF', kind: 'decision', x: cx, y: 206, w: nodeW, h: nodeH, active: running };

    nodes.off = { id: 'off', label: t('page.trafficFlow.routingOff'), sub: t('page.trafficFlow.proxyControl'), kind: 'branch', x: offX, y: 296, w: nodeW, h: nodeH, active: running && !enabled };
    if (directMode) nodes.off.sub2 = t('page.trafficFlow.directExit');
    else if (activeProxy) nodes.off.sub2 = activeProxy;
    else nodes.off.sub2 = t('page.trafficFlow.noUpstream');

    nodes.on = { id: 'on', label: t('page.trafficFlow.routingOn'), kind: 'branch', x: onX, y: 296, w: nodeW, h: nodeH, active: running && enabled };
    nodes.rules = { id: 'rules', label: t('page.trafficFlow.domainRules'), sub: routedLists.length + ' ' + t('common.routes'), kind: 'list', x: onX, y: 378, w: nodeW, h: nodeH, active: running && enabled };
    nodes.match = { id: 'match', label: t('page.trafficFlow.matchDecision'), sub: hasMatch ? (traceResult.matched_list || '') : (traceResult ? t('page.trafficFlow.noMatch') : ''), kind: 'decision', x: onX, y: 460, w: nodeW, h: nodeH, active: running && enabled };
    nodes.default = { id: 'default', label: t('page.trafficFlow.defaultRoute'), sub: routeLabel(defaultRoute), kind: 'branch', x: onX, y: 542, w: nodeW, h: nodeH, active: running && enabled && !hasMatch };

    const destY = 648;
    const n = destNodes.length;
    const dMargin = 70;
    const dArea = W - 2 * dMargin;
    destNodes.forEach((d, i) => {
      d.x = n === 1 ? cx : dMargin + i * dArea / (n - 1);
      d.y = destY;
      d.w = dW; d.h = dH;
      nodes[d.id] = d;
    });

    const channelRoute = channelStatus ? (channelStatus.channel_route || '') : '';
    const channelActive = !!(channelRoute && channelRoute !== 'direct' && channelStatus.proxy);
    const channelY = 758;
    let internetY = 758;
    if (channelActive) {
      const cp = channelStatus.proxy;
      nodes.channel = {
        id: 'channel', label: t('page.trafficFlow.channel'),
        sub: cp ? (cp.host + ':' + cp.port) : '',
        kind: 'engine', x: cx, y: channelY, w: nodeW, h: nodeH,
        active: running && channelStatus.available,
      };
      internetY = 850;
    }

    nodes.internet = { id: 'internet', label: t('page.trafficFlow.internet'), sub: traceResult ? traceResult.domain : '', kind: 'io', x: cx, y: internetY, w: nodeW, h: nodeH, active: running };

    const totalH = internetY + nodeH / 2 + 24;

    const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svgEl.setAttribute('viewBox', `0 0 ${W} ${totalH}`);
    svgEl.setAttribute('preserveAspectRatio', 'xMidYMin meet');
    svgEl.classList.add('flow-svg');
    svgEl.style.width = (BASE_W * zoom) + 'px';
    svgEl.style.maxWidth = 'none';
    svgEl.style.maxHeight = 'none';

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

    const onActive = running && enabled;
    const offActive = running && !enabled;

    const edges = [
      { from: 'client', to: 'server', active: running },
      { from: 'server', to: 'routing', active: running },
      { from: 'routing', to: 'off', active: offActive, curve: true },
      { from: 'routing', to: 'on', active: onActive, curve: true },
      { from: 'on', to: 'rules', active: onActive },
      { from: 'rules', to: 'match', active: onActive },
    ];

    const defaultActive = onActive && !hasMatch;
    edges.push({ from: 'match', to: 'default', active: defaultActive });

    const matchedDest = hasMatch ? destNodes.find(d => d.routeType === routeTypeOf(tracedRoute)) : null;
    if (matchedDest) {
      edges.push({ from: 'match', to: matchedDest.id, active: onActive && hasMatch, curve: true, dashed: true });
    }

    const defaultDest = destNodes.find(d => d.routeType === routeTypeOf(defaultRoute));
    if (defaultDest) {
      edges.push({ from: 'default', to: defaultDest.id, active: defaultActive, curve: true, dashed: true });
    }

    destNodes.forEach(d => {
      if (offActive) {
        edges.push({ from: 'off', to: d.id, active: d.active, curve: true, dashed: true });
      }
    });

    if (channelActive) {
      destNodes.forEach(d => {
        edges.push({ from: d.id, to: 'channel', active: d.active, curve: true });
      });
      edges.push({ from: 'channel', to: 'internet', active: running && channelStatus.available });
    } else {
      destNodes.forEach(d => {
        edges.push({ from: d.id, to: 'internet', active: d.active, curve: true });
      });
    }

    edges.forEach(e => drawEdge(svgEl, nodes[e.from], nodes[e.to], e.active, e.curve, e.dashed, e.thin));

    Object.values(nodes).forEach(n => drawNode(svgEl, n, n.active));

    wrap.appendChild(svgEl);

    updateBadges(enabled, running, directMode);
  }

  function isDestActive(rt, enabled, running, directMode, activeProxy, tracedRoute, hasMatch, defaultRoute) {
    if (!running) return false;
    if (!enabled) {
      return (rt === 'direct' && directMode) || (rt === 'proxy' && !!activeProxy);
    }
    if (hasMatch) return routeTypeOf(tracedRoute) === rt;
    return routeTypeOf(defaultRoute) === rt;
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

  function drawNode(svg, node, active) {
    const g = document.createElementNS('http://www.w3.org/2000/svg', 'g');
    const w = node.w, h = node.h;
    const x = node.x - w / 2, y = node.y - h / 2;
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

    const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    label.setAttribute('x', node.x);
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
      sub.setAttribute('x', node.x);
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
      sub2.setAttribute('x', node.x);
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
        sb.textContent = t('page.trafficFlow.serverRunning') + (directMode ? ' \u00b7 ' + t('page.trafficFlow.directMode') : '');
        sb.style.background = 'var(--success-bg)';
        sb.style.color = 'var(--success)';
      } else {
        sb.textContent = t('page.trafficFlow.stopped');
        sb.style.background = 'var(--surface-raised)';
        sb.style.color = 'var(--text-muted)';
      }
    }
    const cb = document.getElementById('flow-channel-badge');
    if (cb) {
      const route = channelStatus ? (channelStatus.channel_route || '') : '';
      if (route && route !== 'direct' && channelStatus.proxy) {
        cb.style.display = '';
        const ok = channelStatus.available;
        cb.textContent = t('page.trafficFlow.channel') + ': ' + channelStatus.proxy.host + ':' + channelStatus.proxy.port;
        cb.style.background = ok ? 'var(--info-bg)' : 'var(--danger-bg)';
        cb.style.color = ok ? 'var(--info)' : 'var(--danger)';
      } else {
        cb.style.display = 'none';
      }
    }
  }

  build();
  renderFlow();

  async function load() {
    if (_loading) return;
    _loading = true;
    try {
      const [status, ps, dl, cp, ch] = await Promise.all([
        api.routingStatus().catch(e => { console.error('routingStatus', e); return {}; }),
        api.proxyStatus().catch(e => { console.error('proxyStatus', e); return {}; }),
        api.domainLists().catch(e => { console.error('domainLists', e); return { lists: [] }; }),
        api.customProxies().catch(e => { console.error('customProxies', e); return { proxies: [] }; }),
        api.channelStatus().catch(e => { console.error('channelStatus', e); return {}; }),
      ]);
      routingStatus = status;
      proxyStatus = ps;
      domainLists = dl.lists || dl || [];
      customProxies = cp.proxies || cp || [];
      channelStatus = ch;
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
