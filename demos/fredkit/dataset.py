"""Access to one FRED sequence on a single, consistent clock.

Two on-disk layouts are supported:

* **Hugging Face release** (``<root>/{train,test}/<id>/``, the complete dataset): events in
  ``Event/events.hdf5`` (Prophesee HDF5, ECF-compressed, already on the frame clock), RGB in ``RGB/``
  (already 1280x720 in event coordinates), boxes with a drone id and model name.
* **Original raw release** (``<root>/<id>/``): ``Event/events.raw`` (EVT 3.0, offset from the frame
  clock; see below) and ``PADDED_RGB/``.

FRED has three clocks. Everything here is expressed on the **frame clock** (seconds), the one used by
``coordinates.txt`` and by the event-frame filenames (``..._frame_<µs>.png``):

* Annotations: ``coordinates.txt`` timestamps are already frame-clock seconds.
* RGB: filenames carry wall-clock time. Frame-clock 0 is the wall time of the first *kept* RGB frame
  (verified on seq 0 by matching RGB and event YOLO tracks: residual ≈ 3 px).
* Raw events: ``events.raw`` starts earlier than the frame clock (seq 0: +8.426 s, which is the
  sensor's start-up burst). The offset is estimated per sequence by matching raw-event windows to
  FRED's own rendered event frames, and cached in ``cache/event_offsets.json``.
"""
from __future__ import annotations

import json
import os
import re
from functools import cached_property
from pathlib import Path

import numpy as np

from .evt3 import read_evt3


def read_prophesee_hdf5(path) -> dict[str, np.ndarray]:
    """Read Prophesee HDF5 CD events (needs the ECF filter plugin on ``HDF5_PLUGIN_PATH``)."""
    import h5py

    try:
        with h5py.File(path, "r") as f:
            d = f["CD/events"][:]
    except OSError as e:
        raise OSError(f"{e}. FRED's HDF5 events are ECF-compressed: build https://github.com/prophesee-ai/hdf5_ecf "
                      "(or OpenEB) and point HDF5_PLUGIN_PATH at its hdf5/plugin dir; needs HDF5 1.14, not 2.x.") from e
    return {"x": d["x"], "y": d["y"], "t": d["t"].astype(np.int64), "p": np.where(d["p"] > 0, 1, -1).astype(np.int8)}

DEFAULT_ROOT = "~/data/sata/FRED/FRED_hf"
CACHE = Path(__file__).resolve().parents[2] / "cache"
FRAME_US = 33_333  # event-frame accumulation window (30 Hz)


def fred_root() -> Path:
    return Path(os.path.expanduser(os.environ.get("FRED_ROOT", DEFAULT_ROOT)))


def _wall_seconds(name: str) -> float:
    h, m, s = re.search(r"_(\d\d)_(\d\d)_(\d\d\.\d+)\.", name).groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


