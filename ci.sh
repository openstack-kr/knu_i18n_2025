#!/bin/bash
set -e

CONFIG_FILE=${1:-"config.yaml"}
echo "[ci.sh] Using config: $CONFIG_FILE"
echo

# ci 환경에서는 추후 ollama가 아니라 llama.cpp로 변경하는 것이 나음
# 1) make sure the model is available in local ollama
MODEL=$(grep 'model:' "$CONFIG_FILE" | head -n 1 | sed 's/.*model: "\(.*\)"/\1/')
if command -v ollama >/dev/null 2>&1; then
  echo "[local.sh] pulling model: $MODEL ..."
  # if the model already exists, this is a quick no-op
  ollama pull $MODEL || echo "[local.sh] warning: could not pull model (ollama daemon running?)"
else
  echo "[local.sh] warning: ollama is not installed or not in PATH. skipping model pull."
fi

echo "=== [1/3] Running diff.py ==="
python commit_diff.py --config "$CONFIG_FILE"
echo

echo "=== [2/3] Running translate.py ==="
python translate.py --config "$CONFIG_FILE"
echo

echo "=== [3/3] Running merge.py ==="
python merge_po.py --config "$CONFIG_FILE"
echo

echo "[ci.sh] Pipeline completed successfully!"