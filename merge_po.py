#!/usr/bin/env python3
import polib
import os
from config_loader import load_config
import argparse

parser = argparse.ArgumentParser()
parser.add_argument(
    "--config",
    default="config.yaml",
    help="Path to config YAML (default: config.yaml)",
)

args = parser.parse_args()
cfg = load_config("config.yaml")
files_cfg = cfg.get("files", {})
model = cfg["llm"]["model"]
project = cfg["git"]["project"] 

for lang in cfg["languages"]:
    
    target_file = files_cfg["target_file"]
    target_file_path = os.path.join(f"./data/target/{lang}", target_file)
    target_file_name, _ = os.path.splitext(target_file)
    # PO 파일 로드
    target_file = polib.pofile(target_file_path)
    llm_path = f"./po/{model}/{lang}/{target_file_name}.po"
    llm = polib.pofile(llm_path)
    out_path = f"./data/result/{lang}/{target_file_name}.po"
    
    # standard_po 헤더(metadata) 백업
    original_metadata = target_file.metadata.copy()

    # LLM_PO에서 msgid -> POEntry 매핑
    llm_dict = {entry.msgid: entry for entry in llm}

    updated_count = 0
    print(f"[Lang: {lang}] [*] 번역 삽입 전/후 비교:")

    for entry in target_file:
        if entry.msgid in llm_dict:
            llm_entry = llm_dict[entry.msgid]

            # standard_po에 이미 번역이 있으면 덮어쓰지 않음
            if not entry.msgstr.strip() and llm_entry.msgstr.strip():
                print(f"[Lang: {lang}]\n--- msgid: {entry.msgid}")
                print(f"[Lang: {lang}]- before: {entry.msgstr}")
                print(f"[Lang: {lang}]+ after : {llm_entry.msgstr}")

                # msgstr 갱신
                entry.msgstr = llm_entry.msgstr

                # comment, tcomment, flags, previous comments 유지
                if hasattr(llm_entry, 'comment') and llm_entry.comment:
                    entry.comment = llm_entry.comment
                if hasattr(llm_entry, 'tcomment') and llm_entry.tcomment:
                    entry.tcomment = llm_entry.tcomment
                if hasattr(llm_entry, 'flags') and llm_entry.flags:
                    entry.flags = llm_entry.flags

                if hasattr(llm_entry, 'references') and llm_entry.references:
                    entry.references = llm_entry.references

                updated_count += 1

    # 저장 전에 헤더 복원
    target_file.metadata = original_metadata

    # 결과 저장
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    target_file.save(out_path)

    print(f"[Lang: {lang}]\n[+] 총 {updated_count}개 항목이 업데이트되었습니다.")
    print(f"[Lang: {lang}][+] 결과 파일: {out_path}")
