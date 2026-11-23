# Demos

Offline scripts that render every video and figure in the post. Nothing here runs in the browser:
the post embeds the rendered outputs and documents how to regenerate them.
Plan and conventions: `../OUTLINE.md` → *Demo plan*.

## Setup
```bash
mamba env create -f ../environment.yml && conda activate event-drones
export FRED_ROOT="$HOME/data/sata/FRED/FRED - Florence RGB-Event Drone Dataset"
```

## Working now

| Script | Output (`post/figures/`) | Section |
|---|---|---|
| `fig_concepts.py` | `aliasing_sim.png`, `range_regimes.png` (no data needed) | 3, 4 |
| `fig_fred_frames.py --seq 188` | `rgb_vs_events_188.png` | 1–2 |
| `fig_rotor_clock.py --seq 188` | `rotor_clock_188.png` | 4.2 |
| `fig_rotor_spectrum.py --seq 188` | `rotor_spectrum_188.png` | 3 |
| `fig_rotor_speeds.py --seq 188 --t0 30 --t1 50` | `rotor_speeds_188.png` (+ CSV) | 4.1 |

`fredkit` puts all FRED data on one clock (the *frame clock* used by `coordinates.txt`):
- `read_evt3()` decodes EVT 3.0 `.raw` files with numba (~2 s per sequence). It agrees with Prophesee OpenEB to within 81 of 29.3 M events on seq 0.
- `Sequence(id).events(t0, t1)` returns events on the frame clock. The raw stream starts earlier than the frame clock by a per-sequence offset (0.01–10.4 s so far). It's estimated by matching raw windows to FRED's rendered event frames and cached in `cache/event_offsets.json`.
- `Sequence(id).rgb_at(t)` uses `PADDED_RGB/` (aligned to event coordinates). Frame-clock 0 = wall time of the first kept RGB frame, verified on seq 0 via YOLO-track matching and visually on seq 188.

## Planned scripts
| # | Script | Post section | Outputs (`post/media/`, `post/figures/`) |
|---|---|---|---|
| 0 | `fredkit/` (EVT3 decoder, RGB/event/box alignment) | 2, Appendix | — |
| 1 | `01_rgb_vs_events.py` | 0, 2 | `hero_rgb_vs_events.mp4`, `xyt_rotate.mp4`, `xyt_drone_crop.png` |
| 2 | `02_rotor_clock.py` | 3 | `rotor_clock.mp4`, `aliasing_rgb_vs_event.png`, `rotor_freq_heatmap.png` |
| 3 | `03_harmonic_verification.py` (EventRadar) | 4.1 | `harmonic_vs_range.mp4`, `fft_vs_comb_vs_range.png` |
| 4 | `04_rpm_kalman.py` (Event-only KF) | 4.2 | `forecast_overlay.mp4`, `ade_fde_boxplots.png` |
| 5 | `05_rotational_cmax.py` (EventPro) | 4.3 | `cmax_sweep.mp4`, `cmax_landscape.png` |
| 6 | `06_synthesis.py` | 5 | `ladder.svg` |

## Output conventions
- Full-quality renders go to `cache/renders/` (gitignored). Compressed H.264 encodes go to `post/media/` (committed).
- Encode with `ffmpeg -c:v libx264 -crf 23 -preset slow -pix_fmt yuv420p -movflags +faststart -an`. Keep each clip ≤ 1920 px wide and under ~8 MB, with a poster PNG.
- Each output gets a `*.json` sidecar (sequence, window, params, git commit, runtime). The post's appendix table is built from these.
