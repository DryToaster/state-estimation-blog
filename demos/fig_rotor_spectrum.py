"""What a rotor pixel really does, on FRED data (section 3): event raster + per-pixel spectrum.

The drone moves, so events are first shifted into the drone's frame using the annotated box track
(linearly interpolated between the 30 Hz boxes). Each pixel's train of burst onsets (the first event of
each same-polarity run) is binned at 0.1 ms and Fourier-transformed; the per-pixel power spectra are
averaged, so pixels whose blades pass at different phases don't cancel.

    python fig_rotor_spectrum.py --seq 188 [--t 40.8] [--window-ms 200]

Output: post/figures/rotor_spectrum_<seq>.png
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import matplotlib.pyplot as plt

import figstyle as fs
from fredkit import Sequence

fs.apply()
BIN_US = 100  # 0.1 ms -> 10 kHz sampling, Nyquist 5 kHz


def stabilized(seq, t0, t1):
    """Events in [t0, t1) with x, y shifted so the drone's box centre stays where it is at t1."""
    ev = seq.events(t0, t1)
    b = seq.boxes
    b = b[np.r_[True, np.diff(b[:, 0]) > 0]]  # first box per timestamp (single-drone sequence)
    cx, cy = (b[:, 1] + b[:, 3]) / 2, (b[:, 2] + b[:, 4]) / 2
    ts = ev["t"] / 1e6
    dx = np.interp(t1, b[:, 0], cx) - np.interp(ts, b[:, 0], cx)
    dy = np.interp(t1, b[:, 0], cy) - np.interp(ts, b[:, 0], cy)
    x = np.round(ev["x"] + dx).astype(np.int64)
    y = np.round(ev["y"] + dy).astype(np.int64)
    return x, y, ev["t"], ev["p"]


