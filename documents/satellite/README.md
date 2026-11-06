# 衛星(CubeSat)受信の試験 — 設計

2026-11-05 に方針を決め、P0 を稼働させた。**期間限定の試験**であり、kikicom の本来の
目的(ADS-B の平常時基準線を雪害シーズンに向けて途切れず蓄積する)を置き換えない。

## 位置づけと原則

- **ADS-B の基準線が最優先。** 衛星受信は RTL-SDR を「期限付きで借りる」だけ。既定の状態は常に
  ADS-B 稼働中で、どの失敗でも ADS-B に戻る設計にする。
- 対象はアアルト大学の Foresail-1p(437.125MHz、GMSK 9600bps、CW ビーコンあり)と
  Suomi-100(437.775MHz、GMSK 9600bps、60 秒ごとのビーコン)。AO-73(145.935MHz)は、
  437MHz 用のアンテナでは受けられないので、設定で無効にしてある。
- 受信できるかが分からないので、まず「見えるか」を確かめる。段階は、搬送波・CW ビーコンが
  ウォーターフォールで見える → GMSK のフレームがデコードできる → 受信報告を出す。
- SatNOGS 由来のデータ(録音・それから作った表)は CC BY-SA。CC0 の公開物に混ぜない(CLAUDE.md §4)。
  自前で受信・解読したデータは対象外。公開前に、衛星運営者の希望を確認する。

## 決定事項(2026-11-05)

| # | 決定 | 理由 |
|---|---|---|
| D1 | 置き場所は `scripts/sat/` と `documents/satellite/`。ADS-B 側のファイルは触らない | ハードウェアと調停の仕組みを共有しているので kikicom に同居。育てば姉妹リポジトリへ切り出す |
| D2 | 試験は 2 週間。CW ビーコンの検出に失敗したら、アンテナを戻して基準線を再開する | 損失を、2 週間分の基準線の質に限定する |
| D3 | ADS-B の停止は、合計で 1 日 45 分まで。窓どうしの間隔は 5 分以上 | 基準線への影響を抑える(P0 の予定では 48 時間で約 16 分) |
| D4 | 方式は「貸し出し」。窓の間だけ `adsb-research` を止め、終了時に必ず起動し直す | 見張り役のタイマーで、スケジューラが壊れても ADS-B は戻る |
| D5 | パス予測は RPi で行う | slate が止まっていても、予定と実行が RPi 単独で動く |
| D6 | 窓の記録を、ADS-B の欠測として基準線の計算から除外する | 窓の間の受信ゼロを、受信率の低下と誤記録しない |

## 構成

```
slate(開発)          RPi(実行)
  scripts/sat/*  ──install──▶  /usr/local/lib/kikicom/sat-plan.py
                              ├ sat-plan.timer(6 時間ごと)→ ~/sat/schedule.json
                              └ (P2)sat-scheduler → 窓で ADS-B を一時停止 → 受信 → 再開
  ◀── rsync ──  ~/sat/ (予定・窓の記録・パスごとの結果)
```

- 実際のユニットの関係(2026-11-05 確認): `adsb-logger` は `BindsTo=` と `WantedBy=` で
  `adsb-research` に結び付いている。research を止めれば logger も止まり、research を起動すれば
  logger も起動する。systemd は 257 で、`OnSuccess=`/`OnFailure=` が使える。

## 段階

| 段階 | 内容 | ADS-B への影響 | 状態 |
|---|---|---|---|
| P0 | 予定表を作るだけ(ドライラン)。「止めるはずだった窓」を `schedule.json` に残す | なし | **稼働中(2026-11-05 23:31〜)** |
| P1 | 1 回だけ手動で窓を実行(見張り役付き) | 10 分程度 | **準備済み**(2026-11-06)。1 回目は 2026-11-07 09:14 の Suomi-100(承認済み) |
| P2 | 自動化(スケジューラ、欠測の記録、IQ の録音とデコード) | 窓の分だけ | 未着手 |
| P3 | 結果の解析、ダッシュボードへの表示 | なし | 未着手 |

### P0 の運用

```bash
KIKICOM_RPI_HOST=<RPi の ssh 名> ./scripts/install-sat-service.sh install    # 導入・更新
KIKICOM_RPI_HOST=<RPi の ssh 名> ./scripts/install-sat-service.sh status     # 予定の確認
KIKICOM_RPI_HOST=<RPi の ssh 名> ./scripts/install-sat-service.sh uninstall  # ユニットとスクリプトを削除
```

- 観測点の正確な位置は、RPi の `~/sat/location.json`(権限 600)にだけ置く。リポジトリには入れない。
- `scripts/sat/config.json` が設定の正本。インストールで RPi の `~/sat/config.json` に上書きされる。
  - `mask`: 方位ごとの最低仰角(`方位下限-方位上限:最低仰角`)。**90〜200° 以外は仮定**(下記)。
  - `min_max_el` / `min_usable_s` / `min_usable_el`: 選ぶパスの条件。
  - `window_pad_s`: 開口に入る前後の余裕(30 秒)。
  - `daily_cap_min` / `min_gap_min`: ADS-B の停止の予算(D3)。
- 出力は `~/sat/schedule.json`(UTC)と `schedule.tsv`(JST の要約)、`plan-history.jsonl`。

### P1(手動 1 回)の運用

```bash
export KIKICOM_RPI_HOST=<RPi の ssh 名>
./scripts/sat/arm-window.sh arm SUOMI-100 437.775 "2026-11-07 09:13:40" 285 40.2   # 待機をセット
./scripts/sat/arm-window.sh status                                               # 確認
./scripts/sat/arm-window.sh disarm                                               # 取り消し
```

