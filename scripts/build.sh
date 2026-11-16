#!/usr/bin/env bash
# Render the workshop spec into site sources, then build the static site.
#   WORKSHOP=workshops/<name> scripts/build.sh   (default: the path in .workshop, which CI publishes)
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"
ZENSICAL="${ZENSICAL:-zensical}"
WORKSHOP="${WORKSHOP:-$(cat .workshop 2>/dev/null || echo workshops/wanderbricks)}"
"$PYTHON" scripts/validate.py --workshop "$WORKSHOP"
"$PYTHON" scripts/render.py --workshop "$WORKSHOP"
"$ZENSICAL" build -f zensical.eng.toml
cp scripts/root-index.html site/index.html
