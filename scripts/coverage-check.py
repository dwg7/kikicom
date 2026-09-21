#!/usr/bin/env python3
"""Compare what our receiver sees against the adsb.lol public feed.

For every aircraft adsb.lol reports within RADIUS nm of the receiver, show
whether our readsb on the RPi currently has it, with distance, bearing,
altitude and elevation angle. Useful for judging antenna placement
(e.g. balcony vs. between the double-glazed windows): what matters for
range is the low-elevation, far-away traffic.

Run on the dev Mac or the Mac mini role machine (needs ssh to the RPi):
    python3 scripts/coverage-check.py [--radius 60] [--host m329.local]

Prints to stdout only; nothing is stored (raw data stays out of the repo).
"""
import argparse, json, math, subprocess, urllib.request

LAT, LON = 43.05, 141.40  # receiver, rounded to ~1km (same as the service)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--radius", type=int, default=60, help="nm")
    ap.add_argument("--host", default="m329.local")
    args = ap.parse_args()

    url = f"https://api.adsb.lol/v2/point/{LAT}/{LON}/{args.radius}"
    req = urllib.request.Request(url, headers={"User-Agent": "kikicom coverage-check"})
    public = json.load(urllib.request.urlopen(req, timeout=20)).get("ac", [])

    ours_raw = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", args.host, "cat /run/adsb-research/aircraft.json"],
        capture_output=True, text=True, check=True).stdout
    ours = {a["hex"]: a for a in json.loads(ours_raw)["aircraft"] if a.get("seen", 999) < 60}

    rows = []
    for a in public:
        if "lat" not in a or not isinstance(a.get("alt_baro"), (int, float)):
            continue
        d, b, e = geometry(a["lat"], a["lon"], a["alt_baro"])
        rows.append((e, d, b, a, a["hex"] in ours))
    rows.sort(key=lambda r: -r[0])

    print(f"{'seen':4} {'hex':6} {'flight':8} {'type':4} {'alt ft':>6} {'km':>5} {'brg':>4} {'elev':>5}")
    for e, d, b, a, seen in rows:
        print(f"{'YES' if seen else '-':4} {a['hex']:6} {(a.get('flight') or '').strip():8} "
              f"{a.get('t', ''):4} {a['alt_baro']:>6} {d:5.1f} {b:4.0f} {e:5.1f}")
    got = sum(r[4] for r in rows)
    extra = set(ours) - {r[3]["hex"] for r in rows}
    print(f"\nours {got}/{len(rows)} of adsb.lol aircraft within {args.radius}nm"
          f" (+{len(extra)} seen only by us)")


if __name__ == "__main__":
    main()
