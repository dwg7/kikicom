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
  - aircraft/index.json   every aircraft seen in the last 24h, with its passes
  - aircraft/<hex>.json   that aircraft's time series (columnar), for the
                          per-aircraft view and the timeline

NOT FOR PUBLICATION: no military / public-agency filtering is applied yet.
Publishing needs the reviewed classification policy first (CLAUDE.md).
"""
import argparse, datetime, glob, json, os, subprocess, time
from collections import defaultdict

HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(HOME, "kikicom-data", "adsb-log")
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data")
RX = (141.40, 43.05)  # receiver lon/lat, rounded to ~1km
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
    (0x400000, 0x43FFFF, "英国"),
]


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
            if r.get("now", 0) >= since and "lat" in r:
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


def build_tracks(rows):
    tracks, points = [], []
    current, last = None, None
    for r in rows:
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


def build_aircraft(rows):
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
        index.append({"hex": hexcode, "key": key, "flights": flights,
                      "country": country(hexcode), "first": int(rs[0]["now"]),
                      "last": int(rs[-1]["now"]), "n": len(rs), "passes": passes})
        files[key] = {
            "hex": hexcode, "flights": flights, "country": country(hexcode),
            "category": next((r["category"] for r in reversed(rs) if r.get("category")), None),
            "squawk": next((r["squawk"] for r in reversed(rs) if r.get("squawk")), None),
            "passes": passes,
            "series": {
                "t": [round(r["now"], 1) for r in rs],
                "lon": [round(r["lon"], 5) for r in rs],
                "lat": [round(r["lat"], 5) for r in rs],
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

    aircraft = ssh_json(args.host, "/run/adsb-research/aircraft.json")
    rstats = ssh_json(args.host, "/run/adsb-research/stats.json")

    live, table = [], []
    for a in (aircraft or {}).get("aircraft", []):
        if "lat" not in a or a.get("seen_pos", 999) > 60:
            continue
        props = {"hex": a["hex"], "flight": (a.get("flight") or "").strip(),
                 "country": country(a["hex"]), "alt": alt_of(a),
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
        stats["window"] = prev.get("window", {})
    else:
        rows = read_log_rows(min(now - args.hours * 3600, now - 24 * 3600))
        win = [r for r in rows if r["now"] >= now - args.hours * 3600]
        tracks, points = build_tracks(win)
        write_json("tracks.geojson", {"type": "FeatureCollection", "features": tracks})
        write_json("points.geojson", {"type": "FeatureCollection", "features": points})
        stats["hourly"] = hourly(rows, 24)
        index, files = build_aircraft(rows)
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
    print(f"live {len(live)} | window {stats.get('window')}")


if __name__ == "__main__":
    main()
