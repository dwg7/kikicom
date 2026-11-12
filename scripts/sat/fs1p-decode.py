#!/usr/bin/env python3
"""Foresail-1p のフレームを復号する(gr_satellites の FORESAIL-1P ログ → Skylink → PUS → ハウスキーピング)。

入力: gr_satellites (--satellite FORESAIL-1P --verbose 相当) の標準出力/ログ。
      "VERBOSE PDU DEBUG PRINT" の 16 進ダンプを拾う。複数ファイル可、"-" で標準入力。
出力: 1 フレーム 1 行 + 末尾に集計。--json で 1 行 1 JSON(解析用)。

構造の出典: Foresail-1p SGICD V2 (2026-02-23) と Skylink 仕様。バイト順は SGICD に書かれておらず、
実フレームで確かめた: Skylink の seq・PUS ヘッダ・ハウスキーピング先頭の UNIX 時刻はビッグエンディアン、
ファイル転送の block index も同様。ハウスキーピング本体と UINT32 等はリトルエンディアン
(根拠: 稼働時間がビーコンごとに +60 s、ADCS 位置ベクトルから高度 ~512 km・速度 ~7.6 km/s)。

SGICD の表と実機の食い違い(2026-11-08 確認): 実機では UHF HK が TM(3,4)、ADCS HK が TM(3,5)。
SGICD は逆に書いている。本体の長さ(UHF 56 B、ADCS 79 B)と中身の整合から実機側を採る。

フレーム末尾の 4 バイトは認証コードと見られる(鍵が無いので検証しない)。
SatNOGS 由来のデータは CC BY-SA。復号結果を CC0 の公開物に混ぜないこと(CLAUDE.md §4)。
"""
import argparse, collections, datetime, json, math, re, struct, sys

APID = 820
TAIL = 4          # 末尾の認証コード
EARTH_R = 6371.0  # km


def load_frames(text):
    frames = []
    for blk in re.split(r"\*+\n\*+ VERBOSE PDU DEBUG PRINT", text):
        m = re.search(r"pdu length =\s+(\d+) bytes\npdu vector contents = \n((?:[0-9a-f]{4}: .*\n?)+)", blk)
        if not m:
            continue
        h = "".join(re.sub(r"^[0-9a-f]{4}: ", "", l) for l in m.group(2).strip().split("\n")).replace(" ", "")
        b = bytes.fromhex(h)
        if len(b) == int(m.group(1)):
            frames.append(b)
    return frames


def skylink(b):
    il = b[0] & 7
    o = 1 + il
    r = {"id": b[1:o].decode("ascii", "replace"), "flags": b[o], "vc": b[o] & 3,
         "seq": (b[o + 1] << 8) | b[o + 2]}
    el = b[o + 3]
    r["ext"] = b[o + 4:o + 4 + el]
    r["pay"] = b[o + 4 + el:]
    return r


def pus(p):
    if len(p) < 9:
        return None
    pid, _, ln = struct.unpack(">HHH", p[:6])
    if pid & 0x7FF != APID:
        return None
    return {"svc": p[7], "sub": p[8], "body": p[9:6 + ln], "len": ln}


