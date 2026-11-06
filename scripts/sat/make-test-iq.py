#!/usr/bin/env python3
"""Make a synthetic IQ recording to test the P1 pipeline (iq-analyze.py -> gr-satellites).

It takes the FM-demodulated audio of a SatNOGS observation (a WAV, CC BY-SA,
kept out of the repo), re-modulates it as FM on a carrier that follows the
real Doppler of a pass, adds noise and 8-bit quantization like rtl_sdr, and
writes <out>.u8 + <out>.json in the format sat-window.sh produces.

If the Doppler sign, the timing or the file format of iq-analyze.py were
wrong, the packets would not decode from this file.

    python3 make-test-iq.py control.wav /tmp/test --norad 43804 --start-epoch 1793...
        [--snr-db 15] [--duration 178] [--tx-mhz 437.775]

The Doppler here is computed from the radial velocity (position . velocity),
independently of iq-analyze.py, which differences the range.
"""
import argparse, datetime, json, os, sys, wave

import numpy as np
from skyfield.api import EarthSatellite, load, wgs84

C = 299792458.0
UTC = datetime.timezone.utc


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("wav")
    ap.add_argument("out", help="output prefix")
    ap.add_argument("--norad", type=int, required=True)
    ap.add_argument("--start-epoch", type=float, required=True)
    ap.add_argument("--home", default=os.path.expanduser("~/sat"))
    ap.add_argument("--tx-mhz", type=float, default=437.775)
    ap.add_argument("--centre-mhz", type=float, help="default: same as --tx-mhz")
    ap.add_argument("--rate", type=float, default=250000)
    ap.add_argument("--snr-db", type=float, default=15.0, help="signal to noise in a 12 kHz band")
    ap.add_argument("--noise-lsb", type=float, default=6.0, help="noise sigma per I/Q component, in 8-bit LSB")
    ap.add_argument("--deviation", type=float, default=2400.0, help="FM deviation for the audio's plateau level (Hz)")
    ap.add_argument("--duration", type=float, default=0, help="seconds of audio to use (default: all)")
    ap.add_argument("--no-doppler", action="store_true")
    ap.add_argument("--burst", help="LEN:PERIOD in seconds, e.g. 0.15:30 = a 0.15 s burst every 30 s "
                    "(the first after 5 s); default: transmit continuously")
    args = ap.parse_args()

    w = wave.open(args.wav)
    afs = w.getframerate()
    audio = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64) / 32768.0
    if w.getnchannels() > 1:
        audio = audio[:: w.getnchannels()]
    if args.duration:
        audio = audio[: int(args.duration * afs)]
    dur = len(audio) / afs
    plateau = np.percentile(np.abs(audio), 95)
    audio = audio / plateau  # +-1 = symbol plateau
    print(f"audio {dur:.1f} s at {afs} Hz, plateau {plateau:.3f}", file=sys.stderr)

    ts = load.timescale()
    lines = [l.rstrip() for l in open(os.path.join(args.home, "tle", f"{args.norad}.tle")).read().splitlines() if l.strip()]
    sat = EarthSatellite(lines[1], lines[2], lines[0].strip(), ts)
    loc = json.load(open(os.path.join(args.home, "location.json")))
    here = wgs84.latlon(loc["lat"], loc["lon"], elevation_m=loc.get("elev_m", 30.0))

    f_tx = args.tx_mhz * 1e6
    f_c = (args.centre_mhz or args.tx_mhz) * 1e6
    rate = args.rate
    n_total = int(dur * rate)
    base = datetime.datetime.fromtimestamp(args.start_epoch, UTC)

    # Doppler on a 1 s grid from the radial velocity: approaching (vr < 0) -> received higher
    gsec = np.arange(int(dur) + 3, dtype=np.float64) - 1
    st = ts.utc(base.year, base.month, base.day, base.hour, base.minute, base.second + base.microsecond / 1e6 + gsec)
    topo = (sat - here).at(st)
    pos = topo.position.km
    vel = topo.velocity.km_per_s
    vr = (pos * vel).sum(axis=0) / np.sqrt((pos ** 2).sum(axis=0)) * 1000.0
    shift = np.zeros_like(vr) if args.no_doppler else -f_tx * vr / C
    alt = topo.altaz()[0].degrees
    print(f"synthetic pass: elevation {alt[1]:.1f} -> {alt[-2]:.1f} deg, Doppler {shift[1]/1e3:+.2f} -> {shift[-2]/1e3:+.2f} kHz", file=sys.stderr)

    # amplitude from the requested SNR: noise power in 12 kHz = 2*sigma^2*12k/rate (complex, per-sample var 2*sigma^2)
    sig_lsb = args.noise_lsb
    noise_var = 2 * sig_lsb ** 2
    snr = 10 ** (args.snr_db / 10)
    amp = np.sqrt(snr * noise_var * 12000 / rate)
    print(f"signal amplitude {amp:.2f} LSB vs noise {sig_lsb} LSB per component", file=sys.stderr)

    rng = np.random.default_rng(1)
    chunk = int(rate * 5)
    ph = 0.0
    with open(args.out + ".u8", "wb") as f:
        for s in range(0, n_total, chunk):
            n = min(chunk, n_total - s)
            t = (s + np.arange(n)) / rate
            a = np.interp(t, np.arange(len(audio)) / afs, audio)
            inst = (f_tx - f_c) + np.interp(t, gsec, shift) + args.deviation * a
            p = ph + 2 * np.pi * np.cumsum(inst) / rate
            ph = p[-1]
            gate = 1.0
            if args.burst:
                blen, bper = (float(v) for v in args.burst.split(":"))
                gate = (((t - 5.0) % bper) < blen) & (t >= 5.0)
            x = amp * gate * np.exp(1j * p) + sig_lsb * (rng.standard_normal(n) + 1j * rng.standard_normal(n))
            iq = np.empty(2 * n, dtype=np.uint8)
            iq[0::2] = np.clip(np.round(x.real + 127.5), 0, 255)
            iq[1::2] = np.clip(np.round(x.imag + 127.5), 0, 255)
            iq.tofile(f)
    meta = dict(name="synthetic", freq_hz=f_c, samp_rate=rate, gain_db=None, duration_s=dur,
                t_launch_epoch=args.start_epoch, t_end_epoch=args.start_epoch + dur,
                bytes=os.path.getsize(args.out + ".u8"), rc=0, dry=True)
    json.dump(meta, open(args.out + ".json", "w"))
    print(f"wrote {args.out}.u8 / .json", file=sys.stderr)


if __name__ == "__main__":
    main()
