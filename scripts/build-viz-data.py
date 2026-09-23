#!/usr/bin/env python3
"""Build the static data files the dashboard (docs/) reads.

Runs on slate (Mac mini role). Inputs:
  - ~/kikicom-data/adsb-log/*.jsonl[.zst]  (rsync mirror of the RPi's log)
  - the RPi's live /run/adsb-research/{aircraft,stats}.json over ssh
Outputs (docs/data/, gitignored -- LOCAL PROTOTYPE ONLY):
  - live.geojson    aircraft with a recent position (points, for icons)
  - tracks.geojson  one LineString per aircraft pass in the last N hours
  - points.geojson  every logged position in the last N hours (altitude dots)
  - stats.json      hourly counts, receiver status, current aircraft table
  - coverage.json   receive-rate samples vs adsb.lol (from coverage-check.py
                    --record) and a bearing x elevation "field of view" grid
  - aircraft/index.json   every aircraft seen in the last 24h, with its passes
  - aircraft/<hex>.json   that aircraft's time series (columnar), for the
                          per-aircraft view and the timeline

NOT FOR PUBLICATION: no military / public-agency filtering is applied yet.
Publishing needs the reviewed classification policy first (CLAUDE.md).
"""
import argparse, datetime, glob, json, math, os, subprocess, time, urllib.request
from collections import defaultdict

HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(HOME, "kikicom-data", "adsb-log")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data")


def _receiver_location():
    """Precise receiver location if available (~/kikicom-data/receiver-location.json,
    outside the repo, never committed); falls back to the ~1km-rounded public default."""
    p = os.path.join(HOME, "kikicom-data", "receiver-location.json")
    try:
        with open(p) as f:
            d = json.load(f)
        return d["lon"], d["lat"]
    except (OSError, ValueError, KeyError):
        return 141.40, 43.05  # rounded to ~1km


RX = _receiver_location()  # receiver lon/lat
GAP_SEC = 600         # split a track when the aircraft was silent this long
JST = datetime.timezone(datetime.timedelta(hours=9))

# ICAO 24-bit address blocks -> country (only the ones seen around Sapporo)
ICAO_BLOCKS = [
    (0x840000, 0x87FFFF, "日本"), (0x718000, 0x71FFFF, "韓国"),
    (0x780000, 0x7BFFFF, "中国・香港"), (0x899000, 0x8993FF, "台湾"),
    (0x06A000, 0x06A3FF, "カタール"), (0x710000, 0x717FFF, "サウジ"),
    (0x800000, 0x83FFFF, "インド"), (0x880000, 0x887FFF, "タイ"),
    (0x888000, 0x88FFFF, "ベトナム"), (0x758000, 0x75FFFF, "フィリピン"),
    (0x7C0000, 0x7FFFFF, "豪州"), (0xA00000, 0xAFFFFF, "米国"),
    (0x100000, 0x1FFFFF, "ロシア"), (0x3C0000, 0x3FFFFF, "ドイツ"),
    (0x400000, 0x43FFFF, "英国"), (0x460000, 0x467FFF, "フィンランド"),
]


ADSBDB_CACHE = os.path.join(HOME, "kikicom-data", "adsbdb-cache.json")
WATCHLIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "watchlist.json")


