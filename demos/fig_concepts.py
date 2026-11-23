"""Concept figures that need no dataset (sections 3 and 4).

    python fig_concepts.py

Outputs:
    post/figures/aliasing_sim.png    what a rotor pixel does vs what a 30 fps camera reports (simulated)
    post/figures/range_regimes.png   pixels across drone / rotor vs range, with the three papers' regimes
"""
from __future__ import annotations

import time

import numpy as np
import matplotlib.pyplot as plt

import figstyle as fs

fs.apply()


# ---------------------------------------------------------------- aliasing ---------------------------------
def blade_pixel(t, f_bp=200.0, duty=0.2, contrast=0.6):
    """Intensity at one pixel as dark blades pass: 1 (sky) dropping to 1-contrast for `duty` of each period."""
    phase = (t * f_bp) % 1.0
    return np.where(phase < duty, 1.0 - contrast, 1.0)


def events_from_intensity(t, I, C=0.25):
    """Ideal DVS: emit an event each time log-intensity moves C away from the pixel's reference."""
    L = np.log(I)
    ref = L[0]
    on, off = [], []
    for ti, li in zip(t, L):
        while li - ref >= C:
            ref += C
            on.append(ti)
        while ref - li >= C:
            ref -= C
            off.append(ti)
    return np.array(on), np.array(off)


def frame_samples(f_bp, fps=30.0, t_exp=0.010, T=1.0, n_sub=400):
    """Mean intensity over each exposure window starting at k/fps."""
    starts = np.arange(0, T, 1 / fps)
    vals = [blade_pixel(np.linspace(s, s + t_exp, n_sub), f_bp).mean() for s in starts]
    return starts, np.array(vals)


def fig_aliasing():
    f_bp = 200.0
    fig, (a, b) = plt.subplots(2, 1, figsize=(8, 6.0), gridspec_kw={"hspace": 0.55})
    from matplotlib.lines import Line2D

    # (a) 30 ms close-up: the pixel's true intensity and the events it produces.
    t = np.linspace(0, 0.030, 30001)
    I = blade_pixel(t, f_bp)
    on, off = events_from_intensity(t, I)
    a.plot(t * 1e3, I, color=fs.INK_2, lw=1.4)
    a.vlines(on * 1e3, 1.07, 1.17, color=fs.ON, lw=2)
    a.vlines(off * 1e3, 1.07, 1.17, color=fs.OFF, lw=2)
    a.set_ylim(0.22, 1.5)
    a.set_xlim(0, 30)
    a.set_xlabel("time (ms)")
    a.set_ylabel("pixel intensity")
    a.set_title("A rotor pixel at 200 Hz blade-pass, as events")
    a.legend(handles=[Line2D([], [], color=fs.ON, lw=2, label="ON event"),
                      Line2D([], [], color=fs.OFF, lw=2, label="OFF event")],
             loc="upper right", ncol=2, handlelength=1.0)
    a.annotate("", xy=(1, 0.30), xytext=(6, 0.30), arrowprops=dict(arrowstyle="<->", color=fs.INK_2, lw=1))
    a.text(6.4, 0.30, "one period = 5 ms", color=fs.INK_2, va="center", fontsize=10)

    # (b) 1 s of 30 fps frames from the same pixel.
    s_short, v_short = frame_samples(f_bp, t_exp=0.0005)
    s_long, v_long = frame_samples(f_bp, t_exp=0.010)
    b.plot(s_short, v_short, "-o", color=fs.BLUE, ms=4, lw=1.6, label="0.5 ms exposure: aliased to a fake 10 Hz wobble")
    b.plot(s_long, v_long, "-o", color=fs.ORANGE, ms=4, lw=1.6, label="10 ms exposure: averaged flat")
    b.set_ylim(0.22, 1.62)
    b.set_xlim(0, 1)
    b.set_xlabel("time (s)")
    b.set_ylabel("frame value")
    b.set_title("The same pixel through a 30 fps camera")
    b.legend(loc="upper right", ncol=1)
    fig.text(0.0, -0.02, "Simulated: 2-blade prop at 6,000 RPM, dark blade covering the pixel 20% of each period, "
             "contrast threshold C = 0.25.", color=fs.INK_2, fontsize=9)
    return fig


# ---------------------------------------------------------------- range regimes ----------------------------
def fig_range():
    p = 4.86e-6          # IMX636 pixel pitch (m)
    f = 8e-3             # 8 mm lens
    D = 0.35             # drone span (m)
    d_rotor = 0.13       # 5-inch propeller disc (m)
    R = np.logspace(1, np.log10(2000), 400)

    fig, ax = plt.subplots(figsize=(8, 4.8))
    # Regimes are set by pixels on the rotor, which is lens-independent; bands are horizontal.
    bands = [(15, 400, "blades resolved: EventPro"), (1.5, 15, "rotor = a few blinking pixels: rotation-informed KF"),
             (0.05, 1.5, "sub-pixel rotor: EventRadar")]
    for i, (lo, hi, lab) in enumerate(bands):
        ax.axhspan(lo, hi, color=fs.BAND[i % 2], zorder=0, lw=0)
        # label positions chosen to sit in empty space for these lines
        x_lab, y_lab, ha, va = [(11, hi / 1.15, "left", "top"), (1950, hi / 1.15, "right", "top"),
                                (11, lo * 1.15, "left", "bottom")][i]
        ax.text(x_lab, y_lab, lab, ha=ha, va=va, fontsize=9.5, color=fs.INK_2)

    ax.plot(R, D * f / (R * p), color=fs.BLUE, label="whole drone (35 cm)")
    ax.plot(R, d_rotor * f / (R * p), color=fs.ORANGE, label="one rotor disc (13 cm)")
    ax.axhline(37, color=fs.INK_2, lw=1, ls=(0, (1, 2)))
    ax.text(1950, 37 * 1.1, "FRED median drone (37 px)", ha="right", va="bottom", color=fs.INK_2, fontsize=9.5)

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(10, 2000)
    ax.set_ylim(0.05, 400)
    ax.set_xlabel("range (m), for an 8 mm lens")
    ax.set_ylabel("pixels across")
    ax.set_title("What range takes away: pixels on the rotor")
    ax.legend(loc="upper right", bbox_to_anchor=(1.0, 0.93))
    fig.text(0.0, -0.08, "IMX636 (4.86 µm pixels). Pixels across ≈ size × focal length / (range × pixel pitch); a 50 mm lens "
             "shifts both lines right by ×6.25.\nBand boundaries are approximate.", color=fs.INK_2, fontsize=9)
    return fig


if __name__ == "__main__":
    t0 = time.time()
    fs.save(fig_aliasing(), "aliasing_sim", script="demos/fig_concepts.py", command="python fig_concepts.py",
            data="simulated", runtime_s=round(time.time() - t0, 2))
    t0 = time.time()
    fs.save(fig_range(), "range_regimes", script="demos/fig_concepts.py", command="python fig_concepts.py",
            data="analytic", runtime_s=round(time.time() - t0, 2))
    print("wrote post/figures/aliasing_sim.png, post/figures/range_regimes.png")
