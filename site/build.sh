#!/usr/bin/env bash
# Build the GitHub Pages site from post/index.md into _site/ (or the directory given as $1).
#
#   ./site/build.sh                        # needs pandoc >= 3 (pinned to 3.14 in CI)
#   python -m http.server -d _site 8000    # preview at http://localhost:8000
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-_site}"

rm -rf "$OUT"
mkdir -p "$OUT"

# MathJax is loaded by site/template.html (the post's own `math: true` would shadow pandoc's $math$ variable).
# GitHub-flavoured Markdown (what VS Code's preview shows) plus $...$ / $$...$$ math and YAML front matter.
pandoc post/index.md \
  --from gfm+tex_math_dollars+yaml_metadata_block+footnotes \
  --to html5 --standalone \
  --template site/template.html \
  --math-method=mathjax \
  --toc --toc-depth=2 \
  --section-divs=false \
  --metadata pagetitle="$(sed -n 's/^title: *"\(.*\)"$/\1/p' post/index.md | head -1)" \
  --output "$OUT/index.html"

cp site/style.css "$OUT/"
for d in figures media; do
  [ -d "post/$d" ] && cp -r "post/$d" "$OUT/$d"
done

# Fail the build if the post references a figure/video that doesn't exist.
missing=0
while read -r ref; do
  [ -e "$OUT/$ref" ] || { echo "missing: $ref" >&2; missing=1; }
done < <(perl -0pe 's/<!--.*?-->//gs' post/index.md | grep -oE '\((figures|media)/[^) ]+\)|src="(figures|media)/[^"]+"' \
          | sed -E 's/^\(|\)$//g; s/^src="|"$//g' | sort -u)
exit $missing
