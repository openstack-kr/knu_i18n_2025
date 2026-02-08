#!/bin/bash
set -e

CONFIG_FILE=${1:-"config.yaml"}
echo "[local.sh] Using config: $CONFIG_FILE"
echo

# 1) make sure the model is available in local ollama
MODEL=$(grep 'model:' "$CONFIG_FILE" | head -n 1 | sed 's/.*model: "\(.*\)"/\1/')
if command -v ollama >/dev/null 2>&1; then
  echo "[local.sh] pulling model: $MODEL ..."
  # if the model already exists, this is a quick no-op
  ollama pull $MODEL || echo "[local.sh] warning: could not pull model (ollama daemon running?)"
else
  echo "[local.sh] warning: ollama is not installed or not in PATH. skipping model pull."
fi

# config에서 target 파일 경로 복원하여 존재 여부 확인
LANG=$(python -c "
import yaml, sys
cfg = yaml.safe_load(open('$CONFIG_FILE'))
langs = cfg['languages']
print(langs[0] if isinstance(langs, list) else langs)
")
TARGET_FILE=$(python -c "
import yaml
cfg = yaml.safe_load(open('$CONFIG_FILE'))
print(cfg['target_file'])
")
TRANS_PO="./data/target/${LANG}/${TARGET_FILE}"

if [ ! -f "$TRANS_PO" ]; then
  echo "[local.sh] ERROR: Target PO not found: $TRANS_PO"
  exit 1
fi

echo "=== [1/2] Extracting untranslated strings into a .pot file ==="
python src/filter_pot.py --config "$CONFIG_FILE"
echo

echo "=== [2/2] Translate .pot file ==="
python src/translate.py --config "$CONFIG_FILE"
echo

echo "[local.sh] Completed successfully!"
