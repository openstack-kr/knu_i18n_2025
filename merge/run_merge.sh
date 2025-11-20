#!/bin/bash
set -e

MODEL=${1:-"llama3.2:3b"}
LANG=ru

# 기존 번역 포함된 원본 PO
ORIGIN_PO="../filter/nova/$LANG/LC_MESSAGES/nova.po"

# 미번역 msgid 추출 파일
POT_FILE="../filter/nova_ex.pot"

# LLM이 번역한 PO 파일
LLM_PO="../po/$MODEL/$LANG/nova_ex.po"

# 최종 병합 파일
OUT_PO="merge/$MODEL/$LANG/nova.po"

# 병합 스크립트
MERGE_SCRIPT="merge_translations.py"

echo "[*] ORIGIN_PO:   $ORIGIN_PO"
echo "[*] POT_FILE :   $POT_FILE"
echo "[*] LLM_PO   :   $LLM_PO"
echo "[*] OUT_PO   :   $OUT_PO"
echo

# 첫 줄 주석 처리 안전하게
if [ -f "$LLM_PO" ]; then
    sed -i '1s/^/# /' "$LLM_PO"
else
    echo "LLM_PO file not found: $LLM_PO"
    exit 1
fi

python "$MERGE_SCRIPT" \
    "$ORIGIN_PO" \
    "$POT_FILE" \
    "$LLM_PO" \
    "$OUT_PO"

echo
echo "[+] 병합 완료!"
echo "[+] 결과 파일: $OUT_PO"