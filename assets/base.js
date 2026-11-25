/* 共用工具 + 导航 + 图表渲染 */
(function () {
  const D = window.DATA || {};
  const $ = id => document.getElementById(id);
  const fmt = (v, d = 1) => (v == null ? '-' : (v > 0 ? '+' : '') + Number(v).toFixed(d));
  const fmt0 = v => fmt(v, 0);
  const cls = v => (v > 0 ? 'up' : (v < 0 ? 'dn' : ''));
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const PAGES = [
    ['index.html', '今日整体'],
    ['duanxian.html', '短线情绪'],
    ['qushi.html', '趋势波段'],
    ['guojia.html', '国家队/ETF'],
  ];

  function nav(active) {
    return '<nav class="nav">' + PAGES.map(([h, n]) =>
      `<a href="${h}" class="${h === active ? 'on' : ''}">${n}</a>`).join('') + '</nav>';
  }

  function mount(opt) {
    document.body.insertAdjacentHTML('afterbegin', '<div class="wrap" id="wrap"></div>');
    const wrap = $('wrap');
    wrap.insertAdjacentHTML('beforeend', nav(opt.page) +
      `<header><h1>${esc(opt.title)}<span id="dt"></span></h1><div class="badges" id="badges"></div></header>` +
      '<div id="body"></div><footer id="foot"></footer>');
    const t = D.today || {};
    const rg = D.regime || {};
    const s = D.sentiment || {};
    $('dt').textContent = (D.date || '') + (opt.suffix == null ? ' 收盘 ・ 生成于 ' + (D.generatedAt || '') : opt.suffix);
    const b = [];
    if (opt.badges) b.push(opt.badges.join(''));
    if (s.score != null) b.push(`<span class="badge cool">情绪分 ${s.score} · ${esc(s.phase || '')}</span>`);
    if (t.total != null) b.push(`<span class="badge ${t.total > 0 ? 'hot' : 'cool'}">今日全市场 ${fmt0(t.total)} 亿</span>`);
    if (rg.threeX) b.push(`<span class="badge">三X：${esc(rg.threeX)}</span>`);
    $('badges').innerHTML = b.join('');
    $('foot').innerHTML = opt.foot || defaultFoot();
    return $('body');
  }

  function defaultFoot() {
    const s = D.sentiment || {};
    return `数据口径：主力净流入＝超大单＋大单（东财行业板块 496 个），单位亿元。<br>
      题材口径＝同花顺涨停板块（概念）涨停家数与连板数，叠加东财行业资金面印证；玄学炒作按公告原文关键词标注。<br>
      情绪指标：涨停 ${s.ztCount ?? '-'} / 跌停 ${s.dtCount ?? '-'} / 炸板 ${s.zbCount ?? '-'}，炸板率取整百分比，连板高度取整。<br>
      生成：export_data.py ・ 数据更新至 ${D.date || ''}。仅用于跟踪验证，不构成投资建议。`;
  }

  /* 柱+累计线 */
  function barLine(el, rows, opt) {
    opt = opt || {};
    rows = (rows || []).filter(r => r && r.v != null || r && r.cum != null);
    if (!el || !rows.length) return;
    const W = 900, H = 250, padL = 50, padR = 54, padB = 28, padT = 14;
    const n = rows.length;
    const maxV = Math.max(...rows.map(r => Math.abs(r.v || 0)), 1);
    const cums = rows.map(r => r.cum || 0);
    let cMin = Math.min(...cums, 0), cMax = Math.max(...cums, 0);
    if (cMax - cMin < 1) { cMax += 1; cMin -= 1; }
    const zero = padT + (H - padT - padB) / 2, sc = (H - padT - padB) / 2 / maxV, bw = (W - padL - padR) / n;
    let s = '';
    [-1, -0.5, 0, 0.5, 1].forEach(k => {
      const y = zero - k * (H - padT - padB) / 2;
      s += `<line class="axis" x1="${padL}" x2="${W - padR}" y1="${y}" y2="${y}" opacity="${k === 0 ? .9 : .3}"/>`;
      s += `<text x="${padL - 7}" y="${y + 3}" text-anchor="end">${(k * maxV).toFixed(0)}</text>`;
    });
    [cMin, (cMin + cMax) / 2, cMax].forEach(k => {
      const y = H - padB - ((k - cMin) / (cMax - cMin)) * (H - padT - padB);
      s += `<text x="${W - padR + 7}" y="${y + 3}" text-anchor="start" fill="#6f8ab5">${k.toFixed(0)}</text>`;
    });
    rows.forEach((r, i) => {
      if (r.v == null) return;
      const x = padL + i * bw + bw * .18, w = bw * .64, h = Math.abs(r.v) * sc, y = r.v >= 0 ? zero - h : zero;
      s += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${w.toFixed(1)}" height="${Math.max(h, .6).toFixed(1)}" rx="1.5" fill="${r.v >= 0 ? '#f0483e' : '#22b573'}" opacity=".85"><title>${r.d} ${fmt(r.v)} 亿 ・ 累计 ${fmt(r.cum)} 亿</title></rect>`;
      if (i % 4 === 0 || i === n - 1) s += `<text x="${(x + w / 2).toFixed(1)}" y="${H - 8}" text-anchor="middle">${r.d.slice(5)}</text>`;
    });
    const pts = rows.map((r, i) => `${(padL + i * bw + bw / 2).toFixed(1)},${(H - padB - ((r.cum - cMin) / (cMax - cMin)) * (H - padT - padB)).toFixed(1)}`).join(' ');
    s += `<polyline points="${pts}" fill="none" stroke="#4a8cff" stroke-width="1.6" opacity=".9"/>`;
    el.innerHTML = s;
  }

  /* 横向条形列表 */
  function rows(el, list, withPct) {
    if (!el) return;
    list = list || [];
    const max = Math.max(...list.map(x => Math.abs(x.v)), .001);
    el.innerHTML = list.map(x => {
      const w = Math.max(Math.abs(x.v) / max * 100, 1.5);
      return `<div class="row"><div class="nm" title="${esc(x.name)}">${esc(x.name)}</div>
        <div class="bar"><i class="${x.v >= 0 ? 'up' : 'dn'}" style="width:${w}%"></i></div>
        <div class="val ${cls(x.v)}">${fmt(x.v)}${withPct && x.pct != null ? `<span class="pct">${fmt(x.pct, 2)}%</span>` : ''}</div></div>`;
    }).join('');
  }

  window.APP = { D, $, fmt, fmt0, cls, esc, nav, mount, barLine, rows, defaultFoot };
  window.DATA = D;
})();
