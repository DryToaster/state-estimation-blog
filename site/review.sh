#!/usr/bin/env bash
# Reading copy of the post for review: review/index.pdf (git-ignored), the site exactly as readers
# see it, printed by headless Chrome.
# Opening post/index.md itself in a word processor shows raw LaTeX and no figures, and saving it back
# corrupts the Markdown, so review from these and make edits in post/index.md.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p review
./site/build.sh _site >/dev/null

tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT

# --- pdf: print the built site
CHROME=$(command -v google-chrome || command -v chromium || command -v chromium-browser)
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer --virtual-time-budget=15000 \
  --user-data-dir="$tmp/chrome" --print-to-pdf="$PWD/review/index.pdf" "file://$PWD/_site/index.html" 2>/dev/null
ls -la review
