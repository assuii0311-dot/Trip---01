#!/usr/bin/env bash
# 배포용 사이트 디렉터리를 만든다: app/ 내용 + data/. GitHub Pages 워크플로와 로컬 확인에 같이 쓴다.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$ROOT/site}"
rm -rf "$OUT"; mkdir -p "$OUT"
cp -r "$ROOT/app/." "$OUT/"
if [ -d "$ROOT/data" ]; then mkdir -p "$OUT/data"; cp -r "$ROOT/data/." "$OUT/data/"; fi
touch "$OUT/.nojekyll"
echo "site: $OUT ($(du -sh "$OUT" | cut -f1))"
