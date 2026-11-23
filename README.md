# state-estimation-blog

Blog post (and reproducible demos) on drone detection and tracking with event cameras, built around
three papers (EventRadar, Event-only RPM-KF, EventPro) and the FRED RGB-Event dataset.

- `OUTLINE.md`: narrative, synthesis, section-by-section plan, demo plan, open items
- `post/index.md`: the post draft (`figures/`, `media/` alongside)
- `demos/`: code that generates every figure and video from FRED

## Site (GitHub Pages)

The post is built with pandoc (GitHub-flavoured Markdown + `$…$` math, rendered by MathJax) by
`site/build.sh`, and deployed by `.github/workflows/pages.yml` on every push to `main` that touches
`post/` or `site/`.

```bash
./site/build.sh                        # -> _site/ (fails if a referenced figure/video is missing)
python -m http.server -d _site 8000    # preview at http://localhost:8000
```

One-time setup: **Settings → Pages → Source: GitHub Actions**. The page shows a "Draft" badge while
the front matter has `draft: true`.

## Data

The demos default to the complete Hugging Face release of FRED at `~/data/sata/FRED/FRED_hf`
(override with `FRED_ROOT`). Its events are Prophesee HDF5 compressed with the ECF codec, so h5py
needs the plugin: build [hdf5_ecf](https://github.com/prophesee-ai/hdf5_ecf) (or OpenEB) and set
`HDF5_PLUGIN_PATH` to its `hdf5/plugin` directory. The HF events are already on the annotation
clock; the older raw (EVT 3.0) layout is still supported and needs a per-sequence offset (see
`demos/fredkit/dataset.py`).
