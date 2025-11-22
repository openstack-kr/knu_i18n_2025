#!/bin/bash
set -e

MODEL=${1:-"llama3.2:3b"}
LANG=ko_KR

# 기존 번역 포함된 원본 PO
ORIGIN_PO="../data/target/nova/$LANG/LC_MESSAGES/nova.po"

# LLM이 번역한 PO 파일
LLM_PO="../po/$MODEL/$LANG/nova_ex.po"

# 최종 병합 파일
OUT_PO="../result/$MODEL/$LANG/nova.po"

# 병합 스크립트
MERGE_SCRIPT="merge_translations.py"

echo "[*] ORIGIN_PO:   $ORIGIN_PO"
echo "[*] LLM_PO   :   $LLM_PO"
echo "[*] OUT_PO   :   $OUT_PO"
echo

mkdir -p "$(dirname "$OUT_PO")"

python "$MERGE_SCRIPT" \
    "$ORIGIN_PO" \
    "$LLM_PO" \
    "$OUT_PO"

echo
echo "[+] 병합 완료!"
echo "[+] 결과 파일: $OUT_PO"