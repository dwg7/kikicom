#!/usr/bin/env python3
"""Compare what our receiver sees against the adsb.lol public feed.

For every aircraft adsb.lol reports within RADIUS nm of the receiver, show
whether our readsb on the RPi currently has it, with distance, bearing,
altitude and elevation angle. Useful for judging antenna placement
(e.g. balcony vs. between the double-glazed windows): what matters for
range is the low-elevation, far-away traffic.

Run on slate (needs ssh to the RPi):
    python3 scripts/coverage-check.py [--radius 60] [--host m329.local]
    python3 scripts/coverage-check.py --record [--radius 100]

Without --record it only prints. With --record (the 15-minute LaunchAgent,
scripts/install-coverage-timer.sh) it appends one row per public-feed
aircraft to ~/kikicom-data/coverage/YYYY-MM-DD.tsv (JST date) and one summary
row to ~/kikicom-data/coverage/summary.tsv. This is the survivorship-bias-
free measure of the receiving environment (the denominator includes what we
missed), used to notice antenna/window changes (condensation, frost) and to
map the window's field of view by bearing x elevation. adsb.lol data is
ODbL: kept for internal use only, never published or committed.
"""
import argparse, datetime, json, math, os, subprocess, sys, time, urllib.request

def _receiver_location():
    """Precise receiver location if available (~/kikicom-data/receiver-location.json,
    outside the repo, never committed); falls back to the ~1km-rounded public default
    (same value used in the repo's own service defaults / CLAUDE.md)."""
    p = os.path.join(os.path.expanduser("~"), "kikicom-data", "receiver-location.json")
    try:
        with open(p) as f:
            d = json.load(f)
        return d["lat"], d["lon"]
    except (OSError, ValueError, KeyError):
        return 43.05, 141.40  # rounded to ~1km


LAT, LON = _receiver_location()
EARTH_R_M = 6371000.0


def geometry(lat, lon, alt_ft):
    """Distance (km), bearing (deg) and elevation angle (deg) from receiver."""
    p1, p2 = math.radians(LAT), math.radians(lat)
    dl = math.radians(lon - LON)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    central = 2 * math.asin(math.sqrt(a))
    dist_m = EARTH_R_M * central
    brg = math.degrees(math.atan2(
        math.sin(dl) * math.cos(p2),
        math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl))) % 360
    h = alt_ft * 0.3048
    # elevation with earth curvature: angle above the local horizontal
    r1, r2 = EARTH_R_M, EARTH_R_M + h
    elev = math.degrees(math.atan2(r2 * math.cos(central) - r1, r2 * math.sin(central)))
    return dist_m / 1000, brg, elev


