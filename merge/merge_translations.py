#!/usr/bin/env python3
import polib
import sys

if len(sys.argv) != 4:
    print(f"Usage: {sys.argv[0]} ORIGIN_PO LLM_PO OUT_PO")
    sys.exit(1)

origin_path, llm_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

# PO 파일 로드
origin = polib.pofile(origin_path)
llm = polib.pofile(llm_path)

# LLM_PO에서 msgid -> msgstr 매핑
llm_dict = {entry.msgid: entry.msgstr for entry in llm}

updated_count = 0
print("[*] 번역 삽입 전/후 비교:")

for entry in origin:
    if entry.msgid in llm_dict:
        llm_str = llm_dict[entry.msgid]
        # msgstr이 다르거나 빈 경우에만 갱신
        if entry.msgstr != llm_str:
            print(f"\n--- msgid: {entry.msgid}")
            print(f"- before: {entry.msgstr}")
            print(f"+ after : {llm_str}")
            entry.msgstr = llm_str
            updated_count += 1

# 결과 저장
origin.save(out_path)

print(f"\n[+] 총 {updated_count}개 항목이 업데이트되었습니다.")
print(f"[+] 결과 파일: {out_path}")