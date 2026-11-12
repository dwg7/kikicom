# aalto-sats

> アアルト大学(Aalto University、フィンランド)の衛星 — Aalto-1、Aalto-2、Suomi 100、Foresail-1、Foresail-1p(Foresail-1 Prime)、そして次世代の Aalto-3、Foresail-2 — についての基礎知識を、人とAIが時間をかけて醸す miso のインスタンス。
>
> 目的は、437 MHz 帯の受信試験(kikicom `documents/satellite/`)を、衛星の側の事情から支えること。公式資料の再録ではない。

---

# /system-record/instance

- name: aalto-sats
- language: Japanese
- version: 0.1(初版。2026-11-07)
- concept-version: dwg7/miso `CONCEPT.md` のコミット 2ce1553(2026-11-07)
- 実行環境の型: コードエージェント型(ファイルが正本。§4.1)。チャット型で使うときは `examples/agent-contract-template.md` の規則を足す
- 置き場所: kikicom リポジトリの `miso/aalto-sats.md`。育てば dwg7/miso の例へ移してよい
- 構成するファイル: この 1 ファイルのみ
- ライセンス: CC0 1.0(kikicom に従う)。出典の本文は転載せず、言い換えと出所の記録にとどめる。**SatNOGS(Network・DB とも CC BY-SA)の内容は取り込まない**(観測 ID の参照だけ)

## 範囲

- アアルト大学の衛星について、**受信する側が知っておくべき基礎**: 何という衛星か、いつ打ち上げられ、今どうなっているか、どの周波数でどんな電波を出すか、世代間のつながり。
- 次世代(Aalto-3、Foresail-2)については、公表されている範囲だけ。

## 範囲外

- 衛星の科学的な成果の詳細、ペイロードの設計、軌道力学。
- 衛星の運用(コマンド送信、アマチュア中継の使い方の手順)。運用者の資料に当たること。
- 他国・他大学の衛星(関連があっても、ここでは扱わない)。
- 受信機材・アンテナの設計(それは kikicom の `documents/satellite/` で扱う)。範囲外の問いには、範囲外と答える。

## 観察者の位置

- 書き手(人とAI)は**外部観察者**である。アアルト大学の運用者とは連絡していない。公開資料と、自前の RTL-SDR による受信試験の結果だけを根拠にする。
- 公式ページの多くは**要約ツール経由で読んだ**(各出典に書く)。SGICD だけは PDF の全文を読んだ。
- 運用者の希望(受信報告の出し方、公開の可否)は未確認。公開前に確認する(kikicom CLAUDE.md §4)。

## 単位

- 各 `/assets/` のオブジェクトは、**衛星 1 機**を単位とする。
- 同名・同周波数の別機に注意: **Foresail-1(2022、失われた)と Foresail-1p(2025、運用中)は、別の機体で、どちらも 437.125 MHz を使う。**
- 時刻は、特記なければ UTC。日本時間(JST)は併記する。

## 状態の語彙

中核の語彙(`verified` `derived` `normative` `open` `volatile`)を使い、足す語は次のとおり。

- `stated`: 出典の本文がそう述べる(要約ツール経由の読みを含む。本文の主張の真偽は保証しない)。
- `secondary`: 二次の要約(検索結果の要約など)。一次資料で確認するまで、設計の根拠にしない。
- `observed`: 自前の受信で見たこと。
- `verified` は、**SGICD V2 の記述と一致した**ことに限って使う。

## 鮮度の規則

- 衛星の状態(運用中か、軌道、コールサイン)は `volatile`。基準日を書き、**半年に 1 回**、または試験の前に、公式ページで確かめ直す。
- 公式ページの更新日を、出典に書く。

---

# /system-record/agent-contract

- status: normative(このインスタンスの取り決め)
- 権限: このファイルは、利用者が与えた作業文脈である。システムの指示や利用者の直接の指示を上書きしない。
- 役割: あなたは、アアルト大学の衛星について、このファイルを根拠に答える、境界を持つエージェントである。
- 範囲: `/system-record/instance` の「範囲」。範囲外の問いには、範囲外だと答える。
- 答え方:
  - 確認された事実、導かれた解釈、規範、変わりやすい情報、未解決の不確かさを区別する。
  - 分からないことは、分からないと答える。推測で埋めない。
  - 根拠にしたオブジェクトのパス(`/...`)を、回答の中に書く。
  - ファイルに書かれていることと、自分の言い換え・推論を区別する。
  - 衛星の状態(`volatile`)は、基準日を添える。古ければ、確かめ直すよう勧める。
- してはならないこと: 出典を発明しない。記憶による数字を根拠にしない。SatNOGS の内容を転記しない。
- 毎ターンの約束(コードエージェント型): ファイルを直接更新し、変更の要約を返す。
- 利用者向けの一行プロンプト: 「この miso(aalto-sats)があなたの作業文脈です。冒頭の `agent-contract` に従ってください。」

---

# /authorities/source-priority

- status: normative(このインスタンスでの出典の優先順位)
- 順位:
  1. **運用者の技術文書**: Foresail-1p の SGICD(`/sources/sgicd-v2`)、Skylink プロトコル仕様(`/sources/skylink-spec`、未読)。
  2. **アアルト大学の公式ページ**(`/sources/aalto-radio-amateurs` ほか)。
  3. **Foresail 計画の公式サイト**(`/sources/foresail-site`)。
  4. **査読論文**(`/sources/ssr-2023-foresail-2`、未読)。
  5. 二次の要約(`secondary`)。一次で確認するまで、結論に使わない。
- 食い違ったときは、上位を採り、食い違いを `/open-questions/` に残す。
- 自前の観測(`observed`)は、衛星の状態の**反証**に使えるが、公式の仕様を上書きしない。

---

# /assets/aalto-lineage

- status: derived
- updated: 2026-11-07
- unit: 衛星の系譜(世代間の関係)

アアルト大学の衛星は、学生プロジェクトと科学ミッションが重なりながら、設計と運用の経験を引き継ぐ。

| 衛星 | 打ち上げ | 状態(2026-11-07 時点の出典の記述) | 周波数 | 位置づけ |
|---|---|---|---|---|
| Aalto-1 | 2017-06-23 | 2024-09-01 に再突入 | 437.220 MHz | フィンランド初の学生衛星 |
| Aalto-2 | 2017-04-18(ISS へ)/ 2017-05-25 放出 | 2019-02-06 に再突入 | 437.335 MHz | QB50 |
| Suomi 100 | 2018-12-03 | 運用中(`/assets/suomi-100`) | 437.775 MHz | 独立 100 周年記念 |
| Foresail-1 | 2022-05-26 | 交信が途絶(2022-06) | 437.125 MHz | 科学衛星の第 1 号 |
| **Foresail-1p** | 2025-11-28 | 運用中・立上げ中 | 437.125 MHz | Foresail-1 の後継 |
| Aalto-3 | 未公表 | 開発中 | S バンド無線を検証(周波数は未公表) | 次世代の学生衛星 |
| Foresail-2 | 未公表 | 構想 | 未公表 | 放射線帯の観測 |

