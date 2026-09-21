# kikicom — Claude Code 引き継ぎドキュメント

このファイルは `dwg7/kikicom` リポジトリのルートに置く、Claude Code向けの
プロジェクト文脈。新しいセッションを開始する際は、まずこのファイルを
読んでください。

姉妹プロジェクト: [dwg7/kikimimi](https://github.com/dwg7/kikimimi)
(同じRPi 4B + RTL-SDR + Mac mini役の機体という物理構成を共有しているが、
ミッション・データの性質・法的な扱いは全く別)

---

## 1. プロジェクト概要

**kikicom** は、SDR(Software Defined Radio)受信の研究プロジェクト。
ADS-B(1090MHz、航空機の位置・高度・速度等のブロードキャスト)を受信し、
地理空間情報として可視化することを目標にする。

### 生まれた経緯

kikimimi(公共ラジオを社会センサーとして使うプロジェクト)の運用中、
「災害のない平和な時期はNHK-FMの監視が退屈」という気づきから、同じ
RTL-SDR一式でどこまで面白いことができるかを探る過程で生まれた。
航空無線(音声)・漁業無線なども検討したが、以下の理由でADS-Bが
最有力候補になった:

- 受信ハードウェアがそのまま流用できる(RTL2832U+R820T2/R828D系チューナーは
  FlightRadar24等のクラウドソース受信網で使われている定番構成そのもの)
- **法的な位置づけがNHK-FMに近い。** ADS-Bは特定の相手方に向けた通信では
  なく、そもそも不特定多数に受信・共有されることを前提に設計された
  ブロードキャストである。FlightRadar24・FlightAware・ADS-B Exchangeという
  世界規模のクラウドソース受信網が合法的に成立していること自体が、この
  性質の裏付けになっている(航空無線の音声交信とは対照的——後者は
  電波法59条「通信の秘密」の対象になりうる、特定の相手方への通信)

### 唯一の法的・倫理的な注意点:軍用機

受信場所(月寒、札幌市豊平区)の近くには、新千歳空港と同一敷地の
**千歳基地(航空自衛隊)**がある。自衛隊機を検出した場合、**公開データからは
除外・一般化する**方針とする(法律の問題というより配慮の問題。
FlightRadar24等の主要サービスも軍用機・特定機体のブロックリストを持つ
慣行がある)。具体的な除外ロジック(ICAOアドレスの割り当てブロック判定、
既知の自衛隊機登録パターン等)は、公開経路を作る前に必ず設計すること。

---

## 2. ハードウェア構成(kikimimiと共有・時分割)

**RTL-SDRは1台しかなく、kikimimiとkikicomで取り合っている。**

```
RPi 4B (m329.local)
  └ RTL-SDR Blog V4(R828D)+ ロッドアンテナ(1本を1090MHz用に約7cmへ改造済み)
      ├ kikimimi用途: speechmap record (NHK-FM 85.2MHz受信)
      └ kikicom用途: readsb (ADS-B 1090MHz受信) ← 現在稼働中
```

### 現在の状態(2026-09-21時点)

- **kikimimiのNHK-FM録音(`kikimimi-record.service`)は停止・無効化済み**
  (ユーザーの明示的な承認を得て、kikicomの実験のためにRTL-SDRを空けた。
  十勝岳が噴火警戒レベル3継続中であることを踏まえた上での判断)
- **kikicomの`adsb-research.service`が稼働中**(後述)
- 元に戻すには(RPi上、sudo -n が使える):
  ```bash
  sudo systemctl disable --now adsb-research.service   # adsb-logger も連動して止まる
  sudo systemctl enable --now kikimimi-record.service
  ```
- **恒久的な解決策は2台目のRTL-SDRの調達。** 安価(数千円程度)なので、
  両プロジェクトを本当に並行稼働させたくなったら検討する

### アンテナの物理条件(実測で確認済み)

- **1090MHzの1/4波長は約6.87cm。** ロッドアンテナの1本を7cmに調整済み
- **垂直偏波が必須。** 航空機トランスポンダのアンテナは機体下面に垂直に
  ついているため、受信アンテナも垂直に立てる
- **屋外設置が事実上必須。** 屋内(NHK-FM用の設置場所のまま)ではゲインを
  0〜最大まで振っても復調成功率0%だったが、ベランダに出しただけで
  即座に複数機を復調成功。原因はおそらく屋内の広帯域ノイズ源
  (PC電源・LED照明ドライバ等)と、建物(壁・窓)による1GHz帯の減衰。
  アンテナの長さの問題ではなかった

---

## 3. 技術的な知見(実測ログ)

### 周波数

1090MHzはICAO/ITUで固定された国際規格。調整の余地は無い。関連する
1030MHz(地上から機体への質問信号)は位置情報を含まないため、可視化用途
としての優先度は低い。

### ゲイン

| ゲイン | 結果 |
|---|---|
| 29.7dB | 屋外でも復調0件。明確に力不足 |
| 40.2dB | 良好(2分間で616有効メッセージ、5機のトラック) |
| 49.6dB(ほぼ最大) | 良好(約1.7分間で158有効メッセージ、3機のトラック) |

40.2dBと49.6dBの比較は、時間帯によって実際の飛来機数が変わるため
厳密なフェア比較にはなっていない(同時刻に2つのゲインを試せない)。
どちらも問題なく機能するので、現在は40.2dBで稼働中。**29.7dB未満は
避けるべき**、というのが唯一の確かな結論。

### `readsb`のRTL-SDR非対応という落とし穴(解決済み)

Raspberry Pi OS Trixie(Debian trixie)がaptで配布している`readsb`
パッケージ(3.14.1630)は、READMEにlibrtlsdrへの静的リンクが明記されて
いるにもかかわらず、`--device-type rtlsdr`が**認識されない**
(`modesbeast`・`gnshulc`・`ifile`・`none`のみサポート)。

当初の回避策は`rtl_sdr | readsb --device-type ifile --ifile -`のパイプ
だったが、**ifileモードはオフライン再生用で、サンプル数ベースの仮想時計
(1970-01-02起点)で動く**。そのため`aircraft.json`の`now`がサービス起動
時刻で固まり、機体が即座に「古い」扱いになって空配列になっていた
(「`aircraft.json`がライブ更新されない」不具合の正体。2026-09-21特定)。

**現在の解決策:** wiedehopf/readsb を`RTLSDR=yes`でRPi上でビルドし、
`/usr/local/bin/readsb`(3.16.16)に導入(`scripts/build-readsb.sh`)。
`--device-type rtlsdr`で直接RTL-SDRを掴むので、時計は実時刻になる。
`/usr/bin/readsb`(Debian版)は残してあるが使わない。ビルドは
`~/build`(SDカード上。tmpfsの/tmpは避ける)で行い、本リポジトリの
checkoutではない(RPiはキャプチャに徹する方針は維持)。

### RPi上のサービス(`scripts/install-adsb-service.sh`で管理)

```bash
ssh m329.local 'bash -s' < scripts/install-adsb-service.sh           # install
ssh m329.local 'bash -s status' < scripts/install-adsb-service.sh    # 状態確認
ssh m329.local 'bash -s uninstall' < scripts/install-adsb-service.sh
```

- `adsb-research.service`: readsb本体。`Conflicts=kikimimi-record.service`
  (RTL-SDRの排他を systemd に表現)。installは kikimimi-record が
  動いていれば拒否する
- `adsb-logger.service`: readsbの`--net-json-port`(127.0.0.1:30047、
  1位置1行のJSON)を受けて、`~/adsb-log/YYYY-MM-DD.jsonl`(UTC日付)に
  追記する小さなPythonロガー(`/usr/local/lib/kikicom/adsb-logger.py`)。
  **これが蓄積データの正**
- ライブJSON: `/run/adsb-research/`(aircraft.json, stats.json等。
  `RuntimeDirectory=`によるtmpfs。数秒おきの書き換えでSDカードを
  傷めないため)。旧出力先`~/adsb-data/`は使っていない
- 受信位置は`--lat 43.05 --lon 141.40`(意図的に約1km精度に丸めてある)

### 受信の切り分け手順(2026-09-21の知見)

- **「周辺に本当に機体がいるか」は adsb.lol の公開APIで確認できる:**
  `curl -s https://api.adsb.lol/v2/point/43.05/141.40/60`
  (airplanes.live APIは要申請で弾かれる)
- ノイズフロアは readsb 表示で約 -42dBFS。受信できている時もできていない
  時もほぼ同じなので、**ノイズ値は受信可否の診断に使えない**
- 無信号時の平均電力(rtl_sdr生IQ、ゲイン 9.7→29.7→49.6dB):
  150MHz: -44.8→-43.8→-34.2 / 1000MHz: -44.8→-44.1→-38.8 /
  1090MHz: -44.8→-44.3→-42.0 dBFS。周波数が上がるほど最大ゲインでの
  ノイズ持ち上がりが小さい(1090MHzでは+2.8dBのみ)=1GHz帯では
  フロントエンドのゲインが効きにくく、ADCノイズ支配に近い。R828D/V4の
  特性として正常範囲かは未確認。**ゲインは下げず、高め(40〜49.6dB)を維持**
- `scripts/coverage-check.py`: adsb.lolで見えている機体のうち、うちの
  readsbが捉えているものを距離・方位・仰角つきで一覧する。アンテナ設置の
  比較用(結果は標準出力のみ、保存しない)
- 2026-09-21 15:15頃、屋外(ベランダ)設置で adsb.lol 上の12機
  (全機仰角6.3°以下、最近接19km)に対し受信0機。ソフト側(時計・
  ライブラリのV4対応・PLL・USBサンプル欠損)は問題なしと確認済みで、
  物理側(アンテナ接続・エレメント・見通し)の確認待ち
- 周辺機の多くは低高度・遠距離(=低仰角)。受信性能はほぼ
  「地平線方向の見通し」で決まる

### 実証済みの成功例

ICAOアドレス`846682` → 登録番号**JA13HC**、機種**ATR 42-600**、
運航者**北海道エアシステム(HAC)**と特定できた([adsdb.io](https://api.adsbdb.com/)で
照会)。降下中(-1024ft/分)、高度約2500ft、丘珠空港(RJCO)から
北へ数kmの地点(43.036°N, 141.368°E)——丘珠への進入中と推定される。
**キャプチャ→デコード→位置特定→機体照会という経路が、一気通貫で
実証できている。**

---

## 4. リポジトリの方針

- **生データはリポジトリに残さない。** 表現(可視化)に必要なデータのみ
  コミットする。生データ(位置ログJSONL等)はRPi/Mac mini役の機体に置く
- **`docs/`はGitHub Pages(gh-pages)用に予約。** ドキュメント用の
  フォルダが必要なら`documents/`を使う(ADRは`documents/decisions/`)
- ライセンスは**CC0 1.0**(2026-09-21確定)

---

## 5. アーキテクチャ方針(一部着手)

### 役割分担はkikimimiと同じパターンを踏襲する

```
RPi 4B (m329.local)
  → readsb でADS-Bを継続受信するだけ。**gitチェックアウトはしない**
    (kikimimiでも「RPiはキャプチャに徹する」という一貫した方針。
    RPiはリソースが限られ、/tmpがtmpfsで容量制限があることも
    実際に踏み抜いて確認済み)
Mac mini役の機体(slate.local)
  → SSH経由でRPiのreadsb出力を定期取得し、GeoJSONへ変換、
    GitHub Pagesへpush(kikimimiのsync-segments.sh / publish-live-data.sh
    と同じパターンを想定)
開発用のこのMac
  → コード開発・gitコミット
```

### 可視化はMapLibre GL JSを推奨

検討の結果、経緯度・高度・進行方向という今回のデータ構成は、MapLibreが
得意とする組み合わせだと判断した:

- `map.getSource(id).setData(geojson)`でのリアルタイム点群更新
- `icon-rotate`で進行方向に応じた機体アイコンの回転(標準機能)
- `interpolate`expressionで高度に応じた色分け(tar1090・FlightRadar24系の
  Webビューアも基本はこの「2D+高度カラーコーディング」方式で、
  真の3D立体視ではない)

**思ったより面倒になりうる点**(必須ではない、後回しでよい):
- 真の3D(高度を実際の高さとして表示)には、`fill-extrusion`では足りず
  カスタムWebGLレイヤー(Three.js統合等)が要る
- 機体の滑らかな移動アニメーションは自動ではないので、
  `requestAnimationFrame`での自前補間が要る

---

## 6. 現時点でのステータス

- [x] コンセプト確立(ADS-B受信・地理空間可視化、kikimimiの姉妹プロジェクト)
- [x] ハードウェア実証(受信・復調・位置特定・機体照会まで一気通貫で確認)
- [x] ゲイン・アンテナの実測による最適化(屋外設置・垂直偏波・7cm・40dB前後)
- [x] 法的・倫理的な整理(ADS-Bは放送に近い性質、軍用機のみ要配慮)
- [x] 可視化方針の検討(MapLibre GL JS)
- [x] `adsb-research.service`を本リポジトリの管理下に移す
  (`scripts/install-adsb-service.sh`、kikimimiのパターンを踏襲)
- [x] `aircraft.json`のライブ更新不具合の原因調査(ifileモードの仮想時計。
  readsbをRTL-SDR対応でビルドして解決)
- [x] 位置データの蓄積(`adsb-logger.service` → `~/adsb-log/*.jsonl`)
- [ ] 受信感度の改善(アンテナ設置位置。夕方に二重窓の間・吸盤取付モードへ
  移行予定。手すり上端より高い位置を推奨)
- [ ] RPi→Mac mini役の機体への定期データ取得スクリプト
  (`sync-adsb-data.sh`的なもの)
- [ ] GeoJSON変換ロジック
- [ ] 軍用機フィルタリングロジック(**公開経路を作る前に必須**)
- [ ] MapLibreでの可視化ページ試作
- [ ] GitHub Pagesでの公開方針の確定(kikimimiのADR 0016と同じパターンを
  想定、ただし本プロジェクト独自のADRとして記録すること)
- [x] ライセンスの確定(CC0 1.0、kikimimiと同じ。2026-09-21確定)

---

## 7. kikimimiとの違い(作業分担の観点)

kikimimiは「LLMが解釈した放送内容」という誤検出リスクを抱えるデータを
扱うため、`documents/decisions/`にあるように、検出条件(lens)の内容確認や
公開する抜粋の内容確認について、稼働前に必ず人がレビューするという
重い作業分担ルールを敷いていた。

kikicomが扱うのは構造化された測位テレメトリ(緯度・経度・高度・速度・
ICAOアドレス)であり、性質が異なる。**軍用機の除外ロジックの設計・
レビューだけは必ず人が確認する範囲とし**、それ以外(GeoJSON変換、
可視化ページの実装等)はkikimimiほど重いレビュー体制を持ち込む必要は
無いと考えている。この整理自体、プロジェクトが進んだ段階で見直してよい。
