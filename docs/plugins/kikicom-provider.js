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
      style: {
        version: 8,
        glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
        sources: {
          gsi: {
            type: 'raster',
            tiles: ['https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png'],
            tileSize: 256,
            maxzoom: 18,
            attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank">地理院タイル</a>'
          }
        },
        layers: [
          { id: 'bg', type: 'background', paint: { 'background-color': '#1b1d22' } },
          {
            id: 'gsi', type: 'raster', source: 'gsi',
            paint: { 'raster-brightness-max': 0.55, 'raster-saturation': -0.7, 'raster-contrast': 0.1 }
          }
        ]
      }
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
        paint: { 'line-color': '#8a8f99', 'line-width': 0.8, 'line-dasharray': [3, 3], 'line-opacity': 0.7 }
      });
      map.addLayer({
        id: 'rings-label', type: 'symbol', source: 'rings',
        layout: {
          'symbol-placement': 'line', 'text-field': ['get', 'label'], 'text-size': 11,
          'text-font': ['Open Sans Semibold']
        },
        paint: { 'text-color': '#aab0bb', 'text-halo-color': '#1b1d22', 'text-halo-width': 1.2 }
      });

      map.addSource('tracks', { type: 'geojson', data: empty });
      map.addLayer({
        id: 'tracks', type: 'line', source: 'tracks',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: { 'line-color': altColorExpr('alt_max'), 'line-width': 1.4, 'line-opacity': 0.45 }
      });

      map.addSource('points', { type: 'geojson', data: empty });
      map.addLayer({
        id: 'points', type: 'circle', source: 'points',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 6, 1.2, 10, 2.5],
          'circle-color': altColorExpr('alt'), 'circle-opacity': 0.8
        }
      });

      map.addSource('receiver', {
        type: 'geojson',
        data: { type: 'Feature', geometry: { type: 'Point', coordinates: [receiver.lon, receiver.lat] }, properties: {} }
      });
      map.addLayer({
        id: 'receiver', type: 'circle', source: 'receiver',
        paint: { 'circle-radius': 5, 'circle-color': '#ffffff', 'circle-stroke-color': '#e63946', 'circle-stroke-width': 2 }
      });

      map.addSource('live', { type: 'geojson', data: empty });
      map.addLayer({
        id: 'live', type: 'symbol', source: 'live',
        layout: {
          'icon-image': 'plane', 'icon-size': 0.55,
          'icon-rotate': ['coalesce', ['get', 'track'], 0],
          'icon-rotation-alignment': 'map', 'icon-allow-overlap': true,
          'text-field': ['coalesce', ['get', 'flight'], ''], 'text-size': 11,
          'text-font': ['Open Sans Semibold'], 'text-offset': [0, 1.5], 'text-anchor': 'top',
          'text-optional': true
        },
        paint: {
          'icon-color': altColorExpr('alt'),
          'icon-halo-color': '#000', 'icon-halo-width': 1,
          'text-color': '#f0f0f0', 'text-halo-color': '#000', 'text-halo-width': 1.2
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
      table.appendChild(tr);
    });
    container.appendChild(table);
  }

  function buildDashboard(container) {
    var root = el('div', 'kikicom-dashboard');
    root.appendChild(el('h1', 'kikicom-title', 'kikicom 上空ダッシュボード'));
    root.appendChild(el('p', 'kikicom-subtitle',
      '月寒(札幌市豊平区)の受信機(RTL-SDR + readsb、1090MHz ADS-B)が捉えた航空機。' +
      '白丸が受信点(約1km精度)、破線は 25/50/100km。受信率は周辺機の2〜4割で、南東(新千歳方面)が最もよく見える。'));
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

  var objectProvider = {
    get: function (identifier) {
      if (identifier.key !== ROOT_KEY) {
        return Promise.reject(new Error('unknown kikicom object: ' + identifier.key));
      }
      return Promise.resolve({
        identifier: identifier,
        name: 'kikicom 上空ダッシュボード',
        type: 'kikicom.root',
        location: 'ROOT'
      });
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
    openmct.objectViews.addProvider(dashboardViewProvider);
  };
})();