- **系譜の読み方(derived)**: Aalto-3 の公式ページは、Aalto-1、Aalto-2、Foresail-1/Prime の遺産を引き継ぎ、アビオニクス構成をさらに標準化する、と述べる(`/sources/aalto-3-page`)。Foresail-1p の SGICD は、無線基板の既知の不具合が「Aalto-3 と今後の計画で直される」と述べる(`/sources/sgicd-v2`)。すなわち、**Foresail-1/1p の通信方式(Skylink)は、Aalto-3 以降へ引き継がれる前提**で読める。
- 周波数が 437 MHz 帯に並ぶのは、70 cm のアマチュア衛星帯を使うため(`/assets/foresail-1p`)。**1 台の 437 MHz 受信機で、複数世代を受けられる**(derived)。

---

# /assets/aalto-1

- status: stated
- updated: 2026-11-07
- freshness: 終了した計画。変わらない
- unit: 衛星 1 機(終了)

- フィンランド初の学生衛星。質量 4 kg。2010 年初めに、宇宙技術の講義の中の実現可能性調査として始まった。(`/sources/aalto-1-page`)
- 打ち上げ: 2017-06-23(インドから)。無線ページは 03:59 GMT と書く。(`/sources/aalto-1-page`、`/sources/aalto-radio-amateurs`)
- ペイロード: ハイパースペクトル撮像装置 AaSI(VTT 製)、放射線モニタ RADMON、実験的な軌道離脱装置(プラズマブレーキ。気象研究所 FMI が設計)。
- 無線: 437.220 MHz、帯域 13 kHz、最大 1.2 W、GFSK(偏移 3 kHz)。180 秒ごとに 6 秒の CW ビーコンと、それに続く AX.25 のデータメッセージ。
- 終了: 2024-09-01 に予定どおり再突入し、7 年のミッションを終えた。
- 3U、ほぼ 500 km の太陽同期軌道、PSLV での打ち上げは、検索結果の要約にあるだけ(`secondary`。`/open-questions/aalto-1-form`)。

---

# /assets/aalto-2

- status: stated
- updated: 2026-11-07
- freshness: 終了した計画。変わらない
- unit: 衛星 1 機(終了)

- 2U の CubeSat。QB50 の大気観測ミッションのために作られた。ペイロードはオスロ大学の複数針ラングミュア・プローブ(MnLP)。(`/sources/aalto-2-page`)
- アトラス V ロケットのシグナス補給機で ISS へ(2017-04-18)、2017-05-25 に放出、**2019-02-06 に再突入**。
- 無線: コールサイン ON01FI、中心周波数 437.335 MHz、最大 1.2 W、60 秒ごとに「AALTO2」を含む CW ビーコン。(`/sources/aalto-radio-amateurs`。このページの打ち上げ日の書き方は乱れている。`/open-questions/radio-page-glitches`)

---

# /assets/suomi-100

- status: stated(仕様)/ observed(2026-11 に信号を確認)
- updated: 2026-11-07
- freshness: 運用状態は `volatile`。試験の前に SatNOGS などで直近の観測を確かめる
- unit: 衛星 1 機(運用中)

**基礎**

- 1U の CubeSat。アアルト大学の 3 機目の宇宙の CubeSat。フィンランド独立 100 周年(2017)にちなむ名前。極軌道。(`/sources/suomi100-page`)
- 目的: 宇宙天気、特にオーロラの研究。
- ペイロード: 可視光カメラと、アアルト大学で設計・製作した **MF/HF 帯の電波観測装置**(アアルトで設計・製作した最初の CubeSat 計器)。
- 打ち上げ: 2018-12-03、ファルコン 9。(`/sources/aalto-radio-amateurs`。Suomi100 のページは打ち上げ機を書かない)
- チーム: 責任者 Esa Kallio 教授ほか。資金は「フィンランド 100 年」とマグヌス・エーロンルート財団。

**無線(要点)**

- 周波数 **437.775 MHz**、帯域 14.4 kHz、最大 +30 dBm(約 1 W)。
- GMSK、偏移 4.8 kHz、**9600 bit/s**。
- **60 秒ごとのビーコン**(電力・無線・搭載計算機の基本テレメトリ)。
- TLE のカタログ名: SUOMI100。NORAD 番号 43804(kikicom の記録による)。
- ドップラー: 437 MHz 帯で、通過中に約 ±10 kHz 動く(derived。`/interpretations/doppler-at-437`)。

**ビーコンの構造(観測。gr-satellites の `suomi100` テレメトリ定義で解釈した結果の項目名)**

- gr-satellites の設定では、**FSK 9600 baud、偏移 2400 Hz、フレームは AX100 の ASM+Golay**(`Suomi_100.yml`)。
- 中身は **CSP パケット**。ヘッダー(優先度・送信元・宛先・宛先ポート・送信元ポート・分割・HMAC・XTEA・RDP・CRC)のあとに、ビーコンの種類と、次の 3 つの系統の項目が入る。
  - **eps(電源)**: 太陽電池の電圧と電流、バッテリー電圧と入出力電流、各出力の電流、温度、バッテリーのモード
  - **com(無線)**: 温度、**RSSI**、周波数誤差、背景雑音の RSSI
  - **obc(搭載計算機)**: 電流、温度、電源の状態、ソフトウェアのカウント、ファイルシステム、**起動回数と起動原因**、時計
- 2026-11-03 の SatNOGS 録音からのデコード 4 パケットで確認した(`/traces/2026-11-03-positive-control`)。値は取り込まない(録音は CC BY-SA)。項目名は gr-satellites の定義による。
- 含意: **com の RSSI と周波数誤差は、衛星側が測った上り(地上局からの電波)の値**で、下りの強さではない(derived。要確認: `/open-questions/suomi-100-telemetry`)。

**状態**

- 無線ページ(2026-07-15 更新)は、運用中の衛星に分類する。(`stated`)
- 2026-11-03 09:56:40 UTC に、他の局が受けた録音(SatNOGS 観測 15352006、最大仰角 89°)から、gr-satellites が 4 パケットをデコードできた。**この時点で信号を出していた**ことの裏づけ。(`observed`。録音そのものは CC BY-SA のため取り込まない)
- Suomi100 の公式ページは 2020-07-01 の更新で止まり、現況を書かない。(`/open-questions/suomi-100-telemetry`)

---

# /assets/foresail-1

