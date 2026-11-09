/* Giao diện biểu đồ — chỉ HIỂN THỊ dữ liệu đã tính sẵn bởi pipeline (site/data/*.json); không tự tính chỉ báo.
   Mọi kết quả (chỉ báo, swing, đường xu hướng, vùng S/R, pivot) là nhân quả: tại nến i chỉ dùng dữ liệu <= i,
   nên chế độ replay chỉ cần hé lộ dần đến nến hiện tại. */
(function () {
  'use strict';
  var LW = window.LightweightCharts;
  var OFFSET = 7 * 3600; // hiển thị giờ Việt Nam (UTC+7) trên trục thời gian của thư viện (vốn dùng UTC)

  // ------------------------------------------------------------------ tiện ích
  function $(s, r) { return (r || document).querySelector(s); }
  function $all(s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); }
  function LSget(k, d) { try { var v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } }
  function LSset(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* bỏ qua */ } }
  function fmt(x, d) { d = d || 0; return (x == null || isNaN(x)) ? '—' : Number(x).toLocaleString('vi-VN', { minimumFractionDigits: d, maximumFractionDigits: d }); }
  function fmtSigned(x, d) { return x == null ? '—' : (x > 0 ? '+' : '') + fmt(x, d); }
  function cssv(n) { return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function dirClass(x) { return x > 0 ? 'up' : (x < 0 ? 'down' : 'ref'); }
  function two(n) { return n < 10 ? '0' + n : '' + n; }
  function vnDate(t) { return new Date((t + OFFSET) * 1000).toISOString().slice(0, 10); }
  function vnHM(t) { return new Date((t + OFFSET) * 1000).toISOString().slice(11, 16); }
  function vnDMY(t) { var d = vnDate(t).split('-'); return d[2] + '/' + d[1] + '/' + d[0]; }
  function vnDMYHM(t) { return vnDMY(t) + ' ' + vnHM(t); }
  function isoToUnix(s) { return Math.floor(new Date(s).getTime() / 1000); }
  function toTime(t, res) { return res === 'D' ? vnDate(t) : t + OFFSET; }
  function ymdToDMY(s) { var d = s.split('-'); return d[2] + '/' + d[1] + '/' + d[0]; }

  var RES_LABEL = { 'D': '1D', '60': '60p', '15': '15p', '5': '5p', '1': '1p' };
  var RES_MIN = { 'D': 1440, '60': 60, '15': 15, '5': 5, '1': 1 };

  var TIPS = {
    ema: 'EMA(n): trung bình động hàm mũ, α = 2/(n+1), khởi tạo bằng SMA(n). Phản ứng nhanh hơn SMA với giá gần đây.',
    sma: 'SMA(n): trung bình cộng n giá đóng cửa gần nhất.',
    rsi: 'RSI(14) (Wilder) = 100 − 100/(1+RS); RS = trung bình mức tăng / trung bình mức giảm (làm mượt Wilder). Các ngưỡng 70/30 chỉ là quy ước; trong xu hướng mạnh RSI có thể ở vùng đó rất lâu.',
    macd: 'MACD(12,26,9) = EMA12 − EMA26; Signal = EMA9 của MACD; Histogram = MACD − Signal.',
    stoch: 'Stochastic (14,3,3) chậm: %K = SMA3 của 100·(C − đáy14)/(đỉnh14 − đáy14); %D = SMA3 của %K.',
    adx: 'ADX(14) (Wilder) đo độ MẠNH của xu hướng, không cho biết chiều. +DI/−DI so sánh lực tăng và lực giảm. Ngưỡng 20/25 là quy ước.',
    bb: 'Bollinger (20, 2): đường giữa = SMA20; biên = ± 2 độ lệch chuẩn tổng thể. %B = vị trí giá trong dải (0 = biên dưới, 1 = biên trên); Bandwidth = (trên − dưới)/giữa.',
    atr: 'ATR(14) (Wilder): trung bình làm mượt của biên độ thực (True Range) — thước đo mức biến động, đơn vị là giá.',
    vol: 'Khối lượng khớp lệnh (không gồm thỏa thuận). So với trung bình 20 nến để biết cao hay thấp so với thường lệ. Khối lượng nến phút chỉ mang tính tham khảo.',
    obv: 'OBV: cộng khối lượng khi giá đóng cửa tăng, trừ khi giảm. Giá trị tuyệt đối không có ý nghĩa, chỉ xem xu hướng/phân kỳ.',
    vwap: 'VWAP nội phiên = Σ(giá điển hình × KL)/ΣKL tính từ đầu phiên, reset mỗi ngày; giá điển hình = (H+L+C)/3.',
    dow: 'Xu hướng theo Dow (định nghĩa dự án): TĂNG khi đỉnh swing gần nhất cao hơn đỉnh trước VÀ đáy swing gần nhất cao hơn đáy trước; GIẢM khi cả hai thấp dần; còn lại là HỖN HỢP. Swing = fractal 5 nến, chỉ được biết sau 5 nến xác nhận.',
    tl: 'Đường xu hướng: nối các đáy swing cao dần (tăng) hoặc đỉnh swing thấp dần (giảm) đã xác nhận; chọn cặp có nhiều lần chạm nhất (cách đường ≤ 0,3 ATR) và chưa bị nến đóng cửa phá (vượt > 0,25 ATR). Quy ước của dự án, không phải định luật.',
    sr: 'Vùng hỗ trợ/kháng cự: gom các swing có giá cách nhau ≤ 0,5 ATR; cần ≥ 2 swing. Gọi là hỗ trợ khi nằm dưới giá, kháng cự khi nằm trên giá.',
    pivot: 'Pivot cổ điển tính từ cao/thấp/đóng của NGÀY GIAO DỊCH TRƯỚC: P=(H+L+C)/3; R1=2P−L; S1=2P−H; R2=P+(H−L); S2=P−(H−L).',
    patterns: 'Mô hình nến Nhật (chỉ hiển thị mô hình có hướng, sau xu hướng trước đó) và mô hình giá cổ điển (Double top/bottom, Head & Shoulders, tam giác). Quy tắc định lượng ở docs/patterns.md; mô hình chưa xác nhận chỉ là "đang hình thành".',
    fib: 'Fibonacci retracement tính từ hai swing đã xác nhận gần nhất ngược loại. Mức 50% là quy ước, không phải tỷ lệ Fibonacci; độ tin cậy thống kê của công cụ này hạn chế.'
  };

  // ------------------------------------------------------------------ trạng thái
  var DEFAULT_OPTS = {
    adv: { ema9: false, ema20: true, ema50: true, ema200: false, bb: false, vwap: false, pivot: false, trend: true, sr: true, swings: true, patterns: true, fib: false, rsi: true, macd: true, stoch: false, adx: false },
    basic: { ema9: false, ema20: true, ema50: true, ema200: false, bb: false, vwap: false, pivot: false, trend: true, sr: false, swings: false, patterns: false, fib: false, rsi: false, macd: false, stoch: false, adx: false }
  };
  var S = {
    board: null, gold: null, analysis: null, journal: null, backtest: null, hz: 'next_session', sym: 'FPT', res: 'D', mode: LSget('smr.mode', 'adv'),
    opts: null, data: null, cache: {}, cur: 0, times: [], timeIdx: null, view: 'chart',
    replay: { on: false, res: '1', day: null, timer: null, speed: 5, pending: null, markers: [], sessionGuesses: [], lastResult: null }
  };
  S.opts = Object.assign({}, DEFAULT_OPTS[S.mode], LSget('smr.opts.' + S.mode, {}));
  var C = null; // bộ biểu đồ hiện tại
  var seq = 0;

  function activeRes() { return S.replay.on ? S.replay.res : S.res; }
  function itemOf(sym) { return S.board ? S.board.items.filter(function (i) { return i.symbol === sym; })[0] : null; }
  function decimals(meta) { return meta.kind === 'vn' && meta.type !== 'index' ? 0 : 2; }

  // ------------------------------------------------------------------ tải dữ liệu
  function getJSON(url) {
    return fetch(url, { cache: 'no-cache' }).then(function (r) {
      if (!r.ok) throw new Error(url + ' → HTTP ' + r.status);
      return r.json();
    });
  }
  function loadSeries(sym, res) {
    var k = sym + '_' + res;
    if (S.cache[k]) return Promise.resolve(S.cache[k]);
    return getJSON('data/' + k + '.json').then(function (d) { S.cache[k] = d; return d; });
  }

  // ------------------------------------------------------------------ bảng giá & vàng trong nước
  function renderBoard() {
    var groups = [['Vàng', function (i) { return i.symbol === 'XAUUSD'; }], ['Cổ phiếu', function (i) { return i.type === 'stock'; }],
      ['ETF', function (i) { return i.type === 'etf'; }], ['Chỉ số', function (i) { return i.type === 'index'; }]];
    var h = '<table class="board"><thead><tr><th>Mã</th><th>Giá</th><th>+/−%</th></tr></thead><tbody>';
    groups.forEach(function (g) {
      var items = S.board.items.filter(g[1]);
      if (!items.length) return;
      h += '<tr class="group-row"><td colspan="3">' + g[0] + '</td></tr>';
      items.forEach(function (i) {
        var color = 'ref';
        if (i.pct > 0) color = 'up'; else if (i.pct < 0) color = 'down';
        if (i.ceiling != null && i.last === i.ceiling) color = 'ceil'; else if (i.floor != null && i.last === i.floor) color = 'floor';
        var st = i.trend_state_d, dot = st === 1 ? 'up' : (st === -1 ? 'down' : 'flat');
        var d = (i.type === 'index' || i.symbol === 'XAUUSD') ? 2 : 0;
        h += '<tr data-sym="' + i.symbol + '"' + (i.symbol === S.sym ? ' class="sel"' : '') + '><td><span class="sym">' + i.symbol + '</span><span class="sub">' + esc(shortName(i)) + '</span></td>' +
          '<td class="num ' + (color === 'ceil' ? '' : color) + '" style="' + (color === 'ceil' ? 'color:var(--ceil)' : color === 'floor' ? 'color:var(--floor)' : '') + '">' + fmt(i.last, d) + '</td>' +
          '<td class="num ' + dirClass(i.pct) + '"><span class="dot ' + dot + '" title="Xu hướng Dow khung ngày (chấm: xanh=tăng, đỏ=giảm, vàng=hỗn hợp)"></span>' + (i.pct == null ? '—' : fmtSigned(i.pct, 2) + '%') + '</td></tr>';
      });
    });
    h += '</tbody></table>';
    $('#board').innerHTML = h;
    var sel = $('#sym-select');
    if (sel) {
      sel.innerHTML = S.board.items.map(function (i) { return '<option value="' + i.symbol + '"' + (i.symbol === S.sym ? ' selected' : '') + '>' + i.symbol + ' — ' + esc(shortName(i)) + '</option>'; }).join('');
      sel.onchange = function () { selectSymbol(sel.value); };
    }
    $('#board-date').textContent = S.board.latest_session_date ? 'phiên ' + ymdToDMY(S.board.latest_session_date) : '';
    $all('#board tr[data-sym]').forEach(function (tr) {
      tr.addEventListener('click', function () { selectSymbol(tr.getAttribute('data-sym')); });
    });
  }
  function shortName(i) {
    var n = i.name || '';
    n = n.replace(/^Ngân hàng Thương mại Cổ phần /, 'NH ').replace(/^Công ty Cổ phần( - )?/, '').replace(/^Tổng Công ty /, 'TCT ');
    return n;
  }
  function renderGold() {
    var g = S.gold, b = $('#gold-body');
    if (!g || !g.sjc) { b.innerHTML = '<div class="muted">Chưa có đủ dữ liệu SJC/tỷ giá/giá thế giới.</div>'; return; }
    var q = isoToUnix(g.sjc.quoted_at);
    var h = '<table class="kv"><tr><td>SJC mua vào</td><td class="num">' + fmt(g.sjc.buy) + '</td></tr>' +
      '<tr><td>SJC bán ra</td><td class="num">' + fmt(g.sjc.sell) + '</td></tr>' +
      '<tr><td colspan="2" class="muted" style="font-size:12px">đồng/lượng · cập nhật ' + vnDMYHM(q) + '</td></tr>' +
      '<tr class="sep"><td colspan="2"><span class="help" title="' + esc(g.formula) + '">Chênh lệch so với giá thế giới quy đổi</span></td></tr>' +
      '<tr><td>Theo tỷ giá mua (' + fmt(g.usdvnd.buy) + ')</td><td class="num">' + fmt(g.premium_pct_sjc_sell.at_usdvnd_buy, 1) + '%</td></tr>' +
      '<tr><td>Theo tỷ giá bán (' + fmt(g.usdvnd.sell) + ')</td><td class="num">' + fmt(g.premium_pct_sjc_sell.at_usdvnd_sell, 1) + '%</td></tr></table>';
    h += '<p class="note">Độ chênh = giá SJC bán ra so với giá vàng thế giới spot (' + fmt(g.spot.xauusd, 1) + ' USD/oz, ' + esc(g.spot.source) + ') quy đổi sang đồng/lượng bằng tỷ giá Vietcombank. Hiển thị khoảng theo tỷ giá mua – bán.</p>';
    (g.warnings || []).forEach(function (w) { h += '<p class="note" style="color:var(--warn-text);background:var(--warn-bg);padding:4px 8px;border-radius:6px">' + esc(w) + '</p>'; });
    h += '<p class="note">' + esc(g.history_note) + ' Nguồn SJC: bên thứ ba (vnappmob), chưa phải bảng giá chính thức của SJC.</p>';
    b.innerHTML = h;
  }

  // ------------------------------------------------------------------ đầu trang mã + huy hiệu
  function renderHead() {
    var d = S.data, m = d.meta, it = itemOf(S.sym), dec = decimals(m), h = '';
    var live = !S.replay.on;
    var price, chg = null, pct = null;
    if (live && it) { price = it.last; chg = it.change; pct = it.pct; }
    else { price = d.c[S.cur]; }
    h += '<span class="sym">' + esc(S.sym === 'XAUUSD' ? 'Vàng (GC=F)' : S.sym) + '</span><span class="name">' + esc(m.name) + '</span>';
    h += '<span class="price num ' + (live ? dirClass(chg) : '') + '">' + fmt(price, dec) + '</span>';
    if (live && chg != null) h += '<span class="num ' + dirClass(chg) + '" style="font-weight:700">' + fmtSigned(chg, dec) + ' (' + fmtSigned(pct, 2) + '%)</span>';
    if (!live) h += '<span class="muted">giá đóng nến ' + vnHM(d.t[S.cur]) + ' (phát lại)</span>';
    var chips = '';
    if (live && it && it.ref != null && it.ceiling != null) {
      chips += '<span class="chip ceil">Trần <b class="num">' + fmt(it.ceiling, 0) + '</b></span><span class="chip ref">TC <b class="num">' + fmt(it.ref, 0) + '</b></span><span class="chip floor">Sàn <b class="num">' + fmt(it.floor, 0) + '</b></span>';
    } else if (live && it && it.ref != null) {
      chips += '<span class="chip ref">Hôm trước <b class="num">' + fmt(it.ref, dec) + '</b></span>';
    }
    if (live && it && it.nm_volume != null) chips += '<span class="chip">KL khớp <b class="num">' + fmt(it.nm_volume) + '</b></span>';
    if (live && it && it.pt_volume) chips += '<span class="chip">KL thỏa thuận <b class="num">' + fmt(it.pt_volume) + '</b></span>';
    h += '<div class="chips">' + chips + '</div>';
    $('#inst-head').innerHTML = h;

    var b = '';
    var fetched = isoToUnix(m.prices_fetched_at), ageH = (Date.now() / 1000 - fetched) / 3600;
    if (S.replay.on) {
      b += '<span class="badge warn">ĐANG PHÁT LẠI phiên ' + ymdToDMY(S.replay.day) + ' — dữ liệu quá khứ, không phải real-time</span>';
    } else {
      b += '<span class="badge">Nến cuối: ' + vnDMYHM(isoToUnix(m.data_as_of)) + ' · tải lúc ' + vnDMYHM(fetched) + ' · không phải dữ liệu real-time</span>';
      if (ageH > 30) b += '<span class="badge warn">Dữ liệu đã cũ (' + Math.round(ageH) + ' giờ) — có thể pipeline chưa chạy</span>';
      if (m.last_complete_index != null && m.last_complete_index < m.rows - 1) b += '<span class="badge warn">Nến cuối chưa hoàn tất — chỉ báo trên nến này là tạm thời</span>';
    }
    if (m.price_adjusted) b += '<span class="badge" title="Giá quá khứ được điều chỉnh hồi tố theo cổ tức/thưởng cổ phiếu để chuỗi liên tục; có thể khác giá đã giao dịch thực tế.">Giá đã điều chỉnh</span>';
    if (m.is_futures) b += '<span class="badge warn" title="GC=F là hợp đồng tương lai vàng COMEX (front-month), có chênh lệch (basis) so với spot và có thể nhảy giá khi chuyển hợp đồng.">Vàng COMEX (futures), không phải spot XAU/USD</span>';
    if (m.resolution !== 'D' && m.has_volume) b += '<span class="badge">Khối lượng nến phút chỉ tham khảo</span>';
    if (m.kind === 'vn' && m.resolution !== 'D' && d.sessions && d.sessions.length) {
      var ls = d.sessions[d.sessions.length - 1], bars = ls[2] - ls[1] + 1, expected = Math.floor(225 / RES_MIN[m.resolution]);
      if (bars < 0.7 * expected) b += '<span class="badge warn" title="Phút không có giao dịch thì không có nến; chỉ báo tính trên các nến có giao dịch.">Thanh khoản thấp: nến thưa (' + bars + '/' + expected + ' nến ở phiên cuối)</span>';
    }
    $('#badges').innerHTML = b;
  }

  // ------------------------------------------------------------------ thanh công cụ
  var OVERLAY_DEF = [
    { id: 'ema9', label: 'EMA9', color: '--ema9', adv: true }, { id: 'ema20', label: 'EMA20', color: '--ema20' },
    { id: 'ema50', label: 'EMA50', color: '--ema50' }, { id: 'ema200', label: 'EMA200', color: '--ema200', adv: true },
    { id: 'bb', label: 'Bollinger', color: '--bb', adv: true }, { id: 'vwap', label: 'VWAP', color: '--vwap', adv: true, intradayVn: true },
    { id: 'pivot', label: 'Pivot', color: '--pivot', adv: true }, { id: 'trend', label: 'Đường xu hướng', color: '--trend-up' },
    { id: 'sr', label: 'Hỗ trợ/Kháng cự', color: '--sr', adv: true }, { id: 'swings', label: 'Swing', color: '--muted', adv: true }, { id: 'patterns', label: 'Mô hình nến/giá', color: '--accent', adv: true },
    { id: 'fib', label: 'Fibonacci', color: '--fib', adv: true }
  ];
  var PANE_DEF = [{ id: 'rsi', label: 'RSI' }, { id: 'macd', label: 'MACD' }, { id: 'stoch', label: 'Stoch' }, { id: 'adx', label: 'ADX' }];

  function renderToolbar() {
    var adv = S.mode === 'adv', h = '';
    var m = S.data ? S.data.meta : null;
    if (!S.replay.on) {
      h += '<div class="group"><span class="lab">Khung</span><div class="seg" id="res-seg">';
      ['D', '60', '15', '5', '1'].forEach(function (r) {
        if (!adv && (r === '5' || r === '1')) return;
        h += '<button data-res="' + r + '" aria-pressed="' + (S.res === r) + '">' + RES_LABEL[r] + '</button>';
      });
      h += '</div></div>';
    }
    h += '<div class="group"><span class="lab">Lớp phủ</span>';
    OVERLAY_DEF.forEach(function (o) {
      if (!adv && o.adv) return;
      if (o.intradayVn && !(m && m.kind === 'vn' && m.resolution !== 'D')) return;
      h += '<label title="' + esc(TIPS[o.id] || TIPS[o.id.replace(/\d+/, '')] || '') + '"><input type="checkbox" data-opt="' + o.id + '"' + (S.opts[o.id] ? ' checked' : '') + '><span class="swatch" style="background:var(' + o.color + ')"></span>' + o.label + '</label>';
    });
    h += '</div>';
    if (adv) {
      h += '<div class="group"><span class="lab">Chỉ báo</span>';
      PANE_DEF.forEach(function (p) { h += '<label title="' + esc(TIPS[p.id]) + '"><input type="checkbox" data-opt="' + p.id + '"' + (S.opts[p.id] ? ' checked' : '') + '>' + p.label + '</label>'; });
      h += '</div>';
    }
    h += '<div class="group" style="margin-left:auto"><button class="btn ' + (S.replay.on ? 'primary' : '') + '" id="replay-toggle" title="Phát lại từng nến của một phiên đã qua để tập đọc biểu đồ">' + (S.replay.on ? 'Thoát phát lại' : '▶ Phát lại phiên') + '</button></div>';
    $('#toolbar').innerHTML = h;
    $all('#res-seg button').forEach(function (b) { b.addEventListener('click', function () { S.res = b.getAttribute('data-res'); reload(true); }); });
    $all('#toolbar input[data-opt]').forEach(function (cb) {
      cb.addEventListener('change', function () {
        S.opts[cb.getAttribute('data-opt')] = cb.checked; LSset('smr.opts.' + S.mode, S.opts);
        var paneChange = PANE_DEF.some(function (p) { return p.id === cb.getAttribute('data-opt'); });
        if (paneChange) rebuild(false); else { applyOverlayVisibility(); renderStruct(S.cur); }
      });
    });
    $('#replay-toggle').addEventListener('click', toggleReplay);
  }

  // ------------------------------------------------------------------ dựng biểu đồ
  function baseOptions(dec, showTime) {
    return {
      autoSize: true,
      layout: { background: { type: 'solid', color: cssv('--panel') }, textColor: cssv('--muted'), fontSize: 12 },
      grid: { vertLines: { color: cssv('--grid') }, horzLines: { color: cssv('--grid') } },
      rightPriceScale: { borderColor: cssv('--border'), minimumWidth: 84 },
      timeScale: { borderColor: cssv('--border'), timeVisible: activeRes() !== 'D', secondsVisible: false, rightOffset: 10, barSpacing: 8, visible: showTime },
      crosshair: { mode: 0, vertLine: { color: cssv('--crosshair'), labelBackgroundColor: cssv('--accent') }, horzLine: { color: cssv('--crosshair'), labelBackgroundColor: cssv('--accent') } },
      localization: { priceFormatter: function (p) { return fmt(p, dec); } }
    };
  }
  function addLine(chart, color, width, extra) {
    return chart.addLineSeries(Object.assign({ color: color, lineWidth: width || 1, lastValueVisible: false, priceLineVisible: false, crosshairMarkerVisible: false }, extra || {}));
  }
  function destroyCharts() {
    if (C) { C.charts.forEach(function (c) { try { c.remove(); } catch (e) { /* đã gỡ */ } }); C = null; }
  }

  function rebuild(resetRange) {
    destroyCharts();
    var d = S.data, m = d.meta, dec = decimals(m), res = activeRes();
    var wrap = $('#chart-wrap'); wrap.innerHTML = '';
    var activePanes = PANE_DEF.filter(function (p) { return S.mode === 'adv' && S.opts[p.id]; });
    var mainDiv = document.createElement('div'); mainDiv.className = 'chart-main'; wrap.appendChild(mainDiv);
    var legend = document.createElement('div'); legend.className = 'legend'; mainDiv.appendChild(legend);
    var charts = [], paneObjs = {};
    var main = LW.createChart(mainDiv, baseOptions(dec, activePanes.length === 0));
    charts.push(main);
    main.priceScale('right').applyOptions({ scaleMargins: { top: 0.06, bottom: m.has_volume ? 0.24 : 0.06 } });
    var candle = main.addCandlestickSeries({ upColor: cssv('--up'), downColor: cssv('--down'), borderVisible: false, wickUpColor: cssv('--up'), wickDownColor: cssv('--down'),
      priceFormat: { type: 'price', precision: dec, minMove: dec === 0 ? 1 : 0.01 } });
    var series = { candle: candle, lines: {} };
    if (m.has_volume) {
      series.vol = main.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'vol', lastValueVisible: false, priceLineVisible: false });
      main.priceScale('vol').applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      series.volMa = addLine(main, cssv('--muted'), 1, { priceScaleId: 'vol' });
    }
    var noScale = { autoscaleInfoProvider: function () { return null; } };
    function ov(id, col, color, w, extra) { series.lines[id] = { s: addLine(main, cssv(color), w, extra), col: col, group: id }; }
    ov('ema9', 'ema9', '--ema9'); ov('ema20', 'ema20', '--ema20'); ov('ema50', 'ema50', '--ema50'); ov('ema200', 'ema200', '--ema200', 2);
    ov('bb_u', 'bb_upper', '--bb', 1, { lineStyle: 2 }); ov('bb_m', 'bb_mid', '--bb', 1, { lineStyle: 3 }); ov('bb_l', 'bb_lower', '--bb', 1, { lineStyle: 2 });
    series.lines.bb_u.group = series.lines.bb_m.group = series.lines.bb_l.group = 'bb';
    ov('vwap', 'vwap', '--vwap', 2);
    series.trendUp = addLine(main, cssv('--trend-up'), 2, Object.assign({ lineStyle: 0 }, noScale));
    series.trendDown = addLine(main, cssv('--trend-down'), 2, Object.assign({ lineStyle: 0 }, noScale));
    series.patLines = [];
    for (var pi = 0; pi < 6; pi++) series.patLines.push(addLine(main, cssv('--accent'), 1, Object.assign({ lineStyle: 2 }, noScale)));
    series.priceLines = [];

    var legendEl = legend;
    activePanes.forEach(function (p, idx) {
      var div = document.createElement('div'); div.className = 'pane';
      var t = document.createElement('div'); t.className = 'pane-title'; t.textContent = { rsi: 'RSI(14)', macd: 'MACD(12,26,9)', stoch: 'Stochastic(14,3,3)', adx: 'ADX(14) · +DI · −DI' }[p.id];
      div.appendChild(t); wrap.appendChild(div);
      var ch = LW.createChart(div, baseOptions(2, idx === activePanes.length - 1));
      ch.priceScale('right').applyOptions({ scaleMargins: { top: 0.12, bottom: 0.08 } });
      charts.push(ch);
      var po = { chart: ch, s: {} };
      var fixed01 = { autoscaleInfoProvider: function () { return { priceRange: { minValue: 0, maxValue: 100 } }; } };
      if (p.id === 'rsi') {
        po.s.rsi14 = addLine(ch, cssv('--accent'), 2, fixed01);
        [30, 70].forEach(function (v) { po.s.rsi14.createPriceLine({ price: v, color: cssv('--muted'), lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' }); });
      } else if (p.id === 'macd') {
        po.s.macd_hist = ch.addHistogramSeries({ priceFormat: { type: 'price', precision: 2, minMove: 0.01 }, lastValueVisible: false, priceLineVisible: false });
        po.s.macd = addLine(ch, cssv('--ema20'), 1); po.s.macd_signal = addLine(ch, cssv('--ema9'), 1);
      } else if (p.id === 'stoch') {
        po.s.stoch_k = addLine(ch, cssv('--accent'), 2, fixed01); po.s.stoch_d = addLine(ch, cssv('--ema9'), 1, fixed01);
        [20, 80].forEach(function (v) { po.s.stoch_k.createPriceLine({ price: v, color: cssv('--muted'), lineWidth: 1, lineStyle: 2, axisLabelVisible: false, title: '' }); });
      } else if (p.id === 'adx') {
        po.s.adx14 = addLine(ch, cssv('--accent'), 2); po.s.plus_di14 = addLine(ch, cssv('--up'), 1); po.s.minus_di14 = addLine(ch, cssv('--down'), 1);
      }
      paneObjs[p.id] = po;
    });

    // đồng bộ trục thời gian giữa các biểu đồ
    var syncing = false;
    charts.forEach(function (c) {
      c.timeScale().subscribeVisibleLogicalRangeChange(function (r) {
        if (syncing || !r) return; syncing = true;
        charts.forEach(function (o) { if (o !== c) o.timeScale().setVisibleLogicalRange(r); });
        syncing = false;
      });
      c.subscribeCrosshairMove(function (param) {
        if (!param || param.time === undefined) { updatePanel(S.cur); setLegend(S.cur); return; }
        var i = S.timeIdx.get(param.time);
        if (i !== undefined && i <= S.cur) { updatePanel(i); setLegend(i); }
      });
    });
    C = { charts: charts, main: main, series: series, panes: paneObjs, legend: legendEl };
    buildTimes();
    renderFull(S.cur, resetRange !== false);
    applyOverlayVisibility();
  }

  function buildTimes() {
    var d = S.data, res = activeRes(); S.times = []; S.timeIdx = new Map();
    for (var i = 0; i < d.t.length; i++) {
      var tt = toTime(d.t[i], res);
      S.times.push(tt); S.timeIdx.set(tt, i);
    }
  }
  function pt(i, col) {
    var v = S.data[col][i];
    // VWAP reset mỗi ngày: không nối đường giữa hai ngày (nến đầu ngày để trống)
    if (col === 'vwap' && i > 0 && vnDate(S.data.t[i]) !== vnDate(S.data.t[i - 1])) return { time: S.times[i] };
    return v == null ? { time: S.times[i] } : { time: S.times[i], value: v };
  }
  function candlePt(i) { var d = S.data; return { time: S.times[i], open: d.o[i], high: d.h[i], low: d.l[i], close: d.c[i] }; }
  function volPt(i) { var d = S.data; return { time: S.times[i], value: d.v[i], color: d.c[i] >= d.o[i] ? cssv('--up-a') : cssv('--down-a') }; }
  function histPt(i, col) { var v = S.data[col][i]; return v == null ? { time: S.times[i] } : { time: S.times[i], value: v, color: v >= 0 ? cssv('--up-a') : cssv('--down-a') }; }

  function allPoints(upto, fn) { var a = []; for (var i = 0; i <= upto; i++) a.push(fn(i)); return a; }

  function renderFull(cur, resetRange) {
    var d = S.data, sr = C.series;
    sr.candle.setData(allPoints(cur, candlePt));
    if (sr.vol) { sr.vol.setData(allPoints(cur, volPt)); sr.volMa.setData(allPoints(cur, function (i) { return pt(i, 'vol_ma20'); })); }
    Object.keys(sr.lines).forEach(function (k) { var L = sr.lines[k]; L.s.setData(allPoints(cur, function (i) { return pt(i, L.col); })); });
    Object.keys(C.panes).forEach(function (pid) {
      var po = C.panes[pid];
      Object.keys(po.s).forEach(function (col) {
        po.s[col].setData(allPoints(cur, function (i) { return col === 'macd_hist' ? histPt(i, col) : pt(i, col); }));
      });
    });
    renderStruct(cur);
    updatePanel(cur); setLegend(cur);
    if (resetRange) {
      var span = S.replay.on ? 90 : (activeRes() === 'D' ? 130 : 160);
      var ahead = S.replay.on ? 28 : 8;
      C.charts[0].timeScale().setVisibleLogicalRange({ from: Math.max(0, cur - span), to: cur + ahead });
    }
  }
  function renderStep(cur) {
    var sr = C.series;
    sr.candle.update(candlePt(cur));
    if (sr.vol) { sr.vol.update(volPt(cur)); sr.volMa.update(pt(cur, 'vol_ma20')); }
    Object.keys(sr.lines).forEach(function (k) { var L = sr.lines[k]; L.s.update(pt(cur, L.col)); });
    Object.keys(C.panes).forEach(function (pid) {
      var po = C.panes[pid];
      Object.keys(po.s).forEach(function (col) { po.s[col].update(col === 'macd_hist' ? histPt(cur, col) : pt(cur, col)); });
    });
    renderStruct(cur); updatePanel(cur); setLegend(cur);
  }

  function applyOverlayVisibility() {
    var o = S.opts, sr = C.series;
    Object.keys(sr.lines).forEach(function (k) {
      var L = sr.lines[k], on = !!o[L.group];
      L.s.applyOptions({ visible: on });
    });
  }

  // ------------------------------------------------------------------ cấu trúc giá: đường xu hướng, vùng S/R, Fibonacci, swing
  function segActive(s, cur) { return s.from <= cur && (s.to == null || s.to >= cur); }
  function lineY(s, x) { return s.p1 + (s.p2 - s.p1) / (s.i2 - s.i1) * (x - s.i1); }
  function lastTouches(s, cur) { var h = s.touches_hist, v = h[0][1]; for (var k = 0; k < h.length; k++) if (h[k][0] <= cur) v = h[k][1]; return v; }
  function activeLines(cur) {
    var up = null, dn = null;
    S.data.trendlines.forEach(function (s) { if (segActive(s, cur)) { if (s.kind === 'up') up = s; else dn = s; } });
    return { up: up, down: dn };
  }
  function activeZones(cur) {
    var out = [], close = S.data.c[cur];
    S.data.zones.forEach(function (z) {
      var e = null;
      for (var k = 0; k < z.hist.length; k++) if (z.hist[k][0] <= cur) e = z.hist[k];
      if (!e || e[2] < 2 || cur - e[4] > 250) return;
      out.push({ center: e[1], touches: e[2], hw: e[3], dist: (e[1] - close) / close });
    });
    var above = out.filter(function (z) { return z.center > close; }).sort(function (a, b) { return a.dist - b.dist; }).slice(0, 2);
    var below = out.filter(function (z) { return z.center <= close; }).sort(function (a, b) { return b.dist - a.dist; }).slice(0, 2);
    return { above: above, below: below };
  }
  function fibState(cur) {
    var hi = null, lo = null;
    S.data.swings.forEach(function (s) {
      if (s.confirmed_at > cur) return;
      if (s.type === 'high') { if (!hi || s.index > hi.index) hi = s; } else if (!lo || s.index > lo.index) lo = s;
    });
    if (!hi || !lo) return null;
    var a = hi.index < lo.index ? hi : lo, b = a === hi ? lo : hi; // a: swing sớm hơn, b: swing muộn hơn
    var levels = S.data.meta.fib_ratios.map(function (r) { return { r: r, price: b.price - r * (b.price - a.price) }; });
    return { a: a, b: b, levels: levels };
  }

  function patStatus(p, i) {
    if (p.formed_at > i) return null;
    var keys = [['invalidated_at', 'invalidated'], ['expired_at', 'expired'], ['superseded_at', 'superseded']];
    for (var k = 0; k < keys.length; k++) {
      var v = p[keys[k][0]];
      if (v != null && v <= i && (p.confirmed_at == null || v <= p.confirmed_at)) return keys[k][1];
    }
    if (p.confirmed_at != null && p.confirmed_at <= i) {
      if (p.target_hit_at != null && p.target_hit_at <= i) return 'target_hit';
      if (p.failed_at != null && p.failed_at <= i) return 'failed';
      return 'confirmed';
    }
    return 'forming';
  }
  function activeChartPatterns(cur) {
    var out = [];
    (S.data.chart_patterns || []).forEach(function (p) {
      var s = patStatus(p, cur);
      if ((s === 'forming' || s === 'confirmed') && cur - p.formed_at <= 80) { var q = Object.assign({}, p); q.status = s; q.breakout_dir = (p.confirmed_at != null && p.confirmed_at <= cur) ? p.breakout_dir : undefined; out.push(q); }
    });
    return out;
  }
  function pct(x, d) { return x == null ? '—' : fmt(100 * x, d == null ? 1 : d) + '%'; }
  function dirPill(dv) { return '<span class="pill ' + (dv > 0 ? 'up' : dv < 0 ? 'down' : 'flat') + '">' + (dv > 0 ? 'Tăng' : dv < 0 ? 'Giảm' : 'Đi ngang / chưa rõ') + '</span>'; }
  var CONF_VI = { low: 'thấp', medium: 'trung bình', high: 'cao' };
  var HZ_VI = { next_session: 'Phiên kế tiếp', '1_2_weeks': '1–2 tuần' };

  function evidenceHTML(hz, conf) {
    var B = S.backtest && S.backtest.daily && S.backtest.daily.pooled;
    if (!B) return '<p class="note">Chưa có kết quả backtest.</p>';
    var keys = hz === 'next_session' ? ['next_session@h1'] : ['1_2_weeks@h5', '1_2_weeks@h10'];
    var h = '<div class="evid"><b>Bằng chứng lịch sử của quy tắc này</b> <span class="muted">(backtest trên dữ liệu 11 mã, không tinh chỉnh; kiểm tra nội mẫu — không đảm bảo tương lai)</span><ul>';
    keys.forEach(function (k) {
      var x = B[k]; if (!x) return;
      var lo = x.accuracy_ci95_effective ? x.accuracy_ci95_effective[0] : null, hi = x.accuracy_ci95_effective ? x.accuracy_ci95_effective[1] : null;
      var base = Math.max(x.accuracy_if_independent, x.always_majority_accuracy);
      var beat = lo != null && lo > base;
      h += '<li><b>' + (/@h1$/.test(k) ? 'Nến kế tiếp' : 'Sau ' + k.split('@h')[1] + ' phiên') + ':</b> đúng <b>' + pct(x.accuracy) + '</b> (khoảng tin cậy 95%: ' + pct(lo) + '–' + pct(hi) + '; ' + fmt(x.n) + ' nến ≈ ' + fmt(x.n_effective) + ' mẫu độc lập). Đường cơ sở: đoán ngẫu nhiên theo cùng tỷ lệ → ' + pct(x.accuracy_if_independent) + '; luôn đoán nhóm phổ biến nhất → ' + pct(x.always_majority_accuracy) + '. ' +
        (beat ? '<span class="up"><b>Vượt đường cơ sở.</b></span>' : '<span class="down"><b>Chưa vượt đường cơ sở nào</b> → chưa có bằng chứng quy tắc này có lợi thế dự báo.</span>');
      var c = x.by_confidence && x.by_confidence[conf];
      if (c && c.n) h += ' Riêng mức tin cậy “' + CONF_VI[conf] + '”: đúng ' + pct(c.accuracy) + (c.accuracy_ci95_effective ? ' (' + pct(c.accuracy_ci95_effective[0]) + '–' + pct(c.accuracy_ci95_effective[1]) + ')' : '') + ' trên ' + fmt(c.n_effective) + ' mẫu độc lập.';
      h += '</li>';
    });
    return h + '</ul></div>';
  }

  function renderAnalysis() {
    var box = $('#panel-analysis'); if (!box) return;
    if (S.replay.on) { box.innerHTML = '<p class="note">Đang phát lại: nhận định bên dưới chỉ dành cho dữ liệu hiện tại. Ở mỗi lượt đoán, hệ thống sẽ cho biết tín hiệu của quy tắc tại đúng nến đó để so sánh với bạn.</p>'; return; }
    var A = S.analysis && S.analysis.items[S.sym];
    if (!A) { box.innerHTML = '<p class="note">Chưa có nhận định cho mã này (chưa đủ dữ liệu lịch sử).</p>'; return; }
    var X = A.horizons[S.hz], dec = S.sym === 'XAUUSD' || S.board.items.filter(function (i) { return i.symbol === S.sym; })[0].type === 'index' ? 2 : 0;
    var h = '<div class="seg" id="hz-seg" style="margin-bottom:8px">' + ['next_session', '1_2_weeks'].map(function (k) { return '<button data-hz="' + k + '" aria-pressed="' + (S.hz === k) + '">' + HZ_VI[k] + '</button>'; }).join('') + '</div>';
    h += '<p class="muted" style="font-size:12px;margin:0 0 6px">Phân tích tại nến ngày hoàn tất ' + ymdToDMY(A.asof_date) + (A.last_bar_partial ? ' (nến hiện tại chưa hoàn tất nên không dùng)' : '') + '</p>';
    h += '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">' + dirPill(X.direction) + '<span>Độ tin cậy: <b>' + CONF_VI[X.confidence] + '</b></span></div>';
    h += '<p class="note" style="margin-top:4px">' + esc(X.confluence.confluence_note) + '.</p>';
    h += '<table class="kv groups">';
    X.groups.forEach(function (g) {
      h += '<tr><td style="vertical-align:top;width:92px"><span class="help" title="' + esc(g.evidence.map(function (e) { return e.name + ' = ' + (typeof e.value === 'number' ? fmt(e.value, 2) : e.value); }).join('; ')) + '">' + esc(g.group_vi) + '</span><br><span class="pill ' + (g.na ? 'flat' : g.vote > 0 ? 'up' : g.vote < 0 ? 'down' : 'flat') + '" style="font-size:11px">' + esc(g.reading) + '</span></td><td style="text-align:left;font-weight:400;font-size:12.5px">' + esc(g.text) + '</td></tr>';
    });
    h += '</table>';
    h += '<p style="margin:8px 0 2px"><b>' + esc(X.scenario_main) + '</b></p><p style="margin:0 0 6px">' + esc(X.scenario_alt) + '</p>';
    if (X.invalidation) h += '<p class="note">Mức vô hiệu hóa: <b>' + fmt(X.invalidation.level, dec) + '</b> (' + esc(X.invalidation.basis) + ').</p>';
    if (X.levels && X.levels.pattern_target) h += '<p class="note">Mục tiêu đo theo mô hình “' + esc(X.levels.pattern_target.pattern) + '”: ' + fmt(X.levels.pattern_target.target, dec) + ' (' + esc(X.levels.pattern_target.method) + ').</p>';
    if (X.counter_arguments.length) h += '<p class="note"><b>Luận điểm ngược chiều:</b></p><ul class="tight">' + X.counter_arguments.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>';
    if (X.notes.length) h += '<p class="note"><b>Lưu ý:</b></p><ul class="tight">' + X.notes.map(function (t) { return '<li>' + esc(t) + '</li>'; }).join('') + '</ul>';
    var caveats = [];
    if (A.is_futures) caveats.push('Vàng ở đây là hợp đồng tương lai COMEX (GC=F), không phải spot XAU/USD.');
    if (A.price_adjusted) caveats.push('Giá là giá đã điều chỉnh theo sự kiện doanh nghiệp.');
    caveats.push('Nhận định này chưa tính tin tức/vĩ mô (sẽ kết hợp ở bản tin). Đây là quy tắc kỹ thuật cố định, không phải khuyến nghị đầu tư.');
    h += '<p class="note">' + caveats.map(esc).join(' ') + '</p>';
    h += evidenceHTML(S.hz, X.confidence);
    box.innerHTML = h;
    $all('#hz-seg button').forEach(function (b) { b.addEventListener('click', function () { S.hz = b.getAttribute('data-hz'); renderAnalysis(); }); });
  }

  function renderJournal() {
    var box = $('#panel-journal'); if (!box) return;
    var J = S.journal; if (!J) { box.innerHTML = '<p class="note">Chưa có sổ nhật ký.</p>'; return; }
    var s = J.summary || {}, h = '<p style="margin:0 0 6px">Đã phát hành <b>' + fmt(s.predictions_issued || 0) + '</b> nhận định' + (s.first_asof ? ' (từ ' + ymdToDMY(s.first_asof) + ')' : '') + ', đã chấm <b>' + fmt(s.evaluations_scored || 0) + '</b> lượt.</p>';
    if (s.overall && s.overall.n) h += '<p class="note">Tỷ lệ đúng: ' + pct(s.overall.accuracy, 0) + ' (' + s.overall.correct + '/' + s.overall.n + '; khoảng tin cậy 95% ' + pct(s.overall.ci95[0], 0) + '–' + pct(s.overall.ci95[1], 0) + '). ' + (s.overall.enough_sample ? '' : '<b>Chưa đủ mẫu (cần ≥ ' + s.min_sample_for_meaning + ') — chưa có ý nghĩa thống kê.</b> ') + 'Tham chiếu: ' + pct(s.overall.share_outcome_flat, 0) + ' kết quả là “đi ngang”.</p>';
    else h += '<p class="note">Chưa có lượt chấm nào: nhận định được chấm sau khi phiên kế tiếp (hoặc 5/10 phiên) hoàn tất. Đây là bài kiểm tra thực tế, không nhìn lại quá khứ.</p>';
    var rows = (J.recent || []).filter(function (r) { return r.symbol === S.sym; }).slice(-6).reverse();
    if (rows.length) {
      h += '<table class="kv"><tr class="sep"><td colspan="2">Nhận định gần đây của ' + esc(S.sym) + '</td></tr>';
      rows.forEach(function (r) {
        var st = r.evaluations.length ? r.evaluations.map(function (e) { return (e.correct ? '✔' : '✘') + ' h' + e.h + ' (' + e.outcome_vi + ')'; }).join(' · ') : '<span class="muted">chờ chấm</span>';
        h += '<tr><td>' + ymdToDMY(r.asof_date) + ' · ' + HZ_VI[r.horizon] + '</td><td>' + (r.direction > 0 ? '↑' : r.direction < 0 ? '↓' : '↔') + ' ' + esc(CONF_VI[r.confidence]) + ' · ' + st + '</td></tr>';
      });
      h += '</table>';
    }
    box.innerHTML = h + '<p class="note">Nhận định đã phát hành không bao giờ bị sửa. Ngưỡng đúng/sai (τ) được cố định lúc phát hành, dựa trên ATR.</p>';
  }

  function renderStruct(cur) {
    var d = S.data, sr = C.series, o = S.opts;
    // đường xu hướng
    var al = activeLines(cur);
    function lineData(s) { return s && o.trend ? [{ time: S.times[s.i1], value: s.p1 }, { time: S.times[cur], value: lineY(s, cur) }] : []; }
    sr.trendUp.setData(lineData(al.up)); sr.trendDown.setData(lineData(al.down));
    // price lines (vùng S/R + Fibonacci)
    sr.priceLines.forEach(function (pl) { try { sr.candle.removePriceLine(pl); } catch (e) { /* bỏ qua */ } });
    sr.priceLines = [];
    if (o.sr) {
      var z = activeZones(cur);
      z.above.concat(z.below).forEach(function (zz) {
        var res = zz.dist > 0;
        sr.priceLines.push(sr.candle.createPriceLine({ price: zz.center, color: res ? cssv('--down') : cssv('--up'), lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: (res ? 'KC ' : 'HT ') + zz.touches + 'x' }));
      });
    }
    if (o.pivot && d.pv_P && d.pv_P[cur] != null) {
      ['R2', 'R1', 'P', 'S1', 'S2'].forEach(function (k) {
        sr.priceLines.push(sr.candle.createPriceLine({ price: d['pv_' + k][cur], color: cssv('--pivot'), lineWidth: 1, lineStyle: 1, axisLabelVisible: false, title: k }));
      });
    }
    if (o.fib) {
      var f = fibState(cur);
      if (f) f.levels.forEach(function (l) { sr.priceLines.push(sr.candle.createPriceLine({ price: l.price, color: cssv('--fib'), lineWidth: 1, lineStyle: 1, axisLabelVisible: false, title: 'Fib ' + fmt(l.r * 100, 1) + '%' })); });
    }
    // mô hình giá cổ điển: đường cổ/biên của mô hình đang hình thành hoặc đã xác nhận (tối đa 2 mô hình gần nhất)
    sr.patLines.forEach(function (ls) { ls.setData([]); });
    var activePats = o.patterns ? activeChartPatterns(cur).slice(-2) : [];
    var li = 0;
    activePats.forEach(function (p) {
      var col = p.bias > 0 || p.breakout_dir > 0 ? cssv('--up') : (p.bias < 0 || p.breakout_dir < 0 ? cssv('--down') : cssv('--muted'));
      var ls = p.type.indexOf('triangle') >= 0 ? [p.upper, p.lower] : [p.neckline];
      ls.forEach(function (L) {
        if (li >= sr.patLines.length) return;
        var s = sr.patLines[li++];
        s.applyOptions({ color: col });
        s.setData([{ time: S.times[L.i1], value: L.p1 }, { time: S.times[cur], value: L.p1 + (L.p2 - L.p1) / (L.i2 === L.i1 ? 1 : (L.i2 - L.i1)) * (cur - L.i1) }]);
      });
      if (p.status === 'confirmed' && p.target != null) {
        sr.priceLines.push(sr.candle.createPriceLine({ price: p.target, color: col, lineWidth: 1, lineStyle: 3, axisLabelVisible: true, title: 'Mục tiêu đo' }));
      }
    });
    // đánh dấu swing (chỉ những swing đã xác nhận — hiện ra trễ k nến, đúng như khi giao dịch thực)
    var mk = [];
    if (o.swings) d.swings.forEach(function (s) {
      if (s.confirmed_at > cur) return;
      mk.push({ time: S.times[s.index], position: s.type === 'high' ? 'aboveBar' : 'belowBar', color: cssv('--muted'), shape: s.type === 'high' ? 'arrowDown' : 'arrowUp', size: 0.6 });
    });
    if (o.patterns) (d.candles || []).forEach(function (r) {
      if (r.index > cur || r.dir === 0) return;
      var failed = r.failed_at != null && r.failed_at <= cur;
      mk.push({ time: S.times[r.index], position: r.dir > 0 ? 'belowBar' : 'aboveBar', color: failed ? cssv('--muted') : (r.dir > 0 ? cssv('--up') : cssv('--down')), shape: 'circle', size: 0.7, text: r.label.split(' (')[0] });
    });
    if (S.replay.on) S.replay.markers.forEach(function (m) { if (m.idx <= cur) mk.push(m.mk); });
    mk.sort(function (a, b) { return a.time < b.time ? -1 : a.time > b.time ? 1 : 0; });
    sr.candle.setMarkers(mk);
  }

  // ------------------------------------------------------------------ chú giải trên biểu đồ & bảng số liệu
  function setLegend(i) {
    var d = S.data, dec = decimals(d.meta), prev = i > 0 ? d.c[i - 1] : null;
    var ch = prev ? (d.c[i] - prev) : null;
    var t = S.data.t[i], when = activeRes() === 'D' ? vnDMY(t) : vnDMYHM(t);
    C.legend.innerHTML = '<span class="num">' + when + '</span>' +
      '<span class="num">O <b>' + fmt(d.o[i], dec) + '</b></span><span class="num">H <b>' + fmt(d.h[i], dec) + '</b></span>' +
      '<span class="num">L <b>' + fmt(d.l[i], dec) + '</b></span><span class="num">C <b class="' + dirClass(ch) + '">' + fmt(d.c[i], dec) + '</b></span>' +
      (ch != null ? '<span class="num ' + dirClass(ch) + '">' + fmtSigned(ch, dec) + ' (' + fmtSigned(100 * ch / prev, 2) + '%)</span>' : '') +
      (d.meta.has_volume ? '<span class="num">KL <b>' + fmt(d.v[i]) + '</b></span>' : '');
  }
  function kv(label, val, tip) { return '<tr><td>' + (tip ? '<span class="help" title="' + esc(TIPS[tip]) + '">' + label + '</span>' : label) + '</td><td class="num">' + val + '</td></tr>'; }
  function sep(t) { return '<tr class="sep"><td colspan="2">' + t + '</td></tr>'; }
  function trendWord(s) { return s === 1 ? 'Tăng' : s === -1 ? 'Giảm' : s === 0 ? 'Hỗn hợp' : 'Chưa đủ dữ liệu'; }
  function trendPill(s) { return '<span class="pill ' + (s === 1 ? 'up' : s === -1 ? 'down' : 'flat') + '">' + trendWord(s) + '</span>'; }

  function updatePanel(i) {
    var d = S.data, dec = decimals(d.meta), c = d.c[i], A = function (k) { return d[k][i]; };
    $('#panel-time').textContent = (activeRes() === 'D' ? vnDMY(d.t[i]) : vnDMYHM(d.t[i])) + (d.partial[i] ? ' · chưa hoàn tất' : '');
    var h = '<table class="kv">';
    h += kv('Đóng cửa', fmt(c, dec));
    if (d.meta.has_volume) {
      var ratio = A('vol_ma20') ? d.v[i] / A('vol_ma20') : null;
      h += kv('Khối lượng', fmt(d.v[i]), 'vol');
      h += kv('KL / TB 20 nến', ratio == null ? '—' : fmt(ratio, 2) + '×', 'vol');
    }
    h += kv('Xu hướng (Dow)', trendPill(d.trend_state[i]), 'dow');
    function rel(name, col, tip) { var v = A(col); return kv(name, v == null ? '—' : fmt(v, dec) + ' <span class="' + (c >= v ? 'up' : 'down') + '">(' + (c >= v ? 'giá trên' : 'giá dưới') + ')</span>', tip); }
    h += rel('EMA20', 'ema20', 'ema'); h += rel('EMA50', 'ema50', 'ema');
    var rv = A('rsi14');
    h += kv('RSI(14)', rv == null ? '—' : fmt(rv, 1) + (rv >= 70 ? ' <span class="muted">(≥70)</span>' : rv <= 30 ? ' <span class="muted">(≤30)</span>' : ''), 'rsi');
    if (S.mode === 'adv') {
      h += sep('Xu hướng');
      h += rel('EMA9', 'ema9', 'ema'); h += rel('EMA200', 'ema200', 'ema'); h += rel('SMA50', 'sma50', 'sma'); h += rel('SMA200', 'sma200', 'sma');
      h += kv('MACD', fmt(A('macd'), 2), 'macd'); h += kv('Signal', fmt(A('macd_signal'), 2), 'macd'); h += kv('Histogram', fmt(A('macd_hist'), 2), 'macd');
      h += kv('ADX(14)', fmt(A('adx14'), 1), 'adx'); h += kv('+DI / −DI', fmt(A('plus_di14'), 1) + ' / ' + fmt(A('minus_di14'), 1), 'adx');
      h += sep('Động lượng & biến động');
      h += kv('Stoch %K / %D', fmt(A('stoch_k'), 1) + ' / ' + fmt(A('stoch_d'), 1), 'stoch');
      h += kv('Bollinger %B', fmt(A('bb_pct_b'), 2), 'bb'); h += kv('Bollinger bề rộng', A('bb_bandwidth') == null ? '—' : fmt(100 * A('bb_bandwidth'), 1) + '%', 'bb');
      h += kv('ATR(14)', fmt(A('atr14'), dec === 0 ? 0 : 2) + (A('atr14') ? ' <span class="muted">(' + fmt(100 * A('atr14') / c, 2) + '%)</span>' : ''), 'atr');
      if (d.meta.has_volume) { h += sep('Khối lượng'); h += kv('OBV', fmt(A('obv')), 'obv'); if (A('vwap') != null) h += kv('VWAP', fmt(A('vwap'), dec), 'vwap'); }
    }
    h += '</table>';
    if (S.mode === 'basic') h += '<p class="note">Chế độ <b>Cơ bản</b>: chỉ hiển thị số liệu chính. Chuyển sang <b>Chuyên sâu</b> để xem MACD, ADX, Stochastic, Bollinger, ATR, OBV…</p>';
    $('#panel-values').innerHTML = h;
    updateStructurePanel(i);
  }

  var STATUS_VI = { forming: 'đang hình thành (CHƯA xác nhận)', confirmed: 'đã xác nhận (đóng cửa phá đường cổ/biên)' };
  function patEvidence(key, a, b) {
    var P = S.backtest && S.backtest.daily && S.backtest.daily.pattern_stats && S.backtest.daily.pattern_stats.patterns[key];
    if (!P) return '';
    var f = function (lab) { var x = P[lab]; return x && x.n ? (lab.replace('_bar', ' nến') + ': đúng hướng ' + pct(x.hit, 0) + ' so với nền ' + pct(x.base_rate_same_dir, 0) + ', n=' + x.n) : ''; };
    return ' <span class="muted">Lịch sử dữ liệu dự án — ' + [f(a), f(b)].filter(Boolean).join('; ') + ' (mô tả, không phải lợi thế đã kiểm định).</span>';
  }
  function patternListHTML(i) {
    var d = S.data, dec = decimals(d.meta), out = [];
    [i, i - 1].forEach(function (j) {
      (d.candles || []).forEach(function (r) {
        if (r.index !== j) return;
        var st = r.dir === 0 ? 'trung lập (do dự)' : (r.failed_at != null && r.failed_at <= i ? 'đã thất bại (nến sau đóng dưới/trên mức vô hiệu)' : r.confirmed_at != null && r.confirmed_at <= i ? 'đã được nến kế tiếp xác nhận' : 'chưa xác nhận');
        out.push('<li><b>' + esc(r.label) + '</b> (' + (r.dir > 0 ? 'tăng' : r.dir < 0 ? 'giảm' : 'trung lập') + ', nến ' + vnHM(d.t[r.index]) + ' ' + (activeRes() === 'D' ? ymdToDMY(vnDate(d.t[r.index])) : '') + ') — ' + st + (r.invalid_level != null ? '; mức vô hiệu ' + fmt(r.invalid_level, dec) : '') + '.' + (r.dir !== 0 ? patEvidence('candle:' + r.name, '1_bar', '5_bar') : '') + '</li>');
      });
    });
    activeChartPatterns(i).forEach(function (p) {
      var dirv = p.status === 'confirmed' ? (p.type.indexOf('triangle') >= 0 ? p.breakout_dir : p.bias) : p.bias;
      var s = '<li><b>' + esc(p.label) + '</b> — ' + STATUS_VI[p.status];
      if (p.neckline) s += '; đường cổ hiện tại ≈ ' + fmt(p.neckline.p1 + (p.neckline.p2 - p.neckline.p1) / (p.neckline.i2 === p.neckline.i1 ? 1 : p.neckline.i2 - p.neckline.i1) * (i - p.neckline.i1), dec);
      if (p.invalid_level != null) s += '; vô hiệu nếu đóng cửa vượt ' + fmt(p.invalid_level, dec);
      if (p.status === 'confirmed' && p.target != null) s += '; mục tiêu đo ' + fmt(p.target, dec) + ' (đo theo chiều cao mô hình)';
      if (p.status === 'confirmed' && p.volume_confirmed != null) s += '; khối lượng nến phá vỡ ' + (p.volume_confirmed ? '≥' : '<') + ' 1,25× trung bình 20 nến';
      var key = 'chart:' + p.type + (p.type.indexOf('triangle') >= 0 && p.status === 'confirmed' ? ':' + (p.breakout_dir > 0 ? 'up' : 'down') : '');
      s += '.' + (p.status === 'confirmed' ? patEvidence(key, '5_bar', '10_bar') : '') + '</li>';
      out.push(s);
    });
    return out.length ? '<ul class="tight">' + out.join('') + '</ul>' : '';
  }
  function updateStructurePanel(i) {
    var d = S.data, dec = decimals(d.meta), c = d.c[i], h = '<table class="kv">';
    var st = d.trend_state[i];
    h += kv('Xu hướng Dow', trendPill(st), 'dow');
    var hi = null, lo = null, hi2 = null, lo2 = null;
    d.swings.forEach(function (s) {
      if (s.confirmed_at > i) return;
      if (s.type === 'high') { hi2 = hi; hi = s; } else { lo2 = lo; lo = s; }
    });
    if (hi) h += kv('Đỉnh swing gần nhất', fmt(hi.price, dec) + (hi2 ? ' <span class="muted">(trước: ' + fmt(hi2.price, dec) + ')</span>' : ''));
    if (lo) h += kv('Đáy swing gần nhất', fmt(lo.price, dec) + (lo2 ? ' <span class="muted">(trước: ' + fmt(lo2.price, dec) + ')</span>' : ''));
    var al = activeLines(i);
    h += sep('Đường xu hướng');
    [['up', 'Tăng (nối đáy)'], ['down', 'Giảm (nối đỉnh)']].forEach(function (k) {
      var s = al[k[0]];
      if (!s) { h += kv(k[1], '<span class="muted">không có đường hợp lệ</span>', 'tl'); return; }
      var y = lineY(s, i);
      h += kv(k[1], fmt(y, dec) + ' <span class="muted">(' + lastTouches(s, i) + ' chạm; giá cách ' + fmtSigned(100 * (c - y) / y, 1) + '%)</span>', 'tl');
    });
    var z = activeZones(i);
    h += sep('Hỗ trợ / kháng cự gần nhất');
    if (!z.above.length && !z.below.length) h += kv('Vùng', '<span class="muted">chưa đủ swing</span>', 'sr');
    z.above.slice().reverse().forEach(function (zz) { h += kv('Kháng cự (' + zz.touches + ' swing)', fmt(zz.center, dec) + ' <span class="muted">(' + fmtSigned(100 * zz.dist, 1) + '%)</span>', 'sr'); });
    z.below.forEach(function (zz) { h += kv('Hỗ trợ (' + zz.touches + ' swing)', fmt(zz.center, dec) + ' <span class="muted">(' + fmtSigned(100 * zz.dist, 1) + '%)</span>', 'sr'); });
    if (d.pv_P && d.pv_P[i] != null) {
      h += sep('Pivot (ngày giao dịch trước)');
      h += kv('R2 / R1', fmt(d.pv_R2[i], dec) + ' / ' + fmt(d.pv_R1[i], dec), 'pivot');
      h += kv('P', fmt(d.pv_P[i], dec), 'pivot');
      h += kv('S1 / S2', fmt(d.pv_S1[i], dec) + ' / ' + fmt(d.pv_S2[i], dec), 'pivot');
    }
    if (S.opts.fib) {
      var f = fibState(i);
      h += sep('Fibonacci');
      if (!f) h += kv('Hồi', '<span class="muted">chưa đủ swing</span>', 'fib');
      else {
        h += kv('Từ → đến', fmt(f.a.price, dec) + ' → ' + fmt(f.b.price, dec), 'fib');
        f.levels.forEach(function (l) { h += kv(fmt(l.r * 100, 1) + '%', fmt(l.price, dec)); });
      }
    }
    var pats = patternListHTML(i);
    if (pats) h += sep('Mô hình đang hiện diện') + '</table>' + pats + '<table class="kv">';
    h += '</table><p class="note">Đây là số liệu mô tả theo quy tắc trong <code>docs/indicators.md</code> và <code>docs/patterns.md</code>; không phải khuyến nghị. Swing chỉ được biết sau 5 nến xác nhận.</p>';
    $('#panel-structure').innerHTML = h;
  }

  // ------------------------------------------------------------------ chọn mã, khung, chế độ
  function selectSymbol(sym) {
    if (S.sym === sym) return;
    S.sym = sym; var ss = $('#sym-select'); if (ss) ss.value = sym; $all('#board tr[data-sym]').forEach(function (tr) { tr.classList.toggle('sel', tr.getAttribute('data-sym') === sym); });
    if (S.replay.on) { stopTimer(); S.replay.day = null; }
    reload(true);
  }
  function reload(resetRange) {
    var mySeq = ++seq, res = activeRes();
    $('#chart-wrap').innerHTML = '<div class="loading">Đang tải ' + esc(S.sym) + ' (' + RES_LABEL[res] + ')…</div>';
    loadSeries(S.sym, res).then(function (d) {
      if (mySeq !== seq) return;
      S.data = d;
      if (S.replay.on) setupReplayData(); else S.cur = d.meta.rows - 1;
      renderToolbar(); renderHead(); renderAnalysis(); renderJournal();
      rebuild(resetRange);
      if (S.replay.on) renderReplayBar();
    }).catch(function (e) {
      if (mySeq !== seq) return;
      $('#chart-wrap').innerHTML = '<div class="loading">Không tải được dữ liệu: ' + esc(e.message) + '</div>';
    });
  }

  // ------------------------------------------------------------------ phát lại (replay)
  var STATS_KEY = 'smr.replay.stats';
  function stopTimer() { if (S.replay.timer) { clearInterval(S.replay.timer); S.replay.timer = null; } }
  function toggleReplay() {
    var R = S.replay;
    if (R.on) { stopTimer(); R.on = false; R.markers = []; R.pending = null; R.lastResult = null; $('#replay').classList.remove('on'); reload(true); return; }
    R.on = true; R.markers = []; R.pending = null; R.lastResult = null; R.day = null; $('#replay').classList.add('on'); reload(true);
  }
  function eligibleDays() {
    return (S.data.sessions || []).filter(function (s) { return s[1] >= 30 && s[2] > s[1]; });
  }
  function setupReplayData() {
    var R = S.replay, days = eligibleDays();
    if (!days.length) { R.sess = null; S.cur = Math.min(40, S.data.meta.rows - 1); return; }
    var cand = days.filter(function (s) { return s[0] === R.day; })[0] || days[days.length - 1];
    R.day = cand[0]; R.sess = cand; R.markers = []; R.pending = null; R.lastResult = null; R.sessionGuesses = [];
    S.cur = cand[1] - 1; // chưa hé lộ nến nào của phiên: chỉ hiện lịch sử trước đó
  }
  function stats() { return LSget(STATS_KEY, []); }
  function renderReplayBar() {
    var R = S.replay, d = S.data, box = $('#replay');
    if (!R.sess) { box.innerHTML = '<span class="muted">Không có phiên đủ dữ liệu lịch sử để phát lại ở khung này.</span> <select id="rp-res"></select>'; fillResSelect(); return; }
    var days = eligibleDays();
    var h = '<label>Phiên <select id="rp-day">' + days.slice().reverse().map(function (s) { return '<option value="' + s[0] + '"' + (s[0] === R.day ? ' selected' : '') + '>' + ymdToDMY(s[0]) + '</option>'; }).join('') + '</select></label>';
    h += '<label>Khung <select id="rp-res"></select></label>';
    h += '<button class="btn" id="rp-restart" title="Về đầu phiên">⟲ Đầu phiên</button>';
    h += '<button class="btn primary" id="rp-play">' + (R.timer ? '⏸ Dừng' : '▶ Phát') + '</button>';
    h += '<button class="btn" id="rp-step" title="Hé lộ nến kế tiếp">⏭ Nến kế</button>';
    h += '<label>Tốc độ <select id="rp-speed">' + [1, 5, 20].map(function (v) { return '<option value="' + v + '"' + (R.speed === v ? ' selected' : '') + '>' + v + ' nến/giây</option>'; }).join('') + '</select></label>';
    h += '<span class="muted" style="margin-left:8px">Đoán nến kế:</span>';
    h += '<button class="btn g-up" id="rp-up" title="Đoán giá đóng nến kế cao hơn giá đóng hiện tại quá ngưỡng τ">↑ Tăng</button><button class="btn" id="rp-flat" title="Đoán giá đóng nến kế nằm trong ±τ">↔ Đi ngang</button><button class="btn g-down" id="rp-down" title="Đoán giá đóng nến kế thấp hơn quá ngưỡng τ">↓ Giảm</button>';
    h += '<div class="replay-status" id="rp-status"></div><div id="rp-result"></div><div class="replay-status" id="rp-stats"></div>';
    box.innerHTML = h; fillResSelect();
    $('#rp-day').addEventListener('change', function (e) { stopTimer(); R.day = e.target.value; setupReplayData(); rebuildReplay(); });
    $('#rp-restart').addEventListener('click', function () { stopTimer(); setupReplayData(); rebuildReplay(); });
    $('#rp-play').addEventListener('click', function () { if (R.timer) { stopTimer(); } else { startTimer(); } renderReplayDyn(); $('#rp-play').textContent = R.timer ? '⏸ Dừng' : '▶ Phát'; });
    $('#rp-step').addEventListener('click', function () { stopTimer(); doStep(); $('#rp-play').textContent = '▶ Phát'; });
    $('#rp-speed').addEventListener('change', function (e) { R.speed = parseInt(e.target.value, 10); if (R.timer) { stopTimer(); startTimer(); } });
    $('#rp-up').addEventListener('click', function () { guess('up'); });
    $('#rp-flat').addEventListener('click', function () { guess('flat'); });
    $('#rp-down').addEventListener('click', function () { guess('down'); });
    renderReplayDyn();
  }
  function fillResSelect() {
    var R = S.replay, sel = $('#rp-res'); if (!sel) return;
    sel.innerHTML = ['1', '5', '15'].map(function (r) { return '<option value="' + r + '"' + (R.res === r ? ' selected' : '') + '>' + RES_LABEL[r] + '</option>'; }).join('');
    sel.addEventListener('change', function (e) { stopTimer(); R.res = e.target.value; reload(true); });
  }
  function rebuildReplay() { renderHead(); rebuild(true); renderReplayBar(); }
  function startTimer() {
    var R = S.replay; stopTimer();
    R.timer = setInterval(function () { if (!doStep()) { stopTimer(); var b = $('#rp-play'); if (b) b.textContent = '▶ Phát'; } }, 1000 / R.speed);
  }
  function doStep() {
    var R = S.replay, d = S.data;
    if (!R.sess || S.cur >= R.sess[2]) { renderReplayDyn(); return false; }
    S.cur++; renderStep(S.cur);
    evaluatePending();
    var hd = $('#inst-head .price'); if (hd) { hd.textContent = fmt(d.c[S.cur], decimals(d.meta)); }
    renderReplayDyn();
    return S.cur < R.sess[2];
  }
  function tauAt(i) { var a = S.data.atr14[i], c = S.data.c[i]; return (a == null || !c) ? null : 0.25 * a / c; }
  function guess(dir) {
    var R = S.replay;
    if (!R.sess || S.cur >= R.sess[2]) return;
    var tau = tauAt(S.cur);
    if (tau == null) { R.lastResult = { text: 'Chưa đủ dữ liệu ATR để tính ngưỡng τ — hãy bấm "Nến kế" thêm vài nến.', cls: '' }; renderReplayDyn(); return; }
    stopTimer();
    R.pending = { idx: S.cur, dir: dir, ref: S.data.c[S.cur], tau: tau };
    doStep(); var b = $('#rp-play'); if (b) b.textContent = '▶ Phát';
  }
  function evaluatePending() {
    var R = S.replay, p = R.pending; if (!p) return;
    R.pending = null;
    var c1 = S.data.c[p.idx + 1], chg = c1 / p.ref - 1, outcome = chg > p.tau ? 'up' : (chg < -p.tau ? 'down' : 'flat');
    var ok = outcome === p.dir, nm = { up: 'Tăng', down: 'Giảm', flat: 'Đi ngang' };
    var oc = outcome === 'up' ? 1 : outcome === 'down' ? -1 : 0;
    var sysd = S.data.sys_next ? S.data.sys_next[p.idx] : null, sysOk = sysd == null ? null : sysd === oc;
    var rec = { sym: S.sym, res: S.replay.res, date: S.replay.day, idx: p.idx, dir: p.dir, outcome: outcome, ok: ok, tau: p.tau, chg: chg, sys: sysd, sysOk: sysOk };
    var all = stats(); all.push(rec); LSset(STATS_KEY, all.slice(-500));
    R.sessionGuesses.push(rec);
    R.lastResult = { cls: ok ? 'ok' : 'bad', text: (ok ? '✔ Đúng' : '✘ Sai') + ' — bạn đoán ' + nm[p.dir] + ', thực tế ' + nm[outcome] + ' (giá đóng thay đổi ' + fmtSigned(100 * chg, 2) + '%, ngưỡng τ = ±' + fmt(100 * p.tau, 2) + '%). ' + (sysd == null ? 'Hệ thống chưa đủ dữ liệu ở nến đó.' : 'Quy tắc của hệ thống tại nến đó dự đoán ' + nm[sysd > 0 ? 'up' : sysd < 0 ? 'down' : 'flat'] + ' → ' + (sysOk ? 'đúng' : 'sai') + '.') };
    R.markers.push({ idx: p.idx + 1, mk: { time: S.times[p.idx + 1], position: 'belowBar', color: ok ? cssv('--up') : cssv('--down'), shape: p.dir === 'up' ? 'arrowUp' : p.dir === 'down' ? 'arrowDown' : 'circle', text: ok ? '✔' : '✘', size: 1 } });
    renderStruct(S.cur);
  }
  function sysStatsText(all) {
    var s = all.filter(function (x) { return x.sys != null; }), n = s.length;
    if (!n) return '';
    var ok = s.filter(function (x) { return x.sysOk; }).length, you = s.filter(function (x) { return x.ok; }).length;
    return ' <b>So sánh trên cùng ' + n + ' nến:</b> bạn đúng ' + you + '/' + n + ' (' + fmt(100 * you / n, 0) + '%), quy tắc của hệ thống đúng ' + ok + '/' + n + ' (' + fmt(100 * ok / n, 0) + '%). Backtest cho thấy quy tắc nội phiên gần như ngẫu nhiên (xem bằng chứng lịch sử).';
  }
  function renderReplayDyn() {
    var R = S.replay, d = S.data; if (!R.sess) return;
    var st = $('#rp-status'); if (!st) return;
    var total = R.sess[2] - R.sess[1] + 1, shown = S.cur - R.sess[1] + 1;
    var tau = tauAt(S.cur);
    st.innerHTML = 'Phiên ' + ymdToDMY(R.day) + ' · đã hé lộ <b>' + Math.max(0, shown) + '/' + total + '</b> nến' + (shown > 0 ? ' · nến cuối bắt đầu ' + vnHM(d.t[S.cur]) : ' · đang ở đầu phiên (chỉ thấy lịch sử trước đó)') +
      ' · mỗi nến hiện nguyên vẹn khi đã hoàn tất' + (tau != null ? ' · ngưỡng τ nến kế = ±' + fmt(100 * tau, 2) + '% (0,25·ATR14/giá)' : '') +
      (d.meta.price_adjusted ? ' · giá đã điều chỉnh' : '');
    var done = S.cur >= R.sess[2];
    ['rp-up', 'rp-flat', 'rp-down'].forEach(function (id) { var b = $('#' + id); if (b) b.disabled = done || tau == null; });
    var sb = $('#rp-step'); if (sb) sb.disabled = done;
    var res = $('#rp-result'); if (res) { res.className = R.lastResult ? 'result ' + R.lastResult.cls : ''; res.textContent = R.lastResult ? R.lastResult.text : ''; }
    if (done && !R.lastResult) { /* kết thúc phiên mà chưa đoán */ }
    var all = stats(), n = all.length, ok = all.filter(function (x) { return x.ok; }).length, flat = all.filter(function (x) { return x.outcome === 'flat'; }).length;
    var s = $('#rp-stats');
    if (s) s.innerHTML = n ? ('Thống kê của bạn (lưu trên trình duyệt này): <b>' + ok + '/' + n + '</b> đúng (' + fmt(100 * ok / n, 0) + '%) · tham chiếu: luôn đoán "đi ngang" sẽ đúng ' + fmt(100 * flat / n, 0) + '%' + (n < 30 ? ' · <b>mới ' + n + ' lượt — chưa đủ ý nghĩa thống kê (cần ≥ 30)</b>' : '') + '.' + sysStatsText(all)) : 'Chưa có lượt đoán nào. Bấm ↑/↔/↓ để chốt dự đoán rồi nến kế tiếp sẽ hiện ra. Ngưỡng đúng/sai dựa trên ATR, giống phương pháp chấm nhận định của dự án.';
    var pb = $('#rp-play'); if (pb) pb.disabled = done;
  }

  // ------------------------------------------------------------------ chế độ, giao diện, chuyển tab
  function applyMode(m) {
    S.mode = m; LSset('smr.mode', m);
    document.body.classList.toggle('basic', m === 'basic');
    $('#mode-basic').setAttribute('aria-pressed', String(m === 'basic')); $('#mode-adv').setAttribute('aria-pressed', String(m === 'adv'));
    S.opts = Object.assign({}, DEFAULT_OPTS[m], LSget('smr.opts.' + m, {}));
    if (m === 'basic' && (S.res === '5' || S.res === '1')) S.res = '15';
  }
  function setTheme(t) { if (t) document.documentElement.setAttribute('data-theme', t); else document.documentElement.removeAttribute('data-theme'); }
  function init() {
    var th = LSget('smr.theme', null); if (th) setTheme(th);
    applyMode(S.mode);
    $('#mode-basic').addEventListener('click', function () { applyMode('basic'); if (S.data) reload(false); });
    $('#mode-adv').addEventListener('click', function () { applyMode('adv'); if (S.data) reload(false); });
    $('#theme-btn').addEventListener('click', function () {
      var cur = document.documentElement.getAttribute('data-theme');
      var dark = cur ? cur === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches;
      var next = dark ? 'light' : 'dark'; setTheme(next); LSset('smr.theme', next); if (S.data) rebuild(false);
    });
    $('#tab-chart').addEventListener('click', function () { setView('chart'); });
    $('#tab-news').addEventListener('click', function () { setView('news'); });
    var opt = function (u) { return getJSON(u).catch(function () { return null; }); };
    Promise.all([getJSON('data/board.json'), opt('data/gold_domestic.json'), opt('data/analysis.json'), opt('data/journal.json'), opt('data/backtest.json')]).then(function (r) {
      S.board = r[0]; S.gold = r[1]; S.analysis = r[2]; S.journal = r[3]; S.backtest = r[4];
      renderBoard(); renderGold();
      if (!itemOf(S.sym) && S.board.items.length) S.sym = S.board.items[0].symbol;
      reload(true);
    }).catch(function (e) {
      $('#chart-wrap').innerHTML = '<div class="loading">Không tải được dữ liệu bảng giá: ' + esc(e.message) + '<br>Hãy chạy <code>python -m pipeline.export_site</code> rồi mở trang qua một máy chủ web (không mở trực tiếp bằng file://).</div>';
    });
  }
  // ------------------------------------------------------------------ bản tin
  var TIER_VI = { fact: 'Sự kiện', data: 'Số liệu dự án', def: 'Định nghĩa', infer: 'Suy luận', opinion: 'Nhận định', note: 'Ghi chú' };
  var REL_VI_SHORT = { agree: 'đồng thuận', conflict: 'MÂU THUẪN', news_only: 'chỉ tin tức', tech_only: 'chỉ kỹ thuật', both_neutral: 'cùng trung lập' };
  function mdInline(t) {
    t = esc(t).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
    return t.replace(/\[\^(\d+)\]/g, function (m, n) { return '<sup><a href="#ref-' + n + '" title="Xem nguồn ' + n + '">[' + n + ']</a></sup>'; });
  }
  function dirTxt(d) { return d > 0 ? '↑ tăng' : d < 0 ? '↓ giảm' : '↔ đi ngang'; }
  function outlookTable(rows) {
    var h = '<div class="scroll-x"><table class="otable"><thead><tr><th>Mã</th><th>Khung</th><th>Kỹ thuật (quy tắc)</th><th>Tin tức (người viết)</th><th>Kết hợp</th></tr></thead><tbody>';
    rows.forEach(function (r) {
      h += '<tr><td class="sym">' + esc(r.symbol) + '</td><td>' + HZ_VI[r.horizon] + '</td><td>' + dirTxt(r.engine_direction) + ' <span class="muted">(' + CONF_VI[r.engine_confidence] + ')</span><br><span class="muted" style="font-size:11px">nến ' + ymdToDMY(r.engine_asof) + '</span></td>' +
        '<td><span class="help" title="' + esc(r.news_channel) + '">' + dirTxt(r.news_stance) + '</span></td>' +
        '<td><b>' + dirTxt(r.combined_direction) + '</b> <span class="muted">(tin cậy ' + CONF_VI[r.combined_confidence] + ')</span><br><span class="muted" style="font-size:11px">' + REL_VI_SHORT[r.relation] + '</span></td></tr>';
    });
    return h + '</tbody></table></div><p class="note">Rê chuột lên cột “Tin tức” để xem kênh tác động. Độ tin cậy kết hợp tối đa là “trung bình” vì quy tắc kỹ thuật chưa vượt đường cơ sở (xem backtest). Vàng dùng nến ngày hoàn tất gần nhất của hợp đồng tương lai COMEX (GC=F).</p>';
  }
  function renderNews(doc) {
    var fc = doc.factcheck, h = '<div class="nw-head"><div class="nw-meta"><span>' + ymdToDMY(doc.date) + '</span><span>· ' + fmt(doc.word_count) + ' từ</span>' +
      '<span class="fc-badge' + (fc.ok ? '' : ' bad') + '" title="Mỗi câu nêu sự kiện có trích dẫn; câu trích được tải lại từ trang gốc và đối chiếu nguyên văn; số liệu trong câu phải có trong câu trích. Mã: pipeline/factcheck.py">' + (fc.ok ? '✔ Kiểm chứng tự động đạt' : '✘ Chưa đạt kiểm chứng') + ': ' + fc.claims_verified + '/' + fc.claims + ' câu trích khớp trang gốc</span></div><h1>' + esc(doc.title) + '</h1></div>';
    h += '<div class="nw-legend">' + ['fact', 'data', 'def', 'infer', 'opinion', 'note'].map(function (k) { return '<span class="tier ' + k + '">' + TIER_VI[k] + '</span>'; }).join('') +
      '<span class="muted">← mỗi đoạn được gắn tầng: sự kiện (có nguồn) · số liệu của dự án · định nghĩa (có nguồn) · suy luận · nhận định · ghi chú</span></div><div class="nw-body">';
    var i = 0, bl = doc.blocks;
    while (i < bl.length) {
      var b = bl[i];
      if (b.type === 'heading') { h += (b.level <= 1 ? '' : '<h2>' + esc(b.text) + '</h2>'); i++; continue; }
      if (b.type === 'outlook_table') { h += outlookTable(doc.outlook); i++; continue; }
      if (b.type === 'para' && b.bullet) {
        h += '<ul>'; while (i < bl.length && bl[i].type === 'para' && bl[i].bullet) { h += '<li><span class="tier ' + bl[i].tier + '">' + TIER_VI[bl[i].tier] + '</span>' + mdInline(bl[i].text) + '</li>'; i++; } h += '</ul>'; continue;
      }
      if (b.type === 'para') { h += '<p class="t-' + b.tier + '"><span class="tier ' + b.tier + '">' + TIER_VI[b.tier] + '</span>' + mdInline(b.text) + '</p>'; }
      i++;
    }
    h += '</div><div class="refs"><h2>Nguồn tham khảo</h2><ol>';
    doc.refs.forEach(function (r) {
      h += '<li id="ref-' + r.n + '"><a href="' + esc(r.url) + '" target="_blank" rel="noopener">' + esc(r.title) + '</a> — ' + esc(r.outlet) + (r.published ? ', ' + vnDMYHM(isoToUnix(r.published)) : '') + (r.kind === 'definition' ? ' <span class="muted">(định nghĩa tham khảo)</span>' : '') + '</li>';
    });
    h += '</ol></div><p class="note">' + esc(doc.disclaimer) + ' Quy tắc kết hợp nhận định: docs/report-methodology.md. Chỉ trích dẫn ngắn từ bài gốc; vui lòng đọc bài đầy đủ ở liên kết nguồn.</p>';
    return h;
  }
  var newsLoaded = false;
  var STAR_KEY = 'smr.starred.reports';
  function getStarred() { var v = LSget(STAR_KEY, []); return Array.isArray(v) ? v : []; }
  function setStarred(list) { LSset(STAR_KEY, list.slice().sort().reverse()); }
  function toggleStar(date) { var l = getStarred(), i = l.indexOf(date); if (i >= 0) l.splice(i, 1); else l.push(date); setStarred(l); return i < 0; }
  function loadNews() {
    if (newsLoaded) return; newsLoaded = true;
    var root = $('#news-root');
    getJSON('data/reports/index.json').then(function (idx) {
      if (!idx.length) { root.innerHTML = '<p class="muted">Chưa có bản tin.</p>'; return; }
      var N = { sub: 'report', date: idx[0].date };
      var byDate = {}; idx.forEach(function (r) { byDate[r.date] = r; });
      function bar() {
        var st = getStarred();
        var h = '<div class="nw-bar"><div class="seg" role="group" aria-label="Bản tin hoặc lưu trữ">' +
          '<button id="nw-sub-report" aria-pressed="' + (N.sub === 'report') + '">Bản tin</button>' +
          '<button id="nw-sub-archive" aria-pressed="' + (N.sub === 'archive') + '">★ Lưu trữ (' + st.length + ')</button></div>';
        if (N.sub === 'report') {
          h += '<label class="muted">Chọn ngày: <select id="news-pick">' + idx.map(function (r) {
            return '<option value="' + r.date + '"' + (r.date === N.date ? ' selected' : '') + '>' + (st.indexOf(r.date) >= 0 ? '★ ' : '') + ymdToDMY(r.date) + '</option>';
          }).join('') + '</select></label>';
          var on = st.indexOf(N.date) >= 0;
          h += '<button class="star-btn" id="star-btn" aria-pressed="' + on + '" title="Đánh dấu để xem lại ở mục Lưu trữ (lưu trong trình duyệt này)">' + (on ? '★ Đã đánh dấu' : '☆ Đánh dấu bản tin này') + '</button>';
        }
        return h + '</div>';
      }
      function archive() {
        var st = getStarred();
        if (!st.length) return '<div class="card" style="padding:14px"><p><b>Chưa có bản tin nào được đánh dấu.</b></p><p class="muted">Mở một bản tin và bấm “☆ Đánh dấu bản tin này” để lưu vào đây. Đánh dấu được lưu trong trình duyệt này, không đồng bộ giữa các thiết bị.</p></div>';
        var h = '<ul class="arch-list">';
        st.forEach(function (d) {
          var r = byDate[d];
          h += '<li class="arch-item" data-date="' + d + '"><div class="arch-main"><div class="arch-date">★ ' + ymdToDMY(d) + '</div><div class="arch-title">' + (r ? esc(r.title) : '<span class="muted">Bản tin này không còn trong dữ liệu của trang</span>') + '</div>' +
            (r ? '<div class="muted">' + r.word_count + ' từ' + (r.factcheck_ok ? ' · đã qua kiểm chứng tự động' : '') + '</div>' : '') + '</div>' +
            (r ? '<button class="open" data-date="' + d + '">Xem</button>' : '') + '<button class="unstar" data-date="' + d + '" title="Bỏ đánh dấu">★ Bỏ</button></li>';
        });
        return h + '</ul><p class="muted" style="margin-top:10px">Đánh dấu được lưu trong trình duyệt này (không đồng bộ giữa các thiết bị, mất nếu xóa dữ liệu trang).</p>';
      }
      function render() {
        if (N.sub === 'archive') { root.innerHTML = bar() + archive(); wire(); return; }
        getJSON('data/reports/' + N.date + '.json').then(function (d) { root.innerHTML = bar() + renderNews(d); wire(); })
          .catch(function (e) { root.innerHTML = bar() + '<p class="muted">Không tải được bản tin: ' + esc(e.message) + '</p>'; wire(); });
      }
      function wire() {
        $('#nw-sub-report').onclick = function () { N.sub = 'report'; render(); };
        $('#nw-sub-archive').onclick = function () { N.sub = 'archive'; render(); };
        var pick = $('#news-pick'); if (pick) pick.onchange = function () { N.date = pick.value; render(); };
        var sb = $('#star-btn'); if (sb) sb.onclick = function () { toggleStar(N.date); render(); };
        $all('.arch-item .open').forEach(function (b) { b.onclick = function () { N.date = b.getAttribute('data-date'); N.sub = 'report'; render(); window.scrollTo(0, 0); }; });
        $all('.arch-item .unstar').forEach(function (b) { b.onclick = function () { toggleStar(b.getAttribute('data-date')); render(); }; });
      }
      render();
    }).catch(function (e) { root.innerHTML = '<p class="muted">Không tải được bản tin: ' + esc(e.message) + '</p>'; newsLoaded = false; });
  }
  function setView(v) {
    if (v === 'news') loadNews();
    S.view = v; document.body.classList.toggle('news', v === 'news');
    $('#tab-chart').setAttribute('aria-selected', String(v === 'chart')); $('#tab-news').setAttribute('aria-selected', String(v === 'news'));
  }
  document.addEventListener('DOMContentLoaded', init);
})();
