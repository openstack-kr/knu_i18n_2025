#!/bin/bash
# =============================================================
# OpenWebUI Arena 전체 파이프라인
# config.yaml 설정 기반으로 번역 → 평가 → 리포트 자동 실행
#
# 사용법:
#   bash main.sh
#   bash main.sh --skip-translate   # 번역 건너뛰고 평가부터
# =============================================================
set -e
cd "$(dirname "$0")"   # 스크립트 위치(openwebui/)를 작업 디렉토리로

# ── Step 0: 의존성 설치 ────────────────────────
echo "▶ Step 0: 의존성 설치"
pip install -q -r src/requirements.txt
echo "Step 0 완료"
echo ""

# --- .env 로드 ---
if [ -f .env ]; then
    set -a && source .env && set +a
fi

if [ -z "$OPENWEBUI_API_KEY" ]; then
    echo "OPENWEBUI_API_KEY가 설정되지 않았습니다."
    echo "   export OPENWEBUI_API_KEY=sk-... 또는 .env 파일에 추가하세요."
    exit 1
fi

# --- config.yaml에서 값 읽기 ---
MODELS=$(python3 -c "
import yaml
c = yaml.safe_load(open('config.yaml'))
print(','.join(c['llm']['models']))
")
JUDGE_MODEL=$(python3 -c "
import yaml
c = yaml.safe_load(open('config.yaml'))
print(c['llm'].get('judge_model', 'qwen2.5:7b'))
")
TARGET_FILE=$(python3 -c "
import yaml, os
c = yaml.safe_load(open('config.yaml'))
print(os.path.splitext(c['target_file'])[0])
")
LANG=$(python3 -c "
import yaml
c = yaml.safe_load(open('config.yaml'))
lang = c.get('languages', 'ko_KR')
print(lang.split(',')[0].strip() if isinstance(lang, str) else lang[0])
")

POT_FILE="pot/${TARGET_FILE}.pot"
JSONL_OUT="results/arena_dataset.jsonl"
ARENA_OUT="results/arena_results.json"
REPORT_OUT="results/arena_report_llm.html"

echo "============================================="
echo " OpenWebUI Arena Pipeline"
echo "============================================="
echo " 모델  : $MODELS"
echo " Judge : $JUDGE_MODEL"
echo " POT   : $POT_FILE"
echo " 언어  : $LANG"
echo "============================================="
echo ""

SKIP_TRANSLATE=false
if [ "$1" = "--skip-translate" ]; then
    SKIP_TRANSLATE=true
fi

mkdir -p results

# ── Step 1: 번역 ──────────────────────────────
if [ "$SKIP_TRANSLATE" = false ]; then
    echo "▶ Step 1: 번역"
    PYTHONPATH=src python3 src/translate.py --config config.yaml
    echo "Step 1 완료"
else
    echo "⏭  Step 1: 번역 건너뜀 (--skip-translate)"
fi
echo ""

# ── Step 2: PO → JSON 변환 ───────────────────
echo "▶ Step 2: JSONL 생성"
python3 src/po_to_json.py \
  --pot "$POT_FILE" \
  --po-dir po \
  --models "$MODELS" \
  --lang "$LANG" \
  --output results/arena_translations.json

# ── Step 3: LLM 판정 ──────────────────────────
echo "▶ Step 3: LLM 판정 (judge: $JUDGE_MODEL)"
python3 src/arena_score.py \
  --translations results/arena_translations.json \
  --judge-model "$JUDGE_MODEL" \
  --elo-data results/elo_matches.json \
  --submit-feedback \
  --output results/arena_feedback_llm.json

# ── Step 4: HTML 리포트 ────────────────────────
echo "▶ Step 4: HTML 리포트 생성"
python3 src/arena_report_generator.py \
    --elo-matches results/elo_matches.json \
    --translations results/arena_translations.json \
    --judge-model "$JUDGE_MODEL" \
    --output "$REPORT_OUT"
echo "Step 4 완료: $REPORT_OUT"
echo ""

echo "============================================="
echo "파이프라인 완료!"
echo "   리포트: $REPORT_OUT"
echo "============================================="