- status: stated
- updated: 2026-11-07
- freshness: 失われた機体。再突入日は未確認(`/open-questions/foresail-1-decay`)
- unit: 衛星 1 機(交信途絶)

- アアルト大学の宇宙科学・技術の卓越拠点が作った、最初の科学衛星。ペイロードは、トゥルク大学の粒子望遠鏡 PATE(電子 80〜1600 keV、陽子 8〜30 MeV)と、気象研究所 FMI の静電プラズマブレーキ。(`/sources/foresail-1-page`)
- 打ち上げ: 2022-05-26。当初は正常に交信できた。
- **2022 年 6 月、送信機の再設定のあと、突然交信が途絶えた。**バックアップ系を起こす試みは実らず、2022-11-04 の記事は「おそらく永久に失われた」と述べる。原因は公式に述べられていない。(`/sources/foresail-1-loss-news`、`/sources/foresail-1-page`)
- 後継機は、改良した電源系と誤り回復の仕組みを持ち、これまでの開発品と飛行予備品から素早く組み立てる、とされた。→ `/assets/foresail-1p`
- 無線: 437.125 MHz、最大 1.2 W。**Foresail-1p と同じコールサイン(OH2FS1)・同じ周波数**を無線ページに載せる。

---

# /assets/foresail-1p

- status: stated(概要)/ verified(無線仕様。SGICD V2 と一致)/ volatile(状態)
- updated: 2026-11-07
- freshness: 立上げ中。状態は試験の前に確かめる
- unit: 衛星 1 機(運用中・立上げ中)。**Foresail-1(2022)とは別の機体**

**基礎**

- 名前: Foresail-1p。TLE の名前は「Foresail-1 Prime」。コールサイン **OH2F1S**。NORAD **66778**、国際識別符号 25276DS。(`/sources/foresail-site`、`/sources/sgicd-v2`)
- **3U の CubeSat**。Foresail-1 の後継で、同じ主ペイロード(PATE、プラズマブレーキ)を持つ。(`/sources/foresail-site`、`/sources/sgicd-v2`)
- ペイロード: PATE(トゥルク大学)、静電プラズマブレーキ(FMI。約 60 m のアルミのテザー)、MATTI 磁力計(アアルト大学製。PATE を補い、市販部品の限界を試す)、運用監視用の追加カメラ。(`/sources/foresail-site`)
- 打ち上げ: **2025-11-28、スペース X の Transporter-15**(ヴァンデンバーグ)。D-Orbit の ION 宇宙輸送機から、**2025-12-09 に放出**。太陽同期軌道、高度約 520 km。(`/sources/aalto-radio-amateurs`、`/sources/foresail-1p-page`、`/sources/foresail-site`)
- 改良: 電源系の強化と、より頑健な誤り回復。
- 状態: 展開は成功し、**立上げ(commissioning)中**。(`/sources/foresail-site`。Aalto のページには「作っている」と「打ち上げた」が混在する。`/open-questions/radio-page-glitches`)

**無線(SGICD V2 の記述。`verified`)**

| 項目 | 値 |
|---|---|
| 周波数 | 437.125 MHz(ドップラー ±10 kHz) |
| 帯域 | 20 kHz |
| 変調 | GMSK |
| シンボルレート | 9600(標準)。4800、19200、38400 もある |
| 出力 | 1.3 W |
| 偏波 | **円偏波**(旋回の向きは姿勢次第)。任意の直線偏波で受けると 3 dB 弱く、フェージングは最小 |
| フレーム | Skylink PHY(GOMspace Mode 5 互換): プリアンブル 0xAA×6、同期語 0x1ACFFC1D、Golay-24 の長さ欄、RS(255,223) |
| 方式 | 窓つきの時分割複信(TDD) |
| 周波数の調整 | フィンランドのアマチュア無線界と IARU に調整し、ITU が受理(SGICD の記述) |

- **ビーコン**: 平均 60 秒おきに、マルチフレームのビーコンを送る。内容は OBC・EPS・ADCS・UHF のハウスキーピング(VC1)。打ち上げ直後は展開(Deployment)の情報も。アマチュア中継のビーコンは VC3。
**Skylink 仕様(2026-02-26 版、29 ページ。`/sources/skylink-spec`)の要点**

- 変調: 2 値 GFSK(変調指数 0.5、BT 積 0.5)。GMSK として受けると感度が上がる。トランシーバのチップで GMSK を作るときは、**偏移をシンボルレートの 1/4(9.6 kbps なら 2.4 kHz)にする**。低い周波数が「0」、高い周波数が「1」。
- シンボルレート: 上り・下りとも 9600、19200、38400。仕様は、**9600 は古いアマチュア FM 無線機で音声として受けられるための遺産**で、今後は広帯域の SDR での受信を前提にする、と述べる。
- フレームの時間(9600 の場合): **最短 40 ms(データ 11 バイト)、最長 220 ms(データ 223 バイト)**。19200 ではその半分、38400 では 4 分の 1。
- フレームの構成: プリアンブル(0xAA を 6 バイト以上。9600 で約 5 ms)、同期語、Golay(24,12)の長さ欄、データ(最大 223 バイト)、RS のパリティ 32 バイト。データは **CCSDS の疑似乱数(x⁸+x⁷+x⁵+x³+1)で白色化**する(DC の偏りを消し、ビット同期を保つため)。
- 仮想チャネル(VC): VC0 が指令、**VC1 が大量データ(ハウスキーピングのビーコンと、予定された下り)**、VC2 がサービス、VC3 がアマチュア中継。
- 仕様は、**同じ「プリアンブル―同期語―長さ―データ」の枠を Aalto-1 と Suomi 100 も使う**と述べる(同じ系統の枠。derived: `/interpretations/why-two-sats-are-alike`)。
- MAC: 窓つきの時分割複信。最小のフレームは約 20 ms を扱い、時間の分解能は 1 ms。
- **検出器への含意(derived。2026-11-08 に訂正)**: 1 つのビーコンは、40〜220 ms のフレームが続く**複数フレームの塊**になる(実測は `/traces/2026-11-08-satnogs-sync-scan`)。当初は「窓を 40〜50 ms に縮める」と考えたが、実測では塊の全長が約 0.4〜1.3 秒あるので、**ビーコンの長さに合わせて長く積分する**ほうが得で、さらに**周期(約 60 秒)で畳み込む**のが決め手になる。

