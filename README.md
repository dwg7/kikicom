# kikicom

SDR(Software Defined Radio)受信の研究プロジェクト。ADS-B(1090MHz、航空機の位置・高度・速度等のブロードキャスト)を受信し、地理空間情報として可視化することを目標にする。

[dwg7/kikimimi](https://github.com/dwg7/kikimimi)(公共ラジオを社会センサーとして使うプロジェクト)と同じRPi 4B + RTL-SDRのハードウェア一式を時分割で共有する、姉妹プロジェクト。ミッション・データの性質・法的な扱いは全く別。

## これは何か

ADS-Bは、航空機が自機の位置・高度・速度等を、特定の相手方を想定せずブロードキャストし続ける仕組み。FlightRadar24・FlightAware・ADS-B Exchangeといった世界規模のクラウドソース受信網が、まさにこの性質を前提に、個人の安価な受信機からのデータ提供で成立している。

## 詳細

進め方・技術的な知見・現在のステータスは[CLAUDE.md](CLAUDE.md)を参照。

## ライセンス

[CC0 1.0 Universal](LICENSE)