- `arm` は、RPi に `sat-window.sh` と `iq-analyze.py` を置き、systemd の一時タイマー 2 本を作る。
  `kikicom-sat-window-*` が開始時刻に `sat-window.sh` を動かし(`adsb-research` を止めて `rtl_sdr` で IQ を録り、
  終了時に必ず起動し直す)、`kikicom-sat-guard-*` が終了の 90 秒後に、何があっても `adsb-research` を起動する(D4)。
- 出力は RPi の `~/sat/iq/<名前>-<UTC 時刻>.u8`(rtl_sdr の 8 ビット IQ)と `.json`。ADS-B が止まっていた時刻は
  `~/sat/windows.jsonl` に残る(D6: 基準線の計算から除外する)。
- 録音のあとの解析は RPi で行う(ADS-B に影響しない。`nice` を付ける)。

```bash
~/kikicom-sat/mamba/envs/sat/bin/python /usr/local/lib/kikicom/iq-analyze.py ~/sat/iq/<名前>.u8 --norad 43804
MAMBA_ROOT_PREFIX=~/satnogs-test/mamba ~/satnogs-test/bin/micromamba run -n gr \
  gr_satellites "Suomi 100" --rawfile ~/sat/iq/<名前>.dc.cf32 --iq --samp_rate 250000
```

`iq-analyze.py` は、TLE から予測したドップラー(接近中は受信周波数が高く、遠ざかると低い)を IQ から取り除いた
`.dc.cf32` を作る。あわせて、予測した周波数の 12 kHz 帯域の電力を、両側 15〜40 kHz の参照帯域と 100 ms ごとに比べて、
短いバーストの有無を表にする(ビーコンは約 60 秒周期なので、間隔が揃っているかが決め手)。

**パイプラインの検証(2026-11-06、合成データ)。** SatNOGS の Suomi-100 の録音(FM 復調後の音声)を、実際のパスの
ドップラーに合わせた搬送波に FM 変調し直し、雑音と 8 ビット量子化を加えて、`rtl_sdr` と同じ形式の IQ を作った
(`scripts/sat/make-test-iq.py`)。この IQ で、ドップラー補正・形式・時刻合わせを通して、gr-satellites が
パケットをデコードできることを確認した。

| 検証 | 結果 |
|---|---|
| ドップラーの符号 | 接近中は +5.4 kHz から、遠ざかると -8.4 kHz。補正後の平均周波数は 0 Hz 付近(±数 Hz) |
| デコード(12 kHz 帯域の SNR) | 30 dB で 4/4 パケット、24 dB で 3/4、20 dB で 1/4、16 dB 以下は 0 |
| バースト検出(0.15 秒を 30 秒おき) | SNR 0 dB で全バーストを予定時刻に 13〜16σ、-6 dB でも多くが 4〜5σ |

合成なので、デコードの SNR の下限は目安にすぎない(再変調は本物の GMSK より劣る)。ただし、**デコードにはかなり高い
SNR が要り、1 本のホイップでの見積もり(0〜5 dB)では届かない。「見える」(バースト検出)の方がずっと低い SNR で
成立する**という関係は動かない。1 回目の目標は、デコードではなく「見える」を確かめること。

## 未決・未検証

1. **視野マスクは仮定を含む。** 実際に指定された開口は南東(90〜200°)だけ。西〜北西は 45°、
   北東は 60° 以上で見えると仮定した。アンテナの置き場所が決まったら、実測で直す。
2. **アンテナ。** いまのロッドは 1090MHz 用の 7cm。437MHz には 約 17cm(1/4 波長)が要る。
   17cm は 1090MHz では約 0.6 波長で、ADS-B にもある程度使える見込み(要実測)。
   垂直のアンテナは真上に感度の穴があり、CubeSat の高仰角パスには不利。斜め 45° が折衷案(要試験)。
   アンテナを替えたら `documents/antenna-placements.tsv` に記録する(基準線がそこで不連続になる)。
3. **屋外化(検討中)。** 壁に最近空いたエアコン用の穴を使い、アンテナを屋外へ出す案。
   確認すること: 穴の向き(南東の開口か)、同軸を通す隙間と再シール、集合住宅の規約(ベランダは共用部の
   場合がある)、同軸の長さと損失、LNA の置き場所(アンテナ直下)。
4. **冬の強風・雪・氷への対策(検討中)。** 伸縮ロッドは強風で曲がる・折れる。着雪・着氷で同調がずれる。
   案: 17cm の短い素子を剛性のある棒(真鍮・ステンレス)で作る、塩ビ管のレドームで覆う(雪と風を避ける、
   端に水抜き穴)、軒下に固定する、同軸にドリップループとコネクタの防水処理、落下防止ワイヤー、
   嵐の日は取り込める着脱式の取り付け。静電気・雷対策(同軸の接地、避雷器)も要る。
5. **gr-satellites に IQ をどう渡すか。** `rtl_sdr` の出力は 8 ビットの IQ。形式の変換が要るかを試す。
   ドップラー補正は、録音後に skyfield の計算でずれを IQ に反映する案。
6. **Foresail-1p の CW ビーコンの周波数と周期。** 仕様書(SGICD)に当たる必要がある(未取得)。
7. P1 以降の `OnSuccess=`/`OnFailure=` による復帰と、見張り役のタイマーの実装。

## 関連

- 2026-11-03 の調査: RPi に gr-satellites を導入して、SatNOGS の録音から Foresail-1p(7 フレーム)と
  Suomi-100(4 パケット)をデコードできた(陽性対照)。デコードの結果は SatNOGS 由来の録音を使うため、
  リポジトリには入れていない。