- **アマチュア中継(VC3)**: AX.25 のパケットを中継する。受け付ける宛先は OH2F1S、APRS、ALL*、BEACON、CQ*。中継のアドレスは OH2F1S-11。主局は OH2AGS(オタニエミ)。**無線基板の符号に既知の不具合があり、Aalto-3 と今後の計画で直される**(SGICD が引く Skylink の README)。
- **ダウンリンク専用のファイル転送モード**: 第三者の地上局でも受けられるよう設計されている(アマチュア網でダウンリンクを増やすため)。
- **CW ビーコン**: Aalto の無線ページは「CW ビーコンあり」と述べるが、**SGICD に CW の記述はない**。→ `/open-questions/foresail-1p-cw`

**自前の観測**

- 2026-10-24 21:27:57 UTC に、他の局が受けた録音(SatNOGS 観測 15286538、最大仰角 78°)から 7 フレームをデコードできた。信号は出ている。(`observed`)
- 自前の RTL-SDR での試験は `/traces/` を参照。

---

# /assets/aalto-3

- status: stated
- updated: 2026-11-07
- freshness: `volatile`。打ち上げ日・周波数が公表されたら更新する
- unit: 衛星 1 機(開発中)

- アアルト大学の **6 機目の衛星**で、**次世代の学生プロジェクト**。参入の壁を下げ、将来の学生ミッションの標準的な枠組みを作ることを狙う。1U の CubeSat。(`/sources/aalto-3-page`)
- 目的: アアルトで作った **S バンド無線**サブシステムの検証、GNSS 機能の実証、二重の放射線影響の測定、地球の撮像。
- 遺産: Aalto-1、Aalto-2、Foresail-1/Prime。アビオニクスの構成をさらに標準化する。
- 責任者: Jaan Praks 教授。
- 無線: コールサインは **OH2A3S(TBC。未確定)**。詳細は TBD で、変わりうると注記されている。(`/sources/aalto-radio-amateurs`)
- **打ち上げ日、現況、周波数は公表されていない。**(`/open-questions/aalto-3-radio`)

---

# /assets/foresail-2

- status: stated
- updated: 2026-11-07
- freshness: `volatile`
- unit: ミッション構想

- 地球の磁気圏の**放射線帯**と宇宙天気を調べる計画。アアルト大学のページは「衛星ミッションの構想」と呼ぶ。市販部品を基にした CubeSat で、放射線の強い領域を飛ぶのが課題。COSPAR の CORBES 計画の一部。(`/sources/foresail-2-page`)
- 測るもの: 高エネルギー粒子のフラックス、磁場の超低周波波動、磁気圏のプラズマ環境。
- 無線: コールサインは **OH2FS2(TBC)**。詳細は TBD。(`/sources/aalto-radio-amateurs`)
- 設計論文: Slavinskis and Praks, *Space Science Reviews* (2023), DOI 10.1007/s11214-023-01012-7。(`/sources/ssr-2023-foresail-2`、未読)
- 6U・静止トランスファー軌道(GTO)という記述は検索結果の要約にあるが、アアルトの公式ページにはない。→ `/open-questions/foresail-2-orbit`

---

# /procedures/identify-and-receive

- status: derived
- updated: 2026-11-07
- 用途: 現在受けられる 2 機を、437 MHz 帯の 1 台の受信機で狙うときの要点

| | Suomi 100 | Foresail-1p |
|---|---|---|
| 周波数 | 437.775 MHz | 437.125 MHz |
| 変調・速度 | GMSK 9600 bit/s | GMSK 9600 sps(標準) |
| 帯域 | 14.4 kHz | 20 kHz |
| ビーコン | 60 秒おき(基本テレメトリ) | 平均 60 秒おき(マルチフレーム) |
| 偏波 | 未確認 | 円偏波(直線で 3 dB 損) |
| TLE の名前 | SUOMI100(NORAD 43804) | Foresail-1 Prime(NORAD 66778) |
| gr-satellites の名前 | `Suomi 100` | `FORESAIL-1P`(枠は Skylink 系の `FORESAIL-1`。テレメトリの解釈は未実装。`/open-questions/grsat-name-fs1p`) |

- 2 機の周波数の差は 650 kHz。20 kHz の帯域に対して離れているので、**同時には受けられない**が、中心周波数を替えれば 1 台で受けられる(derived)。
- 受信機は、通過ごとのドップラー(±約 10 kHz)を補正する必要がある(`/interpretations/doppler-at-437`)。
- 検出の狙いは**約 60 秒おきの短いバースト**(両機に共通)。連続した搬送波や CW には頼らない(`/open-questions/foresail-1p-cw`)。
- 運用者は、受信報告の出し方を公開していない。**第三者局の受信を、運用者が想定している**(SGICD の目的の記述)が、報告の窓口は未確認。

---

# /interpretations/doppler-at-437

- status: derived
- 受信周波数のずれは、衛星が近づくとき高く、遠ざかるとき低い。ずれ = −f × (距離の変化率) / c。
- 437 MHz で、低軌道の衛星の通過中の最大は約 ±10 kHz。SGICD も ±10 kHz と述べ、kikicom で TLE から計算した値(+10.1 kHz → −8.7 kHz、Foresail-1p、2026-11-07 21:31〜)と整合する。
- 1090 MHz の ADS-B と違い、**周波数が一定ではない**ので、固定の周波数のフィルタでは、通過の途中で帯域から外れうる。

---

# /interpretations/why-two-sats-are-alike

- status: derived
- Suomi 100(2018)と Foresail-1p(2025)は、世代も用途も違うが、**437 MHz 帯・GMSK・9600・約 60 秒おきのビーコン**という点で、受信者にとって似ている。
- 理由の推測: アアルト大学の衛星は、70 cm のアマチュア衛星帯を使い、学生・アマチュアが受けやすい、地上局を共通にしやすい、という設計の傾向を共有しているのだろう(推測。出典は述べていない)。
- 受け取り方の含意: 一方で作った受信・解析の道具は、もう一方にそのまま使える(kikicom の `scripts/sat/` はその前提で作った)。Aalto-3 が S バンドを使うなら、**この共通性は途切れる**可能性がある(`/open-questions/aalto-3-radio`)。

---

# /traces/2026-11-03-positive-control

- kind: 運用の踏み跡
- status: observed
- 2026-11-03、RPi に gr-satellites を導入し、SatNOGS の公開録音(Suomi 100: 観測 15352006、Foresail-1p: 観測 15286538 など)から、Foresail-1p の 7 フレーム、Suomi 100 の 4 パケットをデコードできた。→ **デコーダと、2 機が信号を出していることの陽性対照**になった。
- 録音と、そこから作った表は CC BY-SA。ここには入れない。観測 ID だけを記す。

---

# /traces/2026-11-08-satnogs-sync-scan

