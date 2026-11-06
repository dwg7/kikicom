#!/usr/bin/env bash
# Install/remove the CubeSat pass planner on the RPi (P0 of documents/satellite/README.md).
#
# Run on slate (the development machine); the RPi has no checkout, so this
# pushes the files over ssh. It only installs a planner that writes a schedule:
# it never touches adsb-research.service or the RTL-SDR.
#
#   KIKICOM_RPI_HOST=<rpi ssh name> ./scripts/install-sat-service.sh [install|status|uninstall]
#
# The receiver position goes to the RPi's ~/sat/location.json only (never into
# the repo): $KIKICOM_LAT/$KIKICOM_LON, else ~/kikicom-data/receiver-location.json,
# else the repo's rounded default.
#
# On the RPi:
#   ~/kikicom-sat/            micromamba + env "sat" (python 3.12 + skyfield)
#   ~/sat/                    config.json, location.json, tle/, schedule.json/.tsv, plan-history.jsonl
#   /usr/local/lib/kikicom/sat-plan.py
#   sat-plan.service/.timer   every 6 h
set -euo pipefail

ACTION="${1:-install}"
HOST="${KIKICOM_RPI_HOST:?set KIKICOM_RPI_HOST to the ssh name of the RPi}"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
SSH=(ssh -o ConnectTimeout=10 "$HOST")

# macOS's stock bash 3.2 mis-parses nested quotes inside $( ) in a case branch,
# so the JSON read lives in a function.
json_get() {
  python3 - "$1" "$2" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))[sys.argv[2]])
PY
}

REMOTE_HOME="$("${SSH[@]}" 'echo $HOME')"
REMOTE_USER="$("${SSH[@]}" 'id -un')"
ENV_PY="$REMOTE_HOME/kikicom-sat/mamba/envs/sat/bin/python"

case "$ACTION" in
  install)
    LAT="${KIKICOM_LAT:-}"; LON="${KIKICOM_LON:-}"
    if [ -z "$LAT" ] || [ -z "$LON" ]; then
      LOC_FILE="$HOME/kikicom-data/receiver-location.json"
      if [ -f "$LOC_FILE" ]; then
        LAT="$(json_get "$LOC_FILE" lat)"
        LON="$(json_get "$LOC_FILE" lon)"
      else
        LAT=43.05; LON=141.40
      fi
    fi

    echo "== python env (micromamba + skyfield) =="
    "${SSH[@]}" 'bash -s' <<'EOF_ENV'
set -euo pipefail
mkdir -p ~/kikicom-sat ~/sat
cd ~/kikicom-sat
if [ ! -x bin/micromamba ]; then
  curl -sL -m 300 https://micro.mamba.pm/api/micromamba/linux-aarch64/latest | tar -xj bin/micromamba
fi
export MAMBA_ROOT_PREFIX="$HOME/kikicom-sat/mamba"
if [ ! -x "$MAMBA_ROOT_PREFIX/envs/sat/bin/python" ]; then
  nice -n 19 ionice -c3 ./bin/micromamba create -y -q -n sat -c conda-forge --override-channels python=3.12 skyfield
fi
"$MAMBA_ROOT_PREFIX/envs/sat/bin/python" -c "import skyfield; print('skyfield', skyfield.__version__)"
EOF_ENV

    echo "== files =="
    "${SSH[@]}" 'sudo mkdir -p /usr/local/lib/kikicom && sudo tee /usr/local/lib/kikicom/sat-plan.py >/dev/null && sudo chmod 0755 /usr/local/lib/kikicom/sat-plan.py' < scripts/sat/sat-plan.py
    "${SSH[@]}" 'cat > ~/sat/config.json' < scripts/sat/config.json
    printf '{"lat": %s, "lon": %s, "elev_m": 30}\n' "$LAT" "$LON" | "${SSH[@]}" 'umask 077; cat > ~/sat/location.json'

    echo "== systemd =="
    "${SSH[@]}" "sudo tee /etc/systemd/system/sat-plan.service >/dev/null" <<EOF_UNIT
[Unit]
Description=kikicom: CubeSat pass plan (writes ~/sat/schedule.json; never touches the dongle)
After=network-online.target

[Service]
Type=oneshot
User=${REMOTE_USER}
Nice=19
IOSchedulingClass=idle
ExecStart=${ENV_PY} /usr/local/lib/kikicom/sat-plan.py --home ${REMOTE_HOME}/sat
EOF_UNIT
    "${SSH[@]}" "sudo tee /etc/systemd/system/sat-plan.timer >/dev/null" <<'EOF_UNIT'
[Unit]
Description=kikicom: refresh the CubeSat pass plan every 6 hours

[Timer]
OnCalendar=*-*-* 00,06,12,18:10:00
Persistent=true

[Install]
WantedBy=timers.target
EOF_UNIT
    "${SSH[@]}" 'sudo systemctl daemon-reload && sudo systemctl enable --now sat-plan.timer && sudo systemctl start sat-plan.service'
    echo "installed. check with: $0 status"
    ;;
  status)
    "${SSH[@]}" 'systemctl list-timers sat-plan.timer --no-pager; echo "--- last runs ---"; tail -n 3 ~/sat/plan-history.jsonl; echo "--- selected windows ---"; awk -F"\t" "NR==1 || \$7==\"yes\"" ~/sat/schedule.tsv'
    ;;
  uninstall)
    "${SSH[@]}" 'sudo systemctl disable --now sat-plan.timer 2>/dev/null || true; sudo rm -f /etc/systemd/system/sat-plan.service /etc/systemd/system/sat-plan.timer /usr/local/lib/kikicom/sat-plan.py; sudo systemctl daemon-reload'
    echo "removed the units and script (kept ~/sat and ~/kikicom-sat on the RPi)"
    ;;
  *)
    echo "usage: $0 [install|status|uninstall]" >&2
    exit 1
    ;;
esac
