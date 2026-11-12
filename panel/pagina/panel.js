(() => {
  const F = (d) => (v) => v.toLocaleString('es', { minimumFractionDigits: d, maximumFractionDigits: d }).replace('-', '−');
  const signed = (d) => (v) => (v > 0 ? '+' : '') + F(d)(v) + ' %';
  const fmt = {
    num2: F(2), int: F(0), dec1: F(1),
    pct0: (v) => F(0)(v) + ' %', pct1: (v) => F(1)(v) + ' %', pct2: (v) => F(2)(v) + ' %',
    spct1: signed(1), spct2: signed(2),
    date: (s) => new Date(s + 'T00:00:00Z').toLocaleDateString('es', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }),
    fechaCorta: (s) => new Date(s + 'T00:00:00Z').toLocaleDateString('es', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }),
    sino: (v) => (v ? 'Sí' : 'No'),
    text: String,
  };
  const shortDate = (d) => d.toLocaleDateString('es', { month: 'short', year: '2-digit', timeZone: 'UTC' });

  dash.calc('resumen', {
    inputs: ['activos'],
    title: 'Índices sobre su promedio de 200 días',
    description: 'Cuenta cuántos índices cerraron por encima de su promedio móvil de 200 días.',
    fn: (activos) => [{ sobre: activos.filter((a) => a.sobre_pm200).length, total: activos.length }],
  });
  dash.calc('balance', {
    inputs: ['senales'],
    title: 'Balance histórico de los filtros de tendencia',
    description: 'Cuenta en cuántos casos la regla rindió menos que el índice y en cuántos tuvo una caída máxima menor.',
    fn: (senales) => {
      const reglas = senales.filter((s) => s.tipo === 'tendencia');
      return [{
        total: reglas.length,
        menos: reglas.filter((s) => s.regla_retorno < s.indice_retorno).length,
        menor_caida: reglas.filter((s) => s.regla_caida > s.indice_caida).length,
      }];
    },
  });

  const pick = (el, g) => {
    const [k, v] = (el.dataset.where || '').split('=');
    const data = Array.isArray(g.data) ? g.data : [];
    return k ? data.find((r) => String(r[k]) === decodeURIComponent(v)) : data[+el.dataset.row || 0];
  };

  dash.draw('val', (el) => {
    const g = dash.data(el.dataset.source);
    if (g.status !== 'loading') el.classList.remove('dash-skeleton');
    const r = g.status === 'ok' ? pick(el, g) : null;
    const v = r ? r[el.dataset.field] : null;
    el.textContent = v == null ? '—' : (fmt[el.dataset.fmt] || String)(v);
    if (el.dataset.tone === 'change') el.dataset.sign = v > 0 ? 'up' : v < 0 ? 'down' : 'flat';
  });

  dash.draw('regimen', (el) => {
    const g = dash.data(el.dataset.source);
    const r = g.status === 'ok' ? pick(el, g) : null;
    if (!r) { el.textContent = '—'; delete el.dataset.state; return; }
    el.textContent = r.sobre_pm200 ? 'Sobre el PM200' : 'Bajo el PM200';
    el.dataset.state = r.sobre_pm200 ? 'ok' : 'warn';
  });

  // Columnas de cada tabla: campo, formato y tratamiento
  const T = {
    estado: { src: 'activos', key: 'ticker', cols: [['ticker', 'text', 'l'], ['cambio_1m', 'spct1', 'tone'], ['cambio_1a', 'spct1', 'tone'], ['dist_pm40', 'spct1'], ['dist_pm200', 'spct1'], ['pm20_sobre_pm40', 'sino'], ['dias_en_regimen', 'int']] },
    tendencia: { src: 'senales', key: 'id', filter: (r) => r.tipo === 'tendencia', cols: [['ticker', 'text', 'l'], ['regla', 'text', 'l'], ['estado', 'text', 'pill'], ['regla_retorno', 'pct1'], ['indice_retorno', 'pct1'], ['regla_caida', 'pct1'], ['indice_caida', 'pct1'], ['exposicion', 'pct0']] },
    reversion: { src: 'senales', key: 'id', filter: (r) => r.tipo === 'reversion', cols: [['ticker', 'text', 'l'], ['rsi2', 'dec1'], ['estado', 'text', 'pill'], ['operaciones', 'int'], ['pct_ganadoras', 'pct1'], ['retorno_medio', 'spct2'], ['peor_operacion', 'pct1'], ['dias_medios', 'dec1'], ['ultima_entrada', 'fechaCorta']] },
    riesgo: { src: 'activos', key: 'ticker', cols: [['ticker', 'text', 'l'], ['caida_actual', 'pct1'], ['dias_desde_maximo', 'int'], ['caida_maxima_historica', 'pct1'], ['volatilidad_20d', 'pct1'], ['volatilidad_mediana', 'pct1'], ['volatilidad_percentil', 'int', 'bar']] },
    regimen: { src: 'activos', key: 'ticker', cols: [['ticker', 'text', 'l'], ['sobre_dias', 'int'], ['sobre_retorno', 'pct1'], ['sobre_volatilidad', 'pct1'], ['bajo_dias', 'int'], ['bajo_retorno', 'pct1'], ['bajo_volatilidad', 'pct1']] },
  };

  dash.draw('filas', (tb) => {
    const cfg = T[tb.dataset.tabla];
    const g = cfg ? dash.data(cfg.src) : { status: 'missing' };
    const rows = g.status === 'ok' && Array.isArray(g.data) ? g.data.filter(cfg.filter || (() => true)) : [];
    tb.replaceChildren(...rows.map((r) => {
      const tr = document.createElement('tr');
      tr.dataset.key = encodeURIComponent(r[cfg.key]);
      cfg.cols.forEach(([f, k, mode]) => {
        const td = document.createElement('td');
        const v = r[f];
        const txt = v == null ? '—' : fmt[k](v);
        if (mode === 'l') td.className = 'mp-l';
        if (mode === 'pill') {
          td.className = 'mp-l';
          const s = document.createElement('span');
          s.className = 'mp-pill';
          s.dataset.state = r.activa ? 'ok' : 'idle';
          s.textContent = txt;
          td.append(s);
        } else if (mode === 'bar' && v != null) {
          td.append(txt);
          const b = document.createElement('span');
          b.className = 'mp-bar';
          const i = document.createElement('i');
          i.style.width = Math.max(0, Math.min(100, v)) + '%';
          b.append(i);
          td.append(b);
        } else {
          td.textContent = txt;
          if (mode === 'tone' && v != null) td.dataset.sign = v > 0 ? 'up' : v < 0 ? 'down' : 'flat';
        }
        tr.append(td);
      });
      return tr;
    }));
  });

  // Gráficos del índice elegido
  window.mpSel = 'SPY';

  dash.draw('sel', (el) => {
    const g = dash.data('activos');
    const r = g.status === 'ok' && Array.isArray(g.data) ? g.data.find((x) => x.ticker === window.mpSel) : null;
    el.textContent = r ? r.nombre : window.mpSel;
  });

  function chart(el, cfg) {
    const g = dash.data('series');
    el.classList.toggle('dash-skeleton', g.status === 'loading');
    el.replaceChildren();
    if (g.status !== 'ok' || !Array.isArray(g.data)) {
      if (g.status === 'error') {
        const p = document.createElement('p');
        p.className = 'mp-fail';
        p.textContent = 'No se pudo cargar';
        el.append(p);
      }
      return;
    }
    const rows = g.data.filter((r) => r.ticker === window.mpSel).map((r) => ({ ...r, t: new Date(r.fecha + 'T00:00:00Z') }));
    if (!rows.length) return;

    const W = Math.max(280, el.clientWidth), H = cfg.h;
    const svg = d3.select(el).append('svg').attr('width', '100%').attr('height', H).attr('viewBox', `0 0 ${W} ${H}`)
      .attr('role', 'img').attr('aria-label', cfg.aria + ' de ' + window.mpSel);
    const vals = rows.flatMap((r) => cfg.keys.map((k) => r[k])).filter((v) => v != null);
    const y = d3.scaleLinear().domain(cfg.zero ? [d3.min(vals), 0] : d3.extent(vals)).nice(5);
    const ticks = y.ticks(5);

    // Márgenes medidos con las etiquetas ya dibujadas
    const probe = svg.append('g');
    const width = (s) => probe.append('text').attr('class', 'mp-tick').text(s).node().getComputedTextLength();
    const ml = Math.ceil(d3.max(ticks, (t) => width(cfg.tick(t)))) + 10;
    const mr = cfg.keys.length > 1 ? Math.ceil(d3.max(cfg.keys, (k) => width(cfg.labels[k]))) + 12 : 10;
    probe.remove();
    const m = { t: 10, r: mr, b: 24, l: ml };
    const x = d3.scaleUtc().domain(d3.extent(rows, (r) => r.t)).range([m.l, W - m.r]);
    y.range([H - m.b, m.t]);

    svg.append('g').selectAll('line').data(ticks).join('line').attr('class', (t) => (cfg.zero && t === 0 ? 'mp-zero' : 'mp-grid'))
      .attr('x1', m.l).attr('x2', W - m.r).attr('y1', (t) => y(t)).attr('y2', (t) => y(t));
    svg.append('g').selectAll('text').data(ticks).join('text').attr('class', 'mp-tick').attr('x', m.l - 8).attr('y', (t) => y(t))
      .attr('dy', '0.32em').attr('text-anchor', 'end').text((t) => cfg.tick(t));
    const xt = x.ticks(Math.max(2, Math.floor((W - m.l - m.r) / 90)));
    svg.append('g').selectAll('text').data(xt).join('text').attr('class', 'mp-tick').attr('x', (t) => x(t)).attr('y', H - 6)
      .attr('text-anchor', 'middle').text(shortDate);

    if (cfg.area) {
      svg.append('path').datum(rows).attr('d', d3.area().x((r) => x(r.t)).y0(y(0)).y1((r) => y(r[cfg.keys[0]])))
        .style('fill', dash.colors[0]).style('opacity', 0.18);
    }
    cfg.keys.slice().reverse().forEach((k) => {
      const i = cfg.keys.indexOf(k);
      svg.append('path').datum(rows.filter((r) => r[k] != null)).attr('fill', 'none')
        .attr('d', d3.line().x((r) => x(r.t)).y((r) => y(r[k])))
        .style('stroke', dash.colors[i]).attr('stroke-width', i === 0 ? 2 : 1.5).attr('stroke-linejoin', 'round');
    });

    const last = rows[rows.length - 1];
    if (cfg.keys.length > 1) {
      const ends = cfg.keys.filter((k) => last[k] != null).map((k) => ({ k, y: y(last[k]) })).sort((a, b) => a.y - b.y);
      for (let i = 1; i < ends.length; i++) ends[i].y = Math.max(ends[i].y, ends[i - 1].y + 13);
      const over = ends.length ? ends[ends.length - 1].y - (H - m.b) : 0;
      if (over > 0) ends.forEach((e) => { e.y -= over; });
      svg.append('g').selectAll('text').data(ends).join('text').attr('class', 'mp-tick').attr('x', W - m.r + 6).attr('y', (e) => e.y)
        .attr('dy', '0.32em').text((e) => cfg.labels[e.k]);
    }
    svg.append('circle').attr('cx', x(last.t)).attr('cy', y(last[cfg.keys[0]])).attr('r', 3.5).style('fill', dash.colors[0])
      .style('stroke', 'var(--color-bg)').attr('stroke-width', 2);

    // Lectura al pasar el puntero o tocar
    const rule = svg.append('line').attr('class', 'mp-rule').attr('y1', m.t).attr('y2', H - m.b).style('display', 'none');
    const tip = document.createElement('div');
    tip.className = 'mp-tip';
    tip.style.display = 'none';
    el.append(tip);
    const bis = d3.bisector((r) => r.t).center;
    const show = (ev) => {
      const [px] = d3.pointer(ev, svg.node());
      const r = rows[bis(rows, x.invert(px * (W / svg.node().getBoundingClientRect().width)))];
      if (!r) return;
      rule.style('display', null).attr('x1', x(r.t)).attr('x2', x(r.t));
      const head = document.createElement('div');
      head.className = 'mp-tip-d';
      head.textContent = fmt.date(r.fecha);
      tip.replaceChildren(head, ...cfg.keys.filter((k) => r[k] != null).map((k, i) => {
        const line = document.createElement('div');
        line.className = 'mp-tip-r';
        const sw = document.createElement('i');
        sw.className = 'mp-sw';
        sw.style.background = dash.colors[cfg.keys.indexOf(k)];
        const b = document.createElement('b');
        b.textContent = cfg.value(r[k]);
        line.append(sw, cfg.labels[k], b);
        return line;
      }));
      tip.style.display = 'block';
      const tw = tip.offsetWidth, pos = x(r.t) * (el.clientWidth / W);
      tip.style.left = Math.max(0, Math.min(el.clientWidth - tw, pos + 12 + tw > el.clientWidth ? pos - tw - 12 : pos + 12)) + 'px';
    };
    const hide = () => { rule.style('display', 'none'); tip.style.display = 'none'; };
    svg.on('pointermove', show).on('pointerdown', show).on('pointerleave', hide);
  }

  dash.draw('precio', (el) => chart(el, {
    h: 280, keys: ['cierre', 'pm200', 'pm40'], labels: { cierre: 'Cierre', pm200: 'PM200', pm40: 'PM40' },
    tick: F(0), value: F(2), aria: 'Cierre diario y promedios móviles de 200 y 40 días',
  }));
  dash.draw('caida', (el) => chart(el, {
    h: 170, keys: ['caida'], labels: { caida: 'Caída' }, zero: true, area: true,
    tick: (v) => F(0)(v) + ' %', value: (v) => F(1)(v) + ' %', aria: 'Caída porcentual desde el máximo histórico',
  }));

  document.querySelectorAll('.mp-seg button').forEach((b) => b.addEventListener('click', () => {
    window.mpSel = b.dataset.ticker;
    document.querySelectorAll('.mp-seg button').forEach((o) => o.setAttribute('aria-pressed', String(o === b)));
    ['sel', 'precio', 'caida'].forEach((n) => dash.draw(n));
  }));

  dash.onData(() => {
    document.querySelectorAll('.mp-sw[data-k]').forEach((s) => { s.style.background = dash.colors[+s.dataset.k]; });
  });
})();
