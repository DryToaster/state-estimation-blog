# Outline — "The Propeller Is the Signature": Drone Detection & Tracking with Event Cameras

Working title alternatives:
- *Counting Rotations: What Event Cameras See in a Drone That RGB Can't*
- *From a Blip at 1.5 km to a Flight Command at 20 m*

## The papers

| Short name | Paper | Venue / ID | Group |
|---|---|---|---|
| **EventRadar** | EventRadar: Long-Range Visual UAV Discovery through Spatiotemporal Event Sensing (Zhou et al.) | arXiv 2606.11285 | Tsinghua SIGS / HKU |
| **Event-only KF** | Event-Only Drone Trajectory Forecasting with RPM-Modulated Kalman Filtering (S.M., Habibiroudkenar et al.) | arXiv 2603.01997 | Aalto |
| **EventPro** | Count Every Rotation and Every Rotation Counts: Exploring Drone Dynamics via Propeller Sensing (Chen, Xu et al.) | arXiv 2511.13100 | Tsinghua SIGS / HKU / Meituan |

EventRadar and EventPro share authors (X. Chen, J. Xu, H. Wang, Y. Liu), so EventRadar is in part
EventPro's propeller-periodicity idea pushed out to long range. The Aalto paper is independent and
is the only one evaluated on FRED, the dataset we have locally.

## The synthesis

All three papers use the same physical fact: **a multirotor's propellers create brightness changes
at a fixed period, hundreds of times per second, and an event camera can sample that period. A 30 fps
RGB camera can't.** They differ in how much of the propeller the sensor resolves, and that sets what
each one can do with the signal:

| | EventRadar | Event-only KF | EventPro |
|---|---|---|---|
| Range | 700–1500 m | FRED (tens to low hundreds of m) | ≤ 60 m |
| Drone on sensor | a few px | ~25–45 px blob (FRED) | resolved blades |
| What's measured | ROI event-count **harmonic spectrum** | one **RPM per drone** (ON→OFF period histogram) | **ω per propeller** (contrast-maximizing rotational warp) |
| Role of the frequency | *identity*: is this blob a UAV? | *uncertainty*: how jumpy will it be? → KF process noise Q | *intent*: what command was issued? → SVM + LSTM/EKF prior |
| Pipeline stage | discovery / detection | tracking / short-horizon forecasting | dynamics / intent / precise localization |
| Learning | light (unrolled LISTA, weak labels) | none | SVM + LSTM |

The narrative runs from near to far along two axes at once:
1. **Range ↔ information.** The closer the drone, the more of the rotation you can resolve: a binary
   "it's periodic" at 1.5 km, then a scalar RPM, then a vector of per-motor speeds.
2. **Pipeline stage.** Detect, then track/forecast, then infer intent, which is also the order a
   counter-UAV or landing-assist system would chain them in.

A physics thread links them: thrust is T = κω², so ω² is (up to constants) acceleration. EventPro uses
this explicitly. The Event-only KF uses a heuristic, α_v = max(0.5, 1 + 2r + max(0, ṙ)). One possible
extension for the blog is replacing that heuristic with a ω²-based process-noise model in the demo.

### Critical-reading notes (for an honest "caveats" box per paper)
- **Event-only KF**: the KF gets ground-truth bbox centres *and* GT-differenced velocities as
  measurements, so this tests forecasting in isolation, not with a detector in the loop. Gains over a
  vanilla KF are small (1.6 px at 0.4 s, 4.2 px at 0.8 s ADE). **Table I oddity:** for the DL rows,
  ADE > FDE (e.g. LSTM 171.9 vs 53.04), which is the reverse of the classical rows and implausible
  for a monotone-growing error, so the columns may be swapped. Worth checking against the FRED paper.
  One RPM per drone means it can't use the per-motor asymmetry that encodes direction.
- **EventRadar**: evaluated on the authors' own 116 GB field corpus (not public). SAGE assumes an
  active gimbal with IMU/encoder pose, while FRED's camera is static, so in our demo SAGE collapses to
  a persistence/background map with R_t = I. The CHG-LISTA learned dictionary and weak labels can't be
  reproduced exactly, but a *non-learned* comb + group-ISTA captures the idea.
