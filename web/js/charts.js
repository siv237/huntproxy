const charts = {
  sparkline(data, color = 'var(--accent)', width = 120, height = 40, fill = true) {
    if (!data || data.length < 2) {
      return `<svg class="sparkline" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><path d="" stroke="${color}"/></svg>`;
    }
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const step = width / (data.length - 1);
    const points = data.map((v, i) => {
      const x = i * step;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    });
    const pathD = `M ${points.join(' L ')}`;
    let areaD = '';
    if (fill) {
      areaD = `M ${points[0]} L ${points.join(' L ')} L ${width},${height} L 0,${height} Z`;
    }
    return `
      <svg class="sparkline" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
        ${fill ? `<path class="area" d="${areaD}" fill="${color}"/>` : ''}
        <path d="${pathD}" stroke="${color}" fill="none" vector-effect="non-scaling-stroke"/>
      </svg>`;
  },

  lineChart(data, opts = {}) {
    return this.multiLineChart([{ data, color: opts.color, fillArea: opts.fillArea }], opts);
  },

  multiLineChart(lines, opts = {}) {
    const { width = 600, height = 200, strokeWidth = 1.5, grid = true, labels = [], responsive = false, hideLegend = false } = opts;
    const validLines = (lines || []).filter(l => l && l.data && l.data.length >= 2);
    if (!validLines.length) {
      return `<svg ${responsive ? `width="100%" height="100%"` : `width="${width}" height="${height}"`} viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet"><text x="${width/2}" y="${height/2}" text-anchor="middle" fill="var(--text-muted)" font-size="12">No data</text></svg>`;
    }
    const pad = { top: 10, right: 14, bottom: 32, left: 44 };
    const w = width - pad.left - pad.right;
    const h = height - pad.top - pad.bottom;

    const allValues = validLines.flatMap(l => l.data);
    let min = Math.min(...allValues);
    let max = Math.max(...allValues);
    if (min === max) { min = 0; max = max || 1; }
    const range = max - min || 1;
    const count = validLines[0].data.length;
    const stepX = w / (count - 1);

    const mkPoints = data => data.map((v, i) => {
      const x = pad.left + i * stepX;
      const y = pad.top + h - ((v - min) / range) * h;
      return [x, y];
    });

    const mkPath = points => `M ${points.map(p => p.join(',')).join(' L ')}`;

    let gridLines = '';
    if (grid) {
      for (let i = 0; i <= 4; i++) {
        const y = pad.top + (h / 4) * i;
        gridLines += `<line x1="${pad.left}" y1="${y}" x2="${pad.left + w}" y2="${y}" stroke="var(--border)" stroke-dasharray="2,2" vector-effect="non-scaling-stroke"/>`;
      }
    }

    let labelText = '';
    if (labels.length) {
      const every = Math.ceil(labels.length / 6);
      labels.forEach((l, i) => {
        if (i % every === 0) {
          const x = pad.left + i * stepX;
          labelText += `<text x="${x}" y="${height - 8}" text-anchor="middle" fill="var(--text-muted)" font-size="10">${l}</text>`;
        }
      });
    }

    const yLabels = [min, min + range * 0.5, max].map(v => {
      if (Math.abs(v) >= 1000) return (v / 1000).toFixed(1) + 'K';
      return Number.isInteger(v) ? v.toString() : v.toFixed(1);
    });
    let yText = '';
    yLabels.forEach((t, i) => {
      const y = pad.top + h - (i / 2) * h;
      yText += `<text x="${pad.left - 6}" y="${y + 4}" text-anchor="end" fill="var(--text-muted)" font-size="10">${t}</text>`;
    });

    let paths = '';
    validLines.forEach(l => {
      const points = mkPoints(l.data);
      const pathD = mkPath(points);
      const color = l.color || 'var(--accent)';
      const fill = l.fillArea !== false;
      if (fill) {
        const areaD = `M ${points[0].join(',')} L ${points.map(p => p.join(',')).join(' L ')} L ${points[points.length-1][0]},${pad.top + h} L ${points[0][0]},${pad.top + h} Z`;
        paths += `<path d="${areaD}" fill="${color}" fill-opacity="0.1" stroke="none"/>`;
      }
      paths += `<path d="${pathD}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`;
    });

    let legend = '';
    if (!hideLegend && validLines.length > 1) {
      const items = validLines.map((l, i) => {
        const color = l.color || 'var(--accent)';
        return `<span style="display:inline-flex;align-items:center;gap:4px;margin-right:12px;font-size:10px;color:var(--text-secondary)"><span style="width:8px;height:8px;border-radius:50%;background:${color}"></span>${l.label || `Series ${i+1}`}</span>`;
      }).join('');
      legend = `<foreignObject x="${pad.left}" y="2" width="${w}" height="18"><div xmlns="http://www.w3.org/1999/xhtml" style="display:flex;align-items:center;justify-content:flex-start">${items}</div></foreignObject>`;
    }

    return `
      <svg ${responsive ? `width="100%" height="100%"` : `width="${width}" height="${height}"`} viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" style="display:block">
        ${gridLines}
        ${yText}
        ${paths}
        ${labelText}
        ${legend}
      </svg>`;
  },

  barChart(data, opts = {}) {
    const { width = 400, height = 120, color = 'var(--accent)', barHeight = 8, gap = 8 } = opts;
    if (!data || !data.length) {
      return `<svg width="${width}" height="${height}"><text x="${width/2}" y="${height/2}" text-anchor="middle" fill="var(--text-muted)" font-size="12">No data</text></svg>`;
    }
    const max = Math.max(...data.map(d => d.value || 0));
    const maxBar = max || 1;
    let y = 10;
    let svg = `<svg width="${width}" height="${height}">`;
    data.forEach(d => {
      const pct = ((d.value || 0) / maxBar) * (width * 0.6);
      svg += `<text x="0" y="${y + 10}" fill="var(--text-primary)" font-size="11">${d.label || ''}</text>`;
      svg += `<text x="${width * 0.65 + 4}" y="${y + 10}" fill="var(--text-secondary)" font-size="11">${d.value || 0}</text>`;
      svg += `<text x="${width * 0.8 + 4}" y="${y + 10}" fill="var(--text-muted)" font-size="11">${d.pct || ''}</text>`;
      svg += `<rect x="${width * 0.25}" y="${y}" width="${pct}" height="${barHeight}" rx="3" fill="${color}" fill-opacity="0.85"/>`;
      svg += `<rect x="${width * 0.25}" y="${y}" width="${width * 0.6}" height="${barHeight}" rx="3" fill="var(--surface-raised)"/>`;
      svg += `<rect x="${width * 0.25}" y="${y}" width="${pct}" height="${barHeight}" rx="3" fill="${color}" fill-opacity="0.85"/>`;
      y += barHeight + gap;
    });
    svg += '</svg>';
    return svg;
  },

  donutChart(data, opts = {}) {
    const { size = 120, strokeWidth = 10, colors = ['var(--danger)','var(--warning)','var(--info)','var(--accent)'] } = opts;
    if (!data || !data.length) {
      return `<svg width="${size}" height="${size}"><circle cx="${size/2}" cy="${size/2}" r="${size/2 - strokeWidth}" fill="none" stroke="var(--border)" stroke-width="${strokeWidth}"/></svg>`;
    }
    const total = data.reduce((s, d) => s + (d.value || 0), 0);
    const r = (size - strokeWidth) / 2;
    const c = 2 * Math.PI * r;
    let offset = 0;
    let svg = `<svg width="${size}" height="${size}"><g transform="rotate(-90 ${size/2} ${size/2})">`;
    data.forEach((d, i) => {
      const v = total ? (d.value / total) * c : 0;
      const col = d.color || colors[i % colors.length];
      svg += `<circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${col}" stroke-width="${strokeWidth}" stroke-dasharray="${v} ${c - v}" stroke-dashoffset="${-offset}" stroke-linecap="butt"/>`;
      offset += v;
    });
    svg += '</g>';
    const centerText = opts.centerText || total.toString();
    svg += `<text x="${size/2}" y="${size/2 - 2}" text-anchor="middle" fill="var(--text-primary)" font-size="16" font-weight="700">${centerText}</text>`;
    if (opts.centerLabel) {
      svg += `<text x="${size/2}" y="${size/2 + 14}" text-anchor="middle" fill="var(--text-secondary)" font-size="10">${opts.centerLabel}</text>`;
    }
    svg += '</svg>';
    return svg;
  },
};
