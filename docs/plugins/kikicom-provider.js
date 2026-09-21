/*
 * kikicom 上空ダッシュボードを Open MCT のドメインオブジェクトとして見せるプラグイン。
 * kikimimi(docs/plugins/kikimimi-provider.js)と同じく、addRoot() + 固定identifierの
 * object providerで単一の合成ビューを提供する。地図は MapLibre GL JS をビューの中に
 * 直接埋め込む。頻度プロットは Open MCT の Plot API を使わず自前SVGで描く(kikimimiと同じ理由)。
 *
 * データは data/ 以下(scripts/build-viz-data.py が slate 上で書き出す)。
 *   live.geojson   いま位置がわかっている機体(10秒ごとに再取得)
 *   tracks.geojson 直近N時間の航跡(1分ごと)
 *   points.geojson 直近N時間の全位置(高度の点、1分ごと)
 *   stats.json     時間別集計・受信機の状態・機体表
 *
 * ローカル試作:公的機・自衛隊機の区分と公開粒度の方針(人のレビュー)が
 * 決まるまで、data/ は公開しない(.gitignore済み)。
 */
(function () {
  var NAMESPACE = 'kikicom';
  var ROOT_KEY = 'root';
  var SVG_NS = 'http://www.w3.org/2000/svg';
  var LIVE_MS = 10000;
  var TRACK_MS = 60000;
  var BASEMAP_STYLE = 'https://stars.optgeo.org/style/bvmap-starlight';
  var FONT_LATIN = ['Open Sans Bold'];
  var FONT_JA = ['Noto Sans JP Regular'];

  // 高度(ft)→色。tar1090系と同じ「低いほど暖色、高いほど寒色」
  var ALT_STOPS = [0, '#ff4d4d', 2000, '#ff9f1c', 5000, '#ffd60a',
    10000, '#7bd389', 20000, '#2ec4b6', 30000, '#4ea8de', 40000, '#b388eb'];

  function altColorExpr(prop) {
    return ['interpolate', ['linear'], ['coalesce', ['get', prop], 0]].concat(ALT_STOPS);
  }

  function fetchJson(url) {
    return fetch(url, { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function el(tag, className, text) {
    var e = document.createElement(tag);
    if (className) { e.className = className; }
    if (text != null) { e.textContent = text; }
    return e;
  }

  function svgEl(tag, attrs) {
    var e = document.createElementNS(SVG_NS, tag);
    Object.keys(attrs || {}).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    return e;
  }

  function fmt(v, digits, unit) {
    if (v == null || v === '') { return '—'; }
    if (typeof v === 'number') { v = v.toFixed(digits || 0); }
    return v + (unit || '');
  }

  // 受信点を中心にした距離リング(km)
  function ringFeatures(lon, lat, radiiKm) {
    return radiiKm.map(function (km) {
      var coords = [];
      for (var i = 0; i <= 96; i += 1) {
        var a = (i / 96) * 2 * Math.PI;
        var dLat = (km / 111.32) * Math.cos(a);
        var dLon = (km / (111.32 * Math.cos(lat * Math.PI / 180))) * Math.sin(a);
        coords.push([lon + dLon, lat + dLat]);
      }
      return {
        type: 'Feature',
        geometry: { type: 'LineString', coordinates: coords },
        properties: { label: km + 'km' }
      };
    });
  }

  // 機体アイコン(SDF。色は icon-color で高度ごとに塗る)
  function planeImage() {
    var size = 48;
    var c = document.createElement('canvas');
    c.width = size; c.height = size;
    var g = c.getContext('2d');
    g.fillStyle = '#fff';
    g.beginPath();
    // 上向きの機体シルエット(胴体・主翼・尾翼)
    g.moveTo(24, 3); g.lineTo(28, 18); g.lineTo(45, 28); g.lineTo(45, 32); g.lineTo(28, 27);
    g.lineTo(27, 38); g.lineTo(33, 43); g.lineTo(33, 46); g.lineTo(24, 43); g.lineTo(15, 46);
    g.lineTo(15, 43); g.lineTo(21, 38); g.lineTo(20, 27); g.lineTo(3, 32); g.lineTo(3, 28);
    g.lineTo(20, 18); g.closePath();
    g.fill();
    return g.getImageData(0, 0, size, size);
  }

  function createMap(container, receiver) {
    var map = new maplibregl.Map({
      container: container,
      center: [receiver.lon, receiver.lat - 0.25],
      zoom: 7.6,
      attributionControl: { compact: true },
      // 背景地図: bvmap-starlight(国土地理院最適化ベクトルタイルのグレースケール版、
      // stars.optgeo.org の Martin が配信)。フォントも同じサーバーのものを使う
      style: BASEMAP_STYLE
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-right');
    map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-left');

    var empty = { type: 'FeatureCollection', features: [] };
    map.on('load', function () {
      map.addImage('plane', planeImage(), { sdf: true });

      map.addSource('rings', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: ringFeatures(receiver.lon, receiver.lat, [25, 50, 100]) }
      });
      map.addLayer({
        id: 'rings', type: 'line', source: 'rings',
        paint: { 'line-color': '#555a63', 'line-width': 1, 'line-dasharray': [3, 3], 'line-opacity': 0.8 }
      });
      map.addLayer({
        id: 'rings-label', type: 'symbol', source: 'rings',
        layout: {
          'symbol-placement': 'line', 'text-field': ['get', 'label'], 'text-size': 11,
          'text-font': FONT_JA
        },
        paint: { 'text-color': '#444', 'text-halo-color': '#fff', 'text-halo-width': 1.5 }
      });

      map.addSource('tracks', { type: 'geojson', data: empty });
      // 明るい背景地図の上で黄色系が埋もれないよう、暗い縁取りを下に敷く
      map.addLayer({
        id: 'tracks-casing', type: 'line', source: 'tracks',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': '#1b1d22', 'line-width': 3.2, 'line-opacity': 0.35 }
      });
      map.addLayer({
        id: 'tracks', type: 'line', source: 'tracks',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': altColorExpr('alt_max'), 'line-width': 1.6, 'line-opacity': 0.9 }
      });

      map.addSource('points', { type: 'geojson', data: empty });
      map.addLayer({
        id: 'points', type: 'circle', source: 'points',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 1.2, 10, 2.5],
          'circle-color': altColorExpr('alt'), 'circle-opacity': 0.9,
          'circle-stroke-color': '#1b1d22', 'circle-stroke-width': 0.3
        }
      });

      map.addSource('receiver', {
        type: 'geojson',
        data: { type: 'Feature', geometry: { type: 'Point', coordinates: [receiver.lon, receiver.lat] }, properties: {} }
      });
      map.addLayer({
        id: 'receiver', type: 'circle', source: 'receiver',
        paint: { 'circle-radius': 5, 'circle-color': '#e63946', 'circle-stroke-color': '#ffffff', 'circle-stroke-width': 2 }
      });

      map.addSource('live', { type: 'geojson', data: empty });
      map.addLayer({
        id: 'live', type: 'symbol', source: 'live',
        layout: {
          'icon-image': 'plane', 'icon-size': 0.55,
          'icon-rotate': ['coalesce', ['get', 'track'], 0],
          'icon-rotation-alignment': 'map', 'icon-allow-overlap': true,
          'text-field': ['coalesce', ['get', 'flight'], ''], 'text-size': 11,
          'text-font': FONT_LATIN, 'text-offset': [0, 1.5], 'text-anchor': 'top',
          'text-optional': true
        },
        paint: {
          'icon-color': altColorExpr('alt'),
          'icon-halo-color': '#1b1d22', 'icon-halo-width': 1.5,
          'text-color': '#1b1d22', 'text-halo-color': '#fff', 'text-halo-width': 1.5
        }
      });

      ['live', 'tracks'].forEach(function (layer) {
        map.on('click', layer, function (e) {
          var p = e.features[0].properties;
          // 便名などは電波で受けた値なので、innerHTML に連結せず DOM で組み立てる
          // (kikimimi と同じ方針)
          var box = el('div');
          box.appendChild(el('b', null, p.flight || '(便名なし)'));
          box.appendChild(document.createTextNode(' ' + p.hex + (p.country ? ' / ' + p.country : '')));
          box.appendChild(el('br'));
          box.appendChild(document.createTextNode(layer === 'live'
            ? '高度 ' + fmt(p.alt, 0, 'ft') + ' / ' + fmt(p.gs, 0, 'kt') + ' / 距離 ' + fmt(p.dst_km, 1, 'km')
            : '高度 ' + fmt(p.alt_min, 0) + '–' + fmt(p.alt_max, 0, 'ft') + ' / ' + p.n + '点 / ' +
              new Date(p.t0 * 1000).toLocaleTimeString('ja-JP') + '–' +
              new Date(p.t1 * 1000).toLocaleTimeString('ja-JP')));
          new maplibregl.Popup({ closeButton: false }).setLngLat(e.lngLat).setDOMContent(box).addTo(map);
        });
        map.on('mouseenter', layer, function () { map.getCanvas().style.cursor = 'pointer'; });
        map.on('mouseleave', layer, function () { map.getCanvas().style.cursor = ''; });
      });
      map.fire('kikicom:ready');
    });
    return map;
  }

  function setSource(map, id, data) {
    if (!map || !data || !map.getSource(id)) { return; }
    map.getSource(id).setData(data);
  }

  function renderLegend(container) {
    var legend = el('div', 'kikicom-legend');
    legend.appendChild(el('span', 'kikicom-legend-title', '高度'));
    for (var i = 0; i < ALT_STOPS.length; i += 2) {
      var item = el('span', 'kikicom-legend-item');
      var sw = el('span', 'kikicom-legend-swatch');
      sw.style.background = ALT_STOPS[i + 1];
      item.appendChild(sw);
      item.appendChild(document.createTextNode(ALT_STOPS[i] >= 1000 ? (ALT_STOPS[i] / 1000) + 'k' : String(ALT_STOPS[i])));
      legend.appendChild(item);
    }
    legend.appendChild(el('span', 'kikicom-legend-unit', 'ft'));
    container.appendChild(legend);
  }

  function renderCards(container, stats) {
    container.textContent = '';
    var live = (stats && stats.live) || {};
    var win = (stats && stats.window) || {};
    var health = (stats && stats.health) || {};
    var hourly = (stats && stats.hourly) || [];
    var lastHour = hourly.length ? hourly[hourly.length - 1] : {};
    [
      ['いま位置のわかる機体', fmt(live.with_position), '受信中 ' + fmt(live.aircraft_total) + '機'],
      ['この1時間の機体', fmt(lastHour.aircraft), '位置 ' + fmt(lastHour.positions) + '件'],
      ['直近' + fmt(win.hours) + '時間', fmt(win.aircraft) + '機', '航跡 ' + fmt(win.tracks) + ' / 位置 ' + fmt(win.positions)],
      ['受信メッセージ/分', fmt(health.messages_1min), '信号 ' + fmt(health.signal, 1) + ' / 雑音 ' + fmt(health.noise, 1) + ' dBFS']
    ].forEach(function (c) {
      var card = el('div', 'kikicom-stat-card');
      card.appendChild(el('div', 'kikicom-stat-label', c[0]));
      card.appendChild(el('div', 'kikicom-stat-value', c[1]));
      card.appendChild(el('div', 'kikicom-stat-sub', c[2]));
      container.appendChild(card);
    });
  }

  // 時間別の機体数(棒)。Plot APIは使わず自前SVG
  function renderHourly(container, hourly) {
    container.textContent = '';
    if (!hourly || !hourly.length) {
      container.appendChild(el('p', 'kikicom-caption', 'まだ蓄積されたデータがありません。'));
      return;
    }
    var width = 480, height = 220;
    var m = { top: 12, right: 8, bottom: 30, left: 34 };
    var pw = width - m.left - m.right, ph = height - m.top - m.bottom;
    var maxV = Math.max.apply(null, hourly.map(function (h) { return h.aircraft; }).concat([5])) * 1.15;
    var bw = pw / hourly.length;
    var svg = svgEl('svg', { viewBox: '0 0 ' + width + ' ' + height, class: 'kikicom-plot-svg', role: 'img',
      'aria-label': '時間別の受信機体数' });
    for (var i = 0; i <= 4; i += 1) {
      var v = maxV * i / 4, y = m.top + ph - (v / maxV) * ph;
      svg.appendChild(svgEl('line', { x1: m.left, x2: width - m.right, y1: y, y2: y, class: 'kikicom-plot-grid' }));
      var t = svgEl('text', { x: m.left - 5, y: y + 4, class: 'kikicom-plot-axis', 'text-anchor': 'end' });
      t.textContent = Math.round(v);
      svg.appendChild(t);
    }
    hourly.forEach(function (h, idx) {
      var x = m.left + idx * bw;
      var bh = (h.aircraft / maxV) * ph;
      var r = svgEl('rect', { x: x + 1, y: m.top + ph - bh, width: Math.max(bw - 2, 1), height: bh, class: 'kikicom-plot-bar' });
      var hour = new Date(h.t).getHours();
      r.appendChild(svgEl('title')).textContent = hour + '時台: ' + h.aircraft + '機 / 位置 ' + h.positions + '件';
      svg.appendChild(r);
      if (hour % 3 === 0) {
        var lbl = svgEl('text', { x: x + bw / 2, y: height - 8, class: 'kikicom-plot-axis', 'text-anchor': 'middle' });
        lbl.textContent = hour + '時';
        svg.appendChild(lbl);
      }
    });
    container.appendChild(svg);
  }

  function renderTable(container, rows) {
    container.textContent = '';
    if (!rows || !rows.length) {
      container.appendChild(el('p', 'kikicom-caption', 'いま位置のわかる機体はありません。'));
      return;
    }
    var table = el('table', 'kikicom-table');
    var head = el('tr');
    ['便名', 'ICAO', '国', '高度ft', '昇降ft/分', '速度kt', '距離km', '方位', 'RSSI'].forEach(function (h) {
      head.appendChild(el('th', null, h));
    });
    table.appendChild(head);
    rows.forEach(function (r) {
      var tr = el('tr');
      [r.flight || '—', r.hex, r.country || '—', fmt(r.alt), fmt(r.rate), fmt(r.gs),
        fmt(r.dst_km, 1), fmt(r.dir, 0, '°'), fmt(r.rssi, 1)].forEach(function (v) {
        tr.appendChild(el('td', null, v));
      });
      tr.className = 'kikicom-pass-row';
      tr.title = 'クリックでこの機体のページへ';
      tr.addEventListener('click', function () {
        window.location.hash = aircraftPath(r.hex.replace(/[^0-9a-z]/gi, '').toLowerCase());
      });
      table.appendChild(tr);
    });
    container.appendChild(table);
  }

  function buildDashboard(container) {
    var root = el('div', 'kikicom-dashboard');
    root.appendChild(el('h1', 'kikicom-title', 'kikicom 上空ダッシュボード'));
    root.appendChild(el('p', 'kikicom-subtitle',
      '月寒(札幌市豊平区)の受信機(RTL-SDR + readsb、1090MHz ADS-B)が捉えた航空機。' +
      '赤丸が受信点(約1km精度)、破線は 25/50/100km。受信率は周辺機の2〜4割で、南東(新千歳方面)が最もよく見える。'));
    root.appendChild(el('div', 'kikicom-banner',
      'ローカル試作:公的機・自衛隊機の区分と公開粒度の方針(人のレビュー)が決まるまで公開しない。'));

    var cards = el('div', 'kikicom-lad-row');
    root.appendChild(cards);

    var mapPanel = el('div', 'kikicom-panel');
    mapPanel.appendChild(el('h2', 'kikicom-panel-title', '航跡(直近の数時間)と現在位置'));
    var mapEl = el('div', 'kikicom-map');
    mapPanel.appendChild(mapEl);
    renderLegend(mapPanel);
    root.appendChild(mapPanel);

    var row = el('div', 'kikicom-two-col');
    var plotPanel = el('div', 'kikicom-panel');
    plotPanel.appendChild(el('h2', 'kikicom-panel-title', '時間別の受信機体数(直近24時間)'));
    var plotBody = el('div');
    plotPanel.appendChild(plotBody);
    plotPanel.appendChild(el('p', 'kikicom-caption',
      '雪害検知の基準線になる系列。基準線の起点は 2026-09-21 17:50(アンテナ位置を固定した時刻)。'));
    row.appendChild(plotPanel);

    var tablePanel = el('div', 'kikicom-panel');
    tablePanel.appendChild(el('h2', 'kikicom-panel-title', 'いま位置のわかる機体(近い順)'));
    var tableBody = el('div', 'kikicom-table-wrap');
    tablePanel.appendChild(tableBody);
    row.appendChild(tablePanel);
    root.appendChild(row);

    var notes = el('div', 'kikicom-panel');
    notes.appendChild(el('h2', 'kikicom-panel-title', '人間による確認・注釈'));
    notes.appendChild(el('p', 'kikicom-caption',
      '気づいたこと(公的機・自衛隊機らしい機体、雪の日の流量の変化など)は、左のツリーの' +
      '「マイアイテム」に作成した Notebook に記録してください。'));
    root.appendChild(notes);

    var footer = el('p', 'kikicom-footer', '');
    root.appendChild(footer);
    container.appendChild(root);

    return { cards: cards, mapEl: mapEl, plotBody: plotBody, tableBody: tableBody, footer: footer };
  }

  // ---------------------------------------------------------------------------
  // 機体ごとのビュー(タイムライン・機体ページ)
  // ---------------------------------------------------------------------------
  var GAP_SEC = 600; // scripts/build-viz-data.py と同じ、通過の区切り

  // 高度→色(ALT_STOPS の線形補間)。SVG 用
  function altColor(alt) {
    if (alt == null) { return '#888'; }
    for (var i = 0; i < ALT_STOPS.length - 2; i += 2) {
      var a0 = ALT_STOPS[i], a1 = ALT_STOPS[i + 2];
      if (alt <= a1) {
        var f = Math.max(0, Math.min(1, (alt - a0) / (a1 - a0)));
        return mixHex(ALT_STOPS[i + 1], ALT_STOPS[i + 3], f);
      }
    }
    return ALT_STOPS[ALT_STOPS.length - 1];
  }

  function mixHex(c0, c1, f) {
    var a = parseInt(c0.slice(1), 16), b = parseInt(c1.slice(1), 16);
    var r = Math.round(((a >> 16) & 255) * (1 - f) + ((b >> 16) & 255) * f);
    var g = Math.round(((a >> 8) & 255) * (1 - f) + ((b >> 8) & 255) * f);
    var bl = Math.round((a & 255) * (1 - f) + (b & 255) * f);
    return '#' + ((1 << 24) + (r << 16) + (g << 8) + bl).toString(16).slice(1);
  }

  function hhmm(t) {
    var d = new Date(t * 1000);
    return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');
  }

  function hhmmss(t) {
    return new Date(t * 1000).toLocaleTimeString('ja-JP');
  }

  function durationLabel(sec) {
    if (sec < 60) { return Math.round(sec) + '秒'; }
    if (sec < 3600) { return Math.round(sec / 60) + '分'; }
    return (sec / 3600).toFixed(1) + '時間';
  }

  function aircraftLabel(a) {
    return (a.flights && a.flights.length ? a.flights.join('/') : '(便名なし)') + ' ' + a.hex;
  }

  function aircraftPath(key) {
    return '#/browse/' + NAMESPACE + ':' + ROOT_KEY + '/' + NAMESPACE + ':aircraft/' + NAMESPACE + ':ac-' + key;
  }

  var indexCache = { at: 0, promise: null };
  function fetchIndex() {
    if (!indexCache.promise || Date.now() - indexCache.at > 60000) {
      indexCache.at = Date.now();
      indexCache.promise = fetchJson('data/aircraft/index.json').then(function (d) {
        return (d && d.aircraft) || [];
      });
    }
    return indexCache.promise;
  }

  // 全機体のタイムライン(1機1行、通過ごとの横棒、色は平均高度)
  function renderTimeline(container, list) {
    container.textContent = '';
    if (!list.length) {
      container.appendChild(el('p', 'kikicom-caption', 'まだ機体の記録がありません。'));
      return;
    }
    var now = Date.now() / 1000;
    var tMin = Math.min.apply(null, list.map(function (a) { return a.first; }));
    tMin = Math.floor(tMin / 3600) * 3600;
    var tMax = now;
    var labelW = 190, width = Math.max(container.clientWidth || 900, 600), rowH = 18, top = 24;
    var plotW = width - labelW - 12;
    var height = top + list.length * rowH + 8;
    var x = function (t) { return labelW + ((t - tMin) / (tMax - tMin)) * plotW; };
    var svg = svgEl('svg', { width: width, height: height, class: 'kikicom-timeline-svg', role: 'img',
      'aria-label': '機体ごとの観測タイムライン' });

    for (var h = Math.ceil(tMin / 3600) * 3600; h <= tMax; h += 3600) {
      svg.appendChild(svgEl('line', { x1: x(h), x2: x(h), y1: top - 4, y2: height, class: 'kikicom-plot-grid' }));
      var tl = svgEl('text', { x: x(h), y: top - 8, class: 'kikicom-plot-axis', 'text-anchor': 'middle' });
      tl.textContent = new Date(h * 1000).getHours() + '時';
      svg.appendChild(tl);
    }
    svg.appendChild(svgEl('line', { x1: x(now), x2: x(now), y1: top - 4, y2: height, class: 'kikicom-timeline-now' }));

    list.forEach(function (a, i) {
      var y = top + i * rowH;
      var row = svgEl('g', { class: 'kikicom-timeline-row' });
      row.appendChild(svgEl('rect', { x: 0, y: y, width: width, height: rowH, class: 'kikicom-timeline-hit' }));
      var name = svgEl('text', { x: 4, y: y + 13, class: 'kikicom-timeline-label' });
      name.textContent = (a.flights[0] || '—') + '  ' + a.hex + (a.country ? '  ' + a.country : '');
      row.appendChild(name);
      a.passes.forEach(function (p) {
        var bx = x(p.t0), bw = Math.max(x(p.t1) - bx, 3);
        var bar = svgEl('rect', { x: bx, y: y + 3, width: bw, height: rowH - 6, rx: 2,
          fill: altColor(p.alt_mean), class: 'kikicom-timeline-bar' });
        bar.appendChild(svgEl('title')).textContent =
          aircraftLabel(a) + '\n' + hhmmss(p.t0) + '–' + hhmmss(p.t1) + '(' + durationLabel(p.t1 - p.t0) + ')\n' +
          p.phase + ' ' + fmt(p.alt0) + '→' + fmt(p.alt1) + 'ft / 最接近 ' + fmt(p.dst_min, 1, 'km') + ' / ' + p.n + '点';
        row.appendChild(bar);
      });
      row.addEventListener('click', function () { window.location.hash = aircraftPath(a.key); });
      svg.appendChild(row);
    });
    container.appendChild(svg);
  }

  var timelineViewProvider = {
    key: 'kikicom.timeline.view',
    name: '機体タイムライン',
    canView: function (o) { return o.type === 'kikicom.timeline'; },
    view: function () {
      var root, body, timer;
      function refresh() {
        indexCache.at = 0;
        fetchIndex().then(function (list) {
          if (!body) { return; }
          var sub = root.querySelector('.kikicom-subtitle');
          sub.textContent = '直近24時間に位置を受信した ' + list.length + ' 機。横棒は1回の通過' +
            '(10分以上途切れたら別の通過)、色は平均高度。行をクリックするとその機体のページへ。';
          renderTimeline(body, list);
        });
      }
      return {
        show: function (element) {
          root = el('div', 'kikicom-dashboard');
          root.appendChild(el('h1', 'kikicom-title', '機体タイムライン'));
          root.appendChild(el('p', 'kikicom-subtitle', ''));
          var panel = el('div', 'kikicom-panel');
          body = el('div', 'kikicom-timeline-wrap');
          panel.appendChild(body);
          renderLegend(panel);
          root.appendChild(panel);
          element.appendChild(root);
          refresh();
          timer = setInterval(refresh, TRACK_MS);
        },
        destroy: function () { clearInterval(timer); body = undefined; root = undefined; }
      };
    }
  };

  // 時系列の小さなグラフ(通過の切れ目では線を切る)
  function renderSeries(container, spec, s, range) {
    var idx = [];
    for (var i = 0; i < s.t.length; i += 1) {
      if (s.t[i] >= range[0] && s.t[i] <= range[1] && s[spec.key][i] != null) { idx.push(i); }
    }
    var panel = el('div', 'kikicom-series');
    panel.appendChild(el('div', 'kikicom-series-title', spec.label + '(' + spec.unit + ')'));
    if (!idx.length) {
      panel.appendChild(el('p', 'kikicom-caption', 'データなし'));
      container.appendChild(panel);
      return;
    }
    var vals = idx.map(function (i) { return s[spec.key][i]; });
    var vMin = Math.min.apply(null, vals), vMax = Math.max.apply(null, vals);
    if (spec.zero) { vMin = Math.min(vMin, 0); vMax = Math.max(vMax, 0); }
    if (vMax - vMin < (spec.minSpan || 1)) {
      var mid = (vMax + vMin) / 2; vMin = mid - (spec.minSpan || 1) / 2; vMax = mid + (spec.minSpan || 1) / 2;
    }
    var width = 700, height = 120, m = { top: 8, right: 10, bottom: 20, left: 52 };
    var pw = width - m.left - m.right, ph = height - m.top - m.bottom;
    var x = function (t) { return m.left + ((t - range[0]) / Math.max(range[1] - range[0], 1)) * pw; };
    var y = function (v) { return m.top + ph - ((v - vMin) / (vMax - vMin)) * ph; };
    var svg = svgEl('svg', { viewBox: '0 0 ' + width + ' ' + height, class: 'kikicom-plot-svg' });
    [vMin, (vMin + vMax) / 2, vMax].forEach(function (v) {
      svg.appendChild(svgEl('line', { x1: m.left, x2: width - m.right, y1: y(v), y2: y(v), class: 'kikicom-plot-grid' }));
      var t = svgEl('text', { x: m.left - 6, y: y(v) + 4, class: 'kikicom-plot-axis', 'text-anchor': 'end' });
      t.textContent = Math.round(v);
      svg.appendChild(t);
    });
    if (spec.zero && vMin < 0 && vMax > 0) {
      svg.appendChild(svgEl('line', { x1: m.left, x2: width - m.right, y1: y(0), y2: y(0), class: 'kikicom-series-zero' }));
    }
    [range[0], (range[0] + range[1]) / 2, range[1]].forEach(function (t, k) {
      var lbl = svgEl('text', { x: x(t), y: height - 4, class: 'kikicom-plot-axis',
        'text-anchor': k === 0 ? 'start' : k === 2 ? 'end' : 'middle' });
      lbl.textContent = hhmmss(t);
      svg.appendChild(lbl);
    });
    var d = '', prevT = null;
    idx.forEach(function (i) {
      var cmd = (prevT === null || s.t[i] - prevT > GAP_SEC) ? 'M' : 'L';
      d += cmd + x(s.t[i]).toFixed(1) + ',' + y(s[spec.key][i]).toFixed(1);
      prevT = s.t[i];
    });
    svg.appendChild(svgEl('path', { d: d, class: 'kikicom-series-line' }));
    idx.forEach(function (i) {
      svg.appendChild(svgEl('circle', { cx: x(s.t[i]), cy: y(s[spec.key][i]), r: 2,
        fill: spec.key === 'alt' ? altColor(s.alt[i]) : '#5dade2' }));
    });
    panel.appendChild(svg);
    container.appendChild(panel);
  }

  var SERIES_SPECS = [
    { key: 'alt', label: '気圧高度', unit: 'ft', minSpan: 500 },
    { key: 'rate', label: '昇降率', unit: 'ft/分', zero: true, minSpan: 500 },
    { key: 'gs', label: '対地速度', unit: 'kt', minSpan: 20 },
    { key: 'dst', label: '受信点からの距離', unit: 'km', minSpan: 5 },
    { key: 'rssi', label: '受信強度', unit: 'dBFS', minSpan: 3 },
    { key: 'oat', label: '外気温(Comm-B由来)', unit: '℃', minSpan: 3 },
    { key: 'ws', label: '風速(Comm-B由来)', unit: 'kt', minSpan: 5 }
  ];

  // 機体の航跡を高度で色分けした線分に分解する(通過の切れ目では線を切る)
  function trackSegments(s, range) {
    var feats = [];
    for (var i = 1; i < s.t.length; i += 1) {
      if (s.t[i] < range[0] || s.t[i - 1] > range[1] || s.t[i] - s.t[i - 1] > GAP_SEC) { continue; }
      feats.push({ type: 'Feature',
        geometry: { type: 'LineString', coordinates: [[s.lon[i - 1], s.lat[i - 1]], [s.lon[i], s.lat[i]]] },
        properties: { alt: s.alt[i] } });
    }
    return { type: 'FeatureCollection', features: feats };
  }

  function createAircraftMap(container, data, range, receiver) {
    var map = new maplibregl.Map({ container: container, style: BASEMAP_STYLE,
      center: [receiver.lon, receiver.lat], zoom: 8, attributionControl: { compact: true } });
    map.addControl(new maplibregl.NavigationControl(), 'top-right');
    map.on('load', function () {
      // 高度で色を変えるため2点ずつの短い線分にしているので、簡略化(tolerance)で
      // 低ズーム時に線分が捨てられないよう 0 にする
      map.addSource('seg', { type: 'geojson', data: trackSegments(data.series, range), tolerance: 0 });
      map.addLayer({ id: 'seg-casing', type: 'line', source: 'seg', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#1b1d22', 'line-width': 5, 'line-opacity': 0.35 } });
      map.addLayer({ id: 'seg', type: 'line', source: 'seg', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': altColorExpr('alt'), 'line-width': 3 } });
      map.addSource('rx', { type: 'geojson',
        data: { type: 'Feature', geometry: { type: 'Point', coordinates: [receiver.lon, receiver.lat] }, properties: {} } });
      map.addLayer({ id: 'rx', type: 'circle', source: 'rx',
        paint: { 'circle-radius': 5, 'circle-color': '#e63946', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } });
      fitAircraft(map, data.series, range, receiver);
    });
    return map;
  }

  function fitAircraft(map, s, range, receiver) {
    var b = new maplibregl.LngLatBounds([receiver.lon, receiver.lat], [receiver.lon, receiver.lat]);
    for (var i = 0; i < s.t.length; i += 1) {
      if (s.t[i] >= range[0] && s.t[i] <= range[1]) { b.extend([s.lon[i], s.lat[i]]); }
    }
    map.fitBounds(b, { padding: 40, maxZoom: 11, duration: 0 });
  }

  function renderPassTable(container, passes, selected, onSelect) {
    container.textContent = '';
    var table = el('table', 'kikicom-table');
    var head = el('tr');
    ['#', '時刻', '長さ', '判定', '高度ft(始→終)', '最接近km', '点数'].forEach(function (h) { head.appendChild(el('th', null, h)); });
    table.appendChild(head);
    passes.forEach(function (p, i) {
      var tr = el('tr', 'kikicom-pass-row' + (i === selected ? ' kikicom-pass-selected' : ''));
      [String(i + 1), hhmmss(p.t0) + '–' + hhmmss(p.t1), durationLabel(p.t1 - p.t0), p.phase,
        fmt(p.alt0) + '→' + fmt(p.alt1), fmt(p.dst_min, 1), String(p.n)].forEach(function (v) {
        tr.appendChild(el('td', null, v));
      });
      tr.addEventListener('click', function () { onSelect(i); });
      table.appendChild(tr);
    });
    var all = el('tr', 'kikicom-pass-row' + (selected === -1 ? ' kikicom-pass-selected' : ''));
    var td = el('td', null, '全ての通過をまとめて表示');
    td.colSpan = 7;
    all.appendChild(td);
    all.addEventListener('click', function () { onSelect(-1); });
    table.appendChild(all);
    container.appendChild(table);
  }

  var aircraftViewProvider = {
    key: 'kikicom.aircraft.view',
    name: '機体モニター',
    canView: function (o) { return o.type === 'kikicom.aircraft'; },
    view: function (domainObject) {
      var root, map, timer, data, selected = null, parts;
      var key = domainObject.identifier.key.replace(/^ac-/, '');

      function rangeOf() {
        var p = data.passes;
        if (selected === -1 || !p.length) { return [data.series.t[0], data.series.t[data.series.t.length - 1]]; }
        var q = p[selected];
        return [q.t0 - 5, q.t1 + 5];
      }

      function draw() {
        var s = data.series, range = rangeOf();
        root.querySelector('.kikicom-title').textContent = aircraftLabel(data);
        root.querySelector('.kikicom-subtitle').textContent =
          [data.country || '国籍不明', data.category ? '区分 ' + data.category : null,
            data.squawk ? 'スコーク ' + data.squawk : null,
            '初観測 ' + hhmmss(s.t[0]), '最終観測 ' + hhmmss(s.t[s.t.length - 1])].filter(Boolean).join(' / ');

        parts.cards.textContent = '';
        var alts = s.alt.filter(function (v) { return v != null; });
        var dsts = s.dst.filter(function (v) { return v != null; });
        [
          ['通過回数', String(data.passes.length), '直近24時間'],
          ['位置の受信数', String(s.t.length), '最後の受信 ' + durationLabel(Date.now() / 1000 - s.t[s.t.length - 1]) + '前'],
          ['高度の範囲', alts.length ? Math.min.apply(null, alts) + '–' + Math.max.apply(null, alts) : '—', 'ft'],
          ['最接近', dsts.length ? Math.min.apply(null, dsts).toFixed(1) : '—', 'km(受信点から)']
        ].forEach(function (c) {
          var card = el('div', 'kikicom-stat-card');
          card.appendChild(el('div', 'kikicom-stat-label', c[0]));
          card.appendChild(el('div', 'kikicom-stat-value', c[1]));
          card.appendChild(el('div', 'kikicom-stat-sub', c[2]));
          parts.cards.appendChild(card);
        });

        renderPassTable(parts.passes, data.passes, selected, function (i) { selected = i; draw(); });

        parts.series.textContent = '';
        SERIES_SPECS.forEach(function (spec) {
          var has = s[spec.key].some(function (v) { return v != null; });
          if (has || ['oat', 'ws'].indexOf(spec.key) === -1) { renderSeries(parts.series, spec, s, range); }
        });

        if (!map) {
          map = createAircraftMap(parts.map, data, range, { lon: 141.40, lat: 43.05 });
        } else if (map.getSource('seg')) {
          map.getSource('seg').setData(trackSegments(s, range));
          fitAircraft(map, s, range, { lon: 141.40, lat: 43.05 });
        }
      }

      function refresh() {
        fetchJson('data/aircraft/' + key + '.json').then(function (d) {
          if (!root) { return; }
          if (!d) {
            root.querySelector('.kikicom-subtitle').textContent = 'この機体は直近24時間の記録から外れました。';
            return;
          }
          var wasLatest = selected === null || (data && selected === data.passes.length - 1);
          data = d;
          if (wasLatest) { selected = data.passes.length - 1; }
          draw();
        });
      }

      return {
        show: function (element) {
          root = el('div', 'kikicom-dashboard');
          root.appendChild(el('h1', 'kikicom-title', domainObject.name));
          root.appendChild(el('p', 'kikicom-subtitle', '読み込み中…'));
          root.appendChild(el('div', 'kikicom-banner',
            'ローカル試作:公的機・自衛隊機の区分と公開粒度の方針(人のレビュー)が決まるまで公開しない。'));
          parts = { cards: el('div', 'kikicom-lad-row') };
          root.appendChild(parts.cards);

          var row = el('div', 'kikicom-two-col');
          var mapPanel = el('div', 'kikicom-panel');
          mapPanel.appendChild(el('h2', 'kikicom-panel-title', '航跡(選択中の通過)'));
          parts.map = el('div', 'kikicom-map kikicom-map-small');
          mapPanel.appendChild(parts.map);
          renderLegend(mapPanel);
          row.appendChild(mapPanel);
          var passPanel = el('div', 'kikicom-panel');
          passPanel.appendChild(el('h2', 'kikicom-panel-title', '通過の一覧(行をクリックで切り替え)'));
          parts.passes = el('div', 'kikicom-table-wrap');
          passPanel.appendChild(parts.passes);
          passPanel.appendChild(el('p', 'kikicom-caption',
            '判定は高度変化による大まかなもの(±1000ft超で上昇/降下)。10分以上途切れたら別の通過として扱う。'));
          row.appendChild(passPanel);
          root.appendChild(row);

          var seriesPanel = el('div', 'kikicom-panel');
          seriesPanel.appendChild(el('h2', 'kikicom-panel-title', 'タイムライン(選択中の通過)'));
          parts.series = el('div', 'kikicom-series-grid');
          seriesPanel.appendChild(parts.series);
          root.appendChild(seriesPanel);

          element.appendChild(root);
          refresh();
          timer = setInterval(refresh, LIVE_MS * 3);
        },
        destroy: function () {
          clearInterval(timer);
          if (map) { map.remove(); }
          map = undefined; root = undefined; parts = undefined;
        }
      };
    }
  };

  var objectProvider = {
    get: function (identifier) {
      var key = identifier.key;
      if (key === ROOT_KEY) {
        return Promise.resolve({
          identifier: identifier, name: 'kikicom 上空ダッシュボード', type: 'kikicom.root', location: 'ROOT',
          composition: [{ namespace: NAMESPACE, key: 'timeline' }, { namespace: NAMESPACE, key: 'aircraft' }]
        });
      }
      if (key === 'timeline') {
        return Promise.resolve({ identifier: identifier, name: '機体タイムライン', type: 'kikicom.timeline',
          location: NAMESPACE + ':' + ROOT_KEY });
      }
      if (key === 'aircraft') {
        return fetchIndex().then(function (list) {
          return {
            identifier: identifier, name: '機体(直近24時間)', type: 'folder',
            location: NAMESPACE + ':' + ROOT_KEY,
            composition: list.slice().reverse().map(function (a) { return { namespace: NAMESPACE, key: 'ac-' + a.key }; })
          };
        });
      }
      if (key.indexOf('ac-') === 0) {
        return fetchIndex().then(function (list) {
          var a = list.filter(function (x) { return 'ac-' + x.key === key; })[0];
          return {
            identifier: identifier, type: 'kikicom.aircraft', location: NAMESPACE + ':aircraft',
            name: a ? ((a.flights[0] || '(便名なし)') + ' ' + a.hex + (a.country ? ' ' + a.country : '')) : key.slice(3)
          };
        });
      }
      return Promise.reject(new Error('unknown kikicom object: ' + key));
    }
  };

  var dashboardViewProvider = {
    key: 'kikicom.dashboard.view',
    name: '上空ダッシュボード',
    canView: function (domainObject) { return domainObject.type === 'kikicom.root'; },
    view: function () {
      var parts, map, timers = [], resizeObserver, ready = false;

      function refreshLive() {
        Promise.all([fetchJson('data/live.geojson'), fetchJson('data/stats.json')]).then(function (res) {
          if (!parts) { return; }
          var stats = res[1];
          renderCards(parts.cards, stats);
          renderTable(parts.tableBody, stats && stats.live && stats.live.table);
          renderHourly(parts.plotBody, stats && stats.hourly);
          parts.footer.textContent = 'データ生成時刻: ' + ((stats && stats.generated_at) || '—');
          if (ready) { setSource(map, 'live', res[0]); }
        });
      }

      function refreshTracks() {
        if (!ready) { return; }
        fetchJson('data/tracks.geojson').then(function (d) { setSource(map, 'tracks', d); });
        fetchJson('data/points.geojson').then(function (d) { setSource(map, 'points', d); });
      }

      return {
        show: function (element) {
          parts = buildDashboard(element);
          fetchJson('data/stats.json').then(function (stats) {
            var receiver = (stats && stats.receiver) || { lon: 141.40, lat: 43.05 };
            map = createMap(parts.mapEl, receiver);
            map.on('kikicom:ready', function () {
              ready = true;
              refreshLive();
              refreshTracks();
            });
            if (window.ResizeObserver) {
              resizeObserver = new ResizeObserver(function () { if (map) { map.resize(); } });
              resizeObserver.observe(parts.mapEl);
            }
          });
          refreshLive();
          timers.push(setInterval(refreshLive, LIVE_MS));
          timers.push(setInterval(refreshTracks, TRACK_MS));
        },
        destroy: function () {
          timers.forEach(clearInterval);
          timers = [];
          if (resizeObserver) { resizeObserver.disconnect(); }
          if (map) { map.remove(); }
          map = undefined;
          parts = undefined;
          ready = false;
        }
      };
    }
  };

  window.KikicomProvider = function install(openmct) {
    openmct.objects.addRoot({ namespace: NAMESPACE, key: ROOT_KEY });
    openmct.objects.addProvider(NAMESPACE, objectProvider);
    openmct.types.addType('kikicom.root', {
      name: 'kikicom 上空ダッシュボード',
      description: 'ADS-Bで受信した航空機の航跡・現在位置・時間別集計をまとめた合成ダッシュボード',
      cssClass: 'icon-object',
      creatable: false
    });
    openmct.types.addType('kikicom.timeline', {
      name: '機体タイムライン', description: '直近24時間の機体ごとの観測区間', cssClass: 'icon-timeline', creatable: false
    });
    openmct.types.addType('kikicom.aircraft', {
      name: '機体', description: 'ICAOアドレス単位の機体モニター', cssClass: 'icon-telemetry', creatable: false
    });
    openmct.objectViews.addProvider(dashboardViewProvider);
    openmct.objectViews.addProvider(timelineViewProvider);
    openmct.objectViews.addProvider(aircraftViewProvider);
  };
})();
