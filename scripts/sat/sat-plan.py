#!/usr/bin/env python3
"""Plan CubeSat passes and pick the ones worth borrowing the RTL-SDR for.

P0 of documents/satellite/README.md: this only writes a schedule. It never
touches adsb-research.service or the dongle. For every pass of every enabled
target in the next `horizon_h` hours it computes the part of the pass that is
inside the open part of the sky (the obstruction mask), then marks it
`selected` or gives a `skip_reason`, so the dry run shows exactly which
windows the ADS-B capture would have lost.

Runs on the RPi (and on slate for testing) under a python that has skyfield:
    python3 sat-plan.py --home ~/sat            # write schedule.json / .tsv
    python3 sat-plan.py --home ~/sat --print    # also print the table

Files under --home:
    config.json      copied from scripts/sat/config.json by the installer
    location.json    {"lat":..,"lon":..,"elev_m":..}; written by the installer,
                     never committed (exact position, CLAUDE.md)
    tle/<norad>.tle  Celestrak cache
    schedule.json    the plan (UTC ISO times); schedule.tsv is the JST summary
    plan-history.jsonl  one line per run
"""
import argparse, datetime, json, os, sys, time, urllib.request

from skyfield.api import EarthSatellite, load, wgs84

JST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc
STEP_S = 10  # sampling step along a pass


def parse_mask(spec):
    out = []
    for part in spec.split(","):
        rng, el = part.split(":")
        lo, hi = (float(x) for x in rng.split("-"))
        out.append((lo, hi, float(el)))
    return out


def min_el_at(mask, az):
    for lo, hi, el in mask:
        if lo <= az < hi:
            return el
    return 90.0


def fetch_tle(home, norad, refresh_h):
    """Return (name, line1, line2, age_note). Falls back to the cache when offline."""
    d = os.path.join(home, "tle")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{norad}.tle")
    stale = (not os.path.exists(path)) or time.time() - os.path.getmtime(path) > refresh_h * 3600
    if stale:
        url = f"https://celestrak.org/NORAD/elements/gp.php?CATNR={norad}&FORMAT=tle"
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                text = r.read().decode()
            if "No GP data" not in text and len(text.split("\n")) >= 3:
                tmp = path + ".tmp"
                with open(tmp, "w") as f:
                    f.write(text)
                os.replace(tmp, path)
        except OSError as e:
            print(f"warn: TLE fetch failed for {norad}: {e}; using cache", file=sys.stderr)
    if not os.path.exists(path):
        return None
    lines = [l.rstrip() for l in open(path).read().splitlines() if l.strip()]
    if len(lines) < 3:
        return None
    return lines[0].strip(), lines[1], lines[2]


def passes_for(target, tle, here, ts, t0, t1, mask, cfg):
    name, l1, l2 = tle
    sat = EarthSatellite(l1, l2, name, ts)
    age_days = t0.tt - sat.epoch.tt
    out = []
    times, events = sat.find_events(here, t0, t1, altitude_degrees=0.0)
    i = 0
    while i < len(events):
        # a whole pass is rise(0), culminate(1), set(2); skip fragments at the edges
        if not (events[i] == 0 and i + 2 < len(events) and events[i + 1] == 1 and events[i + 2] == 2):
            i += 1
            continue
        rise, set_ = times[i], times[i + 2]
        n = max(int((set_.tt - rise.tt) * 86400 / STEP_S), 2)
        grid = ts.tt_jd([rise.tt + (set_.tt - rise.tt) * k / n for k in range(n + 1)])
        alt, az, _ = (sat - here).at(grid).altaz()
        alt_d, az_d = alt.degrees, az.degrees
        dt = (set_.tt - rise.tt) * 86400 / n
        vis = [a >= min_el_at(mask, z) for a, z in zip(alt_d, az_d)]
        k = int(alt_d.argmax())
        p = dict(
            sat=target["name"], norad=target["norad"], freq_mhz=target.get("freq_mhz"),
            priority=target.get("priority", 1), tle_age_days=round(float(age_days), 2),
            aos=rise.utc_datetime(), tca=grid[k].utc_datetime(), los=set_.utc_datetime(),
            aos_az=float(az_d[0]), los_az=float(az_d[-1]),
            max_el=float(alt_d[k]), max_az=float(az_d[k]),
            usable_s=sum(vis) * dt,
            usable_el=float(max((a for a, v in zip(alt_d, vis) if v), default=0.0)),
            window_start=None, window_end=None, selected=False, skip_reason=None)
        if any(vis):
            first = vis.index(True)
            last = len(vis) - 1 - vis[::-1].index(True)
            pad = datetime.timedelta(seconds=cfg["window_pad_s"])
            p["window_start"] = grid[first].utc_datetime() - pad
            p["window_end"] = grid[last].utc_datetime() + pad
        out.append(p)
        i += 3
    return out


