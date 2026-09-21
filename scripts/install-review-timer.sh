#!/usr/bin/env bash
# 要確認の機体の日次一覧(毎時)。slate の LaunchAgent com.dwg7.kikicom.review-aircraft として登録する。
# 仕組みは scripts/install-launch-agent.sh(外付けボリュームの TCC 回避のため
# スクリプトを ~/.local/lib/kikicom/ にコピーして実行)。
#   ./scripts/install-review-timer.sh [install|uninstall|status]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
case "${1:-install}" in
  install)   KIKICOM_AGENT_EXTRA_FILES=scripts/watchlist.json exec ./scripts/install-launch-agent.sh install review-aircraft scripts/review-aircraft.py 3600 ;;
  uninstall) exec ./scripts/install-launch-agent.sh uninstall review-aircraft scripts/review-aircraft.py ;;
  status)    exec ./scripts/install-launch-agent.sh status review-aircraft ;;
  *) echo "usage: $0 [install|uninstall|status]" >&2; exit 1 ;;
esac
