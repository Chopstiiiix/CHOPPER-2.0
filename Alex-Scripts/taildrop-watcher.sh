#!/usr/bin/env bash
set -euo pipefail

TAILDROP_DIR="${TAILDROP_DIR:-$HOME/Taildrop}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INCOMING_DIR="${PROJECT_ROOT}/instance/incoming"
LOG_FILE="${PROJECT_ROOT}/logs/taildrop.log"

mkdir -p "$INCOMING_DIR" "${PROJECT_ROOT}/logs"

log() {
  printf '[%s] [TAILDROP] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" | tee -a "$LOG_FILE"
}

handle_file() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  local base
  base="$(basename "$f")"
  local size
  size="$(stat -f%z "$f" 2>/dev/null || stat -c%s "$f" 2>/dev/null || echo 0)"
  log "new file=${base} size=${size}"
  mv "$f" "$INCOMING_DIR/$base"
  log "moved file=${base} to instance/incoming"
}

if command -v inotifywait >/dev/null 2>&1; then
  log "watching with inotifywait dir=$TAILDROP_DIR"
  mkdir -p "$TAILDROP_DIR"
  while inotifywait -e create -e moved_to "$TAILDROP_DIR" >/dev/null 2>&1; do
    for f in "$TAILDROP_DIR"/*; do
      handle_file "$f"
    done
  done
else
  log "inotifywait not found; polling every 30s dir=$TAILDROP_DIR"
  mkdir -p "$TAILDROP_DIR"
  while true; do
    for f in "$TAILDROP_DIR"/*; do
      handle_file "$f"
    done
    sleep 30
  done
fi
