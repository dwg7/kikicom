#!/usr/bin/env bash
# RPi の位置ログを slate へ rsync(15分おき)。slate の LaunchAgent com.dwg7.kikicom.sync-adsb-log として登録する。
# 仕組みは scripts/install-launch-agent.sh(外付けボリュームの TCC 回避のため
# スクリプトを ~/.local/lib/kikicom/ にコピーして実行)。
#   ./scripts/install-sync-timer.sh [install|uninstall|status]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
case "${1:-install}" in
  install)   exec ./scripts/install-launch-agent.sh install sync-adsb-log scripts/sync-adsb-log.sh 900 ;;
  uninstall) exec ./scripts/install-launch-agent.sh uninstall sync-adsb-log scripts/sync-adsb-log.sh ;;
  status)    exec ./scripts/install-launch-agent.sh status sync-adsb-log ;;
  *) echo "usage: $0 [install|uninstall|status]" >&2; exit 1 ;;
esac
