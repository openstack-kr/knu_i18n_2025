#!/usr/bin/env python3
import polib
import sys
import os

if len(sys.argv) != 4:
    print(f"Usage: {sys.argv[0]} ORIGIN_PO LLM_PO OUT_PO")
    sys.exit(1)

origin_path, llm_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

# PO 파일 로드
origin = polib.pofile(origin_path)
llm = polib.pofile(llm_path)

# ORIGIN_PO 헤더(metadata) 백업
original_metadata = origin.metadata.copy()

# LLM_PO에서 msgid -> POEntry 매핑
llm_dict = {entry.msgid: entry for entry in llm}

updated_count = 0
print("[*] 번역 삽입 전/후 비교:")

for entry in origin:
    if entry.msgid in llm_dict:
        llm_entry = llm_dict[entry.msgid]

        # ORIGIN_PO에 이미 번역이 있으면 덮어쓰지 않음
        if not entry.msgstr.strip() and llm_entry.msgstr.strip():
            print(f"\n--- msgid: {entry.msgid}")
            print(f"- before: {entry.msgstr}")
            print(f"+ after : {llm_entry.msgstr}")

            # msgstr 갱신
            entry.msgstr = llm_entry.msgstr

            # comment, tcomment, flags, previous comments 유지
            if hasattr(llm_entry, 'comment') and llm_entry.comment:
                entry.comment = llm_entry.comment
            if hasattr(llm_entry, 'tcomment') and llm_entry.tcomment:
                entry.tcomment = llm_entry.tcomment
            if hasattr(llm_entry, 'flags') and llm_entry.flags:
                entry.flags = llm_entry.flags

            # polib >= 1.1.0에서는 entry.references 존재
            if hasattr(llm_entry, 'references') and llm_entry.references:
                entry.references = llm_entry.references

            updated_count += 1

# 저장 전에 헤더 복원
origin.metadata = original_metadata

# 결과 저장
os.makedirs(os.path.dirname(out_path), exist_ok=True)
origin.save(out_path)

print(f"\n[+] 총 {updated_count}개 항목이 업데이트되었습니다.")
print(f"[+] 결과 파일: {out_path}")
