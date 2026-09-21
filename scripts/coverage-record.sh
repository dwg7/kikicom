#!/usr/bin/env bash
# LaunchAgent entry point for the coverage sampling (scripts/install-coverage-timer.sh).
# Fetches our readsb's aircraft.json over ssh HERE, in bash, and hands it to
# coverage-check.py as a file: under launchd, macOS Local Network privacy
# refuses ssh spawned from Homebrew's framework Python ("No route to host"),
# while ssh spawned from bash/rsync is fine (2026-09-21, measured).
set -uo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${KIKICOM_RPI_HOST:-m329.local}"
TMP="$(mktemp "${TMPDIR:-/tmp}/kikicom-aircraft.XXXXXX")"
trap 'rm -f "$TMP"' EXIT
for attempt in 1 2; do
  if ssh -o BatchMode=yes -o ConnectTimeout=15 "$HOST" cat /run/adsb-research/aircraft.json > "$TMP"; then
    break
  fi
  echo "ssh attempt $attempt failed" >&2
  : > "$TMP"
  sleep 5
done
# an empty file makes coverage-check.py record the sample as missing (NA)
exec python3 "$DIR/coverage-check.py" --record --ours-file "$TMP"
