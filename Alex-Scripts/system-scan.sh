#!/usr/bin/env bash
set -euo pipefail

iso_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

memory_used="N/A"
if command -v free >/dev/null 2>&1; then
  memory_used="$(free -m | awk '/Mem:/{print $3"MB"}')"
elif command -v vm_stat >/dev/null 2>&1; then
  memory_used="$(vm_stat | awk '/Pages active/ {print $3}' | tr -d '.') pages"
fi

load_avg="N/A"
if [[ -f /proc/loadavg ]]; then
  load_avg="$(cat /proc/loadavg)"
elif command -v uptime >/dev/null 2>&1; then
  load_avg="$(uptime | awk -F'load averages?: ' '{print $2}')"
fi

cat <<JSON
{
  "timestamp": "$(iso_now)",
  "hostname": "$(hostname)",
  "uptime": "$(uptime -p 2>/dev/null || uptime)",
  "disk_usage": "$(df -h / | tail -1 | awk '{print $5}')",
  "memory_used": "${memory_used}",
  "load_avg": "${load_avg}",
  "node_running": $(pgrep -f 'src/gateway.js' >/dev/null 2>&1 && echo true || echo false),
  "flask_running": $(pgrep -f 'app.py' >/dev/null 2>&1 && echo true || echo false),
  "telegram_running": $(pgrep -f 'telegram_bot.py' >/dev/null 2>&1 && echo true || echo false)
}
JSON