def utc(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def hk_obc(d):
    side, fdir, wd, fs, sw, up, heap, cpu, fsfree, aup, aage, aboot, atemp = struct.unpack("<BBHBBIBBHHHHh", d[:22])
    return {"side": "AB"[side & 1] + ("-recovery" if side > 1 else ""), "fdir": fdir, "wd_boots": wd,
            "fs_mounted": fs, "sw_rev": sw, "uptime_h": round(up / 3600, 2), "heap_free_pct": round(heap / 2.55),
            "cpu_pct": round(cpu / 2.55), "fs_free_kB": fsfree * 4, "arb_uptime_s": aup, "arb_boots": aboot,
            "arb_temp_C": atemp / 10}


def hk_eps(d):
    up, pb, bb, apr, pdme, pdmf, _, st, pwm = struct.unpack("<IBBBBBBHH", d[:14])
    v = struct.unpack("<24h", d[14:62])
    n = ["i_apr_x", "i_apr_y", "v_apr_x", "v_apr_y", "x_chg_max", "x_pv_max", "y_chg_max", "y_pv_max", "v_bat",
         "v_bat_low", "v_buck_pl", "v_buck_obc", "v_buck_uhf", "t_pcdu", "t_bb", "t_apr", "t_bat", "t_xm", "t_xp",
         "t_ym", "t_yp", "i_bat", "i_bat_min", "i_bat_max"]
    r = {"uptime_h": round(up / 3600, 1), "boots": [pb, bb, apr], "pdm_expected": format(pdme, "08b"),
         "pdm_faults": format(pdmf, "08b"), "state": hex(st), "heater_pwm": pwm}
    for k, x in zip(n, v):
        r[k] = x / 10 if k.startswith("t_") else x  # t_*: ℃、i_*: mA、v_*: mV
    cur = struct.unpack("<%dh" % ((len(d) - 62) // 2), d[62:62 + 2 * ((len(d) - 62) // 2)])
    r["bus_currents_mA"] = list(cur)
    return r


def hk_uhf(d):
    (up, boot, fdir, wd, mbe, bs, bl, bc, bt, txf, rxf, txh, rxh, ba, bb, side, rxr, txr, myw, peer, mcu, pa,
     rssi, rssimax, last, off) = struct.unpack("<IHBBBBBBBIIIIHHBBBiihhhhhh", d[:56])
    return {"uptime_s": up, "boots": boot, "tx_frames": txf, "rx_frames": rxf, "tx_ham": txh, "rx_ham": rxh,
            "side": "AB"[side & 1], "sym_rate_rx_tx": [rxr, txr], "window_ms_own_peer": [myw, peer],
            "mcu_temp_C": mcu / 10, "pa_temp_C": pa / 10,
            # RSSI の符号・較正は SGICD の記述と合わない値が出る(未確定)。生値のまま残す
            "rssi_raw": [rssi, rssimax, last], "freq_offset_Hz": round(off * 19.07)}


def hk_adcs(d):
    det, ctl, mjd = struct.unpack("<BBf", d[:6])
    pos = struct.unpack("<3f", d[6:18])
    vel = struct.unpack("<3f", d[18:30])
    r = math.dist(pos, (0, 0, 0))
    return {"determination": det, "control": ctl, "mjd": round(mjd, 4), "alt_km": round(r - EARTH_R, 1),
            "speed_kms": round(math.dist(vel, (0, 0, 0)), 3),
            "ang_rate_mrads": list(struct.unpack("<3h", d[35:41]))}


HK = {2: ("OBC", hk_obc, 38), 3: ("EPS", hk_eps, 110), 4: ("UHF", hk_uhf, 56), 5: ("ADCS", hk_adcs, 79)}


def ax25(p):
    calls, i = [], 0
    while i + 7 <= len(p):
        calls.append("".join(chr(c >> 1) for c in p[i:i + 6]).strip() + "-%d" % ((p[i + 6] >> 1) & 15))
        i += 7
        if p[i - 1] & 1:
            break
    return calls, p[i:]


def decode(b):
    s = skylink(b)
    out = {"vc": s["vc"], "skylink_seq": s["seq"], "len": len(b)}
    if s["vc"] == 3:
        calls, info = ax25(s["pay"])
        out.update(kind="ham", path=calls, info_hex=info.hex())
        return out
    p = pus(s["pay"])
    if not p:
        out["kind"] = "ctrl"  # 制御フレーム(ペイロードなし)
        return out
    out.update(svc=p["svc"], sub=p["sub"])
    body = p["body"]
    if p["svc"] == 3 and p["sub"] in HK:
        name, fn, size = HK[p["sub"]]
        if len(body) != 4 + size:
            out.update(kind="hk-badlen", name=name, body_len=len(body))
            return out
        out.update(kind="hk", name=name, time=utc(struct.unpack(">I", body[:4])[0]), **{"data": fn(body[4:])})
    elif (p["svc"], p["sub"]) == (6, 8):
        size, crc = struct.unpack(">II", body[1:9])
        out.update(kind="file-init", transfer=body[0], size=size, crc32=hex(crc),
                   name=body[9:].decode("ascii", "replace"), blocks=-(-size // 160))
    elif (p["svc"], p["sub"]) == (6, 13):
        out.update(kind="file-block", transfer=body[0], block=struct.unpack(">H", body[1:3])[0], n=len(body) - 3)
    else:
        out.update(kind="other", body_hex=body.hex())
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("logs", nargs="+", help="gr_satellites のログ('-' で標準入力)")
    ap.add_argument("--json", action="store_true", help="1 行 1 JSON で出力")
    a = ap.parse_args()
    frames = []
    for f in a.logs:
        frames += load_frames(sys.stdin.read() if f == "-" else open(f, errors="replace").read())
    cnt = collections.Counter()
    blocks = collections.defaultdict(set)
    for b in frames:
        try:
            r = decode(b)
        except Exception as e:  # 壊れたフレームで全体を止めない
            r = {"kind": "error", "err": repr(e), "len": len(b)}
        k = r["kind"] + (":" + r["name"] if r.get("name") and r["kind"] == "hk" else "")
        cnt[k] += 1
        if r["kind"] == "file-block":
            blocks[r["transfer"]].add(r["block"])
        if a.json:
            print(json.dumps(r, ensure_ascii=False))
        elif r["kind"] in ("hk", "file-init", "ham"):
            print(r["kind"], r.get("name", ""), r.get("time", ""), json.dumps(r.get("data", {k: v for k, v in r.items()
                  if k not in ("kind", "vc", "len", "skylink_seq")}), ensure_ascii=False))
    print("# frames: %d  %s" % (len(frames), dict(cnt)), file=sys.stderr)
    for t, s in sorted(blocks.items()):
        print("# transfer %d: %d distinct blocks (%d..%d)" % (t, len(s), min(s), max(s)), file=sys.stderr)


if __name__ == "__main__":
    main()
