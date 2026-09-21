#!/usr/bin/env bash
# Register/unregister scripts/sync-adsb-log.sh as a periodic macOS
# LaunchAgent on the Mac mini role machine (slate). Same pattern as
# kikimimi's scripts/install-sync-timer.sh: a LaunchAgent (not a Daemon) so
# it runs with the logged-in user's SSH keys, which rsync to the RPi needs.
#
# Run `./scripts/sync-adsb-log.sh` by hand once and confirm it works before
# installing this.
#
# The script is COPIED to ~/.local/lib/kikicom/ and run from there: this
# checkout lives on an external volume (/Volumes/...), and macOS privacy
# protection (TCC) blocks launchd agents from executing files there
# ("Operation not permitted"). Re-run `install` after editing the script.
set -euo pipefail

ACTION="${1:-install}"
LABEL="com.dwg7.kikicom.sync-adsb-log"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$HOME/Library/Logs/kikicom"
INTERVAL_SEC="${KIKICOM_SYNC_INTERVAL_SEC:-900}"
INSTALLED_SCRIPT="$HOME/.local/lib/kikicom/sync-adsb-log.sh"

case "$ACTION" in
  install)
    mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents" "$(dirname "$INSTALLED_SCRIPT")"
    install -m 0755 "$REPO_DIR/scripts/sync-adsb-log.sh" "$INSTALLED_SCRIPT"
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
        <string>${INSTALLED_SCRIPT}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${HOME}</string>
    <key>StartInterval</key>
    <integer>${INTERVAL_SEC}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/sync-adsb-log.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/sync-adsb-log.log</string>
</dict>
</plist>
EOF_PLIST
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load -w "$PLIST"
    echo "installed and loaded: $PLIST"
    echo "runs every ${INTERVAL_SEC}s. logs: ${LOG_DIR}/sync-adsb-log.log"
    echo "uninstall with: ./scripts/install-sync-timer.sh uninstall"
    ;;
  uninstall)
    if [ -f "$PLIST" ]; then
      launchctl unload "$PLIST" 2>/dev/null || true
      rm -f "$PLIST" "$INSTALLED_SCRIPT"
      echo "unloaded and removed: $PLIST"
    else
      echo "not installed: $PLIST"
    fi
    ;;
  status)
    if launchctl list | grep -q "$LABEL"; then
      echo "loaded:"; launchctl list "$LABEL"
    else
      echo "not loaded"
    fi
    echo "log: ${LOG_DIR}/sync-adsb-log.log"
    [ -f "${LOG_DIR}/sync-adsb-log.log" ] && tail -5 "${LOG_DIR}/sync-adsb-log.log"
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
