// Open MCT シェルの調整(dwg7/sas0 の D83 と dwg7/snow-hokkaido の shell.js に倣う)。
//   1. ツリーを 200px に(保存値がない時だけ。利用者がドラッグした幅は上書きしない)
//   2. Inspect を既定で折りたたむ(ペイン自身のボタンで展開できる)
//   3. 閲覧モード(?viewer=1 またはボタン): ツリー・Inspect・ヘッダーを隠して内容だけ見せる
// openmct.start() より前に読み込むこと(index.html で kikicom-provider.js の前に置く)。
(function () {
  // Open MCT は各ペインの幅を localStorage の 'mct-pane-positions' に保存し、
  // マウント時に適用する(キーはラベルの小文字: 'browse' = ツリー)。保存値がないと
  // ツリーは内容幅任せになり、ノートPCの画面の 25〜40% を占める。
  var PANE_POSITIONS_KEY = 'mct-pane-positions';
  var DEFAULT_TREE_WIDTH = '200px';
  try {
    var saved = JSON.parse(localStorage.getItem(PANE_POSITIONS_KEY) || '{}');
    if (!saved.browse) {
      saved.browse = DEFAULT_TREE_WIDTH;
      localStorage.setItem(PANE_POSITIONS_KEY, JSON.stringify(saved));
    }
  } catch (e) { /* ストレージ不可・JSON破損: Open MCT 既定のまま */ }

  // Inspect ペインはマウント時に URL の hideInspector=true を読んで折りたたむ。
  // 'start' イベント内で付けると最初のルート変更で落ちて効かないので、起動前の
  // 初期 URL のハッシュに付ける。折りたたみは以降のナビゲーションでも保たれる。
  if (!/[?&]hideInspector=/.test(location.hash)) {
    var base = location.hash.length > 2 ? location.hash : '#/browse/';
    location.hash = base + (base.indexOf('?') >= 0 ? '&' : '?') + 'hideInspector=true';
  }

  var root = document.documentElement;
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'kikicom-viewer-btn';
  function setViewer(on) {
    root.classList.toggle('kikicom-viewer', on);
    btn.textContent = on ? '通常表示' : '全画面表示';
    btn.title = on ? 'ツリーと操作パネルを戻す' : 'ツリーと操作パネルを隠して、内容だけを表示する';
    try {
      var u = new URL(location.href);
      if (on) { u.searchParams.set('viewer', '1'); } else { u.searchParams.delete('viewer'); }
      history.replaceState(null, '', u);
    } catch (e) { /* URL の印が付かないだけで、表示は切り替わる */ }
    window.dispatchEvent(new Event('resize')); // 地図などを新しい領域に合わせる
  }
  btn.addEventListener('click', function () { setViewer(!root.classList.contains('kikicom-viewer')); });
  document.addEventListener('DOMContentLoaded', function () {
    document.body.appendChild(btn);
    setViewer(/[?&]viewer=1\b/.test(location.search));
  });
})();
