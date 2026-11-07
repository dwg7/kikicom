#!/usr/bin/env python3
"""Look at an IQ recording from a satellite window (P1) and prepare it for gr-satellites.

Runs on the RPi under the "sat" python (numpy + skyfield):
    python3 iq-analyze.py ~/sat/iq/SUOMI-100-<stamp>.u8 --norad 43804

It reads <file>.json (written by sat-window.sh), predicts the Doppler shift
along the recorded pass from the TLE, and

  1. report: per 100 ms frame (the dongle's DC spike at 0 Hz is left out), the power in a 12 kHz band that follows the
     predicted Doppler vs. the power in reference bands 15-40 kHz to either
     side. A real GMSK burst shows up as a few frames well above the rest.
     Also the satellite's azimuth/elevation during the recording.
  2. writes <file>.dc.cf32: complex float32 with the Doppler removed (the
     signal sits at 0 Hz), ready for
         gr_satellites "Suomi 100" --rawfile X.dc.cf32 --iq --samp_rate 250000

Sign convention: a satellite that approaches is received ABOVE its transmit
frequency (shift = -f * range_rate / c, range_rate < 0 on approach).
"""
import argparse, datetime, json, os, sys

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84

C = 299792458.0
JST = datetime.timezone(datetime.timedelta(hours=9))
UTC = datetime.timezone.utc
FRAME_S = 0.1
CHUNK_S = 10.0
DC_NOTCH_HZ = 1500.0  # ignore bins this close to 0 Hz (the dongle's DC spike, +20-30 dB)


def load_sat(path, ts):
    lines = [l.rstrip() for l in open(path).read().splitlines() if l.strip()]
    return EarthSatellite(lines[1], lines[2], lines[0].strip(), ts)


def skytimes(ts, epoch_array):
    """skyfield Time for an array of unix epochs (UTC)."""
    base = datetime.datetime.fromtimestamp(float(epoch_array[0]), UTC)
    secs = base.second + base.microsecond / 1e6 + (np.asarray(epoch_array) - epoch_array[0])
    return ts.utc(base.year, base.month, base.day, base.hour, base.minute, secs)


def doppler_track(sat, here, ts, t0, dur, f_tx):
    """Return (grid_epochs, shift_hz, alt_deg, az_deg) on a 1 s grid over [t0-2, t0+dur+2]."""
    grid = t0 - 2 + np.arange(int(dur) + 5, dtype=np.float64)
    diff = sat - here
    r_minus = diff.at(skytimes(ts, grid - 0.5)).distance().m
    r_plus = diff.at(skytimes(ts, grid + 0.5)).distance().m
    rdot = (r_plus - r_minus) / 1.0
    alt, az, _ = diff.at(skytimes(ts, grid)).altaz()
    return grid, -f_tx * rdot / C, alt.degrees, az.degrees


