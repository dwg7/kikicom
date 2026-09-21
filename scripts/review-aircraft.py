#!/usr/bin/env python3
"""Daily "要確認" list: aircraft worth a human look (public-agency, military,
rotorcraft, Mode S-only, unusual callsigns).

Runs on slate. Reads the rsync mirror (~/kikicom-data/adsb-log), looks each
ICAO address up in adsbdb (https://api.adsbdb.com, cached locally so each
address is asked about at most once a week), and writes
~/kikicom-data/review/YYYY-MM-DD.md (JST date). Nothing is published and
nothing goes into the repository: this is the learning-use line of what can
be known from reception alone (CLAUDE.md).

    python3 scripts/review-aircraft.py              # today (JST); in the 00:xx
                                                    # hour also finalizes yesterday
    python3 scripts/review-aircraft.py 2026-09-21   # a given JST day

Installed as an hourly LaunchAgent by scripts/install-review-timer.sh.
"""
import datetime, glob, json, os, re, subprocess, sys, time, urllib.request

HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(HOME, "kikicom-data", "adsb-log")
OUT_DIR = os.path.join(HOME, "kikicom-data", "review")
CACHE = os.path.join(HOME, "kikicom-data", "adsbdb-cache.json")
CACHE_TTL = 7 * 86400
JST = datetime.timezone(datetime.timedelta(hours=9))
JP_BLOCK = (0x840000, 0x87FFFF)
AIRLINE_CALLSIGN = re.compile(r"^[A-Z]{3}\d{1,4}[A-Z]{0,2}$")
# 所有者・運航者名にこれらが含まれたら「公用機の候補」
PUBLIC_WORDS = [
    "国土交通", "航空局", "海上保安", "警察", "消防", "防災", "防衛", "自衛隊",
    "開発局", "国土地理院", "気象庁",
    "Ministry", "Civil Aviation Bureau", "Coast Guard", "Police", "Fire and Disaster",
    "Fire Department", "Defense", "Defence", "Self-Defense", "Self Defense",
    "Government", "Geospatial Information", "Prefectural", "Metropolitan Police",
    "Regional Development Bureau", "JASDF", "JMSDF", "JGSDF",
]


def jst_day_bounds(day):
    start = datetime.datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=JST)
    return start.timestamp(), (start + datetime.timedelta(days=1)).timestamp()


def read_rows(t0, t1):
    rows = []
    for path in sorted(glob.glob(os.path.join(LOG_DIR, "*.jsonl*"))):
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
                continue
            if t0 <= r.get("now", 0) < t1:
                rows.append(r)
    return rows


