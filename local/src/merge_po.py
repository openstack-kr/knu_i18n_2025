#!/usr/bin/env python3
import polib
import os
from utils import is_untranslated, load_config
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config YAML (default: config.yaml)",
    )

    args = parser.parse_args()
    cfg = load_config(args.config)

    # Get configuration
    model = cfg["llm"]["model"]
    target_file = cfg["target_file"]
    target_file_name, _ = os.path.splitext(target_file)

    for lang in cfg["languages"]:
        # Local mode: original PO is in ./data/target/{lang}
        target_file_path = os.path.join(f"./data/target/{lang}", target_file)

        if not os.path.isfile(target_file_path):
            print(
                f"[merge_po] ERROR: Target file not found: {target_file_path}")
            continue

        print(f"[merge_po] Using target file: {target_file_path}")

        # PO 파일 로드
        original_po = polib.pofile(target_file_path)
        llm_path = f"./po/{model}/{lang}/{target_file_name}.po"

        if not os.path.isfile(llm_path):
            print(f"[merge_po] ERROR: AI translation not found: {llm_path}")
            print(f"[merge_po] Please run translation first!")
            continue

        llm = polib.pofile(llm_path)
        out_path = f"./data/result/{lang}/{target_file_name}.po"

        # 헤더(metadata) 백업
        original_metadata = original_po.metadata.copy()

        # LLM_PO에서 msgid -> POEntry 매핑
        llm_dict = {entry.msgid: entry for entry in llm}

        updated_count = 0
        print(f"[Lang: {lang}] [*] 번역 삽입 전/후 비교:")

        for entry in original_po:
            if entry.msgid in llm_dict:
                llm_entry = llm_dict[entry.msgid]

                # 이미 번역이 있으면 덮어쓰지 않음
                if is_untranslated(entry) and llm_entry.msgstr.strip():
                    print(f"[Lang: {lang}]\n--- msgid: {entry.msgid}")
                    print(f"[Lang: {lang}]- before: {entry.msgstr}")
                    print(f"[Lang: {lang}]+ after : {llm_entry.msgstr}")

                    entry.msgstr = llm_entry.msgstr

                    for attr in ('comment', 'tcomment', 'flags', 'references'):
                        val = getattr(llm_entry, attr, None)
                        if val:
                            setattr(entry, attr, val)

                    updated_count += 1

        # 헤더 복원
        original_po.metadata = original_metadata

        # 결과 저장
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        original_po.save(out_path)

        print(f"[Lang: {lang}]\n[+] 총 {updated_count}개 항목이 업데이트되었습니다.")
        print(f"[Lang: {lang}][+] 결과 파일: {out_path}")


if __name__ == "__main__":
    main()
