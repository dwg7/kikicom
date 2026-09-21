#!/usr/bin/env bash
# adsb.lol 比の受信率の定点観測(15分おき)。slate の LaunchAgent com.dwg7.kikicom.coverage-check として登録する。
# 入口は scripts/coverage-record.sh(ssh を bash 側で行う)。仕組みは scripts/install-launch-agent.sh(外付けボリュームの TCC 回避のため
# スクリプトを ~/.local/lib/kikicom/ にコピーして実行)。
#   ./scripts/install-coverage-timer.sh [install|uninstall|status]
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
case "${1:-install}" in
  install)   KIKICOM_AGENT_EXTRA_FILES=scripts/coverage-check.py exec ./scripts/install-launch-agent.sh install coverage-check scripts/coverage-record.sh 900 ;;
  uninstall) ./scripts/install-launch-agent.sh uninstall coverage-check scripts/coverage-record.sh; rm -f ~/.local/lib/kikicom/coverage-check.py ;;
  status)    exec ./scripts/install-launch-agent.sh status coverage-check ;;
  *) echo "usage: $0 [install|uninstall|status]" >&2; exit 1 ;;
esac
