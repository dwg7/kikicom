#!/usr/bin/env bash
# kikicom: one satellite window (P1, manual). Runs on the RPi.
#
# Borrows the RTL-SDR from adsb-research, records raw IQ, and always gives it
# back (trap on EXIT). arm-window.sh starts this at the right time with
# systemd-run and adds a separate guard timer that restarts adsb-research even
# if this script dies (README D4).
#
#   sat-window.sh NAME FREQ_HZ DURATION_S [GAIN_DB] [RATE_HZ]
#
# Output (under $KIKICOM_SAT_HOME, default ~/sat):
#   iq/<NAME>-<UTC stamp>.u8        raw rtl_sdr samples (unsigned 8-bit I,Q)
#   iq/<NAME>-<UTC stamp>.json      what was recorded and when
#   windows.jsonl                   one line per window: when ADS-B was down
#                                   (the coverage baseline must skip these)
#
# KIKICOM_SAT_DRYRUN=1: do not touch the services or the dongle; write random
# bytes instead of a recording (for testing this script).
set -u

NAME="${1:?usage: sat-window.sh NAME FREQ_HZ DURATION_S [GAIN_DB] [RATE_HZ]}"
FREQ="${2:?freq_hz}"
DUR="${3:?duration_s}"
GAIN="${4:-40.2}"
RATE="${5:-250000}"
HOME_DIR="${KIKICOM_SAT_HOME:-$HOME/sat}"
DRY="${KIKICOM_SAT_DRYRUN:-0}"

mkdir -p "$HOME_DIR/iq"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BASE="$HOME_DIR/iq/${NAME}-${STAMP}"
LOG="$HOME_DIR/windows.jsonl"
T_STOP=""; T_REC=""; T_REC_END=""; RC=-1

restore() {
  trap - EXIT INT TERM
  if [ "$DRY" != 1 ]; then
    sudo -n systemctl start adsb-research.service
    sudo -n systemctl start adsb-logger.service
  fi
  local t_back; t_back="$(date +%s.%N)"
  printf '{"kind":"window","name":"%s","freq_hz":%s,"adsb_down_epoch":%s,"adsb_back_epoch":%s,"rc":%s,"dry":%s,"file":"%s"}\n' \
    "$NAME" "$FREQ" "${T_STOP:-null}" "$t_back" "$RC" "$([ "$DRY" = 1 ] && echo true || echo false)" "$BASE.u8" >> "$LOG"
}
trap restore EXIT
trap 'exit 130' INT TERM

T_STOP="$(date +%s.%N)"
if [ "$DRY" != 1 ]; then
  sudo -n systemctl stop adsb-research.service
  sleep 1
fi

T_REC="$(date +%s.%N)"
if [ "$DRY" = 1 ]; then
  head -c $((2 * RATE * DUR)) /dev/urandom > "$BASE.u8"; RC=$?
else
  timeout $((DUR + 20)) rtl_sdr -f "$FREQ" -s "$RATE" -g "$GAIN" -n $((RATE * DUR)) "$BASE.u8" 2> "$BASE.rtl_sdr.log"; RC=$?
fi
T_REC_END="$(date +%s.%N)"

NBYTES="$(stat -c %s "$BASE.u8" 2>/dev/null || echo 0)"
printf '{"name":"%s","freq_hz":%s,"samp_rate":%s,"gain_db":%s,"duration_s":%s,"t_launch_epoch":%s,"t_end_epoch":%s,"bytes":%s,"rc":%s,"dry":%s}\n' \
  "$NAME" "$FREQ" "$RATE" "$GAIN" "$DUR" "$T_REC" "$T_REC_END" "$NBYTES" "$RC" "$([ "$DRY" = 1 ] && echo true || echo false)" > "$BASE.json"
exit 0