def read_chunks(path, rate, chunk_s):
    n = int(rate * chunk_s)
    with open(path, "rb") as f:
        while True:
            a = np.fromfile(f, dtype=np.uint8, count=2 * n)
            if a.size < 2:
                return
            a = a[: a.size // 2 * 2].astype(np.float32) - 127.5
            yield a[0::2] + 1j * a[1::2]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("iq", help="<name>.u8 from sat-window.sh")
    ap.add_argument("--norad", type=int, required=True)
    ap.add_argument("--home", default=os.path.expanduser("~/sat"))
    ap.add_argument("--tle", help="default: <home>/tle/<norad>.tle")
    ap.add_argument("--tx-mhz", type=float, help="satellite transmit frequency (default: recording centre)")
    ap.add_argument("--start-epoch", type=float, help="override the time of the first sample (unix, UTC)")
    ap.add_argument("--no-correct", action="store_true", help="skip writing the Doppler-corrected file")
    args = ap.parse_args()

    meta = json.load(open(os.path.splitext(args.iq)[0] + ".json"))
    rate = float(meta["samp_rate"])
    f_center = float(meta["freq_hz"])
    f_tx = args.tx_mhz * 1e6 if args.tx_mhz else f_center
    nsamp = os.path.getsize(args.iq) // 2
    dur = nsamp / rate
    # first sample: counting back from the end is more accurate than the launch time
    t0 = args.start_epoch if args.start_epoch else float(meta["t_end_epoch"]) - dur
    print(f"file {os.path.basename(args.iq)}: {nsamp} samples, {dur:.1f} s at {rate:.0f} S/s, centre {f_center/1e6:.4f} MHz, gain {meta.get('gain_db')} dB")
    print(f"first sample {datetime.datetime.fromtimestamp(t0, JST):%Y-%m-%d %H:%M:%S.%f} JST"
          f"  (launch-based estimate differs by {float(meta['t_launch_epoch']) - t0:+.1f} s)")

    ts = load.timescale()
    sat = load_sat(args.tle or os.path.join(args.home, "tle", f"{args.norad}.tle"), ts)
    loc = json.load(open(os.path.join(args.home, "location.json")))
    here = wgs84.latlon(loc["lat"], loc["lon"], elevation_m=loc.get("elev_m", 30.0))
    print(f"TLE epoch {sat.epoch.utc_strftime('%Y-%m-%d %H:%M')} UTC, {(ts.from_datetime(datetime.datetime.fromtimestamp(t0, UTC)).tt - sat.epoch.tt):.1f} days old at the recording")

    grid, shift, alt, az = doppler_track(sat, here, ts, t0, dur, f_tx)
    off_nominal = f_tx - f_center  # where the transmitter sits relative to the tuner centre

    def offset_at(t):  # baseband offset (Hz) of the signal at unix times t
        return off_nominal + np.interp(t, grid, shift)

    print("pass geometry during the recording:")
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        t = t0 + frac * dur
        i = int(np.argmin(np.abs(grid - t)))
        print(f"  {datetime.datetime.fromtimestamp(t, JST):%H:%M:%S}  el {alt[i]:5.1f}  az {az[i]:5.1f}  Doppler {shift[i]/1e3:+6.2f} kHz")
    s_first, s_last = shift[int(np.argmin(np.abs(grid - t0)))], shift[int(np.argmin(np.abs(grid - (t0 + dur))))]
    if (alt[0] > 0 and s_first < s_last) and not (s_first > s_last):
        print("warning: Doppler does not decrease during the pass; check the sign", file=sys.stderr)

    nfft = 2048
    fs_bin = rate / nfft
    frame_n = int(rate * FRAME_S)
    sub = frame_n // nfft
    window = np.hanning(nfft).astype(np.float32)
    ratios, times = [], []
    phase = 0.0
    out = None if args.no_correct else open(os.path.splitext(args.iq)[0] + ".dc.cf32", "wb")
    done = 0
    for x in read_chunks(args.iq, rate, CHUNK_S):
        n = x.size
        t = t0 + (done + np.arange(n)) / rate
        # frames on the uncorrected signal
        nf = n // frame_n
        if nf:
            blk = x[: nf * frame_n].reshape(nf, frame_n)[:, : sub * nfft].reshape(nf, sub, nfft) * window
            p = (np.abs(np.fft.fftshift(np.fft.fft(blk, axis=2), axes=2)) ** 2).mean(axis=1)  # (nf, nfft)
            tf = t0 + (done + (np.arange(nf) + 0.5) * frame_n) / rate
            offs = offset_at(tf)
            pm = p.copy()
            pm[:, abs(np.arange(nfft) - nfft // 2) * fs_bin < DC_NOTCH_HZ] = np.nan  # RTL-SDR's DC spike
            for k in range(nf):
                c = int(round(offs[k] / fs_bin)) + nfft // 2
                w_in, lo1, lo2 = int(6000 / fs_bin), int(15000 / fs_bin), int(40000 / fs_bin)
                inb = np.nanmean(pm[k, c - w_in: c + w_in + 1])
                ref = np.nanmean(np.concatenate([pm[k, c - lo2: c - lo1], pm[k, c + lo1: c + lo2]]))
                ratios.append(10 * np.log10(inb / ref))
                times.append(tf[k])
        if out is not None:
            ph = phase + 2 * np.pi * np.cumsum(offset_at(t)) / rate
            phase = ph[-1]
            (x * np.exp(-1j * ph)).astype(np.complex64).tofile(out)
        done += n
    if out is not None:
        out.close()
        print(f"wrote {os.path.splitext(args.iq)[0] + '.dc.cf32'} ({done * 8 / 1e6:.0f} MB, Doppler removed)")

    r, tt = np.array(ratios), np.array(times)
    med = float(np.median(r))
    sig = float(1.4826 * np.median(np.abs(r - med))) or 1e-9
    z = (r - med) / sig
    print(f"\nin-band vs reference band over {len(r)} frames of {FRAME_S*1000:.0f} ms: median {med:+.2f} dB, robust sigma {sig:.2f} dB")
    print(f"frames > 4 sigma: {int((z > 4).sum())}   > 6 sigma: {int((z > 6).sum())}")
    print("strongest frames:")
    for k in np.argsort(-r)[:8]:
        print(f"  {datetime.datetime.fromtimestamp(tt[k], JST):%H:%M:%S.%f}  {r[k]:+6.2f} dB  ({z[k]:+.1f} sigma)")
    hits = np.where(z > 4)[0]
    groups = []
    for k in hits:
        if groups and tt[k] - tt[groups[-1][-1]] < 1.0:
            groups[-1].append(k)
        else:
            groups.append([k])
    print(f"bursts (frames > 4 sigma, merged within 1 s), in time order: {len(groups)}")
    prev = None
    for g in groups:
        kk = max(g, key=lambda k: r[k])
        gap = "" if prev is None else f"  (+{tt[kk] - prev:.1f} s)"
        print(f"  {datetime.datetime.fromtimestamp(tt[g[0]], JST):%H:%M:%S.%f}  {r[kk]:+5.2f} dB  {z[kk]:+5.1f} sigma  {len(g)} frame(s){gap}")
        prev = tt[kk]
    print("timeline (max sigma in each 10 s):")
    row = []
    for i in range(int(np.ceil(dur / 10))):
        m = (tt >= t0 + 10 * i) & (tt < t0 + 10 * (i + 1))
        row.append(f"{datetime.datetime.fromtimestamp(t0 + 10 * i, JST):%H:%M:%S} {z[m].max():+5.1f}" if m.any() else "")
    for i in range(0, len(row), 4):
        print("  " + "   ".join(row[i:i + 4]))


if __name__ == "__main__":
    main()
