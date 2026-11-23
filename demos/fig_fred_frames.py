"""RGB vs events at the same instant, full frame and zoomed on the drone (sections 0 and 2).

    python fig_fred_frames.py --seq 188 [--t 42.0] [--window-ms 10]

Output: post/figures/rgb_vs_events_<seq>.png
"""
from __future__ import annotations

import argparse
import time

import cv2
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

import figstyle as fs
from fredkit import Sequence

fs.apply()

SURF = np.array([0xfc, 0xfc, 0xfb]) / 255
ON_RGB = np.array([0x2a, 0x78, 0xd6]) / 255
OFF_RGB = np.array([0xeb, 0x68, 0x34]) / 255


def event_image(ev, h=720, w=1280):
    img = np.tile(SURF, (h, w, 1))
    on = ev["p"] > 0
    img[ev["y"][~on], ev["x"][~on]] = OFF_RGB
    img[ev["y"][on], ev["x"][on]] = ON_RGB  # ON drawn last; overlap is rare at these rates
    return img


def pick_time(seq: Sequence) -> float:
    """Middle-of-sequence timestamp with the largest single annotated box."""
    b = seq.boxes
    area = (b[:, 3] - b[:, 1]) * (b[:, 4] - b[:, 2])
    mid = (b[:, 0] > np.percentile(b[:, 0], 20)) & (b[:, 0] < np.percentile(b[:, 0], 80))
    return float(b[mid][area[mid].argmax(), 0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default="188")
    ap.add_argument("--t", type=float, default=None, help="frame-clock time (s); default: largest box")
    ap.add_argument("--window-ms", type=float, default=10.0)
    args = ap.parse_args()
    t_start = time.time()

    seq = Sequence(args.seq)
    t = args.t if args.t is not None else pick_time(seq)
    t_rgb, rgb_path = seq.rgb_at(t)
    rgb = cv2.cvtColor(cv2.imread(str(rgb_path)), cv2.COLOR_BGR2RGB)
    w = args.window_ms / 1e3
    ev = seq.events(t - w / 2, t + w / 2)
    evimg = event_image(ev)
    box = seq.boxes_at(t)[0]
    x1, y1, x2, y2 = box
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    half = max(x2 - x1, y2 - y1) * 0.9
    zx = (int(max(cx - half, 0)), int(min(cx + half, 1279)))
    zy = (int(max(cy - half, 0)), int(min(cy + half, 719)))

    fig, axs = plt.subplots(2, 2, figsize=(10, 8.4), gridspec_kw={"height_ratios": [0.5625, 1], "hspace": 0.12, "wspace": 0.04})
    titles = [f"RGB frame (30 fps)", f"Events, {args.window_ms:g} ms window"]
    for col, (img, title) in enumerate(zip([rgb, evimg], titles)):
        ax = axs[0, col]
        ax.imshow(img)
        ax.add_patch(Rectangle((zx[0], zy[0]), zx[1] - zx[0], zy[1] - zy[0], fill=False, ec=fs.INK, lw=1.2))
        ax.set_title(title)
        z = axs[1, col]
        z.imshow(img[zy[0]:zy[1], zx[0]:zx[1]], interpolation="nearest")
        z.set_title("zoom on the drone", fontsize=11, fontweight="normal", color=fs.INK_2)
    for ax in axs.ravel():
        ax.set_xticks([]); ax.set_yticks([]); ax.grid(False)
        for sp in ax.spines.values():
            sp.set_visible(True); sp.set_color(fs.GRID)
    fig.text(0.0, 0.06, f"FRED seq {seq.id}, t = {t:.3f} s (RGB frame at {t_rgb:.3f} s). Events: blue = ON, orange = OFF, "
             f"{len(ev['t']):,} events in the window.", color=fs.INK_2, fontsize=9)
    out = fs.save(fig, f"rgb_vs_events_{seq.id}", script="demos/fig_fred_frames.py",
                  command=f"python fig_fred_frames.py --seq {seq.id} --t {t:.3f} --window-ms {args.window_ms:g}",
                  data=f"FRED seq {seq.id}", t=t, runtime_s=round(time.time() - t_start, 1))
    print("wrote", out, "t =", t, "events:", len(ev["t"]), "box:", box)


if __name__ == "__main__":
    main()
