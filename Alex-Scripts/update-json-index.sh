#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT="$PROJECT_ROOT/instance/file-index.json"
mkdir -p "$PROJECT_ROOT/instance"

if command -v jq >/dev/null 2>&1; then
  find "$PROJECT_ROOT" \
    -path "$PROJECT_ROOT/.git" -prune -o \
    -path "$PROJECT_ROOT/node_modules" -prune -o \
    -path "$PROJECT_ROOT/__pycache__" -prune -o \
    -path "$PROJECT_ROOT/logs" -prune -o \
    -print | while read -r p; do
      rel="${p#$PROJECT_ROOT/}"
      if [[ -d "$p" ]]; then
        type="directory"
        size=0
      else
        type="${p##*.}"
        [[ "$p" == *.* ]] || type="file"
        size="$(stat -f%z "$p" 2>/dev/null || stat -c%s "$p" 2>/dev/null || echo 0)"
      fi
      modified="$(date -u -r "$p" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")"
      jq -n --arg path "$rel" --argjson size "$size" --arg modified "$modified" --arg type "$type" '{path:$path,size:$size,modified:$modified,type:$type}'
    done | jq -s '.' > "$OUTPUT"
else
  echo '[' > "$OUTPUT"
  first=true
  while IFS= read -r p; do
    rel="${p#$PROJECT_ROOT/}"
    if [[ -d "$p" ]]; then
      type="directory"
      size=0
    else
      type="${p##*.}"
      [[ "$p" == *.* ]] || type="file"
      size="$(stat -f%z "$p" 2>/dev/null || stat -c%s "$p" 2>/dev/null || echo 0)"
    fi
    modified="$(date -u -r "$p" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "")"
    $first || echo ',' >> "$OUTPUT"
    first=false
    printf '{"path":"%s","size":%s,"modified":"%s","type":"%s"}' "$rel" "$size" "$modified" "$type" >> "$OUTPUT"
  done < <(find "$PROJECT_ROOT" \
    -path "$PROJECT_ROOT/.git" -prune -o \
    -path "$PROJECT_ROOT/node_modules" -prune -o \
    -path "$PROJECT_ROOT/__pycache__" -prune -o \
    -path "$PROJECT_ROOT/logs" -prune -o \
    -print)
  echo ']' >> "$OUTPUT"
fi