def load_cache():
    try:
        with open(CACHE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def lookup(hexcode, cache):
    c = cache.get(hexcode)
    if c and time.time() - c.get("at", 0) < CACHE_TTL:
        return c.get("aircraft")
    aircraft = None
    try:
        req = urllib.request.Request(f"https://api.adsbdb.com/v0/aircraft/{hexcode}",
                                     headers={"User-Agent": "kikicom review-aircraft"})
        resp = json.load(urllib.request.urlopen(req, timeout=20)).get("response")
        aircraft = resp.get("aircraft") if isinstance(resp, dict) else None
    except urllib.error.HTTPError as e:
        if e.code != 404:  # 404 = unknown aircraft; anything else: retry next run
            return None
    except Exception:
        return None
    cache[hexcode] = {"at": time.time(), "aircraft": aircraft}
    time.sleep(0.3)
    return aircraft


def main():
    if len(sys.argv) > 1:
        review(sys.argv[1])
        return
    now = datetime.datetime.now(JST)
    if now.hour == 0:
        review((now - datetime.timedelta(days=1)).strftime("%Y-%m-%d"))
    review(now.strftime("%Y-%m-%d"))


def review(day):
    t0, t1 = jst_day_bounds(day)
    rows = read_rows(t0, t1)

    ac = {}
    for r in rows:
        h = r["hex"]
        a = ac.setdefault(h, {"hex": h, "flights": set(), "cats": set(), "squawks": set(),
                              "n": 0, "npos": 0, "alts": [], "first": r["now"], "last": r["now"],
                              "types": set(), "dmin": None})
        a["n"] += 1
        a["last"] = max(a["last"], r["now"])
        a["first"] = min(a["first"], r["now"])
        f = (r.get("flight") or "").strip()
        if f:
            a["flights"].add(f)
        for k, dst in (("category", "cats"), ("squawk", "squawks"), ("type", "types")):
            if r.get(k):
                a[dst].add(r[k])
        if isinstance(r.get("alt_baro"), (int, float)):
            a["alts"].append(r["alt_baro"])
        if "lat" in r:
            a["npos"] += 1
            if "r_dst" in r:
                d = r["r_dst"] * 1.852
                a["dmin"] = d if a["dmin"] is None else min(a["dmin"], d)

    cache = load_cache()
    for h, a in ac.items():
        a["db"] = lookup(h.lstrip("~"), cache) if not h.startswith("~") else None
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    with open(CACHE, "w") as f:
        json.dump(cache, f, ensure_ascii=False)

    def jp(h):
        try:
            v = int(h.lstrip("~"), 16)
        except ValueError:
            return False
        return JP_BLOCK[0] <= v <= JP_BLOCK[1]

    def owner(a):
        db = a["db"] or {}
        return " ".join(filter(None, [db.get("registered_owner"), db.get("registered_owner_operator_flag_code")]))

    sections = {
        "公用機の候補(所有者名に官公庁らしい語)": [],
        "日本のブロックで登録不明・定期便の便名なし(自衛隊・官公庁・新規登録の候補)": [],
        "ヘリコプター(区分A7)": [],
        "Mode Sのみ(ADS-Bの位置なし)": [],
        "航空会社の便名形式でないコールサイン": [],
    }
    for a in ac.values():
        db = a["db"]
        if db and any(w in owner(a) for w in PUBLIC_WORDS):
            sections["公用機の候補(所有者名に官公庁らしい語)"].append(a)
        # adsbdb に載っていない定期便も多いので、航空会社の便名を送った機体は除く
        airline = bool(a["flights"]) and all(AIRLINE_CALLSIGN.match(f) for f in a["flights"])
        if jp(a["hex"]) and db is None and not airline:
            sections["日本のブロックで登録不明・定期便の便名なし(自衛隊・官公庁・新規登録の候補)"].append(a)
        if "A7" in a["cats"]:
            sections["ヘリコプター(区分A7)"].append(a)
        if a["npos"] == 0:
            sections["Mode Sのみ(ADS-Bの位置なし)"].append(a)
        if a["flights"] and not all(AIRLINE_CALLSIGN.match(f) for f in a["flights"]):
            sections["航空会社の便名形式でないコールサイン"].append(a)

    def line(a):
        db = a["db"] or {}
        t = lambda x: datetime.datetime.fromtimestamp(x, JST).strftime("%H:%M")
        alts = f"{min(a['alts'])}–{max(a['alts'])}ft" if a["alts"] else "高度不明"
        dmin = "%.0fkm" % a["dmin"] if a["dmin"] is not None else "—"
        return (f"| {a['hex']} | {'/'.join(sorted(a['flights'])) or '—'} | "
                f"{db.get('registration', '—')} | {db.get('type', '—')} | {db.get('registered_owner', '—')} | "
                f"{t(a['first'])}–{t(a['last'])} | {alts} | "
                f"{a['npos']}/{a['n']} | {dmin} | "
                f"{','.join(sorted(a['squawks'])) or '—'} |")

    known = sum(1 for a in ac.values() if a["db"])
    out = [f"# 要確認の機体 {day}(JST)", "",
           f"受信した機体 {len(ac)} 機(adsbdb で登録が見つかったもの {known} 機)。記録 {len(rows)} 行。",
           "学習用の記録。公開しない(CLAUDE.md)。登録情報は adsbdb の公開データによる。", ""]
    head = ("| ICAO | コールサイン | 登録 | 機種 | 所有者 | 時刻 | 高度 | 位置あり/全行 | 最接近 | スコーク |\n"
            "|---|---|---|---|---|---|---|---|---|---|")
    for title, items in sections.items():
        out.append(f"## {title}({len(items)})")
        out.append("")
        if items:
            out.append(head)
            out.extend(line(a) for a in sorted(items, key=lambda a: a["first"]))
        else:
            out.append("なし")
        out.append("")
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"{day}.md")
    with open(path, "w") as f:
        f.write("\n".join(out))
    print(path)
    print("\n".join(f"{t}: {len(i)}" for t, i in sections.items()))


if __name__ == "__main__":
    main()
