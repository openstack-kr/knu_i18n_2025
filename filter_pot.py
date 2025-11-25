#!/usr/bin/env python
import sys
import polib
import os
import argparse
from copy import deepcopy
from config_loader import load_config

def is_untranslated(entry: polib.POEntry) -> bool:
    """msgstr(또는 복수형 msgstr_plural) 중 하나라도 채워져 있으면 '번역됨'으로 판단."""
    # 헤더 건드리지 않음
    if entry.msgid == "":
        return False

    # 주석 처리된 엔트리는 무시
    if entry.obsolete:
        return False

    # 복수형일 때
    if entry.msgid_plural:
        return not any(s.strip() for s in entry.msgstr_plural.values())
    # 단수형일 때
    return not bool(entry.msgstr.strip())

def build_fallback_pot_path(translated_po_path):
    
    parts = translated_po_path.split("/")
    if len(parts) < 4:
        base, _ = os.path.splitext(translated_po_path)
        return base + ".pot"

    doc, lang, detail, filename = parts[-4:]
    pot_filename = filename.replace(".po", ".pot")

    return f"./data/target/{lang}/{pot_filename}"


def main(translated_po_path, out_pot_path="remaining.pot"):
    trans_exists = os.path.isfile(translated_po_path)

    # --------------------------------------------------------------
    # 0) 번역 파일 디렉토리 준비
    # --------------------------------------------------------------
    dir_path = os.path.dirname(translated_po_path)
    if dir_path and not os.path.isdir(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        print(f"[+] Created directory: {dir_path}")

    # --------------------------------------------------------------
    # 1) translated_po가 없으면 fallback POT 시도
    # --------------------------------------------------------------
    if not trans_exists:
        print(f"[!] Translated PO not found: {translated_po_path}")
        fallback_pot = build_fallback_pot_path(translated_po_path)
        print(f"[=] Trying fallback POT: {fallback_pot}")

        if not os.path.isfile(fallback_pot):
            print("[ERROR] Neither translated_po nor fallback POT exists.")
            open(out_pot_path, "w").close()
            print(f"[+] Created empty POT: {out_pot_path}")
            return

        # fallback POT 로드
        try:
            base_po = polib.pofile(fallback_pot)
        except:
            print("[ERROR] Fallback POT is invalid. Creating empty POT.")
            open(out_pot_path, "w").close()
            return

        # 미번역 엔트리만 추출
        result = polib.POFile()
        result.metadata = base_po.metadata

        count = 0
        for e in base_po:
            if is_untranslated(e):
                new_e = deepcopy(e)
                new_e.msgstr = ""
                new_e.msgstr_plural = {}
                result.append(new_e)
                count += 1

        result.save(out_pot_path)
        print(f"[+] Generated POT from fallback source: {out_pot_path}")
        print(f"[*] Untranslated entries: {count}")
        return

    # --------------------------------------------------------------
    # 2) 정상 동작: translated_po에서 미번역만 추출
    # --------------------------------------------------------------
    try:
        trans_po = polib.pofile(translated_po_path)
    except:
        print("[ERROR] Cannot read translated_po. Creating empty POT.")
        open(out_pot_path, "w").close()
        return

    result = polib.POFile()
    result.metadata = trans_po.metadata

    count = 0
    for e in trans_po:
        if is_untranslated(e):
            new_e = deepcopy(e)
            new_e.msgstr = ""
            new_e.msgstr_plural = {}
            result.append(new_e)
            count += 1

    result.save(out_pot_path)
    print(f"[+] POT saved: {out_pot_path}")
    print(f"[*] Untranslated entries: {count}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.yaml")
    args = parser.parse_args()

    cfg = load_config(args.config)
    
    languages = cfg.get("languages")

    if isinstance(languages, list):
        # 지금은 한 개만 쓴다고 가정하고 첫 번째 사용
        lang = languages[0]
    else:
        lang = languages

    files_cfg = cfg["files"]
    
    # config에서 파일명만 받음
    target_file = files_cfg["target_file"]
    # target_file (po, pot) 확장자 분리
    target_file_name, _ = os.path.splitext(target_file)
    
    # 자동으로 ./data/target 아래에서 찾도록 경로 구성
    trans_po = os.path.join(f"./data/target/{lang}", target_file)
    pot_dir = "./pot"
    os.makedirs(pot_dir, exist_ok=True)
    
    out_pot = os.path.join(pot_dir, f"{target_file_name}.pot")

    os.makedirs(pot_dir, exist_ok=True)
    main(trans_po, out_pot)