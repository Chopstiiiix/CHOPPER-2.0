#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CRON_FILE="$PROJECT_DIR/cron/alex"
TMP_CRON="$(mktemp)"
MARKER="# CHOPPER-ALEX"

install_cron() {
  if crontab -l 2>/dev/null | grep -q "$MARKER"; then
    echo "CHOPPER cron jobs already installed. Skipping."
    return 0
  fi

  cp "$CRON_FILE" "$TMP_CRON"
  sed -i.bak "s|/opt/chopper|$PROJECT_DIR|g" "$TMP_CRON" 2>/dev/null || sed -i "s|/opt/chopper|$PROJECT_DIR|g" "$TMP_CRON"

  {
    crontab -l 2>/dev/null || true
    echo "$MARKER"
    cat "$TMP_CRON"
    echo "$MARKER END"
  } | crontab -

  echo "Installed CHOPPER cron jobs."
}

remove_cron() {
  if ! crontab -l 2>/dev/null | grep -q "$MARKER"; then
    echo "No CHOPPER cron jobs found."
    return 0
  fi

  crontab -l | awk -v marker="$MARKER" '
    $0 ~ marker {skip = !skip; next}
    skip {next}
    {print}
  ' | crontab -

  echo "Removed CHOPPER cron jobs."
}

if [[ "${1:-}" == "--remove" ]]; then
  remove_cron
  exit 0
fi

echo "Install CHOPPER cron jobs? (y/N)"
read -r ans
if [[ "$ans" =~ ^[Yy]$ ]]; then
  install_cron
else
  echo "Cancelled."
fi
