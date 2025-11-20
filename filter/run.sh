#!/bin/bash
set -e  # 오류 발생 시 즉시 종료

# 입력 파일
SRC_PO="nova/en_AU/LC_MESSAGES/nova.po"
TRANS_PO="nova/ru/LC_MESSAGES/nova.po"

# 출력 파일
OUT_PO="trans/nova_ex.po"
OUT_POT="nova_ex.pot"

echo "[*] 원문 PO : $SRC_PO"
echo "[*] 번역 PO : $TRANS_PO"
echo "[*] 출력 PO : $OUT_PO"
echo "[*] 출력 POT: $OUT_POT"
echo

# 파이썬 스크립트 실행
python filter_to_pot.py "$SRC_PO" "$TRANS_PO" "$OUT_PO" "$OUT_POT"

echo
echo "[+] 완료!"
echo "    생성된 파일 확인:"
echo "    - $OUT_PO"
echo "    - $OUT_POT"