- kind: 運用の踏み跡
- status: observed(ビーコンのタイミング)/ derived(解釈)
- 方法: SatNOGS の公開音声(FM 復調後)を、2 衛星で各 36 本取得した(最大仰角 4 帯 × 局が偏らないよう選択。取得は承認済み、約 275 MB、slate のリポジトリ外)。プリアンブル(0xAA)+同期語 0x1ACFFC1D の相関で、フレームの先頭を探した(`sync_scan.py`)。
- **偏りの注意**: 観測は SatNOGS が「信号が見えた(good)」と判定したものだけ。検出できる割合は、実際の受信可能性より高く出る。局の機材も、私たちの受信より良い。
- **偽検出**: 音声を逆再生して(同期語が存在しない状態で)数えると、毎分約 0.2 件の誤検出がある。**単発の同期の検出は信頼しきれない。決め手は、周期的に並ぶこと。**

| | Suomi 100 | Foresail-1p |
|---|---|---|
| ビーコンの間隔(隣り合う塊) | **59.999 s、標準偏差 0.005 s**(n=15。最小 59.99、最大 60.01) | 平均 59.2 s、標準偏差 0.9 s(n=26。57.2〜60.4 s) |
| 1 回のビーコンのフレーム数 | **1**(26 塊すべて) | 3 または 4 が最も多い(33 塊)。1〜2 は弱い検出の取りこぼしと見られる。まれに 5〜11 |
| 塊の長さ(先頭の同期の間隔) | 単発 | 約 0.24〜1.13 s(最後のフレームは別に最大 0.22 s) |
| 60 秒おきの列が見えた観測 | 36 本中 8 本 | 36 本中 20 本 |

- **解釈(derived)**: Suomi 100 のビーコンは、水晶で刻んだようにきっかり 60 秒で、1 フレームだけ。Foresail-1p は平均 60 秒で、1 秒ほどゆらぎ、SGICD の述べる 4 つのハウスキーピング(OBC・EPS・ADCS・UHF)の 4 フレームと合う。
- **仰角との関係**: 列が見えた割合に、仰角への単調な傾向は見えない(Suomi 100: 0〜30° で 4/9、30〜50° で 0/9、50〜70° で 3/9、70〜91° で 1/9。Foresail-1p は 3/9、6/9、6/9、5/9)。標本が小さく、局の機材もばらばらなので、**傾向があるとも、ないとも言えない**。
- Foresail-1p の 1 本(観測 15385816)の最後の約 20 秒に、塊が密に続く区間があった(5〜11 フレーム)。別の運用モード(ファイル転送の下りなど)の可能性があるが、未確認。
- 録音・波形・表は CC BY-SA のため、リポジトリに入れない。
- **この実測を検出器に反映した結果**(合成 IQ。詳細は kikicom の `documents/satellite/README.md`「検出器の改良」): 周期畳み込みで、Foresail-1p 型(0.5 秒×60 秒おき)の検出下限が約 3 dB 良くなった(SNR −6 → −9 dB)。Suomi 100 型(単発 0.15 秒)は 1〜2 dB 程度。**感度の壁を破る改善ではない。**

# /traces/2026-11-08-satnogs-redecode

- kind: 運用の踏み跡
- status: observed
- 方法: 上の 72 本の音声を、RPi の gr-satellites 5.9.0(`Suomi 100` と `FORESAIL-1P`)で再デコードした。SatNOGS 側の復調データ(観測に付く `demoddata`)と比べた。
- **数え方の注意**: `FORESAIL-1P` はテレメトリを解釈しない設定なので、パケットは「-> Packet from」ではなく **「VERBOSE PDU DEBUG PRINT」(16 進ダンプ。先頭に `OH2F1S` のコールサイン)**で出る。最初、「Packet from」を数えて 0 件と誤った(`pdu length` の行を数えるのが正しい)。
- **選び方の偏り**: Foresail-1p は、SatNOGS が復調済みの観測と、未復調の観測を、半々になるよう選んだ。したがって、ファイル単位の割合(36 本中 13 本)は、母集団の割合ではない。

| | Suomi 100(36 本) | Foresail-1p(36 本) |
|---|---|---|
| 1 フレーム以上を得たファイル: 自前 | 26 | 15 |
| 同: SatNOGS 側 | 26 | 13 |
| 両方 / 自前だけ / SatNOGS だけ | 25 / 1 / 1 | 11 / 4 / 2 |
| 総フレーム数: 自前 | 84 | **205** |
| 同: SatNOGS 側 | 99 | 27 |

- **Suomi 100**: 自前のデコーダは SatNOGS 側と同等。
- **Foresail-1p**: ファイル単位では 13 → 15 本と、あまり増えなかったが、**1 回の通過から取れるフレーム数は約 7.6 倍(27 → 205)**。SatNOGS 側が復調データを付けたのは、通過ごとに 1〜数フレームだけ、という状態。
- **母集団への推定(derived。標本が小さい)**: SatNOGS 側で復調データのない 23 本のうち 4 本(約 17%)で、自前のデコーダはフレームを得た。SatNOGS の「信号が見えた」200 件のうち 21 件(約 10%)が復調済みなので、**自前のデコーダなら約 25% 前後(おおよそ 2 倍強)になる見込み**。信頼区間は広い。
- フレームの長さ(バイト): 23(62 件)、197(39)、71(22)、89(19)、112(18)、143(16)、27、35。複数種類のハウスキーピング・フレームが続く構成と整合する(SGICD の OBC・EPS・ADCS・UHF)。長さと種類の対応は未確認。
- 60 秒おきの列が見えた 20 本のうち、自前で復調できたのは 13 本。**信号があっても復調できない通過が 7 本**ある(弱すぎる)。
- 仰角: 自前の復調は 0〜30° で 1/9、30〜50° で 4/9、50〜70° で 4/9、70〜91° で 6/9。低仰角は弱いが、標本が小さい。
- 内容(テレメトリの値)は、録音が CC BY-SA のため取り込まない。ログは RPi の `~/satnogs-test/batch/logs/` にだけ置く。

# /traces/2026-11-08-fs1p-decode

- kind: 運用の踏み跡
- status: observed(復号の成否と整合性)/ derived(バイト順、サブタイプの対応)
- 方法: 上の再デコードで得た Foresail-1p の 205 フレームを、SGICD V2 の表(`/sources/sgicd-v2`)で復号した。道具は `scripts/sat/fs1p-decode.py`。
- 内訳: ハウスキーピング 75(OBC 22・EPS 16・UHF 19・ADCS 18)、ファイル転送 TM(6,13) 39 と開始報告 TM(6,8) 2、ペイロードの無い制御フレーム 69、アマチュア中継 VC3 の AX.25 が 2、未調査(サービス 4・サービス 1)が 18。エラーは 0 件。
- **バイト順**(SGICD に無い): Skylink の seq、PUS ヘッダ、ハウスキーピング先頭の UNIX 時刻、ファイル転送の block index と開始報告の項目はビッグエンディアン。ハウスキーピング本体はリトルエンディアン。
- **整合性の確認**: 稼働時間がビーコンごとに +60 s。ADCS の位置・速度から高度 約 512 km・速度 約 7.6 km/s。バッテリー約 8.0〜8.1 V(公称 6.5〜8.2 V)。降圧回路約 3.7 V。UHF の送信フレーム数が単調増加。
- **食い違い**: 実機は UHF=TM(3,4)・ADCS=TM(3,5)。SGICD は逆(`/open-questions/sgicd-hk-subtype-swap`)。
- **科学ペイロードは復元できない**(`/open-questions/fs1p-science-payload`)。
- 値そのもの(温度・電圧など)は、録音が CC BY-SA のため、ここには書かない。

