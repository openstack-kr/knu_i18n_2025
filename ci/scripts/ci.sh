#!/bin/bash
set -e

# Usage: bash ci.sh <project> <branch> [languages...]
# Example: bash ci.sh neutron-lib master ko_KR ja zh_CN

if [ $# -lt 2 ]; then
  echo "Usage: $0 <project> <branch> [languages...]"
  echo "Example: $0 neutron-lib master ko_KR ja"
  exit 1
fi

PROJECT=$1
BRANCH=$2
shift 2
LANGUAGES=("$@")

# Default to ko_KR if no languages specified
if [ ${#LANGUAGES[@]} -eq 0 ]; then
  LANGUAGES=("ko_KR")
fi

echo "[ci.sh] Project: $PROJECT"
echo "[ci.sh] Branch: $BRANCH"
echo "[ci.sh] Languages: ${LANGUAGES[@]}"
echo

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
MODEL="llama3.2:3b"
if command -v ollama >/dev/null 2>&1; then
  echo "[ci.sh] pulling model: $MODEL ..."
  # if the model already exists, this is a quick no-op
  ollama pull $MODEL || echo "[ci.sh] warning: could not pull model (ollama daemon running?)"
else
  echo "[ci.sh] warning: ollama is not installed or not in PATH. skipping model pull."
fi

# --- 3) Pipeline ---
# Add src/ to PYTHONPATH so modules can import each other
export PYTHONPATH="${PYTHONPATH:+${PYTHONPATH}:}$(pwd)/src"

echo "=== [1/3] Find added or edited msgid in target file and extract to .pot file ==="
python src/commit_diff.py --project "$PROJECT" --repo-dir "$REPO_DIR"
echo

echo "=== [2/3] Translate file ==="
for lang in "${LANGUAGES[@]}"; do
  echo "[ci.sh] Translating to $lang..."
  python src/translate.py --project "$PROJECT" --repo-dir "$REPO_DIR" --lang "$lang"
done
echo

echo "=== [3/3] Merge AI translated file to original file ==="
for lang in "${LANGUAGES[@]}"; do
  echo "[ci.sh] Merging translations for $lang..."
  python src/merge_po.py --project "$PROJECT" --repo-dir "$REPO_DIR" --lang "$lang"
done

echo "[ci.sh] completed successfully!"
