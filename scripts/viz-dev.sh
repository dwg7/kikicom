#!/usr/bin/env bash
# LOCAL PROTOTYPE: serve docs/ on slate and keep docs/data/ fresh.
#   live aircraft + stats: every 10s (ssh to the RPi)
#   rsync the log mirror + rebuild tracks: every 2 min
# Open http://localhost:${PORT}/ . Ctrl-C to stop.
# Binds to 127.0.0.1 by default: the data is not reviewed for publication.
set -euo pipefail
export PATH="/opt/homebrew/bin:$PATH"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
PORT="${KIKICOM_VIZ_PORT:-8329}"
BIND="${KIKICOM_VIZ_BIND:-127.0.0.1}"

./scripts/sync-adsb-log.sh >/dev/null
python3 scripts/build-viz-data.py
python3 -m http.server "$PORT" --bind "$BIND" --directory docs >/dev/null 2>&1 &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null' EXIT
echo "serving http://${BIND}:${PORT}/"

i=0
while true; do
  sleep 10
  i=$((i + 1))
  if [ $((i % 12)) -eq 0 ]; then
    ./scripts/sync-adsb-log.sh >/dev/null || true
    python3 scripts/build-viz-data.py >/dev/null || echo "build failed" >&2
  else
    python3 scripts/build-viz-data.py --live-only >/dev/null || echo "live refresh failed" >&2
  fi
done
