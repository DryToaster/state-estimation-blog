"""Rotor periodicity in real FRED events (sections 3 and 4.2).

Reproduces the period-histogram RPM estimate from the rotation-informed KF paper (S.M., Habibiroudkenar
et al., 2026) inside one drone box, and compares the paper's OFF->ON interval with the full ON->ON period.

    python fig_rotor_clock.py --seq 188 [--t 40.8] [--window-ms 100]

Output: post/figures/rotor_clock_<seq>.png
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

import figstyle as fs
from fredkit import Sequence
from fig_fred_frames import pick_time

fs.apply()

BIN_MS = 0.1                     # paper: 0.1 ms bins over [0, 25.6] ms
EDGES_MS = np.arange(0, 25.6 + BIN_MS, BIN_MS)
SEQ_BLUE = LinearSegmentedColormap.from_list("seqblue", ["#fcfcfb", "#cde2fb", "#86b6ef", "#2a78d6", "#184f95", "#0d366b"])


def burst_starts(ev, box):
    """Per pixel inside `box`, the first event of each same-polarity run (one per blade edge).

    Returns (pixel_id, t_us, polarity) sorted by pixel then time.
    """
    x1, y1, x2, y2 = box
    m = (ev["x"] >= x1) & (ev["x"] <= x2) & (ev["y"] >= y1) & (ev["y"] <= y2)
    x, y, t, p = ev["x"][m].astype(np.int64), ev["y"][m].astype(np.int64), ev["t"][m], ev["p"][m]
    pid = y * 1280 + x
    order = np.lexsort((t, pid))
    pid, t, p = pid[order], t[order], p[order]
    new_run = np.ones(len(t), bool)
    new_run[1:] = (pid[1:] != pid[:-1]) | (p[1:] != p[:-1])
    return pid[new_run], t[new_run], p[new_run]


def intervals(pid, t, p, keep_pixels):
    """OFF->next-ON gaps (the paper's measurement) and ON->next-ON gaps (full period), in ms."""
    keep = np.isin(pid, keep_pixels)
    pid, t, p = pid[keep], t[keep], p[keep]
    same = pid[1:] == pid[:-1]
    off_on = same & (p[:-1] < 0) & (p[1:] > 0)
    d_off_on = (t[1:] - t[:-1])[off_on] / 1e3
    on = p > 0
    pid_on, t_on = pid[on], t[on]
    same_on = pid_on[1:] == pid_on[:-1]
    d_on_on = (t_on[1:] - t_on[:-1])[same_on] / 1e3
    return d_off_on, d_on_on


def peak_ms(d):
    h, _ = np.histogram(d, EDGES_MS)
    b = h.argmax()
    return (b + 0.5) * BIN_MS, h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default="188")
    ap.add_argument("--t", type=float, default=None)
    ap.add_argument("--window-ms", type=float, default=100.0, help="paper: 100 ms FIFO")
    ap.add_argument("--blades", type=int, default=2)
    args = ap.parse_args()
    t_start = time.time()

    seq = Sequence(args.seq)
    t = args.t if args.t is not None else pick_time(seq)
    w = args.window_ms / 1e3
    ev = seq.events(t - w, t)
    box = seq.boxes_at(t)[0]
    x1, y1, x2, y2 = [int(round(v)) for v in box]

    # (a) per-pixel event count map ("frequency map" F(x, y)) and the 70th-percentile propeller mask
    m = (ev["x"] >= x1) & (ev["x"] <= x2) & (ev["y"] >= y1) & (ev["y"] <= y2)
    F = np.zeros((y2 - y1 + 1, x2 - x1 + 1))
    np.add.at(F, (ev["y"][m] - y1, ev["x"][m] - x1), 1)
    thr = np.percentile(F[F > 0], 70)
    mask = F > thr
    keep_pixels = (np.nonzero(mask)[0] + y1) * 1280 + (np.nonzero(mask)[1] + x1)

    pid, tb, pb = burst_starts(ev, (x1, y1, x2, y2))
    d_off_on, d_on_on = intervals(pid, tb, pb, keep_pixels)
    T_paper, h_paper = peak_ms(d_off_on)
    T_full, h_full = peak_ms(d_on_on)
    rpm = lambda T_ms: 60.0 / (T_ms / 1e3 * args.blades)

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.4), gridspec_kw={"width_ratios": [1, 1.6], "wspace": 0.45})
    im = a.imshow(F, cmap=SEQ_BLUE, interpolation="nearest")
    a.contour(mask, levels=[0.5], colors=[fs.INK], linewidths=0.8)
    a.set_title(f"Events per pixel in {args.window_ms:g} ms")
    a.set_xticks([]); a.set_yticks([]); a.grid(False)
    cb = fig.colorbar(im, ax=a, fraction=0.046, pad=0.03)
    cb.outline.set_visible(False)
    a.text(0, -0.08, "outline: pixels above the 70th percentile\n(the paper's propeller mask)", transform=a.transAxes,
           va="top", fontsize=9, color=fs.INK_2)

    centers = EDGES_MS[:-1] + BIN_MS / 2
    b.step(centers, h_full, where="mid", color=fs.BLUE, label="ON → next ON (full period)")
    b.step(centers, h_paper, where="mid", color=fs.ORANGE, label="OFF → next ON (paper's interval)")
    for T, col, h in [(T_full, fs.BLUE, h_full), (T_paper, fs.ORANGE, h_paper)]:
        b.annotate(f"{T:.2f} ms\n≈ {1e3 / T:.0f} Hz, {rpm(T):,.0f} RPM", xy=(T, h.max()), xytext=(8, -4),
                   textcoords="offset points", fontsize=9.5, color=fs.INK, va="top")
    b.set_xlim(0, 12)
    b.set_xlabel("interval at the same pixel (ms), 0.1 ms bins")
    b.set_ylabel("count")
    b.set_title("Period histogram over the propeller pixels")
    b.legend(loc="center right")
    fig.text(0.0, -0.06, f"FRED seq {seq.id}, {args.window_ms:g} ms ending at t = {t:.3f} s. RPM assumes {args.blades}-blade "
             f"props (RPM = 60 / (T · N_b)). Only the first event of each same-polarity burst per pixel is used.",
             color=fs.INK_2, fontsize=9)
    out = fs.save(fig, f"rotor_clock_{seq.id}", script="demos/fig_rotor_clock.py",
                  command=f"python fig_rotor_clock.py --seq {seq.id} --t {t:.3f} --window-ms {args.window_ms:g}",
                  data=f"FRED seq {seq.id}", t=t, T_full_ms=T_full, T_paper_ms=T_paper,
                  runtime_s=round(time.time() - t_start, 1))
    print("wrote", out, f"| full period {T_full:.2f} ms ({rpm(T_full):.0f} RPM) | paper interval {T_paper:.2f} ms "
          f"({rpm(T_paper):.0f} RPM) | n_on_on={len(d_on_on)} n_off_on={len(d_off_on)}")


if __name__ == "__main__":
    main()