---

# /traces/2026-11-07-first-windows

- kind: 運用の踏み跡
- status: observed
- 自前の RTL-SDR(垂直ダイポール約 14+14 cm)で、ADS-B を止めて短い窓を録音した。

| 窓(JST) | 衛星 | 最大仰角 | ゲイン | 結果 |
|---|---|---|---|---|
| 2026-11-07 09:13:40〜 | Suomi 100 | 未記載(この表には書いていない) | 40.2 dB | 周期的なバーストなし。デコード 0 件 |
| 2026-11-07 21:31:09〜 | Foresail-1p | 約 67°(21:35 前後) | 48.0 dB | 4σ を超えるフレーム 0。最大 3.7σ |

- **解釈(derived)**: どちらも**否定の確証ではない**。1 回目は、録音のゲインが足りなかった疑いがある(同じ日のゲイン比較で、48〜49.6 dB の方が 1〜2 dB 良かった)。2 回目は最大仰角が高く、垂直ダイポールが最も弱い方向(真上)に近い。円偏波の Foresail-1p は、直線偏波で 3 dB 損する。
- 詳細と手順は kikicom の `documents/satellite/README.md`。

---

# /lessons/check-the-satellite-first

- status: derived
- 根拠: `/assets/foresail-1`、`/traces/2026-11-03-positive-control`
- **受信に失敗したとき、アンテナや受信機を疑う前に、衛星が信号を出しているかを確かめる。**Foresail-1 は、送信機の再設定のあと、突然黙った。衛星は止まりうる。他の局の直近の観測(陽性対照)があれば、衛星は生きていると言える。
- 逆に、直近の他局の観測が見当たらない衛星に対して、自前の受信の失敗を「アンテナのせい」と結論づけない。

# /lessons/same-name-different-spacecraft

- status: derived
- 根拠: `/assets/foresail-1`、`/assets/foresail-1p`
- 同じコールサイン・同じ周波数・似た名前でも、別の機体になりうる。**NORAD 番号で衛星を特定する**(Foresail-1p は 66778)。記事や録音の日付が 2022 年なら Foresail-1、2025 年末以降なら Foresail-1p を指す。

---

# /acceptance-tests/foresail-1p-radio

- query: Foresail-1p を受けるには、何 MHz で、どんな変調・速度に合わせればよいか。偏波は?
- expected: 437.125 MHz、GMSK、9600 sps(標準)、帯域 20 kHz、ドップラー ±10 kHz。円偏波で、直線偏波では 3 dB 損。
- requires: /assets/foresail-1p, /interpretations/doppler-at-437
- result: untested
- freshness: 立上げ中のため、周波数・速度の変更に注意

# /acceptance-tests/foresail-1-vs-1p

- query: Foresail-1 と Foresail-1p は同じ衛星か。今受けられるのはどちらか。
- expected: 別の機体。Foresail-1(2022 打ち上げ)は 2022 年 6 月に交信が途絶。後継の Foresail-1p(2025-11-28 打ち上げ、NORAD 66778)が運用中・立上げ中。どちらも 437.125 MHz。
- requires: /assets/foresail-1, /assets/foresail-1p, /lessons/same-name-different-spacecraft
- result: untested

# /acceptance-tests/suomi-100-alive

- query: Suomi 100 は今も信号を出しているか。何を根拠にそう言えるか。
- expected: 無線ページは運用中に分類する(2026-07-15 更新)。2026-11-03 に他局の録音から 4 パケットをデコードできた。ただし公式の現況報告はなく、出し続けているかは試験の前に確かめる。
- requires: /assets/suomi-100, /traces/2026-11-03-positive-control
- result: untested
- freshness: volatile

# /acceptance-tests/next-generation

- query: 次世代の Aalto シリーズは何か。いつ、どの周波数で受けられるか。
- expected: Aalto-3(6 機目、1U、S バンド無線の検証、コールサイン OH2A3S は TBC)と Foresail-2(放射線帯、構想)。**打ち上げ日と周波数は公表されていない**と答える。
- requires: /assets/aalto-3, /assets/foresail-2, /open-questions/aalto-3-radio
- result: untested
- freshness: volatile

# /acceptance-tests/foresail-1p-cw

- query: Foresail-1p の CW ビーコンの周期と内容は?
- expected: **分からない。** 無線ページは「CW ビーコンあり」と述べるが、SGICD に CW の記述はなく、周期・形式は未公開。60 秒おきの GMSK マルチフレームのビーコンは確かな事実。
- requires: /open-questions/foresail-1p-cw
- result: untested

# /acceptance-tests/out-of-scope-antenna

- query: 私のアンテナで Foresail-1p をデコードするには、何 dB の信号対雑音比が要るか。
- expected: 範囲外(示唆あり)。衛星側の仕様(円偏波の 3 dB 損など)は答えられるが、受信機・アンテナの見積もりは kikicom の `documents/satellite/README.md` を参照するよう案内する。
- requires: /system-record/instance
- result: untested

---

# /inventory/sources-status

- 取り込み済み: SGICD V2(全文)、`/sources/` にある Aalto の公式ページ(要約ツール経由)、foresail.github.io の概要。
- **未取り込み(存在は分かっている)**:
  - FS1p Skylink Protocol Specification(`/sources/skylink-spec`)
  - Foresail-2 の設計論文(`/sources/ssr-2023-foresail-2`)
  - Aalto-1 の設計論文(arXiv 2101.10691)
  - SatNOGS DB の各衛星のページ(CC BY-SA。内容は取り込まず、観測 ID だけを使う)
  - アアルト大学の地上局(OH2AGS)のページ
- 取り込まない理由が**ライセンス**のもの: SatNOGS(上記)。

# /inventory/backlog

優先度 A(受信試験に直結):

