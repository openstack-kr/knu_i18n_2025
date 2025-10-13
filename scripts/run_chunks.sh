#!/usr/bin/env bash
set -euo pipefail
CHUNK_DIR="work/releasenotes_chunks"
OUT_DIR="work/releasenotes_out"
GLOSS="glossary/glossary.json"
mkdir -p "$OUT_DIR"

start=$(date +%s)
find "$CHUNK_DIR" -name '*.json' | sort | \
  xargs -I{} -P2 bash -c 'python scripts/translate_chunk.py "{}" "'"$GLOSS"'" "'"$OUT_DIR"'/$(basename "{}")"'
end=$(date +%s)

echo "✅ All chunks translated in $((end-start))s"
