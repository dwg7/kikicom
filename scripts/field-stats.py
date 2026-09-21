#!/usr/bin/env python3
"""Field statistics of the received readsb JSON: how ADS-B is actually used.

The spec says what each field *can* carry; this counts what aircraft around
Sapporo actually send ("踏み跡"). For every field it reports how many
aircraft ever sent it (per-aircraft presence, the main measure -- per-row
presence is skewed toward aircraft we happen to receive well) split into
Japanese-registered (ICAO block 0x840000-0x87FFFF) and foreign aircraft,
plus the value distribution for categorical fields and ranges for numbers.

Runs on slate against the rsync mirror. Writes a Markdown report to
~/kikicom-data/field-stats/<from>_<to>.md (local; aggregated counts only).

    python3 scripts/field-stats.py            # everything in the mirror
    python3 scripts/field-stats.py --days 7   # the last 7 days
"""
import argparse, collections, datetime, glob, json, os, subprocess, time

HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(HOME, "kikicom-data", "adsb-log")
OUT_DIR = os.path.join(HOME, "kikicom-data", "field-stats")
JST = datetime.timezone(datetime.timedelta(hours=9))
JP = (0x840000, 0x87FFFF)

# readsb が常に付ける管理用のフィールド(機体が送った値ではない)
BOOKKEEPING = {"now", "hex", "messages", "seen", "seen_pos", "rssi", "mlat", "tisb",
               "r_dst", "r_dir", "type", "lastPosition"}
CATEGORICAL = {"category", "version", "sil_type", "nic", "rc", "nac_p", "nac_v", "sil",
               "nic_baro", "gva", "sda", "emergency", "nav_modes", "squawk", "type",
               "alert", "spi"}
# 意味の説明(学習用メモ。仕様上の意味の要約)
MEANING = {
    "category": "機体区分(A1軽量〜A5重量、A7回転翼、A0=情報なし)",
    "version": "ADS-B のバージョン(0=DO-260、1=DO-260A、2=DO-260B)",
    "nic": "位置の完全性の区分(大きいほど保証された誤差範囲が小さい)",
    "rc": "封じ込め半径(m、NIC から導出)",
    "nac_p": "位置の精度区分(8で誤差<93m、9で<30m、10で<10m)",
    "nac_v": "速度の精度区分",
    "sil": "完全性の保証水準(3が最高)",
    "sil_type": "SIL の単位(perhour/persample、v0 では unknown)",
    "nic_baro": "気圧高度が別系統と照合されているか",
    "gva": "GNSS 高度の精度区分",
    "sda": "システム設計の保証水準",
    "alt_baro": "気圧高度(ft)",
    "alt_geom": "GNSS による幾何高度(ft)",
    "gs": "対地速度(kt)",
    "ias": "指示対気速度(kt、Comm-B)",
    "tas": "真対気速度(kt、Comm-B)",
    "mach": "マッハ数(Comm-B)",
    "track": "進行方向(真方位)",
    "true_heading": "機首方位(真、Comm-B 由来)",
    "mag_heading": "機首方位(磁方位、Comm-B)",
    "track_rate": "旋回率",
    "roll": "バンク角(Comm-B)",
    "baro_rate": "気圧高度の昇降率(ft/分)",
    "geom_rate": "GNSS 高度の昇降率(ft/分)",
    "squawk": "トランスポンダコード(管制が割り当て)",
    "emergency": "緊急状態",
    "flight": "コールサイン",
    "nav_qnh": "高度計規正値(hPa)",
    "nav_altitude_mcp": "オートパイロットの選択高度(ft)",
    "nav_altitude_fms": "FMS の目標高度(ft)",
    "nav_heading": "オートパイロットの選択方位",
    "nav_modes": "オートパイロットのモード",
    "wd": "風向(readsb が Comm-B から算出)",
    "ws": "風速(同上)",
    "oat": "外気温(同上)",
    "tat": "全温度(同上)",
    "lat": "緯度", "lon": "経度",
    "calc_track": "readsb が位置の変化から計算した進行方向",
    "alert": "スコーク変更の警報フラグ(機体が送る監視状態)",
    "spi": "SPI(アイデント)フラグ(管制の指示でパイロットが押す)",
    "lastPosition": "readsb 管理用:位置が途切れた機体の最後の位置",
}