def select(passes, cfg):
    """Mark passes selected / skipped: filter, then greedy by score under the
    gap and daily-cap limits (the ADS-B outage budget)."""
    gap = datetime.timedelta(minutes=cfg["min_gap_min"])
    cap = datetime.timedelta(minutes=cfg["daily_cap_min"])
    cands = []
    for p in passes:
        if p["max_el"] < cfg["min_max_el"] or p["usable_s"] < cfg["min_usable_s"] or p["usable_el"] < cfg["min_usable_el"]:
            p["skip_reason"] = "below-filter"
        else:
            cands.append(p)
    cands.sort(key=lambda p: (-(p["priority"] * 1000 + p["usable_s"]), p["aos"]))
    taken, per_day = [], {}
    for p in cands:
        a, b = p["window_start"], p["window_end"]
        if any(a < q["window_end"] + gap and q["window_start"] < b + gap for q in taken):
            p["skip_reason"] = "conflict"
            continue
        day = a.astimezone(JST).date()
        if per_day.get(day, datetime.timedelta()) + (b - a) > cap:
            p["skip_reason"] = "daily-cap"
            continue
        per_day[day] = per_day.get(day, datetime.timedelta()) + (b - a)
        p["selected"] = True
        taken.append(p)
    return passes


def iso(d):
    return d.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home", default=os.path.expanduser("~/sat"))
    ap.add_argument("--config", help="default: <home>/config.json")
    ap.add_argument("--print", action="store_true", help="print the table")
    args = ap.parse_args()

    cfg = json.load(open(args.config or os.path.join(args.home, "config.json")))
    loc = json.load(open(os.path.join(args.home, "location.json")))
    mask = parse_mask(cfg["mask"])
    ts = load.timescale()
    here = wgs84.latlon(loc["lat"], loc["lon"], elevation_m=loc.get("elev_m", 30.0))
    now = datetime.datetime.now(UTC)
    t0 = ts.from_datetime(now)
    t1 = ts.from_datetime(now + datetime.timedelta(hours=cfg["horizon_h"]))

    passes, notes = [], []
    for target in cfg["targets"]:
        if not target.get("enabled", True):
            continue
        tle = fetch_tle(args.home, target["norad"], cfg["tle_refresh_h"])
        if tle is None:
            notes.append(f"{target['name']}: no TLE")
            continue
        got = passes_for(target, tle, here, ts, t0, t1, mask, cfg)
        if got and got[0]["tle_age_days"] > cfg["tle_max_age_days"]:
            notes.append(f"{target['name']}: TLE {got[0]['tle_age_days']:.1f} days old, skipped")
            continue
        passes += got
    select(passes, cfg)
    passes.sort(key=lambda p: p["aos"])

    sched = {
        "generated": iso(now), "horizon_h": cfg["horizon_h"], "mask": cfg["mask"], "notes": notes,
        "passes": [{k: (iso(v) if isinstance(v, datetime.datetime) else (round(v, 2) if isinstance(v, float) else v))
                    for k, v in p.items()} for p in passes],
    }
    os.makedirs(args.home, exist_ok=True)
    tmp = os.path.join(args.home, "schedule.json.tmp")
    with open(tmp, "w") as f:
        json.dump(sched, f, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(args.home, "schedule.json"))

    lines = ["sat\tAOS(JST)\tmax_el\tmax_az\twindow(JST)\twindow_s\tselected\treason"]
    for p in passes:
        w = ""
        ws = 0
        if p["window_start"]:
            w = f"{p['window_start'].astimezone(JST):%m-%d %H:%M:%S}-{p['window_end'].astimezone(JST):%H:%M:%S}"
            ws = int((p["window_end"] - p["window_start"]).total_seconds())
        lines.append(f"{p['sat']}\t{p['aos'].astimezone(JST):%m-%d %H:%M}\t{p['max_el']:.0f}\t{p['max_az']:.0f}\t{w}\t{ws}\t"
                     f"{'yes' if p['selected'] else 'no'}\t{p['skip_reason'] or ''}")
    with open(os.path.join(args.home, "schedule.tsv"), "w") as f:
        f.write("\n".join(lines) + "\n")

    sel = [p for p in passes if p["selected"]]
    hist = {"at": iso(now), "passes": len(passes), "selected": len(sel),
            "outage_s": int(sum((p["window_end"] - p["window_start"]).total_seconds() for p in sel)),
            "notes": notes}
    with open(os.path.join(args.home, "plan-history.jsonl"), "a") as f:
        f.write(json.dumps(hist, ensure_ascii=False) + "\n")

    if args.print:
        print("\n".join(l.replace("\t", "  ") for l in lines))
        print(f"\n{len(passes)} passes, {len(sel)} selected, ADS-B outage would be {hist['outage_s']//60} min in {cfg['horizon_h']} h")
        for n in notes:
            print("note:", n)


if __name__ == "__main__":
    main()