- **EventPro**: needs resolved blades (accuracy degrades past ~40° view angle and at 60 m). Ground
  truth comes from a tachometer (indoor) and a motor encoder (outdoor). The command-inference set is
  small (200 samples per motion). FRED drones are mostly too small for per-propeller warping, so that
  demo stays at the near edge of FRED.

## FRED: what we have locally

`~/data/sata/FRED/FRED - Florence RGB-Event Drone Dataset/<seq>/`. There are 99 sequences, each about
110 s long. Contents:
- `Event/events.raw`: Prophesee **EVT3**, 1280×720, IMX636 (the same sensor family EventRadar and EventPro use)
- `Event/Frames/*.png`: pre-rendered event frames at 30 Hz
- `RGB/*.jpg`: 1280×720 frames at 30 Hz (filenames use wall-clock time)
- `coordinates.txt` (`t: x1, y1, x2, y2`); `interpolated_coordinates.txt` (+ id); `tracks.txt` in some sequences only (`t,id,x,y,w,h`)
- `*_YOLO/`: YOLO-format labels

Survey (`coordinates.txt`, √(w·h) of the bbox): the median drone is **37 px** over all 231 sequences of the HF release (was 34 px on the partial copy).
Only **seq 188** has a median above 60 px. No sequence has a median below 20 px. Some sequences have
multiple drones (0, 1, 16–21, 101–104, 113, 115). Two (101, 113) have corrupted timestamps in
`tracks.txt`, and two (2, 119) have no `coordinates.txt`.

So FRED sits squarely in the **Event-only KF's regime**. To reach EventRadar's regime we *emulate*
range by spatially pooling events (e.g. 4×/8× pixel binning plus event subsampling). For EventPro we
use the largest-bbox windows (seq 188 and the p95 frames elsewhere) and are explicit about where it
breaks.

Open data items:
- [ ] Get the official FRED train/test (and challenging) split lists. They aren't in the local copy.
- [ ] Work out the RGB wall-clock ↔ event µs ↔ `coordinates.txt` seconds alignment, and verify it on one sequence.
- [ ] Find which sequences are night / rain / indoor / insects (the dataset README or a manual tag pass). These are needed for the RGB-vs-event comparison shots.
- [ ] Find the drone model per sequence (needed for blade count N_b in the RPM formula).

---

## Post outline

### 0. Cold open (≈150 words + hero media)
Side-by-side loop from FRED, the same 2 s in a night or rain sequence. RGB: the drone is invisible or
a smear. Events: a crisp blob with a shimmer at the rotors. Close on the question *"what's in that
shimmer?"*
- Media: `hero_rgb_vs_events.mp4` (Demo 1)

