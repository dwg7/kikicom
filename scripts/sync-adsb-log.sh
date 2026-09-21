#!/usr/bin/env bash
# Mac mini role machine (slate) side: pull the RPi's accumulated ADS-B
# position logs (~/adsb-log/*.jsonl[.zst]) into a local archive.
#
# Pull (not push) over rsync, same as kikimimi's sync-segments.sh: the RPi
# only captures. This is the copy that makes the RPi's SD card not the only
# place the data exists. Raw data: never committed to this repository.
#
# No delete logic: files the RPi compresses (.jsonl -> .jsonl.zst) simply
# arrive as new files; the matching local .jsonl is removed once its .zst
# has arrived, so the archive mirrors the RPi's own compression.
set -euo pipefail

# launchd runs with a minimal environment (no Homebrew on PATH)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

RPI_HOST="${KIKICOM_RPI_HOST:-m329.local}"
RPI_LOG_DIR="${KIKICOM_RPI_LOG_DIR:-adsb-log}"   # relative to the RPi user's home
LOCAL_DIR="${KIKICOM_LOCAL_LOG_DIR:-$HOME/kikicom-data/adsb-log}"
LOCK_DIR="${TMPDIR:-/tmp}/kikicom-sync-adsb-log.lock"

log() { printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"; }

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "another sync-adsb-log.sh is running, skipping this tick"
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

mkdir -p "$LOCAL_DIR"
rsync -a --timeout=60 -e "ssh -o BatchMode=yes -o ConnectTimeout=15" \
  "${RPI_HOST}:${RPI_LOG_DIR}/" "$LOCAL_DIR/"

for zst in "$LOCAL_DIR"/*.jsonl.zst; do
  [ -e "$zst" ] || continue
  plain="${zst%.zst}"
  if [ -e "$plain" ] && zstd -q -t "$zst"; then
    rm -f "$plain"
  fi
done

log "synced: $(ls "$LOCAL_DIR" | wc -l | tr -d ' ') files, $(du -sh "$LOCAL_DIR" | cut -f1)"
