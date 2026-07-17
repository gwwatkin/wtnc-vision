#!/usr/bin/env bash
# run.sh — start the collection back-end (:8000) and static front-end (:8001).
# Both run on this device; Ctrl-C stops both.  See specs/collection/design.md §10.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # comp-vision-results/collection
REPO="$(cd "$HERE/.." && pwd)"                          # comp-vision-results
VENV="$REPO/.venv"

FRONTEND_PORT="${FRONTEND_PORT:-8001}"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "ERROR: repo venv not found at $VENV (Python 3.12)." >&2
  echo "Create it per CLAUDE.md:  /usr/bin/python3.12 -m venv $VENV" >&2
  exit 1
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

BACKEND_PID=""
FRONTEND_PID=""
cleanup() {
  echo
  echo "Stopping..."
  [[ -n "$BACKEND_PID" ]]  && kill "$BACKEND_PID"  2>/dev/null || true
  [[ -n "$FRONTEND_PID" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Back-end (reads backend/config.yaml -> host/port 127.0.0.1:8000)
( cd "$HERE" && exec python -m backend ) &
BACKEND_PID=$!

# Front-end (static; camera needs a secure context — localhost qualifies)
python -m http.server "$FRONTEND_PORT" --directory "$HERE/frontend" >/dev/null 2>&1 &
FRONTEND_PID=$!

echo "Back-end  : http://localhost:8000  (health: /health)"
echo "Front-end : http://localhost:${FRONTEND_PORT}"
echo
echo "Open  http://localhost:${FRONTEND_PORT}  in your browser.  Ctrl-C to stop both."

# Wait on either child; if one dies, cleanup (via trap) stops the other.
wait -n "$BACKEND_PID" "$FRONTEND_PID"