- (一部済 2026-11-08)Skylink 仕様の物理層・フレーム・VC を `/assets/foresail-1p` に足した。**データリンク層(HMAC・ARQ)と応用層は未読**。ビーコン各フレームの項目表は、SGICD の第 3 章にある(2026-11-08 に `scripts/sat/fs1p-decode.py` へ取り込み、実フレーム 75 件で検証済み。`/traces/2026-11-08-fs1p-decode`)。
- Suomi 100 のビーコンの形式を、運用者の資料で裏づける(項目名は gr-satellites の定義で判明済み)。
- (済 2026-11-07)gr-satellites での Foresail-1p の名前は `FORESAIL-1P`。`/procedures/identify-and-receive` に書いた。
- SatNOGS の公開音声を再デコードし、ビーコンの長さ・周期を測って、バースト検出に生かす(取得の承認済み。`/traces/`)。

優先度 B:

- Aalto-3 の周波数・打ち上げ日の公表を、半年ごとに確認する。
- Foresail-1 の再突入日を、一次資料で確認する。
- 運用者への連絡(受信報告の窓口、公開の希望)。

優先度 C:

- Foresail-2 の設計論文を読む。
- Aalto-1・Aalto-2 の詳細(終了した計画のため、急がない)。

---

# /open-questions/foresail-1p-cw

- status: open
- Aalto の無線ページは Foresail-1p に「CW ビーコン」があると述べる。SGICD V2(2026-02-23)は、ビーコンを GMSK のマルチフレームとして述べ、CW に触れない。
- 仮説: 古い記述の流用か、打ち上げ直後だけの機能か、SGICD の範囲外の機能。
- 閉じ方: 運用者に尋ねる、または Skylink 仕様か受信記録で確かめる。

# /open-questions/aalto-3-radio

- status: open
- Aalto-3 の周波数、変調、打ち上げ日、地上向けの主な通信が UHF か S バンドか。公開資料にない。S バンドは「アアルトで作った無線の**検証**」と書かれ、主回線かは不明。
- 閉じ方: アアルトの宇宙機ページと無線ページの更新を確かめる。

# /open-questions/foresail-2-orbit

- status: open
- Foresail-2 は 6U・GTO という要約が検索結果にあるが、公式ページは「構想」とだけ述べ、軌道を書かない。
- 閉じ方: 設計論文(DOI 10.1007/s11214-023-01012-7)を読む。

# /open-questions/aalto-1-form

- status: open
- Aalto-1 の「3U」「高度約 500 km の太陽同期軌道」「PSLV」は検索結果の要約にあるだけ(`secondary`)。公式ページは軌道を書かず、打ち上げ機を書かない。
- 閉じ方: 設計論文(arXiv 2101.10691)で確かめる。

# /open-questions/foresail-1-decay

- status: open
- Foresail-1 の再突入日。検索結果に、SatNOGS DB の記載を引いた要約があるが、SatNOGS は CC BY-SA のため取り込まない。
- 閉じ方: 一次の出典(アアルト大学、気象研究所、軌道カタログ)を探す。

# /open-questions/suomi-100-telemetry

- status: open
- Suomi 100 の公式ページ(2020-07-01 更新)は、現況とデータの受け方を書かない。偏波と、運用の継続は不明。
- ビーコンの項目は、gr-satellites の定義で分かった(`/assets/suomi-100`)。**運用者の資料で裏づけたものではない**。com の RSSI が上りの値かも未確認。
- 閉じ方: 運用者の資料を探す。gr-satellites の定義の出典(作者の資料)をたどる。

# /open-questions/radio-page-glitches

- status: open
- Aalto の無線ページに、読み違えうる箇所がある: Aalto-2 の打ち上げ日の書き方が乱れている。Foresail-1(失われた)と Foresail-1p が同じコールサインと周波数で並ぶ。Foresail-1p の出力は無線ページで 1.3 W(31.1 dBm)、SGICD で 1.3 W(32 dBm)と書かれ、dBm が合わない(1.3 W は約 31.1 dBm)。
- Foresail-1p の Aalto のページに「作っている」と「打ち上げた」が混在する。
- 閉じ方: 食い違いを運用者に伝える。当面は、SGICD を優先する(`/authorities/source-priority`)。

# /open-questions/sgicd-hk-subtype-swap

- status: derived(実フレームで確認。運用者への確認は未了)
- SGICD V2 は ADCS を TM(3,4)、UHF を TM(3,5) と書くが、実機のフレームでは **UHF が TM(3,4)(本体 56 B)、ADCS が TM(3,5)(本体 79 B)**。長さと中身(UHF の送受信フレーム数・窓長、ADCS の位置・速度)の両方で裏づけた(`/traces/2026-11-08-fs1p-decode`)。
- 閉じ方: 運用者に伝える。当面、**復号には実機の対応を使う**が、`/authorities/source-priority` の「観測は公式の仕様を上書きしない」に従い、SGICD の記述は書き換えず、食い違いとして両方を残す。

---

# /open-questions/fs1p-science-payload

- status: open
- ファイル転送(サービス 6)で downlink される `/r/*.lz4`(1.4〜2.0 MB、160 B のブロック約 9,000〜12,700 個)が、**科学ペイロード**と見られる。どの観測機器のものか、内部形式はどうかは、SGICD に無い。
- 手元には連続 32 ブロック(0.35%)だけ。LZ4 は先頭から展開するので、途中だけでは中身を読めない。完全な復元(CRC32 で検証できる)には、複数の通過・局のブロックを集める必要がある。
- 閉じ方: 運用者の資料(ファイルの形式)を探す。SatNOGS のコミュニティがブロックを集約しているか確かめる。自前で足りるかは、1 通過で何ブロック取れて、重なりがどれだけあるかによる。

---

# /open-questions/grsat-name-fs1p

- status: derived(2026-11-07 に一部解決。残りは open)
- **解決した部分**: gr-satellites 5.9.0 での名前は `FORESAIL-1P`(`FORESAIL-1P.yml`)。周波数 437.125 MHz、FSK 9600 baud、フレームは `FORESAIL-1`(Skylink 系)。RPi の環境で確認した。
- **残り**: (1) このファイルのテレメトリは `unknown` で、**中身の項目は解釈されない**(フレームを取り出せるだけ)。→ 2026-11-08 に自前で解釈した(`scripts/sat/fs1p-decode.py`、`/traces/2026-11-08-fs1p-decode`)。gr-satellites 側の更新は待たなくてよい。(2) この設定の NORAD 番号は 98467 で、66778 と違う(仮の番号が残っていると見られる。要確認)。TLE の照合に使うときは、66778 を使う。

---

# /sources/sgicd-v2

- id: FS1p Space/Ground Interface Control Document, V2, 2026-02-23(19 ページ、公開文書、責任者 Topi Räty)
- url: https://foresail.github.io/docs/FS1p_Space_Ground_Interface_Control_Sheet.pdf
- retrieved: 2026-11-07
- read: PDF の全文を読んだ(テキスト抽出)
- license: 未確認。転載せず、言い換えにとどめる
- 取り込み: 一部(通信方式、ビーコン、中継)。テレメトリの項目表は未取り込み

