#!/usr/bin/env bash
set -euo pipefail

if [[ "${CHANGELOG_AUTO_UPDATE:-false}" != "true" ]]; then
  exit 0
fi

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

COMMITS="$(git log --since='24 hours ago' --oneline || true)"
[[ -n "$COMMITS" ]] || exit 0

{
  echo
  echo "## $(date -u +%Y-%m-%d)"
  echo "$COMMITS" | sed 's/^/- /'
} >> CHANGELOG.md
