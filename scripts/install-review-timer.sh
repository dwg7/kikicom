#!/usr/bin/env bash
# Register/unregister scripts/review-aircraft.py (hourly "要確認" list) as a
# macOS LaunchAgent on slate. Same pattern as install-sync-timer.sh: the
# script is copied to ~/.local/lib/kikicom/ because TCC blocks launchd agents
# from executing files on the external volume this checkout lives on.
set -euo pipefail

ACTION="${1:-install}"
LABEL="com.dwg7.kikicom.review-aircraft"
PLIST="$HOME/Library/LaunchAgents/${LABEL}.plist"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$HOME/Library/Logs/kikicom"
INSTALLED_SCRIPT="$HOME/.local/lib/kikicom/review-aircraft.py"
INTERVAL_SEC="${KIKICOM_REVIEW_INTERVAL_SEC:-3600}"

case "$ACTION" in
  install)
    mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents" "$(dirname "$INSTALLED_SCRIPT")"
    install -m 0755 "$REPO_DIR/scripts/review-aircraft.py" "$INSTALLED_SCRIPT"
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
        <string>/usr/bin/env</string>
        <string>PATH=/opt/homebrew/bin:/usr/bin:/bin</string>
        <string>/usr/bin/python3</string>
        <string>${INSTALLED_SCRIPT}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${HOME}</string>
    <key>StartInterval</key>
    <integer>${INTERVAL_SEC}</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/review-aircraft.log</string>
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/review-aircraft.log</string>
</dict>
</plist>
EOF_PLIST
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load -w "$PLIST"
    echo "installed and loaded: $PLIST (every ${INTERVAL_SEC}s)"
    echo "reports: ~/kikicom-data/review/YYYY-MM-DD.md  logs: ${LOG_DIR}/review-aircraft.log"
    ;;
  uninstall)
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST" "$INSTALLED_SCRIPT"
    echo "unloaded and removed: $PLIST"
    ;;
  status)
    launchctl list | grep "$LABEL" || echo "not loaded"
    [ -f "${LOG_DIR}/review-aircraft.log" ] && tail -8 "${LOG_DIR}/review-aircraft.log"
    ;;
  *)
    echo "usage: $0 [install|uninstall|status]" >&2
    exit 1
    ;;
esac