def onsets(x, y, t, p, box):
    x1, y1, x2, y2 = box
    m = (x >= x1) & (x <= x2) & (y >= y1) & (y <= y2)
    pid = y[m] * 4096 + x[m]
    t, p = t[m], p[m]
    o = np.lexsort((t, pid))
    pid, t, p = pid[o], t[o], p[o]
    keep = np.r_[True, (pid[1:] != pid[:-1]) | (p[1:] != p[:-1])]
    return pid[keep], t[keep], p[keep]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default="188")
    ap.add_argument("--t", type=float, default=40.8)
    ap.add_argument("--window-ms", type=float, default=200.0)
    ap.add_argument("--raster-ms", type=float, default=15.0)
    ap.add_argument("--blades", type=int, default=2)
    args = ap.parse_args()
    t_start = time.time()

    seq = Sequence(args.seq)
    t1 = args.t
    t0 = t1 - args.window_ms / 1e3
    box = [int(round(v)) for v in seq.boxes_at(t1)[0]]
    x, y, t, p = stabilized(seq, t0, t1)
    pid, to, po = onsets(x, y, t, p, box)

    # propeller pixels: top 30% by onset count (as in the rotation-informed KF paper's 70th-percentile mask)
    ids, counts = np.unique(pid, return_counts=True)
    prop = ids[counts > np.percentile(counts, 70)]

    # per-pixel binned onset trains -> mean power spectrum
    n_bins = int(args.window_ms * 1e3 // BIN_US)
    sel = np.isin(pid, prop)
    row = np.searchsorted(prop, pid[sel])
    col = np.clip(((to[sel] - t0 * 1e6) // BIN_US).astype(int), 0, n_bins - 1)
    trains = np.zeros((len(prop), n_bins), np.float32)
    np.add.at(trains, (row, col), 1)
    trains -= trains.mean(1, keepdims=True)
    win = np.hanning(n_bins).astype(np.float32)
    P = (np.abs(np.fft.rfft(trains * win, axis=1)) ** 2).mean(0)
    f = np.fft.rfftfreq(n_bins, BIN_US / 1e6)
    P /= P[f > 20].max()
    band = (f > 100) & (f < 2000)
    f0 = f[band][P[band].argmax()]

    fig, (a, b) = plt.subplots(2, 1, figsize=(9, 7.2), gridspec_kw={"hspace": 0.55, "height_ratios": [1, 1.1]})

    # (a) raster: the busiest propeller pixels over the last raster-ms
    busiest = prop[np.argsort(counts[np.isin(ids, prop)])[::-1][:16]]
    r0 = t1 * 1e6 - args.raster_ms * 1e3
    for k, q in enumerate(busiest):
        m = (pid == q) & (to >= r0)
        tt, pp = (to[m] - r0) / 1e3, po[m]
        a.vlines(tt[pp > 0], k - 0.4, k + 0.4, color=fs.ON, lw=1.6)
        a.vlines(tt[pp < 0], k - 0.4, k + 0.4, color=fs.OFF, lw=1.6)
    a.set_xlim(0, args.raster_ms)
    a.set_ylim(-0.8, len(busiest) - 0.2)
    a.set_yticks([])
    a.grid(axis="y", visible=False)
    a.set_xlabel("time (ms)")
    a.set_ylabel(f"{len(busiest)} rotor pixels")
    a.set_title(f"Real rotor pixels, {args.raster_ms:g} ms of events")
    from matplotlib.lines import Line2D
    a.legend(handles=[Line2D([], [], color=fs.ON, lw=2, label="ON"), Line2D([], [], color=fs.OFF, lw=2, label="OFF")],
             loc="upper right", bbox_to_anchor=(1.0, 1.22), ncol=2, handlelength=1.0)

    # (b) spectrum
    b.axvspan(f[1], 15, color=fs.BAND[0], lw=0, zorder=0)
    b.text(16.5, 0.6, "everything a 30 fps\ncamera can represent\n(0–15 Hz)", color=fs.INK_2, fontsize=9.5, va="center")
    b.plot(f[1:], P[1:], color=fs.BLUE, lw=1.4)
    for h in range(1, 7):
        if h * f0 < f[-1]:
            b.axvline(h * f0, color=fs.INK_2, lw=0.8, ls=(0, (1, 2)), zorder=0)
    rpm = f0 * 60 / args.blades
    b.annotate(f"blade-pass {f0:.0f} Hz\n≈ {rpm:,.0f} RPM ({args.blades}-blade)", xy=(f0, 1.0), xytext=(-12, 0),
               textcoords="offset points", ha="right", va="top", fontsize=9.5, color=fs.INK)
    b.text(2 * f0 * 1.04, 0.93, "harmonics", color=fs.INK_2, fontsize=9.5, va="top")
    b.set_xscale("log")
    b.set_xlim(f[1], f[-1])
    b.set_ylim(0, 1.08)
    b.set_xlabel("frequency (Hz)")
    b.set_ylabel("power (normalized)")
    b.set_title("Mean per-pixel spectrum of the propeller pixels")
    model = seq.models.get(1, "")
    fig.text(0.0, -0.01, f"FRED seq {seq.id} ({model}), {args.window_ms:g} ms ending at t = {t1:.3f} s, events stabilized "
             f"with the annotated box track. {len(prop):,} propeller pixels; onset trains binned at {BIN_US / 1e3:g} ms.",
             color=fs.INK_2, fontsize=9, wrap=True)
    out = fs.save(fig, f"rotor_spectrum_{seq.id}", script="demos/fig_rotor_spectrum.py",
                  command=f"python fig_rotor_spectrum.py --seq {seq.id} --t {t1:.3f} --window-ms {args.window_ms:g}",
                  data=f"FRED seq {seq.id}", f0_hz=float(f0), runtime_s=round(time.time() - t_start, 1))
    print("wrote", out, f"f0={f0:.1f} Hz rpm={rpm:.0f} pixels={len(prop)}")


if __name__ == "__main__":
    main()
