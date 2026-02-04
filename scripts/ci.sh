#!/bin/bash
set -e

CONFIG_FILE=${1:-"config.yaml"}
echo "[ci.sh] Using config: $CONFIG_FILE"
echo

# --- config에서 project, branch 읽기 ---
PROJECT=$(python -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['project'])")
BRANCH=$(python -c "import yaml; print(yaml.safe_load(open('$CONFIG_FILE'))['git']['branch'])")
REPO_DIR="./workspace/${PROJECT}"
REPO_URL="https://opendev.org/openstack/${PROJECT}.git"

# --- 1) Git 저장소 준비 (clone / pull + branch 체크아웃) ---
# *** 실제 파이프라인에서는 clone할 필요가 없을 것으로 추정) ***
if [ -d "${REPO_DIR}/.git" ]; then
  echo "[ci.sh] Updating existing repo at ${REPO_DIR}..."
  git -C "$REPO_DIR" reset --hard HEAD
  git -C "$REPO_DIR" checkout "$BRANCH"
  git -C "$REPO_DIR" pull
else
  echo "[ci.sh] Cloning repo to ${REPO_DIR}..."
  # HEAD와 HEAD~1만 가져옴. 용량과 시간 모두 최소화
  git clone --depth 2 "$REPO_URL" "$REPO_DIR"
  git -C "$REPO_DIR" checkout "$BRANCH"
fi

# --- 2) ollama model pull ---
# ci 환경에서는 추후 ollama가 아니라 llama.cpp로 변경하는 것이 나음
MODEL=$(grep 'model:' "$CONFIG_FILE" | head -n 1 | sed 's/.*model: "\(.*\)"/\1/')
if command -v ollama >/dev/null 2>&1; then
  echo "[ci.sh] pulling model: $MODEL ..."
  # if the model already exists, this is a quick no-op
  ollama pull $MODEL || echo "[ci.sh] warning: could not pull model (ollama daemon running?)"
else
  echo "[ci.sh] warning: ollama is not installed or not in PATH. skipping model pull."
fi

# --- 3) Pipeline ---
echo "=== [1/3] Find added or edited msgid in target file and extract to .pot file ==="
python src/commit_diff.py --config "$CONFIG_FILE" --repo-dir "$REPO_DIR"
echo

echo "=== [2/3] Translate file ==="
python src/translate.py --config "$CONFIG_FILE"
echo

echo "=== [3/3] Merge AI translated file to original file ==="
python src/merge_po.py --config "$CONFIG_FILE" --repo-dir "$REPO_DIR"

echo "[ci.sh] completed successfully!"