class Registry:
    """adsbdb registration lookups, sharing review-aircraft.py's cache.
    Only aircraft currently in the air are fetched (a few per run); others use the cache."""

    CACHE_TTL = 7 * 86400  # same policy as review-aircraft.py's lookup(), kept in sync manually

    def __init__(self, max_fetch=3):
        try:
            with open(ADSBDB_CACHE) as f:
                self.cache = json.load(f)
        except (OSError, ValueError):
            self.cache = {}
        try:
            with open(WATCHLIST) as f:
                self.watch = json.load(f)
        except (OSError, ValueError):
            self.watch = {"label": "注目", "icao_types": [], "owner_keywords": [], "registrations": []}
        self.left = max_fetch
        self.new = {}  # only entries THIS process fetched; save() writes only these back,
                        # so a stale/unchanged in-memory snapshot never clobbers a concurrent
                        # writer's fresher update to a key this process didn't touch.
        self.dirty = False

    def get(self, hexcode, fetch=False):
        c = self.cache.get(hexcode)
        if c is not None and time.time() - c.get("at", 0) < self.CACHE_TTL:
            return c.get("aircraft")
        if not fetch or self.left <= 0 or hexcode.startswith("~"):
            return c.get("aircraft") if c is not None else None  # stale-but-present beats nothing
        self.left -= 1
        aircraft = None
        try:
            req = urllib.request.Request(f"https://api.adsbdb.com/v0/aircraft/{hexcode}",
                                         headers={"User-Agent": "kikicom build-viz-data"})
            resp = json.load(urllib.request.urlopen(req, timeout=5)).get("response")
            aircraft = resp.get("aircraft") if isinstance(resp, dict) else None
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return c.get("aircraft") if c is not None else None
        except Exception:
            return c.get("aircraft") if c is not None else None
        entry = {"at": time.time(), "aircraft": aircraft}
        self.cache[hexcode] = entry
        self.new[hexcode] = entry
        self.dirty = True
        return aircraft

    def info(self, hexcode, fetch=False):
        db = self.get(hexcode, fetch) or {}
        owner = (db.get("registered_owner") or "")
        w = self.watch
        watched = bool(db) and (db.get("icao_type") in w.get("icao_types", [])
                                or db.get("registration") in w.get("registrations", [])
                                or any(k.lower() in owner.lower() for k in w.get("owner_keywords", [])))
        return {"reg": db.get("registration"), "type": db.get("icao_type"), "owner": owner or None,
                "watch": w.get("label") if watched else None}

    def save(self):
        if not self.dirty:
            return
        try:  # merge with whatever review-aircraft.py wrote meanwhile
            with open(ADSBDB_CACHE) as f:
                disk = json.load(f)
        except (OSError, ValueError):
            disk = {}
        disk.update(self.new)  # only overlay entries fetched THIS run -- never the whole
                                # in-memory snapshot, so an untouched key a concurrent writer
                                # (review-aircraft.py) updated meanwhile is left alone
        tmp = ADSBDB_CACHE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(disk, f, ensure_ascii=False)
        os.replace(tmp, ADSBDB_CACHE)


def country(hexcode):
    try:
        v = int(hexcode.lstrip("~"), 16)
    except ValueError:
        return ""
    for lo, hi, name in ICAO_BLOCKS:
        if lo <= v <= hi:
            return name
    return ""


def read_log_rows(since):
    rows = []
    for path in sorted(glob.glob(os.path.join(LOG_DIR, "*.jsonl*"))):
        day = os.path.basename(path)[:10]
        try:
            day_end = datetime.datetime.strptime(day, "%Y-%m-%d").replace(
                tzinfo=datetime.timezone.utc).timestamp() + 86400
        except ValueError:
            continue
        if day_end < since:
            continue
        if path.endswith(".zst"):
            text = subprocess.run(["zstd", "-dc", path], capture_output=True,
                                  text=True, check=True).stdout
        elif path.endswith(".jsonl"):
            with open(path) as f:
                text = f.read()
        else:
            continue
        for line in text.splitlines():
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue  # a line cut mid-write by rsync
            if r.get("now", 0) >= since:
                rows.append(r)
    rows.sort(key=lambda r: (r["hex"], r["now"]))
    return rows


def ssh_json(host, path):
    try:
        out = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                              host, f"cat {path}"], capture_output=True, text=True,
                             timeout=20, check=True).stdout
        return json.loads(out)
    except Exception:
        return None


def alt_of(r):
    a = r.get("alt_baro")
    return a if isinstance(a, (int, float)) else (0 if a == "ground" else None)


# 飛行の性格分類(2026-09-23、CLAUDE.md「受信可能な方角の正確な理解」の続き)。
# 最接近距離だけで判定する: 目的地/出発地への進入出発なら、たとえ高仰角の
# 巡航中しか捕まえられなくても経路は空港の近くを通るはずなので、高度条件は
# 課さない(高度で絞ると低仰角限界で降下し切る前に見失った機を「その他」に
# 取りこぼしていた。実測で「その他」37.6%→2.2%に改善)
CTS = (42.7752, 141.6923)  # 新千歳空港(RJCC)
OKD = (43.1103, 141.3806)  # 丘珠空港(RJCO)
CTS_RADIUS_KM = 20
OKD_RADIUS_KM = 15
CRUISE_ALT_FT = 15000

