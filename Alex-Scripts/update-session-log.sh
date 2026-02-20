#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
if [[ "$MODE" != "start" && "$MODE" != "stop" ]]; then
  echo "Usage: $0 <start|stop>" >&2
  exit 1
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$PROJECT_ROOT/logs"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] SESSION ${MODE} user=${USER:-unknown} host=$(hostname)" >> "$PROJECT_ROOT/logs/session.log"
