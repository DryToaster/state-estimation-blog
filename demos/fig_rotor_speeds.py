"""Four rotors, four speeds: per-rotor blade-pass frequency over time on FRED (sections 3 and 4.1).

Events are stabilized with the annotated box track (see fig_rotor_spectrum.py), the box is split into
quadrants (one rotor each, for a quad seen roughly from below), and each quadrant's mean per-pixel
spectrum is peak-picked in sliding windows.

    python fig_rotor_speeds.py --seq 188 [--t0 30 --t1 50] [--window-ms 200 --step-ms 100]

Output: post/figures/rotor_speeds_<seq>.png
"""
from __future__ import annotations

import argparse
import time

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

import figstyle as fs
from fredkit import Sequence
from fig_rotor_spectrum import stabilized, onsets, BIN_US

fs.apply()
QUADS = ["TL", "TR", "BL", "BR"]
# diagonal pairs share a colour (they spin the same direction on a quad); solid/dashed separate members
STYLE = {"TL": (fs.BLUE, "-"), "BR": (fs.BLUE, (0, (4, 2))), "TR": (fs.ORANGE, "-"), "BL": (fs.ORANGE, (0, (4, 2)))}


def quadrant_peaks(seq, t1, w, fmin=250.0, fmax=1000.0, pad=4):
    t0 = t1 - w
    bx = seq.boxes_at(t1)
    if len(bx) == 0:
        return None
    box = [int(round(v)) for v in bx[0]]
    x, y, t, p = stabilized(seq, t0, t1)
    pid, to, _ = onsets(x, y, t, p, box)
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    px, py = pid % 4096, pid // 4096
    n = int(w * 1e6 // BIN_US)
    f = np.fft.rfftfreq(n * pad, BIN_US / 1e6)
    band = (f > fmin) & (f < fmax)
    out = {}
    for name, q in zip(QUADS, [(px < cx) & (py < cy), (px >= cx) & (py < cy), (px < cx) & (py >= cy), (px >= cx) & (py >= cy)]):
        ids, c = np.unique(pid[q], return_counts=True)
        if len(ids) < 20:
            out[name] = np.nan
            continue
        prop = ids[c > np.percentile(c, 70)]
        sel = q & np.isin(pid, prop)
        tr = np.zeros((len(prop), n), np.float32)
        np.add.at(tr, (np.searchsorted(prop, pid[sel]), np.clip(((to[sel] - t0 * 1e6) // BIN_US).astype(int), 0, n - 1)), 1)
        tr -= tr.mean(1, keepdims=True)
        P = (np.abs(np.fft.rfft(tr * np.hanning(n), n=n * pad, axis=1)) ** 2).mean(0)
        k = np.flatnonzero(band)[P[band].argmax()]
        out[name] = f[k]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default="188")
    ap.add_argument("--t0", type=float, default=30.0)
    ap.add_argument("--t1", type=float, default=50.0)
    ap.add_argument("--window-ms", type=float, default=200.0)
    ap.add_argument("--step-ms", type=float, default=100.0)
    ap.add_argument("--blades", type=int, default=2)
    ap.add_argument("--note", action="append", default=[], help="'t:text' annotation, repeatable")
    args = ap.parse_args()
    args.notes = [(float(n.split(":", 1)[0]), n.split(":", 1)[1]) for n in args.note]
    t_start = time.time()
    seq = Sequence(args.seq)
    w = args.window_ms / 1e3
    ts = np.arange(args.t0 + w, args.t1, args.step_ms / 1e3)
    from figstyle import ROOT
    cache = ROOT / "cache" / f"rotor_speeds_{seq.id}_{args.t0:g}_{args.t1:g}_{args.window_ms:g}_{args.step_ms:g}.npy"
    if cache.exists():
        F = np.load(cache)
    else:
        rows = []
        for t in ts:
            r = quadrant_peaks(seq, t, w)
            rows.append([r[q] if r else np.nan for q in QUADS])
        F = np.array(rows)
        cache.parent.mkdir(exist_ok=True)
        np.save(cache, F)

    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 4.6), gridspec_kw={"width_ratios": [1, 4.2], "wspace": 0.28})
    # key: which quadrant is which line
    a.set_aspect("equal"); a.axis("off")
    for name, (xx, yy) in zip(QUADS, [(0, 1), (1, 1), (0, 0), (1, 0)]):
        col, ls = STYLE[name]
        a.add_patch(Circle((xx, yy), 0.38, fill=False, ec=col, lw=2, ls=ls))
        a.text(xx, yy, name, ha="center", va="center", fontsize=10, color=fs.INK)
    a.plot([0.25, 0.75], [0.25, 0.75], color=fs.GRID, lw=6, solid_capstyle="round", zorder=0)
    a.plot([0.25, 0.75], [0.75, 0.25], color=fs.GRID, lw=6, solid_capstyle="round", zorder=0)
    a.set_xlim(-0.5, 1.5); a.set_ylim(-0.6, 1.8)
    a.text(0.5, 1.62, "rotors (box quadrants)", ha="center", fontsize=10, color=fs.INK_2)

    for i, name in enumerate(QUADS):
        col, ls = STYLE[name]
        b.plot(ts, F[:, i], color=col, ls=ls, lw=1.6, label=name)
    b.set_xlabel("time (s)")
    b.set_ylabel("blade-pass frequency (Hz)")
    b.set_title("Each rotor's blade-pass frequency, measured from events")
    sec = b.secondary_yaxis("right", functions=(lambda hz: hz * 60 / args.blades, lambda rpm: rpm * args.blades / 60))
    sec.set_ylabel(f"RPM ({args.blades}-blade)", color=fs.INK_2)
    sec.spines["right"].set_visible(False)
    b.legend(loc="lower left", ncol=4, handlelength=2.4)
    lo, hi = np.nanpercentile(F, [1, 99])
    b.set_ylim(lo - 40, hi + 90)
    for i, (x, txt) in enumerate(args.notes):
        b.annotate(txt, xy=(x, hi + (25 if i % 2 else 60)), ha="center", va="bottom", fontsize=9, color=fs.INK_2,
                   bbox=dict(fc=fs.SURFACE, ec="none", pad=1))
        b.axvline(x, color=fs.INK_2, lw=0.8, ls=(0, (1, 2)), zorder=0)
    b.set_xlim(ts[0], ts[-1])
    fig.text(0.0, -0.04, f"FRED seq {seq.id} ({seq.models.get(1, '')}). {args.window_ms:g} ms windows every {args.step_ms:g} ms; "
             "same colour = diagonal pair (same spin direction on a quad).",
             color=fs.INK_2, fontsize=9)
    out = fs.save(fig, f"rotor_speeds_{seq.id}", script="demos/fig_rotor_speeds.py",
                  command=f"python fig_rotor_speeds.py --seq {seq.id} --t0 {args.t0:g} --t1 {args.t1:g}",
                  data=f"FRED seq {seq.id}", runtime_s=round(time.time() - t_start, 1))
    np.savetxt(out.with_suffix(".csv"), np.c_[ts, F], delimiter=",", header="t_s," + ",".join(QUADS), fmt="%.3f")
    print("wrote", out, "runtime", round(time.time() - t_start, 1), "s")


if __name__ == "__main__":
    main()