FLIGHT_CATEGORY_LABELS = {
    "helicopter": "ヘリ・低空作業",
    "okadama": "丘珠発着・近傍周回",
    "chitose": "新千歳発着",
    "cruise": "巡航通過(高高度)",
    "mode_s_only": "Mode-Sのみ(位置なし)",
    "other": "その他・分類不能",
}


def haversine_km(lat1, lon1, lat2, lon2):
    r1, r2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(r1) * math.cos(r2) * math.sin(dl / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def classify_flight(rs):
    """優先順位: ヘリ(A7) > 丘珠 近傍 > 新千歳 近傍 > 巡航通過(高高度) > その他。
    位置が一度も取れない機体は Mode-S のみとして別扱い(判定不能)。"""
    if any(r.get("category") == "A7" for r in rs):
        return "helicopter"
    dmin_cts = dmin_okd = None
    for r in rs:
        if "lat" in r and "lon" in r:
            d_cts = haversine_km(r["lat"], r["lon"], *CTS)
            d_okd = haversine_km(r["lat"], r["lon"], *OKD)
            dmin_cts = d_cts if dmin_cts is None else min(dmin_cts, d_cts)
            dmin_okd = d_okd if dmin_okd is None else min(dmin_okd, d_okd)
    if dmin_cts is None:  # 位置が一度も取れなかった
        return "mode_s_only"
    if dmin_okd < OKD_RADIUS_KM:
        return "okadama"
    if dmin_cts < CTS_RADIUS_KM:
        return "chitose"
    known = [a for a in (alt_of(r) for r in rs) if a is not None]
    if known and min(known) >= CRUISE_ALT_FT:
        return "cruise"
    return "other"


def build_tracks(rows):
    # read_log_rows() no longer drops Mode-S-only (no-position) rows -- they still
    # count toward hourly()/build_aircraft()'s aircraft presence, but a line/point
    # needs coordinates, so skip them here specifically.
    tracks, points = [], []
    current, last = None, None
    for r in rows:
        if "lat" not in r or "lon" not in r:
            continue
        if last is None or r["hex"] != last["hex"] or r["now"] - last["now"] > GAP_SEC:
            if current and len(current["coords"]) >= 2:
                tracks.append(current)
            current = {"hex": r["hex"], "coords": [], "flight": "", "alts": [],
                       "t0": r["now"], "t1": r["now"]}
        current["coords"].append([round(r["lon"], 5), round(r["lat"], 5)])
        if (r.get("flight") or "").strip():
            current["flight"] = r["flight"].strip()
        a = alt_of(r)
        if a is not None:
            current["alts"].append(a)
        current["t1"] = r["now"]
        points.append({"type": "Feature",
                       "geometry": {"type": "Point", "coordinates": current["coords"][-1]},
                       "properties": {"hex": r["hex"], "alt": a, "t": int(r["now"])}})
        last = r
    if current and len(current["coords"]) >= 2:
        tracks.append(current)
    feats = [{"type": "Feature",
              "geometry": {"type": "LineString", "coordinates": t["coords"]},
              "properties": {"hex": t["hex"], "flight": t["flight"],
                             "country": country(t["hex"]),
                             "alt_min": min(t["alts"]) if t["alts"] else None,
                             "alt_max": max(t["alts"]) if t["alts"] else None,
                             "t0": int(t["t0"]), "t1": int(t["t1"]),
                             "n": len(t["coords"])}} for t in tracks]
    return feats, points


def passes_of(rs):
    """Split one aircraft's rows (time-sorted) into passes at GAP_SEC gaps."""
    out, cur = [], []
    for r in rs:
        if cur and r["now"] - cur[-1]["now"] > GAP_SEC:
            out.append(cur)
            cur = []
        cur.append(r)
    if cur:
        out.append(cur)
    return out


def phase(alts):
    """Rough flight phase of a pass from its altitude change."""
    alts = [a for a in alts if a is not None]
    if len(alts) < 2:
        return "—"
    d = alts[-1] - alts[0]
    return "上昇" if d > 1000 else "降下" if d < -1000 else "巡航"


def build_aircraft(rows, reg=None):
    """Per-aircraft columnar series + an index with passes (last 24h)."""
    by_hex = defaultdict(list)
    for r in rows:
        by_hex[r["hex"]].append(r)
    index, files = [], {}
    for hexcode, rs in by_hex.items():
        flights = []
        for r in rs:
            f = (r.get("flight") or "").strip()
            if f and f not in flights:
                flights.append(f)
        dst = lambda r: round(r["r_dst"] * 1.852, 1) if "r_dst" in r else None
        passes = []
        for ps in passes_of(rs):
            alts = [alt_of(r) for r in ps]
            known = [a for a in alts if a is not None]
            ds = [d for d in (dst(r) for r in ps) if d is not None]
            passes.append({"t0": int(ps[0]["now"]), "t1": int(ps[-1]["now"]), "n": len(ps),
                           "alt0": next((a for a in alts if a is not None), None),
                           "alt1": next((a for a in reversed(alts) if a is not None), None),
                           "alt_min": min(known) if known else None,
                           "alt_max": max(known) if known else None,
                           "alt_mean": round(sum(known) / len(known)) if known else None,
                           "dst_min": min(ds) if ds else None,
                           "phase": phase(alts)})
        key = "".join(c for c in hexcode if c.isalnum()).lower()
        info = reg.info(hexcode) if reg else {}
        fc = classify_flight(rs)
        index.append({"hex": hexcode, "key": key, "flights": flights, **info,
                      "country": country(hexcode), "first": int(rs[0]["now"]),
                      "last": int(rs[-1]["now"]), "n": len(rs), "passes": passes,
                      "flight_category": fc})
        files[key] = {
            "hex": hexcode, "flights": flights, "country": country(hexcode), **info,
            "category": next((r["category"] for r in reversed(rs) if r.get("category")), None),
            "squawk": next((r["squawk"] for r in reversed(rs) if r.get("squawk")), None),
            "flight_category": fc,
            "passes": passes,
            "series": {
                "t": [round(r["now"], 1) for r in rs],
                "lon": [round(r["lon"], 5) if "lon" in r else None for r in rs],
                "lat": [round(r["lat"], 5) if "lat" in r else None for r in rs],
                "alt": [alt_of(r) for r in rs],
                "gs": [r.get("gs") for r in rs],
                "rate": [r.get("baro_rate", r.get("geom_rate")) for r in rs],
                "track": [r.get("track") for r in rs],
                "dst": [dst(r) for r in rs],
                "rssi": [r.get("rssi") for r in rs],
                "oat": [r.get("oat") for r in rs],
                "ws": [r.get("ws") for r in rs],
                "wd": [r.get("wd") for r in rs],
            },
        }
    index.sort(key=lambda a: a["first"])
    return index, files


COVERAGE_DIR = os.path.join(HOME, "kikicom-data", "coverage")
ELEV_BINS = [(-90, 2, "<2°"), (2, 4, "2–4°"), (4, 8, "4–8°"), (8, 91, "8°+")]
BRG_STEP = 30


PLACEMENTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "documents", "antenna-placements.tsv")


