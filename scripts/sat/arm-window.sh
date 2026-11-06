#!/usr/bin/env bash
# kikicom: schedule one satellite window on the RPi (P1, manual). Run on slate.
#
#   KIKICOM_RPI_HOST=<rpi ssh name> ./scripts/sat/arm-window.sh arm NAME FREQ_MHZ "YYYY-MM-DD HH:MM:SS" DURATION_S [GAIN_DB]
#   KIKICOM_RPI_HOST=<rpi ssh name> ./scripts/sat/arm-window.sh status
#   KIKICOM_RPI_HOST=<rpi ssh name> ./scripts/sat/arm-window.sh disarm
#
# The start time is in the RPi's local time zone (JST). Two transient systemd
# timers are created:
#   kikicom-sat-window-<tag>  runs sat-window.sh at the start time
#   kikicom-sat-guard-<tag>   starts adsb-research again 90 s after the
#                             window should have ended, whatever happened
# Both vanish after they fire. `disarm` removes them before that.
set -euo pipefail

ACTION="${1:-status}"
HOST="${KIKICOM_RPI_HOST:?set KIKICOM_RPI_HOST to the ssh name of the RPi}"
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
SSH=(ssh -o ConnectTimeout=10 "$HOST")

case "$ACTION" in
  arm)
    NAME="${2:?NAME}"; FREQ_MHZ="${3:?FREQ_MHZ}"; START="${4:?start 'YYYY-MM-DD HH:MM:SS'}"; DUR="${5:?DURATION_S}"; GAIN="${6:-40.2}"
    FREQ_HZ="$(python3 -c "print(round(float('$FREQ_MHZ')*1e6))")"
    TAG="$(echo "$NAME" | tr -c 'A-Za-z0-9\n' '-')-$(echo "$START" | tr -c '0-9\n' '-' | sed 's/-*$//')"
    REMOTE_USER="$("${SSH[@]}" 'id -un')"
    DRYENV=""
    # KIKICOM_ARM_DRYRUN=1: the window does not stop adsb-research or touch the dongle (for testing)
    [ "${KIKICOM_ARM_DRYRUN:-0}" = 1 ] && DRYENV="--setenv=KIKICOM_SAT_DRYRUN=1"

    "${SSH[@]}" 'sudo mkdir -p /usr/local/lib/kikicom && sudo tee /usr/local/lib/kikicom/sat-window.sh >/dev/null && sudo chmod 0755 /usr/local/lib/kikicom/sat-window.sh' < scripts/sat/sat-window.sh
    "${SSH[@]}" 'sudo tee /usr/local/lib/kikicom/iq-analyze.py >/dev/null && sudo chmod 0755 /usr/local/lib/kikicom/iq-analyze.py' < scripts/sat/iq-analyze.py

    "${SSH[@]}" "bash -s" <<EOF
set -euo pipefail
START_EPOCH=\$(date -d '$START' +%s)
NOW=\$(date +%s)
if [ "\$START_EPOCH" -le "\$((NOW + 60))" ]; then echo "start time is less than 60 s away (or past); refusing" >&2; exit 1; fi
GUARD="\$(date -d "@\$((START_EPOCH + $DUR + 90))" '+%Y-%m-%d %H:%M:%S')"
sudo systemd-run --quiet --unit="kikicom-sat-window-$TAG" --on-calendar="$START" \
  --timer-property=AccuracySec=1s -p User=$REMOTE_USER $DRYENV \
  /usr/local/lib/kikicom/sat-window.sh "$NAME" "$FREQ_HZ" "$DUR" "$GAIN"
sudo systemd-run --quiet --unit="kikicom-sat-guard-$TAG" --on-calendar="\$GUARD" \
  --timer-property=AccuracySec=1s \
  /bin/systemctl start adsb-research.service
echo "armed: window at $START for ${DUR}s ($FREQ_HZ Hz, gain $GAIN dB); guard at \$GUARD"
systemctl list-timers 'kikicom-sat-*' --no-pager
EOF
    ;;
  status)
    "${SSH[@]}" "systemctl list-timers 'kikicom-sat-*' --no-pager; echo '--- windows.jsonl ---'; tail -n 5 ~/sat/windows.jsonl 2>/dev/null || true; systemctl is-active adsb-research adsb-logger"
    ;;
  disarm)
    "${SSH[@]}" "sudo systemctl stop 'kikicom-sat-window-*.timer' 'kikicom-sat-guard-*.timer' 2>/dev/null || true; systemctl list-timers 'kikicom-sat-*' --no-pager"
    ;;
  *)
    echo "usage: $0 arm NAME FREQ_MHZ 'YYYY-MM-DD HH:MM:SS' DURATION_S [GAIN_DB] | status | disarm" >&2
    exit 1
    ;;
esac