def read_rows(since):
    for path in sorted(glob.glob(os.path.join(LOG_DIR, "*.jsonl*"))):
        if path.endswith(".zst"):
            text = subprocess.run(["zstd", "-dc", path], capture_output=True, text=True, check=True).stdout
        elif path.endswith(".jsonl"):
            with open(path) as f:
                text = f.read()
        else:
            continue
        for line in text.splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("now", 0) >= since:
                yield r


def is_jp(h):
    try:
        v = int(h.lstrip("~"), 16)
    except ValueError:
        return False
    return JP[0] <= v <= JP[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=float, default=None)
    args = ap.parse_args()
    since = time.time() - args.days * 86400 if args.days else 0

    rows = list(read_rows(since))
    if not rows:
        raise SystemExit("no rows")
    groups = {"日本": set(), "外国": set()}
    field_ac = collections.defaultdict(lambda: {"日本": set(), "外国": set()})
    field_rows = collections.Counter()
    values = collections.defaultdict(lambda: {"日本": collections.Counter(), "外国": collections.Counter()})
    numeric = collections.defaultdict(list)
    types = collections.Counter()
    for r in rows:
        g = "日本" if is_jp(r["hex"]) else "外国"
        groups[g].add(r["hex"])
        types[r.get("type", "?")] += 1
        for k, v in r.items():
            if k in ("now", "hex"):
                continue
            field_ac[k][g].add(r["hex"])
            field_rows[k] += 1
            if k in CATEGORICAL:
                values[k][g][json.dumps(v, ensure_ascii=False) if isinstance(v, list) else str(v)] += 1
            elif isinstance(v, (int, float)) and not isinstance(v, bool):
                numeric[k].append(v)

    n_jp, n_fx = len(groups["日本"]), len(groups["外国"])
    t0 = datetime.datetime.fromtimestamp(min(r["now"] for r in rows), JST)
    t1 = datetime.datetime.fromtimestamp(max(r["now"] for r in rows), JST)
    out = [f"# ADS-B フィールドの統計({t0:%Y-%m-%d %H:%M}〜{t1:%m-%d %H:%M} JST)", "",
           f"記録 {len(rows):,} 行、機体 {n_jp + n_fx} 機(日本 {n_jp}・外国 {n_fx})。"
           f"記録の種類: " + ", ".join(f"{k} {v:,}" for k, v in types.most_common()), "",
           "「機体%」はその機体が一度でもそのフィールドを送った割合(運用の実態を見る主指標)。"
           "「行%」は全記録に占める割合(よく受かる機体に偏る)。", "",
           "## フィールドの有無", "",
           "| フィールド | 意味 | 日本 機体% | 外国 機体% | 行% |", "|---|---|---|---|---|"]
    order = sorted(field_ac, key=lambda k: (k in BOOKKEEPING, -len(field_ac[k]["日本"]) - len(field_ac[k]["外国"])))
    for k in order:
        jp = len(field_ac[k]["日本"]) / n_jp * 100 if n_jp else 0
        fx = len(field_ac[k]["外国"]) / n_fx * 100 if n_fx else 0
        name = k + ("(readsb 管理用)" if k in BOOKKEEPING else "")
        out.append(f"| `{name}` | {MEANING.get(k, '')} | {jp:.0f}% | {fx:.0f}% | {field_rows[k] / len(rows) * 100:.0f}% |")

    out += ["", "## 値の分布(区分・コード系、行数)", ""]
    for k in sorted(values):
        if k in ("squawk",):
            continue
        out.append(f"### `{k}` {MEANING.get(k, '')}")
        out.append("")
        out.append("| 値 | 日本 | 外国 |")
        out.append("|---|---|---|")
        keys = sorted(set(values[k]["日本"]) | set(values[k]["外国"]),
                      key=lambda v: -(values[k]["日本"][v] + values[k]["外国"][v]))
        for v in keys[:15]:
            out.append(f"| `{v}` | {values[k]['日本'][v]:,} | {values[k]['外国'][v]:,} |")
        out.append("")

    out += ["## 数値の範囲(全機体、行単位)", "", "| フィールド | 最小 | 中央値 | 最大 | 行数 |", "|---|---|---|---|---|"]
    for k in sorted(numeric):
        if k in BOOKKEEPING or k in CATEGORICAL:
            continue
        v = sorted(numeric[k])
        out.append(f"| `{k}` | {v[0]:g} | {v[len(v) // 2]:g} | {v[-1]:g} | {len(v):,} |")

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{t0:%Y-%m-%d}_{t1:%Y-%m-%d}.md")
    with open(path, "w") as f:
        f.write("\n".join(out) + "\n")
    print(path)


if __name__ == "__main__":
    main()