# /sources/skylink-spec

- id: FS1-FS1p UHF Skylink Protocol Specification(2026-02-26 版、29 ページ、公開文書、責任者 Klaus Kivirikko)
- url: https://foresail.github.io/docs/FS1p_Skylink_protocol_Specification.pdf
- retrieved: 2026-11-08(517,794 バイト。ユーザーの承認のもと取得)
- read: PDF のテキストを抽出して、物理層・フレーム・仮想チャネル・時分割の各章を読んだ。データリンク層(HMAC・ARQ)と応用層は未読
- license: 未確認。転載せず、言い換えにとどめる
- 取り込み: 一部(`/assets/foresail-1p` の「Skylink 仕様の要点」)

# /sources/foresail-site

- id: Foresail-1p のプロジェクトサイト
- url: https://foresail.github.io/
- retrieved: 2026-11-07
- read: 要約ツール経由
- license: 明示なし(著作権表示のみ)
- 取り込み: 一部(識別符号、ペイロード、放出日、アマチュア向けの要点)

# /sources/aalto-radio-amateurs

- id: アアルト大学「for radio amateurs」(2026-07-15 更新、2018-10-30 公開)
- url: https://www.aalto.fi/en/spacecraft/for-radio-amateurs
- retrieved: 2026-11-07
- read: 要約ツール経由
- 取り込み: 一部(各衛星の周波数、変調、コールサイン、状態)。受信報告の依頼は書かれていない

# /sources/aalto-spacecraft-index

- id: アアルト大学「Spacecraft」一覧
- url: https://www.aalto.fi/en/spacecraft
- retrieved: 2026-11-07
- read: 要約ツール経由
- 取り込み: 済(8 つの宇宙機の分類)

# /sources/foresail-1p-page

- id: アアルト大学「Foresail-1 Prime」(2026-06-22 更新)
- url: https://www.aalto.fi/en/spacecraft/foresail-1-prime
- retrieved: 2026-11-07
- read: 要約ツール経由
- 取り込み: 一部(目的、ペイロード、打ち上げ、軌道)

# /sources/foresail-1-page

- id: アアルト大学「Foresail-1」(2024-09-25 更新)
- url: https://www.aalto.fi/en/spacecraft/foresail-1
- retrieved: 2026-11-07
- read: 要約ツール経由

# /sources/foresail-1-loss-news

- id: アアルト大学のニュース「Connection to the Foresail-1 science satellite is lost; the construction of a new satellite is…」(2022-11-04 公開、2022-11-10 更新)
- url: https://aalto.fi/en/news/connection-to-the-foresail-1-science-satellite-is-lost-the-construction-of-a-new-satellite-is
- retrieved: 2026-11-07
- read: 要約ツール経由

# /sources/suomi100-page

- id: アアルト大学「Suomi100-satellite」(2020-07-01 更新)
- url: https://www.aalto.fi/en/spacecraft/suomi100-satellite
- retrieved: 2026-11-07
- read: 要約ツール経由

# /sources/aalto-1-page

- id: アアルト大学「Aalto-1, the Finnish student satellite project」
- url: https://www.aalto.fi/en/spacecraft/aalto-1-the-finnish-student-satellite-project
- retrieved: 2026-11-07
- read: 要約ツール経由

# /sources/aalto-2-page

- id: アアルト大学「Aalto-2, satellite for QB50 constellation」
- url: https://www.aalto.fi/en/spacecraft/aalto-2-satellite-for-qb50-constellation
- retrieved: 2026-11-07
- read: 要約ツール経由

# /sources/aalto-3-page

- id: アアルト大学「Aalto-3 student satellite project」
- url: https://www.aalto.fi/en/spacecraft/aalto-3-student-satellite-project
- retrieved: 2026-11-07
- read: 要約ツール経由

# /sources/foresail-2-page

- id: アアルト大学「Foresail-2: space physics mission in a challenging environment」(2024-09-23 公開、2026-06-22 更新)
- url: https://www.aalto.fi/en/spacecraft/foresail-2-space-physics-mission-in-a-challenging-environment
- retrieved: 2026-11-07
- read: 要約ツール経由

# /sources/ssr-2023-foresail-2

- id: Slavinskis and Praks, Foresail-2 の設計論文, *Space Science Reviews* (2023)
- url: https://link.springer.com/article/10.1007/s11214-023-01012-7
- retrieved: なし
- read: 未読(題名と書誌は検索結果による)

# /sources/satnogs-observations

- id: SatNOGS Network の観測 15352006(Suomi 100、2026-11-03 09:56:40 UTC)、15286538(Foresail-1p、2026-10-24 21:27:57 UTC)
- url: https://network.satnogs.org/observations/15352006/、https://network.satnogs.org/observations/15286538/
- retrieved: 2026-11-07(日時・衛星・状態のメタ情報のみ)
- license: CC BY-SA。**録音・テレメトリは取り込まない**。観測 ID を参照として記す

# /sources/kikicom-records

- id: kikicom の記録(`documents/satellite/README.md`、`documents/antenna-placements.tsv`、`CLAUDE.md` §8)
- 自前の受信試験の記録。CC0

---

# /system-record/changelog

- 2026-11-08(続々): Foresail-1p のフレームの復号を追加(`/traces/2026-11-08-fs1p-decode`)。ハウスキーピング 75 件を復号、SGICD のサブタイプの食い違い(`/open-questions/sgicd-hk-subtype-swap`)と科学ペイロードの未解決(`/open-questions/fs1p-science-payload`)を追記。
- 2026-11-08(続): SatNOGS 音声 72 本の再デコードを追加(`/traces/2026-11-08-satnogs-redecode`)。`FORESAIL-1P` の出力形式(16 進ダンプ)の注意も追記。
- 2026-11-08: Skylink 仕様(物理層・フレーム・VC)、gr-satellites の衛星名、Suomi 100 のビーコン構造、SatNOGS 音声 72 本によるビーコンのタイミングの実測を追加。検出器への含意を訂正(短い窓ではなく、長い積分と周期畳み込み)。
- 2026-11-07: 初版(0.1)。アアルト大学の公式ページと SGICD V2 から、7 機の基礎を作った。受け入れテスト 6 件は、まだ誰も実行していない(`untested`)。盲検の実行(テストの節と結果を除いたコピーを、別の主体に渡す)が次の一歩。

# /system-record/agent-contract-reminder

- status: normative
- 再掲: 衛星の状態(`volatile`)は基準日を添えて答え、根拠のパスを回答の中に書くこと(`/system-record/agent-contract`)。