def fetch_ours(host):
    """Our readsb's aircraft seen in the last 60s, or None if the RPi is unreachable."""
    for attempt in range(2):
        p = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
                            "cat /run/adsb-research/aircraft.json"], capture_output=True, text=True)
        if p.returncode == 0:
            return {a["hex"]: a for a in json.loads(p.stdout)["aircraft"] if a.get("seen", 999) < 60}
        print(f"ssh attempt {attempt + 1} failed ({p.returncode}): {p.stderr.strip()}", file=sys.stderr)
        time.sleep(5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=int, default=None,
                    help="nm (default 60; 100 with --record, where the far low-elevation edge matters)")
    ap.add_argument("--host", default="m329.local")
    ap.add_argument("--ours-file",
                    help="read our aircraft.json from this file instead of ssh (used by "
                         "coverage-record.sh: under launchd, ssh from Homebrew Python is "
                         "refused by macOS Local Network privacy)")
    ap.add_argument("--record", action="store_true",
                    help="append to ~/kikicom-data/coverage/ instead of printing")
    args = ap.parse_args()
    if args.radius is None:
        args.radius = 100 if args.record else 60

    url = f"https://api.adsb.lol/v2/point/{LAT}/{LON}/{args.radius}"
    req = urllib.request.Request(url, headers={"User-Agent": "kikicom coverage-check"})
    public = json.load(urllib.request.urlopen(req, timeout=20)).get("ac", [])

    if args.ours_file:
        try:
            with open(args.ours_file) as f:
                ours = {a["hex"]: a for a in json.load(f)["aircraft"] if a.get("seen", 999) < 60}
        except (OSError, ValueError, KeyError):
            ours = None
    else:
        ours = fetch_ours(args.host)
    if ours is None:
        # 一時的な ssh/mDNS 失敗。欠測を黙って落とさず、欠測として残す
        if args.record:
            record_missing(args.radius, len(public))
        raise SystemExit(f"could not read aircraft.json from {args.host}")

    rows = []
    for a in public:
        if "lat" not in a or not isinstance(a.get("alt_baro"), (int, float)):
            continue
        d, b, e = geometry(a["lat"], a["lon"], a["alt_baro"])
        rows.append((e, d, b, a, a["hex"] in ours))
    rows.sort(key=lambda r: -r[0])

    if args.record:
        record(rows, ours, args.radius)
        return

    print(f"{'seen':4} {'hex':6} {'flight':8} {'type':4} {'alt ft':>6} {'km':>5} {'brg':>4} {'elev':>5}")
    for e, d, b, a, seen in rows:
        print(f"{'YES' if seen else '-':4} {a['hex']:6} {(a.get('flight') or '').strip():8} "
              f"{a.get('t', ''):4} {a['alt_baro']:>6} {d:5.1f} {b:4.0f} {e:5.1f}")
    got = sum(r[4] for r in rows)
    extra = set(ours) - {r[3]["hex"] for r in rows}
    print(f"\nours {got}/{len(rows)} of adsb.lol aircraft within {args.radius}nm"
          f" (+{len(extra)} seen only by us)")


COVERAGE_DIR = os.path.join(os.path.expanduser("~"), "kikicom-data", "coverage")
SUMMARY_HEADER = "time\tradius_nm\tpublic\tours\trate\tpublic_elev_lt4\tours_elev_lt4\n"


def stamp_now():
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))


def append_summary(line):
    os.makedirs(COVERAGE_DIR, exist_ok=True)
    path = os.path.join(COVERAGE_DIR, "summary.tsv")
    new = not os.path.exists(path)
    with open(path, "a") as f:
        if new:
            f.write(SUMMARY_HEADER)
        f.write(line)


def record_missing(radius, n_public):
    append_summary(f"{stamp_now():%Y-%m-%dT%H:%M}\t{radius}\t{n_public}\tNA\tNA\tNA\tNA\n")


def record(rows, ours, radius):
    now = stamp_now()
    out_dir = COVERAGE_DIR
    os.makedirs(out_dir, exist_ok=True)
    stamp = now.strftime("%Y-%m-%dT%H:%M")
    day_path = os.path.join(out_dir, now.strftime("%Y-%m-%d") + ".tsv")
    new_day = not os.path.exists(day_path)
    with open(day_path, "a") as f:
        if new_day:
            f.write("time\thex\tflight\ttype\talt_ft\tdist_km\tbrg\telev\tseen\trssi\n")
        for e, d, b, a, seen in rows:
            rssi = ours[a["hex"]].get("rssi", "") if seen else ""
            f.write(f"{stamp}\t{a['hex']}\t{(a.get('flight') or '').strip()}\t{a.get('t', '')}\t"
                    f"{a['alt_baro']}\t{d:.1f}\t{b:.0f}\t{e:.2f}\t{int(seen)}\t{rssi}\n")
    got = sum(r[4] for r in rows)
    low = [r for r in rows if r[0] < 4]
    append_summary(f"{stamp}\t{radius}\t{len(rows)}\t{got}\t{got / len(rows) if rows else 0:.3f}\t"
                   f"{len(low)}\t{sum(r[4] for r in low)}\n")
    print(f"{stamp} ours {got}/{len(rows)} within {radius}nm")


if __name__ == "__main__":
    main()
