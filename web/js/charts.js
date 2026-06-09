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
        <path d="${pathD}" stroke="${color}" fill="none"/>
      </svg>`;
  },

  lineChart(data, opts = {}) {
    const { width = 600, height = 200, color = 'var(--accent)', strokeWidth = 2, fillArea = true, grid = true, labels = [], responsive = false } = opts;
    if (!data || data.length < 2) {
      return `<svg ${responsive ? `width="100%" height="100%"` : `width="${width}" height="${height}"`} viewBox="0 0 ${width} ${height}"><text x="${width/2}" y="${height/2}" text-anchor="middle" fill="var(--text-muted)" font-size="12">No data</text></svg>`;
    }
    const pad = { top: 10, right: 10, bottom: 30, left: 40 };
    const w = width - pad.left - pad.right;
    const h = height - pad.top - pad.bottom;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;
    const stepX = w / (data.length - 1);
    const points = data.map((v, i) => {
      const x = pad.left + i * stepX;
      const y = pad.top + h - ((v - min) / range) * h;
      return [x, y];
    });
    const pathD = `M ${points.map(p => p.join(',')).join(' L ')}`;
    let areaD = '';
    if (fillArea) {
      areaD = `M ${points[0].join(',')} L ${points.map(p => p.join(',')).join(' L ')} L ${points[points.length-1][0]},${pad.top + h} L ${points[0][0]},${pad.top + h} Z`;
    }

    let gridLines = '';
    if (grid) {
      for (let i = 0; i <= 4; i++) {
        const y = pad.top + (h / 4) * i;
        gridLines += `<line x1="${pad.left}" y1="${y}" x2="${pad.left + w}" y2="${y}" stroke="var(--border)" stroke-dasharray="2,2"/>`;
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

    const yLabels = [min, (min + max) / 2, max].map(v => v.toFixed(1));
    let yText = '';
    yLabels.forEach((t, i) => {
      const y = pad.top + h - (i / 2) * h;
      yText += `<text x="${pad.left - 6}" y="${y + 4}" text-anchor="end" fill="var(--text-muted)" font-size="10">${t}</text>`;
    });

    return `
      <svg ${responsive ? `width="100%" height="100%"` : `width="${width}" height="${height}"`} viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
        ${gridLines}
        ${yText}
        ${fillArea ? `<path d="${areaD}" fill="${color}" fill-opacity="0.1" stroke="none"/>` : ''}
        <path d="${pathD}" fill="none" stroke="${color}" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round"/>
        ${labelText}
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
