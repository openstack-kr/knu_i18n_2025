#!/bin/bash
set -e

CONFIG_FILE=${1:-"ci_config.yaml"}

echo "[ci.sh] Using config: $CONFIG_FILE"
echo

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