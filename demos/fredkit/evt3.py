"""Minimal decoder for Prophesee EVT 3.0 ``.raw`` files (the format FRED ships).

EVT 3.0 is a stream of little-endian 16-bit words. The top 4 bits give the word type:

    0x0  EVT_ADDR_Y     y (11 bits) -> sets current row
    0x2  EVT_ADDR_X     x (11 bits), polarity (bit 11) -> emits one event
    0x3  VECT_BASE_X    x (11 bits), polarity (bit 11) -> sets base column for vectors
    0x4  VECT_12        12-bit validity mask -> up to 12 events at base_x+i, then base_x += 12
    0x5  VECT_8         8-bit validity mask  -> up to 8 events, then base_x += 8
    0x6  EVT_TIME_LOW   low 12 bits of the 24-bit timestamp (µs)
    0x8  EVT_TIME_HIGH  high 12 bits of the 24-bit timestamp
    0xA  EXT_TRIGGER    ignored here
    0x7/0xE/0xF         continued/other words, ignored here

The 24-bit timestamp wraps every 2**24 µs (~16.8 s); we unwrap it when TIME_HIGH goes backwards.
Reference: https://docs.prophesee.ai/stable/data/encoding_formats/evt3.html
"""
from __future__ import annotations

import numpy as np
from numba import njit


def _payload(path: str) -> np.ndarray:
    """Return the file body (after the ``%``-prefixed ASCII header) as uint16 words."""
    with open(path, "rb") as f:
        while True:
            pos = f.tell()
            line = f.readline()
            if not line.startswith(b"%"):
                f.seek(pos)
                break
            if line.startswith(b"% end"):
                break
        body = f.read()
    return np.frombuffer(body[: len(body) // 2 * 2], dtype="<u2")


@njit(cache=True)
def _decode(words, t_min, t_max):
    n = words.shape[0]
    # Upper bound: every word could be a 12-event vector.
    cap = min(n * 12, 400_000_000)
    xs = np.empty(cap, np.uint16)
    ys = np.empty(cap, np.uint16)
    ts = np.empty(cap, np.int64)
    ps = np.empty(cap, np.int8)
    k = 0
    y = 0
    base_x = 0
    vpol = 0
    t_high = 0
    t_low = 0
    t_high_prev = -1
    wraps = 0
    for i in range(n):
        w = words[i]
        typ = w >> 12
        if typ == 0x8:
            th = w & 0xFFF
            if t_high_prev >= 0 and th < t_high_prev and t_high_prev - th > 0x800:
                wraps += 1
            t_high_prev = th
            t_high = th
        elif typ == 0x6:
            t_low = w & 0xFFF
        elif typ == 0x0:
            y = w & 0x7FF
        else:
            t = (wraps << 24) | (t_high << 12) | t_low
            if typ == 0x2:
                if t_min <= t < t_max and k < cap:
                    xs[k] = w & 0x7FF
                    ys[k] = y
                    ts[k] = t
                    ps[k] = 1 if (w >> 11) & 1 else -1
                    k += 1
            elif typ == 0x3:
                base_x = w & 0x7FF
                vpol = 1 if (w >> 11) & 1 else -1
            elif typ == 0x4 or typ == 0x5:
                nbits = 12 if typ == 0x4 else 8
                if t_min <= t < t_max:
                    m = w & 0xFFF
                    for b in range(nbits):
                        if (m >> b) & 1 and k < cap:
                            xs[k] = base_x + b
                            ys[k] = y
                            ts[k] = t
                            ps[k] = vpol
                            k += 1
                base_x += nbits
    return xs[:k], ys[:k], ts[:k], ps[:k]


def read_evt3(path: str, t_min_us: int = 0, t_max_us: int = 2**62) -> dict[str, np.ndarray]:
    """Decode events with ``t_min_us <= t < t_max_us`` (sensor time, µs).

    Returns a dict of equal-length arrays: x, y (uint16), t (int64 µs), p (int8, +1 ON / -1 OFF).
    """
    x, y, t, p = _decode(_payload(path), int(t_min_us), int(t_max_us))
    return {"x": x.copy(), "y": y.copy(), "t": t.copy(), "p": p.copy()}
