"""Shared matplotlib style for every figure in the post (light mode, reference palette)."""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = ROOT / "post" / "figures"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"          # primary text
INK_2 = "#52514e"        # secondary text / axes
GRID = "#e6e5e1"         # recessive grid
BLUE = "#2a78d6"         # series 1  (also: ON events)
ORANGE = "#eb6834"       # series 2  (also: OFF events)
AQUA = "#1baf7a"         # series 3
BAND = ["#f1f0ec", "#f7f6f3"]  # neutral alternating regime shading (never a data hue)

ON, OFF = BLUE, ORANGE


def apply() -> None:
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "font.size": 11, "axes.titlesize": 12, "axes.labelsize": 11,
        "xtick.labelsize": 10, "ytick.labelsize": 10, "legend.fontsize": 10,
        "text.color": INK, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
        "axes.edgecolor": GRID, "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.titleweight": "bold", "axes.titlelocation": "left",
        "lines.linewidth": 2.0, "legend.frameon": False,
        "mathtext.fontset": "cm",
    })


def save(fig: plt.Figure, name: str, **meta) -> Path:
    """Save to post/figures/<name>.png plus a JSON sidecar used by the post's appendix table."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    out = FIG_DIR / f"{name}.png"
    fig.savefig(out, dpi=200, bbox_inches="tight")
    try:
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        commit = None
    meta.update(output=str(out.relative_to(ROOT)), git_commit=commit, created=time.strftime("%Y-%m-%d %H:%M:%S"))
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    return out