def read_placements():
    """Antenna placement history (documents/antenna-placements.tsv): [(epoch, label, note)]."""
    out = []
    if os.path.exists(PLACEMENTS):
        with open(PLACEMENTS) as f:
            next(f, None)
            for line in f:
                c = line.rstrip("\n").split("\t")
                if len(c) >= 2 and c[0]:
                    t = datetime.datetime.strptime(c[0], "%Y-%m-%dT%H:%M").replace(tzinfo=JST).timestamp()
                    out.append((int(t), c[1], c[2] if len(c) > 2 else ""))
    return out


def build_coverage(now, days=7):
    """Receive-rate time series (last 48h) and a bearing x elevation grid (last N days,
    current antenna placement only: mixing placements would defeat the comparison)."""
    placements = read_placements()
    since_placement = placements[-1][0] if placements else 0
    series = []
    path = os.path.join(COVERAGE_DIR, "summary.tsv")
    if os.path.exists(path):
        with open(path) as f:
            next(f, None)
            for line in f:
                c = line.rstrip("\n").split("\t")
                if len(c) < 7:
                    continue
                t = datetime.datetime.strptime(c[0], "%Y-%m-%dT%H:%M").replace(tzinfo=JST).timestamp()
                if t < now - 48 * 3600:
                    continue
                # ssh 失敗(NA)と、分母が0(周りに機体がいない)は「率なし」として扱う
                na = c[3] == "NA" or c[2] == "0"
                series.append({"t": int(t), "radius": int(c[1]), "public": int(c[2]),
                               "missing": c[3] == "NA",
                               "ours": None if na else int(c[3]),
                               "rate": None if na else float(c[4]),
                               "low_public": None if na else int(c[5]),
                               "low_ours": None if na else int(c[6])})
    # 直近1時間の合計で率を出す(夜は分母が1〜3機しかなく、回ごとの値は0%と100%を行き来する)
    for x in series:
        win = [y for y in series if x["t"] - 3600 < y["t"] <= x["t"] and y["ours"] is not None]
        pub = sum(y["public"] for y in win)
        lowp = sum(y["low_public"] for y in win)
        x["rate_1h"] = sum(y["ours"] for y in win) / pub if pub else None
        x["low_1h"] = sum(y["low_ours"] for y in win) / lowp if lowp else None
        x["public_1h"] = pub
    grid = {}
    for i in range(days):
        day = datetime.datetime.fromtimestamp(now - i * 86400, JST).strftime("%Y-%m-%d")
        p = os.path.join(COVERAGE_DIR, day + ".tsv")
        if not os.path.exists(p):
            continue
        with open(p) as f:
            next(f, None)
            for line in f:
                c = line.rstrip("\n").split("\t")
                if len(c) < 9:
                    continue
                t = datetime.datetime.strptime(c[0], "%Y-%m-%dT%H:%M").replace(tzinfo=JST).timestamp()
                if t < since_placement:
                    continue
                brg, elev, seen = float(c[6]), float(c[7]), c[8] == "1"
                b = int(brg // BRG_STEP) % (360 // BRG_STEP)
                e = next((k for k, (lo, hi, _) in enumerate(ELEV_BINS) if lo <= elev < hi), None)
                if e is None:
                    continue  # elev outside [-90, 91): a corrupted/partial line, not a real reading
                cell = grid.setdefault((b, e), [0, 0])
                cell[0] += 1
                cell[1] += seen
    cells = [{"brg0": b * BRG_STEP, "brg1": (b + 1) * BRG_STEP, "elev": e,
              "total": v[0], "seen": v[1]} for (b, e), v in sorted(grid.items())]
    valid = [x for x in series if x["rate"] is not None]
    last = valid[-1] if valid else None
    day_ago = [x for x in valid if x["t"] >= now - 24 * 3600]
    return {"series": series, "elev_bins": [b[2] for b in ELEV_BINS], "brg_step": BRG_STEP,
            "placements": [{"t": t, "label": l, "note": n} for t, l, n in placements],
            "grid_since": since_placement,
            "grid_days": days, "grid": cells, "last": last,
            "rate_24h": (sum(x["ours"] for x in day_ago) / sum(x["public"] for x in day_ago))
            if day_ago and sum(x["public"] for x in day_ago) else None,
            "samples_24h": len(day_ago),
            "missing_24h": sum(1 for x in series if x["rate"] is None and x["t"] >= now - 24 * 3600)}


def hourly(rows, hours):
    now = time.time()
    start = int(now // 3600 - hours + 1) * 3600
    ac, pos = defaultdict(set), defaultdict(int)
    for r in rows:
        h = int(r["now"] // 3600) * 3600
        if h >= start:
            ac[h].add(r["hex"])
            pos[h] += 1
    return [{"t": datetime.datetime.fromtimestamp(h, JST).isoformat(),
             "aircraft": len(ac[h]), "positions": pos[h]}
            for h in range(start, int(now // 3600) * 3600 + 1, 3600)]


def write_json(name, obj):
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = os.path.join(OUT_DIR, name + ".tmp")
    with open(tmp, "w") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, os.path.join(OUT_DIR, name))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=6, help="track window")
    ap.add_argument("--host", default="m329.local")
    ap.add_argument("--live-only", action="store_true",
                    help="refresh live.geojson/stats.json receiver part only")
    args = ap.parse_args()
    now = time.time()

    reg = Registry()
    aircraft = ssh_json(args.host, "/run/adsb-research/aircraft.json")
    rstats = ssh_json(args.host, "/run/adsb-research/stats.json")

    live, table = [], []
    for a in (aircraft or {}).get("aircraft", []):
        if "lat" not in a or a.get("seen_pos", 999) > 60:
            continue
        props = {"hex": a["hex"], "flight": (a.get("flight") or "").strip(),
                 "country": country(a["hex"]), "alt": alt_of(a), **reg.info(a["hex"], fetch=True),
                 "gs": a.get("gs"), "track": a.get("track", 0),
                 "rate": a.get("baro_rate", a.get("geom_rate")),
                 "dst_km": round(a["r_dst"] * 1.852, 1) if "r_dst" in a else None,
                 "dir": round(a["r_dir"]) if "r_dir" in a else None,
                 "rssi": a.get("rssi"), "seen": a.get("seen_pos")}
        live.append({"type": "Feature",
                     "geometry": {"type": "Point", "coordinates": [a["lon"], a["lat"]]},
                     "properties": props})
        table.append(props)
    table.sort(key=lambda p: p["dst_km"] if p["dst_km"] is not None else 1e9)
    write_json("live.geojson", {"type": "FeatureCollection", "features": live})

    stats_path = os.path.join(OUT_DIR, "stats.json")
    prev = {}
    if args.live_only and os.path.exists(stats_path):
        with open(stats_path) as f:
            prev = json.load(f)

    stats = {
        "generated_at": datetime.datetime.fromtimestamp(now, JST).isoformat(timespec="seconds"),
        "receiver": {"lon": RX[0], "lat": RX[1]},
        "live": {"aircraft_total": len((aircraft or {}).get("aircraft", [])),
                 "with_position": len(live), "table": table,
                 "ok": aircraft is not None},
    }
    if rstats:
        m = rstats.get("last1min", {})
        stats["health"] = {"messages_1min": m.get("messages"),
                           "noise": m.get("local", {}).get("noise"),
                           "signal": m.get("local", {}).get("signal"),
                           "tracks_15min": rstats.get("last15min", {}).get("tracks", {}).get("all")}

    if args.live_only and prev:
        stats["hourly"] = prev.get("hourly", [])
        stats["coverage"] = prev.get("coverage")
        stats["window"] = prev.get("window", {})
        stats["flight_categories"] = prev.get("flight_categories")
    else:
        rows = read_log_rows(min(now - args.hours * 3600, now - 24 * 3600))
        win = [r for r in rows if r["now"] >= now - args.hours * 3600]
        tracks, points = build_tracks(win)
        write_json("tracks.geojson", {"type": "FeatureCollection", "features": tracks})
        write_json("points.geojson", {"type": "FeatureCollection", "features": points})
        stats["hourly"] = hourly(rows, 24)
        cov = build_coverage(now)
        write_json("coverage.json", cov)
        stats["coverage"] = {"last": cov["last"], "rate_24h": cov["rate_24h"],
                             "samples_24h": cov["samples_24h"], "missing_24h": cov["missing_24h"]}
        index, files = build_aircraft(rows, reg)
        cat_counts = defaultdict(int)
        for a in index:
            cat_counts[a["flight_category"]] += 1
        stats["flight_categories"] = {
            "labels": FLIGHT_CATEGORY_LABELS, "total": len(index),
            "counts": {k: cat_counts.get(k, 0) for k in FLIGHT_CATEGORY_LABELS},
        }
        ac_dir = os.path.join(OUT_DIR, "aircraft")
        os.makedirs(ac_dir, exist_ok=True)
        for key, obj in files.items():
            write_json(os.path.join("aircraft", key + ".json"), obj)
        write_json(os.path.join("aircraft", "index.json"),
                   {"generated_at": int(now), "hours": 24, "aircraft": index})
        for name in os.listdir(ac_dir):  # drop aircraft that left the 24h window
            if name.endswith(".json") and name != "index.json" and name[:-5] not in files:
                os.remove(os.path.join(ac_dir, name))
        stats["window"] = {"hours": args.hours, "positions": len(win),
                           "aircraft": len({r["hex"] for r in win}),
                           "tracks": len(tracks)}
    write_json("stats.json", stats)
    reg.save()
    print(f"live {len(live)} | window {stats.get('window')}")


if __name__ == "__main__":
    main()