### 1. Why drones are hard for cameras (≈400 words)
- Small, fast, erratic and non-cooperative. Clutter: birds, insects, clouds.
- RGB failure modes: motion blur, low light and dynamic range, 30 fps temporal aliasing.
- The landscape in one paragraph: radar, RF, acoustic, thermal, RGB detectors. Spatial cues fade
  with range (the framing EventRadar's Table 1 uses).

### 2. Event cameras in 5 minutes (≈700 words, the "basics")
- The pixel model: log-intensity change crossing a threshold C, giving an event e = (x, y, t, p).
  µs timestamps, ~120 dB dynamic range, no global exposure.
- Representations we'll use: event frames (counts), time surfaces, x-y-t point clouds, per-pixel
  time series.
- Event-camera noise: hot pixels, background activity, 1/f, polarity imbalance. This sets up why
  each paper spends effort on filtering.
- Figures: (a) a schematic of the pixel threshold, (b) an x-y-t scatter of a FRED drone crop
  showing the helical rotor structure, (c) the same 100 ms as an RGB frame stack.
- Code: Demo 0 (EVT3 loader) and Demo 1.

### 3. The key idea: a propeller is a clock (≈500 words)
- Blades sweep edges past a pixel N_b times per revolution, so each rotor pixel fires at the
  blade-pass frequency. At 3,000–10,000 RPM with 2 blades that's ~100–330 Hz.
- **Aliasing figure:** RGB at 30 fps has a Nyquist limit of 15 Hz, so the rotor signal aliases to
  noise. The event pixel time series shows a clean period.
- The signal is a pulse train, not a sinusoid, which is why harmonics matter. This sets up EventRadar.
- Physics box: T = κω² and τ = κ_τω². RPM ties to thrust and to the controller's command.
- Code: Demo 2 (per-pixel period histogram and frequency heatmap on FRED).

### 4. Three papers, three ranges (the core; ≈2,500 words total)
Each subsection follows the same template: **problem → key mechanism (one diagram + the one
equation that matters) → our re-implementation on FRED next to RGB → what the paper reports → caveats.**

#### 4.1 Far: EventRadar, finding the blip
- C1 "where to look" (SAGE): pixel → ray → scene-anchored bearing, then a persistence map that
  separates transient from persistent events. With a static FRED camera this reduces to a
  background-persistence map, which is still useful against static clutter and flicker.
- C2 "is it a drone?" (CHG-LISTA): ROI count series → detrend (polynomial projection) → robust
  z-score → quadrature harmonic comb (1×, 2×, 3× with 1/h weights) → group-sparse recovery → local
  spectral-ratio score.
- Demo 3: on FRED drone ROIs and on decoy ROIs (background, insects if present), compare raw FFT
  peak, comb pooling and group-ISTA as range is emulated by pooling (1×, 4×, 8×). Plot confidence
  against effective pixel size. RGB comparison: a small-blob detector on downsampled RGB.
- Paper results: 0.990 mAP@.3 and 0.949 F1@.3 at 700–1500 m, against EV-SpSegNet, EvDetMAV,
  EVPropNet and effqpdet.

#### 4.2 Mid: Event-only KF, frequency as a process-noise prior
- RPM via the period histogram (Δb = 0.1 ms, 256 bins, 100 ms FIFO, 70th-percentile propeller mask).
- CV Kalman filter whose Q is scaled by α_v(r, ṙ).
- Demo 4: reproduce linear extrapolation vs vanilla KF vs KF+RPM at 0.4 s and 0.8 s horizons on the
  FRED test split, with ADE/FDE boxplots. Overlay forecasts on RGB and event frames for one
  night/rain clip. **Extension:** a Q scaled by ω² (thrust), and a version with a real detector
  instead of GT boxes (YOLO on event frames vs YOLO on RGB), so that the RGB vs event comparison
  covers the whole pipeline.
- Paper results: Table I (with the ADE/FDE oddity noted).

#### 4.3 Near: EventPro, from rotations to intentions
- Preprocessing: count and polarity-balance heatmaps for filtering, then K-means per propeller.
- Contrast-maximization with a rotational warp: an accumulation reward plus a sparsity reward,
  optimized with Brent's method. Adaptive batching (consistency rate λ) and density-importance
  downsampling.
- Every Rotation Counts: ω² features → SVM command classifier → LSTM trajectory prior → EKF with GPS.
- Demo 5: on seq 188 / largest-bbox windows, run K-means to find the rotor centres, then plot the
  objective landscape R(ω) and show the warped event image at bad vs best ω. **Be explicit if blades
  aren't resolved** (that's the lesson about the range regime). If per-rotor ω works, show the
  asymmetry between rotors during a manoeuvre.
- Paper results: 0.23% RMAE, 3.14 ms latency, 96.5% command precision, >22% tracking improvement.

### 5. Putting it together (≈600 words)
- The ladder diagram: range on the x-axis and "information extracted from rotation" on the y-axis
  (periodic? → RPM → per-motor ω → command), with each paper as a rung.
- A hypothetical full stack: EventRadar cues a bearing → slew/zoom → Event-only-style tracker with
  an RPM-aware Q → once close, EventPro-style intent. Where would the handoffs fail?
- Common weaknesses: everyone assumes rotor visibility (view angle, occlusion, ducted props); none of
  the three handles fixed-wing aircraft; one dataset per paper, mostly private.
- Open problems: per-rotor RPM at FRED-like ranges, learned vs physics priors (the Event-only DL
  baselines lose to linear extrapolation!), and a benchmark that spans range.

### 6. Takeaways (≈200 words)
- Bullet recap.

### Appendix: Reproducing every figure and video (≈400 words + tables)
The demos are too heavy to run in a browser. The post **shows results as pre-rendered videos and
figures** and **documents the code and environment** so readers can regenerate them locally.
- Environment: `conda env create -f environment.yml`, plus the hardware we used (24-core CPU, RTX 5080;
  the GPU is only needed for the optional YOLO comparison).
