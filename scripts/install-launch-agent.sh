#!/usr/bin/env bash
# Generic installer for kikicom's periodic jobs on slate (macOS LaunchAgents).
#
#   ./scripts/install-launch-agent.sh install   NAME SCRIPT INTERVAL_SEC [ARGS...]
#   ./scripts/install-launch-agent.sh uninstall NAME SCRIPT
#   ./scripts/install-launch-agent.sh status    NAME
#
# The label is com.dwg7.kikicom.NAME. SCRIPT (a path under scripts/) is COPIED
# to ~/.local/lib/kikicom/ and run from there: this checkout lives on an
# external volume and macOS privacy protection (TCC) blocks launchd agents
# from executing files there ("Operation not permitted"). Re-run install
# after editing the script. A LaunchAgent (not a Daemon) runs with the
# logged-in user's SSH keys, which the jobs need to reach the RPi.
# Same pattern as kikimimi's scripts/install-sync-timer.sh.
set -euo pipefail

ACTION="${1:?usage: $0 install|uninstall|status NAME [SCRIPT INTERVAL_SEC ARGS...]}"
NAME="${2:?NAME required}"
LABEL="com.dwg7.kikicom.${NAME}"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB_DIR="$HOME/.local/lib/kikicom"
LOG_DIR="$HOME/Library/Logs/kikicom"
LOG="${LOG_DIR}/${NAME}.log"

case "$ACTION" in
  install)
    SCRIPT="${3:?SCRIPT required}"
    INTERVAL="${4:?INTERVAL_SEC required}"
    shift 4
    INSTALLED="$LIB_DIR/$(basename "$SCRIPT")"
    mkdir -p "$LOG_DIR" "$LIB_DIR" "$HOME/Library/LaunchAgents"
    install -m 0755 "$REPO_DIR/$SCRIPT" "$INSTALLED"
    # helpers the entry script calls from the same directory (space-separated)
    for extra in ${KIKICOM_AGENT_EXTRA_FILES:-}; do
      install -m 0755 "$REPO_DIR/$extra" "$LIB_DIR/$(basename "$extra")"
    done
    # macOS の「ローカルネットワーク」プライバシー保護により、launchd 配下で
    # Homebrew の(フレームワーク版)python3 から起動した ssh は RPi(m329.local)に
    # "No route to host" で拒否される。bash や rsync から起動した ssh は通る
    # (2026-09-21 実測)。RPi に ssh するジョブは bash のスクリプトを入口にすること。
    CMD="export PATH=/opt/homebrew/bin:/usr/bin:/bin; '${INSTALLED}'"
    for a in "$@"; do CMD="${CMD} '${a}'"; done
    CMD="${CMD}; exit \$?"
    cat > "$PLIST" <<EOF_PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>${CMD}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${HOME}</string>
    <key>StartInterval</key>
    <integer>${INTERVAL}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG}</string>
    <key>StandardErrorPath</key>
    <string>${LOG}</string>
</dict>
</plist>
EOF_PLIST
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load -w "$PLIST"
    echo "installed and loaded: $PLIST (every ${INTERVAL}s) log: $LOG"
    ;;
  uninstall)
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    [ -n "${3:-}" ] && rm -f "$LIB_DIR/$(basename "$3")"
    echo "unloaded and removed: $PLIST"
    ;;
  status)
    launchctl list | grep "$LABEL" || echo "not loaded: $LABEL"
    [ -f "$LOG" ] && tail -5 "$LOG"
    ;;
  *)
    echo "usage: $0 install|uninstall|status NAME [SCRIPT INTERVAL_SEC ARGS...]" >&2
    exit 1
    ;;
esac