class Sequence:
    def __init__(self, seq_id: int | str):
        self.id = str(seq_id)
        root = fred_root()
        cands = [root / split / self.id for split in ("train", "test")] + [root / self.id]
        found = [c for c in cands if c.is_dir()]
        if not found:
            raise FileNotFoundError(f"FRED sequence {self.id} not found under {root}")
        self.dir = found[0]
        self.split = self.dir.parent.name if self.dir.parent.name in ("train", "test") else None
        self.hdf5 = (self.dir / "Event" / "events.hdf5").exists()

    # ------------------------------------------------------------------ annotations
    @cached_property
    def boxes(self) -> np.ndarray:
        """(N, 6) array: t [s, frame clock], x1, y1, x2, y2 [px], drone id (0 if absent).

        Several drones can share a timestamp; ``self.models`` maps drone id -> model name.
        """
        rows, self._models = [], {}
        for line in open(self.dir / "coordinates.txt"):
            if ":" not in line:
                continue
            t, rest = line.split(":", 1)
            v = [z.strip() for z in rest.split(",")]
            did = int(float(v[4])) if len(v) > 4 else 0
            if len(v) > 5:
                self._models[did] = v[5]
            rows.append([float(t), *map(float, v[:4]), did])
        return np.array(rows)

    @property
    def models(self) -> dict[int, str]:
        """Drone id -> model name (HF release only; empty for the raw release)."""
        self.boxes
        return self._models

    def boxes_at(self, t: float, tol: float = 0.02) -> np.ndarray:
        b = self.boxes
        sel = b[np.abs(b[:, 0] - t) <= tol]
        _, first = np.unique(sel[:, 5], return_index=True)  # one box per drone id
        return sel[np.sort(first), 1:5]

    # ------------------------------------------------------------------ RGB
    @cached_property
    def rgb_frames(self) -> list[tuple[float, Path]]:
        """Kept (padded) RGB frames as (frame-clock time [s], path), sorted."""
        # PADDED_RGB is FRED's RGB re-projected into the event camera's 1280x720 coordinate space,
        # so annotation boxes line up with it; plain RGB/ is missing in some sequences anyway.
        d = self.dir / ("RGB" if self.hdf5 else "PADDED_RGB")
        names = sorted((n for n in os.listdir(d) if n.endswith(".jpg")), key=_wall_seconds)
        w0 = _wall_seconds(names[0])
        return [(_wall_seconds(n) - w0, d / n) for n in names]

    def rgb_at(self, t: float) -> tuple[float, Path]:
        ts = np.array([f[0] for f in self.rgb_frames])
        return self.rgb_frames[int(np.abs(ts - t).argmin())]

    # ------------------------------------------------------------------ event frames (FRED-rendered)
    @cached_property
    def event_frames(self) -> list[tuple[float, Path]]:
        """FRED's rendered event frames as (end time of the 33 ms window [s], path), sorted."""
        d = self.dir / "Event" / "Frames"
        out = [(int(re.search(r"(\d+)\.png$", n).group(1)) / 1e6, d / n) for n in os.listdir(d) if n.endswith(".png")]
        return sorted(out)

    # ------------------------------------------------------------------ raw events
    @cached_property
    def _raw(self) -> dict[str, np.ndarray]:
        if self.hdf5:
            return read_prophesee_hdf5(self.dir / "Event" / "events.hdf5")
        return read_evt3(str(self.dir / "Event" / "events.raw"))

    @cached_property
    def event_offset_us(self) -> int:
        """Raw-event time minus frame-clock time, in µs (cached across runs)."""
        if self.hdf5:
            return 0  # HF release: verified on frame clock (see README)
        cache_file = CACHE / "event_offsets.json"
        cache = json.loads(cache_file.read_text()) if cache_file.exists() else {}
        if self.id not in cache:
            cache[self.id] = int(self._estimate_offset_us())
            CACHE.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps(cache, indent=1, sort_keys=True))
        return cache[self.id]

    def _estimate_offset_us(self, n_frames: int = 5) -> float:
        import cv2

        ev = self._raw
        t, x, y = ev["t"], ev["x"], ev["y"]
        frames = self.event_frames
        bg = None
        estimates = []
        for k in np.linspace(len(frames) * 0.2, len(frames) * 0.9, n_frames).astype(int):
            f_t, f_path = frames[k]
            img = cv2.imread(str(f_path)).astype(int)
            if bg is None:  # background colour = most common pixel value
                vals, counts = np.unique(img.reshape(-1, 3), axis=0, return_counts=True)
                bg = vals[counts.argmax()]
            mask = np.abs(img - bg).sum(2) > 30
            if mask.sum() < 50:
                continue
            cs = np.concatenate([[0], np.cumsum(mask[y, x])])

            def best(starts):
                a, b = np.searchsorted(t, starts), np.searchsorted(t, starts + FRAME_US)
                hits, n = cs[b] - cs[a], b - a
                prec, rec = hits / np.maximum(n, 1), hits / mask.sum()
                score = np.where(n > 30, 2 * prec * rec / (prec + rec + 1e-9), 0)
                return starts[score.argmax()]

            coarse = best(np.arange(0, t[-1] - FRAME_US, 2000))
            fine = best(np.arange(max(coarse - 3000, 0), coarse + 3000, 100))
            estimates.append(fine + FRAME_US - f_t * 1e6)
        if not estimates:
            raise RuntimeError(f"seq {self.id}: could not estimate event offset")
        spread = np.ptp(estimates)
        if spread > 5000:
            raise RuntimeError(f"seq {self.id}: inconsistent offset estimates {estimates}")
        return float(np.median(estimates))

    def events(self, t0: float, t1: float) -> dict[str, np.ndarray]:
        """Events in [t0, t1) on the frame clock. Returned ``t`` is frame-clock µs."""
        ev = self._raw
        off = self.event_offset_us
        a, b = np.searchsorted(ev["t"], [t0 * 1e6 + off, t1 * 1e6 + off])
        out = {k: v[a:b] for k, v in ev.items()}
        out["t"] = out["t"] - off
        return out