- Dataset: where to get FRED, the expected directory layout, and `FRED_ROOT`.
- A table with one row per video/figure: the script, the exact command (sequence id, time window,
  flags), the runtime on our machine, and the output path.
- A short note on the EVT3 decoder, since that's the part readers are most likely to reuse.

---

## Demo plan (`demos/`)

**The demos run offline; the post embeds their videos.** Every demo is a script that renders a
video and/or figures. The post shows a short code excerpt, links to the full script, and embeds the
rendered result. Nothing runs in the reader's browser.

| # | Name | Section | Inputs | Video(s) | Still figures | RGB counterpart in the video |
|---|---|---|---|---|---|---|
| 0 | `fredkit` loader | 2, App. | `events.raw` (EVT3), RGB, coords | — | — | — |
| 1 | RGB vs events | 0, 2 | night/rain seq | `hero_rgb_vs_events.mp4`, `xyt_rotate.mp4` (rotating x-y-t cloud of a drone crop) | `xyt_drone_crop.png` | left half: RGB frames |
| 2 | Rotor clock | 3 | drone ROI | `rotor_clock.mp4` (event crop + live period histogram + RPM(t) trace) | `aliasing_rgb_vs_event.png`, `rotor_freq_heatmap.png` | inset: 30 fps intensity trace of the same ROI |
| 3 | Harmonic verification | 4.1 | drone + decoy ROIs, pooled 1×/4×/8× | `harmonic_vs_range.mp4` (ROI, FFT and comb spectra side by side as pooling increases) | `fft_vs_comb_vs_range.png` | downsampled RGB crop at the same effective range |
| 4 | RPM-modulated KF | 4.2 | FRED test split | `forecast_overlay.mp4` (past/GT/forecast drawn on RGB and on event frames) | `ade_fde_boxplots.png`, results table | RGB panel; optional RGB-YOLO track |
| 5 | Rotational CMax | 4.3 | seq 188 windows | `cmax_sweep.mp4` (warped event image as ω sweeps through the optimum) | `cmax_landscape.png` | — |
| 6 | Synthesis | 5 | outputs of 2–5 | — | `ladder.svg` | — |

Video conventions (so every clip looks consistent):
- **Layout:** RGB | events side by side wherever both exist, with the same crop and timestamps.
  Events render as polarity colour on black (ON = one hue, OFF = another, applied consistently).
- **Time:** show a burned-in timestamp and playback rate on every clip ("events: 1 ms bins, shown at
  1/20× speed"). Slow-motion event clips need this or readers misread them.
- **Encode:** H.264 (libx264, `-crf 23 -preset slow -pix_fmt yuv420p -movflags +faststart`), no audio,
  ≤ 1920 px wide, 5–15 s loops, aiming for < 8 MB each. A poster PNG accompanies each clip.
  Embed with `<video autoplay muted loop playsinline poster=…>`.
- **Masters:** full-quality renders go to `cache/renders/` (gitignored). Only the compressed
  encodes in `post/media/` are committed. Not Git LFS: GitHub Pages serves LFS pointer files, not
  the media.
- Every script writes a small `*.json` sidecar next to its output (sequence, time window, parameters,
  git commit, runtime). The appendix reproduction table is generated from these.

Engineering notes:
- No event libraries are installed (only numpy). Write a small vectorized **EVT3 decoder**
  (numpy + numba) instead of depending on the Metavision SDK. Cache decoded per-sequence windows as
  `.npz` under `cache/` (gitignored).
- Only 1.2 GB per sequence (~150 MB raw events), so everything runs on a laptop. The RTX 5080 is only
  needed for an optional YOLO detector. NVENC is available but libx264 gives smaller files for
  committed clips.
- Frames are rendered with OpenCV/matplotlib and piped to ffmpeg. One `make videos` and one
  `make figures` target regenerate everything.

## Open decisions
- Site generator: plain Markdown with embedded `<video>` is enough now that nothing runs in-browser.
  It works with Jekyll/GitHub Pages or Hugo; executable Quarto cells are no longer needed.
- Video hosting: committing small MP4s directly to the repo is the default. If the total grows past
  ~100 MB, move them to GitHub Release assets or a CDN and keep the links in the post.
- One long post or a short series (basics, then one post per paper, then synthesis)? The outline
  works either way. Sections 2–3 stand alone well.
- PDFs: kept out of git (`.gitignore`). The post links to arXiv instead.
