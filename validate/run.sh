set -euo pipefail

DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY=${PYTHON:-python}

A_DEFAULT="$DIR/../po-example/ko_KR/i18n-docs-source-locale.po"
B_DEFAULT="$DIR/../po/llama3.2:3b/ko_KR/i18n-docs-source-locale-ko_KR.po"

JSON_DIR="$DIR/json"
OUT_BASENAME="${OUT_BASENAME:-result_ko}"   # 파일명 기본값: result_ko
TS_SUFFIX="${TS_SUFFIX:-}"                  # 1이면 타임스탬프 붙임
MODEL="${MODEL:-BM-K/KoSimCSE-roberta-multitask}"

mkdir -p "$JSON_DIR"

OUT_FILE="$JSON_DIR/${OUT_BASENAME}.json"
if [[ "$TS_SUFFIX" == "1" ]]; then
  OUT_FILE="$JSON_DIR/${OUT_BASENAME}_$(date +%Y%m%d-%H%M).json"
fi

A="${A:-$A_DEFAULT}"
B="${B:-$B_DEFAULT}"

[[ -f "$A" ]] || { echo "Missing --a file: $A" >&2; exit 1; }
[[ -f "$B" ]] || { echo "Missing --b file: $B" >&2; exit 1; }

exec "$PY" "$DIR/score.py" \
  --a "$A" \
  --b "$B" \
  --out "$OUT_FILE" \
  --model "$MODEL" \
  --only-translated \
  --normalize-text \
  "$@"
