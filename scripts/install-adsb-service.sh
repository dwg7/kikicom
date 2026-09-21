#!/usr/bin/env bash
# Register/unregister readsb (ADS-B, 1090MHz) as a systemd service on the
# RPi 4B, plus a small position logger that accumulates every decoded
# position as daily JSONL files.
#
# Same pattern as kikimimi's scripts/install-record-service.sh. Run this ON
# the RPi (or via: ssh m329.local 'bash -s' < this script). Requires
# /usr/local/bin/readsb built with RTL-SDR support (scripts/build-readsb.sh).
#
# The RTL-SDR is shared with kikimimi (kikimimi-record.service). Only one of
# the two can own the device; `install` refuses to start while
# kikimimi-record.service is active.
#
# Outputs:
#   /run/adsb-research/   live readsb JSON (aircraft.json, stats.json, ...).
#                         tmpfs via RuntimeDirectory= so the every-few-seconds
#                         rewrites do not wear the SD card.
#   $LOG_DIR/YYYY-MM-DD.jsonl
#                         one JSON object per decoded position (UTC date),
#                         from readsb's --net-json-port. Raw data: kept on the
#                         RPi / Mac mini role machine, never committed.
set -euo pipefail

ACTION="${1:-install}"
UNIT_NAME="adsb-research.service"
LOGGER_UNIT_NAME="adsb-logger.service"
UNIT_PATH="/etc/systemd/system/${UNIT_NAME}"
LOGGER_UNIT_PATH="/etc/systemd/system/${LOGGER_UNIT_NAME}"
LOGGER_PATH="/usr/local/lib/kikicom/adsb-logger.py"
RUN_USER="$(id -un)"

READSB_BIN="${KIKICOM_READSB_BIN:-/usr/local/bin/readsb}"
GAIN="${KIKICOM_GAIN:-49.6}"  # 1090MHz is ADC-noise-limited on the V4; keep it high (CLAUDE.md)
DEVICE="${KIKICOM_DEVICE:-0}"
# Receiver position, deliberately rounded to ~1km (Tsukisamu, Sapporo).
LAT="${KIKICOM_LAT:-43.05}"
LON="${KIKICOM_LON:-141.40}"
JSON_PORT="${KIKICOM_JSON_PORT:-30047}"
LOG_DIR="${KIKICOM_LOG_DIR:-$HOME/adsb-log}"

case "$ACTION" in
  install)
    if [ ! -x "$READSB_BIN" ] || ! "$READSB_BIN" --help 2>&1 | grep 'rtl-sdr devices' > /dev/null; then
      echo "error: $READSB_BIN missing or built without RTL-SDR support." >&2
      echo "run scripts/build-readsb.sh first." >&2
      exit 1
    fi
    if systemctl is-active --quiet kikimimi-record.service; then
      echo "error: kikimimi-record.service is active and owns the RTL-SDR." >&2
      echo "stop it first (with the owner's consent): sudo systemctl disable --now kikimimi-record.service" >&2
      exit 1
    fi
    mkdir -p "$LOG_DIR"
    sudo mkdir -p "$(dirname "$LOGGER_PATH")"
    sudo tee "$LOGGER_PATH" > /dev/null <<'PY'
#!/usr/bin/env python3
"""Append readsb --net-json-port lines to <log_dir>/YYYY-MM-DD.jsonl (UTC)."""
import datetime, os, socket, sys, time

host, port, log_dir = sys.argv[1], int(sys.argv[2]), sys.argv[3]
os.makedirs(log_dir, exist_ok=True)

while True:
    try:
        with socket.create_connection((host, port), timeout=10) as s:
            s.settimeout(None)
            buf = b""
            while True:
                chunk = s.recv(65536)
                if not chunk:
                    break
                buf += chunk
                *lines, buf = buf.split(b"\n")
                lines = [l for l in lines if l.strip()]
                if not lines:
                    continue
                day = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
                with open(os.path.join(log_dir, day + ".jsonl"), "ab") as f:
                    f.write(b"\n".join(lines) + b"\n")
    except OSError as e:
        print(f"adsb-logger: {e}; retrying in 5s", file=sys.stderr, flush=True)
    time.sleep(5)
PY
    sudo chmod 0755 "$LOGGER_PATH"

    sudo tee "$UNIT_PATH" > /dev/null <<EOF_UNIT
[Unit]
Description=kikicom: ADS-B capture (readsb, 1090MHz). Shares the RTL-SDR with kikimimi-record.service
After=network.target
Conflicts=kikimimi-record.service

[Service]
Type=simple
User=${RUN_USER}
RuntimeDirectory=adsb-research
ExecStart=${READSB_BIN} --device-type rtlsdr --device ${DEVICE} --gain ${GAIN} --lat ${LAT} --lon ${LON} --write-json /run/adsb-research --write-json-every 5 --net --net-bind-address 127.0.0.1 --net-json-port ${JSON_PORT} --net-ro-size 8192 --quiet
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF_UNIT

    sudo tee "$LOGGER_UNIT_PATH" > /dev/null <<EOF_UNIT
[Unit]
Description=kikicom: accumulate readsb positions into daily JSONL
After=${UNIT_NAME}
BindsTo=${UNIT_NAME}

[Service]
Type=simple
User=${RUN_USER}
ExecStart=/usr/bin/python3 ${LOGGER_PATH} 127.0.0.1 ${JSON_PORT} ${LOG_DIR}
Restart=always
RestartSec=5

[Install]
WantedBy=${UNIT_NAME}
EOF_UNIT

    sudo systemctl daemon-reload
    sudo systemctl enable "$UNIT_NAME" "$LOGGER_UNIT_NAME"
    sudo systemctl restart "$UNIT_NAME"
    sudo systemctl restart "$LOGGER_UNIT_NAME"
    echo "installed and started: $UNIT_PATH, $LOGGER_UNIT_PATH"
    echo "live json:  /run/adsb-research/  (aircraft.json, stats.json)"
    echo "positions:  $LOG_DIR/YYYY-MM-DD.jsonl"
    echo "check with: ./scripts/install-adsb-service.sh status"
    echo "hand the RTL-SDR back to kikimimi:"
    echo "  sudo systemctl disable --now $UNIT_NAME && sudo systemctl enable --now kikimimi-record.service"
    ;;
  uninstall)
    sudo systemctl disable --now "$LOGGER_UNIT_NAME" "$UNIT_NAME" 2>/dev/null || true
    sudo rm -f "$UNIT_PATH" "$LOGGER_UNIT_PATH" "$LOGGER_PATH"
    sudo systemctl daemon-reload
    echo "stopped and removed: $UNIT_PATH, $LOGGER_UNIT_PATH (logs in $LOG_DIR kept)"
    ;;
  status)
    systemctl status "$UNIT_NAME" "$LOGGER_UNIT_NAME" --no-pager || true
    echo "--- aircraft now ---"
    python3 - <<'PY' || true
import json, time
d = json.load(open("/run/adsb-research/aircraft.json"))
ac = d["aircraft"]
print(f"age {time.time() - d['now']:.0f}s, messages {d['messages']}, "
      f"aircraft {len(ac)} ({sum('lat' in a for a in ac)} with position)")
PY
    echo "--- position logs ---"
    ls -l "$LOG_DIR" | tail -5 || true
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
