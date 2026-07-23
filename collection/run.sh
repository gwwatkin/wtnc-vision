#!/usr/bin/env bash
# run.sh — start the collection + live-pipeline back-end on :8000.
# The back-end serves the built front-end from collection/frontend/dist/ (StaticFiles mount).
# Open http://localhost:8000 in your browser.  Ctrl-C to stop.
# See collection/README.md for details.
#
# PREREQUISITE (one-time, or after any FE change):
#   npm --prefix collection/frontend ci
#   npm --prefix collection/frontend run build
# This produces collection/frontend/dist/ which the back-end serves.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # comp-vision-results/collection
REPO="$(cd "$HERE/.." && pwd)"                          # comp-vision-results
VENV="$REPO/.venv"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "ERROR: repo venv not found at $VENV (Python 3.12)." >&2
  echo "Create it per CLAUDE.md:  /usr/bin/python3.12 -m venv $VENV" >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

echo "Starting back-end on http://localhost:8000 (API + front-end page)"
echo "Open  http://localhost:8000  in your browser.  Ctrl-C to stop."
echo

# One process: FastAPI back-end serves both the API and the static front-end page.
# The backend package lives in collection/, so run from there.
cd "$HERE"
exec python -m backend
